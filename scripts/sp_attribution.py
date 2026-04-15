"""
RAITO — Sale-Point Attribution (Smart Suggest)

When a new branch appears in distributor sales data, we don't want to either
(a) lose the row, or (b) silently dump it into "Biscotti Customer". Instead:

  1. Try a prefix match against customers.name_he_aliases  → confidence 0.95+
  2. Try a contains/substring match                        → confidence 0.70–0.90
  3. Try a fuzzy token match (stripped of generic nouns)   → confidence 0.50–0.70
  4. Nothing matches                                       → attribution_status = 'unassigned'

The MD tab "Unassigned Sale Points" inbox reads `status IN (unassigned, suggested)`
and lets the user confirm or override the suggestion.

This module is the single SSOT for attribution logic — used by BOTH ingest_to_db.py
(at ingest time) and the Flask MD tab API (on-demand re-suggest for a given SP).

Public API:
    suggest_customer_for_branch(cur, distributor_id, branch_name_he) → dict
    list_inbox(cur) → list[dict]
    confirm_sale_point(cur, sale_point_id, customer_id, user=None) → dict
    resuggest_all(cur) → int   # re-runs matcher over all unassigned SPs
"""

from __future__ import annotations

import re
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Generic noun stopwords — stripped before fuzzy matching so we don't get
# false positives on words that appear in every branch name.
# ─────────────────────────────────────────────────────────────────────────────

_HE_STOPWORDS = {
    'סניף', 'סוכנות', 'חנות', 'מרכז', 'מרקט', 'בע"מ', 'בעמ',
    'סופר', 'מחסן', 'תחנה', 'קיוסק', 'צפון', 'דרום', 'מזרח', 'מערב',
    'ישראל', 'תל', 'אביב', 'ירושלים', 'חיפה',
}

# Minimum prefix length for a "prefix match" to count (avoids 2-letter hits)
_MIN_PREFIX_LEN = 4


def _normalize(s: str) -> str:
    """Collapse whitespace + strip quotes / commas / dashes for stable matching."""
    if not s:
        return ''
    s = re.sub(r'[\u05F3\u05F4\'",\-\.]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _tokenize(s: str) -> set[str]:
    return {
        t for t in _normalize(s).split()
        if t and t not in _HE_STOPWORDS and len(t) >= 2
    }


def _load_customer_aliases(cur) -> list[tuple]:
    """
    Returns list of (customer_id, name_en, name_he, aliases[]) for all
    active customers. Cheap enough to call per-SP since we expect <50 customers.
    """
    cur.execute(
        """
        SELECT id, name_en, COALESCE(name_he, ''), COALESCE(name_he_aliases, '{}')
          FROM customers
         WHERE is_active = TRUE
         ORDER BY id
        """
    )
    return cur.fetchall()


# ─────────────────────────────────────────────────────────────────────────────
# Main suggestion function
# ─────────────────────────────────────────────────────────────────────────────

def suggest_customer_for_branch(
    cur,
    distributor_id: int,
    branch_name_he: str,
) -> dict:
    """
    Returns:
        {
            'customer_id':  int | None,
            'confidence':   float,          # 0.0 – 1.0
            'reason':       str,            # short label shown in the inbox
            'status':       'suggested' | 'unassigned',
        }

    Never raises. Always returns a dict — if nothing matches, returns
    {customer_id: None, confidence: 0.0, reason: 'no match', status: 'unassigned'}.
    """
    branch = _normalize(branch_name_he)
    if not branch:
        return _unassigned('empty branch name')

    branch_tokens = _tokenize(branch)
    best = None  # (customer_id, confidence, reason)

    for cust_id, name_en, name_he, aliases in _load_customer_aliases(cur):
        # Compare every alias (+ name_he as an implicit alias)
        candidates = list(aliases or [])
        if name_he:
            candidates.append(name_he)

        for alias in candidates:
            alias_norm = _normalize(alias)
            if not alias_norm or len(alias_norm) < _MIN_PREFIX_LEN:
                continue

            # 1) Exact prefix — strongest signal
            if branch.startswith(alias_norm):
                conf = min(0.99, 0.85 + 0.01 * len(alias_norm))
                best = _better(best, (cust_id, conf, f'prefix: {alias_norm}'))
                continue

            # 2) Substring containment
            if alias_norm in branch:
                conf = min(0.90, 0.70 + 0.01 * len(alias_norm))
                best = _better(best, (cust_id, conf, f'contains: {alias_norm}'))
                continue

            # 3) Fuzzy — token overlap ratio (Jaccard) on non-stopword tokens
            alias_tokens = _tokenize(alias_norm)
            if alias_tokens and branch_tokens:
                overlap = alias_tokens & branch_tokens
                if overlap:
                    jaccard = len(overlap) / len(alias_tokens | branch_tokens)
                    if jaccard >= 0.34:
                        conf = round(0.50 + 0.20 * jaccard, 3)
                        best = _better(
                            best,
                            (cust_id, conf, f'fuzzy: {",".join(sorted(overlap))}')
                        )

    if best is None:
        return _unassigned('no match')

    cust_id, conf, reason = best
    return {
        'customer_id':  cust_id,
        'confidence':   round(conf, 3),
        'reason':       reason,
        'status':       'suggested',
    }


def _better(current, candidate):
    if current is None or candidate[1] > current[1]:
        return candidate
    return current


def _unassigned(reason: str) -> dict:
    return {
        'customer_id':  None,
        'confidence':   0.0,
        'reason':       reason,
        'status':       'unassigned',
    }


# ─────────────────────────────────────────────────────────────────────────────
# Inbox operations — used by MD tab API
# ─────────────────────────────────────────────────────────────────────────────

def list_inbox(cur, limit: int = 500) -> list[dict]:
    """
    Returns all sale_points awaiting confirmation (unassigned or suggested),
    joined with distributor + suggested-customer names for rendering.
    Ordered by confidence DESC so the user confirms easy wins first.
    """
    cur.execute(
        """
        SELECT sp.id,
               sp.branch_name_he,
               sp.attribution_status,
               sp.suggestion_confidence,
               sp.suggestion_reason,
               sp.first_order_date,
               sp.last_order_date,
               d.id       AS distributor_id,
               d.name_en  AS distributor_name,
               sc.id      AS suggested_customer_id,
               sc.name_en AS suggested_customer_name
          FROM sale_points sp
          JOIN distributors d ON d.id = sp.distributor_id
     LEFT JOIN customers sc   ON sc.id = sp.suggested_customer_id
         WHERE sp.attribution_status IN ('unassigned', 'suggested')
      ORDER BY sp.suggestion_confidence DESC NULLS LAST, sp.id ASC
         LIMIT %s
        """,
        (limit,),
    )
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def confirm_sale_point(
    cur,
    sale_point_id: int,
    customer_id: int,
    user: Optional[str] = None,
) -> dict:
    """
    User clicked "confirm" (or override) in the MD tab inbox.
    Sets customer_id, flips attribution_status to 'confirmed', and cascades
    the customer_id down to all sales_transactions attached to this SP.
    """
    cur.execute(
        """
        UPDATE sale_points
           SET customer_id           = %s,
               attribution_status    = 'confirmed',
               suggested_customer_id = NULL,
               suggestion_confidence = NULL,
               suggestion_reason     = NULL
         WHERE id = %s
        RETURNING id, distributor_id, branch_name_he
        """,
        (customer_id, sale_point_id),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"sale_point_id {sale_point_id} not found")

    # Cascade to historical transactions so CC/SP dashboards reattribute
    cur.execute(
        """
        UPDATE sales_transactions
           SET customer_id = %s,
               is_attributed = TRUE
         WHERE sale_point_id = %s
        """,
        (customer_id, sale_point_id),
    )
    tx_updated = cur.rowcount

    return {
        'sale_point_id':       row[0],
        'distributor_id':      row[1],
        'branch_name_he':      row[2],
        'customer_id':         customer_id,
        'transactions_updated': tx_updated,
    }


def resuggest_all(cur) -> int:
    """
    Re-runs the matcher on every sale_point currently in 'unassigned' or
    'suggested' state. Useful after adding new aliases to customers.
    Returns the number of rows whose suggestion changed.
    """
    cur.execute(
        """
        SELECT id, distributor_id, branch_name_he
          FROM sale_points
         WHERE attribution_status IN ('unassigned', 'suggested')
        """
    )
    rows = cur.fetchall()
    changed = 0
    for sp_id, dist_id, branch in rows:
        s = suggest_customer_for_branch(cur, dist_id, branch)
        cur.execute(
            """
            UPDATE sale_points
               SET attribution_status    = %s,
                   suggested_customer_id = %s,
                   suggestion_confidence = %s,
                   suggestion_reason     = %s
             WHERE id = %s
               AND (COALESCE(suggested_customer_id, 0) <> COALESCE(%s, 0)
                 OR attribution_status <> %s)
            """,
            (
                s['status'], s['customer_id'], s['confidence'], s['reason'],
                sp_id, s['customer_id'], s['status'],
            ),
        )
        changed += cur.rowcount
    return changed
