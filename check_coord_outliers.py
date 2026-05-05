#!/usr/bin/env python3
"""
check_coord_outliers.py — 좌표 이상치 전체 목록 조회 (read-only)
"""

import psycopg2
import psycopg2.extras
import config

conn = psycopg2.connect(
    host=config.DB_HOST, port=config.DB_PORT,
    dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
    cursor_factory=psycopg2.extras.RealDictCursor,
)
conn.set_session(readonly=True, autocommit=True)

with conn.cursor() as cur:
    cur.execute("""
        SELECT
            place_id,
            tourapi_content_id,
            name,
            category_id,
            region_1,
            latitude,
            longitude,
            CASE
                WHEN latitude IS NULL OR longitude IS NULL    THEN 'COORD_NULL'
                WHEN latitude  < 33.0 OR latitude  > 43.0    THEN 'LAT_OUT_OF_RANGE'
                WHEN longitude < 124.0 OR longitude > 132.0  THEN 'LNG_OUT_OF_RANGE'
            END AS issue_type
        FROM places
        WHERE is_active IS TRUE
          AND (
              latitude  IS NULL OR longitude IS NULL
              OR latitude  < 33.0  OR latitude  > 43.0
              OR longitude < 124.0 OR longitude > 132.0
          )
        ORDER BY latitude NULLS FIRST, place_id
    """)
    rows = [dict(r) for r in cur.fetchall()]

conn.close()

print(f"\n총 이상치: {len(rows)}건")

coord_map = {}
for r in rows:
    key = (r["latitude"], r["longitude"])
    coord_map.setdefault(key, []).append(r)

print(f"고유 좌표 조합: {len(coord_map)}개")
for (lat, lon), group in sorted(
    coord_map.items(),
    key=lambda kv: (kv[0][0] if kv[0][0] is not None else float("-inf"),
                    kv[0][1] if kv[0][1] is not None else float("-inf")),
):
    print(f"  lat={lat}  lon={lon}  -> {len(group)}건")

print("\n샘플 10건 (place_id / content_id / name / cat / region / lat / lon):")
print("-" * 90)
for r in rows[:10]:
    print(
        f"  {r['place_id']:>6}  {str(r['tourapi_content_id']):>12}"
        f"  {r['name'][:20]:<20}  cat={r['category_id']}"
        f"  {r['region_1']:<4}  {r['latitude']}  {r['longitude']}"
    )
