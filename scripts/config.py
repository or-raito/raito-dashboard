#!/usr/bin/env python3
"""
Raito Dashboard — Shared Configuration
Product definitions, pricing, colors, month mappings, and brand filters.
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR.parent / 'data'
OUTPUT_DIR = BASE_DIR.parent / 'docs'

# ── Product Classification ──────────────────────────────────────────────

PRODUCT_NAMES = {
    'chocolate': 'Turbo Chocolate',
    'vanilla': 'Turbo Vanilla',
    'mango': 'Turbo Mango',
    'magadat': 'Turbo Magadat',
    'dream_cake': "Dani's Dream Cake",
    'dream_cake_2': "Dream Cake - Biscotti",
    'pistachio': 'Turbo Pistachio',
}

PRODUCT_SHORT = {
    'chocolate': 'Chocolate',
    'vanilla': 'Vanilla',
    'mango': 'Mango',
    'magadat': 'Magadat',
    'dream_cake': 'Dream Cake',
    'dream_cake_2': 'Dream Cake',
    'pistachio': 'Pistachio',
}

PRODUCT_STATUS = {
    'chocolate': 'active',
    'vanilla': 'active',
    'mango': 'active',
    'magadat': 'discontinued',
    'dream_cake': 'discontinued',  # Piece of Cake manufacturer — replaced by Biscotti (dream_cake_2)
    'dream_cake_2': 'active',      # Biscotti-manufactured version, active from Apr 2026
    'pistachio': 'new',
}

PRODUCT_COLORS = {
    'chocolate': '#8B4513',
    'vanilla': '#F5DEB3',
    'mango': '#FF8C00',
    'magadat': '#999999',
    'dream_cake': '#4A0E0E',
    'dream_cake_2': '#C2185B',
    'pistachio': '#93C572',
}

FLAVOR_COLORS = {
    'chocolate': '#8B4513', 'vanilla': '#DAA520', 'mango': '#FF8C00',
    'pistachio': '#93C572', 'dream_cake': '#DB7093', 'dream_cake_2': '#C2185B',
    'magadat': '#9CA3AF',
}

# Standard product order for tables and charts
PRODUCTS_ORDER = ['chocolate', 'vanilla', 'mango', 'pistachio', 'dream_cake', 'dream_cake_2', 'magadat']

# ── Pricing & Costs ─────────────────────────────────────────────────────
# CANONICAL SOURCE: pricing_engine.py — all price lookups go through the engine.
# Backward-compatible re-exports for modules that haven't migrated yet.
from pricing_engine import PRODUCTION_COST, all_b2b_prices as _all_b2b

SELLING_PRICE_B2B = _all_b2b()  # Dict copy — for legacy callers only
SELLING_PRICE_B2C = {'dream_cake': 81.1}  # Rarely used, kept for reference

# ── Inventory & Planning ────────────────────────────────────────────────

TARGET_MONTHS_STOCK = 1  # Target months of inventory to maintain
PALLET_DIVISOR = 2400    # Units per pallet

# ── Brand & Creator Info ────────────────────────────────────────────────

DISTRIBUTOR_NAMES = {
    'icedreams': 'Icedream',
    'mayyan': 'מעיין נציגויות',
    'biscotti': 'Biscotti (ביסקוטי)',
}

CREATORS = [
    {'name': 'דני אבדיה', 'brand': 'Turbo',
     'products': ['chocolate', 'vanilla', 'mango', 'pistachio']},
    {'name': 'דניאל עמית', 'brand': "Dani's",
     'products': ['dream_cake', 'dream_cake_2']},
]

BRAND_FILTERS = {
    'ab': {'label': 'All Brands',
            'products': ['chocolate', 'vanilla', 'mango', 'dream_cake', 'dream_cake_2', 'magadat', 'pistachio']},
    'turbo': {'label': 'Turbo',
              'products': ['chocolate', 'vanilla', 'mango', 'pistachio', 'magadat']},
    'danis': {'label': "Dani's",
              'products': ['dream_cake', 'dream_cake_2']},
}

# ── Month Mappings ──────────────────────────────────────────────────────

MONTH_ORDER = {
    'October 2025': 0, 'December 2025': 1, 'January 2026': 2,
    'February 2026': 3, 'March 2026': 4, 'April 2026': 5, 'May 2026': 6,
    'June 2026': 8, 'July 2026': 9, 'August 2026': 10, 'September 2026': 11,
}

MONTH_NAMES_HEB = {
    'October 2025': "Oct '25", 'December 2025': "Dec '25",
    'January 2026': "Jan '26", 'February 2026': "Feb '26", 'March 2026': "Mar '26",
    'April 2026': "Apr '26", 'May 2026': "May '26", 'June 2026': "Jun '26",
    'July 2026': "Jul '26", 'August 2026': "Aug '26", 'September 2026': "Sep '26",
}

CHART_MONTHS = list(MONTH_ORDER.keys())

# ── Shared Helpers ──────────────────────────────────────────────────────

import re

def classify_product(name):
    if name is None:
        return None
    name = str(name)
    # Exclude non-Raito products
    if 'באגסו' in name or 'דובאי' in name:
        return None
    if 'וניל' in name:
        return 'vanilla'
    elif 'מנגו' in name:
        return 'mango'
    elif 'שוקולד' in name:
        return 'chocolate'
    elif 'מארז' in name:
        return 'magadat'
    elif 'דרים' in name:
        return 'dream_cake'
    elif 'פיסטוק' in name:
        return 'pistachio'
    return None

# ── Customer Hierarchy (canonical source: registry.py) ─────────────────────────
# "Chain" terminology is deprecated → use "Customer" / "Branch" instead.
# The mapping and prefixes are sourced from registry.py; config re-exports
# for backward compatibility with existing imports.

from registry import CUSTOMER_NAMES_EN, CUSTOMER_PREFIXES

# Backward-compatible aliases — being phased out
CHAIN_NAMES_EN = CUSTOMER_NAMES_EN

# Known customer name prefixes for Icedream branch → customer aggregation
_CUSTOMER_PREFIXES_LOCAL = CUSTOMER_PREFIXES

def _to_en(name):
    """Translate Hebrew customer name to English via CUSTOMER_NAMES_EN."""
    return CUSTOMER_NAMES_EN.get(name, CUSTOMER_NAMES_EN.get(name.strip(), name))

def extract_customer_name(customer_name, source_customer=None):
    """Extract customer name from a branch-level account name.

    Resolves branch-level names (e.g., "דור אלון AM:PM הרצליה") to their
    parent customer (e.g., "AMPM"). Uses the Customer hierarchy from registry.py.

    Args:
        customer_name: The account/branch name to classify.
        source_customer: Optional original customer name from Ma'ayan data.
            When provided and the account name doesn't match any known
            pattern, returns the source customer instead of the raw name.
    """
    if not customer_name:
        return customer_name
    s = str(customer_name).strip()
    # Normalize all Wolt variants
    if 'וולט' in s or 'וואלט' in s:
        return _to_en('וולט מרקט')
    # Normalize Paz Yellow variants
    if 'פז יילו' in s or 'פז ילו' in s:
        return _to_en('פז ילו')
    # Split טיב טעם out of שוק פרטי
    if 'טיב טעם' in s:
        return _to_en('טיב טעם')
    # Split דור אלון into אלונית and AMPM (all other דור אלון → Alonit)
    if s.startswith('דור אלון'):
        if 'AM:PM' in s or 'AMPM' in s or 'am:pm' in s.lower():
            return _to_en('AMPM')
        return _to_en('אלונית')
    # שפר את אלי לוי → Alonit (0 units, logistics company — fold into Alonit)
    if 'שפר את' in s:
        return _to_en('אלונית')
    for prefix in _CUSTOMER_PREFIXES_LOCAL:
        if s.startswith(prefix):
            if prefix == 'דומינוס פיצה':
                return _to_en('דומינוס')
            return _to_en(prefix)
    # For Ma'ayan accounts: fall back to the source customer name if provided
    if source_customer:
        sc = str(source_customer).strip()
        # Normalize the source customer name too
        if 'פז יילו' in sc or 'פז ילו' in sc:
            return _to_en('פז ילו')
        return _to_en(sc)
    return _to_en(s)

# Backward-compatible alias — being phased out in favor of extract_customer_name
extract_chain_name = extract_customer_name

def extract_units_per_carton(name):
    if name is None:
        return 1
    match = re.search(r'[\*\-]\s*(\d+)\s*יח', str(name))
    return int(match.group(1)) if match else 1

def pallets(units, product=None):
    """Convert units to pallets (1 decimal). Dream cake returns '-'."""
    if product in ('dream_cake', 'dream_cake_2'):
        return '-'
    return round(units / PALLET_DIVISOR, 1) if units > 0 else 0

def fmt(n):
    """Format number with commas."""
    return f'{int(n):,}'

def fc(n):
    """Format currency."""
    return f'₪{int(round(n)):,}'

def compute_kpis(data, month_list, filter_products=None):
    """Compute KPIs for given months, optionally filtered by products."""
    products = filter_products if filter_products else data['products']
    tu = tr = tc = tgm = tmy = tic = tbi = 0
    for month in month_list:
        md = data['monthly_data'].get(month, {})
        for p in products:
            c = md.get('combined', {}).get(p, {})
            u = c.get('units', 0)
            if u > 0:
                tu += u
                tr += c.get('total_value', 0)
                tc += c.get('production_cost', 0)
                tgm += c.get('gross_margin', 0)
                tmy += c.get('mayyan_units', 0)
                tic += c.get('icedreams_units', 0)
                tbi += c.get('biscotti_units', 0)
    td = tmy + tic + tbi
    mp = round(tmy / td * 100) if td > 0 else 0
    ip = round(tic / td * 100) if td > 0 else 0
    bp = 100 - mp - ip
    return tu, tr, tc, tgm, tmy, tic, tbi, mp, ip, bp

def count_pos(data, month_list, active_products=None):
    """Count unique points of sale across months, optionally filtered by products."""
    ice_custs = set()
    may_branches = set()
    for month in month_list:
        md = data['monthly_data'].get(month, {})
        if active_products:
            # Only count customers that have sales in active_products
            for c, pdata in md.get('icedreams_customers', {}).items():
                if any(pdata.get(p, {}).get('units', 0) > 0 for p in active_products if isinstance(pdata.get(p), dict)):
                    ice_custs.add(c)
            # Ma'ayan only sells turbo products — skip if no turbo in active
            turbo_prods = {'chocolate', 'vanilla', 'mango', 'pistachio', 'magadat'}
            if turbo_prods & set(active_products):
                for b in md.get('mayyan_branches', set()):
                    may_branches.add(b)
        else:
            for c in md.get('icedreams_customers', {}):
                ice_custs.add(c)
            for b in md.get('mayyan_branches', set()):
                may_branches.add(b)
    return len(ice_custs) + len(may_branches)
