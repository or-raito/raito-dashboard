# RAITO Dashboard — UX Proposals
Generated: 2026-04-09  |  Trigger: scheduled

## Summary
Total proposals: 4
- High priority: 0
- Medium priority: 3
- Low priority: 1

## 1. [MEDIUM] Distributor Revenue vs. Weeks Active Scatter Plot
**Type:** `new_chart`

Add a scatter plot (BO tab) with X=weeks reported, Y=total season revenue per distributor. Size = total units. Useful when more distributors are added.

**Implementation:** Query: SELECT distributor, COUNT(*) AS weeks_reported, SUM(revenue) AS total_revenue, SUM(units) AS total_units FROM weekly_chart_overrides GROUP BY 1

**New API endpoint:** `GET /api/distributor-scatter`

## 2. [MEDIUM] API: /api/distributor-scatter
**Type:** `new_api_endpoint`

Returns per-distributor season totals for scatter plot

**SQL:**
```sql
SELECT distributor, COUNT(*) AS weeks_reported, SUM(units) AS total_units, SUM(revenue) AS total_revenue FROM weekly_chart_overrides GROUP BY 1
```

## 3. [MEDIUM] API: /api/distributor-wow
**Type:** `new_api_endpoint`

Distributor week-over-week comparison for radar/trend charts

**SQL:**
```sql
SELECT distributor, week_num, units, revenue FROM weekly_chart_overrides ORDER BY distributor, week_num
```

## 4. [LOW] Distributor Performance Radar Chart
**Type:** `new_chart`

Spider/radar chart comparing Icedream, Ma'ayan, Biscotti across axes: Revenue, Units, Weeks Active, WoW Growth. Gives executives a single-glance competitive view.

**Implementation:** Chart.js type: 'radar' in BO tab. Data from SELECT distributor, SUM(revenue), SUM(units), COUNT(*) FROM weekly_chart_overrides GROUP BY 1
