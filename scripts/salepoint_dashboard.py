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

    return f"""
<style>{_css()}</style>
<div id="sp-app">

  <!-- Brand filter bar — persists across both views -->
  <div id="sp-brand-bar">
    <span class="sp-brand-label">Brand</span>
    <button class="sp-brand-btn sp-brand-active" id="spb-all"   onclick="spSetBrand('all')">All Brands</button>
    <button class="sp-brand-btn"                 id="spb-turbo" onclick="spSetBrand('turbo')">Turbo</button>
    <button class="sp-brand-btn"                 id="spb-danis" onclick="spSetBrand('danis')">Dani's Dream Cake</button>
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
            <th>Dec</th><th>Jan</th><th>Feb</th><th>Mar</th>
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
        <div class="sp-kpi"><span class="sp-kpi-n" id="sp-d-active">-</span><span class="sp-kpi-l">Active (Feb→Mar)</span></div>
      </div>
    </div>
    <div class="sp-toolbar">
      <input type="text" id="sp-search" placeholder="Search sale points..." oninput="spFilter()">
      <select id="sp-status-filter" onchange="spFilter()">
        <option value="">All Statuses</option>
        <option value="Active">Active</option>
        <option value="Churned">Churned</option>
        <option value="No Mar order">No Mar order</option>
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
            <th onclick="spSort(2)">Dec</th>
            <th onclick="spSort(3)">Jan</th>
            <th onclick="spSort(4)">Feb</th>
            <th onclick="spSort(5)">Mar</th>
            <th onclick="spSort(6)">Total</th>
            <th onclick="spSort(7)">Months Active</th>
            <th onclick="spSort(8)">Trend</th>
            <th onclick="spSort(9)">Status</th>
            <th onclick="spSort(10)">Choc</th>
            <th onclick="spSort(11)">Van</th>
            <th onclick="spSort(12)">Mango</th>
            <th onclick="spSort(13)">Pist</th>
            <th onclick="spSort(14)">DC</th>
          </tr>
        </thead>
        <tbody id="sp-detail-body"></tbody>
      </table>
    </div>
  </div>
</div>

<script>
window.__SP_DATA__ = {sp_json};
(function() {{
  var D = window.__SP_DATA__;
  var currentCustomer = null;
  var sortCol = -1, sortAsc = true;
  var brandFilter = 'all';

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
  function cHasBrand(c) {{
    if (brandFilter === 'all') return true;
    return c.salepoints.some(spMatchesBrand);
  }}
  function cBrandUnits(c) {{
    // Return brand-specific totals for the customer summary row
    if (brandFilter === 'all') return {{ dec: c.dec, jan: c.jan, feb: c.feb, mar: c.mar, total: c.total_units, rev: c.total_revenue, sp: c.salepoint_count }};
    var dec=0, jan=0, feb=0, mar=0, total=0, rev=0, sp=0;
    c.salepoints.forEach(function(s) {{
      if (!spMatchesBrand(s)) return;
      var bu = spBrandUnits(s);
      // Distribute monthly units proportionally by brand share
      var frac = s.total > 0 ? bu / s.total : 0;
      dec   += Math.round(s.dec * frac);
      jan   += Math.round(s.jan * frac);
      feb   += Math.round(s.feb * frac);
      mar   += Math.round(s.mar * frac);
      total += bu;
      rev   += spBrandRev(s);
      sp++;
    }});
    return {{ dec: dec, jan: jan, feb: feb, mar: mar, total: total, rev: rev, sp: sp }};
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

  // ── Render Summary (landing page) ──
  function renderSummary() {{
    var filtered = D.customers.filter(cHasBrand);
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
      tr.innerHTML =
        '<td>' + (i+1) + '</td>' +
        '<td class="sp-col-name">' + esc(c.name) + '</td>' +
        '<td><span class="sp-dist sp-dist-' + (c.distributor === "Icedream" ? 'ice' : c.distributor === "Biscotti" ? 'bis' : 'may') + '">' + esc(c.distributor) + '</span></td>' +
        '<td>' + bu.sp + '</td>' +
        '<td>' + fmtN(bu.dec) + '</td>' +
        '<td>' + fmtN(bu.jan) + '</td>' +
        '<td>' + fmtN(bu.feb) + '</td>' +
        '<td>' + fmtN(bu.mar) + '</td>' +
        '<td class="sp-bold">' + fmtN(bu.total) + '</td>' +
        '<td>₪' + fmtN(bu.rev) + '</td>';
      tb.appendChild(tr);
    }});
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
    var spCount = sps.length;
    var units = sps.reduce(function(a,x){{return a+spBrandUnits(x);}}, 0);
    var rev   = sps.reduce(function(a,x){{return a+spBrandRev(x);}},   0);
    var active = sps.filter(function(s){{ return s.feb > 0 && s.mar > 0; }}).length;
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
      tr.innerHTML =
        '<td>' + (i+1) + '</td>' +
        '<td class="sp-col-name">' + esc(s.name) + '</td>' +
        '<td>' + fmtN(s.dec) + '</td>' +
        '<td>' + fmtN(s.jan) + '</td>' +
        '<td>' + fmtN(s.feb) + '</td>' +
        '<td>' + fmtN(s.mar) + '</td>' +
        '<td class="sp-bold">' + fmtN(spBrandUnits(s)) + '</td>' +
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
  }}

  // ── Sort ──
  window.spSort = function(col) {{
    if (!currentCustomer) return;
    if (sortCol === col) sortAsc = !sortAsc; else {{ sortCol = col; sortAsc = true; }}
    var keys = ['_i','name','dec','jan','feb','mar','total','months_active','trend','status','choc','van','mango','pist','dc'];
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


def _extract(data):
    """Extract branch-level data, mirroring the Excel structure.

    Pricing: All prices sourced from pricing_engine (no hardcoded literals).
    Status/Trend: Pre-computed via business_logic (Option A — Python-side only).
    """
    months = ['December 2025', 'January 2026', 'February 2026', 'March 2026']
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

        # Biscotti customers (direct distribution — all branches grouped under "Biscotti Customer")
        for branch, pdata in md.get('biscotti_customers', {}).items():
            key = ('Biscotti', 'Biscotti Customer')
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

    # Build output matching Excel columns
    result_customers = []
    total_sp = 0
    total_units = 0
    total_rev = 0

    for (dist, norm), cinfo in customers.items():
        branches = cinfo['branches']
        sp_list = []
        cust_dec = cust_jan = cust_feb = cust_mar = 0
        cust_units = 0
        cust_rev = 0

        for bname, bmonths in branches.items():
            dec_u = bmonths['December 2025']['units']
            jan_u = bmonths['January 2026']['units']
            feb_u = bmonths['February 2026']['units']
            mar_u = bmonths['March 2026']['units']
            tot = dec_u + jan_u + feb_u + mar_u
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
            sp_entry = {
                'name': bname,
                'dec': dec_u, 'jan': jan_u, 'feb': feb_u, 'mar': mar_u,
                'total': tot,
                'choc': flav.get('chocolate', 0),
                'van': flav.get('vanilla', 0),
                'mango': flav.get('mango', 0),
                'pist': flav.get('pistachio', 0),
                'dc': flav.get('dream_cake', 0) + flav.get('dream_cake_2', 0),
                'rev': round(rev),
            }
            enrich_salepoint(sp_entry)  # adds 'status', 'trend', 'months_active'
            sp_list.append(sp_entry)

            cust_dec += dec_u
            cust_jan += jan_u
            cust_feb += feb_u
            cust_mar += mar_u
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
            'dec': cust_dec, 'jan': cust_jan, 'feb': cust_feb, 'mar': cust_mar,
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
