"""
course_builder.py -- 1일 여행 코스 추천

진입점: build_course(conn, request) → dict
"""

import logging
import random
import re
from math import radians, sin, cos, sqrt, atan2, log1p

import psycopg2.extras

from travel_utils import estimate_travel_minutes
from tourism_belt import get_belt_info, TOURISM_BELT, is_belt_seed_name, REGION_TO_BELT_KEYS
from enrichment_service import is_institutional
from city_clusters import CITY_CLUSTERS, CITY_MODE_REGIONS, THEME_TO_CLUSTER_MOOD, CITY_MODE_SLOTS, CITY_MODE_CAFE_SLOTS, CITY_MODE_FOOD_SLOTS
from region_notices import get_option_notice, get_service_level, get_blocked_message

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

TEMPLATES = {
    "light":    [("morning", ["spot", "culture"]), ("lunch", "meal"), ("afternoon", "cafe")],
    "standard": [("morning", ["spot", "culture"]), ("lunch", "meal"), ("afternoon", ["spot", "culture"]), ("dinner", "meal")],
    "full":     [("morning", ["spot", "culture"]), ("lunch", "meal"), ("afternoon", ["spot", "culture"]), ("dinner", "meal"), ("night", ["cafe", "spot", "culture"])],
}

# ── 도시 유형별 확장 템플릿 (기본 theme 없을 때) ──────────────────────────
# large(서울): +3 → light=5, standard=6, full=7
# urban(부산 등): +2 → light=4, standard=5, full=6
# medium/rural: +1 → light=4, standard=5, full=6
_CITY_TEMPLATES: dict[str, dict[str, list]] = {
    "large": {
        "light": [
            ("morning",        ["spot", "culture"]),
            ("morning_2",      ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
        ],
        "standard": [
            ("morning",        ["spot", "culture"]),
            ("morning_2",      ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
            ("dinner",         "meal"),
        ],
        "full": [
            ("morning",        ["spot", "culture"]),
            ("morning_2",      ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
            ("dinner",         "meal"),
            ("evening",        ["spot", "culture"]),
        ],
    },
    "urban": {
        "light": [
            ("morning",        ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
        ],
        "standard": [
            ("morning",        ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
            ("dinner",         "meal"),
        ],
        "full": [
            ("morning",        ["spot", "culture"]),
            ("morning_2",      ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
            ("dinner",         "meal"),
        ],
    },
    "medium": {
        "light": [
            ("morning",        ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
        ],
        "standard": [
            ("morning",        ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
            ("dinner",         "meal"),
        ],
        "full": [
            ("morning",        ["spot", "culture"]),
            ("morning_2",      ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
            ("dinner",         "meal"),
        ],
    },
    "rural": {
        "light": [
            ("morning",        ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
        ],
        "standard": [
            ("morning",        ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
            ("dinner",         "meal"),
        ],
        "full": [
            ("morning",        ["spot", "culture"]),
            ("morning_2",      ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
            ("dinner",         "meal"),
        ],
    },
}

# theme별 slot 구조 오버라이드 (확장 버전)
THEME_SLOT_CONFIG: dict[str, dict[str, list]] = {
    "cafe": {
        "light": [
            ("morning",        ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      "cafe"),
            ("afternoon_cafe", "cafe"),
        ],
        "standard": [
            ("morning",        "cafe"),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
            ("dinner",         "cafe"),
        ],
        "full": [
            ("morning",        ["spot", "culture"]),
            ("morning_2",      "cafe"),
            ("lunch",          "meal"),
            ("afternoon",      "cafe"),
            ("afternoon_cafe", "cafe"),
            ("dinner",         "meal"),
        ],
    },
    "food": {
        "light": [
            ("morning",        ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "meal"),
        ],
        "standard": [
            ("morning",        ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "meal"),
            ("dinner",         "meal"),
        ],
        "full": [
            ("morning",        ["spot", "culture"]),
            ("morning_2",      ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "meal"),
            ("dinner",         "meal"),
        ],
    },
    "history": {
        "light": [
            ("morning",        "culture"),
            ("lunch",          "meal"),
            ("afternoon",      ["culture", "spot"]),
            ("afternoon_cafe", "cafe"),
        ],
        "standard": [
            ("morning",        "culture"),
            ("morning_2",      ["culture", "spot"]),
            ("lunch",          "meal"),
            ("afternoon",      ["culture", "spot"]),
            ("afternoon_cafe", "cafe"),
            ("dinner",         "meal"),
        ],
        "full": [
            ("morning",        "culture"),
            ("morning_2",      ["culture", "spot"]),
            ("lunch",          "meal"),
            ("afternoon",      ["culture", "spot"]),
            ("afternoon_cafe", "cafe"),
            ("dinner",         "meal"),
            ("evening",        ["culture", "spot"]),
        ],
    },
    "nature": {
        "light": [
            ("morning",        ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
        ],
        "standard": [
            ("morning",        ["spot", "culture"]),
            ("morning_2",      ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
        ],
        "full": [
            ("morning",        ["spot", "culture"]),
            ("morning_2",      ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
            ("dinner",         "meal"),
        ],
    },
    "walk": {
        "light": [
            ("morning",        ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
        ],
        "standard": [
            ("morning",        ["spot", "culture"]),
            ("morning_2",      ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
        ],
        "full": [
            ("morning",        ["spot", "culture"]),
            ("morning_2",      ["spot", "culture"]),
            ("lunch",          "meal"),
            ("afternoon",      ["spot", "culture"]),
            ("afternoon_cafe", "cafe"),
            ("dinner",         "meal"),
        ],
    },
}

SLOT_START = {
    "morning":        (9,  0),
    "morning_2":      (10, 30),  # 오전 두 번째 관광 슬롯
    "lunch":          (11, 30),
    "afternoon":      (13, 30),
    "afternoon_2":    (15,  0),  # 오후 두 번째 슬롯
    "afternoon_cafe": (15,  0),  # 오후 카페 전용 슬롯
    "dinner":         (17, 30),
    "evening":        (19,  0),  # 저녁 추가 슬롯 (dinner 계열)
    "night":          (20,  0),  # full 템플릿·카페투어 야간 슬롯
}

# 확장 슬롯 → DB visit_time_slot 매핑
SLOT_DB_MAP: dict[str, str] = {
    "morning_2":      "morning",
    "afternoon_2":    "afternoon",
    "afternoon_cafe": "afternoon",
    "evening":        "dinner",
}

WEIGHTS_DEFAULT   = {"travel_fit": 0.40, "theme_match": 0.30, "popularity_score": 0.15, "slot_fit": 0.15}
WEIGHTS_THEME     = {"travel_fit": 0.25, "theme_match": 0.50, "popularity_score": 0.15, "slot_fit": 0.10}
CITY_MODE_WEIGHTS      = {"travel_fit": 0.10, "theme_match": 0.45, "popularity_score": 0.30, "slot_fit": 0.15}
CITY_MODE_CAFE_WEIGHTS = {"travel_fit": 0.10, "theme_match": 0.55, "popularity_score": 0.20, "slot_fit": 0.15}
# cafe/food/nature 테마 활성 시 theme_match 강화 (공통 weight, CITY_MODE_CAFE_WEIGHTS 재사용)

# 혼합 슬롯 내 theme별 preferred role 우선 선택 bias
# {theme: (preferred_roles, bias_value)}
_THEME_ROLE_BIAS: dict[str, tuple] = {
    "cafe":   (frozenset({"cafe"}),             0.15),
    "food":   (frozenset({"meal"}),             0.15),
    "nature": (frozenset({"spot", "culture"}),  0.12),
}
WEIGHTS = WEIGHTS_DEFAULT  # 하위 호환용 (외부 참조 코드 보호)

# 영어 theme 키워드 → DB ai_tags Korean 태그 매핑 (theme_match 점수 계산용)
THEME_SCORE_EXPAND: dict[str, set] = {
    "nature":  {"자연", "힐링", "조용한"},
    "food":    {"음식", "맛집"},
    "cafe":    {"카페", "카페문화", "디저트"},
    "history": {"역사", "문화"},
    "urban":   {"쇼핑", "문화", "액티비티"},
    "walk":    {"자연", "힐링", "조용한"},
}

MAX_TRAVEL_MIN   = 40
MAX_TOTAL_TRAVEL = 120
MAX_RADIUS_KM    = 10
END_HOUR_LIMIT   = 22 * 60
POPULARITY_BASE  = 1000

# 후보 다양성: 상위 K개 안에서 점수 비례 가중 랜덤 선택
DIVERSITY_TOP_K  = 5

# cafe/meal 품질 보정 — rating·review_count·data_source 반영
_CAFE_MEAL_ROLES            = frozenset({"cafe", "meal"})
_CAFE_MEAL_SOURCE_BONUS     = 0.08   # naver/kakao 외부 검증 가산점 (additive)
_CAFE_MEAL_REVIEW_CAP       = 1000   # review_count log 정규화 상한
_CAFE_MEAL_RATING_MAX       = 5.0    # rating 정규화 최대값

# Tier 분리 Selection 아키텍처
TOURISM_REGION_MAX_RADIUS = 50.0   # tier1(belt_seed) 전용 확장 반경 km (지방 관광형)
TIER1_WEIGHTED_TOP_K      = 3      # tier1 가중 선택 풀 크기 (확정 픽 방지)
_NON_BELT_ANCHOR_TOP_K    = 3      # 비belt anchor 상위 K개 랜덤 선택 풀
TIER2_TIGHT_RADIUS_KM     = 8.0    # tier2 1차 탐색 반경 km
TIER2_FALLBACK_RADII      = (15.0, 20.0)  # tier2 Adaptive Fallback 단계 km
TIER2_MIN_CANDIDATES      = 2      # tier2 fallback 기준: 이 수 미만이면 반경 확장
HEURISTIC_MIN_SPEED_KMH   = 80.0   # 낙관적 직선거리 → 시간 추정 속도 (fail-fast 1차 필터용)

# spot/culture 슬롯에서 여행 코스로 부적절한 업종 필터 (이름 기반)
# 사우나·목욕·스파랜드·찜질방 등 — 관광지가 아닌 위생/레저 시설
_SPOT_UNSUITABLE_PATTERNS: tuple[str, ...] = (
    "사우나", "찜질방", "목욕탕", "스파랜드", "스파 ", "워터피아",
    "어촌계", "펜션", "리조트", "온천지구", "온천탕",
    "폰케이스", "휴대폰", "액세서리",
)

# food 테마 앵커 제외 대상: 폭포·계곡 등 외곽 자연 지형 — 인근 meal 확보 어려움
_FOOD_ANCHOR_NATURE_PATTERNS: tuple[str, ...] = (
    "폭포", "계곡", "능선", "국립공원", "도립공원",
)

# 도시 유형별 이동 프로필
LARGE_CITIES  = {"서울"}                                            # +3 슬롯 확장
URBAN_CITIES  = {"부산", "대구", "대전", "광주", "인천"}            # +2 슬롯 확장
MEDIUM_CITIES = {"울산", "세종", "경기", "충북", "충남"}

MOBILITY_PROFILE: dict[str, dict] = {
    "large":  {"max_radius": 10, "max_travel": 40, "max_total": 150, "meal_fb_r": 15, "meal_fb_t": 50},
    "urban":  {"max_radius": 10, "max_travel": 40, "max_total": 120, "meal_fb_r": 15, "meal_fb_t": 50},
    "medium": {"max_radius": 12, "max_travel": 45, "max_total": 150, "meal_fb_r": 18, "meal_fb_t": 55},
    "rural":  {"max_radius": 15, "max_travel": 60, "max_total": 180, "meal_fb_r": 25, "meal_fb_t": 70},
}

# regional 코스 파라미터 — zone 검증 radius와 동일하게 유지
REGIONAL_STEP_TRAVEL = {10.0: 50, 15.0: 60, 25.0: 60}
REGIONAL_STEP_MEAL_FB = {10.0: 15.0, 15.0: 25.0, 25.0: 30.0}
REGIONAL_MEAL_FB_TRAVEL_MIN = 60
REGIONAL_MAX_TOTAL_TRAVEL   = 180

# ---------------------------------------------------------------------------
# Diversity 패널티 상수
# ---------------------------------------------------------------------------
# T1 후보가 기선택 장소와 동일 (category_id + visit_role) → 25% 감점
DIVERSITY_SAME_CAT_PENALTY   = 0.25
# 기선택 장소와 직선거리 600m 이내 = 동일 클러스터 → 35% 감점
# (대포항/대포항전망대 같이 같은 단지 내 복수 레코드 차단; 경주 주요 명소 간 ~900m는 미적용)
DIVERSITY_CLUSTER_RADIUS_KM  = 0.6
DIVERSITY_CLUSTER_PENALTY    = 0.35

# urban/anchor 기반 단계별 radius → 최대 이동시간 매핑
URBAN_STEP_TRAVEL = {5: 25, 10: 40, 15: 50, 18: 55, 25: 60}

ADJACENT_SLOTS = {
    "morning":        {"lunch", "morning"},
    "morning_2":      {"morning", "lunch"},
    "lunch":          {"morning", "afternoon"},
    "afternoon":      {"lunch", "dinner"},
    "afternoon_2":    {"afternoon", "dinner"},
    "afternoon_cafe": {"afternoon", "dinner"},
    "dinner":         {"afternoon", "night"},
    "evening":        {"dinner", "night"},
    "night":          {"dinner"},
}

# 늦은 출발 전용 slot 구성 (SOT §18)
# - meal은 포함하지 않음 (dinner_included=True 옵션으로 20시대만 허용)
# - 기존 DB slot("afternoon","dinner") 재사용 → 후보 쿼리 그대로 동작
LATE_TEMPLATES = {
    "late_20": [                                    # 20:00 ≤ start < 21:00
        ("afternoon", ["spot", "culture"]),
        ("dinner",    "cafe"),
    ],
    "late_21": [                                    # 21:00 ≤ start < 22:00
        ("dinner", ["spot", "culture"]),
    ],
}


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _get_city_type(region: str) -> str:
    if region in LARGE_CITIES:
        return "large"
    if region in URBAN_CITIES:
        return "urban"
    if region in MEDIUM_CITIES:
        return "medium"
    return "rural"


def _slot_db_name(slot: str) -> str:
    return SLOT_DB_MAP.get(slot, slot)


def _is_unsuitable_spot(name: str) -> bool:
    """spot/culture 슬롯에 부적절한 업종 여부 (사우나·목욕·스파랜드 등 이름 기반)."""
    n = name.replace(" ", "")
    return any(kw.replace(" ", "") in n for kw in _SPOT_UNSUITABLE_PATTERNS)


def _is_food_theme_unsuitable_anchor(name: str) -> bool:
    """food 테마 한정 앵커 제외: 폭포·계곡 등 외곽 자연 지형은 인근 meal 확보 어려움."""
    n = name.replace(" ", "")
    return any(kw in n for kw in _FOOD_ANCHOR_NATURE_PATTERNS)


def _weighted_choice(scored: list, k: int = DIVERSITY_TOP_K) -> tuple:
    """상위 k개 후보 안에서 점수 비례 가중 랜덤 선택.

    scored: [(score, travel_min, dist_km, components, place), ...]  — 내림차순 정렬 가정.
    """
    pool = scored[:k]
    if len(pool) == 1:
        return pool[0]
    weights = [max(item[0], 0.001) for item in pool]
    return random.choices(pool, weights=weights, k=1)[0]


def _heuristic_travel_min(dist_km: float) -> float:
    """직선거리 기반 낙관적 이동 시간 하한 추정 — fail-fast 1차 필터 전용.

    HEURISTIC_MIN_SPEED_KMH(80km/h)를 써서 항상 실제보다 빠르게 추정한다.
    이 값이 한도를 넘으면 어떤 도로로 가도 불가능 → 즉시 탈락.
    """
    return dist_km * 60.0 / HEURISTIC_MIN_SPEED_KMH


def _estimate_rural_travel_min(dist_km: float) -> int:
    """지방/관광지형 이동 시간 추정 (국도·고속화도로 혼용 기준).

    estimate_travel_minutes() 는 서울 도심 속도로 보정되어 있어
    태안·안면도 같은 지방 관광지에서 50km = 350min 으로 과대산정된다.
    이 함수는 현실적인 지방 도로 속도를 적용한다.
    """
    from math import ceil
    d = max(dist_km, 0.05)
    if d < 2.0:
        speed_kmh, factor = 30.0, 1.20   # 마을·해안 도로
    elif d < 10.0:
        speed_kmh, factor = 50.0, 1.20   # 지방도
    else:
        speed_kmh, factor = 70.0, 1.10   # 국도·고속화도로
    return max(5, ceil((d / speed_kmh) * 60 * factor))


def _is_tier1(region: str, name: str, lat: float | None = None, lon: float | None = None) -> bool:
    """이름 매칭 기준 tier1(belt_seed) 여부 판별. lat/lon 제공 시 서브벨트 자동 분기."""
    return is_belt_seed_name(region, name, lat, lon)


def _weighted_choice_tiered(scored: list, top_k: int, max_leg_time: float) -> tuple:
    """이동 시간 페널티를 포함한 Top-K 가중치 선택 (확정 픽 금지).

    scored: [(score, travel_min, dist_km, components, place), ...] — 내림차순 정렬 가정.
    이동 시간이 길수록 weight 가 줄어 동선이 꼬이지 않는 후보가 우선된다.
    """
    pool = scored[:top_k]
    if len(pool) == 1:
        return pool[0]
    weights = []
    for item in pool:
        s, travel_min, *_ = item
        travel_penalty = travel_min / max(max_leg_time, 1.0)
        weights.append(max(s * (1.0 - 0.3 * travel_penalty), 0.001))
    return random.choices(pool, weights=weights, k=1)[0]


def _diversity_penalty(
    score: float,
    place: dict,
    selected: list,
    is_tier1: bool,
    components: dict,
) -> tuple[float, dict]:
    """
    다양성 패널티 적용 — 이미 선택된 장소들과의 중복/유사성 기반 감점.

    1. [Cluster] 기선택 장소와 DIVERSITY_CLUSTER_RADIUS_KM(0.6km) 이내
       → DIVERSITY_CLUSTER_PENALTY(35%) 감점
       동일 단지/구역 내 복수 레코드 차단 (대포항/대포항전망대 등)

    2. [Category] T1 후보 한정, 기선택 장소와 (category_id + visit_role) 동일
       → DIVERSITY_SAME_CAT_PENALTY(25%) 감점
       같은 종류 T1 연속 선택 억제 (해변→해변, 사찰→사찰 등)

    패널티는 additive, 최대 0.55(55%) 상한.
    """
    lat  = place.get("latitude")  or 0.0
    lon  = place.get("longitude") or 0.0
    cat  = place.get("category_id")
    role = place.get("visit_role")

    cluster_pen = 0.0
    cat_pen     = 0.0
    cluster_near: list[str] = []

    for sel in selected:
        sel_lat = sel.get("latitude")  or 0.0
        sel_lon = sel.get("longitude") or 0.0

        # ── 1. Cluster penalty ────────────────────────────────────────
        if lat and lon and sel_lat and sel_lon:
            d = _haversine(lat, lon, sel_lat, sel_lon)
            if d <= DIVERSITY_CLUSTER_RADIUS_KM:
                cluster_pen = max(cluster_pen, DIVERSITY_CLUSTER_PENALTY)
                cluster_near.append(f"{sel['name']}({d:.2f}km)")

        # ── 2. Category diversity penalty (T1 전용) ───────────────────
        if is_tier1 and cat and role:
            if sel.get("category_id") == cat and sel.get("visit_role") == role:
                cat_pen = max(cat_pen, DIVERSITY_SAME_CAT_PENALTY)

    total_pen = min(cluster_pen + cat_pen, 0.55)
    if total_pen == 0.0:
        return score, components

    adjusted  = score * (1.0 - total_pen)
    new_comp  = {
        **components,
        "diversity_penalty": round(total_pen, 4),
        "final_score":       round(adjusted, 4),
    }
    if cluster_near:
        new_comp["cluster_near"]  = cluster_near
    if cat_pen > 0.0:
        new_comp["same_cat_role"] = f"cat={cat}/role={role}"

    logger.debug(
        "diversity_penalty=%.2f (cluster=%.2f cat=%.2f) %s near=%s",
        total_pen, cluster_pen, cat_pen, place["name"], cluster_near,
    )
    return adjusted, new_comp


def _get_weights(themes: list) -> dict:
    return WEIGHTS_THEME if themes else WEIGHTS_DEFAULT


def _parse_start_hour(start_time: str | None) -> int | None:
    """'오늘 20:00', '내일 14:30', '20:00' 등에서 출발 hour 추출. 파싱 실패 시 None."""
    if not start_time:
        return None
    m = re.search(r'(\d{1,2}):\d{2}', start_time)
    return int(m.group(1)) if m else None


def _resolve_slots(template: str, start_time: str | None, request: dict, city_type: str = "rural") -> list | None:
    """
    start_time 기준 실제 사용할 slot 목록을 반환.
    22:00 이상이면 None (생성 불가).

    늦은 출발 slot 정책 (SOT §18):
    - start < 20:00         : _CITY_TEMPLATES[city_type][template]
    - 20:00 ≤ start < 21:00 : LATE_TEMPLATES["late_20"] (meal 제외)
                               단 request["dinner_included"]=True 시 meal 허용
    - 21:00 ≤ start < 22:00 : LATE_TEMPLATES["late_21"] (1 slot 초소형)
    - start >= 22:00        : None (생성 불가)
    """
    hour = _parse_start_hour(start_time)
    if hour is None or hour < 20:
        return list(_CITY_TEMPLATES[city_type][template])
    if hour >= 22:
        return None
    if hour >= 21:
        return list(LATE_TEMPLATES["late_21"])
    # 20:00 ≤ hour < 21:00
    if request.get("dinner_included"):
        return [("afternoon", ["spot", "culture"]), ("dinner", "meal"), ("dinner", "cafe")]
    return list(LATE_TEMPLATES["late_20"])


def _resolve_theme_slots(template: str, themes: list, start_time: str | None, request: dict, city_type: str = "rural") -> list | None:
    """
    theme 우선으로 slot 구성 반환. theme 매핑 없으면 기본 _resolve_slots 위임.

    - cafe theme: THEME_SLOT_CONFIG["cafe"] 사용 (카페 3개 보장 구조)
    - food theme: THEME_SLOT_CONFIG["food"] 사용 (meal 슬롯 증가)
    - 늦은 출발(≥20:00)은 기존 _resolve_slots 로직 그대로 사용
    """
    hour = _parse_start_hour(start_time)
    if hour is not None and hour >= 20:
        return _resolve_slots(template, start_time, request, city_type)

    for t in themes:
        if t in THEME_SLOT_CONFIG and template in THEME_SLOT_CONFIG[t]:
            return list(THEME_SLOT_CONFIG[t][template])

    return _resolve_slots(template, start_time, request, city_type)


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    la1, lo1, la2, lo2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = la2 - la1
    dlon = lo2 - lo1
    a = sin(dlat / 2) ** 2 + cos(la1) * cos(la2) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _slot_fit(place_slots: list, target_slot: str) -> float:
    db_slot = _slot_db_name(target_slot)
    if db_slot in place_slots:
        return 1.0
    if any(s in place_slots for s in ADJACENT_SLOTS.get(target_slot, set())):
        return 0.5
    return 0.0


def _score(
    place: dict,
    prev_coord: tuple | None,
    user_themes: list,
    user_companion: str,
    target_slot: str,
    pop_base: float,
    max_radius_km: float = MAX_RADIUS_KM,
    max_leg_time: int    = MAX_TRAVEL_MIN,
    relax_slot: bool     = False,
    weights: dict | None = None,
    rural_travel: bool   = False,
) -> tuple | None:
    """(score, travel_min, dist_km, components) 반환. Hard filter 위반 시 None.

    max_radius_km : km 기반 보조 필터 (tier별 반경 제어).
    max_leg_time  : 이동 시간(min) 기반 주 필터 — Req 3: 시간 기준 판단.
    rural_travel  : True 이면 지방도로 속도 모델 사용 (태안 등 관광지형).
    relax_slot    : True 이면 slot_fit=0 을 0.5 로 보정 (cafe_tour 용).
    weights       : 미지정 시 WEIGHTS_DEFAULT 사용.

    2-Stage 필터 (Req 3):
      Stage 1 — heuristic: 낙관적 속도로 계산해도 한도 초과 → 즉시 탈락
      Stage 2 — precise  : 실제 도로 속도 모델로 정밀 검증
    """

    sf = _slot_fit(place["visit_time_slot"] or [], target_slot)
    if relax_slot and sf == 0.0:
        sf = 0.5  # cafe는 슬롯 제약 없이 방문 가능
    if sf == 0.0:
        return None

    travel_min     = 0
    distance_score = 1.0
    dist_km        = 0.0
    if prev_coord:
        dist_km = _haversine(prev_coord[0], prev_coord[1],
                             place["latitude"], place["longitude"])
        # Stage 1: heuristic 조기 탈락 (낙관적 속도로도 한도 초과)
        if _heuristic_travel_min(dist_km) > max_leg_time:
            return None
        # Stage 2: km 보조 필터
        if dist_km > max_radius_km:
            return None
        # Stage 3: 도로 속도 모델 정밀 검증
        travel_min = (
            _estimate_rural_travel_min(dist_km) if rural_travel
            else estimate_travel_minutes(dist_km)
        )
        if travel_min >= max_leg_time:
            return None
        distance_score = 1.0 - (travel_min / max_leg_time)

    tags         = place["ai_tags"] or {}
    place_themes = set(tags.get("themes", []) + tags.get("mood", []))
    companions   = set(tags.get("companion", []))
    # 영어 theme 키워드를 Korean DB 태그로 확장해 theme_match 계산
    expanded_user = set(user_themes)
    for t in user_themes:
        expanded_user.update(THEME_SCORE_EXPAND.get(t, set()))
    matched      = len(expanded_user & place_themes)
    theme_score  = min(matched / max(len(user_themes), 1), 1.0)
    if user_companion in companions:
        theme_score = min(theme_score + 0.2, 1.0)

    vc_score  = min((place["view_count"] or 0) / max(pop_base, 1), 1.0)
    pop_score = vc_score

    quality_bonus = 0.0
    role = place.get("visit_role", "")
    if role in _CAFE_MEAL_ROLES:
        # rating: 0–5 → 0–1
        rating_sc = min((place.get("rating") or 0.0) / _CAFE_MEAL_RATING_MAX, 1.0)
        # review_count: log scale, cap at _CAFE_MEAL_REVIEW_CAP
        review_sc = min(log1p(place.get("review_count") or 0) / log1p(_CAFE_MEAL_REVIEW_CAP), 1.0)
        # pop_score: view_count + rating + review_count 통합
        pop_score = 0.4 * vc_score + 0.3 * rating_sc + 0.3 * review_sc
        # data_source: naver/kakao 외부 검증 가산점
        source = (place.get("data_source") or "").lower()
        if "naver" in source or "kakao" in source:
            quality_bonus = _CAFE_MEAL_SOURCE_BONUS

    w = weights or WEIGHTS_DEFAULT
    score = (
        w["travel_fit"]           * distance_score
        + w["theme_match"]        * theme_score
        + w["popularity_score"]   * pop_score
        + w["slot_fit"]           * sf
        + quality_bonus
    )
    components = {
        "travel_fit":         round(distance_score, 4),
        "theme_match":        round(theme_score, 4),
        "popularity_score":   round(pop_score, 4),
        "slot_fit":           round(sf, 4),
        "quality_bonus":      round(quality_bonus, 4),
        "penalty_multiplier": 1.0,
        "final_score":        round(score, 4),
    }
    return score, travel_min, dist_km, components


def _fetch_candidates(
    conn, region: str, role: str | list, slot: str,
    zone_center: tuple | None = None, zone_radius_km: float | None = None,
    relax_slot: bool = False,
    themes: list | None = None,
    pre_filter_radius_km: float | None = None,
    belt_seed_radius_km: float | None = None,
    proximity_center: tuple | None = None,
    proximity_radius_km: float = 10.0,
    proximity_min_count: int = 20,
) -> list:
    """후보 장소 조회.

    relax_slot=True          : visit_time_slot 제약 생략 (cafe_tour 카페 슬롯용).
    themes                   : 후보 조회 단계에서 theme 우선 후보군 구성.
    pre_filter_radius_km     : zone_radius_km 미지정 시 SQL-level 거리 pre-filter.
    belt_seed_radius_km      : tier1 belt_seed 전용 SQL 확장 반경 (TOURISM_REGION_MAX_RADIUS).
                               일반 후보의 zone_radius_km 과 독립적으로 적용.
    """
    roles = role if isinstance(role, list) else [role]
    params = {"region": region, "roles": roles, "slot": _slot_db_name(slot)}
    zone_clause = ""
    # hard zone (regional 모드) 우선, 없으면 soft pre-filter 적용
    effective_r = zone_radius_km or pre_filter_radius_km
    if zone_center and effective_r:
        zone_clause = """
          AND (6371.0 * 2 * ASIN(SQRT(
              POWER(SIN((RADIANS(latitude) - RADIANS(%(zc_lat)s)) / 2), 2) +
              COS(RADIANS(%(zc_lat)s)) * COS(RADIANS(latitude)) *
              POWER(SIN((RADIANS(longitude) - RADIANS(%(zc_lon)s)) / 2), 2)
          ))) <= %(zone_radius_km)s"""
        params["zc_lat"]        = zone_center[0]
        params["zc_lon"]        = zone_center[1]
        params["zone_radius_km"] = effective_r

    slot_clause = "" if relax_slot else "AND visit_time_slot @> ARRAY[%(slot)s]::varchar[]"

    def _exec(extra_where: str = "", limit: int = 50) -> list:
        sql = f"""
            SELECT place_id, name, visit_role, estimated_duration,
                   latitude, longitude, view_count, ai_tags, visit_time_slot,
                   rating, review_count, data_source, first_image_url,
                   ai_summary, overview, category_id
            FROM places
            WHERE region_1 = %(region)s
              AND category_id IN (12, 14, 39)
              AND visit_role = ANY(%(roles)s)
              {slot_clause}
              AND is_active = TRUE
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL{zone_clause}{extra_where}
            ORDER BY view_count DESC NULLS LAST
            LIMIT {limit}
        """
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]

        if not proximity_center or proximity_min_count <= 0 or limit <= 0:
            return rows

        near_limit = min(proximity_min_count, limit)
        near_params = {
            **params,
            "pc_lat": proximity_center[0],
            "pc_lon": proximity_center[1],
            "proximity_radius_km": proximity_radius_km,
        }
        near_sql = f"""
            SELECT place_id, name, visit_role, estimated_duration,
                   latitude, longitude, view_count, ai_tags, visit_time_slot,
                   rating, review_count, data_source, first_image_url,
                   ai_summary, overview, category_id
            FROM places
            WHERE region_1 = %(region)s
              AND category_id IN (12, 14, 39)
              AND visit_role = ANY(%(roles)s)
              {slot_clause}
              AND is_active = TRUE
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL{zone_clause}{extra_where}
              AND (6371.0 * 2 * ASIN(SQRT(
                  POWER(SIN((RADIANS(latitude) - RADIANS(%(pc_lat)s)) / 2), 2) +
                  COS(RADIANS(%(pc_lat)s)) * COS(RADIANS(latitude)) *
                  POWER(SIN((RADIANS(longitude) - RADIANS(%(pc_lon)s)) / 2), 2)
              ))) <= %(proximity_radius_km)s
            ORDER BY
              (6371.0 * 2 * ASIN(SQRT(
                  POWER(SIN((RADIANS(latitude) - RADIANS(%(pc_lat)s)) / 2), 2) +
                  COS(RADIANS(%(pc_lat)s)) * COS(RADIANS(latitude)) *
                  POWER(SIN((RADIANS(longitude) - RADIANS(%(pc_lon)s)) / 2), 2)
              ))) ASC,
              view_count DESC NULLS LAST
            LIMIT {near_limit}
        """
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(near_sql, near_params)
            near_rows = [dict(r) for r in cur.fetchall()]

        merged = near_rows[:]
        used = {r["place_id"] for r in merged}
        for row in rows:
            if row["place_id"] not in used:
                merged.append(row)
                used.add(row["place_id"])
            if len(merged) >= limit:
                break
        return merged

    # nature theme: ai_tags 자연/힐링 태그 장소 우선 조회, 부족 시 일반 풀 합산
    result: list | None = None
    if themes and "nature" in themes and any(r in roles for r in ("spot", "culture")):
        nature_where = (
            "\n          AND (ai_tags->'themes' @> '[\"자연\"]'::jsonb"
            "\n           OR ai_tags->'themes' @> '[\"힐링\"]'::jsonb"
            "\n           OR ai_tags->'mood' @> '[\"조용한\"]'::jsonb)"
        )
        primary = _exec(extra_where=nature_where, limit=40)
        if len(primary) >= 3:
            if len(primary) < 20:
                general = _exec(limit=50)
                used = {r["place_id"] for r in primary}
                primary += [r for r in general if r["place_id"] not in used]
            result = primary

    # history theme: 역사/문화 태그 장소 우선 조회
    if result is None and themes and "history" in themes and any(r in roles for r in ("spot", "culture")):
        history_where = (
            "\n          AND (ai_tags->'themes' @> '[\"역사\"]'::jsonb"
            "\n           OR ai_tags->'themes' @> '[\"문화\"]'::jsonb)"
        )
        primary = _exec(extra_where=history_where, limit=40)
        if len(primary) >= 2:
            if len(primary) < 20:
                general = _exec(limit=50)
                used = {r["place_id"] for r in primary}
                primary += [r for r in general if r["place_id"] not in used]
            result = primary

    # relax_slot: cafe 역할 슬롯은 view_count 상위 150개로 넓은 후보풀 확보
    if result is None and relax_slot:
        result = _exec(limit=150)

    # food theme: meal 슬롯은 visit_time_slot 제약 없이(slot_clause 이미 비어있으면 무효) 넓은 후보풀
    if result is None and themes and "food" in themes and "meal" in roles:
        result = _exec(limit=80)

    if result is None:
        result = _exec()

    # TOURISM_BELT 시드 장소 보강: LIMIT 50 우회, belt_seed_radius_km 우선 적용
    if region in REGION_TO_BELT_KEYS and any(r in roles for r in ("spot", "culture")):
        seed_rows = _fetch_belt_seed_candidates(
            conn, region, roles,
            zone_center=zone_center,
            zone_radius_km=zone_radius_km,
            pre_filter_radius_km=pre_filter_radius_km,
            override_radius_km=belt_seed_radius_km,
        )
        if seed_rows:
            used = {r["place_id"] for r in result}
            result = result + [r for r in seed_rows if r["place_id"] not in used]

    return result


def _fetch_belt_seed_candidates(
    conn, region: str, roles: list,
    zone_center: tuple | None = None,
    zone_radius_km: float | None = None,
    pre_filter_radius_km: float | None = None,
    override_radius_km: float | None = None,
) -> list:
    """TOURISM_BELT 시드 이름과 일치하는 DB 장소 별도 조회 (LIMIT 50 우회용).

    override_radius_km : tier1_max_radius 등 확장 반경 — zone_radius_km 보다 우선.
    반환된 후보는 기존 풀과 중복 제거 후 합산되며,
    거리/슬롯 hard filter 및 belt_boost 가산은 호출부(_score)에서 동일하게 처리된다.
    """
    belt_keys  = REGION_TO_BELT_KEYS.get(region, [region])
    seed_names = [s["name"] for k in belt_keys for s in TOURISM_BELT.get(k, [])]
    if not seed_names:
        return []
    params: dict = {"region": region, "roles": roles, "seed_names": seed_names}
    zone_clause = ""
    effective_r = override_radius_km or zone_radius_km or pre_filter_radius_km
    if zone_center and effective_r:
        zone_clause = """
          AND (6371.0 * 2 * ASIN(SQRT(
              POWER(SIN((RADIANS(latitude) - RADIANS(%(zc_lat)s)) / 2), 2) +
              COS(RADIANS(%(zc_lat)s)) * COS(RADIANS(latitude)) *
              POWER(SIN((RADIANS(longitude) - RADIANS(%(zc_lon)s)) / 2), 2)
          ))) <= %(zone_radius_km)s"""
        params["zc_lat"]         = zone_center[0]
        params["zc_lon"]         = zone_center[1]
        params["zone_radius_km"] = effective_r
    sql = f"""
        SELECT place_id, name, visit_role, estimated_duration,
               latitude, longitude, view_count, ai_tags, visit_time_slot,
               rating, review_count, data_source, first_image_url,
               ai_summary, overview, category_id
        FROM places
        WHERE region_1 = %(region)s
          AND category_id IN (12, 14, 39)
          AND visit_role = ANY(%(roles)s)
          AND is_active = TRUE
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND name = ANY(%(seed_names)s){zone_clause}
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def _region_centroid(conn, region: str, roles: list) -> tuple[float, float] | None:
    """지역 내 전체 후보군의 중심 좌표 (avg lat, avg lon) 반환."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT AVG(latitude), AVG(longitude)
            FROM places
            WHERE region_1 = %(region)s
              AND category_id IN (12, 14, 39)
              AND visit_role = ANY(%(roles)s)
              AND is_active = TRUE
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
        """, {"region": region, "roles": roles})
        row = cur.fetchone()
    if row and row[0] is not None:
        return float(row[0]), float(row[1])
    return None


_MIN_ANCHOR_CANDIDATES  = 5  # 앵커 반경 내 최소 유효 후보 수 (전체)
_MIN_ANCHOR_MEAL        = 1  # meal 슬롯 충족 최소 후보 수
_MIN_ANCHOR_CAFE        = 1  # cafe 슬롯 충족 최소 후보 수


def _count_nearby_candidates(conn, region: str, lat: float, lon: float, radius_km: float) -> dict:
    """앵커 기준 반경 내 활성 장소 수 반환 — role별 분리 (viability 검증용)."""
    sql = """
        SELECT
            COUNT(*)                                         AS total,
            COUNT(*) FILTER (WHERE visit_role = 'meal')     AS meal,
            COUNT(*) FILTER (WHERE visit_role = 'cafe')     AS cafe
        FROM places
        WHERE region_1 = %(region)s
          AND category_id IN (12, 14, 39)
          AND is_active = TRUE
          AND latitude IS NOT NULL AND longitude IS NOT NULL
          AND (6371.0 * 2 * ASIN(SQRT(
              POWER(SIN((RADIANS(latitude) - RADIANS(%(lat)s)) / 2), 2) +
              COS(RADIANS(%(lat)s)) * COS(RADIANS(latitude)) *
              POWER(SIN((RADIANS(longitude) - RADIANS(%(lon)s)) / 2), 2)
          ))) <= %(radius_km)s
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"region": region, "lat": lat, "lon": lon, "radius_km": radius_km})
        row = cur.fetchone()
    if row is None:
        return {"total": 0, "meal": 0, "cafe": 0}
    return {"total": int(row[0]), "meal": int(row[1]), "cafe": int(row[2])}


def _select_city_cluster(region: str, themes: list, zone_center: tuple | None) -> dict | None:
    """zone_center 또는 theme 기반으로 서울 클러스터 선택."""
    clusters = CITY_CLUSTERS.get(region)
    if not clusters:
        return None
    if zone_center:
        clat, clon = zone_center
        return min(clusters, key=lambda c: _haversine(clat, clon, c["center"][0], c["center"][1]))
    preferred_moods: set[str] = set()
    for t in themes:
        preferred_moods.update(THEME_TO_CLUSTER_MOOD.get(t, []))
    if preferred_moods:
        matched = [c for c in clusters if set(c["mood"]) & preferred_moods]
        if matched:
            return random.choice(matched)
    return random.choice(clusters)


_DESCRIPTION_TEMPLATES: dict[str, str] = {
    "cafe":    "{location}에서 감성 카페와 여유로운 시간을 즐기는 코스입니다.",
    "food":    "{location}의 인기 맛집을 중심으로 구성된 식도락 코스입니다.",
    "nature":  "{location}의 자연 풍경과 산책을 즐기는 힐링 코스입니다.",
    "healing": "{location}의 여유롭고 편안한 분위기를 즐기는 힐링 코스입니다.",
    "history": "{location}의 유서 깊은 역사 명소를 따라 걷는 코스입니다.",
    "urban":   "{location}에서 도심의 볼거리와 즐길 거리를 담은 코스입니다.",
    "walk":    "{location}에서 여유롭게 걷고 즐기는 코스입니다.",
}
_DESCRIPTION_PRIORITY = ["cafe", "food", "nature", "healing", "history", "urban", "walk"]


def _build_description(region: str, themes: list, city_cluster: dict | None) -> str:
    """region + theme 기반 1문장 코스 설명 생성."""
    location = city_cluster["name"] if city_cluster else region
    for theme in _DESCRIPTION_PRIORITY:
        if theme in (themes or []):
            return _DESCRIPTION_TEMPLATES[theme].format(location=location)
    return f"{location}의 매력을 한껏 느낄 수 있는 코스입니다."


_SPOT_DESCRIPTION_TEMPLATES: dict[str, list[str]] = {
    "beach": [
        "{name}{josa} 바다 풍경을 따라 가볍게 머물기 좋은 해안 명소입니다.",
        "{name}{josa} 물가 산책과 사진 촬영을 함께 즐기기 좋은 장소입니다.",
        "{name}{josa} 탁 트인 해안 분위기를 느끼며 쉬어가기 좋은 관광지입니다.",
    ],
    "nature": [
        "{name}{josa} 자연 풍경을 가까이에서 느끼며 산책하기 좋은 명소입니다.",
        "{name}{josa} 계절마다 다른 풍경을 만날 수 있는 여유로운 자연 코스입니다.",
        "{name}{josa} 주변 경관을 감상하며 잠시 쉬어가기 좋은 야외 관광지입니다.",
    ],
    "culture_history": [
        "{name}{josa} 지역의 이야기와 문화적 흔적을 함께 살펴볼 수 있는 장소입니다.",
        "{name}{josa} 역사와 전시 요소를 따라 차분히 둘러보기 좋은 문화 명소입니다.",
        "{name}{josa} 지역의 분위기와 시대적 배경을 느낄 수 있는 탐방지입니다.",
    ],
    "general": [
        "{name}{josa} 주변 일정과 함께 들르기 좋은 지역 명소입니다.",
        "{name}{josa} 이동 동선 안에서 부담 없이 둘러보기 좋은 관광지입니다.",
        "{name}{josa} 코스 중간에 들러 지역 분위기를 느끼기 좋은 장소입니다.",
    ],
}


def _has_final_consonant(text: str) -> bool:
    """Return whether the last Hangul syllable has a batchim."""
    for ch in reversed((text or "").strip()):
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            return (code - 0xAC00) % 28 != 0
        if ch.isalnum():
            return False
    return False


def _eun_neun(text: str) -> str:
    return "은" if _has_final_consonant(text) else "는"


def _clean_overview_text(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _summarize_overview(text: str, max_len: int = 180) -> str:
    cleaned = _clean_overview_text(text)
    if not cleaned:
        return ""

    sentences = re.split(r"(?<=[.!?。！？다요음함됨임])\s+", cleaned)
    summary = " ".join(s.strip() for s in sentences[:2] if s.strip())
    if not summary:
        summary = cleaned
    if len(summary) > max_len:
        summary = summary[:max_len].rsplit(" ", 1)[0].rstrip("., ") + "..."
    elif summary and not re.search(r"[.!?。！？…]$", summary):
        summary = summary.rstrip("., ") + "..."
    return summary


def _spot_description_category(place: dict) -> str:
    text = " ".join(
        str(place.get(key) or "")
        for key in ("name", "overview", "ai_summary")
    )
    if re.search(r"해수욕장|해변|해안|바다|항구|선착장|방파제", text):
        return "beach"
    if re.search(r"산|폭포|계곡|숲|호수|강|하천|공원|수목원|정원|동굴|전망대|둘레길|자연|습지", text):
        return "nature"
    if place.get("visit_role") == "culture" or re.search(
        r"박물관|미술관|전시|갤러리|기념관|문화|역사|유적|사찰|절|궁|성곽|향교|서원|고택|생가",
        text,
    ):
        return "culture_history"
    return "general"


def _template_index(name: str, size: int) -> int:
    return sum(ord(ch) for ch in (name or "")) % size


def _build_place_description(place: dict) -> str:
    name = (place.get("name") or "이 장소").strip()
    role = place.get("visit_role", "")

    if role in {"spot", "culture"}:
        description = _summarize_overview(place.get("overview") or "")
        if not description:
            category = _spot_description_category(place)
            templates = _SPOT_DESCRIPTION_TEMPLATES[category]
            template = templates[_template_index(name, len(templates))]
            description = template.format(name=name, josa=_eun_neun(name))
    else:
        role_label = {
            "meal": "지역의 맛을 즐기기 좋은 식사 장소",
            "cafe": "잠시 쉬어가기 좋은 카페",
        }.get(role, "코스 중간에 들르기 좋은 장소")
        description = (
            _summarize_overview(place.get("overview") or "") or
            (place.get("ai_summary") or "").strip() or
            f"{name}{_eun_neun(name)} {role_label}입니다."
        )

    if len(description) < 20:
        description = f"{name}{_eun_neun(name)} 코스 중간에 들러 분위기를 느끼기 좋은 장소입니다."
    if len(description) > 200:
        description = description[:197].rstrip() + "..."
    return description


def _select_anchor(
    conn, region: str, themes: list, first_role: str | list,
    zone_center: tuple | None = None, zone_radius_km: float | None = None,
    exclude_ids: set | None = None,
) -> dict | None:
    """
    중심점 기반 앵커 선택.

    1. 지역 전체 후보군의 centroid 계산
    2. view_count 상위 30개 후보 조회
    3. centroid와 가장 가까운 순으로 정렬
    4. 테마 매치 장소 우선, 없으면 centroid 최근접 장소 반환

    view_count=0 환경에서도 지리적으로 안정적인 앵커를 보장한다.
    meal / cafe는 TEMPLATES 첫 슬롯에 오지 않도록 설계 -- 앵커 금지 조건은 호출부에서 보장.
    """
    roles = first_role if isinstance(first_role, list) else [first_role]

    # zone_center가 있으면 그것을 centroid로 사용, 없으면 region centroid 계산
    centroid = zone_center if zone_center else _region_centroid(conn, region, roles)

    params = {"region": region, "roles": roles}
    zone_clause = ""
    if zone_center and zone_radius_km:
        # regional 모드: 고정 zone 반경 적용
        zone_clause = """
          AND (6371.0 * 2 * ASIN(SQRT(
              POWER(SIN((RADIANS(latitude) - RADIANS(%(zc_lat)s)) / 2), 2) +
              COS(RADIANS(%(zc_lat)s)) * COS(RADIANS(latitude)) *
              POWER(SIN((RADIANS(longitude) - RADIANS(%(zc_lon)s)) / 2), 2)
          ))) <= %(zone_radius_km)s"""
        params["zc_lat"]        = zone_center[0]
        params["zc_lon"]        = zone_center[1]
        params["zone_radius_km"] = zone_radius_km
    elif zone_center:
        # urban/anchor 모드: zone_center 기준 소프트 프리필터(30km) — 부여 등 지방 도시에서
        # view_count=0 전체를 place_id 순 30개로 가져오면 anchor가 엉뚱한 지역으로 잡히는 문제 방지
        zone_clause = """
          AND (6371.0 * 2 * ASIN(SQRT(
              POWER(SIN((RADIANS(latitude) - RADIANS(%(zc_lat)s)) / 2), 2) +
              COS(RADIANS(%(zc_lat)s)) * COS(RADIANS(latitude)) *
              POWER(SIN((RADIANS(longitude) - RADIANS(%(zc_lon)s)) / 2), 2)
          ))) <= %(zone_radius_km)s"""
        params["zc_lat"]        = zone_center[0]
        params["zc_lon"]        = zone_center[1]
        params["zone_radius_km"] = 30.0  # 소프트 프리필터: 30km

    sql = f"""
        SELECT place_id, name, visit_role, estimated_duration,
               latitude, longitude, view_count, ai_tags, visit_time_slot,
               rating, review_count, data_source, first_image_url, category_id
        FROM places
        WHERE region_1 = %(region)s
          AND category_id IN (12, 14, 39)
          AND visit_role = ANY(%(roles)s)
          AND is_active = TRUE
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL{zone_clause}
        ORDER BY view_count DESC NULLS LAST, place_id
        LIMIT 50
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return None

    # belt 시드 앵커 후보 보강 (LIMIT 50 우회)
    if region in REGION_TO_BELT_KEYS:
        _belt_seed_rows = _fetch_belt_seed_candidates(
            conn, region, roles, zone_center,
            zone_radius_km=zone_radius_km,
            pre_filter_radius_km=30.0 if (zone_center and not zone_radius_km) else None,
        )
        _used = {r["place_id"] for r in rows}
        rows = rows + [r for r in _belt_seed_rows if r["place_id"] not in _used]

    # 부적절 관광지 제거 (펜션, 어촌계, 리조트 등)
    rows = [r for r in rows if not _is_unsuitable_spot(r["name"])]
    if not rows:
        return None

    # food 테마: 폭포·계곡 등 외곽 자연 앵커 제외 (meal 확보 불가 지점 방지)
    if "food" in themes:
        rows = [r for r in rows if not _is_food_theme_unsuitable_anchor(r["name"])]
        if not rows:
            return None

    # 재선택 시 이전 실패 앵커 제외
    if exclude_ids:
        rows = [r for r in rows if r["place_id"] not in exclude_ids]
    if not rows:
        return None

    if centroid:
        clat, clon = centroid
        rows.sort(key=lambda r: _haversine(clat, clon, r["latitude"], r["longitude"]))

    # Req 5: belt_seed 앵커 우선 선택 — belt_boost 가중 랜덤 (Top-5 풀)
    if region in REGION_TO_BELT_KEYS:
        belt_rows = [r for r in rows if _is_tier1(region, r["name"], r.get("latitude"), r.get("longitude"))]
        if belt_rows:
            for row in belt_rows:
                tags = row["ai_tags"] or {}
                if set(themes) & set(tags.get("themes", [])):
                    return row
            # theme 매칭 없음: belt_boost 기반 가중 랜덤 (최대 5개 풀)
            _ANCHOR_TOP_K = 5
            clat2, clon2 = centroid if centroid else (belt_rows[0]["latitude"], belt_rows[0]["longitude"])

            def _anchor_score(r: dict) -> float:
                boost, _ = get_belt_info(region, r["name"], r.get("latitude"), r.get("longitude"))
                dist = _haversine(clat2, clon2, r["latitude"], r["longitude"])
                return boost - 0.005 * dist  # 거리 소폭 페널티

            belt_rows.sort(key=_anchor_score, reverse=True)
            pool    = belt_rows[:_ANCHOR_TOP_K]
            weights = [max(_anchor_score(r), 0.001) for r in pool]
            return random.choices(pool, weights=weights, k=1)[0]

    # theme 매칭 후보 수집 → 상위 K개 가중 랜덤 선택
    theme_matched = [
        r for r in rows
        if set(themes) & set((r["ai_tags"] or {}).get("themes", []))
    ]
    pool = theme_matched[:_NON_BELT_ANCHOR_TOP_K] if theme_matched else rows[:_NON_BELT_ANCHOR_TOP_K]

    if centroid and len(pool) > 1:
        clat, clon = centroid
        weights = [
            max(1.0 / (1.0 + _haversine(clat, clon, r["latitude"], r["longitude"])), 0.001)
            for r in pool
        ]
        return random.choices(pool, weights=weights, k=1)[0]

    return pool[0]


_SLOT_KR = {"breakfast": "아침", "morning": "오전", "lunch": "점심",
             "afternoon": "오후", "dinner": "저녁", "night": "야간"}
_ROLE_KR = {"spot": "명소", "culture": "문화", "meal": "식사", "cafe": "카페"}


def _build_reason(slot: str, role: str, components: dict, fallback_info: dict | None) -> str:
    if fallback_info and fallback_info.get("triggered"):
        return f"{slot} {role} 후보 부족으로 {fallback_info.get('reason', 'fallback')} 적용"
    slot_kr = _SLOT_KR.get(slot, slot)
    role_kr = _ROLE_KR.get(role, role)
    factors = []
    if components.get("theme_match", 0) >= 0.5:
        factors.append("테마 일치도 높음")
    if components.get("travel_fit", 0) >= 0.6:
        factors.append("이동 부담 낮음")
    if components.get("popularity_score", 0) >= 0.3:
        factors.append("인기도 높음")
    desc = ", ".join(factors) if factors else "최고 점수 선택"
    return f"{slot_kr} {role_kr} 슬롯 - {desc}"


def _pop_base(conn, region: str) -> float:
    """region의 view_count 상위 10% 임계값."""
    sql = """
        SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY view_count)
        FROM places
        WHERE region_1 = %(region)s AND is_active = TRUE
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"region": region})
        row = cur.fetchone()
    val = row[0] if row and row[0] else POPULARITY_BASE
    return float(val)


def _build_schedule(ordered_places: list, start_min_override: int | None = None) -> list:
    """각 장소에 scheduled_start/end, travel_to_next_min 추가."""
    if not ordered_places:
        return []

    first_slot  = ordered_places[0].get("_slot", "morning")
    h, m        = SLOT_START.get(first_slot, (9, 0))
    current_min = start_min_override if start_min_override is not None else h * 60 + m

    result          = []
    prev_travel_min = None
    prev_dist_km    = None

    for i, place in enumerate(ordered_places):
        slot = place.get("_slot", "morning")
        sh, sm      = SLOT_START.get(slot, (9, 0))
        slot_min    = sh * 60 + sm
        start_min   = max(current_min, slot_min)
        end_min     = start_min + (place["estimated_duration"] or 60)

        travel_min = 0
        dist_km    = 0.0
        if i < len(ordered_places) - 1:
            nxt        = ordered_places[i + 1]
            dist_km    = _haversine(place["latitude"], place["longitude"],
                                    nxt["latitude"], nxt["longitude"])
            travel_min = estimate_travel_minutes(dist_km)

        description = _build_place_description(place)

        entry: dict = {
            "order":                  i + 1,
            "place_id":               place["place_id"],
            "name":                   place["name"],
            "visit_role":             place["visit_role"],
            "scheduled_start":        f"{start_min // 60:02d}:{start_min % 60:02d}",
            "scheduled_end":          f"{end_min   // 60:02d}:{end_min   % 60:02d}",
            "move_minutes_from_prev": prev_travel_min,
            "distance_km_from_prev":  round(prev_dist_km, 2) if prev_dist_km is not None else None,
            "travel_to_next_min":     travel_min if i < len(ordered_places) - 1 else None,
            "distance_to_next_km":    round(dist_km, 2) if i < len(ordered_places) - 1 else None,
            "latitude":               place.get("latitude"),
            "longitude":              place.get("longitude"),
            "first_image_url":        place.get("first_image_url"),
            "description":            description,
            "fallback_reason":        place.get("_fallback_reason"),
            "selection_basis":        place.get("_selection_basis"),
        }
        _bb = place.get("_belt_boost")
        if _bb:
            entry["belt_boost"] = round(_bb, 4)
        result.append(entry)
        prev_travel_min = travel_min if i < len(ordered_places) - 1 else None
        prev_dist_km    = dist_km    if i < len(ordered_places) - 1 else None
        current_min     = end_min + travel_min

    return result


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def build_course(conn, request: dict) -> dict:
    """
    1일 코스 생성 진입점.

    Parameters
    ----------
    conn    : psycopg2 connection (db_client.get_connection())
    request : {region, companion, themes, template}

    Returns
    -------
    {template, region, total_duration_min, total_travel_min, places: [...]}
    """
    region             = request["region"]

    # 서비스 레벨 분기: BLOCKED 지역은 코스 생성 없이 즉시 반환
    if get_service_level(region) == "BLOCKED":
        logger.info("build_course skipped — region=%s is BLOCKED", region)
        return {"error": get_blocked_message(), "places": []}

    companion          = request.get("companion", "")
    themes             = request.get("themes", [])
    template           = request.get("template", "standard")
    start_time         = request.get("start_time") or request.get("departure_time")
    region_travel_type = request.get("region_travel_type", "urban")
    zone_center        = request.get("zone_center")      # (lat, lon) tuple or None
    zone_radius_km     = request.get("zone_radius_km")   # float or None
    walk_max_radius    = request.get("walk_max_radius")  # float or None (urban 거리 부담)
    city_type          = _get_city_type(region)
    is_city_mode       = region in CITY_MODE_REGIONS
    city_cluster: dict | None = None

    # regional 모드: zone 검증 radius를 SQL 필터·per-leg scoring에 동일하게 사용
    if region_travel_type == "regional":
        if not zone_radius_km:
            logger.warning("regional 모드에 zone_radius_km 없음 -- 코스 생성 불가 region=%s", region)
            return {"error": "regional 코스 생성 시 zone_radius_km 필수", "places": []}
        _r = float(zone_radius_km)
        eff_max_radius    = _r
        eff_max_travel    = REGIONAL_STEP_TRAVEL.get(_r, 60)
        eff_max_total     = REGIONAL_MAX_TOTAL_TRAVEL
        eff_meal_fb_r     = REGIONAL_STEP_MEAL_FB.get(_r, min(_r * 1.5, 30.0))
        eff_meal_fb_t     = REGIONAL_MEAL_FB_TRAVEL_MIN
    else:
        # urban/anchor: MOBILITY_PROFILE 기반, walk_max_radius 단계별 매핑 적용
        mob = MOBILITY_PROFILE[_get_city_type(region)]
        if walk_max_radius is not None:
            r = float(walk_max_radius)
            eff_max_radius = r
            eff_max_travel = URBAN_STEP_TRAVEL.get(int(r), min(mob["max_travel"], max(20, int(mob["max_travel"] * r / mob["max_radius"]))))
        else:
            eff_max_radius = mob["max_radius"]
            eff_max_travel = mob["max_travel"]
        eff_max_total     = mob["max_total"]
        eff_meal_fb_r     = mob["meal_fb_r"]
        eff_meal_fb_t     = mob["meal_fb_t"]

    # city_mode: 클러스터 선택 + tight 반경 오버라이드 (belt_mode 미영향)
    if is_city_mode:
        city_cluster = _select_city_cluster(region, themes, zone_center)
        if city_cluster:
            if zone_center is None:
                zone_center = city_cluster["center"]
            zone_radius_km = 2.5
            eff_max_radius = 4.0
            eff_max_travel = 25
            eff_max_total  = 100
            eff_meal_fb_r  = 3.5
            eff_meal_fb_t  = 25

    # Req 2/3: Tier1 belt_seed 전용 확장 반경 + 지방 도로 속도 모델
    tier1_max_radius = TOURISM_REGION_MAX_RADIUS if region in TOURISM_BELT else eff_max_radius
    use_rural_travel = region in TOURISM_BELT or region_travel_type == "regional"

    # zone_radius_km 없는 urban/anchor 모드에서 zone_center 기준 SQL pre-filter 반경
    # → province-wide top-N이 모두 먼 곳에서 뽑히는 문제 방지 (특히 지방 위성 도시)
    # 60km 상한 적용 — 25km radius에서 100km가 되면 광역 후보가 스코어 0 받는 문제 방지
    if zone_center and not zone_radius_km:
        pre_filter_r = min(max(eff_max_radius * 3.0, 30.0), 60.0)
    else:
        pre_filter_r = None

    if template not in TEMPLATES:
        logger.warning("알 수 없는 template '%s' -- standard로 대체", template)
        template = "standard"

    slots = _resolve_theme_slots(template, themes, start_time, request, city_type)
    if slots is None:
        logger.warning("22:00 이후 출발 -- 코스 생성 불가 region=%s start_time=%s", region, start_time)
        return {
            "error":      "22:00 이후 출발은 코스를 생성할 수 없습니다.",
            "error_code": "TOO_LATE",
            "places":     [],
        }

    # city_mode: 슬롯 오버라이드 (늦은 출발 템플릿은 그대로 유지)
    # cafe → morning_2에 cafe 허용 / food → afternoon_cafe에 meal 허용 / 나머지 → 기본
    if is_city_mode:
        _sh = _parse_start_hour(start_time)
        if _sh is None or _sh < 20:
            if "cafe" in themes:
                _slot_map = CITY_MODE_CAFE_SLOTS
            elif "food" in themes:
                _slot_map = CITY_MODE_FOOD_SLOTS
            else:
                _slot_map = CITY_MODE_SLOTS
            slots = list(_slot_map.get(template, _slot_map["standard"]))

    start_hour = _parse_start_hour(start_time)
    start_min_override = start_hour * 60 if start_hour is not None else None

    pop = _pop_base(conn, region)
    weights = _get_weights(themes)  # theme 활성화 시 theme_match 0.50 적용
    if is_city_mode:
        _theme_active = any(t in themes for t in _THEME_ROLE_BIAS)
        weights = CITY_MODE_CAFE_WEIGHTS if _theme_active else CITY_MODE_WEIGHTS

    # Step 1. 앵커 선택 (첫 슬롯 role 기준)
    anchor = _select_anchor(
        conn, region, themes, first_role=slots[0][1],
        zone_center=zone_center, zone_radius_km=zone_radius_km,
    )
    if anchor is None:
        logger.warning("앵커 선택 실패 -- region=%s", region)
        return {"error": "후보 장소 없음", "places": []}

    # 앵커 viability 검증 — total/meal/cafe 최소 기준 미달 시 최대 2회 재선택
    _excluded_anchors: set = set()
    for _retry in range(2):
        _nc = _count_nearby_candidates(
            conn, region, anchor["latitude"], anchor["longitude"], eff_max_radius
        )
        _viable = (
            _nc["total"] >= _MIN_ANCHOR_CANDIDATES
            and _nc["meal"] >= _MIN_ANCHOR_MEAL
            and _nc["cafe"] >= _MIN_ANCHOR_CAFE
        )
        if _viable:
            break
        logger.info(
            "앵커 viability 미달(total=%d meal=%d cafe=%d) -- 재선택 region=%s anchor=%s",
            _nc["total"], _nc["meal"], _nc["cafe"], region, anchor["name"],
        )
        _excluded_anchors.add(anchor["place_id"])
        _fallback = _select_anchor(
            conn, region, themes, first_role=slots[0][1],
            zone_center=zone_center, zone_radius_km=zone_radius_km,
            exclude_ids=_excluded_anchors,
        )
        if _fallback is None:
            break
        anchor = _fallback

    # 관광벨트 추적 — 전체 코스에서 belt 부스트가 적용된 장소 집계
    belt_boost_sum: float       = 0.0
    belt_matched_places: list   = []

    _a_tags     = anchor["ai_tags"] or {}
    _a_themes   = set(_a_tags.get("themes", []) + _a_tags.get("mood", []))
    _a_comp     = set(_a_tags.get("companion", []))
    _a_theme_sc = min(len(set(themes) & _a_themes) / max(len(themes), 1) + (0.2 if companion in _a_comp else 0), 1.0)
    _a_pop_sc   = min((anchor["view_count"] or 0) / max(pop, 1), 1.0)
    _a_final    = weights["travel_fit"] * 1.0 + weights["theme_match"] * _a_theme_sc + weights["popularity_score"] * _a_pop_sc + weights["slot_fit"] * 1.0
    _anchor_belt_b, _anchor_belt_seed = get_belt_info(region, anchor["name"], anchor["latitude"], anchor["longitude"])
    _anchor_scores: dict = {
        "travel_fit":         1.0,
        "theme_match":        round(_a_theme_sc, 4),
        "popularity_score":   round(_a_pop_sc, 4),
        "slot_fit":           1.0,
        "penalty_multiplier": 1.0,
        "final_score":        round(_a_final + _anchor_belt_b, 4),
    }
    if _anchor_belt_b > 0:
        _anchor_scores["belt_boost"]   = round(_anchor_belt_b, 4)
        _anchor_scores["matched_seed"] = _anchor_belt_seed
    anchor["_belt_boost"] = _anchor_belt_b if _anchor_belt_b > 0 else None
    if _anchor_belt_b > 0:
        belt_boost_sum += _anchor_belt_b
        belt_matched_places.append({
            "place_id":    anchor["place_id"],
            "name":        anchor["name"],
            "slot":        slots[0][0],
            "belt_boost":  round(_anchor_belt_b, 4),
            "matched_seed": _anchor_belt_seed,
        })
    anchor["_fallback_reason"] = None
    anchor["_selection_basis"] = {
        "version":     "1.0",
        "selected_by": "engine_anchor",
        "weights":     weights,
        "scores":      _anchor_scores,
        "reason":      "첫 일정 시작점으로 선택됨",
        "evidence": {
            "travel_minutes_from_prev": None,
            "distance_km_from_prev":    None,
            "rating":                   anchor.get("rating"),
            "review_count":             anchor.get("review_count"),
            "data_source":              anchor.get("data_source"),
        },
        "constraints": {
            "role_required":         slots[0][1],
            "time_slot_required":    slots[0][0],
            "travel_time_limit_min": eff_max_travel,
            "max_radius_km":         eff_max_radius,
        },
        "fallback": {"triggered": False, "reason": None},
    }
    anchor["_slot"] = slots[0][0]
    selected          = [anchor]
    used_ids          = {anchor["place_id"]}
    prev_coord        = (anchor["latitude"], anchor["longitude"])
    prev_role         = anchor["visit_role"]
    total_travel      = 0
    dropped_slots     = []
    skips_since_last  = 0  # 마지막 선택 이후 스킵된 슬롯 수 (같은 role 연속 체크용)
    tier1_selected_in_course = _is_tier1(region, anchor["name"], anchor.get("latitude"), anchor.get("longitude"))  # 앵커 belt_seed 여부

    # Step 2. 나머지 슬롯 채우기
    for slot, role in slots[1:]:
        slot_roles = role if isinstance(role, list) else [role]
        role_str = role if isinstance(role, str) else (role[0] if role else "")
        # cafe_tour 테마 cafe 슬롯, food 테마 meal 슬롯은 visit_time_slot 제약 없이 후보 조회
        relax = (
            (("cafe" in themes) and (role_str == "cafe")) or
            (("food" in themes) and (role_str == "meal"))
        )
        candidates = _fetch_candidates(
            conn, region, role, slot,
            zone_center=zone_center, zone_radius_km=zone_radius_km,
            relax_slot=relax, themes=themes,
            pre_filter_radius_km=pre_filter_r,
            belt_seed_radius_km=tier1_max_radius,
            proximity_center=prev_coord,
        )

        # 구내식당/기관 부속 식당 로컬 사전 필터 (meal 슬롯 전용)
        if role_str == "meal" or (isinstance(role, list) and "meal" in role):
            filtered_out = [p for p in candidates if is_institutional(p.get("name", ""))]
            if filtered_out:
                logger.info(
                    "기관식당 사전 필터 제거 %d건 -- region=%s slot=%s names=%s",
                    len(filtered_out), region, slot,
                    [p["name"] for p in filtered_out[:3]],
                )
            candidates = [p for p in candidates if not is_institutional(p.get("name", ""))]

        # 사우나/찜질방/스파랜드 등 부적절 관광지 사전 필터 (spot/culture 슬롯 전용)
        if role_str in ("spot", "culture") or (isinstance(role, list) and any(r in {"spot", "culture"} for r in role)):
            bad = [p for p in candidates if _is_unsuitable_spot(p.get("name", ""))]
            if bad:
                logger.info(
                    "부적절 관광지 사전 필터 %d건 -- region=%s slot=%s names=%s",
                    len(bad), region, slot, [p["name"] for p in bad[:3]],
                )
            candidates = [p for p in candidates if not _is_unsuitable_spot(p.get("name", ""))]

        # ── Req 1/2/3/4: Tier 분리 Scoring ─────────────────────────────────────
        tier1_scored  = []  # belt_seed 이름 매칭 + 물리 검증 통과
        tier2_scored  = []
        fallback_info = None
        is_spot_culture_slot = any(r in {"spot", "culture"} for r in slot_roles)
        # food theme: 연속 meal 허용 / cafe_tour: 연속 cafe 허용
        # skips_since_last > 0: 중간 슬롯 실패 후 재시도 → 같은 role 허용 (lunch→dinner 케이스)
        allow_same_role = (
            ("food" in themes and role_str == "meal" and prev_role == "meal") or
            ("cafe" in themes and role_str == "cafe" and prev_role == "cafe") or
            (skips_since_last > 0)  # 스킵된 슬롯 있으면 연속 체크 해제
        )
        for p in candidates:
            if p["place_id"] in used_ids:
                continue
            if p["visit_role"] == prev_role and not allow_same_role:
                continue
            # Req 4 Fail-Fast: 낙관적 직선거리 추정으로 누적 이동 초과 조기 검증
            if prev_coord:
                _leg_h = _heuristic_travel_min(
                    _haversine(prev_coord[0], prev_coord[1], p["latitude"], p["longitude"])
                )
                if total_travel + _leg_h > eff_max_total:
                    continue
            p_is_tier1 = is_spot_culture_slot and _is_tier1(region, p["name"], p.get("latitude"), p.get("longitude"))
            r_km = tier1_max_radius if p_is_tier1 else TIER2_TIGHT_RADIUS_KM
            result = _score(
                p, prev_coord, themes, companion, slot, pop,
                max_radius_km=r_km, max_leg_time=eff_max_travel,
                relax_slot=relax, weights=weights, rural_travel=use_rural_travel,
            )
            if result is not None:
                s, travel_min, dist_km, components = result
                # 관광벨트 부스트 적용 (지역 시드와 이름/근접도 기반 가산)
                belt_b, belt_seed = get_belt_info(region, p["name"], p["latitude"], p["longitude"])
                if belt_b > 0:
                    s += belt_b
                    components = {**components, "belt_boost": round(belt_b, 4), "matched_seed": belt_seed, "final_score": round(s, 4)}
                # theme별 혼합 슬롯 내 preferred role 우선 선택 bias
                _p_role = p.get("visit_role")
                for _t, (_pref_roles, _bias) in _THEME_ROLE_BIAS.items():
                    if _t in themes and _p_role in _pref_roles and bool(_pref_roles & set(slot_roles)):
                        s += _bias
                        components = {**components, f"{_t}_role_bias": _bias, "final_score": round(s, 4)}
                        break
                # 다양성 패널티: 클러스터 중복(600m) + T1 동일 카테고리 방지
                s, components = _diversity_penalty(s, p, selected, p_is_tier1, components)
                if p_is_tier1:
                    tier1_scored.append((s, travel_min, dist_km, components, p))
                else:
                    tier2_scored.append((s, travel_min, dist_km, components, p))

        # Req 2 Adaptive Fallback: tier2 후보 부족 시 반경 단계적 확장 (5→8→15→20km)
        if not tier2_scored or len(tier2_scored) < TIER2_MIN_CANDIDATES:
            _t2_ids = {item[4]["place_id"] for item in tier2_scored}
            for fb_r in TIER2_FALLBACK_RADII:
                _new: list = []
                for p in candidates:
                    if p["place_id"] in used_ids or p["place_id"] in _t2_ids:
                        continue
                    if p["visit_role"] == prev_role and not allow_same_role:
                        continue
                    if is_spot_culture_slot and _is_tier1(region, p["name"], p.get("latitude"), p.get("longitude")):
                        continue  # tier1은 위에서 이미 처리됨
                    if prev_coord:
                        _leg_h = _heuristic_travel_min(
                            _haversine(prev_coord[0], prev_coord[1], p["latitude"], p["longitude"])
                        )
                        if total_travel + _leg_h > eff_max_total:
                            continue
                    result = _score(
                        p, prev_coord, themes, companion, slot, pop,
                        max_radius_km=fb_r, max_leg_time=eff_max_travel,
                        relax_slot=relax, weights=weights, rural_travel=use_rural_travel,
                    )
                    if result is not None:
                        s, travel_min, dist_km, components = result
                        belt_b, belt_seed = get_belt_info(region, p["name"], p["latitude"], p["longitude"])
                        if belt_b > 0:
                            s += belt_b
                            components = {**components, "belt_boost": round(belt_b, 4), "matched_seed": belt_seed, "final_score": round(s, 4)}
                        # 다양성 패널티 (adaptive fallback은 T2 전용)
                        s, components = _diversity_penalty(s, p, selected, False, components)
                        _new.append((s, travel_min, dist_km, components, p))
                if _new:
                    tier2_scored.extend(_new)
                    _t2_ids.update(item[4]["place_id"] for item in _new)
                    logger.info(
                        "tier2 adaptive fallback 적용 r=%.0fkm +%d건 -- region=%s slot=%s",
                        fb_r, len(_new), region, slot,
                    )
                    if len(tier2_scored) >= TIER2_MIN_CANDIDATES:
                        break

        scored = tier1_scored + tier2_scored

        if not scored:
            raw_count = len(candidates)
            logger.warning(
                "슬롯 후보 없음 -- slot=%s role=%s region=%s (DB후보=%d, 거리/슬롯 필터 후 0건)",
                slot, role, region, raw_count,
            )
            if role == "meal" or (isinstance(role, list) and "meal" in role):
                for p in candidates:
                    if p["place_id"] in used_ids:
                        continue
                    if p["visit_role"] == prev_role and not allow_same_role:
                        continue
                    result = _score(
                        p, prev_coord, themes, companion, slot, pop,
                        max_radius_km=eff_meal_fb_r, max_leg_time=eff_meal_fb_t,
                        relax_slot=relax, weights=weights, rural_travel=use_rural_travel,
                    )
                    if result is not None:
                        s, travel_min, dist_km, components = result
                        scored.append((s, travel_min, dist_km, components, p))
                if scored:
                    logger.info(
                        "meal 거리 fallback 적용 (radius=%dkm travel=%dmin) region=%s",
                        eff_meal_fb_r, eff_meal_fb_t, region,
                    )
                    fallback_info = {"triggered": True, "reason": "meal_distance_relaxed"}
                else:
                    logger.warning("meal 거리 fallback도 후보 없음 -- region=%s", region)
                    skips_since_last += 1
                    continue
            # afternoon spot/culture 실패 시 cafe로 대체 (standard/history 공통 적용)
            elif slot == "afternoon" and any(r in {"spot", "culture"} for r in slot_roles):
                fallback_candidates = _fetch_candidates(
                    conn, region, "cafe", slot,
                    zone_center=zone_center, zone_radius_km=zone_radius_km,
                    themes=themes,
                    pre_filter_radius_km=pre_filter_r,
                )
                for p in fallback_candidates:
                    if p["place_id"] in used_ids:
                        continue
                    if p["visit_role"] == prev_role and not allow_same_role:
                        continue
                    result = _score(
                        p, prev_coord, themes, companion, slot, pop,
                        max_radius_km=eff_max_radius, max_leg_time=eff_max_travel,
                        weights=weights, rural_travel=use_rural_travel,
                    )
                    if result is not None:
                        s, travel_min, dist_km, components = result
                        scored.append((s, travel_min, dist_km, components, p))
                if scored:
                    logger.info("afternoon spot fallback → cafe 적용 (region=%s)", region)
                    fallback_info = {"triggered": True, "reason": "afternoon_spot_no_candidate_fallback_to_cafe"}
                else:
                    logger.warning("afternoon cafe fallback도 후보 없음 -- region=%s", region)
                    skips_since_last += 1
                    continue
            else:
                # 마지막 수단: anchor 위치 기준 반경 재탐색 (zone_center 오버라이드)
                if prev_coord:
                    _fb_cands = _fetch_candidates(
                        conn, region, role, slot,
                        zone_center=prev_coord, zone_radius_km=eff_max_radius,
                        relax_slot=True, themes=themes, pre_filter_radius_km=None,
                    )
                    for p in _fb_cands:
                        if p["place_id"] in used_ids:
                            continue
                        if p["visit_role"] == prev_role and not allow_same_role:
                            continue
                        result = _score(
                            p, prev_coord, themes, companion, slot, pop,
                            max_radius_km=eff_max_radius, max_leg_time=eff_max_travel,
                            relax_slot=True, weights=weights, rural_travel=use_rural_travel,
                        )
                        if result is not None:
                            s, travel_min, dist_km, components = result
                            scored.append((s, travel_min, dist_km, components, p))
                if not scored:
                    skips_since_last += 1
                    continue
                fallback_info = {"triggered": True, "reason": "slot_anchor_radius_fallback"}

        scored.sort(key=lambda x: x[0], reverse=True)

        # ── Req 1: Tier 기반 가중치 선택 (이동 시간 페널티 포함, 확정 픽 없음) ──────
        if tier1_scored and not fallback_info:
            tier1_scored.sort(key=lambda x: x[0], reverse=True)
            _candidate_t1 = tier1_scored
            # 보너스: 기존 tier1 장소와 지리적 일관성 보장 (40km 초과 조합 제외)
            _existing_t1_coords = [
                (s["latitude"], s["longitude"]) for s in selected
                if _is_tier1(region, s["name"], s.get("latitude"), s.get("longitude"))
            ]
            if _existing_t1_coords:
                _coherent = [
                    item for item in tier1_scored
                    if all(
                        _haversine(ec[0], ec[1], item[4]["latitude"], item[4]["longitude"]) <= 40.0
                        for ec in _existing_t1_coords
                    )
                ]
                if _coherent:
                    _candidate_t1 = _coherent
            _, travel_min, dist_km, components, chosen = _weighted_choice_tiered(
                _candidate_t1, TIER1_WEIGHTED_TOP_K, eff_max_travel
            )
            tier1_selected_in_course = True
        else:
            _, travel_min, dist_km, components, chosen = _weighted_choice_tiered(
                scored, DIVERSITY_TOP_K, eff_max_travel
            )

        # 선택된 장소의 벨트 부스트 추적
        _chosen_belt_b    = components.get("belt_boost", 0.0)
        _chosen_belt_seed = components.get("matched_seed")
        chosen["_belt_boost"] = _chosen_belt_b if _chosen_belt_b > 0 else None

        # Req 4 Fail-Fast 안전망: heuristic 통과했으나 정밀 계산 시 총 이동 초과
        if total_travel + travel_min > eff_max_total:
            logger.info(
                "누적 이동 초과(정밀 검증 안전망) -- slot=%s 누적=%d 추가=%d 한도=%d",
                slot, total_travel, travel_min, eff_max_total,
            )
            skips_since_last += 1
            continue

        fb = fallback_info or {"triggered": False, "reason": None}
        chosen["_fallback_reason"]  = fb["reason"]
        chosen["_selection_basis"]  = {
            "version":     "1.0",
            "selected_by": "engine",
            "weights":     weights,
            "scores":      components,
            "reason":      _build_reason(slot, chosen["visit_role"], components, fb if fb["triggered"] else None),
            "evidence": {
                "travel_minutes_from_prev": travel_min,
                "distance_km_from_prev":    round(dist_km, 3),
                "rating":                   chosen.get("rating"),
                "review_count":             chosen.get("review_count"),
                "data_source":              chosen.get("data_source"),
            },
            "constraints": {
                "role_required":        role,
                "time_slot_required":   slot,
                "travel_time_limit_min": eff_max_travel,
                "max_radius_km":        eff_max_radius,
            },
            "fallback": fb,
        }
        chosen["_slot"] = slot
        selected.append(chosen)
        used_ids.add(chosen["place_id"])
        prev_coord       = (chosen["latitude"], chosen["longitude"])
        prev_role        = chosen["visit_role"]
        total_travel    += travel_min
        skips_since_last = 0  # 선택 성공 → 연속 스킵 카운터 리셋
        if _chosen_belt_b > 0:
            belt_boost_sum += _chosen_belt_b
            belt_matched_places.append({
                "place_id":    chosen["place_id"],
                "name":        chosen["name"],
                "slot":        slot,
                "belt_boost":  round(_chosen_belt_b, 4),
                "matched_seed": _chosen_belt_seed,
            })

    # Step 3. 시간표 생성
    schedule = _build_schedule(selected, start_min_override=start_min_override)

    # Step 4. 22:00 초과 제거
    final = []
    for entry in schedule:
        h, m    = map(int, entry["scheduled_end"].split(":"))
        end_min = h * 60 + m
        if end_min > END_HOUR_LIMIT:
            logger.warning("22:00 초과로 '%s' 제외", entry["name"])
            break
        final.append(entry)

    total_dur = sum(
        (p["estimated_duration"] or 60) for p in selected[:len(final)]
    )

    # 도심감성(urban) theme + 비도심 지역(urban 아닌 경우) → fallback_reason 기록
    theme_notes = {}
    if "urban" in themes and city_type not in ("urban", "large"):
        theme_notes["urban"] = "지역 특성상 도심 후보 부족"

    _belt_name = region if region in TOURISM_BELT else None

    # cafe 슬롯 미충족 감지 — 계획된 cafe 슬롯 수 대비 실제 cafe 수 부족 시 안내 문구
    _planned_cafe = sum(
        1 for _, role in slots
        if role == "cafe" or (isinstance(role, list) and "cafe" in role)
    )
    _actual_cafe = sum(1 for p in final if p.get("visit_role") == "cafe")
    missing_slot_reason = (
        "가까운 카페 후보가 부족해, 동선이 자연스러운 장소 위주로 구성했어요."
        if _planned_cafe > _actual_cafe and len(final) > 0
        else None
    )

    _option_notice = get_option_notice(region, themes)
    if (
        len(final) < 5
        and get_service_level(region) != "BLOCKED"
        and not _option_notice
    ):
        _option_notice = (
            f"현재 이 지역·테마에서 추천 가능한 장소가 적어 "
            f"{len(final)}곳으로 코스를 구성했어요. 데이터 보강 후 더 풍성한 코스를 제공할 예정입니다."
        )

    return {
        "template":             template,
        "region":               region,
        "target_place_count":   len(slots),
        "actual_place_count":   len(final),
        "dropped_slots":        dropped_slots,
        "total_duration_min":   total_dur,
        "total_travel_min":     total_travel,
        "selected_radius_km":   eff_max_radius,
        "tier1_max_radius_km":  tier1_max_radius,
        "selection_basis":      {"weights": weights, "mode": "theme" if themes else "default"},
        "theme_notes":          theme_notes or None,
        "tourism_belt_applied": belt_boost_sum > 0,
        "belt_name":            _belt_name,
        "belt_boost_sum":       round(belt_boost_sum, 4),
        "belt_matched_places":  belt_matched_places,
        "tier1_in_course":      tier1_selected_in_course,
        "tier1_fallback_reason": (
            "물리적 제약(거리/시간)으로 tier1(belt_seed) 장소를 코스에 포함하지 못했습니다."
            if region in TOURISM_BELT and not tier1_selected_in_course
            else None
        ),
        "city_mode":            is_city_mode,
        "city_cluster":         city_cluster["name"] if city_cluster else None,
        "description":          _build_description(region, themes, city_cluster),
        "missing_slot_reason":  missing_slot_reason,
        "option_notice":        _option_notice,
        "places":               final,
    }
