#!/usr/bin/env python3
"""좌표 이상치 재조회 대상 목록 추출 (read-only)."""

import psycopg2, psycopg2.extras, config

KR_LAT = (33.0, 38.7)
KR_LON = (124.5, 131.9)
GA_LAT = (19.693, 19.695)
GA_LON = (117.991, 117.993)

conn = psycopg2.connect(
    host=config.DB_HOST, port=config.DB_PORT,
    dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
    cursor_factory=psycopg2.extras.RealDictCursor,
)
conn.set_session(readonly=True, autocommit=True)

with conn.cursor() as cur:
    cur.execute("""
        SELECT place_id, tourapi_content_id, category_id, name,
               latitude, longitude
        FROM   places
        WHERE  is_active IS TRUE
          AND (
               (latitude BETWEEN %s AND %s AND longitude BETWEEN %s AND %s)
            OR  latitude  < %s OR latitude  > %s
            OR  longitude < %s OR longitude > %s
            OR  latitude  IS NULL
            OR  longitude IS NULL
          )
        ORDER BY
            CASE
                WHEN latitude BETWEEN %s AND %s
                 AND longitude BETWEEN %s AND %s THEN 0
                ELSE 1
            END,
            place_id
    """, (
        *GA_LAT, *GA_LON,
        *KR_LAT, *KR_LON,
        *GA_LAT, *GA_LON,
    ))
    rows = [dict(r) for r in cur.fetchall()]

conn.close()

group_a = [r for r in rows
           if r["latitude"] and r["longitude"]
           and GA_LAT[0] <= r["latitude"] <= GA_LAT[1]
           and GA_LON[0] <= r["longitude"] <= GA_LON[1]]
group_b = [r for r in rows if r not in group_a]

print(f"재조회 대상 총 {len(rows)}건  (Group A: {len(group_a)}건 / Group B: {len(group_b)}건)")
print()

print(f"[Group A — 동일좌표 클러스터 lat≈19.694/lon≈117.992]  {len(group_a)}건")
print(f"  {'place_id':>8}  {'content_id':<14}  {'cat':>4}  name")
print(f"  {'-'*8}  {'-'*14}  {'-'*4}  {'-'*30}")
for r in group_a:
    print(f"  {r['place_id']:>8}  {str(r['tourapi_content_id'] or '')::<14}  "
          f"{str(r['category_id']):>4}  {str(r['name'])[:35]}")

print()
print(f"[Group B — 나머지 이상치]  {len(group_b)}건")
print(f"  {'place_id':>8}  {'content_id':<14}  {'cat':>4}  "
      f"{'lat':>12}  {'lon':>13}  name")
print(f"  {'-'*8}  {'-'*14}  {'-'*4}  {'-'*12}  {'-'*13}  {'-'*30}")
for r in group_b:
    print(f"  {r['place_id']:>8}  {str(r['tourapi_content_id'] or '')::<14}  "
          f"{str(r['category_id']):>4}  "
          f"{str(r['latitude'] or 'NULL'):>12}  {str(r['longitude'] or 'NULL'):>13}  "
          f"{str(r['name'])[:35]}")
