#!/usr/bin/env python3
"""
Raito Business Overview — Main Orchestrator
Consolidates data from all sources, generates HTML dashboard and Excel report.

Modules:
  config.py       — Shared constants, product definitions, pricing, helpers
  parsers.py      — All file parsing (Icedream, Ma'ayan, Karfree, stock)
  dashboard.py    — HTML dashboard generator
  excel_report.py — Excel report generator
"""

from config import MONTH_NAMES_HEB
from parsers import consolidate_data
from dashboard import generate_dashboard
from excel_report import generate_excel


if __name__ == '__main__':
    print("=" * 60)
    print("Raito Business Overview — Data Processing Engine")
    print("=" * 60)

    data = consolidate_data()

    print("\n── Generating outputs ──")
    generate_excel(data)
    generate_dashboard(data)

    print("\n── Summary ──")
    for month in data['months']:
        md = data['monthly_data'][month]
        total = sum(md['combined'][p]['units'] for p in data['products'] if md['combined'].get(p))
        print(f"  {MONTH_NAMES_HEB.get(month, month)}: {total:,} יחידות")

    print("\nDone!")
