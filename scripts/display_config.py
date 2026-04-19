#!/usr/bin/env python3
"""
Display configuration — colors, short names, and ordering for dashboards.

These are VISUAL settings, not business data. They stay in code because
they control chart rendering, badge colors, and table column order —
concerns that don't belong in the master_data JSONB.

Moved here from registry.py during the Phase 1 SSOT migration (2026-04-19).
"""

from __future__ import annotations


# ═══════════════════════════════════════════════════════════════════════════════
# Product Colors
# ═══════════════════════════════════════════════════════════════════════════════

# Status-badge colors (used in SP tab, MD tab status badges)
PRODUCT_COLORS: dict[str, str] = {
    'chocolate':    '#8B4513',
    'vanilla':      '#F5DEB3',
    'mango':        '#FF8C00',
    'pistachio':    '#93C572',
    'magadat':      '#999999',
    'dream_cake':   '#4A0E0E',
    'dream_cake_2': '#C2185B',
}

# Flavor colors for charts (some differ from status-badge colors)
FLAVOR_COLORS: dict[str, str] = {
    'chocolate':    '#8B4513',
    'vanilla':      '#DAA520',
    'mango':        '#FF8C00',
    'pistachio':    '#93C572',
    'dream_cake':   '#DB7093',
    'dream_cake_2': '#C2185B',
    'magadat':      '#9CA3AF',
}

# Default color for new products not yet in the map
DEFAULT_PRODUCT_COLOR = '#6B7280'


# ═══════════════════════════════════════════════════════════════════════════════
# Display Order & Short Names
# ═══════════════════════════════════════════════════════════════════════════════

# Standard display order for tables and charts
PRODUCTS_ORDER: list[str] = [
    'chocolate', 'vanilla', 'mango', 'pistachio',
    'dream_cake', 'dream_cake_2', 'magadat',
]

# Short display names for table columns (derived from product name)
# Falls back to stripping 'Turbo ' prefix if a product isn't listed here.
_SHORT_NAME_OVERRIDES: dict[str, str] = {
    'dream_cake':   'Dream Cake',
    'dream_cake_2': 'Dream Cake',
    'magadat':      'Magadat',
}


def get_short_name(sku: str, full_name: str = '') -> str:
    """Return a short display name for a product SKU.

    Uses the override map first, then tries stripping common brand prefixes
    from the full product name.
    """
    if sku in _SHORT_NAME_OVERRIDES:
        return _SHORT_NAME_OVERRIDES[sku]
    # Strip known prefixes from the full name
    for prefix in ('Turbo ', "Dani's "):
        if full_name.startswith(prefix):
            return full_name[len(prefix):]
    # Strip known suffixes
    for suffix in (' - Biscotti', ' - biscotti'):
        if full_name.endswith(suffix):
            return full_name[:-len(suffix)]
    # Fallback: capitalize the SKU key
    return full_name or sku.replace('_', ' ').title()


def get_color(sku: str) -> str:
    """Return the status-badge color for a product SKU."""
    return PRODUCT_COLORS.get(sku, DEFAULT_PRODUCT_COLOR)


def get_flavor_color(sku: str) -> str:
    """Return the chart flavor color for a product SKU."""
    return FLAVOR_COLORS.get(sku, DEFAULT_PRODUCT_COLOR)
