---
title: RAITO System Architecture
date: 2026-04-05
tags: [raito, dashboard, architecture]
status: active
---

# RAITO System Architecture

RAITO is a multi-tier data management system tracking sales, profitability, and point-of-sale behavior across the retail supply chain for Turbo ice cream and Dani's Dream Cake.

## Four Dashboard Modules

- **Business Overview (BO)** — macro trends, flavors, brands, distributor performance
- **Customer Centric (CC)** — top ~18 major customers, profitability after distribution costs
- **Sale Point (SP)** — 1,200+ individual points of sale, ordering patterns, status taxonomies
- **Sales Agents** — field-operation module for sales reps

## Data Flow

Distributor Excel files → `parsers.py` → `consolidate_data()` → `unified_dashboard.py` → HTML output → Cloud Run

## Key Principle: SSOT

All data flows from unified Python engines. No discrepancies between views. See [[RAITO Parser Landscape]] for parser details.

## Infrastructure

- Cloud Run at `https://raito-dashboard-20004010285.me-west1.run.app`
- Cloud SQL PostgreSQL (`raito-db`)
- Region: `me-west1`
- Docker-based deploy from local Mac

## Biscotti Sale Point Relational Model (Apr 14, 2026)

Biscotti branches are now fully modelled relationally in the DB. Each `(distributor_id, branch_name_he)` pair has its own `sale_points` record with the correct `customer_id`. This means:

- **CC attribution** is driven by `sale_point_id → customer_id` join — no prefix hacks needed in DB mode
- **36 SP records** cover: 28 Wolt Market, 5 Naomi's Farm, Carmella, Matilda Yehud, Delicious Rishon LeZion
- **Future uploads** auto-create SP records via `_upsert_sale_point()` in `ingest_to_db.py`
- **COALESCE safety**: ON CONFLICT preserves manually-set customer_ids — auto-resolver never overwrites them

## Master Data Tab — DB-Backed (Apr 14, 2026)

The MD tab now reads from and writes to the PostgreSQL `master_data` table (JSONB). The Flask server auto-seeds from Excel on first API call. The table was created by Flask as the `raito` user — repair scripts must use `raito` credentials, not `raito_app`.

## Related Notes

- [[RAITO Parser Landscape]]
- [[Distributor Overview]]
- [[Data Quality Lessons]]
