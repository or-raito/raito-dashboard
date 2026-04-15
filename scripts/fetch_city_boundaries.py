#!/usr/bin/env python3
"""
Fetch Israeli city/municipality boundary polygons and load into cities_geo table.

Usage (from your Mac):
    cd /Users/osadon/dataset/scripts
    python3 fetch_city_boundaries.py

Data source: https://github.com/idoivri/israel-municipalities-polygons
This provides ~255 municipal boundary polygons for Israeli cities/towns.

The script:
  1. Downloads the GeoJSON from GitHub
  2. Creates the cities_geo table (if not exists)
  3. Inserts each municipality as a row with PostGIS geometry
"""

import json
import os
import sys
import urllib.request

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("psycopg2 not found. Run: pip install psycopg2-binary")
    sys.exit(1)

# --- Config ---
GEOJSON_URL = "https://raw.githubusercontent.com/idoivri/israel-municipalities-polygons/master/municipalities.geojson"
LOCAL_CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "geo", "israel_cities.geojson")


def get_db_conn():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        cloud_sql_instance = os.environ.get(
            "CLOUD_SQL_INSTANCE", "raito-house-of-brands:me-west1:raito-db"
        )
        socket_path = f"/cloudsql/{cloud_sql_instance}"
        if os.path.exists(socket_path):
            database_url = (
                f"postgresql://raito:raito@/{os.environ.get('PGDATABASE', 'raito')}"
                f"?host={socket_path}"
            )
        else:
            database_url = "postgresql://raito:raito@127.0.0.1:5432/raito"

    return psycopg2.connect(database_url)


def download_geojson():
    """Download the GeoJSON file (or use local cache)."""
    # Check local cache first
    if os.path.exists(LOCAL_CACHE):
        print(f"Using cached file: {LOCAL_CACHE}")
        with open(LOCAL_CACHE, encoding="utf-8") as f:
            return json.load(f)

    print(f"Downloading from {GEOJSON_URL}...")
    req = urllib.request.Request(GEOJSON_URL, headers={"User-Agent": "RAITO/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()

    data = json.loads(raw.decode("utf-8"))

    # Cache locally (skip if path not writable, e.g. Cloud Shell)
    try:
        os.makedirs(os.path.dirname(LOCAL_CACHE), exist_ok=True)
        with open(LOCAL_CACHE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        print(f"Cached to {LOCAL_CACHE}")
    except (PermissionError, OSError) as e:
        print(f"  (skip local cache: {e})")

    return data


def create_table(conn):
    """Create the cities_geo table if it doesn't exist."""
    with conn.cursor() as cur:
        # Ensure PostGIS is available
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"  Note: Could not create PostGIS extension ({e}) — assuming it already exists")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS cities_geo (
                city_id     SERIAL PRIMARY KEY,
                name_he     TEXT NOT NULL,
                name_en     TEXT,
                muni_id     TEXT,
                district_id TEXT,
                geom        geometry(MultiPolygon, 4326),
                properties  JSONB
            );

            CREATE INDEX IF NOT EXISTS idx_cities_geo_geom
                ON cities_geo USING GIST (geom);

            CREATE INDEX IF NOT EXISTS idx_cities_geo_name_he
                ON cities_geo (name_he);
        """)
        conn.commit()
    print("Table cities_geo ready.")


def load_features(conn, geojson):
    """Insert GeoJSON features into cities_geo."""
    features = geojson.get("features", [])
    if not features:
        print("No features found in GeoJSON!")
        return

    # Check property keys from first feature
    sample_props = features[0].get("properties", {})
    print(f"Property keys: {list(sample_props.keys())}")
    print(f"Sample: {sample_props}")

    # Clear existing data
    with conn.cursor() as cur:
        cur.execute("TRUNCATE cities_geo RESTART IDENTITY")
    print(f"Loading {len(features)} city boundaries...")

    inserted = 0
    skipped = 0
    with conn.cursor() as cur:
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry")
            if not geom:
                skipped += 1
                continue

            # Extract name — try common property keys
            name_he = (
                props.get("MUN_HEB") or
                props.get("MUNI_HEB") or
                props.get("name") or
                props.get("NAME") or
                props.get("name_he") or
                props.get("HEB_NAME") or
                ""
            )
            name_en = (
                props.get("MUN_ENG") or
                props.get("MUNI_ENG") or
                props.get("name:en") or
                props.get("name_en") or
                props.get("ENG_NAME") or
                ""
            )
            muni_id = str(
                props.get("CBS_CODE") or
                props.get("muni_id") or
                props.get("OBJECTID") or
                props.get("id") or
                ""
            )

            # Ensure geometry is MultiPolygon
            geom_json = json.dumps(geom)

            try:
                cur.execute("""
                    INSERT INTO cities_geo (name_he, name_en, muni_id, properties, geom)
                    VALUES (
                        %s, %s, %s, %s,
                        ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                    )
                """, (name_he, name_en, muni_id, json.dumps(props), geom_json))
                inserted += 1
            except Exception as e:
                print(f"  ⚠ Skipping {name_he or 'unknown'}: {e}")
                conn.rollback()
                skipped += 1
                continue

    conn.commit()
    print(f"Done: {inserted} inserted, {skipped} skipped")

    # Try to link to districts (municipalities_geo)
    _link_districts(conn)


def _link_districts(conn):
    """
    Try to assign district_id by finding which municipalities_geo polygon
    contains each city's centroid.
    """
    try:
        with conn.cursor() as cur:
            # Check if municipalities_geo exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'municipalities_geo'
                )
            """)
            if not cur.fetchone()[0]:
                print("municipalities_geo table not found — skipping district linking")
                return

            cur.execute("""
                UPDATE cities_geo c
                SET district_id = m.municipality_id
                FROM municipalities_geo m
                WHERE ST_Within(ST_Centroid(c.geom), m.geom)
            """)
            linked = cur.rowcount
            conn.commit()
            print(f"Linked {linked} cities to districts via spatial containment")

    except Exception as e:
        print(f"District linking failed (non-fatal): {e}")
        conn.rollback()


def main():
    print("=== Fetch Israeli City Boundaries ===\n")

    # 1. Download
    geojson = download_geojson()
    n = len(geojson.get("features", []))
    print(f"GeoJSON loaded: {n} features\n")

    # 2. Connect to DB
    conn = get_db_conn()
    print("Connected to database\n")

    # 3. Create table
    create_table(conn)

    # 4. Load features
    load_features(conn, geojson)

    conn.close()
    print("\n✓ City boundaries loaded successfully!")
    print("  The GEO tab layer filter will now show 'City' option.")


if __name__ == "__main__":
    main()
