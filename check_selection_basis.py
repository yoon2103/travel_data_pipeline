import json
from course_builder import build_course
import db_client

conn = db_client.get_connection()

request = {
    "region": "서울",
    "days": 1,
    "companion": "커플",
    "themes": ["문화", "산책"]
}

course = build_course(conn, request)
places = course.get("places", [])

result = []
for p in places[:3]:
    sb = p.get("selection_basis", {})
    result.append({
        "place_id": p.get("place_id"),
        "visit_role": p.get("visit_role"),
        "move_minutes_from_prev": p.get("move_minutes_from_prev"),
        "distance_km_from_prev": p.get("distance_km_from_prev"),
        "fallback_reason": p.get("fallback_reason"),
        "weights": sb.get("weights"),
        "scores": sb.get("scores"),
        "constraints": sb.get("constraints"),
        "evidence": sb.get("evidence"),
        "reason": sb.get("reason"),
        "fallback": sb.get("fallback")
    })

print(json.dumps(result, indent=2, ensure_ascii=False))
conn.close()