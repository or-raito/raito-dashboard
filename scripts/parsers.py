#!/usr/bin/env python3
"""
Raito Dashboard — Data Parsers
All file parsing functions: Icedream, Ma'ayan, Karfree, Distributor Stock, Production.
"""
from __future__ import annotations

import re
import math
import logging
import pandas as pd
from openpyxl import load_workbook
from config import (
    DATA_DIR, OUTPUT_DIR, classify_product, extract_units_per_carton,
    MONTH_ORDER, extract_customer_name,
)
from pricing_engine import get_b2b_price_safe, get_production_cost
from registry import validate_sku, PRODUCTS

_log = logging.getLogger(__name__)

# Track unknown SKUs seen during this session (warn once per SKU)
_unknown_skus_warned: set = set()

def _validated_product(product: str) -> str | None:
    """Validate a classified product SKU against the registry.

    Returns the product key if valid, or None if unknown (logs a warning).
    """
    if product is None:
        return None
    if product in PRODUCTS:
        return product
    if product not in _unknown_skus_warned:
        _unknown_skus_warned.add(product)
        _log.warning(
            "Unregistered SKU '%s' detected during data ingestion — "
            "register it in registry.PRODUCTS before use", product
        )
        print(f"  ⚠ WARNING: Unregistered SKU '{product}' — add to registry.py")
    return product  # Pass through so data isn't silently lost


# ── Month Detection ─────────────────────────────────────────────────────

def detect_month_from_sheet(ws):
    """Detect month from sheet name and date range row (Row 3)."""
    title = ws.title or ''
    month_keywords = {
        'דצמבר': 'December 2025', 'December': 'December 2025',
        'ינואר': 'January 2026', 'January': 'January 2026',
        'פברואר': 'February 2026', 'February': 'February 2026',
        'מרץ': 'March 2026', 'March': 'March 2026',
    }
    for keyword, month in month_keywords.items():
        if keyword in title:
            return month

    for col in range(1, 7):
        val = ws.cell(row=3, column=col).value
        if val is None:
            continue
        val = str(val)
        date_match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', val)
        if date_match:
            day, month_num, year = date_match.groups()
            month_num = int(month_num)
            year = int(year)
            month_map = {
                (12, 2025): 'December 2025',
                (1, 2026): 'January 2026', (2, 2026): 'February 2026',
                (3, 2026): 'March 2026', (4, 2026): 'April 2026',
            }
            return month_map.get((month_num, year), f'{month_num}/{year}')

    for row in range(1, 5):
        for col in range(1, 6):
            val = ws.cell(row=row, column=col).value
            if val is None:
                continue
            val = str(val)
            for keyword, month in month_keywords.items():
                if keyword in val:
                    return month
    return None


# ── Icedreams Parser ─────────────────────────────────────────────────────

def _icedream_week_to_month(week_num: int, year: int = 2026) -> str:
    """Map an Icedream week number to a month string.

    Uses Jan 1 as the base (week 1 starts Jan 1).  Weeks 10-13 → March 2026, etc.
    """
    from datetime import date, timedelta
    base = date(year, 1, 1)
    week_start = base + timedelta(weeks=week_num - 1)
    month_map = {
        (1, 2026): 'January 2026', (2, 2026): 'February 2026',
        (3, 2026): 'March 2026',   (4, 2026): 'April 2026',
        (5, 2026): 'May 2026',     (12, 2025): 'December 2025',
    }
    return month_map.get((week_start.month, week_start.year),
                         f'{week_start.month}/{week_start.year}')


def _parse_icedreams_compact(ws, wb):
    """Parse an Icedream compact weekly XLSX (cols: A=account, B=item, C=qty, D=value).

    This format is used for week13.xlsx and similar single-week exports.  Row 1 carries
    the week label (e.g. 'שבוע 13 2026' in col D), row 2 is the column-header row.
    Data starts at row 3.
    """
    # Detect month from the week label in D1
    header_text = str(ws.cell(row=1, column=4).value or '')
    month = None
    m = re.search(r'שבוע\s+(\d+)\s+(\d{4})', header_text)
    if m:
        month = _icedream_week_to_month(int(m.group(1)), int(m.group(2)))
    if not month:
        month = detect_month_from_sheet(ws) or 'Unknown'

    data = {'month': month, 'by_customer': {}, 'totals': {}}
    current_account = None

    for row_idx in range(3, ws.max_row + 1):
        col_a = ws.cell(row=row_idx, column=1).value
        col_b = ws.cell(row=row_idx, column=2).value
        col_c = ws.cell(row=row_idx, column=3).value  # quantity
        col_d = ws.cell(row=row_idx, column=4).value  # value

        # New account block starts when col A is non-empty
        if col_a is not None:
            account_raw = str(col_a).strip()
            # Strip the delivery-type suffix (e.g. '*...*ת.משלוח')
            account_raw = re.sub(r'\*ת\.\s*משלוח$', '', account_raw).strip('* ')
            current_account = account_raw or current_account

        item_name = str(col_b).strip() if col_b else ''
        if not item_name or 'סה"כ' in item_name or item_name == 'שם פריט':
            continue  # skip header / subtotal rows

        if col_c is None or not isinstance(col_c, (int, float)):
            continue

        product = _validated_product(classify_product(item_name))
        if not product:
            continue

        upc = extract_units_per_carton(item_name)
        raw_qty = float(col_c)
        sign = -1 if raw_qty < 0 else 1   # negative in report = outgoing (sales)
        cartons = abs(raw_qty)
        units = round(cartons * upc) * sign * -1   # flip to positive sales
        # col_d is negative for sales (same sign as col_c) → negate to get positive revenue
        value = -float(col_d) if isinstance(col_d, (int, float)) else 0

        if product not in data['totals']:
            data['totals'][product] = {'units': 0, 'value': 0, 'cartons': 0}
        data['totals'][product]['units'] += units
        data['totals'][product]['value'] += value
        data['totals'][product]['cartons'] += cartons * sign * -1

        if current_account:
            if current_account not in data['by_customer']:
                data['by_customer'][current_account] = {}
            if product not in data['by_customer'][current_account]:
                data['by_customer'][current_account][product] = {'units': 0, 'value': 0, 'cartons': 0}
            data['by_customer'][current_account][product]['units'] += units
            data['by_customer'][current_account][product]['value'] += value
            data['by_customer'][current_account][product]['cartons'] += cartons * sign * -1

    wb.close()
    return data


def parse_icedreams_file(filepath):
    """Parse a single Icedreams monthly report.

    Supports two layouts:
    - Classic monthly (cols D=item, E=value, F=qty; bold col-A rows = customer)
    - Compact weekly  (cols A=account, B=item, C=qty, D=value; header row 2 = 'שם חשבון')
    """
    wb = load_workbook(filepath)
    ws = wb[wb.sheetnames[0]]

    # Detect compact weekly format: row 2, col A = 'שם חשבון'
    if str(ws.cell(row=2, column=1).value or '').strip() == 'שם חשבון':
        return _parse_icedreams_compact(ws, wb)

    month = detect_month_from_sheet(ws)
    if not month:
        month = ws.title if ws.title else 'Unknown'

    data = {'month': month, 'by_customer': {}, 'totals': {}}
    pending_products = []

    for row_idx in range(1, ws.max_row + 1):
        cell_a = ws.cell(row=row_idx, column=1)
        is_bold = cell_a.font.bold if cell_a.font else False
        item_name = ws.cell(row=row_idx, column=4).value
        sales_val = ws.cell(row=row_idx, column=5).value
        quantity = ws.cell(row=row_idx, column=6).value

        if is_bold and cell_a.value:
            s = str(cell_a.value).strip()
            if 'סה"כ' in s and 'לדו' not in s and 'מס' not in s:
                cell_b = ws.cell(row=row_idx, column=2)
                customer_name = str(cell_b.value).strip() if cell_b.value else s.replace('סה"כ', '').strip()
                if customer_name:
                    if customer_name not in data['by_customer']:
                        data['by_customer'][customer_name] = {}
                    for pp in pending_products:
                        p, u, v, c = pp
                        if p not in data['by_customer'][customer_name]:
                            data['by_customer'][customer_name][p] = {'units': 0, 'value': 0, 'cartons': 0}
                        data['by_customer'][customer_name][p]['units'] += u
                        data['by_customer'][customer_name][p]['value'] += v
                        data['by_customer'][customer_name][p]['cartons'] += c
                    pending_products = []

        if item_name and quantity is not None:
            product = _validated_product(classify_product(item_name))
            if product:
                upc = extract_units_per_carton(item_name)
                raw_qty = float(quantity)
                # Negative = sales, Positive = returns (subtract)
                sign = -1 if raw_qty < 0 else 1  # sales are negative in report
                cartons = abs(raw_qty)
                units = round(cartons * upc) * sign * -1  # flip: negative→positive sales
                value = float(sales_val) * sign * -1 if sales_val else 0

                if product not in data['totals']:
                    data['totals'][product] = {'units': 0, 'value': 0, 'cartons': 0}
                data['totals'][product]['units'] += units
                data['totals'][product]['value'] += value
                data['totals'][product]['cartons'] += cartons * sign * -1
                pending_products.append((product, units, value, cartons * sign * -1))

    wb.close()
    return data


def parse_format_b_xls(filepath):
    """Parse an Icedream Format B weekly XLS file (BIFF8/OLE2) using xlrd.

    These are the weekly comparison files (e.g. sales_week_12.xls) sent directly
    from Icedream's system. One row per product per customer; multiple week columns.

    Column layout (3-week file):
      0: Account name (only on first product row per customer)
      1: Product name (Hebrew SKU)
      2: W10 qty (cartons, negative = sales)
      3: W10 revenue (ILS, negative = sales)
      4: W11 qty / 5: W11 revenue
      6: W12 qty / 7: W12 revenue
      8: total qty / 9: total revenue

    Returns:
      {chain_en: {wk_idx: {product: {'units': int, 'value': float}}}}
      where wk_idx is 0-based (0=first week col, 1=second, etc.)

    Special rule: 'Oogiplatset' (עוגיפלצת) is only included for the LAST week
    column (W12), not for earlier weeks, per dashboard convention.
    """
    try:
        import xlrd  # noqa: F401
    except ImportError:
        return {}

    try:
        import re as _re_local
        wb = xlrd.open_workbook(str(filepath))
        ws = wb.sheets()[0]
    except Exception:
        return {}

    # Detect week columns by scanning row 2 for 'שבוע' headers
    week_cols = []   # list of (qty_col, rev_col) pairs, in week order
    for j in range(ws.ncols):
        cell_val = str(ws.cell_value(2, j)) if ws.nrows > 2 else ''
        if 'שבוע' in cell_val:
            # qty at j+1 is actually the raw header; actual data starts from col after header
            # Row 3 has: "שם חשבון","שם פריט","כמות","בש\"ח","כמות","בש\"ח",...
            # Each week occupies 2 cols starting at the col where "שבוע X" appears + 1
            pass
    # Instead: parse row 3 for "כמות" / "בש"כ" pairs, skip account+product cols
    # Cols 0=account,1=product then pairs of (qty,rev) per week
    # Cols 0=account, 1=product, then pairs of (qty,rev) per week.
    # Last 2 cols are grand total — exclude them from week_cols.
    data_start_col = 2
    week_cols = []
    for j in range(data_start_col, ws.ncols - 2, 2):  # ws.ncols-2 excludes total cols
        week_cols.append((j, j + 1))

    def _clean(s):
        """Strip branch decorations to get a clean chain name."""
        s = _re_local.sub(r'^\*+|\*+$', '', s).strip()
        s = _re_local.sub(r'\*ת\.משלוח.*$', '', s).strip()
        s = _re_local.sub(r'ת\.משלוח.*$', '', s).strip()
        s = _re_local.sub(r'\*[^*]*$', '', s).strip()
        return s.strip()

    n_weeks = len(week_cols)
    customers = {}   # {chain_en: {wk_idx: {product: {'units', 'value'}}}}
    current_chain = None

    for row_idx in range(4, ws.nrows):
        row = [ws.cell_value(row_idx, j) for j in range(ws.ncols)]
        account_raw = str(row[0]).strip() if row[0] else ''
        product_raw = str(row[1]).strip() if row[1] else ''

        # Skip summary rows
        if product_raw == 'סה"כ' or account_raw == 'סה"כ':
            continue

        if account_raw:
            cleaned = _clean(account_raw)
            current_chain = extract_customer_name(cleaned)

        if not current_chain or not product_raw:
            continue

        # Strict Raito product filter
        if 'טורבו' not in product_raw and 'דרים קייק' not in product_raw:
            continue

        product = _validated_product(classify_product(product_raw))
        if not product:
            continue

        pack_size = extract_units_per_carton(product_raw)
        is_ugipletzet = 'Oogiplatset' in current_chain or 'עוגיפלצת' in current_chain

        if current_chain not in customers:
            customers[current_chain] = {i: {} for i in range(n_weeks)}

        for wk_i, (qi, vi) in enumerate(week_cols):
            # Oogiplatset rule: only include data from the LAST week column
            if is_ugipletzet and wk_i < n_weeks - 1:
                continue

            qty_raw = row[qi] if qi < len(row) and row[qi] != '' else 0
            rev_raw = row[vi] if vi < len(row) and row[vi] != '' else 0
            try:
                qty = float(qty_raw) if qty_raw not in ('', None) else 0.0
                rev = float(rev_raw) if rev_raw not in ('', None) else 0.0
            except (TypeError, ValueError):
                qty = rev = 0.0

            units = int(round(abs(qty) * pack_size))
            value = round(abs(rev), 2)

            if units > 0 or value > 0:
                if product not in customers[current_chain][wk_i]:
                    customers[current_chain][wk_i][product] = {'units': 0, 'value': 0.0}
                customers[current_chain][wk_i][product]['units'] += units
                customers[current_chain][wk_i][product]['value'] += value

    return customers


def parse_all_icedreams():
    """Parse all Icedreams files in the icedreams folder."""
    folder = DATA_DIR / 'icedreams'
    if not folder.exists():
        return {}
    results = {}
    for f in sorted(folder.glob('*.xlsx')):
        if f.name.startswith('~'):
            continue
        if 'stock' in f.name.lower():
            continue
        data = parse_icedreams_file(f)
        month = data['month']
        if month in results:
            for product, vals in data['totals'].items():
                if product not in results[month]['totals']:
                    results[month]['totals'][product] = {'units': 0, 'value': 0, 'cartons': 0}
                for k in ['units', 'value', 'cartons']:
                    results[month]['totals'][product][k] += vals[k]
            for cust, pdata in data.get('by_customer', {}).items():
                if cust not in results[month]['by_customer']:
                    results[month]['by_customer'][cust] = {}
                for p, vals in pdata.items():
                    if p not in results[month]['by_customer'][cust]:
                        results[month]['by_customer'][cust][p] = {'units': 0, 'value': 0, 'cartons': 0}
                    for k in ['units', 'value', 'cartons']:
                        results[month]['by_customer'][cust][p][k] += vals.get(k, 0)
        else:
            results[month] = data

    # ── Supplement months with unattributed units from Format B XLS ──────
    # Some weekly .xlsx files produce flat totals but empty by_customer
    # (e.g. icedream_mar_w10_11.xlsx lacks bold customer-summary rows).
    # The Format B .xls file (sales_week_12.xls) covers the same weeks with
    # full per-customer data.  We take all week columns EXCEPT the LAST one
    # (the last week is already attributed via the corresponding _w12.xlsx).
    for f in sorted(folder.glob('*.xls')):
        if f.name.startswith('~') or 'stock' in f.name.lower():
            continue
        format_b = parse_format_b_xls(f)
        if not format_b:
            continue
        n_weeks = len(next(iter(format_b.values()), {}))
        if n_weeks < 2:
            continue  # nothing to supplement (no earlier weeks)
        weeks_to_supplement = range(n_weeks - 1)  # all except last

        for month_str, mdata in results.items():
            flat_total = sum(v.get('units', 0) for v in mdata.get('totals', {}).values())
            cust_total = sum(
                sum(p.get('units', 0) for p in prods.values())
                for prods in mdata.get('by_customer', {}).values()
            )
            if flat_total <= cust_total:
                continue  # already fully attributed — nothing to supplement

            # Merge early-week customer data from Format B into by_customer.
            # Format B returns English chain names; they pass through
            # extract_customer_name() unchanged and resolve via _CUSTOMER_EN_TO_CC_ID.
            for chain_en, weeks in format_b.items():
                for wk_i in weeks_to_supplement:
                    wk_data = weeks.get(wk_i, {})
                    for product, pd in wk_data.items():
                        units = pd.get('units', 0)
                        value = round(pd.get('value', 0.0), 2)
                        if units == 0:
                            continue
                        if chain_en not in mdata['by_customer']:
                            mdata['by_customer'][chain_en] = {}
                        if product not in mdata['by_customer'][chain_en]:
                            mdata['by_customer'][chain_en][product] = {'units': 0, 'value': 0.0, 'cartons': 0}
                        mdata['by_customer'][chain_en][product]['units'] += units
                        mdata['by_customer'][chain_en][product]['value'] += value

    return results


# ── Ma'ayan Price Table ───────────────────────────────────────────────────

# Maps Maayan raw chain names (שם רשת) → price DB customer name
_MAAYAN_CHAIN_TO_PRICEDB = {
    'דור אלון':                    'AMPM',
    'שוק פרטי':                    'שוק פרטי',
    'דלק מנטה':                    'דלק',
    'סונול':                       'סונול',
    'פז ילו':                      'פז יילו',
    'פז יילו':                     'פז יילו',
    'פז חברת נפט- סופר יודה':      'פז סופר יודה',
    'שפר את אלי לוי בע"מ':         'אלונית',
}

# Maps Hebrew product names in price DB → internal product keys
_PRICEDB_PRODUCT_MAP = {
    'גלידת חלבון וניל':            'vanilla',
    'גלידת חלבון מנגו':            'mango',
    'גלידת חלבון פיסטוק':          'pistachio',
    'גלידת חלבון שוקולד לוז':      'chocolate',
}

def _load_mayyan_price_table():
    """Load latest price DB file and return {product: {chain: price}} for Maayan.
    Falls back to B2B list price via pricing_engine for any missing product/chain combo.
    """
    price_dir = DATA_DIR / 'price data'
    if not price_dir.exists():
        return {}

    # Use most recently modified price db file
    candidates = sorted(
        [f for f in price_dir.glob('price db*.xlsx') if not f.name.startswith('~')],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return {}

    try:
        # Detect the header row: scan for the row that contains 'לקוח' and 'מחיר'
        _probe = pd.read_excel(candidates[0], header=None)
        header_row = 0
        for _i, _row in _probe.iterrows():
            _vals = [str(v) for v in _row.values]
            if any('לקוח' in v for v in _vals) and any('מחיר' in v for v in _vals):
                header_row = _i
                break
        df = pd.read_excel(candidates[0], header=header_row)
        price_col = next((c for c in df.columns if 'מחיר' in str(c) and 'מכירה' in str(c)), None)
        cust_col  = next((c for c in df.columns if 'לקוח' in str(c)), None)
        # 'מוצרים' is old column name; file uses 'שם פריט' or 'פריט' in newer exports
        prod_col  = next((c for c in df.columns if 'מוצרים' in str(c) or 'פריט' in str(c)), None)
        dist_col  = next((c for c in df.columns if 'מפיץ' in str(c)), None)
        if not all([price_col, cust_col, prod_col, dist_col]):
            return {}

        # Filter to Maayan rows only
        may_df = df[df[dist_col].astype(str).str.contains('מעיין', na=False)]

        # Build {product_key: {pricedb_customer: price}}
        table = {}
        for _, row in may_df.iterrows():
            prod_key = _PRICEDB_PRODUCT_MAP.get(str(row[prod_col]).strip())
            if not prod_key:
                continue
            cust = str(row[cust_col]).strip()
            price = float(row[price_col]) if row[price_col] else 0
            if prod_key not in table:
                table[prod_key] = {}
            table[prod_key][cust] = price
        return table
    except Exception:
        return {}


def _mayyan_chain_price(price_table, chain_raw, product):
    """Look up actual selling price for a Maayan chain + product.
    Falls back to B2B list price via pricing_engine if not found.
    """
    pricedb_cust = _MAAYAN_CHAIN_TO_PRICEDB.get(str(chain_raw).strip())
    if pricedb_cust and product in price_table:
        price = price_table[product].get(pricedb_cust)
        if price:
            return price
    return get_b2b_price_safe(product)


# ── Ma'ayan Parser ───────────────────────────────────────────────────────

def parse_mayyan_file(filepath, price_table=None):
    """Parse Ma'ayan detailed distribution report.

    Always reads from the detail sheet (דוח_הפצה_גלידות_טורבו__אל_פירוט).
    The file also contains a pivot/summary sheet (טבלת ציר) whose raw sum
    double-counts rows — we never use it.

    Sheet selection priority:
      1. Any sheet whose name contains 'פירוט'  (most specific — the detail sheet)
      2. Any sheet whose name contains 'דוח'    (secondary — also the detail sheet)
      3. Reject sheets whose name contains pivot/summary keywords (ציר, סיכום, summary)
      4. Last sheet as final fallback
    """
    import pandas as pd
    if price_table is None:
        price_table = _load_mayyan_price_table()
    wb_meta = load_workbook(filepath, read_only=True)
    sheet_names = wb_meta.sheetnames
    wb_meta.close()

    # Sheets to skip — pivot/summary tabs that aggregate rows
    SKIP_KEYWORDS = ('ציר', 'סיכום', 'summary', 'pivot', 'totals')

    # Priority 1: sheet name contains 'פירוט'
    detail_sheet = next(
        (s for s in sheet_names if 'פירוט' in s),
        None
    )
    # Priority 2: sheet name contains 'דוח' but is NOT a skip-sheet
    if not detail_sheet:
        detail_sheet = next(
            (s for s in sheet_names
             if 'דוח' in s and not any(kw in s.lower() for kw in SKIP_KEYWORDS)),
            None
        )
    # Priority 3: any non-pivot sheet
    if not detail_sheet:
        detail_sheet = next(
            (s for s in sheet_names
             if not any(kw in s.lower() for kw in SKIP_KEYWORDS)),
            None
        )
    # Final fallback: last sheet
    if not detail_sheet:
        detail_sheet = sheet_names[-1]

    import os
    print(f"  [Mayyan] {os.path.basename(filepath)} → sheet: '{detail_sheet}'")
    df = pd.read_excel(filepath, sheet_name=detail_sheet)

    month_col = next((c for c in df.columns if 'חודש' in str(c)), None)
    week_col = next((c for c in df.columns if 'שבועי' in str(c)), None)
    product_col = next((c for c in df.columns if 'פריט' in str(c)), None)
    units_col = next((c for c in df.columns if 'בודדים' in str(c)), None)
    chain_col = next((c for c in df.columns if 'רשת' in str(c)), None)
    type_col = next((c for c in df.columns if 'סוג' in str(c)), None)
    branch_col = next((c for c in df.columns if 'חשבון' in str(c) and 'שם' in str(c)), None)

    if not all([product_col, units_col]):
        return {}
    if not month_col and not week_col:
        return {}

    df['product'] = df[product_col].apply(lambda x: _validated_product(classify_product(x)))
    df = df[df['product'].notna()]

    if month_col:
        # Standard monthly format — map Hebrew month names to standard keys
        month_map = {}
        for m in df[month_col].unique():
            ms = str(m)
            if 'דצמבר' in ms or 'December' in ms:
                month_map[m] = 'December 2025'
            elif 'ינואר' in ms or 'January' in ms:
                month_map[m] = 'January 2026'
            elif 'פברואר' in ms or 'February' in ms:
                month_map[m] = 'February 2026'
            elif 'מרץ' in ms or 'March' in ms:
                month_map[m] = 'March 2026'
            else:
                month_map[m] = str(m)
        df['month_std'] = df[month_col].map(month_map)
    else:
        # Weekly format — no month column; infer month from filename or sheet names
        fname = str(filepath).lower()
        inferred_month = None
        month_keywords = {
            'dec': 'December 2025', 'דצמבר': 'December 2025',
            'jan': 'January 2026', 'ינואר': 'January 2026',
            'feb': 'February 2026', 'פברואר': 'February 2026',
            'mar': 'March 2026', 'מרץ': 'March 2026',
            'apr': 'April 2026', 'אפריל': 'April 2026',
        }
        for kw, month_val in month_keywords.items():
            if kw in fname:
                inferred_month = month_val
                break
        if not inferred_month:
            # Try sheet names
            for sn in sheet_names:
                for kw, month_val in month_keywords.items():
                    if kw in sn.lower():
                        inferred_month = month_val
                        break
                if inferred_month:
                    break
        if not inferred_month and week_col:
            # Try to infer month from week numbers in the data
            # Week numbers are ISO weeks in the data; map to months for 2025-2026 season
            week_to_month = {
                # Dec 2025: weeks ~49-52
                49: 'December 2025', 50: 'December 2025', 51: 'December 2025', 52: 'December 2025',
                # Jan 2026: weeks ~1-4
                1: 'January 2026', 2: 'January 2026', 3: 'January 2026', 4: 'January 2026',
                # Feb 2026: weeks ~5-8
                5: 'February 2026', 6: 'February 2026', 7: 'February 2026', 8: 'February 2026',
                # Mar 2026: weeks ~9-13
                9: 'March 2026', 10: 'March 2026', 11: 'March 2026', 12: 'March 2026', 13: 'March 2026',
                # Apr 2026: weeks ~14-17
                14: 'April 2026', 15: 'April 2026', 16: 'April 2026', 17: 'April 2026',
            }
            weeks_in_data = df[week_col].dropna().unique()
            for w in weeks_in_data:
                try:
                    w_int = int(w)
                    if w_int in week_to_month:
                        inferred_month = week_to_month[w_int]
                        break
                except (ValueError, TypeError):
                    pass
        if not inferred_month:
            inferred_month = 'Unknown'
        df['month_std'] = inferred_month
    results = {}

    for month in df['month_std'].unique():
        mdf = df[df['month_std'] == month]

        # Compute value per row using per-chain actual prices from price DB
        totals = {}
        if chain_col and price_table:
            for product in mdf['product'].unique():
                pdf = mdf[mdf['product'] == product]
                total_units = int(pdf[units_col].sum())
                total_value = 0.0
                for _, row in pdf.iterrows():
                    row_units = row[units_col] if row[units_col] else 0
                    chain_raw = row[chain_col] if chain_col else ''
                    unit_price = _mayyan_chain_price(price_table, chain_raw, product)
                    total_value += row_units * unit_price
                totals[product] = {
                    'units': total_units,
                    'value': round(total_value, 2),
                    'transactions': int(len(pdf))
                }
        else:
            for product in mdf['product'].unique():
                pdf = mdf[mdf['product'] == product]
                totals[product] = {
                    'units': int(pdf[units_col].sum()),
                    'value': 0,
                    'transactions': int(len(pdf))
                }

        by_chain = {}
        if chain_col:
            for _, row in mdf.groupby([chain_col, 'product']).agg(
                total_units=(units_col, 'sum')
            ).reset_index().iterrows():
                chain = str(row[chain_col])
                if chain not in by_chain:
                    by_chain[chain] = {}
                by_chain[chain][row['product']] = int(row['total_units'])

        by_type = {}
        if type_col:
            for _, row in mdf.groupby([type_col, 'product']).agg(
                total_units=(units_col, 'sum')
            ).reset_index().iterrows():
                ct = str(row[type_col])
                if ct not in by_type:
                    by_type[ct] = {}
                by_type[ct][row['product']] = int(row['total_units'])

        by_account = {}
        if branch_col:
            for _, row in mdf.iterrows():
                acct_raw = row.get(branch_col) if branch_col in row.index else None
                if not acct_raw:
                    continue
                acct = str(acct_raw).strip()
                chain_name = str(row[chain_col]).strip() if chain_col and chain_col in row.index else ''
                product = row.get('product')
                if not product:
                    continue
                row_units = int(row[units_col]) if row.get(units_col) else 0
                unit_price = _mayyan_chain_price(price_table, chain_name, product)
                key = (chain_name, acct)
                if key not in by_account:
                    by_account[key] = {}
                if product not in by_account[key]:
                    by_account[key][product] = {'units': 0, 'value': 0.0}
                by_account[key][product]['units'] += row_units
                by_account[key][product]['value'] = round(
                    by_account[key][product]['value'] + row_units * unit_price, 2
                )

        branches = set()
        if branch_col:
            for b in mdf[branch_col].dropna().unique():
                branches.add(str(b).strip())

        results[month] = {
            'totals': totals,
            'by_chain': by_chain,
            'by_account': by_account,
            'by_customer_type': by_type,
            'branches': branches,
        }

    return results


def parse_all_mayyan():
    folder = DATA_DIR / 'mayyan'
    if not folder.exists():
        return {}
    price_table = _load_mayyan_price_table()
    results = {}
    for f in sorted(folder.glob('*.xlsx')):
        if f.name.startswith('~'):
            continue
        data = parse_mayyan_file(f, price_table=price_table)
        for month, mdata in data.items():
            if month not in results:
                results[month] = mdata
            else:
                # Merge: accumulate totals and by_account across multiple files for the same month
                existing = results[month]
                # Merge totals
                for sku, vals in mdata.get('totals', {}).items():
                    if sku not in existing.setdefault('totals', {}):
                        existing['totals'][sku] = {'units': 0, 'value': 0.0}
                    existing['totals'][sku]['units'] += vals.get('units', 0)
                    existing['totals'][sku]['value'] = round(
                        existing['totals'][sku]['value'] + vals.get('value', 0.0), 2)
                # Merge by_account
                for key, products in mdata.get('by_account', {}).items():
                    if key not in existing.setdefault('by_account', {}):
                        existing['by_account'][key] = {}
                    for sku, vals in products.items():
                        if sku not in existing['by_account'][key]:
                            existing['by_account'][key][sku] = {'units': 0, 'value': 0.0}
                        existing['by_account'][key][sku]['units'] += vals.get('units', 0)
                        existing['by_account'][key][sku]['value'] = round(
                            existing['by_account'][key][sku]['value'] + vals.get('value', 0.0), 2)
                # Merge branches
                existing.setdefault('branches', set()).update(mdata.get('branches', set()))
    return results


# ── Production Parser ─────────────────────────────────────────────────

def get_production_data():
    """Returns known production data. Will be extended to parse files."""
    production = {
    }
    folder = DATA_DIR / 'production'
    if folder.exists():
        for f in sorted(folder.glob('*.xlsx')):
            pass  # TODO: parse production files when format is known
    return production


# ── Karfree Warehouse Inventory Parser ────────────────────────────────

def _classify_product_karfree(text):
    """Classify product from reversed Hebrew PDF text."""
    t = text.lower()
    # Exclude non-Raito products (דובאי = יאבוד reversed, באגסו = וסגאב reversed)
    if 'יאבוד' in t or 'וסגאב' in t:
        return None
    if 'וגנמ' in t or 'mango' in t:
        return 'mango'
    if 'דלוקוש' in t or 'chocolate' in t:
        return 'chocolate'
    if 'לינו' in t or 'vanilla' in t:
        return 'vanilla'
    if 'קוטסיפ' in t or 'וקטסיפ' in t or 'pistachio' in t:
        return 'pistachio'
    if 'תגדגמ' in t or 'magadat' in t:
        return 'magadat'
    if 'תגוע' in t or 'dream' in t or 'cake' in t:
        return 'dream_cake'
    return None


def parse_karfree_inventory():
    """Parse Karfree cold storage PDF inventory reports."""
    folder = DATA_DIR / 'karfree'
    if not folder.exists():
        return {}

    # Glob *.pdf plus non-pdf files that are actually PDFs (missing/wrong extension)
    pdf_files = list(folder.glob('*.pdf'))
    for f in folder.iterdir():
        if f.is_file() and f.suffix != '.pdf' and f not in pdf_files:
            try:
                with open(f, 'rb') as fh:
                    if fh.read(5) == b'%PDF-':
                        pdf_files.append(f)
            except Exception:
                pass
    pdf_files = sorted(pdf_files, key=lambda f: f.stat().st_mtime)
    if not pdf_files:
        return {}

    try:
        import pdfplumber
    except ImportError:
        print("  Warning: pdfplumber not installed, skipping inventory")
        return {}

    filepath = pdf_files[-1]
    results = {
        'report_date': None,
        'products': {},
        'total_units': 0,
        'total_pallets': 0,
    }

    with pdfplumber.open(filepath) as pdf:
        full_text = ''
        for page in pdf.pages:
            full_text += page.extract_text() + '\n'

    lines = full_text.split('\n')
    current_product = None

    for line in lines:
        if ':ךיראתל ןוכנ' in line:
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
            if date_match:
                results['report_date'] = date_match.group(1)

        if 'טירפ' in line and ':' in line:
            product = _classify_product_karfree(line)
            current_product = product  # Reset even if None (e.g. Dubai products)
            if product and product not in results['products']:
                results['products'][product] = {
                    'units': 0, 'pallets': 0, 'batches': []
                }

        if current_product and re.match(r'^\s*0\s+000017', line):
            parts = line.split()
            try:
                packages = None
                for i, p in enumerate(parts):
                    if p == '0.00' and i + 1 < len(parts):
                        packages = int(parts[i + 1])
                        break
                if packages:
                    # Vanilla (לינו) has both 6-pack and 10-pack SKUs:
                    # non-240 pallets are old 6-packs, 240 pallets are 10-packs
                    if current_product == 'vanilla':
                        factor = 10 if packages == 240 else 6
                    else:
                        factor = 10  # all other ice cream products are 10 units/carton
                    actual_units = packages * factor
                    dates = re.findall(r'\d{2}/\d{2}/\d{4}', line)
                    batch = {
                        'packages': packages,
                        'factor': factor,
                        'units': actual_units,
                        'expiry': dates[0] if len(dates) > 0 else None,
                        'production': dates[1] if len(dates) > 1 else None,
                        'entry': dates[2] if len(dates) > 2 else None,
                    }
                    results['products'][current_product]['batches'].append(batch)
            except (ValueError, IndexError):
                pass

        if 'טירפל' in line and 'כ"הס' in line:
            total_match = re.search(r'(\d[\d\s,]*\d)\s+(\d+)\s+:טירפל', line)
            if total_match and current_product:
                pallets_count = int(total_match.group(2))
                results['products'][current_product]['pallets'] = pallets_count

    for p, pdata in results['products'].items():
        pdata['units'] = sum(b['units'] for b in pdata['batches'])
        pdata['packages'] = sum(b['packages'] for b in pdata['batches'])
        results['total_units'] += pdata['units']
        results['total_pallets'] += pdata['pallets']

    return results


def get_warehouse_data():
    """Returns warehouse inventory data from Karfree reports."""
    return parse_karfree_inventory()


# ── Distributor Inventory Parser ──────────────────────────────────────

def parse_distributor_stock(filepath):
    """Parse a distributor stock Excel file (Icedream / Ma'ayan format)."""
    from pathlib import Path
    fp = Path(filepath)
    # Handle files without .xlsx extension
    if fp.suffix not in ('.xlsx', '.xlsm', '.xltx', '.xltm'):
        import shutil, tempfile
        tmp = Path(tempfile.mktemp(suffix='.xlsx'))
        shutil.copy2(fp, tmp)
        filepath = tmp
    wb = load_workbook(filepath)
    ws = wb[wb.sheetnames[0]]
    results = {'products': {}, 'total_units': 0, 'report_date': None}

    for row_idx in range(1, min(5, ws.max_row + 1)):
        for col_idx in range(1, ws.max_column + 1):
            val = ws.cell(row=row_idx, column=col_idx).value
            if val:
                date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', str(val))
                if date_match:
                    results['report_date'] = date_match.group(1)
                    break
        if results['report_date']:
            break

    name_col = None
    qty_col = None
    header_row = None
    for row_idx in range(1, min(10, ws.max_row + 1)):
        for col_idx in range(1, ws.max_column + 1):
            val = str(ws.cell(row=row_idx, column=col_idx).value or '')
            if 'שם פריט' in val or ('פריט' in val and 'מפתח' not in val and 'בר' not in val):
                name_col = col_idx
                header_row = row_idx
            if 'מלאי' in val or 'כמות' in val or 'יתרת' in val:
                qty_col = col_idx
        if name_col and qty_col:
            break

    if not name_col or not qty_col:
        wb.close()
        return results

    is_units_format = False
    start_row = (header_row + 1) if header_row else 5
    for test_row in range(start_row, min(start_row + 3, ws.max_row + 1)):
        test_name = str(ws.cell(row=test_row, column=name_col).value or '')
        if re.search(r'\d+/\d+', test_name) and not re.search(r'\*\s*\d+\s*יח', test_name):
            is_units_format = True
            break

    for row_idx in range(start_row, ws.max_row + 1):
        item_name = ws.cell(row=row_idx, column=name_col).value
        qty_val = ws.cell(row=row_idx, column=qty_col).value

        if not item_name or qty_val is None:
            continue
        item_name = str(item_name)

        if 'סה"כ' in item_name:
            continue

        product = _validated_product(classify_product(item_name))
        if not product:
            continue

        qty = float(qty_val)
        if is_units_format:
            units = max(0, int(qty))
            factor = 1
            cartons = qty
        else:
            factor = extract_units_per_carton(item_name)
            cartons = qty
            units = math.ceil(cartons * factor)

        if units <= 0:
            continue

        if product not in results['products']:
            results['products'][product] = {'units': 0, 'cartons': 0, 'factor': factor}
        results['products'][product]['units'] += units
        results['products'][product]['cartons'] += cartons
        results['total_units'] += units

    wb.close()
    return results


def get_distributor_inventory():
    """Parse distributor stock files from icedream and mayyan folders."""
    dist_inv = {}

    # Search in multiple possible locations for stock files
    ice_folders = [DATA_DIR / 'icedreams', OUTPUT_DIR / 'icedream']
    for icedream_folder in ice_folders:
        if not icedream_folder.exists():
            continue
        for f in sorted(icedream_folder.glob('*stock*'), key=lambda p: p.stat().st_mtime, reverse=True):
            if f.name.startswith('~'):
                continue
            try:
                data = parse_distributor_stock(f)
                if data.get('products'):
                    dist_inv['icedream'] = data
                    break
            except Exception:
                pass
        if 'icedream' in dist_inv:
            break

    may_folders = [DATA_DIR / 'mayyan', OUTPUT_DIR / 'Maayan']
    for mayyan_folder in may_folders:
        if not mayyan_folder.exists():
            continue
        for f in sorted(mayyan_folder.glob('*stock*'), key=lambda p: p.stat().st_mtime, reverse=True):
            if f.name.startswith('~'):
                continue
            try:
                data = parse_distributor_stock(f)
                if data.get('products'):
                    dist_inv['mayyan'] = data
                    break
            except Exception:
                pass
        if 'mayyan' in dist_inv:
            break

    return dist_inv


# ── Biscotti Parser ────────────────────────────────────────────────────

# Biscotti Dream Cake price — sourced from pricing_engine (SSOT)
BISCOTTI_PRICE_DREAM_CAKE = get_b2b_price_safe('dream_cake_2')

def _normalize_biscotti_branch(name: str) -> str:
    """Roll up Biscotti branch legal names to their parent customer name.

    Wolt Market branches (וולט מרקט-X) → וולט מרקט
    Naomi's Farm branches (חוות נעמי*) → חוות נעמי
    חן כרמלה למסחר בע"מ → כרמלה  (same physical customer as Icedream's כרמלה)
    All others kept as-is.
    """
    if name.startswith('וולט מרקט'):
        return 'וולט מרקט'
    if name.startswith('חוות נעמי'):
        return 'חוות נעמי'
    if 'כרמלה' in name:
        return 'כרמלה'
    return name


def _parse_biscotti_file(filepath):
    """Parse Biscotti weekly sales report.

    Supports two formats:
      Format A (daniel_amit_weekly_biscotti.xlsx) — Multi-sheet:
        'סיכום כללי': row 2=headers (col 0=סניף, last=סה"כ), data rows 3..N-2
        'שבוע N': per-week daily columns, col 0=branch, last=total
      Format B (week13.xlsx and future) — Single sheet, 3 columns:
        Row 0: headers (מספר לקוח | שם לקוח | כמות)
        Data rows 1..N-2, last row = grand total (סה"כ)
        Col 0 = customer number (ignored), col 1 = customer name, col 2 = quantity

    Returns {month_key: {'totals': {product: {'units', 'value'}},
                         'by_customer': {branch: {product: {'units', 'value'}}}}}
    All data maps to March 2026.
    """
    import os
    xl = pd.ExcelFile(filepath)
    print(f"  [Biscotti] {os.path.basename(filepath)} → sheets: {xl.sheet_names}")

    SUMMARY_KEYWORD = 'סיכום'
    WEEK_KEYWORD = 'שבוע'

    summary_sheet = next((s for s in xl.sheet_names if SUMMARY_KEYWORD in s), None)
    week_sheets = [s for s in xl.sheet_names if WEEK_KEYWORD in s]

    branch_totals = {}  # {branch_name: units}

    if summary_sheet:
        df = pd.read_excel(filepath, sheet_name=summary_sheet, header=None)

        # Detect Format B: 3 columns, header row has 'שם לקוח' or 'כמות' in col 1/2
        is_format_b = (df.shape[1] == 3 and
                       not week_sheets and
                       str(df.iloc[0, 1]).strip() in ('שם לקוח', 'כמות') or
                       (df.shape[1] == 3 and not week_sheets and
                        str(df.iloc[0, 0]).strip() == 'מספר לקוח'))

        if is_format_b:
            # Format B: col 0=customer_num, col 1=name, col 2=quantity
            # Header at row 0, data rows 1..N-2, last row = grand total
            for i in range(1, len(df) - 1):
                name = str(df.iloc[i, 1]).strip()
                qty  = df.iloc[i, 2]
                if name and name != 'nan' and qty and str(qty) != 'nan':
                    norm = _normalize_biscotti_branch(name)
                    branch_totals[norm] = branch_totals.get(norm, 0) + int(qty)
        else:
            # Format A: row 2=headers, col 0=branch, last col=total, data rows 3..N-2
            total_col = df.shape[1] - 1
            for i in range(3, len(df) - 1):
                branch = str(df.iloc[i, 0]).strip()
                total = df.iloc[i, total_col]
                if branch and branch != 'nan' and total and str(total) != 'nan':
                    branch_totals[branch] = branch_totals.get(branch, 0) + int(total)

    elif week_sheets:
        # Aggregate across all week sheets
        for sheet in week_sheets:
            df = pd.read_excel(filepath, sheet_name=sheet, header=None)
            total_col = df.shape[1] - 1
            for i in range(2, len(df) - 1):
                branch = str(df.iloc[i, 0]).strip()
                total = df.iloc[i, total_col]
                if branch and branch != 'nan' and total and str(total) != 'nan':
                    branch_totals[branch] = branch_totals.get(branch, 0) + int(total)

    if not branch_totals:
        return {}

    # All data maps to March 2026
    month_key = 'March 2026'
    total_units = sum(branch_totals.values())
    total_value = round(total_units * BISCOTTI_PRICE_DREAM_CAKE, 2)

    by_customer = {}
    for branch, units in branch_totals.items():
        by_customer[branch] = {
            'dream_cake_2': {
                'units': units,
                'value': round(units * BISCOTTI_PRICE_DREAM_CAKE, 2),
            }
        }

    return {
        month_key: {
            'totals': {
                'dream_cake_2': {
                    'units': total_units,
                    'value': total_value,
                }
            },
            'by_customer': by_customer,
        }
    }


def parse_all_biscotti():
    """Parse all Biscotti distributor sales reports from data/biscotti/."""
    folder = DATA_DIR / 'biscotti'
    if not folder.exists():
        return {}

    results = {}
    for f in sorted(folder.glob('*.xlsx')):
        if f.name.startswith('~') or f.name.startswith('.'):
            continue
        # Skip item-setup / admin files — only parse weekly sales reports
        # Identified by presence of 'שבוע' or 'סיכום' sheets
        try:
            xl = pd.ExcelFile(f)
            sheets = xl.sheet_names
            is_sales_report = any(
                'שבוע' in s or 'סיכום' in s for s in sheets
            )
            if not is_sales_report:
                continue
        except Exception:
            continue

        try:
            data = _parse_biscotti_file(f)
            for month, mdata in data.items():
                if month not in results:
                    results[month] = mdata
                else:
                    # Merge: add units/value per branch
                    for branch, prods in mdata['by_customer'].items():
                        if branch not in results[month]['by_customer']:
                            results[month]['by_customer'][branch] = prods
                        else:
                            for p, pdata in prods.items():
                                existing = results[month]['by_customer'][branch].get(p, {})
                                results[month]['by_customer'][branch][p] = {
                                    'units': existing.get('units', 0) + pdata['units'],
                                    'value': existing.get('value', 0) + pdata['value'],
                                }
                    # Recalculate totals
                    for p in results[month]['totals']:
                        results[month]['totals'][p]['units'] = sum(
                            results[month]['by_customer'][b].get(p, {}).get('units', 0)
                            for b in results[month]['by_customer']
                        )
                        results[month]['totals'][p]['value'] = round(
                            results[month]['totals'][p]['units'] * BISCOTTI_PRICE_DREAM_CAKE, 2
                        )
        except Exception as e:
            print(f"  [Biscotti] Error parsing {f.name}: {e}")

    return results


# ── Data Consolidation ──────────────────────────────────────────────────

def consolidate_data():
    """Merge all data sources into a unified dataset."""
    print("Processing Icedreams reports...")
    icedreams = parse_all_icedreams()
    print(f"  Found {len(icedreams)} months")

    print("Processing Ma'ayan reports...")
    mayyan = parse_all_mayyan()
    print(f"  Found {len(mayyan)} months")

    print("Processing Biscotti reports...")
    biscotti = parse_all_biscotti()
    print(f"  Found {len(biscotti)} months")

    production = get_production_data()
    warehouse = get_warehouse_data()
    if warehouse:
        print(f"Processing Karfree inventory...")
        print(f"  Report date: {warehouse.get('report_date', 'N/A')}, Total: {warehouse.get('total_units', 0):,} units")

    dist_inv = get_distributor_inventory()
    for dist_name, dist_data in dist_inv.items():
        print(f"Processing {dist_name} stock...")
        print(f"  Report date: {dist_data.get('report_date', 'N/A')}, Total: {dist_data.get('total_units', 0):,} units")

    all_months = sorted(
        [m for m in set(list(icedreams.keys()) + list(mayyan.keys()) + list(biscotti.keys()))
         if m in MONTH_ORDER],
        key=lambda x: MONTH_ORDER.get(x, 99)
    )
    products = ['chocolate', 'vanilla', 'mango', 'magadat', 'dream_cake', 'dream_cake_2', 'pistachio']

    consolidated = {
        'months': all_months,
        'products': products,
        'monthly_data': {},
        'production': production,
        'warehouse': warehouse,
        'dist_inv': dist_inv,
    }

    for month in all_months:
        month_data = {
            'icedreams': icedreams.get(month, {}).get('totals', {}),
            'mayyan': mayyan.get(month, {}).get('totals', {}),
            'icedreams_customers': icedreams.get(month, {}).get('by_customer', {}),
            'mayyan_chains': mayyan.get(month, {}).get('by_chain', {}),
            'mayyan_accounts': mayyan.get(month, {}).get('by_account', {}),
            'mayyan_branches': mayyan.get(month, {}).get('branches', set()),
            'mayyan_types': mayyan.get(month, {}).get('by_customer_type', {}),
            'biscotti': biscotti.get(month, {}).get('totals', {}),
            'biscotti_customers': biscotti.get(month, {}).get('by_customer', {}),
            'combined': {},
        }

        for p in products:
            ice_units = month_data['icedreams'].get(p, {}).get('units', 0)
            may_units = month_data['mayyan'].get(p, {}).get('units', 0)
            bisc_units = month_data['biscotti'].get(p, {}).get('units', 0)
            ice_value = month_data['icedreams'].get(p, {}).get('value', 0)
            # Use actual per-chain Maayan revenue when available; fall back to estimate
            _may_actual = month_data['mayyan'].get(p, {}).get('value', 0)
            may_value = _may_actual if _may_actual > 0 else round(may_units * get_b2b_price_safe(p), 2)
            bisc_value = month_data['biscotti'].get(p, {}).get('value', 0)
            total_value = round(ice_value + may_value + bisc_value, 2)
            prod_cost_per_unit = get_production_cost(p)
            total_units = ice_units + may_units + bisc_units
            total_prod_cost = round(total_units * prod_cost_per_unit, 2)
            gross_margin = round(total_value - total_prod_cost, 2) if p != 'magadat' else 0

            month_data['combined'][p] = {
                'units': total_units,
                'icedreams_units': ice_units,
                'mayyan_units': may_units,
                'biscotti_units': bisc_units,
                'icedreams_value': ice_value,
                'mayyan_value': may_value,
                'biscotti_value': bisc_value,
                'total_value': total_value,
                'production_cost': total_prod_cost,
                'gross_margin': gross_margin,
            }

        filtered_custs = {}
        for cust, pdata in month_data.get('icedreams_customers', {}).items():
            total_u = sum(v.get('units', 0) for v in pdata.values())
            # Allow through negative-unit customers (returns/credit notes) so CC can
            # account for them — previously total_u > 0 silently dropped returns.
            if total_u != 0:
                for p, vals in pdata.items():
                    vals['value'] = round(vals.get('value', 0), 2)
                filtered_custs[cust] = pdata
        month_data['icedreams_customers'] = filtered_custs

        mayyan_chains_revenue = {}
        for chain, pdata in month_data.get('mayyan_chains', {}).items():
            mayyan_chains_revenue[chain] = {}
            for p, units in pdata.items():
                mayyan_chains_revenue[chain][p] = {
                    'units': units,
                    'value': round(units * get_b2b_price_safe(p), 2),
                }
        month_data['mayyan_chains_revenue'] = mayyan_chains_revenue

        # mayyan_accounts now carries {product: {units, value}} — pass through directly
        # (pricing was applied at parse time using _mayyan_chain_price per row)
        month_data['mayyan_accounts_revenue'] = month_data.get('mayyan_accounts', {})

        consolidated['monthly_data'][month] = month_data

    return consolidated
