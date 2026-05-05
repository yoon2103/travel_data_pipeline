#!/usr/bin/env python3
"""
check_duration_low.py — cat39 estimated_duration < 40 건수 및 visit_role 분포 확인 (read-only)
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

# [1] cat39 전체 duration 분포 요약
print("=== [1] cat39 estimated_duration 전체 분포 요약 ===")
with conn.cursor() as cur:
    cur.execute("""
        SELECT
            COUNT(*)                                             AS total,
            COUNT(*) FILTER (WHERE estimated_duration IS NULL)  AS null_count,
            MIN(estimated_duration)                              AS min_dur,
            MAX(estimated_duration)                              AS max_dur,
            ROUND(AVG(estimated_duration), 1)                   AS avg_dur,
            COUNT(*) FILTER (WHERE estimated_duration < 40)     AS below_40,
            COUNT(*) FILTER (WHERE estimated_duration > 90)     AS above_90
        FROM places
        WHERE is_active = TRUE AND category_id = 39
    """)
    row = dict(cur.fetchone())
    for k, v in row.items():
        print(f"  {k:<12}: {v}")

# [2] cat39 중 estimated_duration < 40인 행의 visit_role 분포
print("\n=== [2] cat39 duration < 40 : visit_role 분포 ===")
with conn.cursor() as cur:
    cur.execute("""
        SELECT
            visit_role,
            COUNT(*)                    AS cnt,
            MIN(estimated_duration)     AS min_dur,
            MAX(estimated_duration)     AS max_dur,
            ROUND(AVG(estimated_duration), 1) AS avg_dur
        FROM places
        WHERE is_active = TRUE
          AND category_id = 39
          AND estimated_duration < 40
        GROUP BY visit_role
        ORDER BY cnt DESC
    """)
    rows = cur.fetchall()
    for r in rows:
        print(f"  visit_role={str(r['visit_role']):<8}  cnt={r['cnt']:>5}"
              f"  min={r['min_dur']}  max={r['max_dur']}  avg={r['avg_dur']}")

# [3] cat39 중 estimated_duration < 40인 행 샘플 10건 (name + overview 일부)
print("\n=== [3] cat39 duration < 40 샘플 10건 ===")
with conn.cursor() as cur:
    cur.execute("""
        SELECT place_id, name, visit_role, estimated_duration,
               LEFT(COALESCE(overview, ''), 80) AS overview_preview
        FROM places
        WHERE is_active = TRUE
          AND category_id = 39
          AND estimated_duration < 40
        ORDER BY estimated_duration, place_id
        LIMIT 10
    """)
    for r in cur.fetchall():
        print(f"  place_id={r['place_id']:>6}  dur={r['estimated_duration']:>3}"
              f"  role={str(r['visit_role']):<8}  {r['name'][:20]}")
        if r["overview_preview"]:
            print(f"           {r['overview_preview']}")

conn.close()
