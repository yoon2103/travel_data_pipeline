import config, psycopg2, psycopg2.extras, json
import ai_processor
from ai_validator import log_validation_errors

conn = psycopg2.connect(
    host=config.DB_HOST, port=config.DB_PORT,
    dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
    cursor_factory=psycopg2.extras.RealDictCursor
)

# ── 검증 대상 3건 선택 ────────────────────────────────────────────────
targets = []

with conn.cursor() as cur:
    # 1. 음식점 (category_id=39, 카페/커피 제외)
    cur.execute("""
        SELECT place_id, name, category_id, region_1, region_2, overview
        FROM places
        WHERE category_id = 39
          AND visit_role IS NULL
          AND overview IS NOT NULL AND overview != ''
          AND name NOT ILIKE '%카페%'
          AND name NOT ILIKE '%커피%'
          AND name NOT ILIKE '%coffee%'
        ORDER BY place_id DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    if row:
        targets.append(("음식점", dict(row)))

    # 2. 카페 (category_id=39, 이름에 카페/커피 포함)
    cur.execute("""
        SELECT place_id, name, category_id, region_1, region_2, overview
        FROM places
        WHERE category_id = 39
          AND visit_role IS NULL
          AND overview IS NOT NULL AND overview != ''
          AND (name ILIKE '%카페%' OR name ILIKE '%커피%' OR name ILIKE '%coffee%')
        ORDER BY place_id DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    if row:
        targets.append(("카페", dict(row)))

    # 3. 관광지 (category_id=12)
    cur.execute("""
        SELECT place_id, name, category_id, region_1, region_2, overview
        FROM places
        WHERE category_id = 12
          AND visit_role IS NULL
          AND overview IS NOT NULL AND overview != ''
        ORDER BY place_id DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    if row:
        targets.append(("관광지", dict(row)))

print(f"검증 대상 {len(targets)}건 선택 완료\n")

# ── AI 처리 + DB 저장 ─────────────────────────────────────────────────
SLOT_LOGIC = {
    "meal": {"breakfast", "lunch", "dinner"},
    "cafe": {"morning", "lunch", "afternoon"},
    "spot": {"morning", "afternoon"},
}

for label, place in targets:
    print(f"{'='*60}")
    print(f"[{label}] place_id={place['place_id']}  name={place['name']}")
    print(f"  overview={len(place['overview'] or '')}자")

    ai = ai_processor.generate_tags_and_summary(place)

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

    # ── 결과 출력 ────────────────────────────────────────────────────
    print(f"  name               : {place['name']}")
    print(f"  visit_role         : {ai['visit_role']}")
    print(f"  estimated_duration : {ai['estimated_duration']}분")
    print(f"  visit_time_slot    : {ai['visit_time_slot']}")
    print(f"  ai_validation_status : {ai['ai_validation_status']}")
    print(f"  ai_validation_errors : {ai['ai_validation_errors']}")

    # ── 시간대 상식 판정 ─────────────────────────────────────────────
    role = ai["visit_role"]
    slots = set(ai["visit_time_slot"] or [])
    expected = SLOT_LOGIC.get(role, set())
    overlap = slots & expected
    unexpected = slots - expected

    if not slots:
        verdict = "[주의] 시간대 없음 (비어있음)"
    elif unexpected:
        verdict = f"[주의] 비정상 -- 예상 외 슬롯 포함: {unexpected}"
    elif overlap:
        verdict = f"[정상] {role} 기준 슬롯 일치"
    else:
        verdict = f"[주의] 비정상 -- {role} 기준 슬롯 없음"

    print(f"  [시간대 판정]        : {verdict}")
    print()

conn.close()
