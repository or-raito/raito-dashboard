#!/usr/bin/env python3
"""
RAITO Geo Layer — Flask API Endpoints
======================================

Registers three Blueprint routes onto the existing Flask app:

  GET /api/geo/municipalities   → Full GeoJSON FeatureCollection of Israeli
                                   municipal boundaries (cached in memory after
                                   first load from the DB).

  GET /api/geo/choropleth       → KPI values per municipality, filtered by
                                   month, distributor, and brand.  Drives map colours.
                                   Query params:
                                     kpi         — revenue | units | pos_count
                                     month       — all | 2026-01 | 2026-02 | …
                                     distributor — all | icedream | mayyan | biscotti
                                     brand       — all | turbo | danis

  GET /api/geo/pos              → Individual POS data within a municipality.
                                   Drives markers/heatmap and the info panel.
                                   Query params:
                                     municipality_id — CBS code (e.g. "5000")
                                     month           — all | 2026-01 | 2026-02 | …
                                     distributor     — all | icedream | mayyan | biscotti
                                     brand           — all | turbo | danis

INTEGRATION
-----------
In your Flask app (app.py / unified_dashboard.py server section):

    from geo_api import geo_blueprint
    app.register_blueprint(geo_blueprint)

CACHING
-------
Municipality GeoJSON is loaded once at startup and cached in memory.
KPI data is queried live on each request (fast because of the PostGIS indexes).
For high-traffic use, wrap KPI queries in a short TTL cache (e.g. Flask-Caching).
"""

import csv
import io
import json
import logging
import os
from functools import lru_cache
from pathlib import Path

try:
    from flask import Blueprint, jsonify, request, current_app
except ImportError:
    raise ImportError(
        "Flask not installed. Run: pip install flask --break-system-packages"
    )

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    raise ImportError(
        "psycopg2 not installed. Run: pip install psycopg2-binary --break-system-packages"
    )

log = logging.getLogger("geo_api")

geo_blueprint = Blueprint("geo", __name__, url_prefix="/api/geo")

# Path to a fallback GeoJSON file (used if municipalities_geo table is empty)
GEOJSON_FALLBACK_PATH = Path(__file__).parent.parent / "data" / "geo" / "israel_municipalities.geojson"


# ---------------------------------------------------------------------------
# DB connection helper (reuses logic from geocoding_pipeline.py)
# ---------------------------------------------------------------------------

def _get_db_conn():
    """
    Open a fresh DB connection using the same pattern as db_dashboard.py.
    Uses DATABASE_URL if set, otherwise falls back to Cloud SQL Unix socket
    or local dev defaults.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        # Cloud Run: try Unix socket (same as db_dashboard.py)
        cloud_sql_instance = os.environ.get(
            "CLOUD_SQL_INSTANCE", "raito-house-of-brands:me-west1:raito-db"
        )
        socket_path = f"/cloudsql/{cloud_sql_instance}"
        if Path(socket_path).exists():
            database_url = (
                f"postgresql://raito:raito@/{os.environ.get('PGDATABASE', 'raito')}"
                f"?host={socket_path}"
            )
        else:
            database_url = "postgresql://raito:raito@127.0.0.1:5432/raito"

    return psycopg2.connect(database_url)


# ---------------------------------------------------------------------------
# In-memory cache for municipality boundaries
# (loaded once per process; restart to refresh after a GeoJSON update)
# ---------------------------------------------------------------------------

_MUNICIPALITY_GEOJSON_CACHE = None  # Optional[dict]


def _load_municipality_geojson() -> dict:
    """
    Load the GeoJSON FeatureCollection from:
      1. The municipalities_geo table (PostGIS ST_AsGeoJSON)
      2. Fallback: data/geo/israel_municipalities.geojson file

    Each Feature includes properties:
        municipality_id, name_he, name_en, region
    """
    global _MUNICIPALITY_GEOJSON_CACHE
    if _MUNICIPALITY_GEOJSON_CACHE is not None:
        return _MUNICIPALITY_GEOJSON_CACHE

    # Try DB first
    try:
        conn = _get_db_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT
                        municipality_id,
                        name_he,
                        name_en,
                        region,
                        ST_AsGeoJSON(geom, 6)::json AS geometry
                    FROM municipalities_geo
                    ORDER BY name_en
                """)
                rows = cur.fetchall()
        finally:
            conn.close()

        if rows:
            features = []
            for row in rows:
                features.append({
                    "type": "Feature",
                    "geometry": row["geometry"],
                    "properties": {
                        "municipality_id": row["municipality_id"],
                        "name_he":         row["name_he"],
                        "name_en":         row["name_en"] or row["name_he"],
                        "region":          row["region"] or "",
                    }
                })
            _MUNICIPALITY_GEOJSON_CACHE = {
                "type": "FeatureCollection",
                "features": features
            }
            log.info(f"Loaded {len(features)} municipality boundaries from DB")
            return _MUNICIPALITY_GEOJSON_CACHE

    except Exception as e:
        log.warning(f"Could not load boundaries from DB: {e} — trying file fallback")

    # File fallback
    if GEOJSON_FALLBACK_PATH.exists():
        with open(GEOJSON_FALLBACK_PATH, encoding="utf-8") as f:
            _MUNICIPALITY_GEOJSON_CACHE = json.load(f)
        n = len(_MUNICIPALITY_GEOJSON_CACHE.get("features", []))
        log.info(f"Loaded {n} municipality boundaries from file fallback")
        return _MUNICIPALITY_GEOJSON_CACHE

    # Nothing available — return empty collection
    log.error("No municipality boundary data available. Run fetch_israel_municipalities.py first.")
    _MUNICIPALITY_GEOJSON_CACHE = {"type": "FeatureCollection", "features": []}
    return _MUNICIPALITY_GEOJSON_CACHE


# ---------------------------------------------------------------------------
# Route 1: Municipality boundaries
# ---------------------------------------------------------------------------

@geo_blueprint.route("/municipalities")
def get_municipalities():
    """
    GET /api/geo/municipalities
    Returns the full GeoJSON FeatureCollection (cached after first load).
    """
    try:
        geojson = _load_municipality_geojson()
        # Set long cache headers — boundaries don't change often
        resp = current_app.response_class(
            response=json.dumps(geojson),
            status=200,
            mimetype="application/json",
        )
        resp.headers["Cache-Control"] = "public, max-age=3600"  # 1h
        return resp
    except Exception as e:
        log.exception("Error serving municipalities GeoJSON")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Route 2: Choropleth KPI data
# ---------------------------------------------------------------------------

@geo_blueprint.route("/choropleth")
def get_choropleth():
    """
    GET /api/geo/choropleth?kpi=revenue&week=all&distributor=all

    Returns:
      {
        "data": {
          "5000": { "revenue": 12500.0, "units": 430, "pos_count": 8 },
          "6200": { "revenue": 3200.0,  "units": 110, "pos_count": 2 },
          ...
        },
        "kpi": "revenue",
        "week": "all",
        "distributor": "all"
      }

    municipality_id is the CBS city code (string).
    """
    kpi         = request.args.get("kpi", "revenue")
    month       = request.args.get("month", "all")
    # Backward compat: accept 'week' param and map to 'month' if month not given
    if month == "all" and request.args.get("week", "all") != "all":
        month = request.args.get("week", "all")
    distributor = request.args.get("distributor", "all")
    brand       = request.args.get("brand", "all")

    # Validate inputs
    if kpi not in ("revenue", "units", "pos_count"):
        return jsonify({"error": "Invalid kpi parameter"}), 400

    try:
        conn = _get_db_conn()
        try:
            result = _query_choropleth(conn, month, distributor, brand)
        finally:
            conn.close()

        return jsonify({
            "data":        result,
            "kpi":         kpi,
            "month":       month,
            "distributor": distributor,
            "brand":       brand,
        })
    except Exception as e:
        log.exception("Error in /api/geo/choropleth")
        return jsonify({"error": str(e)}), 500


# Map frontend distributor filter values → DB key patterns (for LIKE matching)
# "icedream" matches DB key "icedreams" or "icedream"
# "mayyan" matches "mayyan_froz" and "mayyan_amb"
DISTRIBUTOR_KEY_PATTERNS = {
    "icedream": "icedream%",
    "mayyan":   "mayyan%",
    "maayan":   "mayyan%",
    "biscotti": "biscotti%",
}

# Brand → product brand_key in products table
BRAND_KEY_MAP = {
    "turbo": "turbo",
    "danis": "danis",
}


def _build_dist_clause(distributor: str, params: list) -> str:
    """
    Build a distributor filter clause using a DB subquery instead of hardcoded IDs.
    Returns SQL clause and appends to params list.
    """
    if distributor == "all":
        return ""
    pattern = DISTRIBUTOR_KEY_PATTERNS.get(distributor.lower())
    if not pattern:
        return ""
    params.append(pattern)
    return "AND sp.distributor_id IN (SELECT id FROM distributors WHERE key LIKE %s)"


def _build_month_clause(month: str, params: list, table_alias: str = "st") -> str:
    """
    Parse a month param like '2026-01' into year/month WHERE clause.
    Returns the SQL clause string and appends to params list.
    """
    if month == "all":
        # Default to current year so GEO matches BO/CC scope
        params.append(2026)
        return f"AND {table_alias}.year >= %s"
    try:
        parts = month.split("-")
        year = int(parts[0])
        mon = int(parts[1])
        params.append(year)
        params.append(mon)
        return f"AND {table_alias}.year = %s AND {table_alias}.month = %s"
    except (ValueError, IndexError):
        # Backward compat: try week_label format (W1, W2, ...)
        if month.startswith("W"):
            params.append(month)
            return f"AND {table_alias}.week_label = %s"
        return ""


def _build_brand_clause(brand: str, params: list) -> str:
    """
    Build a product brand filter clause via JOIN to products table.
    Returns SQL clause for WHERE on st (sales_transactions).
    """
    if brand == "all":
        return ""
    brand_key = BRAND_KEY_MAP.get(brand.lower())
    if not brand_key:
        return ""
    params.append(brand_key)
    return "AND p.brand_key = %s"


def _query_choropleth(conn, month: str, distributor: str, brand: str = "all") -> dict:
    """
    Aggregate sales by municipality from sales_transactions + sale_points.

    Returns: { municipality_id: { revenue, units, pos_count } }
    """
    # Build clauses — params must be appended in SQL placeholder order:
    #   1. dist_clause  (in sale_points JOIN)
    #   2. month_clause (in sales_transactions JOIN)
    #   3. brand_clause (in products JOIN)
    params = []
    dist_clause = _build_dist_clause(distributor, params)

    month_clause = _build_month_clause(month, params)

    brand_join = ""
    brand_clause = ""
    if brand != "all":
        brand_clause = _build_brand_clause(brand, params)
        if brand_clause:
            brand_join = "LEFT JOIN products p ON p.id = st.product_id"

    sql = f"""
        SELECT
            mg.municipality_id,
            COALESCE(SUM(st.revenue_ils), 0)::float   AS revenue,
            COALESCE(SUM(st.units_sold),  0)::int      AS units,
            COUNT(DISTINCT st.sale_point_id)::int      AS pos_count
        FROM municipalities_geo mg
        LEFT JOIN sale_points sp
            ON sp.latitude IS NOT NULL
            AND (
                -- Spatial match (preferred if geo_point is populated)
                (sp.geo_point IS NOT NULL AND ST_Within(sp.geo_point, mg.geom))
                OR
                -- Name fallback: geo_municipality (Hebrew from Google) vs name_he/name_en
                (sp.geo_point IS NULL AND (
                    sp.geo_municipality = mg.name_he
                    OR sp.geo_municipality = mg.name_en
                ))
            )
            {dist_clause}
        LEFT JOIN sales_transactions st
            ON st.sale_point_id = sp.id
            {month_clause}
        {brand_join}
            {brand_clause}
        GROUP BY mg.municipality_id
    """

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return {
        row["municipality_id"]: {
            "revenue":   round(row["revenue"], 2),
            "units":     row["units"],
            "pos_count": row["pos_count"],
        }
        for row in rows
    }


# ---------------------------------------------------------------------------
# Route 3: POS drill-down
# ---------------------------------------------------------------------------

@geo_blueprint.route("/pos")
def get_pos():
    """
    GET /api/geo/pos?municipality_id=5000&week=all&distributor=all

    Returns:
      {
        "data": [
          {
            "pos_id": 101,
            "pos_name": "SuperPharm Tel Aviv",
            "latitude": 32.0853,
            "longitude": 34.7818,
            "distributor": "icedream",
            "revenue_ils": 4200.0,
            "units_sold": 140
          },
          ...
        ],
        "municipality_id": "5000",
        "week": "all"
      }
    """
    municipality_id = request.args.get("municipality_id")
    month           = request.args.get("month", "all")
    # Backward compat
    if month == "all" and request.args.get("week", "all") != "all":
        month = request.args.get("week", "all")
    distributor     = request.args.get("distributor", "all")
    brand           = request.args.get("brand", "all")
    layer           = request.args.get("layer", "district")

    if not municipality_id:
        return jsonify({"error": "municipality_id is required"}), 400

    try:
        conn = _get_db_conn()
        try:
            rows = _query_pos(conn, municipality_id, month, distributor, brand, layer=layer)
        finally:
            conn.close()

        return jsonify({
            "data":            rows,
            "municipality_id": municipality_id,
            "month":           month,
            "distributor":     distributor,
            "brand":           brand,
        })
    except Exception as e:
        log.exception("Error in /api/geo/pos")
        return jsonify({"error": str(e)}), 500


def _query_pos(conn, municipality_id: str, month: str, distributor: str,
               brand: str = "all", layer: str = "district") -> list:
    """
    Return POS rows within the given municipality/city with aggregated sales.
    Uses ST_Within for spatial accuracy (falls back to name match if PostGIS
    geo_point is not populated).

    layer='district' → lookup in municipalities_geo (default)
    layer='city'     → lookup in cities_geo
    """
    # Build clauses — params must be appended in SQL placeholder order:
    #   1. month_clause (in sales_transactions JOIN)
    #   2. brand_clause (in products JOIN)
    #   3. dist_clause  (in WHERE)
    #   4. municipality_id (×3, at the end)
    params = []
    month_clause = _build_month_clause(month, params)

    brand_join = ""
    brand_clause = ""
    if brand != "all":
        brand_clause = _build_brand_clause(brand, params)
        if brand_clause:
            brand_join = "LEFT JOIN products p ON p.id = st.product_id"

    dist_clause = _build_dist_clause(distributor, params)

    # Choose the right geo table and ID column based on layer
    if layer == "city":
        geo_table = "cities_geo"
        geo_id_col = "city_id"
    else:
        geo_table = "municipalities_geo"
        geo_id_col = "municipality_id"

    # municipality_id params go at the end (3 occurrences)
    sql = f"""
        SELECT
            sp.id              AS pos_id,
            sp.branch_name_he  AS pos_name,
            sp.latitude,
            sp.longitude,
            sp.distributor_id,
            d.key              AS distributor_key,
            sp.address_city,
            sp.address_street,
            sp.geo_municipality,
            COALESCE(SUM(st.revenue_ils), 0)::float  AS revenue_ils,
            COALESCE(SUM(st.units_sold),  0)::int     AS units_sold
        FROM sale_points sp
        LEFT JOIN distributors d ON d.id = sp.distributor_id
        LEFT JOIN sales_transactions st
            ON st.sale_point_id = sp.id
            {month_clause}
        {brand_join}
            {brand_clause}
        WHERE sp.geo_status = 'OK'
          AND sp.latitude IS NOT NULL
          {dist_clause}
          AND (
            -- Spatial containment (preferred)
            (sp.geo_point IS NOT NULL AND ST_Within(
                sp.geo_point,
                (SELECT geom FROM {geo_table} WHERE {geo_id_col} = %s)
            ))
            OR
            -- Name-based fallback: check both name_he and name_en
            sp.geo_municipality IN (
                SELECT name_he FROM {geo_table} WHERE {geo_id_col} = %s
                UNION
                SELECT name_en FROM {geo_table} WHERE {geo_id_col} = %s
            )
          )
        GROUP BY sp.id, sp.branch_name_he, sp.latitude, sp.longitude, sp.distributor_id,
                 d.key, sp.address_city, sp.address_street, sp.geo_municipality
        ORDER BY revenue_ils DESC
    """
    # Append municipality_id three times (ST_Within, name_he fallback, name_en fallback)
    params.extend([municipality_id, municipality_id, municipality_id])

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    # Map distributor keys to frontend labels
    _DIST_KEY_LABEL = {
        "icedream": "icedream", "icedreams": "icedream",
        "mayyan_froz": "mayyan", "mayyan_amb": "mayyan",
        "biscotti": "biscotti", "karfree": "karfree",
    }

    return [
        {
            "pos_id":          row["pos_id"],
            "pos_name":        row["pos_name"],
            "latitude":        float(row["latitude"]),
            "longitude":       float(row["longitude"]),
            "distributor":     _DIST_KEY_LABEL.get(row["distributor_key"] or "", row["distributor_key"] or "unknown"),
            "address_city":    row["address_city"] or "",
            "address_street":  row["address_street"] or "",
            "geo_municipality": row["geo_municipality"] or "",
            "revenue_ils":     round(row["revenue_ils"], 2),
            "units_sold":      row["units_sold"],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Route 1b: City boundaries (ADM2 — individual city/town polygons)
# ---------------------------------------------------------------------------

_CITY_GEOJSON_CACHE = None  # Optional[dict]
_city_load_error = None      # str | None — last load exception (for diagnostics)


@geo_blueprint.route("/cities")
def get_cities():
    """
    GET /api/geo/cities
    Returns city-level boundary GeoJSON (cached after first load).
    Used by the 'City' layer toggle in the GEO tab.
    """
    try:
        geojson = _load_city_geojson()
        if not geojson.get("features"):
            return jsonify({"type": "FeatureCollection", "features": [],
                            "_note": "No city boundaries loaded. Run fetch_city_boundaries.py."}), 200

        payload = json.dumps(geojson)
        log.info(f"cities GeoJSON payload: {len(payload)} bytes, {len(geojson['features'])} features")
        resp = current_app.response_class(
            response=payload,
            status=200,
            mimetype="application/json",
        )
        # Short cache — avoid stale empty responses
        resp.headers["Cache-Control"] = "public, max-age=300"
        return resp
    except Exception as e:
        log.exception("Error serving cities GeoJSON")
        return jsonify({"error": str(e)}), 500


def _load_city_geojson() -> dict:
    """Load city boundaries from cities_geo table. Caches only non-empty results."""
    global _CITY_GEOJSON_CACHE
    if _CITY_GEOJSON_CACHE is not None and len(_CITY_GEOJSON_CACHE.get("features", [])) > 0:
        return _CITY_GEOJSON_CACHE

    try:
        conn = _get_db_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # Simplify geometry to reduce payload size (~30MB raw → ~3MB simplified)
                # Tolerance 0.001 ≈ ~100m at Israel latitudes — visually fine for dashboard zoom
                cur.execute("""
                    SELECT
                        city_id,
                        name_he,
                        name_en,
                        muni_id,
                        district_id,
                        ST_AsGeoJSON(ST_Simplify(geom, 0.001), 5) AS geometry_text
                    FROM cities_geo
                    WHERE geom IS NOT NULL
                    ORDER BY name_he
                """)
                rows = cur.fetchall()
        finally:
            conn.close()

        log.info(f"cities_geo query returned {len(rows)} rows")

        if rows:
            features = []
            for row in rows:
                geom_text = row["geometry_text"]
                if not geom_text:
                    continue
                try:
                    geom_obj = json.loads(geom_text)
                except (json.JSONDecodeError, TypeError):
                    continue
                features.append({
                    "type": "Feature",
                    "geometry": geom_obj,
                    "properties": {
                        "city_id":         row["city_id"],
                        "municipality_id": row["muni_id"] or str(row["city_id"]),
                        "name_he":         row["name_he"],
                        "name_en":         row["name_en"] or row["name_he"],
                        "district_id":     row["district_id"] or "",
                    }
                })
            _CITY_GEOJSON_CACHE = {
                "type": "FeatureCollection",
                "features": features
            }
            log.info(f"Loaded {len(features)} city boundaries from DB")
            return _CITY_GEOJSON_CACHE
        else:
            log.warning("cities_geo ST_AsGeoJSON query returned 0 rows")

    except Exception as e:
        log.warning(f"Could not load city boundaries from DB: {e}")
        # Store error for debug endpoint
        global _city_load_error
        _city_load_error = str(e)

    return {"type": "FeatureCollection", "features": []}


# Choropleth for city layer — aggregate by city_id instead of municipality_id
@geo_blueprint.route("/choropleth-city")
def get_choropleth_city():
    """
    GET /api/geo/choropleth-city?kpi=revenue&month=all&distributor=all&brand=all

    Same as /choropleth but grouped by city (cities_geo) instead of district.
    """
    kpi         = request.args.get("kpi", "revenue")
    month       = request.args.get("month", "all")
    distributor = request.args.get("distributor", "all")
    brand       = request.args.get("brand", "all")

    if kpi not in ("revenue", "units", "pos_count"):
        return jsonify({"error": "Invalid kpi parameter"}), 400

    try:
        conn = _get_db_conn()
        try:
            result = _query_choropleth_city(conn, month, distributor, brand)
        finally:
            conn.close()

        return jsonify({
            "data":        result,
            "kpi":         kpi,
            "month":       month,
            "distributor": distributor,
            "brand":       brand,
        })
    except Exception as e:
        log.exception("Error in /api/geo/choropleth-city")
        return jsonify({"error": str(e)}), 500


def _query_choropleth_city(conn, month: str, distributor: str, brand: str = "all") -> dict:
    """
    Aggregate sales by city from sales_transactions + sale_points + cities_geo.
    Uses ST_Within to match POS to city polygons.
    Returns: { city_id: { revenue, units, pos_count } }
    """
    params = []
    dist_clause = _build_dist_clause(distributor, params)

    month_clause = _build_month_clause(month, params)

    brand_join = ""
    brand_clause = ""
    if brand != "all":
        brand_clause = _build_brand_clause(brand, params)
        if brand_clause:
            brand_join = "LEFT JOIN products p ON p.id = st.product_id"

    sql = f"""
        SELECT
            cg.city_id,
            COALESCE(SUM(st.revenue_ils), 0)::float   AS revenue,
            COALESCE(SUM(st.units_sold),  0)::int      AS units,
            COUNT(DISTINCT st.sale_point_id)::int      AS pos_count
        FROM cities_geo cg
        LEFT JOIN sale_points sp
            ON sp.latitude IS NOT NULL
            AND (
                (sp.geo_point IS NOT NULL AND ST_Within(sp.geo_point, cg.geom))
                OR
                (sp.geo_point IS NULL AND (
                    sp.geo_municipality = cg.name_he
                    OR sp.geo_municipality = cg.name_en
                ))
            )
            {dist_clause}
        LEFT JOIN sales_transactions st
            ON st.sale_point_id = sp.id
            {month_clause}
        {brand_join}
            {brand_clause}
        GROUP BY cg.city_id
    """

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return {
        row["city_id"]: {
            "revenue":   round(row["revenue"], 2),
            "units":     row["units"],
            "pos_count": row["pos_count"],
        }
        for row in rows
    }


# ---------------------------------------------------------------------------
# Route 4: Export POS addresses
# ---------------------------------------------------------------------------

@geo_blueprint.route("/export-addresses")
def export_addresses():
    """
    GET /api/geo/export-addresses?filter=all|missing&month=all&distributor=all&brand=all

    Returns all POS with address info for CSV export.
    filter=missing → only POS where address_city or address_street is empty.
    """
    filt = request.args.get("filter", "all")
    month = request.args.get("month", "all")
    distributor = request.args.get("distributor", "all")
    brand = request.args.get("brand", "all")

    params = []

    # Build optional clauses
    dist_clause = _build_dist_clause(distributor, params)

    missing_clause = ""
    if filt == "missing":
        missing_clause = "AND (sp.address_city IS NULL OR sp.address_city = '' OR sp.address_street IS NULL OR sp.address_street = '')"

    sql = f"""
        SELECT
            sp.id              AS pos_id,
            sp.branch_name_he  AS pos_name,
            sp.address_city,
            sp.address_street,
            sp.distributor_id
        FROM sale_points sp
        WHERE sp.geo_status = 'OK'
          {dist_clause}
          {missing_clause}
        ORDER BY sp.branch_name_he
    """

    try:
        conn = _get_db_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        finally:
            conn.close()

        data = [
            {
                "pos_id":         row["pos_id"],
                "pos_name":       row["pos_name"] or "",
                "address_city":   row["address_city"] or "",
                "address_street": row["address_street"] or "",
            }
            for row in rows
        ]

        return jsonify({"data": data, "count": len(data)})

    except Exception as e:
        log.exception("Error in /api/geo/export-addresses")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Route 5: Update POS address (inline editing)
# ---------------------------------------------------------------------------

@geo_blueprint.route("/update-pos", methods=["POST"])
def update_pos():
    """
    POST /api/geo/update-pos
    Body (JSON):
      {
        "pos_id": 101,
        "address_city": "תל אביב",
        "address_street": "דיזנגוף 99"
      }

    Updates address_city and/or address_street on the sale_points row.
    Returns: { "ok": true } or { "error": "..." }
    """
    data = request.get_json(silent=True)
    if not data or "pos_id" not in data:
        return jsonify({"error": "pos_id is required"}), 400

    pos_id = data["pos_id"]
    new_city = data.get("address_city")
    new_street = data.get("address_street")

    if new_city is None and new_street is None:
        return jsonify({"error": "Nothing to update — send address_city and/or address_street"}), 400

    # Build dynamic SET clause
    set_parts = []
    params = []
    if new_city is not None:
        set_parts.append("address_city = %s")
        params.append(new_city.strip())
    if new_street is not None:
        set_parts.append("address_street = %s")
        params.append(new_street.strip())

    params.append(pos_id)

    sql = f"UPDATE sale_points SET {', '.join(set_parts)} WHERE id = %s"

    try:
        conn = _get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if cur.rowcount == 0:
                    conn.rollback()
                    return jsonify({"error": f"No sale_point found with id={pos_id}"}), 404
                conn.commit()
        finally:
            conn.close()

        log.info(f"Updated sale_point {pos_id}: city={new_city}, street={new_street}")
        return jsonify({"ok": True})

    except Exception as e:
        log.exception(f"Error updating sale_point {pos_id}")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Route 6: Upload POS addresses (bulk CSV)
# ---------------------------------------------------------------------------

@geo_blueprint.route("/upload-addresses", methods=["POST"])
def upload_addresses():
    """
    POST /api/geo/upload-addresses
    Multipart form: file (CSV), geocode ('true'/'false')

    CSV columns: pos_id, pos_name, address_city, address_street
    Updates address_city and address_street for each pos_id.
    Optionally triggers re-geocoding for changed addresses.

    Returns: { updated, skipped, errors, geocoded }
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    do_geocode = request.form.get("geocode", "false") == "true"

    try:
        # Read CSV — handle BOM
        raw = f.read()
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        # Validate columns
        required = {"pos_id", "address_city", "address_street"}
        if not required.issubset(set(reader.fieldnames or [])):
            return jsonify({
                "error": f"CSV must have columns: {', '.join(sorted(required))}. "
                         f"Found: {', '.join(reader.fieldnames or [])}"
            }), 400

        rows = list(reader)
        if not rows:
            return jsonify({"error": "CSV is empty"}), 400

    except Exception as e:
        return jsonify({"error": f"Could not parse CSV: {e}"}), 400

    updated = 0
    skipped = 0
    errors = 0
    changed_ids = []

    try:
        conn = _get_db_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                for row in rows:
                    try:
                        pos_id = int(row["pos_id"])
                    except (ValueError, TypeError):
                        errors += 1
                        continue

                    new_city = (row.get("address_city") or "").strip()
                    new_street = (row.get("address_street") or "").strip()

                    # Check current values to detect changes
                    cur.execute(
                        "SELECT address_city, address_street FROM sale_points WHERE id = %s",
                        (pos_id,)
                    )
                    existing = cur.fetchone()
                    if not existing:
                        errors += 1
                        continue

                    old_city = (existing["address_city"] or "").strip()
                    old_street = (existing["address_street"] or "").strip()

                    if new_city == old_city and new_street == old_street:
                        skipped += 1
                        continue

                    cur.execute(
                        "UPDATE sale_points SET address_city = %s, address_street = %s WHERE id = %s",
                        (new_city, new_street, pos_id)
                    )
                    updated += 1
                    changed_ids.append(pos_id)

                conn.commit()
        finally:
            conn.close()

    except Exception as e:
        log.exception("Error in bulk address update")
        return jsonify({"error": f"Database error: {e}"}), 500

    # Optionally re-geocode changed addresses
    geocoded = None
    if do_geocode and changed_ids:
        geocoded = _geocode_pos_ids(changed_ids)

    log.info(
        f"Address upload: {updated} updated, {skipped} skipped, "
        f"{errors} errors, {geocoded} geocoded"
    )

    return jsonify({
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "geocoded": geocoded,
        "total_rows": len(rows),
    })


def _geocode_pos_ids(pos_ids: list) -> int:
    """
    Re-geocode the given sale_point IDs using the geocoding pipeline.
    Returns count of successfully geocoded POS.
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from geocoding_pipeline import geocode_address

        api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
        if not api_key:
            log.warning("No GOOGLE_MAPS_API_KEY — skipping geocoding")
            return 0

        conn = _get_db_conn()
        geocoded = 0
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                for pos_id in pos_ids:
                    cur.execute(
                        "SELECT address_city, address_street, branch_name_he "
                        "FROM sale_points WHERE id = %s",
                        (pos_id,)
                    )
                    row = cur.fetchone()
                    if not row:
                        continue

                    city = row["address_city"] or ""
                    street = row["address_street"] or ""
                    name = row["branch_name_he"] or ""

                    # Build address string
                    address = f"{street}, {city}, Israel" if street and city else \
                              f"{city}, Israel" if city else \
                              f"{name}, Israel"

                    try:
                        result = geocode_address(api_key, address)
                        if result and result.get("status") == "OK" and result.get("lat") and result.get("lng"):
                            cur.execute("""
                                UPDATE sale_points
                                SET latitude = %s,
                                    longitude = %s,
                                    geo_municipality = %s,
                                    geo_status = 'OK',
                                    geo_point = ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                                WHERE id = %s
                            """, (
                                result["lat"], result["lng"],
                                result.get("municipality_he", ""),
                                result["lng"], result["lat"],
                                pos_id
                            ))
                            geocoded += 1
                    except Exception as e:
                        log.warning(f"Geocoding failed for POS {pos_id}: {e}")
                        continue

                conn.commit()
        finally:
            conn.close()

        return geocoded

    except ImportError as e:
        log.warning(f"geocoding_pipeline not available: {e}")
        return 0
    except Exception as e:
        log.exception("Error during re-geocoding")
        return 0


# ---------------------------------------------------------------------------
# Route: Stock deployment by geography
# ---------------------------------------------------------------------------

@geo_blueprint.route("/stock")
def get_stock():
    """
    GET /api/geo/stock?layer=district&month=all&distributor=all&brand=all

    Returns units sold TO each sale point, aggregated by district or city.
    This represents the B2B stock deployed to the field.

    Returns:
      {
        "data": {
          "<geo_id>": {
            "name": "Tel Aviv",
            "name_he": "תל אביב",
            "pos_total": 347,
            "pos_stocked": 280,
            "units": 52000,
            "revenue": 929504,
            "products": { "turbo_chocolate": 12000, ... }
          }
        }
      }
    """
    layer       = request.args.get("layer", "district")
    month       = request.args.get("month", "all")
    distributor = request.args.get("distributor", "all")
    brand       = request.args.get("brand", "all")

    try:
        conn = _get_db_conn()
        try:
            result = _query_stock(conn, layer, month, distributor, brand)
        finally:
            conn.close()

        return jsonify({
            "data":        result,
            "layer":       layer,
            "month":       month,
            "distributor": distributor,
            "brand":       brand,
        })
    except Exception as e:
        log.exception("Error in /api/geo/stock")
        return jsonify({"error": str(e)}), 500


def _query_stock(conn, layer: str, month: str, distributor: str, brand: str) -> dict:
    """
    Aggregate B2B stock (units sold to POS) by district or city.
    Includes per-product breakdown and stocked-vs-total POS counts.
    """
    if layer == "city":
        geo_table = "cities_geo"
        geo_id = "cg.city_id"
        geo_name = "cg.name_en"
        geo_name_he = "cg.name_he"
        spatial = "(sp.geo_point IS NOT NULL AND ST_Within(sp.geo_point, cg.geom)) OR (sp.geo_point IS NULL AND (sp.geo_municipality = cg.name_he OR sp.geo_municipality = cg.name_en))"
    else:
        geo_table = "municipalities_geo"
        geo_id = "mg.municipality_id"
        geo_name = "mg.name_en"
        geo_name_he = "mg.name_he"
        spatial = "(sp.geo_point IS NOT NULL AND ST_Within(sp.geo_point, mg.geom)) OR (sp.geo_point IS NULL AND (sp.geo_municipality = mg.name_he OR sp.geo_municipality = mg.name_en))"

    alias = "cg" if layer == "city" else "mg"

    params = []
    dist_clause = _build_dist_clause(distributor, params)
    month_clause = _build_month_clause(month, params)

    brand_join = ""
    brand_clause = ""
    if brand != "all":
        brand_clause = _build_brand_clause(brand, params)
        if brand_clause:
            brand_join = "LEFT JOIN products p ON p.id = st.product_id"

    # Main aggregation
    sql = f"""
        SELECT
            {geo_id}                                      AS geo_id,
            {geo_name}                                    AS name,
            {geo_name_he}                                 AS name_he,
            COUNT(DISTINCT sp.id)::int                    AS pos_total,
            COUNT(DISTINCT CASE WHEN st.id IS NOT NULL THEN sp.id END)::int AS pos_stocked,
            COALESCE(SUM(st.units_sold), 0)::int          AS units,
            COALESCE(SUM(st.revenue_ils), 0)::float       AS revenue
        FROM {geo_table} {alias}
        LEFT JOIN sale_points sp
            ON sp.latitude IS NOT NULL
            AND ({spatial})
            {dist_clause}
        LEFT JOIN sales_transactions st
            ON st.sale_point_id = sp.id
            {month_clause}
        {brand_join}
            {brand_clause}
        GROUP BY {geo_id}, {geo_name}, {geo_name_he}
        ORDER BY units DESC
    """

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    result = {}
    for row in rows:
        gid = row["geo_id"]
        result[gid] = {
            "name":        row["name"] or row["name_he"],
            "name_he":     row["name_he"],
            "pos_total":   row["pos_total"],
            "pos_stocked": row["pos_stocked"],
            "units":       row["units"],
            "revenue":     round(row["revenue"], 2),
        }

    return result


# ---------------------------------------------------------------------------
# Route: Demand trend + repeat purchases by geography
# ---------------------------------------------------------------------------

@geo_blueprint.route("/demand-trend")
def get_demand_trend():
    """
    GET /api/geo/demand-trend?layer=district&geo_id=all&distributor=all&brand=all

    Returns monthly demand time series + repeat purchase metrics per geography.

    Returns:
      {
        "monthly": [
          { "year": 2026, "month": 1, "label": "Jan 26",
            "data": { "<geo_id>": { "units": 1200, "revenue": 18000, "active_pos": 45 } }
          }, ...
        ],
        "repeat": {
          "<geo_id>": {
            "name": "Tel Aviv",
            "total_pos": 347,
            "multi_month_pos": 210,
            "multi_month_pct": 60.5,
            "consecutive_pos": 180,
            "consecutive_pct": 51.9,
            "avg_active_months": 3.2,
            "total_months": 5
          }
        }
      }
    """
    layer       = request.args.get("layer", "district")
    geo_id      = request.args.get("geo_id", "all")
    distributor = request.args.get("distributor", "all")
    brand       = request.args.get("brand", "all")

    try:
        conn = _get_db_conn()
        try:
            monthly = _query_demand_monthly(conn, layer, distributor, brand, geo_id)
            repeat  = _query_repeat_purchases(conn, layer, distributor, brand, geo_id)
        finally:
            conn.close()

        return jsonify({
            "monthly": monthly,
            "repeat":  repeat,
            "layer":   layer,
            "geo_id":  geo_id,
            "distributor": distributor,
            "brand":   brand,
        })
    except Exception as e:
        log.exception("Error in /api/geo/demand-trend")
        return jsonify({"error": str(e)}), 500


def _geo_join_fragment(layer: str):
    """Return (table, alias, id_col, name_col, name_he_col, spatial_clause) for district or city."""
    if layer == "city":
        return ("cities_geo", "cg", "cg.city_id", "cg.name_en", "cg.name_he",
                "(sp.geo_point IS NOT NULL AND ST_Within(sp.geo_point, cg.geom)) OR "
                "(sp.geo_point IS NULL AND (sp.geo_municipality = cg.name_he OR sp.geo_municipality = cg.name_en))")
    return ("municipalities_geo", "mg", "mg.municipality_id", "mg.name_en", "mg.name_he",
            "(sp.geo_point IS NOT NULL AND ST_Within(sp.geo_point, mg.geom)) OR "
            "(sp.geo_point IS NULL AND (sp.geo_municipality = mg.name_he OR sp.geo_municipality = mg.name_en))")


def _query_demand_monthly(conn, layer: str, distributor: str, brand: str, geo_id: str) -> list:
    """Monthly units/revenue/active_pos by geography."""
    geo_table, alias, id_col, name_col, name_he_col, spatial = _geo_join_fragment(layer)

    params = []
    dist_clause = _build_dist_clause(distributor, params)
    brand_join = ""
    brand_clause = ""
    if brand != "all":
        brand_clause = _build_brand_clause(brand, params)
        if brand_clause:
            brand_join = "LEFT JOIN products p ON p.id = st.product_id"

    geo_filter = ""
    if geo_id != "all":
        params.append(geo_id)
        geo_filter = f"AND {id_col} = %s"

    sql = f"""
        SELECT
            st.year,
            st.month,
            {id_col}                                     AS geo_id,
            COALESCE(SUM(st.units_sold), 0)::int         AS units,
            COALESCE(SUM(st.revenue_ils), 0)::float      AS revenue,
            COUNT(DISTINCT st.sale_point_id)::int         AS active_pos
        FROM {geo_table} {alias}
        INNER JOIN sale_points sp
            ON sp.latitude IS NOT NULL
            AND ({spatial})
            {dist_clause}
        INNER JOIN sales_transactions st
            ON st.sale_point_id = sp.id
        {brand_join}
            {brand_clause}
        WHERE 1=1 {geo_filter}
        GROUP BY st.year, st.month, {id_col}
        ORDER BY st.year, st.month
    """

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # Group by (year, month)
    months_data = {}
    for row in rows:
        key = (row["year"], row["month"])
        if key not in months_data:
            yr_short = str(row["year"])[-2:]
            months_data[key] = {
                "year": row["year"],
                "month": row["month"],
                "label": f"{month_names[row['month']]} '{yr_short}",
                "data": {}
            }
        months_data[key]["data"][row["geo_id"]] = {
            "units":      row["units"],
            "revenue":    round(row["revenue"], 2),
            "active_pos": row["active_pos"],
        }

    return [months_data[k] for k in sorted(months_data.keys())]


def _query_repeat_purchases(conn, layer: str, distributor: str, brand: str, geo_id: str) -> dict:
    """
    Per geography: total POS, multi-month POS (2+), consecutive-month POS,
    average active months per POS.
    """
    geo_table, alias, id_col, name_col, name_he_col, spatial = _geo_join_fragment(layer)

    params = []
    dist_clause = _build_dist_clause(distributor, params)
    brand_join = ""
    brand_clause = ""
    if brand != "all":
        brand_clause = _build_brand_clause(brand, params)
        if brand_clause:
            brand_join = "LEFT JOIN products p ON p.id = st.product_id"

    geo_filter = ""
    if geo_id != "all":
        params.append(geo_id)
        geo_filter = f"AND {id_col} = %s"

    # Step 1: Get per-POS monthly activity per geo area
    sql = f"""
        WITH pos_months AS (
            SELECT
                {id_col}              AS geo_id,
                {name_col}            AS name,
                {name_he_col}         AS name_he,
                st.sale_point_id,
                st.year,
                st.month,
                (st.year * 100 + st.month) AS ym
            FROM {geo_table} {alias}
            INNER JOIN sale_points sp
                ON sp.latitude IS NOT NULL
                AND ({spatial})
                {dist_clause}
            INNER JOIN sales_transactions st
                ON st.sale_point_id = sp.id
            {brand_join}
                {brand_clause}
            WHERE st.sale_point_id IS NOT NULL
                  {geo_filter}
            GROUP BY {id_col}, {name_col}, {name_he_col},
                     st.sale_point_id, st.year, st.month
        ),
        pos_stats AS (
            SELECT
                geo_id,
                name,
                name_he,
                sale_point_id,
                COUNT(*)::int                               AS active_months,
                ARRAY_AGG(ym ORDER BY ym)                   AS ym_list
            FROM pos_months
            GROUP BY geo_id, name, name_he, sale_point_id
        ),
        total_months AS (
            SELECT COUNT(DISTINCT ym)::int AS total
            FROM pos_months
        )
        SELECT
            ps.geo_id,
            ps.name,
            ps.name_he,
            COUNT(*)::int                                               AS total_pos,
            COUNT(*) FILTER (WHERE ps.active_months >= 2)::int          AS multi_month_pos,
            SUM(ps.active_months)::float / NULLIF(COUNT(*), 0)         AS avg_active_months,
            ps.ym_list,
            ps.sale_point_id,
            ps.active_months,
            tm.total                                                    AS total_months
        FROM pos_stats ps
        CROSS JOIN total_months tm
        GROUP BY ps.geo_id, ps.name, ps.name_he, ps.ym_list,
                 ps.sale_point_id, ps.active_months, tm.total
    """

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    # Post-process: aggregate per geo_id and compute consecutive months
    geo_agg = {}
    for row in rows:
        gid = row["geo_id"]
        if gid not in geo_agg:
            geo_agg[gid] = {
                "name": row["name"] or row["name_he"],
                "name_he": row["name_he"],
                "total_pos": 0,
                "multi_month_pos": 0,
                "consecutive_pos": 0,
                "total_active_months": 0,
                "total_months": row["total_months"],
            }
        agg = geo_agg[gid]
        agg["total_pos"] += 1
        agg["total_active_months"] += row["active_months"]
        if row["active_months"] >= 2:
            agg["multi_month_pos"] += 1

        # Check for consecutive months
        ym_list = row["ym_list"]
        if ym_list and len(ym_list) >= 2:
            has_consec = False
            for i in range(len(ym_list) - 1):
                y1, m1 = divmod(ym_list[i], 100)
                y2, m2 = divmod(ym_list[i + 1], 100)
                # Next month check
                if (y1 == y2 and m2 == m1 + 1) or (m1 == 12 and m2 == 1 and y2 == y1 + 1):
                    has_consec = True
                    break
            if has_consec:
                agg["consecutive_pos"] += 1

    # Compute percentages
    result = {}
    for gid, agg in geo_agg.items():
        tp = agg["total_pos"]
        result[gid] = {
            "name":              agg["name"],
            "name_he":           agg["name_he"],
            "total_pos":         tp,
            "multi_month_pos":   agg["multi_month_pos"],
            "multi_month_pct":   round(agg["multi_month_pos"] / tp * 100, 1) if tp > 0 else 0,
            "consecutive_pos":   agg["consecutive_pos"],
            "consecutive_pct":   round(agg["consecutive_pos"] / tp * 100, 1) if tp > 0 else 0,
            "avg_active_months": round(agg["total_active_months"] / tp, 1) if tp > 0 else 0,
            "total_months":      agg["total_months"],
        }

    return result


# ---------------------------------------------------------------------------
# Optional: invalidate the in-memory boundary cache (call after re-importing GeoJSON)
# ---------------------------------------------------------------------------

def invalidate_boundary_cache():
    """Call this after running fetch_israel_municipalities.py to force a reload."""
    global _MUNICIPALITY_GEOJSON_CACHE, _CITY_GEOJSON_CACHE
    _MUNICIPALITY_GEOJSON_CACHE = None
    _CITY_GEOJSON_CACHE = None
    log.info("Municipality + city boundary caches invalidated")
