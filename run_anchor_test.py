import io, sys, config, psycopg2, psycopg2.extras
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

out = []

for region in REGIONS:
    for i, run in enumerate(RUNS, 1):
        req = {"region": region, "companion": run["companion"],
               "themes": run["themes"], "template": "standard"}
        c = build_course(conn, req)
        places = c.get("places", [])

        out.append(f"\n{'='*55}")
        out.append(f"[{region} - 코스{i}]  테마={run['themes']}  동반={run['companion'] or '없음'}")
        out.append(f"  장소수={c.get('actual_place_count')}  이동합={c.get('total_travel_min')}분  "
                   f"dropped={c.get('dropped_slots', [])}")

        if not places:
            out.append("  [결과없음] " + str(c.get("error", "")))
            continue

        out.append(f"  {places[0]['scheduled_start']} ~ {places[-1]['scheduled_end']}")
        for p in places:
            move = p.get("move_minutes_from_prev")
            dist = p.get("distance_km_from_prev")
            move_s = f"{move}분({dist}km)" if move is not None else "출발점"
            try:
                sh,sm = map(int, p["scheduled_start"].split(":"))
                eh,em = map(int, p["scheduled_end"].split(":"))
                dur = (eh*60+em)-(sh*60+sm)
            except Exception:
                dur = "?"
            fb = p.get("fallback_reason") or "-"
            out.append(f"  [{p['order']}] {p['name'][:22]:<22} {p['visit_role']:<7} "
                       f"{p['scheduled_start']}~{p['scheduled_end']} 체류={dur}분 이동={move_s} fb={fb}")

conn.close()

with open("_anchor_test.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("완료: _anchor_test.txt")
