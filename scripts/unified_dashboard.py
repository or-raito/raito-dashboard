#!/usr/bin/env python3
"""
Raito Unified Dashboard — Multi-Tab HTML Generator
Combines Business Overview, Customer Performance, and Master Data into a single dashboard.
"""

import json
import re
from pathlib import Path
from datetime import datetime

from config import (
    BASE_DIR, OUTPUT_DIR, MONTH_NAMES_HEB, BRAND_FILTERS,
    PRODUCT_NAMES, PRODUCT_SHORT, PRODUCT_STATUS,
    FLAVOR_COLORS, PRODUCTS_ORDER, fmt, fc,
)
from registry import CUSTOMER_NAMES_EN
from dashboard import _build_month_section, _build_excel_data_json
from master_data_parser import parse_master_data
from salepoint_dashboard import build_salepoint_tab
from salepoint_excel import generate_salepoint_excel
from cc_dashboard import build_cc_tab
from pricing_engine import get_b2b_price_safe


def _read_cc_dashboard():
    """
    Read the Customer Centric dashboard HTML file and extract CSS, HTML body, and scripts.

    Returns:
        dict with keys 'css', 'html_body', 'scripts', or empty dict if file not found
    """
    cc_path = BASE_DIR.parent / 'dashboards' / 'customer centric dashboard 11.3.26.html'

    if not cc_path.exists():
        print(f"CC Dashboard not found: {cc_path}")
        return {'css': '', 'html_body': '', 'scripts': ''}

    try:
        with open(cc_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading CC dashboard: {e}")
        return {'css': '', 'html_body': '', 'scripts': ''}

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
        import re as _re
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


def _build_master_data_tab(master_data):
    """
    Generate full interactive HTML for the Master Data tab.
    Includes sub-navigation, brand cards, CRUD tables with add/edit/delete,
    portfolio matrix, pricing with margin warnings, and save-to-Excel.
    """
    if not master_data:
        return '<div style="padding:40px;text-align:center;color:var(--text-muted)">Master Data not available. Please check the Excel file path.</div>'

    # Serialize all data to JSON (handle datetime, None, etc.)
    data_json = json.dumps(master_data, default=str, ensure_ascii=False)

    # Use a placeholder so we never fight with Python string escaping in JS
    template = '''
<style>
/* ═══════════════════════════════ MD TAB STYLES ═══════════════════════════════ */
#tab-md { background:var(--bg); min-height:100vh; }

/* Top bar */
#tab-md .md-topbar {
  background:var(--card); border-bottom:1px solid var(--border-light);
  padding:18px 32px; display:flex; align-items:center;
  justify-content:space-between; gap:16px;
  position:sticky; top:0; z-index:50;
}
#tab-md .md-topbar h2 { font-size:18px; font-weight:700; color:var(--text); margin:0; }
#tab-md .md-topbar p  { font-size:12px; color:var(--text-muted); margin:2px 0 0; }
#tab-md .md-topbar-actions { display:flex; gap:10px; align-items:center; }

/* Sub-nav */
#tab-md .md-subnav {
  background:var(--card); border-bottom:1px solid var(--border-light);
  padding:0 32px; display:flex; gap:2px; overflow-x:auto;
}
#tab-md .md-stab {
  padding:12px 16px; border:none; background:transparent;
  font-size:13px; font-weight:500; color:var(--text-muted);
  cursor:pointer; font-family:inherit; white-space:nowrap;
  border-bottom:2px solid transparent; transition:all 0.15s;
  display:flex; align-items:center; gap:6px;
}
#tab-md .md-stab:hover { color:var(--text); }
#tab-md .md-stab.active {
  color:var(--primary); border-bottom-color:var(--primary); font-weight:600;
}

/* Body / Sections */
#tab-md .md-body { padding:28px 32px; max-width:1400px; margin:0 auto; }
#tab-md .md-section { display:none; }
#tab-md .md-section.active { display:block; }

/* Brand cards */
#tab-md .md-brand-cards {
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(200px,1fr));
  gap:16px; margin-bottom:28px;
}
#tab-md .md-brand-card {
  background:var(--card); border-radius:16px; padding:0;
  border:1px solid var(--border-light); box-shadow:var(--shadow-sm);
  transition:box-shadow 0.2s; overflow:hidden;
  display:flex; flex-direction:column;
}
#tab-md .md-brand-card:hover { box-shadow:var(--shadow); }

/* Coloured top accent bar */
#tab-md .mbc-accent { height:4px; width:100%; }

/* Main body of card */
#tab-md .mbc-body { padding:18px 18px 14px; flex:1; }
#tab-md .mbc-top  { display:flex; align-items:flex-start; justify-content:space-between; gap:8px; margin-bottom:12px; }
#tab-md .mbc-icon {
  width:38px; height:38px; border-radius:10px; flex-shrink:0;
  display:flex; align-items:center; justify-content:center;
  color:#fff; font-weight:800; font-size:16px;
}
#tab-md .mbc-name {
  font-size:14px; font-weight:700; color:var(--text);
  line-height:1.3; white-space:nowrap; overflow:hidden;
  text-overflow:ellipsis; max-width:120px;
}
#tab-md .mbc-cat  { font-size:11px; color:var(--text-muted); margin-top:2px; }

/* Two numeric stats side by side */
#tab-md .mbc-nums {
  display:flex; gap:0;
  border-top:1px solid var(--border-light); padding-top:12px; margin-top:4px;
}
#tab-md .mbc-stat { flex:1; text-align:center; }
#tab-md .mbc-stat + .mbc-stat { border-left:1px solid var(--border-light); }
#tab-md .mbc-num  { font-size:22px; font-weight:800; color:var(--text); line-height:1.1; }
#tab-md .mbc-lbl  { font-size:9px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.6px; margin-top:3px; }

/* Owner footer strip */
#tab-md .mbc-footer {
  padding:8px 18px; border-top:1px solid var(--border-light);
  background:var(--surface2);
  display:flex; align-items:center; gap:7px;
}
#tab-md .mbc-footer-lbl { font-size:10px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; }
#tab-md .mbc-footer-val { font-size:12px; font-weight:600; color:var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

/* Section card (table container) */
#tab-md .md-section-card {
  background:var(--card); border-radius:var(--radius); padding:0;
  border:1px solid var(--border-light); box-shadow:var(--shadow); overflow:hidden;
  margin-bottom:24px;
}
#tab-md .md-card-header {
  padding:18px 24px; display:flex; align-items:center;
  justify-content:space-between; border-bottom:1px solid var(--border-light);
}
#tab-md .md-card-header h3 { font-size:15px; font-weight:700; color:var(--text); }
#tab-md .md-card-header .md-count {
  font-size:12px; color:var(--text-muted); background:var(--surface);
  padding:3px 10px; border-radius:20px; margin-left:10px;
}

/* Buttons */
#tab-md .md-btn {
  padding:8px 16px; border-radius:10px; border:none; cursor:pointer;
  font-family:inherit; font-size:13px; font-weight:600; transition:all 0.15s;
  display:inline-flex; align-items:center; gap:6px;
}
#tab-md .md-btn-primary { background:var(--primary); color:#fff; }
#tab-md .md-btn-primary:hover { background:#4B4DD9; }
#tab-md .md-btn-secondary {
  background:var(--card); color:var(--text); border:1px solid var(--border);
  box-shadow:var(--shadow-sm);
}
#tab-md .md-btn-secondary:hover { border-color:var(--primary); color:var(--primary); }

/* Filter bar */
#tab-md .md-filter-bar {
  display:flex; gap:10px; align-items:center; padding:14px 24px;
  background:var(--surface2); border-bottom:1px solid var(--border-light);
  flex-wrap:wrap;
}
#tab-md .md-filter-bar label { font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; }
#tab-md .md-filter-bar select {
  padding:6px 10px; border:1px solid var(--border); border-radius:8px;
  font-family:inherit; font-size:13px; background:var(--card);
  color:var(--text); cursor:pointer;
}
#tab-md .md-filter-bar select:focus { outline:none; border-color:var(--primary); }

/* Tables */
#tab-md .md-tbl { width:100%; border-collapse:collapse; font-size:13px; }
#tab-md .md-tbl thead th {
  background:transparent; color:var(--text-muted); padding:10px 16px;
  text-align:left; font-weight:600; font-size:10px; text-transform:uppercase;
  letter-spacing:0.6px; border-bottom:1px solid var(--border);
  white-space:nowrap;
}
#tab-md .md-tbl tbody td {
  padding:11px 16px; border-bottom:1px solid var(--border-light);
  color:var(--text); vertical-align:middle;
}
#tab-md .md-tbl tbody tr:last-child td { border-bottom:none; }
#tab-md .md-tbl tbody tr:hover { background:var(--surface2); }
#tab-md .td-actions { width:80px; white-space:nowrap; }

/* Action buttons inside table */
#tab-md .md-act-btn {
  border:none; background:none; cursor:pointer; padding:4px 7px;
  border-radius:6px; font-size:13px; transition:background 0.15s; opacity:0.6;
}
#tab-md .md-act-btn:hover { background:var(--surface); opacity:1; }
#tab-md .md-act-btn.danger:hover { background:#fef2f2; }

/* Status chips */
#tab-md .md-chip {
  display:inline-block; padding:3px 10px; border-radius:20px;
  font-size:11px; font-weight:600; letter-spacing:0.2px; white-space:nowrap;
}
#tab-md .chip-active   { background:#ecfdf5; color:#065f46; }
#tab-md .chip-pipeline { background:#fef3c7; color:#92400e; }
#tab-md .chip-planned  { background:rgba(93,95,239,0.1); color:#5D5FEF; }
#tab-md .chip-danger   { background:#fef2f2; color:#991b1b; }
#tab-md .chip-potential { background:#f0f9ff; color:#0369a1; }

/* Brand tag */
#tab-md .md-brand-tag {
  display:inline-block; padding:2px 8px; border-radius:6px;
  font-size:11px; font-weight:600;
  background:rgba(93,95,239,0.08); color:var(--primary);
}

/* Portfolio table */
#tab-md .md-portfolio-tbl { min-width:700px; }
#tab-md .md-portfolio-tbl td { font-size:12px; }

/* Modal overlay */
#tab-md #md-overlay {
  display:none; position:fixed; inset:0; background:rgba(0,0,0,0.25);
  z-index:200; align-items:center; justify-content:center;
  backdrop-filter:blur(4px);
}
#tab-md #md-modal {
  background:var(--card); border-radius:20px;
  padding:0; width:520px; max-width:95vw; max-height:90vh;
  overflow:hidden; display:flex; flex-direction:column;
  box-shadow:0 20px 60px rgba(0,0,0,0.15);
}
#tab-md .md-modal-hdr {
  padding:20px 24px; border-bottom:1px solid var(--border-light);
  display:flex; align-items:center; justify-content:space-between;
}
#tab-md .md-modal-hdr h3 { font-size:16px; font-weight:700; }
#tab-md .md-modal-hdr button {
  border:none; background:none; font-size:20px; cursor:pointer;
  color:var(--text-muted); line-height:1; padding:0 4px;
}
#tab-md .md-modal-hdr button:hover { color:var(--text); }
#tab-md .md-modal-body {
  padding:20px 24px; overflow-y:auto; flex:1;
  display:grid; grid-template-columns:1fr 1fr; gap:14px 18px;
}
#tab-md .md-modal-body .md-field-full { grid-column:1/-1; }
#tab-md .md-field-lbl {
  display:block; font-size:11px; font-weight:600; color:var(--text-muted);
  text-transform:uppercase; letter-spacing:0.5px; margin-bottom:5px;
}
#tab-md .md-field-inp {
  width:100%; padding:9px 12px; border:1px solid var(--border);
  border-radius:10px; font-family:inherit; font-size:13px; color:var(--text);
  background:var(--bg); transition:border-color 0.2s;
}
#tab-md .md-field-inp:focus { outline:none; border-color:var(--primary); background:#fff; }
#tab-md .md-field-inp[rows] { resize:vertical; }
#tab-md .md-modal-ftr {
  padding:16px 24px; border-top:1px solid var(--border-light);
  display:flex; justify-content:flex-end; gap:10px;
}

/* Toast */
#tab-md #md-toast {
  position:fixed; bottom:28px; left:50%; transform:translateX(-50%);
  background:#1e293b; color:#fff; padding:10px 20px;
  border-radius:10px; font-size:13px; font-weight:500;
  z-index:300; opacity:0; transition:opacity 0.3s; pointer-events:none;
}

/* Unsaved-changes banner */
#md-dirty-banner {
  display:none;
  background:#fefce8; border-bottom:1px solid #fde68a;
  padding:12px 32px; align-items:center; gap:16px; flex-wrap:wrap;
}
#md-dirty-banner .mdb-icon { font-size:18px; flex-shrink:0; }
#md-dirty-banner .mdb-text { flex:1; min-width:200px; }
#md-dirty-banner .mdb-text strong { font-size:13px; color:#92400e; display:block; margin-bottom:2px; }
#md-dirty-banner .mdb-steps {
  display:flex; gap:6px; align-items:center; flex-wrap:wrap; margin-top:4px;
}
#md-dirty-banner .mdb-step {
  display:inline-flex; align-items:center; gap:5px;
  background:#fff; border:1px solid #fde68a; border-radius:20px;
  padding:3px 10px; font-size:12px; color:#78350f; font-weight:500;
}
#md-dirty-banner .mdb-step .mdb-num {
  width:18px; height:18px; background:#f59e0b; color:#fff;
  border-radius:50%; display:inline-flex; align-items:center;
  justify-content:center; font-size:10px; font-weight:700; flex-shrink:0;
}
#md-dirty-banner .mdb-save-btn {
  background:#f59e0b; color:#fff; border:none; border-radius:10px;
  padding:9px 18px; font-size:13px; font-weight:600; cursor:pointer;
  font-family:inherit; white-space:nowrap; transition:background 0.15s;
  display:inline-flex; align-items:center; gap:7px;
}
#md-dirty-banner .mdb-save-btn:hover { background:#d97706; }
#md-dirty-banner .mdb-dismiss {
  background:none; border:none; cursor:pointer; color:#92400e;
  font-size:18px; opacity:0.5; padding:0 4px; line-height:1;
}
#md-dirty-banner .mdb-dismiss:hover { opacity:1; }
</style>

<!-- ── MD Top Bar ── -->
<div class="md-topbar">
  <div>
    <h2>📊 Master Data</h2>
    <p>Raito &middot; Products, Customers, Pricing &amp; Logistics</p>
  </div>
  <div class="md-topbar-actions" style="display:flex;align-items:center;gap:12px;">
    <span id="md-api-status" style="display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;padding:5px 12px;border-radius:20px;background:#fee2e2;color:#991b1b;">
      <span style="width:8px;height:8px;border-radius:50%;background:#ef4444;display:inline-block;"></span>
      Offline
    </span>
    <button class="md-btn md-btn-secondary" onclick="mdSave()">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
      Save to Excel
    </button>
  </div>
</div>

<!-- ── Unsaved Changes Banner ── -->
<div id="md-dirty-banner">
  <div class="mdb-icon">✏️</div>
  <div class="mdb-text">
    <strong>You have unsaved changes</strong>
    <div class="mdb-steps">
      <span class="mdb-step"><span class="mdb-num">1</span> Click Save to Excel below</span>
      <span style="color:#d97706">→</span>
      <span class="mdb-step"><span class="mdb-num">2</span> Replace the original <code style="font-size:11px">Raito_Master_Data.xlsx</code> with the exported file</span>
      <span style="color:#d97706">→</span>
      <span class="mdb-step"><span class="mdb-num">3</span> Re-run <code style="font-size:11px">python3 scripts/unified_dashboard.py</code> to rebuild</span>
    </div>
  </div>
  <button class="mdb-save-btn" onclick="mdSave()">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
    Export to Excel
  </button>
  <button class="mdb-save-btn" id="md-rebuild-btn" onclick="mdRebuild()" style="background:#5D5FEF;margin-left:6px;display:none">
    ↻ Rebuild Dashboard
  </button>
  <button class="mdb-dismiss" onclick="document.getElementById('md-dirty-banner').style.display='none'" title="Dismiss">&#x2715;</button>
</div>

<!-- ── Sub-Navigation ── -->
<div class="md-subnav">
  <button class="md-stab" onclick="mdGo('brands')"       id="mdt-brands">🏷 Brands</button>
  <button class="md-stab" onclick="mdGo('products')"     id="mdt-products">📦 Products</button>
  <button class="md-stab" onclick="mdGo('manufacturers')" id="mdt-manufacturers">🏭 Manufacturers</button>
  <button class="md-stab" onclick="mdGo('distributors')" id="mdt-distributors">🚛 Distributors</button>
  <button class="md-stab" onclick="mdGo('customers')"    id="mdt-customers">🏪 Customers</button>
  <button class="md-stab" onclick="mdGo('pricing')"      id="mdt-pricing">💰 Pricing</button>
  <button class="md-stab" onclick="mdGo('logistics')"    id="mdt-logistics">📐 Logistics</button>
  <button class="md-stab" onclick="mdGo('portfolio')"    id="mdt-portfolio">📊 Portfolio</button>
</div>

<!-- ── Content Body ── -->
<div class="md-body">

  <!-- Brands -->
  <div id="mds-brands" class="md-section">
    <div id="md-brand-cards"></div>
    <div class="md-section-card">
      <div class="md-card-header">
        <div style="display:flex;align-items:center">
          <h3>All Brands</h3>
          <span class="md-count" id="cnt-brands"></span>
        </div>
        <button class="md-btn md-btn-primary" onclick="mdAdd('brands')">+ Add Brand</button>
      </div>
      <table class="md-tbl">
        <thead><tr><th>Key</th><th>Name</th><th>Category</th><th>Status</th><th>Launch</th><th>Owner</th><th></th></tr></thead>
        <tbody id="md-tbl-brands"></tbody>
      </table>
    </div>
  </div>

  <!-- Products -->
  <div id="mds-products" class="md-section">
    <div class="md-section-card">
      <div class="md-filter-bar">
        <label>Brand</label>
        <select id="flt-products-brand" onchange="mdRender('products')"><option value="all">All Brands</option></select>
        <label>Status</label>
        <select id="flt-products-status" onchange="mdRender('products')">
          <option value="all">All Statuses</option>
          <option>Active</option><option>Planned</option><option>Discontinued</option>
        </select>
      </div>
      <div class="md-card-header">
        <div style="display:flex;align-items:center">
          <h3>Product Catalog (SKUs)</h3>
          <span class="md-count" id="cnt-products"></span>
        </div>
        <button class="md-btn md-btn-primary" onclick="mdAdd('products')">+ Add SKU</button>
      </div>
      <table class="md-tbl">
        <thead><tr><th>SKU Key</th><th>Name HE</th><th>Name EN</th><th>Brand</th><th>Category</th><th>Status</th><th>Manufacturer</th><th>Cost</th><th></th></tr></thead>
        <tbody id="md-tbl-products"></tbody>
      </table>
    </div>
  </div>

  <!-- Manufacturers -->
  <div id="mds-manufacturers" class="md-section">
    <div class="md-section-card">
      <div class="md-card-header">
        <div style="display:flex;align-items:center">
          <h3>Manufacturers</h3>
          <span class="md-count" id="cnt-manufacturers"></span>
        </div>
        <button class="md-btn md-btn-primary" onclick="mdAdd('manufacturers')">+ Add Manufacturer</button>
      </div>
      <table class="md-tbl">
        <thead><tr><th>Key</th><th>Name</th><th>Products</th><th>Contact</th><th>Location</th><th>Lead Time</th><th>MOQ</th><th>Payment Terms</th><th></th></tr></thead>
        <tbody id="md-tbl-manufacturers"></tbody>
      </table>
    </div>
  </div>

  <!-- Distributors -->
  <div id="mds-distributors" class="md-section">
    <div class="md-section-card">
      <div class="md-card-header">
        <div style="display:flex;align-items:center">
          <h3>Distributors</h3>
          <span class="md-count" id="cnt-distributors"></span>
        </div>
        <button class="md-btn md-btn-primary" onclick="mdAdd('distributors')">+ Add Distributor</button>
      </div>
      <table class="md-tbl">
        <thead><tr><th>Key</th><th>Name</th><th>Products</th><th>Commission %</th><th>Report Format</th><th>Report Freq</th><th>Contact</th><th></th></tr></thead>
        <tbody id="md-tbl-distributors"></tbody>
      </table>
    </div>
  </div>

  <!-- Customers -->
  <div id="mds-customers" class="md-section">
    <div class="md-section-card">
      <div class="md-filter-bar">
        <label>Type</label>
        <select id="flt-cust-type" onchange="mdRender('customers')">
          <option value="all">All Types</option>
          <option>Retail</option><option>B2B</option><option>Online</option><option>HoReCa</option>
        </select>
        <label>Status</label>
        <select id="flt-cust-status" onchange="mdRender('customers')">
          <option value="all">All Statuses</option>
          <option>Active</option><option>Potential</option><option>Inactive</option><option>Churned</option>
        </select>
        <label>Distributor</label>
        <select id="flt-cust-dist" onchange="mdRender('customers')"><option value="all">All Distributors</option></select>
      </div>
      <div class="md-card-header">
        <div style="display:flex;align-items:center">
          <h3>Customers</h3>
          <span class="md-count" id="cnt-customers"></span>
        </div>
        <button class="md-btn md-btn-primary" onclick="mdAdd('customers')">+ Add Customer</button>
      </div>
      <table class="md-tbl">
        <thead><tr><th>Name HE</th><th>Name EN</th><th>Type</th><th>Distributor</th><th>Chain/Group</th><th>Status</th><th>Contact</th><th></th></tr></thead>
        <tbody id="md-tbl-customers"></tbody>
      </table>
    </div>
  </div>

  <!-- Pricing -->
  <div id="mds-pricing" class="md-section">
    <div class="md-section-card">
      <div class="md-filter-bar">
        <label>SKU</label>
        <select id="flt-pricing-sku" onchange="mdRender('pricing')"><option value="all">All SKUs</option></select>
        <label>Status</label>
        <select id="flt-pricing-status" onchange="mdRender('pricing')">
          <option value="all">All</option>
          <option>Active</option><option>Pipeline</option><option>Archived</option>
        </select>
        <label>Distributor</label>
        <select id="flt-pricing-dist" onchange="mdRender('pricing')"><option value="all">All Distributors</option></select>
      </div>
      <div class="md-card-header">
        <div style="display:flex;align-items:center">
          <h3>B2B Pricing</h3>
          <span class="md-count" id="cnt-pricing"></span>
        </div>
        <button class="md-btn md-btn-primary" onclick="mdAdd('pricing')">+ Add Price</button>
      </div>
      <div style="overflow-x:auto">
        <table class="md-tbl" style="min-width:900px">
          <thead><tr><th>SKU</th><th>Name EN</th><th>Customer</th><th>Distributor</th><th>Comm%</th><th>Sale Price</th><th>Cost</th><th>GP%</th><th>Op Margin%</th><th>Status</th><th></th></tr></thead>
          <tbody id="md-tbl-pricing"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Logistics -->
  <div id="mds-logistics" class="md-section">
    <div class="md-section-card">
      <div class="md-card-header">
        <div style="display:flex;align-items:center">
          <h3>Logistics &amp; Storage</h3>
          <span class="md-count" id="cnt-logistics"></span>
        </div>
        <button class="md-btn md-btn-primary" onclick="mdAdd('logistics')">+ Add Entry</button>
      </div>
      <table class="md-tbl">
        <thead><tr><th>Product Key</th><th>Product Name</th><th>Storage Type</th><th>Temp</th><th>Units/Carton</th><th>Cartons/Pallet</th><th>Units/Pallet</th><th>Warehouse</th><th></th></tr></thead>
        <tbody id="md-tbl-logistics"></tbody>
      </table>
    </div>
  </div>

  <!-- Portfolio -->
  <div id="mds-portfolio" class="md-section">
    <div class="md-section-card">
      <div class="md-card-header">
        <h3>📊 Product Portfolio Matrix</h3>
        <span style="font-size:12px;color:var(--text-muted)">Customer × SKU availability &amp; pricing</span>
      </div>
      <div style="padding:8px 0 16px">
        <div style="padding:0 16px 12px;display:flex;gap:16px;font-size:12px;align-items:center;flex-wrap:wrap">
          <span style="background:#ecfdf5;color:#065f46;padding:3px 10px;border-radius:6px;font-weight:600">₪ Price = Active</span>
          <span style="background:#fef3c7;color:#92400e;padding:3px 10px;border-radius:6px;font-weight:600">~ Pipeline</span>
          <span style="color:#cbd5e1;padding:3px 10px">— Not listed</span>
        </div>
        <div id="md-portfolio-matrix" style="overflow-x:auto; padding:0 16px 16px"></div>
      </div>
    </div>
  </div>

</div><!-- /md-body -->

<!-- ── Modal ── -->
<div id="md-overlay">
  <div id="md-modal">
    <div class="md-modal-hdr">
      <h3 id="md-modal-title">Edit</h3>
      <button onclick="mdModalClose()">&#x2715;</button>
    </div>
    <div class="md-modal-body" id="md-modal-fields"></div>
    <div class="md-modal-ftr">
      <button class="md-btn md-btn-secondary" onclick="mdModalClose()">Cancel</button>
      <button class="md-btn md-btn-primary" onclick="mdModalSave()">Save Changes</button>
    </div>
  </div>
</div>

<!-- ── Toast ── -->
<div id="md-toast"></div>

<script>
(function() {
  /* ── API Configuration ── */
  var API_BASE = 'http://localhost:5555/api';
  var API_OK = false;  // detected at init

  /* ── Initial Data from Python (fallback) ── */
  var MD = __MD_DATA__;

  /* ── Mutable State ── */
  var S = {
    brands:        MD.brands        || [],
    products:      MD.products      || [],
    manufacturers: MD.manufacturers || [],
    distributors:  MD.distributors  || [],
    customers:     MD.customers     || [],
    logistics:     MD.logistics     || [],
    pricing:       MD.pricing       || [],
    portfolio:     MD.portfolio     || {headers:[], rows:[]}
  };

  /* ── API entity → table field mapping ── */
  var ENTITY_MAP = {
    brands:        {pk:'key'},
    products:      {pk:'sku_key',   fkFields:{brand:'brand_key', manufacturer:'manufacturer_key'}},
    manufacturers: {pk:'key'},
    distributors:  {pk:'key'},
    customers:     {pk:'key',       fkFields:{distributor:'distributor_key'}},
    logistics:     {pk:'id'},
    pricing:       {pk:'id',        fkFields:{customer:'customer_key', distributor:'distributor_key', sku_key:'sku_key'}}
  };

  /* ── API helper ── */
  function apiCall(method, path, body) {
    var opts = {method: method, headers: {'Content-Type':'application/json'}};
    if (body) opts.body = JSON.stringify(body);
    return fetch(API_BASE + path, opts).then(function(r) {
      if (!r.ok) return r.json().then(function(e) { throw new Error(e.error || 'API error'); });
      return r.json();
    });
  }

  /* ── Map local field names → API field names for writes ── */
  function toApiRecord(sheet, rec) {
    var map = ENTITY_MAP[sheet];
    if (!map || !map.fkFields) return rec;
    var out = {};
    for (var k in rec) {
      if (map.fkFields[k]) out[map.fkFields[k]] = rec[k];
      else out[k] = rec[k];
    }
    return out;
  }

  /* ── Field Schemas for modals ── */
  var SCHEMAS = {
    brands: { label:'Brand', fields:[
      {key:'key',         label:'Brand Key',   type:'text', required:true, half:false},
      {key:'name',        label:'Brand Name',  type:'text'},
      {key:'category',    label:'Category',    type:'text'},
      {key:'status',      label:'Status',      type:'select', options:['Active','Planned','Discontinued']},
      {key:'launch_date', label:'Launch Date', type:'text'},
      {key:'owner',       label:'Owner',       type:'text'},
      {key:'notes',       label:'Notes',       type:'textarea', full:true},
    ]},
    products: { label:'Product / SKU', fields:[
      {key:'sku_key',     label:'SKU Key',      type:'text', required:true},
      {key:'barcode',     label:'Barcode',      type:'text'},
      {key:'name_he',     label:'Name (HE)',    type:'text'},
      {key:'name_en',     label:'Name (EN)',    type:'text'},
      {key:'brand',       label:'Brand',        type:'fk_select', lookup:'brands', valKey:'key', labelKey:'name'},
      {key:'category',    label:'Category',     type:'text'},
      {key:'status',      label:'Status',       type:'select', options:['Active','New','Planned','Discontinued']},
      {key:'launch_date', label:'Launch Date',  type:'text'},
      {key:'manufacturer',label:'Manufacturer', type:'fk_select', lookup:'manufacturers', valKey:'key', labelKey:'name'},
      {key:'cost',        label:'Cost (₪)',      type:'number'},
    ]},
    manufacturers: { label:'Manufacturer', fields:[
      {key:'key',           label:'Key',            type:'text', required:true},
      {key:'name',          label:'Name',           type:'text'},
      {key:'products',      label:'Products',       type:'text'},
      {key:'contact',       label:'Contact',        type:'text'},
      {key:'location',      label:'Location',       type:'text'},
      {key:'lead_time',     label:'Lead Time',      type:'text'},
      {key:'moq',           label:'MOQ',            type:'text'},
      {key:'payment_terms', label:'Payment Terms',  type:'text'},
      {key:'notes',         label:'Notes',          type:'textarea', full:true},
    ]},
    distributors: { label:'Distributor', fields:[
      {key:'key',           label:'Key',             type:'text', required:true},
      {key:'name',          label:'Name',            type:'text'},
      {key:'products',      label:'Products',        type:'text'},
      {key:'commission_pct',label:'Commission (0-1)',type:'number'},
      {key:'report_format', label:'Report Format',   type:'text'},
      {key:'report_freq',   label:'Report Frequency',type:'text'},
      {key:'contact',       label:'Contact',         type:'text'},
      {key:'notes',         label:'Notes',           type:'textarea', full:true},
    ]},
    customers: { label:'Customer', fields:[
      {key:'key',        label:'Customer Key', type:'text', required:true},
      {key:'name_he',    label:'Name (HE)',    type:'text'},
      {key:'name_en',    label:'Name (EN)',    type:'text'},
      {key:'type',       label:'Type',         type:'select', options:['Retail','B2B','Online','HoReCa','Chain','Independent','Delivery App','Other']},
      {key:'distributor',label:'Distributor',  type:'fk_select', lookup:'distributors', valKey:'key', labelKey:'name'},
      {key:'chain',      label:'Chain/Group',  type:'text'},
      {key:'status',     label:'Status',       type:'select', options:['Active','Pipeline','Potential','Inactive','Churned']},
      {key:'contact',    label:'Contact',      type:'text'},
      {key:'phone',      label:'Phone',        type:'text'},
      {key:'notes',      label:'Notes',        type:'textarea', full:true},
    ]},
    logistics: { label:'Logistics Entry', fields:[
      {key:'product_key',       label:'Product Key',     type:'text', required:true},
      {key:'product_name',      label:'Product Name',    type:'text'},
      {key:'storage_type',      label:'Storage Type',    type:'text'},
      {key:'temp',              label:'Temperature',     type:'text'},
      {key:'units_per_carton',  label:'Units/Carton',    type:'number'},
      {key:'cartons_per_pallet',label:'Cartons/Pallet',  type:'number'},
      {key:'units_per_pallet',  label:'Units/Pallet',    type:'number'},
      {key:'pallet_divisor',    label:'Pallet Divisor',  type:'number'},
      {key:'warehouse',         label:'Warehouse',       type:'text'},
      {key:'notes',             label:'Notes',           type:'textarea', full:true},
    ]},
    pricing: { label:'Pricing Entry', fields:[
      {key:'sku_key',       label:'Product',          type:'fk_select', lookup:'products', valKey:'sku_key', labelKey:'name_en', required:true},
      {key:'customer',      label:'Customer',         type:'fk_select', lookup:'customers', valKey:'name_en', labelKey:'name_en'},
      {key:'distributor',   label:'Distributor',      type:'fk_select', lookup:'distributors', valKey:'key', labelKey:'name'},
      {key:'commission_pct',label:'Commission (0-1)', type:'number'},
      {key:'sale_price',    label:'Sale Price (₪)',    type:'number'},
      {key:'cost',          label:'Cost (₪)',          type:'number'},
      {key:'status',        label:'Status',           type:'select', options:['Active','Pipeline','Archived']},
      {key:'last_updated',  label:'Last Updated',     type:'text', full:true},
    ]},
  };

  /* ── Helpers ── */
  function esc(s) {
    if (s == null) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function chip(val) {
    if (!val) return '';
    var v = String(val).toLowerCase();
    var cls = 'md-chip ';
    if (v==='active')                                          cls+='chip-active';
    else if (v==='pipeline')                                   cls+='chip-pipeline';
    else if (v==='planned'||v==='potential'||v==='in progress') cls+='chip-planned';
    else if (v==='discontinued'||v==='archived'||v==='inactive'||v==='churned') cls+='chip-danger';
    else                                                       cls+='chip-planned';
    return '<span class="'+cls+'">'+esc(val)+'</span>';
  }
  function pct(v) { return v!=null ? (v*100).toFixed(0)+'%' : '—'; }
  function price(v) { return v!=null ? '₪'+Number(v).toFixed(2) : '—'; }
  function getVal(id) { var e=document.getElementById(id); return e?e.value:''; }
  function setHTML(id,h) { var e=document.getElementById(id); if(e) e.innerHTML=h; }
  function uniqueVals(arr, key) {
    var seen={}, out=['all'];
    arr.forEach(function(r){ var v=r[key]; if(v&&!seen[v]){seen[v]=1;out.push(v);} });
    return out;
  }
  function populateSel(id, opts, allLabel, cur) {
    var el=document.getElementById(id); if(!el) return;
    var prev = cur||el.value||'all';
    el.innerHTML = opts.map(function(o){
      var l = o==='all' ? allLabel : o;
      return '<option value="'+esc(o)+'"'+(o===prev?' selected':'')+'>'+esc(l)+'</option>';
    }).join('');
  }
  function showToast(msg) {
    var t=document.getElementById('md-toast');
    if(!t) return;
    t.textContent=msg; t.style.opacity='1';
    setTimeout(function(){t.style.opacity='0';},2200);
  }
  function markDirty() {
    var b=document.getElementById('md-dirty-banner');
    if(b) b.style.display='flex';
  }
  function markClean() {
    var b=document.getElementById('md-dirty-banner');
    if(b) b.style.display='none';
  }
  function setCount(id, n) {
    var e=document.getElementById('cnt-'+id);
    if(e) e.textContent=n;
  }

  /* ── Navigation ── */
  var _cur = null;
  window.mdGo = function(sec) {
    _cur = sec;
    document.querySelectorAll('#tab-md .md-stab').forEach(function(b){b.classList.remove('active');});
    var btn=document.getElementById('mdt-'+sec); if(btn) btn.classList.add('active');
    document.querySelectorAll('#tab-md .md-section').forEach(function(s){s.classList.remove('active');});
    var sel=document.getElementById('mds-'+sec); if(sel) sel.classList.add('active');
    mdRender(sec);
  };

  function mdRender(sec) {
    var fn = {
      brands: rBrands, products: rProducts, manufacturers: rManufacturers,
      distributors: rDistributors, customers: rCustomers,
      pricing: rPricing, logistics: rLogistics, portfolio: rPortfolio
    }[sec];
    if(fn) fn();
  }

  /* ── BRANDS ── */
  // Per-brand accent colours (cycles if more brands added)
  var BRAND_COLORS = ['#10b981','#5D5FEF','#f59e0b','#ef4444','#06b6d4','#8b5cf6','#ec4899'];

  function rBrands() {
    // Brand cards — new uniform layout
    var cardsHtml = '<div class="md-brand-cards">';
    S.brands.forEach(function(b, bi) {
      var prods = S.products.filter(function(p){return p.brand===b.key;}).length;
      var deals = S.pricing.filter(function(p){
        return S.products.some(function(pr){return pr.brand===b.key&&(pr.sku_key===p.sku_key||pr.name_en===p.name_en);})
               && p.status&&p.status.toLowerCase()==='active';
      }).length;
      var bs = (b.status||'').toLowerCase();
      // Status drives accent colour; planned brands get their index colour dimmed
      var accent = bs==='active' ? BRAND_COLORS[bi % BRAND_COLORS.length]
                 : bs==='discontinued' ? '#94a3b8'
                 : BRAND_COLORS[bi % BRAND_COLORS.length];
      var chipBg = bs==='active'?'#ecfdf5':bs==='planned'?'rgba(93,95,239,0.08)':'#fef2f2';
      var chipFg = bs==='active'?'#065f46':bs==='planned'?'#5D5FEF':'#991b1b';
      var initial = (b.name||b.key||'?').charAt(0).toUpperCase();

      cardsHtml += '<div class="md-brand-card">';
      // Coloured top bar
      cardsHtml += '<div class="mbc-accent" style="background:'+accent+'"></div>';
      // Card body
      cardsHtml += '<div class="mbc-body">';
      cardsHtml +=   '<div class="mbc-top">';
      cardsHtml +=     '<div class="mbc-icon" style="background:'+accent+'">'+initial+'</div>';
      cardsHtml +=     '<div style="flex:1;min-width:0">';
      cardsHtml +=       '<div class="mbc-name" title="'+esc(b.name||b.key)+'">'+esc(b.name||b.key)+'</div>';
      cardsHtml +=       '<div class="mbc-cat">'+esc(b.category||'')+'</div>';
      cardsHtml +=     '</div>';
      cardsHtml +=     '<span class="md-chip" style="background:'+chipBg+';color:'+chipFg+';flex-shrink:0">'+esc(b.status||'')+'</span>';
      cardsHtml +=   '</div>';
      // Two numeric stats only
      cardsHtml +=   '<div class="mbc-nums">';
      cardsHtml +=     '<div class="mbc-stat"><div class="mbc-num">'+prods+'</div><div class="mbc-lbl">SKUs</div></div>';
      cardsHtml +=     '<div class="mbc-stat"><div class="mbc-num">'+deals+'</div><div class="mbc-lbl">Active Deals</div></div>';
      cardsHtml +=   '</div>';
      cardsHtml += '</div>';
      // Owner in a footer strip
      cardsHtml += '<div class="mbc-footer">';
      cardsHtml +=   '<span class="mbc-footer-lbl">Owner</span>';
      cardsHtml +=   '<span class="mbc-footer-val">'+esc(b.owner||'—')+'</span>';
      cardsHtml += '</div>';
      cardsHtml += '</div>';
    });
    cardsHtml += '</div>';
    setHTML('md-brand-cards', cardsHtml);

    // Table
    var rows='';
    S.brands.forEach(function(b,i){
      rows+='<tr><td><code style="font-size:11px">'+esc(b.key)+'</code></td>';
      rows+='<td><b>'+esc(b.name)+'</b></td>';
      rows+='<td>'+esc(b.category)+'</td>';
      rows+='<td>'+chip(b.status)+'</td>';
      rows+='<td>'+esc(b.launch_date)+'</td>';
      rows+='<td>'+esc(b.owner)+'</td>';
      rows+='<td class="td-actions"><button class="md-act-btn" data-s="brands" data-i="'+i+'" onclick="mdEdit(this.dataset.s,+this.dataset.i)">✏️</button>'
           +'<button class="md-act-btn danger" data-s="brands" data-i="'+i+'" onclick="mdDel(this.dataset.s,+this.dataset.i)">🗑</button></td></tr>';
    });
    setHTML('md-tbl-brands', rows);
    setCount('brands', S.brands.length);
  }

  /* ── PRODUCTS ── */
  function rProducts() {
    var bf=getVal('flt-products-brand'), sf=getVal('flt-products-status');
    populateSel('flt-products-brand', uniqueVals(S.products,'brand'), 'All Brands', bf);
    var data=S.products.filter(function(p){
      if(bf&&bf!=='all'&&p.brand!==bf) return false;
      if(sf&&sf!=='all'&&p.status!==sf) return false;
      return true;
    });
    var rows='';
    data.forEach(function(p){
      var i=S.products.indexOf(p);
      rows+='<tr>';
      rows+='<td><code style="font-size:11px">'+esc(p.sku_key)+'</code></td>';
      rows+='<td>'+esc(p.name_he)+'</td>';
      rows+='<td style="font-size:12px;color:var(--text-muted)">'+esc(p.name_en)+'</td>';
      rows+='<td><span class="md-brand-tag">'+esc(p.brand)+'</span></td>';
      rows+='<td>'+esc(p.category)+'</td>';
      rows+='<td>'+chip(p.status)+'</td>';
      rows+='<td>'+esc(p.manufacturer)+'</td>';
      rows+='<td style="text-align:right">'+(p.cost!=null?'₪'+Number(p.cost).toFixed(2):'')+'</td>';
      rows+='<td class="td-actions"><button class="md-act-btn" data-s="products" data-i="'+i+'" onclick="mdEdit(this.dataset.s,+this.dataset.i)">✏️</button>'
           +'<button class="md-act-btn danger" data-s="products" data-i="'+i+'" onclick="mdDel(this.dataset.s,+this.dataset.i)">🗑</button></td></tr>';
    });
    setHTML('md-tbl-products', rows);
    setCount('products', data.length+(data.length!==S.products.length?'/'+S.products.length:''));
  }

  /* ── MANUFACTURERS ── */
  function rManufacturers() {
    var rows='';
    S.manufacturers.forEach(function(m,i){
      rows+='<tr><td><code style="font-size:11px">'+esc(m.key)+'</code></td>';
      rows+='<td><b>'+esc(m.name)+'</b></td>';
      rows+='<td style="font-size:12px">'+esc(m.products)+'</td>';
      rows+='<td>'+esc(m.contact)+'</td>';
      rows+='<td>'+esc(m.location)+'</td>';
      rows+='<td>'+esc(m.lead_time)+'</td>';
      rows+='<td>'+esc(m.moq)+'</td>';
      rows+='<td>'+esc(m.payment_terms)+'</td>';
      rows+='<td class="td-actions"><button class="md-act-btn" data-s="manufacturers" data-i="'+i+'" onclick="mdEdit(this.dataset.s,+this.dataset.i)">✏️</button>'
           +'<button class="md-act-btn danger" data-s="manufacturers" data-i="'+i+'" onclick="mdDel(this.dataset.s,+this.dataset.i)">🗑</button></td></tr>';
    });
    setHTML('md-tbl-manufacturers', rows);
    setCount('manufacturers', S.manufacturers.length);
  }

  /* ── DISTRIBUTORS ── */
  function rDistributors() {
    var rows='';
    S.distributors.forEach(function(d,i){
      rows+='<tr><td><code style="font-size:11px">'+esc(d.key)+'</code></td>';
      rows+='<td><b>'+esc(d.name)+'</b></td>';
      rows+='<td style="font-size:12px">'+esc(d.products)+'</td>';
      rows+='<td style="text-align:center">'+pct(d.commission_pct)+'</td>';
      rows+='<td>'+esc(d.report_format)+'</td>';
      rows+='<td>'+esc(d.report_freq)+'</td>';
      rows+='<td>'+esc(d.contact)+'</td>';
      rows+='<td class="td-actions"><button class="md-act-btn" data-s="distributors" data-i="'+i+'" onclick="mdEdit(this.dataset.s,+this.dataset.i)">✏️</button>'
           +'<button class="md-act-btn danger" data-s="distributors" data-i="'+i+'" onclick="mdDel(this.dataset.s,+this.dataset.i)">🗑</button></td></tr>';
    });
    setHTML('md-tbl-distributors', rows);
    setCount('distributors', S.distributors.length);
  }

  /* ── CUSTOMERS ── */
  function rCustomers() {
    var tf=getVal('flt-cust-type'), sf=getVal('flt-cust-status'), df=getVal('flt-cust-dist');
    populateSel('flt-cust-dist', uniqueVals(S.customers,'distributor'), 'All Distributors', df);
    var data=S.customers.filter(function(c){
      if(tf&&tf!=='all'&&c.type!==tf) return false;
      if(sf&&sf!=='all'&&c.status!==sf) return false;
      if(df&&df!=='all'&&c.distributor!==df) return false;
      return true;
    });
    var rows='';
    data.forEach(function(c){
      var i=S.customers.indexOf(c);
      rows+='<tr><td><b>'+esc(c.name_he)+'</b></td>';
      rows+='<td style="font-size:12px;color:var(--text-muted)">'+esc(c.name_en)+'</td>';
      rows+='<td>'+esc(c.type)+'</td>';
      rows+='<td>'+esc(c.distributor)+'</td>';
      rows+='<td>'+esc(c.chain)+'</td>';
      rows+='<td>'+chip(c.status)+'</td>';
      rows+='<td>'+esc(c.contact)+'</td>';
      rows+='<td class="td-actions"><button class="md-act-btn" data-s="customers" data-i="'+i+'" onclick="mdEdit(this.dataset.s,+this.dataset.i)">✏️</button>'
           +'<button class="md-act-btn danger" data-s="customers" data-i="'+i+'" onclick="mdDel(this.dataset.s,+this.dataset.i)">🗑</button></td></tr>';
    });
    setHTML('md-tbl-customers', rows);
    setCount('customers', data.length+(data.length!==S.customers.length?'/'+S.customers.length:''));
  }

  /* ── PRICING ── */
  function rPricing() {
    var sf=getVal('flt-pricing-sku'), stf=getVal('flt-pricing-status'), df=getVal('flt-pricing-dist');
    populateSel('flt-pricing-sku',  uniqueVals(S.pricing,'sku_key'),    'All SKUs',         sf);
    populateSel('flt-pricing-dist', uniqueVals(S.pricing,'distributor'),'All Distributors', df);
    var data=S.pricing.filter(function(p){
      if(sf&&sf!=='all'&&p.sku_key!==sf) return false;
      if(stf&&stf!=='all'&&p.status!==stf) return false;
      if(df&&df!=='all'&&p.distributor!==df) return false;
      return true;
    });
    var rows='';
    data.forEach(function(p){
      var i=S.pricing.indexOf(p);
      // Compute margins if not stored
      var gm = p.gross_margin!=null ? (p.gross_margin*100).toFixed(1)+'%'
              : (p.sale_price&&p.cost ? ((p.sale_price-p.cost)/p.sale_price*100).toFixed(1)+'%' : '—');
      var om = p.op_margin!=null ? (p.op_margin*100).toFixed(1)+'%' : '—';
      var omN = p.op_margin!=null ? p.op_margin*100 : null;
      var omStyle='';
      if(omN!==null){ omStyle=omN<10?'color:#ef4444;font-weight:700':omN<20?'color:#f59e0b;font-weight:600':'color:#10b981;font-weight:600'; }
      rows+='<tr>';
      rows+='<td><span class="md-brand-tag">'+esc(p.sku_key)+'</span></td>';
      rows+='<td style="font-size:12px">'+esc(p.name_en)+'</td>';
      rows+='<td>'+esc(p.customer)+'</td>';
      rows+='<td>'+esc(p.distributor)+'</td>';
      rows+='<td style="text-align:center">'+pct(p.commission_pct)+'</td>';
      rows+='<td style="text-align:right;font-weight:600">'+price(p.sale_price)+'</td>';
      rows+='<td style="text-align:right">'+price(p.cost)+'</td>';
      rows+='<td style="text-align:center">'+gm+'</td>';
      rows+='<td style="text-align:center;'+omStyle+'">'+om+'</td>';
      rows+='<td>'+chip(p.status)+'</td>';
      rows+='<td class="td-actions"><button class="md-act-btn" data-s="pricing" data-i="'+i+'" onclick="mdEdit(this.dataset.s,+this.dataset.i)">✏️</button>'
           +'<button class="md-act-btn danger" data-s="pricing" data-i="'+i+'" onclick="mdDel(this.dataset.s,+this.dataset.i)">🗑</button></td></tr>';
    });
    setHTML('md-tbl-pricing', rows);
    setCount('pricing', data.length+(data.length!==S.pricing.length?'/'+S.pricing.length:''));
  }

  /* ── LOGISTICS ── */
  function rLogistics() {
    var rows='';
    S.logistics.forEach(function(l,i){
      rows+='<tr><td><code style="font-size:11px">'+esc(l.product_key)+'</code></td>';
      rows+='<td>'+esc(l.product_name)+'</td>';
      rows+='<td>'+esc(l.storage_type)+'</td>';
      rows+='<td style="text-align:center">'+esc(l.temp)+'</td>';
      rows+='<td style="text-align:center">'+(l.units_per_carton||'')+'</td>';
      rows+='<td style="text-align:center">'+(l.cartons_per_pallet||'')+'</td>';
      rows+='<td style="text-align:center">'+(l.units_per_pallet||'')+'</td>';
      rows+='<td>'+esc(l.warehouse)+'</td>';
      rows+='<td class="td-actions"><button class="md-act-btn" data-s="logistics" data-i="'+i+'" onclick="mdEdit(this.dataset.s,+this.dataset.i)">✏️</button>'
           +'<button class="md-act-btn danger" data-s="logistics" data-i="'+i+'" onclick="mdDel(this.dataset.s,+this.dataset.i)">🗑</button></td></tr>';
    });
    setHTML('md-tbl-logistics', rows);
    setCount('logistics', S.logistics.length);
  }

  /* ── PORTFOLIO ── */
  function rPortfolio() {
    var pf=S.portfolio, headers=pf.headers, rows=pf.rows;
    if(!headers||headers.length<6){
      setHTML('md-portfolio-matrix','<p style="color:var(--text-muted);padding:24px">No portfolio data.</p>');
      return;
    }
    var skuCols=headers.slice(6, headers.length-1);
    var html='<table class="md-tbl md-portfolio-tbl">';
    html+='<thead><tr>';
    html+='<th>Customer</th><th>Type</th><th>Distributor</th><th>Status</th>';
    skuCols.forEach(function(h){
      html+='<th style="text-align:center;min-width:90px;font-size:10px">'+esc(h)+'</th>';
    });
    html+='</tr></thead><tbody>';
    rows.forEach(function(r){
      if(!r[1]) return;
      html+='<tr>';
      html+='<td><b>'+esc(r[2]||r[1])+'</b><div style="font-size:11px;color:var(--text-muted)">'+esc(r[1])+'</div></td>';
      html+='<td>'+esc(r[3])+'</td>';
      html+='<td>'+esc(r[4])+'</td>';
      html+='<td>'+chip(r[5])+'</td>';
      for(var ci=6;ci<headers.length-1;ci++){
        var v=r[ci];
        if(v==null||v===''||v==='—'||v==='-'){
          html+='<td style="text-align:center;color:#cbd5e1;font-size:12px">—</td>';
        } else if(String(v).toLowerCase()==='pipeline'){
          html+='<td style="text-align:center;background:#fef3c7"><span style="color:#92400e;font-size:11px;font-weight:600">~ Pipeline</span></td>';
        } else {
          html+='<td style="text-align:center;background:#ecfdf5;color:#065f46;font-weight:700;font-size:12px">₪'+(typeof v==='number'?Number(v).toFixed(2):v)+'</td>';
        }
      }
      html+='</tr>';
    });
    html+='</tbody></table>';
    setHTML('md-portfolio-matrix', html);
  }

  /* ── CRUD ── */
  var _mMode=null, _mSheet=null, _mIdx=null;

  /* ── Reload entity from API ── */
  function reloadEntity(sheet) {
    if(!API_OK) return;
    apiCall('GET', '/'+sheet).then(function(data){
      S[sheet] = data;
      mdRender(sheet);
    }).catch(function(){});
    /* Also reload portfolio if pricing/customers/products changed */
    if(['pricing','customers','products'].indexOf(sheet) >= 0) {
      apiCall('GET', '/portfolio').then(function(data){
        S.portfolio = data;
      }).catch(function(){});
    }
  }

  window.mdAdd = function(sheet) {
    _mMode='add'; _mSheet=sheet; _mIdx=null;
    openModal(sheet, null);
  };
  window.mdEdit = function(sheet, idx) {
    _mMode='edit'; _mSheet=sheet; _mIdx=idx;
    openModal(sheet, S[sheet][idx]);
  };
  window.mdDel = function(sheet, idx) {
    if(!confirm('Delete this entry?')) return;
    if(API_OK) {
      var map = ENTITY_MAP[sheet];
      var pk = S[sheet][idx][map.pk];
      apiCall('DELETE', '/'+sheet+'/'+encodeURIComponent(pk)).then(function(){
        reloadEntity(sheet);
        showToast('Deleted ✓ (removed from database)');
      }).catch(function(e){ alert('Error: '+e.message); });
    } else {
      S[sheet].splice(idx,1);
      mdRender(sheet);
      markDirty();
      showToast('Entry deleted (export to Excel to persist)');
    }
  };

  function openModal(sheet, rec) {
    var schema=SCHEMAS[sheet]; if(!schema) return;
    document.getElementById('md-modal-title').textContent=(_mMode==='add'?'Add ':'Edit ')+schema.label;
    var html='';
    var fkLoads = [];  // track FK select fields to populate async
    schema.fields.forEach(function(f){
      var val=rec&&rec[f.key]!=null?rec[f.key]:'';
      var wrap=f.full?'class="md-field-full"':'';
      html+='<div '+wrap+'>';
      html+='<label class="md-field-lbl">'+f.label+(f.required?' *':'')+'</label>';
      if(f.type==='fk_select'){
        /* FK dropdown — populated from lookup data or S[entity] */
        html+='<select class="md-field-inp" data-key="'+f.key+'" id="fk-sel-'+f.key+'">';
        html+='<option value="">— Select —</option>';
        /* Pre-populate from local state as fallback */
        var srcArr = S[f.lookup] || [];
        srcArr.forEach(function(item){
          var v = item[f.valKey]||'';
          var lbl = item[f.labelKey]||v;
          html+='<option value="'+esc(v)+'"'+(String(val)===String(v)?' selected':'')+'>'+esc(v)+' — '+esc(lbl)+'</option>';
        });
        html+='</select>';
        if(API_OK) fkLoads.push({key:f.key, lookup:f.lookup, valKey:f.valKey, labelKey:f.labelKey, curVal:val});
      } else if(f.type==='select'){
        html+='<select class="md-field-inp" data-key="'+f.key+'">';
        f.options.forEach(function(o){
          html+='<option value="'+esc(o)+'"'+(String(val)===o?' selected':'')+'>'+esc(o)+'</option>';
        });
        html+='</select>';
      } else if(f.type==='textarea'){
        html+='<textarea class="md-field-inp" data-key="'+f.key+'" rows="3">'+esc(String(val))+'</textarea>';
      } else {
        html+='<input class="md-field-inp" type="'+(f.type==='number'?'number':'text')+'" data-key="'+f.key+'" value="'+esc(String(val))+'" step="any">';
      }
      html+='</div>';
    });
    document.getElementById('md-modal-fields').innerHTML=html;
    document.getElementById('md-overlay').style.display='flex';
    /* Async-populate FK selects from API if available */
    fkLoads.forEach(function(fl){
      apiCall('GET', '/lookup/'+fl.lookup).then(function(items){
        var sel = document.getElementById('fk-sel-'+fl.key);
        if(!sel) return;
        sel.innerHTML = '<option value="">— Select —</option>';
        items.forEach(function(item){
          var v=item[fl.valKey]||'';
          var lbl=item[fl.labelKey]||v;
          var opt=document.createElement('option');
          opt.value=v; opt.textContent=v+' — '+lbl;
          if(String(fl.curVal)===String(v)) opt.selected=true;
          sel.appendChild(opt);
        });
      }).catch(function(){});  // Fallback already in DOM
    });
  }

  window.mdModalClose = function() {
    document.getElementById('md-overlay').style.display='none';
  };
  window.mdModalSave = function() {
    var schema=SCHEMAS[_mSheet]; if(!schema) return;
    var rec={};
    document.querySelectorAll('#md-modal-fields .md-field-inp').forEach(function(inp){
      var k=inp.dataset.key, v=inp.value;
      var field=schema.fields.find(function(f){return f.key===k;});
      if(field&&field.type==='number') v=v!==''?parseFloat(v):null;
      rec[k]=v;
    });
    if(API_OK) {
      /* ── API mode: persist directly to SQLite ── */
      var apiRec = toApiRecord(_mSheet, rec);
      var map = ENTITY_MAP[_mSheet];
      if(_mMode==='add') {
        apiCall('POST', '/'+_mSheet, apiRec).then(function(res){
          mdModalClose();
          reloadEntity(_mSheet);
          showToast('Created ✓ (saved to database)');
        }).catch(function(e){ alert('Error: '+e.message); });
      } else {
        var pk = S[_mSheet][_mIdx][map.pk];
        apiCall('PUT', '/'+_mSheet+'/'+encodeURIComponent(pk), apiRec).then(function(res){
          mdModalClose();
          reloadEntity(_mSheet);
          showToast('Updated ✓ (saved to database)');
        }).catch(function(e){ alert('Error: '+e.message); });
      }
    } else {
      /* ── Offline mode: mutate local state ── */
      if(_mMode==='add') S[_mSheet].push(rec);
      else { var old=S[_mSheet][_mIdx]; for(var k in rec) old[k]=rec[k]; rec=old; }
      /* Auto-resolve product display fields for pricing */
      if(_mSheet==='pricing' && rec.sku_key) {
        var prod=S.products.find(function(p){return p.sku_key===rec.sku_key;});
        if(prod) {
          if(!rec.name_en) rec.name_en=prod.name_en||'';
          if(!rec.name_he) rec.name_he=prod.name_he||'';
          if(!rec.barcode) rec.barcode=prod.barcode||'';
        }
      }
      mdModalClose();
      mdRender(_mSheet);
      markDirty();
      showToast('Saved locally ✓ (export to Excel to persist)');
    }
  };

  /* ── SAVE TO EXCEL ── */
  window.mdSave = function() {
    if(typeof XLSX==='undefined'){alert('XLSX library not loaded');return;}
    var wb=XLSX.utils.book_new();
    function addWS(name, data, cols) {
      if(!data||!data.length) return;
      var aoa=[cols.map(function(c){return c.label;})];
      data.forEach(function(r){ aoa.push(cols.map(function(c){return r[c.key]!=null?r[c.key]:'';}) ); });
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(aoa), name);
    }
    addWS('Brands', S.brands, [
      {key:'key',label:'Brand Key'},{key:'name',label:'Brand Name'},{key:'category',label:'Category'},
      {key:'status',label:'Status'},{key:'launch_date',label:'Launch Date'},{key:'owner',label:'Owner'},{key:'notes',label:'Notes'}
    ]);
    addWS('Products', S.products, [
      {key:'sku_key',label:'SKU Key'},{key:'barcode',label:'Barcode'},{key:'name_he',label:'Name HE'},
      {key:'name_en',label:'Name EN'},{key:'brand',label:'Brand Key'},{key:'category',label:'Category'},
      {key:'status',label:'Status'},{key:'launch_date',label:'Launch Date'},{key:'manufacturer',label:'Manufacturer'},{key:'cost',label:'Cost'}
    ]);
    addWS('Manufacturers', S.manufacturers, [
      {key:'key',label:'Key'},{key:'name',label:'Name'},{key:'products',label:'Products'},
      {key:'contact',label:'Contact'},{key:'location',label:'Location'},{key:'lead_time',label:'Lead Time'},
      {key:'moq',label:'MOQ'},{key:'payment_terms',label:'Payment Terms'},{key:'notes',label:'Notes'}
    ]);
    addWS('Distributors', S.distributors, [
      {key:'key',label:'Key'},{key:'name',label:'Name'},{key:'products',label:'Products'},
      {key:'commission_pct',label:'Commission'},{key:'report_format',label:'Report Format'},
      {key:'report_freq',label:'Report Freq'},{key:'contact',label:'Contact'},{key:'notes',label:'Notes'}
    ]);
    addWS('Customers', S.customers, [
      {key:'key',label:'Customer Key'},{key:'name_he',label:'Name HE'},{key:'name_en',label:'Name EN'},
      {key:'type',label:'Type'},{key:'distributor',label:'Distributor'},{key:'chain',label:'Chain/Group'},
      {key:'status',label:'Status'},{key:'contact',label:'Contact'},{key:'phone',label:'Phone'},{key:'notes',label:'Notes'}
    ]);
    addWS('Logistics', S.logistics, [
      {key:'product_key',label:'Product Key'},{key:'product_name',label:'Product Name'},
      {key:'storage_type',label:'Storage Type'},{key:'temp',label:'Temp'},
      {key:'units_per_carton',label:'Units/Carton'},{key:'cartons_per_pallet',label:'Cartons/Pallet'},
      {key:'units_per_pallet',label:'Units/Pallet'},{key:'pallet_divisor',label:'Pallet Divisor'},
      {key:'warehouse',label:'Warehouse'},{key:'notes',label:'Notes'}
    ]);
    addWS('Pricing', S.pricing, [
      {key:'barcode',label:'Barcode'},{key:'sku_key',label:'SKU Key'},{key:'name_en',label:'Name EN'},
      {key:'name_he',label:'Name HE'},{key:'customer',label:'Customer'},{key:'distributor',label:'Distributor'},
      {key:'commission_pct',label:'Commission'},{key:'sale_price',label:'Sale Price'},{key:'cost',label:'Cost'},
      {key:'gross_margin',label:'Gross Margin'},{key:'op_margin',label:'Op Margin'},
      {key:'status',label:'Status'},{key:'last_updated',label:'Last Updated'}
    ]);
    XLSX.writeFile(wb, 'Raito_Master_Data_export.xlsx');
    markClean();
    showToast('Exported to Excel ✓');
  };
  window.mdExportToExcel = window.mdSave;

  /* ── Close modal on overlay click ── */
  document.getElementById('md-overlay').addEventListener('click', function(e){
    if(e.target===this) mdModalClose();
  });

  /* ── Rebuild dashboard via API ── */
  window.mdRebuild = function() {
    if(!API_OK) { showToast('API server not running'); return; }
    showToast('Rebuilding dashboard...');
    apiCall('POST', '/rebuild').then(function(res) {
      showToast('Dashboard rebuilt ✓ Refresh page to see changes.');
    }).catch(function(e) { alert('Rebuild error: '+e.message); });
  };

  /* ── Init with API detection ── */
  function mdInit() {
    /* Try to detect API server */
    fetch(API_BASE + '/health', {method:'GET'})
      .then(function(r){ return r.json(); })
      .then(function(d){
        if(d.status==='ok') {
          API_OK = true;
          console.log('MD API connected:', API_BASE);
          /* Show status indicator + rebuild button */
          var st = document.getElementById('md-api-status');
          if(st) { st.style.background='#dcfce7'; st.style.color='#166534'; st.innerHTML='<span style=\"width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;\"></span> API Connected'; }
          var rbBtn = document.getElementById('md-rebuild-btn');
          if(rbBtn) rbBtn.style.display = '';
          var banner = document.getElementById('md-dirty-banner');
          if(banner) {
            banner.querySelector('.mdb-steps').innerHTML =
              '<b>API Connected</b> — Changes are saved directly to the database. Use "Rebuild Dashboard" to regenerate after edits.';
          }
          /* Load fresh data from API */
          var entities = ['brands','products','manufacturers','distributors','customers','logistics','pricing'];
          var loads = entities.map(function(e){ return apiCall('GET','/'+e); });
          loads.push(apiCall('GET','/portfolio'));
          Promise.all(loads).then(function(results){
            entities.forEach(function(e,i){ S[e] = results[i]; });
            S.portfolio = results[results.length-1];
            mdGo('brands');
          }).catch(function(){ mdGo('brands'); });
        } else {
          mdGo('brands');
        }
      })
      .catch(function(){
        console.log('MD API not available — using embedded data');
        mdGo('brands');
      });
  }
  if(document.readyState==='loading') {
    document.addEventListener('DOMContentLoaded', mdInit);
  } else {
    setTimeout(mdInit, 60);
  }

})();
</script>
'''
    return template.replace('__MD_DATA__', data_json)


DASHBOARD_PASSWORD = 'raito2026'  # Change this to set a different password

def _js_hash(s):
    """Replicate the JavaScript simpleHash function in Python."""
    h = 0
    for c in s:
        h = ((h << 5) - h) + ord(c)
        h = h & 0xFFFFFFFF  # Convert to 32-bit
        if h >= 0x80000000:
            h -= 0x100000000
    return str(h)

def _build_agent_plan_tab():
    """Build the Agent Plan tab content — Ma'ayan private market field agents goal tracking."""
    import pandas as pd

    agent_file = BASE_DIR.parent / 'data' / 'agents' / 'agents_plan.xlsx'
    if not agent_file.exists():
        return '<div style="padding:40px;text-align:center;color:#94a3b8">Agent plan data not found.</div>', '[]'

    df = pd.read_excel(agent_file, header=None)

    # Parse agents from rows 3..25 (0-indexed)
    agents = []
    for i in range(3, 26):
        row = df.iloc[i]
        agent_num = str(row[0]).strip() if pd.notna(row[0]) else ''
        agent_name = str(row[1]).strip() if pd.notna(row[1]) else ''
        num_customers = int(row[2]) if pd.notna(row[2]) else 0
        hist_nov = float(row[3]) if pd.notna(row[3]) else 0
        hist_dec = float(row[4]) if pd.notna(row[4]) else 0
        hist_jan = float(row[5]) if pd.notna(row[5]) else 0
        hist_feb = float(row[6]) if pd.notna(row[6]) else 0
        hist_total = float(row[7]) if pd.notna(row[7]) else 0
        pct_share = float(row[8]) if pd.notna(row[8]) else 0
        daily_avg = float(row[9]) if pd.notna(row[9]) else 0
        goal_final = float(row[12]) if pd.notna(row[12]) else 0
        daily_needed = float(row[13]) if pd.notna(row[13]) else 0

        # Skip excluded agents (red rows in source file)
        excluded_agents = {'^^^11', '^^^18', '^^^38', '^^^7^'}
        if agent_num in excluded_agents:
            continue

        if agent_name and goal_final > 0:
            agents.append({
                'num': agent_num,
                'name': agent_name,
                'customers': num_customers,
                'hist_total': hist_total,
                'pct_share': pct_share,
                'daily_avg': daily_avg,
                'goal': goal_final,
                'daily_needed': daily_needed,
                'achieved': 0,  # Will be filled by weekly updates
                'weekly': {},   # {week_label: amount} — filled from weekly reports
            })

    total_goal = sum(a['goal'] for a in agents)
    total_achieved = sum(a['achieved'] for a in agents)
    total_agents = len(agents)
    total_customers = sum(a['customers'] for a in agents)
    pct_achieved = round(total_achieved / total_goal * 100, 1) if total_goal > 0 else 0

    # Plan period info
    plan_start = '15/3/2026'
    plan_end = '31/5/2026'
    plan_days = 78  # 15 Mar - 31 May

    # Days elapsed (from 15/3/2026)
    from datetime import date
    today = date.today()
    start_date = date(2026, 3, 15)
    end_date = date(2026, 5, 31)
    days_elapsed = max(0, min((today - start_date).days, plan_days))
    days_remaining = max(0, plan_days - days_elapsed)
    time_pct = round(days_elapsed / plan_days * 100, 1)

    # Build agent table rows
    agent_rows = ''
    for idx, a in enumerate(agents):
        pct = round(a['achieved'] / a['goal'] * 100, 1) if a['goal'] > 0 else 0
        # Progress bar color
        if pct >= 80:
            bar_color = '#10b981'
        elif pct >= 40:
            bar_color = '#f59e0b'
        else:
            bar_color = '#e2e8f0'

        # Status badge
        if pct >= 100:
            status = '<span style="background:#ecfdf5;color:#10b981;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600">Done</span>'
        elif pct >= 50:
            status = '<span style="background:#fffbeb;color:#f59e0b;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600">On Track</span>'
        elif a['achieved'] > 0:
            status = '<span style="background:#fef2f2;color:#ef4444;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600">Behind</span>'
        else:
            status = '<span style="background:#f1f5f9;color:#94a3b8;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600">Not Started</span>'

        gap = a['goal'] - a['achieved']
        agent_rows += f'''<tr>
            <td style="font-weight:600;color:#1e293b">{idx+1}</td>
            <td style="font-weight:600;color:#1e293b">{a['name']}</td>
            <td style="color:#64748b">{a['num']}</td>
            <td style="text-align:center">{a['customers']}</td>
            <td style="text-align:right;font-weight:600">₪{a['goal']:,.0f}</td>
            <td style="text-align:right;font-weight:600;color:#10b981">₪{a['achieved']:,.0f}</td>
            <td style="min-width:120px">
                <div style="display:flex;align-items:center;gap:6px">
                    <div style="flex:1;background:#f1f5f9;border-radius:6px;height:8px;overflow:hidden">
                        <div style="width:{min(pct,100):.1f}%;background:{bar_color};height:100%;border-radius:6px;transition:width 0.3s"></div>
                    </div>
                    <span style="font-size:11px;font-weight:600;color:#64748b;min-width:36px">{pct:.0f}%</span>
                </div>
            </td>
            <td style="text-align:right;color:#ef4444;font-size:12px">₪{gap:,.0f}</td>
            <td style="text-align:right;font-size:12px;color:#64748b">₪{a['daily_needed']:,.0f}</td>
            <td style="text-align:center">{status}</td>
        </tr>'''

    # Build JSON blob for client-side updates (weekly data will be appended here)
    agents_json = json.dumps(agents, ensure_ascii=False)

    # KPI progress ring SVG helper
    def progress_ring(pct_val, color, size=80, stroke=6):
        r = (size - stroke) / 2
        circ = 2 * 3.14159 * r
        offset = circ * (1 - pct_val / 100)
        return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
                f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="#f1f5f9" stroke-width="{stroke}"/>'
                f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="{color}" stroke-width="{stroke}" '
                f'stroke-dasharray="{circ}" stroke-dashoffset="{offset:.1f}" '
                f'stroke-linecap="round" transform="rotate(-90 {size/2} {size/2})" style="transition:stroke-dashoffset 0.5s"/>'
                f'<text x="{size/2}" y="{size/2 + 1}" text-anchor="middle" dominant-baseline="middle" '
                f'font-size="14" font-weight="700" fill="{color}">{pct_val:.0f}%</text>'
                f'</svg>')

    goal_ring = progress_ring(pct_achieved, '#5D5FEF')
    time_ring = progress_ring(time_pct, '#f59e0b')

    html = f'''
<div style="padding:20px 28px;max-width:1400px;margin:0 auto">
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px;padding-right:160px">
        <div>
            <h2 style="font-size:20px;font-weight:800;color:#1A1D23;margin-bottom:4px">Agent Plan — Ma'ayan Private Market</h2>
            <p style="font-size:13px;color:#64748b">Field agent sales goals · {plan_start} — {plan_end} · Turbo Ice Cream</p>
        </div>
        <div style="display:flex;gap:8px">
            <div style="background:#f1f5f9;border-radius:10px;padding:6px 14px;font-size:12px;color:#64748b">
                <span style="font-weight:600;color:#1e293b">{days_elapsed}</span> / {plan_days} days elapsed
            </div>
            <div style="background:#f1f5f9;border-radius:10px;padding:6px 14px;font-size:12px;color:#64748b">
                <span style="font-weight:600;color:#1e293b">{days_remaining}</span> days remaining
            </div>
        </div>
    </div>

    <!-- KPI Cards -->
    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:24px">
        <!-- Total Goal -->
        <div style="background:#fff;border:1px solid #f1f5f9;border-radius:16px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.04)">
            <div style="font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">Total Goal</div>
            <div style="font-size:22px;font-weight:800;color:#5D5FEF;letter-spacing:-0.5px">₪{total_goal:,.0f}</div>
            <div style="font-size:11px;color:#94a3b8;margin-top:4px">{total_agents} agents · {total_customers} customers</div>
        </div>
        <!-- Total Achieved -->
        <div style="background:#fff;border:1px solid #f1f5f9;border-radius:16px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.04)">
            <div style="font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">Achieved</div>
            <div style="font-size:22px;font-weight:800;color:#10b981;letter-spacing:-0.5px">₪{total_achieved:,.0f}</div>
            <div style="font-size:11px;color:#94a3b8;margin-top:4px">of ₪{total_goal:,.0f} target</div>
        </div>
        <!-- Goal Progress Ring -->
        <div style="background:#fff;border:1px solid #f1f5f9;border-radius:16px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.04);display:flex;align-items:center;gap:14px">
            {goal_ring}
            <div>
                <div style="font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px">Goal Progress</div>
                <div style="font-size:13px;font-weight:600;color:#1e293b;margin-top:2px">₪{total_goal - total_achieved:,.0f} remaining</div>
            </div>
        </div>
        <!-- Time Progress Ring -->
        <div style="background:#fff;border:1px solid #f1f5f9;border-radius:16px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.04);display:flex;align-items:center;gap:14px">
            {time_ring}
            <div>
                <div style="font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px">Time Elapsed</div>
                <div style="font-size:13px;font-weight:600;color:#1e293b;margin-top:2px">{days_remaining} days left</div>
            </div>
        </div>
        <!-- Avg Goal per Agent -->
        <div style="background:#fff;border:1px solid #f1f5f9;border-radius:16px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.04)">
            <div style="font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">Avg Goal / Agent</div>
            <div style="font-size:22px;font-weight:800;color:#1e293b;letter-spacing:-0.5px">₪{total_goal/total_agents:,.0f}</div>
            <div style="font-size:11px;color:#94a3b8;margin-top:4px">₪{total_goal/total_agents/plan_days:,.0f} / day needed</div>
        </div>
    </div>

    <!-- Weekly Progress placeholder -->
    <div id="ap-weekly-chart" style="background:#fff;border:1px solid #f1f5f9;border-radius:16px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.04);margin-bottom:24px">
        <h3 style="font-size:14px;font-weight:700;color:#1A1D23;margin-bottom:12px">Weekly Progress</h3>
        <div style="text-align:center;padding:30px 0;color:#94a3b8;font-size:13px;border:2px dashed #e2e8f0;border-radius:12px">
            <div style="font-size:24px;margin-bottom:8px">📊</div>
            Weekly progress data from Ma'ayan will appear here.<br>
            <span style="font-size:11px">Upload weekly reports to <code>data/agents/</code> to populate.</span>
        </div>
    </div>

    <!-- Agent Table -->
    <div style="background:#fff;border:1px solid #f1f5f9;border-radius:16px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.04)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
            <h3 style="font-size:14px;font-weight:700;color:#1A1D23">Agent Performance</h3>
            <div style="font-size:11px;color:#94a3b8">Sorted by goal (desc) · Goals set by historical performance</div>
        </div>
        <div style="overflow-x:auto">
            <table style="width:100%;border-collapse:collapse;font-size:12px">
                <thead>
                    <tr style="border-bottom:2px solid #e2e8f0">
                        <th style="padding:8px 6px;text-align:left;font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.3px">#</th>
                        <th style="padding:8px 6px;text-align:left;font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.3px">Agent</th>
                        <th style="padding:8px 6px;text-align:left;font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.3px">ID</th>
                        <th style="padding:8px 6px;text-align:center;font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.3px">Customers</th>
                        <th style="padding:8px 6px;text-align:right;font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.3px">Goal (₪)</th>
                        <th style="padding:8px 6px;text-align:right;font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.3px">Achieved (₪)</th>
                        <th style="padding:8px 6px;text-align:left;font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.3px">Progress</th>
                        <th style="padding:8px 6px;text-align:right;font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.3px">Gap (₪)</th>
                        <th style="padding:8px 6px;text-align:right;font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.3px">Daily Target</th>
                        <th style="padding:8px 6px;text-align:center;font-size:10px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.3px">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {agent_rows}
                    <!-- Totals Row -->
                    <tr style="border-top:2px solid #e2e8f0;background:#f8fafc">
                        <td></td>
                        <td style="font-weight:700;color:#1e293b">Total</td>
                        <td></td>
                        <td style="text-align:center;font-weight:700">{total_customers}</td>
                        <td style="text-align:right;font-weight:700;color:#5D5FEF">₪{total_goal:,.0f}</td>
                        <td style="text-align:right;font-weight:700;color:#10b981">₪{total_achieved:,.0f}</td>
                        <td>
                            <div style="display:flex;align-items:center;gap:6px">
                                <div style="flex:1;background:#f1f5f9;border-radius:6px;height:8px;overflow:hidden">
                                    <div style="width:{min(pct_achieved,100):.1f}%;background:#5D5FEF;height:100%;border-radius:6px"></div>
                                </div>
                                <span style="font-size:11px;font-weight:700;color:#5D5FEF;min-width:36px">{pct_achieved:.0f}%</span>
                            </div>
                        </td>
                        <td style="text-align:right;font-weight:700;color:#ef4444">₪{total_goal - total_achieved:,.0f}</td>
                        <td style="text-align:right;font-weight:700;color:#64748b">₪{sum(a['daily_needed'] for a in agents):,.0f}</td>
                        <td></td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</div>
'''
    return html, agents_json


def generate_unified_dashboard(data, master_data=None):
    """
    Generate the unified multi-tab HTML dashboard.

    Args:
        data: dict from consolidate_data() with monthly_data, months, etc.
        master_data: dict from parse_master_data() (optional)

    Returns:
        HTML string for the complete dashboard
    """

    # Parse Master Data if not provided
    if master_data is None:
        master_data = parse_master_data()

    months = data.get('months', [])
    now_str = datetime.now().strftime('%d/%m/%Y %H:%M')

    # Last updated = dashboard generation time (updates each time new data is processed)
    last_update = now_str

    # Pricing constants from the engine (injected into JS f-strings, no hardcoding)
    turbo_b2b = get_b2b_price_safe('chocolate')
    dc_b2b = get_b2b_price_safe('dream_cake_2')

    # Build CC tab — passes the same consolidated data object as BO (single pipeline)
    cc_data = build_cc_tab(data)

    # Build Excel data JSON
    excel_json = _build_excel_data_json(data)

    # ── Build Business Overview Tab Content ──
    # Group months by year
    year_months = {}
    for m in months:
        year = m.split()[-1]
        year_months.setdefault(year, []).append(m)
    years_sorted = sorted(year_months.keys())

    # Build year filter buttons (default: 2026)
    default_year = '2026'
    year_btn_html = f'<button class="fbtn year-btn" onclick="boSetYear(\'all\')">All Years</button>\n'
    for yr in years_sorted:
        active = ' fbtn-active' if yr == default_year else ''
        year_btn_html += f'<button class="fbtn year-btn{active}" onclick="boSetYear(\'{yr}\')">{yr}</button>\n'

    # Build month filter buttons (hide non-2026 months by default)
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
        # Hide month buttons that don't belong to default year
        hide = ' style="display:none"' if year_attr != 'all' and year_attr != default_year else ''
        month_btn_html += f'<button class="fbtn month-btn{active}"{hide} data-year="{year_attr}" onclick="boSetMonth(\'{fid}\')">{flabel}</button>\n'

    # Build brand filter buttons
    brand_btn_html = ''
    for bid, binfo in BRAND_FILTERS.items():
        active = ' fbtn-active' if bid == 'ab' else ''
        brand_btn_html += f'<button class="fbtn brand-btn{active}" onclick="boSetBrand(\'{bid}\')">{binfo["label"]}</button>\n'

    btn_html = (f'<span>Year:</span> {year_btn_html}'
                f'<span style="margin-left:16px">Period:</span> {month_btn_html}'
                f'<span style="margin-left:16px">Brand:</span> {brand_btn_html}')

    # Build sections
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

    import json as _json
    year_overview_map_json = _json.dumps(year_overview_ids)

    # ── Build Agent Plan Tab ──
    agent_plan_content, agent_plan_json = _build_agent_plan_tab()

    # ── Build Master Data Tab ──
    master_data_content = _build_master_data_tab(master_data)

    # ── Build Sale Points Tab ──
    salepoint_content = build_salepoint_tab(data)

    # ── Unified HTML ──
    html = f"""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Raito Unified Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {{
  --primary:#5D5FEF; --primary-light:#A5A6F6; --primary-bg:rgba(93,95,239,0.08);
  --success:#10b981; --success-bg:#ecfdf5; --success-border:#a7f3d0;
  --danger:#ef4444; --danger-bg:#fef2f2; --danger-border:#fecaca;
  --warning:#f59e0b;
  --bg:#F8F9FB; --card:#ffffff; --text:#1A1D23; --text-muted:#64748B;
  --border:#E2E8F0; --border-light:#f1f5f9;
  --surface:#F1F5F9; --surface2:#f8fafc;
  --shadow:0 8px 30px rgba(0,0,0,0.04);
  --shadow-sm:0 1px 3px rgba(0,0,0,0.06);
  --radius:24px; --radius-sm:12px; --radius-pill:12px;
}}

* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family:'Inter',system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
  background:var(--bg); color:var(--text); direction:ltr;
  font-size:14px; line-height:1.5; -webkit-font-smoothing:antialiased;
}}

/* ── App Layout: Sidebar + Main ── */
.app-layout {{
  display:flex; min-height:100vh;
}}

/* ── Left Sidebar ── */
.sidebar {{
  width:240px; min-width:240px; background:var(--card);
  border-right:1px solid var(--border-light);
  display:flex; flex-direction:column;
  padding:0; position:fixed; top:0; left:0; bottom:0; z-index:100;
  overflow-y:auto;
}}
.sidebar-logo {{
  padding:24px 24px 20px; display:flex; align-items:center; gap:10px;
}}
.sidebar-logo .logo-icon {{
  width:36px; height:36px; background:var(--primary); border-radius:10px;
  display:flex; align-items:center; justify-content:center;
  color:#fff; font-weight:800; font-size:16px;
}}
.sidebar-logo .logo-text {{
  font-size:18px; font-weight:800; color:var(--text); letter-spacing:-0.3px;
}}
.sidebar-section {{
  padding:16px 16px 4px;
  font-size:10px; font-weight:700; color:var(--text-muted);
  text-transform:uppercase; letter-spacing:1.2px;
}}
.sidebar-nav {{ list-style:none; padding:0 10px; margin:0; }}
.sidebar-nav li {{ margin-bottom:2px; }}
.sidebar-nav a {{
  display:flex; align-items:center; gap:12px;
  padding:10px 14px; border-radius:10px;
  font-size:14px; font-weight:500; color:var(--text-muted);
  text-decoration:none; transition:all 0.15s; cursor:pointer;
}}
.sidebar-nav a:hover {{ background:var(--surface); color:var(--text); }}
.sidebar-nav a.active {{
  background:var(--surface); color:var(--text); font-weight:600;
}}
.sidebar-nav a svg {{ width:18px; height:18px; opacity:0.5; flex-shrink:0; }}
.sidebar-nav a.active svg {{ opacity:0.8; }}
.sidebar-footer {{
  margin-top:auto; padding:16px 20px; border-top:1px solid var(--border-light);
  font-size:11px; color:var(--text-muted);
}}
.sidebar-export-btn {{
  width:100%; background:var(--primary); color:#fff; border:none;
  padding:10px 16px; border-radius:10px; cursor:pointer;
  font-weight:600; font-size:12px; transition:background 0.2s;
  display:flex; align-items:center; justify-content:center; gap:7px;
  box-shadow:0 2px 8px rgba(99,102,241,0.3);
}}
.sidebar-export-btn:hover {{ background:#4f46e5; }}
.sidebar-export-btn svg {{ flex-shrink:0; }}

/* ── Export Modal ── */
.export-modal-overlay {{
  display:none; position:fixed; top:0; left:0; width:100vw; height:100vh;
  background:rgba(0,0,0,0.4); z-index:9999; align-items:center; justify-content:center;
}}
.export-modal-overlay.active {{ display:flex; }}
.export-modal {{
  background:#fff; border-radius:16px; box-shadow:0 20px 60px rgba(0,0,0,0.25);
  width:420px; max-width:92vw; max-height:82vh; overflow:hidden; display:flex; flex-direction:column;
}}
.export-modal-header {{
  padding:20px 24px 12px; border-bottom:1px solid var(--border-light);
  display:flex; align-items:center; justify-content:space-between;
}}
.export-modal-header h3 {{ margin:0; font-size:15px; font-weight:700; color:var(--text); }}
.export-modal-close {{
  background:none; border:none; cursor:pointer; color:var(--text-muted); font-size:20px; line-height:1; padding:4px;
}}
.export-modal-close:hover {{ color:var(--text); }}
.export-modal-body {{
  padding:16px 24px; overflow-y:auto; flex:1;
}}
.export-modal-section {{
  margin-bottom:16px;
}}
.export-modal-section-title {{
  font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;
  color:var(--text-muted); margin-bottom:8px;
}}
.export-modal-checks {{
  display:flex; flex-wrap:wrap; gap:6px;
}}
.export-modal-checks label {{
  display:flex; align-items:center; gap:6px; padding:6px 10px;
  background:var(--surface); border:1px solid var(--border-light); border-radius:8px;
  font-size:12px; color:var(--text); cursor:pointer; transition:all 0.15s;
  min-width:calc(50% - 3px); box-sizing:border-box;
}}
.export-modal-checks label:hover {{ border-color:var(--primary); background:#f0f0ff; }}
.export-modal-checks label input {{ accent-color:var(--primary); }}
.export-modal-checks .emc-all {{
  width:100%; background:var(--card); font-weight:600; border-color:var(--border);
}}
.export-modal-footer {{
  padding:12px 24px 16px; border-top:1px solid var(--border-light);
  display:flex; gap:8px; justify-content:flex-end;
}}
.export-modal-footer button {{
  padding:8px 20px; border-radius:10px; font-size:13px; font-weight:600; cursor:pointer; transition:all 0.15s;
}}
.export-modal-footer .emc-cancel {{
  background:var(--surface); border:1px solid var(--border); color:var(--text);
}}
.export-modal-footer .emc-cancel:hover {{ background:#eee; }}
.export-modal-footer .emc-download {{
  background:var(--primary); border:1px solid var(--primary); color:#fff;
}}
.export-modal-footer .emc-download:hover {{ background:#4a4cdb; }}

/* ── Main Content Area ── */
.main-content {{
  flex:1; margin-left:240px; min-height:100vh;
  max-width:calc(100vw - 240px); overflow-x:hidden; box-sizing:border-box;
}}

/* ── Tab Content Container ── */
.tab-content {{ display:none; }}
.tab-content.active {{ display:block; }}

/* ── Business Overview Tab Styles ── */
#tab-bo .fbar {{
  background:var(--card); padding:16px 180px 16px 32px; border-bottom:1px solid var(--border-light);
  display:flex; gap:12px; align-items:center; flex-wrap:wrap;
}}
#tab-bo .fbar span {{
  font-weight:700; font-size:11px; color:var(--text-muted);
  text-transform:uppercase; letter-spacing:0.8px;
}}
#tab-bo .filter-group {{
  display:inline-flex; background:var(--surface); padding:3px; border-radius:var(--radius-pill);
}}
#tab-bo .fbtn {{
  padding:6px 14px; border:none; border-radius:10px;
  background:transparent; font-size:12px; cursor:pointer; font-family:inherit;
  font-weight:600; color:var(--text-muted); transition:all 0.2s;
}}
#tab-bo .fbtn:hover {{ color:var(--text); }}
#tab-bo .fbtn-active {{
  background:var(--card); color:var(--text);
  box-shadow:0 1px 3px rgba(0,0,0,0.08);
}}
#tab-bo .ctr {{ max-width:1440px; margin:0 auto; padding:24px; overflow-x:clip; }}
#tab-bo .kpis {{ display:grid; grid-template-columns:repeat(5,1fr) !important; gap:12px; margin-bottom:20px; }}
#tab-bo .kpi {{
  background:var(--card) !important; border-radius:var(--radius) !important;
  padding:14px 12px !important; text-align:center !important;
  border:1px solid var(--border-light) !important; box-shadow:var(--shadow) !important;
  display:flex !important; flex-direction:column !important;
  align-items:center !important; justify-content:center !important;
  min-height:90px;
}}
#tab-bo .kpi-title {{
  font-size:11px !important; font-weight:700 !important; color:var(--text-muted) !important;
  margin-bottom:6px !important; text-transform:uppercase; letter-spacing:0.6px;
}}
#tab-bo .card {{
  background:var(--card) !important; border-radius:var(--radius) !important; padding:16px !important;
  border:1px solid var(--border-light) !important; box-shadow:var(--shadow) !important;
  margin-bottom:14px !important; box-sizing:border-box !important; max-width:100% !important;
  overflow-x:auto !important;
}}
#tab-bo .card.full {{ width:100% !important; }}
#tab-bo .card.half {{ min-width:0 !important; flex:1; }}
#tab-bo .card h3 {{ font-size:15px !important; font-weight:700 !important; margin-bottom:14px !important; color:var(--text) !important; }}
#tab-bo .tbl {{ width:100%; border-collapse:collapse; font-size:12px; margin-top:16px; table-layout:auto; }}
#tab-bo .tbl-wrap {{ overflow-x:auto; max-width:100%; }}
#tab-bo .tbl th {{
  background:var(--surface) !important; color:var(--text2) !important; padding:7px 12px !important;
  text-align:center !important; font-weight:700 !important; border-bottom:2px solid var(--border) !important;
  font-size:11px !important; text-transform:uppercase; letter-spacing:0.5px; white-space:nowrap;
}}
#tab-bo .tbl th:first-child {{ text-align:left !important; padding-left:28px !important; }}
#tab-bo .tbl th:nth-child(2) {{ text-align:left !important; }}
#tab-bo .tbl td {{ padding:8px 12px !important; text-align:center !important; border-bottom:1px solid var(--border-light) !important; color:var(--text); font-size:12px !important; white-space:nowrap; }}
#tab-bo .tbl td:first-child {{ text-align:left !important; }}
#tab-bo .tbl td:nth-child(2) {{ text-align:left !important; }}
/* Product ranking table has only 1 label column — override nth-child(2) back to center */
#tab-bo .tbl-prod-rank th:nth-child(n+2) {{ text-align:center !important; }}
#tab-bo .tbl-prod-rank td:nth-child(n+2) {{ text-align:center !important; }}
#tab-bo .tbl tr:last-child td {{ border-bottom:none !important; }}
#tab-bo .tbl tbody tr:hover {{ background:var(--surface2) !important; }}
#tab-bo .tbl .tot {{ font-weight:700; }}
#tab-bo .tbl tr[style*="border-top:2px solid #1e3a5f"] {{ border-top:2px solid var(--border) !important; }}

/* Distribution items in KPI cards */
#tab-bo .dist-item {{
  display:flex; align-items:center; gap:10px; padding:8px 0;
  border-bottom:1px solid var(--border-light); font-size:13px;
}}
#tab-bo .dist-item:last-child {{ border-bottom:none; }}
#tab-bo .dist-name {{ font-weight:600; flex:1; }}
#tab-bo .dist-pct {{ font-size:20px; font-weight:800; color:var(--primary); }}
#tab-bo .dist-units {{ font-size:11px; color:var(--text-muted); }}

/* SVG chart overrides */
#tab-bo svg {{ max-width:100% !important; height:auto !important; }}
#tab-bo svg text {{ font-family:'Inter',system-ui,sans-serif !important; }}

/* Make all content fit */
#tab-bo .card.full {{ width:100% !important; max-width:100% !important; box-sizing:border-box !important; }}
#tab-bo .card.half {{ min-width:0 !important; flex:1; }}
#tab-bo .month-section {{ max-width:100%; overflow-x:clip; }}

/* Badge overrides */
#tab-bo .badge.disc {{ background:#fef2f2 !important; color:#ef4444 !important; border:1px solid #fecaca !important; font-size:10px !important; padding:1px 8px; border-radius:20px; }}
#tab-bo .badge.new {{ background:#ecfdf5 !important; color:#10b981 !important; border:1px solid #a7f3d0 !important; font-size:10px !important; padding:1px 8px; border-radius:20px; }}

@media (max-width:1200px) {{ #tab-bo .kpis {{ grid-template-columns:repeat(3,1fr) !important; }} }}
@media (max-width:768px) {{ #tab-bo .kpis {{ grid-template-columns:repeat(2,1fr) !important; }} }}
@media (max-width:480px) {{ #tab-bo .kpis {{ grid-template-columns:1fr !important; }} }}

/* ── Trend badges ── */
.badge-up {{
  display:inline-flex; align-items:center; gap:2px;
  background:var(--success-bg); color:var(--success);
  font-size:10px; font-weight:700; padding:2px 8px;
  border-radius:20px; border:1px solid var(--success-border);
}}
.badge-down {{
  display:inline-flex; align-items:center; gap:2px;
  background:var(--danger-bg); color:var(--danger);
  font-size:10px; font-weight:700; padding:2px 8px;
  border-radius:20px; border:1px solid var(--danger-border);
}}
.big-number {{ font-size:24px !important; font-weight:800 !important; letter-spacing:-0.5px; line-height:1.2; }}
.big-number-md {{ font-size:20px !important; font-weight:800 !important; letter-spacing:-0.3px; line-height:1.2; }}
.stat-label {{ font-size:11px !important; }}
.stat-label {{
  font-size:10px; font-weight:600; color:var(--text-muted);
  text-transform:uppercase; letter-spacing:0.5px; margin-top:4px;
  text-align:center;
}}

/* ── Customer Performance Tab (CC) Styles - Scoped ── */
{cc_data['css']}

/* ── Master Data Tab ── */
#tab-md .ctr {{ max-width:1200px; margin:0 auto; padding:32px; }}
#tab-md .card {{
  background:var(--card); border-radius:var(--radius); padding:32px;
  border:1px solid var(--border-light); box-shadow:var(--shadow);
  margin-bottom:24px;
}}
#tab-md .card.full {{ width:100%; }}
#tab-md .card h3 {{ font-size:18px; font-weight:700; margin-bottom:20px; color:var(--text); }}
#tab-md .tbl {{ width:100%; border-collapse:collapse; font-size:13px; margin-top:16px; }}
#tab-md .tbl th {{
  background:transparent; color:var(--text-muted); padding:10px 14px;
  text-align:left; font-weight:600; border-bottom:1px solid var(--border);
  font-size:11px; text-transform:uppercase; letter-spacing:0.5px;
}}
#tab-md .tbl td {{ padding:10px 14px; border-bottom:1px solid var(--border-light); }}
#tab-md .tbl tr:last-child td {{ border-bottom:none; }}
#tab-md .tbl tbody tr:hover {{ background:var(--surface2); }}
</style>
</head>
<body>

<!-- Password Gate -->
<div id="login-gate" style="position:fixed;inset:0;z-index:9999;background:#F8F9FB;display:flex;align-items:center;justify-content:center">
  <div style="background:#fff;border-radius:20px;padding:48px 40px;box-shadow:0 20px 60px rgba(0,0,0,0.08);text-align:center;max-width:380px;width:90%">
    <div style="width:56px;height:56px;background:#5D5FEF;border-radius:16px;display:flex;align-items:center;justify-content:center;margin:0 auto 20px">
      <span style="color:#fff;font-weight:800;font-size:22px">R</span>
    </div>
    <h2 style="font-size:20px;font-weight:700;color:#1e293b;margin-bottom:6px">Raito Dashboard</h2>
    <p style="font-size:13px;color:#94a3b8;margin-bottom:24px">Enter password to continue</p>
    <input id="pwd-input" type="password" placeholder="Password"
      style="width:100%;padding:12px 16px;border:1px solid #e2e8f0;border-radius:12px;font-size:14px;font-family:inherit;outline:none;background:#F8F9FB;transition:border-color 0.2s"
      onfocus="this.style.borderColor='#5D5FEF'" onblur="this.style.borderColor='#e2e8f0'"
      onkeydown="if(event.key==='Enter')checkPwd()">
    <button onclick="checkPwd()"
      style="width:100%;margin-top:12px;padding:12px;background:#5D5FEF;color:#fff;border:none;border-radius:12px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;transition:background 0.2s"
      onmouseover="this.style.background='#4B4DD9'" onmouseout="this.style.background='#5D5FEF'">Sign In</button>
    <p id="pwd-err" style="color:#ef4444;font-size:12px;margin-top:10px;display:none">Incorrect password</p>
  </div>
</div>
<script>
// Simple hash check — not cryptographically secure but prevents casual access
var PWD_HASH='%%PWD_HASH%%';
function simpleHash(s){{var h=0;for(var i=0;i<s.length;i++){{h=((h<<5)-h)+s.charCodeAt(i);h|=0;}}return h.toString();}}
function checkPwd(){{
  var inp=document.getElementById('pwd-input').value;
  if(simpleHash(inp)===PWD_HASH){{
    document.getElementById('login-gate').style.display='none';
    sessionStorage.setItem('raito-auth','1');
  }}else{{
    document.getElementById('pwd-err').style.display='block';
    document.getElementById('pwd-input').style.borderColor='#ef4444';
    setTimeout(function(){{document.getElementById('pwd-err').style.display='none';document.getElementById('pwd-input').style.borderColor='#e2e8f0';}},2000);
  }}
}}
// Auto-login if already authenticated this session
if(sessionStorage.getItem('raito-auth')==='1'){{document.getElementById('login-gate').style.display='none';}}
</script>

<!-- Export Modal Overlay -->
<div class="export-modal-overlay" id="export-modal-overlay" onclick="if(event.target===this)closeExportModal()">
  <div class="export-modal">
    <div class="export-modal-header">
      <h3 id="export-modal-title">Export to Excel</h3>
      <button class="export-modal-close" onclick="closeExportModal()">&times;</button>
    </div>
    <div class="export-modal-body" id="export-modal-body"></div>
    <div class="export-modal-footer">
      <button class="emc-cancel" onclick="closeExportModal()">Cancel</button>
      <button class="emc-download" onclick="runExport()">Download</button>
    </div>
  </div>
</div>

<div class="app-layout">

<!-- Left Sidebar -->
<nav class="sidebar">
  <div class="sidebar-logo">
    <div class="logo-icon">R</div>
    <span class="logo-text">Raito</span>
  </div>

  <div class="sidebar-section">Dashboard</div>
  <ul class="sidebar-nav">
    <li><a class="active" onclick="switchTab('bo')" id="nav-bo">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
      Business Overview</a></li>
  </ul>

  <div class="sidebar-section">Analytics</div>
  <ul class="sidebar-nav">
    <li><a onclick="switchTab('cc')" id="nav-cc">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4-4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
      Customer Performance</a></li>
    <li><a onclick="switchTab('sp')" id="nav-sp">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
      Sale Points</a></li>
    <li><a onclick="switchTab('ap')" id="nav-ap">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20V10"/><path d="M18 20V4"/><path d="M6 20v-4"/></svg>
      Agent Plan</a></li>
  </ul>

  <div class="sidebar-section">Data</div>
  <ul class="sidebar-nav">
    <li><a onclick="switchTab('md')" id="nav-md">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
      Master Data</a></li>
  </ul>

  <div class="sidebar-footer">
    <button class="sidebar-export-btn" onclick="showExportModal()">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      Export Excel
    </button>
    <div style="text-align:center; font-size:10px; color:var(--text-muted); margin-top:8px;">Last updated: {last_update}</div>
  </div>
</nav>

<!-- Main Content -->
<div class="main-content">

<!-- Business Overview Tab -->
<div id="tab-bo" class="tab-content active">
  <div class="fbar" style="display:flex;align-items:center;flex-wrap:wrap;gap:6px"><span>Year</span> <div class="filter-group">{year_btn_html}</div><span style="margin-left:8px">Period</span> <div class="filter-group">{month_btn_html}</div><span style="margin-left:8px">Brand</span> <div class="filter-group">{brand_btn_html}</div></div>
  <div class="ctr">
    {sections}
  </div>
</div>

<!-- Customer Performance Tab -->
<div id="tab-cc" class="tab-content">
  {cc_data['html_body']}
</div>

<!-- Agent Plan Tab -->
<div id="tab-ap" class="tab-content">
  {agent_plan_content}
</div>

<!-- Sale Points Tab -->
<div id="tab-sp" class="tab-content">
  {salepoint_content}
</div>

<!-- Master Data Tab -->
<div id="tab-md" class="tab-content">
  {master_data_content}
</div>

</div><!-- /main-content -->
</div><!-- /app-layout -->

<!-- Scripts -->
<script>
// ══════════════════════════════════════════════════════════════════════════════
// UNIFIED TAB MANAGEMENT
// ══════════════════════════════════════════════════════════════════════════════

function switchTab(tabId) {{
  // Hide all tabs
  ['bo', 'cc', 'sp', 'ap', 'md'].forEach(t => {{
    var tab = document.getElementById('tab-' + t);
    if (tab) tab.classList.remove('active');
  }});

  // Show selected tab
  var selectedTab = document.getElementById('tab-' + tabId);
  if (selectedTab) selectedTab.classList.add('active');

  // Update sidebar nav active states
  document.querySelectorAll('.sidebar-nav a').forEach(a => a.classList.remove('active'));
  var navLink = document.getElementById('nav-' + tabId);
  if (navLink) navLink.classList.add('active');

  // Initialize CC charts on first view (lazy loading)
  if (tabId === 'cc' && !window._ccChartInit) {{
    window._ccChartInit = true;
    if (typeof renderAll === 'function') {{
      setTimeout(renderAll, 100);
    }}
  }}
}}

// ── Export Modal Logic ──────────────────────────────────────────────────────
var _exportTab = '';

function showExportModal(tab) {{
  var name = tab || '';
  if (!name) {{
    var a = document.querySelector('.sidebar-nav a.active');
    if (a) {{
      var t = a.textContent.trim();
      if (t.includes('Business')) name = 'bo';
      else if (t.includes('Customer')) name = 'cc';
      else if (t.includes('Sale')) name = 'sp';
      else if (t.includes('Master')) name = 'md';
    }}
  }}
  _exportTab = name;
  var body = document.getElementById('export-modal-body');
  var title = document.getElementById('export-modal-title');
  body.innerHTML = '';

  // Brand radio (shown first for BO, CC, SP — not MD)
  var brandHtml = (name !== 'md') ? _emcBrandRadio() : '';

  if (name === 'bo') {{
    title.textContent = 'Export Business Overview';
    var sheets = [['Overview','overview',true],['Detailed Sales','detailed',true],['Icedream Customers','ice_cust',true],["Ma'ayan Chains",'may_chains',true],['Inventory','inventory',true]];
    body.innerHTML = brandHtml
      + _emcSection('Sheets', sheets, 'bos')
      + _emcSection('Months', _boD.overview.map(function(r){{ return [r.month, r.month, true]; }}), 'bom');
  }} else if (name === 'cc') {{
    title.textContent = 'Export Customer Performance';
    var ccSheets = [['Summary','summary',true],['Customer Performance','cp',true],['Weekly Sales Trend','wst',true],['Weekly Detail','wd',true],['Product Mix','pm',true],['Inactive','inactive',true]];
    var ccCusts = (typeof customers!=='undefined') ? customers.map(function(c){{ return [c.name, c.name, true]; }}) : [];
    body.innerHTML = brandHtml
      + _emcSection('Sheets', ccSheets, 'ccs')
      + _emcSection('Customers', ccCusts, 'ccc');
  }} else if (name === 'sp') {{
    title.textContent = 'Export Sale Points';
    var spCusts = (typeof window.__SP_DATA__!=='undefined') ? window.__SP_DATA__.customers.map(function(c){{ return [c.name, c.name, true]; }}) : [];
    var spDists = [['All Distributors','all',true],['Icedream','Icedream',false],["Ma'ayan","Ma'ayan",false],['Biscotti','Biscotti',false]];
    body.innerHTML = brandHtml
      + _emcDistRadio(spDists)
      + _emcSection('Customers', spCusts, 'spc');
  }} else if (name === 'md') {{
    title.textContent = 'Export Master Data';
    var mdSheets = [['Brands','brands',true],['Products','products',true],['Manufacturers','manufacturers',true],['Distributors','distributors',true],['Customers','customers',true],['Logistics','logistics',true],['Pricing','pricing',true]];
    body.innerHTML = _emcSection('Sheets', mdSheets, 'mds');
  }} else {{
    alert('Export not available for this tab.');
    return;
  }}

  document.getElementById('export-modal-overlay').classList.add('active');
}}

function closeExportModal() {{
  document.getElementById('export-modal-overlay').classList.remove('active');
}}

// Brand — single-select radio buttons (no Select All)
function _emcBrandRadio() {{
  var brands = [['All Brands','all'],['Turbo','turbo'],["Dani's Dream Cake",'danis']];
  var h = '<div class="export-modal-section"><div class="export-modal-section-title">Brand</div><div class="export-modal-checks">';
  brands.forEach(function(b, i) {{
    h += '<label><input type="radio" name="emc-brand" value="' + b[1] + '"' + (i===0?' checked':'') + ' style="accent-color:var(--primary)">&nbsp;' + _emcEsc(b[0]) + '</label>';
  }});
  h += '</div></div>';
  return h;
}}

// Distributor — single-select radio buttons (for SP)
function _emcDistRadio(items) {{
  var h = '<div class="export-modal-section"><div class="export-modal-section-title">Distributor</div><div class="export-modal-checks">';
  items.forEach(function(d, i) {{
    h += '<label><input type="radio" name="emc-dist" value="' + _emcEsc(d[1]) + '"' + (i===0?' checked':'') + ' style="accent-color:var(--primary)">&nbsp;' + _emcEsc(d[0]) + '</label>';
  }});
  h += '</div></div>';
  return h;
}}

function _emcGetBrand() {{
  var r = document.querySelector('input[name="emc-brand"]:checked');
  return r ? r.value : 'all';
}}

function _emcGetDist() {{
  var r = document.querySelector('input[name="emc-dist"]:checked');
  return r ? r.value : 'all';
}}

// Checkbox section with Select All
function _emcSection(label, items, prefix) {{
  var h = '<div class="export-modal-section"><div class="export-modal-section-title">' + label + '</div><div class="export-modal-checks">';
  h += '<label class="emc-all"><input type="checkbox" checked onchange="_emcToggleAll(this,\\'' + prefix + '\\')">&nbsp;Select All</label>';
  items.forEach(function(it, i) {{
    h += '<label><input type="checkbox" ' + (it[2]?'checked':'') + ' data-emc="' + prefix + '" data-val="' + _emcEsc(it[1]) + '">&nbsp;' + _emcEsc(it[0]) + '</label>';
  }});
  h += '</div></div>';
  return h;
}}

function _emcEsc(s) {{ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }}

function _emcToggleAll(master, prefix) {{
  document.querySelectorAll('input[data-emc="' + prefix + '"]').forEach(function(cb) {{ cb.checked = master.checked; }});
}}

function _emcGetSelected(prefix) {{
  var sel = [];
  document.querySelectorAll('input[data-emc="' + prefix + '"]:checked').forEach(function(cb) {{ sel.push(cb.getAttribute('data-val')); }});
  return sel;
}}

function runExport() {{
  var brand = [_emcGetBrand()];
  if (_exportTab === 'bo') {{
    boExportToExcel(_emcGetSelected('bos'), _emcGetSelected('bom'), brand);
  }} else if (_exportTab === 'cc') {{
    ccExportToExcel(_emcGetSelected('ccs'), _emcGetSelected('ccc'), brand);
  }} else if (_exportTab === 'sp') {{
    spExportToExcel(_emcGetSelected('spc'), brand, _emcGetDist());
  }} else if (_exportTab === 'md') {{
    mdExportToExcel(_emcGetSelected('mds'));
  }}
  closeExportModal();
}}

// ══════════════════════════════════════════════════════════════════════════════
// BUSINESS OVERVIEW TAB STATE
// ══════════════════════════════════════════════════════════════════════════════

var boCurrentYear = '2026';
var boCurrentMonth = 'all';
var boCurrentBrand = 'ab';
var boYearOverviewMap = {year_overview_map_json};

function boSetYear(yr) {{
  boCurrentYear = yr;
  document.querySelectorAll('#tab-bo .year-btn').forEach(b => b.classList.remove('fbtn-active'));
  event.target.classList.add('fbtn-active');
  // Show/hide month buttons based on year
  document.querySelectorAll('#tab-bo .month-btn').forEach(function(b) {{
    var btnYear = b.getAttribute('data-year');
    if (yr === 'all' || btnYear === 'all' || btnYear === yr) {{
      b.style.display = '';
    }} else {{
      b.style.display = 'none';
    }}
  }});
  // Reset to Overview for the selected year
  boCurrentMonth = 'all';
  document.querySelectorAll('#tab-bo .month-btn').forEach(b => b.classList.remove('fbtn-active'));
  var ovBtn = document.querySelector('#tab-bo .month-btn[data-year="all"]');
  if (ovBtn) ovBtn.classList.add('fbtn-active');
  boUpdateVisibility();
}}

function boSetMonth(fid) {{
  boCurrentMonth = fid;
  boUpdateVisibility();
  document.querySelectorAll('#tab-bo .month-btn').forEach(b => b.classList.remove('fbtn-active'));
  event.target.classList.add('fbtn-active');
}}

function boSetBrand(bid) {{
  boCurrentBrand = bid;
  boUpdateVisibility();
  document.querySelectorAll('#tab-bo .brand-btn').forEach(b => b.classList.remove('fbtn-active'));
  event.target.classList.add('fbtn-active');
}}

function boUpdateVisibility() {{
  document.querySelectorAll('#tab-bo .month-section').forEach(function(s) {{
    s.style.display = 'none';
  }});
  // Determine which section to show
  var secId;
  if (boCurrentMonth === 'all' && boCurrentYear !== 'all') {{
    // Year overview
    secId = boYearOverviewMap[boCurrentYear] + '-' + boCurrentBrand;
  }} else {{
    secId = boCurrentMonth + '-' + boCurrentBrand;
  }}
  var el = document.getElementById('sec-' + secId);
  if (el) el.style.display = 'block';
}}

// ══════════════════════════════════════════════════════════════════════════════
// BUSINESS OVERVIEW EXPORT FUNCTION
// ══════════════════════════════════════════════════════════════════════════════

var _boD={excel_json};
function boExportToExcel(selSheets, selMonths, selBrands) {{
  if(typeof XLSX==='undefined'){{alert('SheetJS library not loaded.');return;}}
  selSheets = selSheets || ['overview','detailed','ice_cust','may_chains','inventory'];
  selMonths = selMonths || _boD.overview.map(function(r){{return r.month;}});
  selBrands = selBrands || ['all','turbo','danis'];
  // Brand filter: if 'all' is selected, include everything; otherwise filter by selected brands
  var _boIncludeAll = selBrands.indexOf('all') >= 0;
  var _boTurboProds = ['Turbo Chocolate','Turbo Vanilla','Turbo Mango','Turbo Pistachio'];
  var _boDanisProds = ["Dani's Dream Cake","Dani's Dream Cake (Biscotti)"];
  function _boBrandFilter(productName) {{
    if (_boIncludeAll) return true;
    if (selBrands.indexOf('turbo')>=0 && _boTurboProds.indexOf(productName)>=0) return true;
    if (selBrands.indexOf('danis')>=0 && _boDanisProds.indexOf(productName)>=0) return true;
    return false;
  }}
  var wb=XLSX.utils.book_new();
  var nf='#,##0',cf='₪#,##0';
  function tc(v,t,z){{var c={{v:v,t:t||'s'}};if(z)c.z=z;return c;}}
  function n(v,z){{return tc(v,'n',z||nf);}}
  function mf(r) {{ return selMonths.indexOf(r.month) >= 0; }}

  // Sheet 1: Overview
  if(selSheets.indexOf('overview')>=0) {{
    var ov=_boD.overview.filter(mf);
    var s1=[[tc('Raito Business Overview')],[],
      [tc('Month'),tc('Total Units'),tc('Total Revenue (₪)'),tc("Ma'ayan Units"),tc('Icedream Units')]];
    ov.forEach(function(r){{
      s1.push([tc(r.month),n(r.total_u),n(r.total_v,cf),n(r.may_u),n(r.ice_u)]);
    }});
    var ws1=XLSX.utils.aoa_to_sheet(s1);
    ws1['!cols']=[{{wch:16}},{{wch:14}},{{wch:18}},{{wch:16}},{{wch:16}}];
    XLSX.utils.book_append_sheet(wb,ws1,'Overview');
  }}

  // Sheet 2: Detailed Sales
  if(selSheets.indexOf('detailed')>=0) {{
    var dt=_boD.detailed.filter(mf).filter(function(r){{return _boBrandFilter(r.product);}});
    var s2=[[tc('Detailed Sales by Product & Month')],[],
      [tc('Month'),tc('Product'),tc("Ma'ayan (units)"),tc('Icedream (units)'),tc('Total Units'),tc('Revenue (₪)')]];
    dt.forEach(function(r){{
      s2.push([tc(r.month),tc(r.product),n(r.may_u),n(r.ice_u),n(r.total_u),n(r.revenue,cf)]);
    }});
    var ws2=XLSX.utils.aoa_to_sheet(s2);
    XLSX.utils.book_append_sheet(wb,ws2,'Detailed Sales');
  }}

  // Sheet 3: Icedream Customers
  if(selSheets.indexOf('ice_cust')>=0) {{
    var ic=_boD.ice_customers.filter(mf),ipl=_boD.ice_pl,ps=_boD.product_names;
    var h3=[tc('Month'),tc('Customer')];
    ipl.forEach(function(p){{h3.push(tc(ps[p]+' (units)'));}});
    ipl.forEach(function(p){{h3.push(tc(ps[p]+' (₪)'));}});
    h3.push(tc('Total Units'));h3.push(tc('Total ₪'));
    var s3=[[tc('Icedream Customers')],[],h3];
    ic.forEach(function(r){{
      var row=[tc(r.month),tc(r.customer)];
      ipl.forEach(function(p){{row.push(n(r[p+'_u']||0));}});
      ipl.forEach(function(p){{row.push(n(r[p+'_v']||0,cf));}});
      row.push(n(r.total_u));row.push(n(r.total_v,cf));
      s3.push(row);
    }});
    var ws3=XLSX.utils.aoa_to_sheet(s3);
    XLSX.utils.book_append_sheet(wb,ws3,'Icedream Customers');
  }}

  // Sheet 4: Ma'ayan Chains
  if(selSheets.indexOf('may_chains')>=0) {{
    var mc=_boD.may_chains.filter(mf),mpl=_boD.may_pl,ps2=_boD.product_names;
    var h4=[tc('Month'),tc('Chain')];
    mpl.forEach(function(p){{h4.push(tc(ps2[p]+' (units)'));}});
    mpl.forEach(function(p){{h4.push(tc(ps2[p]+' (₪)'));}});
    h4.push(tc('Total Units'));h4.push(tc('Total ₪'));
    var s4=[[tc("Ma'ayan Chains")],[],h4];
    mc.forEach(function(r){{
      var row=[tc(r.month),tc(r.chain)];
      mpl.forEach(function(p){{row.push(n(r[p+'_u']||0));}});
      mpl.forEach(function(p){{row.push(n(r[p+'_v']||0,cf));}});
      row.push(n(r.total_u));row.push(n(r.total_v,cf));
      s4.push(row);
    }});
    var ws4=XLSX.utils.aoa_to_sheet(s4);
    XLSX.utils.book_append_sheet(wb,ws4,"Ma'ayan Chains");
  }}

  // Sheet 5: Inventory
  if(selSheets.indexOf('inventory')>=0) {{
    var inv=_boD.inventory;
    if(inv && inv.length) {{
      var s5=[[tc('Inventory')],[],
        [tc('Product'),tc('Karfree'),tc('Icedream'),tc("Ma'ayan"),tc('Total')]];
      inv.forEach(function(r){{
        s5.push([tc(r.product),n(r.wh_u),n(r.ice_u),n(r.may_u),n(r.total_u)]);
      }});
      var ws5=XLSX.utils.aoa_to_sheet(s5);
      XLSX.utils.book_append_sheet(wb,ws5,'Inventory');
    }}
  }}

  if(wb.SheetNames.length===0){{alert('No sheets selected.');return;}}
  var d=new Date();
  XLSX.writeFile(wb,'Raito_Business_Overview_'+d.getDate()+'.'+(d.getMonth()+1)+'.'+d.getFullYear()+'.xlsx');
}}

// ══════════════════════════════════════════════════════════════════════════════
// CUSTOMER CENTRIC DASHBOARD EMBEDDED SCRIPTS
// ══════════════════════════════════════════════════════════════════════════════

{cc_data['scripts']}

// ══════════════════════════════════════════════════════════════════════════════
// MASTER DATA TAB EXPORT FUNCTION
// ══════════════════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════════════════
// SALE POINTS EXPORT FUNCTION (dynamic, SheetJS-based)
// ══════════════════════════════════════════════════════════════════════════════
function spExportToExcel(selCustomers, selBrands, selDist) {{
  if(typeof XLSX==='undefined'){{alert('SheetJS library not loaded.');return;}}
  if(!window.__SP_DATA__){{alert('No sale points data.');return;}}
  selCustomers = selCustomers || window.__SP_DATA__.customers.map(function(c){{return c.name;}});
  selBrands = selBrands || ['all','turbo','danis'];
  selDist = selDist || 'all';
  var _spIncAll = selBrands.indexOf('all')>=0;
  var _spTurbo = selBrands.indexOf('turbo')>=0;
  var _spDanis = selBrands.indexOf('danis')>=0;
  function _spBrandUnits(s) {{
    if (_spIncAll) return s.total;
    var u = 0;
    if (_spTurbo) u += (s.choc||0)+(s.van||0)+(s.mango||0)+(s.pist||0);
    if (_spDanis) u += (s.dc||0);
    return u;
  }}
  function _spBrandRev(s) {{
    if (_spIncAll) return s.rev||0;
    var r = 0;
    if (_spTurbo) r += ((s.choc||0)+(s.van||0)+(s.mango||0)+(s.pist||0)) * {turbo_b2b};
    if (_spDanis) r += (s.dc||0) * {dc_b2b};
    return r;
  }}
  function _spBrandMatch(s) {{
    return _spBrandUnits(s) > 0;
  }}
  var wb=XLSX.utils.book_new();
  var nf='#,##0',cf='₪#,##0';
  function tc(v,t,z){{var c={{v:v,t:t||'s'}};if(z)c.z=z;return c;}}
  function n(v,z){{return tc(v,'n',z||nf);}}

  var custs = window.__SP_DATA__.customers.filter(function(c){{
    if(selCustomers.indexOf(c.name)<0) return false;
    if(selDist!=='all' && c.distributor!==selDist) return false;
    return true;
  }});

  // Sheet 1: Summary
  var s1=[[tc('SALE POINTS DEEP DIVE — Summary')],[],
    [tc('#'),tc('Customer'),tc('Distributor'),tc('Sale Points'),tc('Dec'),tc('Jan'),tc('Feb'),tc('Mar'),tc('Total Units'),tc('Total Revenue')]];
  var gi=1;
  custs.forEach(function(c){{
    var pts=c.salepoints.filter(_spBrandMatch);
    if(pts.length===0) return;
    var sp=pts.length, tu=0,tr=0,dec=0,jan=0,feb=0,mar=0;
    pts.forEach(function(s){{tu+=_spBrandUnits(s);tr+=_spBrandRev(s);dec+=s.dec;jan+=s.jan;feb+=s.feb;mar+=s.mar;}});
    s1.push([n(gi++),tc(c.name),tc(c.distributor),n(sp),n(dec),n(jan),n(feb),n(mar),n(tu),n(Math.round(tr),cf)]);
  }});
  var ws1=XLSX.utils.aoa_to_sheet(s1);
  ws1['!cols']=[{{wch:4}},{{wch:22}},{{wch:12}},{{wch:12}},{{wch:10}},{{wch:10}},{{wch:10}},{{wch:10}},{{wch:13}},{{wch:14}}];
  XLSX.utils.book_append_sheet(wb,ws1,'Summary');

  // Sheet 2: All Sale Points
  var s2=[[tc('ALL SALE POINTS')],[],
    [tc('#'),tc('Customer Group'),tc('Distributor'),tc('Sale Point'),tc('Status'),tc('Dec'),tc('Jan'),tc('Feb'),tc('Mar'),tc('Total'),tc('Revenue'),tc('Choc'),tc('Van'),tc('Mango'),tc('Pist'),tc('DC')]];
  var ri=1;
  custs.forEach(function(c){{
    c.salepoints.filter(_spBrandMatch).forEach(function(s){{
      s2.push([n(ri++),tc(c.name),tc(c.distributor),tc(s.name),tc(s.status),n(s.dec),n(s.jan),n(s.feb),n(s.mar),n(_spBrandUnits(s)),n(Math.round(_spBrandRev(s)),cf),n(s.choc),n(s.van),n(s.mango),n(s.pist),n(s.dc)]);
    }});
  }});
  var ws2=XLSX.utils.aoa_to_sheet(s2);
  ws2['!cols']=[{{wch:4}},{{wch:18}},{{wch:12}},{{wch:36}},{{wch:12}},{{wch:8}},{{wch:8}},{{wch:8}},{{wch:8}},{{wch:10}},{{wch:12}},{{wch:8}},{{wch:8}},{{wch:8}},{{wch:8}},{{wch:8}}];
  XLSX.utils.book_append_sheet(wb,ws2,'All Sale Points');

  // Per-customer sheets
  custs.forEach(function(c){{
    var pts = c.salepoints.filter(_spBrandMatch);
    if(pts.length===0) return;
    var name = c.name.substring(0,31);
    var s=[[tc(c.name + ' — ' + c.distributor)],[],
      [tc('#'),tc('Sale Point'),tc('Status'),tc('Dec'),tc('Jan'),tc('Feb'),tc('Mar'),tc('Total'),tc('Revenue'),tc('Choc'),tc('Van'),tc('Mango'),tc('Pist'),tc('DC')]];
    var ci=1;
    pts.forEach(function(sp){{
      s.push([n(ci++),tc(sp.name),tc(sp.status),n(sp.dec),n(sp.jan),n(sp.feb),n(sp.mar),n(_spBrandUnits(sp)),n(Math.round(_spBrandRev(sp)),cf),n(sp.choc),n(sp.van),n(sp.mango),n(sp.pist),n(sp.dc)]);
    }});
    var ws=XLSX.utils.aoa_to_sheet(s);
    ws['!cols']=[{{wch:4}},{{wch:36}},{{wch:12}},{{wch:8}},{{wch:8}},{{wch:8}},{{wch:8}},{{wch:10}},{{wch:12}},{{wch:8}},{{wch:8}},{{wch:8}},{{wch:8}},{{wch:8}}];
    XLSX.utils.book_append_sheet(wb,ws,name);
  }});

  if(wb.SheetNames.length===0){{alert('No customers selected.');return;}}
  var d=new Date();
  XLSX.writeFile(wb,'Raito_Sale_Points_'+d.getDate()+'.'+(d.getMonth()+1)+'.'+d.getFullYear()+'.xlsx');
}}

// ══════════════════════════════════════════════════════════════════════════════
// MASTER DATA EXPORT FUNCTION
// ══════════════════════════════════════════════════════════════════════════════
function mdExportToExcel(selSheets) {{
  if(typeof window.mdSave === 'function') {{
    // mdSave already handles the full master data export
    window.mdSave();
  }} else {{
    alert('Master Data export not available.');
  }}
}}

</script>
</body>
</html>
"""

    # Generate Sale Points Excel
    sp_excel_path = OUTPUT_DIR / 'raito_salepoints_deep_dive.xlsx'
    generate_salepoint_excel(data, sp_excel_path)

    return html


def main():
    """Main entry point — generate and save the unified dashboard."""
    from parsers import consolidate_data

    # Load consolidated data
    print("Loading consolidated data...")
    data = consolidate_data()

    # Parse master data
    print("Parsing master data...")
    master_data = parse_master_data()

    # Generate dashboard
    print("Generating unified dashboard...")
    html = generate_unified_dashboard(data, master_data)

    # Save to file
    output_path = OUTPUT_DIR / 'unified_dashboard.html'
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Inject password hash
    pwd_hash = _js_hash(DASHBOARD_PASSWORD)
    html = html.replace('%%PWD_HASH%%', pwd_hash)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Dashboard saved to: {output_path}")
    print(f"File size: {len(html) / 1024:.1f} KB")

    # Auto-copy Excel to github-deploy so the Export Excel button works on GitHub Pages
    import shutil
    deploy_dir = BASE_DIR / 'github-deploy'
    if deploy_dir.exists():
        sp_excel = OUTPUT_DIR / 'raito_salepoints_deep_dive.xlsx'
        if sp_excel.exists():
            shutil.copy(sp_excel, deploy_dir / 'raito_salepoints_deep_dive.xlsx')
            print(f"Copied salepoints Excel to github-deploy/")


if __name__ == '__main__':
    main()
