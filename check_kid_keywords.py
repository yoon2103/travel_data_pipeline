import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import psycopg2
import psycopg2.extras
import config

KID_KEYWORDS = [
    "어린이", "키즈", "가족", "체험", "놀이", "아이", "유아", "동물원",
    "수족관", "테마파크", "워터파크", "박물관", "과학관", "자연학습",
    "체험관", "놀이터", "야외", "공원", "수영장", "썰매", "눈썰매",
    "에버랜드", "롯데월드", "뽀로로", "키즈카페",
]

conn = psycopg2.connect(
    host=config.DB_HOST, port=config.DB_PORT,
    dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
)
psycopg2.extras.register_default_jsonb(conn)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

print("=" * 60)
print("1. 전체 places 수 / category별")
print("=" * 60)
cur.execute("""
    SELECT category_id, visit_role, COUNT(*) as cnt
    FROM places
    WHERE is_active = TRUE AND category_id IN (12, 14, 39)
    GROUP BY category_id, visit_role
    ORDER BY category_id, visit_role
""")
for row in cur.fetchall():
    print(f"  cat{row['category_id']} / {row['visit_role']:8s}: {row['cnt']}개")

print()
print("=" * 60)
print("2. 키워드별 name/overview 히트 수 (category IN 12,14,39)")
print("=" * 60)
for kw in KID_KEYWORDS:
    cur.execute("""
        SELECT COUNT(*) as cnt, array_agg(DISTINCT category_id) as cats
        FROM places
        WHERE is_active = TRUE
          AND category_id IN (12, 14, 39)
          AND (name ILIKE %(kw)s OR overview ILIKE %(kw)s)
    """, {"kw": f"%{kw}%"})
    row = cur.fetchone()
    if row["cnt"] > 0:
        print(f"  '{kw}': {row['cnt']}개  cat={sorted(row['cats'])}")

print()
print("=" * 60)
print("3. ai_tags 내 'kid_friendly' 또는 'family' 태그 존재 여부")
print("=" * 60)
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM places
    WHERE is_active = TRUE
      AND category_id IN (12, 14, 39)
      AND ai_tags IS NOT NULL
      AND (
          ai_tags::text ILIKE '%kid%'
          OR ai_tags::text ILIKE '%family%'
          OR ai_tags::text ILIKE '%어린이%'
          OR ai_tags::text ILIKE '%가족%'
      )
""")
row = cur.fetchone()
print(f"  ai_tags 내 family/kid 관련: {row['cnt']}개")

print()
print("=" * 60)
print("4. ai_tags 내 'indoor_outdoor' 분포")
print("=" * 60)
cur.execute("""
    SELECT
        ai_tags->>'indoor_outdoor' as io,
        COUNT(*) as cnt
    FROM places
    WHERE is_active = TRUE
      AND category_id IN (12, 14, 39)
      AND ai_tags IS NOT NULL
    GROUP BY io
    ORDER BY cnt DESC
""")
for row in cur.fetchall():
    print(f"  indoor_outdoor={row['io']}: {row['cnt']}개")

print()
print("=" * 60)
print("5. 키워드 히트 샘플 (최대 10개)")
print("=" * 60)
cur.execute("""
    SELECT place_id, name, category_id, visit_role,
           ai_tags->>'indoor_outdoor' as io,
           LEFT(overview, 80) as ov_preview
    FROM places
    WHERE is_active = TRUE
      AND category_id IN (12, 14, 39)
      AND (
          name ILIKE ANY(ARRAY[
              '%어린이%','%키즈%','%가족%','%체험%','%동물원%',
              '%수족관%','%박물관%','%과학관%','%테마파크%'
          ])
          OR overview ILIKE ANY(ARRAY[
              '%어린이%','%키즈%','%가족%','%체험%','%동물원%',
              '%수족관%','%박물관%','%과학관%','%테마파크%'
          ])
      )
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  [{row['category_id']}] {row['name']} ({row['visit_role']}, io={row['io']})")
    if row["ov_preview"]:
        print(f"       → {row['ov_preview']}")

cur.close()
conn.close()
