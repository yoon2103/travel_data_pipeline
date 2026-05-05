#!/usr/bin/env python3
"""
check_coord_outlier_analysis.py — 좌표 이상치 분석 (read-only)

한국 좌표 범위 기준: lat 33.0~38.7 / lon 124.5~131.9
  Group A: lat=19.694 / lon=117.992 동일좌표 46건 묶음 분석
  Group B: 나머지 이상치 개별 상세
"""

import psycopg2
import psycopg2.extras
import config

KR_LAT = (33.0, 38.7)
KR_LON = (124.5, 131.9)

# Group A 클러스터 기준 (소수점 3자리 범위)
GA_LAT = (19.693, 19.695)
GA_LON = (117.991, 117.993)

conn = psycopg2.connect(
    host=config.DB_HOST, port=config.DB_PORT,
    dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
    cursor_factory=psycopg2.extras.RealDictCursor,
)
conn.set_session(readonly=True, autocommit=True)


# ─────────────────────────────────────────────────────────────────
# Group A: lat=19.694 / lon=117.992 동일좌표 46건 묶음
# ─────────────────────────────────────────────────────────────────
print("=" * 64)
print("  Group A — lat≈19.694 / lon≈117.992 동일좌표 클러스터")
print("=" * 64)

with conn.cursor() as cur:
    cur.execute("""
        SELECT
            COUNT(*)                                    AS total,
            COUNT(DISTINCT category_id)                 AS cat_kinds,
            COUNT(DISTINCT region_1)                    AS region_kinds,
            MIN(created_at)::date                       AS created_min,
            MAX(created_at)::date                       AS created_max,
            MIN(updated_at)::date                       AS updated_min,
            MAX(updated_at)::date                       AS updated_max,
            COUNT(*) FILTER (WHERE synced_at IS NULL)   AS synced_null,
            COUNT(*) FILTER (WHERE synced_at IS NOT NULL) AS synced_ok,
            COUNT(*) FILTER (WHERE tourapi_modified_time IS NOT NULL) AS tmt_ok,
            COUNT(*) FILTER (WHERE tourapi_modified_time IS NULL)     AS tmt_null
        FROM places
        WHERE is_active IS TRUE
          AND latitude  BETWEEN %s AND %s
          AND longitude BETWEEN %s AND %s
    """, (*GA_LAT, *GA_LON))
    summary = dict(cur.fetchone())

print(f"\n  total                    : {summary['total']}건")
print(f"  created_at 범위          : {summary['created_min']} ~ {summary['created_max']}")
print(f"  updated_at 범위          : {summary['updated_min']} ~ {summary['updated_max']}")
print(f"  synced_at NULL           : {summary['synced_null']}건  / NOT NULL: {summary['synced_ok']}건")
print(f"  tourapi_modified_time    : NOT NULL={summary['tmt_ok']}건 / NULL={summary['tmt_null']}건")

# category_id 분포
with conn.cursor() as cur:
    cur.execute("""
        SELECT category_id, COUNT(*) AS cnt
        FROM   places
        WHERE  is_active IS TRUE
          AND  latitude  BETWEEN %s AND %s
          AND  longitude BETWEEN %s AND %s
        GROUP BY category_id
        ORDER BY cnt DESC
    """, (*GA_LAT, *GA_LON))
    rows = [dict(r) for r in cur.fetchall()]

print(f"\n  [category_id 분포]")
for r in rows:
    print(f"    cat{r['category_id']}  :  {r['cnt']}건")

# region_1 분포
with conn.cursor() as cur:
    cur.execute("""
        SELECT COALESCE(region_1, 'NULL') AS region_1, COUNT(*) AS cnt
        FROM   places
        WHERE  is_active IS TRUE
          AND  latitude  BETWEEN %s AND %s
          AND  longitude BETWEEN %s AND %s
        GROUP BY region_1
        ORDER BY cnt DESC
        LIMIT 10
    """, (*GA_LAT, *GA_LON))
    rows = [dict(r) for r in cur.fetchall()]

print(f"\n  [region_1 분포 (상위 10)]")
for r in rows:
    print(f"    {r['region_1']:<14}  :  {r['cnt']}건")

# synced_at 분포 (NOT NULL인 경우 날짜별)
with conn.cursor() as cur:
    cur.execute("""
        SELECT synced_at::date AS sync_date, COUNT(*) AS cnt
        FROM   places
        WHERE  is_active IS TRUE
          AND  latitude  BETWEEN %s AND %s
          AND  longitude BETWEEN %s AND %s
          AND  synced_at IS NOT NULL
        GROUP BY synced_at::date
        ORDER BY synced_at::date
    """, (*GA_LAT, *GA_LON))
    rows = [dict(r) for r in cur.fetchall()]

if rows:
    print(f"\n  [synced_at 분포 (NOT NULL분)]")
    for r in rows:
        print(f"    {r['sync_date']}  :  {r['cnt']}건")
else:
    print(f"\n  [synced_at] 전량 NULL")


# ─────────────────────────────────────────────────────────────────
# Group B: 나머지 이상치 3건 개별 상세
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 64)
print("  Group B — 나머지 좌표 이상치 (동일좌표 클러스터 제외)")
print("=" * 64)

with conn.cursor() as cur:
    cur.execute("""
        SELECT
            place_id, tourapi_content_id, name, category_id,
            region_1, latitude, longitude, synced_at,
            tourapi_modified_time
        FROM   places
        WHERE  is_active IS TRUE
          AND  (
               latitude  < %s OR latitude  > %s
            OR longitude < %s OR longitude > %s
            OR latitude  IS NULL
            OR longitude IS NULL
          )
          AND NOT (
               latitude  BETWEEN %s AND %s
           AND longitude BETWEEN %s AND %s
          )
        ORDER BY place_id
    """, (*KR_LAT, *KR_LON, *GA_LAT, *GA_LON))
    rows = [dict(r) for r in cur.fetchall()]

print(f"\n  총 {len(rows)}건\n")
print(f"  {'place_id':>8}  {'content_id':<14}  {'cat':>4}  "
      f"{'region_1':<10}  {'lat':>8}  {'lon':>9}  "
      f"{'synced_at':<12}  {'tmt':>5}  name")
print(f"  {'-'*8}  {'-'*14}  {'-'*4}  "
      f"{'-'*10}  {'-'*8}  {'-'*9}  "
      f"{'-'*12}  {'-'*5}  {'-'*20}")
for r in rows:
    tmt = 'Y' if r['tourapi_modified_time'] else 'N'
    sync = str(r['synced_at'])[:10] if r['synced_at'] else 'NULL'
    print(f"  {r['place_id']:>8}  {str(r['tourapi_content_id'] or ''):<14}  "
          f"{str(r['category_id']):>4}  "
          f"{str(r['region_1'] or ''):<10}  "
          f"{str(r['latitude'] or ''):>8}  {str(r['longitude'] or ''):>9}  "
          f"{sync:<12}  {tmt:>5}  {str(r['name'])[:30]}")

conn.close()
