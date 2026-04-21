#!/usr/bin/env python3
"""
Raito Sale Points Dashboard — Mirrors the Excel deep-dive structure.
Landing page = Customer Summary table. Click a customer = their sale points table.
Columns match the Excel exactly: #, Sale Point, Dec, Jan, Feb, Mar, Total, Months Active, Trend, Status, Choc, Van, Mango, Pist, DC.
"""

import json
from config import extract_customer_name, PRODUCT_SHORT
from registry import CUSTOMER_NAMES_EN
from pricing_engine import (
    get_b2b_price_safe,
    all_b2b_prices,
)
from business_logic import enrich_salepoint


def build_salepoint_tab(data):
    """Build complete HTML for the Sale Points tab."""
    sp = _extract(data)
    sp_json = json.dumps(sp, ensure_ascii=False)

    # Inject prices from the pricing engine (no hardcoded literals in JS)
    turbo_b2b = get_b2b_price_safe('chocolate')
    dc_b2b = get_b2b_price_safe('dream_cake_2')

    # Generate dynamic month arrays from registry
    from config import ALL_MONTH_KEYS, _MONTH_REGISTRY, get_active_months
    sp_all_month_keys_js = json.dumps(ALL_MONTH_KEYS)
    sp_mon_labels_js = json.dumps([m[2].split()[0] for m in _MONTH_REGISTRY])
    sp_period_options = '\n      '.join(
        f'<option value="{m[1]}">{m[2]}</option>' for m in _MONTH_REGISTRY
    )

    # Dynamic HTML table headers for month columns
    sp_summary_month_ths = ''.join(
        f'<th class="sp-mc sp-mc-{m[1]}">{m[2].split()[0]}</th>'
        for m in _MONTH_REGISTRY
    )
    sp_detail_month_ths = ''.join(
        f'<th onclick="spSort({i+2})" class="sp-mc sp-mc-{m[1]}">{m[2].split()[0]}</th>'
        for i, m in enumerate(_MONTH_REGISTRY)
    )
    n_months = len(_MONTH_REGISTRY)
    sp_detail_post_ths = (
        f'<th onclick="spSort({n_months+2})">Total</th>\n'
        f'            <th onclick="spSort({n_months+3})">Months Active</th>\n'
        f'            <th onclick="spSort({n_months+4})">Trend</th>\n'
        f'            <th onclick="spSort({n_months+5})">Status</th>\n'
        f'            <th onclick="spSort({n_months+6})">Choc</th>\n'
        f'            <th onclick="spSort({n_months+7})">Van</th>\n'
        f'            <th onclick="spSort({n_months+8})">Mango</th>\n'
        f'            <th onclick="spSort({n_months+9})">Pist</th>\n'
        f'            <th onclick="spSort({n_months+10})">DC</th>'
    )

    # Dynamic labels for status references
    _active_months = get_active_months()
    _last_active = _active_months[-1] if _active_months else _MONTH_REGISTRY[-1]
    _prev_active = _active_months[-2] if len(_active_months) >= 2 else _active_months[0]
    sp_last_month_label = _last_active[2].split()[0]   # e.g. 'Apr'
    sp_prev_month_label = _prev_active[2].split()[0]   # e.g. 'Mar'
    sp_no_order_label = f'No {sp_last_month_label} order'
    sp_active_label = f'Active ({sp_prev_month_label}→{sp_last_month_label})'
    # Last two active month keys for the "active" KPI count in JS
    sp_prev_month_key = _prev_active[1]
    sp_last_month_key = _last_active[1]

    return f"""
<style>{_css()}</style>
<div id="sp-app">

  <!-- Filter bar — persists across both views -->
  <div id="sp-brand-bar">
    <span class="sp-brand-label">Brand</span>
    <button class="sp-brand-btn sp-brand-active" id="spb-all"   onclick="spSetBrand('all')">All Brands</button>
    <button class="sp-brand-btn"                 id="spb-turbo" onclick="spSetBrand('turbo')">Turbo</button>
    <button class="sp-brand-btn"                 id="spb-danis" onclick="spSetBrand('danis')">Dani's Dream Cake</button>
    <span class="sp-brand-label" style="margin-left:18px">Distributor</span>
    <button class="sp-brand-btn sp-brand-active" id="spd-all"   onclick="spSetDist('all')">All</button>
    <button class="sp-brand-btn"                 id="spd-ice"   onclick="spSetDist('Icedream')">Icedream</button>
    <button class="sp-brand-btn"                 id="spd-may"   onclick="spSetDist('Ma\\'ayan')">Ma'ayan</button>
    <button class="sp-brand-btn"                 id="spd-bis"   onclick="spSetDist('Biscotti')">Biscotti</button>
    <span class="sp-brand-label" style="margin-left:18px">Period</span>
    <select id="sp-period-filter" onchange="spSetPeriod(this.value)" style="padding:6px 12px;border:1.5px solid #e5e7eb;border-radius:8px;font-size:13px;font-family:inherit;background:#fff;cursor:pointer">
      <option value="all">All Months</option>
      {sp_period_options}
    </select>
  </div>

  <!-- Landing: Customer Summary -->
  <div id="sp-summary">
    <div class="sp-topbar">
      <div><h2>Sale Points</h2><p>Click a customer to see all sale points</p></div>
      <div class="sp-kpis">
        <div class="sp-kpi"><span class="sp-kpi-n" id="sp-k-cust">-</span><span class="sp-kpi-l">Customers</span></div>
        <div class="sp-kpi"><span class="sp-kpi-n" id="sp-k-sp">-</span><span class="sp-kpi-l">Sale Points</span></div>
        <div class="sp-kpi"><span class="sp-kpi-n" id="sp-k-units">-</span><span class="sp-kpi-l">Total Units</span></div>
        <div class="sp-kpi"><span class="sp-kpi-n" id="sp-k-rev">-</span><span class="sp-kpi-l">Total Revenue</span></div>
      </div>
    </div>
    <div class="sp-body">
      <table class="sp-tbl" id="sp-summary-tbl">
        <thead>
          <tr>
            <th>#</th><th class="sp-col-name">Customer</th><th class="sp-col-name">Distributor</th><th>Sale Points</th>
            {sp_summary_month_ths}
            <th>Total Units</th><th>Total Revenue</th>
          </tr>
        </thead>
        <tbody id="sp-summary-body"></tbody>
      </table>
    </div>
  </div>

  <!-- Detail: Per-Customer Sale Points -->
  <div id="sp-detail" style="display:none">
    <div class="sp-topbar">
      <div style="display:flex;align-items:center;gap:12px">
        <button class="sp-back" onclick="spBack()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>
          Back
        </button>
        <div>
          <h2 id="sp-detail-title">-</h2>
          <p id="sp-detail-sub">-</p>
        </div>
      </div>
      <div class="sp-kpis">
        <div class="sp-kpi"><span class="sp-kpi-n" id="sp-d-sp">-</span><span class="sp-kpi-l">Sale Points</span></div>
        <div class="sp-kpi"><span class="sp-kpi-n" id="sp-d-units">-</span><span class="sp-kpi-l">Total Units</span></div>
        <div class="sp-kpi"><span class="sp-kpi-n" id="sp-d-rev">-</span><span class="sp-kpi-l">Revenue</span></div>
        <div class="sp-kpi"><span class="sp-kpi-n" id="sp-d-active">-</span><span class="sp-kpi-l">{sp_active_label}</span></div>
      </div>
    </div>
    <div class="sp-toolbar">
      <input type="text" id="sp-search" placeholder="Search sale points..." oninput="spFilter()">
      <select id="sp-status-filter" onchange="spFilter()">
        <option value="">All Statuses</option>
        <option value="Active">Active</option>
        <option value="Churned">Churned</option>
        <option value="{sp_no_order_label}">{sp_no_order_label}</option>
        <option value="Reactivated">Reactivated</option>
        <option value="New">New</option>
      </select>
      <span class="sp-count" id="sp-showing">-</span>
    </div>
    <div class="sp-body">
      <table class="sp-tbl" id="sp-detail-tbl">
        <thead>
          <tr>
            <th onclick="spSort(0)">#</th>
            <th onclick="spSort(1)" class="sp-col-name">Sale Point</th>
            {sp_detail_month_ths}
            {sp_detail_post_ths}
          </tr>
        </thead>
        <tbody id="sp-detail-body"></tbody>
      </table>
    </div>
  </div>
</div>

<script>
window.__SP_DATA__ = {sp_json};
window.__SP_MONTHS__ = {sp_all_month_keys_js};
window.__SP_MON_LABELS__ = {sp_mon_labels_js};
(function() {{
  var D = window.__SP_DATA__;
  var currentCustomer = null;
  var sortCol = -1, sortAsc = true;
  var brandFilter = 'all';
  var distFilter = 'all';
  var periodFilter = 'all';

  // ── Brand helpers ──
  function spMatchesBrand(s) {{
    if (brandFilter === 'all')   return true;
    if (brandFilter === 'turbo') return (s.choc + s.van + s.mango + s.pist) > 0;
    if (brandFilter === 'danis') return s.dc > 0;
    return true;
  }}
  // Brand-specific unit count for a single sale point
  function spBrandUnits(s) {{
    if (brandFilter === 'turbo') return s.choc + s.van + s.mango + s.pist;
    if (brandFilter === 'danis') return s.dc;
    return s.total;
  }}
  // Brand-specific revenue for a single sale point (prices from pricing_engine)
  var _TURBO_B2B = {turbo_b2b};
  var _DC_B2B = {dc_b2b};
  function spBrandRev(s) {{
    if (brandFilter === 'turbo') return (s.choc + s.van + s.mango + s.pist) * _TURBO_B2B;
    if (brandFilter === 'danis') return s.dc * _DC_B2B;
    return s.rev;
  }}
  function cMatchesDist(c) {{
    if (distFilter === 'all') return true;
    return c.distributor === distFilter;
  }}
  function cHasFilters(c) {{
    if (!cMatchesDist(c)) return false;
    if (brandFilter === 'all') return true;
    return c.salepoints.some(spMatchesBrand);
  }}
  // Period-aware unit accessor: returns total or just selected month's units
  function spPeriodUnits(s) {{
    if (periodFilter === 'all') return s.total;
    return s[periodFilter] || 0;
  }}
  var months = {sp_all_month_keys_js};
  function cBrandUnits(c) {{
    // Return brand-specific totals for the customer summary row
    if (brandFilter === 'all' && periodFilter === 'all') {{
      var obj = {{ total: c.total_units, rev: c.total_revenue, sp: c.salepoint_count }};
      months.forEach(function(m) {{ obj[m] = c[m] || 0; }});
      return obj;
    }}
    var mt = {{}};
    months.forEach(function(m) {{ mt[m] = 0; }});
    var total=0, rev=0, sp=0;
    c.salepoints.forEach(function(s) {{
      if (!spMatchesBrand(s)) return;
      if (periodFilter !== 'all' && !(s[periodFilter] > 0)) return;
      var bu = spBrandUnits(s);
      var frac = s.total > 0 ? bu / s.total : 0;
      months.forEach(function(m) {{ mt[m] += Math.round((s[m]||0) * frac); }});
      sp++;
      if (periodFilter !== 'all') {{
        var pUnits = Math.round((s[periodFilter] || 0) * frac);
        total += pUnits;
        rev   += s.total > 0 ? spBrandRev(s) * (s[periodFilter] / s.total) : 0;
      }} else {{
        total += bu;
        rev   += spBrandRev(s);
      }}
    }});
    rev = Math.round(rev);
    mt.total = total; mt.rev = rev; mt.sp = sp;
    return mt;
  }}

  // ── Set brand filter ──
  window.spSetBrand = function(b) {{
    brandFilter = b;
    ['all','turbo','danis'].forEach(function(id) {{
      document.getElementById('spb-' + id).classList.toggle('sp-brand-active', id === b);
    }});
    if (currentCustomer) {{
      renderDetailFiltered();
    }} else {{
      renderSummary();
    }}
  }};

  // ── Set distributor filter ──
  window.spSetDist = function(d) {{
    distFilter = d;
    var dmap = {{'all':'all','Icedream':'ice',"Ma'ayan":'may','Biscotti':'bis'}};
    ['all','ice','may','bis'].forEach(function(id) {{
      document.getElementById('spd-' + id).classList.toggle('sp-brand-active', dmap[d] === id);
    }});
    if (currentCustomer) {{
      // If viewing a customer that doesn't match new filter, go back to summary
      if (!cMatchesDist(currentCustomer)) {{
        spBack();
      }} else {{
        renderDetailFiltered();
      }}
    }}
    renderSummary();
  }};

  // ── Show/hide month columns based on period filter ──
  function spApplyMonthColumns() {{
    months.forEach(function(m) {{
      var vis = (periodFilter === 'all' || periodFilter === m) ? '' : 'none';
      document.querySelectorAll('.sp-mc-' + m).forEach(function(el) {{ el.style.display = vis; }});
    }});
  }}

  // ── Set period filter ──
  window.spSetPeriod = function(p) {{
    periodFilter = p;
    if (currentCustomer) {{
      renderDetailFiltered();
    }} else {{
      renderSummary();
    }}
    spApplyMonthColumns();
  }};

  // ── Render Summary (landing page) ──
  function renderSummary() {{
    var filtered = D.customers.filter(cHasFilters);
    var totSP = 0, totUnits = 0, totRev = 0;
    filtered.forEach(function(c) {{
      var bu = cBrandUnits(c);
      totSP += bu.sp; totUnits += bu.total; totRev += bu.rev;
    }});
    document.getElementById('sp-k-cust').textContent = filtered.length;
    document.getElementById('sp-k-sp').textContent = fmtN(totSP);
    document.getElementById('sp-k-units').textContent = fmtN(totUnits);
    document.getElementById('sp-k-rev').textContent = '₪' + fmtN(totRev);

    var tb = document.getElementById('sp-summary-body');
    tb.innerHTML = '';
    filtered.forEach(function(c, i) {{
      var bu = cBrandUnits(c);
      var tr = document.createElement('tr');
      tr.className = 'sp-clickable';
      // Find original index for spOpen
      var origIdx = D.customers.indexOf(c);
      tr.onclick = function() {{ spOpen(origIdx); }};
      var mCells = months.map(function(m) {{
        return '<td class="sp-mc sp-mc-' + m + '">' + fmtN(bu[m]||0) + '</td>';
      }}).join('');
      tr.innerHTML =
        '<td>' + (i+1) + '</td>' +
        '<td class="sp-col-name">' + esc(c.name) + '</td>' +
        '<td><span class="sp-dist sp-dist-' + (c.distributor === "Icedream" ? 'ice' : c.distributor === "Biscotti" ? 'bis' : 'may') + '">' + esc(c.distributor) + '</span></td>' +
        '<td>' + bu.sp + '</td>' +
        mCells +
        '<td class="sp-bold">' + fmtN(bu.total) + '</td>' +
        '<td>₪' + fmtN(bu.rev) + '</td>';
      tb.appendChild(tr);
    }});
    spApplyMonthColumns();
  }}

  // ── Open customer detail ──
  window.spOpen = function(idx) {{
    currentCustomer = D.customers[idx];
    sortCol = -1; sortAsc = true;
    document.getElementById('sp-summary').style.display = 'none';
    document.getElementById('sp-detail').style.display = 'block';
    document.getElementById('sp-detail-title').textContent = currentCustomer.name;
    document.getElementById('sp-search').value = '';
    document.getElementById('sp-status-filter').value = '';
    renderDetailFiltered();
  }};

  function renderDetailFiltered() {{
    var sps = currentCustomer.salepoints.filter(spMatchesBrand);
    if (periodFilter !== 'all') sps = sps.filter(function(s){{ return (s[periodFilter] || 0) > 0; }});
    var spCount = sps.length;
    var units = sps.reduce(function(a,x){{return a+spPeriodUnits(x);}}, 0);
    var rev   = sps.reduce(function(a,x){{
      if (periodFilter !== 'all') {{
        return a + (x.total > 0 ? spBrandRev(x) * (x[periodFilter] / x.total) : 0);
      }}
      return a+spBrandRev(x);
    }},   0);
    rev = Math.round(rev);
    var active = sps.filter(function(s){{ return (s['{sp_prev_month_key}']||0) > 0 && (s['{sp_last_month_key}']||0) > 0; }}).length;
    var brandLabel = brandFilter === 'all' ? '' : (brandFilter === 'turbo' ? ' · Turbo' : " · Dani's Dream Cake");
    document.getElementById('sp-detail-sub').textContent =
      currentCustomer.distributor + (currentCustomer.parent ? ' · ' + currentCustomer.parent : '') +
      ' · ' + spCount + ' sale points' + brandLabel;
    document.getElementById('sp-d-sp').textContent = spCount;
    document.getElementById('sp-d-units').textContent = fmtN(units);
    document.getElementById('sp-d-rev').textContent = '₪' + fmtN(rev);
    document.getElementById('sp-d-active').textContent = active;
    renderDetail(getFiltered());
  }}

  // ── Back to summary ──
  window.spBack = function() {{
    document.getElementById('sp-detail').style.display = 'none';
    document.getElementById('sp-summary').style.display = 'block';
    currentCustomer = null;
  }};

  // ── Render detail table ──
  function renderDetail(rows) {{
    var tb = document.getElementById('sp-detail-body');
    tb.innerHTML = '';
    document.getElementById('sp-showing').textContent = 'Showing ' + rows.length + ' of ' + currentCustomer.salepoints.length;
    rows.forEach(function(s, i) {{
      var tr = document.createElement('tr');
      var trendHtml = s.trend !== null ? ((s.trend >= 0 ? '<span class="sp-up">+' : '<span class="sp-down">') + s.trend + '%</span>') : '<span class="sp-na">—</span>';
      var statusCls = 'sp-st-' + s.status.toLowerCase().replace(/[^a-z]/g, '');
      var dCells = months.map(function(m) {{
        return '<td class="sp-mc sp-mc-' + m + '">' + fmtN(s[m]||0) + '</td>';
      }}).join('');
      tr.innerHTML =
        '<td>' + (i+1) + '</td>' +
        '<td class="sp-col-name">' + esc(s.name) + '</td>' +
        dCells +
        '<td class="sp-bold">' + fmtN(spPeriodUnits(s)) + '</td>' +
        '<td>' + s.months_active + '</td>' +
        '<td>' + trendHtml + '</td>' +
        '<td><span class="sp-status ' + statusCls + '">' + esc(s.status) + '</span></td>' +
        '<td>' + fmtN(s.choc) + '</td>' +
        '<td>' + fmtN(s.van) + '</td>' +
        '<td>' + fmtN(s.mango) + '</td>' +
        '<td>' + fmtN(s.pist) + '</td>' +
        '<td>' + fmtN(s.dc) + '</td>';
      tb.appendChild(tr);
    }});
    spApplyMonthColumns();
  }}

  // ── Sort ──
  window.spSort = function(col) {{
    if (!currentCustomer) return;
    if (sortCol === col) sortAsc = !sortAsc; else {{ sortCol = col; sortAsc = true; }}
    var keys = ['_i','name'].concat({sp_all_month_keys_js}).concat(['total','months_active','trend','status','choc','van','mango','pist','dc']);
    var key = keys[col];
    var arr = getFiltered();
    arr.sort(function(a,b) {{
      var va = key === '_i' ? 0 : a[key], vb = key === '_i' ? 0 : b[key];
      if (va === null) va = -9999; if (vb === null) vb = -9999;
      if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
      return sortAsc ? va - vb : vb - va;
    }});
    renderDetail(arr);
  }};

  // ── Filter ──
  window.spFilter = function() {{
    renderDetail(getFiltered());
  }};

  function getFiltered() {{
    var q = document.getElementById('sp-search').value.toLowerCase();
    var st = document.getElementById('sp-status-filter').value;
    return currentCustomer.salepoints.filter(function(s) {{
      if (!spMatchesBrand(s)) return false;
      if (periodFilter !== 'all' && !(s[periodFilter] > 0)) return false;
      if (q && s.name.toLowerCase().indexOf(q) < 0) return false;
      if (st && s.status !== st) return false;
      return true;
    }});
  }}

  // ── Helpers ──
  function fmtN(n) {{ return n == null || n === 0 ? '0' : Number(n).toLocaleString('en-US', {{maximumFractionDigits:0}}); }}
  function esc(s) {{ var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }}

  // ── Init ──
  renderSummary();
}})();
</script>
"""


import re as _re

def _normalize_sp_name(name):
    """Strip delivery/logistics suffixes so DB names match Excel-parsed names.

    Examples:
        'וולט מרקט אשדוד - אספקה עד13:30'  → 'וולט מרקט אשדוד'
        'וולט מרקט אשקלון*עד 13:30 חובה'    → 'וולט מרקט אשקלון'
        'וולט מרקט אשדוד -'                  → 'וולט מרקט אשדוד'
    """
    s = name.strip()
    # Strip from common suffix markers
    s = _re.split(r'\s*[-*]\s*אספקה', s)[0]
    s = _re.split(r'\s*\*\s*עד\b', s)[0]
    s = _re.split(r'\s*\*\s*לא\b', s)[0]
    # Strip trailing dash/asterisk and whitespace
    s = s.rstrip(' \t-*')
    # Collapse multiple spaces
    s = _re.sub(r'\s+', ' ', s).strip()
    return s


def _load_canonical_merges():
    """Query DB for canonical_sp_id mappings → {normalized_alias: canonical_branch_name}.

    Uses normalized names to bridge differences between DB and Excel-parsed names.
    Returns empty dict if DB is unavailable (graceful no-op for local builds).
    """
    try:
        import os
        import psycopg2
        url = os.environ.get('DATABASE_URL', '')
        if not url:
            return {}
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        # Get all alias→canonical mappings (raw names)
        cur.execute("""
            SELECT alias.branch_name_he, canon.branch_name_he
            FROM sale_points alias
            JOIN sale_points canon ON alias.canonical_sp_id = canon.id
            WHERE alias.canonical_sp_id IS NOT NULL
        """)
        raw_merges = cur.fetchall()

        # Also get all branch names that ARE canonical targets (for name lookup)
        cur.execute("""
            SELECT DISTINCT canon.branch_name_he
            FROM sale_points alias
            JOIN sale_points canon ON alias.canonical_sp_id = canon.id
            WHERE alias.canonical_sp_id IS NOT NULL
        """)
        canonical_names = {row[0] for row in cur.fetchall()}
        conn.close()

        # Build normalized lookup: norm(alias_name) → canonical_name
        # Also map norm(canonical_name) → canonical_name for target resolution
        merges = {}
        for alias_name, canon_name in raw_merges:
            if alias_name and canon_name:
                # Exact match first
                merges[alias_name] = canon_name
                # Normalized match as fallback
                merges[_normalize_sp_name(alias_name)] = canon_name

        return merges, canonical_names
    except Exception:
        return {}, set()


def _extract(data):
    """Extract branch-level data, mirroring the Excel structure.

    Pricing: All prices sourced from pricing_engine (no hardcoded literals).
    Status/Trend: Pre-computed via business_logic (Option A — Python-side only).
    """
    from config import CHART_MONTHS
    months = CHART_MONTHS
    # Collect per-customer, per-branch data — same grouping as the Excel
    # For Ma'ayan: group by normalized chain. Each account = one sale point.
    # For Icedream: group by normalized chain. Each customer entry = one sale point.
    customers = {}  # {(dist, norm_chain): {branches: {name: {month_data}}}}

    for m in months:
        md = data['monthly_data'].get(m, {})

        # Ma'ayan accounts — pdata is {product: {units, value}} (priced at parse time)
        for (raw_chain, acct_name), pdata in md.get('mayyan_accounts', {}).items():
            norm = extract_customer_name(acct_name, source_customer=raw_chain)
            key = ("Ma'ayan", norm)
            if key not in customers:
                rc = raw_chain.strip() if raw_chain else ''
                customers[key] = {'parent': CUSTOMER_NAMES_EN.get(rc, rc), 'branches': {}}
            if acct_name not in customers[key]['branches']:
                customers[key]['branches'][acct_name] = {mo: {'units': 0, 'rev': 0, 'flav': {}} for mo in months}
            b = customers[key]['branches'][acct_name][m]
            for prod, prod_data in pdata.items():
                units = prod_data.get('units', 0) if isinstance(prod_data, dict) else (prod_data or 0)
                value = prod_data.get('value', 0) if isinstance(prod_data, dict) else 0
                if units != 0:
                    b['units'] += units
                    b['rev'] += value
                    b['flav'][prod] = b['flav'].get(prod, 0) + units

        # Icedream customers
        for cust, pdata in md.get('icedreams_customers', {}).items():
            norm = extract_customer_name(cust)
            key = ('Icedream', norm)
            if key not in customers:
                customers[key] = {'parent': '', 'branches': {}}
            if cust not in customers[key]['branches']:
                customers[key]['branches'][cust] = {mo: {'units': 0, 'rev': 0, 'flav': {}} for mo in months}
            b = customers[key]['branches'][cust][m]
            for prod, val in pdata.items():
                if isinstance(val, dict) and 'units' in val:
                    u = val['units']
                    if u != 0:
                        price = get_b2b_price_safe(prod)
                        b['units'] += u
                        b['rev'] += u * price
                        b['flav'][prod] = b['flav'].get(prod, 0) + u

        # Biscotti customers — route each branch to its real customer name
        _BISCOTTI_SP_CUSTOMER = [
            ('וולט מרקט',   'Wolt Market'),
            ('חוות נעמי',   "Naomi's Farm"),
            ('חן כרמלה',    'Carmella'),
            ('כרמלה',       'Carmella'),
            ('מתילדה יהוד', 'Matilda Yehud'),
            ('דלישס',       'Delicious RL'),
        ]

        def _resolve_biscotti_sp_customer(branch_name):
            for prefix, cust in _BISCOTTI_SP_CUSTOMER:
                if branch_name.startswith(prefix):
                    return cust
            return 'Biscotti Customer'  # fallback for unrecognised branches

        for branch, pdata in md.get('biscotti_customers', {}).items():
            cust_name = _resolve_biscotti_sp_customer(branch)
            key = ('Biscotti', cust_name)
            if key not in customers:
                customers[key] = {'parent': 'Biscotti', 'branches': {}}
            if branch not in customers[key]['branches']:
                customers[key]['branches'][branch] = {mo: {'units': 0, 'rev': 0, 'flav': {}} for mo in months}
            b = customers[key]['branches'][branch][m]
            for prod, val in pdata.items():
                if isinstance(val, dict) and 'units' in val:
                    u = val['units']
                    if u != 0:
                        price = get_b2b_price_safe(prod)
                        b['units'] += u
                        b['rev'] += u * price
                        b['flav'][prod] = b['flav'].get(prod, 0) + u

    # ── SP Dedup: merge same sale point appearing under different distributors ──
    # Build index: branch_name → list of (dist, norm, key) where it appears
    from collections import defaultdict
    branch_index = defaultdict(list)  # {branch_name: [(key, dist), ...]}
    for (dist, norm), cinfo in customers.items():
        for bname in cinfo['branches']:
            branch_index[bname].append(((dist, norm), dist))

    # For branches appearing under multiple distributors, merge into first key
    # and record combined distributor name
    _sp_distributor_names = {}  # {branch_name: "Dist1 + Dist2"}
    for bname, entries in branch_index.items():
        if len(entries) <= 1:
            continue
        # Sort so the merge target is deterministic (alphabetical by dist name)
        entries.sort(key=lambda e: e[1])
        target_key = entries[0][0]
        combined_dists = ' + '.join(sorted(set(e[1] for e in entries)))
        _sp_distributor_names[bname] = combined_dists
        # Merge all non-target entries into target
        for src_key, _ in entries[1:]:
            src_branches = customers[src_key]['branches']
            if bname not in src_branches:
                continue
            src_months = src_branches.pop(bname)
            tgt_months = customers[target_key]['branches'].setdefault(
                bname, {mo: {'units': 0, 'rev': 0, 'flav': {}} for mo in months}
            )
            for mo in months:
                tgt_months[mo]['units'] += src_months[mo]['units']
                tgt_months[mo]['rev'] += src_months[mo]['rev']
                for fl, fu in src_months[mo]['flav'].items():
                    tgt_months[mo]['flav'][fl] = tgt_months[mo]['flav'].get(fl, 0) + fu

    # ── Canonical SP Merge: fold DB-defined aliases into their canonical branch ──
    # Uses normalized names to bridge DB ↔ Excel naming differences
    canonical_result = _load_canonical_merges()
    canonical_map, canonical_names = canonical_result  # map + set of canonical target names
    if canonical_map:
        # Helper: look up canonical name for a branch (exact first, then normalized)
        def _find_canon(bname):
            c = canonical_map.get(bname)
            if c:
                return c
            return canonical_map.get(_normalize_sp_name(bname))

        # Helper: check if a branch name is itself a canonical target
        _norm_canonical = {_normalize_sp_name(cn): cn for cn in canonical_names}

        def _find_branch_in_group(branches, canon_name):
            """Find a branch matching canon_name (exact or normalized)."""
            if canon_name in branches:
                return canon_name
            norm_c = _normalize_sp_name(canon_name)
            for bn in branches:
                if _normalize_sp_name(bn) == norm_c:
                    return bn
            return None

        def _merge_months(tgt, src, months):
            for mo in months:
                tgt[mo]['units'] += src[mo]['units']
                tgt[mo]['rev'] += src[mo]['rev']
                for fl, fu in src[mo]['flav'].items():
                    tgt[mo]['flav'][fl] = tgt[mo]['flav'].get(fl, 0) + fu

        for (dist, norm), cinfo in customers.items():
            branches = cinfo['branches']
            aliases_to_remove = []
            for bname in list(branches.keys()):
                canon_name = _find_canon(bname)
                if not canon_name or canon_name == bname:
                    # Also skip if normalized names match (already the canonical)
                    if not canon_name or _normalize_sp_name(canon_name) == _normalize_sp_name(bname):
                        continue

                # Find canonical branch in same customer group (by normalized match)
                tgt_bname = _find_branch_in_group(branches, canon_name)
                if tgt_bname and tgt_bname != bname:
                    _merge_months(branches[tgt_bname], branches[bname], months)
                    aliases_to_remove.append(bname)
                    continue

                # Check other customer groups
                found_elsewhere = False
                for (d2, n2), c2 in customers.items():
                    if (d2, n2) == (dist, norm):
                        continue
                    tgt_b2 = _find_branch_in_group(c2['branches'], canon_name)
                    if tgt_b2:
                        _merge_months(c2['branches'][tgt_b2], branches[bname], months)
                        aliases_to_remove.append(bname)
                        found_elsewhere = True
                        break

                if not found_elsewhere:
                    # Canonical target not found anywhere — rename alias to canonical
                    branches[canon_name] = branches[bname]
                    aliases_to_remove.append(bname)

            for bname in aliases_to_remove:
                branches.pop(bname, None)

    # Build output matching Excel columns — fully dynamic from MONTH_REGISTRY
    from config import MONTH_KEYS, ALL_MONTH_KEYS, get_active_month_keys
    month_key_map = MONTH_KEYS  # full_name → short_key
    all_mk = ALL_MONTH_KEYS     # ordered short keys
    active_mk = get_active_month_keys()  # months up to today (for status/trend)

    result_customers = []
    total_sp = 0
    total_units = 0
    total_rev = 0

    for (dist, norm), cinfo in customers.items():
        branches = cinfo['branches']
        sp_list = []
        cust_month_totals = {mk: 0 for mk in all_mk}
        cust_units = 0
        cust_rev = 0

        for bname, bmonths in branches.items():
            # Extract units per month key dynamically
            month_units = {}
            for full_name in months:
                mk = month_key_map.get(full_name)
                if mk:
                    month_units[mk] = bmonths[full_name]['units']
            tot = sum(month_units.values())
            rev = sum(bmonths[m]['rev'] for m in months)

            if tot == 0:
                continue

            # Flavor totals
            flav = {}
            for m in months:
                for f, u in bmonths[m]['flav'].items():
                    flav[f] = flav.get(f, 0) + u

            # Build sale-point dict, then enrich with status/trend/months_active
            # from the canonical business_logic engine (Option A: pre-compute)
            sp_dist_label = _sp_distributor_names.get(bname, dist)
            sp_entry = {
                'name': bname,
                'distributor': sp_dist_label,
                **month_units,
                'total': tot,
                'choc': flav.get('chocolate', 0),
                'van': flav.get('vanilla', 0),
                'mango': flav.get('mango', 0),
                'pist': flav.get('pistachio', 0),
                'dc': flav.get('dream_cake', 0) + flav.get('dream_cake_2', 0),
                'rev': round(rev),
            }
            enrich_salepoint(sp_entry, month_keys=active_mk)
            sp_list.append(sp_entry)

            for mk in all_mk:
                cust_month_totals[mk] += month_units.get(mk, 0)
            cust_units += tot
            cust_rev += rev

        if not sp_list:
            continue

        # Sort by total desc
        sp_list.sort(key=lambda x: -x['total'])

        result_customers.append({
            'name': norm,
            'distributor': dist,
            'parent': cinfo['parent'] if cinfo['parent'] != norm else '',
            'salepoints': sp_list,
            'salepoint_count': len(sp_list),
            **cust_month_totals,
            'total_units': cust_units,
            'total_revenue': round(cust_rev),
        })
        total_sp += len(sp_list)
        total_units += cust_units
        total_rev += cust_rev

    result_customers.sort(key=lambda x: -x['total_units'])

    return {
        'customers': result_customers,
        'total_salepoints': total_sp,
        'total_units': total_units,
        'total_revenue': round(total_rev),
    }


def _css():
    return """
/* ── Sale Points Tab ── */
#tab-sp { background:var(--bg); }

#sp-app { font-family:'Inter',system-ui,sans-serif; color:var(--text); }

/* Brand filter bar */
#sp-brand-bar {
  background:var(--card); border-bottom:1px solid var(--border-light);
  padding:10px 32px; display:flex; align-items:center; gap:8px;
  position:sticky; top:0; z-index:10;
}
.sp-brand-label {
  font-size:11px; font-weight:600; color:var(--text-muted);
  text-transform:uppercase; letter-spacing:0.5px; margin-right:4px;
}
.sp-brand-btn {
  padding:5px 16px; border-radius:20px; font-size:12px; font-weight:600;
  border:1.5px solid var(--border); background:transparent; color:var(--text-muted);
  cursor:pointer; font-family:inherit; transition:all 0.15s;
}
.sp-brand-btn:hover { border-color:var(--primary); color:var(--primary); }
.sp-brand-active {
  border-color:var(--primary) !important;
  background:var(--primary) !important;
  color:#fff !important;
}

/* Topbar */
.sp-topbar {
  background:var(--card); border-bottom:1px solid var(--border-light);
  padding:20px 32px; display:flex; justify-content:space-between; align-items:center; gap:20px; flex-wrap:wrap;
}
.sp-topbar h2 { font-size:18px; font-weight:700; margin:0; }
.sp-topbar p  { font-size:12px; color:var(--text-muted); margin:2px 0 0; }

/* KPI chips */
.sp-kpis { display:flex; gap:16px; }
.sp-kpi {
  background:var(--surface); border-radius:12px; padding:10px 18px;
  display:flex; flex-direction:column; align-items:center; min-width:100px;
}
.sp-kpi-n { font-size:20px; font-weight:800; color:var(--text); }
.sp-kpi-l { font-size:10px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; margin-top:2px; }

/* Body / table area */
.sp-body {
  padding:20px 32px; overflow-x:auto;
}

/* Toolbar (search + count) */
.sp-toolbar {
  padding:12px 32px; display:flex; align-items:center; gap:16px; background:var(--card);
  border-bottom:1px solid var(--border-light);
}
#sp-search {
  padding:8px 14px; border:1px solid var(--border); border-radius:10px;
  font-size:13px; font-family:inherit; width:280px; background:var(--surface);
  outline:none; transition:border-color 0.2s;
}
#sp-search:focus { border-color:var(--primary); }
#sp-status-filter {
  padding:8px 14px; border:1px solid var(--border); border-radius:10px;
  font-size:13px; font-family:inherit; background:var(--surface);
  outline:none; cursor:pointer; color:var(--text);
}
#sp-status-filter:focus { border-color:var(--primary); }
.sp-count { font-size:12px; color:var(--text-muted); }
/* .tab-export-btn styled in unified dashboard CSS */

/* Tables */
.sp-tbl {
  width:100%; border-collapse:collapse; font-size:12px;
  background:var(--card); border-radius:16px; overflow:hidden;
  box-shadow:var(--shadow-sm);
}
.sp-tbl thead th {
  background:var(--surface); padding:10px 10px; text-align:center;
  font-size:11px; font-weight:700; color:var(--text2);
  text-transform:uppercase; letter-spacing:0.5px;
  border-bottom:2px solid var(--border); cursor:pointer; white-space:nowrap;
  user-select:none; position:sticky; top:0; z-index:1;
}
.sp-tbl thead th:hover { color:var(--primary); }
.sp-tbl tbody td {
  padding:8px 10px; border-bottom:1px solid var(--border-light);
  text-align:center; white-space:nowrap;
}
.sp-tbl tbody tr:hover { background:var(--surface2); }
.sp-tbl tbody tr:last-child td { border-bottom:none; }

.sp-col-name { text-align:left !important; min-width:120px; direction:rtl; }
.sp-bold { font-weight:700; }

/* Clickable summary rows */
.sp-clickable { cursor:pointer; transition:background 0.15s; }
.sp-clickable:hover { background:rgba(93,95,239,0.04) !important; }

/* Distributor badges */
.sp-dist { font-size:10px; padding:2px 8px; border-radius:20px; font-weight:600; }
.sp-dist-ice { background:#ecfdf5; color:#065f46; }
.sp-dist-may { background:#eff6ff; color:#1e40af; }
.sp-dist-bis { background:#fce7f3; color:#9d174d; }

/* Status badges */
.sp-status { font-size:10px; padding:2px 8px; border-radius:20px; font-weight:600; white-space:nowrap; }
.sp-st-active { background:#ecfdf5; color:#065f46; }
.sp-st-churned { background:#fef2f2; color:#991b1b; }
.sp-st-nomarorder { background:#fef3c7; color:#92400e; }
.sp-st-reactivated { background:#eff6ff; color:#1e40af; }
.sp-st-new { background:rgba(93,95,239,0.08); color:#5D5FEF; }

/* Trend */
.sp-up { color:#10b981; font-weight:600; }
.sp-down { color:#ef4444; font-weight:600; }
.sp-na { color:#94a3b8; }

/* Back button */
.sp-back {
  display:flex; align-items:center; gap:6px; padding:8px 16px;
  border:1px solid var(--border); border-radius:10px; background:var(--card);
  font-size:13px; font-weight:600; color:var(--text-muted); cursor:pointer;
  font-family:inherit; transition:all 0.15s;
}
.sp-back:hover { border-color:var(--primary); color:var(--primary); }

@media (max-width:900px) {
  .sp-topbar { flex-direction:column; align-items:flex-start; }
  .sp-kpis { flex-wrap:wrap; }
  .sp-body { padding:12px 16px; }
  .sp-toolbar { padding:10px 16px; }
  #sp-search { width:100%; }
}
"""
