#!/usr/bin/env python3
"""
Raito Product & Customer Registry — Single Source of Truth for business entities.

This module centralizes:
  - Product definitions, brand memberships, and category classifications
  - Customer hierarchy: Customer → Sub-customers (Branches / Sale Points)
  - Distributor metadata

Every module that needs to classify a product, look up a brand membership,
or resolve a customer name MUST use this registry. Adding a new product or
customer here automatically propagates to all dashboards and exports.

Architectural note: This module is kept separate from config.py to maintain
a clean separation between system settings (paths, months, formatting) and
business data entities. This prepares for a future SQL migration.
"""

from __future__ import annotations

from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Product Registry
# ═══════════════════════════════════════════════════════════════════════════════

class Product:
    """A product in the Raito catalog."""
    __slots__ = ('sku', 'name', 'short_name', 'brand', 'status', 'color',
                 'manufacturer', 'category')

    def __init__(self, sku: str, name: str, short_name: str, brand: str,
                 status: str, color: str, manufacturer: str,
                 category: str = 'ice_cream'):
        self.sku = sku
        self.name = name
        self.short_name = short_name
        self.brand = brand
        self.status = status
        self.color = color
        self.manufacturer = manufacturer
        self.category = category

    def is_active(self) -> bool:
        return self.status == 'active'

    def is_turbo(self) -> bool:
        return self.brand == 'turbo'

    def is_danis(self) -> bool:
        return self.brand == 'danis'


# ── Master Product Table ──────────────────────────────────────────────────────

PRODUCTS: dict[str, Product] = {
    'chocolate':    Product('chocolate',    'Turbo Chocolate',       'Chocolate',   'turbo', 'active',       '#8B4513', 'Raito'),
    'vanilla':      Product('vanilla',      'Turbo Vanilla',         'Vanilla',     'turbo', 'active',       '#F5DEB3', 'Raito'),
    'mango':        Product('mango',        'Turbo Mango',           'Mango',       'turbo', 'active',       '#FF8C00', 'Raito'),
    'pistachio':    Product('pistachio',    'Turbo Pistachio',       'Pistachio',   'turbo', 'new',          '#93C572', 'Raito'),
    'magadat':      Product('magadat',      'Turbo Magadat',         'Magadat',     'turbo', 'discontinued', '#999999', 'Raito'),
    'dream_cake':   Product('dream_cake',   "Dani's Dream Cake",     'Dream Cake',  'danis', 'discontinued', '#4A0E0E', 'Piece of Cake'),
    'dream_cake_2': Product('dream_cake_2', 'Dream Cake - Biscotti', 'Dream Cake',  'danis', 'active',       '#C2185B', 'Biscotti'),
}


# ── Derived Lookups (auto-generated from PRODUCTS) ───────────────────────────

PRODUCT_NAMES:  dict[str, str] = {sku: p.name       for sku, p in PRODUCTS.items()}
PRODUCT_SHORT:  dict[str, str] = {sku: p.short_name for sku, p in PRODUCTS.items()}
PRODUCT_STATUS: dict[str, str] = {sku: p.status     for sku, p in PRODUCTS.items()}
PRODUCT_COLORS: dict[str, str] = {sku: p.color      for sku, p in PRODUCTS.items()}

# Flavor colors (some products have alternate chart colors vs. their status badge)
FLAVOR_COLORS: dict[str, str] = {
    'chocolate': '#8B4513', 'vanilla': '#DAA520', 'mango': '#FF8C00',
    'pistachio': '#93C572', 'dream_cake': '#DB7093', 'dream_cake_2': '#C2185B',
    'magadat': '#9CA3AF',
}

# Standard display order for tables and charts
PRODUCTS_ORDER: list[str] = [
    'chocolate', 'vanilla', 'mango', 'pistachio',
    'dream_cake', 'dream_cake_2', 'magadat',
]

ACTIVE_SKUS: list[str] = [sku for sku, p in PRODUCTS.items() if p.is_active()]
TURBO_SKUS:  list[str] = [sku for sku, p in PRODUCTS.items() if p.is_turbo()]
DANIS_SKUS:  list[str] = [sku for sku, p in PRODUCTS.items() if p.is_danis()]


# ═══════════════════════════════════════════════════════════════════════════════
# Brand Registry
# ═══════════════════════════════════════════════════════════════════════════════

BRANDS: dict[str, dict] = {
    'ab':    {'label': 'All Brands', 'skus': list(PRODUCTS.keys())},
    'turbo': {'label': 'Turbo',      'skus': TURBO_SKUS},
    'danis': {'label': "Dani's",     'skus': DANIS_SKUS},
}

CREATORS: list[dict] = [
    {'name': 'דני אבדיה',   'brand': 'Turbo',  'skus': TURBO_SKUS},
    {'name': 'דניאל עמית', 'brand': "Dani's", 'skus': DANIS_SKUS},
]


# ═══════════════════════════════════════════════════════════════════════════════
# Distributor Registry
# ═══════════════════════════════════════════════════════════════════════════════

DISTRIBUTORS: dict[str, dict] = {
    'icedream': {'name': 'Icedream',               'name_heb': 'אייסדרים',       'brands': ['turbo', 'danis']},
    'mayyan':   {'name': "Ma'ayan",                'name_heb': 'מעיין נציגויות', 'brands': ['turbo']},
    'biscotti': {'name': 'Biscotti (ביסקוטי)',     'name_heb': 'ביסקוטי',        'brands': ['danis']},
}


# ═══════════════════════════════════════════════════════════════════════════════
# Customer Hierarchy
# ═══════════════════════════════════════════════════════════════════════════════
# Terminology:
#   Customer  = top-level entity (e.g., "AMPM", "Alonit", "Wolt Market")
#   Branch    = sub-customer / sale point (e.g., "דור אלון AM:PM הרצליה")
#
# Previously called "chain" in the codebase. All references to "chain" are
# being migrated to "customer" per the SSOT refactoring roadmap.

# Hebrew → English customer name mapping
# This is the canonical mapping used by config.extract_customer_name()
CUSTOMER_NAMES_EN: dict[str, str] = {
    'AMPM':              'AMPM',
    'אלונית':            'Alonit',
    'גוד פארם':          'Good Pharm',
    'דומינוס':           "Domino's Pizza",
    'דור אלון':          'Alonit',
    'דלק מנטה':          'Delek Menta',
    'וולט מרקט':         'Wolt Market',
    'חוות נעמי':         "Naomi's Farm",
    'טיב טעם':           'Tiv Taam',
    'ינגו':              'Yango Deli',
    'כרמלה':             'Carmella',
    'נוי השדה':          'Noy HaSade',
    'סונול':             'Sonol',
    'עוגיפלצת':          'Oogiplatset',
    'פוט לוקר':          'Foot Locker',
    'פז חברת נפט- סופר יודה': 'Paz Super Yuda',
    'פז סופר יודה':      'Paz Super Yuda',
    'פז ילו':            'Paz Yellow',
    'שוק פרטי':          'Private Market',
}

# Known customer name prefixes for Icedream branch → customer aggregation
CUSTOMER_PREFIXES: list[str] = [
    'דומינוס פיצה', 'דומינוס', 'גוד פארם', 'חוות נעמי', 'נוי השדה',
    'וואלט', 'וולט', 'ינגו', 'כרמלה', 'עוגיפלצת',
]


# ═══════════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════════

def validate_sku(sku: str) -> None:
    """Raise KeyError if sku is not in the product registry.

    Call this at data-ingestion boundaries to catch new products that
    haven't been registered yet (the "silent failure" risk from the audit).
    """
    if sku not in PRODUCTS:
        raise KeyError(
            f"Unknown SKU '{sku}' — register it in registry.PRODUCTS before use"
        )


def get_product(sku: str) -> Optional[Product]:
    """Look up a product by SKU. Returns None if not found."""
    return PRODUCTS.get(sku)


def get_brand_skus(brand: str) -> list[str]:
    """Return the list of SKUs for a brand filter key ('turbo', 'danis', 'ab')."""
    b = BRANDS.get(brand)
    if b is None:
        raise KeyError(f"Unknown brand filter '{brand}'")
    return b['skus']


def is_turbo_sku(sku: str) -> bool:
    """Check if a SKU belongs to the Turbo brand."""
    p = PRODUCTS.get(sku)
    return p is not None and p.is_turbo()


def is_danis_sku(sku: str) -> bool:
    """Check if a SKU belongs to the Dani's brand."""
    p = PRODUCTS.get(sku)
    return p is not None and p.is_danis()
