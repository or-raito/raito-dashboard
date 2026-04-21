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

# ── Month Registry (auto-generated — SINGLE SOURCE OF TRUTH) ──────────
# Add months here ONLY. Every other file imports from this registry.
# Format: ('Month Year', 'short_key', 'Short Label')

from datetime import date as _date

_MONTH_REGISTRY = [
    # ('October 2025',   'oct25', "Oct '25"),  # Pre-launch, minimal data — excluded
    ('November 2025',  'nov',   "Nov '25"),
    ('December 2025',  'dec',   "Dec '25"),
    ('January 2026',   'jan',   "Jan '26"),
    ('February 2026',  'feb',   "Feb '26"),
    ('March 2026',     'mar',   "Mar '26"),
    ('April 2026',     'apr',   "Apr '26"),
    ('May 2026',       'may',   "May '26"),
    ('June 2026',      'jun',   "Jun '26"),
    ('July 2026',      'jul',   "Jul '26"),
    ('August 2026',    'aug',   "Aug '26"),
    ('September 2026', 'sep',   "Sep '26"),
    ('October 2026',   'oct',   "Oct '26"),
    ('November 2026',  'nov26', "Nov '26"),
    ('December 2026',  'dec26', "Dec '26"),
]

# ── Derived structures (all auto-generated from _MONTH_REGISTRY) ──────

MONTH_ORDER = {m[0]: i for i, m in enumerate(_MONTH_REGISTRY)}

MONTH_NAMES_HEB = {m[0]: m[2] for m in _MONTH_REGISTRY}

# full_name → short_key  (e.g. 'March 2026' → 'mar')
MONTH_KEYS = {m[0]: m[1] for m in _MONTH_REGISTRY}

# Ordered list of short keys  (e.g. ['dec', 'jan', 'feb', ...])
ALL_MONTH_KEYS = [m[1] for m in _MONTH_REGISTRY]

# Ordered list of full names  (e.g. ['December 2025', 'January 2026', ...])
CHART_MONTHS = list(MONTH_ORDER.keys())

# short_key → full_name reverse lookup
MONTH_KEY_TO_FULL = {m[1]: m[0] for m in _MONTH_REGISTRY}

# full_name → 'YYYY-MM' API format  (e.g. 'March 2026' → '2026-03')
_MONTH_ABBR_TO_NUM = {
    'January': '01', 'February': '02', 'March': '03', 'April': '04',
    'May': '05', 'June': '06', 'July': '07', 'August': '08',
    'September': '09', 'October': '10', 'November': '11', 'December': '12',
}
MONTH_TO_API = {}
for _m in _MONTH_REGISTRY:
    _parts = _m[0].split()  # e.g. ['March', '2026']
    MONTH_TO_API[_m[0]] = f"{_parts[1]}-{_MONTH_ABBR_TO_NUM[_parts[0]]}"

# ── Week-to-Month mapping (ISO weeks → month full name) ──────────────
# Auto-generated: for each ISO week, determine which month it belongs to
# by checking the Thursday of that week (ISO standard).

def _build_week_to_month():
    """Build {(year, week_num): 'Month Year'} for all weeks in range."""
    from datetime import timedelta
    mapping = {}
    valid_months = set(MONTH_ORDER.keys())
    # Cover ISO weeks for years 2025 and 2026
    for year in (2025, 2026):
        for wk in range(1, 54):
            try:
                # Thursday of ISO week determines the month
                thu = _date.fromisocalendar(year, wk, 4)
            except ValueError:
                continue
            month_name = thu.strftime('%B %Y')  # e.g. 'March 2026'
            if month_name in valid_months:
                mapping[wk] = month_name
                # Also store with year prefix for disambiguation
                mapping[(year, wk)] = month_name
    return mapping

WEEK_TO_MONTH = _build_week_to_month()

# Hebrew month name → full English name (for Ma'ayan parser)
HEBREW_MONTH_NAMES = {
    'ינואר': 'January', 'פברואר': 'February', 'מרץ': 'March',
    'אפריל': 'April', 'מאי': 'May', 'יוני': 'June',
    'יולי': 'July', 'אוגוסט': 'August', 'ספטמבר': 'September',
    'אוקטובר': 'October', 'נובמבר': 'November', 'דצמבר': 'December',
}

# Filename keywords → month full name (for Ma'ayan file detection)
# First occurrence wins — e.g. 'dec' → 'December 2025', not 'December 2026'
FILENAME_MONTH_KEYWORDS = {}
for _m in _MONTH_REGISTRY:
    _parts = _m[0].split()
    _eng = _parts[0].lower()[:3]  # 'jan', 'feb', etc.
    _full = _m[0]
    if _eng not in FILENAME_MONTH_KEYWORDS:
        FILENAME_MONTH_KEYWORDS[_eng] = _full
    # Hebrew keywords
    for _heb, _eng_full in HEBREW_MONTH_NAMES.items():
        if _eng_full == _parts[0] and _heb not in FILENAME_MONTH_KEYWORDS:
            FILENAME_MONTH_KEYWORDS[_heb] = _full
            break

# ── Active Months (auto-computed from current date) ───────────────────

def get_active_months():
    """Return registry entries up to and including the current month.

    Used for status/trend computation — ensures the system knows which
    months to expect data for. Months beyond today are excluded from
    status calculations but still appear in table columns and dropdowns.
    """
    today = _date.today()
    current = today.strftime('%B %Y')
    result = []
    for m in _MONTH_REGISTRY:
        result.append(m)
        if m[0] == current:
            break
    # If current month not in registry, return all registry entries
    return result if result and result[-1][0] == current else list(_MONTH_REGISTRY)


def get_active_month_keys():
    """Return short keys for months up to and including today."""
    return [m[1] for m in get_active_months()]


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

# ── Internal / Promo Accounts (excluded from all customer metrics) ────────────
# These are not real customers — they represent internal orders (promotions,
# samples, ops manager orders, etc.) and should not count in revenue,
# customer counts, or sale point metrics.
INTERNAL_ACCOUNTS = {'Oogiplatset', 'עוגיפלצת', 'עוגיפלצת בע"מ'}

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
    # Holmes Place / Caffein branches (e.g. "(קפאין הרצליה(הולמס פלייס")
    if 'הולמס' in s:
        return 'Holmes Place'
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
