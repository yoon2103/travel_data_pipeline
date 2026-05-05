import json, sys, io, config, psycopg2, psycopg2.extras
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from course_builder import build_course

conn = psycopg2.connect(
    host=config.DB_HOST, port=config.DB_PORT,
    dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
)

REGIONS = ["서울", "부산", "제주"]
RUNS = [
    {"themes": [],              "companion": ""},
    {"themes": ["자연", "힐링"], "companion": "커플"},
    {"themes": ["역사", "문화"], "companion": "가족"},
]

results = []

for region in REGIONS:
    for i, run in enumerate(RUNS, 1):
        req = {
            "region":    region,
            "companion": run["companion"],
            "themes":    run["themes"],
            "template":  "standard",
        }
        course = build_course(conn, req)
        results.append({
            "region": region,
            "run":    i,
            "params": run,
            "course": course,
        })

conn.close()

out = []
for r in results:
    region = r["region"]
    run    = r["run"]
    c      = r["course"]
    places = c.get("places", [])

    out.append(f"\n{'='*60}")
    out.append(f"[{region} - 코스 {run}]  테마={r['params']['themes']}  동반={r['params']['companion'] or '없음'}")
    out.append(f"  총 장소: {c.get('actual_place_count')}개  이동합계: {c.get('total_travel_min')}분  "
               f"체류합계: {c.get('total_duration_min')}분")

    if not places:
        out.append("  [결과없음] " + str(c.get("error", "")))
        continue

    first_start = places[0]["scheduled_start"]
    last_end    = places[-1]["scheduled_end"]
    out.append(f"  시작: {first_start}  종료: {last_end}")
    out.append(f"  dropped_slots: {c.get('dropped_slots', [])}")
    out.append("")

    for p in places:
        sb    = p.get("selection_basis") or {}
        scores= sb.get("scores") or {}
        fb    = p.get("fallback_reason") or "-"
        move  = p.get("move_minutes_from_prev")
        dist  = p.get("distance_km_from_prev")
        dur_field = None
        # estimated_duration은 places 원본에 없으므로 start/end로 역산
        try:
            sh, sm = map(int, p["scheduled_start"].split(":"))
            eh, em = map(int, p["scheduled_end"].split(":"))
            dur_field = (eh*60+em) - (sh*60+sm)
        except Exception:
            pass

        move_str = f"{move}분" if move is not None else "출발점"
        dist_str = f"{dist}km" if dist is not None else "-"
        out.append(
            f"  [{p['order']}] {p['name'][:20]:<20} "
            f"role={p['visit_role']:<7} "
            f"{p['scheduled_start']}~{p['scheduled_end']} "
            f"체류={dur_field}분  이동={move_str}({dist_str})"
        )
        reason = sb.get("reason", "")
        tf = scores.get("travel_fit", "?")
        tm = scores.get("theme_match", "?")
        pp = scores.get("popularity_score", "?")
        sf = scores.get("slot_fit", "?")
        out.append(
            f"       선택이유: {reason[:50]}"
        )
        out.append(
            f"       scores: travel={tf} theme={tm} pop={pp} slot={sf}  fallback={fb}"
        )

with open("_course_quality_test.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))

print("완료: _course_quality_test.txt")
