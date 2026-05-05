import io, sys, config, psycopg2
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

conn = psycopg2.connect(
    host=config.DB_HOST, port=config.DB_PORT,
    dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
)

out = []

# ── 작업 1: cat39 visit_role='spot' 건수 ────────────────────────────────
with conn.cursor() as cur:
    cur.execute("""
        SELECT COUNT(*) FROM places
        WHERE category_id = 39 AND visit_role = 'spot' AND is_active = TRUE
    """)
    cnt = cur.fetchone()[0]
    out.append(f"[작업1] cat39 visit_role=spot 대상: {cnt}건")

    cur.execute("""
        SELECT place_id, name, LEFT(overview,80) AS ov
        FROM places
        WHERE category_id = 39 AND visit_role = 'spot' AND is_active = TRUE
        ORDER BY place_id
        LIMIT 20
    """)
    rows = cur.fetchall()
    for r in rows:
        out.append(f"  pid={r[0]}  {r[1][:30]}  ov={r[2]}")

# ── 작업 2: 지역별 meal + lunch slot 분포 ───────────────────────────────
out.append("")
out.append("[작업2] 지역별 meal + lunch slot 분포")
with conn.cursor() as cur:
    cur.execute("""
        SELECT region_1, COUNT(*) AS cnt
        FROM places
        WHERE category_id = 39
          AND visit_role = 'meal'
          AND visit_time_slot @> ARRAY['lunch']::varchar[]
          AND is_active = TRUE
        GROUP BY region_1
        ORDER BY cnt DESC
    """)
    rows = cur.fetchall()
    for r in rows:
        marker = " ← 부족" if r[1] < 10 else ""
        out.append(f"  {r[0]:<10} {r[1]:>5}건{marker}")

# ── 작업 3: 전체 meal 건수 vs lunch 가능 건수 비교 ──────────────────────
out.append("")
out.append("[작업3] meal 전체 vs lunch slot 상세")
with conn.cursor() as cur:
    cur.execute("""
        SELECT region_1,
               COUNT(*) FILTER (WHERE visit_role='meal') AS meal_total,
               COUNT(*) FILTER (WHERE visit_role='meal' AND visit_time_slot @> ARRAY['lunch']::varchar[]) AS lunch_ok,
               COUNT(*) FILTER (WHERE visit_role='meal' AND visit_time_slot IS NULL) AS slot_null,
               COUNT(*) FILTER (WHERE visit_role='meal' AND visit_time_slot = '{}') AS slot_empty
        FROM places
        WHERE category_id = 39 AND is_active = TRUE
        GROUP BY region_1
        ORDER BY region_1
    """)
    rows = cur.fetchall()
    out.append(f"  {'지역':<10} {'meal전체':>8} {'lunch가능':>9} {'slot_null':>9} {'slot_empty':>10}")
    for r in rows:
        out.append(f"  {r[0]:<10} {r[1]:>8} {r[2]:>9} {r[3]:>9} {r[4]:>10}")

# ── 작업 4: view_count 분포 ─────────────────────────────────────────────
out.append("")
out.append("[작업4] view_count 분포 (엔진 후보군 category IN 12,14,39)")
with conn.cursor() as cur:
    cur.execute("""
        SELECT
            MIN(view_count),
            MAX(view_count),
            ROUND(AVG(view_count),1),
            COUNT(*) FILTER (WHERE view_count = 0 OR view_count IS NULL),
            COUNT(*) FILTER (WHERE view_count > 0)
        FROM places
        WHERE category_id IN (12,14,39) AND is_active = TRUE
    """)
    r = cur.fetchone()
    out.append(f"  min={r[0]}  max={r[1]}  avg={r[2]}")
    out.append(f"  view_count=0 또는 NULL: {r[3]}건")
    out.append(f"  view_count>0         : {r[4]}건")

conn.close()

with open("_dq_diagnosis.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("완료: _dq_diagnosis.txt")
