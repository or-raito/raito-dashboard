#!/usr/bin/env python3
"""
RAITO Geo Layer — Israeli Municipality GeoJSON Importer
========================================================

Downloads Israeli municipality boundary GeoJSON and imports it into
the municipalities_geo table in Cloud SQL.

DATA SOURCES (tried in order)
-----------------------------
1. geoBoundaries (www.geoboundaries.org) — ADM2 level for Israel (ISR).
   Two-step: fetch API metadata → follow gjDownloadURL for the GeoJSON.
   Most reliable open-data source with good global coverage.

2. data.gov.il CBS API — official Israeli localities dataset (~255 entries).
   Returns WGS84 polygons for all Israeli localities.

3. Local file — use --from-file to import a manually downloaded GeoJSON.

USAGE
-----
  # Download and import into DB (run once, or after boundary updates)
  python3 fetch_israel_municipalities.py --import

  # Download only, save to file (inspect before importing)
  python3 fetch_israel_municipalities.py --download-only

  # Import from a local file you already have
  python3 fetch_israel_municipalities.py --from-file data/geo/israel_municipalities.geojson

  # List what's currently in the DB
  python3 fetch_israel_municipalities.py --list

NOTES
-----
- After running this, re-run: python3 geocoding_pipeline.py --backfill-en
  to populate the English municipality name on all geocoded POS records.
- After import, restart the Flask app (or call invalidate_boundary_cache())
  so the in-memory GeoJSON cache is refreshed.
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import requests

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: pip install psycopg2-binary --break-system-packages")
    sys.exit(1)

log = logging.getLogger("fetch_municipalities")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR      = Path(__file__).parent.parent
GEO_DIR       = BASE_DIR / "data" / "geo"
DEFAULT_FILE  = GEO_DIR / "israel_municipalities.geojson"
GEO_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# GeoJSON source URLs (tried in order)
# ---------------------------------------------------------------------------
# Option A: geoBoundaries — ADM2 (municipality-level) boundaries for Israel.
# Two-step: fetch API metadata → follow gjDownloadURL to get GeoJSON.
# This is the most reliable open-data source with good coverage.
GEOBOUNDARIES_API = (
    "https://www.geoboundaries.org/api/current/gbOpen/ISR/ADM2/"
)

# Option B: data.gov.il localities dataset (official CBS data, ~255 entries)
# This endpoint returns WGS84 polygons for all Israeli localities.
GOVIL_API = (
    "https://data.gov.il/api/3/action/datastore_search"
    "?resource_id=d04e55d8-9313-4a4c-88d6-8a9f81e5bb79"
    "&limit=500"
)

# Option C: Local fallback (user-provided file)
# Nothing — handled by --from-file flag.


# ---------------------------------------------------------------------------
# DB connection (same pattern as geocoding_pipeline.py)
# ---------------------------------------------------------------------------

def _get_db_conn():
    cloud_sql_instance = os.environ.get(
        "CLOUD_SQL_INSTANCE", "raito-house-of-brands:me-west1:raito-db"
    )
    socket_path = f"/cloudsql/{cloud_sql_instance}"
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        return psycopg2.connect(database_url)
    if Path(socket_path).exists():
        return psycopg2.connect(
            dbname=os.environ.get("PGDATABASE", "raito"),
            user=os.environ.get("PGUSER", "raito_app"),
            password=os.environ.get("PGPASSWORD", ""),
            host=socket_path,
        )
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "127.0.0.1"),
        port=int(os.environ.get("PGPORT", 5432)),
        dbname=os.environ.get("PGDATABASE", "raito"),
        user=os.environ.get("PGUSER", "raito_app"),
        password=os.environ.get("PGPASSWORD", ""),
    )


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def _download_geoboundaries() -> dict:
    """
    Two-step download from geoBoundaries API:
    1. Fetch metadata JSON from the API endpoint
    2. Follow 'gjDownloadURL' to get the actual GeoJSON FeatureCollection
    Returns the parsed GeoJSON dict, or raises on failure.
    """
    log.info(f"Trying geoBoundaries API: {GEOBOUNDARIES_API}")
    meta_resp = requests.get(GEOBOUNDARIES_API, timeout=30)
    meta_resp.raise_for_status()
    meta = meta_resp.json()

    # The API returns a list for some endpoints, a dict for others
    if isinstance(meta, list):
        meta = meta[0] if meta else {}

    gj_url = meta.get("gjDownloadURL") or meta.get("downloadURL")
    if not gj_url:
        raise ValueError(f"No gjDownloadURL in geoBoundaries response. Keys: {list(meta.keys())}")

    log.info(f"  → Downloading GeoJSON from: {gj_url[:80]}…")
    gj_resp = requests.get(gj_url, timeout=60)
    gj_resp.raise_for_status()
    data = gj_resp.json()

    if data.get("type") != "FeatureCollection":
        raise ValueError(f"Unexpected top-level type: {data.get('type')}")

    # geoBoundaries uses 'shapeName' for the name and 'shapeISO' / 'shapeID' for ID.
    # Normalise properties to our schema.
    data = _convert_geoboundaries_to_standard(data)
    return data


def _convert_geoboundaries_to_standard(data: dict) -> dict:
    """
    Normalise geoBoundaries property names to our standard schema:
      municipality_id, name_he, name_en, region
    geoBoundaries ADM2 features typically have:
      shapeName, shapeISO, shapeID, shapeGroup, shapeType
    """
    features = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry")
        if not geom:
            continue

        # shapeID is like "ISR-ADM2-12345" — extract the numeric part as municipality_id
        shape_id = str(props.get("shapeID", ""))
        mun_id = shape_id.split("-")[-1] if shape_id else ""

        # shapeName is usually the English name
        name_en = str(props.get("shapeName", "")).strip()
        # geoBoundaries doesn't carry Hebrew — leave blank, geocoder will fill it
        name_he = str(props.get("shapeName_he", "")).strip() or name_en

        # shapeGroup = country code, shapeType = admin level — not useful as region
        region = str(props.get("ADM1", props.get("shapeGroup", ""))).strip() or None

        # Normalise geometry to MultiPolygon
        if geom.get("type") == "Polygon":
            geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "municipality_id": mun_id,
                "name_he": name_he,
                "name_en": name_en,
                "region": region,
            }
        })

    return {"type": "FeatureCollection", "features": features}


def download_geojson(output_path: Path) -> dict:
    """
    Try each source in order.  Save the raw GeoJSON to output_path and
    return the parsed dict.  Raises RuntimeError if all sources fail.
    """
    errors = []

    # --- Source 1: geoBoundaries (most reliable) ---
    try:
        data = _download_geoboundaries()
        n = len(data.get("features", []))
        if n == 0:
            raise ValueError("geoBoundaries returned 0 features")
        log.info(f"Downloaded {n} municipality features from geoBoundaries")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info(f"Saved to {output_path}")
        return data
    except Exception as e:
        log.warning(f"  ✗ geoBoundaries failed: {e}")
        errors.append(("geoBoundaries", str(e)))
        time.sleep(1)

    # --- Source 2: data.gov.il CBS API ---
    try:
        log.info(f"Trying data.gov.il CBS API: {GOVIL_API[:80]}…")
        resp = requests.get(GOVIL_API, timeout=30)
        resp.raise_for_status()
        raw = resp.json()

        if "result" in raw and "records" in raw["result"]:
            data = _convert_govil_to_geojson(raw)
        else:
            data = raw

        if data.get("type") != "FeatureCollection":
            raise ValueError(f"Unexpected top-level type: {data.get('type')}")

        n = len(data.get("features", []))
        if n == 0:
            raise ValueError("FeatureCollection has no features")

        log.info(f"Downloaded {n} municipality features from data.gov.il")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info(f"Saved to {output_path}")
        return data
    except Exception as e:
        log.warning(f"  ✗ data.gov.il failed: {e}")
        errors.append(("data.gov.il", str(e)))

    raise RuntimeError(
        "All download sources failed:\n"
        + "\n".join(f"  - {name}: {err}" for name, err in errors)
        + "\n\nPlease manually download an Israeli municipalities GeoJSON and use:\n"
        "  python3 fetch_israel_municipalities.py --from-file <path>"
    )


def _convert_govil_to_geojson(govil_response: dict) -> dict:
    """
    Convert the data.gov.il datastore_search response to a GeoJSON FeatureCollection.
    The CBS localities dataset includes semel_yishuv (CBS code), shem_yishuv (name HE),
    and geometry encoded as WKT or GeoJSON strings.
    """
    records = govil_response["result"]["records"]
    features = []
    for rec in records:
        geom_str = rec.get("geometry") or rec.get("geom") or "{}"
        try:
            geom = json.loads(geom_str) if isinstance(geom_str, str) else geom_str
        except Exception:
            continue

        if not geom or not geom.get("type"):
            continue

        # Normalise to MultiPolygon
        if geom["type"] == "Polygon":
            geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "municipality_id": str(rec.get("semel_yishuv", rec.get("SEMEL", ""))),
                "name_he":         str(rec.get("shem_yishuv", rec.get("SHEM_YISHUV", ""))),
                "name_en":         str(rec.get("shem_yishuv_english", rec.get("SHEM_EN", ""))),
                "region":          str(rec.get("machoz", rec.get("MACHOZ", ""))),
            }
        })

    return {"type": "FeatureCollection", "features": features}


def load_from_file(file_path: Path) -> dict:
    """Load and validate a local GeoJSON file."""
    if not file_path.exists():
        raise FileNotFoundError(f"GeoJSON file not found: {file_path}")
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("type") != "FeatureCollection":
        raise ValueError(f"File is not a GeoJSON FeatureCollection: {file_path}")
    log.info(f"Loaded {len(data.get('features', []))} features from {file_path}")
    return data


# ---------------------------------------------------------------------------
# Import into DB
# ---------------------------------------------------------------------------

def import_into_db(geojson: dict) -> int:
    """
    Upsert municipality boundaries into municipalities_geo.
    Uses ON CONFLICT DO UPDATE so re-running is safe.

    Returns: number of rows upserted.
    """
    features = geojson.get("features", [])
    if not features:
        log.warning("No features to import")
        return 0

    conn = _get_db_conn()
    upserted = 0
    skipped  = 0

    try:
        with conn.cursor() as cur:
            for feat in features:
                props = feat.get("properties", {})
                geom  = feat.get("geometry")

                mun_id  = str(props.get("municipality_id", "")).strip()
                name_he = str(props.get("name_he", "")).strip()
                name_en = str(props.get("name_en", "")).strip() or None
                region  = str(props.get("region", "")).strip() or None

                if not mun_id or not name_he:
                    skipped += 1
                    continue
                if not geom:
                    skipped += 1
                    continue

                # Normalise to MultiPolygon
                if geom.get("type") == "Polygon":
                    geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}

                geom_str = json.dumps(geom, ensure_ascii=False)

                cur.execute("""
                    INSERT INTO municipalities_geo
                        (municipality_id, name_he, name_en, region, geom)
                    VALUES (
                        %s, %s, %s, %s,
                        ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
                    )
                    ON CONFLICT (municipality_id) DO UPDATE SET
                        name_he = EXCLUDED.name_he,
                        name_en = EXCLUDED.name_en,
                        region  = EXCLUDED.region,
                        geom    = EXCLUDED.geom
                """, (mun_id, name_he, name_en, region, geom_str))
                upserted += 1

            conn.commit()
    except Exception as e:
        conn.rollback()
        log.exception("Error importing into DB")
        raise
    finally:
        conn.close()

    log.info(f"Imported {upserted} municipalities into DB ({skipped} skipped)")
    return upserted


def list_db_municipalities() -> None:
    """Print the current content of municipalities_geo."""
    conn = _get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT municipality_id, name_he, name_en, region
                FROM municipalities_geo
                ORDER BY name_en NULLS LAST, name_he
                LIMIT 100
            """)
            rows = cur.fetchall()
            total_cur = conn.cursor()
            total_cur.execute("SELECT COUNT(*) FROM municipalities_geo")
            total = total_cur.fetchone()[0]
    finally:
        conn.close()

    print(f"\n=== municipalities_geo ({total} rows) ===")
    for mun_id, name_he, name_en, region in rows:
        print(f"  [{mun_id:>6}] {name_he:<20}  {(name_en or ''):.<25}  {region or ''}")
    if total > 100:
        print(f"  ... and {total - 100} more")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Download and import Israeli municipality boundaries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--import", dest="do_import", action="store_true",
                        help="Download from the web and import into municipalities_geo")
    parser.add_argument("--download-only", action="store_true",
                        help="Download and save to file but do NOT import into DB")
    parser.add_argument("--from-file", metavar="GEOJSON_PATH",
                        help="Import from a local GeoJSON file instead of downloading")
    parser.add_argument("--list", action="store_true",
                        help="List municipalities currently in the DB")
    parser.add_argument("--output", default=str(DEFAULT_FILE),
                        help=f"Output file path (default: {DEFAULT_FILE})")
    args = parser.parse_args()

    output_path = Path(args.output)

    if args.list:
        list_db_municipalities()
        return

    if args.from_file:
        geojson = load_from_file(Path(args.from_file))
        import_into_db(geojson)
        # Save a local copy too
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        log.info("Import complete. Run --list to verify.")
        return

    if args.download_only:
        download_geojson(output_path)
        log.info(f"Saved to {output_path} — ready to inspect or import with --from-file")
        return

    if args.do_import:
        geojson = download_geojson(output_path)
        import_into_db(geojson)
        log.info("\nNext steps:")
        log.info("  1. python3 geocoding_pipeline.py --backfill-en")
        log.info("  2. Restart Flask app (or call geo_api.invalidate_boundary_cache())")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
