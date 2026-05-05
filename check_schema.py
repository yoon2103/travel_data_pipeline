import sys
import io
import json
import psycopg2
import psycopg2.extras
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import config
from course_builder import build_course

TOP_REQUIRED = ["template", "region", "total_duration_min", "total_travel_min", "places"]
PLACE_REQUIRED = [
    "order", "place_id", "name", "visit_role",
    "scheduled_start", "scheduled_end",
    "move_minutes_from_prev", "distance_km_from_prev",
    "selection_basis", "fallback_reason",
]

CASES = [
    ("서울", "light"),   ("서울", "standard"),  ("서울", "full"),
    ("부산", "light"),   ("부산", "standard"),  ("부산", "full"),
    ("제주", "light"),   ("제주", "standard"),  ("제주", "full"),
]

def check_type(key, val):
    """예상 타입 반환 (None 허용 필드는 별도 표시)"""
    if val is None:
        return "None"
    return type(val).__name__

def run():
    conn = psycopg2.connect(
        host=config.DB_HOST, port=config.DB_PORT,
        dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
    )
    psycopg2.extras.register_default_jsonb(conn)

    results = []
    for region, template in CASES:
        label = f"{region}/{template}"
        try:
            course = build_course(conn, {"region": region, "template": template})
        except Exception as e:
            results.append({"label": label, "error": str(e)})
            continue

        issues = []

        # 1. top-level 필드 누락
        for f in TOP_REQUIRED:
            if f not in course:
                issues.append(f"[top] 누락: {f}")

        # 2. places 필드 누락 + 타입 수집
        place_type_map = {}
        for idx, p in enumerate(course.get("places", [])):
            for f in PLACE_REQUIRED:
                if f not in p:
                    issues.append(f"[place#{idx}] 키 누락: {f}")
                else:
                    t = check_type(f, p[f])
                    place_type_map.setdefault(f, set()).add(t)

        # 3. 타입 불일치 (같은 필드에 다른 타입이 섞임)
        type_issues = []
        for f, types in place_type_map.items():
            none_only = types == {"None"}
            if len(types) > 1 and not (types - {"None"}).__len__() == 1:
                type_issues.append(f"{f}: {types}")

        results.append({
            "label":       label,
            "places_count": len(course.get("places", [])),
            "top_fields":  [f for f in TOP_REQUIRED if f in course],
            "issues":      issues,
            "type_issues": type_issues,
            "place_types": {k: list(v) for k, v in place_type_map.items()},
            "fallback_reason_present": all(
                "fallback_reason" in p for p in course.get("places", [])
            ),
            "sample_place": course["places"][0] if course.get("places") else None,
        })

    conn.close()

    # 출력
    print("=" * 60)
    print("엔진 출력 스키마 검증 결과")
    print("=" * 60)

    all_ok = True
    for r in results:
        print(f"\n[{r['label']}]")
        if "error" in r:
            print(f"  ERROR: {r['error']}")
            all_ok = False
            continue

        print(f"  places 수: {r['places_count']}")
        print(f"  fallback_reason key 전체 존재: {r['fallback_reason_present']}")

        if r["issues"]:
            all_ok = False
            for iss in r["issues"]:
                print(f"  ISSUE: {iss}")
        else:
            print(f"  필드 누락: 없음")

        if r["type_issues"]:
            all_ok = False
            for ti in r["type_issues"]:
                print(f"  타입불일치: {ti}")
        else:
            print(f"  타입 불일치: 없음")

    # 타입 일관성 비교 (전 코스 종합)
    print("\n" + "=" * 60)
    print("place 필드별 타입 (전 코스 통합)")
    print("=" * 60)
    combined = {}
    for r in results:
        if "place_types" not in r:
            continue
        for f, types in r["place_types"].items():
            combined.setdefault(f, set()).update(types)

    for f in PLACE_REQUIRED:
        types = combined.get(f, {"(데이터없음)"})
        flag = " *** 혼합" if len(types - {"None"}) > 1 else ""
        print(f"  {f:30s}: {sorted(types)}{flag}")

    print("\n" + "=" * 60)
    print(f"종합: {'전 항목 정상' if all_ok else '문제 항목 있음 (위 ISSUE 확인)'}")
    print("=" * 60)

    # sample place 출력 (첫 번째 코스)
    first = next((r for r in results if "sample_place" in r and r["sample_place"]), None)
    if first:
        print(f"\n[sample place — {first['label']}]")
        print(json.dumps(first["sample_place"], ensure_ascii=False, indent=2, default=str))

if __name__ == "__main__":
    run()
