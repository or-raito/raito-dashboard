#!/usr/bin/env python3
"""
Customer name matching rules — prefix-based aggregation logic.

These are matching RULES, not master data. They stay in code (not in the DB)
because they encode ordering constraints and pattern-matching semantics that
are not suitable for a CRUD table.

Moved here from registry.py during the Phase 1 SSOT migration (2026-04-19).
"""

from __future__ import annotations


# ═══════════════════════════════════════════════════════════════════════════════
# Customer Prefix Matching
# ═══════════════════════════════════════════════════════════════════════════════
#
# These prefixes are used by config.extract_customer_name() to aggregate
# Icedream/Biscotti branch names into canonical customer names.
#
# CRITICAL: Must be ordered LONGEST-PREFIX-FIRST within any overlap group.
#   'חן כרמלה' (5 chars) MUST come before 'כרמלה' (5 chars)
#   'דומינוס פיצה' (11 chars) MUST come before 'דומינוס' (7 chars)
#
# If you add a new prefix, place it BEFORE any shorter prefix that is a
# substring of it. Or use rebuild_prefixes_sorted() to regenerate.

CUSTOMER_PREFIXES: list[str] = [
    'דומינוס פיצה', 'דומינוס', 'גוד פארם', 'חוות נעמי', 'נוי השדה',
    'וואלט', 'וולט', 'ינגו',
    'חן כרמלה', 'כרמלה',          # 'חן כרמלה' MUST come before 'כרמלה'
    'מתילדה', 'דלישס',             # Biscotti SPs under חנויות ביסקוטי
    'עוגיפלצת',
]

# Mapping: prefix → canonical customer name (EN).
# Used by the matching logic to resolve a branch name to its customer.
# Prefixes NOT listed here will be resolved via CUSTOMER_NAMES_EN in registry.
BISCOTTI_SP_TO_CUSTOMER: dict[str, str] = {
    'מתילדה': 'Biscotti - Chain',
    'דלישס':  'Biscotti - Chain',
    'חן כרמלה': 'Carmella',
}


def rebuild_prefixes_sorted(prefixes: list[str]) -> list[str]:
    """Sort prefixes longest-first to guarantee correct matching order.

    Call this when constructing CUSTOMER_PREFIXES from dynamic data
    (e.g., if a new prefix is added via the MD tab in a future phase).
    """
    return sorted(prefixes, key=lambda s: -len(s))


def validate_prefix_order(prefixes: list[str]) -> list[str]:
    """Check for ordering violations. Returns list of error messages (empty = OK).

    An ordering violation occurs when a shorter prefix appears before a
    longer one that starts with it (e.g., 'כרמלה' before 'חן כרמלה').
    """
    errors = []
    for i, p1 in enumerate(prefixes):
        for p2 in prefixes[i + 1:]:
            if p2.startswith(p1) and len(p2) > len(p1):
                errors.append(
                    f"Ordering violation: '{p1}' (pos {i}) appears before "
                    f"longer prefix '{p2}' which starts with it"
                )
    return errors
