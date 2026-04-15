#!/usr/bin/env python3
"""
RAITO Geo Layer — Phase 0 + Phase 1: Address Collection & Geocoding Pipeline
=============================================================================

WORKFLOW
--------
Since POS records don't yet have addresses, this script handles two phases:

  Phase 0 — Seed address fields in the DB from any data available (POS name,
             city hints, manual CSV import).  Run once to bootstrap.

  Phase 1 — Geocode every sale_points row that has a non-empty address but
             no lat/lng yet.  Safe to re-run; skips already-geocoded rows.

USAGE
-----
  # Show all un-geocoded POS (dry run, no API calls)
  python3 geocoding_pipeline.py --dry-run

  # Import addresses from a CSV (phase 0 bootstrapping)
  python3 geocoding_pipeline.py --import-csv data/geo/pos_addresses.csv

  # Geocode all records that have addresses but no coordinates
  python3 geocoding_pipeline.py --geocode

  # Geocode a single POS by ID (useful for testing)
  python3 geocoding_pipeline.py --geocode --pos-id 42

  # Re-geocode records that previously failed or returned low confidence
  python3 geocoding_pipeline.py --geocode --retry-failed

  # Full pipeline: import CSV then geocode everything
  python3 geocoding_pipeline.py --import-csv data/geo/pos_addresses.csv --geocode

ENVIRONMENT VARIABLES
---------------------
  GOOGLE_MAPS_API_KEY   — your Geocoding API key (required for --geocode)
  DATABASE_URL          — postgres://... (falls back to Cloud SQL socket if not set)
  CLOUD_SQL_INSTANCE    — raito-house-of-brands:me-west1:raito-db (Cloud Run context)

CSV FORMAT (for --import-csv)
------------------------------
Required columns:  pos_id, address_full
Optional columns:  address_street, address_city, address_city_he

Example:
  pos_id,address_street,address_city,address_full
  101,רחוב דיזנגוף 99,תל אביב,"רחוב דיזנגוף 99, תל אביב"
  102,שדרות הנשיא 1,חיפה,"שדרות הנשיא 1, חיפה"
"""

import os
import sys
import csv
import time
import json
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Try to import psycopg2; give a helpful message if missing
# ---------------------------------------------------------------------------
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 not installed. Run:  pip install psycopg2-binary --break-system-packages")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("geocoding_pipeline")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GEOCODING_API_URL = "https://maps.googleapis.com/maps/api/geocode/json"
GEOCODE_REGION    = "IL"          # bias results toward Israel
GEOCODE_LANGUAGE  = "iw"         # prefer Hebrew responses (for municipality names)
RATE_LIMIT_DELAY  = 0.1          # seconds between API calls (10 req/s = free tier safe)
MAX_RETRIES       = 3
CONFIDENCE_ACCEPT = {"ROOFTOP", "RANGE_INTERPOLATED"}   # accept these without warning
CONFIDENCE_WARN   = {"GEOMETRIC_CENTER", "APPROXIMATE"}  # flag but still store

BASE_DIR = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

def get_db_connection() -> psycopg2.extensions.connection:
    """
    Connect to Cloud SQL PostgreSQL.
    Supports:
      - DATABASE_URL env var (postgres://user:pass@host/db)
      - Cloud SQL Unix socket via CLOUD_SQL_INSTANCE env var
      - Local dev via PG* env vars
    """
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        conn = psycopg2.connect(database_url)
        log.info("Connected via DATABASE_URL")
        return conn

    cloud_sql_instance = os.environ.get("CLOUD_SQL_INSTANCE",
                                         "raito-house-of-brands:me-west1:raito-db")
    socket_path = f"/cloudsql/{cloud_sql_instance}"
    if Path(socket_path).exists():
        conn = psycopg2.connect(
            dbname=os.environ.get("PGDATABASE", "raito"),
            user=os.environ.get("PGUSER", "raito_app"),
            password=os.environ.get("PGPASSWORD", ""),
            host=socket_path,
        )
        log.info(f"Connected via Cloud SQL socket: {socket_path}")
        return conn

    # Local development fallback
    conn = psycopg2.connect(
        host=os.environ.get("PGHOST", "127.0.0.1"),
        port=int(os.environ.get("PGPORT", 5432)),
        dbname=os.environ.get("PGDATABASE", "raito"),
        user=os.environ.get("PGUSER", "raito_app"),
        password=os.environ.get("PGPASSWORD", ""),
    )
    log.info("Connected to local PostgreSQL")
    return conn


# ---------------------------------------------------------------------------
# Phase 0: Address import
# ---------------------------------------------------------------------------

def ensure_address_columns(conn: psycopg2.extensions.connection) -> None:
    """Add address/geo columns to sale_points if they don't exist yet."""
    cols = {
        "address_street":   "TEXT",
        "address_city":     "VARCHAR(100)",
        "address_city_he":  "VARCHAR(100)",
        "address_full":     "TEXT",
        "latitude":         "DOUBLE PRECISION",
        "longitude":        "DOUBLE PRECISION",
        "geo_confidence":   "VARCHAR(30)",
        "geo_status":       "VARCHAR(30)",
        "geo_municipality":  "VARCHAR(100)",
        "geo_formatted":    "TEXT",
        "geo_raw":          "JSONB",
        "geocoded_at":      "TIMESTAMPTZ",
    }
    with conn.cursor() as cur:
        for col, dtype in cols.items():
            cur.execute(f"""
                ALTER TABLE sale_points
                ADD COLUMN IF NOT EXISTS {col} {dtype};
            """)
        conn.commit()
    log.info("Address/geo columns ensured on sale_points")


def import_addresses_from_csv(conn: psycopg2.extensions.connection,
                               csv_path: Path) -> int:
    """
    Upsert address data from CSV into sale_points.
    Required column: pos_id
    At least one of: address_full, address_street + address_city

    Returns the number of rows updated.
    """
    if not csv_path.exists():
        log.error(f"CSV not found: {csv_path}")
        return 0

    updated = 0
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        log.warning("CSV is empty — nothing to import")
        return 0

    log.info(f"Importing {len(rows)} address rows from {csv_path.name}")

    with conn.cursor() as cur:
        for row in rows:
            pos_id = row.get("pos_id", "").strip()
            if not pos_id:
                log.warning(f"Skipping row with no pos_id: {row}")
                continue

            address_full   = row.get("address_full", "").strip()
            address_street = row.get("address_street", "").strip()
            address_city   = row.get("address_city", "").strip()
            address_city_he = row.get("address_city_he", "").strip()

            # Build full address if not provided
            if not address_full and address_street and address_city:
                address_full = f"{address_street}, {address_city}"

            if not address_full:
                log.warning(f"pos_id {pos_id}: no usable address, skipping")
                continue

            cur.execute("""
                UPDATE sale_points
                SET
                    address_street  = COALESCE(NULLIF(%s,''), address_street),
                    address_city    = COALESCE(NULLIF(%s,''), address_city),
                    address_city_he = COALESCE(NULLIF(%s,''), address_city_he),
                    address_full    = COALESCE(NULLIF(%s,''), address_full),
                    geo_status      = CASE
                                        WHEN geo_status IS NULL THEN 'PENDING'
                                        WHEN geo_status = 'OK'  THEN 'OK'  -- don't reset already-geocoded
                                        ELSE 'PENDING'
                                      END
                WHERE id = %s::int
            """, (address_street, address_city, address_city_he,
                  address_full, pos_id))

            if cur.rowcount == 0:
                log.warning(f"pos_id {pos_id} not found in sale_points — skipping")
            else:
                updated += 1

        conn.commit()

    log.info(f"Updated {updated} POS records with address data")
    return updated


def show_address_status(conn: psycopg2.extensions.connection) -> None:
    """Print a summary of geocoding readiness."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*)                                        AS total_pos,
                COUNT(address_full)                             AS has_address,
                COUNT(*) FILTER (WHERE geo_status = 'OK')      AS geocoded,
                COUNT(*) FILTER (WHERE geo_status = 'PENDING') AS pending,
                COUNT(*) FILTER (WHERE geo_status = 'ZERO_RESULTS') AS failed,
                COUNT(*) FILTER (WHERE geo_status IS NULL
                                 AND address_full IS NULL)      AS no_address
            FROM sale_points
        """)
        row = cur.fetchone()
        total, has_addr, geocoded, pending, failed, no_addr = row

    print("\n=== RAITO Geocoding Status ===")
    print(f"  Total sale points :  {total}")
    print(f"  Has address       :  {has_addr}")
    print(f"  Geocoded (OK)     :  {geocoded}")
    print(f"  Pending geocode   :  {pending}")
    print(f"  Failed (0 results):  {failed}")
    print(f"  No address at all :  {no_addr}")
    print()

    if no_addr > 0:
        cur2 = conn.cursor()
        cur2.execute("""
            SELECT sp.id, sp.branch_name_he, d.key
            FROM sale_points sp
            JOIN distributors d ON d.id = sp.distributor_id
            WHERE sp.address_full IS NULL
            ORDER BY d.key, sp.id
            LIMIT 50
        """)
        missing = cur2.fetchall()
        print("  Sale points still needing an address:")
        for sp_id, name, dist in missing:
            print(f"    [{sp_id}] ({dist}) {name}")
        if no_addr > 50:
            print(f"    ... and {no_addr - 50} more")
        print()
        print("  → Fill addresses in data/geo/pos_addresses.csv then run:")
        print("    python3 geocoding_pipeline.py --import-csv data/geo/pos_addresses.csv --geocode")


# ---------------------------------------------------------------------------
# Phase 1: Geocoding
# ---------------------------------------------------------------------------

def geocode_address(api_key: str, address: str) -> dict:
    """
    Call the Google Geocoding API for a single address.

    Returns a dict with keys:
        status, lat, lng, formatted_address, confidence,
        municipality_he, municipality_en, raw
    """
    params = {
        "address":  address,
        "region":   GEOCODE_REGION,
        "language": GEOCODE_LANGUAGE,
        "key":      api_key,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(GEOCODING_API_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            break
        except requests.RequestException as e:
            log.warning(f"Geocoding request failed (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt == MAX_RETRIES:
                return {"status": "REQUEST_ERROR", "raw": str(e)}
            time.sleep(2 ** attempt)

    status = data.get("status")

    if status != "OK":
        return {"status": status, "raw": data}

    if not data.get("results"):
        return {"status": "ZERO_RESULTS", "raw": data}

    result = data["results"][0]

    # Extract confidence level
    confidence = result.get("geometry", {}).get("location_type", "UNKNOWN")

    # Extract lat/lng
    location = result["geometry"]["location"]
    lat = location["lat"]
    lng = location["lng"]
    formatted = result.get("formatted_address", "")

    # Extract municipality (locality or administrative_area_level_2)
    municipality_he = ""
    municipality_en = ""
    for component in result.get("address_components", []):
        types = component.get("types", [])
        if "locality" in types or "administrative_area_level_2" in types:
            municipality_he = component.get("long_name", "")
            # Get English name (re-query with language=en would be cleanest but costly)
            # For now store Hebrew; English translation done via municipality lookup table
            municipality_en = component.get("long_name", "")  # API returns HE when language=iw
            break

    return {
        "status":            "OK",
        "lat":               lat,
        "lng":               lng,
        "formatted_address": formatted,
        "confidence":        confidence,
        "municipality_he":   municipality_he,
        "municipality_en":   municipality_en,
        "raw":               result,
    }


def run_geocoding(
    conn: psycopg2.extensions.connection,
    api_key: str,
    pos_id: Optional[str] = None,
    retry_failed: bool = False,
) -> None:
    """
    Geocode sale_points records that have addresses but no coordinates.

    Args:
        conn:          DB connection
        api_key:       Google Maps API key
        pos_id:        If set, only geocode this specific sale_point id
        retry_failed:  If True, also retry ZERO_RESULTS / REQUEST_ERROR rows
    """
    where_clauses = ["sp.address_full IS NOT NULL"]

    if pos_id:
        where_clauses.append(f"sp.id = {int(pos_id)}")
    else:
        status_filter = ["'PENDING'"]
        if retry_failed:
            status_filter += ["'ZERO_RESULTS'", "'REQUEST_ERROR'"]
        # Include NULL geo_status rows that have an address
        where_clauses.append(
            f"(sp.geo_status IN ({','.join(status_filter)}) OR sp.geo_status IS NULL)"
        )

    query = f"""
        SELECT sp.id, sp.branch_name_he, sp.address_full
        FROM sale_points sp
        WHERE {' AND '.join(where_clauses)}
        ORDER BY sp.id
    """

    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    if not rows:
        log.info("No POS records need geocoding. Done.")
        return

    log.info(f"Geocoding {len(rows)} POS records...")
    success = failed = warned = 0

    with conn.cursor() as cur:
        for sp_id, pos_name, address in rows:
            log.info(f"  [{sp_id}] {pos_name} — '{address}'")

            result = geocode_address(api_key, address)
            now = datetime.now(timezone.utc)

            if result["status"] == "OK":
                confidence = result["confidence"]

                if confidence in CONFIDENCE_WARN:
                    log.warning(
                        f"    ⚠  Low confidence ({confidence}) — "
                        f"check: {result['formatted_address']}"
                    )
                    warned += 1
                else:
                    success += 1

                cur.execute("""
                    UPDATE sale_points SET
                        latitude         = %s,
                        longitude        = %s,
                        geo_confidence   = %s,
                        geo_status       = 'OK',
                        geo_formatted    = %s,
                        geo_municipality = %s,
                        geocoded_at      = %s,
                        geo_raw          = %s
                    WHERE id = %s
                """, (
                    result["lat"],
                    result["lng"],
                    confidence,
                    result["formatted_address"],
                    result["municipality_he"],
                    now,
                    json.dumps(result["raw"]),
                    sp_id,
                ))

                log.info(
                    f"    ✓  ({result['lat']:.5f}, {result['lng']:.5f}) "
                    f"[{confidence}] — {result['municipality_he']}"
                )

            else:
                failed += 1
                cur.execute("""
                    UPDATE sale_points SET
                        geo_status  = %s,
                        geocoded_at = %s
                    WHERE id = %s
                """, (result["status"], now, sp_id))
                log.warning(f"    ✗  Status: {result['status']}")

            conn.commit()
            time.sleep(RATE_LIMIT_DELAY)

    log.info(
        f"\nGeocoding complete: {success} OK, {warned} low-confidence, {failed} failed"
    )

    if warned > 0:
        log.info(
            "  Low-confidence results stored but may be inaccurate. "
            "Review with: SELECT id, branch_name_he, geo_formatted, geo_confidence "
            "FROM sale_points WHERE geo_confidence IN ('GEOMETRIC_CENTER','APPROXIMATE');"
        )


# ---------------------------------------------------------------------------
# Municipality name translation
# (Hebrew → English, built from municipalities_geo table)
# ---------------------------------------------------------------------------

def backfill_municipality_en(conn: psycopg2.extensions.connection) -> int:
    """
    After geocoding populates geo_municipality (Hebrew from Google API),
    do a one-time lookup against municipalities_geo to cross-reference
    English names.  Currently geo_municipality stores the Hebrew name
    returned by the API; this backfill adds English where we have a match.

    Run after importing the municipality GeoJSON.
    """
    with conn.cursor() as cur:
        # geo_municipality stores the Hebrew name from Google API.
        # We match against municipalities_geo.name_he to verify/enrich.
        cur.execute("""
            UPDATE sale_points sp
            SET geo_municipality = mg.name_en
            FROM municipalities_geo mg
            WHERE sp.geo_municipality = mg.name_he
              AND sp.geo_status = 'OK'
              AND mg.name_en IS NOT NULL
        """)
        updated = cur.rowcount
        conn.commit()

    log.info(f"Backfilled English municipality name for {updated} POS records")
    return updated


def generate_address_template(conn: psycopg2.extensions.connection,
                               output_path: Path) -> None:
    """
    Generate a CSV template pre-filled with sale_point id, name, and
    distributor info — ready for the team to fill in addresses manually.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT sp.id, sp.branch_name_he, sp.distributor_id, sp.city,
                   sp.address_full
            FROM sale_points sp
            WHERE sp.address_full IS NULL
            ORDER BY sp.distributor_id, sp.branch_name_he
        """)
        rows = cur.fetchall()

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["pos_id", "pos_name", "distributor_id", "city_hint",
                          "address_street", "address_city", "address_city_he",
                          "address_full"])
        for sp_id, name, dist_id, city_hint, _ in rows:
            writer.writerow([sp_id, name, dist_id, city_hint or "", "", "", "", ""])

    log.info(f"Address template written to {output_path} ({len(rows)} rows)")
    print(f"\n→ Fill in the CSV at:\n  {output_path}")
    print("  Then run: python3 geocoding_pipeline.py --import-csv <path> --geocode")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="RAITO Geocoding Pipeline — address collection and geocoding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show geocoding status without making API calls")
    parser.add_argument("--generate-template", metavar="OUTPUT_CSV",
                        help="Generate a blank address CSV template for manual filling")
    parser.add_argument("--import-csv", metavar="CSV_PATH",
                        help="Import addresses from CSV into sale_points")
    parser.add_argument("--geocode", action="store_true",
                        help="Run geocoding on all PENDING records")
    parser.add_argument("--pos-id", metavar="POS_ID",
                        help="Geocode a specific POS by ID (use with --geocode)")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Also retry previously failed geocoding attempts")
    parser.add_argument("--backfill-en", action="store_true",
                        help="Backfill English municipality names from municipalities_geo table")
    args = parser.parse_args()

    conn = get_db_connection()

    try:
        # Always ensure address columns exist
        ensure_address_columns(conn)

        if args.dry_run or (not args.generate_template and not args.import_csv
                             and not args.geocode and not args.backfill_en):
            show_address_status(conn)
            return

        if args.generate_template:
            out = Path(args.generate_template)
            generate_address_template(conn, out)

        if args.import_csv:
            csv_path = Path(args.import_csv)
            import_addresses_from_csv(conn, csv_path)

        if args.geocode:
            api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
            if not api_key:
                log.error(
                    "GOOGLE_MAPS_API_KEY environment variable not set.\n"
                    "  export GOOGLE_MAPS_API_KEY='your_key_here'"
                )
                sys.exit(1)
            run_geocoding(conn, api_key,
                          pos_id=args.pos_id,
                          retry_failed=args.retry_failed)

        if args.backfill_en:
            backfill_municipality_en(conn)

        # Always show final status
        show_address_status(conn)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
