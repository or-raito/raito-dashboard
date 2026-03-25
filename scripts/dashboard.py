#!/usr/bin/env python3
"""
Raito Business Overview — HTML Dashboard Generator
Generates a fully static HTML dashboard with month + brand filters.

TABLE ALIGNMENT CONVENTION (Decision #90):
  - All numeric columns use text-align:center (never right).
  - Tables with class="tbl" are styled via CSS in unified_dashboard.py.
    • Default: first 2 columns left-aligned, rest center.
    • Product-only tables (1 text column): use class="tbl tbl-prod-rank"
      so column 2+ override to center.
  - Inline-styled tables (no .tbl class): set text-align:center on
    every numeric <th> and <td> explicitly.
  - When adding a new table, follow this convention.
"""

from datetime import datetime
from config import (
    fmt as _fmt, fc as _fc, compute_kpis as _compute_kpis, count_pos as _count_pos,
    PRODUCT_NAMES, PRODUCT_NAMES, PRODUCT_STATUS, PRODUCT_COLORS,
    FLAVOR_COLORS, PRODUCTS_ORDER,
    MONTH_NAMES_HEB, MONTH_ORDER, CHART_MONTHS,
    BRAND_FILTERS, TARGET_MONTHS_STOCK, PALLET_DIVISOR,
    CREATORS, DISTRIBUTOR_NAMES,
    OUTPUT_DIR, pallets,
)
from pricing_engine import (
    get_b2b_price_safe, get_production_cost, all_b2b_prices, PRODUCTION_COST,
)

# Backward-compatible alias — BO tab still uses dict lookups in a few places
SELLING_PRICE_B2B = all_b2b_prices()



def _bar_html(items, max_val, color='#3b82f6', height=22):
    """Generate CSS bar chart rows."""
    rows = []
    for label, value in items:
        pct = (value / max_val * 100) if max_val > 0 else 0
        rows.append(
            f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0">'
            f'<div style="width:200px;min-width:200px;text-align:right;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{label}</div>'
            f'<div style="flex:1;background:#f0f0f0;border-radius:4px;height:{height}px">'
            f'<div style="width:{pct:.1f}%;background:{color};height:100%;border-radius:4px;min-width:2px"></div>'
            f'</div>'
            f'<div style="min-width:60px;text-align:left;font-size:12px;font-weight:600">{_fmt(value)}</div>'
            f'</div>'
        )
    return '\n'.join(rows)




def _smooth_path(points):
    """Generate smooth cubic bezier SVG path through points."""
    if len(points) < 2:
        return ''
    d = f'M {points[0][0]:.1f},{points[0][1]:.1f}'
    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        # Control point offset: ~30% of horizontal distance
        cpx = (x1 - x0) * 0.3
        d += f' C {x0 + cpx:.1f},{y0:.1f} {x1 - cpx:.1f},{y1:.1f} {x1:.1f},{y1:.1f}'
    return d


def _build_svg_timeline_chart(data, active_products, value_key, title, line_color, fill_id, label_color, fmt_func, show_mom=False, month_list=None):
    """Build SVG line chart over timeline with smooth curves and summary header.
    If month_list is provided, only those months are plotted (for year-filtered views).
    Otherwise falls back to CHART_MONTHS (all months).
    """
    # Use provided month_list or fall back to all chart months
    chart_months = month_list if month_list else CHART_MONTHS

    # Build data for the relevant months
    timeline = []
    for month in chart_months:
        md = data['monthly_data'].get(month, {})
        if md:
            val = sum(md.get('combined', {}).get(p, {}).get(value_key, 0) for p in active_products)
            timeline.append((month, val if val > 0 else None))
        else:
            timeline.append((month, None))

    # Summary: total + trend
    actual_vals = [v for _, v in timeline if v is not None]
    total_val = sum(actual_vals) if actual_vals else 0
    trend_pct = None
    if len(actual_vals) >= 2:
        trend_pct = round((actual_vals[-1] - actual_vals[-2]) / actual_vals[-2] * 100) if actual_vals[-2] > 0 else 0

    # Chart dimensions — compact
    w, h_chart = 560, 110
    mx_l, mx_r, my_t, my_b = 52, 8, 14, 6
    pw = w - mx_l - mx_r
    ph = h_chart - my_t - my_b
    h_total = h_chart + (30 if show_mom else 20)  # extra room for MoM line if needed
    n = len(chart_months)
    step = pw / (n - 1) if n > 1 else pw

    x_positions = [mx_l + i * step for i in range(n)]

    max_val = max(actual_vals) if actual_vals else 1
    if max_val == 0:
        max_val = 1

    # Abbreviated format for y-axis tick labels (keeps left margin clean)
    def _abbrev(v):
        sample = fmt_func(v)
        prefix = '₪' if sample.startswith('₪') else ''
        if v >= 1_000_000:
            return f'{prefix}{v / 1_000_000:.1f}M'
        elif v >= 10_000:
            return f'{prefix}{int(round(v / 1_000))}K'
        else:
            return sample

    # Data points
    data_points = []
    for i, (month, val) in enumerate(timeline):
        if val is not None:
            x = x_positions[i]
            y = my_t + ph - (val / max_val * ph * 0.88)
            data_points.append((x, y, month, val))

    svg = [f'<svg viewBox="0 0 {w} {h_total}" xmlns="http://www.w3.org/2000/svg" style="width:100%;direction:ltr">']

    # No grid lines — clean chart area
    # Only Y-axis labels for reference (no grid lines)
    for i in range(5):
        gy = my_t + ph * i / 4
        gval = max_val * (4 - i) / 4
        svg.append(f'<text x="{mx_l-4}" y="{gy+3:.1f}" text-anchor="end" font-size="6" fill="#c0c0c0" font-weight="400">{_abbrev(gval)}</text>')

    # Smooth curve + gradient area fill
    if len(data_points) >= 2:
        pts = [(x, y) for x, y, _, _ in data_points]
        curve_d = _smooth_path(pts)

        # Area: close path to bottom
        area_d = curve_d + f' L {pts[-1][0]:.1f},{my_t+ph:.1f} L {pts[0][0]:.1f},{my_t+ph:.1f} Z'
        svg.append(f'<defs><linearGradient id="{fill_id}" x1="0" y1="0" x2="0" y2="1">'
                   f'<stop offset="0%" stop-color="{line_color}" stop-opacity="0.22"/>'
                   f'<stop offset="100%" stop-color="{line_color}" stop-opacity="0.02"/>'
                   f'</linearGradient></defs>')
        svg.append(f'<path d="{area_d}" fill="url(#{fill_id})"/>')

        # Smooth line
        svg.append(f'<path d="{curve_d}" fill="none" stroke="{line_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')

    # Month labels on X-axis — clamp anchors at edges so text stays inside SVG
    label_y = h_chart + 12
    mom_y = h_chart + 22  # MoM line sits just below month label
    for i, month in enumerate(chart_months):
        x = x_positions[i]
        mh = MONTH_NAMES_HEB.get(month, month)
        has_data = timeline[i][1] is not None
        fill = '#999' if has_data else '#ccc'
        if i == 0:
            anchor, lx = 'start', max(mx_l, x)
        elif i == n - 1:
            anchor, lx = 'end', min(w - 2, x)
        else:
            anchor, lx = 'middle', x
        svg.append(f'<text x="{lx:.1f}" y="{label_y:.1f}" text-anchor="{anchor}" font-size="8" font-weight="400" fill="{fill}">{mh}</text>')
        # MoM % change label (revenue chart only)
        if show_mom and has_data and i > 0:
            prev_val = next((timeline[j][1] for j in range(i - 1, -1, -1) if timeline[j][1] is not None), None)
            cur_val = timeline[i][1]
            if prev_val and prev_val > 0:
                mom_pct = round((cur_val - prev_val) / prev_val * 100)
                mom_sign = '+' if mom_pct >= 0 else ''
                mom_color = '#10b981' if mom_pct >= 0 else '#ef4444'
                mom_anchor = anchor  # align MoM % same as its month label
                svg.append(f'<text x="{lx:.1f}" y="{mom_y:.1f}" text-anchor="{mom_anchor}" font-size="6.5" font-weight="600" fill="{mom_color}">{mom_sign}{mom_pct}%</text>')

    # Data point dots + value labels (clamped so pills stay inside SVG)
    for x, y, month, val in data_points:
        # White halo behind dot
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#fff" opacity="0.9"/>')
        # Colored dot
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{line_color}" stroke="#fff" stroke-width="1"/>')
        # Value label above dot with pill background — clamp center so pill doesn't bleed outside SVG
        lbl = fmt_func(val)
        lbl_w = len(lbl) * 4.8 + 8
        ly = y - 10
        lbl_x = max(lbl_w / 2 + 2, min(w - lbl_w / 2 - 2, x))
        svg.append(f'<rect x="{lbl_x - lbl_w/2:.1f}" y="{ly - 6:.1f}" width="{lbl_w:.1f}" height="11" rx="5" fill="#fff" opacity="0.85"/>')
        svg.append(f'<text x="{lbl_x:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="7" font-weight="600" fill="{label_color}">{lbl}</text>')

    svg.append('</svg>')

    # Build summary header HTML (big number above chart, no trend badge)
    header_html = (
        f'<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:2px">'
        f'<span style="font-size:20px;font-weight:800;letter-spacing:-0.5px;color:var(--text)">{fmt_func(total_val)}</span>'
        f'</div>'
        f'<div style="font-size:10px;color:var(--text-muted);margin-bottom:8px">total</div>'
    )

    return f'<div class="card full"><h3>{title}</h3>{header_html}' + '\n'.join(svg) + '</div>'


def _build_svg_revenue_chart(data, month_list, active_products):
    return _build_svg_timeline_chart(data, active_products, 'total_value',
                                     'Monthly Revenue (₪)', '#10b981', 'ag', '#065f46', _fc, show_mom=True,
                                     month_list=month_list)


def _build_svg_units_chart(data, month_list, active_products):
    return _build_svg_timeline_chart(data, active_products, 'units',
                                     'Monthly Sales (units)', '#5D5FEF', 'ag2', '#3b3d99', _fmt, show_mom=True,
                                     month_list=month_list)


def _build_inventory_section(data, active_products=None):
    """Build unified inventory section: Warehouse (Karfree) + Distributors."""
    wh = data.get('warehouse', {})
    dist_inv = data.get('dist_inv', {})

    has_warehouse = wh and wh.get('products')
    has_distributors = bool(dist_inv)

    if not has_warehouse and not has_distributors:
        return ''

    all_prods = ['chocolate', 'vanilla', 'mango', 'pistachio', 'magadat', 'dream_cake']
    prod_order = [p for p in all_prods if p in active_products] if active_products else all_prods
    wh_products = wh.get('products', {}) if has_warehouse else {}

    # ── Karfree warehouse table with production planning columns ──
    karfree_html = ''
    if has_warehouse:
        report_date = wh.get('report_date', 'N/A')
        # Recompute totals for filtered products
        total_units = sum(wh_products.get(p, {}).get('units', 0) for p in prod_order)
        total_pallets = sum(wh_products.get(p, {}).get('pallets', 0) for p in prod_order)

        months = data.get('months', [])
        num_months = len(months) if months else 1

        rows = ''
        for p in prod_order:
            pd = wh_products.get(p)
            if not pd:
                continue
            name = PRODUCT_NAMES.get(p, p)
            units = pd.get('units', 0)
            plt = pd.get('pallets', 0)
            pct = round(units / total_units * 100) if total_units > 0 else 0

            batches = pd.get('batches', [])
            expiry_dates = [b['expiry'] for b in batches if b.get('expiry')]
            earliest_exp = min(expiry_dates) if expiry_dates else '---'
            latest_exp = max(expiry_dates) if expiry_dates else '---'

            # Production planning columns
            p_total = sum(
                data['monthly_data'].get(m, {}).get('combined', {}).get(p, {}).get('units', 0)
                for m in months)
            avg_monthly = round(p_total / num_months) if num_months > 0 else 0
            last_md = data['monthly_data'].get(months[-1], {}) if months else {}
            last_month_u = last_md.get('combined', {}).get(p, {}).get('units', 0)

            # Coverage calc based on Karfree stock only
            if avg_monthly > 0:
                months_stock = round(units / avg_monthly, 1)
            else:
                months_stock = 99 if units > 0 else 0

            if months_stock >= TARGET_MONTHS_STOCK * 1.5:
                cov_color = '#10b981'; cov_label = 'OK'
            elif months_stock >= TARGET_MONTHS_STOCK * 0.5:
                cov_color = '#f59e0b'; cov_label = 'Low'
            else:
                cov_color = '#ef4444'; cov_label = 'Critical'

            target_units = avg_monthly * TARGET_MONTHS_STOCK
            suggested = max(0, target_units - units)
            bar_pct = min(months_stock / 3 * 100, 100)

            sug_pallets = '-' if p == 'dream_cake' else (str(round(suggested / PALLET_DIVISOR, 1)) if suggested > 0 else '✓')

            rows += (f'<tr>'
                     f'<td><b>{name}</b></td>'
                     f'<td style="text-align:center">{_fmt(units)}</td>'
                     f'<td style="text-align:center">{plt}</td>'
                     f'<td style="text-align:center">{pct}%</td>'
                     f'<td style="text-align:center;font-size:11px">{earliest_exp}</td>'
                     f'<td style="text-align:center;font-size:11px">{latest_exp}</td>'
                     f'<td style="text-align:center">{_fmt(avg_monthly)}</td>'
                     f'<td style="text-align:center">{_fmt(last_month_u)}</td>'
                     f'<td style="text-align:center">'
                     f'<div style="display:flex;align-items:center;gap:4px;justify-content:center">'
                     f'<div style="width:60px;background:#f0f0f0;border-radius:3px;height:14px">'
                     f'<div style="width:{bar_pct:.0f}%;background:{cov_color};height:100%;border-radius:3px"></div></div>'
                     f'<span style="font-weight:700;color:{cov_color}">{months_stock}</span></div></td>'
                     f'<td style="text-align:center;font-weight:700;color:{cov_color}">{cov_label}</td>'
                     f'<td style="text-align:center;font-weight:700">{_fmt(suggested) if suggested > 0 else "✓"}</td>'
                     f'<td style="text-align:center;color:#888;font-size:12px">{sug_pallets}</td>'
                     f'</tr>')

        rows += (f'<tr style="font-weight:700;border-top:2px solid #e2e8f0">'
                 f'<td>Total</td>'
                 f'<td style="text-align:center">{_fmt(total_units)}</td>'
                 f'<td style="text-align:center">{round(total_pallets, 1) if isinstance(total_pallets, float) else total_pallets}</td>'
                 f'<td style="text-align:center">100%</td>'
                 f'<td></td><td></td>'
                 f'<td></td><td></td><td></td><td></td><td></td><td></td></tr>')

        bars = ''
        colors = {'chocolate': '#8B4513', 'vanilla': '#F5DEB3', 'mango': '#FF8C00',
                  'pistachio': '#93C572', 'dream_cake': '#DB7093'}
        for p in prod_order:
            pd = wh_products.get(p)
            if not pd:
                continue
            units = pd.get('units', 0)
            pct = round(units / total_units * 100) if total_units > 0 else 0
            color = colors.get(p, '#6366f1')
            name = PRODUCT_NAMES.get(p, p)
            bars += (f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0">'
                     f'<div style="width:140px;min-width:140px;text-align:right;font-size:12px;white-space:nowrap">{name}</div>'
                     f'<div style="flex:1;background:#f0f0f0;border-radius:4px;height:22px">'
                     f'<div style="width:{pct}%;background:{color};height:100%;border-radius:4px;min-width:2px"></div></div>'
                     f'<div style="min-width:90px;font-size:12px;font-weight:600">{_fmt(units)} ({pct}%)</div></div>')

        karfree_html = (f'<div class="card full" style="margin-bottom:14px">'
                   f'<h3>Transfer Warehouse Inventory (Karfree) — as of {report_date}</h3>'
                   f'{bars}'
                   f'<table class="tbl tbl-prod-rank" style="margin-top:12px"><thead><tr>'
                   f'<th>Product</th><th>Units in Stock</th><th>Pallets</th>'
                   f'<th>Share</th><th>Earliest Expiry</th><th>Latest Expiry</th>'
                   f'<th>Avg Sales/Mo</th><th>Last Month</th>'
                   f'<th>Months of Stock</th><th>Status</th>'
                   f'<th>Suggested Production</th><th style="color:#888;font-size:11px">Pallets</th>'
                   f'</tr></thead><tbody>{rows}</tbody></table></div>')

    # ── Distributor inventory tables ──
    dist_html = ''
    if has_distributors:
        for dist_key, dist_label in [('icedream', 'Icedream'), ('mayyan', "Ma'ayan"), ('biscotti', 'Biscotti')]:
            ddata = dist_inv.get(dist_key)
            if not ddata or not ddata.get('products'):
                continue
            d_date = ddata.get('report_date', 'N/A')
            d_prods = ddata['products']
            # Recompute total for filtered products
            d_total = sum(d_prods.get(p, {}).get('units', 0) for p in prod_order)
            if d_total == 0:
                continue

            d_rows = ''
            d_pallets_total = 0
            for p in prod_order:
                pd = d_prods.get(p)
                if not pd:
                    continue
                name = PRODUCT_NAMES.get(p, p)
                units = pd.get('units', 0)
                pct = round(units / d_total * 100) if d_total > 0 else 0
                plt_str = '-' if p == 'dream_cake' else str(round(units / 2400, 1))
                if p != 'dream_cake':
                    d_pallets_total += round(units / 2400, 1)
                d_rows += (f'<tr>'
                           f'<td><b>{name}</b></td>'
                           f'<td style="text-align:center">{_fmt(units)}</td>'
                           f'<td style="text-align:center;color:#888;font-size:12px">{plt_str}</td>'
                           f'<td style="text-align:center">{pct}%</td>'
                           f'</tr>')
            d_rows += (f'<tr style="font-weight:700;border-top:2px solid #e2e8f0">'
                       f'<td>Total</td>'
                       f'<td style="text-align:center">{_fmt(d_total)}</td>'
                       f'<td style="text-align:center;color:#888;font-size:12px">{round(d_pallets_total, 1)}</td>'
                       f'<td style="text-align:center">100%</td></tr>')

            dist_html += (f'<div class="card half" style="margin-bottom:14px">'
                          f'<h3>Distributor Inventory ({dist_label}) — as of {d_date}</h3>'
                          f'<table class="tbl tbl-prod-rank"><thead><tr>'
                          f'<th>Product</th><th>Units</th><th style="color:#888;font-size:11px">Pallets</th><th>Share</th>'
                          f'</tr></thead><tbody>{d_rows}</tbody></table></div>')

    # ── Unified total stock summary with pallets ──
    summary_html = ''
    if has_warehouse or has_distributors:
        def _pallets_str(units, product):
            """Ice cream pallets = floor(units/2400). Dream cake = '-'."""
            if product == 'dream_cake':
                return '-'
            return str(round(units / 2400, 1)) if units > 0 else '-'

        s_rows = ''
        grand_total = 0
        grand_pallets = 0
        for p in prod_order:
            wh_u = wh_products.get(p, {}).get('units', 0)
            ice_u = dist_inv.get('icedream', {}).get('products', {}).get(p, {}).get('units', 0)
            may_u = dist_inv.get('mayyan', {}).get('products', {}).get(p, {}).get('units', 0)
            bisc_u = dist_inv.get('biscotti', {}).get('products', {}).get(p, {}).get('units', 0)
            total_u = wh_u + ice_u + may_u + bisc_u
            if total_u == 0:
                continue
            name = PRODUCT_NAMES.get(p, p)
            color = FLAVOR_COLORS.get(p, '#666')
            dot = f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{color};margin-right:6px"></span>'

            wh_p = _pallets_str(wh_u, p)
            ice_p = _pallets_str(ice_u, p)
            may_p = _pallets_str(may_u, p)
            bisc_p = _pallets_str(bisc_u, p)
            total_p = _pallets_str(total_u, p)
            if p != 'dream_cake':
                grand_pallets += round(total_u / 2400, 1)

            s_rows += (f'<tr>'
                       f'<td>{dot}<b>{name}</b></td>'
                       f'<td style="text-align:center">{_fmt(wh_u) if wh_u else "-"}</td>'
                       f'<td style="text-align:center;color:#888;font-size:12px">{wh_p}</td>'
                       f'<td style="text-align:center">{_fmt(ice_u) if ice_u else "-"}</td>'
                       f'<td style="text-align:center;color:#888;font-size:12px">{ice_p}</td>'
                       f'<td style="text-align:center">{_fmt(may_u) if may_u else "-"}</td>'
                       f'<td style="text-align:center;color:#888;font-size:12px">{may_p}</td>'
                       f'<td style="text-align:center">{_fmt(bisc_u) if bisc_u else "-"}</td>'
                       f'<td style="text-align:center;color:#888;font-size:12px">{bisc_p}</td>'
                       f'<td style="text-align:center;font-weight:700">{_fmt(total_u)}</td>'
                       f'<td style="text-align:center;font-weight:700;color:#555">{total_p}</td>'
                       f'</tr>')
            grand_total += total_u

        # Recompute totals for filtered products
        wh_total = sum(wh_products.get(p, {}).get('units', 0) for p in prod_order) if has_warehouse else 0
        ice_total = sum(dist_inv.get('icedream', {}).get('products', {}).get(p, {}).get('units', 0) for p in prod_order)
        may_total = sum(dist_inv.get('mayyan', {}).get('products', {}).get(p, {}).get('units', 0) for p in prod_order)
        bisc_total = sum(dist_inv.get('biscotti', {}).get('products', {}).get(p, {}).get('units', 0) for p in prod_order)
        s_rows += (f'<tr style="font-weight:700;border-top:2px solid #e2e8f0">'
                   f'<td>Total</td>'
                   f'<td style="text-align:center">{_fmt(wh_total) if wh_total else "-"}</td>'
                   f'<td style="text-align:center;color:#888;font-size:12px">{round(wh_total / 2400, 1) if wh_total else "-"}</td>'
                   f'<td style="text-align:center">{_fmt(ice_total) if ice_total else "-"}</td>'
                   f'<td style="text-align:center;color:#888;font-size:12px">{round(ice_total / 2400, 1) if ice_total else "-"}</td>'
                   f'<td style="text-align:center">{_fmt(may_total) if may_total else "-"}</td>'
                   f'<td style="text-align:center;color:#888;font-size:12px">{round(may_total / 2400, 1) if may_total else "-"}</td>'
                   f'<td style="text-align:center">{_fmt(bisc_total) if bisc_total else "-"}</td>'
                   f'<td style="text-align:center;color:#888;font-size:12px">{round(bisc_total / 2400, 1) if bisc_total else "-"}</td>'
                   f'<td style="text-align:center;font-weight:700">{_fmt(grand_total)}</td>'
                   f'<td style="text-align:center;font-weight:700;color:#555">{round(grand_pallets, 1)}</td>'
                   f'</tr>')

        summary_html = (f'<div class="card full" style="margin-bottom:14px">'
                        f'<h3>Total Available Stock — All Locations</h3>'
                        f'<table class="tbl tbl-prod-rank"><thead><tr>'
                        f'<th>Product</th>'
                        f'<th>Warehouse (Karfree)</th><th style="color:#888;font-size:11px">Pallets</th>'
                        f'<th>Icedream</th><th style="color:#888;font-size:11px">Pallets</th>'
                        f'<th>Ma\'ayan</th><th style="color:#888;font-size:11px">Pallets</th>'
                        f'<th>Biscotti</th><th style="color:#888;font-size:11px">Pallets</th>'
                        f'<th>Total Available</th><th style="color:#888;font-size:11px">Pallets</th>'
                        f'</tr></thead><tbody>{s_rows}</tbody></table></div>')

    # Wrap distributor cards in a flex row
    if dist_html:
        dist_html = f'<div style="display:flex;gap:14px;flex-wrap:wrap">{dist_html}</div>'

    return summary_html + karfree_html + dist_html


FLAVOR_COLORS = {
    'chocolate': '#8B4513', 'vanilla': '#DAA520', 'mango': '#FF8C00',
    'pistachio': '#93C572', 'dream_cake': '#DB7093', 'dream_cake_2': '#C2185B',
    'magadat': '#9CA3AF',
}
TARGET_MONTHS_STOCK = 1  # Target months of inventory to maintain

def _build_flavor_svg_chart(data, months):
    """Build SVG multi-line chart showing units per flavor over 12-month timeline."""
    products_order = ['chocolate', 'vanilla', 'mango', 'dream_cake', 'dream_cake_2', 'magadat']
    w, h_chart = 560, 120
    pad_l, pad_r, pad_t = 40, 15, 8

    # Collect data per product per month
    all_vals = []
    product_lines = {}
    for p in products_order:
        line = []
        for month in CHART_MONTHS:
            md = data['monthly_data'].get(month, {})
            u = md.get('combined', {}).get(p, {}).get('units', 0)
            line.append(u if u > 0 else None)
            if u > 0:
                all_vals.append(u)
        product_lines[p] = line

    if not all_vals:
        return ''

    max_val = 50000  # Fixed Y-axis ceiling for consistent scale
    min_val = 0
    x_start = pad_l
    x_end = w - pad_r
    step_x = (x_end - x_start) / (len(CHART_MONTHS) - 1)
    x_positions = [x_start + i * step_x for i in range(len(CHART_MONTHS))]

    def y_pos(val):
        if max_val == min_val:
            return h_chart / 2 + pad_t
        clamped = min(val, max_val)
        return pad_t + (1 - (clamped - min_val) / (max_val - min_val)) * (h_chart - 20)

    svg = [f'<svg viewBox="0 0 {w} {h_chart + 30}" style="width:100%;font-family:system-ui,sans-serif">']

    # Y-axis labels only (no grid lines)
    for i in range(5):
        yv = min_val + (max_val - min_val) * (4 - i) / 4
        yp = y_pos(yv)
        svg.append(f'<text x="{pad_l-4}" y="{yp+2:.1f}" text-anchor="end" font-size="7" fill="#ccc">{_fmt(yv)}</text>')

    # X-axis month labels
    label_y = h_chart + 5
    for i, month in enumerate(CHART_MONTHS):
        x = x_positions[i]
        mh = MONTH_NAMES_HEB.get(month, month)
        has_data = any(product_lines[p][i] is not None for p in products_order)
        font_w = '500' if has_data else '400'
        fill = '#999' if has_data else '#ccc'
        svg.append(f'<text x="{x:.1f}" y="{label_y:.1f}" text-anchor="middle" font-size="7" font-weight="{font_w}" fill="{fill}">{mh}</text>')

    # Draw smooth lines per product
    for p in products_order:
        line = product_lines[p]
        color = FLAVOR_COLORS.get(p, '#666')
        points = []
        for i, val in enumerate(line):
            if val is not None:
                points.append((x_positions[i], y_pos(val), val))
        if len(points) < 1:
            continue
        # Smooth curve
        if len(points) >= 2:
            curve_pts = [(x, y) for x, y, _ in points]
            curve_d = _smooth_path(curve_pts)
            svg.append(f'<path d="{curve_d}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>')
        # Data point dots
        for x, y, val in points:
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="{color}" stroke="#fff" stroke-width="1"/>')

    # Legend
    lx = pad_l
    ly = h_chart + 16
    for p in products_order:
        if not any(v is not None for v in product_lines[p]):
            continue
        color = FLAVOR_COLORS.get(p, '#666')
        name = PRODUCT_NAMES.get(p, p)
        svg.append(f'<rect x="{lx}" y="{ly}" width="8" height="8" rx="2" fill="{color}"/>')
        svg.append(f'<text x="{lx+10}" y="{ly+7}" font-size="7" fill="#666">{name}</text>')
        lx += len(name) * 5 + 18

    svg.append('</svg>')
    return '\n'.join(svg)


def _build_flavor_analysis(data, month_list, is_all, active_products=None):
    """Build units-only sales-by-flavor analysis for production planning.
    Overview: multi-line chart + monthly units table + inventory coverage.
    Per-month: bar chart with units per flavor.
    """
    all_products = ['chocolate', 'vanilla', 'mango', 'pistachio', 'dream_cake', 'dream_cake_2', 'magadat']
    products_order = [p for p in all_products if p in active_products] if active_products else all_products
    wh = data.get('warehouse', {})
    wh_products = wh.get('products', {}) if wh else {}
    dist_inv = data.get('dist_inv', {})

    if is_all:
        months = month_list
        num_months = len(months)

        chart_html = ''  # Removed flavor trend chart per user request

        # ── Monthly units table ──
        month_labels = [MONTH_NAMES_HEB.get(m, m) for m in months]
        hdr = '<th>Product</th>'
        for ml in month_labels:
            hdr += f'<th>{ml}</th>'
        hdr += '<th>Total</th><th>Avg/Month</th><th>Trend</th>'

        rows = ''
        grand_units = 0
        for p in products_order:
            name = PRODUCT_NAMES.get(p, p)
            color = FLAVOR_COLORS.get(p, '#666')
            row = f'<td><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{color};margin-right:6px"></span><b>{name}</b></td>'
            monthly_units = []
            p_total = 0
            has_data = False
            for month in months:
                md = data['monthly_data'].get(month, {})
                u = md.get('combined', {}).get(p, {}).get('units', 0)
                monthly_units.append(u)
                p_total += u
                if u > 0:
                    has_data = True
                row += f'<td style="text-align:center">{_fmt(u) if u else "-"}</td>'

            avg = round(p_total / num_months) if num_months > 0 else 0
            # Trend: compare last month to first month with data
            non_zero = [u for u in monthly_units if u > 0]
            if len(non_zero) >= 2:
                trend_pct = round((non_zero[-1] - non_zero[-2]) / non_zero[-2] * 100)
                trend_color = '#10b981' if trend_pct >= 0 else '#ef4444'
                trend_sign = '+' if trend_pct >= 0 else ''
                trend_str = f'<span style="color:{trend_color};font-weight:700">{trend_sign}{trend_pct}%</span>'
            else:
                trend_str = '-'

            row += f'<td class="tot" style="text-align:center">{_fmt(p_total)}</td>'
            row += f'<td style="text-align:center;font-weight:600">{_fmt(avg)}</td>'
            row += f'<td style="text-align:center">{trend_str}</td>'
            if has_data:
                rows += f'<tr>{row}</tr>'
                grand_units += p_total

        # Total row
        total_row = '<td><b>Total</b></td>'
        for month in months:
            md = data['monthly_data'].get(month, {})
            mu = sum(md.get('combined', {}).get(p, {}).get('units', 0) for p in products_order)
            total_row += f'<td style="text-align:center"><b>{_fmt(mu)}</b></td>'
        grand_avg = round(grand_units / num_months) if num_months > 0 else 0
        total_row += f'<td class="tot" style="text-align:center"><b>{_fmt(grand_units)}</b></td>'
        total_row += f'<td style="text-align:center"><b>{_fmt(grand_avg)}</b></td>'
        total_row += '<td></td>'
        rows += f'<tr style="border-top:2px solid #e2e8f0">{total_row}</tr>'

        # ── Donut chart (Gridle-style) with hover tooltips ──
        import math
        from config import extract_customer_name

        # Check if single-product brand → show by-customer donut instead of by-flavor
        single_product_mode = len(products_order) == 1

        if single_product_mode:
            # ── By-Customer donut for single-product brands (e.g. Dani's) ──
            the_product = products_order[0]
            CUSTOMER_COLORS = [
                '#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6',
                '#ec4899', '#14b8a6', '#f97316', '#06b6d4', '#84cc16',
                '#a855f7', '#e11d48', '#0ea5e9', '#d97706', '#22c55e',
            ]
            cust_units = {}
            for m in months:
                md = data['monthly_data'].get(m, {})
                # Icedream customers
                for cust, pdata in md.get('icedreams_customers', {}).items():
                    chain = extract_customer_name(cust)
                    u = pdata.get(the_product, {}).get('units', 0) if isinstance(pdata.get(the_product), dict) else 0
                    if u > 0:
                        cust_units[chain] = cust_units.get(chain, 0) + u
                # Biscotti customers (sum across all products in the filter)
                for cust, pdata in md.get('biscotti_customers', {}).items():
                    u = sum((pdata.get(pp) or {}).get('units', 0) for pp in products_order)
                    if u > 0:
                        cust_units[cust] = cust_units.get(cust, 0) + u

            donut_data = sorted(cust_units.items(), key=lambda x: x[1], reverse=True)
            top_n = donut_data[:10]
            others_u = sum(u for _, u in donut_data[10:])
            if others_u > 0:
                top_n.append(('Others', others_u))

            cx, cy, r_outer, r_inner = 120, 120, 110, 70
            donut_arcs = ''
            donut_id = 'donut-ov'
            angle = -90
            for idx, (cust_name, u) in enumerate(top_n):
                pct = u / grand_units if grand_units > 0 else 0
                pct_r = round(pct * 100, 1)
                sweep = pct * 360
                if sweep < 0.5:
                    continue
                color = CUSTOMER_COLORS[idx % len(CUSTOMER_COLORS)]
                safe_name = cust_name.replace("'", "\\'")
                a_start = math.radians(angle)
                a_end = math.radians(angle + sweep)
                x1 = cx + r_outer * math.cos(a_start)
                y1 = cy + r_outer * math.sin(a_start)
                x2 = cx + r_outer * math.cos(a_end)
                y2 = cy + r_outer * math.sin(a_end)
                x3 = cx + r_inner * math.cos(a_end)
                y3 = cy + r_inner * math.sin(a_end)
                x4 = cx + r_inner * math.cos(a_start)
                y4 = cy + r_inner * math.sin(a_start)
                large = 1 if sweep > 180 else 0
                donut_arcs += (f'<path d="M {x1:.2f},{y1:.2f} '
                               f'A {r_outer},{r_outer} 0 {large},1 {x2:.2f},{y2:.2f} '
                               f'L {x3:.2f},{y3:.2f} '
                               f'A {r_inner},{r_inner} 0 {large},0 {x4:.2f},{y4:.2f} Z" '
                               f'fill="{color}" style="cursor:pointer;transition:opacity 0.15s" '
                               f'onmouseenter="document.getElementById(\'{donut_id}-name\').textContent=\'{safe_name}\';'
                               f'document.getElementById(\'{donut_id}-pct\').textContent=\'{pct_r}%\'" '
                               f'onmouseleave="document.getElementById(\'{donut_id}-name\').textContent=\'Customers\';'
                               f'document.getElementById(\'{donut_id}-pct\').textContent=\'units\'" />')
                angle += sweep

            donut_svg = (f'<svg viewBox="0 0 240 240" style="width:210px;height:210px;flex-shrink:0">'
                         f'{donut_arcs}'
                         f'<text id="{donut_id}-name" x="{cx}" y="{cy - 4}" text-anchor="middle" font-size="14" font-weight="700" fill="#1e293b">Customers</text>'
                         f'<text id="{donut_id}-pct" x="{cx}" y="{cy + 14}" text-anchor="middle" font-size="12" fill="#94a3b8">units</text>'
                         f'</svg>')

            legend_items = ''
            for idx, (cust_name, u) in enumerate(top_n):
                color = CUSTOMER_COLORS[idx % len(CUSTOMER_COLORS)]
                pct = round(u / grand_units * 100) if grand_units > 0 else 0
                legend_items += (
                    f'<div style="display:flex;align-items:center;gap:10px;padding:5px 0;'
                    f'border-bottom:1px solid #f1f5f9">'
                    f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:{color};flex-shrink:0"></span>'
                    f'<span style="font-size:12px;color:#334155;font-weight:500;min-width:110px">{cust_name}</span>'
                    f'<span style="font-size:12px;color:#334155;font-weight:600;min-width:50px;text-align:right">{_fmt(u)}</span>'
                    f'<span style="font-size:12px;color:#94a3b8;min-width:32px;text-align:right">{pct}%</span></div>')

            donut_section = (
                f'<div style="display:flex;align-items:flex-start;gap:28px;padding:12px 0">'
                f'{donut_svg}'
                f'<div style="flex-shrink:0">'
                f'<div style="font-size:11px;font-weight:600;color:#64748b;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px">'
                f'Top {len(top_n)} customers</div>'
                f'{legend_items}</div>'
                f'</div>')
        else:
            # ── Multi-product flavor donut (original) ──
            donut_data = []
            dist_by_flavor = {}
            for p in products_order:
                p_total_u = 0
                ice_t = may_t = bisc_t = 0
                for m in months:
                    c = data['monthly_data'].get(m, {}).get('combined', {}).get(p, {})
                    p_total_u += c.get('units', 0)
                    ice_t += c.get('icedreams_units', 0)
                    may_t += c.get('mayyan_units', 0)
                    bisc_t += c.get('biscotti_units', 0)
                if p_total_u > 0:
                    donut_data.append((p, p_total_u))
                    dist_by_flavor[p] = {'icedream': ice_t, 'mayyan': may_t, 'biscotti': bisc_t}
            donut_data.sort(key=lambda x: x[1], reverse=True)

            cx, cy, r_outer, r_inner = 120, 120, 110, 70
            donut_arcs = ''
            donut_id = 'donut-ov'
            angle = -90
            for p, u in donut_data:
                pct = u / grand_units if grand_units > 0 else 0
                pct_r = round(pct * 100, 1)
                sweep = pct * 360
                color = FLAVOR_COLORS.get(p, '#666')
                name = PRODUCT_NAMES.get(p, p)
                a_start = math.radians(angle)
                a_end = math.radians(angle + sweep)
                x1 = cx + r_outer * math.cos(a_start)
                y1 = cy + r_outer * math.sin(a_start)
                x2 = cx + r_outer * math.cos(a_end)
                y2 = cy + r_outer * math.sin(a_end)
                x3 = cx + r_inner * math.cos(a_end)
                y3 = cy + r_inner * math.sin(a_end)
                x4 = cx + r_inner * math.cos(a_start)
                y4 = cy + r_inner * math.sin(a_start)
                large = 1 if sweep > 180 else 0
                donut_arcs += (f'<path d="M {x1:.2f},{y1:.2f} '
                               f'A {r_outer},{r_outer} 0 {large},1 {x2:.2f},{y2:.2f} '
                               f'L {x3:.2f},{y3:.2f} '
                               f'A {r_inner},{r_inner} 0 {large},0 {x4:.2f},{y4:.2f} Z" '
                               f'fill="{color}" style="cursor:pointer;transition:opacity 0.15s" '
                               f'onmouseenter="document.getElementById(\'{donut_id}-name\').textContent=\'{name}\';'
                               f'document.getElementById(\'{donut_id}-pct\').textContent=\'{pct_r}%\'" '
                               f'onmouseleave="document.getElementById(\'{donut_id}-name\').textContent=\'Flavors\';'
                               f'document.getElementById(\'{donut_id}-pct\').textContent=\'units\'" />')
                angle += sweep

            donut_svg = (f'<svg viewBox="0 0 240 240" style="width:210px;height:210px;flex-shrink:0">'
                         f'{donut_arcs}'
                         f'<text id="{donut_id}-name" x="{cx}" y="{cy - 4}" text-anchor="middle" font-size="14" font-weight="700" fill="#1e293b">Flavors</text>'
                         f'<text id="{donut_id}-pct" x="{cx}" y="{cy + 14}" text-anchor="middle" font-size="12" fill="#94a3b8">units</text>'
                         f'</svg>')

            legend_items = ''
            for p, u in donut_data:
                name = PRODUCT_NAMES.get(p, p)
                color = FLAVOR_COLORS.get(p, '#666')
                pct = round(u / grand_units * 100) if grand_units > 0 else 0
                legend_items += (
                    f'<div style="display:flex;align-items:center;gap:10px;padding:5px 0;'
                    f'border-bottom:1px solid #f1f5f9">'
                    f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:{color};flex-shrink:0"></span>'
                    f'<span style="font-size:12px;color:#334155;font-weight:500;min-width:110px">{name}</span>'
                    f'<span style="font-size:12px;color:#334155;font-weight:600;min-width:50px;text-align:right">{_fmt(u)}</span>'
                    f'<span style="font-size:12px;color:#94a3b8;min-width:32px;text-align:right">{pct}%</span></div>')

            # Sales by Flavor by Client (right side)
            client_rows = ''
            for p, u in donut_data:
                name = PRODUCT_NAMES.get(p, p)
                color = FLAVOR_COLORS.get(p, '#666')
                dd = dist_by_flavor.get(p, {})
                ice_u = dd.get('icedream', 0)
                may_u = dd.get('mayyan', 0)
                bisc_u = dd.get('biscotti', 0)
                client_rows += (
                    f'<tr>'
                    f'<td style="padding:4px 6px;font-size:11px;white-space:nowrap">'
                    f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{color};margin-right:4px"></span>{name}</td>'
                    f'<td style="padding:4px 6px;font-size:11px;text-align:center;color:#334155">{_fmt(ice_u) if ice_u else "-"}</td>'
                    f'<td style="padding:4px 6px;font-size:11px;text-align:center;color:#334155">{_fmt(may_u) if may_u else "-"}</td>'
                    f'<td style="padding:4px 6px;font-size:11px;text-align:center;color:#334155">{_fmt(bisc_u) if bisc_u else "-"}</td>'
                    f'<td style="padding:4px 6px;font-size:11px;text-align:center;font-weight:600">{_fmt(u)}</td>'
                    f'</tr>')

            client_table = (
                f'<div>'
                f'<div style="font-size:10px;font-weight:600;color:#64748b;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px">'
                f'By Distributor</div>'
                f'<table style="border-collapse:collapse;width:100%">'
                f'<thead><tr>'
                f'<th style="padding:4px 6px;font-size:9px;text-align:left;color:#94a3b8;font-weight:600;text-transform:uppercase;border-bottom:1px solid #e2e8f0">Flavor</th>'
                f'<th style="padding:4px 6px;font-size:9px;text-align:center;color:#94a3b8;font-weight:600;text-transform:uppercase;border-bottom:1px solid #e2e8f0">Icedream</th>'
                f'<th style="padding:4px 6px;font-size:9px;text-align:center;color:#94a3b8;font-weight:600;text-transform:uppercase;border-bottom:1px solid #e2e8f0">Ma\'ayan</th>'
                f'<th style="padding:4px 6px;font-size:9px;text-align:center;color:#94a3b8;font-weight:600;text-transform:uppercase;border-bottom:1px solid #e2e8f0">Biscotti</th>'
                f'<th style="padding:4px 6px;font-size:9px;text-align:center;color:#94a3b8;font-weight:600;text-transform:uppercase;border-bottom:1px solid #e2e8f0">Total</th>'
                f'</tr></thead><tbody>{client_rows}</tbody></table></div>')

            donut_section = (
                f'<div style="display:flex;align-items:flex-start;gap:28px;padding:12px 0">'
                f'{donut_svg}'
                f'<div style="flex-shrink:0">'
                f'<div style="font-size:11px;font-weight:600;color:#64748b;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px">'
                f'Top {len(donut_data)} flavors</div>'
                f'{legend_items}</div>'
                f'<div style="flex:1;min-width:200px">{client_table}</div>'
                f'</div>')

        card_title = 'Units Sold by Customer — Monthly' if single_product_mode else 'Units Sold by Flavor — Monthly'
        units_table = (f'<div class="card full" style="margin-bottom:14px">'
                       f'<h3>{card_title}</h3>'
                       f'{donut_section}'
                       f'<div style="overflow-x:auto;max-width:100%">'
                       f'<table class="tbl" style="margin-top:10px"><thead><tr>{hdr}</tr></thead>'
                       f'<tbody>{rows}</tbody></table></div></div>')

        # ── Inventory Coverage / Production Planning ──
        coverage_html = ''
        has_any_stock = wh_products or dist_inv
        if has_any_stock:
            cov_rows = ''
            for p in products_order:
                name = PRODUCT_NAMES.get(p, p)
                color = FLAVOR_COLORS.get(p, '#666')

                # Avg monthly sales
                p_total = sum(
                    data['monthly_data'].get(m, {}).get('combined', {}).get(p, {}).get('units', 0)
                    for m in months)
                avg_monthly = round(p_total / num_months) if num_months > 0 else 0

                # Last month sales
                last_md = data['monthly_data'].get(months[-1], {})
                last_month_u = last_md.get('combined', {}).get(p, {}).get('units', 0)

                # Current stock — total across all locations
                wh_stock = wh_products.get(p, {}).get('units', 0)
                ice_stock = dist_inv.get('icedream', {}).get('products', {}).get(p, {}).get('units', 0)
                may_stock = dist_inv.get('mayyan', {}).get('products', {}).get(p, {}).get('units', 0)
                stock = wh_stock + ice_stock + may_stock

                # Months of stock remaining (based on avg)
                if avg_monthly > 0:
                    months_stock = round(stock / avg_monthly, 1)
                else:
                    months_stock = 99 if stock > 0 else 0

                # Coverage bar color
                if months_stock >= TARGET_MONTHS_STOCK * 1.5:
                    cov_color = '#10b981'  # green - good
                    cov_label = 'OK'
                elif months_stock >= TARGET_MONTHS_STOCK * 0.5:
                    cov_color = '#f59e0b'  # yellow - warning
                    cov_label = 'Low'
                else:
                    cov_color = '#ef4444'  # red - critical
                    cov_label = 'Critical'

                # Suggested production (to reach target months of stock)
                target_units = avg_monthly * TARGET_MONTHS_STOCK
                suggested = max(0, target_units - stock)

                # Coverage bar visual (max 3 months width)
                bar_pct = min(months_stock / 3 * 100, 100)

                if avg_monthly == 0 and stock == 0:
                    continue

                dot = f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{color};margin-right:6px"></span>'
                stock_pallets = '-' if p == 'dream_cake' else str(round(stock / 2400, 1))
                sug_pallets = '-' if p == 'dream_cake' else (str(round(suggested / 2400, 1)) if suggested > 0 else '✓')
                cov_rows += (f'<tr>'
                             f'<td>{dot}<b>{name}</b></td>'
                             f'<td style="text-align:center">{_fmt(avg_monthly)}</td>'
                             f'<td style="text-align:center">{_fmt(last_month_u)}</td>'
                             f'<td style="text-align:center"><b>{_fmt(stock)}</b></td>'
                             f'<td style="text-align:center;color:#888;font-size:12px">{stock_pallets}</td>'
                             f'<td style="text-align:center">'
                             f'<div style="display:flex;align-items:center;gap:4px;justify-content:center">'
                             f'<div style="width:60px;background:#f0f0f0;border-radius:3px;height:14px">'
                             f'<div style="width:{bar_pct:.0f}%;background:{cov_color};height:100%;border-radius:3px"></div></div>'
                             f'<span style="font-weight:700;color:{cov_color}">{months_stock}</span></div></td>'
                             f'<td style="text-align:center;font-weight:700;color:{cov_color}">{cov_label}</td>'
                             f'<td style="text-align:center;font-weight:700">{_fmt(suggested) if suggested > 0 else "✓"}</td>'
                             f'<td style="text-align:center;color:#888;font-size:12px">{sug_pallets}</td>'
                             f'</tr>')

            coverage_html = (f'<div class="card full" style="margin-bottom:14px">'
                             f'<h3>Inventory Coverage & Production Planning (target: {TARGET_MONTHS_STOCK} month stock)</h3>'
                             f'<table class="tbl tbl-prod-rank"><thead><tr>'
                             f'<th>Product</th><th>Avg Sales/Mo</th><th>Last Month</th>'
                             f'<th>Current Stock</th><th style="color:#888;font-size:11px">Pallets</th><th>Months of Stock</th><th>Status</th>'
                             f'<th>Suggested Production</th><th style="color:#888;font-size:11px">Pallets</th>'
                             f'</tr></thead><tbody>{cov_rows}</tbody></table></div>')

        return chart_html + units_table + coverage_html

    else:
        # ── Per-month: single month flavor donut ──
        import math
        from config import extract_customer_name
        month = month_list[0]
        md = data['monthly_data'].get(month, {})

        flavor_data = []
        total_u = 0
        for p in products_order:
            c = md.get('combined', {}).get(p, {})
            u = c.get('units', 0)
            if u > 0:
                flavor_data.append((p, u))
                total_u += u

        if not flavor_data:
            return ''

        flavor_data.sort(key=lambda x: x[1], reverse=True)

        single_product_mode = len(products_order) == 1

        if single_product_mode:
            # ── By-Customer donut for single-product brand (per-month) ──
            the_product = products_order[0]
            CUSTOMER_COLORS = [
                '#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6',
                '#ec4899', '#14b8a6', '#f97316', '#06b6d4', '#84cc16',
                '#a855f7', '#e11d48', '#0ea5e9', '#d97706', '#22c55e',
            ]
            cust_units = {}
            for cust, pdata in md.get('icedreams_customers', {}).items():
                chain = extract_customer_name(cust)
                u = pdata.get(the_product, {}).get('units', 0) if isinstance(pdata.get(the_product), dict) else 0
                if u > 0:
                    cust_units[chain] = cust_units.get(chain, 0) + u
            for cust, pdata in md.get('biscotti_customers', {}).items():
                u = sum((pdata.get(pp) or {}).get('units', 0) for pp in products_order)
                if u > 0:
                    cust_units[cust] = cust_units.get(cust, 0) + u

            cust_sorted_donut = sorted(cust_units.items(), key=lambda x: x[1], reverse=True)
            top_n = cust_sorted_donut[:10]
            others_u = sum(u for _, u in cust_sorted_donut[10:])
            if others_u > 0:
                top_n.append(('Others', others_u))

            cx, cy, r_outer, r_inner = 110, 110, 100, 65
            donut_arcs = ''
            angle = -90
            for idx, (cust_name, u) in enumerate(top_n):
                pct = u / total_u if total_u > 0 else 0
                sweep = pct * 360
                if sweep < 0.5:
                    continue
                color = CUSTOMER_COLORS[idx % len(CUSTOMER_COLORS)]
                safe_name = cust_name.replace("'", "\\'")
                a_start = math.radians(angle)
                a_end = math.radians(angle + sweep)
                x1 = cx + r_outer * math.cos(a_start)
                y1 = cy + r_outer * math.sin(a_start)
                x2 = cx + r_outer * math.cos(a_end)
                y2 = cy + r_outer * math.sin(a_end)
                x3 = cx + r_inner * math.cos(a_end)
                y3 = cy + r_inner * math.sin(a_end)
                x4 = cx + r_inner * math.cos(a_start)
                y4 = cy + r_inner * math.sin(a_start)
                large = 1 if sweep > 180 else 0
                donut_arcs += (f'<path d="M {x1:.2f},{y1:.2f} '
                               f'A {r_outer},{r_outer} 0 {large},1 {x2:.2f},{y2:.2f} '
                               f'L {x3:.2f},{y3:.2f} '
                               f'A {r_inner},{r_inner} 0 {large},0 {x4:.2f},{y4:.2f} Z" '
                               f'fill="{color}" style="cursor:pointer;transition:opacity 0.15s" '
                               f'onmouseenter="this.parentElement.querySelector(\'[data-center-name]\').textContent=\'{safe_name}\';'
                               f'this.parentElement.querySelector(\'[data-center-pct]\').textContent=\'{round(pct*100,1)}%\'" '
                               f'onmouseleave="this.parentElement.querySelector(\'[data-center-name]\').textContent=\'Customers\';'
                               f'this.parentElement.querySelector(\'[data-center-pct]\').textContent=\'units\'" />')
                angle += sweep

            donut_svg = (f'<svg viewBox="0 0 220 220" style="width:180px;height:180px;flex-shrink:0">'
                         f'{donut_arcs}'
                         f'<text data-center-name x="{cx}" y="{cy - 6}" text-anchor="middle" font-size="15" font-weight="700" fill="#1e293b">Customers</text>'
                         f'<text data-center-pct x="{cx}" y="{cy + 12}" text-anchor="middle" font-size="11" fill="#94a3b8">units</text>'
                         f'</svg>')

            legend_items = ''
            for idx, (cust_name, u) in enumerate(top_n):
                color = CUSTOMER_COLORS[idx % len(CUSTOMER_COLORS)]
                pct = round(u / total_u * 100) if total_u > 0 else 0
                legend_items += (
                    f'<div style="display:flex;align-items:center;gap:12px;padding:6px 0;'
                    f'border-bottom:1px solid #f1f5f9">'
                    f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:{color};flex-shrink:0"></span>'
                    f'<div style="min-width:120px"><span style="font-size:13px;color:#334155;font-weight:500">{cust_name}</span></div>'
                    f'<span style="font-size:13px;color:#334155;font-weight:600;min-width:55px;text-align:right">{_fmt(u)}</span>'
                    f'<span style="font-size:13px;color:#94a3b8;min-width:36px;text-align:right">{pct}%</span></div>')

            donut_section = (
                f'<div style="display:flex;align-items:center;gap:32px;padding:12px 0">'
                f'{donut_svg}'
                f'<div>'
                f'<div style="font-size:12px;font-weight:600;color:#64748b;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px">'
                f'Top {len(top_n)} customers</div>'
                f'{legend_items}'
                f'<div style="border-top:1px solid #e2e8f0;margin-top:5px;padding-top:6px;display:flex;justify-content:space-between;font-weight:700;font-size:13px;color:#1e293b">'
                f'<span>Total</span><span>{_fmt(total_u)} units</span></div></div></div>')

            return (f'<div class="card full" style="margin-bottom:14px">'
                    f'<h3>Units Sold by Customer</h3>{donut_section}</div>')

        # ── Multi-product flavor donut (original per-month) ──
        # SVG donut
        cx, cy, r_outer, r_inner = 110, 110, 100, 65
        donut_arcs = ''
        angle = -90
        for p, u in flavor_data:
            pct = u / total_u if total_u > 0 else 0
            sweep = pct * 360
            color = FLAVOR_COLORS.get(p, '#666')
            a_start = math.radians(angle)
            a_end = math.radians(angle + sweep)
            x1 = cx + r_outer * math.cos(a_start)
            y1 = cy + r_outer * math.sin(a_start)
            x2 = cx + r_outer * math.cos(a_end)
            y2 = cy + r_outer * math.sin(a_end)
            x3 = cx + r_inner * math.cos(a_end)
            y3 = cy + r_inner * math.sin(a_end)
            x4 = cx + r_inner * math.cos(a_start)
            y4 = cy + r_inner * math.sin(a_start)
            large = 1 if sweep > 180 else 0
            donut_arcs += (f'<path d="M {x1:.2f},{y1:.2f} '
                           f'A {r_outer},{r_outer} 0 {large},1 {x2:.2f},{y2:.2f} '
                           f'L {x3:.2f},{y3:.2f} '
                           f'A {r_inner},{r_inner} 0 {large},0 {x4:.2f},{y4:.2f} Z" '
                           f'fill="{color}" />')
            angle += sweep

        donut_svg = (f'<svg viewBox="0 0 220 220" style="width:180px;height:180px;flex-shrink:0">'
                     f'{donut_arcs}'
                     f'<text x="{cx}" y="{cy - 6}" text-anchor="middle" font-size="15" font-weight="700" fill="#1e293b">Flavors</text>'
                     f'<text x="{cx}" y="{cy + 12}" text-anchor="middle" font-size="11" fill="#94a3b8">units breakdown</text>'
                     f'</svg>')

        legend_items = ''
        for p, u in flavor_data:
            name = PRODUCT_NAMES.get(p, p)
            color = FLAVOR_COLORS.get(p, '#666')
            pct = round(u / total_u * 100) if total_u > 0 else 0
            # Distributor split
            c = md.get('combined', {}).get(p, {})
            may_u = c.get('mayyan_units', 0)
            ice_u = c.get('icedreams_units', 0)
            bisc_u = c.get('biscotti_units', 0)
            split_parts = []
            if may_u > 0: split_parts.append(f"Ma'ayan {_fmt(may_u)}")
            if ice_u > 0: split_parts.append(f"Icedream {_fmt(ice_u)}")
            if bisc_u > 0: split_parts.append(f"Biscotti {_fmt(bisc_u)}")
            split_str = f'<div style="font-size:10px;color:#94a3b8;margin-top:1px">{" / ".join(split_parts)}</div>' if split_parts else ''

            legend_items += (
                f'<div style="display:flex;align-items:center;gap:12px;padding:6px 0;'
                f'border-bottom:1px solid #f1f5f9">'
                f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:{color};flex-shrink:0"></span>'
                f'<div style="min-width:120px"><span style="font-size:13px;color:#334155;font-weight:500">{name}</span>{split_str}</div>'
                f'<span style="font-size:13px;color:#334155;font-weight:600;min-width:55px;text-align:right">{_fmt(u)}</span>'
                f'<span style="font-size:13px;color:#94a3b8;min-width:36px;text-align:right">{pct}%</span></div>')

        donut_section = (
            f'<div style="display:flex;align-items:center;gap:32px;padding:12px 0">'
            f'{donut_svg}'
            f'<div>'
            f'<div style="font-size:12px;font-weight:600;color:#64748b;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px">'
            f'Top {len(flavor_data)} flavors</div>'
            f'{legend_items}'
            f'<div style="border-top:1px solid #e2e8f0;margin-top:5px;padding-top:6px;display:flex;justify-content:space-between;font-weight:700;font-size:13px;color:#1e293b">'
            f'<span>Total</span><span>{_fmt(total_u)} units</span></div></div></div>')

        # ── By Customer breakdown table ──
        flavor_products = [p for p, _ in flavor_data]
        cust_flavor = {}  # {customer_name: {product: units}}

        # Icedream customers
        for cust, pdata in md.get('icedreams_customers', {}).items():
            chain = extract_customer_name(cust)
            if chain not in cust_flavor:
                cust_flavor[chain] = {}
            for p in flavor_products:
                u = pdata.get(p, {}).get('units', 0) if isinstance(pdata.get(p), dict) else 0
                cust_flavor[chain][p] = cust_flavor[chain].get(p, 0) + u

        # Ma'ayan customers
        for key, pdata in md.get('mayyan_accounts_revenue', {}).items():
            source_chain, acct = key if isinstance(key, tuple) else ('', key)
            chain = extract_customer_name(acct, source_customer=source_chain)
            if chain not in cust_flavor:
                cust_flavor[chain] = {}
            for p in flavor_products:
                u = pdata.get(p, {}).get('units', 0) if isinstance(pdata.get(p), dict) else 0
                cust_flavor[chain][p] = cust_flavor[chain].get(p, 0) + u

        # Biscotti customers
        for cust, pdata in md.get('biscotti_customers', {}).items():
            if cust not in cust_flavor:
                cust_flavor[cust] = {}
            for p in flavor_products:
                u = pdata.get(p, {}).get('units', 0) if isinstance(pdata.get(p), dict) else 0
                cust_flavor[cust][p] = cust_flavor[cust].get(p, 0) + u

        # Filter out zero-total customers, sort by total desc
        cust_totals = {c: sum(pvals.values()) for c, pvals in cust_flavor.items()}
        cust_sorted = sorted(((c, cust_totals[c]) for c in cust_flavor if cust_totals[c] > 0),
                             key=lambda x: x[1], reverse=True)

        cust_table_html = ''
        if cust_sorted:
            cust_hdr = '<th style="padding:4px 6px;font-size:9px;text-align:left;color:#94a3b8;font-weight:600;text-transform:uppercase;border-bottom:1px solid #e2e8f0">Customer</th>'
            for p in flavor_products:
                color = FLAVOR_COLORS.get(p, '#666')
                short = PRODUCT_NAMES.get(p, p)
                cust_hdr += f'<th style="padding:4px 6px;font-size:9px;text-align:center;color:#94a3b8;font-weight:600;text-transform:uppercase;border-bottom:1px solid #e2e8f0">{short}</th>'
            cust_hdr += '<th style="padding:4px 6px;font-size:9px;text-align:center;color:#94a3b8;font-weight:600;text-transform:uppercase;border-bottom:1px solid #e2e8f0">Total</th>'

            # Show top 10, with show-more for the rest
            cust_rows_all = ''
            for idx, (cust, ct) in enumerate(cust_sorted):
                hide_style = ' style="display:none"' if idx >= 10 else ''
                hide_cls = f' class="cust-extra-{month.replace(" ", "_")}"' if idx >= 10 else ''
                row = f'<td style="padding:4px 6px;font-size:11px;white-space:nowrap">{cust}</td>'
                for p in flavor_products:
                    u = cust_flavor[cust].get(p, 0)
                    row += f'<td style="padding:4px 6px;font-size:11px;text-align:center;color:#334155">{_fmt(u) if u else "-"}</td>'
                row += f'<td style="padding:4px 6px;font-size:11px;text-align:center;font-weight:600">{_fmt(ct)}</td>'
                cust_rows_all += f'<tr{hide_cls}{hide_style}>{row}</tr>'

            show_more_btn = ''
            if len(cust_sorted) > 10:
                extra_cls = f'cust-extra-{month.replace(" ", "_")}'
                show_more_btn = (
                    f'<div style="text-align:center;margin-top:6px">'
                    f'<button onclick="document.querySelectorAll(\'.\' + \'{extra_cls}\').forEach(function(r){{r.style.display=r.style.display===\'none\'?\'table-row\':\'none\'}});'
                    f'this.textContent=this.textContent.indexOf(\'Show\')>=0?\'Hide\':\'Show More ({len(cust_sorted)-10})\';"'
                    f' style="background:none;border:1px solid #e2e8f0;border-radius:6px;padding:4px 12px;font-size:11px;color:#64748b;cursor:pointer">'
                    f'Show More ({len(cust_sorted)-10})</button></div>')

            cust_table_html = (
                f'<div style="margin-top:12px;border-top:1px solid #e2e8f0;padding-top:10px">'
                f'<div style="font-size:10px;font-weight:600;color:#64748b;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px">'
                f'By Customer</div>'
                f'<div style="overflow-x:auto"><table style="border-collapse:collapse;width:100%">'
                f'<thead><tr>{cust_hdr}</tr></thead>'
                f'<tbody>{cust_rows_all}</tbody></table></div>'
                f'{show_more_btn}</div>')

        return (f'<div class="card full" style="margin-bottom:14px">'
                f'<h3>Units Sold by Flavor</h3>{donut_section}{cust_table_html}</div>')


def _build_month_section(data, month_list, section_id, active_products):
    """Build one month section (KPIs + charts + tables)."""
    products = data['products']
    tu, tr, tc, tgm, tmy, tic, tbi, mp, ip, bp = _compute_kpis(data, month_list, active_products)
    is_all = len(month_list) > 1
    label = 'Overview' if is_all else MONTH_NAMES_HEB.get(month_list[0], month_list[0])

    # ── KPI Cards ──
    pos_count = _count_pos(data, month_list, active_products)

    # Creators card - filtered by brand
    creators_blocks = ''
    cr_idx = 0
    total_skus = 0
    creator_rows_html = ''
    creator_row_items = []
    for cr in CREATORS:
        relevant_skus = [p for p in cr['products'] if p in active_products]
        if not relevant_skus:
            continue
        total_skus += len(relevant_skus)
        cr_idx += 1
        # Build SKU dots with EN product names
        sku_dots = ''.join(
            f'<span style="display:inline-flex;align-items:center;gap:3px;margin-right:6px">'
            f'<span style="width:6px;height:6px;border-radius:50%;background:{FLAVOR_COLORS.get(p,"#888")};flex-shrink:0"></span>'
            f'<span style="font-size:9px;color:#555">{PRODUCT_NAMES.get(p, p)}</span>'
            f'</span>'
            for p in relevant_skus
        )
        border_left = 'border-left:1px solid #e5e7eb;' if cr_idx > 1 else ''
        creator_row_items.append(
            f'<div style="padding:4px 8px;{border_left}">'
            f'<div style="display:flex;align-items:baseline;gap:4px">'
            f'<span style="font-size:11px;font-weight:700;color:#1e3a5f">{cr["brand"]}</span>'
            f'<span style="font-size:9px;color:#888">{cr["name"]}</span>'
            f'</div>'
            f'<div style="display:flex;flex-wrap:wrap;gap:3px;margin-top:3px">{sku_dots}</div>'
            f'</div>'
        )
    creators_count = cr_idx
    if creator_row_items:
        creator_rows_html = (
            f'<div style="margin-top:8px;padding-top:7px;border-top:1px solid #e5e7eb;width:100%;'
            f'display:grid;grid-template-columns:1fr 1fr;gap:0">'
            + ''.join(creator_row_items)
            + '</div>'
        )

    # ── Modern KPI Cards with big numbers ──
    rev_trend = ''
    if is_all and len(month_list) >= 2:
        # Calculate revenue trend from last two months with data
        rev_vals = []
        for m in month_list:
            md = data['monthly_data'].get(m, {})
            rv = sum(md.get('combined', {}).get(p, {}).get('total_value', 0) for p in active_products)
            if rv > 0:
                rev_vals.append(rv)
        if len(rev_vals) >= 2:
            rpct = round((rev_vals[-1] - rev_vals[-2]) / rev_vals[-2] * 100)
            if rpct >= 0:
                rev_trend = f'<span class="badge-up">+{rpct}%</span>'
            else:
                rev_trend = f'<span class="badge-down">{rpct}%</span>'

    units_trend = ''
    if is_all and len(month_list) >= 2:
        unit_vals = []
        for m in month_list:
            md = data['monthly_data'].get(m, {})
            uv = sum(md.get('combined', {}).get(p, {}).get('units', 0) for p in active_products)
            if uv > 0:
                unit_vals.append(uv)
        if len(unit_vals) >= 2:
            upct = round((unit_vals[-1] - unit_vals[-2]) / unit_vals[-2] * 100)
            if upct >= 0:
                units_trend = f'<span class="badge-up">+{upct}%</span>'
            else:
                units_trend = f'<span class="badge-down">{upct}%</span>'

    sales_card = f'''<div class="kpi">
    <div class="kpi-title">Total Revenue</div>
    <div class="big-number" style="color:var(--success)">{_fc(tr)}</div>
    <div class="stat-label" style="margin-top:8px">all time</div>
  </div>'''

    units_card_kpi = f'''<div class="kpi">
    <div class="kpi-title">Units Sold</div>
    <div class="big-number">{_fmt(tu)}</div>
    <div class="stat-label" style="margin-top:8px">all time</div>
  </div>'''

    pos_card = f'''<div class="kpi">
    <div class="kpi-title">Points of Sale</div>
    <div class="big-number-md">{pos_count}</div>
    <div class="stat-label" style="margin-top:8px">Active locations</div>
  </div>'''

    creators_card = f'''<div class="kpi" style="align-items:flex-start">
    <div class="kpi-title" style="width:100%">Creators</div>
    <div class="big-number-md">{creators_count}</div>
    <div class="stat-label" style="margin-top:4px">{total_skus} SKUs</div>
    {creator_rows_html}
  </div>'''

    # Supply Chain card — filtered by active_products
    wh = data.get('warehouse', {})
    wh_products_kpi = wh.get('products', {})

    # Filter inventory to active products only
    filtered_inv_total = 0
    if wh_products_kpi:
        for p in active_products:
            pd_kpi = wh_products_kpi.get(p)
            if pd_kpi:
                filtered_inv_total += pd_kpi.get('units', 0)
    # Also add distributor inventory for filtered products
    dist_inv_data = data.get('dist_inv', {})
    for dk in ['icedream', 'mayyan', 'biscotti']:
        dprods = dist_inv_data.get(dk, {}).get('products', {})
        for p in active_products:
            pd_d = dprods.get(p)
            if pd_d:
                filtered_inv_total += pd_d.get('units', 0)
    inv_total = filtered_inv_total

    # Build per-flavor rows for inventory KPI
    flavor_rows_html = ''
    if inv_total > 0 and wh_products_kpi:
        prod_order_kpi = [p for p in ['chocolate', 'vanilla', 'mango', 'pistachio', 'dream_cake', 'magadat'] if p in active_products]
        rows_list = []
        for p in prod_order_kpi:
            # Sum across all locations for this product
            u = wh_products_kpi.get(p, {}).get('units', 0)
            for dk in ['icedream', 'mayyan', 'biscotti']:
                u += dist_inv_data.get(dk, {}).get('products', {}).get(p, {}).get('units', 0)
            if u == 0:
                continue
            color = FLAVOR_COLORS.get(p, '#888')
            en_name = PRODUCT_NAMES.get(p, p)
            pct = round(u / inv_total * 100) if inv_total > 0 else 0
            rows_list.append(
                f'<div style="display:flex;align-items:center;gap:5px;padding:2px 0">'
                f'<span style="width:7px;height:7px;border-radius:50%;background:{color};flex-shrink:0"></span>'
                f'<span style="flex:1;font-size:10px;color:#555;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{en_name}</span>'
                f'<span style="font-size:10px;font-weight:600;color:#333">{_fmt(u)}</span>'
                f'<span style="font-size:9px;color:#999;min-width:26px;text-align:right">{pct}%</span>'
                f'</div>'
            )
        if rows_list:
            flavor_rows_html = (
                f'<div style="margin-top:8px;padding-top:7px;border-top:1px solid #e5e7eb;width:100%">'
                + ''.join(rows_list)
                + '</div>'
            )

    supply_card = f'''<div class="kpi" style="align-items:flex-start">
    <div class="kpi-title" style="width:100%">Total Inventory</div>
    <div class="big-number-md" style="color:var(--primary)">{_fmt(inv_total) if inv_total > 0 else '---'}</div>
    <div class="stat-label" style="margin-top:4px">{'units in stock' if inv_total > 0 else 'Awaiting data'}</div>
    {flavor_rows_html}
  </div>'''

    if is_all:
        kpis = f'''<div class="kpis" style="grid-template-columns:repeat(5,1fr)">
  {sales_card}
  {units_card_kpi}
  {pos_card}
  {creators_card}
  {supply_card}
</div>'''
    else:
        # Distribution — count active distributors
        active_dists = sum(1 for x in [tmy, tic, tbi] if x > 0)
        dist_card = f'''<div class="kpi">
    <div class="kpi-title">Distributors</div>
    <div class="big-number-md">{active_dists}</div>
    <div class="stat-label" style="margin-top:4px">active channels</div>
  </div>'''

        kpis = f'''<div class="kpis" style="grid-template-columns:repeat(5,1fr)">
  {sales_card}
  {units_card_kpi}
  {pos_card}
  {dist_card}
  {supply_card}
</div>'''

    # ── Revenue & Units Charts ──
    units_card = ''
    if is_all and len(month_list) >= 2:
        rev_card = _build_svg_revenue_chart(data, month_list, active_products)
        units_card = _build_svg_units_chart(data, month_list, active_products)
    else:
        rev_card = ''  # Revenue card removed from per-month view

    # ── Summary Table (sorted by revenue desc) ──
    rows_data = []
    for month in month_list:
        md = data['monthly_data'][month]
        mh = MONTH_NAMES_HEB.get(month, month)
        for p in active_products:
            c = md['combined'].get(p, {})
            u = c.get('units', 0)
            if u == 0:
                continue
            disc = PRODUCT_STATUS.get(p) == 'discontinued'
            badge = '<span class="badge disc">Disc.</span>' if disc else (
                '<span class="badge new">New</span>' if PRODUCT_STATUS.get(p) == 'new' else '')
            ds = ' style="color:#999;font-style:italic"' if disc else ''
            val = c.get('total_value', 0)
            row_html = (f'<tr{ds}><td><b>{mh}</b></td><td>{PRODUCT_NAMES.get(p,p)} {badge}</td>'
                        f'<td>{_fmt(c.get("mayyan_units",0))}</td><td>{_fmt(c.get("icedreams_units",0))}</td>'
                        f'<td>{_fmt(c.get("biscotti_units",0))}</td>'
                        f'<td><b>{_fmt(u)}</b></td><td>{_fc(val)}</td></tr>')
            rows_data.append((val, row_html))
    rows_data.sort(key=lambda x: x[0], reverse=True)
    top_rows = '\n'.join(r for _, r in rows_data[:10])
    extra_rows = '\n'.join(r for _, r in rows_data[10:])
    show_more_summary = ''
    if len(rows_data) > 10:
        show_more_summary = (
            f'<tbody id="summary-extra" style="display:none">{extra_rows}</tbody>'
            f'</table>'
            f'<button onclick="var el=document.getElementById(\'summary-extra\');if(el.style.display===\'none\'){{el.style.display=\'table-row-group\';this.textContent=\'Show Less\'}}else{{el.style.display=\'none\';this.textContent=\'Show More ({len(rows_data)-10})\'}}" '
            f'style="display:block;margin:12px auto 0;padding:8px 24px;background:#f1f5f9;border:1px solid #e2e8f0;border-radius:8px;color:#5D5FEF;font-size:13px;font-weight:600;cursor:pointer">'
            f'Show More ({len(rows_data)-10})</button>')
    else:
        show_more_summary = '</table>'

    summary_tbl = (f'<div class="card full" style="margin-bottom:14px"><h3>Detailed Summary - {label}</h3>'
                   f'<table class="tbl"><thead><tr><th>Month</th><th>Product</th><th>Ma\'ayan (units)</th>'
                   f'<th>Icedream (units)</th><th>Biscotti (units)</th><th>Total Units</th><th>Revenue (₪)</th></tr></thead>'
                   f'<tbody>{top_rows}</tbody>'
                   f'{show_more_summary}</div>')

    # ── Icedream Customers (aggregated by chain, sorted by revenue desc) ──
    from config import extract_customer_name
    ice_pl = [p for p in ['chocolate', 'vanilla', 'mango', 'pistachio', 'magadat', 'dream_cake'] if p in active_products]
    ice_h = ''.join(f'<th>{PRODUCT_NAMES[p]} (units)</th>' for p in ice_pl)
    ice_h += ''.join(f'<th>{PRODUCT_NAMES[p]} (₪)</th>' for p in ice_pl)
    ice_rows_data = []
    for month in month_list:
        md = data['monthly_data'][month]
        mh = MONTH_NAMES_HEB.get(month, month)
        # Aggregate branches into chains
        chains = {}
        for cust, pdata in md.get('icedreams_customers', {}).items():
            chain = extract_customer_name(cust)
            if chain not in chains:
                chains[chain] = {}
            for p in ice_pl:
                if p not in chains[chain]:
                    chains[chain][p] = {'units': 0, 'value': 0}
                chains[chain][p]['units'] += pdata.get(p, {}).get('units', 0)
                chains[chain][p]['value'] += pdata.get(p, {}).get('value', 0)
        for chain, pdata in chains.items():
            ctu = sum(pdata.get(p, {}).get('units', 0) for p in ice_pl)
            ctv = sum(pdata.get(p, {}).get('value', 0) for p in ice_pl)
            r = f'<td>{mh}</td><td><b>{chain}</b></td>'
            for p in ice_pl:
                u = pdata.get(p, {}).get('units', 0)
                r += f'<td>{_fmt(u) if u else ""}</td>'
            for p in ice_pl:
                v = pdata.get(p, {}).get('value', 0)
                r += f'<td>{_fc(v) if v else ""}</td>'
            r += f'<td class="tot">{_fmt(ctu)}</td><td class="tot">{_fc(ctv)}</td>'
            ice_rows_data.append((ctv, f'<tr>{r}</tr>'))
    ice_rows_data.sort(key=lambda x: x[0], reverse=True)
    ice_top = '\n'.join(r for _, r in ice_rows_data[:10])
    ice_extra = '\n'.join(r for _, r in ice_rows_data[10:])
    if ice_rows_data:
        show_more_ice = ''
        if len(ice_rows_data) > 10:
            show_more_ice = (
                f'<tbody id="ice-extra" style="display:none">{ice_extra}</tbody>'
                f'</table>'
                f'<button onclick="var el=document.getElementById(\'ice-extra\');if(el.style.display===\'none\'){{el.style.display=\'table-row-group\';this.textContent=\'Show Less\'}}else{{el.style.display=\'none\';this.textContent=\'Show More ({len(ice_rows_data)-10})\'}}" '
                f'style="display:block;margin:12px auto 0;padding:8px 24px;background:#f1f5f9;border:1px solid #e2e8f0;border-radius:8px;color:#5D5FEF;font-size:13px;font-weight:600;cursor:pointer">'
                f'Show More ({len(ice_rows_data)-10})</button>')
        else:
            show_more_ice = '</table>'
        ice_tbl = (f'<div class="card full" style="margin-bottom:14px"><h3>Icedream Customers - By Product</h3>'
                   f'<table class="tbl"><thead><tr><th>Month</th><th>Customer</th>{ice_h}'
                   f'<th>Total Units</th><th>Total ₪</th></tr></thead>'
                   f'<tbody>{ice_top}</tbody>'
                   f'{show_more_ice}</div>')
    else:
        ice_tbl = ''

    # ── Ma'ayan Chains (aggregated by normalized chain name, sorted by revenue desc) ──
    may_pl = [p for p in ['chocolate', 'vanilla', 'mango', 'pistachio'] if p in active_products]
    may_h = ''.join(f'<th>{PRODUCT_NAMES[p]} (units)</th>' for p in may_pl)
    may_h += ''.join(f'<th>{PRODUCT_NAMES[p]} (₪)</th>' for p in may_pl)
    may_rows_data = []
    for month in month_list:
        md = data['monthly_data'][month]
        mh = MONTH_NAMES_HEB.get(month, month)
        cr = md.get('mayyan_accounts_revenue', {})
        # Aggregate accounts by normalized chain name (splits טיב טעם from שוק פרטי, דור אלון into AMPM/אלונית)
        norm_chains = {}
        for key, pdata in cr.items():
            # key is (chain_name, account_name) tuple
            source_chain, acct = key if isinstance(key, tuple) else ('', key)
            norm = extract_customer_name(acct, source_customer=source_chain)
            if norm not in norm_chains:
                norm_chains[norm] = {}
            for p in may_pl:
                if p not in norm_chains[norm]:
                    norm_chains[norm][p] = {'units': 0, 'value': 0}
                pd_ = pdata.get(p, {})
                if isinstance(pd_, dict):
                    norm_chains[norm][p]['units'] += pd_.get('units', 0)
                    norm_chains[norm][p]['value'] += pd_.get('value', 0)
        for chain, pdata in norm_chains.items():
            ctu = sum(pdata.get(p, {}).get('units', 0) for p in may_pl)
            ctv = sum(pdata.get(p, {}).get('value', 0) for p in may_pl)
            if ctu == 0:
                continue
            r = f'<td>{mh}</td><td><b>{chain}</b></td>'
            for p in may_pl:
                u = pdata.get(p, {}).get('units', 0)
                r += f'<td>{_fmt(u) if u else ""}</td>'
            for p in may_pl:
                v = pdata.get(p, {}).get('value', 0)
                r += f'<td>{_fc(v) if v else ""}</td>'
            r += f'<td class="tot">{_fmt(ctu)}</td><td class="tot">{_fc(ctv)}</td>'
            may_rows_data.append((ctv, f'<tr>{r}</tr>'))
    may_rows_data.sort(key=lambda x: x[0], reverse=True)
    may_top = '\n'.join(r for _, r in may_rows_data[:10])
    may_extra = '\n'.join(r for _, r in may_rows_data[10:])
    if may_rows_data:
        show_more_may = ''
        if len(may_rows_data) > 10:
            show_more_may = (
                f'<tbody id="may-extra" style="display:none">{may_extra}</tbody>'
                f'</table>'
                f'<button onclick="var el=document.getElementById(\'may-extra\');if(el.style.display===\'none\'){{el.style.display=\'table-row-group\';this.textContent=\'Show Less\'}}else{{el.style.display=\'none\';this.textContent=\'Show More ({len(may_rows_data)-10})\'}}" '
                f'style="display:block;margin:12px auto 0;padding:8px 24px;background:#f1f5f9;border:1px solid #e2e8f0;border-radius:8px;color:#5D5FEF;font-size:13px;font-weight:600;cursor:pointer">'
                f'Show More ({len(may_rows_data)-10})</button>')
        else:
            show_more_may = '</table>'
        may_tbl = (f'<div class="card full" style="margin-bottom:14px"><h3>Ma\'ayan Chains - By Product</h3>'
                   f'<table class="tbl"><thead><tr><th>Month</th><th>Chain</th>{may_h}'
                   f'<th>Total Units</th><th>Total ₪</th></tr></thead>'
                   f'<tbody>{may_top}</tbody>'
                   f'{show_more_may}</div>')
    else:
        may_tbl = ''

    # ── Biscotti Customers (placeholder or real data) ──
    bisc_pl = [p for p in ['dream_cake_2', 'dream_cake'] if p in active_products]
    bisc_rows_data = []
    for month in month_list:
        md = data['monthly_data'][month]
        mh = MONTH_NAMES_HEB.get(month, month)
        for cust, pdata in md.get('biscotti_customers', {}).items():
            ctu = sum(pdata.get(p, {}).get('units', 0) for p in bisc_pl)
            ctv = sum(pdata.get(p, {}).get('value', 0) for p in bisc_pl)
            if ctu == 0:
                continue
            bisc_h_cols = ''.join(f'<td>{_fmt((pdata.get(p) or {}).get("units", 0))}</td>' for p in bisc_pl)
            bisc_v_cols = ''.join(f'<td>{_fc((pdata.get(p) or {}).get("value", 0))}</td>' for p in bisc_pl)
            r = f'<td>{mh}</td><td><b>{cust}</b></td>{bisc_h_cols}{bisc_v_cols}<td class="tot">{_fmt(ctu)}</td><td class="tot">{_fc(ctv)}</td>'
            bisc_rows_data.append((ctv, f'<tr>{r}</tr>'))
    bisc_rows_data.sort(key=lambda x: x[0], reverse=True)

    if bisc_rows_data:
        bisc_h = ''.join(f'<th>{PRODUCT_NAMES[p]} (units)</th>' for p in bisc_pl)
        bisc_h += ''.join(f'<th>{PRODUCT_NAMES[p]} (₪)</th>' for p in bisc_pl)
        bisc_rows = '\n'.join(r for _, r in bisc_rows_data)
        bisc_tbl = (f'<div class="card full" style="margin-bottom:14px"><h3>Biscotti Customers - By Product</h3>'
                    f'<table class="tbl"><thead><tr><th>Month</th><th>Customer</th>{bisc_h}'
                    f'<th>Total Units</th><th>Total ₪</th></tr></thead>'
                    f'<tbody>{bisc_rows}</tbody></table></div>')
    else:
        # Only show Biscotti placeholder if dream_cake_2 or dream_cake is in active_products
        if 'dream_cake_2' in active_products or 'dream_cake' in active_products:
            bisc_tbl = (f'<div class="card full" style="margin-bottom:14px;border:2px dashed #cbd5e1;background:#f8fafc">'
                        f'<h3 style="color:#64748b">Biscotti (ביסקוטי) — Distribution starts 10 Apr 2026</h3>'
                        f'<p style="color:#94a3b8;font-size:13px;padding:12px 0">Awaiting first reports. '
                        f'Dream Cake (chilled) will be distributed through Biscotti.</p></div>')
        else:
            bisc_tbl = ''

    # ── Top Customers (aggregated by chain) ──
    all_c = {}
    for month in month_list:
        md = data['monthly_data'][month]
        for c, pd in md.get('icedreams_customers', {}).items():
            chain = extract_customer_name(c)
            k = f"Icedream: {chain}"
            all_c[k] = all_c.get(k, 0) + sum(pd.get(p, {}).get('units', 0) for p in active_products)
        for key, pd in md.get('mayyan_accounts_revenue', {}).items():
            source_chain, acct = key if isinstance(key, tuple) else ('', key)
            norm = extract_customer_name(acct, source_customer=source_chain)
            k = f"Ma'ayan: {norm}"
            all_c[k] = all_c.get(k, 0) + sum(pd.get(p, {}).get('units', 0) for p in active_products if isinstance(pd.get(p), dict))
        for cust, pd in md.get('biscotti_customers', {}).items():
            k = f"Biscotti: {cust}"
            all_c[k] = all_c.get(k, 0) + sum(pd.get(p, {}).get('units', 0) for p in active_products if isinstance(pd.get(p), dict))
    all_c = {k: v for k, v in all_c.items() if v > 0}
    tc_list = sorted(all_c.items(), key=lambda x: x[1], reverse=True)[:10]
    mc = tc_list[0][1] if tc_list else 1
    top_bars = _bar_html(tc_list, mc, '#6366f1')
    top_tbl = f'<div class="card full" style="margin-bottom:14px"><h3>Top Customers (units)</h3>{top_bars}</div>' if tc_list else ''

    # Flavor analysis - for all views
    flavor_section = _build_flavor_analysis(data, month_list, is_all, active_products)

    # Inventory section - only in overview
    inv_section = _build_inventory_section(data, active_products) if is_all else ''

    display = 'block' if section_id == 'y2026-ab' else 'none'
    return (f'<div class="month-section" id="sec-{section_id}" style="display:{display}">\n'
            f'{kpis}\n{rev_card}\n{units_card}\n{flavor_section}\n{inv_section}\n{summary_tbl}\n{ice_tbl}\n{may_tbl}\n{bisc_tbl}\n{top_tbl}\n</div>')


BRAND_FILTERS = {
    'ab': {'label': 'All Brands', 'products': ['chocolate', 'vanilla', 'mango', 'dream_cake', 'dream_cake_2', 'magadat', 'pistachio']},
    'turbo': {'label': 'Turbo', 'products': ['chocolate', 'vanilla', 'mango', 'pistachio', 'magadat']},
    'danis': {'label': "Dani's", 'products': ['dream_cake', 'dream_cake_2']},
}

def _build_excel_data_json(data):
    """Build a JSON blob with all dashboard data for client-side Excel export."""
    import json
    from config import extract_customer_name

    months = data['months']
    products_all = ['chocolate', 'vanilla', 'mango', 'pistachio', 'dream_cake', 'dream_cake_2', 'magadat']
    products_turbo = ['chocolate', 'vanilla', 'mango', 'pistachio']

    # Sheet 1: Overview — monthly KPIs
    overview = []
    for month in months:
        md = data['monthly_data'][month]
        total_u = sum(md['combined'].get(p, {}).get('units', 0) for p in products_all)
        total_v = sum(md['combined'].get(p, {}).get('total_value', 0) for p in products_all)
        may_u = sum(md['mayyan'].get(p, {}).get('units', 0) for p in products_all)
        ice_u = sum(md['icedreams'].get(p, {}).get('units', 0) for p in products_all)
        overview.append({
            'month': MONTH_NAMES_HEB.get(month, month),
            'total_u': total_u, 'total_v': round(total_v, 2),
            'may_u': may_u, 'ice_u': ice_u,
        })

    # Sheet 2: Detailed Sales
    detailed = []
    for month in months:
        md = data['monthly_data'][month]
        mh = MONTH_NAMES_HEB.get(month, month)
        for p in products_all:
            c = md['combined'].get(p, {})
            u = c.get('units', 0)
            if u == 0:
                continue
            detailed.append({
                'month': mh, 'product': PRODUCT_NAMES.get(p, p),
                'may_u': c.get('mayyan_units', 0), 'ice_u': c.get('icedreams_units', 0),
                'total_u': u, 'revenue': round(c.get('total_value', 0), 2),
            })

    # Sheet 3: Icedream Customers
    ice_pl = ['chocolate', 'vanilla', 'mango', 'pistachio', 'magadat', 'dream_cake']
    ice_customers = []
    for month in months:
        md = data['monthly_data'][month]
        mh = MONTH_NAMES_HEB.get(month, month)
        chains = {}
        for cust, pdata in md.get('icedreams_customers', {}).items():
            chain = extract_customer_name(cust)
            if chain not in chains:
                chains[chain] = {}
            for p in ice_pl:
                if p not in chains[chain]:
                    chains[chain][p] = {'units': 0, 'value': 0}
                chains[chain][p]['units'] += pdata.get(p, {}).get('units', 0)
                chains[chain][p]['value'] += pdata.get(p, {}).get('value', 0)
        sorted_chains = sorted(chains.items(),
                               key=lambda x: sum(v.get('value', 0) for v in x[1].values()), reverse=True)
        for chain, pdata in sorted_chains:
            ctu = sum(pdata.get(p, {}).get('units', 0) for p in ice_pl)
            if ctu == 0:
                continue
            ctv = sum(pdata.get(p, {}).get('value', 0) for p in ice_pl)
            row = {'month': mh, 'customer': chain}
            for p in ice_pl:
                row[f'{p}_u'] = pdata.get(p, {}).get('units', 0)
                row[f'{p}_v'] = round(pdata.get(p, {}).get('value', 0), 2)
            row['total_u'] = ctu
            row['total_v'] = round(ctv, 2)
            ice_customers.append(row)

    # Sheet 4: Ma'ayan Chains
    may_pl = ['chocolate', 'vanilla', 'mango', 'pistachio']
    may_chains = []
    for month in months:
        md = data['monthly_data'][month]
        mh = MONTH_NAMES_HEB.get(month, month)
        cr = md.get('mayyan_accounts_revenue', {})
        norm_chains = {}
        for key, pdata in cr.items():
            source_chain, acct = key if isinstance(key, tuple) else ('', key)
            norm = extract_customer_name(acct, source_customer=source_chain)
            if norm not in norm_chains:
                norm_chains[norm] = {}
            for p in may_pl:
                if p not in norm_chains[norm]:
                    norm_chains[norm][p] = {'units': 0, 'value': 0}
                pd_ = pdata.get(p, {})
                if isinstance(pd_, dict):
                    norm_chains[norm][p]['units'] += pd_.get('units', 0)
                    norm_chains[norm][p]['value'] += pd_.get('value', 0)
        sorted_chains = sorted(norm_chains.items(),
                               key=lambda x: sum(v.get('value', 0) for v in x[1].values()), reverse=True)
        for chain, pdata in sorted_chains:
            ctu = sum(pdata.get(p, {}).get('units', 0) for p in may_pl)
            if ctu == 0:
                continue
            ctv = sum(pdata.get(p, {}).get('value', 0) for p in may_pl)
            row = {'month': mh, 'chain': chain}
            for p in may_pl:
                row[f'{p}_u'] = pdata.get(p, {}).get('units', 0)
                row[f'{p}_v'] = round(pdata.get(p, {}).get('value', 0), 2)
            row['total_u'] = ctu
            row['total_v'] = round(ctv, 2)
            may_chains.append(row)

    # Sheet 5: Inventory
    wh = data.get('warehouse', {})
    dist_inv = data.get('dist_inv', {})
    wh_products = wh.get('products', {})
    prod_order = ['chocolate', 'vanilla', 'mango', 'pistachio', 'magadat', 'dream_cake']
    inventory = []
    for p in prod_order:
        wh_u = wh_products.get(p, {}).get('units', 0)
        ice_u = dist_inv.get('icedream', {}).get('products', {}).get(p, {}).get('units', 0)
        may_u = dist_inv.get('mayyan', {}).get('products', {}).get(p, {}).get('units', 0)
        total_u = wh_u + ice_u + may_u
        if total_u == 0:
            continue
        is_dc = p == 'dream_cake'
        inventory.append({
            'product': PRODUCT_NAMES.get(p, p),
            'wh_u': wh_u, 'wh_p': round(wh_u / 2400, 1) if not is_dc and wh_u else None,
            'ice_u': ice_u, 'ice_p': round(ice_u / 2400, 1) if not is_dc and ice_u else None,
            'may_u': may_u, 'may_p': round(may_u / 2400, 1) if not is_dc and may_u else None,
            'total_u': total_u, 'total_p': round(total_u / 2400, 1) if not is_dc else None,
        })

    # Sheet 6: Top Customers
    all_c = {}
    for month in months:
        md = data['monthly_data'][month]
        for c, pd in md.get('icedreams_customers', {}).items():
            chain = extract_customer_name(c)
            k = f"Icedream: {chain}"
            all_c[k] = all_c.get(k, 0) + sum(pd.get(p, {}).get('units', 0) for p in products_all)
        for key, pd in md.get('mayyan_accounts_revenue', {}).items():
            source_chain, acct = key if isinstance(key, tuple) else ('', key)
            norm = extract_customer_name(acct, source_customer=source_chain)
            k = f"Ma'ayan: {norm}"
            all_c[k] = all_c.get(k, 0) + sum(pd.get(p, {}).get('units', 0) for p in products_all if isinstance(pd.get(p), dict))
    all_c = {k: v for k, v in all_c.items() if v > 0}
    tc_list = sorted(all_c.items(), key=lambda x: x[1], reverse=True)[:20]
    grand = sum(v for _, v in tc_list)
    top_customers = [{'rank': i+1, 'name': n, 'units': u, 'share': round(u/grand, 4) if grand else 0}
                     for i, (n, u) in enumerate(tc_list)]

    # Product short names for headers
    ps = {p: PRODUCT_NAMES.get(p, p) for p in products_all}

    return json.dumps({
        'overview': overview, 'detailed': detailed,
        'ice_customers': ice_customers, 'may_chains': may_chains,
        'inventory': inventory, 'top_customers': top_customers,
        'product_names': ps,
        'ice_pl': ice_pl, 'may_pl': may_pl,
    }, ensure_ascii=False)


def generate_dashboard(data):
    """Generate static HTML dashboard with month + brand filters."""
    months = data['months']
    now_str = datetime.now().strftime('%d/%m/%Y %H:%M')

    # Compute last data update date from all sources
    last_update_dates = []
    wh = data.get('warehouse', {})
    if wh and wh.get('report_date'):
        last_update_dates.append(wh['report_date'])
    for dist_key, dist_data in data.get('dist_inv', {}).items():
        if dist_data.get('report_date'):
            last_update_dates.append(dist_data['report_date'])
    last_update = last_update_dates[0] if last_update_dates else now_str

    # Build Excel data JSON for export button
    excel_json = _build_excel_data_json(data)

    # ── Year filter setup ──
    # Group months by year
    year_months = {}  # {year_str: [month_keys]}
    for m in months:
        year = m.split()[-1]  # e.g. "2025" from "December 2025"
        year_months.setdefault(year, []).append(m)
    years_sorted = sorted(year_months.keys())

    # Build year filter buttons
    year_btn_html = ''
    year_btn_html += f'<button class="fbtn year-btn fbtn-active" onclick="setYear(\'all\')">All Years</button>\n'
    for yr in years_sorted:
        year_btn_html += f'<button class="fbtn year-btn" onclick="setYear(\'{yr}\')">{yr}</button>\n'

    # Build month filter buttons (each has data-year attribute)
    filter_ids = ['all'] + [f'm{i}' for i in range(len(months))]
    filter_labels = ['Overview'] + [MONTH_NAMES_HEB.get(m, m) for m in months]
    month_btn_html = ''
    for fid, flabel in zip(filter_ids, filter_labels):
        active = ' fbtn-active' if fid == 'all' else ''
        if fid == 'all':
            year_attr = 'all'
        else:
            idx = int(fid[1:])
            year_attr = months[idx].split()[-1]
        month_btn_html += f'<button class="fbtn month-btn{active}" data-year="{year_attr}" onclick="setMonth(\'{fid}\')">{flabel}</button>\n'

    # Build brand filter buttons
    brand_btn_html = ''
    for bid, binfo in BRAND_FILTERS.items():
        active = ' fbtn-active' if bid == 'ab' else ''
        brand_btn_html += f'<button class="fbtn brand-btn{active}" onclick="setBrand(\'{bid}\')">{binfo["label"]}</button>\n'

    btn_html = (f'<span>Year:</span> {year_btn_html}'
                f'<span style="margin-left:16px">Period:</span> {month_btn_html}'
                f'<span style="margin-left:16px">Brand:</span> {brand_btn_html}')

    # Build sections: one per (period × brand) combination
    # Periods: 'all' (all months overview), 'y{year}' (year overview), 'm{i}' (individual month)
    sections = ''

    # Year-specific overviews
    year_overview_ids = {}
    for yr in years_sorted:
        yr_months = year_months[yr]
        for bid, binfo in BRAND_FILTERS.items():
            sec_id = f'y{yr}-{bid}'
            active_products = binfo['products']
            sections += _build_month_section(data, yr_months, sec_id, active_products)
        year_overview_ids[yr] = f'y{yr}'

    # All months overview + individual months
    for fid, _ in zip(filter_ids, filter_labels):
        if fid == 'all':
            month_list = months
        else:
            idx = int(fid[1:])
            month_list = [months[idx]]
        for bid, binfo in BRAND_FILTERS.items():
            sec_id = f'{fid}-{bid}'
            active_products = binfo['products']
            sections += _build_month_section(data, month_list, sec_id, active_products)

    # Build year→overview mapping for JS
    import json as _json
    year_overview_map_json = _json.dumps(year_overview_ids)

    html = f"""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Raito Business Overview</title>
<style>
:root {{ --bg:#f0f2f5; --card:#fff; --text:#1a1a2e; --text2:#555; --border:#e0e0e0; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Segoe UI',Tahoma,sans-serif; background:var(--bg); color:var(--text); direction:ltr; }}
.hdr {{ background:linear-gradient(135deg,#1e3a5f,#2563eb); color:#fff; padding:20px 32px; }}
.hdr h1 {{ font-size:22px; }} .hdr .sub {{ opacity:.8; font-size:13px; margin-top:4px; }}
.hdr .brands {{ display:flex; gap:24px; margin-top:8px; font-size:12px; opacity:.7; }}
.fbar {{ background:var(--card); padding:12px 32px; border-bottom:1px solid var(--border); display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
.fbar span {{ font-weight:600; font-size:13px; margin-left:8px; }}
.fbtn {{ padding:7px 16px; border:1px solid var(--border); border-radius:8px; background:#fff; font-size:13px; cursor:pointer; font-family:inherit; }}
.fbtn:hover {{ background:#e8f0fe; }}
.fbtn-active {{ background:#2563eb; color:#fff; border-color:#2563eb; }}
.ctr {{ max-width:1440px; margin:0 auto; padding:20px; }}
.kpis {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:20px; }}
.kpi {{ background:var(--card); border-radius:10px; padding:16px; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
.kpi .l {{ font-size:12px; color:var(--text2); margin-bottom:6px; }}
.kpi .v {{ font-size:24px; font-weight:700; }}
.kpi-title {{ font-size:16px; font-weight:700; color:#1e3a5f; margin-bottom:10px; border-bottom:2px solid #2563eb; padding-bottom:5px; text-align:center; }}
.kpi .v.green {{ color:#10b981; }} .kpi .v.blue {{ color:#2563eb; }}
.card {{ background:var(--card); border-radius:10px; padding:16px; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
.card.full {{ width:100%; }}
.card h3 {{ font-size:14px; margin-bottom:10px; color:#1e3a5f; }}
.tbl {{ width:100%; border-collapse:collapse; font-size:12px; margin-top:8px; }}
.tbl th {{ background:#2C3E50; color:#fff; padding:8px 6px; text-align:center; font-weight:600; }}
.tbl td {{ padding:6px; text-align:center; border-bottom:1px solid var(--border); }}
.tbl tr:hover {{ background:#f8f9fa; }}
.tbl .tot {{ font-weight:700; background:#f0f0f0; }}
.badge {{ display:inline-block; padding:1px 6px; border-radius:8px; font-size:10px; font-weight:600; }}
.badge.disc {{ background:#fee2e2; color:#dc2626; }}
.badge.new {{ background:#d1fae5; color:#059669; }}
.notes {{ background:var(--card); border-radius:10px; padding:16px; margin-top:12px; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
.notes h3 {{ margin-bottom:6px; font-size:14px; }} .notes ul {{ padding-left:18px; font-size:13px; color:var(--text2); }} .notes li {{ margin-bottom:3px; }}
.ts {{ text-align:center; padding:12px; color:var(--text2); font-size:11px; }}
@media (max-width:900px) {{ .kpis {{ grid-template-columns:repeat(2,1fr); }} }}
</style>
</head>
<body>
<div class="hdr" style="display:flex;justify-content:space-between;align-items:flex-start">
  <div>
    <h1>Raito Business Overview</h1>
    <div class="sub">Inventory, Sales &amp; Distribution | Last updated: {last_update}</div>
    <div class="brands">
      <span>Turbo Ice Cream | Danny Avdia</span>
      <span>Dani's Dream Cake | Daniel Amit</span>
      <span>Distributors: Icedream | Ma'ayan | Biscotti</span>
    </div>
  </div>
  <button onclick="exportToExcel()" style="background:#10b981;color:#fff;border:none;padding:10px 20px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap;margin-top:4px">&#x1F4E5; Export Excel</button>
</div>
<div class="fbar">
  <span>View:</span>
  {btn_html}
</div>
<div class="ctr">
  {sections}
  <div class="notes"><h3>Notes</h3><ul>
    <li><span class="badge disc">Disc.</span> Turbo Magadat - sold until stock runs out</li>
    <li><span class="badge new">New</span> Turbo Pistachio - launching Feb 2026</li>
    <li>Dani's Dream Cake - switched to Biscotti distribution from 1.3.2026</li>
    <li><span class="badge new">New</span> Dream Cake Biscotti (chilled) - launching 10 Apr 2026, distributed by Biscotti</li>
  </ul></div>
  <div class="ts">Auto-generated | {now_str}</div>
</div>
<script>
var curYear='all', curMonth='all', curBrand='ab';
var yearOverviewMap={year_overview_map_json};
function updateView(){{
  document.querySelectorAll('.month-section').forEach(function(s){{s.style.display='none';}});
  // Determine which section to show
  var secId;
  if(curMonth==='all' && curYear!=='all'){{
    // Year overview
    secId=yearOverviewMap[curYear]+'-'+curBrand;
  }} else {{
    secId=curMonth+'-'+curBrand;
  }}
  var el=document.getElementById('sec-'+secId);
  if(el) el.style.display='block';
}}
function setYear(yr){{
  curYear=yr;
  document.querySelectorAll('.year-btn').forEach(function(b){{b.classList.remove('fbtn-active');}});
  event.target.classList.add('fbtn-active');
  // Show/hide month buttons based on year
  document.querySelectorAll('.month-btn').forEach(function(b){{
    var btnYear=b.getAttribute('data-year');
    if(yr==='all'||btnYear==='all'||btnYear===yr){{
      b.style.display='';
    }} else {{
      b.style.display='none';
    }}
  }});
  // Reset to Overview for the selected year
  curMonth='all';
  document.querySelectorAll('.month-btn').forEach(function(b){{b.classList.remove('fbtn-active');}});
  var ovBtn=document.querySelector('.month-btn[data-year="all"]');
  if(ovBtn) ovBtn.classList.add('fbtn-active');
  updateView();
}}
function setMonth(id){{
  curMonth=id;
  document.querySelectorAll('.month-btn').forEach(function(b){{b.classList.remove('fbtn-active');}});
  event.target.classList.add('fbtn-active');
  updateView();
}}
function setBrand(id){{
  curBrand=id;
  document.querySelectorAll('.brand-btn').forEach(function(b){{b.classList.remove('fbtn-active');}});
  event.target.classList.add('fbtn-active');
  updateView();
}}
</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
<script>
var _D={excel_json};
function exportToExcel(){{
  if(typeof XLSX==='undefined'){{alert('SheetJS library not loaded. Check internet connection.');return;}}
  var wb=XLSX.utils.book_new();
  var nf='#,##0',cf='₪#,##0',pf='0%';
  function tc(v,t,z){{var c={{v:v,t:t||'s'}};if(z)c.z=z;return c;}}
  function n(v,z){{return tc(v,'n',z||nf);}}

  // Sheet 1: Overview
  var ov=_D.overview;
  var s1=[
    [tc('Raito Business Overview','s'),null,null,null,null,null,null],
    [],
    [tc('Month'),tc('Total Units'),tc('Total Revenue (₪)'),tc("Ma'ayan Units"),tc('Icedream Units'),tc("Ma'ayan %"),tc('Icedream %')]
  ];
  var tu=0,tv=0,mu=0,iu=0;
  ov.forEach(function(r){{
    var td=r.total_u||1;
    s1.push([tc(r.month),n(r.total_u),n(r.total_v,cf),n(r.may_u),n(r.ice_u),
      n(r.may_u/td,'0%'),n(r.ice_u/td,'0%')]);
    tu+=r.total_u;tv+=r.total_v;mu+=r.may_u;iu+=r.ice_u;
  }});
  s1.push([tc('Total'),n(tu),n(tv,cf),n(mu),n(iu),n(tu?mu/tu:0,'0%'),n(tu?iu/tu:0,'0%')]);
  var ws1=XLSX.utils.aoa_to_sheet(s1);
  ws1['!cols']=[{{wch:16}},{{wch:14}},{{wch:18}},{{wch:16}},{{wch:16}},{{wch:13}},{{wch:13}}];
  XLSX.utils.book_append_sheet(wb,ws1,'Overview');

  // Sheet 2: Detailed Sales
  var dt=_D.detailed;
  var s2=[[tc('Detailed Sales by Product & Month')],[],
    [tc('Month'),tc('Product'),tc("Ma'ayan (units)"),tc('Icedream (units)'),tc('Total Units'),tc('Revenue (₪)')]];
  dt.forEach(function(r){{
    s2.push([tc(r.month),tc(r.product),n(r.may_u),n(r.ice_u),n(r.total_u),n(r.revenue,cf)]);
  }});
  var ws2=XLSX.utils.aoa_to_sheet(s2);
  ws2['!cols']=[{{wch:14}},{{wch:22}},{{wch:16}},{{wch:16}},{{wch:14}},{{wch:16}}];
  XLSX.utils.book_append_sheet(wb,ws2,'Detailed Sales');

  // Sheet 3: Icedream Customers
  var ic=_D.ice_customers,ipl=_D.ice_pl,ps=_D.product_names;
  var h3=[tc('Month'),tc('Customer')];
  ipl.forEach(function(p){{h3.push(tc(ps[p]+' (units)'));}});
  ipl.forEach(function(p){{h3.push(tc(ps[p]+' (₪)'));}});
  h3.push(tc('Total Units'));h3.push(tc('Total ₪'));
  var s3=[[tc('Icedream Customers - By Product')],[],h3];
  ic.forEach(function(r){{
    var row=[tc(r.month),tc(r.customer)];
    ipl.forEach(function(p){{row.push(n(r[p+'_u']||0));}});
    ipl.forEach(function(p){{row.push(n(r[p+'_v']||0,cf));}});
    row.push(n(r.total_u));row.push(n(r.total_v,cf));
    s3.push(row);
  }});
  var ws3=XLSX.utils.aoa_to_sheet(s3);
  XLSX.utils.book_append_sheet(wb,ws3,'Icedream Customers');

  // Sheet 4: Ma'ayan Chains
  var mc=_D.may_chains,mpl=_D.may_pl;
  var h4=[tc('Month'),tc('Chain')];
  mpl.forEach(function(p){{h4.push(tc(ps[p]+' (units)'));}});
  mpl.forEach(function(p){{h4.push(tc(ps[p]+' (₪)'));}});
  h4.push(tc('Total Units'));h4.push(tc('Total ₪'));
  var s4=[[tc("Ma'ayan Chains - By Product")],[],h4];
  mc.forEach(function(r){{
    var row=[tc(r.month),tc(r.chain)];
    mpl.forEach(function(p){{row.push(n(r[p+'_u']||0));}});
    mpl.forEach(function(p){{row.push(n(r[p+'_v']||0,cf));}});
    row.push(n(r.total_u));row.push(n(r.total_v,cf));
    s4.push(row);
  }});
  var ws4=XLSX.utils.aoa_to_sheet(s4);
  XLSX.utils.book_append_sheet(wb,ws4,"Ma'ayan Chains");

  // Sheet 5: Inventory
  var inv=_D.inventory;
  var s5=[[tc('Total Available Stock — All Locations')],[],
    [tc('Product'),tc('Karfree (units)'),tc('Karfree (pallets)'),
     tc('Icedream (units)'),tc('Icedream (pallets)'),
     tc("Ma'ayan (units)"),tc("Ma'ayan (pallets)"),
     tc('Total Units'),tc('Total Pallets')]];
  var gt=0,gp=0;
  inv.forEach(function(r){{
    s5.push([tc(r.product),n(r.wh_u),r.wh_p!=null?n(r.wh_p,'0.0'):tc('-'),
      n(r.ice_u),r.ice_p!=null?n(r.ice_p,'0.0'):tc('-'),
      n(r.may_u),r.may_p!=null?n(r.may_p,'0.0'):tc('-'),
      n(r.total_u),r.total_p!=null?n(r.total_p,'0.0'):tc('-')]);
    gt+=r.total_u; if(r.total_p)gp+=r.total_p;
  }});
  var wht=0,ict=0,mt=0;inv.forEach(function(r){{wht+=r.wh_u;ict+=r.ice_u;mt+=r.may_u;}});
  s5.push([tc('Total'),n(wht),n(+(wht/2400).toFixed(1),'0.0'),
    n(ict),n(+(ict/2400).toFixed(1),'0.0'),
    n(mt),n(+(mt/2400).toFixed(1),'0.0'),
    n(gt),n(+gp.toFixed(1),'0.0')]);
  var ws5=XLSX.utils.aoa_to_sheet(s5);
  ws5['!cols']=[{{wch:22}},{{wch:16}},{{wch:14}},{{wch:16}},{{wch:14}},{{wch:16}},{{wch:14}},{{wch:16}},{{wch:14}}];
  XLSX.utils.book_append_sheet(wb,ws5,'Inventory');

  // Sheet 6: Top Customers
  var tcs=_D.top_customers;
  var s6=[[tc('Top Customers (All Months, by Units)')],[],
    [tc('Rank'),tc('Customer'),tc('Total Units'),tc('Share')]];
  tcs.forEach(function(r){{
    s6.push([n(r.rank),tc(r.name),n(r.units),n(r.share,'0%')]);
  }});
  var ws6=XLSX.utils.aoa_to_sheet(s6);
  ws6['!cols']=[{{wch:8}},{{wch:30}},{{wch:16}},{{wch:12}}];
  XLSX.utils.book_append_sheet(wb,ws6,'Top Customers');

  var d=new Date();
  var fn='Raito_Business_Overview_'+d.getDate()+'.'+(d.getMonth()+1)+'.'+d.getFullYear()+'.xlsx';
  XLSX.writeFile(wb,fn);
}}
</script>
</body></html>"""

    out = OUTPUT_DIR / 'dashboard.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Dashboard saved: {out}")
    return out
