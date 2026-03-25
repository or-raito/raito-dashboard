#!/usr/bin/env node
/**
 * weekly_deck.js — Generate Raito weekly insights deck from insights_data.py JSON.
 * Usage: python3 scripts/insights_data.py 2>/dev/null | node scripts/weekly_deck.js [output.pptx]
 *
 * Slides:
 *   1. Cover
 *   2. This Week at a Glance (Icedream KPIs)
 *   3. Icedream Weekly Trend (units + revenue per unit)
 *   4. Icedream Channel Breakdown (W-current)
 *   5. Flavor Mix
 *   6. Stock Levels & Projection
 *   7. Key Highlights
 */

const path = require('path');
const NM   = '/sessions/relaxed-keen-hopper/.npm-global/lib/node_modules';
const pptxgen = require(path.join(NM, 'pptxgenjs'));
const fs      = require('fs');

// ─── Palette ─────────────────────────────────────────────────────────────────
const C = {
  navy:    '0D1B2A',
  teal:    '06B6D4',
  blue:    '1E40AF',
  amber:   'F59E0B',
  white:   'FFFFFF',
  offWhite:'F8FAFC',
  muted:   '94A3B8',
  dark:    '1E293B',
  ice_col: '0EA5E9',
  green:   '22C55E',
  red:     'EF4444',
  purple:  '7C3AED',
};

const makeShadow = () => ({ type:'outer', blur:8, offset:3, angle:135, color:'000000', opacity:0.18 });

// ─── Formatters ───────────────────────────────────────────────────────────────
const fmtNum  = n => n >= 1000 ? (n/1000).toFixed(1)+'K' : String(n);
const fmtRev  = n => n >= 1000000 ? '₪'+(n/1000000).toFixed(2)+'M' : '₪'+(Math.round(n/1000))+'K';
const fmtPct  = v => v == null ? 'N/A' : (v > 0 ? '+' : '') + v.toFixed(1) + '%';
const pctColor = v => v == null ? C.muted : v > 0 ? C.green : C.red;

// ─── Slide 1: Cover ───────────────────────────────────────────────────────────
function addCover(pres, d) {
  const s = pres.addSlide();
  s.background = { color: C.navy };

  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.06, fill:{color:C.teal}, line:{color:C.teal} });
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0.06, w:0.08, h:5.565, fill:{color:C.teal}, line:{color:C.teal} });

  s.addText('RAITO', {
    x:0.5, y:1.3, w:9, h:1,
    fontSize:60, bold:true, color:C.white, fontFace:'Calibri', charSpacing:14, margin:0,
  });
  s.addText('Weekly Business Review', {
    x:0.5, y:2.35, w:9, h:0.6,
    fontSize:22, color:C.teal, fontFace:'Calibri', margin:0,
  });

  s.addShape(pres.shapes.RECTANGLE, { x:0.5, y:3.1, w:3, h:0.04, fill:{color:C.teal}, line:{color:C.teal} });

  const cur = d.current_week;
  s.addText(`W${cur.week}  ·  ${cur.label.replace('/', ' / ')}`, {
    x:0.5, y:3.3, w:6, h:0.55,
    fontSize:18, color:C.muted, fontFace:'Calibri', margin:0,
  });

  // Badge: Icedream focus note (when Ma'ayan pending)
  if (cur.maay_units === 0) {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x:0.5, y:4.0, w:3.8, h:0.45,
      fill:{color:'16243A'}, line:{color:C.amber, pt:1}, rectRadius:0.05,
    });
    s.addText('Icedream Focus  —  Ma\'ayan data pending', {
      x:0.55, y:4.06, w:3.7, h:0.33,
      fontSize:11, color:C.amber, fontFace:'Calibri', margin:0,
    });
  }

  s.addText(d.current_month.toUpperCase(), {
    x:0.5, y:4.8, w:9, h:0.45,
    fontSize:13, color:C.muted, fontFace:'Calibri', charSpacing:4, margin:0,
  });

  s.addShape(pres.shapes.RECTANGLE, { x:0, y:5.565, w:10, h:0.06, fill:{color:C.blue}, line:{color:C.blue} });
}

// ─── Slide 2: KPI — Icedream Focus ───────────────────────────────────────────
function addKpiSlide(pres, d) {
  const s = pres.addSlide();
  s.background = { color: C.navy };
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.06, fill:{color:C.teal}, line:{color:C.teal} });

  const cur = d.current_week;
  const maayPending = cur.maay_units === 0;

  s.addText('Icedream — This Week', {
    x:0.4, y:0.2, w:9, h:0.5,
    fontSize:22, bold:true, color:C.white, fontFace:'Calibri', margin:0,
  });
  s.addText(`W${cur.week} · ${cur.label}  ${maayPending ? "  |  Ma'ayan data pending" : ''}`, {
    x:0.4, y:0.68, w:9, h:0.35,
    fontSize:13, color:C.muted, fontFace:'Calibri', margin:0,
  });

  // Icedream RPU this week
  const iceRpu = cur.ice_units > 0 ? (cur.ice_rev / cur.ice_units).toFixed(2) : '—';

  const kpis = [
    { label:'Icedream Units',   value:fmtNum(cur.ice_units),
      sub:`${fmtPct(d.wow_ice_units)} vs W${cur.week-1}`, sub_color:pctColor(d.wow_ice_units) },
    { label:'Icedream Revenue', value:fmtRev(cur.ice_rev),
      sub:`${fmtPct(d.wow_rev)} vs W${cur.week-1}`, sub_color:pctColor(d.wow_rev) },
    { label:'Revenue / Unit',   value:`₪${iceRpu}`,
      sub:'Icedream blended avg', sub_color: C.muted },
    { label:"Ma'ayan Units",   value: maayPending ? 'Pending' : fmtNum(cur.maay_units),
      sub: maayPending ? 'Awaiting report' : `${fmtPct(d.wow_maay_units)} vs W${cur.week-1}`,
      sub_color: maayPending ? C.muted : pctColor(d.wow_maay_units) },
  ];

  const cols = [0.3, 2.8, 5.3, 7.8];
  kpis.forEach((k, i) => {
    const x = cols[i];
    const accent = i < 3 ? C.teal : C.muted;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y:1.25, w:2.2, h:2.8,
      fill:{color:'16243A'}, line:{color:'1E3A5F', pt:1}, shadow:makeShadow(),
    });
    s.addShape(pres.shapes.RECTANGLE, { x, y:1.25, w:2.2, h:0.055, fill:{color:accent}, line:{color:accent} });
    s.addText(k.label, {
      x:x+0.12, y:1.42, w:2.0, h:0.35,
      fontSize:11, color:C.muted, fontFace:'Calibri', margin:0,
    });
    s.addText(k.value, {
      x:x+0.1, y:1.85, w:2.05, h:0.9,
      fontSize:32, bold:true, color:C.white, fontFace:'Calibri', margin:0,
    });
    s.addText(k.sub, {
      x:x+0.12, y:2.82, w:2.0, h:0.4,
      fontSize:11, color:k.sub_color, fontFace:'Calibri', margin:0,
    });
  });

  // Bottom strip: top highlight
  s.addShape(pres.shapes.RECTANGLE, { x:0.3, y:4.35, w:9.4, h:0.95, fill:{color:'0D2137'}, line:{color:'1E3A5F', pt:1} });
  const hl = d.highlights.slice(0, 2).map(h => h.replace('▲','↑').replace('▼','↓')).join('   ·   ');
  s.addText(hl, {
    x:0.5, y:4.5, w:9, h:0.65,
    fontSize:11, color:C.muted, fontFace:'Calibri', margin:0,
  });
}

// ─── Slide 3: Icedream Weekly Trend ──────────────────────────────────────────
function addIcedreamTrendSlide(pres, d) {
  const s = pres.addSlide();
  s.background = { color: C.offWhite };
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.06, fill:{color:C.teal}, line:{color:C.teal} });

  s.addText('Icedream Weekly Trend', {
    x:0.4, y:0.15, w:9, h:0.5,
    fontSize:22, bold:true, color:C.dark, fontFace:'Calibri', margin:0,
  });
  s.addText('6-week units sold + revenue per unit', {
    x:0.4, y:0.62, w:9, h:0.35,
    fontSize:13, color:C.muted, fontFace:'Calibri', margin:0,
  });

  const tw     = d.trend_weeks;
  const labels = tw.map(w => `W${w.week}\n${w.label}`);

  // Units bar chart (left)
  s.addText('Units Sold — Icedream', {
    x:0.4, y:0.92, w:5.6, h:0.25,
    fontSize:11, bold:true, color:C.dark, fontFace:'Calibri', margin:0,
  });
  s.addChart(pres.charts.BAR, [
    { name:'Icedream Units', labels, values: tw.map(w => w.ice_units) },
  ], {
    x:0.4, y:1.1, w:5.6, h:3.8,
    barDir:'col',
    chartColors:[C.ice_col],
    chartArea:{ fill:{color:C.offWhite}, roundedCorners:false },
    catAxisLabelColor:C.dark, valAxisLabelColor:C.muted,
    valGridLine:{ color:'E2E8F0', size:0.5 }, catGridLine:{ style:'none' },
    showLegend:false,
    catAxisFontSize:9, valAxisFontSize:9,
    showValue:true, dataLabelColor:C.dark, dataLabelFontSize:9,
  });

  // Revenue per unit line chart (right)
  s.addText('Revenue per Unit (₪)', {
    x:6.2, y:0.92, w:3.5, h:0.25,
    fontSize:11, bold:true, color:C.dark, fontFace:'Calibri', margin:0,
  });
  s.addChart(pres.charts.LINE, [
    { name:'₪ / unit', labels, values: tw.map(w => w.ice_rpu) },
  ], {
    x:6.2, y:1.1, w:3.5, h:3.8,
    chartColors:[C.amber],
    chartArea:{ fill:{color:C.offWhite} },
    catAxisLabelColor:C.dark, valAxisLabelColor:C.muted,
    valGridLine:{ color:'E2E8F0', size:0.5 }, catGridLine:{ style:'none' },
    lineSize:3, lineSmooth:false,
    showLegend:false,
    catAxisFontSize:9, valAxisFontSize:9,
    showValue:true, dataLabelColor:C.amber, dataLabelFontSize:9,
  });
}

// ─── Slide 4: Icedream Channel Breakdown ─────────────────────────────────────
function addChannelSlide(pres, d) {
  const s = pres.addSlide();
  s.background = { color: C.offWhite };
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.06, fill:{color:C.teal}, line:{color:C.teal} });

  const wk = d.current_week.week;
  s.addText('Icedream Channel Breakdown', {
    x:0.4, y:0.15, w:9, h:0.5,
    fontSize:22, bold:true, color:C.dark, fontFace:'Calibri', margin:0,
  });
  s.addText(`W${wk} · ${d.current_week.label} — units by customer network`, {
    x:0.4, y:0.62, w:9, h:0.35,
    fontSize:13, color:C.muted, fontFace:'Calibri', margin:0,
  });

  const cb     = d.channel_breakdown;
  const labels = cb.map(c => c.network);
  const values = cb.map(c => c.units);

  // Horizontal bar chart (left)
  s.addChart(pres.charts.BAR, [
    { name:'Units', labels, values },
  ], {
    x:0.4, y:1.05, w:5.8, h:4.05,
    barDir:'bar',
    chartColors:[C.ice_col],
    chartArea:{ fill:{color:C.offWhite} },
    catAxisLabelColor:C.dark, valAxisLabelColor:C.muted,
    valGridLine:{ color:'E2E8F0', size:0.5 }, catGridLine:{ style:'none' },
    showLegend:false,
    catAxisFontSize:10, valAxisFontSize:9,
    showValue:true, dataLabelColor:C.white, dataLabelFontSize:10,
  });

  // Right: channel cards with % share bar
  const CARD_COLORS = ['0EA5E9','06B6D4','0284C7','0369A1','7DD3FC','BAE6FD'];
  cb.forEach((c, i) => {
    const y = 1.1 + i * 0.72;
    s.addShape(pres.shapes.RECTANGLE, {
      x:6.5, y, w:3.1, h:0.62,
      fill:{color:'FFFFFF'}, line:{color:'E2E8F0', pt:1}, shadow:makeShadow(),
    });
    // Coloured left accent
    s.addShape(pres.shapes.RECTANGLE, {
      x:6.5, y, w:0.07, h:0.62,
      fill:{color:CARD_COLORS[i] || C.teal}, line:{color:CARD_COLORS[i] || C.teal},
    });
    // Network name
    s.addText(c.network, {
      x:6.65, y:y+0.05, w:1.9, h:0.28,
      fontSize:11, bold:true, color:C.dark, fontFace:'Calibri', margin:0,
    });
    // Units + % on right
    s.addText(`${c.units.toLocaleString()}u`, {
      x:8.0, y:y+0.05, w:1.5, h:0.28,
      fontSize:12, bold:true, color:C.ice_col, fontFace:'Calibri', align:'right', margin:0,
    });
    // % share bar (mini)
    const barW = Math.max(0.05, (c.pct / 100) * 2.55);
    s.addShape(pres.shapes.RECTANGLE, {
      x:6.65, y:y+0.38, w:2.55, h:0.12,
      fill:{color:'E2E8F0'}, line:{color:'E2E8F0'},
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x:6.65, y:y+0.38, w:barW, h:0.12,
      fill:{color:CARD_COLORS[i] || C.teal}, line:{color:CARD_COLORS[i] || C.teal},
    });
    s.addText(`${c.pct}%`, {
      x:9.25, y:y+0.34, w:0.35, h:0.20,
      fontSize:9, color:C.muted, fontFace:'Calibri', align:'right', margin:0,
    });
  });
}

// ─── Slide 5: Flavor Mix ──────────────────────────────────────────────────────
function addFlavorSlide(pres, d) {
  const s = pres.addSlide();
  s.background = { color: C.offWhite };
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.06, fill:{color:C.teal}, line:{color:C.teal} });

  s.addText('Flavor Mix', {
    x:0.4, y:0.15, w:9, h:0.5,
    fontSize:22, bold:true, color:C.dark, fontFace:'Calibri', margin:0,
  });
  s.addText(`${d.current_month} · Icedream + Ma'ayan combined`, {
    x:0.4, y:0.62, w:9, h:0.35,
    fontSize:13, color:C.muted, fontFace:'Calibri', margin:0,
  });

  const fm     = d.flavor_mix;
  const labels = fm.map(f => f.flavor);

  s.addChart(pres.charts.BAR, [
    { name:'Icedream',  labels, values: fm.map(f => f.ice_units) },
    { name:"Ma'ayan",   labels, values: fm.map(f => f.maay_units) },
  ], {
    x:0.4, y:1.05, w:5.8, h:3.9,
    barDir:'bar', barGrouping:'stacked',
    chartColors:[C.ice_col, C.teal],
    chartArea:{ fill:{color:C.offWhite} },
    catAxisLabelColor:C.dark, valAxisLabelColor:C.muted,
    valGridLine:{ color:'E2E8F0', size:0.5 }, catGridLine:{ style:'none' },
    showLegend:true, legendPos:'b', legendColor:C.dark, legendFontSize:10,
    catAxisFontSize:11, valAxisFontSize:9,
    showValue:true, dataLabelColor:C.white, dataLabelFontSize:9,
  });

  const FLAVOR_COLORS = { 'Chocolate':'6B3A2A', 'Vanilla':'B8860B', 'Mango':'F97316', 'Pistachio':'4D7C0F', 'Dream Cake':'7C3AED' };
  fm.forEach((f, i) => {
    const y = 1.1 + i * 0.85;
    s.addShape(pres.shapes.RECTANGLE, {
      x:6.5, y, w:3.1, h:0.72,
      fill:{color:'FFFFFF'}, line:{color:'E2E8F0', pt:1}, shadow:makeShadow(),
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x:6.5, y, w:0.07, h:0.72,
      fill:{color: FLAVOR_COLORS[f.flavor] || C.teal}, line:{color: FLAVOR_COLORS[f.flavor] || C.teal},
    });
    s.addText(f.flavor, {
      x:6.65, y:y+0.06, w:2, h:0.28,
      fontSize:12, bold:true, color:C.dark, fontFace:'Calibri', margin:0,
    });
    s.addText(`${f.units.toLocaleString()} units total`, {
      x:6.65, y:y+0.35, w:2.8, h:0.25,
      fontSize:10, color:C.muted, fontFace:'Calibri', margin:0,
    });
    s.addText(f.units.toLocaleString(), {
      x:8.85, y:y+0.06, w:0.8, h:0.28,
      fontSize:14, bold:true, color:C.teal, fontFace:'Calibri', align:'right', margin:0,
    });
  });
}

// ─── Slide 6: Stock Levels & Projection ──────────────────────────────────────
function addStockSlide(pres, d) {
  const s = pres.addSlide();
  s.background = { color: C.navy };
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.06, fill:{color:C.amber}, line:{color:C.amber} });

  s.addText('Stock Levels & Projection', {
    x:0.4, y:0.18, w:9, h:0.5,
    fontSize:22, bold:true, color:C.white, fontFace:'Calibri', margin:0,
  });
  s.addText(`Inventory snapshot · ${new Date().toLocaleDateString('en-GB')}`, {
    x:0.4, y:0.66, w:9, h:0.32,
    fontSize:12, color:C.muted, fontFace:'Calibri', margin:0,
  });

  const inv = d.inventory;

  // ── Stock cards row ─────────────────────────────────────────────────────────
  const stockCards = [
    { label:'Icedream', units:inv.icedream, note:'at distributor', color:C.ice_col },
    { label:"Ma'ayan",  units:inv.maayan,   note:'at distributor', color:C.teal },
    { label:'Karfree',  units:inv.karfree,  note:'warehouse total', color:C.amber },
  ];
  const scols = [0.4, 3.6, 6.8];
  stockCards.forEach((c, i) => {
    const x = scols[i];
    s.addShape(pres.shapes.RECTANGLE, {
      x, y:1.25, w:2.8, h:1.5,
      fill:{color:'16243A'}, line:{color:'1E3A5F', pt:1}, shadow:makeShadow(),
    });
    s.addShape(pres.shapes.RECTANGLE, { x, y:1.25, w:2.8, h:0.055, fill:{color:c.color}, line:{color:c.color} });
    s.addText(c.label, {
      x:x+0.12, y:1.38, w:2.5, h:0.32,
      fontSize:12, color:C.muted, fontFace:'Calibri', margin:0,
    });
    s.addText(c.units.toLocaleString() + 'u', {
      x:x+0.1, y:1.68, w:2.6, h:0.6,
      fontSize:28, bold:true, color:C.white, fontFace:'Calibri', margin:0,
    });
    s.addText(c.note, {
      x:x+0.12, y:2.3, w:2.5, h:0.3,
      fontSize:10, color:C.muted, fontFace:'Calibri', margin:0,
    });
  });

  // ── Icedream cover scenarios table ──────────────────────────────────────────
  s.addText('Icedream Stock Cover — Scenarios', {
    x:0.4, y:3.0, w:5.5, h:0.38,
    fontSize:13, bold:true, color:C.white, fontFace:'Calibri', margin:0,
  });

  // Table header
  s.addShape(pres.shapes.RECTANGLE, { x:0.4, y:3.38, w:5.5, h:0.38, fill:{color:C.amber}, line:{color:C.amber} });
  s.addText('Scenario', { x:0.5, y:3.40, w:3.0, h:0.32, fontSize:11, bold:true, color:C.dark, fontFace:'Calibri', margin:0 });
  s.addText('Rate/wk', { x:3.4, y:3.40, w:1.2, h:0.32, fontSize:11, bold:true, color:C.dark, fontFace:'Calibri', align:'right', margin:0 });
  s.addText('Weeks left', { x:4.5, y:3.40, w:1.3, h:0.32, fontSize:11, bold:true, color:C.dark, fontFace:'Calibri', align:'right', margin:0 });

  const rowBgs = ['1A2D42', '16243A'];
  d.stock_scenarios.forEach((sc, i) => {
    const y = 3.76 + i * 0.42;
    s.addShape(pres.shapes.RECTANGLE, { x:0.4, y, w:5.5, h:0.40, fill:{color:rowBgs[i%2]}, line:{color:'1E3A5F', pt:1} });
    s.addText(sc.label, { x:0.5, y:y+0.04, w:2.9, h:0.32, fontSize:11, color:C.muted, fontFace:'Calibri', margin:0 });
    s.addText(sc.rate.toLocaleString()+'u', { x:3.4, y:y+0.04, w:1.2, h:0.32, fontSize:11, color:C.white, fontFace:'Calibri', align:'right', margin:0 });
    // Color code weeks: red < 2, amber 2-4, green > 4
    const wColor = sc.weeks < 2 ? C.red : sc.weeks < 4 ? C.amber : C.green;
    s.addText(sc.weeks != null ? sc.weeks + ' wks' : '—', {
      x:4.5, y:y+0.04, w:1.3, h:0.32, fontSize:12, bold:true, color:wColor, fontFace:'Calibri', align:'right', margin:0,
    });
  });

  // ── Karfree note ────────────────────────────────────────────────────────────
  const karf_months = d.karf_cover_months;
  const karf_color  = karf_months < 2 ? C.red : karf_months < 3 ? C.amber : C.green;
  s.addShape(pres.shapes.RECTANGLE, {
    x:6.2, y:3.0, w:3.4, h:1.8,
    fill:{color:'16243A'}, line:{color:'1E3A5F', pt:1}, shadow:makeShadow(),
  });
  s.addShape(pres.shapes.RECTANGLE, { x:6.2, y:3.0, w:3.4, h:0.055, fill:{color:C.amber}, line:{color:C.amber} });
  s.addText('Karfree Warehouse', {
    x:6.32, y:3.1, w:3.0, h:0.35,
    fontSize:12, bold:true, color:C.white, fontFace:'Calibri', margin:0,
  });
  s.addText(inv.karfree.toLocaleString() + ' units', {
    x:6.32, y:3.5, w:3.0, h:0.5,
    fontSize:22, bold:true, color:C.amber, fontFace:'Calibri', margin:0,
  });
  s.addText(`~${karf_months} months cover`, {
    x:6.32, y:3.98, w:3.0, h:0.32,
    fontSize:13, bold:true, color:karf_color, fontFace:'Calibri', margin:0,
  });
  s.addText(`at Dec–Feb avg (${(d.monthly_avg_combined/1000).toFixed(1)}K u/mo)`, {
    x:6.32, y:4.30, w:3.0, h:0.28,
    fontSize:10, color:C.muted, fontFace:'Calibri', margin:0,
  });

  s.addShape(pres.shapes.RECTANGLE, { x:0, y:5.565, w:10, h:0.06, fill:{color:C.amber}, line:{color:C.amber} });
}

// ─── Slide 7: Key Highlights ──────────────────────────────────────────────────
function addHighlightsSlide(pres, d) {
  const s = pres.addSlide();
  s.background = { color: C.navy };
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.06, fill:{color:C.amber}, line:{color:C.amber} });

  s.addText('Key Highlights', {
    x:0.4, y:0.18, w:9, h:0.5,
    fontSize:22, bold:true, color:C.white, fontFace:'Calibri', margin:0,
  });
  s.addText(`Auto-generated · W${d.current_week.week} · ${new Date().toLocaleDateString('en-GB')}`, {
    x:0.4, y:0.66, w:9, h:0.32,
    fontSize:12, color:C.muted, fontFace:'Calibri', margin:0,
  });

  const hl = d.highlights;
  hl.forEach((h, i) => {
    const y = 1.2 + i * 0.65;
    if (y + 0.6 > 5.5) return; // guard overflow
    // Colour accent bar: pending note → amber, down → red-tint, up → green-tint, else navy
    let accent = '1E3A5F';
    const clean = h.replace('▲','↑').replace('▼','↓');
    if (h.includes('pending')) accent = C.amber;
    else if (h.startsWith('▼') || h.startsWith('↓')) accent = C.red;
    else if (h.startsWith('▲') || h.startsWith('↑')) accent = C.green;

    s.addShape(pres.shapes.RECTANGLE, {
      x:0.4, y, w:9.2, h:0.56,
      fill:{color:'16243A'}, line:{color:'1E3A5F', pt:1},
    });
    s.addShape(pres.shapes.RECTANGLE, { x:0.4, y, w:0.06, h:0.56, fill:{color:accent}, line:{color:accent} });
    s.addText(clean, {
      x:0.56, y:y+0.08, w:8.9, h:0.38,
      fontSize:12, color:C.white, fontFace:'Calibri', margin:0,
    });
  });

  s.addShape(pres.shapes.RECTANGLE, { x:0, y:5.565, w:10, h:0.06, fill:{color:C.amber}, line:{color:C.amber} });
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  let raw = '';
  for await (const chunk of process.stdin) raw += chunk;

  let d;
  try { d = JSON.parse(raw); }
  catch(e) { console.error('Failed to parse JSON from stdin:', e.message); process.exit(1); }

  const outFile = process.argv[2] || 'docs/raito_weekly_insights.pptx';

  const pres = new pptxgen();
  pres.layout = 'LAYOUT_16x9';
  pres.title  = `Raito Weekly Review W${d.current_week.week}`;
  pres.author = 'Raito Analytics';

  addCover(pres, d);
  addKpiSlide(pres, d);
  addIcedreamTrendSlide(pres, d);
  addChannelSlide(pres, d);
  addFlavorSlide(pres, d);
  addStockSlide(pres, d);
  addHighlightsSlide(pres, d);

  await pres.writeFile({ fileName: outFile });
  console.log(`Deck saved: ${outFile}`);
}

main().catch(e => { console.error(e); process.exit(1); });
