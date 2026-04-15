#!/usr/bin/env python3
"""
Raito Business Logic Engine — Single Source of Truth for status & trend rules.

Every module that needs to classify a sale point's status or compute a trend
MUST call into this engine. No duplicated logic in dashboard JS or Excel scripts.

Design: Option A (pre-compute in Python). All status taxonomies and trend
calculations are computed in the Python backend. The JS dashboard receives
pre-computed values in the JSON payload — it never re-derives them.

Canonical definitions (as of 2026-04-14):
  Status: Based on chronological unit history (any number of months).
  Trend:  MoM comparison of last two consecutive non-zero months.

All functions accept *monthly_values (variadic) — backward compatible with
the old 4-positional-arg signature (dec, jan, feb, mar).
"""

from __future__ import annotations

from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Status Taxonomy
# ═══════════════════════════════════════════════════════════════════════════════
#
# CANONICAL RULES (dynamic — works with any number of months):
#
#   last > 0 AND any prior month > 0     → "Active"
#   last > 0 AND no prior months > 0     → "New"
#   last == 0 AND second-to-last > 0     → "No {label} order"
#   last == 0 AND second-to-last == 0 AND any prior > 0 → "Churned"
#   all months == 0                      → excluded (shouldn't reach here)

def compute_status(*monthly_values, last_month_label: str = 'recent') -> str:
    """Compute sale-point status from chronological unit history.

    Accepts any number of monthly unit values in chronological order.
    The last value is treated as the "current" month.

    Args:
        *monthly_values: Unit counts per month, oldest first.
        last_month_label: Short name of the last month (e.g., 'Apr')
            for the "No X order" status label.

    Returns:
        One of: 'Active', 'New', 'No {label} order', 'Churned'
    """
    vals = [v or 0 for v in monthly_values]
    if not vals:
        return 'Churned'

    last = vals[-1]
    prior = vals[:-1]
    second_last = prior[-1] if prior else 0

    if last > 0:
        if any(v > 0 for v in prior):
            return 'Active'
        else:
            return 'New'
    elif second_last > 0:
        return f'No {last_month_label} order'
    elif any(v > 0 for v in prior):
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

def compute_trend(*monthly_values) -> Optional[int]:
    """Compute MoM trend as integer percentage.

    Compares the last two consecutive months that both have > 0 units.
    Returns None if no such pair exists.

    Args:
        *monthly_values: Unit counts per month, oldest first.

    Returns:
        Integer percentage change (e.g., 25 for +25%, -50 for -50%),
        or None if trend cannot be computed.
    """
    vals = [v or 0 for v in monthly_values]

    for i in range(len(vals) - 1, 0, -1):
        if vals[i] > 0 and vals[i - 1] > 0:
            return round((vals[i] - vals[i - 1]) / vals[i - 1] * 100)

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

def compute_ordering_pattern(*monthly_values) -> str:
    """Classify ordering consistency.

    Returns 'Consistent' if data in >= 75% of months, else 'Sporadic'.
    """
    vals = [v or 0 for v in monthly_values]
    if not vals:
        return 'Sporadic'
    active = sum(1 for v in vals if v > 0)
    threshold = max(3, len(vals) * 3 // 4)  # 75%, minimum 3
    return 'Consistent' if active >= threshold else 'Sporadic'


# ═══════════════════════════════════════════════════════════════════════════════
# Months Active
# ═══════════════════════════════════════════════════════════════════════════════

def compute_months_active(*monthly_values) -> int:
    """Count how many months had > 0 units."""
    return sum(1 for v in monthly_values if (v or 0) > 0)


# ═══════════════════════════════════════════════════════════════════════════════
# Batch Pre-Computation (for SP dashboard JSON payload)
# ═══════════════════════════════════════════════════════════════════════════════

def enrich_salepoint(sp: dict, month_keys=None) -> dict:
    """Add computed status, trend, and months_active to a sale-point dict.

    Reads unit values for each month key from the dict, computes status/trend,
    and writes the results back. Mutates and returns the same dict.

    Args:
        sp: Sale-point dict with month short keys (e.g., 'dec', 'jan', ...).
        month_keys: Ordered list of month short keys to use for computation.
            If None, uses active months from config.get_active_month_keys().
    """
    if month_keys is None:
        from config import get_active_month_keys
        month_keys = get_active_month_keys()

    vals = [sp.get(k, 0) or 0 for k in month_keys]

    # Determine the last month's short label for the "No X order" status
    from config import _MONTH_REGISTRY
    label_map = {m[1]: m[2].split()[0] for m in _MONTH_REGISTRY}
    last_key = month_keys[-1] if month_keys else 'recent'
    last_label = label_map.get(last_key, last_key.capitalize())

    sp['status'] = compute_status(*vals, last_month_label=last_label)
    sp['trend'] = compute_trend(*vals)
    sp['months_active'] = compute_months_active(*vals)
    return sp
