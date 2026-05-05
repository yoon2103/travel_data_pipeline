from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import db_client  # noqa: E402
from batch.external.common import (  # noqa: E402
    external_content_id,
    haversine_km,
    log_step,
    map_role,
    normalize_name,
    valid_korea_coord,
)


def _load_raw(conn, run_id: str, region: str | None) -> list[dict]:
    sql = """
        SELECT *
        FROM raw_external_places
        WHERE run_id = %s
    """
    params: list = [run_id]
    if region:
        sql += " AND region = %s"
        params.append(region)
    sql += " ORDER BY source, keyword, id"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def _existing_duplicate(conn, region: str, name: str, lat: float, lon: float, threshold_km: float) -> bool:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT name, latitude, longitude
            FROM places
            WHERE region_1 = %s
              AND is_active = TRUE
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND name ILIKE %s
            LIMIT 20
            """,
            (region, f"%{name[:8]}%"),
        )
        for row in cur.fetchall():
            if normalize_name(row["name"]) == normalize_name(name):
                dist = haversine_km(float(row["latitude"]), float(row["longitude"]), lat, lon)
                if dist <= threshold_km:
                    return True
    return False


def _insert_invalid(conn, row: dict, reason_code: str, reason_message: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO invalid_places (
                run_id, source, tourapi_content_id, name, reason_code, reason_message, raw_payload
            )
            VALUES (%s, 'external', %s, %s, %s, %s, %s)
            """,
            (
                row["run_id"],
                external_content_id(row["source"], row["external_id"]) if row.get("external_id") else None,
                row.get("name"),
                reason_code,
                reason_message,
                psycopg2.extras.Json(row.get("raw_payload") or {}),
            ),
        )


def clean(run_id: str, region: str | None, duplicate_threshold_km: float, skip_existing: bool, write: bool) -> dict:
    conn = db_client.get_connection()
    try:
        raw_rows = _load_raw(conn, run_id, region)
        seen_keys: list[tuple[str, float, float]] = []
        clean_rows: list[dict] = []
        invalid = 0
        for row in raw_rows:
            name = row.get("name") or ""
            lat = row.get("latitude")
            lon = row.get("longitude")
            if not valid_korea_coord(lat, lon):
                invalid += 1
                if write:
                    _insert_invalid(conn, row, "INVALID_COORD", "좌표가 없거나 국내 좌표 범위를 벗어났습니다.")
                continue
            role = map_role(name, row.get("category"))
            if role is None:
                invalid += 1
                if write:
                    _insert_invalid(conn, row, "UNSUPPORTED_CATEGORY", "카페/식당/문화시설로 매핑되지 않았습니다.")
                continue
            lat_f = float(lat)
            lon_f = float(lon)
            name_key = normalize_name(name)
            in_run_duplicate = any(
                key == name_key and haversine_km(prev_lat, prev_lon, lat_f, lon_f) <= duplicate_threshold_km
                for key, prev_lat, prev_lon in seen_keys
            )
            if in_run_duplicate:
                invalid += 1
                if write:
                    _insert_invalid(conn, row, "DUPLICATE_IN_RUN", "동일 run 내 이름+좌표 유사 중복입니다.")
                continue
            if skip_existing and _existing_duplicate(conn, row["region"], name, lat_f, lon_f, duplicate_threshold_km):
                invalid += 1
                if write:
                    _insert_invalid(conn, row, "DUPLICATE_EXISTING_PLACE", "운영 places에 이미 유사 장소가 있습니다.")
                continue

            seen_keys.append((name_key, lat_f, lon_f))
            clean_rows.append({
                "run_id": row["run_id"],
                "raw_external_place_id": row["id"],
                "region": row["region"],
                "source": row["source"],
                "external_id": row["external_id"],
                "external_content_id": external_content_id(row["source"], row["external_id"]),
                "name": name,
                "latitude": lat_f,
                "longitude": lon_f,
                "category": row.get("category"),
                "address": row.get("address"),
                "phone": row.get("phone"),
                "place_url": row.get("place_url"),
                "visit_role": role,
                "duplicate_key": f"{name_key}:{round(lat_f, 4)}:{round(lon_f, 4)}",
                "normalized_payload": {
                    "source_category": row.get("category"),
                    "raw_external_place_id": row["id"],
                },
            })

        inserted = 0
        if write:
            with conn.cursor() as cur:
                for row in clean_rows:
                    cur.execute(
                        """
                        INSERT INTO clean_external_places (
                            run_id, raw_external_place_id, region, source, external_id,
                            external_content_id, name, latitude, longitude, category,
                            address, phone, place_url, visit_role, duplicate_key, normalized_payload
                        )
                        VALUES (
                            %(run_id)s, %(raw_external_place_id)s, %(region)s, %(source)s, %(external_id)s,
                            %(external_content_id)s, %(name)s, %(latitude)s, %(longitude)s, %(category)s,
                            %(address)s, %(phone)s, %(place_url)s, %(visit_role)s, %(duplicate_key)s, %(normalized_payload)s
                        )
                        ON CONFLICT (run_id, source, external_id) DO NOTHING
                        """,
                        {**row, "normalized_payload": psycopg2.extras.Json(row["normalized_payload"])},
                    )
                    inserted += cur.rowcount
            conn.commit()
            log_step(conn, run_id, "clean_external_places", "SUCCESS", input_count=len(raw_rows), output_count=inserted, metadata={"invalid_count": invalid})
        return {"run_id": run_id, "write": write, "raw_count": len(raw_rows), "clean_count": len(clean_rows), "inserted_count": inserted, "invalid_count": invalid}
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean raw_external_places into clean_external_places.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--region")
    parser.add_argument("--duplicate-threshold-km", type=float, default=0.10)
    parser.add_argument("--include-existing-duplicates", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = clean(args.run_id, args.region, args.duplicate_threshold_km, not args.include_existing_duplicates, args.write)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
