#!/usr/bin/env python3
"""
Raito Pricing Engine — Single Source of Truth for all price lookups.

Every module that needs a price MUST call into this engine.
No hardcoded price literals anywhere else in the codebase.

Three-tier lookup (highest priority first):
  1. master_data JSONB pricing table (DB — editable via MD tab)
  2. Ma'ayan price DB Excel file (for chain-specific Ma'ayan prices)
  3. Hardcoded fallback dicts below (legacy, used when DB unavailable)

Two-tier public API:
  get_b2b_price(sku)                → flat list price (SP, BO views)
  get_customer_price(sku, customer, distributor)  → negotiated per-customer price (CC view)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
import pandas as pd

log = logging.getLogger(__name__)

# ── Canonical B2B List Prices ─────────────────────────────────────────────────
# These are the standard wholesale (B2B, ex-VAT) selling prices.
# dream_cake  = Piece of Cake manufacturer (legacy, discontinued)
# dream_cake_2 = Biscotti manufacturer (active)

_B2B_PRICES: dict[str, float] = {
    'chocolate':    13.8,
    'vanilla':      13.8,
    'mango':        13.8,
    'pistachio':    13.8,
    'magadat':      13.8,
    'dream_cake':   81.1,
    'dream_cake_2': 80.0,
}

# ── Production Costs ──────────────────────────────────────────────────────────

PRODUCTION_COST: dict[str, float] = {
    'chocolate':    6.5,
    'vanilla':      6.5,
    'mango':        6.5,
    'pistachio':    7.1,
    'dream_cake':   53.5,
    'dream_cake_2': 58.0,
}

# ── Customer-Specific Prices (CC view) ────────────────────────────────────────
# Per-customer negotiated selling prices for Ma'ayan / Icedream chains.
# Keyed by English customer name (as returned by config.extract_customer_name).
# If a customer is missing here, falls back to B2B list price.

_CUSTOMER_PRICES: dict[str, float] = {
    'AMPM':           12.39,
    'Alonit':         12.27,
    'Delek Menta':    12.74,
    'Tiv Taam':       14.2,
    'Private Market': 14.1,
    'Paz Yellow':     11.0,
    'Paz Super Yuda': 11.0,
    'Sonol':          14.0,
}

# ── Ma'ayan Price-DB integration ──────────────────────────────────────────────
# Maps raw Hebrew chain names from Ma'ayan data → keys in the external price DB.
# This table is used by load_mayyan_price_table() to look up actual invoiced
# prices from the latest 'price db*.xlsx' export.

_MAAYAN_CHAIN_TO_PRICEDB: dict[str, str] = {
    'דור אלון':                    'AMPM',
    'שוק פרטי':                    'שוק פרטי',
    'דלק מנטה':                    'דלק',
    'סונול':                       'סונול',
    'פז ילו':                      'פז יילו',
    'פז יילו':                     'פז יילו',
    'פז חברת נפט- סופר יודה':      'פז סופר יודה',
    'שפר את אלי לוי בע"מ':         'אלונית',
}

# Hebrew product names in price DB → internal SKU keys
_PRICEDB_PRODUCT_MAP: dict[str, str] = {
    'גלידת חלבון וניל':            'vanilla',
    'גלידת חלבון מנגו':            'mango',
    'גלידת חלבון פיסטוק':          'pistachio',
    'גלידת חלבון שוקולד לוז':      'chocolate',
}

# Module-level cache for the loaded price table
_price_table_cache: Optional[dict] = None

# ═══════════════════════════════════════════════════════════════════════════════
# Master Data JSONB Integration
# ═══════════════════════════════════════════════════════════════════════════════
# On first access, loads pricing records from the master_data JSONB table.
# Builds three lookup structures:
#   _md_sale_prices: {(sku, customer, distributor): sale_price}
#   _md_costs:       {sku: cost}  (from any pricing row for that SKU)
#   _md_loaded:      True once loaded (even if DB unavailable)

_md_sale_prices: dict[tuple[str, str, str], float] = {}
_md_costs: dict[str, float] = {}
_md_loaded: bool = False


def _load_md_pricing() -> None:
    """Load pricing from master_data JSONB and populate lookup dicts.

    Overrides hardcoded _B2B_PRICES, PRODUCTION_COST, and _CUSTOMER_PRICES
    with values from the MD tab. Falls back silently if DB is unavailable.
    """
    global _md_sale_prices, _md_costs, _md_loaded
    if _md_loaded:
        return
    _md_loaded = True

    try:
        import os
        import psycopg2
        url = os.environ.get('DATABASE_URL', '')
        if not url:
            log.debug("pricing_engine: no DATABASE_URL, using hardcoded fallbacks")
            return
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("SELECT data FROM master_data WHERE entity = 'pricing'")
        row = cur.fetchone()
        conn.close()
        if not row or not row[0]:
            return

        records = row[0]  # psycopg2 auto-decodes JSONB → Python list
        if isinstance(records, str):
            import json
            records = json.loads(records)

        for r in records:
            sku = r.get('sku_key', '')
            customer = r.get('customer', '')
            distributor = r.get('distributor', '')
            sale_price = r.get('sale_price')
            cost = r.get('cost')

            if not sku:
                continue

            # Build (sku, customer, distributor) → sale_price lookup
            if sale_price is not None:
                try:
                    sp = float(sale_price)
                    if sp > 0:
                        _md_sale_prices[(sku, customer, distributor)] = sp
                except (ValueError, TypeError):
                    pass

            # Build sku → cost lookup (take first non-null cost per SKU)
            if cost is not None and sku not in _md_costs:
                try:
                    c = float(cost)
                    if c > 0:
                        _md_costs[sku] = c
                except (ValueError, TypeError):
                    pass

        log.info("pricing_engine: loaded %d sale prices, %d costs from master_data",
                 len(_md_sale_prices), len(_md_costs))

    except Exception as e:
        log.warning("pricing_engine: could not load from master_data: %s", e)


def reload_md_pricing() -> None:
    """Force reload of MD pricing (called after MD tab edits)."""
    global _md_loaded
    _md_loaded = False
    _md_sale_prices.clear()
    _md_costs.clear()
    _load_md_pricing()


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def get_b2b_price(sku: str) -> float:
    """Return the flat B2B list price for a SKU.

    Used by SP tab, BO tab, and any module that doesn't need customer-level
    price differentiation.

    Lookup order:
      1. MD pricing (any row for this SKU — picks the first match)
      2. Hardcoded _B2B_PRICES fallback

    Raises KeyError if sku is unknown in both sources.
    """
    _load_md_pricing()
    # Check MD: find any sale_price for this SKU (first match)
    for (s, c, d), price in _md_sale_prices.items():
        if s == sku:
            return price
    if sku not in _B2B_PRICES:
        raise KeyError(
            f"Unknown SKU '{sku}' — add it to pricing_engine._B2B_PRICES"
        )
    return _B2B_PRICES[sku]


def get_b2b_price_safe(sku: str, fallback: Optional[float] = None) -> float:
    """Like get_b2b_price but returns fallback instead of raising.

    If fallback is None and sku is unknown, returns 0.0.
    """
    _load_md_pricing()
    for (s, c, d), price in _md_sale_prices.items():
        if s == sku:
            return price
    return _B2B_PRICES.get(sku, fallback if fallback is not None else 0.0)


def get_customer_price(sku: str, customer_en: str, distributor: str = '') -> float:
    """Return the negotiated per-customer price for a SKU.

    Lookup order:
      1. MD pricing — exact match (sku, customer, distributor)
      2. MD pricing — (sku, customer, any distributor)
      3. Legacy _CUSTOMER_PRICES dict (Turbo SKUs only)
      4. Fall back to B2B list price

    Args:
        sku: Internal product key (e.g. 'chocolate', 'dream_cake_2').
        customer_en: English customer name (as returned by extract_customer_name).
        distributor: Distributor key or name (optional, for exact match).
    """
    _load_md_pricing()

    # 1. Exact match: (sku, customer, distributor)
    if distributor:
        key = (sku, customer_en, distributor)
        if key in _md_sale_prices:
            return _md_sale_prices[key]

    # 2. Partial match: (sku, customer, any distributor)
    for (s, c, d), price in _md_sale_prices.items():
        if s == sku and c == customer_en:
            return price

    # 3. Legacy customer prices (Turbo SKUs only)
    if customer_en in _CUSTOMER_PRICES and sku not in ('dream_cake', 'dream_cake_2'):
        return _CUSTOMER_PRICES[customer_en]

    return get_b2b_price(sku)


def get_production_cost(sku: str) -> float:
    """Return production cost for a SKU. Returns 0.0 if unknown.

    Checks MD pricing first, falls back to hardcoded PRODUCTION_COST.
    """
    _load_md_pricing()
    if sku in _md_costs:
        return _md_costs[sku]
    return PRODUCTION_COST.get(sku, 0.0)


def get_gross_margin(sku: str, customer_en: Optional[str] = None) -> float:
    """Return gross margin (price - cost) for a SKU, optionally customer-specific."""
    if customer_en:
        price = get_customer_price(sku, customer_en)
    else:
        price = get_b2b_price(sku)
    cost = get_production_cost(sku)
    return price - cost


def all_b2b_prices() -> dict[str, float]:
    """Return a copy of the full B2B price table. For JS injection."""
    return dict(_B2B_PRICES)


def all_customer_prices() -> dict[str, float]:
    """Return a copy of the customer price table. For JS injection."""
    return dict(_CUSTOMER_PRICES)


# ═══════════════════════════════════════════════════════════════════════════════
# Ma'ayan Price-DB File Integration
# ═══════════════════════════════════════════════════════════════════════════════

def load_mayyan_price_table(data_dir: Optional[Path] = None) -> dict:
    """Load the latest price DB file and return {product: {chain: price}}.

    Falls back to B2B list prices for any missing product/chain combo.
    Results are cached after first load.
    """
    global _price_table_cache
    if _price_table_cache is not None:
        return _price_table_cache

    if data_dir is None:
        from config import DATA_DIR
        data_dir = DATA_DIR

    price_dir = data_dir / 'price data'
    if not price_dir.exists():
        _price_table_cache = {}
        return _price_table_cache

    candidates = sorted(
        [f for f in price_dir.glob('price db*.xlsx') if not f.name.startswith('~')],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        _price_table_cache = {}
        return _price_table_cache

    try:
        _probe = pd.read_excel(candidates[0], header=None)
        header_row = 0
        for _i, _row in _probe.iterrows():
            _vals = [str(v) for v in _row.values]
            if any('לקוח' in v for v in _vals) and any('מחיר' in v for v in _vals):
                header_row = _i
                break
        df = pd.read_excel(candidates[0], header=header_row)
        price_col = next((c for c in df.columns if 'מחיר' in str(c) and 'מכירה' in str(c)), None)
        cust_col = next((c for c in df.columns if 'לקוח' in str(c)), None)
        prod_col = next((c for c in df.columns if 'מוצרים' in str(c) or 'פריט' in str(c)), None)
        dist_col = next((c for c in df.columns if 'מפיץ' in str(c)), None)
        if not all([price_col, cust_col, prod_col, dist_col]):
            _price_table_cache = {}
            return _price_table_cache

        may_df = df[df[dist_col].astype(str).str.contains('מעיין', na=False)]

        table: dict[str, dict[str, float]] = {}
        for _, row in may_df.iterrows():
            prod_key = _PRICEDB_PRODUCT_MAP.get(str(row[prod_col]).strip())
            if not prod_key:
                continue
            cust = str(row[cust_col]).strip()
            price = float(row[price_col]) if row[price_col] else 0
            if prod_key not in table:
                table[prod_key] = {}
            table[prod_key][cust] = price

        _price_table_cache = table
        return _price_table_cache
    except Exception:
        _price_table_cache = {}
        return _price_table_cache


def get_mayyan_chain_price(price_table: dict, chain_raw: str, sku: str) -> float:
    """Look up actual invoiced price for a Ma'ayan chain + product.

    Three-tier lookup:
      1. master_data JSONB via get_customer_price (SSOT)
      2. Ma'ayan price-DB Excel file (legacy fallback)
      3. B2B list price (last resort)
    """
    _load_md_pricing()
    chain_str = str(chain_raw).strip()

    # 1. Try master_data JSONB — resolve Hebrew chain to English customer name
    try:
        from config import extract_customer_name
        customer_en = extract_customer_name(chain_str)
        if customer_en:
            for (s, c, d), price in _md_sale_prices.items():
                if s == sku and c == customer_en:
                    return price
    except ImportError:
        pass

    # 2. Fallback: Ma'ayan price-DB Excel file
    pricedb_cust = _MAAYAN_CHAIN_TO_PRICEDB.get(chain_str)
    if pricedb_cust and sku in price_table:
        price = price_table[sku].get(pricedb_cust)
        if price:
            return price

    # 3. Last resort: B2B list price
    return get_b2b_price_safe(sku)


def reset_cache():
    """Clear the price table cache. Useful for testing."""
    global _price_table_cache
    _price_table_cache = None


# ═══════════════════════════════════════════════════════════════════════════════
# JS Code Generation Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def js_brand_rev_function(turbo_skus: list[str] | None = None) -> str:
    """Generate the JS spBrandRev() function with prices from the engine.

    This replaces hardcoded `* 13.8` and `* 80.0` in SP dashboard JS.
    """
    turbo_price = get_b2b_price('chocolate')  # All Turbo SKUs share the same price
    dc_price = get_b2b_price('dream_cake_2')  # Active DC SKU

    return (
        f"function spBrandRev(s) {{\n"
        f"    if (brandFilter === 'turbo') return (s.choc + s.van + s.mango + s.pist) * {turbo_price};\n"
        f"    if (brandFilter === 'danis') return s.dc * {dc_price};\n"
        f"    return s.rev;\n"
        f"  }}"
    )


def js_price_constants() -> str:
    """Generate JS constants for all B2B prices.

    Returns a block like:
      const TURBO_PRICE = 13.8;
      const DC_PRICE = 80.0;
    """
    turbo = get_b2b_price('chocolate')
    dc = get_b2b_price('dream_cake_2')
    dc_legacy = get_b2b_price('dream_cake')
    return (
        f"const TURBO_PRICE = {turbo};\n"
        f"const DC_PRICE = {dc};\n"
        f"const DC_LEGACY_PRICE = {dc_legacy};"
    )
