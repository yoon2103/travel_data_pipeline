"""
QA 진단 실행 스크립트
- 엔진 직접 호출로 입력값 반영 여부 검증
- 지역별 anchor 후보 집계
- 재계산 시간 오류 시뮬레이션
"""
import sys, json, traceback
sys.path.insert(0, "D:/travel_data_pipeline")

import db_client
import course_builder
import regional_zone_builder
import anchor_definitions

BASE_REGION   = "서울"
BASE_ANCHOR   = "서울"
BASE_ANCHOR_LAT = 37.4979
BASE_ANCHOR_LON = 127.0276
BASE_TIME     = "오늘 10:00"

RESULTS = {}

def run_build(conn, region, lat, lon, template, themes, companion, walk_max_radius, label):
    req = {
        "region":             region,
        "departure_time":     BASE_TIME,
        "start_time":         BASE_TIME,
        "companion":          companion,
        "themes":             themes,
        "template":           template,
        "region_travel_type": "urban",
        "zone_center":        (lat, lon),
        "zone_radius_km":     None,
        "walk_max_radius":    walk_max_radius,
    }
    result = course_builder.build_course(conn, req)
    places = result.get("places", [])
    cafe_count    = sum(1 for p in places if p.get("visit_role") == "cafe")
    meal_count    = sum(1 for p in places if p.get("visit_role") == "meal")
    tourist_count = sum(1 for p in places if p.get("visit_role") in ("spot","culture"))
    roles_str     = [p.get("visit_role","?") for p in places]
    names_str     = [p.get("name","?") for p in places]
    scheduled_end = places[-1].get("scheduled_end","?") if places else "N/A"
    total_travel  = result.get("total_travel_min", 0)
    radius_fb     = result.get("radius_fallback", False)

    top_sb = result.get("selection_basis", {})
    row = {
        "label":              label,
        "template":           result.get("template","?"),
        "target_place_count": result.get("target_place_count","?"),
        "actual_place_count": result.get("actual_place_count","?"),
        "cafe_count":         cafe_count,
        "meal_count":         meal_count,
        "tourist_count":      tourist_count,
        "scheduled_end":      scheduled_end,
        "total_travel_min":   total_travel,
        "radius_fallback":    radius_fb,
        "selected_radius_km": result.get("selected_radius_km", "?"),
        "selection_basis":    top_sb,
        "roles":              roles_str,
        "place_names":        names_str,
        "place_selection_reasons": [p.get("selection_basis",{}).get("reason","?") for p in places] if places else [],
        "error":              result.get("error"),
    }
    RESULTS[label] = row
    return row

def section1_front_payload_check():
    """프론트 → API payload 검증 (정적 분석)"""
    findings = {}

    # canGenerate 조건 확인
    findings["canGenerate_condition"] = (
        "HomeScreen:161 → const canGenerate = !!departureTime && !!selectedAnchor\n"
        "region은 기본값 '서울'로 항상 존재 → region 미선택 상태에서도 버튼 활성화 가능\n"
        "요청사항: region/start_time/start_anchor 3개 모두 필수여야 함\n"
        "판정: 구조상 region은 기본값 존재로 항상 truthy → 기능적으로는 OK지만, "
        "명시적 region 선택 없이 기본값 서울로 진행 가능한 UX 문제 존재"
    )

    # ConditionScreen 뒤로가기 시 선택값 초기화
    findings["condition_state_reset"] = (
        "ConditionScreen:64 → useState({ companion:'혼자', mood:'자연 선택', walk:'보통', density:'적당히' })\n"
        "App.jsx:38 → onBack() → setScreen('condition') 로 돌아올 때 ConditionScreen 재마운트\n"
        "결과: CourseResultScreen에서 뒤로가기 시 ConditionScreen 로컬 state 초기화됨\n"
        "판정: 프론트 BUG - 이전 선택값 유지 안 됨"
    )

    # payload 포함 여부
    findings["payload_fields"] = (
        "CourseResultScreen:115-127 payload 구성:\n"
        "  region:             ✅ params.region\n"
        "  departure_time:     ✅ params.departure_time\n"
        "  start_anchor:       ✅ params.start_anchor\n"
        "  start_lat/lon:      ✅ params.start_lat, params.start_lon\n"
        "  companion:          ✅ params.companion\n"
        "  themes:             ✅ MOOD_TO_THEMES[params.mood] 변환 후\n"
        "  template:           ✅ DENSITY_TO_TEMPLATE[params.density] 변환 후\n"
        "  walk_max_radius:    ✅ WALK_TO_RADIUS[params.walk] 변환 후\n"
        "  density (원값):     ❌ 미전송 — template으로 변환되어 원값 소실\n"
        "  distance_preference(원값): ❌ 미전송 — walk_max_radius로 변환\n"
        "console.log 존재: CourseResultScreen:128 '[CourseGenerate] request payload:'"
    )

    # MOOD_TO_THEMES 매핑
    findings["mood_to_themes_mapping"] = (
        "dayTripDummyData.js MOOD_TO_THEMES:\n"
        "  '자연 선택'  → ['nature']\n"
        "  '도심 감성'  → ['urban']\n"
        "  '카페 투어'  → ['cafe']\n"
        "  '맛집 탐방'  → ['food']\n"
        "  '역사 문화'  → ['history']\n"
        "  '조용한 산책' → ['walk']"
    )

    findings["density_to_template_mapping"] = (
        "CourseResultScreen:109 DENSITY_TO_TEMPLATE:\n"
        "  '여유롭게' → 'light'    (3 slots)\n"
        "  '적당히'   → 'standard' (4 slots)\n"
        "  '알차게'   → 'full'     (4 slots)\n"
        "course_builder.py:22-25 TEMPLATES:\n"
        "  'full' == 'standard' → 완전히 동일한 slot 구조\n"
        "  판정: 엔진 BUG - density=알차게 와 density=적당히 결과 동일"
    )

    findings["walk_to_radius_mapping"] = (
        "CourseResultScreen:112-113 WALK_TO_RADIUS:\n"
        "  '적게'              → 5km\n"
        "  '보통'              → 10km\n"
        "  '조금 멀어도 좋아요' → 18km\n"
        "course_builder.py:57 URBAN_STEP_TRAVEL:\n"
        "  5km  → 25min\n"
        "  10km → 40min\n"
        "  18km → 55min"
    )

    return findings

def section2_anchor_diagnosis(conn):
    """출발 기준점 진단: 지역별 anchor 존재·후보 수 확인"""
    target_regions = ["서울", "광주", "대구", "대전", "인천", "울산", "세종", "강원", "경북"]
    display_map = {
        "서울": "서울", "광주": "광주", "대구": "대구", "대전": "대전",
        "인천": "인천", "울산": "울산", "세종": "세종", "강원": "강릉(강원)", "경북": "경주(경북)"
    }

    results = {}
    for region in target_regions:
        raw = anchor_definitions.REGION_ANCHORS.get(region, [])
        if not raw:
            results[region] = {
                "display": display_map.get(region, region),
                "anchor_defined": False,
                "cause": "A. anchor 정의 없음",
                "anchors": [],
            }
            continue

        anchor_rows = []
        for a in raw:
            try:
                counts = regional_zone_builder._validate_anchor(
                    conn, region, a["latitude"], a["longitude"]
                )
                viable = (counts["tourist_10km"] >= regional_zone_builder.ANCHOR_TOURIST_MIN
                          and counts["meal_10km"] >= regional_zone_builder.ANCHOR_MEAL_MIN)
                anchor_rows.append({
                    "anchor_id":     a["anchor_id"],
                    "display_name":  a["display_name"],
                    "tourist_10km":  counts["tourist_10km"],
                    "meal_10km":     counts["meal_10km"],
                    "cafe_10km":     counts["cafe_10km"],
                    "total_10km":    counts["total_10km"],
                    "total_15km":    counts["total_15km"],
                    "total_25km":    counts["total_25km"],
                    "viable":        viable,
                    "excluded_reason": (
                        None if viable else
                        f"관광지 {counts['tourist_10km']}개 < 2" if counts["tourist_10km"] < 2
                        else f"식당 {counts['meal_10km']}개 < 1"
                    ),
                })
            except Exception as e:
                anchor_rows.append({"anchor_id": a["anchor_id"], "error": str(e)})

        viable_count = sum(1 for a in anchor_rows if a.get("viable"))
        results[region] = {
            "display":       display_map.get(region, region),
            "anchor_defined": True,
            "anchor_count":  len(raw),
            "viable_count":  viable_count,
            "cause":         None if viable_count > 0 else "C. DB 후보 부족 또는 D. 필터 과도",
            "anchors":       anchor_rows,
        }

    return results

def section3_api_response_fields():
    """API 응답 필드 존재 여부 확인 (정적 분석)"""
    return {
        "build_course_returns": {
            "template":           "✅ 반환",
            "region":             "✅ 반환",
            "target_place_count": "✅ 반환",
            "actual_place_count": "✅ 반환",
            "total_duration_min": "✅ 반환",
            "total_travel_min":   "✅ 반환",
            "dropped_slots":      "✅ 반환",
            "places":             "✅ 반환",
            "applied_options":    "❌ 미반환",
            "selected_radius_km": "❌ 미반환",
            "selection_basis":    "❌ top-level 미반환 (place별로는 있음)",
        },
        "api_server_adds": {
            "radius_fallback":       "✅ _build_course_with_fallback 에서 추가",
            "radius_fallback_label": "✅ 추가",
            "radius_fallback_reason":"✅ 추가",
            "course_id":             "✅ 추가",
        },
        "api_receives": {
            "companion":          "✅ GenerateRequest:41",
            "themes":             "✅ GenerateRequest:42",
            "template":           "✅ GenerateRequest:43",
            "walk_max_radius":    "✅ GenerateRequest:46",
            "region_travel_type": "✅ GenerateRequest:44",
        },
        "default_overwrite_check": (
            "api_server.py:327-338 request 딕셔너리 구성:\n"
            "  companion: body.companion or '' → 빈 문자열로 기본값 처리\n"
            "  themes: body.themes or [] → 빈 리스트로 기본값 처리\n"
            "  template: body.template or 'standard' → 미전송 시 standard 강제\n"
            "  walk_max_radius: body.walk_max_radius → None 허용 (course_builder에서 MAX_RADIUS_KM=10 적용)\n"
            "  판정: 기본값 덮어쓰기 없음, 수신값 그대로 전달"
        ),
    }

def section4_engine_test(conn):
    """엔진 진단: 조건별 결과 비교"""
    lat, lon = BASE_ANCHOR_LAT, BASE_ANCHOR_LON

    tests = [
        # (label, template, themes, companion, walk_max_radius)
        ("기본(서울)",        "standard", [],          "",       10),
        ("카페투어(서울)",    "standard", ["cafe"],     "",       10),
        ("맛집탐방(서울)",    "standard", ["food"],     "",       10),
        ("자연산책(서울)",    "standard", ["nature"],   "",       10),
        ("여유롭게(서울)",    "light",    [],           "",       10),
        ("알차게(서울)",      "full",     [],           "",       10),
        ("거리부담적게(서울)","standard", [],           "",        5),
        ("거리멀어도OK(서울)","standard", [],           "",       18),
    ]

    rows = []
    for label, tmpl, themes, companion, walk in tests:
        try:
            row = run_build(conn, BASE_REGION, lat, lon, tmpl, themes, companion, walk, label)
            rows.append(row)
        except Exception as e:
            rows.append({"label": label, "error": str(e), "traceback": traceback.format_exc()})

    return rows

def section4_engine_test_regional(conn):
    """지방 지역 엔진 테스트 (강원·경북)"""
    regional_tests = [
        # (label, region, lat, lon, template, themes, walk)
        ("기본(강원/강릉역)",  "강원", 37.7750, 128.9400, "standard", [], 10),
        ("기본(경북/경주역)",  "경북", 35.8392, 129.2101, "standard", [], 10),
        ("기본(경북/황리단길)", "경북", 35.8342, 129.2259, "standard", [], 10),
        ("거리멀어도OK(강원)", "강원", 37.7750, 128.9400, "standard", [], 18),
    ]
    rows = []
    for label, region, lat, lon, tmpl, themes, walk in regional_tests:
        try:
            row = run_build(conn, region, lat, lon, tmpl, themes, "", walk, label)
            rows.append(row)
        except Exception as e:
            rows.append({"label": label, "error": str(e)})
    return rows

def section5_radius_policy():
    """도시/지방 반경 정책 진단 (정적 분석)"""
    return {
        "MAX_RADIUS_KM": "course_builder.py:38 → MAX_RADIUS_KM = 10 (모든 지역 일괄 적용)",
        "MAX_TRAVEL_MIN": "course_builder.py:37 → MAX_TRAVEL_MIN = 40",
        "SPARSE_REGIONS": "course_builder.py:47 → {제주, 강원, 전남, 경북, 충남, 전북, 경남, 충북}",
        "SPARSE_meal_fallback": "course_builder.py:45-46 → sparse 지역 meal fallback 20km/60min",
        "urban_step_travel": {
            "5km": "25min",
            "10km": "40min",
            "15km": "50min",
            "18km": "55min",
            "25km": "60min",
        },
        "city_type_exists": "❌ city_type 또는 region_mobility_profile 미구현",
        "analysis": (
            "문제: MAX_RADIUS_KM=10이 서울/대도시/지방 모두 동일 적용\n"
            "서울 10km → 적정 (지하철 2~4km 권역이지만 관광지 밀집)\n"
            "지방 10km → 과도하게 짧을 수 있음 (차량 이동 기준 15~25km 적절)\n"
            "sparse 지역은 meal만 20km fallback 있으나 spot/culture는 동일 10km\n"
            "MAX_TOTAL_TRAVEL=120 (urban) 지방 코스에서 탈락 가능성\n"
            "REGIONAL_MAX_TOTAL_TRAVEL=180 (regional) → regional 모드는 분리됨\n"
            "urban 모드로 지방 지역 접근 시 10km/120분 제한이 문제\n"
            "판정: 지방 지역을 urban 모드로 생성 시 후보 부족 가능성 높음"
        ),
    }

def section6_recalculate_bug():
    """경로 재계산 시간 오류 진단 (정적 분석)"""
    return {
        "recalculate_endpoint": "api_server.py:463-536",
        "time_format": (
            "api_server.py:514-515:\n"
            "  'scheduled_start': f'{s_min // 60:02d}:{s_min % 60:02d}'\n"
            "  'scheduled_end':   f'{e_min // 60:02d}:{e_min % 60:02d}'\n"
            "  → 24시간 초과 방어 없음 → 25:03, 33:04 출력 가능"
        ),
        "end_hour_limit_missing": (
            "course_builder.py:648-655: build_course 에는 END_HOUR_LIMIT(22:00) 체크 있음\n"
            "api_server.py:recalculate_course: END_HOUR_LIMIT 체크 없음 → 버그 확인"
        ),
        "cascade_bug": (
            "재계산 시 duration 복원 로직 (api_server.py:493-499):\n"
            "  sh,sm = scheduled_start 파싱\n"
            "  eh,em = scheduled_end 파싱\n"
            "  duration_min = (eh*60+em) - (sh*60+sm)\n"
            "만약 이전 재계산이 '25:03'을 생성했다면:\n"
            "  duration_min = (25*60+3) - (9*60+0) = 963분\n"
            "  → 다음 재계산에서 963분 체류 적용 → 더 큰 시간 생성 (cascade)"
        ),
        "replace_reuses_old_time": (
            "api_server.py:436-444 replace_place:\n"
            "  replaced['scheduled_start'] = old['scheduled_start']\n"
            "  replaced['scheduled_end']   = old['scheduled_end']\n"
            "  → 교체 후 hasPendingRecalculate=true 설정 → 재계산 필요\n"
            "  → 재계산 전에는 UI에 올바른 교체 시간 표시되지 않음 (OK)"
        ),
        "added_place_disappears": (
            "CourseResultScreen:248-267 handleAddConfirm:\n"
            "  추가된 장소 id: added-${Date.now()}\n"
            "  api_server.py:474 place_map은 원본 place_id 기준\n"
            "  → 재계산 시 added- ID를 place_map에서 못 찾음 → 장소 사라짐\n"
            "  판정: 프론트 + API BUG"
        ),
        "no_24h_modulo": (
            "minutes → HH:mm 변환 시 24시간 초과를 그대로 출력\n"
            "수정: s_min % (24*60), e_min % (24*60) 또는 e_min > 22*60 시 truncate"
        ),
    }

def section7_post_fix_verification(conn):
    """수정 후 검증: request.md 항목 1-6 통과 기준 확인"""
    lat, lon = BASE_ANCHOR_LAT, BASE_ANCHOR_LON

    # 테스트 케이스: 동일 출발점, 동일 시간, 4가지 theme + 3가지 density
    cases = [
        # (label, template, themes)
        ("기본",     "standard", []),
        ("카페투어",  "standard", ["cafe"]),
        ("맛집탐방",  "standard", ["food"]),
        ("자연산책",  "standard", ["nature"]),
        ("여유롭게",  "light",    []),
        ("적당히",   "standard", []),
        ("알차게",   "full",     []),
    ]
    rows = {}
    for label, tmpl, themes in cases:
        try:
            row = run_build(conn, BASE_REGION, lat, lon, tmpl, themes, "", 10, label)
            rows[label] = row
        except Exception as e:
            rows[label] = {"label": label, "error": str(e), "traceback": traceback.format_exc()}

    verdicts = {}

    # 판정 1: 4가지 theme 결과가 서로 달라야 함
    base_names  = set(rows.get("기본",  {}).get("place_names", []))
    cafe_names  = set(rows.get("카페투어", {}).get("place_names", []))
    food_names  = set(rows.get("맛집탐방", {}).get("place_names", []))
    nature_names= set(rows.get("자연산책", {}).get("place_names", []))
    verdicts["theme_구분"] = {
        "기본vs카페": "PASS" if base_names != cafe_names else "FAIL — 동일결과",
        "기본vs맛집": "PASS" if base_names != food_names else "FAIL — 동일결과",
        "기본vs자연": "PASS" if base_names != nature_names else "FAIL — 동일결과",
    }

    # 판정 2: 카페투어 카페 3개 이상
    cafe_cnt = rows.get("카페투어", {}).get("cafe_count", 0)
    verdicts["카페투어_cafe_3개이상"] = f"PASS (cafe={cafe_cnt})" if cafe_cnt >= 3 else f"FAIL (cafe={cafe_cnt}, 기준 3개 이상)"

    # 판정 3: density 구분 — full vs standard
    full_names = set(rows.get("알차게", {}).get("place_names", []))
    std_names  = set(rows.get("적당히", {}).get("place_names", []))
    full_target = rows.get("알차게", {}).get("target_place_count", 0)
    std_target  = rows.get("적당히", {}).get("target_place_count", 0)
    full_end    = rows.get("알차게", {}).get("scheduled_end", "?")
    std_end     = rows.get("적당히", {}).get("scheduled_end", "?")
    verdicts["density_full_vs_standard"] = {
        "target_count_다름": "PASS" if full_target != std_target else f"FAIL (full={full_target}, std={std_target})",
        "결과_다름":         "PASS" if full_names != std_names else "FAIL — 동일결과",
        "종료시각_다름":     "PASS" if full_end != std_end else f"FAIL (둘다 {full_end})",
    }

    # 판정 4: roles 구성 — 카페투어는 cafe 포함, 맛집탐방은 meal 비중
    cafe_roles  = rows.get("카페투어", {}).get("roles", [])
    food_roles  = rows.get("맛집탐방", {}).get("roles", [])
    base_roles  = rows.get("기본",    {}).get("roles", [])
    verdicts["slot_구조_다름"] = {
        "카페투어_roles":  cafe_roles,
        "맛집탐방_roles":  food_roles,
        "기본_roles":      base_roles,
        "카페투어에cafe있음": "PASS" if "cafe" in cafe_roles else "FAIL",
        "맛집탐방에meal>기본meal": "PASS" if food_roles.count("meal") > base_roles.count("meal") else f"FAIL (food_meal={food_roles.count('meal')}, base_meal={base_roles.count('meal')})",
    }

    # 판정 5: selection_basis weights — theme 활성화 시 theme_match 상승
    cafe_sb = rows.get("카페투어", {}).get("selection_basis", {})
    base_sb = rows.get("기본",    {}).get("selection_basis", {})
    cafe_w  = cafe_sb.get("weights", {})
    base_w  = base_sb.get("weights", {})
    verdicts["weights_theme_반영"] = {
        "기본_travel_fit":    base_w.get("travel_fit", "?"),
        "기본_theme_match":   base_w.get("theme_match", "?"),
        "카페투어_travel_fit": cafe_w.get("travel_fit", "?"),
        "카페투어_theme_match":cafe_w.get("theme_match", "?"),
        "판정": "PASS" if cafe_w.get("theme_match", 0) > base_w.get("theme_match", 0) else "FAIL",
    }

    # 판정 6: selected_radius_km 반환
    verdicts["selected_radius_km_반환"] = {
        r: rows.get(r, {}).get("selected_radius_km", "MISSING")
        for r in ["기본", "카페투어", "맛집탐방", "자연산책"]
    }

    # 종합 summary
    all_pass = all(
        v == "PASS" or (isinstance(v, str) and v.startswith("PASS"))
        for group in [
            verdicts["theme_구분"].values(),
            [verdicts["카페투어_cafe_3개이상"]],
            verdicts["density_full_vs_standard"].values(),
            [verdicts["slot_구조_다름"]["카페투어에cafe있음"],
             verdicts["slot_구조_다름"]["맛집탐방에meal>기본meal"]],
            [verdicts["weights_theme_반영"]["판정"]],
        ]
        for v in group
    )
    verdicts["_종합"] = "PASS — 모든 기준 통과" if all_pass else "FAIL — 일부 기준 미통과"

    return {"rows": rows, "verdicts": verdicts}


def main():
    print("=" * 70)
    print("QA 진단 실행")
    print("=" * 70)

    conn = db_client.get_connection()

    # Section 1: 프론트
    print("\n[1] 프론트 payload 진단 (정적 분석)")
    s1 = section1_front_payload_check()
    for k, v in s1.items():
        print(f"\n  [{k}]")
        print(f"  {v}")

    # Section 2: 출발 기준점
    print("\n\n[2] 출발 기준점 진단")
    s2 = section2_anchor_diagnosis(conn)
    for region, info in s2.items():
        print(f"\n  [{info['display']}]")
        if not info["anchor_defined"]:
            print(f"    ANCHOR 정의 없음 → cause: {info['cause']}")
        else:
            print(f"    anchor 정의: {info['anchor_count']}개, 실사용 가능: {info['viable_count']}개")
            for a in info.get("anchors", []):
                status = "✅" if a.get("viable") else "❌"
                print(f"    {status} {a.get('display_name','?')}: "
                      f"관광지10km={a.get('tourist_10km','?')} "
                      f"식당10km={a.get('meal_10km','?')} "
                      f"카페10km={a.get('cafe_10km','?')} "
                      f"전체10km={a.get('total_10km','?')} "
                      f"15km={a.get('total_15km','?')} "
                      f"25km={a.get('total_25km','?')}")
                if a.get("excluded_reason"):
                    print(f"       제외사유: {a['excluded_reason']}")

    # Section 3: API
    print("\n\n[3] API 진단 (정적 분석)")
    s3 = section3_api_response_fields()
    for k, v in s3.items():
        print(f"\n  [{k}]")
        if isinstance(v, dict):
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"  {v}")

    # Section 4: 엔진
    print("\n\n[4] 엔진 진단 — 서울 조건별 비교")
    s4 = section4_engine_test(conn)
    headers = ["라벨", "template", "target", "actual", "카페", "식당", "관광지", "종료시각", "이동(분)", "fallback"]
    row_fmt = "{:<20} {:<10} {:>6} {:>6} {:>4} {:>4} {:>4} {:>8} {:>7} {:<6}"
    print("\n  " + row_fmt.format(*headers))
    print("  " + "-"*78)
    for r in s4:
        if r.get("error"):
            print(f"  {r['label']}: ERROR — {r['error']}")
            continue
        print("  " + row_fmt.format(
            r["label"][:20],
            str(r["template"])[:10],
            str(r["target_place_count"]),
            str(r["actual_place_count"]),
            str(r["cafe_count"]),
            str(r["meal_count"]),
            str(r["tourist_count"]),
            str(r["scheduled_end"]),
            str(r["total_travel_min"]),
            "Y" if r["radius_fallback"] else "N",
        ))
        print(f"    roles: {r['roles']}")
        print(f"    places: {r['place_names'][:3]}...")

    print("\n\n[4b] 지방 지역 엔진 진단")
    s4b = section4_engine_test_regional(conn)
    print("\n  " + row_fmt.format(*headers))
    print("  " + "-"*78)
    for r in s4b:
        if r.get("error"):
            print(f"  {r['label']}: ERROR — {r['error']}")
            continue
        print("  " + row_fmt.format(
            r["label"][:20],
            str(r["template"])[:10],
            str(r["target_place_count"]),
            str(r["actual_place_count"]),
            str(r["cafe_count"]),
            str(r["meal_count"]),
            str(r["tourist_count"]),
            str(r["scheduled_end"]),
            str(r["total_travel_min"]),
            "Y" if r["radius_fallback"] else "N",
        ))
        print(f"    roles: {r['roles']}")
        print(f"    places: {r['place_names'][:3]}...")

    # Section 5: 반경 정책
    print("\n\n[5] 도시/지방 반경 정책 진단 (정적 분석)")
    s5 = section5_radius_policy()
    for k, v in s5.items():
        print(f"\n  [{k}]: {v}")

    # Section 6: 재계산 시간 오류
    print("\n\n[6] 경로 재계산 시간 오류 진단 (정적 분석)")
    s6 = section6_recalculate_bug()
    for k, v in s6.items():
        print(f"\n  [{k}]:")
        print(f"  {v}")

    # Section 7: 수정 후 검증
    print("\n\n[7] 수정 후 검증 — theme / density / slot / weights / radius")
    s7 = section7_post_fix_verification(conn)
    vd = s7["verdicts"]
    print(f"\n  종합: {vd.get('_종합','?')}")
    print(f"\n  [theme 구분]")
    for k, v in vd.get("theme_구분", {}).items():
        print(f"    {k}: {v}")
    print(f"\n  [카페투어 카페 수] {vd.get('카페투어_cafe_3개이상','?')}")
    print(f"\n  [density full vs standard]")
    for k, v in vd.get("density_full_vs_standard", {}).items():
        print(f"    {k}: {v}")
    print(f"\n  [slot 구조]")
    for k, v in vd.get("slot_구조_다름", {}).items():
        print(f"    {k}: {v}")
    print(f"\n  [weights theme 반영]")
    for k, v in vd.get("weights_theme_반영", {}).items():
        print(f"    {k}: {v}")
    print(f"\n  [selected_radius_km]")
    for k, v in vd.get("selected_radius_km_반환", {}).items():
        print(f"    {k}: {v}")
    print("\n  [각 케이스 요약]")
    hdr = "{:<12} {:<10} {:>6} {:>6} {:>4} {:>4} {:>4} {:>8} {:>10} {}"
    print("  " + hdr.format("라벨","template","target","actual","카페","식당","관광지","종료","radius","weights_mode"))
    print("  " + "-"*90)
    for label in ["기본","카페투어","맛집탐방","자연산책","여유롭게","적당히","알차게"]:
        r = s7["rows"].get(label, {})
        if r.get("error"):
            print(f"  {label}: ERROR — {r['error']}")
            continue
        sb = r.get("selection_basis", {})
        print("  " + hdr.format(
            label,
            str(r.get("template","?"))[:10],
            str(r.get("target_place_count","?")),
            str(r.get("actual_place_count","?")),
            str(r.get("cafe_count","?")),
            str(r.get("meal_count","?")),
            str(r.get("tourist_count","?")),
            str(r.get("scheduled_end","?")),
            str(r.get("selected_radius_km","?")),
            sb.get("mode","?"),
        ))
        print(f"    roles: {r.get('roles','?')}")
        print(f"    places: {r.get('place_names','?')[:4]}")

    # 결과 저장
    output = {
        "section1_front": s1,
        "section2_anchor": {
            k: {**v, "anchors": [
                {kk: vv for kk, vv in a.items()} for a in v.get("anchors", [])
            ]} for k, v in s2.items()
        },
        "section3_api": s3,
        "section4_engine_seoul": s4,
        "section4_engine_regional": s4b,
        "section5_radius": s5,
        "section6_recalculate": s6,
        "section7_post_fix": s7,
    }

    with open("D:/travel_data_pipeline/qa_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    conn.close()
    print("\n\n진단 완료. 결과: D:/travel_data_pipeline/qa_results.json")

if __name__ == "__main__":
    main()
