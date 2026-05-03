"""
CC Dashboard — Customer Centric tab generator for the unified dashboard.

Self-contained: the CC HTML source is embedded as a Python constant.
This eliminates the runtime dependency on the external dashboards/ folder.
Processing logic is identical to the original _read_cc_dashboard() function.

To update data (weekly arrays, customer data, etc.):
  Edit the constants in this file instead of the HTML file.
  After editing, run: cd scripts && python3 unified_dashboard.py

Updated: 2026-03-24
"""
import re
import re as _re
from registry import CUSTOMER_NAMES_EN
from pricing_engine import (
    get_customer_price, get_b2b_price_safe, get_production_cost,
    load_mayyan_price_table, _MAAYAN_CHAIN_TO_PRICEDB,
)


# ═══════════════════════════════════════════════════════════════════════════
# Dynamic data generation — replaces hardcoded customers[] and productMix{}
# ═══════════════════════════════════════════════════════════════════════════

# Static customer metadata: structural fields only.
# avgPrice, grossMargin, opMargin, momGrowth are computed DYNAMICALLY from
# actual transaction data by _compute_cc_dynamic_data() — never hardcoded.
_CC_CUSTOMER_META = {
    1:  dict(name="AMPM",           status="active",      distributor="מעיין נציגויות", dist_pct=25, activeSKUs=4,  hasPricing=True,  hasSales=True,  brands=["turbo"]),
    2:  dict(name="Alonit",         status="active",      distributor="מעיין נציגויות", dist_pct=25, activeSKUs=4,  hasPricing=True,  hasSales=True,  brands=["turbo"]),
    3:  dict(name="Good Pharm",     status="active",      distributor="אייסדרים",       dist_pct=15, activeSKUs=4,  hasPricing=True,  hasSales=True,  brands=["turbo"]),
    4:  dict(name="Delek",          status="active",      distributor="מעיין נציגויות", dist_pct=25, activeSKUs=4,  hasPricing=True,  hasSales=True,  brands=["turbo"]),
    5:  dict(name="Wolt Market",    status="active",      distributor="אייסדרים",       dist_pct=15, activeSKUs=6,  hasPricing=True,  hasSales=True,  brands=["turbo", "danis"]),
    6:  dict(name="Tiv Taam",       status="active",      distributor="מעיין נציגויות", dist_pct=25, activeSKUs=4,  hasPricing=True,  hasSales=True,  brands=["turbo"]),
    7:  dict(name="Yingo Deli",     status="active",      distributor="אייסדרים",       dist_pct=15, activeSKUs=6,  hasPricing=True,  hasSales=True,  brands=["turbo", "danis"]),
    8:  dict(name="Carmela",        status="active",      distributor="אייסדרים",       dist_pct=15, activeSKUs=6,  hasPricing=True,  hasSales=True,  brands=["turbo", "danis"]),
    9:  dict(name="Noy Hasade",     status="active",      distributor="אייסדרים",       dist_pct=15, activeSKUs=5,  hasPricing=True,  hasSales=True,  brands=["turbo", "danis"]),
    10: dict(name="Carrefour",      status="negotiation", distributor="מעיין נציגויות", dist_pct=25, activeSKUs=3,  hasPricing=True,  hasSales=False, brands=["turbo"]),
    11: dict(name="Private Market", status="active",      distributor="מעיין נציגויות", dist_pct=25, activeSKUs=4,  hasPricing=True,  hasSales=True,  brands=["turbo"]),
    12: dict(name="Ugipletzet",     status="active",      distributor="אייסדרים",       dist_pct=15, activeSKUs=3,  hasPricing=False, hasSales=True,  brands=["turbo"]),
    13: dict(name="Paz Yellow",     status="active",      distributor="מעיין נציגויות", dist_pct=25, activeSKUs=3,  hasPricing=True,  hasSales=True,  brands=["turbo"]),
    14: dict(name="Paz Super Yuda", status="active",      distributor="מעיין נציגויות", dist_pct=25, activeSKUs=3,  hasPricing=True,  hasSales=True,  brands=["turbo"]),
    15: dict(name="Sonol",          status="active",      distributor="מעיין נציגויות", dist_pct=25, activeSKUs=3,  hasPricing=True,  hasSales=True,  brands=["turbo"]),
    16: dict(name="Domino's",       status="active",      distributor="אייסדרים",       dist_pct=15, activeSKUs=4,  hasPricing=True,  hasSales=True,  brands=["turbo"]),
    17: dict(name="Naomi's Farm",   status="active",      distributor="אייסדרים",       dist_pct=15, activeSKUs=5,  hasPricing=True,  hasSales=True,  brands=["turbo", "danis"]),
    18: dict(name="Hama",           status="negotiation", distributor="אייסדרים",       dist_pct=15, activeSKUs=4,  hasPricing=True,  hasSales=False, brands=["turbo"]),
    19: dict(name="Foot Locker",    status="active",      distributor="אייסדרים",       dist_pct=15, activeSKUs=4,  hasPricing=True,  hasSales=True,  brands=["turbo"]),
    20: dict(name="Biscotti Chain", status="active",      distributor="ביסקוטי",        dist_pct=0,  activeSKUs=1,  hasPricing=True,  hasSales=True,  brands=["danis"]),
    21: dict(name="Matilda Yehud",  status="active",      distributor="ביסקוטי",        dist_pct=0,  activeSKUs=1,  hasPricing=True,  hasSales=True,  brands=["danis"]),
    22: dict(name="Delicious RL",   status="active",      distributor="ביסקוטי",        dist_pct=0,  activeSKUs=1,  hasPricing=True,  hasSales=True,  brands=["danis"]),
}

# Maps English chain name (as returned by extract_customer_name) → CC customer ID.
# Used to route parsed records to the right customer row.
_CUSTOMER_EN_TO_CC_ID = {
    'AMPM':            1,
    'Alonit':          2,
    'Good Pharm':      3,
    'Delek Menta':     4,   # CC display name: "Delek"
    'Wolt Market':     5,
    'Tiv Taam':        6,
    'Yango Deli':      7,
    "Domino's Pizza":  16,
    'Carmella':        8,
    'Noy HaSade':      9,
    'Private Market':  11,
    # 'Oogiplatset' removed — internal/promo account, not a real customer
    'Paz Yellow':      13,
    'Paz Super Yuda':  14,
    'Sonol':           15,
    "Naomi's Farm":    17,
    'Foot Locker':     19,
}

# Biscotti branch prefix → CC customer ID.
# Branches are matched longest-prefix-first so more specific prefixes win.
# Anything that doesn't match falls back to CC ID 20 (Biscotti Chain).
_BISCOTTI_BRANCH_CC_ID = [
    ('וולט מרקט',   5),   # Wolt Market
    ('חוות נעמי',   17),  # Naomi's Farm
    ('חן כרמלה',    8),   # Carmella
    ('כרמלה',       8),   # Carmella (short form)
    ('מתילדה יהוד', 21),  # Matilda Yehud
    ('דלישס',       22),  # Delicious Rishon LeZion
]


def _resolve_biscotti_branch(branch_name):
    """Map a raw Biscotti branch name to a CC customer ID via prefix matching.
    Returns 20 (Biscotti Chain) for unrecognised branches.
    """
    for prefix, cc_id in _BISCOTTI_BRANCH_CC_ID:
        if branch_name.startswith(prefix):
            return cc_id
    return 20  # default: Biscotti Chain


# Parser month strings → JS revenue object keys (from central registry)
from config import MONTH_KEYS as _MONTH_KEYS, ALL_MONTH_KEYS as _ALL_MONTHS

# Customers that carry both Turbo and Danis brands (need turboRev/danisRev split)
_MULTI_BRAND_IDS = {5, 7, 8, 9, 17, 20}

# Products that belong to Dani's Dream Cake brand
_DANIS_PRODUCTS = {'dream_cake', 'dream_cake_2'}

# JS product output order for productMix{}
_PRODUCT_ORDER = ['chocolate', 'vanilla', 'mango', 'pistachio', 'magadat', 'dream_cake', 'dream_cake_2']

# Maps CC customer ID → price-DB customer key for Ma'ayan price table lookups.
# Only Ma'ayan-distributed customers appear here. Others fall back to
# get_customer_price() or B2B list price.
_CC_ID_TO_PRICEDB_CUST = {
    1:  'AMPM',
    2:  'אלונית',
    4:  'דלק',
    11: 'שוק פרטי',
    13: 'פז יילו',
    14: 'פז סופר יודה',
    15: 'סונול',
}

# Maps CC customer ID → English name used by pricing_engine.get_customer_price().
# Needed because _CC_CUSTOMER_META display names may differ from pricing-engine keys.
_CC_ID_TO_PRICING_EN = {
    1:  'AMPM',
    2:  'Alonit',
    3:  'Good Pharm',
    4:  'Delek Menta',
    5:  'Wolt Market',
    6:  'Tiv Taam',
    7:  'Yango Deli',
    8:  'Carmella',
    9:  'Noy HaSade',
    11: 'Private Market',
    13: 'Paz Yellow',
    14: 'Paz Super Yuda',
    15: 'Sonol',
    16: "Domino's Pizza",
    17: "Naomi's Farm",
    19: 'Foot Locker',
    21: 'Matilda Yehud',
    22: 'Delicious Rishon LeZion',
}

# Products shown per customer in the pricing drawer (const productPricing).
# Structural: which SKUs Raito sells to this customer.
_CC_CUST_SKUS = {
    1:  ['vanilla', 'mango', 'chocolate', 'pistachio'],
    2:  ['vanilla', 'mango', 'chocolate', 'pistachio'],
    3:  ['vanilla', 'mango', 'chocolate', 'pistachio'],
    4:  ['vanilla', 'mango', 'chocolate', 'pistachio'],
    5:  ['vanilla', 'mango', 'chocolate', 'pistachio', 'dream_cake_2', 'magadat'],
    6:  ['vanilla', 'mango', 'chocolate', 'pistachio'],
    7:  ['vanilla', 'mango', 'chocolate', 'pistachio', 'dream_cake_2', 'magadat'],
    8:  ['vanilla', 'mango', 'chocolate', 'pistachio', 'dream_cake_2', 'magadat'],
    9:  ['vanilla', 'mango', 'chocolate', 'pistachio', 'magadat'],
    10: ['vanilla', 'mango', 'chocolate'],
    11: ['vanilla', 'mango', 'chocolate', 'pistachio'],
    13: ['vanilla', 'mango', 'chocolate'],
    14: ['vanilla', 'mango', 'chocolate'],
    15: ['vanilla', 'mango', 'chocolate'],
    16: ['vanilla', 'mango', 'chocolate', 'pistachio'],
    17: ['vanilla', 'mango', 'chocolate', 'pistachio', 'dream_cake_2'],
    18: ['vanilla', 'mango', 'chocolate', 'pistachio'],
    19: ['vanilla', 'mango', 'chocolate', 'pistachio'],
    20: ['dream_cake_2'],
    21: ['dream_cake_2'],
    22: ['dream_cake_2'],
}

# Per-SKU distribution % overrides for customers served by multiple distributors.
# Biscotti-sourced SKUs (dream_cake_2) carry 0% commission.
# Customers not listed here use their flat dist_pct from _CC_CUSTOMER_META.
_CC_SKU_DIST_PCT = {
    5:  {'dream_cake_2': 0},   # Wolt Market — Biscotti (0%) + Icedream (15%) split
    8:  {'dream_cake_2': 0},   # Carmela — Biscotti (0%) + Icedream (15%) split
    17: {'dream_cake_2': 0},   # Naomi's Farm — same split
}


def _get_dist_pct(cc_id, sku):
    """Effective distribution % for a CC customer + SKU pair.
    Falls back to the customer-level flat rate for SKUs not in the override table.
    """
    return _CC_SKU_DIST_PCT.get(cc_id, {}).get(sku, _CC_CUSTOMER_META[cc_id]['dist_pct'])


# Hebrew product names for the pricing drawer
_PROD_HEB = {
    'vanilla':      'גלידת חלבון וניל',
    'mango':        'גלידת חלבון מנגו',
    'chocolate':    'גלידת חלבון שוקולד לוז',
    'pistachio':    'גלידת חלבון פיסטוק',
    'dream_cake':   'דרים קייק (Piece of Cake)',
    'dream_cake_2': 'דרים קייק',
    'magadat':      'מארז שלישיית גלידות',
}


def _compute_cc_dynamic_data(data):
    """Build customers[] and productMix{} JS from the shared consolidated data dict.

    Consumes the SAME data object used by the BO tab — no independent file parsing.
    Revenue values come pre-priced from parsers.py:
      - Icedream: actual invoice value from monthly XLSX files
      - Ma'ayan:  _mayyan_chain_price() per row (price DB + B2B fallback)
      - Biscotti: BISCOTTI_PRICE_DREAM_CAKE per unit

    avgPrice, grossMargin, opMargin, momGrowth are ALL computed dynamically
    from the aggregated transaction data — no static literals.

    Returns two JS variable declaration strings suitable for regex-injecting
    into the _CC_HTML constant to replace the hardcoded blocks.
    """
    from config import extract_customer_name

    months = _ALL_MONTHS

    # ── Accumulators ────────────────────────────────────────────────────────
    rev  = {cid: {m: 0.0 for m in months} for cid in _CC_CUSTOMER_META}
    u    = {cid: {m: 0   for m in months} for cid in _CC_CUSTOMER_META}
    trev = {cid: {m: 0.0 for m in months} for cid in _CC_CUSTOMER_META}
    drev = {cid: {m: 0.0 for m in months} for cid in _CC_CUSTOMER_META}
    tu   = {cid: {m: 0   for m in months} for cid in _CC_CUSTOMER_META}
    du   = {cid: {m: 0   for m in months} for cid in _CC_CUSTOMER_META}
    pmix = {cid: {} for cid in _CC_CUSTOMER_META}
    # Revenue-weighted distribution cost per customer (tracks correct rate per SKU
    # so multi-distributor customers like Wolt Market get accurate op_margin).
    dist_cost_rev = {cid: 0.0 for cid in _CC_CUSTOMER_META}
    # Which distributors have contributed revenue to each CC customer
    dist_sources  = {cid: set() for cid in _CC_CUSTOMER_META}

    def _add(cid, mkey, product, units_val, value_val, source=None):
        # Allow negative contributions (returns) — clamped at the end.
        units_val = int(round(units_val))
        value_val = float(value_val)
        rev[cid][mkey]  += value_val
        u[cid][mkey]    += units_val
        if product in _DANIS_PRODUCTS:
            drev[cid][mkey] += value_val
            du[cid][mkey]   += units_val
        else:
            trev[cid][mkey] += value_val
            tu[cid][mkey]   += units_val
        if units_val > 0:
            pmix[cid][product] = pmix[cid].get(product, 0) + units_val
        # Accumulate actual distribution cost using per-SKU rate
        if value_val > 0:
            dist_cost_rev[cid] += value_val * _get_dist_pct(cid, product) / 100
        # Track which distributors contributed to this customer
        if source and units_val != 0:
            dist_sources[cid].add(source)

    # ── 1. All distributors, all months — from consolidated data ──────────
    # Single pipeline: same data object as BO tab.
    for month_str, mkey in _MONTH_KEYS.items():
        md = data['monthly_data'].get(month_str, {})

        # Icedream customers (Hebrew name keys → translate to English → lookup CC ID)
        for cust_heb, prods in md.get('icedreams_customers', {}).items():
            chain_en = extract_customer_name(cust_heb)
            cid = _CUSTOMER_EN_TO_CC_ID.get(chain_en)
            if not cid:
                continue
            for product, pdata in prods.items():
                _add(cid, mkey, product, pdata.get('units', 0), pdata.get('value', 0.0), source='אייסדרים')

        # Ma'ayan accounts — pdata is {product: {units, value}} priced at parse time
        # via _mayyan_chain_price() (price DB per customer+product, B2B fallback).
        # Branch-level name logic in extract_customer_name() handles:
        #   דור אלון → AMPM vs Alonit, שוק פרטי → Tiv Taam vs Private Market
        for (chain_raw, acct), prods in md.get('mayyan_accounts', {}).items():
            chain_en = extract_customer_name(acct, source_customer=chain_raw)
            cid = _CUSTOMER_EN_TO_CC_ID.get(chain_en)
            if not cid:
                continue
            for product, prod_data in prods.items():
                units_val = prod_data.get('units', 0) if isinstance(prod_data, dict) else 0
                value_val = prod_data.get('value', 0.0) if isinstance(prod_data, dict) else 0.0
                _add(cid, mkey, product, units_val, value_val, source='מעיין נציגויות')

        # Biscotti customers — route each branch to its parent CC customer
        for branch, prods in md.get('biscotti_customers', {}).items():
            branch_cc_id = _resolve_biscotti_branch(branch)
            for product, pdata in prods.items():
                _add(branch_cc_id, mkey, product, pdata.get('units', 0), pdata.get('value', 0.0), source='ביסקוטי')

    # ── 2. Clamp negative unit totals to 0 ───────────────────────────────
    # If a customer's net units go negative in a month (e.g. pure return month),
    # clamp units to 0.  Revenue is preserved when positive — a positive revenue
    # with negative units indicates a credit note (return of product from a prior
    # period whose invoice value is still recognised).  Only zero revenue when it
    # is itself negative (i.e. an outright debit to Raito's account).
    for cid in _CC_CUSTOMER_META:
        for m in months:
            if u[cid][m] < 0:
                u[cid][m]  = 0
                tu[cid][m] = 0
                du[cid][m] = 0
                # Zero negative revenue; keep positive (credit-note scenario)
                if rev[cid][m]  < 0: rev[cid][m]  = 0.0
                if trev[cid][m] < 0: trev[cid][m] = 0.0
                if drev[cid][m] < 0: drev[cid][m] = 0.0

    # ── 3. JS number formatter ────────────────────────────────────────────
    def _jn(v, ndigits=2):
        """Format Python value as JS literal. None → null, bool → true/false."""
        if v is None:
            return 'null'
        if isinstance(v, bool):
            return 'true' if v else 'false'
        if isinstance(v, int):
            return str(v)
        r = round(float(v), ndigits)
        return str(int(r)) if r == int(r) else str(r)

    # ── 4. Build customers[] JS ───────────────────────────────────────────
    lines = ['const customers = [']
    for cid in sorted(_CC_CUSTOMER_META.keys()):
        meta = _CC_CUSTOMER_META[cid]
        brands_js = ','.join(f"'{b}'" for b in meta['brands'])

        # Dynamic financial fields — derived from actual transaction data
        total_units = sum(u[cid].values())
        total_rev   = sum(rev[cid].values())
        dp = meta['dist_pct']  # flat rate used for JS field + single-dist customers

        if total_units > 0 and total_rev > 0 and meta.get('hasPricing'):
            avg_price = round(total_rev / total_units, 2)
            total_cost = sum(
                pmix[cid].get(p, 0) * get_production_cost(p)
                for p in pmix[cid]
            )
            gross_margin = round((total_rev - total_cost) / total_rev * 100, 2)
            # Use revenue-weighted effective dist % (handles multi-distributor customers)
            effective_dp = round(dist_cost_rev[cid] / total_rev * 100, 2)
            op_margin    = round(gross_margin - effective_dp, 2)
        else:
            avg_price = gross_margin = op_margin = effective_dp = None

        # MoM growth: last two consecutive months with revenue > 0
        month_revs = [rev[cid][m] for m in months]
        mom_growth = None
        for i in range(len(month_revs) - 1, 0, -1):
            if month_revs[i] > 0 and month_revs[i - 1] > 0:
                mom_growth = round(
                    (month_revs[i] - month_revs[i - 1]) / month_revs[i - 1] * 100, 1
                )
                break

        rev_js  = ','.join(f"{m}:{_jn(rev[cid][m])}" for m in months)
        unit_js = ','.join(f"{m}:{u[cid][m]}" for m in months)

        # Build distributors array from actual revenue sources
        actual_dists = sorted(dist_sources[cid]) or [meta['distributor']]
        dists_js = ','.join(f'"{d}"' for d in actual_dists)
        # Display label: primary distributor name or "Multiple" for multi-source customers
        dist_label = meta['distributor'] if len(actual_dists) <= 1 else 'Multiple'

        row = (
            f"  {{id:{cid}, name:\"{meta['name']}\", status:\"{meta['status']}\","
            f" distributor:\"{dist_label}\", distributors:[{dists_js}],"
            f" dist_pct:{_jn(effective_dp if effective_dp is not None else dp, 1)}, avgPrice:{_jn(avg_price)},"
            f" grossMargin:{_jn(gross_margin)}, opMargin:{_jn(op_margin)},"
            f" activeSKUs:{meta['activeSKUs']}, hasPricing:{_jn(meta['hasPricing'])},"
            f" hasSales:{_jn(meta['hasSales'])}, brands:[{brands_js}],\n"
            f"          revenue:{{{rev_js}}},"
        )

        if cid in _MULTI_BRAND_IDS:
            trev_js = ','.join(f"{m}:{_jn(trev[cid][m])}" for m in months)
            drev_js = ','.join(f"{m}:{_jn(drev[cid][m])}" for m in months)
            tu_js   = ','.join(f"{m}:{tu[cid][m]}" for m in months)
            du_js   = ','.join(f"{m}:{du[cid][m]}" for m in months)
            row += (
                f" turboRev:{{{trev_js}}}, danisRev:{{{drev_js}}},\n"
                f"          units:{{{unit_js}}},\n"
                f"          turboUnits:{{{tu_js}}}, danisUnits:{{{du_js}}},"
            )
        else:
            row += f"\n          units:{{{unit_js}}},"

        row += f" momGrowth:{_jn(mom_growth)}}},\n"
        lines.append(row)

    lines.append('];')
    customers_js = '\n'.join(lines)

    # ── 5. Build productMix{} JS ──────────────────────────────────────────
    pm_lines = ['const productMix = {']
    for cid in sorted(_CC_CUSTOMER_META.keys()):
        mx = pmix[cid]
        items = [f"{p}:{mx[p]}" for p in _PRODUCT_ORDER if mx.get(p, 0) > 0]
        if items:
            pm_lines.append(f"  {cid}: {{{','.join(items)}}},")
    pm_lines.append('};')
    product_mix_js = '\n'.join(pm_lines)

    return customers_js, product_mix_js


def _build_product_pricing_js():
    """Generate const productPricing = {...} from pricing_engine — no hardcoded literals.

    For Ma'ayan customers: uses the price DB per-product lookup (most accurate).
    For Icedream/Biscotti customers: uses get_customer_price() with B2B fallback.
    Computes p18 (inc-VAT), cost, gm%, and om% from the engine.
    """
    price_table = load_mayyan_price_table()
    vat = 1.18

    def _get_price(sku, cid):
        """Best-available price for a CC customer + SKU.

        Three-tier lookup:
          1. master_data JSONB via get_customer_price (SSOT)
          2. Ma'ayan price-DB Excel file (legacy fallback)
          3. B2B list price (last resort)
        """
        cust_en = _CC_ID_TO_PRICING_EN.get(cid, '')
        # 1. Try master_data JSONB first (SSOT)
        if cust_en:
            from pricing_engine import _md_sale_prices, _load_md_pricing
            _load_md_pricing()
            for (s, c, d), price in _md_sale_prices.items():
                if s == sku and c == cust_en:
                    return price
        # 2. Fallback: Ma'ayan price-DB Excel
        pricedb_cust = _CC_ID_TO_PRICEDB_CUST.get(cid)
        if pricedb_cust and sku in price_table:
            p = price_table[sku].get(pricedb_cust)
            if p:
                return p
        # 3. Last resort: B2B list price (or legacy customer price)
        return get_customer_price(sku, cust_en) if cust_en else get_b2b_price_safe(sku)

    lines = ['const productPricing = {']
    for cid in sorted(_CC_CUST_SKUS.keys()):
        if cid not in _CC_CUSTOMER_META:
            continue
        meta = _CC_CUSTOMER_META[cid]
        skus = _CC_CUST_SKUS[cid]

        prod_parts = []
        for sku in skus:
            p0   = _get_price(sku, cid)
            p18  = round(p0 * vat, 2)
            cost = get_production_cost(sku)
            gm   = round((p0 - cost) / p0 * 100, 2) if p0 > 0 else 0
            dp   = _get_dist_pct(cid, sku)   # per-SKU rate (handles multi-distributor)
            om   = round(gm - dp, 2)
            heb  = _PROD_HEB.get(sku, sku)
            prod_parts.append(
                f'      {{name:"{heb}",p0:{p0},p18:{p18},cost:{cost},gm:{gm},om:{om},dp:{dp}}}'
            )

        lines.append(f'  {cid}: [')
        lines.append(',\n'.join(prod_parts) + '],')

    lines.append('};')
    return '\n'.join(lines)



# ═══════════════════════════════════════════════════════════════════════════════
# V2 REBUILD — Clean f-string template, all months from config._MONTH_REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

import json as _json
from config import (
    ALL_MONTH_KEYS, _MONTH_REGISTRY, MONTH_KEYS, CHART_MONTHS,
    get_active_months, get_active_month_keys,
)


def build_cc_tab(data):
    """Generate the Customer Centric tab — V2 clean rebuild.

    All month references are driven by config._MONTH_REGISTRY.
    No raw HTML constant, no .replace() patches.
    Returns dict with keys 'css', 'html_body', 'scripts'.
    """
    # ── Compute dynamic data from parsers ────────────────────────────────
    customers_js, product_mix_js = _compute_cc_dynamic_data(data)
    product_pricing_js = _build_product_pricing_js()

    # ── Registry-derived JS constants ────────────────────────────────────
    months_js = _json.dumps(ALL_MONTH_KEYS)
    mon_labels_js = _json.dumps([m[2] for m in _MONTH_REGISTRY])

    # Month→year mapping: {nov:'2025', dec:'2025', jan:'2026', ..., total:'all'}
    month_year_map = {}
    for mr in _MONTH_REGISTRY:
        year = mr[0].split()[-1]
        month_year_map[mr[1]] = year
    month_year_map['total'] = 'all'
    month_year_js = '{' + ','.join(f"{k}:'{v}'" for k, v in month_year_map.items()) + '}'

    # Month number+year → key mapping for weekly chart
    # e.g. {'2025_11':'nov', '2025_12':'dec', '2026_1':'jan', ...}
    _mname_to_num = {
        'January': 1, 'February': 2, 'March': 3, 'April': 4,
        'May': 5, 'June': 6, 'July': 7, 'August': 8,
        'September': 9, 'October': 10, 'November': 11, 'December': 12,
    }
    mny_map = {}
    for mr in _MONTH_REGISTRY:
        parts = mr[0].split()
        mny_map[f"{parts[1]}_{_mname_to_num[parts[0]]}"] = mr[1]
    mny_to_key_js = _json.dumps(mny_map)

    # Active months (for status labels, default filters)
    active = get_active_months()
    last_active_key = active[-1][1] if active else ALL_MONTH_KEYS[-1]
    last_active_label = active[-1][2].split()[0] if active else 'Last'
    prev_active_label = active[-2][2].split()[0] if len(active) >= 2 else ''

    # Unique years in registry
    years = sorted(set(mr[0].split()[-1] for mr in _MONTH_REGISTRY))
    latest_year = years[-1] if years else '2026'

    # Month dropdown options (chronological — ascending, Jan→Dec)
    month_options = '\n      '.join(
        f'<option value="{m[1]}" data-year="{m[0].split()[-1]}">{m[0]}</option>'
        for m in _MONTH_REGISTRY
    )

    # Year dropdown options
    year_options = '\n      '.join(
        f'<option value="{y}"{" selected" if y == latest_year else ""}>{y}</option>'
        for y in years
    )

    # Short month labels for table headers (e.g. "Dec", "Jan")
    month_short_labels = [m[2].split()[0] for m in _MONTH_REGISTRY]

    # MoM column headers for Excel export
    mom_headers = []
    for i in range(1, len(_MONTH_REGISTRY)):
        prev_short = _MONTH_REGISTRY[i-1][2].split()[0]
        cur_short = _MONTH_REGISTRY[i][2].split()[0]
        mom_headers.append(f'{prev_short}→{cur_short}')

    print("  [CC] V2 rebuild: dynamic data computed successfully")

    return {
        'css': _cc_css(),
        'html_body': _cc_html_body(month_options, year_options, latest_year,
                                     prev_active_label, last_active_label),
        'scripts': _cc_scripts(
            customers_js=customers_js,
            product_mix_js=product_mix_js,
            product_pricing_js=product_pricing_js,
            months_js=months_js,
            mon_labels_js=mon_labels_js,
            month_year_js=month_year_js,
            mny_to_key_js=mny_to_key_js,
            last_active_key=last_active_key,
            last_active_label=last_active_label,
            prev_active_label=prev_active_label,
            latest_year=latest_year,
        ),
    }


def _cc_css():
    """CC tab CSS — clean light theme, scoped under #tab-cc."""
    return """
/* ── CC Tab Variables ── */
#tab-cc {
  --bg:#F8F9FB; --surface:#ffffff; --surface2:#F1F5F9;
  --border:#E2E8F0; --border-light:#f1f5f9;
  --text:#1A1D23; --text2:#64748B; --text-muted:#94a3b8;
  --accent:#5D5FEF; --primary:#5D5FEF;
  --green:#10b981; --amber:#f59e0b; --red:#ef4444;
  --radius:16px;
  font-family:'Inter',system-ui,-apple-system,sans-serif;
  -webkit-font-smoothing:antialiased;
  background:var(--bg);
}

/* Filter bar */
#tab-cc .cc-filter-bar {
  background:var(--surface); border-bottom:1px solid var(--border); padding:12px 24px;
  display:flex; flex-wrap:wrap; gap:10px 20px; align-items:center;
  position:sticky; top:0; z-index:99;
}
#tab-cc .cc-filter-bar label {
  font-size:11px; font-weight:700; color:var(--text2); text-transform:uppercase; letter-spacing:0.8px;
}
#tab-cc .cc-filter-bar select, #tab-cc .cc-filter-bar input {
  background:var(--surface); border:1px solid var(--border); color:var(--text);
  padding:6px 10px; border-radius:8px; font-size:12px; font-weight:500;
  outline:none; cursor:pointer; font-family:inherit;
}
#tab-cc .fgroup { display:flex; align-items:center; gap:6px; }
#tab-cc .btn-secondary {
  padding:6px 14px; border-radius:8px; font-size:12px; cursor:pointer;
  font-weight:600; border:1px solid var(--border); font-family:inherit;
  background:var(--surface); color:var(--text2);
}

/* Brand toggle */
#tab-cc .tab-grp { display:flex; gap:4px; }
#tab-cc .tab {
  padding:5px 14px; border-radius:8px; font-size:12px; font-weight:600;
  border:1px solid var(--border); background:transparent; color:var(--text2);
  cursor:pointer; font-family:inherit; transition:all 0.15s;
}
#tab-cc .tab:hover { border-color:var(--accent); color:var(--accent); }
#tab-cc .tab.on { background:var(--accent); border-color:var(--accent); color:#fff; }
#tab-cc .tab.on-turbo { background:#0ea5e9; border-color:#0ea5e9; color:#fff; border-radius:8px; }
#tab-cc .tab.on-danis { background:#a855f7; border-color:#a855f7; color:#fff; border-radius:8px; }

/* Chips */
#tab-cc .chips { display:flex; gap:6px; flex-wrap:wrap; }
#tab-cc .chip {
  background:rgba(93,95,239,0.06); border:1px solid rgba(93,95,239,0.2);
  color:#5D5FEF; border-radius:20px; font-size:11px; padding:3px 10px;
  display:flex; align-items:center; gap:4px;
}
#tab-cc .chip button { background:none; border:none; color:inherit; cursor:pointer; font-size:14px; padding:0 2px; }

/* KPI grid */
#tab-cc .kpi-grid { display:grid; grid-template-columns:repeat(6,1fr); gap:12px; margin-bottom:16px; }
@media(max-width:1300px){ #tab-cc .kpi-grid { grid-template-columns:repeat(3,1fr); } }
#tab-cc .kpi-card {
  background:var(--surface); border-radius:16px; padding:18px 14px;
  border:1px solid var(--border-light); box-shadow:0 4px 16px rgba(0,0,0,0.03);
  text-align:center; display:flex; flex-direction:column; align-items:center;
  justify-content:center; min-height:110px;
}
#tab-cc .kpi-label {
  font-size:9px; font-weight:700; letter-spacing:0.6px; margin-bottom:8px;
  color:var(--text-muted); text-transform:uppercase;
}
#tab-cc .kpi-value { font-size:22px; font-weight:800; letter-spacing:-0.5px; line-height:1.2; }
#tab-cc .kpi-meta { font-size:10px; margin-top:6px; color:var(--text-muted); line-height:1.3; }
#tab-cc .up { color:var(--green); }
#tab-cc .down { color:var(--red); }

/* Panels */
#tab-cc .panel, #tab-cc .weekly-panel, #tab-cc .tpanel {
  background:var(--surface); border-radius:16px; padding:20px;
  border:1px solid var(--border-light); box-shadow:0 4px 16px rgba(0,0,0,0.03);
  margin-bottom:16px;
}
#tab-cc .pt { font-size:14px; font-weight:700; color:var(--text); margin-bottom:2px; }
#tab-cc .ps { font-size:11px; color:var(--text-muted); margin-bottom:12px; }
#tab-cc .chart-box { height:320px; position:relative; }
#tab-cc .chart-box canvas { width:100%!important; height:100%!important; }

/* Weekly chart */
#tab-cc .weekly-box { height:340px; position:relative; }
#tab-cc .weekly-box canvas { width:100%!important; height:100%!important; }
#tab-cc .wlegend { display:flex; gap:16px; margin-top:8px; flex-wrap:wrap; }
#tab-cc .wleg { display:flex; align-items:center; gap:6px; font-size:11px; color:var(--text2); cursor:pointer; }
#tab-cc .wleg-dot { width:10px; height:10px; border-radius:50%; }
#tab-cc .wleg-line { width:20px; height:3px; border-radius:2px; }
#tab-cc .weekly-no-cust {
  display:none; height:300px; align-items:center; justify-content:center;
  color:var(--text-muted); font-size:13px; text-align:center;
}

/* Two-column row */
#tab-cc .row2 { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px; }
@media(max-width:900px){ #tab-cc .row2 { grid-template-columns:1fr; } }

/* Table */
#tab-cc .tsearch {
  background:#F8F9FB; border:1px solid #E2E8F0; border-radius:8px;
  padding:7px 12px; font-size:12px; width:260px; font-family:inherit; color:var(--text);
}
#tab-cc table.dt { width:100%; border-collapse:collapse; }
#tab-cc table.dt th {
  background:#F8F9FB; color:var(--text2); font-size:10px; text-transform:uppercase;
  letter-spacing:0.4px; border-bottom:1px solid #E2E8F0; padding:8px 10px;
  cursor:pointer; white-space:nowrap; text-align:left;
}
#tab-cc table.dt td { border-bottom:1px solid #f1f5f9; font-size:12px; padding:8px 10px; }
#tab-cc table.dt tr:hover td { background:#f8f9fb; }
#tab-cc table.dt tr.sel td { background:rgba(93,95,239,0.04); }
#tab-cc .dtag { font-size:10px; padding:2px 8px; border-radius:10px; font-weight:600; }
#tab-cc .dtag.active { background:rgba(16,185,129,0.08); color:var(--green); }
#tab-cc .dtag.negotiation { background:rgba(245,158,11,0.08); color:var(--amber); }
#tab-cc .brand-tag { font-size:9px; padding:1px 6px; border-radius:8px; margin-left:4px; font-weight:600; }
#tab-cc .brand-tag.brand-turbo { background:rgba(14,165,233,0.08); color:#0ea5e9; }
#tab-cc .brand-tag.brand-danis { background:rgba(168,85,247,0.08); color:#a855f7; }
#tab-cc .pct-bar { display:flex; align-items:center; gap:6px; font-size:11px; }
#tab-cc .bar-bg { flex:1; height:6px; background:#f1f5f9; border-radius:3px; overflow:hidden; }
#tab-cc .bar-fg { height:100%; border-radius:3px; }

/* Drawer */
#tab-cc .drawer {
  position:fixed; top:0; right:0; width:430px; height:100vh;
  background:#fff; border-left:1px solid #E2E8F0;
  box-shadow:-4px 0 20px rgba(0,0,0,0.06); border-radius:16px 0 0 16px;
  z-index:200; display:none; overflow-y:auto; padding:20px;
}
#tab-cc .drawer.open { display:block; }
#tab-cc .dh { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }
#tab-cc .dclose { background:none; border:none; font-size:24px; cursor:pointer; color:var(--text2); }
#tab-cc .dkpis { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin:12px 0; }
#tab-cc .dkpi { background:#F8F9FB; border-radius:10px; padding:10px; text-align:center; }
#tab-cc .dkpi-l { font-size:9px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px; }
#tab-cc .dkpi-v { font-size:16px; font-weight:700; }
#tab-cc .sec { font-size:13px; font-weight:700; margin:16px 0 8px; color:var(--text); }
#tab-cc .d-chart-box { height:200px; margin-bottom:12px; }
#tab-cc .d-chart-box canvas { width:100%!important; height:100%!important; }
#tab-cc .skut { width:100%; border-collapse:collapse; font-size:11px; }
#tab-cc .skut th { text-align:left; padding:4px 6px; color:var(--text-muted); font-size:10px; border-bottom:1px solid #E2E8F0; }
#tab-cc .skut td { padding:4px 6px; border-bottom:1px solid #f1f5f9; }

/* Export modal overlay */
#tab-cc .cc-export-overlay {
  display:none; position:fixed; inset:0; background:rgba(0,0,0,0.3);
  z-index:300; align-items:center; justify-content:center;
}
#tab-cc .cc-export-overlay.show { display:flex; }
#tab-cc .cc-export-box {
  background:#fff; border-radius:16px; padding:28px; min-width:320px;
  box-shadow:0 8px 32px rgba(0,0,0,0.12);
}
#tab-cc .cc-export-box h3 { margin:0 0 16px; font-size:16px; }
#tab-cc .cc-export-box button {
  display:block; width:100%; padding:10px; margin:8px 0; border-radius:10px;
  border:1px solid var(--border); background:var(--surface); cursor:pointer;
  font-size:13px; font-weight:600; font-family:inherit; color:var(--text);
}
#tab-cc .cc-export-box button:hover { border-color:var(--accent); color:var(--accent); }
"""


def _cc_html_body(month_options, year_options, latest_year,
                  prev_active_label, last_active_label):
    """HTML template for the CC tab body — all month refs come from caller."""
    return f"""
    <!-- Filter bar -->
    <div class="cc-filter-bar">
      <div class="fgroup">
        <label>Customer</label>
        <select id="ccFiltCust" onchange="ccApplyFilters()">
          <option value="all">All Customers</option>
        </select>
      </div>
      <div class="fgroup">
        <label>Distributor</label>
        <select id="ccFiltDist" onchange="ccApplyFilters()">
          <option value="all">All</option>
          <option value="אייסדרים">Icedream</option>
          <option value="מעיין נציגויות">Ma'ayan</option>
          <option value="ביסקוטי">Biscotti</option>
          <option value="none">No Distributor</option>
        </select>
      </div>
      <div class="fgroup">
        <label>Status</label>
        <select id="ccFiltStatus" onchange="ccApplyFilters()">
          <option value="all">All</option>
          <option value="active">Active</option>
          <option value="negotiation">Negotiation</option>
        </select>
      </div>
      <div class="fgroup">
        <label>Year</label>
        <select id="ccFiltYear" onchange="ccApplyFilters()">
          <option value="all">All Years</option>
          {year_options}
        </select>
      </div>
      <div class="fgroup">
        <label>Period</label>
        <select id="ccFiltMonth" onchange="ccApplyFilters()">
          <option value="total" selected>All Months</option>
          {month_options}
        </select>
      </div>
      <div class="tab-grp">
        <button class="tab on" onclick="ccSetBrand('all')">All Brands</button>
        <button class="tab" onclick="ccSetBrand('turbo')">Turbo</button>
        <button class="tab" onclick="ccSetBrand('danis')">Dani's</button>
      </div>
      <button class="btn-secondary" onclick="ccResetFilters()">Reset</button>
      <button class="btn-secondary" onclick="ccShowExport()">Export</button>
      <div class="chips" id="ccChips"></div>
    </div>

    <!-- KPI grid -->
    <div style="padding:16px 24px 0">
      <div class="kpi-grid" id="ccKpiGrid"></div>

      <!-- Trend line (full width) -->
      <div class="panel">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <div class="pt">Portfolio Trend</div>
            <div class="ps" id="ccTrendSub">Monthly revenue across portfolio</div>
          </div>
          <div class="tab-grp">
            <button class="tab on" onclick="ccSetTrendMode('rev')">Revenue</button>
            <button class="tab" onclick="ccSetTrendMode('units')">Units</button>
          </div>
        </div>
        <div class="chart-box"><canvas id="ccTrendChart"></canvas></div>
      </div>

      <!-- Two-column: Pareto + Mix -->
      <div class="row2">
        <div class="panel">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
              <div class="pt">Revenue Pareto</div>
              <div class="ps">Customer contribution — click bar for detail</div>
            </div>
            <div class="tab-grp">
              <button class="tab on" onclick="ccSetParetoMode('revenue')">Revenue</button>
              <button class="tab" onclick="ccSetParetoMode('units')">Units</button>
            </div>
          </div>
          <div class="chart-box"><canvas id="ccParetoChart"></canvas></div>
        </div>
        <div class="panel">
          <div class="pt">Product Mix</div>
          <div class="ps">SKU distribution by customer</div>
          <div class="chart-box"><canvas id="ccMixChart"></canvas></div>
        </div>
      </div>

      <!-- Weekly chart -->
      <div class="weekly-panel">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <div class="pt">Weekly Performance</div>
            <div class="ps" id="ccWeeklySub">Weekly revenue by distributor</div>
          </div>
          <div class="tab-grp">
            <button class="tab on" onclick="ccSetWeeklyMode('rev')">Revenue</button>
            <button class="tab" onclick="ccSetWeeklyMode('units')">Units</button>
          </div>
        </div>
        <div class="weekly-box"><canvas id="ccWeeklyChart"></canvas></div>
        <div class="weekly-no-cust" id="ccWeeklyNoCust">
          Select a single customer or distributor<br>to view weekly breakdown
        </div>
        <div class="wlegend" id="ccWeeklyLegend"></div>
      </div>

      <!-- Customer table -->
      <div class="tpanel">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <div class="pt">Customer Performance</div>
          <input class="tsearch" id="ccSearch" placeholder="Search customers..." oninput="ccRenderTable()">
        </div>
        <div style="overflow-x:auto">
          <table class="dt" id="ccTable">
            <thead><tr id="ccTableHead"></tr></thead>
            <tbody id="ccTableBody"></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Drawer (customer detail) -->
    <div class="drawer" id="ccDrawer">
      <div class="dh">
        <h3 id="ccDrawerTitle"></h3>
        <button class="dclose" onclick="ccCloseDrawer()">&times;</button>
      </div>
      <div class="dkpis" id="ccDrawerKpis"></div>
      <div class="sec">Monthly Revenue</div>
      <div class="d-chart-box"><canvas id="ccDrawerChart"></canvas></div>
      <div class="sec">SKU Breakdown</div>
      <table class="skut" id="ccDrawerSkuTable"></table>
    </div>

    <!-- Export modal -->
    <div class="cc-export-overlay" id="ccExportOverlay" onclick="if(event.target===this)ccHideExport()">
      <div class="cc-export-box">
        <h3>Export Customer Data</h3>
        <button onclick="ccExportToExcel()">Download as CSV</button>
        <button onclick="ccHideExport()">Cancel</button>
      </div>
    </div>
"""


def _cc_scripts(*, customers_js, product_mix_js, product_pricing_js,
                months_js, mon_labels_js, month_year_js, mny_to_key_js,
                last_active_key, last_active_label, prev_active_label,
                latest_year):
    """All CC tab JavaScript — fully dynamic month references via MONTHS array."""
    return f"""
// ═══════════════════════════════════════════════════════════════════════════
// CC Tab — Customer Centric Dashboard  (V2 — registry-driven months)
// ═══════════════════════════════════════════════════════════════════════════
(function() {{
'use strict';

// ── Data injected by Python ────────────────────────────────────────────
{customers_js}

{product_mix_js}

{product_pricing_js}

const MONTHS     = {months_js};
const MON_LABELS = {mon_labels_js};
const MON_YEAR   = {month_year_js};
const MNY_TO_KEY = {mny_to_key_js};

// ── Product constants ──────────────────────────────────────────────────
const PROD_COLORS = {{
  chocolate:'rgba(139,69,19,0.85)', vanilla:'rgba(245,158,11,0.85)',
  mango:'rgba(249,115,22,0.85)', pistachio:'rgba(147,197,114,0.85)',
  dream_cake:'rgba(219,112,147,0.85)', dream_cake_2:'rgba(219,112,147,0.85)',
  magadat:'rgba(168,85,247,0.85)',
}};
const PROD_LABELS = {{
  chocolate:'Chocolate', vanilla:'Vanilla', mango:'Mango',
  pistachio:'Pistachio', dream_cake:'Dream Cake', dream_cake_2:'Dream Cake',
  magadat:'Triple Pack',
}};
const PROD_KEY = {{
  'גלידת חלבון וניל':'vanilla','גלידת חלבון מנגו':'mango',
  'גלידת חלבון שוקולד לוז':'chocolate','גלידת חלבון פיסטוק':'pistachio',
  'דרים קייק':'dream_cake','דרים קייק 2':'dream_cake_2',
  'מארז שלישיית גלידות':'magadat',
}};

// ── Weekly data (hardcoded — future: DB migration) ─────────────────────
const weeklyXLabels = ["28/12","4/1","11/1","18/1","25/1","1/2","8/2","15/2","22/2","1/3","8/3","15/3","22/3","29/3","5/4","12/4","19/4","26/4"];
const DATA_LAST_WEEK       = weeklyXLabels.length;
const DATA_LAST_WEEK_LABEL = weeklyXLabels[DATA_LAST_WEEK - 1];
const WEEKLY_WINDOW = 10;

const _iceWkRev        = [9256,10076,1460,8070,599111,17666,2673,2916,437981,21831,26678,111979,13493,50901,13943,24428,17940,30024];
const _iceWkUnits      = [144,324,108,66,17068,483,198,216,12290,725,553,3067,970,2148,1000,1790,1330,2350];
const _iceWkRevTurbo   = [497,3776,1460,0,143429,5416,2673,2916,112840,7803,3354,29872,13493,22099,13943,24428,17940,30024];
const _iceWkUnitsTurbo = [36,282,108,0,11537,400,198,216,8290,602,272,2182,970,1678,1000,1790,1330,2350];
const _iceWkRevDanis   = [8759,6300,0,8070,455682,12249,0,0,325141,14028,23324,82106,0,28802,0,0,0,0];
const _iceWkUnitsDanis = [108,42,0,66,5531,83,0,0,4000,123,281,885,0,416,0,0,0,0];
const _iceWkRetRev     = [0,8278,1309,2392,0,233,1890,1925,0,1125,null,0,null,null,null,null,null,null];
const _iceWkRetUnits   = [0,117,51,204,0,7,114,33,0,30,null,0,null,null,null,null,null,null];

const _maayWkRev   = {{6:135406,7:106260,8:240106,9:122351,10:99415,11:109572,12:67672,13:142182,14:78750,15:52099,16:166214,17:85801}};
const _maayWkUnits = {{6:9812,7:7700,8:17399,9:8866,10:7204,11:7940,12:4970,13:10410,14:5516,15:3840,16:12123,17:6320}};

const _biscWkRev   = {{12:8080,13:43840,14:111120,15:12000,16:60160,17:81360}};
const _biscWkUnits = {{12:101,13:548,14:1389,15:150,16:752,17:1017}};

const _iceMonRev   = {{dec:686481, jan:641087}};
const _iceMonUnits = {{dec:20289,  jan:17919}};
const _maayMonRev   = {{dec:852496, jan:415214}};
const _maayMonUnits = {{dec:61775,  jan:30088}};

// Returns data
const icedreamsReturns = {{
  dec:{{units:0,revenue:0,rate:0}},jan:{{units:0,revenue:0,rate:0}},
  feb:{{units:124,revenue:1682,rate:0.9}},mar:{{units:30,revenue:1125,rate:3.2}},
  total:{{units:154,revenue:2807,rate:0.3}}
}};
const mayanReturns = {{
  dec:{{units:0,revenue:0,rate:0}},jan:{{units:28,revenue:365,rate:0.1}},
  feb:{{units:124,revenue:1614,rate:0.3}},mar:{{units:0,revenue:0,rate:0}},
  total:{{units:152,revenue:1979,rate:0.1}}
}};
const allReturns = {{
  dec:{{units:0,revenue:0,rate:0}},jan:{{units:28,revenue:365,rate:0.1}},
  feb:{{units:248,revenue:3296,rate:0.4}},mar:{{units:30,revenue:1125,rate:3.2}},
  total:{{units:306,revenue:4786,rate:0.2}}
}};

// ── State ──────────────────────────────────────────────────────────────
const S = {{
  cust:'all', dist:'all', status:'all',
  month:'total', year:'{latest_year}', brand:'all',
  sortCol:'revActive', sortDir:-1,
  paretoMode:'revenue', trendMode:'rev',
  selId:null
}};
let _weeklyMode = 'rev';
let charts = {{}};

// ── Helpers ────────────────────────────────────────────────────────────
const $  = id => document.getElementById(id);
const N  = (v,d=0) => v==null?'—':(+v).toLocaleString('he-IL',{{minimumFractionDigits:d,maximumFractionDigits:d}});
const P  = v => v==null?'—':(v>=0?'+':'')+v.toFixed(1)+'%';
const K  = v => {{ if(v==null) return '—'; const a=Math.abs(v); if(a>=1e6) return (v<0?'-':'')+'₪'+(a/1e6).toFixed(1)+'M'; if(a>=1e3) return (v<0?'-':'')+'₪'+(a/1e3).toFixed(0)+'K'; return '₪'+N(v); }};
const colorGM = g => g==null?'var(--text)':g>=50?'var(--green)':g>=40?'var(--amber)':'var(--red)';
const colorOM = g => g==null?'var(--text)':g>=30?'var(--green)':g>=20?'var(--amber)':'var(--red)';

// Derive effective brand from BOTH the brand pill and the distributor filter.
// When viewing one distributor (e.g. Biscotti) for a multi-brand customer,
// we want only that distributor's slice — Biscotti only carries danis,
// Icedream/Ma'ayan only carry turbo. This relies on the assortment rule.
function _effectiveBrand() {{
  if(S.brand !== 'all') return S.brand;
  if(S.dist === 'ביסקוטי') return 'danis';
  if(S.dist === 'אייסדרים' || S.dist === 'מעיין נציגויות') return 'turbo';
  return 'all';
}}

function getBrandRev(c) {{
  const b = _effectiveBrand();
  if(b==='turbo' && c.turboRev) return c.turboRev;
  if(b==='danis' && c.danisRev) return c.danisRev;
  return c.revenue;
}}
function getBrandUnits(c) {{
  const b = _effectiveBrand();
  if(b==='turbo' && c.turboUnits) return c.turboUnits;
  if(b==='danis' && c.danisUnits) return c.danisUnits;
  return c.units;
}}

function getRevField(c) {{
  const r = getBrandRev(c);
  if(S.month==='total') {{
    if(S.year==='all') return MONTHS.reduce((s,m)=>s+(r[m]||0),0);
    return MONTHS.filter(m=>MON_YEAR[m]===S.year).reduce((s,m)=>s+(r[m]||0),0);
  }}
  return r[S.month]||0;
}}
function getUnitField(c) {{
  const u = getBrandUnits(c);
  if(S.month==='total') {{
    if(S.year==='all') return MONTHS.reduce((s,m)=>s+(u[m]||0),0);
    return MONTHS.filter(m=>MON_YEAR[m]===S.year).reduce((s,m)=>s+(u[m]||0),0);
  }}
  return u[S.month]||0;
}}

function filtered() {{
  return customers.filter(c => {{
    if(S.cust!=='all' && c.id!=+S.cust) return false;
    if(S.dist!=='all') {{
      if(S.dist==='none'){{ if(c.distributor) return false; }}
      else {{
        // Prefer the distributors[] array (handles multi-distributor customers
        // like Wolt Market who buy turbo from Icedream AND danis from Biscotti).
        // Falls back to the legacy single distributor field.
        const dists = (c.distributors && c.distributors.length) ? c.distributors : [c.distributor];
        if(!dists.includes(S.dist)) return false;
      }}
    }}
    if(S.status!=='all' && c.status!==S.status) return false;
    if(S.brand==='turbo' && !c.brands.includes('turbo')) return false;
    if(S.brand==='danis'  && !c.brands.includes('danis')) return false;
    return true;
  }});
}}

function portfolioMonthly(list) {{
  const active = S.year==='all' ? MONTHS : MONTHS.filter(m=>MON_YEAR[m]===S.year);
  return active.map((m,i)=> {{
    let rev=0, units=0;
    list.forEach(c => {{ rev+=getBrandRev(c)[m]||0; units+=getBrandUnits(c)[m]||0; }});
    return {{month:m, label:MON_LABELS[MONTHS.indexOf(m)], revenue:rev, units:units}};
  }});
}}

// ── Populate customer dropdown ─────────────────────────────────────────
(function() {{
  const sel=$('ccFiltCust');
  customers.filter(c=>c.hasSales).sort((a,b)=>a.name.localeCompare(b.name))
    .forEach(c => {{ const o=document.createElement('option'); o.value=c.id; o.textContent=c.name; sel.appendChild(o); }});
}})();

// ── Filter/Sort ────────────────────────────────────────────────────────
// Sync period dropdown to show only months matching selected year
function ccSyncPeriodDropdown() {{
  const sel = $('ccFiltMonth');
  const yr = $('ccFiltYear').value;
  const curVal = sel.value;
  // Show/hide options based on year
  Array.from(sel.options).forEach(o => {{
    if(o.value==='total') {{ o.style.display=''; return; }}
    const optYear = o.getAttribute('data-year');
    o.style.display = (yr==='all' || optYear===yr) ? '' : 'none';
  }});
  // If current selection is now hidden, reset to "All Months"
  const curOpt = sel.querySelector(`option[value="${{curVal}}"]`);
  if(curOpt && curOpt.style.display==='none') sel.value='total';
}}

function ccApplyFilters() {{
  S.cust   = $('ccFiltCust').value;
  S.dist   = $('ccFiltDist').value;
  S.status = $('ccFiltStatus').value;
  S.year   = $('ccFiltYear').value;
  ccSyncPeriodDropdown();
  S.month  = $('ccFiltMonth').value;
  renderAll();
}}
window.ccApplyFilters = ccApplyFilters;

function ccResetFilters() {{
  S.cust='all'; S.dist='all'; S.status='all';
  S.month='total'; S.year='all'; S.brand='all';
  S.sortCol='revActive'; S.sortDir=-1;
  $('ccFiltCust').value='all'; $('ccFiltDist').value='all';
  $('ccFiltStatus').value='all'; $('ccFiltMonth').value='total';
  $('ccFiltYear').value='all';
  ccSyncPeriodDropdown();
  document.querySelectorAll('#tab-cc .tab-grp .tab').forEach(t => {{
    t.className='tab'; if(t.textContent==='All Brands'||t.textContent==='Revenue') t.classList.add('on');
  }});
  renderAll();
}}
window.ccResetFilters = ccResetFilters;

function ccSetBrand(b) {{
  S.brand = b;
  const btns = document.querySelectorAll('#tab-cc .cc-filter-bar .tab-grp:first-of-type .tab');
  // First tab-grp in filter bar is brand
  const grp = document.querySelector('#tab-cc .cc-filter-bar .tab-grp');
  if(grp) grp.querySelectorAll('.tab').forEach(t => {{
    t.className='tab';
    const lb = t.textContent.trim();
    if(lb==='All Brands' && b==='all') t.classList.add('on');
    if(lb==='Turbo' && b==='turbo') {{ t.classList.add('on-turbo'); }}
    if(lb==="Dani's" && b==='danis') {{ t.classList.add('on-danis'); }}
  }});
  renderAll();
}}
window.ccSetBrand = ccSetBrand;

function updateChips() {{
  const el=$('ccChips'); let h='';
  if(S.cust!=='all') {{ const c=customers.find(x=>x.id==+S.cust); h+=`<span class="chip">${{c?c.name:S.cust}}<button onclick="ccClearChip('cust')">&times;</button></span>`; }}
  if(S.dist!=='all') h+=`<span class="chip">${{S.dist}}<button onclick="ccClearChip('dist')">&times;</button></span>`;
  if(S.status!=='all') h+=`<span class="chip">${{S.status}}<button onclick="ccClearChip('status')">&times;</button></span>`;
  el.innerHTML=h;
}}
function ccClearChip(k) {{
  if(k==='cust') {{ S.cust='all'; $('ccFiltCust').value='all'; }}
  if(k==='dist') {{ S.dist='all'; $('ccFiltDist').value='all'; }}
  if(k==='status') {{ S.status='all'; $('ccFiltStatus').value='all'; }}
  renderAll();
}}
window.ccClearChip = ccClearChip;

function ccSortBy(col) {{
  if(S.sortCol===col) S.sortDir*=-1; else {{ S.sortCol=col; S.sortDir=-1; }}
  ccRenderTable();
}}
window.ccSortBy = ccSortBy;

function ccSetParetoMode(m) {{
  S.paretoMode=m;
  document.querySelectorAll('#ccParetoChart').closest('.panel')
    ?.querySelectorAll('.tab').forEach(t=>{{t.className='tab'; if(t.textContent.toLowerCase()===m) t.classList.add('on');}});
  renderPareto();
}}
window.ccSetParetoMode = ccSetParetoMode;

function ccSetTrendMode(m) {{
  S.trendMode=m;
  const p = $('ccTrendChart')?.closest('.panel');
  if(p) p.querySelectorAll('.tab').forEach(t=>{{t.className='tab'; if(t.textContent.toLowerCase().startsWith(m)) t.classList.add('on');}});
  renderTrend();
}}
window.ccSetTrendMode = ccSetTrendMode;

function ccSetWeeklyMode(m) {{
  _weeklyMode=m;
  const p=$('ccWeeklyChart')?.closest('.weekly-panel');
  if(p) p.querySelectorAll('.tab').forEach(t=>{{t.className='tab'; if(t.textContent.toLowerCase().startsWith(m)) t.classList.add('on');}});
  renderWeeklyChart();
}}
window.ccSetWeeklyMode = ccSetWeeklyMode;

// ── Export ──────────────────────────────────────────────────────────────
function ccShowExport() {{ $('ccExportOverlay').classList.add('show'); }}
function ccHideExport() {{ $('ccExportOverlay').classList.remove('show'); }}
window.ccShowExport = ccShowExport;
window.ccHideExport = ccHideExport;

function ccExportToExcel() {{
  const list = filtered();
  let hdr = ['Customer','Revenue','VAT 18%','Share %','Gross %','Gross ₪','Op %','Op ₪','Units','MoM %','Distributor','Status'];
  const totalRev = list.reduce((s,c)=>s+getRevField(c),0);
  let rows = [hdr.join(',')];
  list.forEach(c => {{
    const rev = getRevField(c);
    const units = getUnitField(c);
    const share = totalRev>0?(rev/totalRev*100):0;
    rows.push([
      `"${{c.name}}"`,rev,(rev*1.18).toFixed(0),share.toFixed(1),
      c.grossMargin||'',(rev*(c.grossMargin||0)/100).toFixed(0),
      c.opMargin||'',(rev*(c.opMargin||0)/100).toFixed(0),
      units,c.momGrowth||'',`"${{c.distributor}}"`,c.status
    ].join(','));
  }});
  const blob=new Blob([rows.join('\\n')],{{type:'text/csv;charset=utf-8;'}});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download='cc_export.csv';
  a.click();
  ccHideExport();
}}
window.ccExportToExcel = ccExportToExcel;

// ── Chart.js datalabels plugin (inline) ────────────────────────────────
if(typeof Chart!=='undefined' && !Chart.registry?.plugins?.get('datalabels')) {{
  Chart.register({{
    id:'datalabels',
    afterDatasetsDraw(chart) {{
      chart.data.datasets.forEach((ds,di) => {{
        const meta = chart.getDatasetMeta(di);
        if(!meta.hidden && ds.datalabels) {{
          const cfg = ds.datalabels;
          meta.data.forEach((el,i) => {{
            if(cfg.display && typeof cfg.display==='function' && !cfg.display({{dataIndex:i,dataset:ds}})) return;
            const val = ds.data[i];
            if(val==null) return;
            const label = cfg.formatter ? cfg.formatter(val,{{dataIndex:i,dataset:ds}}) : val;
            if(!label && label!==0) return;
            const ctx = chart.ctx;
            ctx.save();
            ctx.font = (cfg.font?.weight||'600')+' '+(cfg.font?.size||10)+'px Inter,sans-serif';
            ctx.fillStyle = cfg.color||'#64748B';
            const offset = cfg.offset||0;
            const anchor = cfg.anchor||'end';
            const align = cfg.align||'center';
            let x=el.x, y=el.y;
            if(anchor==='end') y-=offset; else if(anchor==='start') y+=offset;
            ctx.textAlign = align==='left'?'left':align==='right'?'right':'center';
            ctx.fillText(label,x,y);
            ctx.restore();
          }});
        }}
      }});
    }}
  }});
}}

// ── KPI rendering ──────────────────────────────────────────────────────
function renderKPIs() {{
  const list = filtered();
  const totalRev = list.reduce((s,c)=>s+getRevField(c),0);
  const totalUnits = list.reduce((s,c)=>s+getUnitField(c),0);

  // Gross/op profit — margin-percentage method (matches per-customer margin from data engine)
  const grossVal = list.reduce((s,c)=>s+(getRevField(c)*(c.grossMargin||0)/100),0);
  const opVal    = list.reduce((s,c)=>s+(getRevField(c)*(c.opMargin||0)/100),0);

  // MoM: compare current month to previous
  const mIdx = S.month==='total' ? MONTHS.length-1 : MONTHS.indexOf(S.month);
  let momPct = null, momLabel = '';
  if(mIdx > 0) {{
    const curKey = MONTHS[mIdx], prevKey = MONTHS[mIdx-1];
    const curRev = list.reduce((s,c)=>s+(getBrandRev(c)[curKey]||0),0);
    const prevRev = list.reduce((s,c)=>s+(getBrandRev(c)[prevKey]||0),0);
    if(prevRev>0) momPct = ((curRev-prevRev)/prevRev*100);
    momLabel = MON_LABELS[mIdx-1]+'→'+MON_LABELS[mIdx];
  }}

  // Return rate
  const retObj = S.dist==='אייסדרים'? icedreamsReturns : S.dist==='מעיין נציגויות'? mayanReturns : allReturns;
  const retKey = S.month==='total'?'total':S.month;
  const retRate = retObj[retKey]?.rate || 0;

  // Period label
  const periodLabel = S.month==='total' ? (S.year==='all'?'All Months':S.year) : MON_LABELS[MONTHS.indexOf(S.month)];

  const grid=$('ccKpiGrid');
  grid.innerHTML = `
    <div class="kpi-card"><div class="kpi-label">REVENUE (${{periodLabel}})</div><div class="kpi-value">₪${{N(totalRev)}}</div></div>
    <div class="kpi-card"><div class="kpi-label">UNITS (${{periodLabel}})</div><div class="kpi-value">${{N(totalUnits)}}</div></div>
    <div class="kpi-card"><div class="kpi-label">GROSS PROFIT</div><div class="kpi-value">₪${{N(grossVal)}}</div>
      <div class="kpi-meta">${{totalRev>0?(grossVal/totalRev*100).toFixed(1)+'%':'—'}}</div></div>
    <div class="kpi-card"><div class="kpi-label">OP PROFIT</div><div class="kpi-value">₪${{N(opVal)}}</div>
      <div class="kpi-meta">${{totalRev>0?(opVal/totalRev*100).toFixed(1)+'%':'—'}}</div></div>
    <div class="kpi-card"><div class="kpi-label">RETURN RATE</div><div class="kpi-value">${{retRate.toFixed(1)}}%</div></div>
    <div class="kpi-card"><div class="kpi-label">MOM GROWTH</div><div class="kpi-value ${{momPct!=null?(momPct>=0?'up':'down'):''}}">
      ${{momPct!=null?P(momPct):'—'}}</div><div class="kpi-meta">${{momLabel}}</div></div>
  `;
}}

// ── Pareto chart ───────────────────────────────────────────────────────
function renderPareto() {{
  const list = filtered().filter(c=>getRevField(c)>0||getUnitField(c)>0);
  const isRev = S.paretoMode==='revenue';
  const sorted = [...list].sort((a,b)=>(isRev?getRevField(b)-getRevField(a):getUnitField(b)-getUnitField(a)));
  const labels = sorted.map(c=>c.name);
  const values = sorted.map(c=>isRev?getRevField(c):getUnitField(c));
  const colors = sorted.map(c => {{
    const gm = c.grossMargin;
    return gm==null?'rgba(148,163,184,0.7)':gm>=50?'rgba(16,185,129,0.75)':gm>=40?'rgba(245,158,11,0.75)':'rgba(239,68,68,0.75)';
  }});

  if(charts.pareto) charts.pareto.destroy();
  charts.pareto = new Chart($('ccParetoChart'),{{
    type:'bar',
    data:{{ labels, datasets:[{{ data:values, backgroundColor:colors, borderRadius:6,
      datalabels:{{ anchor:'end', align:'top', offset:4, color:'#64748B',
        font:{{size:9,weight:'600'}},
        formatter:v=>isRev?K(v):N(v),
        display:(ctx)=>ctx.dataIndex<10
      }}
    }}] }},
    options:{{
      responsive:true, maintainAspectRatio:false,
      plugins:{{ legend:{{display:false}}, tooltip:{{
        callbacks:{{ label:t=>isRev?'₪'+N(t.raw):N(t.raw)+' units' }}
      }} }},
      scales:{{ x:{{grid:{{display:false}}, ticks:{{font:{{size:10}}}}}},
               y:{{display:false,grid:{{display:false}}}} }},
      onClick(e,els) {{ if(els.length) {{ const c=sorted[els[0].index]; selectRow(c.id); }} }}
    }}
  }});
}}

// ── Product mix chart ──────────────────────────────────────────────────
function renderMix() {{
  const list = filtered().filter(c=>getRevField(c)>0);
  const prodKeys = Object.keys(PROD_COLORS);

  const datasets = prodKeys.map(pk => ({{
    label: PROD_LABELS[pk]||pk,
    data: list.map(c => (productMix[c.id]||{{}})[pk]||0),
    backgroundColor: PROD_COLORS[pk],
    borderRadius: 4,
  }})).filter(ds=>ds.data.some(v=>v>0));

  if(charts.mix) charts.mix.destroy();
  charts.mix = new Chart($('ccMixChart'),{{
    type:'bar',
    data:{{ labels:list.map(c=>c.name), datasets }},
    options:{{
      responsive:true, maintainAspectRatio:false,
      plugins:{{ legend:{{position:'bottom',labels:{{boxWidth:10,font:{{size:10}}}}}},
                 tooltip:{{mode:'index'}} }},
      scales:{{ x:{{stacked:true,grid:{{display:false}},ticks:{{font:{{size:10}}}}}},
               y:{{stacked:true,grid:{{color:'#f1f5f9'}},ticks:{{font:{{size:10}}}}}} }}
    }}
  }});
}}

// ── Trend chart ────────────────────────────────────────────────────────
function renderTrend() {{
  const list = filtered();
  const pm = portfolioMonthly(list);
  const isRev = S.trendMode==='rev';
  const values = pm.map(d=>isRev?d.revenue:d.units);
  const labels = pm.map(d=>d.label);

  // Last month: dashed (partial)
  const borderDash = pm.map((_,i)=>i===pm.length-1?[5,5]:[]);
  const pointBg = pm.map((_,i)=>i===pm.length-1?'rgba(93,95,239,0.4)':'#5D5FEF');

  if(charts.trend) charts.trend.destroy();
  charts.trend = new Chart($('ccTrendChart'),{{
    type:'line',
    data:{{ labels, datasets:[{{
      data:values, borderColor:'#5D5FEF', backgroundColor:'rgba(93,95,239,0.08)',
      fill:true, tension:0.35, pointRadius:5, pointBackgroundColor:pointBg,
      segment:{{ borderDash: ctx => ctx.p1DataIndex===pm.length-1?[5,5]:undefined }},
      datalabels:{{ anchor:'end', align:'top', offset:6, color:'#5D5FEF',
        font:{{size:10,weight:'700'}},
        formatter:v=>isRev?'₪'+N(v):N(v)
      }}
    }}] }},
    options:{{
      responsive:true, maintainAspectRatio:false,
      plugins:{{ legend:{{display:false}} }},
      scales:{{ x:{{grid:{{display:false}}}}, y:{{grid:{{color:'#f1f5f9'}},ticks:{{font:{{size:10}}}}}} }}
    }}
  }});

  // Subtitle
  if(pm.length>=2) {{
    const last=pm[pm.length-1], prev=pm[pm.length-2];
    const v1=isRev?prev.revenue:prev.units, v2=isRev?last.revenue:last.units;
    const chg = v1>0?((v2-v1)/v1*100).toFixed(1)+'%':'—';
    $('ccTrendSub').textContent = `${{prev.label}}→${{last.label}}: ${{chg}} | W${{DATA_LAST_WEEK}}`;
  }}
}}

// ── Table rendering ────────────────────────────────────────────────────
function ccRenderTable() {{
  const list = filtered();
  const q = ($('ccSearch')?.value||'').toLowerCase();
  const totalRev = list.reduce((s,c)=>s+getRevField(c),0);

  // Header — matches original CC table layout
  $('ccTableHead').innerHTML = `
    <th onclick="ccSortBy('name')">Customer</th>
    <th onclick="ccSortBy('revActive')">Revenue</th>
    <th onclick="ccSortBy('vat')">VAT 18%</th>
    <th onclick="ccSortBy('share')">Share %</th>
    <th onclick="ccSortBy('grossVal')">Gross %</th>
    <th onclick="ccSortBy('grossAbs')">Gross ₪</th>
    <th onclick="ccSortBy('opVal')">Op %</th>
    <th onclick="ccSortBy('opAbs')">Op ₪</th>
    <th onclick="ccSortBy('unitsActive')">Units</th>
    <th onclick="ccSortBy('mom')">MoM</th>
    <th onclick="ccSortBy('distributor')">Distributor</th>
    <th onclick="ccSortBy('status')">Status</th>`;

  // Sort
  const rows = list.filter(c=>!q||c.name.toLowerCase().includes(q)||c.distributor.toLowerCase().includes(q));
  rows.sort((a,b) => {{
    let va, vb;
    if(S.sortCol==='name') return S.sortDir*a.name.localeCompare(b.name);
    if(S.sortCol==='distributor') return S.sortDir*a.distributor.localeCompare(b.distributor);
    if(S.sortCol==='status') return S.sortDir*a.status.localeCompare(b.status);
    if(S.sortCol==='revActive') {{ va=getRevField(a); vb=getRevField(b); }}
    else if(S.sortCol==='vat') {{ va=getRevField(a); vb=getRevField(b); }}
    else if(S.sortCol==='unitsActive') {{ va=getUnitField(a); vb=getUnitField(b); }}
    else if(S.sortCol==='share') {{ va=getRevField(a); vb=getRevField(b); }}
    else if(S.sortCol==='grossVal') {{ va=a.grossMargin||0; vb=b.grossMargin||0; }}
    else if(S.sortCol==='grossAbs') {{ va=getRevField(a)*(a.grossMargin||0)/100; vb=getRevField(b)*(b.grossMargin||0)/100; }}
    else if(S.sortCol==='opVal') {{ va=a.opMargin||0; vb=b.opMargin||0; }}
    else if(S.sortCol==='opAbs') {{ va=getRevField(a)*(a.opMargin||0)/100; vb=getRevField(b)*(b.opMargin||0)/100; }}
    else if(S.sortCol==='mom') {{ va=a.momGrowth||0; vb=b.momGrowth||0; }}
    else {{ va=getRevField(a); vb=getRevField(b); }}
    return S.sortDir*((va||0)-(vb||0));
  }});

  // Active rows first
  rows.sort((a,b) => {{
    const aActive = getRevField(a)>0 ? 1 : 0;
    const bActive = getRevField(b)>0 ? 1 : 0;
    return bActive - aActive;
  }});

  // Period label for zero-row reason
  const mLbl = S.month==='total'?'selected period':MON_LABELS[MONTHS.indexOf(S.month)];

  let tbody = '';
  rows.forEach(c => {{
    const rev = getRevField(c);
    const units = getUnitField(c);
    const vat18 = rev * 1.18;
    const share = totalRev>0?(rev/totalRev*100):0;
    const gm = c.grossMargin;
    const om = c.opMargin;
    const grossAbs = rev*(gm||0)/100;
    const opAbs = rev*(om||0)/100;
    const sel = S.selId===c.id ? 'sel' : '';
    const fade = rev<=0 ? 'style="opacity:0.5"' : '';

    const brandTags = c.brands.map(b=>`<span class="brand-tag brand-${{b}}">${{b==='turbo'?'Turbo':"Dani's"}}</span>`).join('');

    // Zero-revenue reason
    let reason = '';
    if(rev<=0) {{
      reason = c.status==='negotiation'
        ? '<div style="font-size:10px;color:var(--text-muted)">negotiation — no sales yet</div>'
        : `<div style="font-size:10px;color:var(--text-muted)">no sales in ${{mLbl}}</div>`;
    }}

    tbody += `<tr class="${{sel}}" ${{fade}} onclick="ccSelectRow(${{c.id}})">
      <td>${{c.name}} ${{brandTags}}${{reason}}</td>
      <td>₪${{N(rev)}}</td>
      <td>₪${{N(vat18)}}</td>
      <td>
        <div class="pct-bar"><div class="bar-bg"><div class="bar-fg" style="width:${{Math.min(share,100)}}%;background:var(--accent)"></div></div>${{share.toFixed(1)}}%</div>
      </td>
      <td style="color:${{colorGM(gm)}}">${{gm!=null?gm.toFixed(1)+'%':'—'}}</td>
      <td>₪${{N(grossAbs)}}</td>
      <td style="color:${{colorOM(om)}}">${{om!=null?om.toFixed(1)+'%':'—'}}</td>
      <td>₪${{N(opAbs)}}</td>
      <td>${{N(units)}}</td>
      <td class="${{c.momGrowth!=null?(c.momGrowth>=0?'up':'down'):''}}">
        ${{c.momGrowth!=null?(c.momGrowth>=0?'▲':'▼')+' '+Math.abs(c.momGrowth).toFixed(1)+'%':'—'}}</td>
      <td style="color:var(--text2)">${{c.distributor}}</td>
      <td><span class="dtag ${{c.status}}">${{c.status}}</span></td>
    </tr>`;
  }});
  $('ccTableBody').innerHTML = tbody;
  updateChips();
}}
window.ccRenderTable = ccRenderTable;

// ── Weekly chart ───────────────────────────────────────────────────────
function _weeklyDistKey() {{
  if(S.cust!=='all') {{
    const c=customers.find(x=>x.id==+S.cust);
    if(c?.distributor?.includes('אייסדרים')) return 'ice';
    if(c?.distributor?.includes('מעיין')) return 'maay';
    if(c?.distributor?.includes('ביסקוטי')) return 'bisc';
  }}
  if(S.dist==='אייסדרים') return 'ice';
  if(S.dist==='מעיין נציגויות') return 'maay';
  if(S.dist==='ביסקוטי') return 'bisc';
  return 'both';
}}

function _iceDataArr(r) {{
  if(S.brand==='turbo') return r ? _iceWkRetRev : _iceWkRevTurbo;
  if(S.brand==='danis')  return r ? null : _iceWkRevDanis;
  return r ? _iceWkRetRev : _iceWkRev;
}}
function _iceUnitArr() {{
  if(S.brand==='turbo') return _iceWkUnitsTurbo;
  if(S.brand==='danis')  return _iceWkUnitsDanis;
  return _iceWkUnits;
}}

function _sparseToArr(obj) {{
  if(!obj) return weeklyXLabels.map(()=>null);
  return weeklyXLabels.map((_,i) => obj[i+1]??null);
}}

function _mkWeeklyDatasets(mode) {{
  const dk = _weeklyDistKey();
  const isRev = mode==='rev';
  const ds = [];
  const dlCfg = {{ anchor:'end', align:'center', offset:8, font:{{size:9,weight:'600'}},
    formatter:v=>v==null?'':isRev?K(v):N(v), display:ctx=>{{ const v=ctx.dataset.data[ctx.dataIndex]; return v!=null&&v>0; }} }};
  if(dk==='ice'||dk==='both') {{
    ds.push({{ label:'Icedream '+(isRev?'Rev':'Units'),
      data: isRev ? _iceDataArr(false) : _iceUnitArr(),
      borderColor:'#4f8ef7', backgroundColor:'rgba(79,142,247,0.1)',
      tension:0.3, fill:false, pointRadius:3, spanGaps:true,
      datalabels:{{...dlCfg, color:'#4f8ef7'}} }});
  }}
  if(dk==='maay'||dk==='both') {{
    if(S.brand!=='danis') {{
      ds.push({{ label:"Ma'ayan "+(isRev?'Rev':'Units'),
        data: _sparseToArr(isRev?_maayWkRev:_maayWkUnits),
        borderColor:'#22c55e', backgroundColor:'rgba(34,197,94,0.1)',
        tension:0.3, fill:false, pointRadius:3, spanGaps:true,
        datalabels:{{...dlCfg, color:'#22c55e'}} }});
    }}
  }}
  if(dk==='bisc'||dk==='both') {{
    if(S.brand!=='turbo') {{
      ds.push({{ label:'Biscotti '+(isRev?'Rev':'Units'),
        data: _sparseToArr(isRev?_biscWkRev:_biscWkUnits),
        borderColor:'#f59e0b', backgroundColor:'rgba(245,158,11,0.1)',
        tension:0.3, fill:false, pointRadius:3, spanGaps:true,
        datalabels:{{...dlCfg, color:'#f59e0b'}} }});
    }}
  }}
  return ds;
}}

function renderWeeklyChart() {{
  const dk = _weeklyDistKey();
  const noCust = $('ccWeeklyNoCust');
  const canvas = $('ccWeeklyChart');

  if(dk==='both' && S.cust==='all') {{
    // Show all distributors combined
  }}

  noCust.style.display='none';
  canvas.style.display='block';

  // Rolling window
  const startIdx = Math.max(0, DATA_LAST_WEEK - WEEKLY_WINDOW);
  const labels = weeklyXLabels.slice(startIdx);
  const datasets = _mkWeeklyDatasets(_weeklyMode).map(ds => ({{
    ...ds,
    data: ds.data.slice(startIdx)
  }}));

  if(charts.weekly) charts.weekly.destroy();
  charts.weekly = new Chart(canvas, {{
    type:'line',
    data:{{ labels, datasets }},
    options:{{
      responsive:true, maintainAspectRatio:false,
      plugins:{{ legend:{{position:'bottom',labels:{{boxWidth:10,font:{{size:10}}}}}} }},
      scales:{{ x:{{grid:{{display:false}}}}, y:{{grid:{{color:'#f1f5f9'}},
        ticks:{{font:{{size:10}},callback:v=>_weeklyMode==='rev'?'₪'+N(v):N(v)}}
      }} }}
    }}
  }});

  // Legend info
  const el=$('ccWeeklyLegend');
  el.innerHTML = `<span class="wleg"><span class="wleg-line" style="background:#4f8ef7"></span>Icedream</span>
    <span class="wleg"><span class="wleg-line" style="background:#22c55e"></span>Ma'ayan</span>
    <span class="wleg"><span class="wleg-line" style="background:#f59e0b"></span>Biscotti</span>`;
}}

// ── Drawer ─────────────────────────────────────────────────────────────
function openDrawer(c) {{
  S.selId = c.id;
  $('ccDrawerTitle').textContent = c.name;
  $('ccDrawer').classList.add('open');

  // KPIs
  const totalRev = MONTHS.reduce((s,m)=>(s+(getBrandRev(c)[m]||0)),0);
  const totalUnits = MONTHS.reduce((s,m)=>(s+(getBrandUnits(c)[m]||0)),0);
  const avgP = totalUnits>0?(totalRev/totalUnits).toFixed(2):'—';
  $('ccDrawerKpis').innerHTML = `
    <div class="dkpi"><div class="dkpi-l">TOTAL REV</div><div class="dkpi-v">₪${{N(totalRev)}}</div></div>
    <div class="dkpi"><div class="dkpi-l">TOTAL UNITS</div><div class="dkpi-v">${{N(totalUnits)}}</div></div>
    <div class="dkpi"><div class="dkpi-l">AVG PRICE</div><div class="dkpi-v">₪${{avgP}}</div></div>
  `;

  // Monthly bar chart
  const monData = MONTHS.map(m=>getBrandRev(c)[m]||0);
  const monLabels = MON_LABELS.map(l=>l.split(' ')[0]);
  if(charts.drawer) charts.drawer.destroy();
  charts.drawer = new Chart($('ccDrawerChart'),{{
    type:'bar',
    data:{{ labels:monLabels, datasets:[{{
      data:monData,
      backgroundColor:MONTHS.map((_,i)=>i===MONTHS.length-1?'rgba(93,95,239,0.4)':'rgba(93,95,239,0.75)'),
      borderRadius:6,
      datalabels:{{ anchor:'end', align:'top', offset:4, color:'#5D5FEF',
        font:{{size:9,weight:'600'}}, formatter:v=>v>0?'₪'+N(v):'' }}
    }}] }},
    options:{{
      responsive:true, maintainAspectRatio:false,
      plugins:{{ legend:{{display:false}} }},
      scales:{{ x:{{grid:{{display:false}}}}, y:{{display:false}} }}
    }}
  }});

  // SKU table
  const mix = productMix[c.id]||{{}};
  const pricing = productPricing[c.id]||[];
  const totalMixUnits = Object.values(mix).reduce((s,v)=>s+v,0);
  let skuHtml = '<thead><tr><th>SKU</th><th>Units</th><th>%</th><th>Price</th><th>GM%</th></tr></thead><tbody>';
  // Merge priced + unpriced
  const allSkus = new Set([...Object.keys(mix), ...pricing.map(p=>{{
    const entry = Object.entries(PROD_KEY).find(([_,v])=>v && p.name.includes(_));
    return entry?entry[1]:null;
  }}).filter(Boolean)]);

  allSkus.forEach(sk => {{
    const qty = mix[sk]||0;
    const pct = totalMixUnits>0?(qty/totalMixUnits*100).toFixed(1):'0';
    const pr = pricing.find(p=>p.name===({{
      vanilla:'גלידת חלבון וניל',mango:'גלידת חלבון מנגו',
      chocolate:'גלידת חלבון שוקולד לוז',pistachio:'גלידת חלבון פיסטוק',
      dream_cake:'דרים קייק (Piece of Cake)',dream_cake_2:'דרים קייק',
      magadat:'מארז שלישיית גלידות',
    }}[sk]));
    skuHtml += `<tr><td>${{PROD_LABELS[sk]||sk}}</td><td>${{N(qty)}}</td><td>${{pct}}%</td>
      <td>${{pr?'₪'+pr.p0:'—'}}</td><td style="color:${{colorGM(pr?.gm)}}">${{pr?pr.gm.toFixed(1)+'%':'—'}}</td></tr>`;
  }});
  skuHtml += '</tbody>';
  $('ccDrawerSkuTable').innerHTML = skuHtml;
}}

function ccCloseDrawer() {{
  S.selId=null;
  $('ccDrawer').classList.remove('open');
  ccRenderTable();
}}
window.ccCloseDrawer = ccCloseDrawer;

function ccSelectRow(id) {{
  if(S.selId===id) {{ ccCloseDrawer(); return; }}
  const c = customers.find(x=>x.id===id);
  if(c) openDrawer(c);
  ccRenderTable();
}}
window.ccSelectRow = ccSelectRow;

// ── Render all ─────────────────────────────────────────────────────────
function renderAll() {{
  renderKPIs();
  renderPareto();
  renderMix();
  renderTrend();
  ccRenderTable();
  renderWeeklyChart();
}}

// ── Init ───────────────────────────────────────────────────────────────
ccSyncPeriodDropdown();
renderAll();

}})();  // end CC IIFE
"""
