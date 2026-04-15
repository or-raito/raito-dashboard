"""
RAITO — Flask blueprint for the "Unassigned Sale Points" inbox.

Mount into unified_dashboard.py (or wherever the Flask app lives) with:

    from sp_inbox_api import sp_inbox_bp
    app.register_blueprint(sp_inbox_bp)

Endpoints (all prefixed /api/sp-inbox):
    GET    /api/sp-inbox/                  → list inbox rows (unassigned + suggested)
    POST   /api/sp-inbox/<sp_id>/confirm   → body: {"customer_id": int}
    POST   /api/sp-inbox/resuggest         → re-run matcher on all pending rows
    GET    /api/sp-inbox/customers         → list customers (for the dropdown)

All endpoints return JSON. Errors → {"error": "...", "status": 4xx/5xx}.

Connection: uses DATABASE_URL env var (same as the rest of the DB code).
"""

from __future__ import annotations

import os
import psycopg2
import psycopg2.extras
from flask import Blueprint, jsonify, request

from sp_attribution import (
    list_inbox,
    confirm_sale_point,
    resuggest_all,
)

sp_inbox_bp = Blueprint('sp_inbox', __name__, url_prefix='/api/sp-inbox')


def _conn():
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://raito:raito@localhost:5432/raito",
    )
    c = psycopg2.connect(url)
    c.autocommit = False
    return c


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/sp-inbox/  — list pending SPs with suggestions pre-filled
# ─────────────────────────────────────────────────────────────────────────────

@sp_inbox_bp.route('/', methods=['GET'])
def get_inbox():
    limit = int(request.args.get('limit', 500))
    try:
        with _conn() as conn, conn.cursor() as cur:
            rows = list_inbox(cur, limit=limit)
        # Convert date/decimal to JSON-friendly types
        for r in rows:
            for k, v in list(r.items()):
                if hasattr(v, 'isoformat'):
                    r[k] = v.isoformat()
                elif v is not None and hasattr(v, 'as_tuple'):  # Decimal
                    r[k] = float(v)
        return jsonify({'rows': rows, 'count': len(rows)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/sp-inbox/<sp_id>/confirm  — body: {"customer_id": int}
# ─────────────────────────────────────────────────────────────────────────────

@sp_inbox_bp.route('/<int:sp_id>/confirm', methods=['POST'])
def confirm(sp_id: int):
    body = request.get_json(silent=True) or {}
    customer_id = body.get('customer_id')
    if customer_id is None:
        return jsonify({'error': 'customer_id is required'}), 400
    try:
        with _conn() as conn, conn.cursor() as cur:
            result = confirm_sale_point(cur, sp_id, int(customer_id))
            conn.commit()
        return jsonify({'ok': True, 'result': result})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/sp-inbox/resuggest  — re-run matcher over all pending rows
# ─────────────────────────────────────────────────────────────────────────────

@sp_inbox_bp.route('/resuggest', methods=['POST'])
def resuggest():
    try:
        with _conn() as conn, conn.cursor() as cur:
            changed = resuggest_all(cur)
            conn.commit()
        return jsonify({'ok': True, 'changed': changed})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/sp-inbox/customers  — list active customers for the override dropdown
# ─────────────────────────────────────────────────────────────────────────────

@sp_inbox_bp.route('/customers', methods=['GET'])
def list_customers():
    try:
        with _conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT id, name_en, COALESCE(name_he, '') AS name_he
                  FROM customers
                 WHERE is_active = TRUE
              ORDER BY name_en
            """)
            rows = [
                {'id': r[0], 'name_en': r[1], 'name_he': r[2]}
                for r in cur.fetchall()
            ]
        return jsonify({'rows': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
