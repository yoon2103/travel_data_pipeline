import psycopg2, psycopg2.extras, config

conn = psycopg2.connect(
    host=config.DB_HOST, port=config.DB_PORT,
    dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
    cursor_factory=psycopg2.extras.RealDictCursor,
)
conn.set_session(readonly=True, autocommit=True)

with conn.cursor() as cur:
    cur.execute("""
        SELECT place_id, name, visit_role, estimated_duration
        FROM   places
        WHERE  is_active    IS TRUE
          AND  category_id  = 39
          AND  (estimated_duration < 40 OR estimated_duration > 90)
        ORDER BY estimated_duration DESC, place_id
    """)
    rows = [dict(r) for r in cur.fetchall()]

conn.close()

durs = [r["estimated_duration"] for r in rows]
below = sum(1 for d in durs if d < 40)
above = sum(1 for d in durs if d > 90)

print(f"  cat39 estimated_duration < 40  : {below}건")
print(f"  cat39 estimated_duration > 90  : {above}건")
print(f"  cat39 out_of_range 총 잔여     : {len(rows)}건")
print(f"  min={min(durs) if durs else 'N/A'}  max={max(durs) if durs else 'N/A'}")

if rows:
    print(f"\n  잔여 상세:")
    for r in rows:
        print(f"    place_id={r['place_id']:>6}  role={str(r['visit_role']):<6}  "
              f"dur={r['estimated_duration']:>4}  {str(r['name'])[:30]}")
