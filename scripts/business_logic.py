#!/usr/bin/env python3
"""
Raito Business Logic Engine — Single Source of Truth for status & trend rules.

Every module that needs to classify a sale point's status or compute a trend
MUST call into this engine. No duplicated logic in dashboard JS or Excel scripts.

Design: Option A (pre-compute in Python). All status taxonomies and trend
calculations are computed in the Python backend. The JS dashboard receives
pre-computed values in the JSON payload — it never re-derives them.

Canonical definitions (as of 2026-03-25):
  Status: Based on 4-month unit history (Dec, Jan, Feb, Mar).
  Trend:  MoM comparison of last two consecutive non-zero months.
"""

from __future__ import annotations

from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Status Taxonomy
# ═══════════════════════════════════════════════════════════════════════════════
#
# CANONICAL RULES (unified from SP dashboard + SP Excel):
#
#   mar > 0 AND any prior month > 0     → "Active"
#   mar > 0 AND no prior months > 0     → "New"
#   mar == 0 AND feb > 0                → "No Mar order"  (W13 data may be pending)
#   mar == 0 AND feb == 0 AND prior > 0 → "Churned"
#   all months == 0                     → excluded (shouldn't reach here)
#
# Note: The previous SP Excel used a stricter "Active" rule (required feb > 0
# specifically). We now unify to the dashboard's rule: mar > 0 AND *any* prior.
# This means a sale point with mar=5, dec=3, jan=0, feb=0 is "Active" (not
# "Reactivated"), because it has prior history even though feb was zero.

def compute_status(dec: int, jan: int, feb: int, mar: int) -> str:
    """Compute sale-point status from four-month unit history.

    Args:
        dec: Units in December 2025
        jan: Units in January 2026
        feb: Units in February 2026
        mar: Units in March 2026

    Returns:
        One of: 'Active', 'New', 'No Mar order', 'Churned'
    """
    dec = dec or 0
    jan = jan or 0
    feb = feb or 0
    mar = mar or 0

    if mar > 0:
        if dec > 0 or jan > 0 or feb > 0:
            return 'Active'
        else:
            return 'New'
    elif feb > 0:
        return 'No Mar order'
    elif dec > 0 or jan > 0:
        return 'Churned'
    else:
        return 'Churned'


# ═══════════════════════════════════════════════════════════════════════════════
# Trend Calculation
# ═══════════════════════════════════════════════════════════════════════════════
#
# CANONICAL RULE (unified):
#   Walk the monthly sequence backwards. Find the last two consecutive months
#   where both have > 0 units. Return the % change.
#
# Previous SP Excel compared only Dec→Feb. We unify to the dashboard's
# approach: last two consecutive non-zero months, which adapts better as
# new months are added.

def compute_trend(dec: int, jan: int, feb: int, mar: int) -> Optional[int]:
    """Compute MoM trend as integer percentage.

    Compares the last two consecutive months that both have > 0 units.
    Returns None if no such pair exists.

    Args:
        dec: Units in December 2025
        jan: Units in January 2026
        feb: Units in February 2026
        mar: Units in March 2026

    Returns:
        Integer percentage change (e.g., 25 for +25%, -50 for -50%),
        or None if trend cannot be computed.
    """
    dec = dec or 0
    jan = jan or 0
    feb = feb or 0
    mar = mar or 0

    monthly_seq = [dec, jan, feb, mar]

    for i in range(len(monthly_seq) - 1, 0, -1):
        if monthly_seq[i] > 0 and monthly_seq[i - 1] > 0:
            return round((monthly_seq[i] - monthly_seq[i - 1]) / monthly_seq[i - 1] * 100)

    return None


def compute_trend_fraction(dec: int, feb: int) -> Optional[float]:
    """Compute Dec→Feb trend as a float fraction (for Excel formatting).

    This is a convenience wrapper for cases where the Excel export needs
    a decimal fraction (e.g., 0.25 for +25%) rather than an integer %.

    Returns None if dec == 0.
    """
    dec = dec or 0
    feb = feb or 0
    if dec > 0:
        return (feb - dec) / dec if feb else -1.0
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Ordering Pattern
# ═══════════════════════════════════════════════════════════════════════════════

def compute_ordering_pattern(dec: int, jan: int, feb: int, mar: int) -> str:
    """Classify ordering consistency across 4 months.

    Returns 'Consistent' if data in >= 3 of 4 months, else 'Sporadic'.
    """
    active = sum(1 for v in [dec or 0, jan or 0, feb or 0, mar or 0] if v > 0)
    return 'Consistent' if active >= 3 else 'Sporadic'


# ═══════════════════════════════════════════════════════════════════════════════
# Months Active
# ═══════════════════════════════════════════════════════════════════════════════

def compute_months_active(dec: int, jan: int, feb: int, mar: int) -> int:
    """Count how many of the 4 months had > 0 units."""
    return sum(1 for v in [dec or 0, jan or 0, feb or 0, mar or 0] if v > 0)


# ═══════════════════════════════════════════════════════════════════════════════
# Batch Pre-Computation (for SP dashboard JSON payload)
# ═══════════════════════════════════════════════════════════════════════════════

def enrich_salepoint(sp: dict) -> dict:
    """Add computed status, trend, and months_active to a sale-point dict.

    Expects keys: 'dec', 'jan', 'feb', 'mar' (unit counts).
    Adds keys: 'status', 'trend', 'months_active'.

    Mutates and returns the same dict for chaining convenience.
    """
    d = sp.get('dec', 0) or 0
    j = sp.get('jan', 0) or 0
    f = sp.get('feb', 0) or 0
    m = sp.get('mar', 0) or 0

    sp['status'] = compute_status(d, j, f, m)
    sp['trend'] = compute_trend(d, j, f, m)
    sp['months_active'] = compute_months_active(d, j, f, m)
    return sp
