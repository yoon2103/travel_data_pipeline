import config, psycopg2, psycopg2.extras, json
import ai_processor
from ai_validator import log_validation_errors

conn = psycopg2.connect(
    host=config.DB_HOST,
    port=config.DB_PORT,
    dbname=config.DB_NAME,
    user=config.DB_USER,
    password=config.DB_PASSWORD,
    cursor_factory=psycopg2.extras.RealDictCursor
)

# 초기화
with conn.cursor() as cur:
    cur.execute("""
        UPDATE places
        SET visit_role=NULL, ai_validation_status=NULL
        WHERE place_id=103
    """)
conn.commit()

# 조회
with conn.cursor() as cur:
    cur.execute("""
        SELECT place_id, name, category_id, region_1, region_2, overview
        FROM places WHERE place_id=103
    """)
    place = dict(cur.fetchone())

print(f"[대상] {place['place_id']} / {place['name']}")

# AI 처리
ai = ai_processor.generate_tags_and_summary(place)

# 저장
with conn.cursor() as cur:
    cur.execute("""
        UPDATE places SET
            ai_summary=%(ai_summary)s,
            ai_tags=%(ai_tags)s::jsonb,
            visit_role=%(visit_role)s,
            estimated_duration=%(estimated_duration)s,
            visit_time_slot=%(visit_time_slot)s,
            ai_validation_status=%(ai_validation_status)s,
            ai_validation_errors=%(ai_validation_errors)s::jsonb,
            updated_at=NOW()
        WHERE place_id=%(place_id)s
    """, {
        "ai_summary": ai["ai_summary"],
        "ai_tags": json.dumps(ai["ai_tags"], ensure_ascii=False),
        "visit_role": ai["visit_role"],
        "estimated_duration": ai["estimated_duration"],
        "visit_time_slot": ai["visit_time_slot"],
        "ai_validation_status": ai["ai_validation_status"],
        "ai_validation_errors": json.dumps(ai["ai_validation_errors"], ensure_ascii=False),
        "place_id": 103,
    })
conn.commit()

log_validation_errors(conn, 103, ai["ai_validation_errors"], ai)

print(f"visit_role         : {ai['visit_role']}")
print(f"estimated_duration : {ai['estimated_duration']}")
print(f"visit_time_slot    : {ai['visit_time_slot']}")
print(f"ai_validation_status : {ai['ai_validation_status']}")
print(f"ai_validation_errors : {ai['ai_validation_errors']}")

conn.close()