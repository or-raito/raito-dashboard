#!/usr/bin/env python3
"""
Raito Pricing Engine — Single Source of Truth for all price lookups.

Every module that needs a price MUST call into this engine.
No hardcoded price literals anywhere else in the codebase.

Two-tier API:
  get_b2b_price(sku)                → flat list price (SP, BO views)
  get_customer_price(sku, customer)  → negotiated per-customer price (CC view)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import pandas as pd

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
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def get_b2b_price(sku: str) -> float:
    """Return the flat B2B list price for a SKU.

    Used by SP tab, BO tab, and any module that doesn't need customer-level
    price differentiation.

    Raises KeyError if sku is unknown (to surface new-product omissions).
    """
    if sku not in _B2B_PRICES:
        raise KeyError(
            f"Unknown SKU '{sku}' — add it to pricing_engine._B2B_PRICES"
        )
    return _B2B_PRICES[sku]


def get_b2b_price_safe(sku: str, fallback: Optional[float] = None) -> float:
    """Like get_b2b_price but returns fallback instead of raising.

    If fallback is None and sku is unknown, returns 0.0.
    """
    return _B2B_PRICES.get(sku, fallback if fallback is not None else 0.0)


def get_customer_price(sku: str, customer_en: str) -> float:
    """Return the negotiated per-customer price for a SKU.

    Lookup order:
      1. Customer-specific negotiated price (_CUSTOMER_PRICES)
      2. Fall back to B2B list price

    Args:
        sku: Internal product key (e.g. 'chocolate', 'dream_cake_2').
        customer_en: English customer name (as returned by extract_customer_name).
    """
    # Customer-specific prices currently apply uniformly to all Turbo SKUs
    # for a given customer. If the customer has a negotiated price, use it
    # for all Turbo products. Dani's products always use B2B list.
    if customer_en in _CUSTOMER_PRICES and sku not in ('dream_cake', 'dream_cake_2'):
        return _CUSTOMER_PRICES[customer_en]
    return get_b2b_price(sku)


def get_production_cost(sku: str) -> float:
    """Return production cost for a SKU. Returns 0.0 if unknown."""
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

    Falls back to B2B list price if no price-DB entry found.
    """
    pricedb_cust = _MAAYAN_CHAIN_TO_PRICEDB.get(str(chain_raw).strip())
    if pricedb_cust and sku in price_table:
        price = price_table[sku].get(pricedb_cust)
        if price:
            return price
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
