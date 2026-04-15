#!/usr/bin/env python3
"""
RAITO — ID Resolvers

Provides cached lookup functions that resolve raw Hebrew strings
(from distributor Excel files) to canonical integer IDs.

Usage:
    from db.resolvers import EntityResolver

    resolver = EntityResolver()  # connects to DB, caches all lookups
    cid = resolver.resolve_customer("וולט מרקט")   # → (customer_id, "Wolt Market")
    pid = resolver.resolve_product("שוקולד")        # → (product_id, "chocolate")
    did = resolver.resolve_distributor("icedream")  # → distributor_id
    bid = resolver.resolve_brand("turbo")           # → brand_id

All resolvers return None for unmatched inputs and log them for review.
"""

import os
import sys
import logging
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger("raito.resolvers")

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

DEFAULT_DB_URL = "postgresql://raito:raito@localhost:5432/raito"


class EntityResolver:
    """
    Cached entity resolver. Loads all lookups from DB on init,
    then resolves in-memory with zero DB round-trips.

    Tracks unresolved names for reporting.
    """

    def __init__(self, conn=None, db_url=None):
        """
        Initialize resolver. Pass an existing connection or a DB URL.
        If neither, uses DATABASE_URL env var or default.
        """
        import psycopg2

        self._own_conn = False
        if conn:
            self._conn = conn
        else:
            url = db_url or os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
            self._conn = psycopg2.connect(url)
            self._own_conn = True

        # Lookup caches
        self._customer_alias = {}     # alias (str) → (customer_id, name_en)
        self._product_alias = {}      # alias (str) → (product_id, sku_key, name_en)
        self._product_keyword = {}    # keyword → (product_id, sku_key) for Hebrew substring matching
        self._distributor_key = {}    # key (str) → distributor_id
        self._distributor_name = {}   # name_he/name_en → distributor_id
        self._brand_key = {}          # key (str) → brand_id
        self._brand_id_to_en = {}     # brand_id → name_en

        # Unresolved tracking
        self._unresolved_customers = defaultdict(int)  # raw_name → count
        self._unresolved_products = defaultdict(int)    # raw_name → count

        self._load_all()

    def _load_all(self):
        """Load all lookup tables from DB into memory."""
        cur = self._conn.cursor()
        try:
            self._load_customers(cur)
            self._load_products(cur)
            self._load_distributors(cur)
            self._load_brands(cur)
        finally:
            cur.close()

    def _load_customers(self, cur):
        """Load customer alias lookup."""
        try:
            cur.execute("SELECT alias, customer_id, name_en FROM customer_alias_lookup")
            for alias, cid, name_en in cur.fetchall():
                if alias:
                    self._customer_alias[alias.strip()] = (cid, name_en)
            logger.info(f"Loaded {len(self._customer_alias)} customer aliases")
        except Exception as e:
            logger.warning(f"customer_alias_lookup not available: {e}")
            self._conn.rollback()
            # Fallback: load directly from customers table
            cur.execute("SELECT id, name_en, name_he, name_he_aliases FROM customers")
            for cid, name_en, name_he, aliases in cur.fetchall():
                if name_en:
                    self._customer_alias[name_en] = (cid, name_en)
                if name_he:
                    self._customer_alias[name_he] = (cid, name_en)
                if aliases:
                    for a in aliases:
                        if a:
                            self._customer_alias[a.strip()] = (cid, name_en)
            logger.info(f"Loaded {len(self._customer_alias)} customer aliases (fallback)")

    def _load_products(self, cur):
        """Load product alias lookup + keyword matching."""
        try:
            cur.execute("SELECT alias, product_id, sku_key, name_en FROM product_alias_lookup")
            for alias, pid, sku, name_en in cur.fetchall():
                if alias:
                    self._product_alias[alias.strip()] = (pid, sku, name_en)
            logger.info(f"Loaded {len(self._product_alias)} product aliases")
        except Exception as e:
            logger.warning(f"product_alias_lookup not available: {e}")
            self._conn.rollback()
            # Fallback: load directly from products table
            cur.execute("SELECT id, sku_key, full_name_en, full_name_he FROM products")
            for pid, sku, name_en, name_he in cur.fetchall():
                self._product_alias[sku] = (pid, sku, name_en)
                if name_en:
                    self._product_alias[name_en] = (pid, sku, name_en)
                if name_he:
                    self._product_alias[name_he] = (pid, sku, name_en)
            logger.info(f"Loaded {len(self._product_alias)} product aliases (fallback)")

        # Build Hebrew keyword map for substring matching
        # (same logic as config.classify_product but from DB data)
        _KEYWORDS = {
            'וניל':    'vanilla',
            'מנגו':    'mango',
            'שוקולד':  'chocolate',
            'מארז':    'magadat',
            'דרים':    'dream_cake',
            'פיסטוק':  'pistachio',
        }
        for keyword, sku in _KEYWORDS.items():
            if sku in self._product_alias:
                entry = self._product_alias[sku]
                self._product_keyword[keyword] = (entry[0], entry[1])

    def _load_distributors(self, cur):
        """Load distributor lookups."""
        cur.execute("SELECT id, key, name_en, name_he FROM distributors")
        for did, key, name_en, name_he in cur.fetchall():
            self._distributor_key[key] = did
            if name_en:
                self._distributor_name[name_en] = did
            if name_he:
                self._distributor_name[name_he] = did
        logger.info(f"Loaded {len(self._distributor_key)} distributors")

    def _load_brands(self, cur):
        """Load brand lookups."""
        try:
            cur.execute("SELECT id, key, name_en FROM brands")
            for bid, key, name_en in cur.fetchall():
                self._brand_key[key] = bid
                self._brand_id_to_en[bid] = name_en
            logger.info(f"Loaded {len(self._brand_key)} brands")
        except Exception as e:
            logger.warning(f"brands table not available: {e}")
            self._conn.rollback()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def resolve_customer(self, raw_name):
        """
        Resolve a raw Hebrew customer/chain/branch name to (customer_id, name_en).
        Returns None if not found (and logs the miss).
        """
        if not raw_name:
            return None

        clean = raw_name.strip()

        # Direct lookup
        result = self._customer_alias.get(clean)
        if result:
            return result

        # Try without common decorations (asterisks, shipping notation)
        import re
        cleaned = re.sub(r'^\*+|\*+$', '', clean).strip()
        cleaned = re.sub(r'\*?ת\.משלוח.*$', '', cleaned).strip()
        result = self._customer_alias.get(cleaned)
        if result:
            return result

        # Try prefix matching (longest first)
        for alias in sorted(self._customer_alias.keys(), key=len, reverse=True):
            if cleaned.startswith(alias) and len(alias) >= 3:
                return self._customer_alias[alias]

        # Not found
        self._unresolved_customers[raw_name] += 1
        return None

    def resolve_product(self, raw_name):
        """
        Resolve a raw Hebrew product name to (product_id, sku_key, name_en).
        Uses exact match first, then keyword substring matching.
        Returns None if not found.
        """
        if not raw_name:
            return None

        clean = raw_name.strip()

        # Exact match
        result = self._product_alias.get(clean)
        if result:
            return result

        # Keyword substring match (same logic as classify_product)
        for keyword, (pid, sku) in self._product_keyword.items():
            if keyword in clean:
                name_en = self._product_alias.get(sku, (None, None, sku))[2]
                return (pid, sku, name_en)

        # Not found
        self._unresolved_products[raw_name] += 1
        return None

    def resolve_product_by_sku(self, sku_key):
        """Resolve a SKU key to (product_id, sku_key, name_en). Fast path."""
        return self._product_alias.get(sku_key)

    def resolve_distributor(self, key_or_name):
        """Resolve a distributor key or name to distributor_id."""
        if not key_or_name:
            return None
        result = self._distributor_key.get(key_or_name)
        if result:
            return result
        return self._distributor_name.get(key_or_name)

    def resolve_brand(self, key):
        """Resolve a brand key to brand_id."""
        return self._brand_key.get(key)

    def brand_name(self, brand_id):
        """Get brand display name (English) from brand_id."""
        return self._brand_id_to_en.get(brand_id)

    # ─────────────────────────────────────────────────────────────────────────
    # Reporting
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def unresolved_customers(self):
        """Dict of raw names that couldn't be resolved → count."""
        return dict(self._unresolved_customers)

    @property
    def unresolved_products(self):
        """Dict of raw names that couldn't be resolved → count."""
        return dict(self._unresolved_products)

    def print_unresolved(self):
        """Print all unresolved names for review."""
        if self._unresolved_customers:
            print(f"\n⚠ Unresolved customers ({len(self._unresolved_customers)}):")
            for name, count in sorted(self._unresolved_customers.items(), key=lambda x: -x[1]):
                print(f"  [{count}x] '{name}'")
        else:
            print("\n✓ All customers resolved")

        if self._unresolved_products:
            print(f"\n⚠ Unresolved products ({len(self._unresolved_products)}):")
            for name, count in sorted(self._unresolved_products.items(), key=lambda x: -x[1]):
                print(f"  [{count}x] '{name}'")
        else:
            print("\n✓ All products resolved")

    def close(self):
        """Close the DB connection if we own it."""
        if self._own_conn and self._conn:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
