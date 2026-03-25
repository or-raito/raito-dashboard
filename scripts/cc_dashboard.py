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
    'Oogiplatset':     12,
    'Paz Yellow':      13,
    'Paz Super Yuda':  14,
    'Sonol':           15,
    "Naomi's Farm":    17,
    'Foot Locker':     19,
}

# Parser month strings → JS revenue object keys
_MONTH_KEYS = {
    'December 2025':  'dec',
    'January 2026':   'jan',
    'February 2026':  'feb',
    'March 2026':     'mar',
}
_ALL_MONTHS = ['dec', 'jan', 'feb', 'mar']

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
}

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

    def _add(cid, mkey, product, units_val, value_val):
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
                _add(cid, mkey, product, pdata.get('units', 0), pdata.get('value', 0.0))

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
                _add(cid, mkey, product, units_val, value_val)

        # Biscotti customers
        for _branch, prods in md.get('biscotti_customers', {}).items():
            for product, pdata in prods.items():
                _add(20, mkey, product, pdata.get('units', 0), pdata.get('value', 0.0))

    # ── 2. Clamp negative totals to 0 ────────────────────────────────────
    for cid in _CC_CUSTOMER_META:
        for m in months:
            if u[cid][m] < 0:
                u[cid][m] = 0;    rev[cid][m] = 0.0
                tu[cid][m] = 0;   trev[cid][m] = 0.0
                du[cid][m] = 0;   drev[cid][m] = 0.0

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
        dp = meta['dist_pct']

        if total_units > 0 and total_rev > 0 and meta.get('hasPricing'):
            avg_price = round(total_rev / total_units, 2)
            total_cost = sum(
                pmix[cid].get(p, 0) * get_production_cost(p)
                for p in pmix[cid]
            )
            gross_margin = round((total_rev - total_cost) / total_rev * 100, 2)
            op_margin    = round(gross_margin - dp, 2)
        else:
            avg_price = gross_margin = op_margin = None

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

        row = (
            f"  {{id:{cid}, name:\"{meta['name']}\", status:\"{meta['status']}\","
            f" distributor:\"{meta['distributor']}\","
            f" dist_pct:{meta['dist_pct']}, avgPrice:{_jn(avg_price)},"
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
        """Best-available price for a CC customer + SKU."""
        pricedb_cust = _CC_ID_TO_PRICEDB_CUST.get(cid)
        if pricedb_cust and sku in price_table:
            p = price_table[sku].get(pricedb_cust)
            if p:
                return p
        # Fallback: pricing_engine per-customer price (or B2B list)
        cust_en = _CC_ID_TO_PRICING_EN.get(cid, '')
        return get_customer_price(sku, cust_en) if cust_en else get_b2b_price_safe(sku)

    lines = ['const productPricing = {']
    for cid in sorted(_CC_CUST_SKUS.keys()):
        if cid not in _CC_CUSTOMER_META:
            continue
        meta = _CC_CUSTOMER_META[cid]
        dp   = meta['dist_pct']
        skus = _CC_CUST_SKUS[cid]

        prod_parts = []
        for sku in skus:
            p0   = _get_price(sku, cid)
            p18  = round(p0 * vat, 2)
            cost = get_production_cost(sku)
            gm   = round((p0 - cost) / p0 * 100, 2) if p0 > 0 else 0
            om   = round(gm - dp, 2)
            heb  = _PROD_HEB.get(sku, sku)
            prod_parts.append(
                f'      {{name:"{heb}",p0:{p0},p18:{p18},cost:{cost},gm:{gm},om:{om},dp:{dp}}}'
            )

        lines.append(f'  {cid}: [')
        lines.append(',\n'.join(prod_parts) + '],')

    lines.append('};')
    return '\n'.join(lines)


def build_cc_tab(data):
    """
    Generate the Customer Centric tab HTML content.

    Args:
        data: The consolidated data dict from parsers.consolidate_data().
              CC consumes the SAME object as the BO tab (single pipeline).

    Applies the same CSS/JS processing as _read_cc_dashboard() in unified_dashboard.py,
    but reads from the embedded _CC_HTML constant instead of a file.

    Returns:
        dict with keys 'css', 'html_body', 'scripts'
    """
    content = _CC_HTML

    # ── Inject dynamically computed customer data ─────────────────────────
    # Replaces const customers=[...], productMix={...}, productPricing={...}
    # with live data derived from the shared consolidated data object.
    try:
        customers_js, product_mix_js = _compute_cc_dynamic_data(data)
        product_pricing_js = _build_product_pricing_js()
        content = re.sub(
            r'const customers = \[.*?\];',
            lambda m: customers_js,
            content,
            flags=re.DOTALL,
        )
        content = re.sub(
            r'const productMix = \{.*?\};',
            lambda m: product_mix_js,
            content,
            flags=re.DOTALL,
        )
        content = re.sub(
            r'const productPricing = \{.*?\};',
            lambda m: product_pricing_js,
            content,
            flags=re.DOTALL,
        )
        print("  [CC] Dynamic customers[], productMix{}, productPricing{} injected successfully")
    except Exception as _cc_dyn_err:
        import traceback as _tb
        print(f"  [CC] Warning: dynamic data generation failed — using hardcoded values")
        print(f"       Error: {_cc_dyn_err}")
        _tb.print_exc()

    # Translate Hebrew chain names to English throughout the CC content
    for heb, eng in CUSTOMER_NAMES_EN.items():
        if heb != eng:  # skip already-English names like AMPM
            content = content.replace(heb, eng)

    # Fix legacy English names that were renamed
    content = content.replace('Shuk Prati', 'Private Market')

    # Fix JS single-quoted strings broken by apostrophes in EN names
    # e.g. network:'Domino's Pizza' → network:'Domino\'s Pizza'
    # Names with apostrophes that appear inside JS single-quoted strings
    for eng in CUSTOMER_NAMES_EN.values():
        if "'" in eng:
            # Split on apostrophe: e.g. "Domino's Pizza" → ["Domino", "s Pizza"]
            # In broken JS: 'Domino' s Pizza' — the first ' after Domino closes the string
            # We need to find these broken patterns and escape the apostrophe
            parts = eng.split("'")
            # Pattern: 'parts[0]' s parts[1]' — the middle quote broke the string
            # Replace with properly escaped version
            escaped = eng.replace("'", "\\'")
            # Direct replacement for all occurrences
            content = content.replace(eng, escaped)
            # But this double-escapes HTML attributes and JSON — fix those back
            # In HTML: value="Domino\'s Pizza" → value="Domino's Pizza"
            content = content.replace(f'"{escaped}"', f'"{eng}"')
            content = content.replace(f'>{escaped}<', f'>{eng}<')

    result = {'css': '', 'html_body': '', 'scripts': ''}

    # Extract CSS from <style> tags
    style_match = re.search(r'<style[^>]*>(.*?)</style>', content, re.DOTALL)
    if style_match:
        raw_css = style_match.group(1)
        # Convert dark theme to modern light theme matching Gridle design
        light_css = raw_css
        light_css = light_css.replace('--bg:#0f1117', '--bg:#F8F9FB')
        light_css = light_css.replace('--surface:#1a1d27', '--surface:#ffffff')
        light_css = light_css.replace('--surface2:#22263a', '--surface2:#F1F5F9')
        light_css = light_css.replace('--border:#2e3348', '--border:#E2E8F0')
        light_css = light_css.replace('--text:#e2e8f0', '--text:#1A1D23')
        light_css = light_css.replace('--text2:#8892a4', '--text2:#64748B')
        light_css = light_css.replace('--text1:#e2e8f0', '--text1:#1A1D23')
        light_css = light_css.replace('--accent:#4f8ef7', '--accent:#5D5FEF')
        light_css = light_css.replace('--radius:10px', '--radius:16px')
        light_css = re.sub(r'rgba\(46,51,72,0\.4\)', 'rgba(0,0,0,0.06)', light_css)
        light_css = re.sub(r'rgba\(46,51,72,0\.45\)', 'rgba(0,0,0,0.05)', light_css)
        light_css = re.sub(r'rgba\(46,51,72,0\.35\)', 'rgba(0,0,0,0.04)', light_css)
        # Fix drawer shadow, scrollbar
        light_css = light_css.replace('rgba(0,0,0,0.5)', 'rgba(0,0,0,0.12)')
        light_css = light_css.replace('::-webkit-scrollbar-track{background:var(--bg)}', '::-webkit-scrollbar-track{background:#f1f5f9}')
        light_css = light_css.replace('::-webkit-scrollbar-thumb{background:var(--border)', '::-webkit-scrollbar-thumb{background:#cbd5e1')
        # Modernize KPI cards
        light_css = light_css.replace('font-size:21px;font-weight:700', 'font-size:26px;font-weight:800;letter-spacing:-0.5px')
        # Modernize panel/card border-radius
        light_css = light_css.replace('border-radius:var(--radius);padding:17px', 'border-radius:20px;padding:24px;box-shadow:0 8px 30px rgba(0,0,0,0.04)')
        light_css = light_css.replace('border-radius:var(--radius);padding:15px', 'border-radius:20px;padding:20px;box-shadow:0 8px 30px rgba(0,0,0,0.04)')
        light_css = light_css.replace('border-radius:var(--radius);padding:16px', 'border-radius:20px;padding:20px;box-shadow:0 8px 30px rgba(0,0,0,0.04)')
        # Tab buttons
        light_css = light_css.replace('background:var(--accent);border-color:var(--accent);color:#fff', 'background:#5D5FEF;border-color:#5D5FEF;color:#fff;border-radius:8px')
        light_css = light_css.replace("background:#0ea5e9;border-color:#0ea5e9;color:#fff", "background:#0ea5e9;border-color:#0ea5e9;color:#fff;border-radius:8px")
        light_css = light_css.replace("background:var(--purple);border-color:var(--purple);color:#fff", "background:#a855f7;border-color:#a855f7;color:#fff;border-radius:8px")
        # Scope ALL CC CSS under #tab-cc to prevent style conflicts
        # We do this by adding #tab-cc prefix to each selector
        scoped_lines = []
        for line in light_css.split('\n'):
            stripped = line.strip()
            # Skip empty lines and root-level things
            if not stripped or stripped.startswith('/*') or stripped.startswith('*'):
                scoped_lines.append(line)
            elif stripped.startswith(':root'):
                # Scope :root vars under #tab-cc
                scoped_lines.append(line.replace(':root', '#tab-cc'))
            elif stripped.startswith('::-webkit'):
                scoped_lines.append(line.replace('::-webkit', '#tab-cc ::-webkit'))
            elif stripped.startswith('@media'):
                scoped_lines.append(line)
            elif stripped.startswith('}') or stripped.startswith('{'):
                scoped_lines.append(line)
            elif '{' in stripped and not stripped.startswith('#tab-cc'):
                # Add #tab-cc prefix to selectors
                parts = stripped.split('{', 1)
                selectors = parts[0].split(',')
                scoped_selectors = ','.join(f'#tab-cc {s.strip()}' for s in selectors)
                scoped_lines.append(scoped_selectors + '{' + parts[1] if len(parts) > 1 else scoped_selectors + '{')
            else:
                scoped_lines.append(line)
        # Add extra modern overrides
        scoped_lines.append("""
/* ── CC Modern Overrides ── */
#tab-cc { font-family:'Inter',system-ui,-apple-system,sans-serif; -webkit-font-smoothing:antialiased; }

/* Header: clean, compact, no sticky */
#tab-cc .header {
  background:#fff; border-bottom:1px solid #f1f5f9; padding:14px 24px;
  display:flex; align-items:center; justify-content:space-between; position:relative; z-index:auto;
}
#tab-cc .header h1 { font-size:16px; font-weight:700; color:#1e293b; }
#tab-cc .header h1 span { font-size:12px; font-weight:400; color:#94a3b8; }
#tab-cc .badges { gap:6px; }
#tab-cc .badge { background:#F8F9FB; border:1px solid #E2E8F0; border-radius:20px; font-size:10px; padding:3px 10px; color:#64748b; }
#tab-cc .badge.green { background:rgba(16,185,129,0.06); border-color:rgba(16,185,129,0.25); color:#10b981; font-size:10px; }
#tab-cc .badge.amber { background:rgba(245,158,11,0.06); border-color:rgba(245,158,11,0.25); color:#f59e0b; font-size:10px; }

/* Filter bar: match BO style */
#tab-cc .filter-bar {
  background:var(--surface); border-bottom:1px solid var(--border); padding:12px 24px;
  display:flex; flex-direction:row; flex-wrap:wrap; gap:10px 20px; align-items:center;
  position:sticky; top:0; z-index:99;
}
#tab-cc .filter-bar label { font-size:11px; font-weight:700; color:var(--text2); white-space:nowrap; text-transform:uppercase; letter-spacing:0.8px; }
#tab-cc .filter-bar select, #tab-cc .filter-bar input {
  background:var(--surface); border:1px solid var(--border); color:var(--text);
  padding:6px 10px; border-radius:8px; font-size:12px; font-weight:500;
  outline:none; cursor:pointer; font-family:inherit;
}
#tab-cc .fgroup { display:flex; align-items:center; gap:6px; }
#tab-cc .btn-secondary { padding:6px 14px; border-radius:8px; font-size:12px; cursor:pointer; font-weight:600; border:none; font-family:inherit; background:var(--surface); color:var(--text2); border:1px solid var(--border); }

/* Export button */
#tab-cc .btn-export { background:rgba(16,185,129,0.06); border:1px solid rgba(16,185,129,0.2); color:#10b981; border-radius:8px; font-size:12px; padding:6px 14px; }
#tab-cc .btn-export:hover { background:rgba(16,185,129,0.12); }

/* Info banner: subtle, compact */
#tab-cc .info-banner {
  background:#f8fffe; border:1px solid rgba(16,185,129,0.12); border-radius:12px;
  padding:10px 16px; font-size:12px; color:#475569; display:flex; align-items:center; gap:10px;
}
#tab-cc .info-banner span { font-size:16px; }
#tab-cc .info-banner strong { color:#1e293b; font-weight:600; }

/* Main area */
#tab-cc .main { padding:20px 24px; gap:16px; }
#tab-cc .kpi-grid { gap:12px !important; display:grid !important; grid-template-columns:repeat(6,1fr) !important; }
#tab-cc .kpi-card {
  border-radius:16px !important; padding:18px 14px !important;
  border:1px solid #f1f5f9 !important; box-shadow:0 4px 16px rgba(0,0,0,0.03) !important;
  text-align:center !important;
  display:flex !important; flex-direction:column !important;
  align-items:center !important; justify-content:center !important;
  min-height:110px !important;
}
#tab-cc .kpi-label {
  font-size:9px !important; font-weight:700 !important; letter-spacing:0.6px !important;
  margin-bottom:8px !important; color:#94a3b8 !important;
  text-transform:uppercase !important; text-align:center !important;
}
#tab-cc .kpi-value {
  font-size:22px !important; font-weight:800 !important; letter-spacing:-0.5px !important;
  text-align:center !important; line-height:1.2 !important;
}
#tab-cc .kpi-meta {
  font-size:10px !important; margin-top:6px !important; color:#94a3b8 !important;
  text-align:center !important; line-height:1.3 !important;
}

/* Panels */
#tab-cc .panel, #tab-cc .weekly-panel, #tab-cc .tpanel, #tab-cc .inactive-panel {
  border-radius:16px !important; padding:20px !important;
  border:1px solid #f1f5f9 !important; box-shadow:0 4px 16px rgba(0,0,0,0.03) !important;
  background:#fff !important;
}
#tab-cc .pt { font-size:14px; font-weight:700; }
#tab-cc .ps { font-size:11px; color:#94a3b8; }

/* Tables */
#tab-cc table.dt th, #tab-cc .itable th {
  background:#F8F9FB !important; color:#64748B !important; font-size:10px !important;
  text-transform:uppercase; letter-spacing:0.4px; border-bottom:1px solid #E2E8F0 !important; padding:8px 10px !important;
}
#tab-cc table.dt td, #tab-cc .itable td {
  border-bottom:1px solid #f1f5f9 !important; font-size:12px; padding:8px 10px !important;
}
#tab-cc table.dt tr:hover td, #tab-cc .itable tr:hover td { background:#f8f9fb !important; }
#tab-cc select, #tab-cc input[type=text], #tab-cc .tsearch, #tab-cc .ifilters select, #tab-cc .ifilters input {
  background:#F8F9FB; border:1px solid #E2E8F0; border-radius:8px; color:#1e293b; font-family:inherit; font-size:12px;
}
#tab-cc .chip { background:rgba(93,95,239,0.06); border:1px solid rgba(93,95,239,0.2); color:#5D5FEF; border-radius:20px; font-size:11px; }
#tab-cc .drawer { background:#fff; border-left:1px solid #E2E8F0; box-shadow:-4px 0 20px rgba(0,0,0,0.06); border-radius:16px 0 0 16px; }
#tab-cc .dkpi { background:#F8F9FB; border-radius:10px; }
#tab-cc .ichip { background:#F8F9FB; border-radius:10px; }
""")
        result['css'] = '\n'.join(scoped_lines)

    # Extract body content (from first div after </style> until before final closing tags)
    # Start from <div class="filter-bar"> (header was removed) or fall back to <div class="header">
    body_match = re.search(r'<div class="filter-bar">.*?(?=<script|</body>)', content, re.DOTALL)
    if not body_match:
        body_match = re.search(r'<div class="header">.*?(?=<script|</body>)', content, re.DOTALL)
    if body_match:
        body_html = body_match.group(0)
        # Rename exportToExcel in onclick handlers to avoid conflicts with BO
        body_html = body_html.replace('onclick="exportToExcel()"', 'onclick="showExportModal(\'cc\')"')
        # Remove the CC inline export button (we use the global fixed button now)
        body_html = re.sub(r'<button class="btn-export"[^>]*>.*?</button>', '', body_html, flags=re.DOTALL)
        # Move Weekly chart below KPI grid by extracting between markers
        wp_start = body_html.find('<div class="weekly-panel">')
        kpi_line = '<div class="kpi-grid" id="kpi-grid"></div>'
        kpi_pos = body_html.find(kpi_line)
        if wp_start >= 0 and kpi_pos >= 0:
            # Find the end of the weekly-panel: it closes with </div>\n    <div class="wlegend"...></div>\n  </div>
            wlegend_end = body_html.find('</div>', body_html.find('id="wlegend"', wp_start))
            # The weekly-panel's closing </div> is right after wlegend's closing </div>
            wp_end = body_html.find('</div>', wlegend_end + 6) + 6
            weekly_block = body_html[wp_start:wp_end]
            # Remove from original position
            body_html = body_html[:wp_start] + body_html[wp_end:]
            # Recalculate kpi position after removal
            kpi_pos2 = body_html.find(kpi_line)
            insert_at = kpi_pos2 + len(kpi_line)
            body_html = body_html[:insert_at] + '\n\n  ' + weekly_block + body_html[insert_at:]
        # ── Inject Year filter dropdown into CC filter bar ──
        # Add Year dropdown before the Month dropdown
        year_dropdown = (
            '<div class="fgroup"><label>Year</label>'
            '<select id="f-year" onchange="ccSetYear()">'
            '<option value="all">All Years</option>'
            '<option value="2025">2025</option>'
            '<option value="2026" selected>2026</option>'
            '</select></div>\n  '
        )
        # Insert before the Month fgroup
        month_fgroup = '<div class="fgroup"><label>Month</label>'
        body_html = body_html.replace(month_fgroup, year_dropdown + month_fgroup)

        # Default month dropdown to "All Months" (total)
        body_html = body_html.replace(
            '<option value="total">All Months</option>',
            '<option value="total" selected>All Months</option>'
        )
        body_html = body_html.replace(
            '<option value="mar">March 2026 (W10)</option>',
            '<option value="mar">March 2026 (W10)</option>'  # remove implicit first-selected
        )

        result['html_body'] = body_html

    # Extract all <script> tags content
    script_matches = re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
    if script_matches:
        combined_scripts = '\n'.join(script_matches)
        combined_scripts = combined_scripts.replace('exportToExcel', 'ccExportToExcel')
        combined_scripts = combined_scripts.replace('function ccExportToExcel', 'window.ccExportToExcel = function')

        # ── Chart.js style overrides for modern look ──

        # 1. Weekly chart datasets: smooth curves, updated colors
        combined_scripts = combined_scripts.replace(
            "borderColor: '#4f8ef7',\n      backgroundColor: 'rgba(79,142,247,0.1)',\n      borderWidth: 2.5, fill: true, tension: 0.3,\n      pointRadius: 4, pointHoverRadius: 7",
            "borderColor: '#5D5FEF',\n      backgroundColor: 'rgba(93,95,239,0.08)',\n      borderWidth: 2.5, fill: true, tension: 0.4,\n      pointRadius: 5, pointBackgroundColor:'#5D5FEF', pointBorderColor:'#fff', pointBorderWidth:2, pointHoverRadius: 7"
        )
        combined_scripts = combined_scripts.replace(
            "borderColor: '#22c55e',\n      backgroundColor: 'rgba(34,197,94,0.08)',\n      borderWidth: 2.5, fill: true, tension: 0.3,",
            "borderColor: '#10b981',\n      backgroundColor: 'rgba(16,185,129,0.08)',\n      borderWidth: 2.5, fill: true, tension: 0.4,"
        )
        combined_scripts = combined_scripts.replace(
            "borderColor: '#a78bfa',\n      backgroundColor: 'rgba(167,139,250,0.1)',\n      borderWidth: 2.5, fill: true, tension: 0.3,\n      pointRadius: 4, pointHoverRadius: 7",
            "borderColor: '#5D5FEF',\n      backgroundColor: 'rgba(93,95,239,0.08)',\n      borderWidth: 2.5, fill: true, tension: 0.4,\n      pointRadius: 5, pointBackgroundColor:'#5D5FEF', pointBorderColor:'#fff', pointBorderWidth:2, pointHoverRadius: 7"
        )

        # 2. Weekly chart value labels: white pill instead of dark
        combined_scripts = combined_scripts.replace(
            "c2.fillStyle = 'rgba(18,22,38,0.78)';",
            "c2.fillStyle = 'rgba(255,255,255,0.92)';"
        )
        combined_scripts = combined_scripts.replace(
            "c2.fillStyle = ds.borderColor || '#e2e8f0';",
            "c2.fillStyle = ds.borderColor || '#1A1D23';"
        )
        combined_scripts = combined_scripts.replace(
            "c2.font = '600 10px sans-serif';",
            "c2.font = '700 10px Inter,sans-serif';"
        )

        # 3. ALL grids: display:false (no grid lines anywhere)
        # Use regex to catch ALL variations (different opacities, spacing)
        combined_scripts = _re.sub(
            r"""grid\s*:\s*\{\s*color\s*:\s*['"]rgba\(46,51,72,[^)]+\)['"]\s*\}""",
            "grid:{display:false,drawBorder:false,drawTicks:false}",
            combined_scripts
        )
        combined_scripts = _re.sub(
            r"""grid\s*:\s*\{\s*color\s*:\s*['"]rgba\(0,0,0,[^)]+\)['"]\s*\}""",
            "grid:{display:false,drawBorder:false,drawTicks:false}",
            combined_scripts
        )
        # Also catch any grid:{display:false} without drawBorder and upgrade it
        combined_scripts = combined_scripts.replace(
            "grid:{display:false}",
            "grid:{display:false,drawBorder:false,drawTicks:false}"
        )
        # Also remove any standalone grid:{ } blocks that might still have lines
        combined_scripts = _re.sub(
            r"""grid\s*:\s*\{\s*display\s*:\s*false\s*\}""",
            "grid:{display:false,drawBorder:false,drawTicks:false}",
            combined_scripts
        )
        # Set Chart.js defaults for no borders on axes
        combined_scripts = "Chart.defaults.scales.linear = Chart.defaults.scales.linear || {};\n" + combined_scripts

        # 4. Trend chart: smooth curve, updated colors
        combined_scripts = combined_scripts.replace(
            "tension:0.3,pointRadius:5,pointBackgroundColor:'#4f8ef7'",
            "tension:0.4,pointRadius:5,pointBackgroundColor:'#5D5FEF',pointBorderColor:'#fff',pointBorderWidth:2,pointHoverRadius:7"
        )
        combined_scripts = combined_scripts.replace("borderColor:'#4f8ef7'", "borderColor:'#5D5FEF'")
        combined_scripts = combined_scripts.replace("backgroundColor:'rgba(79,142,247,0.1)'", "backgroundColor:'rgba(93,95,239,0.08)'")

        # 5. Tick/label colors
        combined_scripts = combined_scripts.replace("color:'#8892a4'", "color:'#94a3b8'")
        combined_scripts = combined_scripts.replace("color:'#b0bac9'", "color:'#64748b'")

        # 6. Pareto bars: softer colors
        combined_scripts = combined_scripts.replace("rgba(34,197,94,0.7)", "rgba(16,185,129,0.75)")
        combined_scripts = combined_scripts.replace("rgba(245,158,11,0.7)", "rgba(245,158,11,0.65)")
        combined_scripts = combined_scripts.replace("rgba(239,68,68,0.7)", "rgba(239,68,68,0.6)")
        combined_scripts = combined_scripts.replace("rgba(136,146,164,0.6)", "rgba(148,163,184,0.5)")

        # 7. Remaining accent color replacements
        combined_scripts = combined_scripts.replace("'rgba(79,142,247,", "'rgba(93,95,239,")

        # ── Inject Year filtering logic for CC dashboard ──
        # 1. Add year to state object
        combined_scripts = combined_scripts.replace(
            "const S = {\n  cust:'all', dist:'all', status:'all', month:'mar', brand:'all',",
            "const S = {\n  year:'2026', cust:'all', dist:'all', status:'all', month:'total', brand:'all',"
        )

        # 2. Map each weekly label to a year
        # weeklyXLabels = ["28/12","4/1","11/1","18/1","25/1","1/2","8/2","15/2","22/2","1/3","8/3"]
        # "28/12" → Dec → 2025; rest → 2026
        year_filter_js = r"""

// ── YEAR + MONTH FILTER FOR CC WEEKLY CHART ──────────────────────────────────
// Map weekly labels to years and months
const _ccWeekYearMap = weeklyXLabels.map(lbl => {
  const m = parseInt(lbl.split('/')[1]);
  return m === 12 ? '2025' : '2026';
});
const _ccWeekMonthMap = weeklyXLabels.map(lbl => {
  const m = parseInt(lbl.split('/')[1]);
  if (m === 12) return 'dec';
  if (m === 1) return 'jan';
  if (m === 2) return 'feb';
  if (m === 3) return 'mar';
  return 'unknown';
});

// Month-to-year mapping for the month dropdown
const _ccMonthYear = { dec:'2025', jan:'2026', feb:'2026', mar:'2026', total:'all' };

function ccSetYear() {
  S.year = document.getElementById('f-year').value;
  // Filter month dropdown options based on year
  const monthSel = document.getElementById('f-month');
  const opts = monthSel.options;
  for (let i = 0; i < opts.length; i++) {
    const mv = opts[i].value;
    if (mv === 'total') {
      opts[i].style.display = '';
    } else if (S.year === 'all') {
      opts[i].style.display = '';
    } else {
      opts[i].style.display = (_ccMonthYear[mv] === S.year) ? '' : 'none';
    }
  }
  // If current month selection is hidden, reset to appropriate default
  const curMonth = monthSel.value;
  if (curMonth !== 'total' && S.year !== 'all' && _ccMonthYear[curMonth] !== S.year) {
    if (S.year === '2025') { monthSel.value = 'dec'; S.month = 'dec'; }
    else if (S.year === '2026') { monthSel.value = 'mar'; S.month = 'mar'; }
  }
  updateChips(); renderAll();
}

// Helper: get filtered week indices based on current year + month
function _ccFilteredWeekIndices() {
  let indices = weeklyXLabels.map((_, i) => i);
  // Filter by year
  if (S.year && S.year !== 'all') {
    indices = indices.filter(i => _ccWeekYearMap[i] === S.year);
  }
  // Filter by month (if a specific month is selected, not "total")
  if (S.month && S.month !== 'total') {
    indices = indices.filter(i => _ccWeekMonthMap[i] === S.month);
  }
  return indices;
}

// Override renderWeeklyChart to respect year + month filters
const _origRenderWeeklyChart = renderWeeklyChart;
renderWeeklyChart = function() {
  // Portfolio-level chart — hide when a single customer is selected
  const _noCust  = document.getElementById('weekly-no-cust');
  const _wrap    = document.getElementById('weekly-chart-wrap');
  const _custSel = S.cust !== 'all';
  if (_noCust) _noCust.style.display = _custSel ? 'flex' : 'none';
  if (_wrap)   _wrap.style.display   = _custSel ? 'none' : 'block';
  if (_custSel) { if (charts.weekly) { charts.weekly.destroy(); charts.weekly = null; } return; }

  const mode = _weeklyMode;
  const dk   = _weeklyDistKey();
  const ctx  = document.getElementById('c-weekly').getContext('2d');
  if (charts.weekly) charts.weekly.destroy();
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);

  const isRev = mode === 'rev';
  const _comma = n => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const fmtAx = v => isRev
    ? (v >= 1000000 ? '\u20aa'+(v/1000000).toFixed(1)+'M' : v >= 1000 ? '\u20aa'+Math.round(v/1000)+'K' : '\u20aa'+v)
    : (v >= 1000 ? Math.round(v/1000)+'K' : String(v));
  const fmtTip = v => isRev ? '\u20aa'+_comma(v) : _comma(v)+' units';

  const datasets = _mkWeeklyDatasets(mode);
  _updateWeeklyLegend(dk);

  // Get filtered indices based on year + month
  const filteredIndices = _ccFilteredWeekIndices();

  // Apply rolling window on filtered data
  const winIndices = filteredIndices.slice(-WEEKLY_WINDOW);
  const winLabels = winIndices.map(i => weeklyXLabels[i]);
  const winDatasets = datasets.map(ds => ({...ds, data: winIndices.map(i => ds.data[i])}));

  // Dynamic Y-axis max
  const _flatVals = winDatasets.flatMap(ds => ds.data).filter(v => v != null && isFinite(v) && v > 0);
  const _rawMax   = _flatVals.length ? Math.max(..._flatVals) : (isRev ? 100000 : 10000);
  const _mag      = Math.pow(10, Math.floor(Math.log10(_rawMax)));
  const _yMax     = Math.ceil(_rawMax * 1.20 / _mag) * _mag;

  charts.weekly = new Chart(ctx, {
    type: 'line',
    data: { labels: winLabels, datasets: winDatasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        datalabels: false,
        tooltip: {
          backgroundColor: 'rgba(255,255,255,0.95)',
          titleColor: '#1e293b',
          bodyColor: '#475569',
          borderColor: '#e2e8f0',
          borderWidth: 1,
          padding: 10,
          cornerRadius: 8,
          bodyFont: { family: 'Inter,sans-serif' },
          callbacks: {
            label: function(ctx2) { return ctx2.dataset.label + ': ' + fmtTip(ctx2.parsed.y); }
          }
        }
      },
      scales: {
        x: { ticks: { color: '#94a3b8', font: { size: 11, family: 'Inter,sans-serif' } }, grid: { display: false, drawBorder: false, drawTicks: false } },
        y: { beginAtZero: true, suggestedMax: _yMax, ticks: { color: '#94a3b8', font: { size: 11, family: 'Inter,sans-serif' }, callback: fmtAx }, grid: { display: false, drawBorder: false, drawTicks: false } }
      }
    },
    plugins: [{
      id: 'weeklyValueLabels',
      afterDraw: function(chart) {
        var c2 = chart.ctx;
        chart.data.datasets.forEach(function(ds, di) {
          var meta = chart.getDatasetMeta(di);
          if (!meta || meta.hidden) return;
          meta.data.forEach(function(el, idx) {
            var val = ds.data[idx];
            if (val === null || val === undefined) return;
            var lbl = fmtTip(val);
            c2.save();
            c2.font = '700 12px Inter,sans-serif';
            var tw = c2.measureText(lbl).width + 10;
            var th = 16;
            var lx = el.x, ly = el.y - 10;
            c2.textAlign = 'center';
            c2.textBaseline = 'bottom';
            c2.fillStyle = 'rgba(255,255,255,0.92)';
            var rx = lx - tw/2, ry = ly - th;
            c2.beginPath(); c2.roundRect(rx, ry, tw, th, 3); c2.fill();
            c2.fillStyle = ds.borderColor || '#1A1D23';
            c2.fillText(lbl, lx, ly);
            c2.restore();
          });
        });
      }
    }]
  });
};
"""

        combined_scripts += year_filter_js

        # 3. Patch resetFilters to also reset year to 2026
        combined_scripts = combined_scripts.replace(
            "function resetFilters(){\n  ['f-cust','f-dist','f-status'].forEach(id=>document.getElementById(id).value='all');\n  document.getElementById('f-month').value='mar';",
            "function resetFilters(){\n  ['f-cust','f-dist','f-status'].forEach(id=>document.getElementById(id).value='all');\n  document.getElementById('f-year').value='2026';\n  S.year='2026';\n  document.getElementById('f-month').value='total';"
        )

        # 4. Patch applyFilters to also read year
        combined_scripts = combined_scripts.replace(
            "function applyFilters(){\n  S.cust  = document.getElementById('f-cust').value;",
            "function applyFilters(){\n  S.year  = document.getElementById('f-year').value;\n  S.cust  = document.getElementById('f-cust').value;"
        )

        # 5. Patch DOMContentLoaded boot to trigger year filter on load
        # After renderAll() in boot, call ccSetYear to apply initial year filter
        combined_scripts = combined_scripts.replace(
            "renderAll();\n});",
            "renderAll();\n  ccSetYear();\n});"
        )

        # 6. Translate Returns KPI card from Hebrew to English
        combined_scripts = combined_scripts.replace("'החזרות — מעיין'", "'Returns — Ma\\'ayan'")
        combined_scripts = combined_scripts.replace("'החזרות — אייסדרים'", "'Returns — Icedreams'")
        combined_scripts = combined_scripts.replace("'החזרות — כלל'", "'Returns — All'")
        combined_scripts = combined_scripts.replace('אבדן הכנסה', 'Revenue Loss')
        combined_scripts = combined_scripts.replace('שיעור החזרה', 'Return Rate')

        result['scripts'] = combined_scripts

    return result




# ── Embedded CC HTML Source ────────────────────────────────────────────────────
# Raw copy of: dashboards/customer centric dashboard 11.3.26.html
# Last data update: W12 (15/3/2026), Biscotti W12-W13 (22/3/2026)
# To update: edit arrays _iceWkRev, _iceWkUnits, customers[], weeklyDetailHistory[], etc.
_CC_HTML = r"""<!DOCTYPE html>
<html lang="he" dir="ltr">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Customer-Centric Trade &amp; Sales Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0f1117;--surface:#1a1d27;--surface2:#22263a;--border:#2e3348;
  --text:#e2e8f0;--text2:#8892a4;--accent:#4f8ef7;--green:#22c55e;
  --amber:#f59e0b;--red:#ef4444;--purple:#a855f7;--orange:#f97316;
  --radius:10px;
}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;font-size:14px;min-height:100vh}
.header{background:var(--surface);border-bottom:1px solid var(--border);padding:14px 180px 14px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:99}
.header h1{font-size:17px;font-weight:700}
.header h1 span{font-weight:400;color:var(--text2);font-size:13px;margin-left:8px}
.badges{display:flex;gap:8px}
.badge{background:var(--surface2);border:1px solid var(--border);padding:3px 10px;border-radius:20px;font-size:11px;color:var(--text2)}
.badge.green{border-color:var(--green);color:var(--green)}
.badge.amber{border-color:var(--amber);color:var(--amber)}
.btn-export{background:rgba(34,197,94,0.12);border:1px solid rgba(34,197,94,0.4);color:var(--green);padding:6px 14px;border-radius:7px;font-size:12px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:6px;transition:all .15s}
.btn-export:hover{background:rgba(34,197,94,0.22);border-color:var(--green)}
.btn-export svg{flex-shrink:0}
.filter-bar{background:var(--surface);border-bottom:1px solid var(--border);padding:16px 32px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:99}
.fgroup{display:flex;align-items:center;gap:6px}
.fgroup label{font-size:11px;font-weight:700;color:var(--text2);white-space:nowrap;text-transform:uppercase;letter-spacing:0.8px}
select,input[type=text]{background:var(--surface);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:8px;font-size:12px;font-weight:500;outline:none;cursor:pointer;font-family:inherit}
select:focus,input:focus{border-color:var(--accent)}
.btn{padding:6px 14px;border-radius:8px;font-size:12px;cursor:pointer;font-weight:600;border:none;font-family:inherit}
.btn-secondary{background:var(--surface);color:var(--text2);border:1px solid var(--border)}
.btn-secondary:hover{border-color:var(--accent);color:var(--accent)}
.chips{display:flex;gap:5px;flex-wrap:wrap}
.chip{background:rgba(79,142,247,0.12);border:1px solid rgba(79,142,247,0.35);color:var(--accent);padding:3px 9px;border-radius:20px;font-size:11px;display:flex;align-items:center;gap:5px}
.chip button{background:none;border:none;color:inherit;cursor:pointer}
.main{padding:18px 24px;display:flex;flex-direction:column;gap:18px}
.kpi-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}
@media(max-width:1300px){.kpi-grid{grid-template-columns:repeat(3,1fr)}}
.kpi-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:15px;transition:border-color .2s}
.kpi-card:hover{border-color:var(--accent)}
.kpi-label{font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.5px;margin-bottom:7px}
.kpi-value{font-size:21px;font-weight:700}
.kpi-meta{margin-top:5px;font-size:11px;color:var(--text2)}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:3px}
.dot-g{background:var(--green)}.dot-a{background:var(--amber)}.dot-r{background:var(--red)}
.up{color:var(--green)}.down{color:var(--red)}
.row2{display:grid;grid-template-columns:2fr 1fr;gap:16px}
.row2b{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.row2b.single{grid-template-columns:1fr;max-width:100%}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:17px}
.ph{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:14px}
.pt{font-size:13px;font-weight:600}
.ps{font-size:11px;color:var(--text2);margin-top:2px}
.tab-grp{display:flex;gap:4px}
.tab{background:none;border:1px solid var(--border);color:var(--text2);padding:4px 9px;border-radius:4px;font-size:11px;cursor:pointer}
.tab.on{background:var(--accent);border-color:var(--accent);color:#fff}
.tab.on-turbo{background:#0ea5e9;border-color:#0ea5e9;color:#fff}
.tab.on-danis{background:var(--purple);border-color:var(--purple);color:#fff}
.chart-box{position:relative;height:255px}
.tpanel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:17px}
.tsearch{background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 11px;border-radius:6px;font-size:12px;width:210px;outline:none}
.tsearch:focus{border-color:var(--accent)}
table.dt{width:100%;border-collapse:collapse;font-size:12px;margin-top:11px}
table.dt th{background:var(--surface2);color:var(--text2);font-weight:600;padding:8px 11px;text-align:left;border-bottom:1px solid var(--border);cursor:pointer;white-space:nowrap;user-select:none}
table.dt th:hover{color:var(--accent)}
table.dt td{padding:8px 11px;border-bottom:1px solid rgba(46,51,72,0.45);color:var(--text)}
table.dt tr:hover td{background:rgba(79,142,247,0.05);cursor:pointer}
table.dt tr.sel td{background:rgba(79,142,247,0.1);border-left:3px solid var(--accent)}
.pct-bar{display:flex;align-items:center;gap:6px}
.bar-bg{background:var(--surface2);border-radius:3px;height:5px;width:55px;flex-shrink:0}
.bar-fg{height:100%;border-radius:3px}
.drawer{display:none;position:fixed;right:0;top:0;bottom:0;width:430px;background:var(--surface);border-left:1px solid var(--border);z-index:200;padding:22px;overflow-y:auto;box-shadow:-6px 0 30px rgba(0,0,0,0.5)}
.drawer.open{display:block}
.dh{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.dt-name{font-size:15px;font-weight:700}
.dclose{background:none;border:1px solid var(--border);color:var(--text);padding:4px 9px;border-radius:5px;cursor:pointer;font-size:12px}
.dkpis{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:18px;margin-top:14px}
.dkpi{background:var(--surface2);border-radius:7px;padding:11px}
.dkpi-l{font-size:10px;color:var(--text2);margin-bottom:3px}
.dkpi-v{font-size:15px;font-weight:700}
.sec{font-size:10px;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px;margin-top:16px}
.dch{height:150px;margin-bottom:4px}
.dtag{display:inline-block;padding:2px 7px;border-radius:10px;font-size:10px;font-weight:600}
.dtag.active{background:rgba(34,197,94,0.12);color:var(--green);border:1px solid rgba(34,197,94,0.25)}
.dtag.negotiation{background:rgba(245,158,11,0.12);color:var(--amber);border:1px solid rgba(245,158,11,0.25)}
.dtag.sales-only{background:rgba(79,142,247,0.12);color:var(--accent);border:1px solid rgba(79,142,247,0.25)}
.brand-tag{display:inline-block;padding:2px 6px;border-radius:8px;font-size:10px;font-weight:600;margin-left:4px}
.brand-turbo{background:rgba(14,165,233,0.12);color:#0ea5e9;border:1px solid rgba(14,165,233,0.25)}
.brand-danis{background:rgba(168,85,247,0.12);color:var(--purple);border:1px solid rgba(168,85,247,0.25)}
table.skut{width:100%;border-collapse:collapse;font-size:11px}
table.skut th{color:var(--text2);font-weight:600;padding:5px 7px;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap}
table.skut td{padding:5px 7px;border-bottom:1px solid rgba(46,51,72,0.35);color:var(--text)}
.ql-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-top:10px}
.ql{padding:4px 7px;border-radius:4px;font-size:10px;text-align:center}
.ql.star{background:rgba(34,197,94,0.08);color:var(--green);border:1px solid rgba(34,197,94,0.2)}
.ql.risk{background:rgba(239,68,68,0.08);color:var(--red);border:1px solid rgba(239,68,68,0.2)}
.ql.em{background:rgba(79,142,247,0.08);color:var(--accent);border:1px solid rgba(79,142,247,0.2)}
.ql.tail{background:rgba(100,116,139,0.08);color:var(--text2);border:1px solid var(--border)}
.info-banner{background:rgba(34,197,94,0.05);border:1px solid rgba(34,197,94,0.2);border-radius:10px;padding:12px 18px;display:flex;align-items:center;gap:14px;font-size:12px;color:var(--text2)}
.info-banner strong{color:var(--text)}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

/* Weekly chart */
.weekly-panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px 20px;margin-bottom:0}
.weekly-box{position:relative;height:320px}
.wlegend{display:flex;gap:18px;align-items:center;margin-top:10px;flex-wrap:wrap}
.wleg-item{display:flex;align-items:center;gap:7px;font-size:11px;color:var(--text2)}
.wleg-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.wleg-line{width:22px;height:3px;border-radius:2px;flex-shrink:0}

</style>
</head>
<body>


<div class="filter-bar">
  <div class="fgroup"><label>Customer</label>
    <select id="f-cust" onchange="applyFilters()"><option value="all">All Customers</option></select></div>
  <div class="fgroup"><label>Distributor</label>
    <select id="f-dist" onchange="applyFilters()">
      <option value="all">All</option>
      <option value="אייסדרים">Icedream</option>
      <option value="מעיין">Ma'ayan</option>
      <option value="none">No Pricing Data</option>
      <option value="ביסקוטי">Biscotti</option>
    </select></div>
  <div class="fgroup"><label>Status</label>
    <select id="f-status" onchange="applyFilters()">
      <option value="all">All</option>
      <option value="active">Active</option>
      <option value="negotiation">Negotiation</option>
    </select></div>
  <div class="fgroup"><label>Month</label>
    <select id="f-month" onchange="applyFilters()">
      <option value="mar" id="opt-mar">March 2026 (W12)</option>
      <option value="feb">February 2026</option>
      <option value="jan">January 2026</option>
      <option value="dec">December 2025</option>
      <option value="total">All Months</option>
    </select></div>
  <div class="fgroup"><label>Brand</label>
    <div class="tab-grp">
      <button class="tab on" id="bb-all"   onclick="setBrand('all')">All Brands</button>
      <button class="tab"    id="bb-turbo" onclick="setBrand('turbo')">Turbo</button>
      <button class="tab"    id="bb-danis" onclick="setBrand('danis')">Dani's</button>
    </div>
  </div>
  <button class="btn btn-secondary" onclick="resetFilters()">Reset</button>
  <div class="chips" id="chips"></div>
</div>

<div class="main">


  <div class="weekly-panel">
    <div class="ph">
      <div>
        <div class="pt">Weekly Sales Trend — Icedreams · Ma'ayan · Biscotti</div>
        <div class="ps" id="chart-subtitle">28/12–22/3 2026 · Each point = week start (Sunday) · Icedreams W1–W13 · Ma'ayan W6–W11 · Biscotti W12–W13 · Rolling 10-week window</div>
      </div>
      <div class="tab-grp">
        <button class="tab on" id="wb-rev" onclick="setWeeklyMode('rev')">Revenue ₪</button>
        <button class="tab" id="wb-u" onclick="setWeeklyMode('units')">Units</button>
      </div>
    </div>
    <div id="weekly-no-cust" style="display:none;flex-direction:column;align-items:center;justify-content:center;height:180px;gap:10px;color:var(--text2);font-size:13px">
      <svg width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24" style="opacity:.5"><circle cx="12" cy="12" r="10"/><path d="M12 8v4m0 4h.01" stroke-linecap="round"/></svg>
      <span>Weekly trend shows <strong>portfolio-level</strong> data &mdash; select <strong>All Customers</strong> to view</span>
    </div>
    <div id="weekly-chart-wrap">
      <div class="weekly-box"><canvas id="c-weekly"></canvas></div>
      <div class="wlegend" id="wlegend"></div>
    </div>
  </div>

  <div class="kpi-grid" id="kpi-grid"></div>

  <div class="row2b">
    <div class="panel">
      <div class="ph">
        <div><div class="pt">Customer Revenue Ranking — Pareto</div><div class="ps">Click bar → customer detail · color = Gross Margin RAG</div></div>
        <div class="tab-grp">
          <button class="tab on" id="pb-rev" onclick="setParetoMode('revenue')">Revenue</button>
          <button class="tab"    id="pb-u"   onclick="setParetoMode('units')">Units</button>
        </div>
      </div>
      <div class="chart-box"><canvas id="c-pareto"></canvas></div>
    </div>
    <div class="panel">
      <div class="ph">
        <div><div class="pt">Portfolio Revenue Trend</div><div class="ps" id="trend-subtitle">Monthly VAT0 + units</div></div>
        <div class="tab-grp">
          <button class="tab on" id="tb-r" onclick="setTrendMode('rev')">Revenue</button>
          <button class="tab"    id="tb-u" onclick="setTrendMode('units')">Units</button>
        </div>
      </div>
      <div class="chart-box"><canvas id="c-trend"></canvas></div>
    </div>
  </div>

  <div class="row2b single">
    <div class="panel">
      <div class="ph"><div><div class="pt">Product Mix per Customer</div><div class="ps">Units share by SKU · all months combined</div></div></div>
      <div class="chart-box"><canvas id="c-mix"></canvas></div>
    </div>
  </div>

  <div class="tpanel">
    <div class="ph">
      <div><div class="pt">Customer Performance Table</div><div class="ps">Click row → customer detail</div></div>
      <input class="tsearch" id="t-search" placeholder="Search customer…" oninput="renderTable()"/>
    </div>
    <table class="dt">
      <thead><tr id="t-head">
        <th onclick="sortBy('name')">Customer ↕</th>
        <th onclick="sortBy('revActive')">Revenue ↕</th>
        <th>VAT18%</th>
        <th onclick="sortBy('share')">Share % ↕</th>
        <th onclick="sortBy('grossMargin')">Gross % ↕</th>
        <th onclick="sortBy('grossVal')">Gross ₪ ↕</th>
        <th onclick="sortBy('opMargin')">Op % ↕</th>
        <th onclick="sortBy('opVal')">Op ₪ ↕</th>
        <th onclick="sortBy('unitsActive')">Units ↕</th>
        <th onclick="sortBy('momGrowth')">MoM ↕</th>
        <th onclick="sortBy('distributor')">Distributor ↕</th>
        <th onclick="sortBy('status')">Status ↕</th>
      </tr></thead>
      <tbody id="t-body"></tbody>
    </table>
  </div>
</div>


<div class="drawer" id="drawer">
  <div class="dh">
    <div class="dt-name" id="d-name">—</div>
    <button class="dclose" onclick="closeDrawer()">✕ Close</button>
  </div>
  <div id="d-tag-row" style="margin-bottom:4px"></div>
  <div class="dkpis" id="d-kpis"></div>
  <div class="sec">Monthly Revenue (Dec – Feb 2026)</div>
  <div class="dch"><canvas id="d-chart"></canvas></div>
  <div class="sec" id="d-sku-sec">SKU Price List</div>
  <table class="skut">
    <thead><tr><th>Product</th><th>VAT0</th><th>VAT18%</th><th>Cost</th><th>Gross%</th><th>Op%</th><th>Dist%</th></tr></thead>
    <tbody id="d-skus"></tbody>
  </table>
</div>

<script>
// ── DATA ──────────────────────────────────────────────────────────────────────
// Nov excluded. Feb = complete month. Sub-customers extracted from detail sheets.
// Brand: turbo = ice cream (Turbo brand), danis = dream cake (Dani's brand)
// Price DB updated: 24/2 — אייסדרים dist 15%, dream_cake cost 53.5
// Revenue verified against actual files: ICEDREAM-*.xlsx (actual invoice) + Mayyan_Turbo.xlsx (units×₪13.8)
// Last updated: 10/03/2026 — Icedreams customers recalculated from files (וולט, ינגו, כרמלה, נוי השדה)
// Biscotti (ביסקוטי): Dream Cake distributor (dream_cake_2). Active from 18/3/2026.
// Sale price ₪80/unit, 0% commission, 27.5% gross margin. Data: daniel_amit_weekly_biscotti.xlsx.

const customers = [
  {id:1,  name:"AMPM",          status:"active",      distributor:"מעיין נציגויות", dist_pct:25, avgPrice:12.39,  grossMargin:47.42, opMargin:22.42, activeSKUs:4,  hasPricing:true,  hasSales:true, brands:['turbo'],
          revenue:{dec:240426.31, jan:49814.27, feb:136710.57, mar:31966.2},  units:{dec:19412, jan:4023,  feb:11038, mar:2580}, momGrowth:174.4},
  {id:2,  name:"Alonit",        status:"active",      distributor:"מעיין נציגויות", dist_pct:25, avgPrice:12.27,  grossMargin:46.95, opMargin:21.95, activeSKUs:4,  hasPricing:true,  hasSales:true, brands:['turbo'],
          revenue:{dec:18184.96, jan:17252.4, feb:21203.52, mar:4417.2},   units:{dec:1482,  jan:1406,  feb:1728, mar:360},   momGrowth:22.9},
  {id:3,  name:"Good Pharm",      status:"active",      distributor:"אייסדרים",       dist_pct:15, avgPrice:12.67,  grossMargin:48.70, opMargin:33.70, activeSKUs:4,  hasPricing:true,  hasSales:true, brands:['turbo'],
          revenue:{dec:0,      jan:14620,  feb:0, mar:2066},   units:{dec:0,     jan:1128,  feb:0, mar:156},   momGrowth:null},
  {id:4,  name:"Delek",           status:"active",      distributor:"מעיין נציגויות", dist_pct:25, avgPrice:12.74,  grossMargin:48.98, opMargin:23.98, activeSKUs:4,  hasPricing:true,  hasSales:true, brands:['turbo'],
          revenue:{dec:29442.14, jan:19415.76, feb:12714.52, mar:7644.0},   units:{dec:2311,  jan:1524,  feb:998, mar:600},   momGrowth:-34.5},
  {id:5,  name:"Wolt Market",    status:"active",      distributor:"אייסדרים",       dist_pct:15, avgPrice:37.5,   grossMargin:37.44, opMargin:22.44, activeSKUs:6,  hasPricing:true,  hasSales:true, brands:['turbo','danis'],
          revenue:{dec:644423,    jan:526052,   feb:400142,   mar:78278},
          turboRev:{dec:178502,   jan:77973,    feb:104044,   mar:18672},  danisRev:{dec:465921,   jan:448079,  feb:296098,  mar:59607},
          units:{dec:18951,       jan:11588,    feb:11350,    mar:2077},
          turboUnits:{dec:13146,  jan:6063,     feb:7699,     mar:1342},  danisUnits:{dec:5805,   jan:5525,    feb:3651,    mar:735},
          momGrowth:-80.5},
  {id:6,  name:"Tiv Taam",       status:"active",      distributor:"מעיין נציגויות", dist_pct:25, avgPrice:14.2,   grossMargin:54.23, opMargin:29.23, activeSKUs:4,  hasPricing:true,  hasSales:true, brands:['turbo'],
          revenue:{dec:47286.0, jan:15871.6, feb:22720.0, mar:11502.0},   units:{dec:3330,  jan:1118,  feb:1600, mar:810},   momGrowth:43.1},
  {id:7,  name:"Yingo Deli",      status:"active",      distributor:"אייסדרים",       dist_pct:15, avgPrice:39.9,   grossMargin:40.25, opMargin:25.25, activeSKUs:6,  hasPricing:true,  hasSales:true, brands:['turbo','danis'],
          revenue:{dec:25173,  jan:33718,    feb:25041,    mar:35037},
          turboRev:{dec:2673,  jan:7169,     feb:13041,    mar:11637},  danisRev:{dec:22500, jan:26549,  feb:12000,  mar:23400},
          units:{dec:348,      jan:708,      feb:1046,     mar:1018},
          turboUnits:{dec:198, jan:531,      feb:966,      mar:862},    danisUnits:{dec:150, jan:177,    feb:80,     mar:156},
          momGrowth:39.9},
  {id:8,  name:"Carmela",         status:"active",      distributor:"אייסדרים",       dist_pct:15, avgPrice:15.6,   grossMargin:43.49, opMargin:28.49, activeSKUs:6,  hasPricing:true,  hasSales:true, brands:['turbo','danis'],
          revenue:{dec:17185,    jan:4470,     feb:2676,     mar:980},
          turboRev:{dec:17185,   jan:1800,     feb:1341,     mar:980},  danisRev:{dec:0,    jan:2670,    feb:1335,    mar:0},
          units:{dec:1272,       jan:180,      feb:105,      mar:70},
          turboUnits:{dec:1272,  jan:150,      feb:90,       mar:70},   danisUnits:{dec:0,  jan:30,      feb:15,      mar:0},
          momGrowth:-63.4},
  {id:9,  name:"Noy Hasade",      status:"active",      distributor:"אייסדרים",       dist_pct:15, avgPrice:13.4,   grossMargin:49.53, opMargin:34.53, activeSKUs:5,  hasPricing:true,  hasSales:true, brands:['turbo','danis'],
          revenue:{dec:13409,    jan:13679,   feb:0,   mar:0},
          turboRev:{dec:13409,   jan:13679,   feb:0,   mar:0},  danisRev:{dec:0,    jan:0,   feb:0,   mar:0},
          units:{dec:978,        jan:1044,    feb:0,   mar:0},
          turboUnits:{dec:978,   jan:1044,    feb:0,   mar:0},  danisUnits:{dec:0,  jan:0,   feb:0,   mar:0},
          momGrowth:-100.0},
  {id:10, name:"Carrefour",        status:"negotiation", distributor:"מעיין נציגויות", dist_pct:25, avgPrice:13.8,   grossMargin:52.9,  opMargin:27.9,  activeSKUs:3,  hasPricing:true,  hasSales:false, brands:['turbo'],
          revenue:{dec:0, jan:0, feb:0, mar:0}, units:{dec:0, jan:0, feb:0, mar:0}, momGrowth:null},
  {id:11, name:"Private Market",      status:"active",      distributor:"מעיין נציגויות", dist_pct:25, avgPrice:14.1,   grossMargin:53.9,  opMargin:28.9,  activeSKUs:4,  hasPricing:true,  hasSales:true, brands:['turbo'],
          revenue:{dec:380643.6, jan:203673.0, feb:275514.0, mar:106652.4}, units:{dec:26996, jan:14445, feb:19540, mar:7564}, momGrowth:35.1},
  {id:12, name:"Ugipletzet",     status:"active",      distributor:"אייסדרים",       dist_pct:15, avgPrice:null,   grossMargin:null,  opMargin:null,  activeSKUs:3,  hasPricing:false, hasSales:true, brands:['turbo'],
          revenue:{dec:0, jan:0, feb:19967.79, mar:7650}, units:{dec:0, jan:0, feb:1582, mar:51}, momGrowth:null},
  {id:13, name:"Paz Yellow",        status:"active",      distributor:"מעיין נציגויות", dist_pct:25, avgPrice:11.0,   grossMargin:40.91, opMargin:15.91, activeSKUs:3,  hasPricing:true,  hasSales:true, brands:['turbo'],
          revenue:{dec:29832.0, jan:64856.0, feb:72105.0, mar:25300.0},  units:{dec:2712,  jan:5896,  feb:6555, mar:2300},  momGrowth:11.2},
  {id:14, name:"Paz Super Yuda",  status:"active",      distributor:"מעיין נציגויות", dist_pct:25, avgPrice:11.0,   grossMargin:40.91, opMargin:15.91, activeSKUs:3,  hasPricing:true,  hasSales:true, brands:['turbo'],
          revenue:{dec:53592.0, jan:15983.0, feb:20240.0, mar:9570.0},  units:{dec:4872,  jan:1453,  feb:1840, mar:870},  momGrowth:26.6},
  {id:15, name:"Sonol",         status:"active",      distributor:"מעיין נציגויות", dist_pct:25, avgPrice:14.0,   grossMargin:53.57, opMargin:28.57, activeSKUs:3,  hasPricing:true,  hasSales:true, brands:['turbo'],
          revenue:{dec:8736.0, jan:6832.0, feb:6692.0, mar:840.0},   units:{dec:624,   jan:488,   feb:478, mar:60},   momGrowth:-2.0},
  {id:16, name:"Domino's",       status:"active",      distributor:"אייסדרים",       dist_pct:15, avgPrice:11.4,   grossMargin:42.98, opMargin:27.98, activeSKUs:4,  hasPricing:true,  hasSales:true, brands:['turbo'],
          revenue:{dec:0,      jan:63418,  feb:0,    mar:5407},   units:{dec:0,     jan:5646,  feb:0,    mar:472},   momGrowth:null},
  {id:17, name:"Naomi's Farm",    status:"active",      distributor:"אייסדרים",       dist_pct:15, avgPrice:35.03,  grossMargin:39.48, opMargin:24.48, activeSKUs:5,  hasPricing:true,  hasSales:true, brands:['turbo','danis'],
          revenue:{dec:7185,   jan:17277,  feb:30748.3,  mar:29768},
          turboRev:{dec:5940,  jan:4329,   feb:3607.48,  mar:966},    danisRev:{dec:1245, jan:12948, feb:27140.82, mar:28802},
          units:{dec:465, jan:484, feb:595, mar:417},
          turboUnits:{dec:450, jan:328, feb:268, mar:70},              danisUnits:{dec:15, jan:156, feb:327, mar:347},
          momGrowth:-3.2},
  {id:18, name:"Hama",          status:"negotiation", distributor:"אייסדרים",       dist_pct:15, avgPrice:14.1,   grossMargin:53.9,  opMargin:38.9,  activeSKUs:4,  hasPricing:true,  hasSales:false, brands:['turbo'],
          revenue:{dec:0, jan:0, feb:0, mar:0}, units:{dec:0, jan:0, feb:0, mar:0}, momGrowth:null},
  {id:19, name:"Foot Locker",      status:"active",      distributor:"אייסדרים",       dist_pct:15, avgPrice:15.5,   grossMargin:58.06, opMargin:43.06, activeSKUs:4,  hasPricing:true,  hasSales:true, brands:['turbo'],
          revenue:{dec:0, jan:0, feb:0, mar:1302}, units:{dec:0, jan:0, feb:0, mar:84}, momGrowth:null},
  {id:20, name:"Biscotti Chain", status:"active",    distributor:"ביסקוטי",         dist_pct:0,  avgPrice:80.0,   grossMargin:27.5,  opMargin:27.5,  activeSKUs:1,  hasPricing:true,  hasSales:true, brands:['danis'],
          revenue:{dec:0, jan:0, feb:0, mar:9680},
          turboRev:{dec:0, jan:0, feb:0, mar:0},    danisRev:{dec:0, jan:0, feb:0, mar:9680},
          units:{dec:0, jan:0, feb:0, mar:121},
          turboUnits:{dec:0, jan:0, feb:0, mar:0},  danisUnits:{dec:0, jan:0, feb:0, mar:121},
          momGrowth:null},
];

// Product mix per customer (total units, all months combined)
const productMix = {
  1:  {chocolate:11782, vanilla:11118, mango:6992, pistachio:4580},
  2:  {chocolate:1725,  vanilla:1581,  mango:1150, pistachio:160},
  3:  {chocolate:420,   vanilla:426,   mango:314,  pistachio:20},
  4:  {chocolate:1829,  vanilla:1706,  mango:1278},
  5:  {chocolate:7527,  vanilla:7164,  mango:4109, dream_cake:15716, pistachio:3750, magadat:5700},
  6:  {chocolate:2255,  vanilla:2156,  mango:1463},
  7:  {chocolate:768,   vanilla:876,   mango:480,  dream_cake:506,  magadat:45},
  8:  {chocolate:420,   vanilla:390,   mango:240,  pistachio:70, dream_cake:45,  magadat:462},
  9:  {chocolate:702,   vanilla:708,   mango:564,  magadat:48},
  11: {chocolate:21435, vanilla:20566, mango:13213,pistachio:5697},
  12: {chocolate:630,   vanilla:492,   mango:320,  pistachio:140, dream_cake:51},
  13: {chocolate:5808,  vanilla:5416,  mango:3939},
  14: {chocolate:3244,  vanilla:2949,  mango:1972},
  15: {chocolate:620,   vanilla:646,   mango:360},
  16: {chocolate:2060,  vanilla:1920,  mango:1796, pistachio:30},
  17: {chocolate:330,   vanilla:378,   mango:238,  pistachio:100, dream_cake:498},
  19: {chocolate:20,    vanilla:24,    mango:20,   pistachio:20},
};

// SKU price list per customer (from price DB - updated 24/2)
const skuDetail = {
  1: [{name:"גלידת חלבון וניל",      p0:12.23,p18:14.43,cost:6.5, gm:46.85,om:21.85,dp:25},
      {name:"גלידת חלבון מנגו",      p0:12.23,p18:14.43,cost:6.5, gm:46.85,om:21.85,dp:25},
      {name:"גלידת חלבון שוקולד לוז",p0:12.23,p18:14.43,cost:6.5, gm:46.85,om:21.85,dp:25},
      {name:"גלידת חלבון פיסטוק",    p0:13.4, p18:15.81,cost:6.5, gm:51.49,om:26.49,dp:25}],
  2: [{name:"גלידת חלבון וניל",      p0:12.23,p18:14.43,cost:6.5, gm:46.85,om:21.85,dp:25},
      {name:"גלידת חלבון מנגו",      p0:12.23,p18:14.43,cost:6.5, gm:46.85,om:21.85,dp:25},
      {name:"גלידת חלבון שוקולד לוז",p0:12.23,p18:14.43,cost:6.5, gm:46.85,om:21.85,dp:25},
      {name:"גלידת חלבון פיסטוק",    p0:13.4, p18:15.81,cost:6.5, gm:51.49,om:26.49,dp:25}],
  3: [{name:"גלידת חלבון וניל",      p0:12.66,p18:14.94,cost:6.5, gm:48.66,om:33.66,dp:15},
      {name:"גלידת חלבון מנגו",      p0:12.66,p18:14.94,cost:6.5, gm:48.66,om:33.66,dp:15},
      {name:"גלידת חלבון שוקולד לוז",p0:12.66,p18:14.94,cost:6.5, gm:48.66,om:33.66,dp:15},
      {name:"גלידת חלבון פיסטוק",    p0:13.2, p18:15.58,cost:6.5, gm:50.76,om:35.76,dp:15}],
  4: [{name:"גלידת חלבון וניל",      p0:12.74,p18:15.03,cost:6.5, gm:48.98,om:23.98,dp:25},
      {name:"גלידת חלבון מנגו",      p0:12.74,p18:15.03,cost:6.5, gm:48.98,om:23.98,dp:25},
      {name:"גלידת חלבון שוקולד לוז",p0:12.74,p18:15.03,cost:6.5, gm:48.98,om:23.98,dp:25},
      {name:"גלידת חלבון פיסטוק",    p0:13.56,p18:16.0, cost:6.5, gm:52.06,om:27.06,dp:25}],
  5: [{name:"גלידת חלבון וניל",      p0:13.8, p18:16.28,cost:6.5, gm:52.9, om:37.9, dp:15},
      {name:"גלידת חלבון מנגו",      p0:13.8, p18:16.28,cost:6.5, gm:52.9, om:37.9, dp:15},
      {name:"גלידת חלבון שוקולד לוז",p0:13.8, p18:16.28,cost:6.5, gm:52.9, om:37.9, dp:15},
      {name:"גלידת חלבון פיסטוק",    p0:13.8, p18:16.28,cost:6.5, gm:52.9, om:37.9, dp:15},
      {name:"דרים קייק",             p0:81.1, p18:95.7, cost:53.5, gm:34.03,om:19.03,dp:15},
      {name:"מארז שלישיית גלידות",   p0:35.0, p18:41.3, cost:22.5, gm:35.71,om:20.71,dp:15}],
  6: [{name:"גלידת חלבון וניל",      p0:14.2, p18:16.76,cost:6.5, gm:54.23,om:29.23,dp:25},
      {name:"גלידת חלבון מנגו",      p0:14.2, p18:16.76,cost:6.5, gm:54.23,om:29.23,dp:25},
      {name:"גלידת חלבון שוקולד לוז",p0:14.2, p18:16.76,cost:6.5, gm:54.23,om:29.23,dp:25},
      {name:"גלידת חלבון פיסטוק",    p0:14.2, p18:16.76,cost:6.5, gm:54.23,om:29.23,dp:25}],
  7: [{name:"גלידת חלבון וניל",      p0:13.5, p18:15.93,cost:6.5, gm:51.85,om:36.85,dp:15},
      {name:"גלידת חלבון מנגו",      p0:13.5, p18:15.93,cost:6.5, gm:51.85,om:36.85,dp:15},
      {name:"גלידת חלבון שוקולד לוז",p0:13.5, p18:15.93,cost:6.5, gm:51.85,om:36.85,dp:15},
      {name:"גלידת חלבון פיסטוק",    p0:13.9, p18:16.4, cost:6.5, gm:53.24,om:38.24,dp:15},
      {name:"דרים קייק",             p0:81.2, p18:95.82,cost:53.5, gm:34.11,om:19.11,dp:15},
      {name:"מארז שלישיית גלידות",   p0:34.0, p18:40.12,cost:22.5, gm:33.82,om:18.82,dp:15}],
  8: [{name:"גלידת חלבון וניל",      p0:14.0, p18:16.52,cost:6.5, gm:53.57,om:38.57,dp:15},
      {name:"גלידת חלבון מנגו",      p0:14.0, p18:16.52,cost:6.5, gm:53.57,om:38.57,dp:15},
      {name:"גלידת חלבון שוקולד לוז",p0:14.0, p18:16.52,cost:6.5, gm:53.57,om:38.57,dp:15},
      {name:"גלידת חלבון פיסטוק",    p0:14.0, p18:16.52,cost:6.5, gm:53.57,om:38.57,dp:15},
      {name:"דרים קייק",             p0:89.0, p18:105.02,cost:53.5,gm:39.89,om:24.89,dp:15},
      {name:"מארז שלישיית גלידות",   p0:36.0, p18:42.48,cost:22.5, gm:37.5, om:22.5, dp:15}],
  9: [{name:"גלידת חלבון וניל",      p0:13.1, p18:15.46,cost:6.5, gm:50.38,om:35.38,dp:15},
      {name:"גלידת חלבון מנגו",      p0:13.1, p18:15.46,cost:6.5, gm:50.38,om:35.38,dp:15},
      {name:"גלידת חלבון שוקולד לוז",p0:13.1, p18:15.46,cost:6.5, gm:50.38,om:35.38,dp:15},
      {name:"גלידת חלבון פיסטוק",    p0:13.9, p18:16.4, cost:6.5, gm:53.24,om:38.24,dp:15},
      {name:"מארז שלישיית גלידות",   p0:34.0, p18:40.12,cost:22.5, gm:33.82,om:18.82,dp:15}],
  10:[{name:"גלידת חלבון וניל",      p0:13.8, p18:16.28,cost:6.5, gm:52.9, om:27.9, dp:25},
      {name:"גלידת חלבון מנגו",      p0:13.8, p18:16.28,cost:6.5, gm:52.9, om:27.9, dp:25},
      {name:"גלידת חלבון שוקולד לוז",p0:13.8, p18:16.28,cost:6.5, gm:52.9, om:27.9, dp:25}],
  11:[{name:"גלידת חלבון וניל",      p0:14.1, p18:16.64,cost:6.5, gm:53.9, om:28.9, dp:25},
      {name:"גלידת חלבון מנגו",      p0:14.1, p18:16.64,cost:6.5, gm:53.9, om:28.9, dp:25},
      {name:"גלידת חלבון שוקולד לוז",p0:14.1, p18:16.64,cost:6.5, gm:53.9, om:28.9, dp:25},
      {name:"גלידת חלבון פיסטוק",    p0:14.1, p18:16.64,cost:6.5, gm:53.9, om:28.9, dp:25}],
  13:[{name:"גלידת חלבון וניל",      p0:11.0, p18:12.98,cost:6.5, gm:40.91,om:15.91,dp:25},
      {name:"גלידת חלבון מנגו",      p0:11.0, p18:12.98,cost:6.5, gm:40.91,om:15.91,dp:25},
      {name:"גלידת חלבון שוקולד לוז",p0:11.0, p18:12.98,cost:6.5, gm:40.91,om:15.91,dp:25}],
  14:[{name:"גלידת חלבון וניל",      p0:11.0, p18:12.98,cost:6.5, gm:40.91,om:15.91,dp:25},
      {name:"גלידת חלבון מנגו",      p0:11.0, p18:12.98,cost:6.5, gm:40.91,om:15.91,dp:25},
      {name:"גלידת חלבון שוקולד לוז",p0:11.0, p18:12.98,cost:6.5, gm:40.91,om:15.91,dp:25}],
  15:[{name:"גלידת חלבון וניל",      p0:14.0, p18:16.52,cost:6.5, gm:53.57,om:28.57,dp:25},
      {name:"גלידת חלבון מנגו",      p0:14.0, p18:16.52,cost:6.5, gm:53.57,om:28.57,dp:25},
      {name:"גלידת חלבון שוקולד לוז",p0:14.0, p18:16.52,cost:6.5, gm:53.57,om:28.57,dp:25}],
  16:[{name:"גלידת חלבון וניל",      p0:11.4, p18:13.45,cost:6.5, gm:42.98,om:27.98,dp:15},
      {name:"גלידת חלבון מנגו",      p0:11.4, p18:13.45,cost:6.5, gm:42.98,om:27.98,dp:15},
      {name:"גלידת חלבון שוקולד לוז",p0:11.4, p18:13.45,cost:6.5, gm:42.98,om:27.98,dp:15},
      {name:"גלידת חלבון פיסטוק",    p0:12.3, p18:14.51,cost:6.5, gm:47.15,om:32.15,dp:15}],
  17:[{name:"גלידת חלבון וניל",      p0:13.2, p18:15.58,cost:6.5, gm:50.76,om:35.76,dp:15},
      {name:"גלידת חלבון מנגו",      p0:13.2, p18:15.58,cost:6.5, gm:50.76,om:35.76,dp:15},
      {name:"גלידת חלבון שוקולד לוז",p0:13.2, p18:15.58,cost:6.5, gm:50.76,om:35.76,dp:15},
      {name:"גלידת חלבון פיסטוק",    p0:13.9, p18:16.4, cost:6.5, gm:53.24,om:38.24,dp:15},
      {name:"דרים קייק",             p0:83.0, p18:97.94,cost:53.5, gm:35.54,om:20.54,dp:15}],
  18:[{name:"גלידת חלבון וניל",      p0:14.1, p18:16.64,cost:6.5, gm:53.9, om:38.9, dp:15},
      {name:"גלידת חלבון מנגו",      p0:14.1, p18:16.64,cost:6.5, gm:53.9, om:38.9, dp:15},
      {name:"גלידת חלבון שוקולד לוז",p0:14.1, p18:16.64,cost:6.5, gm:53.9, om:38.9, dp:15},
      {name:"גלידת חלבון פיסטוק",    p0:14.1, p18:16.64,cost:6.5, gm:53.9, om:38.9, dp:15}],
  19:[{name:"גלידת חלבון וניל",      p0:15.5, p18:18.29,cost:6.5, gm:58.06,om:43.06,dp:15},
      {name:"גלידת חלבון מנגו",      p0:15.5, p18:18.29,cost:6.5, gm:58.06,om:43.06,dp:15},
      {name:"גלידת חלבון שוקולד לוז",p0:15.5, p18:18.29,cost:6.5, gm:58.06,om:43.06,dp:15},
      {name:"גלידת חלבון פיסטוק",    p0:15.5, p18:18.29,cost:6.5, gm:58.06,om:43.06,dp:15}],
};

const PROD_COLORS = {
  chocolate:'rgba(139,69,19,0.85)', vanilla:'rgba(245,158,11,0.85)',
  mango:'rgba(249,115,22,0.85)', pistachio:'rgba(147,197,114,0.85)',
  dream_cake:'rgba(219,112,147,0.85)', magadat:'rgba(168,85,247,0.85)',
};
const PROD_LABELS = {
  chocolate:'Chocolate', vanilla:'Vanilla', mango:'Mango',
  pistachio:'Pistachio', dream_cake:'Dream Cake', magadat:'Triple Pack',
};
const PROD_KEY = {
  'גלידת חלבון וניל':'vanilla','גלידת חלבון מנגו':'mango',
  'גלידת חלבון שוקולד לוז':'chocolate','גלידת חלבון פיסטוק':'pistachio',
  'דרים קייק':'dream_cake','מארז שלישיית גלידות':'magadat',
};
const PROD_NAMES = {
  vanilla:'גלידת חלבון וניל',mango:'גלידת חלבון מנגו',
  chocolate:'גלידת חלבון שוקולד לוז',pistachio:'גלידת חלבון פיסטוק',
  dream_cake:'דרים קייק',magadat:'מארז שלישיית גלידות',
};

// ── RETURNS DATA ─────────────────────────────────────────────────────────────
// Method: NET per (customer × item × month) — only excess-negative counts as a real return.
// Fulfillment credits (positive delivery + matching negative credit = net 0) are excluded.
// Mayyan source: Mayyan_Turbo.xlsx + maay_feb_full.xlsx
const mayanReturns = {
  dec:  { units:   0, revenue:     0, rate: 0.0 },
  jan:  { units:  28, revenue:   365, rate: 0.1 },
  feb:  { units: 124, revenue:  1614, rate: 0.3 },
  mar:  { units:   0, revenue:     0, rate: 0.0 },
  total:{ units: 152, revenue:  1979, rate: 0.1 }
};
// Icedreams: positive כמות + negative מכירות/קניות נטו in monthly sales files
const icedreamsReturns = {
  dec:  { units:   0, revenue:     0, rate: 0.0 },
  jan:  { units:   0, revenue:     0, rate: 0.0 },
  feb:  { units: 124, revenue:  1682, rate: 0.9 },
  mar:  { units:  30, revenue:  1125, rate: 3.2 },
  total:{ units: 154, revenue:  2807, rate: 0.3 }
};
// Combined (all distributors)
const allReturns = {
  dec:  { units:   0, revenue:     0, rate: 0.0 },
  jan:  { units:  28, revenue:   365, rate: 0.1 },
  feb:  { units: 248, revenue:  3296, rate: 0.4 },
  mar:  { units:  30, revenue:  1125, rate: 3.2 },
  total:{ units: 306, revenue:  4786, rate: 0.2 }
};

// ── STATE ────────────────────────────────────────────────────────────────────
const S = {
  cust:'all', dist:'all', status:'all', month:'mar', brand:'all',
  sortCol:'revActive', sortDir:-1, selId:null,
  paretoMode:'revenue', trendMode:'rev'
};
let charts = {};

// ── BOOT ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const sel = document.getElementById('f-cust');
  customers.forEach(c => {
    const o = document.createElement('option');
    o.value = c.id; o.textContent = c.name; sel.appendChild(o);
  });
  renderAll();
});

// ── HELPERS ───────────────────────────────────────────────────────────────────
// Inline data-labels plugin — no external CDN needed
Chart.register({
  id:'datalabels',
  afterDraw(chart){
    try {
      const cfg=chart.options&&chart.options.plugins&&chart.options.plugins.datalabels;
      if(!cfg) return;
      const canvasCtx=chart.ctx;
      const fSize=(cfg.font&&cfg.font.size)||10;
      const fWeight=(cfg.font&&cfg.font.weight)||'normal';
      const offset=cfg.offset||4;
      const align=cfg.align||'top';
      chart.data.datasets.forEach(function(ds,di){
        try {
          var meta=chart.getDatasetMeta(di);
          if(!meta||meta.hidden) return;
          var pts=meta.data;
          if(!pts||!pts.length) return;
          canvasCtx.save();
          canvasCtx.font=fWeight+' '+fSize+'px sans-serif';
          canvasCtx.textAlign='center';
          for(var idx=0;idx<pts.length;idx++){
            var raw=ds.data[idx];
            if(raw===null||raw===undefined) continue;
            var el=pts[idx];
            if(!el||el.x==null||el.y==null) continue;
            // display check
            if(typeof cfg.display==='function'){
              if(!cfg.display({dataset:ds,dataIndex:idx,datasetIndex:di})) continue;
            } else if(cfg.display===false) continue;
            // color
            var fillColor=typeof cfg.color==='function'
              ?cfg.color({dataset:ds,dataIndex:idx,datasetIndex:di})
              :(cfg.color||'#8892a4');
            canvasCtx.fillStyle=fillColor;
            // label
            var label=raw;
            if(typeof cfg.formatter==='function'){
              label=cfg.formatter(raw,{dataset:ds,dataIndex:idx,datasetIndex:di});
            }
            if(label===null||label===undefined||label==='') continue;
            // position
            var lx=el.x, ly;
            if(align==='center'&&el.base!=null){
              ly=el.y+(el.base-el.y)/2;
              canvasCtx.textBaseline='middle';
            } else {
              ly=el.y-offset;
              canvasCtx.textBaseline='bottom';
            }
            canvasCtx.fillText(String(label),lx,ly);
          }
          canvasCtx.restore();
        } catch(e2){}
      });
    } catch(e){}
  }
});
const N = (v,d=0) => v==null?'—':v.toLocaleString('he-IL',{minimumFractionDigits:d,maximumFractionDigits:d});
const P = v => v==null?'—':v.toFixed(1)+'%';
const colorGM = g => g==null?'var(--text2)':g>=50?'var(--green)':g>=40?'var(--amber)':'var(--red)';
const colorOM = g => g==null?'var(--text2)':g>=30?'var(--green)':g>=20?'var(--amber)':'var(--red)';

function getBrandRev(c){
  if(S.brand==='turbo' && c.turboRev) return c.turboRev;
  if(S.brand==='danis' && c.danisRev) return c.danisRev;
  return c.revenue;
}
function getBrandUnits(c){
  if(S.brand==='turbo' && c.turboUnits) return c.turboUnits;
  if(S.brand==='danis' && c.danisUnits) return c.danisUnits;
  return c.units;
}
function getRevField(c){
  const r=getBrandRev(c);
  if(S.month==='dec') return r.dec;
  if(S.month==='jan') return r.jan;
  if(S.month==='feb') return r.feb;
  if(S.month==='mar') return r.mar||0;
  // total: respect year filter
  if(S.year==='2025') return r.dec;
  if(S.year==='2026') return r.jan+r.feb+(r.mar||0);
  return r.dec+r.jan+r.feb+(r.mar||0);
}
function getUnitField(c){
  const u=getBrandUnits(c);
  if(S.month==='dec') return u.dec;
  if(S.month==='jan') return u.jan;
  if(S.month==='feb') return u.feb;
  if(S.month==='mar') return u.mar||0;
  // total: respect year filter
  if(S.year==='2025') return u.dec;
  if(S.year==='2026') return u.jan+u.feb+(u.mar||0);
  return u.dec+u.jan+u.feb+(u.mar||0);
}

// ── FILTERS ───────────────────────────────────────────────────────────────────
function filtered(){
  return customers.filter(c=>{
    if(S.cust!=='all' && c.id!=S.cust) return false;
    if(S.dist==='אייסדרים' && c.distributor!=='אייסדרים') return false;
    if(S.dist==='מעיין' && c.distributor!=='מעיין נציגויות') return false;
    if(S.dist==='none' && c.hasPricing) return false;
    if(S.status!=='all' && c.status!==S.status) return false;
    if(S.brand!=='all' && !c.brands.includes(S.brand)) return false;
    return true;
  });
}

function portfolioMonthly(list){
  const src=list||filtered();
  const allM=['dec','jan','feb','mar'];
  const allL=["Dec '25","Jan '26","Feb '26","Mar '26"];
  // When showing 'total' mode, only include months for the selected year
  const active = S.month!=='total' ? allM
    : S.year==='2025' ? ['dec']
    : S.year==='2026' ? ['jan','feb','mar']
    : allM;
  return active.map(m=>{
    const i=allM.indexOf(m);
    let rev=0,units=0;
    src.forEach(c=>{
      const r=getBrandRev(c); const u=getBrandUnits(c);
      rev+=r[m]||0; units+=u[m]||0;
    });
    return {month:allL[i],revenue:rev,units};
  });
}

function applyFilters(){
  S.cust  = document.getElementById('f-cust').value;
  S.dist  = document.getElementById('f-dist').value;
  S.status= document.getElementById('f-status').value;
  S.month = document.getElementById('f-month').value;
  updateChips(); renderAll();
}
function resetFilters(){
  ['f-cust','f-dist','f-status'].forEach(id=>document.getElementById(id).value='all');
  document.getElementById('f-month').value='mar';
  setBrand('all');
  S.cust='all';S.dist='all';S.status='all';S.month='mar';S.brand='all';
  updateChips(); renderAll();
}
function setBrand(b){
  S.brand=b;
  ['all','turbo','danis'].forEach(x=>{
    const el=document.getElementById('bb-'+x);
    el.className='tab'+(x===b?(b==='all'?' on':b==='turbo'?' on-turbo':' on-danis'):'');
  });
  renderAll();
}
function updateChips(){
  const chips=[];
  if(S.cust!=='all'){const c=customers.find(x=>x.id==S.cust);if(c)chips.push(['Customer',c.name,'cust']);}
  if(S.dist!=='all') chips.push(['Dist',S.dist,'dist']);
  if(S.status!=='all') chips.push(['Status',S.status,'status']);
  document.getElementById('chips').innerHTML=chips.map(([l,v,k])=>
    `<div class="chip">${l}: ${v} <button onclick="clearChip('${k}')">×</button></div>`
  ).join('');
}
function clearChip(k){
  document.getElementById('f-'+k).value='all';
  S[k]='all'; updateChips(); renderAll();
}
function sortBy(col){
  if(S.sortCol===col) S.sortDir*=-1; else{S.sortCol=col;S.sortDir=-1;}
  renderTable();
}
function setParetoMode(m){
  S.paretoMode=m;
  document.getElementById('pb-rev').className='tab'+(m==='revenue'?' on':'');
  document.getElementById('pb-u').className='tab'+(m==='units'?' on':'');
  renderPareto();
}
function setTrendMode(m){
  S.trendMode=m;
  document.getElementById('tb-r').className='tab'+(m==='rev'?' on':'');
  document.getElementById('tb-u').className='tab'+(m==='units'?' on':'');
  renderTrend();
}

// ── RENDER ALL ────────────────────────────────────────────────────────────────
function renderAll(){
  renderKPIs(); renderPareto(); renderMix(); renderTrend(); renderTable(); renderWeeklyChart();
}

// ── KPIs ──────────────────────────────────────────────────────────────────────
function renderKPIs(){
  const list=filtered();
  const totals=portfolioMonthly(list);
  const mIdx={dec:0,jan:1,feb:2,mar:3}[S.month];
  const yLbl=S.year==='2025'?" '25":S.year==='2026'?" '26":'';
  const mLbl={dec:"Dec '25",jan:"Jan '26",feb:"Feb '26",mar:`Mar '26 (W${DATA_LAST_WEEK})`,total:`All Months${yLbl}`}[S.month];
  // For 'total' mode use getRevField (year-aware) rather than summing portfolioMonthly
  const curRev  =mIdx!=null?totals[mIdx].revenue :list.reduce((s,c)=>s+getRevField(c),0);
  const curUnits=mIdx!=null?totals[mIdx].units   :list.reduce((s,c)=>s+getUnitField(c),0);
  const grossVal=list.reduce((s,c)=>s+(getRevField(c)*(c.grossMargin||0)/100),0);
  const opVal   =list.reduce((s,c)=>s+(getRevField(c)*(c.opMargin||0)/100),0);
  const withSales=list.filter(c=>getRevField(c)>0).length;
  // MoM (jan vs dec for jan, feb vs jan for feb, mar vs feb for mar)
  let momRev=null;
  if(S.month==='jan'&&totals[0].revenue>0) momRev=((totals[1].revenue-totals[0].revenue)/totals[0].revenue*100);
  if(S.month==='feb'&&totals[1].revenue>0) momRev=((totals[2].revenue-totals[1].revenue)/totals[1].revenue*100);
  if(S.month==='mar'&&totals[2].revenue>0) momRev=((totals[3].revenue-totals[2].revenue)/totals[2].revenue*100);
  const momHtml=momRev!=null?`<span class="${momRev>=0?'up':'down'}">${momRev>=0?'▲':'▼'}${Math.abs(momRev).toFixed(1)}% vs prev month</span>`:'—';

  const avgGM=list.filter(c=>c.grossMargin!=null&&getRevField(c)>0).reduce((a,c,_,ar)=>{
    const w=getRevField(c); return {sum:a.sum+c.grossMargin*w,w:a.w+w};
  },{sum:0,w:0});
  const avgGMval=avgGM.w>0?(avgGM.sum/avgGM.w).toFixed(1):'—';

  document.getElementById('kpi-grid').innerHTML=`
  <div class="kpi-card"><div class="kpi-label">Revenue (${mLbl})</div><div class="kpi-value">₪${N(curRev)}</div><div class="kpi-meta">${momHtml}</div></div>
  <div class="kpi-card"><div class="kpi-label">Units (${mLbl})</div><div class="kpi-value">${N(curUnits)}</div><div class="kpi-meta">${withSales} customers w/ sales</div></div>
  <div class="kpi-card"><div class="kpi-label">Gross Profit ₪</div><div class="kpi-value" style="color:var(--green)">₪${N(grossVal)}</div><div class="kpi-meta">Avg Gross: ${avgGMval}%</div></div>
  <div class="kpi-card"><div class="kpi-label">Op Profit ₪</div><div class="kpi-value" style="color:var(--accent)">₪${N(opVal)}</div><div class="kpi-meta">After dist. costs</div></div>
  ${(()=>{const mKey=S.month==='total'?'total':S.month;const db=S.dist==='מעיין'?mayanReturns:S.dist==='אייסדרים'?icedreamsReturns:allReturns;const lbl=S.dist==='מעיין'?'Returns — Ma\'ayan':S.dist==='אייסדרים'?'Returns — Icedream':'Returns — All';const ret=db[mKey]||db.jan;const rateCol=ret.rate>=12?'var(--red)':ret.rate>=6?'rgba(245,158,11,0.9)':'var(--green)';return `<div class="kpi-card"><div class="kpi-label">${lbl}</div><div class="kpi-value" style="color:${rateCol}">${N(ret.units)}</div><div class="kpi-meta">₪${N(ret.revenue)} revenue loss &nbsp;·&nbsp; <span style="color:${rateCol};font-weight:600">${ret.rate}%</span> return rate</div></div>`;})()}
  <div class="kpi-card"><div class="kpi-label">Portfolio ${S.month==='mar'?'Feb→Mar':S.month==='feb'?'Jan→Feb':S.month==='jan'?'Dec→Jan':'MoM Change'}</div><div class="kpi-value">${momRev!=null?`<span class="${momRev>=0?'up':'down'}">${momRev>=0?'+':''}${momRev.toFixed(1)}%</span>`:'—'}</div><div class="kpi-meta">Revenue MoM change${list.length<19?' · filtered':''}${S.dist!=='all'?` · ${S.dist==='מעיין'?"Ma'ayan":S.dist==='אייסדרים'?'Icedream':'Biscotti'}`:''}</div></div>`;
}

// ── PARETO ────────────────────────────────────────────────────────────────────
function renderPareto(){
  const list=filtered().filter(c=>getRevField(c)>0||getUnitField(c)>0);
  const key=S.paretoMode==='revenue'?'rev':'u';
  const vals=list.map(c=>({name:c.name,v:S.paretoMode==='revenue'?getRevField(c):getUnitField(c),gm:c.grossMargin,id:c.id}));
  vals.sort((a,b)=>b.v-a.v);
  const bgColors=vals.map(x=>x.gm==null?'rgba(136,146,164,0.6)':x.gm>=50?'rgba(34,197,94,0.7)':x.gm>=40?'rgba(245,158,11,0.7)':'rgba(239,68,68,0.7)');
  const _isRev=S.paretoMode==='revenue';
  const _fmtK=v=>v>=1000000?(v/1000000).toFixed(1)+'M':v>=1000?Math.round(v/1000)+'K':String(Math.round(v));
  const _fmtBar=v=>(_isRev?'\u20aa':'')+_fmtK(v);
  const ctx=document.getElementById('c-pareto').getContext('2d');
  if(charts.pareto) charts.pareto.destroy();
  charts.pareto=new Chart(ctx,{type:'bar',data:{labels:vals.map(v=>v.name),datasets:[{data:vals.map(v=>v.v),backgroundColor:bgColors,borderWidth:0}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:function(c){return _fmtBar(c.raw);}}},
    datalabels:{anchor:'end',align:'end',color:'#8892a4',font:{size:9},formatter:function(v){return _fmtBar(v);}}},
    scales:{x:{ticks:{color:'#8892a4',font:{size:10}},grid:{display:false}},y:{min:0,ticks:{color:'#8892a4',font:{size:10},callback:function(v){return _fmtBar(v);}},grid:{color:'rgba(46,51,72,0.4)'},suggestedMax:vals.length?vals[0].v*1.15:100}},
    onClick:function(_,els){if(els.length>0){const c=vals[els[0].index];S.selId=c.id;renderTable();openDrawer(customers.find(x=>x.id===c.id));}}}});
}

// ── SCATTER ───────────────────────────────────────────────────────────────────

// ── MIX ───────────────────────────────────────────────────────────────────────
function renderMix(){
  const list=filtered().filter(c=>productMix[c.id]);
  const agg={};
  list.forEach(c=>{Object.entries(productMix[c.id]).forEach(([k,v])=>{agg[k]=(agg[k]||0)+v;});});
  const labels=Object.keys(agg).map(k=>PROD_LABELS[k]||k);
  const vals=Object.values(agg);
  const colors=Object.keys(agg).map(k=>PROD_COLORS[k]||'rgba(136,146,164,0.7)');
  const ctx=document.getElementById('c-mix').getContext('2d');
  if(charts.mix) charts.mix.destroy();
  charts.mix=new Chart(ctx,{type:'bar',data:{labels:list.map(c=>c.name),
    datasets:Object.keys(agg).map(k=>({label:PROD_LABELS[k]||k,data:list.map(c=>(productMix[c.id]||{})[k]||0),backgroundColor:PROD_COLORS[k]||'rgba(136,146,164,0.7)',stack:'s'}))},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'bottom',labels:{color:'#8892a4',font:{size:10},boxWidth:10}},
    datalabels:{anchor:'center',align:'center',color:'#fff',font:{size:8},display:function(c){return c.dataset.data[c.dataIndex]>0;},formatter:function(v){return v>0?N(v):'';}}},
    scales:{x:{stacked:true,ticks:{color:'#8892a4',font:{size:10}},grid:{display:false}},y:{stacked:true,ticks:{color:'#8892a4',font:{size:10}},grid:{color:'rgba(46,51,72,0.4)'},grace:'10%'}}}});
}

// ── TREND ─────────────────────────────────────────────────────────────────────
function renderTrend(){
  const pm=portfolioMonthly();
  const isRev=S.trendMode==='rev';
  const vals=pm.map(p=>isRev?p.revenue:p.units);
  const lastIdx=vals.length-1;
  const _tFmt=v=>isRev?'\u20aa'+Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g,','):Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g,',')+' u';
  const ptColors=vals.map((_,i)=>i===lastIdx?'#94a3b8':'#4f8ef7');
  // Dynamic subtitle
  (function(){
    const el=document.getElementById('trend-subtitle');
    if(!el) return;
    const mths=pm.map(p=>p.month);
    const partial=mths[mths.length-1];
    const lastComplete=mths.length>1?mths[mths.length-2]:null;
    const wLabel='W'+DATA_LAST_WEEK;
    el.textContent='Monthly VAT0 + units'+(lastComplete?' \u00b7 '+lastComplete+' = Complete':'')+' \u00b7 '+partial+' = Partial ('+wLabel+')';
  })();
  const ctx=document.getElementById('c-trend').getContext('2d');
  if(charts.trend) charts.trend.destroy();
  charts.trend=new Chart(ctx,{type:'line',data:{labels:pm.map(p=>p.month),datasets:[{data:vals,
    borderColor:'#4f8ef7',backgroundColor:'rgba(79,142,247,0.1)',fill:true,tension:0.3,
    pointRadius:5,pointBackgroundColor:ptColors,
    segment:{borderColor:ctx2=>ctx2.p1DataIndex===lastIdx?'#94a3b8':'#4f8ef7',borderDash:ctx2=>ctx2.p1DataIndex===lastIdx?[6,4]:[]}}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:function(c){return N(c.raw);}}},
    datalabels:{anchor:'end',align:'top',offset:6,color:'#b0bac9',font:{size:11,weight:'600'},formatter:function(v,c){return (c.dataIndex===lastIdx?'partial \u00b7 ':'')+_tFmt(v);}}},
    scales:{x:{ticks:{color:'#8892a4',font:{size:10}},grid:{display:false}},y:{ticks:{color:'#8892a4',font:{size:10},callback:function(v){return N(v);}},grid:{color:'rgba(46,51,72,0.4)'}}}}});
}

// ── TABLE ─────────────────────────────────────────────────────────────────────
function renderTable(){
  const q=(document.getElementById('t-search').value||'').toLowerCase();
  const base=filtered().filter(c=>!q||c.name.toLowerCase().includes(q)||c.distributor.toLowerCase().includes(q));
  const totalRev=base.reduce((s,c)=>s+getRevField(c),0);
  const withMeta=base.map(c=>({...c,
    _rev:getRevField(c),_units:getUnitField(c),
    _grossVal:c.grossMargin!=null?getRevField(c)*(c.grossMargin/100):-Infinity,
    _opVal:c.opMargin!=null?getRevField(c)*(c.opMargin/100):-Infinity,
  }));
  // Sort: active rows first, then by sort column
  const activeRows=withMeta.filter(c=>c._rev>0);
  const zeroRows =withMeta.filter(c=>c._rev===0);
  const getSortVal=(c,col)=>{
    if(col==='revActive') return c._rev;
    if(col==='unitsActive') return c._units;
    if(col==='share') return totalRev>0?c._rev/totalRev:0;
    if(col==='grossVal') return c._grossVal;
    if(col==='opVal') return c._opVal;
    if(col==='name') return c.name;
    if(col==='distributor') return c.distributor;
    if(col==='status') return c.status;
    return c[col]??-Infinity;
  };
  const sortFn=(a,b)=>{
    const av=getSortVal(a,S.sortCol), bv=getSortVal(b,S.sortCol);
    if(typeof av==='string') return S.sortDir*(av<bv?-1:av>bv?1:0);
    return S.sortDir*(av-bv);
  };
  activeRows.sort(sortFn);

  const tYLbl=S.year==='2025'?"'25":S.year==='2026'?"'26":'';
  const mLbl={dec:"Dec",jan:"Jan",feb:"Feb",mar:`Mar (W${DATA_LAST_WEEK})`,total:tYLbl?`Total ${tYLbl}`:"Total"}[S.month];
  const rows=[...activeRows,...zeroRows].map(c=>{
    const rev=c._rev, units=c._units;
    const share=totalRev>0?(rev/totalRev*100):0;
    const grossVal=c.grossMargin!=null?rev*(c.grossMargin/100):null;
    const opVal=c.opMargin!=null?rev*(c.opMargin/100):null;
    const gmCol=colorGM(c.grossMargin), omCol=colorOM(c.opMargin);
    const isZero=rev===0;
    const zeroReason=isZero?(c.status==='negotiation'?'negotiation — no sales yet':`no sales in ${mLbl}`):'';
    const statusHtml=c.status==='active'?'<span class="dtag active">Active</span>':'<span class="dtag negotiation">Negotiation</span>';
    const brandHtml=c.brands.map(b=>b==='turbo'?'<span class="brand-tag brand-turbo">Turbo</span>':'<span class="brand-tag brand-danis">Dani\'s</span>').join('');
    return `<tr class="${c.id===S.selId?'sel':''}" onclick="selectRow(${c.id})" style="${isZero?'opacity:0.5':''}">
      <td><strong>${c.name}</strong>${brandHtml}${isZero?`<br><span style="font-size:10px;color:var(--text2)">${zeroReason}</span>`:''}</td>
      <td><strong>${rev>0?'₪'+N(rev):'—'}</strong></td>
      <td style="color:var(--text2)">${rev>0?'₪'+N(rev*1.18):'—'}</td>
      <td><div class="pct-bar"><div class="bar-bg"><div class="bar-fg" style="width:${Math.min(100,share).toFixed(0)}%;background:var(--accent)"></div></div>${share>0?share.toFixed(1)+'%':'—'}</div></td>
      <td style="color:${gmCol};font-weight:600">${P(c.grossMargin)}</td>
      <td style="color:${gmCol};font-weight:600">${grossVal!=null?'₪'+N(grossVal):'—'}</td>
      <td style="color:${omCol};font-weight:600">${P(c.opMargin)}</td>
      <td style="color:${omCol};font-weight:600">${opVal!=null?'₪'+N(opVal):'—'}</td>
      <td>${units>0?N(units):'—'}</td>
      <td>${c.momGrowth!=null?`<span class="${c.momGrowth>=0?'up':'down'}">${c.momGrowth>=0?'▲':'▼'}${Math.abs(c.momGrowth).toFixed(1)}%</span>`:'—'}</td>
      <td style="color:var(--text2);font-size:11px">${c.distributor}</td>
      <td>${statusHtml}</td>
    </tr>`;
  });
  document.getElementById('t-body').innerHTML=rows.join('');
}

function selectRow(id){
  const c=customers.find(x=>x.id===id);
  if(!c) return;
  if(S.selId===id){S.selId=null;closeDrawer();}
  else{S.selId=id;openDrawer(c);}
  renderTable();
}

// ── DRAWER ────────────────────────────────────────────────────────────────────
function openDrawer(c){
  document.getElementById('drawer').classList.add('open');
  document.getElementById('d-name').textContent=c.name;
  const statusHtml=c.status==='active'?'<span class="dtag active">Active</span>':'<span class="dtag negotiation">Negotiation</span>';
  const brandHtml=c.brands.map(b=>b==='turbo'?'<span class="brand-tag brand-turbo">Turbo</span>':'<span class="brand-tag brand-danis">Dani\'s</span>').join('');
  document.getElementById('d-tag-row').innerHTML=statusHtml+brandHtml+`<span style="font-size:11px;color:var(--text2);margin-left:8px">${c.distributor} · ${c.dist_pct}% dist</span>`;

  const revTotal=c.revenue.dec+c.revenue.jan+c.revenue.feb+(c.revenue.mar||0);
  const unitsTotal=c.units.dec+c.units.jan+c.units.feb+(c.units.mar||0);
  const gmCol=colorGM(c.grossMargin), omCol=colorOM(c.opMargin);
  document.getElementById('d-kpis').innerHTML=`
    <div class="dkpi"><div class="dkpi-l">Total Revenue (4M)</div><div class="dkpi-v">₪${N(revTotal)}</div></div>
    <div class="dkpi"><div class="dkpi-l">Avg Price (VAT0)</div><div class="dkpi-v">${c.avgPrice!=null?'₪'+c.avgPrice.toFixed(2):'—'}</div></div>
    <div class="dkpi"><div class="dkpi-l">Gross Margin</div><div class="dkpi-v" style="color:${gmCol}">${P(c.grossMargin)}</div></div>
    <div class="dkpi"><div class="dkpi-l">Op Margin</div><div class="dkpi-v" style="color:${omCol}">${P(c.opMargin)}</div></div>
    <div class="dkpi"><div class="dkpi-l">Total Units (4M)</div><div class="dkpi-v">${N(unitsTotal)}</div></div>
    <div class="dkpi"><div class="dkpi-l">Active SKUs</div><div class="dkpi-v">${c.activeSKUs}</div></div>`;

  // Monthly chart
  const ctx=document.getElementById('d-chart').getContext('2d');
  if(charts.drawer) charts.drawer.destroy();
  const months=["Dec '25","Jan '26","Feb '26","Mar '26"];
  const revData=[c.revenue.dec,c.revenue.jan,c.revenue.feb,c.revenue.mar||0];
  charts.drawer=new Chart(ctx,{type:'bar',data:{labels:months,datasets:[{data:revData,backgroundColor:['rgba(79,142,247,0.6)','rgba(79,142,247,0.9)','rgba(79,142,247,0.5)','rgba(79,142,247,0.8)'],borderWidth:0}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:function(c){return N(c.raw);}}},
    datalabels:{anchor:'end',align:'end',color:'#b0bac9',font:{size:11,weight:'600'},formatter:function(v){return v>0?N(v):'';}}},
    scales:{x:{ticks:{color:'#8892a4',font:{size:10}},grid:{display:false}},y:{min:0,ticks:{color:'#8892a4',font:{size:10},callback:function(v){return N(v);}},grid:{color:'rgba(46,51,72,0.35)'}}}}});

  // SKU table: merge priced SKUs + unpriced from productMix
  const skus=skuDetail[c.id]||[];
  const mix=productMix[c.id]||null;
  const totU=mix?Object.values(mix).reduce((s,v)=>s+v,0):0;
  const pricedNames=new Set(skus.map(s=>PROD_KEY[s.name]||s.name));

  const pricedRows=skus.map(s=>{
    const k=PROD_KEY[s.name]||s.name;
    const u=mix&&mix[k]!=null?mix[k]:null;
    const uCell=u!=null&&totU>0?`<span style="color:var(--text2);font-size:10px">${N(u)}u · ${(u/totU*100).toFixed(0)}%</span>`:'<span>—</span>';
    const gmCol2=colorGM(s.gm), omCol2=colorOM(s.om);
    return `<tr>
      <td>${s.name}<br>${uCell}</td>
      <td>₪${s.p0}</td><td>₪${s.p18}</td>
      <td>${s.cost!=null?'₪'+s.cost:'—'}</td>
      <td style="color:${gmCol2}">${s.gm!=null?s.gm.toFixed(1)+'%':'—'}</td>
      <td style="color:${omCol2}">${s.om!=null?s.om.toFixed(1)+'%':'—'}</td>
      <td>${s.dp}%</td>
    </tr>`;
  });

  let unpricedRows=[];
  if(mix){
    unpricedRows=Object.entries(mix).filter(([k])=>!pricedNames.has(k)&&mix[k]>0).map(([k,v])=>`
      <tr style="opacity:0.7">
        <td>${PROD_NAMES[k]||k} <span style="color:var(--amber);font-size:10px">★ no price</span><br>
        <span style="color:var(--text2);font-size:10px">${N(v)}u · ${totU>0?(v/totU*100).toFixed(0):'?'}%</span></td>
        <td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>${c.dist_pct}%</td>
      </tr>`);
  }

  if(pricedRows.length===0&&unpricedRows.length===0){
    document.getElementById('d-sku-sec').textContent='SKU Data';
    document.getElementById('d-skus').innerHTML='<tr><td colspan="7" style="color:var(--text2);font-size:11px;padding:12px">No Product Data</td></tr>';
  } else {
    document.getElementById('d-sku-sec').textContent=`SKU Price List (${c.dist_pct}% Dist)`;
    document.getElementById('d-skus').innerHTML=[...pricedRows,...unpricedRows].join('');
  }
}

function closeDrawer(){
  document.getElementById('drawer').classList.remove('open');
  S.selId=null;
  renderTable();
}

// ══════════════════════════════════════════════════════════════════════════════
// WEEKLY SALES TREND CHART
// ══════════════════════════════════════════════════════════════════════════════
// X-axis: 11 positions
//   0 = "דצ'25"  (Dec 2025 — monthly total, displayed as dot)
//   1 = "ינ'26"  (Jan 2026 — monthly total, displayed as dot)
//   2–10 = "ש'1"–"ש'9"  (weekly, 2026)
// Source: icedream_weekly_sales.xls  +  CP tab monthly totals  +  maay_feb_full.xlsx
const weeklyXLabels = ["28/12","4/1","11/1","18/1","25/1","1/2","8/2","15/2","22/2","1/3","8/3","15/3"];

// ── Inactive customers: dynamic period config ─────────────────────────────
// DATA_LAST_WEEK auto-derived from weeklyXLabels length — update by adding labels above
const DATA_LAST_WEEK       = weeklyXLabels.length;                   // e.g. 11
const DATA_LAST_WEEK_LABEL = weeklyXLabels[DATA_LAST_WEEK - 1];     // e.g. "8/3"


const WEEKLY_WINDOW = 10;  // Rolling window — always show last N weeks

// Icedreams monthly totals (Dec & Jan) — from Customer Performance tab, distributor=Icedreams
// Customers: גוד פארם, וולט מרקט, ינגו דלי, כרמלה, נוי השדה, דומינוס, חוות נעמי, עוגיפלצת
const _iceMonRev   = { dec: 686481,  jan: 641087  };
const _iceMonUnits = { dec: 20289,   jan: 17919   };

// Mayyan monthly totals (Dec & Jan) — from CP tab, distributor=מעיין
// Customers: AMPM, אלונית, דלק, טיב טעם, שוק פרטי, פז יילו, פז סופר יודה, סונול
const _maayMonRev   = { dec: 852496,  jan: 415214  };
const _maayMonUnits = { dec: 61775,   jan: 30088   };

// Icedreams weekly (weeks 1–10) — from icedream_weekly_sales.xls, per-product rows
// Raito products only (באגסו / דובאי excluded). Units = cartons × UPC.
// GROSS deliveries only (returns excluded). Fixed RK decoder (float byte-order + MULRK offset).
// Danis revenue validated exactly. Yingo W2 validated by user.
// W10 (1/3/2026): ינגו 445u/₪13788, דומינוס 164u/₪1869, חוות נעמי 116u/₪6173, וולט -30u return (excluded from gross)
// Combined (Turbo + Danis)  — W11 source: icedream_15_3 | W12 source: icedream_mar_w12.xlsx (19/3/2026) | W13 pending
const _iceWkRev        = [9256, 10076, 1460, 8070, 599111, 17666, 2673, 2916, 437981, 21831, 26678, 111979, null];
const _iceWkUnits      = [144, 324, 108, 66, 17068, 483, 198, 216, 12290, 725, 553, 3067, null];
// Turbo (ice cream) only
const _iceWkRevTurbo   = [497, 3776, 1460, 0, 143429, 5416, 2673, 2916, 112840, 7803, 3354, 29872, null];
const _iceWkUnitsTurbo = [36, 282, 108, 0, 11537, 400, 198, 216, 8290, 602, 272, 2182, null];
// Danis (dream cake) only — validated exact match all weeks
const _iceWkRevDanis   = [8759, 6300, 0, 8070, 455682, 12249, 0, 0, 325141, 14028, 23324, 82106, null];
const _iceWkUnitsDanis = [108, 42, 0, 66, 5531, 83, 0, 0, 4000, 123, 281, 885, null];
// Returns tracked separately
const _iceWkRetRev   = [0, 8278, 1309, 2392, 0, 233, 1890, 1925, 0, 1125, null, 0, null];
const _iceWkRetUnits = [0, 117, 51, 204, 0, 7, 114, 33, 0, 30, null, 0, null];

// Mayyan weekly — source: דוח_הפצה_גלידות_טורבו__אל_פירוט (detail sheet), net כמות בודדים × ₪13.8
// W6–W9: maay_feb_full.xlsx | W10–W11: maayan_sales_week_10_11.xlsx
const _maayWkRev   = { 6: 135406, 7: 106260, 8: 240106, 9: 122351, 10: 99415, 11: 109572 };
const _maayWkUnits = { 6: 9812,   7: 7700,   8: 17399,  9: 8866,   10: 7204,  11: 7940   };

// Biscotti weekly — source: daniel_amit_weekly_biscotti.xlsx (24/3/2026)
// Dream Cake (dream_cake_2) only. Sale price ₪80/unit, 0% commission.
// W12 (18/3–21/3) = Biscotti "שבוע 1": 101 units × ₪80 = ₪8,080
// W13 (22/3–27/3) = Biscotti "שבוע 2": 20 units × ₪80 = ₪1,600 (partial: only 22/3 data)
const _biscWkRev   = { 12: 8080, 13: 1600 };
const _biscWkUnits = { 12: 101,  13: 20   };

// ── WEEKLY CHART ─────────────────────────────────────────────────────────────
let _weeklyMode = 'rev';

// Returns which distributor view to show based on current filter state:
//   'ice'  = Icedreams only  (blue)
//   'maay' = מעיין only      (green, turbo data only — no danis at Mayyan)
//   'bisc' = ביסקוטי only    (amber, danis only — dream_cake_2)
//   'both' = combined        (purple — ice + maay + bisc where applicable)
//   'none' = no weekly data available (e.g. Mayyan + Danis filter)
function _weeklyDistKey() {
  if (S.cust !== 'all') {
    const c = customers.find(x => x.id == S.cust);
    if (!c) return 'none';
    if (c.distributor === 'אייסדרים') return 'ice';
    // Mayyan customer + danis brand → no data
    if (c.distributor === 'מעיין נציגויות') return S.brand === 'danis' ? 'none' : 'maay';
    if (c.distributor === 'ביסקוטי') return 'bisc';
    return 'none';
  }
  if (S.dist === 'אייסדרים') return 'ice';
  // Mayyan + danis → no data
  if (S.dist === 'מעיין') return S.brand === 'danis' ? 'none' : 'maay';
  if (S.dist === 'ביסקוטי') return 'bisc';
  if (S.dist === 'none')  return 'none';
  return 'both';  // S.dist === 'all', any brand — combined (bisc null for turbo, maay null for danis)
}

// Get the correct Icedreams data array for current brand filter
function _iceDataArr(r) {
  if (S.brand === 'turbo') return r ? _iceWkRevTurbo   : _iceWkUnitsTurbo;
  if (S.brand === 'danis') return r ? _iceWkRevDanis   : _iceWkUnitsDanis;
  return                          r ? _iceWkRev         : _iceWkUnits;
}

// Mayyan is turbo-only; return nulls if danis filter is active
// Dynamic: always same length as _iceWkRev, with known weeks filled in
function _maayDataArr(r) {
  const len = _iceWkRev.length;
  if (S.brand === 'danis') return Array(len).fill(null);
  const src = r ? _maayWkRev : _maayWkUnits;
  const arr = Array(len).fill(null);
  // W6–W9 = index 5–8 (W1=index0 → Wk=index(Wk-1))
  Object.entries(src).forEach(([wk, val]) => { arr[parseInt(wk) - 1] = val; });
  return arr;
}

// Biscotti is danis-only (dream_cake_2); return nulls if turbo filter is active
// Dynamic: always same length as _iceWkRev, with known weeks filled in
function _biscDataArr(r) {
  const len = _iceWkRev.length;
  if (S.brand === 'turbo') return Array(len).fill(null);
  const src = r ? _biscWkRev : _biscWkUnits;
  const arr = Array(len).fill(null);
  Object.entries(src).forEach(([wk, val]) => { arr[parseInt(wk) - 1] = val; });
  return arr;
}

function _mkWeeklyDatasets(mode) {
  const r  = mode === 'rev';
  const dk = _weeklyDistKey();
  const iceData  = _iceDataArr(r);
  const maayData = _maayDataArr(r);
  const biscData = _biscDataArr(r);

  if (dk === 'ice') {
    return [{
      label: 'Icedreams',
      data: [...iceData],
      borderColor: '#4f8ef7',
      backgroundColor: 'rgba(79,142,247,0.1)',
      borderWidth: 2.5, fill: true, tension: 0.3,
      pointRadius: 4, pointHoverRadius: 7, spanGaps: false
    }];
  }

  if (dk === 'maay') {
    return [{
      label: 'Ma\'ayan',
      data: maayData,
      borderColor: '#22c55e',
      backgroundColor: 'rgba(34,197,94,0.08)',
      borderWidth: 2.5, fill: true, tension: 0.3,
      pointRadius: maayData.map(v => v !== null ? 4 : 0),
      pointHoverRadius: 7, spanGaps: false
    }];
  }

  if (dk === 'bisc') {
    return [{
      label: 'Biscotti',
      data: biscData,
      borderColor: '#f59e0b',
      backgroundColor: 'rgba(245,158,11,0.08)',
      borderWidth: 2.5, fill: true, tension: 0.3,
      pointRadius: biscData.map(v => v !== null ? 4 : 0),
      pointHoverRadius: 7, spanGaps: false
    }];
  }

  if (dk === 'both') {
    // Combined: ice + maay (turbo) + bisc (danis) — null-safe per distributor's scope
    const combined = iceData.map((v, i) => (v ?? 0) + (maayData[i] ?? 0) + (biscData[i] ?? 0));
    return [{
      label: 'All Distributors',
      data: combined,
      borderColor: '#a78bfa',
      backgroundColor: 'rgba(167,139,250,0.1)',
      borderWidth: 2.5, fill: true, tension: 0.3,
      pointRadius: 4, pointHoverRadius: 7, spanGaps: false
    }];
  }

  return [];  // 'none'
}

function _updateWeeklyLegend(dk) {
  const el = document.getElementById('wlegend');
  if (!el) return;
  const brandTag = S.brand === 'turbo' ? ' · Turbo only' : S.brand === 'danis' ? ' · Dani\'s only' : '';
  if (dk === 'none') {
    el.innerHTML = `<div class="wleg-item" style="color:var(--amber)">⚠ No weekly data for this filter (Ma'ayan does not carry Dani's)</div>`;
    return;
  }
  if (dk === 'both') {
    el.innerHTML =
      `<div class="wleg-item"><div class="wleg-line" style="background:#a78bfa"></div>All Distributors (28/12–22/3)${brandTag} — W1–W5: Icedreams · W6–W11: Icedreams + Ma'ayan · W12+: Icedreams + Biscotti</div>`;
    return;
  }
  if (dk === 'ice') {
    const suffix = S.brand === 'danis' ? ' · Dani\'s only (Ma\'ayan does not carry Dani\'s)' : brandTag;
    el.innerHTML =
      `<div class="wleg-item"><div class="wleg-line" style="background:#4f8ef7"></div>Icedreams weekly (28/12–22/3)${suffix}</div>`;
    return;
  }
  if (dk === 'maay') {
    el.innerHTML =
      `<div class="wleg-item"><div class="wleg-line" style="background:#22c55e"></div>Ma'ayan weekly (1/2–8/3)${brandTag} · W12+ no data</div>`;
    return;
  }
  if (dk === 'bisc') {
    el.innerHTML =
      `<div class="wleg-item"><div class="wleg-line" style="background:#f59e0b"></div>Biscotti weekly (18/3–22/3) · Dani's Dream Cake only · W12: 101 units · W13: 20 units (partial)</div>`;
    return;
  }
}

function renderWeeklyChart() {
  const mode = _weeklyMode;
  const dk   = _weeklyDistKey();
  const ctx  = document.getElementById('c-weekly').getContext('2d');
  if (charts.weekly) charts.weekly.destroy();

  const isRev = mode === 'rev';
  const fmtAx = v => isRev
    ? (v >= 1000000 ? '₪'+(v/1000000).toFixed(1)+'M' : v >= 1000 ? '₪'+Math.round(v/1000)+'K' : '₪'+v)
    : (v >= 1000 ? Math.round(v/1000)+'K' : String(v));
  const fmtTip = v => isRev
    ? '₪'+Math.round(v).toLocaleString()
    : Math.round(v).toLocaleString()+' units';

  const datasets = _mkWeeklyDatasets(mode);
  _updateWeeklyLegend(dk);

  // Apply rolling window: always show last WEEKLY_WINDOW weeks
  const winLabels = weeklyXLabels.slice(-WEEKLY_WINDOW);
  const winDatasets = datasets.map(ds => ({...ds, data: ds.data.slice(-WEEKLY_WINDOW)}));

  // Dynamic Y-axis max: scan visible data, add 20% headroom, round up to a clean magnitude
  const _flatVals = winDatasets.flatMap(ds => ds.data).filter(v => v != null && isFinite(v) && v > 0);
  const _rawMax   = _flatVals.length ? Math.max(..._flatVals) : (isRev ? 100000 : 10000);
  const _mag      = Math.pow(10, Math.floor(Math.log10(_rawMax)));
  const _yMax     = Math.ceil(_rawMax * 1.20 / _mag) * _mag;

  charts.weekly = new Chart(ctx, {
    type: 'line',
    data: { labels: winLabels, datasets: winDatasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        datalabels: false,
        tooltip: {
          callbacks: {
            label: function(c) { return c.raw !== null ? c.dataset.label + ': ' + fmtTip(c.raw) : null; }
          },
          filter: function(item) { return item.raw !== null; }
        }
      },
      scales: {
        x: {
          ticks: { color: '#8892a4', font: { size: 11 } },
          grid: { color: 'rgba(46,51,72,0.45)' }
        },
        y: {
          beginAtZero: true,
          min: 0,
          max: _yMax,
          ticks: { color: '#8892a4', font: { size: 10 }, callback: fmtAx },
          grid: { color: 'rgba(46,51,72,0.4)' }
        }
      }
    },
    plugins: [{
      id: 'weeklyValueLabels',
      afterDraw: function(chart) {
        var c2 = chart.ctx;
        chart.data.datasets.forEach(function(ds, di) {
          var meta = chart.getDatasetMeta(di);
          if (!meta || meta.hidden) return;
          meta.data.forEach(function(el, idx) {
            var val = ds.data[idx];
            if (val === null || val === undefined) return;
            var lbl = fmtTip(val);
            var tw = c2.measureText(lbl).width + 6;
            var th = 13;
            var lx = el.x;
            var ly = el.y - 10;
            c2.save();
            c2.font = '600 10px sans-serif';
            c2.textAlign = 'center';
            c2.textBaseline = 'bottom';
            /* dark pill background */
            c2.fillStyle = 'rgba(18,22,38,0.78)';
            var rx = lx - tw/2, ry = ly - th;
            c2.beginPath();
            c2.roundRect(rx, ry, tw, th, 3);
            c2.fill();
            /* label in dataset color */
            c2.fillStyle = ds.borderColor || '#e2e8f0';
            c2.fillText(lbl, lx, ly);
            c2.restore();
          });
        });
      }
    }]
  });
}

function setWeeklyMode(mode) {
  _weeklyMode = mode;
  document.getElementById('wb-rev').classList.toggle('on', mode === 'rev');
  document.getElementById('wb-u').classList.toggle('on', mode !== 'rev');
  renderWeeklyChart();
}


// ══════════════════════════════════════════════════════════════════════════════
// WEEKLY GRANULAR DATA  (per account × product, updated each week)
// ══════════════════════════════════════════════════════════════════════════════
// weeklyDetailHistory — rolling weekly detail, last 4 entries used in export.
// Each entry: { label: string, rows: [{distributor, network, product, units, revenue}] }
// Network-level aggregation. All distributors included. W12 appended dynamically via IIFE below.
// Sources:
//   Icedream: sales_week_12.xls parsed & validated (W10: 725u ✓, W11: 553u ✓, W12: 3067u ✓)
//   Ma'ayan:  maayan_sales_week_10_11.xlsx parsed & validated (W10: 7204u ✓, W11: 7940u ✓)
//   Ma'ayan revenue: proportionally distributed from _maayWkRev totals (~₪13.80/unit avg)
const weeklyDetailHistory = [
  {
    label: 'W10|1/3/2026',
    rows: [
      // Icedream (source: sales_week_12.xls · W10 total: 725u / ₪21,830)
      {distributor:'Icedream', network:'דומינוס',   product:'Chocolate',  units:80,  revenue:911.98},
      {distributor:'Icedream', network:'דומינוס',   product:'Mango',      units:60,  revenue:683.95},
      {distributor:'Icedream', network:'דומינוס',   product:'Vanilla',    units:24,  revenue:273.56},
      {distributor:'Icedream', network:'חוות נעמי', product:'Dream Cake', units:66,  revenue:5477.91},
      {distributor:'Icedream', network:'חוות נעמי', product:'Pistachio',  units:50,  revenue:694.97},
      {distributor:'Icedream', network:'ינגו',      product:'Chocolate',  units:140, revenue:1889.96},
      {distributor:'Icedream', network:'ינגו',      product:'Dream Cake', units:57,  revenue:8549.81},
      {distributor:'Icedream', network:'ינגו',      product:'Mango',      units:140, revenue:1889.96},
      {distributor:'Icedream', network:'ינגו',      product:'Vanilla',    units:108, revenue:1457.97},
      // Ma'ayan (source: maayan_sales_week_10_11.xlsx · W10 total: 7204u / ₪99,415)
      {distributor:'מעיין', network:'דור אלון',                 product:'Chocolate', units:480,  revenue:6623.99},
      {distributor:'מעיין', network:'דור אלון',                 product:'Mango',     units:280,  revenue:3863.99},
      {distributor:'מעיין', network:'דור אלון',                 product:'Vanilla',   units:370,  revenue:5105.99},
      {distributor:'מעיין', network:'דור אלון',                 product:'Pistachio', units:510,  revenue:7037.99},
      {distributor:'מעיין', network:'דלק מנטה',                product:'Chocolate', units:60,   revenue:828.00},
      {distributor:'מעיין', network:'דלק מנטה',                product:'Mango',     units:60,   revenue:828.00},
      {distributor:'מעיין', network:'דלק מנטה',                product:'Vanilla',   units:70,   revenue:966.00},
      {distributor:'מעיין', network:'סונול',                   product:'Chocolate', units:20,   revenue:276.00},
      {distributor:'מעיין', network:'סונול',                   product:'Mango',     units:20,   revenue:276.00},
      {distributor:'מעיין', network:'פז חברת נפט- סופר יודה',  product:'Chocolate', units:240,  revenue:3311.99},
      {distributor:'מעיין', network:'פז חברת נפט- סופר יודה',  product:'Mango',     units:150,  revenue:2070.00},
      {distributor:'מעיין', network:'פז חברת נפט- סופר יודה',  product:'Vanilla',   units:250,  revenue:3449.99},
      {distributor:'מעיין', network:'פז יילו',                 product:'Chocolate', units:490,  revenue:6761.99},
      {distributor:'מעיין', network:'פז יילו',                 product:'Mango',     units:360,  revenue:4967.99},
      {distributor:'מעיין', network:'פז יילו',                 product:'Vanilla',   units:520,  revenue:7175.99},
      {distributor:'מעיין', network:'שוק פרטי',               product:'Chocolate', units:1010, revenue:13937.97},
      {distributor:'מעיין', network:'שוק פרטי',               product:'Mango',     units:640,  revenue:8831.98},
      {distributor:'מעיין', network:'שוק פרטי',               product:'Vanilla',   units:774,  revenue:10681.18},
      {distributor:'מעיין', network:'שוק פרטי',               product:'Pistachio', units:900,  revenue:12419.98},
    ]
  },  // W10 combined: 7929u / ₪121,245 (Icedream 725u + Ma'ayan 7204u)
  {
    label: 'W11|8/3/2026',
    rows: [
      // Icedream (source: sales_week_12.xls · W11 total: 553u / ₪26,679)
      {distributor:'Icedream', network:'גוד פארם',  product:'Chocolate',  units:30,  revenue:379.81},
      {distributor:'Icedream', network:'גוד פארם',  product:'Mango',      units:30,  revenue:379.79},
      {distributor:'Icedream', network:'גוד פארם',  product:'Pistachio',  units:20,  revenue:334.03},
      {distributor:'Icedream', network:'גוד פארם',  product:'Vanilla',    units:24,  revenue:303.83},
      {distributor:'Icedream', network:'דומינוס',   product:'Chocolate',  units:100, revenue:1139.49},
      {distributor:'Icedream', network:'דומינוס',   product:'Vanilla',    units:48,  revenue:546.95},
      {distributor:'Icedream', network:'חוות נעמי', product:'Chocolate',  units:10,  revenue:132.03},
      {distributor:'Icedream', network:'חוות נעמי', product:'Dream Cake', units:281, revenue:23323.90},
      {distributor:'Icedream', network:'חוות נעמי', product:'Pistachio',  units:10,  revenue:138.99},
      // Ma'ayan (source: maayan_sales_week_10_11.xlsx · W11 total: 7940u / ₪109,572)
      {distributor:'מעיין', network:'דור אלון',                 product:'Chocolate', units:400,  revenue:5520.00},
      {distributor:'מעיין', network:'דור אלון',                 product:'Mango',     units:110,  revenue:1518.00},
      {distributor:'מעיין', network:'דור אלון',                 product:'Vanilla',   units:360,  revenue:4968.00},
      {distributor:'מעיין', network:'דור אלון',                 product:'Pistachio', units:430,  revenue:5934.00},
      {distributor:'מעיין', network:'דלק מנטה',                product:'Chocolate', units:130,  revenue:1794.00},
      {distributor:'מעיין', network:'דלק מנטה',                product:'Mango',     units:110,  revenue:1518.00},
      {distributor:'מעיין', network:'דלק מנטה',                product:'Vanilla',   units:140,  revenue:1932.00},
      {distributor:'מעיין', network:'דלק מנטה',                product:'Pistachio', units:30,   revenue:414.00},
      {distributor:'מעיין', network:'סונול',                   product:'Mango',     units:10,   revenue:138.00},
      {distributor:'מעיין', network:'סונול',                   product:'Vanilla',   units:10,   revenue:138.00},
      {distributor:'מעיין', network:'פז חברת נפט- סופר יודה',  product:'Chocolate', units:70,   revenue:966.00},
      {distributor:'מעיין', network:'פז חברת נפט- סופר יודה',  product:'Mango',     units:60,   revenue:828.00},
      {distributor:'מעיין', network:'פז חברת נפט- סופר יודה',  product:'Vanilla',   units:100,  revenue:1380.00},
      {distributor:'מעיין', network:'פז יילו',                 product:'Chocolate', units:350,  revenue:4830.00},
      {distributor:'מעיין', network:'פז יילו',                 product:'Mango',     units:240,  revenue:3312.00},
      {distributor:'מעיין', network:'פז יילו',                 product:'Vanilla',   units:340,  revenue:4692.00},
      {distributor:'מעיין', network:'שוק פרטי',               product:'Chocolate', units:1370, revenue:18906.00},
      {distributor:'מעיין', network:'שוק פרטי',               product:'Mango',     units:880,  revenue:12144.00},
      {distributor:'מעיין', network:'שוק פרטי',               product:'Vanilla',   units:1690, revenue:23322.00},
      {distributor:'מעיין', network:'שוק פרטי',               product:'Pistachio', units:1110, revenue:15318.00},
    ]
  },  // W11 combined: 8493u / ₪136,251 (Icedream 553u + Ma'ayan 7940u)
  // W12 is appended dynamically from weeklyDetail below (Ma'ayan W12 file pending)
];

// ══════════════════════════════════════════════════════════════════════════════
// Each entry: { network, account, product, upc, boxes, units, revenue }
// revenue = VAT0 invoice value (negative = return)
// Branch detail: icedream_mar_w12.xlsx (W12, 19/3/2026).
const weeklyDetail = [
  // ── גוד פארם ─────────────────────────────────────────────────────────
  {network:'גוד פארם', account:'גוד פארם קרית אונו', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:2, units:12, revenue:152.004},
  {network:'גוד פארם', account:'גוד פארם קרית אונו', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:2, units:20, revenue:253.341},
  {network:'גוד פארם', account:'גוד פארם קרית אונו', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:2, units:20, revenue:264.147},
  // ── דומינוס ──────────────────────────────────────────────────────────
  {network:'דומינוס', account:'דומינוס פיצה נהריה', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:2, units:12, revenue:136.792},
  {network:'דומינוס', account:'דומינוס פיצה נהריה', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:2, units:20, revenue:227.987},
  {network:'דומינוס', account:'דומינוס פיצה נהריה', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:5, units:50, revenue:569.967},
  {network:'דומינוס', account:'דומינוס פיצה ראשון מזרח', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:3, units:18, revenue:205.178},
  {network:'דומינוס', account:'דומינוס פיצה ראשון מזרח', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:3, units:30, revenue:368.96},
  {network:'דומינוס', account:'דומינוס פיצה ראשון מזרח', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:3, units:30, revenue:341.963},
  // ── וולט מרקט ────────────────────────────────────────────────────────
  {network:'וולט מרקט', account:'וולט מרקט  יד אליהו -', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:15, units:45, revenue:3649.153},
  {network:'וולט מרקט', account:'וולט מרקט אור יהודה', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:15, units:45, revenue:3649.153},
  {network:'וולט מרקט', account:'וולט מרקט אשדוד -', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:1, units:6, revenue:82.808},
  {network:'וולט מרקט', account:'וולט מרקט אשדוד -', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:1, units:10, revenue:142.015},
  {network:'וולט מרקט', account:'וולט מרקט אשדוד -', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:1, units:10, revenue:138.014},
  {network:'וולט מרקט', account:'וולט מרקט אשדוד -', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:15, units:45, revenue:3649.875},
  {network:'וולט מרקט', account:'וולט מרקט אשקלון', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:3, units:30, revenue:413.979},
  {network:'וולט מרקט', account:'וולט מרקט אשקלון', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:1, units:10, revenue:142.08},
  {network:'וולט מרקט', account:'וולט מרקט אשקלון', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:275.986},
  {network:'וולט מרקט', account:'וולט מרקט אשקלון', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:15, units:45, revenue:3649.312},
  {network:'וולט מרקט', account:'וולט מרקט באר שבע -', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:3, units:18, revenue:248.388},
  {network:'וולט מרקט', account:'וולט מרקט באר שבע -', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:1, units:10, revenue:138.046},
  {network:'וולט מרקט', account:'וולט מרקט באר שבע -', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:3, units:30, revenue:425.979},
  {network:'וולט מרקט', account:'וולט מרקט באר שבע -', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:275.933},
  {network:'וולט מרקט', account:'וולט מרקט בן יהודה ת"א-', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:6, units:36, revenue:496.82},
  {network:'וולט מרקט', account:'וולט מרקט בן יהודה ת"א-', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:276.011},
  {network:'וולט מרקט', account:'וולט מרקט בן יהודה ת"א-', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:10, units:30, revenue:2433.1},
  {network:'וולט מרקט', account:'וולט מרקט הקריון -', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:3, units:18, revenue:248.423},
  {network:'וולט מרקט', account:'וולט מרקט הקריון -', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:2, units:20, revenue:284.026},
  {network:'וולט מרקט', account:'וולט מרקט הקריון -', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:276.025},
  {network:'וולט מרקט', account:'וולט מרקט הרובע ראשון -', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:3, units:30, revenue:414.006},
  {network:'וולט מרקט', account:'וולט מרקט הרובע ראשון -', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:15, units:45, revenue:3649.553},
  {network:'וולט מרקט', account:'וולט מרקט הרצליה -', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:1, units:6, revenue:82.769},
  {network:'וולט מרקט', account:'וולט מרקט הרצליה -', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:1, units:10, revenue:137.948},
  {network:'וולט מרקט', account:'וולט מרקט הרצליה -', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:2, units:20, revenue:283.894},
  {network:'וולט מרקט', account:'וולט מרקט הרצליה -', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:275.897},
  {network:'וולט מרקט', account:'וולט מרקט וולפסון -', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:2, units:20, revenue:283.988},
  {network:'וולט מרקט', account:'וולט מרקט וולפסון -', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:275.988},
  {network:'וולט מרקט', account:'וולט מרקט וולפסון -', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:15, units:45, revenue:3649.346},
  {network:'וולט מרקט', account:'וולט מרקט חיפה -', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:2, units:12, revenue:165.592},
  {network:'וולט מרקט', account:'וולט מרקט חיפה -', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:1, units:10, revenue:137.993},
  {network:'וולט מרקט', account:'וולט מרקט חיפה -', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:2, units:20, revenue:283.987},
  {network:'וולט מרקט', account:'וולט מרקט חיפה -', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:275.987},
  {network:'וולט מרקט', account:'וולט מרקט ירושלים -', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:3, units:18, revenue:248.398},
  {network:'וולט מרקט', account:'וולט מרקט ירושלים -', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:1, units:10, revenue:137.999},
  {network:'וולט מרקט', account:'וולט מרקט ירושלים -', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:3, units:30, revenue:425.997},
  {network:'וולט מרקט', account:'וולט מרקט ירושלים -', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:15, units:45, revenue:3649.471},
  {network:'וולט מרקט', account:'וולט מרקט כפר סבא', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:1, units:10, revenue:138.028},
  {network:'וולט מרקט', account:'וולט מרקט כפר סבא', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:1, units:10, revenue:142.029},
  {network:'וולט מרקט', account:'וולט מרקט כפר סבא', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:1, units:10, revenue:138.028},
  {network:'וולט מרקט', account:'וולט מרקט לב השרון -', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:3, units:18, revenue:248.423},
  {network:'וולט מרקט', account:'וולט מרקט לב השרון -', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:2, units:20, revenue:284.026},
  {network:'וולט מרקט', account:'וולט מרקט לב השרון -', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:276.025},
  {network:'וולט מרקט', account:'וולט מרקט מודיעין -', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:1, units:10, revenue:141.988},
  {network:'וולט מרקט', account:'וולט מרקט נס ציונה', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:4, units:24, revenue:331.216},
  {network:'וולט מרקט', account:'וולט מרקט נס ציונה', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:1, units:10, revenue:138.007},
  {network:'וולט מרקט', account:'וולט מרקט נס ציונה', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:276.014},
  {network:'וולט מרקט', account:'וולט מרקט נס ציונה', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:3, units:9, revenue:730.187},
  {network:'וולט מרקט', account:'וולט מרקט נתניה -', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:5, units:30, revenue:413.965},
  {network:'וולט מרקט', account:'וולט מרקט נתניה -', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:3, units:30, revenue:413.965},
  {network:'וולט מרקט', account:'וולט מרקט נתניה -', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:15, units:45, revenue:3649.189},
  {network:'וולט מרקט', account:'וולט מרקט סינמה ירושלים', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:3, units:18, revenue:248.412},
  {network:'וולט מרקט', account:'וולט מרקט סינמה ירושלים', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:1, units:10, revenue:138.007},
  {network:'וולט מרקט', account:'וולט מרקט סינמה ירושלים', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:3, units:30, revenue:426.021},
  {network:'וולט מרקט', account:'וולט מרקט סינמה ירושלים', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:276.014},
  {network:'וולט מרקט', account:'וולט מרקט סינמה ירושלים', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:15, units:45, revenue:3649.681},
  {network:'וולט מרקט', account:'וולט מרקט פולג -', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:4, units:24, revenue:331.176},
  {network:'וולט מרקט', account:'וולט מרקט פולג -', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:1, units:10, revenue:137.99},
  {network:'וולט מרקט', account:'וולט מרקט פולג -', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:275.98},
  {network:'וולט מרקט', account:'וולט מרקט פולג -', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:10, units:30, revenue:2432.821},
  {network:'וולט מרקט', account:'וולט מרקט פלורנטין', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:4, units:24, revenue:331.149},
  {network:'וולט מרקט', account:'וולט מרקט פלורנטין', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:1, units:10, revenue:137.966},
  {network:'וולט מרקט', account:'וולט מרקט פלורנטין', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:5, units:50, revenue:709.929},
  {network:'וולט מרקט', account:'וולט מרקט פלורנטין', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:3, units:30, revenue:413.949},
  {network:'וולט מרקט', account:'וולט מרקט פלורנטין', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:10, units:30, revenue:2433.278},
  {network:'וולט מרקט', account:'וולט מרקט קרית אונו  -', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:4, units:24, revenue:331.198},
  {network:'וולט מרקט', account:'וולט מרקט קרית אונו  -', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:2, units:20, revenue:283.999},
  {network:'וולט מרקט', account:'וולט מרקט קרית אונו  -', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:275.999},
  {network:'וולט מרקט', account:'וולט מרקט קרית אונו  -', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:15, units:45, revenue:3649.482},
  {network:'וולט מרקט', account:'וולט מרקט ראשון מערב -', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:4, units:40, revenue:551.953},
  {network:'וולט מרקט', account:'וולט מרקט ראשון מערב -', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:275.976},
  {network:'וולט מרקט', account:'וולט מרקט ראשון מערב -', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:15, units:45, revenue:3649.189},
  {network:'וולט מרקט', account:'וולט מרקט רחובות   -', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:2, units:12, revenue:165.59},
  {network:'וולט מרקט', account:'וולט מרקט רחובות   -', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:1, units:10, revenue:137.992},
  {network:'וולט מרקט', account:'וולט מרקט רחובות   -', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:2, units:6, revenue:486.248},
  {network:'וולט מרקט', account:'וולט מרקט רמת גן', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:4, units:24, revenue:331.175},
  {network:'וולט מרקט', account:'וולט מרקט רמת גן', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:1, units:10, revenue:138.1},
  {network:'וולט מרקט', account:'וולט מרקט רמת גן', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:6, units:60, revenue:852.275},
  {network:'וולט מרקט', account:'וולט מרקט רמת גן', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:3, units:30, revenue:413.969},
  {network:'וולט מרקט', account:'וולט מרקט רמת גן', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:15, units:45, revenue:3649.227},
  {network:'וולט מרקט', account:'וולט מרקט רמת השרון -', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:2, units:12, revenue:165.583},
  {network:'וולט מרקט', account:'וולט מרקט רמת השרון -', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:275.972},
  {network:'וולט מרקט', account:'וולט מרקט רמת השרון -', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:15, units:45, revenue:3649.124},
  {network:'וולט מרקט', account:'וולט מרקט רעננה -', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:3, units:18, revenue:248.423},
  {network:'וולט מרקט', account:'וולט מרקט רעננה -', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:2, units:20, revenue:284.026},
  {network:'וולט מרקט', account:'וולט מרקט רעננה -', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:276.025},
  {network:'וולט מרקט', account:'וולט מרקט ת"א צפון-', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:15, units:45, revenue:3649.153},
  // ── ינגו ─────────────────────────────────────────────────────────────
  {network:'ינגו', account:'ינגו דלי ישראל בע"מ', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:34, units:204, revenue:2753.947},
  {network:'ינגו', account:'ינגו דלי ישראל בע"מ', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:3, units:30, revenue:404.992},
  {network:'ינגו', account:'ינגו דלי ישראל בע"מ', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:24, units:240, revenue:3239.938},
  {network:'ינגו', account:'ינגו דלי ישראל בע"מ', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:33, units:99, revenue:14849.714},
  // ── כרמלה ────────────────────────────────────────────────────────────
  {network:'כרמלה', account:'כרמלה', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:4, units:40, revenue:559.88},
  {network:'כרמלה', account:'כרמלה', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:3, units:30, revenue:419.91},
  // ── עוגיפלצת ─────────────────────────────────────────────────────────
  {network:'עוגיפלצת', account:'עוגיפלצת בע"מ', product:'דרים קייק- 3 יח (×3)', upc:'×3', boxes:17, units:51, revenue:7650.01},
  // ── פוט לוקר ─────────────────────────────────────────────────────────
  {network:'פוט לוקר', account:'פוט לוקר', product:'טורבו וניל מדגסקר (×6)', upc:'×6', boxes:4, units:24, revenue:371.913},
  {network:'פוט לוקר', account:'פוט לוקר', product:'טורבו מנגו מאיה (×10)', upc:'×10', boxes:2, units:20, revenue:309.927},
  {network:'פוט לוקר', account:'פוט לוקר', product:'טורבו פיסטוק (×10)', upc:'×10', boxes:2, units:20, revenue:309.927},
  {network:'פוט לוקר', account:'פוט לוקר', product:'טורבו שוקולד אגוזי לוז (×10)', upc:'×10', boxes:2, units:20, revenue:309.927},
  // ── חנויות ביסקוטי (W12: 18/3–21/3) — source: daniel_amit_weekly_biscotti.xlsx ─
  {distributor:'ביסקוטי', network:'חנויות ביסקוטי', account:'ביסקוטי אור ים',      product:'דרים קייק (×1)', upc:'×1', boxes:17, units:17, revenue:1360},
  {distributor:'ביסקוטי', network:'חנויות ביסקוטי', account:'ביסקוטי אלקנה',       product:'דרים קייק (×1)', upc:'×1', boxes:4,  units:4,  revenue:320},
  {distributor:'ביסקוטי', network:'חנויות ביסקוטי', account:'ביסקוטי באר יעקב',    product:'דרים קייק (×1)', upc:'×1', boxes:18, units:18, revenue:1440},
  {distributor:'ביסקוטי', network:'חנויות ביסקוטי', account:'ביסקוטי בני ברק',     product:'דרים קייק (×1)', upc:'×1', boxes:9,  units:9,  revenue:720},
  {distributor:'ביסקוטי', network:'חנויות ביסקוטי', account:'ביסקוטי כרמי גת',     product:'דרים קייק (×1)', upc:'×1', boxes:11, units:11, revenue:880},
  {distributor:'ביסקוטי', network:'חנויות ביסקוטי', account:'ביסקוטי נתניה',       product:'דרים קייק (×1)', upc:'×1', boxes:2,  units:2,  revenue:160},
  {distributor:'ביסקוטי', network:'חנויות ביסקוטי', account:'ביסקוטי פתח תקווה',   product:'דרים קייק (×1)', upc:'×1', boxes:21, units:21, revenue:1680},
  {distributor:'ביסקוטי', network:'חנויות ביסקוטי', account:'ביסקוטי ראש העין',    product:'דרים קייק (×1)', upc:'×1', boxes:15, units:15, revenue:1200},
  {distributor:'ביסקוטי', network:'חנויות ביסקוטי', account:'ביסקוטי תל מונד',     product:'דרים קייק (×1)', upc:'×1', boxes:4,  units:4,  revenue:320},
];

// Label shown in Excel headers
const weeklyDetailLabel = 'שבוע 12 | 15/3/2026';

// Append W12 detail into weeklyDetailHistory (network-level aggregation from weeklyDetail)
// Icedream W12: icedream_mar_w12.xlsx — Ma'ayan W12 file pending
// Biscotti W12 (18/3–21/3): 101 units / ₪8,080 — source: daniel_amit_weekly_biscotti.xlsx
;(function() {
  const netAgg = {};
  weeklyDetail.forEach(r => {
    const fl = (function(p){
      if(p.includes('וניל'))    return 'Vanilla';
      if(p.includes('מנגו'))    return 'Mango';
      if(p.includes('פיסטוק')) return 'Pistachio';
      if(p.includes('שוקולד')) return 'Chocolate';
      if(p.includes('דרים'))   return 'Dream Cake';
      return p;
    })(r.product);
    const key = r.network + '||' + fl;
    const dist = r.distributor || 'Icedream';
    if(!netAgg[key]) netAgg[key] = {distributor:dist, network:r.network, product:fl, units:0, revenue:0};
    netAgg[key].units   += r.units;
    netAgg[key].revenue += r.revenue;
  });
  weeklyDetailHistory.push({ label: weeklyDetailLabel, rows: Object.values(netAgg) });
})();

// ══════════════════════════════════════════════════════════════════════════════
// EXCEL EXPORT — Sales Dashboard - Raito format (4 sheets)
// ══════════════════════════════════════════════════════════════════════════════
function exportToExcel(selSheets, selCustomers, selBrands) {
  if (typeof XLSX === 'undefined') { alert('SheetJS library not loaded. Check internet connection.'); return; }
  selSheets = selSheets || ['summary','cp','wst','wd','pm','inactive'];
  selCustomers = selCustomers || customers.map(c => c.name);
  selBrands = selBrands || ['all','turbo','danis'];
  const _ccBrandAll = selBrands.indexOf('all') >= 0;
  const _ccBrandTurbo = selBrands.indexOf('turbo') >= 0;
  const _ccBrandDanis = selBrands.indexOf('danis') >= 0;
  const _ccCustFilter = c => {
    if (selCustomers.indexOf(c.name) < 0) return false;
    if (_ccBrandAll) return true;
    if (_ccBrandTurbo && c.brands && c.brands.indexOf('turbo') >= 0) return true;
    if (_ccBrandDanis && c.brands && c.brands.indexOf('danis') >= 0) return true;
    return false;
  };
  // Product-level brand helpers
  const _ccIsTurboFlavor = f => ['chocolate','vanilla','mango','pistachio'].indexOf(f) >= 0;
  const _ccIsDanisFlavor = f => f === 'dream_cake';
  const _ccFlavorIncluded = f => {
    if (_ccBrandAll) return true;
    if (_ccBrandTurbo && _ccIsTurboFlavor(f)) return true;
    if (_ccBrandDanis && _ccIsDanisFlavor(f)) return true;
    return false;
  };
  const _ccIsTurboProduct = p => p && (p.includes('טורבו') || p.includes('Turbo') || p.includes('Chocolate') || p.includes('Vanilla') || p.includes('Mango') || p.includes('Pistachio'));
  const _ccIsDanisProduct = p => p && (p.includes('דרים קייק') || p.includes('Dream Cake'));
  const _ccProductIncluded = p => {
    if (_ccBrandAll) return true;
    if (_ccBrandTurbo && _ccIsTurboProduct(p)) return true;
    if (_ccBrandDanis && _ccIsDanisProduct(p)) return true;
    return false;
  };

  const wb  = XLSX.utils.book_new();

  // ── Shared helpers ────────────────────────────────────────────────────────
  const pct  = v => v == null ? null : { v, t:'n', z:'0.0%' };
  const num  = v => v == null ? null : { v, t:'n', z:'#,##0' };
  const dec2 = v => v == null ? null : { v, t:'n', z:'#,##0.00' };
  const str  = v => v == null ? null : { v, t:'s' };

  function makeWS(aoa, colWidths) {
    // Filter nulls from each row for aoa_to_sheet compatibility
    const ws = XLSX.utils.aoa_to_sheet(aoa.map(row => Array.isArray(row) ? row.map(c => {
      if (c === null || c === undefined) return null;
      if (typeof c === 'object' && c.v !== undefined) return c;
      return c;
    }) : row));
    if (colWidths) ws['!cols'] = colWidths.map(w => ({ wch: w }));
    return ws;
  }

  const MONTHS = ['dec','jan','feb','mar'];
  const MON_LABELS = ['Dec 2025','Jan 2026','Feb 2026',`Mar 2026 (W10–W${DATA_LAST_WEEK})`];

  function sumRevMonth(m, dist) {
    return customers.reduce((s,c) => {
      if (dist && c.distributor !== dist) return s;
      return s + (c.revenue[m] || 0);
    }, 0);
  }
  function sumUnitsMonth(m, dist) {
    return customers.reduce((s,c) => {
      if (dist && c.distributor !== dist) return s;
      return s + (c.units[m] || 0);
    }, 0);
  }
  const mom = (a,b) => a > 0 ? pct((b-a)/a) : null;
  const sum4 = arr => arr.reduce((s,v)=>s+(v||0),0);

  // ══════════════════════════════════════════════════════════════════════════
  // Sheet 1: Summary
  // ══════════════════════════════════════════════════════════════════════════
  // Use filtered customers for summary aggregation
  function sumRevMonthF(m, dist) {
    return customers.filter(_ccCustFilter).reduce((s,c) => {
      if (dist && c.distributor !== dist) return s;
      return s + (c.revenue[m] || 0);
    }, 0);
  }
  function sumUnitsMonthF(m, dist) {
    return customers.filter(_ccCustFilter).reduce((s,c) => {
      if (dist && c.distributor !== dist) return s;
      return s + (c.units[m] || 0);
    }, 0);
  }
  const totRev   = MONTHS.map(m => sumRevMonthF(m));
  const totUnits = MONTHS.map(m => sumUnitsMonthF(m));
  const maayRev  = MONTHS.map(m => sumRevMonthF(m, 'מעיין נציגויות'));
  const iceRev   = MONTHS.map(m => sumRevMonthF(m, 'אייסדרים'));
  const maayU    = MONTHS.map(m => sumUnitsMonthF(m, 'מעיין נציגויות'));
  const iceU     = MONTHS.map(m => sumUnitsMonthF(m, 'אייסדרים'));

  const ws1 = makeWS([
    [`ICE CREAM SALES DASHBOARD  ·  Dec 2025 – Mar 2026 (W10–W${DATA_LAST_WEEK})`],
    ['Source: ICEDREAM invoice files + Mayyan_Turbo.xlsx + weekly XLS  ·  Gross deliveries, returns excluded'],
    [],
    ['  PORTFOLIO KPIs — All Customers'],
    ['Metric', ...MON_LABELS, 'Dec→Jan','Jan→Feb','Feb→Mar','4M Total','4M Avg / Month'],
    ['Total Revenue (NIS)', ...totRev.map(num), mom(totRev[0],totRev[1]), mom(totRev[1],totRev[2]), mom(totRev[2],totRev[3]), num(sum4(totRev)), num(sum4(totRev)/4)],
    ['Total Units',         ...totUnits.map(num), mom(totUnits[0],totUnits[1]), mom(totUnits[1],totUnits[2]), mom(totUnits[2],totUnits[3]), num(sum4(totUnits)), num(sum4(totUnits)/4)],
    [],
    ['  BY DISTRIBUTOR — Revenue (NIS)'],
    ['Distributor', ...MON_LABELS, 'Dec→Jan','Jan→Feb','Feb→Mar','4M Total','% of Total'],
    ['Ma\'ayan', ...maayRev.map(num), mom(maayRev[0],maayRev[1]), mom(maayRev[1],maayRev[2]), mom(maayRev[2],maayRev[3]), num(sum4(maayRev)), pct(sum4(totRev)>0?sum4(maayRev)/sum4(totRev):0)],
    ['Icedream',       ...iceRev.map(num),  mom(iceRev[0],iceRev[1]),   mom(iceRev[1],iceRev[2]),   mom(iceRev[2],iceRev[3]),   num(sum4(iceRev)),  pct(sum4(totRev)>0?sum4(iceRev)/sum4(totRev):0)],
    ['TOTAL',          ...totRev.map(num),  mom(totRev[0],totRev[1]),   mom(totRev[1],totRev[2]),   mom(totRev[2],totRev[3]),   num(sum4(totRev)),  pct(1)],
    [],
    ['  BY DISTRIBUTOR — Units'],
    ['Distributor', ...MON_LABELS, 'Dec→Jan','Jan→Feb','Feb→Mar','4M Total','% of Total'],
    ['Ma\'ayan', ...maayU.map(num), mom(maayU[0],maayU[1]), mom(maayU[1],maayU[2]), mom(maayU[2],maayU[3]), num(sum4(maayU)), pct(sum4(totUnits)>0?sum4(maayU)/sum4(totUnits):0)],
    ['Icedream',       ...iceU.map(num),  mom(iceU[0],iceU[1]),   mom(iceU[1],iceU[2]),   mom(iceU[2],iceU[3]),   num(sum4(iceU)),  pct(sum4(totUnits)>0?sum4(iceU)/sum4(totUnits):0)],
    ['TOTAL',          ...totUnits.map(num), mom(totUnits[0],totUnits[1]), mom(totUnits[1],totUnits[2]), mom(totUnits[2],totUnits[3]), num(sum4(totUnits)), pct(1)],
  ], [30,14,14,14,14,10,10,10,14,14]);
  if(selSheets.indexOf('summary')>=0) XLSX.utils.book_append_sheet(wb, ws1, 'Summary');

  // ══════════════════════════════════════════════════════════════════════════
  // Sheet 2: Customer Performance
  // ══════════════════════════════════════════════════════════════════════════
  const cpHeader = [
    'Customer','Distributor','Status','Dist %',
    'Rev Dec','Rev Jan','Rev Feb',`Rev Mar(W${DATA_LAST_WEEK})`,'4M Revenue',
    'Units Dec','Units Jan','Units Feb',`Units Mar(W${DATA_LAST_WEEK})`,'4M Units',
    'Avg Price','Gross Margin','Op Margin','MoM Growth (Feb→Mar)','SKUs'
  ];
  const cpRows = customers.filter(_ccCustFilter).map(c => [
    c.name, c.distributor, c.status==='active'?'Active':'Negotiation', pct(c.dist_pct/100),
    num(c.revenue.dec), num(c.revenue.jan), num(c.revenue.feb), num(c.revenue.mar||0),
    num(c.revenue.dec+c.revenue.jan+c.revenue.feb+(c.revenue.mar||0)),
    num(c.units.dec), num(c.units.jan), num(c.units.feb), num(c.units.mar||0),
    num(c.units.dec+c.units.jan+c.units.feb+(c.units.mar||0)),
    c.avgPrice!=null ? dec2(c.avgPrice) : null,
    c.grossMargin!=null ? pct(c.grossMargin/100) : null,
    c.opMargin!=null ? pct(c.opMargin/100) : null,
    c.momGrowth!=null ? pct(c.momGrowth/100) : null,
    c.activeSKUs
  ]);
  const cpTotRow = [
    'TOTAL / AVERAGE', null, null, null,
    num(sumRevMonthF('dec')), num(sumRevMonthF('jan')), num(sumRevMonthF('feb')), num(sumRevMonthF('mar')),
    num(MONTHS.reduce((s,m)=>s+sumRevMonthF(m),0)),
    num(sumUnitsMonthF('dec')), num(sumUnitsMonthF('jan')), num(sumUnitsMonthF('feb')), num(sumUnitsMonthF('mar')),
    num(MONTHS.reduce((s,m)=>s+sumUnitsMonthF(m),0)),
    null, null, null, null, null
  ];
  const ws2 = makeWS([
    ['CUSTOMER PERFORMANCE — Revenue, Units & Margins (Dec 2025 – Mar 2026)'],
    [],
    cpHeader,
    ...cpRows,
    cpTotRow
  ], [20,22,12,7,12,12,12,14,12,10,10,10,12,10,10,10,10,18,6]);
  if(selSheets.indexOf('cp')>=0) XLSX.utils.book_append_sheet(wb, ws2, 'Customer Performance');

  // ══════════════════════════════════════════════════════════════════════════
  // Sheet 3: Weekly Sales Trend
  // ══════════════════════════════════════════════════════════════════════════
  const nW = weeklyXLabels.length;
  const wkNums = weeklyXLabels.map((_,i) => 'W'+(i+1));

  const totalIceRev   = _iceWkRev.reduce((s,v)=>s+(v||0),0);
  const totalTurboRev = _iceWkRevTurbo.reduce((s,v)=>s+(v||0),0);
  const totalDanisRev = _iceWkRevDanis.reduce((s,v)=>s+(v||0),0);
  const totalRetRev   = _iceWkRetRev.reduce((s,v)=>s+(v||0),0);
  const totalMaayRev  = Object.values(_maayWkRev).reduce((s,v)=>s+v,0);
  const totalIceU     = _iceWkUnits.reduce((s,v)=>s+(v||0),0);
  const totalMaayU    = Object.values(_maayWkUnits).reduce((s,v)=>s+v,0);

  const maayRevRow = weeklyXLabels.map((_,i) => _maayWkRev[i+1] ? num(_maayWkRev[i+1]) : null);
  const maayURow   = weeklyXLabels.map((_,i) => _maayWkUnits[i+1] ? num(_maayWkUnits[i+1]) : null);
  const combRevRow = weeklyXLabels.map((_,i) => num((_iceWkRev[i]||0)+(_maayWkRev[i+1]||0)));
  const combURow   = weeklyXLabels.map((_,i) => num((_iceWkUnits[i]||0)+(_maayWkUnits[i+1]||0)));

  const wow = arr => arr.map((v,i) => i===0 ? '—' : (arr[i-1]>0 ? pct((v-arr[i-1])/arr[i-1]) : null));
  const iceWow = wow(_iceWkRev);
  const wowHdrs = weeklyXLabels.slice(1).map((_,i)=>`W${i+1}→W${i+2}`);
  const wowVals = _iceWkRev.map((v,i)=>i>0&&_iceWkRev[i-1]>0?(v-_iceWkRev[i-1])/_iceWkRev[i-1]:null).filter(v=>v!=null);

  // ── Breakdown by customer & flavor from weeklyDetail ────────────────────
  const _detNetOrder = [];
  const _detNetMap = {};
  weeklyDetail.filter(r => _ccProductIncluded(r.product)).forEach(r => {
    if (!_detNetMap[r.network]) { _detNetMap[r.network] = {}; _detNetOrder.push(r.network); }
    if (!_detNetMap[r.network][r.account]) _detNetMap[r.network][r.account] = [];
    _detNetMap[r.network][r.account].push(r);
  });
  const _detRows = [];
  _detNetOrder.forEach(net => {
    const accs = _detNetMap[net];
    let netU = 0, netR = 0;
    Object.entries(accs).forEach(([acc, rows]) => {
      rows.forEach(r => {
        _detRows.push([str(r.network), str(r.account), str(r.product), num(r.boxes), num(r.units), {v:r.revenue, t:'n', z:'#,##0.00'}]);
        netU += r.units; netR += r.revenue;
      });
    });
    _detRows.push([str(`  ${net} — Subtotal`), null, null, null, num(netU), {v:netR, t:'n', z:'#,##0.00'}]);
    _detRows.push([]);
  });
  const _detGrandU = weeklyDetail.reduce((s,r)=>s+r.units, 0);
  const _detGrandR = weeklyDetail.reduce((s,r)=>s+r.revenue, 0);

  const ws3 = makeWS([
    [`WEEKLY SALES TREND — Icedreams vs. Ma'ayan vs. Biscotti  ·  ${weeklyXLabels[0]} – ${weeklyXLabels[nW-1]} 2026`],
    [`Icedreams: W1–W${nW}  ·  Ma'ayan: W6–W11 only  ·  Biscotti: W12+ only  ·  Gross deliveries, returns excluded`],
    [],
    ['  WEEKLY REVENUE (NIS)  ·  Icedreams vs. Ma\'ayan vs. Biscotti'],
    ['Metric','Date',...weeklyXLabels,'Total','Avg/Week'],
    ['Icedreams — Combined',          null,..._iceWkRev.map(num),      num(totalIceRev),   num(totalIceRev/nW)],
    ['  ↳ Turbo only',                null,..._iceWkRevTurbo.map(num), num(totalTurboRev), num(totalTurboRev/nW)],
    ["  ↳ Danis (Dream Cake) only",   null,..._iceWkRevDanis.map(num), num(totalDanisRev), num(totalDanisRev/nW)],
    ['  ↳ Returns (excl.)',           null,..._iceWkRetRev.map(num),   num(totalRetRev),   num(totalRetRev/nW)],
    ['Ma\'ayan — Turbo',               null,...maayRevRow,              num(totalMaayRev),  num(totalMaayRev/4)],
    ['Combined (Ice+Ma\'ayan+Biscotti)', null,...combRevRow,              num(totalIceRev+totalMaayRev), num((totalIceRev+totalMaayRev)/nW)],
    ['Week date',                     null,...weeklyXLabels],
    [],
    ['  WEEKLY UNITS  ·  Icedreams vs. Ma\'ayan vs. Biscotti'],
    ['Week','Date',...wkNums,'Total','Avg/Week'],
    ['Icedreams', null,..._iceWkUnits.map(num), num(totalIceU),  num(totalIceU/nW)],
    ['Ma\'ayan',  null,...maayURow,             num(totalMaayU), num(totalMaayU/4)],
    ['Combined',  null,...combURow,             num(totalIceU+totalMaayU), num((totalIceU+totalMaayU)/nW)],
    [],
    ['  WEEK-OVER-WEEK REVENUE GROWTH (%)  ·  Icedreams Combined'],
    ['Metric',null,...wowHdrs,'Best Week','Worst Week'],
    ['Icedreams WoW %',null,...iceWow, pct(wowVals.length?Math.max(...wowVals):null), pct(wowVals.length?Math.min(...wowVals):null)],
    [],
    [],
    [`  BREAKDOWN BY CUSTOMER & FLAVOR — ${weeklyDetailLabel}  (Icedreams only)`],
    ['Network', 'Account', 'Product', 'Boxes', 'Units', 'Revenue (₪)'],
    ..._detRows,
    ['GRAND TOTAL', null, null, null, num(_detGrandU), {v:_detGrandR, t:'n', z:'#,##0.00'}],
  ], [24, 32, 36, 8, 10, 12, ...Array(Math.max(0, nW-2)).fill(10), 10, 10]);
  if(selSheets.indexOf('wst')>=0) XLSX.utils.book_append_sheet(wb, ws3, 'Weekly Sales Trend');

  // ══════════════════════════════════════════════════════════════════════════
  // Sheet 4: Weekly Detail — by Week × Flavor × Customer
  // ══════════════════════════════════════════════════════════════════════════

  // Map Hebrew product names → English flavor
  const _flavorMap = [
    ['טורבו שוקולד', 'Chocolate'],
    ['טורבו וניל',   'Vanilla'],
    ['טורבו מנגו',   'Mango'],
    ['טורבו פיסטוק', 'Pistachio'],
    ['דרים קייק',    'Dream Cake'],
  ];
  const _toFlavor = prod => {
    for (const [k,v] of _flavorMap) { if (prod.includes(k)) return v; }
    return prod;
  };
  const _flavorOrderAll = ['Chocolate', 'Vanilla', 'Mango', 'Pistachio', 'Dream Cake'];
  const _flavorToBrand = {'Chocolate':'turbo','Vanilla':'turbo','Mango':'turbo','Pistachio':'turbo','Dream Cake':'danis'};
  const _flavorOrder = _flavorOrderAll.filter(f => _ccBrandAll || (_ccBrandTurbo && _flavorToBrand[f]==='turbo') || (_ccBrandDanis && _flavorToBrand[f]==='danis'));

  // Build Weekly Detail sheet from last 4 entries of weeklyDetailHistory
  // Shows ALL distributors (Icedream + Ma'ayan). Grouped by week → distributor → flavor → network.
  const _histSlice = weeklyDetailHistory.slice(-4);
  const _wdRows = [];
  let _wdGrandU = 0, _wdGrandR = 0;

  _histSlice.forEach(entry => {
    // Group rows by distributor
    const _byDist = {};
    entry.rows.forEach(r => {
      const dist = r.distributor || 'Icedream';
      if (!_byDist[dist]) _byDist[dist] = {};
      const fl  = r.product;
      const net = r.network;
      if (!_byDist[dist][fl]) _byDist[dist][fl] = {};
      if (!_byDist[dist][fl][net]) _byDist[dist][fl][net] = {units:0, revenue:0};
      _byDist[dist][fl][net].units   += r.units;
      _byDist[dist][fl][net].revenue += r.revenue;
    });

    // Render each distributor section
    const distOrder = ['Icedream', 'מעיין', 'ביסקוטי'];
    distOrder.forEach(dist => {
      if (!_byDist[dist]) return;
      let distU = 0, distR = 0;
      _flavorOrder.forEach(fl => {
        if (!_byDist[dist][fl]) return;
        const nets = Object.entries(_byDist[dist][fl]).sort((a,b) => b[1].units - a[1].units);
        let flU = 0, flR = 0;
        nets.forEach(([net, d]) => {
          _wdRows.push([str(entry.label), str(dist), str(fl), str(net), num(d.units), {v:d.revenue,t:'n',z:'#,##0.00'}]);
          flU += d.units; flR += d.revenue;
          _wdGrandU += d.units; _wdGrandR += d.revenue;
          distU += d.units; distR += d.revenue;
        });
        _wdRows.push([null, null, str(`  ${fl} — Subtotal`), null, num(flU), {v:flR,t:'n',z:'#,##0.00'}]);
        _wdRows.push([]);
      });
      _wdRows.push([null, str(`${dist} — Week Subtotal`), null, null, num(distU), {v:distR,t:'n',z:'#,##0.00'}]);
      _wdRows.push([]);
    });
    _wdRows.push([]);  // extra blank row between weeks
  });
  _wdRows.push([str('GRAND TOTAL (all weeks, all distributors)'), null, null, null, num(_wdGrandU), {v:_wdGrandR,t:'n',z:'#,##0.00'}]);

  const _wdFirstLabel = _histSlice[0]?.label || '';
  const _wdLastLabel  = _histSlice[_histSlice.length-1]?.label || '';
  const ws4b = makeWS([
    [`WEEKLY DETAIL — ALL DISTRIBUTORS  ·  ${_wdFirstLabel} – ${_wdLastLabel}`],
    [`Aggregated to network level  ·  Gross deliveries only  ·  Last ${_histSlice.length} available weeks  ·  Ma'ayan revenue proportional to weekly total`],
    [],
    ['Week', 'Distributor', 'Flavor', 'Customer Network', 'Units', 'Revenue (₪)'],
    ..._wdRows,
  ], [20, 12, 14, 28, 10, 14]);
  if(selSheets.indexOf('wd')>=0) XLSX.utils.book_append_sheet(wb, ws4b, 'Weekly Detail');

  // ══════════════════════════════════════════════════════════════════════════
  // Sheet 5: Product Mix (was Sheet 4)
  // ══════════════════════════════════════════════════════════════════════════
  const PKEYS = ['chocolate','vanilla','mango','pistachio','dream_cake'];
  const _pmKeys = PKEYS.filter(_ccFlavorIncluded);
  const _pmLabels = {'chocolate':'Chocolate','vanilla':'Vanilla','mango':'Mango','pistachio':'Pistachio','dream_cake':'Dream Cake'};
  const pmRows = customers.filter(c=>productMix[c.id]&&_ccCustFilter(c)).map(c=>{
    const mx=productMix[c.id];
    const vals=_pmKeys.map(k=>mx[k]!=null?mx[k]:null);
    const tot=_pmKeys.reduce((s,k)=>s+(mx[k]||0),0);
    const cv=(_ccFlavorIncluded('chocolate')?(mx.chocolate||0):0)+(_ccFlavorIncluded('vanilla')?(mx.vanilla||0):0);
    const _dn={'מעיין נציגויות':"Ma'ayan",'אייסדרים':'Icedream','ביסקוטי':'Biscotti'}; return [c.name,(_dn[c.distributor]||c.distributor),...vals,num(tot),pct(tot>0?cv/tot:null)];
  });
  const pmGT=_pmKeys.map(k=>customers.filter(_ccCustFilter).reduce((s,c)=>s+((productMix[c.id]||{})[k]||0),0));
  const pmGrand=pmGT.reduce((s,v)=>s+v,0);
  const pmGCV=customers.filter(_ccCustFilter).reduce((s,c)=>{const mx=productMix[c.id]||{};return s+(_ccFlavorIncluded('chocolate')?(mx.chocolate||0):0)+(_ccFlavorIncluded('vanilla')?(mx.vanilla||0):0);},0);
  const ws4=makeWS([
    ['PRODUCT MIX PER CUSTOMER — Total Units (All Months Combined)'],
    [],
    ['Customer','Distributor',..._pmKeys.map(k=>_pmLabels[k]),'Total','% Choc+Van'],
    ...pmRows,
    ['TOTAL',null,...pmGT.map(num),num(pmGrand),pct(pmGrand>0?pmGCV/pmGrand:null)],
  ],[20,22,10,10,10,10,11,10,11]);
  if(selSheets.indexOf('pm')>=0) XLSX.utils.book_append_sheet(wb,ws4,'Product Mix');


  // ── Write file ─────────────────────────────────────────────────────────────
  if(wb.SheetNames.length===0){alert('No sheets selected.');return;}
  const today=new Date();
  const dd=String(today.getDate()).padStart(2,'0');
  const mm=String(today.getMonth()+1).padStart(2,'0');
  const yy=today.getFullYear();
  XLSX.writeFile(wb,`Sales Dashboard - Raito ${dd}.${mm}.${yy}.xlsx`);
}


</script>
</body>
</html>
"""
