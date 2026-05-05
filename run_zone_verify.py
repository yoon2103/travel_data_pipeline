"""
run_zone_verify.py -- regional 권역 기반 출발지 구조 엔진 검증

검증 대상:
  강릉(강원) 14:00 / 경주(경북) 14:00 / 제주 14:00 / 전북 14:00

실행:
  python run_zone_verify.py
"""

import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s -- %(message)s",
    stream=sys.stdout,
)

import db_client
import regional_zone_builder
import course_builder

# (표시 이름, region_1 값, 대상 도시 설명)
TEST_CASES = [
    ("강릉",  "강원",  "강원도 -- 강릉 권역 포함"),
    ("경주",  "경북",  "경상북도 -- 경주 권역 포함"),
    ("제주",  "제주",  "제주특별자치도"),
    ("전북",  "전북",  "전라북도"),
]

SEP = "=" * 70


def _pass_fail(ok: bool) -> str:
    return "PASS ✓" if ok else "FAIL ✗"


def verify_zone(conn, label: str, region: str, desc: str) -> dict:
    print(f"\n{SEP}")
    print(f"[{label}] {desc}  (region_1={region!r})")
    print(SEP)

    # 1. 권역 후보 생성
    regional_zone_builder.invalidate_cache(region)
    zones = regional_zone_builder.generate_zone_candidates(conn, region)

    print(f"\n권역 후보: {len(zones)}개")
    if not zones:
        print("  → 권역 후보 없음. 데이터 부족 가능성.")
        return {"region": region, "zones": 0, "passed": 0, "success": False}

    passed_count = 0
    for i, z in enumerate(zones, 1):
        q = z["quality"]
        status = _pass_fail(z.get("build_passed", False))
        print(
            f"  [{i:02d}] {z['name']:<30}  radius={z['radius_km']:.0f}km  "
            f"spot={q['spot_count']}  meal={q['meal_count']}  cafe={q['cafe_count']}  "
            f"{'primary' if z['is_primary'] else 'supp':<5}  build={status}"
        )
        if z.get("build_passed"):
            passed_count += 1

    print(f"\n빌드 통과: {passed_count}/{len(zones)}")

    # 2. 첫 번째 통과 권역으로 실제 코스 생성 확인
    first_passed = next((z for z in zones if z.get("build_passed")), None)
    if first_passed is None:
        print("  → 빌드 통과 권역 없음.")
        return {"region": region, "zones": len(zones), "passed": 0, "success": False}

    print(f"\n첫 통과 권역 '{first_passed['name']}' 코스 상세:")
    result = course_builder.build_course(conn, {
        "region":             region,
        "companion":          "",
        "themes":             [],
        "template":           "standard",
        "start_time":         "14:00",
        "region_travel_type": "regional",
        "zone_center":        (first_passed["center_lat"], first_passed["center_lon"]),
        "zone_radius_km":     first_passed["radius_km"],
    })

    if "error" in result:
        print(f"  오류: {result['error']}")
        return {"region": region, "zones": len(zones), "passed": passed_count, "success": False}

    places = result.get("places", [])
    total_travel = result.get("total_travel_min", 0)
    has_meal = any(p.get("visit_role") == "meal" for p in places)

    print(f"  장소 수: {len(places)}")
    print(f"  총 이동: {total_travel}분")
    print(f"  meal 포함: {has_meal}")
    for p in places:
        print(
            f"    [{p['order']}] {p['name']:<25} "
            f"{p['visit_role']:<8} "
            f"{p['scheduled_start']}–{p['scheduled_end']}"
        )

    # 통과 기준 체크
    checks = {
        "places ≥ 3":           len(places) >= 3,
        "meal 포함":             has_meal,
        "total_travel ≤ 180":   total_travel <= 180,
        "scheduled_end 정상":   bool(places[-1].get("scheduled_end")) if places else False,
        "error 없음":            "error" not in result,
    }
    print("\n  통과 기준:")
    all_ok = True
    for k, v in checks.items():
        print(f"    {_pass_fail(v)}  {k}")
        if not v:
            all_ok = False

    overall = _pass_fail(all_ok)
    print(f"\n  최종: {overall}")

    return {
        "region":  region,
        "zones":   len(zones),
        "passed":  passed_count,
        "success": all_ok,
        "checks":  checks,
    }


def main():
    print(f"\n{'#' * 70}")
    print("  regional 권역 기반 출발지 엔진 검증")
    print(f"{'#' * 70}")

    conn = db_client.get_connection()
    results = []
    try:
        for label, region, desc in TEST_CASES:
            res = verify_zone(conn, label, region, desc)
            results.append(res)
    finally:
        conn.close()

    print(f"\n{SEP}")
    print("최종 요약")
    print(SEP)
    all_pass = True
    for r in results:
        ok = r["success"]
        if not ok:
            all_pass = False
        print(
            f"  {_pass_fail(ok)}  {r['region']:<8}  "
            f"권역={r['zones']}개  빌드통과={r['passed']}개"
        )

    print()
    if all_pass:
        print(">>> 전체 통과 -- UI/API 결함 처리 진행 가능")
    else:
        print(">>> 실패 존재 -- UI 작업 금지, 엔진/권역 로직 재수정 필요")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
