#!/usr/bin/env python3
"""
RAITO Geo Dashboard — Tab 5: Geographical Sales Analysis
=========================================================

Generates the HTML/CSS/JS for the Geo tab, following the same pattern as
cc_dashboard.py and salepoint_dashboard.py.

Call: build_geo_tab(data) → returns an HTML string to be embedded in
unified_dashboard.py as the 5th tab.

The map renders via Google Maps JavaScript API and is driven by two
Flask API endpoints (see geo_api.py):
  GET /api/geo/choropleth   — municipality KPIs for the colour layer
  GET /api/geo/pos          — individual POS points for drill-down

The GeoJSON boundaries for Israeli municipalities are served from:
  GET /api/geo/municipalities  — the full boundary file (cached in memory)

All controls (KPI selector, period filter, distributor filter, brand filter, layer toggle)
live entirely in the frontend — no page reload required.
"""

import os
from pathlib import Path

# The Maps API key is injected at build time from the environment.
# In production (Cloud Run) set the GOOGLE_MAPS_API_KEY secret.
# In local dev: export GOOGLE_MAPS_API_KEY="your_key_here"
MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "YOUR_API_KEY_HERE")


def build_geo_tab(data: dict) -> str:
    """
    Build the Geographical Sales Analysis tab HTML.

    Args:
        data: the consolidated data dict from parsers.py (same as all other tabs).
              Used here only to extract the list of available month labels.

    Returns:
        An HTML string ready to be injected into the unified dashboard's tab system.
    """
    # --- Extract month labels from data (same pattern as other tabs) ----------
    month_labels = _get_month_labels(data)
    month_options_html = '\n'.join(
        f'<option value="{m["value"]}">{m["label"]}</option>' for m in month_labels
    )

    return f"""
<!-- =========================================================
     TAB 5: Geographical Sales Analysis
     ========================================================= -->
<div id="tab-geo" class="tab-content">

  <!-- ── Top controls bar ─────────────────────────────────── -->
  <div class="geo-controls-bar">

    <div class="geo-control-group">
      <label class="geo-label" for="geo-kpi-select">KPI</label>
      <select id="geo-kpi-select" class="geo-select" onchange="geoUpdateMap()">
        <option value="revenue">Revenue (₪)</option>
        <option value="units">Units Sold</option>
        <option value="pos_count">Active POS Count</option>
      </select>
    </div>

    <div class="geo-control-group">
      <label class="geo-label" for="geo-month-select">Period</label>
      <select id="geo-month-select" class="geo-select" onchange="geoUpdateMap()">
        <option value="all">All Time</option>
        {month_options_html}
      </select>
    </div>

    <div class="geo-control-group">
      <label class="geo-label" for="geo-dist-select">Distributor</label>
      <select id="geo-dist-select" class="geo-select" onchange="geoUpdateMap()">
        <option value="all">All</option>
        <option value="icedream">Icedream</option>
        <option value="mayyan">Ma'ayan</option>
        <option value="biscotti">Biscotti</option>
      </select>
    </div>

    <div class="geo-control-group">
      <label class="geo-label" for="geo-brand-select">Brand</label>
      <select id="geo-brand-select" class="geo-select" onchange="geoUpdateMap()">
        <option value="all">All Brands</option>
        <option value="turbo">Turbo</option>
        <option value="danis">Dani's</option>
      </select>
    </div>

    <div class="geo-control-group">
      <label class="geo-label" for="geo-layer-select">Boundaries</label>
      <select id="geo-layer-select" class="geo-select" onchange="geoSwitchLayer()">
        <option value="district">District</option>
        <option value="city">City</option>
      </select>
    </div>

    <div class="geo-control-group">
      <label class="geo-label">POS Layer</label>
      <div class="geo-toggle-group">
        <button id="geo-btn-none"    class="geo-toggle-btn geo-toggle-active" onclick="geoSetPosLayer('none')">Off</button>
        <button id="geo-btn-markers" class="geo-toggle-btn" onclick="geoSetPosLayer('markers')">Markers</button>
        <button id="geo-btn-heatmap" class="geo-toggle-btn" onclick="geoSetPosLayer('heatmap')">Heatmap</button>
      </div>
    </div>

    <div class="geo-control-group" style="margin-left:auto;">
      <button class="geo-btn-reset" onclick="geoResetView()">⟳ Reset View</button>
    </div>

  </div><!-- /.geo-controls-bar -->

  <!-- ── Map (40% height) ──────────────────────────────────── -->
  <div class="geo-map-wrap">
    <div id="geo-map-canvas"></div>
    <!-- Compact legend overlay -->
    <div class="geo-legend-overlay">
      <span>Low</span>
      <div id="geo-legend-gradient" class="geo-legend-gradient"></div>
      <span>High</span>
      <span id="geo-legend-range" class="geo-legend-range"></span>
    </div>
  </div>

  <!-- ── Data table area (60% height) ────────────────────── -->
  <div class="geo-table-area">
    <!-- KPI summary row (shown when a municipality is selected) -->
    <div id="geo-detail-bar" class="geo-detail-bar" style="display:none;">
      <div class="geo-detail-title">
        <span id="geo-info-title">Municipality</span>
        <button class="geo-detail-close" onclick="geoClosePanel()">✕ Back to all</button>
      </div>
      <div id="geo-info-kpi-bar" class="geo-info-kpi-bar"></div>
    </div>

    <div id="geo-status-bar" class="geo-status-bar">Loading map data…</div>

    <div class="geo-table-scroll">
      <table class="geo-tbl" id="geo-main-table">
        <thead>
          <tr>
            <th class="geo-th-sortable" data-sort="name" onclick="geoSortTable('name')">Name <span class="geo-sort-icon">⇅</span></th>
            <th class="geo-th-sortable" data-sort="city" onclick="geoSortTable('city')">City <span class="geo-sort-icon">⇅</span></th>
            <th class="geo-th-sortable" data-sort="address" onclick="geoSortTable('address')">Address <span class="geo-sort-icon">⇅</span></th>
            <th class="geo-th-sortable" data-sort="dist" onclick="geoSortTable('dist')">Dist. <span class="geo-sort-icon">⇅</span></th>
            <th class="geo-th-sortable geo-th-right" data-sort="revenue" onclick="geoSortTable('revenue')">Revenue <span class="geo-sort-icon">⇅</span></th>
            <th class="geo-th-sortable geo-th-right" data-sort="units" onclick="geoSortTable('units')">Units <span class="geo-sort-icon">⇅</span></th>
            <th style="width:50px;"></th>
          </tr>
        </thead>
        <tbody id="geo-main-tbody"></tbody>
      </table>
    </div>
  </div>

  <!-- ── Section 2: Stock Deployment ──────────────────────── -->
  <div class="geo-section-divider">
    <h3 class="geo-section-title">Stock Deployment</h3>
    <p class="geo-section-subtitle">Units sold to sale points — where is our product in the field?</p>
  </div>
  <div class="geo-stock-area">
    <div id="geo-stock-status" class="geo-status-bar">Loading stock data…</div>
    <div class="geo-table-scroll">
      <table class="geo-tbl geo-tbl-fixed" id="geo-stock-table">
        <colgroup>
          <col style="width:20%">
          <col style="width:13%">
          <col style="width:13%">
          <col style="width:20%">
          <col style="width:15%">
          <col style="width:19%">
        </colgroup>
        <thead>
          <tr>
            <th class="geo-th-sortable" data-sort="name" onclick="geoSortStock('name')">Location <span class="geo-sort-icon">⇅</span></th>
            <th class="geo-th-sortable geo-th-right" data-sort="pos_total" onclick="geoSortStock('pos_total')">Total POS <span class="geo-sort-icon">⇅</span></th>
            <th class="geo-th-sortable geo-th-right" data-sort="pos_stocked" onclick="geoSortStock('pos_stocked')">Stocked POS <span class="geo-sort-icon">⇅</span></th>
            <th class="geo-th-sortable geo-th-right" data-sort="coverage" onclick="geoSortStock('coverage')">Coverage <span class="geo-sort-icon">⇅</span></th>
            <th class="geo-th-sortable geo-th-right" data-sort="units" onclick="geoSortStock('units')">Units <span class="geo-sort-icon">⇅</span></th>
            <th class="geo-th-sortable geo-th-right" data-sort="revenue" onclick="geoSortStock('revenue')">Revenue <span class="geo-sort-icon">⇅</span></th>
          </tr>
        </thead>
        <tbody id="geo-stock-tbody"></tbody>
        <tfoot id="geo-stock-tfoot"></tfoot>
      </table>
    </div>
  </div>

  <!-- ── Section 3: Demand Trend + Repeat Purchases ───────── -->
  <div class="geo-section-divider">
    <h3 class="geo-section-title">Demand Over Time &amp; Repeat Purchases</h3>
    <p class="geo-section-subtitle">Monthly demand trend and purchase consistency by geography</p>
  </div>
  <div class="geo-demand-area">
    <div id="geo-demand-status" class="geo-status-bar">Loading demand data…</div>
    <!-- Demand chart -->
    <div id="geo-demand-chart-wrap" class="geo-demand-chart-wrap" style="display:none;">
      <canvas id="geo-demand-canvas" height="260"></canvas>
    </div>
    <!-- Repeat purchase table -->
    <div id="geo-repeat-area" style="display:none;">
      <h4 class="geo-repeat-title">Repeat Purchase Analysis</h4>
      <div class="geo-table-scroll">
        <table class="geo-tbl geo-tbl-fixed" id="geo-repeat-table">
          <colgroup>
            <col style="width:18%">
            <col style="width:12%">
            <col style="width:12%">
            <col style="width:14%">
            <col style="width:14%">
            <col style="width:14%">
            <col style="width:16%">
          </colgroup>
          <thead>
            <tr>
              <th class="geo-th-sortable" data-sort="name" onclick="geoSortRepeat('name')">Location <span class="geo-sort-icon">⇅</span></th>
              <th class="geo-th-sortable geo-th-right" data-sort="total_pos" onclick="geoSortRepeat('total_pos')">Total POS <span class="geo-sort-icon">⇅</span></th>
              <th class="geo-th-sortable geo-th-right" data-sort="multi_month_pos" onclick="geoSortRepeat('multi_month_pos')">2+ Months <span class="geo-sort-icon">⇅</span></th>
              <th class="geo-th-sortable geo-th-right" data-sort="multi_month_pct" onclick="geoSortRepeat('multi_month_pct')">Repeat % <span class="geo-sort-icon">⇅</span></th>
              <th class="geo-th-sortable geo-th-right" data-sort="consecutive_pos" onclick="geoSortRepeat('consecutive_pos')">Consecutive <span class="geo-sort-icon">⇅</span></th>
              <th class="geo-th-sortable geo-th-right" data-sort="consecutive_pct" onclick="geoSortRepeat('consecutive_pct')">Consec. % <span class="geo-sort-icon">⇅</span></th>
              <th class="geo-th-sortable geo-th-right" data-sort="avg_active_months" onclick="geoSortRepeat('avg_active_months')">Avg Months <span class="geo-sort-icon">⇅</span></th>
            </tr>
          </thead>
          <tbody id="geo-repeat-tbody"></tbody>
        </table>
      </div>
    </div>
  </div>

</div><!-- /#tab-geo -->


<!-- =========================================================
     GEO TAB STYLES
     ========================================================= -->
<style>
/* Controls bar */
.geo-controls-bar {{
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 14px;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}}
.geo-control-group {{
  display: flex;
  align-items: center;
  gap: 8px;
}}
.geo-label {{
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  white-space: nowrap;
}}
.geo-select {{
  font-size: 13px;
  padding: 5px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #f9fafb;
  color: #111827;
  cursor: pointer;
  outline: none;
}}
.geo-select:focus {{ border-color: #6366f1; }}

/* Toggle buttons */
.geo-toggle-group {{
  display: flex;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  overflow: hidden;
}}
.geo-toggle-btn {{
  font-size: 12px;
  padding: 5px 12px;
  border: none;
  background: #f9fafb;
  color: #374151;
  cursor: pointer;
  border-right: 1px solid #d1d5db;
}}
.geo-toggle-btn:last-child {{ border-right: none; }}
.geo-toggle-btn.geo-toggle-active {{
  background: #6366f1;
  color: #fff;
  font-weight: 600;
}}
.geo-btn-reset {{
  font-size: 12px;
  padding: 5px 14px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #f3f4f6;
  color: #374151;
  cursor: pointer;
}}
.geo-btn-reset:hover {{ background: #e5e7eb; }}

/* Map area — 50% of available height */
.geo-map-wrap {{
  position: relative;
  height: calc(50vh - 50px);
  min-height: 250px;
  background: #f0f4f8;
}}
#geo-map-canvas {{
  width: 100%;
  height: 100%;
}}
/* Legend overlay on map */
.geo-legend-overlay {{
  position: absolute;
  bottom: 8px;
  left: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255,255,255,0.92);
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 10px;
  color: #6b7280;
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  z-index: 5;
}}
.geo-legend-gradient {{
  width: 100px;
  height: 10px;
  border-radius: 4px;
  background: linear-gradient(to right, #e0e7ff, #4338ca);
}}
.geo-legend-range {{
  font-size: 10px;
  color: #6b7280;
}}

/* Data table area — 50% of available height */
.geo-table-area {{
  display: flex;
  flex-direction: column;
  height: calc(50vh - 50px);
  min-height: 250px;
  background: #fff;
  border-top: 2px solid #e5e7eb;
}}

/* Detail bar (when municipality selected) */
.geo-detail-bar {{
  padding: 10px 20px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}}
.geo-detail-title {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}}
.geo-detail-title span {{
  font-size: 15px;
  font-weight: 700;
  color: #111827;
}}
.geo-detail-close {{
  font-size: 12px;
  padding: 4px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  color: #6b7280;
  cursor: pointer;
}}
.geo-detail-close:hover {{ background: #f3f4f6; }}
.geo-info-kpi-bar {{
  display: flex;
  gap: 0;
}}
.geo-kpi-card {{
  flex: 1;
  text-align: center;
  padding: 8px 6px;
  border-right: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 6px;
  margin-right: 6px;
}}
.geo-kpi-card:last-child {{ border-right: none; margin-right:0; }}
.geo-kpi-val {{
  font-size: 16px;
  font-weight: 700;
  color: #111827;
}}
.geo-kpi-lbl {{
  font-size: 10px;
  color: #9ca3af;
  margin-top: 2px;
}}

/* Status bar */
.geo-status-bar {{
  font-size: 11px;
  color: #9ca3af;
  padding: 4px 20px;
  background: #fff;
  border-bottom: 1px solid #f3f4f6;
  min-height: 22px;
}}

/* Table scroll container */
.geo-table-scroll {{
  flex: 1;
  overflow-y: auto;
  padding: 0;
}}

/* Main data table */
.geo-tbl {{
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  color: #374151;
}}
.geo-tbl thead {{
  position: sticky;
  top: 0;
  background: #f9fafb;
  z-index: 1;
}}
.geo-tbl th {{
  padding: 8px 10px;
  font-weight: 600;
  font-size: 11px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  border-bottom: 2px solid #e5e7eb;
  text-align: left;
  white-space: nowrap;
  user-select: none;
}}
.geo-th-sortable {{ cursor: pointer; }}
.geo-th-sortable:hover {{ color: #6366f1; }}
.geo-th-right {{ text-align: left; }}
.geo-tbl-fixed {{ table-layout: fixed; }}
.geo-tbl-fixed td.geo-th-right {{ text-align: center; }}
.geo-sort-icon {{ font-size: 9px; opacity: 0.4; }}
.geo-th-sortable.geo-sort-active .geo-sort-icon {{ opacity: 1; color: #6366f1; }}
.geo-tbl td {{
  padding: 6px 10px;
  border-bottom: 1px solid #f3f4f6;
  vertical-align: middle;
}}
.geo-tbl tr:hover td {{ background: #f0f4ff; }}
.geo-tbl tr.geo-row-mun {{ cursor: pointer; }}
.geo-tbl tr.geo-row-mun:hover td {{ background: #eef2ff; }}
.geo-td-name {{ max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.geo-td-city {{ max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.geo-td-addr {{ max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #6b7280; font-size: 11px; }}
.geo-td-dist {{ font-size: 11px; color: #9ca3af; }}
.geo-td-rev {{ text-align: right; font-weight: 600; color: #6366f1; white-space: nowrap; }}
.geo-td-units {{ text-align: right; white-space: nowrap; }}
.geo-td-actions {{ text-align: center; }}
.geo-pos-empty {{
  color: #9ca3af;
  font-size: 12px;
  padding: 12px 10px;
}}

/* Editable cell */
.geo-edit-input {{
  font-size: 11px;
  padding: 3px 6px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  width: 100%;
  max-width: 150px;
  font-family: inherit;
  color: #374151;
  background: #fffbeb;
}}
.geo-edit-input:focus {{ outline: none; border-color: #6366f1; background: #fff; }}
.geo-btn-save {{
  font-size: 10px;
  padding: 2px 8px;
  border: 1px solid #6366f1;
  border-radius: 4px;
  background: #6366f1;
  color: #fff;
  cursor: pointer;
}}
.geo-btn-save:hover {{ background: #4f46e5; }}
.geo-btn-edit {{
  font-size: 10px;
  padding: 2px 8px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  background: #f9fafb;
  color: #6b7280;
  cursor: pointer;
}}
.geo-btn-edit:hover {{ background: #e5e7eb; }}
.geo-save-ok {{ color: #22c55e; font-size: 11px; font-weight: 600; }}
.geo-save-err {{ color: #ef4444; font-size: 11px; }}

/* ── Section dividers ── */
.geo-section-divider {{
  padding: 18px 16px 8px;
  border-top: 2px solid #e5e7eb;
  margin-top: 12px;
}}
.geo-section-title {{
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 2px;
}}
.geo-section-subtitle {{
  font-size: 12px;
  color: #9ca3af;
  margin: 0;
}}

/* ── Stock area ── */
.geo-stock-area {{
  padding: 0 0 12px;
}}

/* Coverage bar */
.geo-coverage-bar {{
  display: inline-block;
  width: 60px;
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
  vertical-align: middle;
  margin-right: 6px;
}}
.geo-coverage-fill {{
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}}
.geo-cov-high {{ background: #22c55e; }}
.geo-cov-mid {{ background: #f59e0b; }}
.geo-cov-low {{ background: #ef4444; }}

/* ── Demand area ── */
.geo-demand-area {{
  padding: 0 0 20px;
}}
.geo-demand-chart-wrap {{
  padding: 12px 16px;
  position: relative;
  height: 280px;
}}
.geo-repeat-title {{
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  padding: 14px 16px 6px;
  margin: 0;
}}

/* Repeat % badges */
.geo-pct-badge {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}}
.geo-pct-high {{ background: #dcfce7; color: #166534; }}
.geo-pct-mid {{ background: #fef3c7; color: #92400e; }}
.geo-pct-low {{ background: #fee2e2; color: #991b1b; }}

/* Stock table footer */
.geo-tbl tfoot td {{
  font-weight: 700;
  border-top: 2px solid #e5e7eb;
  background: #f9fafb;
}}
</style>


<!-- =========================================================
     GEO TAB JAVASCRIPT
     ========================================================= -->
<script>
// ─── State ────────────────────────────────────────────────────────────────
var _geoMap            = null;
var _geoDataLayer      = null;   // active choropleth GeoJSON layer (district OR city)
var _geoBoundaryData   = null;   // cached district GeoJSON (FeatureCollection)
var _geoCityBoundaryData = null; // cached city GeoJSON (FeatureCollection)
var _geoChoroplethData = null;   // cached KPI values per area
var _geoPosMarkers     = [];     // current POS markers array
var _geoHeatmap        = null;   // HeatmapLayer instance
var _geoPosLayer       = 'none'; // 'none' | 'markers' | 'heatmap'
var _geoSelectedMunId  = null;   // currently selected municipality_id or city_id
var _geoActiveLayer    = 'district'; // 'district' | 'city'

// Colour scale: indigo from light → dark
var GEO_COLORS = [
  '#e0e7ff','#c7d2fe','#a5b4fc','#818cf8',
  '#6366f1','#4f46e5','#4338ca','#3730a3'
];

// ─── Initialise (called by Maps JS API callback) ──────────────────────────
function geoInitMap() {{
  _geoMap = new google.maps.Map(document.getElementById('geo-map-canvas'), {{
    center:           {{ lat: 31.5, lng: 34.9 }},  // centre of Israel
    zoom:             8,
    mapTypeId:        'roadmap',
    disableDefaultUI: false,
    gestureHandling:  'cooperative',
    styles: [
      {{ featureType:'poi', elementType:'labels', stylers:[{{visibility:'off'}}] }},
      {{ featureType:'transit', stylers:[{{visibility:'off'}}] }}
    ]
  }});

  _geoDataLayer = new google.maps.Data({{ map: _geoMap }});

  // Polygon click → drill-down
  _geoDataLayer.addListener('click', function(event) {{
    var munId = (_geoActiveLayer === 'city')
      ? event.feature.getProperty('city_id')
      : event.feature.getProperty('municipality_id');
    geoOnMunicipalityClick(munId, event.feature);
  }});

  // Polygon hover highlight
  _geoDataLayer.addListener('mouseover', function(event) {{
    _geoDataLayer.overrideStyle(event.feature, {{
      strokeWeight: 2.5,
      strokeColor:  '#312e81'
    }});
  }});
  _geoDataLayer.addListener('mouseout', function(event) {{
    _geoDataLayer.revertStyle(event.feature);
  }});

  // Load boundaries once, then fetch KPI data
  geoLoadBoundaries();
}}

// ─── Load municipality/district boundaries (GeoJSON) ─────────────────────
function geoLoadBoundaries() {{
  geoSetStatus('Loading district boundaries…');
  fetch('/api/geo/municipalities?_v=' + Date.now())
    .then(function(r) {{
      if (!r.ok) throw new Error('Boundary API returned ' + r.status);
      return r.json();
    }})
    .then(function(geojson) {{
      _geoBoundaryData = geojson;
      _geoDataLayer.addGeoJson(geojson);
      geoUpdateMap();
    }})
    .catch(function(err) {{
      geoSetStatus('⚠ Could not load boundaries: ' + err.message);
      console.error(err);
    }});
}}

// ─── Layer switching (District ↔ City) ───────────────────────────────────
function geoSwitchLayer() {{
  var newLayer = document.getElementById('geo-layer-select').value;
  if (newLayer === _geoActiveLayer) return;

  _geoActiveLayer = newLayer;
  _geoSelectedMunId = null;
  document.getElementById('geo-detail-bar').style.display = 'none';
  _geoViewMode = 'summary';

  // Clear current data layer features
  _geoDataLayer.forEach(function(f) {{ _geoDataLayer.remove(f); }});
  geoClearPosLayer();

  if (newLayer === 'city') {{
    // Load city boundaries (lazy load + cache)
    if (_geoCityBoundaryData) {{
      _geoDataLayer.addGeoJson(_geoCityBoundaryData);
      geoUpdateMap();
    }} else {{
      geoSetStatus('Loading city boundaries…');
      fetch('/api/geo/cities?_t=' + Date.now(), {{cache: 'no-store'}})
        .then(function(r) {{
          if (!r.ok) throw new Error('City boundary API returned ' + r.status);
          return r.json();
        }})
        .then(function(geojson) {{
          console.log('[GEO] cities API returned', geojson.features ? geojson.features.length : 0, 'features', geojson._debug || '', geojson._load_error || '');
          if (!geojson.features || geojson.features.length === 0) {{
            geoSetStatus('⚠ No city boundaries loaded (' + (geojson._debug || 'unknown') + ')');
            return;  // Do NOT cache empty results
          }}
          _geoCityBoundaryData = geojson;
          _geoDataLayer.addGeoJson(geojson);
          geoUpdateMap();
        }})
        .catch(function(err) {{
          geoSetStatus('⚠ Could not load city boundaries: ' + err.message);
          console.error(err);
        }});
    }}
  }} else {{
    // District layer — already cached
    if (_geoBoundaryData) {{
      _geoDataLayer.addGeoJson(_geoBoundaryData);
      geoUpdateMap();
    }} else {{
      geoLoadBoundaries();
    }}
  }}
}}

// ─── Fetch choropleth KPIs and repaint ───────────────────────────────────
function geoUpdateMap() {{
  // Check that relevant boundary data is loaded
  if (_geoActiveLayer === 'city' && !_geoCityBoundaryData) return;
  if (_geoActiveLayer === 'district' && !_geoBoundaryData) return;

  var kpi   = document.getElementById('geo-kpi-select').value;
  var month = document.getElementById('geo-month-select').value;
  var dist  = document.getElementById('geo-dist-select').value;
  var brand = document.getElementById('geo-brand-select').value;

  geoSetStatus('Fetching KPI data…');

  var choroplethUrl = (_geoActiveLayer === 'city')
    ? '/api/geo/choropleth-city?kpi=' + kpi + '&month=' + month + '&distributor=' + dist + '&brand=' + brand
    : '/api/geo/choropleth?kpi=' + kpi + '&month=' + month + '&distributor=' + dist + '&brand=' + brand;

  fetch(choroplethUrl)
    .then(function(r) {{
      if (!r.ok) throw new Error('Choropleth API returned ' + r.status);
      return r.json();
    }})
    .then(function(payload) {{
      _geoChoroplethData = payload.data;
      geoPaintChoropleth(kpi);
      if (_geoPosLayer !== 'none') {{
        geoClearPosLayer();
        if (_geoSelectedMunId) {{
          geoLoadPosForMunicipality(_geoSelectedMunId);
        }}
      }}
      // Refresh drill-down if open, else show municipality summary
      if (_geoSelectedMunId && _geoChoroplethData) {{
        var d = _geoChoroplethData[_geoSelectedMunId] || {{}};
        document.getElementById('geo-info-kpi-bar').innerHTML =
          '<div class="geo-kpi-card"><div class="geo-kpi-val">' + geoFmt(d.revenue||0,'revenue') + '</div><div class="geo-kpi-lbl">Revenue</div></div>' +
          '<div class="geo-kpi-card"><div class="geo-kpi-val">' + (d.units||0).toLocaleString() + '</div><div class="geo-kpi-lbl">Units</div></div>' +
          '<div class="geo-kpi-card"><div class="geo-kpi-val">' + (d.pos_count||0) + '</div><div class="geo-kpi-lbl">POS</div></div>';
        geoLoadPosForMunicipality(_geoSelectedMunId);
      }} else {{
        geoRenderMunicipalitySummary();
      }}
    }})
    .catch(function(err) {{
      geoSetStatus('⚠ KPI fetch failed: ' + err.message);
      console.error(err);
    }});
}}

// ─── Colour the polygons ─────────────────────────────────────────────────
function geoPaintChoropleth(kpi) {{
  if (!_geoChoroplethData) return;

  // Find min/max for the selected KPI
  var values = Object.values(_geoChoroplethData).map(function(d) {{
    return d[kpi] || 0;
  }});
  var maxVal = Math.max.apply(null, values);
  var minVal = 0;

  _geoDataLayer.setStyle(function(feature) {{
    var munId = (_geoActiveLayer === 'city')
      ? feature.getProperty('city_id')
      : feature.getProperty('municipality_id');
    var val   = (_geoChoroplethData[munId] && _geoChoroplethData[munId][kpi]) || 0;
    var color = geoValueToColor(val, minVal, maxVal);
    return {{
      fillColor:   color,
      fillOpacity: val > 0 ? 0.72 : 0.12,
      strokeColor: '#6366f1',
      strokeWeight: 0.6,
      strokeOpacity: 0.6,
    }};
  }});

  // Update legend
  var kpiLabel = {{ revenue:'Revenue (₪)', units:'Units', pos_count:'POS Count' }}[kpi];
  document.getElementById('geo-legend-range').textContent =
    geoFmt(minVal, kpi) + ' – ' + geoFmt(maxVal, kpi);

  var n = Object.values(_geoChoroplethData).filter(function(d) {{
    return (d[kpi] || 0) > 0;
  }}).length;
  var _monthSel = document.getElementById('geo-month-select');
  var _monthLabel = _monthSel.value !== 'all' ? _monthSel.options[_monthSel.selectedIndex].text : '';
  geoSetStatus(
    n + ' municipalities with ' + kpiLabel + ' data' +
    (_monthLabel ? ' · ' + _monthLabel : '')
  );
}}

// Map a value 0–max to one of the GEO_COLORS steps
function geoValueToColor(val, min, max) {{
  if (max === 0) return GEO_COLORS[0];
  var ratio = (val - min) / (max - min);
  var idx   = Math.min(Math.floor(ratio * GEO_COLORS.length), GEO_COLORS.length - 1);
  return GEO_COLORS[idx];
}}

// ─── Municipality click → drill-down (shows in table below map) ─────────
function geoOnMunicipalityClick(munId, feature) {{
  _geoSelectedMunId = munId;
  _geoViewMode = 'detail';

  // If called from table row, find the feature from the data layer
  if (!feature) {{
    var idProp = (_geoActiveLayer === 'city') ? 'city_id' : 'municipality_id';
    _geoDataLayer.forEach(function(f) {{
      if (f.getProperty(idProp) == munId) feature = f;
    }});
  }}

  var nameHe = feature ? (feature.getProperty('name_he') || '') : '';
  var nameEn = feature ? (feature.getProperty('name_en') || munId) : munId;
  var title  = nameEn + (nameHe ? ' · ' + nameHe : '');

  document.getElementById('geo-info-title').textContent = title;

  // KPI bar
  var d = (_geoChoroplethData && _geoChoroplethData[munId]) || {{}};
  document.getElementById('geo-info-kpi-bar').innerHTML =
    '<div class="geo-kpi-card"><div class="geo-kpi-val">' + geoFmt(d.revenue||0,'revenue') + '</div><div class="geo-kpi-lbl">Revenue</div></div>' +
    '<div class="geo-kpi-card"><div class="geo-kpi-val">' + (d.units||0).toLocaleString() + '</div><div class="geo-kpi-lbl">Units</div></div>' +
    '<div class="geo-kpi-card"><div class="geo-kpi-val">' + (d.pos_count||0) + '</div><div class="geo-kpi-lbl">POS</div></div>';

  document.getElementById('geo-detail-bar').style.display = '';
  document.getElementById('geo-main-tbody').innerHTML =
    '<tr><td colspan="7" class="geo-pos-empty">Loading…</td></tr>';

  // Zoom to municipality bounds
  if (feature) {{
    var bounds = new google.maps.LatLngBounds();
    feature.getGeometry().forEachLatLng(function(pt) {{ bounds.extend(pt); }});
    _geoMap.fitBounds(bounds, {{ top:20, right:20, bottom:20, left:20 }});
  }}

  geoLoadPosForMunicipality(munId);
}}

function geoClosePanel() {{
  document.getElementById('geo-detail-bar').style.display = 'none';
  _geoSelectedMunId = null;
  _geoViewMode = 'summary';
  geoClearPosLayer();
  geoRenderMunicipalitySummary();
}}

// ─── POS loading ─────────────────────────────────────────────────────────
function geoLoadPosForMunicipality(munId) {{
  var month = document.getElementById('geo-month-select').value;
  var dist  = document.getElementById('geo-dist-select').value;
  var brand = document.getElementById('geo-brand-select').value;

  fetch('/api/geo/pos?municipality_id=' + munId + '&month=' + month + '&distributor=' + dist + '&brand=' + brand + '&layer=' + _geoActiveLayer)
    .then(function(r) {{ return r.json(); }})
    .then(function(payload) {{
      var posList = payload.data || [];
      geoRenderPosLayer(posList);
      geoRenderPosList(posList);
    }})
    .catch(function(err) {{
      console.error('POS load error:', err);
    }});
}}

// ─── POS layer rendering ─────────────────────────────────────────────────
function geoRenderPosLayer(posList) {{
  geoClearPosLayer();
  if (_geoPosLayer === 'none' || !posList.length) return;

  var kpi = document.getElementById('geo-kpi-select').value;

  if (_geoPosLayer === 'markers') {{
    posList.forEach(function(pos) {{
      var marker = new google.maps.Marker({{
        position: {{ lat: pos.latitude, lng: pos.longitude }},
        map:      _geoMap,
        title:    pos.pos_name,
        icon: {{
          path:        google.maps.SymbolPath.CIRCLE,
          scale:       6 + Math.min(pos[kpi === 'revenue' ? 'revenue_ils' : 'units_sold'] / 500, 8),
          fillColor:   _geoDistColor(pos.distributor),
          fillOpacity: 0.9,
          strokeColor: '#fff',
          strokeWeight: 1.5,
        }}
      }});

      var infoWindow = new google.maps.InfoWindow({{
        content:
          '<div style="font-size:13px;line-height:1.6;padding:4px 6px;">' +
          '<strong>' + pos.pos_name + '</strong><br>' +
          '₪' + (pos.revenue_ils||0).toLocaleString() + ' · ' +
          (pos.units_sold||0).toLocaleString() + ' units<br>' +
          '<span style="color:#9ca3af;">' + pos.distributor + '</span>' +
          '</div>'
      }});
      marker.addListener('click', function() {{
        infoWindow.open(_geoMap, marker);
      }});

      _geoPosMarkers.push(marker);
    }});

  }} else if (_geoPosLayer === 'heatmap') {{
    var heatData = posList.map(function(pos) {{
      var weight = (kpi === 'revenue')
        ? pos.revenue_ils || 0
        : pos.units_sold  || 0;
      return {{
        location: new google.maps.LatLng(pos.latitude, pos.longitude),
        weight:   Math.max(weight, 1)
      }};
    }});
    _geoHeatmap = new google.maps.visualization.HeatmapLayer({{
      data:    heatData,
      map:     _geoMap,
      radius:  30,
      opacity: 0.75,
      gradient: [
        'rgba(99,102,241,0)',
        'rgba(99,102,241,0.4)',
        'rgba(79,70,229,0.7)',
        'rgba(67,56,202,0.9)',
        'rgba(55,48,163,1)'
      ]
    }});
  }}
}}

function geoClearPosLayer() {{
  _geoPosMarkers.forEach(function(m) {{ m.setMap(null); }});
  _geoPosMarkers = [];
  if (_geoHeatmap) {{ _geoHeatmap.setMap(null); _geoHeatmap = null; }}
}}

// ─── Table data ─────────────────────────────────────────────────────────
var _geoCurrentPosList = [];
var _geoSortKey = 'revenue';
var _geoSortAsc = false;
var _geoViewMode = 'summary';  // 'summary' | 'detail'
var _geoEditingId = null;  // pos_id being edited

var _geoDistLabels = {{ icedream:'Icedream', mayyan:"Ma\\x27ayan", biscotti:'Biscotti', karfree:'Karfree' }};

// ── Municipality/City summary table (default view) ──
function geoRenderMunicipalitySummary() {{
  if (!_geoChoroplethData) return;
  // Ensure the relevant boundary data is loaded
  if (_geoActiveLayer === 'city' && !_geoCityBoundaryData) return;
  if (_geoActiveLayer === 'district' && !_geoBoundaryData) return;

  _geoViewMode = 'summary';
  _geoSortKey = 'revenue';
  _geoSortAsc = false;

  // Build array of area data
  var munList = [];
  _geoDataLayer.forEach(function(feature) {{
    var munId = (_geoActiveLayer === 'city')
      ? feature.getProperty('city_id')
      : feature.getProperty('municipality_id');
    var d = _geoChoroplethData[munId] || {{}};
    munList.push({{
      munId: munId,
      name: feature.getProperty('name_en') || '',
      nameHe: feature.getProperty('name_he') || '',
      revenue: d.revenue || 0,
      units: d.units || 0,
      pos_count: d.pos_count || 0,
      feature: feature
    }});
  }});

  // Sort by revenue desc
  munList.sort(function(a,b) {{ return b.revenue - a.revenue; }});
  _geoCurrentPosList = munList;

  var kpiLabel = document.getElementById('geo-kpi-select').value;
  var areaLabel = (_geoActiveLayer === 'city') ? 'cities' : 'districts';
  geoSetStatus(munList.length + ' ' + areaLabel);

  _geoRenderMunRows(munList);
}}

function _geoRenderMunRows(list) {{
  var tbody = document.getElementById('geo-main-tbody');
  var totRev = 0, totUnits = 0, totPOS = 0;

  var rows = list.map(function(m, i) {{
    totRev += m.revenue;
    totUnits += m.units;
    totPOS += m.pos_count;
    return '<tr class="geo-row-mun" onclick="geoOnMunicipalityClick(\\x27' + m.munId + '\\x27, null)" data-mun-id="' + m.munId + '">' +
      '<td class="geo-td-name" title="' + (m.nameHe||'').replace(/"/g,'&quot;') + '">' + (m.name || m.nameHe || m.munId) + '</td>' +
      '<td class="geo-td-city">' + (m.nameHe || '') + '</td>' +
      '<td class="geo-td-addr">—</td>' +
      '<td class="geo-td-dist">' + m.pos_count + ' POS</td>' +
      '<td class="geo-td-rev">₪' + Math.round(m.revenue).toLocaleString() + '</td>' +
      '<td class="geo-td-units">' + m.units.toLocaleString() + '</td>' +
      '<td></td>' +
    '</tr>';
  }}).join('');

  rows += '<tr style="font-weight:700;border-top:2px solid #e5e7eb;background:#f9fafb;">' +
    '<td colspan="3" style="padding:8px 10px;">Total (' + list.length + ' ' + ((_geoActiveLayer === 'city') ? 'cities' : 'districts') + ')</td>' +
    '<td style="padding:8px 10px;">' + totPOS + ' POS</td>' +
    '<td class="geo-td-rev" style="padding:8px 10px;">₪' + Math.round(totRev).toLocaleString() + '</td>' +
    '<td class="geo-td-units" style="padding:8px 10px;">' + totUnits.toLocaleString() + '</td>' +
    '<td></td></tr>';

  tbody.innerHTML = rows;
  _geoUpdateSortIndicator();
}}

// ── POS detail table (after clicking a municipality) ──
function geoRenderPosList(posList) {{
  _geoCurrentPosList = posList;
  _geoSortKey = 'revenue';
  _geoSortAsc = false;
  _geoEditingId = null;

  var tbody = document.getElementById('geo-main-tbody');

  if (!posList.length) {{
    tbody.innerHTML = '<tr><td colspan="7" class="geo-pos-empty">No POS data for this selection.</td></tr>';
    return;
  }}

  posList.sort(function(a,b) {{ return (b.revenue_ils||0) - (a.revenue_ils||0); }});
  _geoRenderPosRows(posList);
}}

function _geoRenderPosRows(posList) {{
  var tbody = document.getElementById('geo-main-tbody');
  var totRev = 0, totUnits = 0;

  var rows = posList.map(function(pos) {{
    var rev = pos.revenue_ils || 0;
    var units = pos.units_sold || 0;
    totRev += rev;
    totUnits += units;
    var distLabel = _geoDistLabels[pos.distributor] || pos.distributor || '—';
    var city = pos.address_city || pos.geo_municipality || '';
    var addr = pos.address_street || '';
    var isEditing = (_geoEditingId === pos.pos_id);

    if (isEditing) {{
      return '<tr data-pos-id="' + pos.pos_id + '">' +
        '<td class="geo-td-name" title="' + (pos.pos_name||'').replace(/"/g,'&quot;') + '">' + (pos.pos_name||'–') + '</td>' +
        '<td><input class="geo-edit-input" id="geo-edit-city-' + pos.pos_id + '" value="' + city.replace(/"/g,'&quot;') + '" placeholder="City"></td>' +
        '<td><input class="geo-edit-input" id="geo-edit-addr-' + pos.pos_id + '" value="' + addr.replace(/"/g,'&quot;') + '" placeholder="Street address"></td>' +
        '<td class="geo-td-dist">' + distLabel + '</td>' +
        '<td class="geo-td-rev">₪' + rev.toLocaleString() + '</td>' +
        '<td class="geo-td-units">' + units.toLocaleString() + '</td>' +
        '<td class="geo-td-actions"><button class="geo-btn-save" onclick="geoSavePos(' + pos.pos_id + ')">Save</button></td>' +
      '</tr>';
    }}

    return '<tr data-pos-id="' + pos.pos_id + '">' +
      '<td class="geo-td-name" title="' + (pos.pos_name||'').replace(/"/g,'&quot;') + '">' + (pos.pos_name||'–') + '</td>' +
      '<td class="geo-td-city" title="' + city.replace(/"/g,'&quot;') + '">' + (city || '<span style="color:#d1d5db">—</span>') + '</td>' +
      '<td class="geo-td-addr" title="' + addr.replace(/"/g,'&quot;') + '">' + (addr || '<span style="color:#d1d5db">—</span>') + '</td>' +
      '<td class="geo-td-dist">' + distLabel + '</td>' +
      '<td class="geo-td-rev">₪' + rev.toLocaleString() + '</td>' +
      '<td class="geo-td-units">' + units.toLocaleString() + '</td>' +
      '<td class="geo-td-actions"><button class="geo-btn-edit" onclick="geoEditPos(' + pos.pos_id + ')">Edit</button></td>' +
    '</tr>';
  }}).join('');

  rows += '<tr style="font-weight:700;border-top:2px solid #e5e7eb;background:#f9fafb;">' +
    '<td colspan="4" style="padding:8px 10px;">Total (' + posList.length + ' POS)</td>' +
    '<td class="geo-td-rev" style="padding:8px 10px;">₪' + totRev.toLocaleString() + '</td>' +
    '<td class="geo-td-units" style="padding:8px 10px;">' + totUnits.toLocaleString() + '</td>' +
    '<td></td></tr>';

  tbody.innerHTML = rows;
  _geoUpdateSortIndicator();
}}

// ── Inline edit functions ──
function geoEditPos(posId) {{
  _geoEditingId = posId;
  _geoRenderPosRows(_geoCurrentPosList.slice().sort(_geoSortFn()));
  // Auto-focus the city field
  var cityInput = document.getElementById('geo-edit-city-' + posId);
  if (cityInput) cityInput.focus();
}}

function geoSavePos(posId) {{
  var cityEl = document.getElementById('geo-edit-city-' + posId);
  var addrEl = document.getElementById('geo-edit-addr-' + posId);
  if (!cityEl || !addrEl) return;

  var newCity = cityEl.value.trim();
  var newAddr = addrEl.value.trim();

  // Save to DB via API
  fetch('/api/geo/update-pos', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{
      pos_id: posId,
      address_city: newCity,
      address_street: newAddr
    }})
  }})
  .then(function(r) {{ return r.json(); }})
  .then(function(result) {{
    if (result.error) {{
      alert('Save failed: ' + result.error);
      return;
    }}
    // Update local cache
    _geoCurrentPosList.forEach(function(p) {{
      if (p.pos_id === posId) {{
        p.address_city = newCity;
        p.address_street = newAddr;
        p.geo_municipality = newCity;
      }}
    }});
    _geoEditingId = null;
    _geoRenderPosRows(_geoCurrentPosList.slice().sort(_geoSortFn()));
  }})
  .catch(function(err) {{
    alert('Save failed: ' + err.message);
  }});
}}

function _geoUpdateSortIndicator() {{
  document.querySelectorAll('.geo-th-sortable').forEach(function(th) {{
    th.classList.toggle('geo-sort-active', th.getAttribute('data-sort') === _geoSortKey);
    var icon = th.querySelector('.geo-sort-icon');
    if (icon) icon.textContent = th.getAttribute('data-sort') === _geoSortKey ? (_geoSortAsc ? '↑' : '↓') : '⇅';
  }});
}}

function _geoSortFn() {{
  var key = _geoSortKey;
  var asc = _geoSortAsc;
  return function(a,b) {{
    var va, vb;
    if (_geoViewMode === 'summary') {{
      if (key === 'name') {{ va = (a.name||'').toLowerCase(); vb = (b.name||'').toLowerCase(); }}
      else if (key === 'city') {{ va = (a.nameHe||'').toLowerCase(); vb = (b.nameHe||'').toLowerCase(); }}
      else if (key === 'revenue') {{ va = a.revenue||0; vb = b.revenue||0; }}
      else if (key === 'units') {{ va = a.units||0; vb = b.units||0; }}
      else {{ va = 0; vb = 0; }}
    }} else {{
      if (key === 'name') {{ va = (a.pos_name||'').toLowerCase(); vb = (b.pos_name||'').toLowerCase(); }}
      else if (key === 'city') {{ va = (a.address_city||a.geo_municipality||'').toLowerCase(); vb = (b.address_city||b.geo_municipality||'').toLowerCase(); }}
      else if (key === 'address') {{ va = (a.address_street||'').toLowerCase(); vb = (b.address_street||'').toLowerCase(); }}
      else if (key === 'dist') {{ va = a.distributor||''; vb = b.distributor||''; }}
      else if (key === 'revenue') {{ va = a.revenue_ils||0; vb = b.revenue_ils||0; }}
      else {{ va = a.units_sold||0; vb = b.units_sold||0; }}
    }}
    if (va < vb) return asc ? -1 : 1;
    if (va > vb) return asc ? 1 : -1;
    return 0;
  }};
}}

function geoSortTable(key) {{
  if (!_geoCurrentPosList.length) return;

  if (_geoSortKey === key) {{
    _geoSortAsc = !_geoSortAsc;
  }} else {{
    _geoSortKey = key;
    _geoSortAsc = (key === 'name' || key === 'dist' || key === 'city' || key === 'address');
  }}

  var sorted = _geoCurrentPosList.slice().sort(_geoSortFn());
  if (_geoViewMode === 'summary') {{
    _geoRenderMunRows(sorted);
  }} else {{
    _geoRenderPosRows(sorted);
  }}
}}

// ─── Layer toggle ─────────────────────────────────────────────────────────
function geoSetPosLayer(mode) {{
  _geoPosLayer = mode;
  ['none','markers','heatmap'].forEach(function(m) {{
    var btn = document.getElementById('geo-btn-' + m);
    if (btn) btn.classList.toggle('geo-toggle-active', m === mode);
  }});
  if (_geoSelectedMunId) {{
    geoLoadPosForMunicipality(_geoSelectedMunId);
  }} else {{
    geoClearPosLayer();
  }}
}}

// ─── Reset view ───────────────────────────────────────────────────────────
function geoResetView() {{
  if (!_geoMap) return;
  _geoMap.setCenter({{ lat: 31.5, lng: 34.9 }});
  _geoMap.setZoom(8);
  geoClosePanel();  // also renders municipality summary
}}

// ─── Helpers ─────────────────────────────────────────────────────────────
function geoFmt(val, kpi) {{
  if (kpi === 'revenue') return '₪' + Math.round(val).toLocaleString();
  return Math.round(val).toLocaleString();
}}

function _geoDistColor(dist) {{
  return {{ icedream:'#6366f1', mayyan:'#22c55e', biscotti:'#f59e0b' }}[dist] || '#94a3b8';
}}

function geoSetStatus(msg) {{
  var el = document.getElementById('geo-status-bar');
  if (el) el.textContent = msg;
}}

// ─── Export POS addresses as CSV ─────────────────────────────────────────
function geoExportAddressCSV() {{
  var filterRadio = document.querySelector('input[name="emc-geo-filter"]:checked');
  var filterVal = filterRadio ? filterRadio.value : 'all';

  geoSetStatus('Fetching all POS data for export…');

  // Fetch ALL POS (no municipality filter) with current distributor/brand/month
  var month = document.getElementById('geo-month-select').value;
  var dist  = document.getElementById('geo-dist-select').value;
  var brand = document.getElementById('geo-brand-select').value;

  fetch('/api/geo/export-addresses?filter=' + filterVal + '&month=' + month + '&distributor=' + dist + '&brand=' + brand)
    .then(function(r) {{
      if (!r.ok) throw new Error('Export API returned ' + r.status);
      return r.json();
    }})
    .then(function(payload) {{
      var rows = payload.data || [];
      if (!rows.length) {{
        geoSetStatus('No POS data to export.');
        return;
      }}
      // Build CSV
      var csv = 'pos_id,pos_name,address_city,address_street\\n';
      rows.forEach(function(r) {{
        csv += r.pos_id + ',' +
          _geoCsvEsc(r.pos_name) + ',' +
          _geoCsvEsc(r.address_city) + ',' +
          _geoCsvEsc(r.address_street) + '\\n';
      }});

      // Trigger download
      var blob = new Blob([new Uint8Array([0xEF,0xBB,0xBF]), csv], {{ type: 'text/csv;charset=utf-8;' }});
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = 'raito_pos_addresses_' + new Date().toISOString().slice(0,10) + '.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      geoSetStatus('Exported ' + rows.length + ' POS addresses.');
    }})
    .catch(function(err) {{
      geoSetStatus('⚠ Export failed: ' + err.message);
      console.error(err);
    }});
}}

function _geoCsvEsc(val) {{
  if (val == null) return '';
  var s = String(val);
  if (s.indexOf(',') !== -1 || s.indexOf('"') !== -1 || s.indexOf('\\n') !== -1) {{
    return '"' + s.replace(/"/g, '""') + '"';
  }}
  return s;
}}

// ═══════════════════════════════════════════════════════════════════════════
// SECTION 2: Stock Deployment
// ═══════════════════════════════════════════════════════════════════════════

var _geoStockData = null;
var _geoStockSort = {{ col: 'units', asc: false }};

function geoLoadStock() {{
  var layer = document.getElementById('geo-layer-select').value;
  var month = document.getElementById('geo-month-select').value;
  var dist  = document.getElementById('geo-dist-select').value;
  var brand = document.getElementById('geo-brand-select').value;

  var el = document.getElementById('geo-stock-status');
  if (el) el.textContent = 'Loading stock data…';

  fetch('/api/geo/stock?layer=' + layer + '&month=' + month + '&distributor=' + dist + '&brand=' + brand + '&_v=' + Date.now())
    .then(function(r) {{ if (!r.ok) throw new Error('Stock API ' + r.status); return r.json(); }})
    .then(function(payload) {{
      _geoStockData = payload.data;
      geoRenderStockTable();
    }})
    .catch(function(err) {{
      if (el) el.textContent = '⚠ ' + err.message;
    }});
}}

function geoRenderStockTable() {{
  var data = _geoStockData;
  if (!data) return;

  var rows = Object.keys(data).map(function(k) {{
    var d = data[k];
    d._id = k;
    d.coverage = d.pos_total > 0 ? Math.round(d.pos_stocked / d.pos_total * 100) : 0;
    return d;
  }});

  // Sort
  var col = _geoStockSort.col;
  var asc = _geoStockSort.asc;
  rows.sort(function(a, b) {{
    var va = col === 'name' ? (a.name || '').toLowerCase() : (a[col] || 0);
    var vb = col === 'name' ? (b.name || '').toLowerCase() : (b[col] || 0);
    if (va < vb) return asc ? -1 : 1;
    if (va > vb) return asc ? 1 : -1;
    return 0;
  }});

  // Filter out zero-data rows
  rows = rows.filter(function(r) {{ return r.units > 0 || r.pos_stocked > 0; }});

  var tbody = document.getElementById('geo-stock-tbody');
  var html = '';
  var totals = {{ pos_total: 0, pos_stocked: 0, units: 0, revenue: 0 }};

  rows.forEach(function(r) {{
    var covClass = r.coverage >= 70 ? 'geo-cov-high' : r.coverage >= 40 ? 'geo-cov-mid' : 'geo-cov-low';
    html += '<tr>'
      + '<td style="font-weight:500;">' + (r.name || '—') + '</td>'
      + '<td class="geo-th-right">' + r.pos_total.toLocaleString() + '</td>'
      + '<td class="geo-th-right">' + r.pos_stocked.toLocaleString() + '</td>'
      + '<td class="geo-th-right"><div class="geo-coverage-bar"><div class="geo-coverage-fill ' + covClass + '" style="width:' + r.coverage + '%;"></div></div>' + r.coverage + '%</td>'
      + '<td class="geo-th-right" style="font-weight:600;">' + r.units.toLocaleString() + '</td>'
      + '<td class="geo-th-right">₪' + Math.round(r.revenue).toLocaleString() + '</td>'
      + '</tr>';
    totals.pos_total += r.pos_total;
    totals.pos_stocked += r.pos_stocked;
    totals.units += r.units;
    totals.revenue += r.revenue;
  }});
  tbody.innerHTML = html;

  // Footer totals
  var tfoot = document.getElementById('geo-stock-tfoot');
  var totalCov = totals.pos_total > 0 ? Math.round(totals.pos_stocked / totals.pos_total * 100) : 0;
  tfoot.innerHTML = '<tr>'
    + '<td style="font-weight:700;">Total (' + rows.length + ' areas)</td>'
    + '<td class="geo-th-right">' + totals.pos_total.toLocaleString() + '</td>'
    + '<td class="geo-th-right">' + totals.pos_stocked.toLocaleString() + '</td>'
    + '<td class="geo-th-right">' + totalCov + '%</td>'
    + '<td class="geo-th-right" style="font-weight:700;">' + totals.units.toLocaleString() + '</td>'
    + '<td class="geo-th-right" style="font-weight:700;">₪' + Math.round(totals.revenue).toLocaleString() + '</td>'
    + '</tr>';

  var el = document.getElementById('geo-stock-status');
  if (el) el.textContent = rows.length + ' areas with stock deployed';
}}

function geoSortStock(col) {{
  if (_geoStockSort.col === col) _geoStockSort.asc = !_geoStockSort.asc;
  else {{ _geoStockSort.col = col; _geoStockSort.asc = col === 'name'; }}
  geoRenderStockTable();
}}


// ═══════════════════════════════════════════════════════════════════════════
// SECTION 3: Demand Trend + Repeat Purchases
// ═══════════════════════════════════════════════════════════════════════════

var _geoDemandChart = null;
var _geoRepeatData = null;
var _geoRepeatSort = {{ col: 'multi_month_pct', asc: false }};

function geoLoadDemand() {{
  var layer = document.getElementById('geo-layer-select').value;
  var dist  = document.getElementById('geo-dist-select').value;
  var brand = document.getElementById('geo-brand-select').value;

  var el = document.getElementById('geo-demand-status');
  if (el) el.textContent = 'Loading demand trend…';

  fetch('/api/geo/demand-trend?layer=' + layer + '&distributor=' + dist + '&brand=' + brand + '&_v=' + Date.now())
    .then(function(r) {{ if (!r.ok) throw new Error('Demand API ' + r.status); return r.json(); }})
    .then(function(payload) {{
      geoRenderDemandChart(payload.monthly);
      _geoRepeatData = payload.repeat;
      geoRenderRepeatTable();
      if (el) el.textContent = '';
      el.style.display = 'none';
    }})
    .catch(function(err) {{
      if (el) {{ el.textContent = '⚠ ' + err.message; el.style.display = ''; }}
    }});
}}

function geoRenderDemandChart(monthly) {{
  if (!monthly || !monthly.length) return;

  var wrap = document.getElementById('geo-demand-chart-wrap');
  wrap.style.display = '';

  var labels = monthly.map(function(m) {{ return m.label; }});

  // Aggregate total units & revenue across all geos per month
  var totalUnits = monthly.map(function(m) {{
    var sum = 0;
    Object.values(m.data).forEach(function(d) {{ sum += d.units; }});
    return sum;
  }});
  var totalRevenue = monthly.map(function(m) {{
    var sum = 0;
    Object.values(m.data).forEach(function(d) {{ sum += d.revenue; }});
    return Math.round(sum);
  }});
  var totalPOS = monthly.map(function(m) {{
    var sum = 0;
    Object.values(m.data).forEach(function(d) {{ sum += d.active_pos; }});
    return sum;
  }});

  // Destroy old chart
  if (_geoDemandChart) {{ _geoDemandChart.destroy(); _geoDemandChart = null; }}

  var ctx = document.getElementById('geo-demand-canvas').getContext('2d');
  _geoDemandChart = new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: labels,
      datasets: [
        {{
          label: 'Units',
          data: totalUnits,
          backgroundColor: 'rgba(99,102,241,0.7)',
          borderRadius: 4,
          yAxisID: 'y',
          order: 2,
        }},
        {{
          label: 'Revenue (₪)',
          data: totalRevenue,
          type: 'line',
          borderColor: '#22c55e',
          backgroundColor: 'rgba(34,197,94,0.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 4,
          borderWidth: 2,
          yAxisID: 'y1',
          order: 1,
        }},
        {{
          label: 'Active POS',
          data: totalPOS,
          type: 'line',
          borderColor: '#f59e0b',
          borderDash: [5, 3],
          pointRadius: 3,
          borderWidth: 2,
          yAxisID: 'y2',
          order: 0,
        }}
      ]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ position: 'top', labels: {{ boxWidth: 12, padding: 14, font: {{ size: 11 }} }} }},
        tooltip: {{
          callbacks: {{
            label: function(ctx) {{
              var v = ctx.parsed.y;
              if (ctx.dataset.label.indexOf('Revenue') !== -1) return 'Revenue: ₪' + v.toLocaleString();
              return ctx.dataset.label + ': ' + v.toLocaleString();
            }}
          }}
        }}
      }},
      scales: {{
        x: {{ grid: {{ display: false }} }},
        y: {{
          position: 'left',
          title: {{ display: true, text: 'Units', font: {{ size: 11 }} }},
          ticks: {{ callback: function(v) {{ return v >= 1000 ? Math.round(v/1000) + 'K' : v; }} }}
        }},
        y1: {{
          position: 'right',
          title: {{ display: true, text: 'Revenue (₪)', font: {{ size: 11 }} }},
          grid: {{ drawOnChartArea: false }},
          ticks: {{ callback: function(v) {{ return '₪' + (v >= 1000 ? Math.round(v/1000) + 'K' : v); }} }}
        }},
        y2: {{
          display: false,
        }}
      }}
    }}
  }});
}}

function geoRenderRepeatTable() {{
  var data = _geoRepeatData;
  if (!data) return;

  document.getElementById('geo-repeat-area').style.display = '';

  var rows = Object.keys(data).map(function(k) {{
    var d = data[k];
    d._id = k;
    return d;
  }});

  // Sort
  var col = _geoRepeatSort.col;
  var asc = _geoRepeatSort.asc;
  rows.sort(function(a, b) {{
    var va = col === 'name' ? (a.name || '').toLowerCase() : (a[col] || 0);
    var vb = col === 'name' ? (b.name || '').toLowerCase() : (b[col] || 0);
    if (va < vb) return asc ? -1 : 1;
    if (va > vb) return asc ? 1 : -1;
    return 0;
  }});

  // Filter out areas with no POS
  rows = rows.filter(function(r) {{ return r.total_pos > 0; }});

  var tbody = document.getElementById('geo-repeat-tbody');
  var html = '';
  rows.forEach(function(r) {{
    var rpClass = r.multi_month_pct >= 60 ? 'geo-pct-high' : r.multi_month_pct >= 30 ? 'geo-pct-mid' : 'geo-pct-low';
    var cpClass = r.consecutive_pct >= 60 ? 'geo-pct-high' : r.consecutive_pct >= 30 ? 'geo-pct-mid' : 'geo-pct-low';
    html += '<tr>'
      + '<td style="font-weight:500;">' + (r.name || '—') + '</td>'
      + '<td class="geo-th-right">' + r.total_pos + '</td>'
      + '<td class="geo-th-right">' + r.multi_month_pos + '</td>'
      + '<td class="geo-th-right"><span class="geo-pct-badge ' + rpClass + '">' + r.multi_month_pct + '%</span></td>'
      + '<td class="geo-th-right">' + r.consecutive_pos + '</td>'
      + '<td class="geo-th-right"><span class="geo-pct-badge ' + cpClass + '">' + r.consecutive_pct + '%</span></td>'
      + '<td class="geo-th-right">' + r.avg_active_months + ' / ' + r.total_months + '</td>'
      + '</tr>';
  }});
  tbody.innerHTML = html;
}}

function geoSortRepeat(col) {{
  if (_geoRepeatSort.col === col) _geoRepeatSort.asc = !_geoRepeatSort.asc;
  else {{ _geoRepeatSort.col = col; _geoRepeatSort.asc = col === 'name'; }}
  geoRenderRepeatTable();
}}


// ─── Hook stock + demand into the existing filter change flow ────────────
var _origGeoUpdateMap = geoUpdateMap;
geoUpdateMap = function() {{
  _origGeoUpdateMap();
  geoLoadStock();
  geoLoadDemand();
}};

// ─── Expose init for Maps API callback ───────────────────────────────────
window.geoInitMap = geoInitMap;
</script>

<!-- Google Maps JS API — loaded last so geoInitMap is defined first -->
<!-- The visualization library is required for HeatmapLayer -->
<script
  src="https://maps.googleapis.com/maps/api/js?key={MAPS_API_KEY}&libraries=visualization&callback=geoInitMap&loading=async"
  async defer>
</script>
"""


def _get_month_labels(data: dict) -> list:
    """
    Extract ordered month labels from the consolidated data dict.
    Returns list of dicts with 'value' (YYYY-MM for API) and 'label' (display name).
    Example: [{'value': '2025-12', 'label': "Dec '25"}, {'value': '2026-01', 'label': "Jan '26"}, …]
    """
    from config import MONTH_ORDER, MONTH_NAMES_HEB, MONTH_TO_API

    months = data.get('months', [])
    result = []
    for m in months:
        api_val = MONTH_TO_API.get(m)
        label = MONTH_NAMES_HEB.get(m, m)
        if api_val:
            result.append({'value': api_val, 'label': label})
    return result
