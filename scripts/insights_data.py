"""
insights_data.py — Extract all Raito data for the weekly insights deck.
Outputs a JSON-serialisable dict with monthly + weekly numbers, WoW deltas, and auto-generated highlights.
Usage: python3 scripts/insights_data.py  →  prints JSON
       or: from scripts.insights_data import get_insights_data
"""

import sys, re, json, io
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

# Redirect stdout → stderr while importing parsers so progress lines
# don't corrupt the JSON we emit on stdout.
_real_stdout = sys.stdout
sys.stdout = sys.stderr
from parsers import consolidate_data
sys.stdout = _real_stdout

SHEKEL = "₪"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _read_cc_source():
    p = ROOT / 'dashboards' / 'customer centric dashboard 11.3.26.html'
    return p.read_text(encoding='utf-8')

def _extract_js_array(src, name):
    m = re.search(rf'const {name}\s*=\s*(\[[^\]]+\])', src)
    return eval(m.group(1)) if m else []

def _extract_js_dict(src, name):
    m = re.search(rf'const {name}\s*=\s*(\{{[^}}]+\}})', src)
    if not m: return {}
    s = re.sub(r'(\d+):', r'"\1":', m.group(1))
    try:
        return json.loads(s)
    except Exception:
        return {}

def pct_change(new, old):
    if not old: return None
    return round((new - old) / old * 100, 1)

def fmt_pct(v):
    if v is None: return "N/A"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}%"

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def get_insights_data():
    src   = _read_cc_source()
    sys.stdout = sys.stderr
    pdata = consolidate_data()
    sys.stdout = _real_stdout

    # ── Weekly arrays from CC dashboard ──────────────────────────────────────
    labels   = _extract_js_array(src, 'weeklyXLabels')
    ice_rev  = _extract_js_array(src, '_iceWkRev')
    ice_u    = _extract_js_array(src, '_iceWkUnits')
    maay_rev = _extract_js_dict(src, '_maayWkRev')
    maay_u   = _extract_js_dict(src, '_maayWkUnits')

    weeks = []
    for i, lbl in enumerate(labels):
        w   = i + 1
        ir  = ice_rev[i]  if i < len(ice_rev)  else 0
        iu  = ice_u[i]    if i < len(ice_u)     else 0
        mr  = maay_rev.get(str(w), 0) or 0
        mu  = maay_u.get(str(w), 0)   or 0
        weeks.append({
            'week': w, 'label': lbl,
            'ice_units': iu, 'ice_rev': ir,
            'maay_units': mu, 'maay_rev': mr,
            'total_units': iu + mu,
            'total_rev': ir + mr,
        })

    # ── Current + previous week ───────────────────────────────────────────────
    cur  = weeks[-1]
    prev = weeks[-2] if len(weeks) >= 2 else None

    wow_units = pct_change(cur['total_units'], prev['total_units']) if prev else None
    wow_rev   = pct_change(cur['total_rev'],   prev['total_rev'])   if prev else None
    wow_ice_u = pct_change(cur['ice_units'],   prev['ice_units'])   if prev else None
    wow_maay_u= pct_change(cur['maay_units'],  prev['maay_units'])  if prev else None

    # ── Monthly data ──────────────────────────────────────────────────────────
    months = []
    for m_name in pdata['months']:
        md = pdata['monthly_data'][m_name]
        comb = md.get('combined', {})
        total_u   = sum(v.get('units', 0)       for v in comb.values())
        total_rev = sum(v.get('total_value', 0)  for v in comb.values())
        total_gm  = sum(v.get('gross_margin', 0) for v in comb.values())
        ice_u_m   = sum(v.get('icedreams_units', 0) for v in comb.values())
        maay_u_m  = sum(v.get('mayyan_units', 0)    for v in comb.values())
        months.append({
            'month': m_name,
            'short': m_name.split()[0][:3].upper(),   # DEC, JAN, FEB, MAR
            'total_units': total_u,
            'total_rev': round(total_rev, 0),
            'gross_margin': round(total_gm, 0),
            'ice_units': ice_u_m,
            'maay_units': maay_u_m,
        })

    # ── Flavor mix for current month ─────────────────────────────────────────
    latest_month = pdata['monthly_data'].get(pdata['months'][-1], {})
    comb_latest  = latest_month.get('combined', {})
    FLAVOR_LABELS = {'chocolate': 'Chocolate', 'vanilla': 'Vanilla',
                     'mango': 'Mango', 'pistachio': 'Pistachio', 'dream_cake': 'Dream Cake'}
    flavor_mix = []
    for key, label in FLAVOR_LABELS.items():
        v = comb_latest.get(key, {})
        u = v.get('units', 0)
        if u > 0:
            flavor_mix.append({'flavor': label, 'units': u,
                                'ice_units': v.get('icedreams_units', 0),
                                'maay_units': v.get('mayyan_units', 0)})
    flavor_mix.sort(key=lambda x: -x['units'])

    # ── Inventory snapshot ────────────────────────────────────────────────────
    inv = pdata.get('dist_inv', {})
    wh  = pdata.get('warehouse', {})
    ice_stock  = inv.get('icedream', {}).get('total_units', 0)
    maay_stock = inv.get('mayyan', {}).get('total_units', 0)
    karf_stock = wh.get('total_units', 0) if wh else 0

    # ── Auto-generated highlights ─────────────────────────────────────────────
    highlights = []

    # WoW trend
    if wow_units is not None:
        direction = "▲" if wow_units > 0 else "▼"
        highlights.append(f"{direction} Weekly units {fmt_pct(wow_units)} vs W{cur['week']-1} "
                           f"({cur['total_units']:,} vs {prev['total_units']:,})")
    if wow_rev is not None:
        direction = "▲" if wow_rev > 0 else "▼"
        highlights.append(f"{direction} Weekly revenue {fmt_pct(wow_rev)} vs W{cur['week']-1} "
                           f"(₪{cur['total_rev']:,.0f} vs ₪{prev['total_rev']:,.0f})")

    # Distributor split this week
    total_this = cur['total_units']
    if total_this > 0 and cur['maay_units'] > 0:
        ice_share  = round(cur['ice_units']  / total_this * 100)
        maay_share = round(cur['maay_units'] / total_this * 100)
        highlights.append(f"Distributor split: Icedream {ice_share}% · Ma'ayan {maay_share}%")
    elif cur['maay_units'] == 0:
        highlights.append(f"Ma'ayan W{cur['week']} data pending — split shown from Icedream only")

    # Top flavor this month
    if flavor_mix:
        top = flavor_mix[0]
        highlights.append(f"Top flavor ({pdata['months'][-1].split()[0]}): {top['flavor']} "
                           f"with {top['units']:,} units")

    # MoM revenue trend
    if len(months) >= 2:
        mom = pct_change(months[-1]['total_rev'], months[-2]['total_rev'])
        if mom is not None:
            direction = "▲" if mom > 0 else "▼"
            highlights.append(f"{direction} Monthly revenue {fmt_pct(mom)} vs prior month "
                               f"(₪{months[-1]['total_rev']:,.0f} vs ₪{months[-2]['total_rev']:,.0f})")

    # Stock note
    highlights.append(f"Stock on hand: Icedream {ice_stock:,}u · Ma'ayan {maay_stock:,}u · "
                       f"Karfree {karf_stock:,}u")

    # ── Last 6 weeks for trend chart ─────────────────────────────────────────
    trend_weeks = weeks[-6:]

    # Revenue-per-unit per week (Icedream only, for trend)
    for w in trend_weeks:
        w['ice_rpu'] = round(w['ice_rev'] / w['ice_units'], 2) if w['ice_units'] else 0

    # ── Channel breakdown — current week (from weeklyDetail JS var) ───────────
    # weeklyDetail is the live per-branch array populated for the latest week
    wd_match = re.search(r'const weeklyDetail\s*=\s*(\[.*?\]);', src, re.DOTALL)
    channel_breakdown = []
    if wd_match:
        raw_wd = wd_match.group(1)
        # Extract all {network, product, units, revenue} objects via regex
        entries = re.findall(
            r'\{[^}]*network\s*:\s*["\']([^"\']+)["\'][^}]*units\s*:\s*(\d+)[^}]*\}',
            raw_wd)
        net_totals = {}
        for net, u in entries:
            net_totals[net] = net_totals.get(net, 0) + int(u)
        channel_breakdown = sorted(
            [{'network': k, 'units': v} for k, v in net_totals.items()],
            key=lambda x: -x['units'])
        # Compute percentages
        cb_total = sum(c['units'] for c in channel_breakdown)
        for c in channel_breakdown:
            c['pct'] = round(c['units'] / cb_total * 100, 1) if cb_total else 0

    # ── Icedream-focused highlights ───────────────────────────────────────────
    # Replace generic highlights with Icedream-focus when Ma'ayan is pending
    if cur['maay_units'] == 0:
        ice_highlights = []
        wk = cur['week']

        # Icedream WoW
        if prev:
            ice_wow = pct_change(cur['ice_units'], prev['ice_units'])
            direction = "▲" if ice_wow and ice_wow > 0 else "▼"
            ice_highlights.append(
                f"{direction} Icedream units {fmt_pct(ice_wow)} vs W{wk-1} "
                f"({cur['ice_units']:,} vs {prev['ice_units']:,})")
            ice_rev_wow = pct_change(cur['ice_rev'], prev['ice_rev'])
            direction = "▲" if ice_rev_wow and ice_rev_wow > 0 else "▼"
            ice_highlights.append(
                f"{direction} Icedream revenue {fmt_pct(ice_rev_wow)} vs W{wk-1} "
                f"(₪{cur['ice_rev']:,} vs ₪{prev['ice_rev']:,})")

        # Top channel
        if channel_breakdown:
            top_ch = channel_breakdown[0]
            ice_highlights.append(
                f"Top channel W{wk}: {top_ch['network']} — {top_ch['units']:,}u ({top_ch['pct']}% of Icedream)")

        # Dream Cake revenue share
        dc = next((f for f in flavor_mix if f['flavor'] == 'Dream Cake'), None)
        if dc and dc['ice_units'] > 0:
            # Estimate W12 DC revenue: use rpu from trend
            cur_rpu = trend_weeks[-1]['ice_rpu']
            # From monthly flavor mix, DC is ice_units for month; estimate roughly
            ice_highlights.append(
                f"Dream Cake: {dc['ice_units']:,}u this month — highest revenue/unit in Icedream lineup")

        # Stock cover scenarios
        ice_wkly_avg = sum(w['ice_units'] for w in trend_weeks[-3:]) / 3
        cover_avg = round(ice_stock / ice_wkly_avg, 1) if ice_wkly_avg else 0
        cover_w12 = round(ice_stock / cur['ice_units'], 1) if cur['ice_units'] else 0
        ice_highlights.append(
            f"Icedream stock {ice_stock:,}u: ~{cover_avg}w cover at recent avg · ~{cover_w12}w at W{wk} pace")
        ice_highlights.append(
            f"Karfree warehouse {karf_stock:,}u · Ma'ayan stock {maay_stock:,}u")

        highlights = ice_highlights
        # Keep pending note
        highlights.insert(2, f"Ma'ayan W{wk} data pending — Icedream-only week")

    # ── Stock projection scenarios ────────────────────────────────────────────
    # Conservative = avg of two slowest recent weeks (W10+W11)
    slow_avg   = round((trend_weeks[-3]['ice_units'] + trend_weeks[-2]['ice_units']) / 2)
    # March weekly avg
    mar_avg    = round(sum(w['ice_units'] for w in trend_weeks[-3:]) / 3)
    # Current week pace
    cur_pace   = cur['ice_units']
    stock_scenarios = [
        {'label': f'Slow (W{cur["week"]-2}/W{cur["week"]-1} avg)', 'rate': slow_avg,
         'weeks': round(ice_stock / slow_avg, 1) if slow_avg else None},
        {'label': 'March avg', 'rate': mar_avg,
         'weeks': round(ice_stock / mar_avg, 1) if mar_avg else None},
        {'label': f'W{cur["week"]} pace', 'rate': cur_pace,
         'weeks': round(ice_stock / cur_pace, 1) if cur_pace else None},
    ]
    # Karfree combined
    monthly_avg_combined = round(sum(m['total_units'] for m in months[:-1]) / max(len(months)-1, 1))
    karf_cover_months = round(karf_stock / monthly_avg_combined, 1) if monthly_avg_combined else None

    return {
        'current_week': cur,
        'prev_week': prev,
        'wow_units': wow_units,
        'wow_rev': wow_rev,
        'wow_ice_units': wow_ice_u,
        'wow_maay_units': wow_maay_u,
        'trend_weeks': trend_weeks,
        'months': months,
        'flavor_mix': flavor_mix,
        'current_month': pdata['months'][-1],
        'highlights': highlights,
        'inventory': {
            'icedream': ice_stock,
            'maayan': maay_stock,
            'karfree': karf_stock,
        },
        'channel_breakdown': channel_breakdown[:6],   # top 6 channels
        'stock_scenarios': stock_scenarios,
        'karf_cover_months': karf_cover_months,
        'monthly_avg_combined': monthly_avg_combined,
    }


if __name__ == '__main__':
    import os
    os.chdir(ROOT)
    d = get_insights_data()
    print(json.dumps(d, ensure_ascii=False, indent=2))
