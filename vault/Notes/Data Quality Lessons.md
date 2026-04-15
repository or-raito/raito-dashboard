---
title: Data Quality Lessons
date: 2026-04-05
tags: [raito, data-quality, operations]
status: active
---

# Data Quality Lessons

Hard-won lessons from QA passes and production bugs.

## Biscotti Duplicate Bug (Apr 1, 2026)

Two overlapping files in `data/biscotti/` both passed the sales report filter. Old format file (`daniel_amit_weekly_biscotti.xlsx`) and new format (`week13.xlsx`) were merged, doubling some unit counts. Fix: archive old file, update parser to prioritize new format.

**Lesson:** When switching file formats, archive old files immediately. Don't rely on parsers to deduplicate.

## Stock mtime Sorting (Apr 1, 2026)

Files copied at the same time (e.g., during setup) have near-identical mtimes. Sorting by mtime to pick "latest" stock file picked the wrong one for both Icedream and Ma'ayan. Fix: parse all stock files, sort by report_date inside the file.

**Lesson:** Never trust filesystem metadata for business logic. Use data inside the file.

## Ma'ayan Pivot Sheet (historical)

The `טבלת ציר` pivot sheet in Ma'ayan files double-counts rows. Parser must always use the detail sheet (`פירוט`). Skip keywords enforced in sheet selection.

**Lesson:** Summary/pivot sheets in Excel files are often wrong. Always use raw detail data.

## Geo Deployment (Mar 2026)

Docker `--no-cache` is essential after code changes. Inline styles in HTML get stripped by some browsers. Google Maps needs explicit resize trigger. DB connection must use the right user (`raito_app` for DDL).

## fkFields Renaming Bug — MD Tab (Apr 14, 2026)

The `fkFields` config in `ENTITY_MAP` (`unified_dashboard.py`) was renaming field keys before API PUT calls — e.g. `distributor` → `distributor_key`. Records were stored under the wrong key in the JSONB `master_data` table, then rendered as `undefined` in the table.

**Lesson:** Never add a renaming layer between the UI and the JSON store. API field names must match JSONB field names exactly.

## PostgreSQL Table Ownership Trap (Apr 14, 2026)

The Flask server creates tables as the `raito` user (not `raito_app`). Running `UPDATE` on `master_data` with `raito_app` credentials fails with `permission denied`. Always check table ownership (`\dt+ tablename` in psql) before running repair scripts.

**Rule:** Flask = `raito` user. Ingestion scripts = `raito_app` user. If a table was created by Flask, repair scripts must use `raito`.

## Related Notes

- [[RAITO Parser Landscape]]
- [[Distributor Overview]]
