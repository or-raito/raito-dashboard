#!/usr/bin/env python3
"""
Validation layer for Master Data write operations.

Phase 2 SSOT migration (2026-04-19):
  Every POST/PUT to /api/<entity> passes through validate_record() before
  the write is committed. Rules enforce:

  1. Required fields — entity-specific mandatory columns
  2. FK references — e.g. a product's brand_key must exist in brands
  3. Assortment rules — dream_cake_2 only via Biscotti; turbo SKUs only
     via Icedream or Ma'ayan
  4. Gated field warnings — cascading changes (e.g. renaming a brand_key)
     return a warning that the client must confirm before re-submitting

Usage in db_dashboard.py:
    from md_validation import validate_record
    errors, warnings = validate_record('products', record, existing_data, action='create')
    if errors:
        return jsonify({'errors': errors}), 422
    if warnings and not request.args.get('confirmed'):
        return jsonify({'warnings': warnings, 'confirm_required': True}), 409
"""

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Required Fields per Entity
# ═══════════════════════════════════════════════════════════════════════════════

_REQUIRED: dict[str, list[str]] = {
    'brands':        ['key', 'name'],
    'products':      ['sku_key', 'name_en', 'brand', 'status'],
    'manufacturers': ['key', 'name'],
    'distributors':  ['key', 'name'],
    'customers':     ['key', 'name_he', 'name_en'],
    'logistics':     ['product_key'],
    'pricing':       ['sku_key', 'customer'],
}

# Fields that are identity / FK — changing them cascades and needs confirmation
_GATED_FIELDS: dict[str, list[str]] = {
    'brands':        ['key'],
    'products':      ['sku_key', 'brand'],
    'manufacturers': ['key'],
    'distributors':  ['key'],
    'customers':     ['key'],
    'logistics':     ['product_key'],
    'pricing':       ['sku_key', 'customer', 'distributor'],
}

# Valid status values per entity (lowercased for comparison)
_VALID_STATUSES: dict[str, set[str]] = {
    'products': {'active', 'new', 'discontinued', 'planned', 'seasonal'},
    'brands':   {'active', 'inactive', 'planned'},
    'customers': {'active', 'inactive', 'prospect'},
}

# Assortment: which brands can flow through which distributors
_ASSORTMENT_RULES: dict[str, set[str]] = {
    'icedream': {'turbo', 'danis'},
    'mayyan':   {'turbo'},
    'biscotti': {'danis'},
}


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def validate_record(
    entity: str,
    record: dict,
    all_data: dict[str, list],
    action: str = 'create',
    old_record: Optional[dict] = None,
) -> tuple[list[str], list[str]]:
    """Validate a record before writing.

    Args:
        entity:     Entity name ('products', 'brands', etc.)
        record:     The new/updated record dict
        all_data:   Dict of all entities' current data {entity: [rows...]}
        action:     'create' | 'update' | 'delete'
        old_record: The existing record (for updates — used for gated field checks)

    Returns:
        (errors, warnings) — errors block the write; warnings require confirmation.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if action == 'delete':
        # Deletion: check for FK references pointing to this record
        _check_delete_references(entity, record, all_data, errors)
        return errors, warnings

    # 1. Required fields
    _check_required(entity, record, errors)

    # 2. Status values
    _check_status(entity, record, errors)

    # 3. FK references
    _check_fk_references(entity, record, all_data, errors)

    # 4. Assortment rules (pricing entity)
    _check_assortment(entity, record, all_data, errors)

    # 5. Gated fields (update only)
    if action == 'update' and old_record:
        _check_gated_fields(entity, record, old_record, all_data, warnings)

    return errors, warnings


# ═══════════════════════════════════════════════════════════════════════════════
# Validators
# ═══════════════════════════════════════════════════════════════════════════════

def _check_required(entity: str, record: dict, errors: list[str]) -> None:
    """Ensure all required fields are present and non-empty."""
    for field in _REQUIRED.get(entity, []):
        val = record.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            errors.append(f"Required field '{field}' is missing or empty.")


def _check_status(entity: str, record: dict, errors: list[str]) -> None:
    """Validate status field if the entity has constrained status values."""
    valid = _VALID_STATUSES.get(entity)
    if not valid:
        return
    status = (record.get('status') or '').strip().lower()
    if status and status not in valid:
        errors.append(
            f"Invalid status '{record.get('status')}'. "
            f"Allowed: {', '.join(sorted(valid))}."
        )


def _check_fk_references(entity: str, record: dict,
                         all_data: dict[str, list], errors: list[str]) -> None:
    """Check that FK fields reference existing records."""
    # Products → Brands
    if entity == 'products':
        brand_val = record.get('brand_key', '') or record.get('brand', '')
        if brand_val:
            brands = all_data.get('brands', [])
            brand_keys = {b.get('key', '') or b.get('brand_key', '') for b in brands}
            if brand_val not in brand_keys:
                errors.append(
                    f"brand '{brand_val}' not found in brands. "
                    f"Available: {', '.join(sorted(brand_keys))}."
                )

        manufacturer = record.get('manufacturer', '')
        if manufacturer:
            mfrs = all_data.get('manufacturers', [])
            mfr_keys = {m.get('key', '') for m in mfrs}
            if manufacturer not in mfr_keys:
                errors.append(
                    f"manufacturer '{manufacturer}' not found in manufacturers. "
                    f"Available: {', '.join(sorted(mfr_keys))}."
                )

    # Pricing → Products + Customers + Distributors
    if entity == 'pricing':
        sku = record.get('sku_key', '')
        if sku:
            products = all_data.get('products', [])
            sku_keys = {p.get('sku_key', '') for p in products}
            if sku not in sku_keys:
                errors.append(f"sku_key '{sku}' not found in products.")

        customer = record.get('customer', '')
        if customer:
            customers = all_data.get('customers', [])
            # Match by key, name_he, or name_en (form dropdowns may send any)
            cust_all = set()
            for c in customers:
                cust_all.add(c.get('key', ''))
                cust_all.add(c.get('name_he', ''))
                cust_all.add(c.get('name_en', ''))
            cust_all.discard('')
            if customer not in cust_all:
                errors.append(f"customer '{customer}' not found in customers.")

        distributor = record.get('distributor', '')
        if distributor:
            dists = all_data.get('distributors', [])
            # Match by key or name
            dist_all = set()
            for d in dists:
                dist_all.add(d.get('key', ''))
                dist_all.add(d.get('name', ''))
            dist_all.discard('')
            if distributor not in dist_all:
                errors.append(f"distributor '{distributor}' not found in distributors.")

    # Logistics → Products
    if entity == 'logistics':
        pk = record.get('product_key', '')
        if pk:
            products = all_data.get('products', [])
            sku_keys = {p.get('sku_key', '') for p in products}
            if pk not in sku_keys:
                errors.append(f"product_key '{pk}' not found in products.")

    # Customers → Distributors
    if entity == 'customers':
        dist = record.get('distributor', '')
        if dist:
            dists = all_data.get('distributors', [])
            dist_keys = {d.get('key', '') for d in dists}
            if dist not in dist_keys:
                errors.append(f"distributor '{dist}' not found in distributors.")


def _check_assortment(entity: str, record: dict,
                      all_data: dict[str, list], errors: list[str]) -> None:
    """Enforce brand ↔ distributor assortment rules on pricing records."""
    if entity != 'pricing':
        return

    distributor = (record.get('distributor') or '').strip().lower()
    sku_key = record.get('sku_key', '')
    if not distributor or not sku_key:
        return

    # Look up the product's brand
    products = all_data.get('products', [])
    brand = ''
    for p in products:
        if p.get('sku_key') == sku_key:
            brand = (p.get('brand') or p.get('brand_key') or '').strip().lower()
            break

    if not brand:
        return  # Unknown product — FK check already catches this

    allowed_brands = _ASSORTMENT_RULES.get(distributor)
    if allowed_brands is not None and brand not in allowed_brands:
        errors.append(
            f"Assortment violation: '{sku_key}' (brand={brand}) cannot be "
            f"distributed via '{distributor}'. "
            f"Allowed brands for {distributor}: {', '.join(sorted(allowed_brands))}."
        )


def _check_gated_fields(entity: str, record: dict, old_record: dict,
                        all_data: dict[str, list], warnings: list[str]) -> None:
    """Warn when identity/FK fields are being changed (cascading impact)."""
    gated = _GATED_FIELDS.get(entity, [])
    for field in gated:
        old_val = old_record.get(field, '')
        new_val = record.get(field, '')
        if str(old_val) != str(new_val) and old_val:
            warnings.append(
                f"Changing '{field}' from '{old_val}' to '{new_val}' is a "
                f"cascading change. Other entities referencing '{old_val}' "
                f"will NOT be updated automatically."
            )


def _check_delete_references(entity: str, record: dict,
                             all_data: dict[str, list],
                             errors: list[str]) -> None:
    """Block deletion if other entities reference this record."""
    pk_map = {
        'brands':        'key',
        'products':      'sku_key',
        'manufacturers': 'key',
        'distributors':  'key',
        'customers':     'key',
    }
    pk_field = pk_map.get(entity)
    if not pk_field:
        return
    pk_val = record.get(pk_field, '')
    if not pk_val:
        return

    # Check which entities reference this one
    refs = _REFERENCE_MAP.get(entity, [])
    for ref_entity, ref_field in refs:
        items = all_data.get(ref_entity, [])
        referencing = [r for r in items if r.get(ref_field) == pk_val]
        if referencing:
            errors.append(
                f"Cannot delete {entity} '{pk_val}': {len(referencing)} "
                f"{ref_entity} record(s) reference it via '{ref_field}'."
            )


# Entity → [(referencing_entity, field_that_points_here)]
_REFERENCE_MAP: dict[str, list[tuple[str, str]]] = {
    'brands':        [('products', 'brand'), ('products', 'brand_key')],
    'products':      [('pricing', 'sku_key'), ('logistics', 'product_key')],
    'manufacturers': [('products', 'manufacturer')],
    'distributors':  [('pricing', 'distributor'), ('customers', 'distributor')],
    'customers':     [('pricing', 'customer')],
}
