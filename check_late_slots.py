import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import psycopg2
import psycopg2.extras
import config
from course_builder import build_course

CASES = [
    {"region": "서울", "start_time": "오늘 19:00", "template": "standard"},
    {"region": "서울", "start_time": "오늘 20:00", "template": "standard"},
    {"region": "서울", "start_time": "오늘 21:00", "template": "standard"},
    {"region": "서울", "start_time": "오늘 22:00", "template": "standard"},
    {"region": "제주", "start_time": "오늘 20:00", "template": "standard"},
]

conn = psycopg2.connect(
    host=config.DB_HOST, port=config.DB_PORT,
    dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
)
psycopg2.extras.register_default_jsonb(conn)

for req in CASES:
    label = f"{req['region']} {req['start_time']}"
    course = build_course(conn, req)
    if "error" in course:
        print(f"\n[{label}] ERROR: {course['error']} (code={course.get('error_code')})")
        continue
    places = course.get("places", [])
    print(f"\n[{label}] places={len(places)}")
    for p in places:
        meal_flag = " ← MEAL" if p["visit_role"] == "meal" else ""
        print(f"  {p['scheduled_start']}-{p['scheduled_end']} {p['visit_role']:8s} {p['name']}{meal_flag}")
    print(f"  dropped_slots: {course.get('dropped_slots', [])}")

conn.close()
