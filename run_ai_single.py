import config, psycopg2, psycopg2.extras, json
import ai_processor
from ai_validator import log_validation_errors

conn = psycopg2.connect(
    host=config.DB_HOST, port=config.DB_PORT,
    dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
    cursor_factory=psycopg2.extras.RealDictCursor
)

# 1. visit_role IS NULL + overview 있는 1건 선택
with conn.cursor() as cur:
    cur.execute("""
        SELECT place_id, name, category_id, region_1, region_2, overview
        FROM places
        WHERE visit_role IS NULL
          AND overview IS NOT NULL AND overview != ''
        ORDER BY place_id DESC
        LIMIT 1
    """)
    place = dict(cur.fetchone())

print(f'[대상] place_id={place["place_id"]}  name={place["name"]}')
print(f'       overview={len(place["overview"] or "")}자')

# 2. AI 가공
print('[처리] AI 가공 중...')
ai = ai_processor.generate_tags_and_summary(place)

# 3. DB 저장
params = {
    "ai_summary":           ai["ai_summary"],
    "ai_tags":              json.dumps(ai["ai_tags"], ensure_ascii=False),
    "visit_role":           ai["visit_role"],
    "estimated_duration":   ai["estimated_duration"],
    "visit_time_slot":      ai["visit_time_slot"],
    "ai_validation_status": ai["ai_validation_status"],
    "ai_validation_errors": json.dumps(ai["ai_validation_errors"], ensure_ascii=False),
    "place_id":             place["place_id"],
}

with conn.cursor() as cur:
    cur.execute("""
        UPDATE places SET
            ai_summary           = %(ai_summary)s,
            ai_tags              = %(ai_tags)s::jsonb,
            visit_role           = %(visit_role)s,
            estimated_duration   = %(estimated_duration)s,
            visit_time_slot      = %(visit_time_slot)s,
            ai_validation_status = %(ai_validation_status)s,
            ai_validation_errors = %(ai_validation_errors)s::jsonb,
            updated_at           = NOW()
        WHERE place_id = %(place_id)s
    """, params)
conn.commit()

log_validation_errors(conn, place["place_id"], ai["ai_validation_errors"], ai)
print('[저장] DB 업데이트 완료')

# 4. DB 재조회
with conn.cursor() as cur:
    cur.execute("""
        SELECT name, visit_role, estimated_duration, visit_time_slot,
               ai_validation_status, ai_validation_errors
        FROM places WHERE place_id = %(place_id)s
    """, {"place_id": place["place_id"]})
    row = dict(cur.fetchone())

print()
print("=== 최종 저장 결과 ===")
for k, v in row.items():
    print(f"  {k}: {v}")

conn.close()
