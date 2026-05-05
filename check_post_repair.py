#!/usr/bin/env python3
"""
check_post_repair.py — repair 후 검증 (read-only)

1. place_id=19177 단건 상세 비교
2. v08 / v09 / v10a 재검증
3. cat12 / cat14 duration out_of_range 잔여 확인
"""

import os
import psycopg2
import psycopg2.extras
import config
from batch_rules import classify_place

conn = psycopg2.connect(
    host=config.DB_HOST, port=config.DB_PORT,
    dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
    cursor_factory=psycopg2.extras.RealDictCursor,
)
conn.set_session(readonly=True, autocommit=True)


# ─────────────────────────────────────────────────────────────────
# 1. place_id=19177 단건 상세 비교
# ─────────────────────────────────────────────────────────────────
print("=" * 64)
print("  1. place_id=19177 단건 상세 비교")
print("=" * 64)

with conn.cursor() as cur:
    cur.execute("""
        SELECT place_id, name, category_id,
               visit_role, estimated_duration, visit_time_slot, indoor_outdoor,
               LEFT(COALESCE(overview, ''), 300) AS overview_preview
        FROM   places
        WHERE  place_id = 19177
    """)
    row = dict(cur.fetchone())

result = classify_place(row["name"], row["overview_preview"], row["category_id"])

print(f"\n  장소명    : {row['name']}")
print(f"  overview  : {row['overview_preview'][:120]}")
print()
print(f"  {'항목':<22}  {'stored (DB)':<16}  {'new (classify_place)'}")
print(f"  {'-'*22}  {'-'*16}  {'-'*20}")
print(f"  {'visit_role':<22}  {str(row['visit_role']):<16}  {result['visit_role']}")
print(f"  {'estimated_duration':<22}  {str(row['estimated_duration']):<16}  {result['estimated_duration']}")
print(f"  {'visit_time_slot':<22}  {str(row['visit_time_slot']):<16}  {result['visit_time_slot']}")
print(f"  {'indoor_outdoor':<22}  {str(row['indoor_outdoor']):<16}  {result['indoor_outdoor']}")

print("\n  판단:")
if row["visit_role"] != result["visit_role"]:
    print(f"    role 불일치: stored={row['visit_role']} / new={result['visit_role']}")
    print("    → 단건 scripted repair 필요 여부는 아래 제안 참조")
else:
    print("    role 일치 — duration만 repair 가능")


# ─────────────────────────────────────────────────────────────────
# 2. v08 재검증 — estimated_duration 분포
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 64)
print("  2a. v08 재검증 — estimated_duration 분포")
print("=" * 64)

with conn.cursor() as cur:
    cur.execute("""
        SELECT
            category_id,
            COUNT(*)                                                          AS total,
            COUNT(*) FILTER (WHERE estimated_duration IS NULL)                AS null_count,
            MIN(estimated_duration)                                           AS min_dur,
            MAX(estimated_duration)                                           AS max_dur,
            ROUND(AVG(estimated_duration), 0)                                 AS avg_dur,
            COUNT(*) FILTER (WHERE estimated_duration IS NOT NULL AND CASE category_id
                WHEN 12 THEN estimated_duration < 60  OR estimated_duration > 120
                WHEN 14 THEN estimated_duration < 45  OR estimated_duration > 100
                WHEN 39 THEN estimated_duration < 40  OR estimated_duration > 90
                ELSE FALSE
            END)                                                              AS out_of_range
        FROM places
        WHERE is_active IS TRUE
          AND category_id IN (12, 14, 39)
        GROUP BY category_id
        ORDER BY category_id
    """)
    rows = cur.fetchall()

print(f"\n  {'cat':<5}  {'total':>6}  {'null':>5}  {'min':>5}  {'max':>5}  {'avg':>5}  {'out_of_range':>12}")
print(f"  {'-'*5}  {'-'*6}  {'-'*5}  {'-'*5}  {'-'*5}  {'-'*5}  {'-'*12}")
for r in rows:
    print(f"  {r['category_id']:<5}  {r['total']:>6}  {str(r['null_count'] or 0):>5}"
          f"  {str(r['min_dur'] or ''):>5}  {str(r['max_dur'] or ''):>5}"
          f"  {str(r['avg_dur'] or ''):>5}  {r['out_of_range']:>12}")


# ─────────────────────────────────────────────────────────────────
# 2b. v09 재검증 — indoor_outdoor 분포
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 64)
print("  2b. v09 재검증 — indoor_outdoor 분포")
print("=" * 64)

with conn.cursor() as cur:
    cur.execute("""
        SELECT
            category_id,
            indoor_outdoor,
            COUNT(*)                                              AS cnt,
            ROUND(100.0 * COUNT(*) /
                  SUM(COUNT(*)) OVER (PARTITION BY category_id), 1) AS pct
        FROM places
        WHERE is_active IS TRUE
          AND category_id IN (12, 14, 39)
        GROUP BY category_id, indoor_outdoor
        ORDER BY category_id, cnt DESC
    """)
    rows = cur.fetchall()

print(f"\n  {'cat':<5}  {'indoor_outdoor':<14}  {'cnt':>6}  {'pct':>6}")
print(f"  {'-'*5}  {'-'*14}  {'-'*6}  {'-'*6}")
for r in rows:
    print(f"  {r['category_id']:<5}  {str(r['indoor_outdoor'] or 'NULL'):<14}"
          f"  {r['cnt']:>6}  {r['pct']:>6}")


# ─────────────────────────────────────────────────────────────────
# 2c. v10a 재검증 — 오분류 의심 건수
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 64)
print("  2c. v10a 재검증 — 오분류 의심 건수")
print("=" * 64)

with conn.cursor() as cur:
    cur.execute("""
        SELECT check_type, category_id, flagged_value, suspicious_count FROM (
            SELECT 'cat39_outdoor' AS check_type, 39 AS category_id,
                   'outdoor'       AS flagged_value,
                   COUNT(*)        AS suspicious_count
            FROM   places
            WHERE  is_active = TRUE AND category_id = 39 AND indoor_outdoor = 'outdoor'
            UNION ALL
            SELECT 'cat12_indoor', 12, 'indoor',
                   COUNT(*)
            FROM   places
            WHERE  is_active = TRUE AND category_id = 12 AND indoor_outdoor = 'indoor'
            UNION ALL
            SELECT 'cat14_outdoor', 14, 'outdoor',
                   COUNT(*)
            FROM   places
            WHERE  is_active = TRUE AND category_id = 14 AND indoor_outdoor = 'outdoor'
        ) t
        ORDER BY check_type
    """)
    rows = cur.fetchall()

total_suspicious = 0
print(f"\n  {'check_type':<16}  {'cat':>4}  {'flagged':>8}  {'count':>8}")
print(f"  {'-'*16}  {'-'*4}  {'-'*8}  {'-'*8}")
for r in rows:
    print(f"  {r['check_type']:<16}  {r['category_id']:>4}  "
          f"{r['flagged_value']:>8}  {r['suspicious_count']:>8}")
    total_suspicious += r["suspicious_count"]
print(f"\n  합계: {total_suspicious}건")


# ─────────────────────────────────────────────────────────────────
# 3. cat12 / cat14 duration out_of_range 잔여
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 64)
print("  3. cat12 / cat14 duration out_of_range 잔여 상세")
print("=" * 64)

for cat, lo, hi in [(12, 60, 120), (14, 45, 100)]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT estimated_duration, COUNT(*) AS cnt
            FROM   places
            WHERE  is_active = TRUE
              AND  category_id = %s
              AND  estimated_duration IS NOT NULL
              AND  (estimated_duration < %s OR estimated_duration > %s)
            GROUP BY estimated_duration
            ORDER BY estimated_duration
        """, (cat, lo, hi))
        rows = cur.fetchall()
    total = sum(r["cnt"] for r in rows)
    print(f"\n  cat{cat}  clamp={lo}~{hi}  out_of_range 합계: {total}건")
    for r in rows:
        print(f"    dur={r['estimated_duration']:>4}  {r['cnt']:>5}건")

conn.close()
