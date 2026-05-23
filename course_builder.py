"""
course_builder.py -- 1일 여행 코스 추천

진입점: build_course(conn, request) → dict
"""

import logging
import random
import re
from collections import Counter
from math import radians, sin, cos, sqrt, atan2, log1p

import psycopg2.extras

from travel_utils import estimate_travel_minutes
from tourism_belt import get_belt_info, TOURISM_BELT, is_belt_seed_name, REGION_TO_BELT_KEYS
from enrichment_service import is_institutional
from city_clusters import CITY_CLUSTERS, CITY_MODE_REGIONS, THEME_TO_CLUSTER_MOOD, CITY_MODE_SLOTS, CITY_MODE_CAFE_SLOTS, CITY_MODE_FOOD_SLOTS
from region_notices import get_option_notice, get_service_level, get_blocked_message
from region_identity_layer import (
    infer_course_flow_profile,
    infer_region_belt,
    infer_seoul_district_vibe,
    score_editorial_route_fit,
    score_meal_cafe_suitability,
    score_belt_match,
    score_dominant_belt_affinity,
    score_flow_continuity,
    score_route_contamination,
    score_vibe_tourism_suitability,
    summarize_course_belt_coherence,
    summarize_route_coherence,
)
from recommendation_observability import (
    build_recommendation_trace,
    summarize_city_distribution,
    summarize_scored_candidates,
    infer_city_token,
)
from landmark_authority import iter_landmark_seeds, score_landmark_authority


_IMAGE_URL_FIELDS = (
    "first_image_url",
    "image_url",
    "image",
    "thumbnail",
    "thumbnail_url",
    "firstimage",
    "firstimage2",
)

HAEDONG_YONGGUNGSA_CURATED_IMAGE_URL = (
    "https://images.unsplash.com/photo-1740785978879-506357754d72"
    "?auto=format&fit=crop&fm=jpg&q=80&w=1200"
)
HAEDONG_YONGGUNGSA_CURATED_IMAGE_SOURCE = (
    "Unsplash / Dmitry Voronov / Free to use under the Unsplash License"
)


def _is_haedong_yonggungsa_place(place: dict | None) -> bool:
    if not isinstance(place, dict):
        return False
    text = _normalize_city_token(" ".join(str(place.get(key) or "") for key in (
        "name", "category", "category_name", "description", "overview", "address", "addr", "region_2"
    )))
    return any(token in text for token in (
        _normalize_city_token("해동용궁사"),
        _normalize_city_token("해동 용궁사"),
        _normalize_city_token("용궁사"),
        _normalize_city_token("Haedong Yonggungsa"),
        _normalize_city_token("Haedong Yonggung Temple"),
    ))


def _apply_haedong_yonggungsa_curated_image(place: dict | None) -> dict:
    """Apply a narrow curated image fallback for Haedong Yonggungsa only."""
    if not isinstance(place, dict) or not _is_haedong_yonggungsa_place(place):
        return {
            "first_image_url": place.get("first_image_url") if isinstance(place, dict) else None,
            "image_available": _has_representative_image(place),
            "placeholder_used": not _has_representative_image(place),
            "curated_image_used": False,
            "curated_image_source": None,
            "curated_image_reason": None,
        }

    original_image = place.get("first_image_url")
    use_curated = not _has_representative_image(place) or _normalize_city_token(place.get("name")) == _normalize_city_token("해동용궁사")
    if not use_curated:
        return {
            "first_image_url": original_image,
            "image_available": True,
            "placeholder_used": False,
            "curated_image_used": False,
            "curated_image_source": None,
            "curated_image_reason": None,
        }

    reason = "haedong_yonggungsa_missing_image_fallback" if not original_image else "haedong_yonggungsa_curated_representative_image"
    return {
        "first_image_url": HAEDONG_YONGGUNGSA_CURATED_IMAGE_URL,
        "image_available": True,
        "placeholder_used": False,
        "curated_image_used": True,
        "curated_image_source": HAEDONG_YONGGUNGSA_CURATED_IMAGE_SOURCE,
        "curated_image_reason": reason,
    }

_SEA_FLOW_TERMS = {
    "sea_drive",
    "night_city",
    "cafe_relaxed",
}

_COASTAL_TEXT_TERMS = (
    "바다",
    "해변",
    "해수욕장",
    "오션",
    "해안",
    "항구",
    "포구",
    "수변",
    "야경",
    "sea",
    "ocean",
    "beach",
    "harbor",
)

_INDOOR_LEISURE_TERMS = (
    "실내수영장",
    "수영장",
    "워터파크",
    "스파",
    "사우나",
    "찜질",
    "체육관",
    "헬스",
    "실내스포츠",
    "키즈",
    "키즈월드",
    "pool",
    "waterpark",
    "spa",
)

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
    "night": {
        "light": [
            ("dinner", ["meal", "cafe", "spot", "culture"]),
            ("evening", ["spot", "culture", "cafe"]),
        ],
        "standard": [
            ("dinner", ["meal", "cafe", "spot", "culture"]),
            ("evening", ["spot", "culture", "cafe"]),
        ],
        "full": [
            ("dinner", ["meal", "cafe", "spot", "culture"]),
            ("evening", ["spot", "culture", "cafe"]),
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

# 전역 대표 관광 부적합 키워드 필터 (이름 기반 quick guard)
# locality 문제가 아니라 tourism eligibility 문제를 먼저 차단한다.
_GLOBAL_UNSUITABLE_GROUPS: dict[str, tuple[str, ...]] = {
    "education_childcare": (
        "유치원", "어린이집", "초등학교", "중학교", "고등학교", "대학교",
        "학교", "학원", "교습소", "교육원", "캠퍼스",
    ),
    "medical_welfare": (
        "병원", "의원", "치과", "한의원", "약국", "요양원", "복지관", "보건소",
    ),
    "public_office": (
        "주민센터", "행정복지센터", "구청", "시청", "군청", "경찰서", "파출소",
        "소방서", "우체국", "세무서", "법원", "등기소",
    ),
    "daily_commerce_noise": (
        "편의점", "마트", "슈퍼", "주유소", "충전소", "세차장", "정비소",
        "공업사", "부동산", "은행", "ATM",
    ),
    "lodging_adult_purpose": (
        "모텔", "무인텔", "호텔", "펜션", "리조트", "콘도", "사우나", "찜질",
        "목욕탕", "마사지", "안마", "노래방", "PC방", "피시방", "당구장", "오락실", "만화카페",
    ),
    "tourism_noise_existing": (
        "해수랜드", "찜질방", "스파랜드", "스파월드", "워터피아", "어촌계",
        "온천탕", "온천장", "폰케이스", "휴대폰", "액세서리",
    ),
}

_GLOBAL_TOURISM_UNSUITABLE_PATTERNS: tuple[str, ...] = tuple(
    keyword for group in _GLOBAL_UNSUITABLE_GROUPS.values() for keyword in group
)

_ALL_ROLE_UNSUITABLE_GROUPS = frozenset({
    "education_childcare",
    "medical_welfare",
    "public_office",
    "daily_commerce_noise",
})

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

EVENING_TEMPLATES = {
    "light": [
        ("dinner", "meal"),
        ("evening", "cafe"),
        ("evening", "cafe"),
    ],
    "standard": [
        ("dinner", "meal"),
        ("evening", "cafe"),
        ("dinner", "meal"),
    ],
    "full": [
        ("dinner", "meal"),
        ("evening", "cafe"),
        ("dinner", "meal"),
        ("evening", "cafe"),
    ],
}

LATE_USER_SELECTED_TEMPLATES = {
    "light": [
        ("dinner", ["meal", "cafe", "spot"]),
        ("evening", ["spot", "culture", "cafe"]),
    ],
    "standard": [
        ("dinner", ["meal", "cafe", "spot"]),
        ("evening", ["spot", "culture", "cafe"]),
        ("evening", ["cafe", "spot", "culture"]),
    ],
    "full": [
        ("dinner", ["meal", "cafe", "spot"]),
        ("evening", ["spot", "culture", "cafe"]),
        ("evening", ["cafe", "spot", "culture"]),
        ("evening", ["spot", "culture", "cafe"]),
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


def _compact_name(name: str) -> str:
    return str(name or "").replace(" ", "").lower()


def _get_unsuitable_reason(name: str) -> dict | None:
    """Return global tourism-unsuitable reason for trace/report."""
    n = _compact_name(name)
    for group, patterns in _GLOBAL_UNSUITABLE_GROUPS.items():
        for keyword in patterns:
            compact = _compact_name(keyword)
            if compact and compact in n:
                return {"keyword": keyword, "group": group}
    return None


def _is_globally_unsuitable_tourism_place(name: str, category=None, tags=None) -> bool:
    """Global quick guard for representative tourism candidates."""
    return _get_unsuitable_reason(name) is not None


def _is_unsuitable_spot(name: str) -> bool:
    """spot/culture 슬롯에 부적절한 업종 여부."""
    return _is_globally_unsuitable_tourism_place(name)


def _is_representative_limited_spot(name: str) -> bool:
    """Backward-compatible alias for representative guard."""
    return _is_globally_unsuitable_tourism_place(name)


def _is_unsuitable_representative_spot(name: str) -> bool:
    """anchor/tourism-belt 대표 후보에서 제외할 시설 여부."""
    return _is_globally_unsuitable_tourism_place(name)


def _should_drop_candidate_for_role(place: dict, roles: list[str]) -> bool:
    """Apply global guard by role without over-pruning meal/cafe fallback pools."""
    reason = _get_unsuitable_reason(place.get("name", ""))
    if not reason:
        return False
    if any(r in {"spot", "culture"} for r in roles):
        return True
    return reason.get("group") in _ALL_ROLE_UNSUITABLE_GROUPS


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


def _parse_start_minute(start_time: str | None) -> int | None:
    """'오늘 20:00', '내일 14:30', '20:00' 등에서 출발 시각을 분 단위로 추출."""
    if not start_time:
        return None
    m = re.search(r'(\d{1,2}):(\d{2})', start_time)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2))
    if hour < 0 or hour > 24 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute


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
    if hour is None or hour < 18:
        return list(_CITY_TEMPLATES[city_type][template])
    if hour < 20:
        return list(EVENING_TEMPLATES.get(template, EVENING_TEMPLATES["standard"]))
    if hour >= 22:
        return None
    if hour >= 21:
        return list(LATE_TEMPLATES["late_21"])
    # 20:00 ≤ hour < 21:00
    if request.get("dinner_included"):
        return [("afternoon", ["spot", "culture"]), ("dinner", "meal"), ("dinner", "cafe")]
    return list(LATE_TEMPLATES["late_20"])


_NIGHT_FRIENDLY_TERMS = (
    "야간",
    "야경",
    "노포",
    "을지로",
    "힙지로",
    "광안리야경",
    "광안리 야경",
    "익선",
    "데이트",
    "한남",
    "감성",
    "night",
    "nightlife",
    "nightview",
    "date",
    "기장",
    "드라이브",
    "바다",
    "coastal",
)


def _is_night_friendly_request(request: dict, themes: list, start_time: str | None) -> bool:
    hour = _parse_start_hour(start_time)
    if request.get("euljiro_night_mode_removed"):
        return False
    if request.get("time_band_night_friendly") and hour is not None and 16 <= hour < 24:
        return True
    if hour is None or hour < 18 or hour >= 24:
        return False
    text = " ".join(
        str(request.get(key) or "")
        for key in (
            "selected_anchor",
            "start_anchor",
            "start_anchor_label",
            "anchor_theme_seed",
            "selected_anchor_vibe",
            "mood",
            "theme",
        )
    ).lower()
    theme_text = " ".join(str(t or "") for t in (themes or [])).lower()
    combined = f"{text} {theme_text}"
    return any(term.lower().replace(" ", "") in combined.replace(" ", "") for term in _NIGHT_FRIENDLY_TERMS)


def _is_late_user_selected_request(request: dict, start_time: str | None) -> bool:
    hour = _parse_start_hour(start_time)
    if (
        request.get("departure_time_user_selected")
        and (request.get("selected_time_band") == "evening" or request.get("time_band_night_friendly"))
        and hour is not None
        and 16 <= hour < 24
    ):
        return True
    if hour is None or hour < 18 or hour >= 24:
        return False
    return bool(request.get("departure_time_user_selected"))


def _resolve_theme_slots(template: str, themes: list, start_time: str | None, request: dict, city_type: str = "rural") -> list | None:
    """
    theme 우선으로 slot 구성 반환. theme 매핑 없으면 기본 _resolve_slots 위임.

    - cafe theme: THEME_SLOT_CONFIG["cafe"] 사용 (카페 3개 보장 구조)
    - food theme: THEME_SLOT_CONFIG["food"] 사용 (meal 슬롯 증가)
    - 야간/야경 의도가 명확한 늦은 출발은 night-friendly slot 사용
    - 그 외 늦은 출발(≥20:00)은 기존 _resolve_slots 로직 그대로 사용
    """
    hour = _parse_start_hour(start_time)
    if _is_night_friendly_request(request, themes, start_time):
        request["night_friendly_mode"] = True
        request["night_late_safe_relaxed_mode"] = True
        request["late_user_selected_mode"] = _is_late_user_selected_request(request, start_time)
        request["intentional_late_schedule"] = bool(request.get("late_user_selected_mode"))
        request["late_cutoff_relaxed"] = bool(request.get("late_user_selected_mode"))
        request["night_support_slot_preserved"] = bool(request.get("late_user_selected_mode"))
        request["short_course_prevented"] = bool(request.get("late_user_selected_mode"))
        request["relaxed_operating_hour_filter"] = True
        request["night_safe_candidate_preserved"] = True
        request["nightlife_support_slot_fallback"] = True
        request["strict_closed_filter_skipped"] = True
        request["night_friendly_time_policy"] = {
            "applied": True,
            "reason": "night theme/anchor with departure between 18:00 and 24:00",
            "start_hour": hour,
            "late_safe_relaxed_mode": True,
        }
        if request.get("late_user_selected_mode"):
            return list(LATE_USER_SELECTED_TEMPLATES.get(template, LATE_USER_SELECTED_TEMPLATES["standard"]))
        return list(THEME_SLOT_CONFIG["night"].get(template, THEME_SLOT_CONFIG["night"]["standard"]))
    if _is_late_user_selected_request(request, start_time):
        request["night_friendly_mode"] = False
        request["late_user_selected_mode"] = True
        request["intentional_late_schedule"] = True
        request["late_cutoff_relaxed"] = True
        request["night_support_slot_preserved"] = True
        request["short_course_prevented"] = True
        return list(LATE_USER_SELECTED_TEMPLATES.get(template, LATE_USER_SELECTED_TEMPLATES["standard"]))
    if hour is not None and hour >= 18:
        request["night_friendly_mode"] = False
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


def _normalize_city_token(value: str | None) -> str:
    return re.sub(r"[\\s\\-\\(\\)\\[\\],·/]", "", str(value or "").strip().lower())


def _build_city_alias_set(intended_city: str | None) -> set[str]:
    base = _normalize_city_token(intended_city)
    if not base:
        return set()

    aliases = {base}
    aliases.update({
        base.replace("시", ""),
        base.replace("군", ""),
        base.replace("구", ""),
        base.replace("읍", ""),
        base.replace("면", ""),
    })

    city_aliases = {
        _normalize_city_token("속초"): {_normalize_city_token("속초"), _normalize_city_token("속초시")},
        _normalize_city_token("여수"): {_normalize_city_token("여수"), _normalize_city_token("여수시")},
        _normalize_city_token("전주"): {_normalize_city_token("전주"), _normalize_city_token("전주시")},
        _normalize_city_token("강릉"): {_normalize_city_token("강릉")},
        _normalize_city_token("경주"): {_normalize_city_token("경주"), _normalize_city_token("경주시")},
        _normalize_city_token("부산"): {_normalize_city_token("부산")},
        _normalize_city_token("제주"): {_normalize_city_token("제주"), _normalize_city_token("제주시")},
    }
    for key, value in city_aliases.items():
        if base == key:
            aliases.update(value)
            break

    return {a for a in aliases if a}


def _extract_city_terms(place: dict) -> list[str]:
    if not isinstance(place, dict):
        return []

    terms: list[str] = []
    for key in ("name", "region_1", "region_2", "region", "address", "addr", "address_name", "overview"):
        value = place.get(key)
        if value:
            terms.append(str(value))

    ai_tags = place.get("ai_tags")
    if isinstance(ai_tags, dict):
        for value in ai_tags.get("themes", []) or []:
            terms.append(str(value))
        for value in ai_tags.get("mood", []) or []:
            terms.append(str(value))
    return terms


_ANCHOR_LOCALITY_ALIASES: dict[str, dict[str, set[str]]] = {
    "??": {
        "city": {"??", "???"},
        "anchors": {"???", "????", "??????", "??", "????", "???", "???"},
    },
    "??": {
        "city": {"??", "???"},
        "anchors": {"??????", "????????", "?????????", "???", "????", "??????"},
    },
    "??": {
        "city": {"??", "???"},
        "anchors": {"???", "???", "????"},
    },
    "??": {
        "city": {"??", "???"},
        "anchors": {"???", "????"},
    },
    "??": {
        "city": {"??", "???"},
        "anchors": {"????"},
    },
    "??": {
        "city": {"??", "???"},
        "anchors": {"???", "??", "????"},
    },
    "??": {
        "city": {"??", "???"},
        "anchors": {"???", "???"},
    },
}

_JEONBUK_LOCALITY_CITIES = tuple(_ANCHOR_LOCALITY_ALIASES.keys())


def _normalize_selected_anchor_for_debug(selected_anchor: str | dict | set | list | tuple | None) -> dict:
    """Normalize selected anchor label into city/anchor tokens used by locality scoring."""
    if not selected_anchor:
        return {
            "city": None,
            "anchor": None,
            "tokens": [],
            "normalized_city_token": None,
            "normalized_anchor_token": None,
            "normalized_anchor_aliases": [],
        }

    if isinstance(selected_anchor, dict):
        label = str(
            selected_anchor.get("name")
            or selected_anchor.get("display_name")
            or selected_anchor.get("anchor_name")
            or selected_anchor.get("zone_id")
            or ""
        )
    elif isinstance(selected_anchor, (set, list, tuple)):
        label = " ".join(str(v) for v in selected_anchor if v)
    else:
        label = str(selected_anchor or "")

    normalized = _normalize_city_token(label)
    cleanup_terms = (
        "??", "??", "??", "??", "??", "??", "???",
        "???", "????", "??????",
    )
    compact = normalized
    for term in cleanup_terms:
        compact = compact.replace(_normalize_city_token(term), "")

    selected_city = None
    selected_anchor_token = None
    aliases: set[str] = {compact} if compact else set()

    for city, config in _ANCHOR_LOCALITY_ALIASES.items():
        city_aliases = {_normalize_city_token(alias) for alias in config["city"]}
        anchor_aliases = {_normalize_city_token(alias) for alias in config["anchors"]}
        if any(alias and alias in normalized for alias in city_aliases | anchor_aliases):
            selected_city = city
            aliases.update(city_aliases)
            aliases.update(anchor_aliases)
            for alias in sorted(anchor_aliases, key=len, reverse=True):
                if alias and alias in normalized:
                    selected_anchor_token = alias
                    break
            break

    if selected_city and not selected_anchor_token:
        selected_anchor_token = compact or _normalize_city_token(selected_city)

    return {
        "city": selected_city,
        "anchor": selected_anchor_token,
        "tokens": sorted(token for token in aliases if token),
        "normalized_city_token": _normalize_city_token(selected_city) if selected_city else None,
        "normalized_anchor_token": selected_anchor_token,
        "normalized_anchor_aliases": sorted(token for token in aliases if token),
    }


def _selected_anchor_tokens(selected_anchor: str | dict | set | list | tuple | None) -> set[str]:
    normalized = _normalize_selected_anchor_for_debug(selected_anchor)
    return set(normalized.get("normalized_anchor_aliases") or normalized.get("tokens") or [])


def _infer_locality_city_from_terms(terms: list[str]) -> str | None:
    joined = "|".join(terms)
    for city, config in _ANCHOR_LOCALITY_ALIASES.items():
        aliases = {_normalize_city_token(v) for v in (config["city"] | config["anchors"])}
        if any(alias and alias in joined for alias in aliases):
            return city
    return None


def _looks_like_region_code(value: str | None) -> bool:
    """Return True for compact numeric/code-like region_2 metadata.

    This helper is intentionally narrow: it prevents runtime NameError in the
    existing city-intent path without introducing new ranking behavior.
    """
    token = _normalize_city_token(value)
    if not token:
        return False
    return token.isdigit() or bool(re.fullmatch(r"[a-z]{1,4}\d{1,6}", token))


def _infer_region2_codes_for_intent(candidates: list[dict] | None, intended_city: str | None) -> set[str]:
    if not candidates or not intended_city:
        return set()

    normalized = _normalize_city_token(intended_city)
    if not normalized:
        return set()

    codes = []
    for place in candidates:
        if not isinstance(place, dict):
            continue
        region_2 = _normalize_city_token(str(place.get("region_2") or ""))
        if _looks_like_region_code(region_2):
            codes.append(region_2)

    if not codes:
        return set()

    counter = Counter(codes)
    total = sum(counter.values())
    threshold = max(2, int(total * 0.25))
    return {code for code, count in counter.items() if count >= threshold}


def _score_city_intent(
    place: dict,
    intended_city: str | None,
    query_region_1: str | None = None,
    selected_anchor: str | dict | set | list | tuple | None = None,
    selected_anchor_coord: tuple | None = None,
    region2_code_hints: set[str] | None = None,
) -> dict:
    aliases = _build_city_alias_set(intended_city)
    if not aliases:
        return {
            "score": 0.0,
            "evidence": "none",
            "positive_hits": 0,
            "negative_hits": 0,
            "evidence_tokens": [],
            "anchor_distance_score": 0.0,
            "locality_bonus": 0.0,
            "wrong_city_demote": 0.0,
        }

    terms = [_normalize_city_token(t) for t in _extract_city_terms(place)]
    joined = "|".join(terms)

    selected_anchor_debug = _normalize_selected_anchor_for_debug(selected_anchor)
    anchor_tokens = set(selected_anchor_debug.get("normalized_anchor_aliases") or [])
    selected_city = selected_anchor_debug.get("city")
    selected_city_token = selected_anchor_debug.get("normalized_city_token")
    selected_anchor_token = selected_anchor_debug.get("normalized_anchor_token")

    selected_anchor_hit = any(token and token in joined for token in anchor_tokens)
    city_hit = any(token and token in joined for token in aliases)

    region_2 = _normalize_city_token(str(place.get("region_2") or ""))
    region2_hit = bool(region_2) and any(
        token in region_2 for token in aliases if len(token) > 1
    )
    region2_hint_hit = bool(region2_code_hints and region_2 in region2_code_hints)

    locality_bonus = 0.0
    wrong_city_demote = 0.0
    locality_evidence: list[str] = []

    if selected_city:
        selected_city_aliases = {
            _normalize_city_token(v)
            for v in _ANCHOR_LOCALITY_ALIASES.get(selected_city, {}).get("city", set())
        }
        selected_anchor_aliases = {
            _normalize_city_token(v)
            for v in _ANCHOR_LOCALITY_ALIASES.get(selected_city, {}).get("anchors", set())
        } | anchor_tokens
        same_city_hit = any(alias and alias in joined for alias in selected_city_aliases)
        same_anchor_hit = any(alias and alias in joined for alias in selected_anchor_aliases)
        inferred_place_city = _infer_locality_city_from_terms(terms)
        explicit_other_locality = bool(inferred_place_city and inferred_place_city != selected_city)

        if same_anchor_hit:
            locality_bonus += 0.12
            locality_evidence.append("same_anchor_bonus")
        elif same_city_hit:
            locality_bonus += 0.08
            locality_evidence.append("same_city_bonus")

        if explicit_other_locality:
            wrong_city_demote = 0.08
            locality_evidence.append(f"wrong_city_soft_demote:{inferred_place_city}")

    anchor_distance_score = 0.0
    if selected_anchor_coord and place.get("latitude") is not None and place.get("longitude") is not None:
        anchor_distance = _haversine(
            selected_anchor_coord[0],
            selected_anchor_coord[1],
            float(place["latitude"]),
            float(place["longitude"]),
        )
        if anchor_distance <= 2.0:
            anchor_distance_score = 0.4
        elif anchor_distance <= 4.0:
            anchor_distance_score = 0.3
        elif anchor_distance <= 6.0:
            anchor_distance_score = 0.2
        elif anchor_distance <= 10.0:
            anchor_distance_score = 0.1
        elif anchor_distance <= 15.0:
            anchor_distance_score = 0.05

    positive_hits = 0
    negative_hits = 0
    evidence_tokens: list[str] = []

    for token in aliases:
        if token and token in joined:
            positive_hits += 1
            evidence_tokens.append(token)
            break

    evidence = "none"
    score = 0.0

    if city_hit:
        score = 1.0
        evidence = "city_alias_match"
        positive_hits += 1
        evidence_tokens.append(next((token for token in aliases if token in joined), ""))
    elif region2_hint_hit:
        score = 0.92
        evidence = "region2_hint_match"
        positive_hits += 1
    elif region2_hit:
        score = 0.76
        evidence = "region2_match"
        positive_hits += 1
    elif selected_anchor_hit:
        score = 0.64
        evidence = "selected_anchor_match"
        positive_hits += 1
    elif terms:
        score = 0.22
        evidence = "sparse_metadata"
    else:
        score = 0.0

    if not city_hit and not region2_hit and not selected_anchor_hit:
        explicit_other_city = any(
            city in joined for city in (
                "??", "??", "??", "??", "??", "??", "??", "??",
                "??", "??", "??", "??", "??", "??",
            )
        )
        if explicit_other_city:
            negative_hits += 1
            score *= 0.88
            evidence = f"{evidence}:wrong_city_hint"

    if wrong_city_demote > 0:
        negative_hits += 1
        score = max(0.0, score - wrong_city_demote)
        evidence = f"{evidence}:locality_demote"

    if _looks_like_region_code(region_2):
        score = max(score, 0.5)

    return {
        "score": round(min(max(score, 0.0), 1.0), 4),
        "evidence": evidence,
        "positive_hits": positive_hits,
        "negative_hits": negative_hits,
        "evidence_tokens": (evidence_tokens + locality_evidence)[:12],
        "anchor_distance_score": round(anchor_distance_score, 4),
        "locality_bonus": round(locality_bonus, 4),
        "wrong_city_demote": round(wrong_city_demote, 4),
        "normalized_city_token": selected_city_token,
        "normalized_anchor_token": selected_anchor_token,
    }


def _has_representative_image(place: dict | None) -> bool:
    if not isinstance(place, dict):
        return False
    for field in _IMAGE_URL_FIELDS:
        value = place.get(field)
        if isinstance(value, str) and value.strip():
            return True
    return False


def _score_image_availability(
    place: dict | None,
    *,
    flow_profile: dict | None = None,
    target_slot: str | None = None,
    first_place: bool = False,
) -> dict:
    """Small visual-quality signal. Advisory only; never filters candidates."""
    image_available = _has_representative_image(place)
    role = str((place or {}).get("visit_role") or "").lower()
    profile = str((flow_profile or {}).get("flow_profile") or (flow_profile or {}).get("inferred_flow_profile") or "")
    image_quality_bonus = 0.0
    no_image_first_place_demote = 0.0
    reason = None

    if image_available:
        image_quality_bonus = 0.025
        if first_place or target_slot in {"anchor", "morning"}:
            image_quality_bonus += 0.015
        if role in {"spot", "culture", "cafe"}:
            image_quality_bonus += 0.005
    elif first_place or target_slot in {"anchor", "morning"}:
        no_image_first_place_demote = 0.055
        reason = "no_image_first_place"
        if profile in {"cafe_relaxed", "sea_drive", "night_city", "history_walk", "walk_emotional"}:
            no_image_first_place_demote += 0.015

    return {
        "image_available": image_available,
        "image_quality_bonus": round(image_quality_bonus, 4),
        "no_image_first_place_demote": round(no_image_first_place_demote, 4),
        "no_image_first_place_reason": reason,
    }


def _score_coastal_indoor_leisure(
    place: dict | None,
    *,
    flow_profile: dict | None = None,
    target_slot: str | None = None,
    first_place: bool = False,
) -> dict:
    """Soft demote indoor leisure in coastal/sea first-place contexts."""
    if not isinstance(place, dict):
        return {"indoor_leisure_demote": 0.0, "indoor_leisure_reason": None}

    profile = str((flow_profile or {}).get("flow_profile") or (flow_profile or {}).get("inferred_flow_profile") or "")
    joined = " ".join(
        str(place.get(key) or "")
        for key in ("name", "category", "category_name", "visit_role", "description", "overview", "address", "addr", "region", "region_1", "region_2")
    ).lower()
    coastal_context = profile in _SEA_FLOW_TERMS or any(term.lower() in joined for term in _COASTAL_TEXT_TERMS)
    indoor_hit = next((term for term in _INDOOR_LEISURE_TERMS if term.lower() in joined), None)
    if not coastal_context or not indoor_hit:
        return {"indoor_leisure_demote": 0.0, "indoor_leisure_reason": None}

    demote = 0.055
    if first_place or target_slot in {"anchor", "morning"}:
        demote += 0.045
    return {
        "indoor_leisure_demote": round(demote, 4),
        "indoor_leisure_reason": f"coastal_indoor_leisure:{indoor_hit}",
    }



_DEFAULT_PRESET_THEME_TOKENS = {"", "default", "basic", "기본", "기본 추천", "자연 선택"}
_DEFAULT_PRESET_WEIRD_TERMS = (
    "생활", "복지관", "주민센터", "행정복지", "체육센터", "국민체육", "스포츠센터",
    "교육문화", "문화센터", "수련관", "연수원", "오피스", "빌딩", "사옥", "청사",
    "센터", "회관", "교육원", "실내체육", "체육관",
)


_SELECTED_ANCHOR_FAMILY_MAP = {
    "광화문종로주변": {
        "family_id": "seoul_gwanghwamun_jongno",
        "tokens": ["광화문", "종로", "경복궁", "청계천", "인사동", "북촌", "삼청"],
    },
    "강남역주변": {
        "family_id": "seoul_gangnam",
        "tokens": ["강남역", "강남", "신논현", "가로수길", "압구정", "청담", "코엑스", "별마당도서관", "봉은사", "선정릉", "역삼"],
    },
    "여의도주변": {
        "family_id": "seoul_yeouido",
        "tokens": ["여의도", "여의도공원", "여의도한강공원", "한강공원", "더현대서울", "더현대", "IFC", "IFC몰", "샛강", "샛강생태공원", "63빌딩"],
    },
    "홍대입구주변": {
        "family_id": "seoul_hongdae",
        "tokens": ["홍대", "홍대거리", "홍대입구", "연남동", "경의선숲길", "망원", "상수", "합정"],
    },
    "잠실주변": {
        "family_id": "seoul_jamsil",
        "tokens": ["잠실", "롯데월드타워", "롯데월드", "석촌호수", "올림픽공원"],
    },
    "명동을지로주변": {
        "family_id": "seoul_myeongdong_euljiro",
        "tokens": ["명동", "을지로", "청계천", "남산", "힙지로", "남대문"],
    },
    "성수동건대주변": {
        "family_id": "seoul_seongsu_geondae",
        "tokens": ["성수", "성수동", "서울숲", "건대", "뚝섬"],
    },
    "성수감성카페": {
        "family_id": "seoul_seongsu_cafe",
        "tokens": ["성수", "성수동", "서울숲", "연무장", "카페거리", "로스터리"],
    },
    "성수감성": {
        "family_id": "seoul_seongsu_cafe",
        "tokens": ["성수", "성수동", "서울숲", "연무장", "카페거리", "로스터리"],
    },
    "성수동카페": {
        "family_id": "seoul_seongsu_cafe",
        "tokens": ["성수", "성수동", "서울숲", "연무장", "카페거리", "로스터리"],
    },
    "북촌한옥산책": {
        "family_id": "seoul_bukchon",
        "tokens": ["북촌", "북촌한옥마을", "한옥", "삼청", "전통찻집", "창덕궁", "경복궁"],
    },
    "북촌산책": {
        "family_id": "seoul_bukchon",
        "tokens": ["북촌", "북촌한옥마을", "한옥", "삼청", "전통찻집", "창덕궁", "경복궁"],
    },
    "익선데이트": {
        "family_id": "seoul_ikseon",
        "tokens": ["익선", "익선동", "종로3가", "한옥", "골목", "카페"],
    },
    "한남감성": {
        "family_id": "seoul_hannam",
        "tokens": ["한남", "한남동", "브런치", "갤러리", "편집숍", "이태원"],
    },
    "을지로야간": {
        "family_id": "seoul_euljiro_night",
        "tokens": ["을지로", "힙지로", "청계천", "노포", "야간", "골목"],
    },
    "을지로감성": {
        "family_id": "seoul_euljiro_night",
        "tokens": ["을지로", "힙지로", "청계천", "골목", "레트로카페", "세운상가", "충무로"],
    },
    "한강야경": {
        "family_id": "seoul_yeouido",
        "tokens": ["한강", "한강공원", "여의도한강공원", "뚝섬한강공원", "수변", "산책", "야경"],
    },
    "여의도한강공원": {
        "family_id": "seoul_yeouido",
        "tokens": ["여의도", "여의도한강공원", "한강공원", "여의도공원", "샛강", "더현대서울", "IFC"],
    },
    "잠실가족": {
        "family_id": "seoul_jamsil_family",
        "tokens": ["잠실", "석촌", "롯데", "올림픽공원", "한강"],
    },
    "해운대주변": {
        "family_id": "busan_haeundae",
        "tokens": ["해운대", "해운대해수욕장", "달맞이길", "동백섬", "더베이101", "미포"],
    },
    "광안리주변": {
        "family_id": "busan_gwangan",
        "tokens": ["광안리", "광안리해수욕장", "광안대교", "민락수변공원", "민락"],
    },
    "기장드라이브": {
        "family_id": "busan_gijang_east_coast",
        "tokens": ["기장", "해동용궁사", "용궁사", "송정", "송정해수욕장", "오시리아", "기장해안", "기장해안도로", "죽성성당", "아난티", "청사포", "기장카페거리"],
    },
    "해동용궁사": {
        "family_id": "busan_gijang_east_coast",
        "tokens": ["해동용궁사", "해동 용궁사", "용궁사", "기장", "송정", "송정해수욕장", "오시리아", "기장해안", "죽성성당", "아난티", "청사포"],
    },
    "서면주변": {
        "family_id": "busan_seomyeon",
        "tokens": ["서면", "전포", "전포동", "전포카페거리", "전리단길", "부전", "부전동", "부전시장", "부산진", "부산진구", "서면젊음의거리", "젊음의거리", "서면지하상가", "서면1번가", "서면일번가"],
    },
    "남포동부산역주변": {
        "family_id": "busan_nampo_station",
        "tokens": ["남포", "남포동", "부산역", "자갈치시장", "BIFF", "비프광장", "국제시장", "용두산", "용두산공원", "부산타워", "감천문화마을", "흰여울문화마을", "흰여울해안터널", "깡깡이예술마을", "송도해상케이블카", "송도해수욕장"],
    },
    "동성로주변": {
        "family_id": "daegu_dongseongno",
        "tokens": ["동성로", "김광석거리", "서문시장", "근대골목"],
    },
    "동대구역주변": {
        "family_id": "daegu_dongdaegu",
        "tokens": ["동대구", "동대구역", "신세계동대구", "신세계", "아양기찻길"],
    },
    "수성못주변": {
        "family_id": "daegu_suseongmot",
        "tokens": ["수성못", "수성", "카페거리", "야경산책"],
    },
    "인천역차이나타운주변": {
        "family_id": "incheon_chinatown",
        "tokens": ["인천역", "차이나타운", "송월동", "동화마을", "개항장", "신포"],
    },
    "월미도주변": {
        "family_id": "incheon_wolmi",
        "tokens": ["월미도", "월미", "월미테마파크", "월미바다열차"],
    },
    "송도주변": {
        "family_id": "incheon_songdo",
        "tokens": ["송도", "송도센트럴파크", "센트럴파크", "트리플스트리트", "G타워"],
    },
    "광주역주변": {
        "family_id": "gwangju_station",
        "tokens": ["광주역", "국립아시아문화전당", "아시아문화전당", "양림동", "충장로"],
    },
    "충장로동명동주변": {
        "family_id": "gwangju_chungjang_dongmyeong",
        "tokens": ["충장로", "동명동", "동명동카페거리", "양림동", "펭귄마을"],
    },
    "대전역주변": {
        "family_id": "daejeon_station",
        "tokens": ["대전역", "성심당", "소제동", "중앙시장"],
    },
    "둔산시청주변": {
        "family_id": "daejeon_dunsan",
        "tokens": ["둔산", "시청", "한밭수목원", "예술의전당"],
    },
    "유성온천주변": {
        "family_id": "daejeon_yuseong",
        "tokens": ["유성", "유성온천", "온천거리", "카이스트", "갑천"],
    },
    "제주공항주변": {
        "family_id": "jeju_airport",
        "tokens": ["제주공항", "용두암", "동문시장", "이호테우", "이호"],
    },
    "애월주변": {
        "family_id": "jeju_aewol",
        "tokens": ["애월", "애월해안도로", "곽지해수욕장", "한담해변", "한담"],
    },
    "중문주변": {
        "family_id": "jeju_jungmun",
        "tokens": ["중문", "중문관광단지", "천제연폭포", "주상절리", "색달"],
    },
    "성산주변": {
        "family_id": "jeju_seongsan",
        "tokens": ["성산", "성산일출봉", "섭지코지", "광치기해변", "광치기"],
    },
    "황리단길대릉원주변": {
        "family_id": "gyeongju_hwangni",
        "tokens": ["황리단길", "대릉원", "첨성대", "동궁과월지", "월정교"],
    },
    "경주역주변": {
        "family_id": "gyeongju_station",
        "tokens": ["경주역", "경주", "황리단길", "대릉원"],
    },
    "불국사주변": {
        "family_id": "gyeongju_bulguksa",
        "tokens": ["불국사", "석굴암", "토함산"],
    },
    "강릉역주변": {
        "family_id": "gangwon_gangneung_station",
        "tokens": ["강릉역", "강릉", "중앙시장", "월화거리", "안목", "강릉카페거리"],
    },
    "경포해변주변": {
        "family_id": "gangwon_gyeongpo",
        "tokens": ["경포", "경포해변", "경포호", "안목커피거리", "안목"],
    },
    "속초주변": {
        "family_id": "gangwon_sokcho",
        "tokens": ["속초", "속초해수욕장", "영랑호", "대포항", "아바이마을", "속초중앙시장", "청초호"],
    },
    "전주한옥마을주변": {
        "family_id": "jeonbuk_jeonju_hanok",
        "tokens": ["전주한옥마을", "한옥", "경기전", "남부시장"],
    },
    "전주역주변": {
        "family_id": "jeonbuk_jeonju_station",
        "tokens": ["전주역", "전주", "전주한옥마을", "객리단길", "객사"],
    },
    "군산주변": {
        "family_id": "jeonbuk_gunsan",
        "tokens": ["군산", "군산근대거리", "근대", "초원사진관", "은파호수공원", "시간여행"],
    },
}

_SELECTED_ANCHOR_FAMILY_MAP.update({
    "광화문/종로 주변": {
        "family_id": "seoul_gwanghwamun_jongno",
        "tokens": ["광화문", "종로", "경복궁", "청계천", "인사동", "북촌", "삼청"],
    },
    "강남역 주변": {
        "family_id": "seoul_gangnam",
        "tokens": ["강남역", "강남", "신논현", "가로수길", "압구정", "청담", "코엑스", "별마당도서관", "봉은사", "선정릉", "역삼"],
    },
    "여의도 주변": {
        "family_id": "seoul_yeouido",
        "tokens": ["여의도", "여의도공원", "여의도한강공원", "한강공원", "더현대서울", "더현대", "IFC", "IFC몰", "샛강", "샛강생태공원", "63빌딩"],
    },
    "북촌 한옥 산책": {
        "family_id": "seoul_bukchon",
        "tokens": ["북촌", "북촌한옥마을", "삼청", "한옥", "전통찻집", "창덕궁", "경복궁"],
    },
    "성수 감성 카페": {
        "family_id": "seoul_seongsu_cafe",
        "tokens": ["성수", "성수동", "서울숲", "연무장", "카페거리", "로스터리"],
    },
    "전주한옥마을": {
        "family_id": "jeonbuk_jeonju_hanok",
        "tokens": ["전주한옥마을", "한옥", "경기전", "전동성당", "남부시장", "오목대", "향교", "부채문화관", "전통술박물관", "공예품전시관", "교동", "자만마을", "벽화"],
    },
    "전주한옥마을 주변": {
        "family_id": "jeonbuk_jeonju_hanok",
        "tokens": ["전주한옥마을", "한옥", "경기전", "전동성당", "남부시장", "오목대", "향교", "부채문화관", "전통술박물관", "공예품전시관", "교동", "자만마을", "벽화"],
    },
    "광안리 야경": {
        "family_id": "busan_gwangan",
        "tokens": ["광안리", "광안리해수욕장", "광안대교", "민락", "수변공원", "야경", "바다"],
    },
})

_SELECTED_ANCHOR_FAMILY_MAP.update({
    "남포동/부산역 주변": {
        "family_id": "busan_nampo_station",
        "tokens": ["남포", "남포동", "부산역", "자갈치시장", "자갈치", "BIFF", "비프광장", "국제시장", "용두산", "용두산공원", "부산타워", "감천문화마을", "흰여울문화마을", "흰여울해안터널", "깡깡이예술마을", "송도해상케이블카", "송도해수욕장"],
    },
    "감천문화마을": {
        "family_id": "busan_nampo_station",
        "tokens": ["감천문화마을", "감천", "남포", "자갈치", "국제시장", "BIFF", "비프광장", "용두산", "흰여울", "송도"],
    },
    "송도해상케이블카": {
        "family_id": "busan_nampo_station",
        "tokens": ["송도해상케이블카", "송도", "송도해수욕장", "송도해변", "남포", "자갈치", "용두산", "감천", "흰여울"],
    },
    "태종대": {
        "family_id": "busan_yeongdo_oldtown",
        "tokens": ["태종대", "영도", "흰여울문화마을", "흰여울", "깡깡이예술마을", "남포", "송도"],
    },
})

_SELECTED_ANCHOR_FAMILY_MAP.update({
    "전주한옥마을": {
        "family_id": "jeonbuk_jeonju_hanok",
        "tokens": ["전주한옥마을", "한옥", "경기전", "전동성당", "남부시장", "오목대", "향교", "부채문화관"],
    },
    "전주한옥마을 주변": {
        "family_id": "jeonbuk_jeonju_hanok",
        "tokens": ["전주한옥마을", "한옥", "경기전", "전동성당", "남부시장", "오목대", "향교", "부채문화관"],
    },
    "북촌 한옥 산책": {
        "family_id": "seoul_bukchon",
        "tokens": ["북촌", "북촌한옥마을", "삼청동", "한옥", "전통찻집", "궁궐", "창덕궁", "경복궁"],
    },
    "성수 감성 카페": {
        "family_id": "seoul_seongsu_cafe",
        "tokens": ["성수", "서울숲", "성수동카페거리", "연무장길", "로스터리", "디저트", "전시", "편집숍"],
    },
    "광화문/종로 주변": {
        "family_id": "seoul_gwanghwamun_jongno",
        "tokens": ["광화문", "종로", "경복궁", "청계천", "인사동", "북촌", "삼청동"],
    },
    "광안리 야경": {
        "family_id": "busan_gwangan",
        "tokens": ["광안리", "광안리해수욕장", "광안대교", "민락", "민락수변공원", "야경", "바다"],
    },
    "기장 드라이브": {
        "family_id": "busan_gijang_east_coast",
        "tokens": ["기장", "해동용궁사", "용궁사", "송정", "송정해수욕장", "오시리아", "기장해안", "기장해안도로", "죽성성당", "아난티", "청사포", "기장카페거리"],
    },
})

_SELECTED_ANCHOR_FAMILY_MAP.update({
    "전주한옥마을": {
        "family_id": "jeonbuk_jeonju_hanok",
        "tokens": ["전주한옥마을", "한옥", "경기전", "전동성당", "남부시장", "오목대", "향교", "부채문화관", "전통술박물관", "공예품전시관", "교동", "자만마을", "벽화"],
    },
    "전주한옥마을 주변": {
        "family_id": "jeonbuk_jeonju_hanok",
        "tokens": ["전주한옥마을", "한옥", "경기전", "전동성당", "남부시장", "오목대", "향교", "부채문화관", "전통술박물관", "공예품전시관", "교동", "자만마을", "벽화"],
    },
})


def _resolve_selected_anchor_family(selected_anchor: str | dict | set | list | tuple | None) -> dict:
    def _family_key(value: object) -> str:
        return re.sub(r"[\s\-\(\)\[\],·ㆍ쨌/]+", "", str(value or "").strip().lower())

    if selected_anchor is None:
        return {"family_id": None, "tokens": [], "normalized_tokens": []}
    if isinstance(selected_anchor, dict):
        raw = " ".join(str(v) for v in selected_anchor.values() if v)
    elif isinstance(selected_anchor, (set, list, tuple)):
        raw = " ".join(str(v) for v in selected_anchor if v)
    else:
        raw = str(selected_anchor)
    normalized = _family_key(raw)
    if not normalized:
        return {"family_id": None, "tokens": [], "normalized_tokens": []}

    best_key = None
    for key in _SELECTED_ANCHOR_FAMILY_MAP:
        normalized_key = _family_key(key)
        if normalized_key and (normalized_key in normalized or normalized in normalized_key):
            if best_key is None or len(key) > len(best_key):
                best_key = key
    if not best_key:
        return {"family_id": None, "tokens": [], "normalized_tokens": []}

    family = _SELECTED_ANCHOR_FAMILY_MAP[best_key]
    tokens = list(family.get("tokens") or [])
    normalized_tokens = [_family_key(token) for token in tokens if _family_key(token)]
    return {
        "family_id": family.get("family_id"),
        "tokens": tokens,
        "normalized_tokens": normalized_tokens,
        "matched_anchor_key": best_key,
    }


def _score_selected_anchor_family(
    place: dict | None,
    selected_anchor_family: dict | None,
    landmark_authority_signal: dict | None = None,
    *,
    default_preset_mode: bool = False,
    target_slot: str | None = None,
) -> dict:
    family = selected_anchor_family or {}
    tokens = family.get("normalized_tokens") or []
    if not default_preset_mode or not isinstance(place, dict) or not tokens:
        return {
            "selected_anchor_family_id": family.get("family_id"),
            "selected_anchor_family_match_score": 0.0,
            "selected_anchor_family_preserved": False,
            "selected_anchor_family_drift_demote": 0.0,
            "selected_anchor_drift_reason": None,
            "fallback_level_used": "no_family_map" if not tokens else None,
        }

    text = re.sub(r"[\s\-\(\)\[\],·ㆍ쨌/]+", "", " ".join(str(place.get(k) or "") for k in (
        "name", "category", "category_name", "description", "overview", "address", "addr", "region_2"
    )).strip().lower())
    matched = [token for token in tokens if token and token in text]
    slot = str(target_slot or "")
    first_place_slot = slot in {"anchor", "morning", "morning_2"}
    match_score = 0.0
    if matched:
        match_score = 0.18 if first_place_slot else 0.11
        if len(matched) >= 2:
            match_score += 0.035

    signal = landmark_authority_signal or {}
    has_generic_representative_pull = bool(signal.get("landmark_authority_matches")) or (
        float(signal.get("landmark_authority_score") or 0.0)
        + float(signal.get("external_verified_score") or 0.0)
        + float(signal.get("representative_confidence_score") or 0.0)
    ) >= 0.08
    drift_demote = 0.0
    drift_reason = None
    if not matched and has_generic_representative_pull:
        drift_demote = 0.16 if first_place_slot else 0.09
        drift_reason = f"unrelated_representative_outside_family:{family.get('family_id')}"

    return {
        "selected_anchor_family_id": family.get("family_id"),
        "selected_anchor_family_match_score": round(match_score, 4),
        "selected_anchor_family_preserved": bool(matched),
        "selected_anchor_family_matched_terms": matched[:6],
        "selected_anchor_family_drift_demote": round(drift_demote, 4),
        "selected_anchor_drift_reason": drift_reason,
        "fallback_level_used": "selected_anchor_family" if matched else ("region_level_fallback" if drift_demote else "broad_fallback"),
    }


_BUSAN_OLDTOWN_FAMILY_IDS = {"busan_nampo_station", "busan_yeongdo_oldtown"}
_BUSAN_OLDTOWN_POSITIVE_TERMS = (
    "남포", "부산역", "자갈치", "국제시장", "biff", "비프", "용두산", "부산타워",
    "감천", "흰여울", "송도", "깡깡이", "영도", "보수동", "산복도로", "해안터널",
)
_BUSAN_OLDTOWN_DRIFT_TERMS = (
    "해운대", "광안리", "광안대교", "민락", "달맞이", "동백섬", "더베이", "기장", "오시리아",
)
_EXACT_LANDMARK_VISIBILITY_FAMILY_IDS = {"busan_nampo_station", "busan_yeongdo_oldtown", "jeonbuk_jeonju_hanok"}
_BUSAN_OLDTOWN_EXACT_LANDMARK_TERMS = (
    "감천문화마을", "감천", "BIFF광장", "BIFF", "비프광장", "비프", "흰여울문화마을",
    "흰여울", "자갈치시장", "자갈치", "송도해상케이블카", "송도", "국제시장", "용두산",
)
_BUSAN_OLDTOWN_STRICT_EXACT_LANDMARK_TERMS = (
    "감천문화마을", "BIFF광장", "비프광장", "흰여울문화마을",
    "자갈치시장", "국제시장", "송도해상케이블카",
)
_BUSAN_OLDTOWN_PRIMARY_EXACT_TERMS = (
    "감천문화마을", "감천", "BIFF광장", "BIFF", "비프광장", "비프", "흰여울문화마을",
    "흰여울", "자갈치시장", "자갈치", "송도해상케이블카",
)
_BUSAN_OLDTOWN_FOCUS_TERMS_BY_ANCHOR = {
    "감천문화마을": ("감천문화마을",),
    "송도해상케이블카": ("송도해상케이블카", "케이블카"),
    "남포동/부산역 주변": (
        "감천문화마을", "BIFF광장", "비프광장",
        "흰여울문화마을", "자갈치시장", "국제시장",
    ),
}
_JEONJU_HANOK_EXACT_LANDMARK_TERMS = (
    "경기전", "전동성당", "오목대", "남부시장", "전주향교", "전주부채문화관",
    "부채문화관", "전주공예품전시관", "공예품전시관",
)
_JEONJU_HANOK_PRIMARY_EXACT_TERMS = (
    "경기전", "전동성당", "오목대", "남부시장", "전주향교",
)
_JEONJU_HANOK_WRONG_CITY_TERMS = (
    "익산", "임실", "군산", "남원", "정읍", "고창", "부안", "김제",
)
_EXACT_LANDMARK_WEAK_SUBSTITUTE_TERMS = (
    "양곱창", "국밥", "감자탕", "기사식당", "분식", "일반음식점", "푸드", "맛집",
    "체험관", "교육관", "문화센터", "생활관", "크루즈", "해수욕장",
)


def _exact_focus_terms_for_family(selected_anchor_family: dict | None) -> tuple[str, ...]:
    family = selected_anchor_family or {}
    if str(family.get("family_id") or "") not in _BUSAN_OLDTOWN_FAMILY_IDS:
        return ()
    anchor_key = str(family.get("matched_anchor_key") or "")
    if anchor_key in _BUSAN_OLDTOWN_FOCUS_TERMS_BY_ANCHOR:
        return _BUSAN_OLDTOWN_FOCUS_TERMS_BY_ANCHOR[anchor_key]
    return ()


def _score_exact_landmark_visibility(
    place: dict | None,
    selected_anchor_family: dict | None,
    landmark_authority_signal: dict | None = None,
    *,
    region: str | None = None,
    target_slot: str | None = None,
) -> dict:
    family = selected_anchor_family or {}
    family_id = str(family.get("family_id") or "")
    if family_id not in _EXACT_LANDMARK_VISIBILITY_FAMILY_IDS or not isinstance(place, dict):
        return {
            "exact_landmark_visibility_score": 0.0,
            "exact_landmark_pool_included": False,
            "exact_landmark_support_slot_bonus": 0.0,
            "exact_support_slot_visibility_bonus": 0.0,
            "exact_slot_alignment_bonus": 0.0,
            "exact_anchor_final_visibility": False,
            "exact_landmark_missing_reason": None,
            "weak_substitute_demote": 0.0,
            "oldtown_substitute_demote": 0.0,
            "exact_landmark_match_terms": [],
            "exact_landmark_focus_match_terms": [],
        }

    text = _normalize_city_token(" ".join(str(place.get(k) or "") for k in (
        "name", "category", "category_name", "description", "overview", "address", "addr", "region_2"
    )))
    first_place = str(target_slot or "") in {"anchor", "morning", "morning_2"}
    support_slot = not first_place
    role = str(place.get("visit_role") or place.get("role") or "")
    expected_region = "부산" if family_id in _BUSAN_OLDTOWN_FAMILY_IDS else "전북"
    same_region = not region or str(region) == expected_region
    terms = _BUSAN_OLDTOWN_EXACT_LANDMARK_TERMS if family_id in _BUSAN_OLDTOWN_FAMILY_IDS else _JEONJU_HANOK_EXACT_LANDMARK_TERMS
    strict_terms = (
        _BUSAN_OLDTOWN_STRICT_EXACT_LANDMARK_TERMS
        if family_id in _BUSAN_OLDTOWN_FAMILY_IDS
        else _JEONJU_HANOK_PRIMARY_EXACT_TERMS
    )
    primary_terms = _BUSAN_OLDTOWN_PRIMARY_EXACT_TERMS if family_id in _BUSAN_OLDTOWN_FAMILY_IDS else _JEONJU_HANOK_PRIMARY_EXACT_TERMS
    matches = [term for term in terms if _normalize_city_token(term) in text]
    strict_matches = [term for term in strict_terms if _normalize_city_token(term) in text]
    primary_matches = [term for term in primary_terms if _normalize_city_token(term) in text]
    focus_terms = _exact_focus_terms_for_family(family)
    focus_matches = [term for term in focus_terms if _normalize_city_token(term) in text]
    anchor_key = str(family.get("matched_anchor_key") or "")
    specific_focus_anchor = anchor_key in {"감천문화마을", "송도해상케이블카"}
    authority = landmark_authority_signal or {}
    authority_score = (
        float(authority.get("landmark_authority_score") or 0.0)
        + float(authority.get("representative_confidence_score") or 0.0)
        + float(authority.get("external_verified_score") or 0.0)
    )

    visibility_score = 0.0
    support_bonus = 0.0
    exact_slot_alignment_bonus = 0.0
    exact_visibility_matches = focus_matches if specific_focus_anchor else (strict_matches or focus_matches)
    if same_region and exact_visibility_matches:
        visibility_score = 0.34 if first_place else 0.2
        if primary_matches:
            visibility_score += 0.12 if first_place else 0.08
        if focus_matches:
            visibility_score += 0.16 if first_place else 0.12
            if specific_focus_anchor:
                exact_slot_alignment_bonus = 0.35 if first_place else 0.42
        if len(exact_visibility_matches) >= 2:
            visibility_score += 0.035
        if authority_score > 0:
            visibility_score += min(0.08, authority_score * 0.16)
        if support_slot:
            support_bonus = 0.45 if specific_focus_anchor and focus_matches else (0.24 if focus_matches else (0.2 if primary_matches else 0.12))

    weak_terms = [
        term for term in _EXACT_LANDMARK_WEAK_SUBSTITUTE_TERMS
        if _normalize_city_token(term) in text
    ]
    wrong_city_terms = [
        term for term in _JEONJU_HANOK_WRONG_CITY_TERMS
        if family_id == "jeonbuk_jeonju_hanok" and _normalize_city_token(term) in text
    ]
    weak_substitute_demote = 0.0
    oldtown_substitute_demote = 0.0
    if same_region and not exact_visibility_matches and weak_terms:
        weak_substitute_demote = 0.2 if first_place else 0.08
        if role in {"meal", "cafe"}:
            weak_substitute_demote += 0.05 if first_place else 0.025
    if same_region and specific_focus_anchor and not focus_matches and matches:
        oldtown_substitute_demote = 0.22 if first_place else 0.16
    if wrong_city_terms:
        weak_substitute_demote = max(weak_substitute_demote, 0.32 if first_place else 0.14)

    missing_reason = None
    if same_region and not exact_visibility_matches:
        missing_reason = "no_exact_landmark_alias_match"
    elif not same_region:
        missing_reason = "region_mismatch"
    if wrong_city_terms:
        missing_reason = "wrong_city_jeonju_family:" + ",".join(wrong_city_terms[:3])

    return {
        "exact_landmark_visibility_score": round(visibility_score, 4),
        "exact_landmark_pool_included": bool(exact_visibility_matches),
        "exact_landmark_support_slot_bonus": round(support_bonus, 4),
        "exact_support_slot_visibility_bonus": round(support_bonus, 4),
        "exact_slot_alignment_bonus": round(exact_slot_alignment_bonus, 4),
        "exact_anchor_final_visibility": bool(focus_matches if specific_focus_anchor else exact_visibility_matches),
        "exact_landmark_missing_reason": missing_reason,
        "weak_substitute_demote": round(weak_substitute_demote, 4),
        "oldtown_substitute_demote": round(oldtown_substitute_demote, 4),
        "exact_landmark_match_terms": (strict_matches or matches)[:6],
        "exact_landmark_focus_match_terms": focus_matches[:4],
    }


def _score_busan_oldtown_family(
    place: dict | None,
    selected_anchor_family: dict | None,
    *,
    region: str | None = None,
    target_slot: str | None = None,
) -> dict:
    family = selected_anchor_family or {}
    family_id = str(family.get("family_id") or "")
    if str(region or "") != "부산" or family_id not in _BUSAN_OLDTOWN_FAMILY_IDS or not isinstance(place, dict):
        return {
            "busan_oldtown_family_score": 0.0,
            "busan_oldtown_pool_included": False,
            "busan_oldtown_drift_demote": 0.0,
            "busan_oldtown_support_slot_score": 0.0,
            "busan_oldtown_expected_landmark_visible": False,
        }

    text = _normalize_city_token(" ".join(str(place.get(k) or "") for k in (
        "name", "category", "category_name", "description", "overview", "address", "addr", "region_2"
    )))
    positive = [term for term in _BUSAN_OLDTOWN_POSITIVE_TERMS if _normalize_city_token(term) in text]
    drift = [term for term in _BUSAN_OLDTOWN_DRIFT_TERMS if _normalize_city_token(term) in text]
    first_place = str(target_slot or "") in {"anchor", "morning", "morning_2"}
    role = str(place.get("visit_role") or place.get("role") or "")

    family_score = 0.0
    support_score = 0.0
    if positive:
        family_score = 0.13 if first_place else 0.075
        if len(positive) >= 2:
            family_score += 0.025
        support_score = 0.055 if not first_place else 0.035

    drift_demote = 0.0
    if drift and not positive:
        drift_demote = 0.18 if first_place else 0.1
    elif drift and positive:
        drift_demote = 0.035

    return {
        "busan_oldtown_family_score": round(family_score, 4),
        "busan_oldtown_pool_included": bool(positive),
        "busan_oldtown_drift_demote": round(drift_demote, 4),
        "busan_oldtown_support_slot_score": round(support_score, 4),
        "busan_oldtown_expected_landmark_visible": bool(positive),
        "busan_oldtown_match_terms": positive[:6],
        "busan_oldtown_drift_terms": drift[:4],
    }


_BUSAN_EAST_COAST_FAMILY_IDS = {"busan_gijang_east_coast"}
_BUSAN_EAST_COAST_POSITIVE_TERMS = (
    "기장", "해동용궁사", "해동", "용궁사", "송정", "송정해수욕장", "오시리아",
    "기장해안", "기장해안도로", "죽성성당", "아난티", "청사포", "기장카페거리",
)
_BUSAN_EAST_COAST_DRIFT_TERMS = (
    "광안리", "광안대교", "민락", "더베이", "동백섬", "해운대해수욕장", "달맞이", "남포", "자갈치", "송도",
)


def _score_busan_east_coast_family(
    place: dict | None,
    selected_anchor_family: dict | None,
    *,
    region: str | None = None,
    target_slot: str | None = None,
) -> dict:
    family = selected_anchor_family or {}
    family_id = str(family.get("family_id") or "")
    if str(region or "") != "부산" or family_id not in _BUSAN_EAST_COAST_FAMILY_IDS or not isinstance(place, dict):
        return {
            "busan_east_coast_family_score": 0.0,
            "east_coast_family_preserved": False,
            "haeundae_gwangan_drift_demote": 0.0,
            "east_coast_support_slot_score": 0.0,
            "east_coast_expected_landmark_visible": False,
        }

    text = _normalize_city_token(" ".join(str(place.get(k) or "") for k in (
        "name", "category", "category_name", "description", "overview", "address", "addr", "region_2"
    )))
    positive = [term for term in _BUSAN_EAST_COAST_POSITIVE_TERMS if _normalize_city_token(term) in text]
    drift = [term for term in _BUSAN_EAST_COAST_DRIFT_TERMS if _normalize_city_token(term) in text]
    first_place = str(target_slot or "") in {"anchor", "morning", "morning_2"}

    family_score = 0.0
    support_score = 0.0
    if positive:
        family_score = 0.16 if first_place else 0.09
        if any(term in positive for term in ("해동용궁사", "해동", "용궁사")):
            family_score += 0.08 if first_place else 0.035
        if len(positive) >= 2:
            family_score += 0.025
        support_score = 0.06 if not first_place else 0.04

    drift_demote = 0.0
    if drift and not positive:
        drift_demote = 0.22 if first_place else 0.12
    elif drift and positive:
        drift_demote = 0.04

    return {
        "busan_east_coast_family_score": round(family_score, 4),
        "east_coast_family_preserved": bool(positive),
        "haeundae_gwangan_drift_demote": round(drift_demote, 4),
        "east_coast_support_slot_score": round(support_score, 4),
        "east_coast_expected_landmark_visible": bool(positive),
        "east_coast_match_terms": positive[:6],
        "east_coast_drift_terms": drift[:4],
    }


_BUSAN_SEOMYEON_FAMILY_IDS = {"busan_seomyeon"}
_BUSAN_SEOMYEON_POSITIVE_TERMS = (
    "서면", "전포", "전포동", "전포카페거리", "전리단길", "부전", "부전동", "부전시장",
    "부산진", "부산진구",
    "서면젊음의거리", "젊음의거리", "서면1번가", "서면일번가", "서면지하상가",
    "카페거리", "감성카페", "나이트", "밤", "bar", "펍",
)
_BUSAN_SEOMYEON_REPRESENTATIVE_TERMS = (
    "전포카페거리", "전리단길", "부전시장", "서면젊음의거리",
    "서면1번가", "서면일번가", "서면지하상가",
)
_BUSAN_SEOMYEON_DRIFT_TERMS = (
    "해운대", "광안리", "광안대교", "민락", "달맞이", "기장", "송정",
    "남포", "자갈치", "송도", "감천", "흰여울",
)
_BUSAN_SEOMYEON_WEAK_TERMS = (
    "구덕", "민속촌", "공공", "도서관", "문화센터", "체육센터", "행정",
    "주민센터", "오피스", "빌딩", "상가", "아파트",
)


def _score_busan_seomyeon_family(
    place: dict | None,
    selected_anchor_family: dict | None,
    landmark_authority_signal: dict | None = None,
    *,
    region: str | None = None,
    target_slot: str | None = None,
) -> dict:
    family = selected_anchor_family or {}
    family_id = str(family.get("family_id") or "")
    if str(region or "") != "부산" or family_id not in _BUSAN_SEOMYEON_FAMILY_IDS or not isinstance(place, dict):
        return {
            "seomyeon_family_score": 0.0,
            "seomyeon_nightlife_pool_included": False,
            "seomyeon_drift_demote": 0.0,
            "seomyeon_weak_candidate_demote": 0.0,
            "seomyeon_family_match_terms": [],
        }

    text = _normalize_city_token(" ".join(str(place.get(k) or "") for k in (
        "name", "category", "category_name", "description", "overview", "address", "addr", "region_2"
    )))
    first_place = str(target_slot or "") in {"anchor", "morning", "morning_2"}
    role = str(place.get("visit_role") or place.get("role") or "")
    positive = [term for term in _BUSAN_SEOMYEON_POSITIVE_TERMS if _normalize_city_token(term) in text]
    representative = [term for term in _BUSAN_SEOMYEON_REPRESENTATIVE_TERMS if _normalize_city_token(term) in text]
    drift = [term for term in _BUSAN_SEOMYEON_DRIFT_TERMS if _normalize_city_token(term) in text]
    weak = [term for term in _BUSAN_SEOMYEON_WEAK_TERMS if _normalize_city_token(term) in text]
    authority = landmark_authority_signal or {}
    authority_score = (
        float(authority.get("landmark_authority_score") or 0.0)
        + float(authority.get("external_verified_score") or 0.0)
        + float(authority.get("representative_confidence_score") or 0.0)
    )

    family_score = 0.0
    if positive:
        family_score = 0.18 if first_place else 0.11
        if representative:
            family_score += 0.12 if first_place else 0.08
        if role in {"cafe", "meal", "spot", "culture"}:
            family_score += 0.035
        if authority_score > 0:
            family_score += min(0.06, authority_score * 0.12)

    drift_demote = 0.0
    if drift and not positive:
        drift_demote = 0.24 if first_place else 0.13
    elif drift and positive:
        drift_demote = 0.04

    weak_demote = 0.0
    if weak and not representative:
        weak_demote = 0.18 if first_place else 0.08

    return {
        "seomyeon_family_score": round(family_score, 4),
        "seomyeon_family_pool_included": bool(place.get("_seomyeon_family_pool_included")),
        "seomyeon_nightlife_pool_included": bool(positive),
        "seomyeon_drift_demote": round(drift_demote, 4),
        "seomyeon_weak_candidate_demote": round(weak_demote, 4),
        "seomyeon_family_match_terms": (representative or positive)[:6],
    }


def _fetch_busan_seomyeon_family_candidates(
    conn,
    region: str,
    roles: list,
    selected_anchor_family: dict | None,
    zone_center: tuple | None = None,
    zone_radius_km: float | None = None,
) -> list:
    """Fetch verified Seomyeon/Jeonpo family candidates that may be absent from top-N popularity rows."""
    family_id = str((selected_anchor_family or {}).get("family_id") or "")
    if region != "부산" or family_id not in _BUSAN_SEOMYEON_FAMILY_IDS:
        return []

    names = [
        "서면 젊음의거리",
        "서면젊음의거리",
        "전포카페거리",
        "전포 카페거리",
        "전리단길",
        "부전시장",
        "부전마켓타운",
        "부산시민공원",
    ]
    name_patterns = [f"%{name}%" for name in names]
    effective_roles = list(dict.fromkeys([*(roles or []), "spot", "culture", "cafe", "meal"]))
    params: dict = {
        "region": region,
        "roles": effective_roles,
        "names": names,
        "name_patterns": name_patterns,
    }
    zone_clause = ""
    if zone_center and zone_radius_km:
        zone_clause = """
          AND (6371.0 * 2 * ASIN(SQRT(
              POWER(SIN((RADIANS(latitude) - RADIANS(%(zc_lat)s)) / 2), 2) +
              COS(RADIANS(%(zc_lat)s)) * COS(RADIANS(latitude)) *
              POWER(SIN((RADIANS(longitude) - RADIANS(%(zc_lon)s)) / 2), 2)
          ))) <= %(zone_radius_km)s"""
        params["zc_lat"] = zone_center[0]
        params["zc_lon"] = zone_center[1]
        params["zone_radius_km"] = max(float(zone_radius_km), 8.0)

    sql = f"""
        SELECT place_id, name, visit_role, estimated_duration,
               latitude, longitude, view_count, ai_tags, visit_time_slot,
               rating, review_count, data_source, first_image_url,
               ai_summary, overview, category_id, opening_hours, indoor_outdoor, region_1 AS region, region_2,
               NULL::text AS address, NULL::text AS addr
        FROM places
        WHERE region_1 = %(region)s
          AND category_id IN (12, 14, 38, 39)
          AND visit_role = ANY(%(roles)s)
          AND is_active = TRUE
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND (
              name = ANY(%(names)s)
              OR name ILIKE ANY(%(name_patterns)s)
          ){zone_clause}
        ORDER BY
          CASE WHEN name IN ('서면 젊음의거리', '서면젊음의거리', '전포카페거리', '부전시장', '부산시민공원') THEN 0 ELSE 1 END,
          CASE WHEN visit_role IN ('spot', 'culture') THEN 0 ELSE 1 END,
          view_count DESC NULLS LAST,
          place_id
        LIMIT 30
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]

    for row in rows:
        row["_landmark_candidate_entered_pool"] = True
        row["_representative_landmark_pool_status"] = "entered_pool"
        row["_representative_candidate_pool_included"] = True
        row["_alias_normalization_match"] = True
        row["_region_aware_alias_guard"] = "same_region"
        row["_family_candidate_lookup_bonus"] = 0.08
        row["_representative_alias_pool_included"] = True
        row["_representative_candidate_pool_reason"] = "busan_seomyeon_family_candidate_coverage"
        row["_seomyeon_family_pool_included"] = True
    return rows


_SEOUL_BROAD_DEFAULT_FAMILY_TERMS = {
    "gwanghwamun_jongno": ("경복궁", "광화문", "청계천", "인사동", "북촌", "삼청"),
    "bukchon_samcheong": ("북촌", "북촌한옥마을", "삼청", "삼청동길", "창덕궁", "전통찻집", "한옥카페"),
    "myeongdong_namsan": ("명동", "남산", "남산서울타워", "남산골한옥마을", "남산케이블카"),
    "yeouido_hangang": ("여의도", "여의도한강공원", "여의도공원", "샛강생태공원", "더현대서울"),
    "seongsu_forest": ("성수", "서울숲", "성수동카페거리", "연무장길", "로스터리", "편집숍"),
    "euljiro_hipjiro": ("을지로", "힙지로", "청계천", "노가리골목", "세운상가"),
    "hangang_city": ("한강공원", "망원한강공원", "양화한강공원", "난지한강공원"),
}
_SEOUL_BROAD_SEONGSU_DOMINANCE_TERMS = ("성수", "서울숲", "성수동카페거리", "연무장길")
_BUKCHON_EDITORIAL_DEPTH_TERMS = (
    "삼청동길", "삼청동", "삼청", "전통찻집", "찻집", "한옥카페", "궁궐", "창덕궁", "경복궁", "공방", "갤러리",
)
_SEONGSU_EDITORIAL_DEPTH_TERMS = (
    "연무장길", "연무장", "로스터리", "로스터", "성수동카페거리", "카페거리", "편집숍", "전시", "갤러리", "팝업", "수제화거리",
)
_SEOUL_EDITORIAL_WEAK_TERMS = (
    "감자탕", "기사식당", "체육센터", "주민센터", "도서관", "문화센터", "오피스", "빌딩", "상가",
)
_SEOUL_EDITORIAL_WEAK_SUPPORT_TERMS = (
    "감자탕", "국밥", "순두부", "막국수", "곱창", "고깃집", "버거", "분식", "기사식당",
    "체육센터", "주민센터", "도서관", "문화센터", "공공", "오피스", "빌딩", "상가",
)


def _score_seoul_editorial_depth(
    place: dict | None,
    selected_anchor_family: dict | None,
    landmark_authority_signal: dict | None = None,
    *,
    region: str | None = None,
    target_slot: str | None = None,
    default_preset_mode: bool = False,
) -> dict:
    if str(region or "") != "서울" or not isinstance(place, dict):
        return {
            "seoul_broad_default_family_balance": 0.0,
            "bukchon_editorial_depth_score": 0.0,
            "seongsu_editorial_depth_score": 0.0,
            "lifestyle_support_slot_visibility": 0.0,
            "representative_family_rotation_balance": 0.0,
            "seoul_broad_family_key": None,
            "seoul_editorial_weak_demote": 0.0,
            "seoul_editorial_depth_pool_included": False,
            "bukchon_editorial_candidate_exists": False,
            "bukchon_lifestyle_support_slot_score": 0.0,
            "seongsu_editorial_candidate_exists": False,
            "seongsu_support_slot_coherence": 0.0,
            "editorial_lifestyle_visibility_bonus": 0.0,
            "seoul_curated_district_priority": 0.0,
            "broad_seoul_demoted": 0.0,
            "district_identity_alignment": 0.0,
            "support_slot_role_diversity": 0.0,
        }

    text = _normalize_city_token(" ".join(str(place.get(k) or "") for k in (
        "name", "category", "category_name", "description", "overview", "address", "addr", "region_2"
    )))
    slot = str(target_slot or "")
    first_place = slot in {"anchor", "morning", "morning_2"}
    support_slot = not first_place
    role = str(place.get("visit_role") or "")
    family_id = str((selected_anchor_family or {}).get("family_id") or "")
    signal = landmark_authority_signal or {}
    authority_total = (
        float(signal.get("landmark_authority_score") or 0.0)
        + float(signal.get("external_verified_score") or 0.0)
        + float(signal.get("representative_confidence_score") or 0.0)
    )

    broad_family_key = None
    broad_matches: list[str] = []
    for key, terms in _SEOUL_BROAD_DEFAULT_FAMILY_TERMS.items():
        matches = [term for term in terms if _normalize_city_token(term) in text]
        if matches and len(matches) > len(broad_matches):
            broad_family_key = key
            broad_matches = matches

    broad_balance = 0.0
    rotation_balance = 0.0
    if default_preset_mode and not family_id and broad_matches:
        broad_balance = 0.055 if first_place else 0.035
        broad_balance += min(0.02, 0.006 * len(set(broad_matches)))
        broad_balance += min(0.018, authority_total * 0.04)
        rotation_balance = 0.025 if first_place else 0.012
        if broad_family_key == "seongsu_forest":
            # Keep Seongsu valid, but stop it from swallowing every broad Seoul default entry.
            broad_balance *= 0.68
            rotation_balance *= 0.62

    bukchon_matches = [term for term in _BUKCHON_EDITORIAL_DEPTH_TERMS if _normalize_city_token(term) in text]
    seongsu_matches = [term for term in _SEONGSU_EDITORIAL_DEPTH_TERMS if _normalize_city_token(term) in text]
    weak_matches = [term for term in _SEOUL_EDITORIAL_WEAK_TERMS if _normalize_city_token(term) in text]
    weak_support_matches = [
        term for term in _SEOUL_EDITORIAL_WEAK_SUPPORT_TERMS
        if _normalize_city_token(term) in text
    ]

    bukchon_score = 0.0
    if family_id == "seoul_bukchon" and bukchon_matches:
        bukchon_score = 0.17 if first_place else 0.105
        bukchon_score += min(0.06, 0.015 * len(set(bukchon_matches)))
        bukchon_score += min(0.035, authority_total * 0.08)

    seongsu_score = 0.0
    if family_id == "seoul_seongsu_cafe" and seongsu_matches:
        seongsu_score = 0.17 if first_place else 0.105
        seongsu_score += min(0.06, 0.015 * len(set(seongsu_matches)))
        seongsu_score += min(0.035, authority_total * 0.08)

    lifestyle_visibility = 0.0
    if bukchon_score or seongsu_score:
        lifestyle_visibility = min(0.11 if first_place else 0.075, max(bukchon_score, seongsu_score) * 0.42)
    elif default_preset_mode and broad_matches and not first_place:
        lifestyle_visibility = 0.045

    bukchon_support_score = 0.0
    if family_id == "seoul_bukchon" and support_slot and bukchon_matches:
        bukchon_support_score = 0.075
        if role in {"spot", "culture", "cafe"}:
            bukchon_support_score += 0.025
        bukchon_support_score += min(0.035, 0.01 * len(set(bukchon_matches)))

    seongsu_support_score = 0.0
    if family_id == "seoul_seongsu_cafe" and support_slot and seongsu_matches:
        seongsu_support_score = 0.085
        if role in {"cafe", "spot", "culture"}:
            seongsu_support_score += 0.03
        seongsu_support_score += min(0.04, 0.012 * len(set(seongsu_matches)))

    editorial_lifestyle_bonus = 0.0
    if bukchon_support_score or seongsu_support_score:
        editorial_lifestyle_bonus = min(0.09, max(bukchon_support_score, seongsu_support_score) * 0.52)

    weak_demote = 0.0
    if weak_matches and not (bukchon_matches or seongsu_matches):
        weak_demote = 0.12 if first_place else 0.06
    elif weak_matches:
        weak_demote = 0.035
    if support_slot and weak_support_matches:
        if family_id == "seoul_seongsu_cafe" and not seongsu_matches:
            weak_demote = max(weak_demote, 0.115)
        elif family_id == "seoul_bukchon" and not bukchon_matches:
            weak_demote = max(weak_demote, 0.095)
        elif not (bukchon_matches or seongsu_matches):
            weak_demote = max(weak_demote, 0.075)
    if default_preset_mode and not family_id and first_place and broad_family_key == "seongsu_forest":
        # Broad Seoul default should sample Seongsu, but not start there so often
        # that a narrow cafe/lifestyle pool can exhaust the route fallback.
        weak_demote = max(weak_demote, 0.095)

    curated_district_priority = 0.0
    district_identity_alignment = 0.0
    support_slot_role_diversity = 0.0
    district_family_ids = {
        "seoul_bukchon",
        "seoul_seongsu_cafe",
        "seoul_ikseon",
        "seoul_hannam",
        "seoul_euljiro_night",
        "seoul_gangnam",
        "seoul_yeouido",
    }
    positive_district_signal = max(
        bukchon_score,
        seongsu_score,
        bukchon_support_score,
        seongsu_support_score,
        lifestyle_visibility,
        editorial_lifestyle_bonus,
    )
    if family_id in district_family_ids:
        if positive_district_signal > 0:
            curated_district_priority = min(0.08, positive_district_signal * 0.38)
            district_identity_alignment = min(0.11, positive_district_signal * 0.52)
        elif support_slot and role in {"spot", "culture", "cafe"}:
            support_slot_role_diversity = 0.026
        elif support_slot and role == "meal":
            weak_demote = max(weak_demote, 0.045)
    broad_seoul_demoted = 0.0
    if default_preset_mode and not family_id:
        broad_seoul_demoted = 0.045 if first_place else 0.028

    return {
        "seoul_broad_default_family_balance": round(broad_balance, 4),
        "bukchon_editorial_depth_score": round(bukchon_score, 4),
        "seongsu_editorial_depth_score": round(seongsu_score, 4),
        "lifestyle_support_slot_visibility": round(lifestyle_visibility, 4),
        "representative_family_rotation_balance": round(rotation_balance, 4),
        "seoul_broad_family_key": broad_family_key,
        "seoul_broad_family_matches": broad_matches[:6],
        "bukchon_editorial_depth_matches": bukchon_matches[:6],
        "seongsu_editorial_depth_matches": seongsu_matches[:6],
        "seoul_editorial_weak_demote": round(weak_demote, 4),
        "seoul_editorial_depth_pool_included": bool(place.get("_seoul_editorial_depth_pool_included")),
        "bukchon_editorial_candidate_exists": bool(family_id == "seoul_bukchon" and bukchon_matches),
        "bukchon_lifestyle_support_slot_score": round(bukchon_support_score, 4),
        "seongsu_editorial_candidate_exists": bool(family_id == "seoul_seongsu_cafe" and seongsu_matches),
        "seongsu_support_slot_coherence": round(seongsu_support_score, 4),
        "editorial_lifestyle_visibility_bonus": round(editorial_lifestyle_bonus, 4),
        "seoul_curated_district_priority": round(curated_district_priority, 4),
        "broad_seoul_demoted": round(broad_seoul_demoted, 4),
        "district_identity_alignment": round(district_identity_alignment, 4),
        "support_slot_role_diversity": round(support_slot_role_diversity, 4),
    }


def _fetch_seoul_editorial_depth_candidates(
    conn,
    region: str,
    roles: list,
    selected_anchor_family: dict | None,
    selected_anchor: str | dict | set | None = None,
    *,
    default_preset_mode: bool = False,
    zone_center: tuple | None = None,
    zone_radius_km: float | None = None,
) -> list:
    if region != "서울":
        return []
    family_id = str((selected_anchor_family or {}).get("family_id") or "")
    names: list[str] = []
    if family_id == "seoul_bukchon":
        names.extend(["삼청동길", "삼청동", "전통찻집", "한옥카페", "창덕궁", "경복궁", "북촌공방", "북촌갤러리"])
    elif family_id == "seoul_seongsu_cafe":
        names.extend(["연무장길", "성수동 카페거리", "성수동카페거리", "로스터리", "편집숍", "수제화거리", "서울숲"])
    elif default_preset_mode and not selected_anchor:
        for terms in _SEOUL_BROAD_DEFAULT_FAMILY_TERMS.values():
            names.extend(terms)
    else:
        return []

    names = list(dict.fromkeys(name for name in names if len(str(name).strip()) >= 2))
    if not names:
        return []

    effective_roles = list(dict.fromkeys([*(roles or []), "spot", "culture", "cafe"]))
    params: dict = {
        "region": region,
        "roles": effective_roles,
        "names": names,
        "name_patterns": [f"%{name}%" for name in names],
    }
    zone_clause = ""
    if zone_center and zone_radius_km:
        zone_clause = """
          AND (6371.0 * 2 * ASIN(SQRT(
              POWER(SIN((RADIANS(latitude) - RADIANS(%(zc_lat)s)) / 2), 2) +
              COS(RADIANS(%(zc_lat)s)) * COS(RADIANS(latitude)) *
              POWER(SIN((RADIANS(longitude) - RADIANS(%(zc_lon)s)) / 2), 2)
          ))) <= %(zone_radius_km)s"""
        params["zc_lat"] = zone_center[0]
        params["zc_lon"] = zone_center[1]
        params["zone_radius_km"] = max(float(zone_radius_km), 8.0)

    sql = f"""
        SELECT place_id, name, visit_role, estimated_duration,
               latitude, longitude, view_count, ai_tags, visit_time_slot,
               rating, review_count, data_source, first_image_url,
               ai_summary, overview, category_id, opening_hours, indoor_outdoor, region_1 AS region, region_2,
               NULL::text AS address, NULL::text AS addr
        FROM places
        WHERE region_1 = %(region)s
          AND category_id IN (12, 14, 39)
          AND visit_role = ANY(%(roles)s)
          AND is_active = TRUE
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND (
              name = ANY(%(names)s)
              OR name ILIKE ANY(%(name_patterns)s)
          ){zone_clause}
        ORDER BY
          CASE WHEN visit_role IN ('spot', 'culture') THEN 0 ELSE 1 END,
          CASE WHEN category_id IN (12, 14) THEN 0 ELSE 1 END,
          view_count DESC NULLS LAST,
          place_id
        LIMIT 60
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]

    for row in rows:
        row["_landmark_candidate_entered_pool"] = True
        row["_representative_landmark_pool_status"] = "entered_pool"
        row["_representative_candidate_pool_included"] = True
        row["_alias_normalization_match"] = True
        row["_region_aware_alias_guard"] = "same_region"
        row["_family_candidate_lookup_bonus"] = 0.055 if family_id else 0.03
        row["_representative_alias_pool_included"] = True
        row["_representative_candidate_pool_reason"] = "seoul_editorial_depth_candidate_coverage"
        row["_seoul_editorial_depth_pool_included"] = True
    return rows


_SEOUL_CORE_FAMILY_IDS = {"seoul_gangnam", "seoul_yeouido", "seoul_euljiro_night"}
_SEOUL_GANGNAM_POSITIVE_TERMS = (
    "강남역", "강남", "신논현", "코엑스", "별마당도서관", "봉은사",
    "가로수길", "압구정", "청담", "선정릉", "선릉", "역삼",
)
_SEOUL_YEOUIDO_POSITIVE_TERMS = (
    "여의도", "여의도한강공원", "한강공원", "더현대서울", "더현대",
    "ifc", "ifc몰", "여의도공원", "샛강", "샛강생태공원", "63빌딩", "63스퀘어",
)
_SEOUL_FAMILY_DRIFT_TERMS = (
    "성수", "서울숲", "북촌", "삼청", "익선", "을지로", "힙지로", "홍대", "연남",
    "잠실", "석촌", "남산", "남대문",
)
_SEOUL_WEAK_LIFESTYLE_TERMS = (
    "도서관", "국회도서관", "구립", "시립", "문화센터", "교육문화", "주민센터",
    "행정", "구민회관", "체육센터", "브랜드", "사옥", "오피스", "빌딩",
    "플레어비", "도곡점", "메종", "럭셔리", "아파트", "상가",
)
_SEOUL_GANGNAM_DEPTH_TERMS = (
    "코엑스동측광장", "코엑스 아쿠아리움", "코엑스아쿠아리움", "코엑스", "별마당도서관",
    "신사동 가로수길", "신사동가로수길", "가로수길", "봉은사", "압구정", "청담",
    "신논현", "강남역", "강남대로",
)
_SEOUL_GANGNAM_DOMINANCE_TERMS = (
    "서울 선릉과 정릉", "서울선릉과정릉", "선릉과정릉",
)
_SEOUL_YEOUIDO_PUBLIC_FACILITY_TERMS = (
    "여의샛강도서관", "국회도서관", "공공도서관", "도서관",
)
_SEOUL_EULJIRO_NIGHT_POSITIVE_TERMS = (
    "을지로", "을지로3가", "을지로4가", "힙지로", "노가리골목", "노포", "청계천",
    "세운상가", "충무로", "인쇄골목", "익선동", "종로3가", "야간", "야경", "골목",
    "루프탑", "바", "bar", "레트로",
)
_SEOUL_EULJIRO_WEAK_TERMS = (
    "오피스", "사옥", "빌딩", "점심", "런치", "백반", "구내", "교육", "센터", "회관",
)
_SEOUL_GANGNAM_REPRESENTATIVE_TERMS = (
    "코엑스", "코엑스동측광장", "코엑스 아쿠아리움", "별마당도서관", "신사동 가로수길",
    "가로수길", "압구정 로데오거리", "청담패션거리", "봉은사", "선정릉",
)
_SEOUL_GANGNAM_WEAK_EDITORIAL_TERMS = (
    "청담근린공원", "청담도로공원", "오아시스 청담점", "근린공원", "도로공원",
    "청담점", "압구정곱창",
)


def _score_seoul_gangnam_yeouido_family(
    place: dict | None,
    selected_anchor_family: dict | None,
    landmark_authority_signal: dict | None = None,
    *,
    region: str | None = None,
    target_slot: str | None = None,
) -> dict:
    family = selected_anchor_family or {}
    family_id = str(family.get("family_id") or "")
    if str(region or "") != "서울" or family_id not in _SEOUL_CORE_FAMILY_IDS or not isinstance(place, dict):
        return {
            "seoul_external_authority_boost": 0.0,
            "gangnam_family_score": 0.0,
            "yeouido_family_score": 0.0,
            "seoul_weak_lifestyle_demote": 0.0,
            "seoul_family_pool_included": False,
            "gangnam_candidate_depth_score": 0.0,
            "gangnam_representative_pool_included": False,
            "gangnam_first_place_dominance_penalty": 0.0,
            "yeouido_public_facility_final_demote": 0.0,
            "family_candidate_depth_before_after": None,
            "euljiro_night_family_score": 0.0,
            "euljiro_nightlife_pool_included": False,
            "gangnam_editorial_representative_score": 0.0,
            "weak_editorial_first_place_demote": 0.0,
            "nightlife_coherence_score": 0.0,
        }

    text = _normalize_city_token(" ".join(str(place.get(k) or "") for k in (
        "name", "category", "category_name", "description", "overview", "address", "addr", "region_2"
    )))
    if family_id == "seoul_gangnam":
        positive_terms = _SEOUL_GANGNAM_POSITIVE_TERMS
    elif family_id == "seoul_yeouido":
        positive_terms = _SEOUL_YEOUIDO_POSITIVE_TERMS
    else:
        positive_terms = _SEOUL_EULJIRO_NIGHT_POSITIVE_TERMS
    positive = [term for term in positive_terms if _normalize_city_token(term) in text]
    drift = [term for term in _SEOUL_FAMILY_DRIFT_TERMS if _normalize_city_token(term) in text]
    weak = [term for term in _SEOUL_WEAK_LIFESTYLE_TERMS if _normalize_city_token(term) in text]
    gangnam_depth = [term for term in _SEOUL_GANGNAM_DEPTH_TERMS if _normalize_city_token(term) in text]
    gangnam_dominant = [
        term for term in _SEOUL_GANGNAM_DOMINANCE_TERMS if _normalize_city_token(term) in text
    ]
    yeouido_public_facility = [
        term for term in _SEOUL_YEOUIDO_PUBLIC_FACILITY_TERMS if _normalize_city_token(term) in text
    ]
    euljiro_nightlife = [
        term for term in _SEOUL_EULJIRO_NIGHT_POSITIVE_TERMS if _normalize_city_token(term) in text
    ]
    euljiro_weak = [
        term for term in _SEOUL_EULJIRO_WEAK_TERMS if _normalize_city_token(term) in text
    ]
    gangnam_representative = [
        term for term in _SEOUL_GANGNAM_REPRESENTATIVE_TERMS if _normalize_city_token(term) in text
    ]
    gangnam_weak_editorial = [
        term for term in _SEOUL_GANGNAM_WEAK_EDITORIAL_TERMS if _normalize_city_token(term) in text
    ]
    first_place = str(target_slot or "") in {"anchor", "morning", "morning_2"}
    role = str(place.get("visit_role") or place.get("role") or "")
    gangnam_generic_meal_first_place = (
        family_id == "seoul_gangnam"
        and first_place
        and any(_normalize_city_token(term) in text for term in ("곱창", "등심", "고깃집", "식당"))
    )

    signal = landmark_authority_signal or {}
    authority_total = (
        float(signal.get("landmark_authority_score") or 0.0)
        + float(signal.get("external_verified_score") or 0.0)
        + float(signal.get("external_popularity_score") or 0.0)
        + float(signal.get("representative_confidence_score") or 0.0)
    )
    external_boost = 0.0
    if positive and authority_total > 0:
        external_boost = min(0.11 if first_place else 0.065, authority_total * 0.55)

    family_score = 0.0
    if positive:
        family_score = 0.14 if first_place else 0.08
        if len(positive) >= 2:
            family_score += 0.025
        if any(_normalize_city_token(term) in text for term in ("코엑스", "별마당도서관", "봉은사", "선정릉", "여의도한강공원", "더현대서울", "여의도공원", "샛강생태공원", "63빌딩")):
            family_score += 0.035 if first_place else 0.02

    weak_demote = 0.0
    if weak and not positive:
        weak_demote = 0.2 if first_place else 0.11
    elif weak and positive:
        weak_demote = 0.045
    if weak and "별마당도서관" not in text:
        weak_demote += 0.08 if first_place else 0.04
    if drift and not positive:
        weak_demote += 0.12 if first_place else 0.07

    gangnam_candidate_depth_score = 0.0
    if family_id == "seoul_gangnam" and gangnam_depth:
        gangnam_candidate_depth_score = 0.52 if first_place else 0.12
        if len(gangnam_depth) >= 2:
            gangnam_candidate_depth_score += 0.04
        if authority_total > 0:
            gangnam_candidate_depth_score += min(0.08, authority_total * 0.22)

    gangnam_first_place_dominance_penalty = 0.0
    if family_id == "seoul_gangnam" and first_place and gangnam_dominant:
        gangnam_first_place_dominance_penalty = 0.72
    if family_id == "seoul_gangnam" and first_place and not positive and not gangnam_depth:
        weak_demote += 0.18

    yeouido_public_facility_final_demote = 0.0
    if family_id == "seoul_yeouido" and yeouido_public_facility:
        yeouido_public_facility_final_demote = 0.3 if first_place else 0.16
        if not positive:
            yeouido_public_facility_final_demote += 0.04

    euljiro_night_family_score = 0.0
    nightlife_coherence_score = 0.0
    if family_id == "seoul_euljiro_night" and euljiro_nightlife:
        euljiro_night_family_score = 0.2 if first_place else 0.105
        nightlife_coherence_score = min(0.14 if first_place else 0.08, 0.032 * len(set(euljiro_nightlife)))
        if authority_total > 0:
            euljiro_night_family_score += min(0.055, authority_total * 0.16)

    gangnam_editorial_representative_score = 0.0
    if family_id == "seoul_gangnam" and gangnam_representative:
        gangnam_editorial_representative_score = 0.18 if first_place else 0.075
        if any(_normalize_city_token(term) in text for term in ("코엑스", "별마당도서관", "가로수길", "압구정로데오거리", "청담패션거리")):
            gangnam_editorial_representative_score += 0.06 if first_place else 0.025

    weak_editorial_first_place_demote = 0.0
    if first_place:
        if family_id == "seoul_gangnam" and gangnam_weak_editorial and not gangnam_representative:
            weak_editorial_first_place_demote = 0.3
        elif (
            family_id == "seoul_gangnam"
            and (role in {"meal", "cafe"} or gangnam_generic_meal_first_place)
            and not gangnam_representative
        ):
            weak_editorial_first_place_demote = 0.48
        elif family_id == "seoul_euljiro_night" and euljiro_weak and not euljiro_nightlife:
            weak_editorial_first_place_demote = 0.18

    return {
        "seoul_external_authority_boost": round(external_boost, 4),
        "gangnam_family_score": round(family_score if family_id == "seoul_gangnam" else 0.0, 4),
        "yeouido_family_score": round(family_score if family_id == "seoul_yeouido" else 0.0, 4),
        "seoul_weak_lifestyle_demote": round(min(0.28, weak_demote), 4),
        "seoul_family_pool_included": bool(positive),
        "gangnam_candidate_depth_score": round(gangnam_candidate_depth_score, 4),
        "gangnam_representative_pool_included": bool(family_id == "seoul_gangnam" and gangnam_depth),
        "gangnam_first_place_dominance_penalty": round(gangnam_first_place_dominance_penalty, 4),
        "yeouido_public_facility_final_demote": round(min(0.34, yeouido_public_facility_final_demote), 4),
        "family_candidate_depth_before_after": {
            "family_id": family_id,
            "positive_match_count": len(positive),
            "gangnam_depth_match_count": len(gangnam_depth) if family_id == "seoul_gangnam" else 0,
            "yeouido_public_facility_match_count": len(yeouido_public_facility) if family_id == "seoul_yeouido" else 0,
        },
        "euljiro_night_family_score": round(euljiro_night_family_score, 4),
        "euljiro_nightlife_pool_included": bool(family_id == "seoul_euljiro_night" and euljiro_nightlife),
        "gangnam_editorial_representative_score": round(gangnam_editorial_representative_score, 4),
        "weak_editorial_first_place_demote": round(weak_editorial_first_place_demote, 4),
        "nightlife_coherence_score": round(nightlife_coherence_score, 4),
        "seoul_family_match_terms": positive[:6],
        "seoul_weak_lifestyle_terms": weak[:4],
        "seoul_family_drift_terms": drift[:4],
    }


_TARGETED_SEOUL_BROAD_SUPPORT_TERMS = (
    "여의도", "한강", "여의도공원", "샛강", "을지로", "힙지로", "청계천",
    "명동", "남산", "서울숲", "성수", "경복궁", "광화문", "북촌", "삼청",
)
_TARGETED_GIJANG_SUPPORT_TERMS = (
    "해동용궁사", "용궁사", "송정", "송정해수욕장", "청사포", "오시리아",
    "기장", "죽성성당", "기장해안", "해운대 그린레일웨이",
)
_TARGETED_GIJANG_DRIFT_TERMS = (
    "광안리", "광안대교", "민락", "남포", "자갈치", "서면", "전포",
)
_TARGETED_GANGNAM_SUPPORT_TERMS = (
    "코엑스", "별마당", "봉은사", "가로수길", "압구정", "청담", "선정릉",
    "신논현", "강남역", "로데오", "패션거리",
)
_TARGETED_GANGNAM_WEAK_TERMS = (
    "개나리공원", "근린공원", "도로공원", "곱창", "막국수", "민물장어",
    "일반음식점", "오피스", "상가",
)
_TARGETED_JINJU_SUPPORT_TERMS = (
    "진주성", "촉석루", "남강", "의암", "진주향교", "국립진주박물관",
    "진주성 주변", "역사", "유등",
)
_TARGETED_JINJU_WEAK_TERMS = (
    "재봉틀", "어린이박물관", "맥주", "갈비탕", "냉면", "카페", "공방", "전수관",
)

_SUPPORT_SLOT_GANGNAM_REPRESENTATIVE_TERMS = (
    "코엑스", "별마당", "봉은사", "가로수길", "압구정", "청담", "로데오",
    "선정릉", "신논현", "강남역", "스타필드", "아쿠아리움", "패션",
)
_SUPPORT_SLOT_GANGNAM_WEAK_TERMS = (
    "곱창", "막국수", "민물장어", "진해장", "돈까스", "마초쉐프", "알라프리마",
    "일반음식점", "파인다이닝", "근린공원", "도로공원", "성당", "전수교육관",
    "국가무형유산전수교육관", "전기박물관", "문화원", "예림당아트홀", "국기원",
    "고깃집열", "논현문화마루", "동달식당", "럭셔리 meal", "럭셔리식당",
)
_SUPPORT_SLOT_JINJU_REPRESENTATIVE_TERMS = (
    "진주성", "촉석루", "남강", "의암", "국립진주박물관", "진주향교",
    "남강댐", "유등", "유등테마공원", "소망진산", "중앙시장", "역사", "문화관", "성곽",
)
_SUPPORT_SLOT_JINJU_WEAK_TERMS = (
    "재봉틀", "어린이", "갈비탕", "안의갈비탕", "냉면", "식당", "마롱", "카페",
    "의곡사", "연화사", "북경장", "맥주", "맥주협동조합", "프로스트맥주", "공방",
    "목공예", "스텝온더그라운드", "용호정원", "아오라", "천수식당", "천황식당",
)

_SUPPORT_SLOT_SEONGSU_POSITIVE_TERMS = (
    "성수", "서울숲", "연무장길", "카페거리", "로스터리", "편집숍", "수제화거리",
    "전시", "갤러리", "팝업", "디저트", "산책",
)
_SUPPORT_SLOT_SEONGSU_WEAK_TERMS = (
    "국밥", "감자탕", "대돈집", "신의한국수", "버거", "일반음식점", "해장",
    "생활", "새활용플라자", "공공", "오피스", "도쎄멕시칸", "성수망치버거",
)

_SUPPORT_SLOT_GIJANG_POSITIVE_TERMS = (
    "해동용궁사", "용궁사", "송정", "청사포", "오시리아", "기장", "죽성성당",
    "해안", "바다", "오션", "카페", "드라이브", "항구", "산책",
)
_SUPPORT_SLOT_GIJANG_WEAK_TERMS = (
    "제주항통갈치", "롯데월드", "어드벤처", "테마파크", "해운대문화회관",
    "도서관", "실내", "문화회관", "일반음식점", "다솥맛집", "조현화랑", "하진이네",
    "맘보식당", "하가원", "갤러리이알디",
)

_SUPPORT_SLOT_EULJIRO_NIGHTLIFE_TERMS = (
    "을지로", "을지로3가", "을지로4가", "힙지로", "노가리골목", "노포",
    "세운상가", "충무로", "인쇄골목", "청계천", "루프탑", "바", "펍",
    "야장", "골목", "레트로", "조명", "야간",
)
_SUPPORT_SLOT_EULJIRO_CORE_TERMS = (
    "을지로", "을지로3가", "을지로4가", "힙지로", "노가리골목",
    "세운상가", "충무로 인쇄골목", "청계천",
)
_SUPPORT_SLOT_EULJIRO_WEAK_TERMS = (
    "오피스", "업무지구", "사무", "점심", "구내", "기사식당", "백반",
    "돈까스", "전시관", "교육", "문화센터", "문화원", "국악당", "주차장", "상가",
    "남산", "남대문", "덕수궁", "동대문", "백범", "롯데호텔", "중구문화원",
    "커뮤니티하우스", "기념관",
)

_SUPPORT_SLOT_GWANGAN_NIGHT_WEAK_TERMS = (
    "돼지국밥", "수변최고돼지국밥", "수영 돼지국밥", "해장", "감자탕",
    "순두부", "일반음식점", "마린시티", "해운대리버크루즈", "바로해장",
    "국밥", "meal-first",
)

_SUPPORT_SLOT_GWANGAN_NIGHT_POSITIVE_TERMS = (
    "광안리", "광안대교", "민락", "수변", "바다", "야경", "루프탑", "바",
    "펍", "포차", "해변", "테마거리",
)


def _score_targeted_route_coherence(
    place: dict | None,
    selected_anchor_family: dict | None,
    *,
    region: str | None = None,
    target_slot: str | None = None,
    default_preset_mode: bool = False,
) -> dict:
    """Small bounded coherence signal for known residual route-quality cases."""
    # Guardrail: the first targeted tuning attempt increased NO_COURSE/P1 in
    # production probes. Keep the observability contract but disable score
    # influence until the next pass can be tested against a wider fixture.
    disabled_signal = {
        "targeted_route_coherence_score": 0.0,
        "support_slot_family_alignment": 0.0,
        "coherence_demote_reason": None,
        "broad_default_balance_score": 0.0,
        "editorial_route_alignment": 0.0,
        "targeted_coherence_positive_terms": [],
        "targeted_coherence_weak_terms": [],
        "targeted_coherence_demote": 0.0,
    }
    return disabled_signal
    if not isinstance(place, dict):
        return {
            "targeted_route_coherence_score": 0.0,
            "support_slot_family_alignment": 0.0,
            "coherence_demote_reason": None,
            "broad_default_balance_score": 0.0,
            "editorial_route_alignment": 0.0,
        }

    text = _normalize_city_token(" ".join(str(place.get(k) or "") for k in (
        "name", "category", "category_name", "description", "overview", "address", "addr", "region_2"
    )))
    family_id = str((selected_anchor_family or {}).get("family_id") or "")
    slot = str(target_slot or "")
    first_place = slot in {"anchor", "morning", "morning_2"}
    support_slot = not first_place
    role = str(place.get("visit_role") or place.get("role") or "")

    alignment = 0.0
    balance = 0.0
    editorial = 0.0
    demote = 0.0
    reason = None
    positive_terms: list[str] = []
    weak_terms: list[str] = []

    if str(region or "") == "서울" and default_preset_mode and not family_id:
        positive_terms = [term for term in _TARGETED_SEOUL_BROAD_SUPPORT_TERMS if _normalize_city_token(term) in text]
        if positive_terms and support_slot:
            balance = 0.045
            alignment = min(0.055, 0.018 * len(set(positive_terms)))
            if any(term in positive_terms for term in ("여의도", "한강", "을지로", "힙지로", "명동", "남산")):
                balance += 0.025
        if role in {"meal", "cafe"} and support_slot and not positive_terms:
            demote = max(demote, 0.045)
            reason = "seoul_broad_default_support_weak_fit"

    elif str(region or "") == "부산" and family_id == "busan_gijang_east_coast":
        positive_terms = [term for term in _TARGETED_GIJANG_SUPPORT_TERMS if _normalize_city_token(term) in text]
        weak_terms = [term for term in _TARGETED_GIJANG_DRIFT_TERMS if _normalize_city_token(term) in text]
        if positive_terms:
            alignment = 0.07 if support_slot else 0.035
            editorial = min(0.05, 0.015 * len(set(positive_terms)))
        if weak_terms and not positive_terms:
            demote = max(demote, 0.09 if support_slot else 0.06)
            reason = "gijang_east_coast_support_drift:" + ",".join(weak_terms[:3])

    elif str(region or "") == "서울" and family_id == "seoul_gangnam":
        positive_terms = [term for term in _TARGETED_GANGNAM_SUPPORT_TERMS if _normalize_city_token(term) in text]
        weak_terms = [term for term in _TARGETED_GANGNAM_WEAK_TERMS if _normalize_city_token(term) in text]
        if positive_terms:
            alignment = 0.065 if support_slot else 0.025
            editorial = min(0.045, 0.014 * len(set(positive_terms)))
        if weak_terms and not positive_terms:
            demote = max(demote, 0.105 if support_slot else 0.08)
            reason = "gangnam_weak_support_slot:" + ",".join(weak_terms[:3])

    elif str(region or "") == "경남" and family_id == "gyeongnam_jinju_history":
        positive_terms = [term for term in _TARGETED_JINJU_SUPPORT_TERMS if _normalize_city_token(term) in text]
        weak_terms = [term for term in _TARGETED_JINJU_WEAK_TERMS if _normalize_city_token(term) in text]
        if positive_terms:
            alignment = 0.085 if support_slot else 0.035
            editorial = min(0.055, 0.018 * len(set(positive_terms)))
        if weak_terms and not positive_terms:
            demote = max(demote, 0.13 if support_slot else 0.09)
            reason = "jinju_history_support_drift:" + ",".join(weak_terms[:3])

    targeted_score = max(0.0, alignment + balance + editorial - demote)
    return {
        "targeted_route_coherence_score": round(targeted_score, 4),
        "support_slot_family_alignment": round(alignment, 4),
        "coherence_demote_reason": reason,
        "broad_default_balance_score": round(balance, 4),
        "editorial_route_alignment": round(editorial, 4),
        "targeted_coherence_positive_terms": positive_terms[:6],
        "targeted_coherence_weak_terms": weak_terms[:4],
        "targeted_coherence_demote": round(demote, 4),
    }


def _score_support_slot_family_assembly(
    place: dict | None,
    selected_anchor_family: dict | None,
    *,
    region: str | None = None,
    selected_anchor: str | dict | None = None,
    target_slot: str | None = None,
) -> dict:
    """Bounded support-slot alignment for residual Gangnam/Jinju coherence."""
    empty = {
        "support_slot_family_assembly_score": 0.0,
        "representative_support_slot_alignment": 0.0,
        "weak_support_slot_demote": 0.0,
        "support_slot_coherence_balance": 0.0,
        "editorial_support_slot_match": False,
        "support_slot_family_match_terms": [],
        "weak_support_slot_terms": [],
        "support_slot_editorial_contamination": False,
        "representative_support_purity_score": 0.0,
        "residual_cleanup_applied": False,
        "weak_contamination_repeat": False,
        "support_slot_minimal_cleanup": False,
        "runtime_stability_guard": True,
    }
    if not isinstance(place, dict):
        return empty

    slot = str(target_slot or "")
    if slot in {"anchor", "morning", "morning_2"}:
        return empty

    text = _normalize_city_token(" ".join(str(place.get(k) or "") for k in (
        "name", "category", "category_name", "description", "overview", "address", "addr", "region_2"
    )))
    family_id = str((selected_anchor_family or {}).get("family_id") or "")
    anchor_text = _normalize_city_token(str(selected_anchor or ""))
    is_gangnam = str(region or "") == "서울" and (
        family_id == "seoul_gangnam"
        or any(token in anchor_text for token in ("강남", "신논현", "코엑스", "봉은사", "가로수길", "압구정", "청담"))
    )
    is_jinju = str(region or "") == "경남" and (
        family_id == "gyeongnam_jinju_history"
        or any(token in anchor_text for token in ("진주", "촉석루", "남강", "진주성"))
    )
    is_seongsu = str(region or "") == "서울" and (
        family_id == "seoul_seongsu_cafe"
        or any(token in anchor_text for token in ("성수", "서울숲", "연무장", "카페"))
    )
    is_gijang = str(region or "") == "부산" and (
        family_id == "busan_gijang_east_coast"
        or any(token in anchor_text for token in ("기장", "해동용궁사", "용궁사", "송정", "오시리아"))
    )
    is_euljiro = str(region or "") == "서울" and (
        family_id == "seoul_euljiro_night"
        or any(token in anchor_text for token in ("을지로", "힙지로", "청계천", "노가리", "야간"))
    )
    is_gwangan_night = str(region or "") == "부산" and (
        family_id in {"busan_gwangan", "busan_gwangan_night"}
        or any(token in anchor_text for token in ("광안리", "광안대교", "민락", "야경"))
    )
    if not is_gangnam and not is_jinju and not is_seongsu and not is_gijang and not is_euljiro and not is_gwangan_night:
        return empty

    role = str(place.get("visit_role") or place.get("role") or "")
    nightlife_alignment = 0.0
    nightlife_depth = 0.0
    support_editorial_contamination = False
    representative_support_purity_score = 0.0
    if is_euljiro:
        positive = [term for term in _SUPPORT_SLOT_EULJIRO_NIGHTLIFE_TERMS if _normalize_city_token(term) in text]
        core = [term for term in _SUPPORT_SLOT_EULJIRO_CORE_TERMS if _normalize_city_token(term) in text]
        weak = [term for term in _SUPPORT_SLOT_EULJIRO_WEAK_TERMS if _normalize_city_token(term) in text]
        alignment = min(0.12, 0.03 * len(set(positive))) if positive else 0.0
        balance = 0.06 if positive and role in {"spot", "culture", "cafe", "meal"} else 0.0
        nightlife_alignment = alignment
        nightlife_depth = min(0.13, 0.022 * len(set(positive + core))) if positive or core else 0.0
        demote = 0.0
        if weak and not positive:
            demote = 0.16 if role in {"spot", "culture"} else 0.12
            support_editorial_contamination = True
        elif role == "meal" and not positive:
            demote = 0.1
            support_editorial_contamination = True
        elif role == "cafe" and not positive:
            demote = 0.08
            support_editorial_contamination = True
        representative_support_purity_score = max(0.0, nightlife_depth + alignment - demote)
    elif is_gangnam:
        positive = [term for term in _SUPPORT_SLOT_GANGNAM_REPRESENTATIVE_TERMS if _normalize_city_token(term) in text]
        weak = [term for term in _SUPPORT_SLOT_GANGNAM_WEAK_TERMS if _normalize_city_token(term) in text]
        alignment = min(0.09, 0.028 * len(set(positive))) if positive else 0.0
        balance = 0.035 if positive and role in {"spot", "culture", "cafe"} else 0.0
        if role == "meal" and positive:
            balance = 0.015
        demote = 0.0
        if weak and not positive:
            demote = 0.16 if role in {"spot", "culture"} else 0.13
            support_editorial_contamination = True
        elif role == "meal" and not positive:
            demote = 0.095
            support_editorial_contamination = True
        representative_support_purity_score = max(0.0, alignment + balance - demote)
    elif is_jinju:
        positive = [term for term in _SUPPORT_SLOT_JINJU_REPRESENTATIVE_TERMS if _normalize_city_token(term) in text]
        weak = [term for term in _SUPPORT_SLOT_JINJU_WEAK_TERMS if _normalize_city_token(term) in text]
        alignment = min(0.12, 0.035 * len(set(positive))) if positive else 0.0
        balance = 0.055 if positive and role in {"spot", "culture", "cafe"} else 0.0
        if role == "meal" and positive:
            balance = 0.02
        demote = 0.0
        if weak and not positive:
            demote = 0.2 if role in {"spot", "culture"} else 0.15
            support_editorial_contamination = True
        elif role == "meal" and not positive:
            demote = 0.18
            support_editorial_contamination = True
        elif role == "cafe" and not positive:
            demote = 0.1
            support_editorial_contamination = True
        representative_support_purity_score = max(0.0, alignment + balance - demote)
    elif is_seongsu:
        positive = [term for term in _SUPPORT_SLOT_SEONGSU_POSITIVE_TERMS if _normalize_city_token(term) in text]
        weak = [term for term in _SUPPORT_SLOT_SEONGSU_WEAK_TERMS if _normalize_city_token(term) in text]
        alignment = min(0.1, 0.026 * len(set(positive))) if positive else 0.0
        balance = 0.05 if positive and role in {"spot", "culture", "cafe"} else 0.0
        if role == "meal" and positive:
            balance = 0.015
        demote = 0.0
        if weak and not positive:
            demote = 0.15 if role in {"spot", "culture"} else 0.13
            support_editorial_contamination = True
        elif role == "meal" and not positive:
            demote = 0.12
            support_editorial_contamination = True
        elif role == "cafe" and not positive:
            demote = 0.08
            support_editorial_contamination = True
        representative_support_purity_score = max(0.0, alignment + balance - demote)
    elif is_gijang:
        positive = [term for term in _SUPPORT_SLOT_GIJANG_POSITIVE_TERMS if _normalize_city_token(term) in text]
        weak = [term for term in _SUPPORT_SLOT_GIJANG_WEAK_TERMS if _normalize_city_token(term) in text]
        alignment = min(0.095, 0.024 * len(set(positive))) if positive else 0.0
        balance = 0.05 if positive and role in {"spot", "culture", "cafe"} else 0.0
        if role == "meal" and positive:
            balance = 0.015
        demote = 0.0
        if weak and not positive:
            demote = 0.16 if role in {"spot", "culture"} else 0.14
            support_editorial_contamination = True
        elif role == "meal" and not positive:
            demote = 0.12
            support_editorial_contamination = True
        representative_support_purity_score = max(0.0, alignment + balance - demote)
    else:
        positive = [term for term in _SUPPORT_SLOT_GWANGAN_NIGHT_POSITIVE_TERMS if _normalize_city_token(term) in text]
        weak = [term for term in _SUPPORT_SLOT_GWANGAN_NIGHT_WEAK_TERMS if _normalize_city_token(term) in text]
        alignment = min(0.08, 0.025 * len(set(positive))) if positive else 0.0
        balance = 0.04 if positive and role in {"spot", "culture", "cafe"} else 0.0
        demote = 0.0
        if weak and not positive:
            demote = 0.14 if role == "meal" else 0.1
            support_editorial_contamination = True
        elif role == "meal" and not positive:
            demote = 0.1
            support_editorial_contamination = True
        representative_support_purity_score = max(0.0, alignment + balance - demote)

    score = max(0.0, alignment + balance - demote)
    return {
        "support_slot_family_assembly_score": round(score, 4),
        "representative_support_slot_alignment": round(alignment, 4),
        "weak_support_slot_demote": round(demote, 4),
        "support_slot_coherence_balance": round(balance, 4),
        "editorial_support_slot_match": bool(positive),
        "support_slot_family_match_terms": positive[:6],
        "weak_support_slot_terms": weak[:5],
        "nightlife_support_slot_alignment": round(nightlife_alignment, 4),
        "nightlife_family_depth": round(nightlife_depth, 4),
        "nightlife_core_match_terms": core[:6] if is_euljiro else [],
        "central_seoul_broad_demote": 0.0,
        "support_slot_purity_score": 0.0,
        "support_slot_editorial_contamination": bool(support_editorial_contamination),
        "representative_support_purity_score": round(representative_support_purity_score, 4),
        "residual_cleanup_applied": bool(support_editorial_contamination and weak),
        "weak_contamination_repeat": bool(weak),
        "support_slot_minimal_cleanup": bool(support_editorial_contamination and weak),
        "runtime_stability_guard": True,
    }


_CURATED_NIGHT_FAMILY_TERMS: dict[str, tuple[str, ...]] = {
    "서울": (
        "을지로", "노가리", "힙지로", "청계천", "익선", "한남", "성수", "서울숲",
        "한강", "루프탑", "rooftop", "bar", "펍", "노포", "삼청", "남산", "야경", "야간", "골목",
    ),
    "부산": (
        "광안", "광안대교", "민락", "수변", "해운대", "청사포", "송정", "기장",
        "해안", "coastal", "밤바다", "남포", "흰여울", "자갈치", "송도", "야경",
    ),
    "제주": (
        "애월", "밤바다", "중문", "드라이브", "함덕", "협재", "해안", "해변", "야경", "산책",
    ),
    "강원": (
        "안목", "밤바다", "속초", "영랑호", "경포", "해변", "해안", "야경", "산책",
    ),
    "전북": (
        "한옥마을", "전동성당", "남부시장", "야시장", "야경", "전주", "전통", "산책",
    ),
    "전주": (
        "한옥마을", "전동성당", "남부시장", "야시장", "야경", "전주", "전통", "산책",
    ),
    "경남": (
        "남강", "촉석루", "유등", "진주", "야경", "강변", "산책", "통영", "강구안", "디피랑",
    ),
    "진주": (
        "남강", "촉석루", "유등", "진주", "야경", "강변", "산책",
    ),
    "대구": (
        "김광석", "수성못", "야경", "야간", "동성로", "서문시장", "산책",
    ),
}

_CURATED_NIGHT_GENERIC_TERMS: tuple[str, ...] = (
    "야경", "야간", "밤바다", "수변", "해변", "해안", "산책", "전망", "루프탑",
    "rooftop", "bar", "pub", "펍", "바", "노포", "포차", "야시장", "시장", "골목",
    "강변", "호수", "대교", "전망대",
)

_CURATED_NIGHT_WEAK_TERMS: tuple[str, ...] = (
    "도서관", "주민센터", "행정", "관공서", "문화센터", "문화원", "체육센터",
    "교육관", "교육문화", "복지관", "공공", "사무", "오피스", "박물관", "미술관",
    "전시관", "체험관", "공예관", "워크숍", "클래스", "daytime",
)

_CURATED_NIGHT_DAYTIME_MEAL_TERMS: tuple[str, ...] = (
    "해장", "국밥", "감자탕", "갈비탕", "냉면", "기사식당", "백반", "순두부",
)


def _score_curated_night_family(
    place: dict | None,
    *,
    region: str | None = None,
    selected_anchor: str | dict | None = None,
    selected_anchor_family: dict | None = None,
    flow_profile: dict | None = None,
    target_slot: str | None = None,
    late_context: bool = False,
) -> dict:
    """Advisory curated night family layer for late/night routes.

    This is intentionally bounded: it nudges night-safe representative places
    within the existing region/family scoring, but does not insert or lock a route.
    """
    empty = {
        "curated_night_family_applied": False,
        "night_representative_preference": 0.0,
        "nightlife_curated_alignment": 0.0,
        "night_vibe_coherence": 0.0,
        "curated_night_support_slot": 0.0,
        "curated_night_match_terms": [],
        "curated_night_weak_demote": 0.0,
    }
    if not isinstance(place, dict):
        return empty

    family_id = str((selected_anchor_family or {}).get("family_id") or "")
    flow_name = str((flow_profile or {}).get("inferred_flow_profile") or (flow_profile or {}).get("flow_profile") or "")
    anchor_text = _normalize_city_token(str(selected_anchor or "") + " " + family_id + " " + flow_name)
    night_context = bool(late_context) or any(
        _normalize_city_token(term) in anchor_text
        for term in ("야간", "야경", "밤", "night", "nightlife", "nightview", "노포", "힙지로", "을지로", "광안리")
    ) or flow_name == "night_city"
    if not night_context:
        return empty

    place_text = _normalize_city_token(" ".join(str(place.get(k) or "") for k in (
        "name", "category", "category_name", "description", "overview", "address", "addr", "region_2"
    )))
    region_key = str(region or "")
    region_terms: list[str] = list(_CURATED_NIGHT_FAMILY_TERMS.get(region_key, ()))
    if "전주" in anchor_text:
        region_terms.extend(_CURATED_NIGHT_FAMILY_TERMS.get("전주", ()))
    if "진주" in anchor_text:
        region_terms.extend(_CURATED_NIGHT_FAMILY_TERMS.get("진주", ()))
    if not region_terms:
        region_terms = list(_CURATED_NIGHT_GENERIC_TERMS)

    family_tokens = [
        str(token)
        for token in (selected_anchor_family or {}).get("tokens", [])
        if str(token or "").strip()
    ]
    all_positive_terms = list(dict.fromkeys(region_terms + family_tokens + list(_CURATED_NIGHT_GENERIC_TERMS)))
    matched_terms = [
        term for term in all_positive_terms
        if _normalize_city_token(term) and _normalize_city_token(term) in place_text
    ]
    weak_terms = [
        term for term in _CURATED_NIGHT_WEAK_TERMS
        if _normalize_city_token(term) and _normalize_city_token(term) in place_text
    ]
    daytime_meal_terms = [
        term for term in _CURATED_NIGHT_DAYTIME_MEAL_TERMS
        if _normalize_city_token(term) and _normalize_city_token(term) in place_text
    ]
    role = str(place.get("visit_role") or place.get("role") or "")
    slot = str(target_slot or "")
    support_slot = slot not in {"anchor", "morning", "morning_2"}
    has_family_or_region_match = bool(matched_terms)

    preference = min(0.11, 0.022 * len(set(matched_terms))) if matched_terms else 0.0
    alignment = 0.0
    coherence = 0.0
    support_bonus = 0.0
    if matched_terms:
        if any(_normalize_city_token(t) in place_text for t in _CURATED_NIGHT_GENERIC_TERMS):
            alignment = 0.045
        if role in {"spot", "culture", "cafe", "meal"}:
            coherence = 0.035
        if support_slot:
            support_bonus = 0.045
        else:
            preference += 0.025

    demote = 0.0
    if weak_terms and not has_family_or_region_match:
        demote = max(demote, 0.105 if support_slot else 0.08)
    if daytime_meal_terms and role == "meal" and not matched_terms:
        demote = max(demote, 0.075 if support_slot else 0.055)

    applied = bool(matched_terms or demote > 0)
    return {
        "curated_night_family_applied": applied,
        "night_representative_preference": round(min(preference, 0.14), 4),
        "nightlife_curated_alignment": round(alignment, 4),
        "night_vibe_coherence": round(coherence, 4),
        "curated_night_support_slot": round(support_bonus, 4),
        "curated_night_match_terms": matched_terms[:8],
        "curated_night_weak_demote": round(demote, 4),
    }


def _is_default_preset_mode(request: dict | None, themes: list | None) -> bool:
    if isinstance(request, dict) and request.get("default_preset_mode") is True:
        return True
    theme_tokens = [str(t or "").strip().lower() for t in (themes or []) if str(t or "").strip()]
    return not theme_tokens or all(token in _DEFAULT_PRESET_THEME_TOKENS for token in theme_tokens)


def _score_default_preset_landmark(
    place: dict | None,
    landmark_authority_signal: dict | None,
    *,
    default_preset_mode: bool = False,
    target_slot: str | None = None,
) -> dict:
    if not default_preset_mode or not isinstance(place, dict):
        return {
            "default_preset_mode": bool(default_preset_mode),
            "representative_landmark_selected": False,
            "default_preset_landmark_bonus": 0.0,
            "weird_candidate_demote": 0.0,
            "weird_candidate_demote_reason": None,
        }

    signal = landmark_authority_signal or {}
    slot = str(target_slot or "")
    role = str(place.get("visit_role") or place.get("role") or "")
    first_place_slot = slot in {"anchor", "morning", "morning_2"}
    has_landmark = bool(signal.get("landmark_authority_matches"))
    authority = float(signal.get("landmark_authority_score") or 0.0)
    confidence = float(signal.get("representative_confidence_score") or 0.0)
    representative_landmark_selected = has_landmark and (authority + confidence) > 0.04

    bonus = 0.0
    if representative_landmark_selected:
        bonus = 0.055 if first_place_slot else 0.028

    joined = _normalize_city_token(" ".join(str(place.get(k) or "") for k in (
        "name", "category", "category_name", "description", "overview", "address", "addr", "region_2"
    )))
    weird_hit = next((term for term in _DEFAULT_PRESET_WEIRD_TERMS if _normalize_city_token(term) in joined), None)
    weak_signal = float(signal.get("weak_generic_authority_demote") or 0.0)
    public_weak = bool(signal.get("public_data_weakness_reason"))
    demote = 0.0
    reason = None
    if not representative_landmark_selected and (weird_hit or weak_signal > 0 or public_weak) and role in {"spot", "culture"}:
        demote = 0.075 if first_place_slot else 0.04
        reason = f"default_preset_weird_candidate:{weird_hit or signal.get('weak_generic_authority_reason') or signal.get('public_data_weakness_reason')}"

    return {
        "default_preset_mode": True,
        "representative_landmark_selected": representative_landmark_selected,
        "default_preset_landmark_bonus": round(bonus, 4),
        "weird_candidate_demote": round(demote, 4),
        "weird_candidate_demote_reason": reason,
    }


_PUBLIC_FACILITY_TOURISM_DEMOTE_TERMS = (
    "도서관",
    "작은도서관",
    "공공도서관",
    "주민센터",
    "행정복지센터",
    "행정복지",
    "문화센터",
    "교육문화센터",
    "구민회관",
    "시민회관",
    "공공강당",
    "강당",
    "체육센터",
    "국민체육센터",
    "생활체육",
    "공공체육",
    "공공시설",
    "행정시설",
    "국기원",
    "태권도장",
    "훈련원",
    "연수센터",
)

_PUBLIC_FACILITY_TOURISM_POSITIVE_TERMS = (
    "해변",
    "해수욕장",
    "공원",
    "숲",
    "한옥",
    "시장",
    "야시장",
    "전망",
    "야경",
    "거리",
    "골목",
    "마을",
    "궁",
    "산책",
    "유적",
    "문화마을",
    "케이블카",
    "카페거리",
)


def _score_public_facility_tourism_fit(
    place: dict | None,
    landmark_authority_signal: dict | None,
    *,
    default_preset_mode: bool = False,
    target_slot: str | None = None,
    first_place: bool = False,
) -> dict:
    """Softly keep generic public facilities out of representative tourism slots."""
    if not isinstance(place, dict):
        return {
            "public_facility_demote": 0.0,
            "representative_tourism_fit": 0.0,
            "weak_public_facility_reason": None,
        }

    joined = _normalize_city_token(" ".join(str(place.get(k) or "") for k in (
        "name",
        "category",
        "category_name",
        "visit_role",
        "description",
        "overview",
        "address",
        "addr",
        "region",
        "region_1",
        "region_2",
    )))
    role = str(place.get("visit_role") or place.get("role") or "")
    slot = str(target_slot or "")
    representative_slot = first_place or slot in {"anchor", "morning", "morning_2"}
    authority = landmark_authority_signal or {}
    has_authority = bool(authority.get("landmark_authority_matches")) or (
        float(authority.get("landmark_authority_score") or 0.0)
        + float(authority.get("representative_confidence_score") or 0.0)
        + float(authority.get("representative_tourism_bonus") or 0.0)
    ) >= 0.08

    positive_hit = next(
        (term for term in _PUBLIC_FACILITY_TOURISM_POSITIVE_TERMS if _normalize_city_token(term) in joined),
        None,
    )
    public_hit = next(
        (term for term in _PUBLIC_FACILITY_TOURISM_DEMOTE_TERMS if _normalize_city_token(term) in joined),
        None,
    )

    representative_tourism_fit = 0.0
    if (has_authority or positive_hit) and role in {"spot", "culture"}:
        representative_tourism_fit = 0.025
        if representative_slot:
            representative_tourism_fit += 0.02
        if has_authority and positive_hit:
            representative_tourism_fit += 0.015

    if not public_hit:
        return {
            "public_facility_demote": 0.0,
            "representative_tourism_fit": round(min(0.06, representative_tourism_fit), 4),
            "weak_public_facility_reason": None,
        }

    # If a public-ish word appears inside a governed tourism landmark, keep it advisory only.
    if has_authority and positive_hit:
        return {
            "public_facility_demote": 0.0,
            "representative_tourism_fit": round(min(0.06, representative_tourism_fit), 4),
            "weak_public_facility_reason": None,
        }

    demote = 0.08
    if representative_slot:
        demote += 0.055
    if default_preset_mode:
        demote += 0.05
    if public_hit in {"도서관", "작은도서관", "공공도서관", "국기원"}:
        demote += 0.23
    if role not in {"spot", "culture"}:
        demote *= 0.75
    if has_authority:
        demote *= 0.55

    return {
        "public_facility_demote": round(min(0.48, demote), 4),
        "representative_tourism_fit": round(min(0.04, representative_tourism_fit), 4),
        "weak_public_facility_reason": f"weak_public_facility:{public_hit}",
    }


_NIGHT_SAFE_OUTDOOR_TERMS = (
    "야경", "야간", "밤바다", "산책", "수변", "해변", "해수욕장", "해안", "포구", "항",
    "전망", "전망대", "루프탑", "공원", "광장", "시장", "야시장", "거리", "골목",
    "대교", "다리", "등대", "포차", "노포", "바", "bar", "pub", "카페거리",
)

_NIGHT_RISKY_INDOOR_TERMS = (
    "박물관", "미술관", "문화원", "문화센터", "교육관", "전시관", "체험관", "도서관",
    "아트홀", "회관", "강당", "센터", "기념관", "실내", "몰", "백화점", "아쿠아리움",
)

_NIGHT_INDOOR_SEMANTIC_TERMS = (
    "문화관", "문화원", "문화센터", "체험관", "체험", "공예관", "공예", "전시관",
    "전시", "박물관", "미술관", "클래스", "교육관", "기념관", "갤러리", "gallery",
    "culture center", "culture centre", "culture lounge", "class", "workshop",
    "컬처", "컬쳐",
)

_NIGHT_INDOOR_EXCEPTION_TERMS = (
    "노포", "바", "bar", "pub", "루프탑", "야장", "포차", "야시장", "카페거리",
    "찻집", "카페", "베이커리", "디저트",
)

_KNOWN_NIGHT_CLOSED_INDOOR_CLOSE_MIN = {
    "북촌전통공예체험관": 18 * 60,
    "북촌문화센터": 18 * 60,
    "북촌 한옥청": 18 * 60,
    "락고재 컬처 라운지": 18 * 60,
    "락고재 컬쳐 라운지": 18 * 60,
    "락고재 컬쳐 라운지 애가헌": 18 * 60,
    "락고재 컬처 라운지 애가헌": 18 * 60,
}


def _coerce_opening_hours_text(value) -> str:
    if not value:
        return ""
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            parts.append(str(key))
            if isinstance(item, (list, tuple)):
                parts.extend(str(x) for x in item)
            elif isinstance(item, dict):
                parts.extend(f"{k}:{v}" for k, v in item.items())
            else:
                parts.append(str(item))
        return " ".join(parts)
    if isinstance(value, (list, tuple)):
        return " ".join(str(x) for x in value)
    return str(value)


def _extract_known_close_min(place: dict) -> tuple[int | None, str | None]:
    """Return a known closing minute when the data has an explicit close signal."""
    name = str(place.get("name") or "")
    for key, close_min in _KNOWN_NIGHT_CLOSED_INDOOR_CLOSE_MIN.items():
        if key in name:
            return close_min, f"known_closed_indoor:{key}"

    opening_text = _coerce_opening_hours_text(place.get("opening_hours"))
    if not opening_text:
        return None, None
    if any(term in opening_text.lower() for term in ("24", "24h", "24시간", "연중무휴", "상시", "open all day")):
        return None, "night_safe_indoor_exception:all_day"

    times: list[int] = []
    for hour, minute in re.findall(r"(\d{1,2})[:시](\d{2})?", opening_text):
        h = int(hour)
        m = int(minute or 0)
        if 0 <= h <= 24 and 0 <= m <= 59:
            times.append(h * 60 + m)
    if len(times) < 2:
        return None, None

    # Most source strings are ranges like 09:00~18:00. Use the latest daytime
    # value as close time; do not infer close from ambiguous single-time text.
    close_candidates = [value for value in times if 12 * 60 <= value <= 24 * 60]
    if not close_candidates:
        return None, None
    return max(close_candidates), "opening_hours_explicit_close"


def _score_night_operating_confidence(
    place: dict,
    flow_profile: dict | None,
    target_slot: str,
    *,
    late_context: bool = False,
    current_minute: int | None = None,
) -> dict:
    """Advisory confidence for late/night support slots.

    This never filters candidates. It preserves outdoor/night/coastal candidates
    while softly weakening risky indoor/public venues that are likely to have
    unreliable late operating hours.
    """
    if not late_context:
        return {
            "night_operating_confidence": 0.0,
            "indoor_night_confidence_demote": 0.0,
            "night_safe_outdoor_priority": 0.0,
            "nightlife_suitability_alignment": 0.0,
            "indoor_heavy_route_detected": False,
            "night_operating_confidence_reason": None,
            "operating_hours_known_closed": False,
            "night_indoor_strong_demote": 0.0,
            "relaxed_unknown_hours_allowed": False,
            "known_closed_removed": False,
            "night_safe_indoor_exception": False,
            "indoor_semantic_detected": False,
            "known_closed_indoor_removed": False,
            "night_indoor_semantic_demote": 0.0,
            "indoor_closing_time_applied": False,
        }

    text = " ".join(
        str(place.get(key) or "")
        for key in ("name", "visit_role", "category", "category_name", "description", "overview", "address", "addr", "indoor_outdoor")
    ).lower()
    profile = str((flow_profile or {}).get("inferred_flow_profile") or "").lower()
    slot = str(target_slot or "").lower()
    role = str(place.get("visit_role") or "").lower()

    outdoor_matches = [term for term in _NIGHT_SAFE_OUTDOOR_TERMS if term.lower() in text]
    indoor_matches = [term for term in _NIGHT_RISKY_INDOOR_TERMS if term.lower() in text]
    indoor_semantic_matches = [term for term in _NIGHT_INDOOR_SEMANTIC_TERMS if term.lower() in text]
    exception_matches = [term for term in _NIGHT_INDOOR_EXCEPTION_TERMS if term.lower() in text]
    is_night_context = (
        "night" in profile
        or "night" in slot
        or slot in {"dinner", "evening"}
        or any(term in text for term in ("야간", "야경", "밤바다", "노포", "힙지로"))
    )
    if not is_night_context and not indoor_matches and not outdoor_matches:
        return {
            "night_operating_confidence": 0.0,
            "indoor_night_confidence_demote": 0.0,
            "night_safe_outdoor_priority": 0.0,
            "nightlife_suitability_alignment": 0.0,
            "indoor_heavy_route_detected": False,
            "night_operating_confidence_reason": None,
            "operating_hours_known_closed": False,
            "night_indoor_strong_demote": 0.0,
            "relaxed_unknown_hours_allowed": False,
            "known_closed_removed": False,
            "night_safe_indoor_exception": False,
            "indoor_semantic_detected": False,
            "known_closed_indoor_removed": False,
            "night_indoor_semantic_demote": 0.0,
            "indoor_closing_time_applied": False,
        }

    outdoor_priority = 0.0
    if outdoor_matches:
        outdoor_priority = 0.055 + min(0.045, 0.01 * len(set(outdoor_matches)))
        if role in {"spot", "culture", "cafe"}:
            outdoor_priority += 0.015

    nightlife_alignment = 0.0
    if outdoor_matches or exception_matches:
        nightlife_alignment = 0.04
    if "night" in profile or "야경" in text or "밤바다" in text:
        nightlife_alignment += 0.025

    known_close_min, known_close_reason = _extract_known_close_min(place)
    curated_known_closed = (known_close_reason or "").startswith("known_closed_indoor:")
    operating_hours_known_closed = (
        current_minute is not None
        and known_close_min is not None
        and current_minute >= known_close_min
        and (
            curated_known_closed
            or (bool(indoor_matches or indoor_semantic_matches) and not outdoor_matches and not exception_matches)
        )
    )
    safe_indoor_exception = bool(exception_matches) or (known_close_reason or "").startswith("night_safe_indoor_exception")
    indoor_semantic_detected = bool(indoor_semantic_matches or indoor_matches)
    unknown_hours_allowed = bool(indoor_semantic_detected and known_close_min is None and not exception_matches)

    indoor_demote = 0.0
    strong_demote = 0.0
    semantic_demote = 0.0
    reason = None
    if operating_hours_known_closed and not safe_indoor_exception:
        strong_demote = 30.0 if curated_known_closed else 1.15
        if indoor_semantic_matches:
            semantic_demote = 2.0 if curated_known_closed else 0.55
        if role in {"spot", "culture"}:
            strong_demote += 0.25
        reason = f"known_closed_indoor_after_start:{known_close_min // 60:02d}:{known_close_min % 60:02d}"
    if indoor_semantic_detected and not outdoor_matches and not exception_matches:
        indoor_demote = 0.075
        if role in {"spot", "culture"}:
            indoor_demote += 0.035
        if any(term in text for term in ("도서관", "문화원", "문화센터", "교육관", "아트홀", "회관")):
            indoor_demote += 0.035
        if not place.get("rating") and not place.get("review_count"):
            indoor_demote += 0.02
        if not reason:
            reason = "risky_indoor_unknown_hours:" + ",".join(sorted(set(indoor_matches or indoor_semantic_matches))[:3])

    confidence = max(0.0, outdoor_priority + nightlife_alignment - indoor_demote - strong_demote - semantic_demote)
    return {
        "night_operating_confidence": round(confidence, 4),
        "indoor_night_confidence_demote": round(min(indoor_demote, 0.16), 4),
        "night_safe_outdoor_priority": round(min(outdoor_priority, 0.12), 4),
        "nightlife_suitability_alignment": round(min(nightlife_alignment, 0.08), 4),
        "indoor_heavy_route_detected": bool(indoor_demote > 0 or strong_demote > 0),
        "night_operating_confidence_reason": reason or ("night_safe_outdoor:" + ",".join(sorted(set(outdoor_matches))[:3]) if outdoor_matches else None),
        "operating_hours_known_closed": bool(operating_hours_known_closed),
        "night_indoor_strong_demote": round(min(strong_demote + semantic_demote, 32.25), 4),
        "relaxed_unknown_hours_allowed": bool(unknown_hours_allowed and not operating_hours_known_closed),
        "known_closed_removed": bool(operating_hours_known_closed and strong_demote >= 0.36),
        "night_safe_indoor_exception": bool(safe_indoor_exception),
        "indoor_semantic_detected": bool(indoor_semantic_detected),
        "known_closed_indoor_removed": bool(operating_hours_known_closed and not safe_indoor_exception),
        "night_indoor_semantic_demote": round(min(semantic_demote, 2.0), 4),
        "indoor_closing_time_applied": bool(operating_hours_known_closed and known_close_min is not None),
    }


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
    intended_city: str | None = None,
    query_region_1: str | None = None,
    selected_anchor: str | dict | None = None,
    selected_anchor_coord: tuple | None = None,
    region2_code_hints: set[str] | None = None,
    region_identity: dict | None = None,
    flow_profile: dict | None = None,
    previous_place: dict | None = None,
    default_preset_mode: bool = False,
    selected_anchor_family: dict | None = None,
    late_context: bool = False,
    late_current_minute: int | None = None,
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

    city_signal = _score_city_intent(
        place,
        intended_city=intended_city,
        query_region_1=query_region_1,
        selected_anchor=selected_anchor,
        selected_anchor_coord=selected_anchor_coord,
        region2_code_hints=region2_code_hints,
    )
    score_region = str((region_identity or {}).get("region") or query_region_1 or place.get("region_1") or place.get("region") or "")
    belt_signal = score_belt_match(place, region_identity)
    belt_match_bonus = float(belt_signal.get("belt_match_bonus") or 0.0)
    belt_confidence = float(belt_signal.get("belt_confidence") or 0.0)
    candidate_belt_affinity = belt_match_bonus * max(belt_confidence, 0.0)
    dominant_belt_signal = score_dominant_belt_affinity(place, region_identity)
    dominant_belt_bonus = float(dominant_belt_signal.get("dominant_belt_bonus") or 0.0)
    flow_signal = score_flow_continuity(place, previous_place, flow_profile)
    continuity_bonus = float(flow_signal.get("continuity_bonus") or 0.0)
    suitability_signal = score_vibe_tourism_suitability(
        place,
        flow_profile,
        target_slot=target_slot,
    )
    suitability_bonus = float(suitability_signal.get("suitability_bonus") or 0.0)
    suitability_soft_demote = float(suitability_signal.get("suitability_soft_demote") or 0.0)
    meal_cafe_signal = score_meal_cafe_suitability(
        place,
        flow_profile,
        target_slot=target_slot,
    )
    meal_cafe_bonus = float(meal_cafe_signal.get("meal_cafe_bonus") or 0.0)
    meal_cafe_soft_demote = float(meal_cafe_signal.get("meal_cafe_soft_demote") or 0.0)
    route_contamination_signal = score_route_contamination(
        place,
        region_identity,
        flow_profile,
        target_slot=target_slot,
    )
    route_contamination_demote = float(route_contamination_signal.get("route_contamination_demote") or 0.0)
    editorial_signal = score_editorial_route_fit(
        place,
        region_identity,
        flow_profile,
        target_slot=target_slot,
    )
    editorial_bonus = float(editorial_signal.get("editorial_bonus") or 0.0)
    editorial_demote = float(editorial_signal.get("editorial_demote") or 0.0)
    gimhae_support_slot_family_score = float(editorial_signal.get("gimhae_support_slot_family_score") or 0.0)
    gimhae_support_slot_drift_demote = float(editorial_signal.get("gimhae_support_slot_drift_demote") or 0.0)
    support_slot_coherence_score = float(editorial_signal.get("support_slot_coherence_score") or 0.0)
    seoul_default_representative_score = float(editorial_signal.get("seoul_default_representative_score") or 0.0)
    seoul_default_weak_first_place_demote = float(editorial_signal.get("seoul_default_weak_first_place_demote") or 0.0)
    landmark_authority_signal = score_landmark_authority(
        place,
        region_identity,
        flow_profile,
        target_slot=target_slot,
    )
    landmark_authority_score = float(landmark_authority_signal.get("landmark_authority_score") or 0.0)
    external_verified_score = float(landmark_authority_signal.get("external_verified_score") or 0.0)
    external_popularity_score = float(landmark_authority_signal.get("external_popularity_score") or 0.0)
    public_data_weakness_penalty = float(landmark_authority_signal.get("public_data_weakness_penalty") or 0.0)
    representative_confidence_score = float(landmark_authority_signal.get("representative_confidence_score") or 0.0)
    weak_generic_authority_demote = float(landmark_authority_signal.get("weak_generic_authority_demote") or 0.0)
    family_candidate_lookup_bonus = float(landmark_authority_signal.get("family_candidate_lookup_bonus") or 0.0)
    wrong_region_alias_demote = float(landmark_authority_signal.get("wrong_region_alias_demote") or 0.0)
    curated_representative_priority = float(landmark_authority_signal.get("curated_representative_priority") or 0.0)
    curated_support_slot_alignment = float(landmark_authority_signal.get("curated_support_slot_alignment") or 0.0)
    weak_public_contamination_demote = float(landmark_authority_signal.get("weak_public_contamination_demote") or 0.0)
    default_preset_signal = _score_default_preset_landmark(
        place,
        landmark_authority_signal,
        default_preset_mode=default_preset_mode,
        target_slot=target_slot,
    )
    default_preset_landmark_bonus = float(default_preset_signal.get("default_preset_landmark_bonus") or 0.0)
    weird_candidate_demote = float(default_preset_signal.get("weird_candidate_demote") or 0.0)
    public_facility_signal = _score_public_facility_tourism_fit(
        place,
        landmark_authority_signal,
        default_preset_mode=default_preset_mode,
        target_slot=target_slot,
        first_place=False,
    )
    public_facility_demote = float(public_facility_signal.get("public_facility_demote") or 0.0)
    representative_tourism_fit = float(public_facility_signal.get("representative_tourism_fit") or 0.0)
    anchor_family_signal = _score_selected_anchor_family(
        place,
        selected_anchor_family,
        landmark_authority_signal,
        default_preset_mode=default_preset_mode,
        target_slot=target_slot,
    )
    selected_anchor_family_match_score = float(anchor_family_signal.get("selected_anchor_family_match_score") or 0.0)
    selected_anchor_family_drift_demote = float(anchor_family_signal.get("selected_anchor_family_drift_demote") or 0.0)
    busan_oldtown_signal = _score_busan_oldtown_family(
        place,
        selected_anchor_family,
        region=score_region,
        target_slot=target_slot,
    )
    busan_oldtown_family_score = float(busan_oldtown_signal.get("busan_oldtown_family_score") or 0.0)
    busan_oldtown_drift_demote = float(busan_oldtown_signal.get("busan_oldtown_drift_demote") or 0.0)
    busan_oldtown_support_slot_score = float(busan_oldtown_signal.get("busan_oldtown_support_slot_score") or 0.0)
    exact_landmark_signal = _score_exact_landmark_visibility(
        place,
        selected_anchor_family,
        landmark_authority_signal,
        region=score_region,
        target_slot=target_slot,
    )
    exact_landmark_visibility_score = float(exact_landmark_signal.get("exact_landmark_visibility_score") or 0.0)
    exact_landmark_support_slot_bonus = float(exact_landmark_signal.get("exact_landmark_support_slot_bonus") or 0.0)
    weak_substitute_demote = float(exact_landmark_signal.get("weak_substitute_demote") or 0.0)
    exact_slot_alignment_bonus = float(exact_landmark_signal.get("exact_slot_alignment_bonus") or 0.0)
    oldtown_substitute_demote = float(exact_landmark_signal.get("oldtown_substitute_demote") or 0.0)
    east_coast_signal = _score_busan_east_coast_family(
        place,
        selected_anchor_family,
        region=score_region,
        target_slot=target_slot,
    )
    east_coast_family_score = float(east_coast_signal.get("busan_east_coast_family_score") or 0.0)
    east_coast_drift_demote = float(east_coast_signal.get("haeundae_gwangan_drift_demote") or 0.0)
    east_coast_support_slot_score = float(east_coast_signal.get("east_coast_support_slot_score") or 0.0)
    seomyeon_signal = _score_busan_seomyeon_family(
        place,
        selected_anchor_family,
        landmark_authority_signal,
        region=score_region,
        target_slot=target_slot,
    )
    seomyeon_family_score = float(seomyeon_signal.get("seomyeon_family_score") or 0.0)
    seomyeon_drift_demote = float(seomyeon_signal.get("seomyeon_drift_demote") or 0.0)
    seomyeon_weak_candidate_demote = float(seomyeon_signal.get("seomyeon_weak_candidate_demote") or 0.0)
    seoul_editorial_depth_signal = _score_seoul_editorial_depth(
        place,
        selected_anchor_family,
        landmark_authority_signal,
        region=score_region,
        target_slot=target_slot,
        default_preset_mode=default_preset_mode,
    )
    seoul_broad_default_family_balance = float(seoul_editorial_depth_signal.get("seoul_broad_default_family_balance") or 0.0)
    bukchon_editorial_depth_score = float(seoul_editorial_depth_signal.get("bukchon_editorial_depth_score") or 0.0)
    seongsu_editorial_depth_score = float(seoul_editorial_depth_signal.get("seongsu_editorial_depth_score") or 0.0)
    lifestyle_support_slot_visibility = float(seoul_editorial_depth_signal.get("lifestyle_support_slot_visibility") or 0.0)
    representative_family_rotation_balance = float(seoul_editorial_depth_signal.get("representative_family_rotation_balance") or 0.0)
    seoul_editorial_weak_demote = float(seoul_editorial_depth_signal.get("seoul_editorial_weak_demote") or 0.0)
    bukchon_lifestyle_support_slot_score = float(
        seoul_editorial_depth_signal.get("bukchon_lifestyle_support_slot_score") or 0.0
    )
    seongsu_support_slot_coherence = float(
        seoul_editorial_depth_signal.get("seongsu_support_slot_coherence") or 0.0
    )
    editorial_lifestyle_visibility_bonus = float(
        seoul_editorial_depth_signal.get("editorial_lifestyle_visibility_bonus") or 0.0
    )
    seoul_curated_district_priority = float(seoul_editorial_depth_signal.get("seoul_curated_district_priority") or 0.0)
    broad_seoul_demoted = float(seoul_editorial_depth_signal.get("broad_seoul_demoted") or 0.0)
    district_identity_alignment = float(seoul_editorial_depth_signal.get("district_identity_alignment") or 0.0)
    support_slot_role_diversity = float(seoul_editorial_depth_signal.get("support_slot_role_diversity") or 0.0)
    seoul_family_signal = _score_seoul_gangnam_yeouido_family(
        place,
        selected_anchor_family,
        landmark_authority_signal,
        region=score_region,
        target_slot=target_slot,
    )
    seoul_external_authority_boost = float(seoul_family_signal.get("seoul_external_authority_boost") or 0.0)
    gangnam_family_score = float(seoul_family_signal.get("gangnam_family_score") or 0.0)
    yeouido_family_score = float(seoul_family_signal.get("yeouido_family_score") or 0.0)
    seoul_weak_lifestyle_demote = float(seoul_family_signal.get("seoul_weak_lifestyle_demote") or 0.0)
    gangnam_candidate_depth_score = float(seoul_family_signal.get("gangnam_candidate_depth_score") or 0.0)
    gangnam_first_place_dominance_penalty = float(
        seoul_family_signal.get("gangnam_first_place_dominance_penalty") or 0.0
    )
    yeouido_public_facility_final_demote = float(
        seoul_family_signal.get("yeouido_public_facility_final_demote") or 0.0
    )
    euljiro_night_family_score = float(seoul_family_signal.get("euljiro_night_family_score") or 0.0)
    gangnam_editorial_representative_score = float(
        seoul_family_signal.get("gangnam_editorial_representative_score") or 0.0
    )
    weak_editorial_first_place_demote = float(seoul_family_signal.get("weak_editorial_first_place_demote") or 0.0)
    nightlife_coherence_score = float(seoul_family_signal.get("nightlife_coherence_score") or 0.0)
    targeted_coherence_signal = _score_targeted_route_coherence(
        place,
        selected_anchor_family,
        region=score_region,
        target_slot=target_slot,
        default_preset_mode=default_preset_mode,
    )
    targeted_route_coherence_score = float(targeted_coherence_signal.get("targeted_route_coherence_score") or 0.0)
    support_slot_family_alignment = float(targeted_coherence_signal.get("support_slot_family_alignment") or 0.0)
    broad_default_balance_score = float(targeted_coherence_signal.get("broad_default_balance_score") or 0.0)
    editorial_route_alignment = float(targeted_coherence_signal.get("editorial_route_alignment") or 0.0)
    targeted_coherence_demote = float(targeted_coherence_signal.get("targeted_coherence_demote") or 0.0)
    support_slot_assembly_signal = _score_support_slot_family_assembly(
        place,
        selected_anchor_family,
        region=score_region,
        selected_anchor=selected_anchor,
        target_slot=target_slot,
    )
    support_slot_family_assembly_score = float(
        support_slot_assembly_signal.get("support_slot_family_assembly_score") or 0.0
    )
    representative_support_slot_alignment = float(
        support_slot_assembly_signal.get("representative_support_slot_alignment") or 0.0
    )
    weak_support_slot_demote = float(support_slot_assembly_signal.get("weak_support_slot_demote") or 0.0)
    support_slot_coherence_balance = float(
        support_slot_assembly_signal.get("support_slot_coherence_balance") or 0.0
    )
    nightlife_support_slot_alignment = float(
        support_slot_assembly_signal.get("nightlife_support_slot_alignment") or 0.0
    )
    nightlife_family_depth = float(support_slot_assembly_signal.get("nightlife_family_depth") or 0.0)
    central_seoul_broad_demote = float(support_slot_assembly_signal.get("central_seoul_broad_demote") or 0.0)
    support_slot_purity_score = float(support_slot_assembly_signal.get("support_slot_purity_score") or 0.0)
    representative_support_purity_score = float(
        support_slot_assembly_signal.get("representative_support_purity_score") or 0.0
    )
    curated_night_signal = _score_curated_night_family(
        place,
        region=score_region,
        selected_anchor=selected_anchor,
        selected_anchor_family=selected_anchor_family,
        flow_profile=flow_profile,
        target_slot=target_slot,
        late_context=late_context,
    )
    night_representative_preference = float(curated_night_signal.get("night_representative_preference") or 0.0)
    nightlife_curated_alignment = float(curated_night_signal.get("nightlife_curated_alignment") or 0.0)
    night_vibe_coherence = float(curated_night_signal.get("night_vibe_coherence") or 0.0)
    curated_night_support_slot = float(curated_night_signal.get("curated_night_support_slot") or 0.0)
    curated_night_weak_demote = float(curated_night_signal.get("curated_night_weak_demote") or 0.0)
    image_signal = _score_image_availability(
        place,
        flow_profile=flow_profile,
        target_slot=target_slot,
        first_place=False,
    )
    image_quality_bonus = float(image_signal.get("image_quality_bonus") or 0.0)
    no_image_first_place_demote = float(image_signal.get("no_image_first_place_demote") or 0.0)
    indoor_leisure_signal = _score_coastal_indoor_leisure(
        place,
        flow_profile=flow_profile,
        target_slot=target_slot,
        first_place=False,
    )
    indoor_leisure_demote = float(indoor_leisure_signal.get("indoor_leisure_demote") or 0.0)
    night_confidence_signal = _score_night_operating_confidence(
        place,
        flow_profile,
        target_slot,
        late_context=late_context,
        current_minute=late_current_minute,
    )
    night_operating_confidence = float(night_confidence_signal.get("night_operating_confidence") or 0.0)
    indoor_night_confidence_demote = float(night_confidence_signal.get("indoor_night_confidence_demote") or 0.0)
    night_safe_outdoor_priority = float(night_confidence_signal.get("night_safe_outdoor_priority") or 0.0)
    nightlife_suitability_alignment = float(night_confidence_signal.get("nightlife_suitability_alignment") or 0.0)
    night_indoor_strong_demote = float(night_confidence_signal.get("night_indoor_strong_demote") or 0.0)
    w = weights or WEIGHTS_DEFAULT
    score = (
        w["travel_fit"]           * distance_score
        + w["theme_match"]        * theme_score
        + w["popularity_score"]   * pop_score
        + w["slot_fit"]           * sf
        + 0.22 * city_signal.get("score", 0.0)
        + (0.18 * city_signal.get("anchor_distance_score", 0.0))
        + city_signal.get("locality_bonus", 0.0)
        - city_signal.get("wrong_city_demote", 0.0)
        + quality_bonus
        + belt_match_bonus
        + dominant_belt_bonus
        + continuity_bonus
        + suitability_bonus
        - suitability_soft_demote
        + meal_cafe_bonus
        - meal_cafe_soft_demote
        - route_contamination_demote
        + editorial_bonus
        - editorial_demote
        + gimhae_support_slot_family_score
        - gimhae_support_slot_drift_demote
        + seoul_default_representative_score
        - seoul_default_weak_first_place_demote
        + landmark_authority_score
        + external_verified_score
        + external_popularity_score
        + representative_confidence_score
        + family_candidate_lookup_bonus
        + curated_representative_priority
        + curated_support_slot_alignment
        - public_data_weakness_penalty
        - wrong_region_alias_demote
        - weak_generic_authority_demote
        - weak_public_contamination_demote
        + default_preset_landmark_bonus
        - weird_candidate_demote
        - public_facility_demote
        + representative_tourism_fit
        + selected_anchor_family_match_score
        - selected_anchor_family_drift_demote
        + busan_oldtown_family_score
        + busan_oldtown_support_slot_score
        - busan_oldtown_drift_demote
        + exact_landmark_visibility_score
        + exact_landmark_support_slot_bonus
        + exact_slot_alignment_bonus
        - weak_substitute_demote
        - oldtown_substitute_demote
        + east_coast_family_score
        + east_coast_support_slot_score
        - east_coast_drift_demote
        + seomyeon_family_score
        - seomyeon_drift_demote
        - seomyeon_weak_candidate_demote
        + seoul_broad_default_family_balance
        + bukchon_editorial_depth_score
        + seongsu_editorial_depth_score
        + lifestyle_support_slot_visibility
        + representative_family_rotation_balance
        + bukchon_lifestyle_support_slot_score
        + seongsu_support_slot_coherence
        + editorial_lifestyle_visibility_bonus
        + seoul_curated_district_priority
        + district_identity_alignment
        + support_slot_role_diversity
        - seoul_editorial_weak_demote
        - broad_seoul_demoted
        + seoul_external_authority_boost
        + gangnam_family_score
        + yeouido_family_score
        + gangnam_candidate_depth_score
        - seoul_weak_lifestyle_demote
        - gangnam_first_place_dominance_penalty
        - yeouido_public_facility_final_demote
        + euljiro_night_family_score
        + gangnam_editorial_representative_score
        + nightlife_coherence_score
        - weak_editorial_first_place_demote
        + targeted_route_coherence_score
        + support_slot_family_alignment
        + broad_default_balance_score
        + editorial_route_alignment
        + support_slot_family_assembly_score
        + representative_support_slot_alignment
        + support_slot_coherence_balance
        + nightlife_support_slot_alignment
        + nightlife_family_depth
        + support_slot_purity_score
        + representative_support_purity_score
        + night_representative_preference
        + nightlife_curated_alignment
        + night_vibe_coherence
        + curated_night_support_slot
        - targeted_coherence_demote
        - weak_support_slot_demote
        - central_seoul_broad_demote
        - curated_night_weak_demote
        + image_quality_bonus
        - no_image_first_place_demote
        - indoor_leisure_demote
        + night_safe_outdoor_priority
        + nightlife_suitability_alignment
        + night_operating_confidence
        - indoor_night_confidence_demote
        - night_indoor_strong_demote
    )

    components = {
        "travel_fit":         round(distance_score, 4),
        "theme_match":        round(theme_score, 4),
        "popularity_score":   round(pop_score, 4),
        "slot_fit":           round(sf, 4),
        "quality_bonus":      round(quality_bonus, 4),
        "penalty_multiplier": 1.0,
        "city_intent_score":  round(city_signal.get("score", 0.0), 4),
        "city_intent_evidence": city_signal.get("evidence", "none"),
        "city_intent_positive_hits": city_signal.get("positive_hits", 0),
        "city_intent_negative_hits": city_signal.get("negative_hits", 0),
        "city_anchor_distance_score": city_signal.get("anchor_distance_score", 0.0),
        "locality_bonus":     city_signal.get("locality_bonus", 0.0),
        "wrong_city_demote":  city_signal.get("wrong_city_demote", 0.0),
        "normalized_city_token": city_signal.get("normalized_city_token"),
        "normalized_anchor_token": city_signal.get("normalized_anchor_token"),
        "inferred_belt": belt_signal.get("inferred_belt"),
        "belt_confidence": belt_signal.get("belt_confidence", 0.0),
        "belt_match_bonus": round(belt_match_bonus, 4),
        "belt_match_reasons": belt_signal.get("belt_match_reasons") or [],
        "candidate_belt_match": belt_match_bonus > 0,
        "candidate_belt_affinity": round(candidate_belt_affinity, 4),
        "wrong_belt_match": belt_signal.get("wrong_belt_match"),
        "dominant_belt": dominant_belt_signal.get("dominant_belt"),
        "dominant_belt_bonus": round(dominant_belt_bonus, 4),
        "dominant_belt_reasons": dominant_belt_signal.get("dominant_belt_reasons") or [],
        "inferred_flow_profile": flow_signal.get("inferred_flow_profile"),
        "slot_flow_alignment": flow_signal.get("slot_flow_alignment", 0.0),
        "continuity_bonus": round(continuity_bonus, 4),
        "flow_break_candidate": flow_signal.get("flow_break_candidate", False),
        "flow_match_reasons": flow_signal.get("flow_match_reasons") or [],
        "suitability_profile": suitability_signal.get("suitability_profile"),
        "vibe_suitability_score": suitability_signal.get("vibe_suitability_score", 0.0),
        "tourism_suitability_score": suitability_signal.get("tourism_suitability_score", 0.0),
        "suitability_bonus": round(suitability_bonus, 4),
        "suitability_soft_demote": round(suitability_soft_demote, 4),
        "vibe_match_reasons": suitability_signal.get("vibe_match_reasons") or [],
        "soft_demote_reason": suitability_signal.get("soft_demote_reason"),
        "meal_cafe_profile": meal_cafe_signal.get("meal_cafe_profile"),
        "meal_vibe_score": meal_cafe_signal.get("meal_vibe_score", 0.0),
        "meal_experience_score": meal_cafe_signal.get("meal_experience_score", 0.0),
        "meal_soft_demote_reason": meal_cafe_signal.get("meal_soft_demote_reason"),
        "local_food_bonus": meal_cafe_signal.get("local_food_bonus", 0.0),
        "view_bonus": meal_cafe_signal.get("view_bonus", 0.0),
        "meal_cafe_bonus": round(meal_cafe_bonus, 4),
        "meal_cafe_soft_demote": round(meal_cafe_soft_demote, 4),
        "meal_cafe_match_reasons": meal_cafe_signal.get("meal_cafe_match_reasons") or [],
        "route_contamination_demote": round(route_contamination_demote, 4),
        "route_contamination_flags": route_contamination_signal.get("route_contamination_flags") or [],
        "route_contamination_reasons": route_contamination_signal.get("route_contamination_reasons") or [],
        "route_positive_matches": route_contamination_signal.get("route_positive_matches") or [],
        "heritage_family_exception": route_contamination_signal.get("heritage_family_exception") or [],
        "nightlife_core_exception": route_contamination_signal.get("nightlife_core_exception") or [],
        "coherence_false_positive_removed": bool(route_contamination_signal.get("coherence_false_positive_removed")),
        "nightlife_false_positive_removed": bool(route_contamination_signal.get("nightlife_false_positive_removed")),
        "heritage_false_positive_removed": bool(route_contamination_signal.get("heritage_false_positive_removed")),
        "coastal_vibe_score": route_contamination_signal.get("coastal_vibe_score", 0.0),
        "night_view_score": route_contamination_signal.get("night_view_score", 0.0),
        "harbor_alignment": route_contamination_signal.get("harbor_alignment", 0.0),
        "sea_route_continuity": route_contamination_signal.get("sea_route_continuity", 0.0),
        "inland_contamination_flags": route_contamination_signal.get("inland_contamination_flags") or [],
        "religious_facility_demote": route_contamination_signal.get("religious_facility_demote", 0.0),
        "religious_tourism_exception": route_contamination_signal.get("religious_tourism_exception") or [],
        "editorial_bonus": round(editorial_bonus, 4),
        "editorial_demote": round(editorial_demote, 4),
        "editorial_demote_reason": editorial_signal.get("editorial_demote_reason"),
        "weak_first_place_reason": editorial_signal.get("weak_first_place_reason"),
        "central_drift_reason": editorial_signal.get("central_drift_reason"),
        "landmark_priority_score": editorial_signal.get("landmark_priority_score", 0.0),
        "representative_vibe_score": editorial_signal.get("representative_vibe_score", 0.0),
        "weak_indoor_demote": editorial_signal.get("weak_indoor_demote", 0.0),
        "landmark_alignment_reason": editorial_signal.get("landmark_alignment_reason"),
        "seongsu_vibe_score": editorial_signal.get("seongsu_vibe_score", 0.0),
        "cafe_street_alignment": editorial_signal.get("cafe_street_alignment", 0.0),
        "weak_meal_demote": editorial_signal.get("weak_meal_demote", 0.0),
        "editorial_first_place_bonus": editorial_signal.get("editorial_first_place_bonus", 0.0),
        "euljiro_night_score": editorial_signal.get("euljiro_night_score", 0.0),
        "hipjiro_alignment": editorial_signal.get("hipjiro_alignment", 0.0),
        "central_drift_demote": editorial_signal.get("central_drift_demote", 0.0),
        "night_vibe_bonus": editorial_signal.get("night_vibe_bonus", 0.0),
        "seoul_date_score": editorial_signal.get("seoul_date_score", 0.0),
        "date_vibe_alignment": editorial_signal.get("date_vibe_alignment", 0.0),
        "broad_seoul_drift_demote": editorial_signal.get("broad_seoul_drift_demote", 0.0),
        "romantic_walk_bonus": editorial_signal.get("romantic_walk_bonus", 0.0),
        "busan_night_meal_score": editorial_signal.get("busan_night_meal_score", 0.0),
        "waterfront_alignment": editorial_signal.get("waterfront_alignment", 0.0),
        "weak_daytime_meal_demote": editorial_signal.get("weak_daytime_meal_demote", 0.0),
        "night_meal_bonus": editorial_signal.get("night_meal_bonus", 0.0),
        "busan_landmark_priority_score": editorial_signal.get("busan_landmark_priority_score", 0.0),
        "busan_representative_bonus": editorial_signal.get("busan_representative_bonus", 0.0),
        "busan_landmark_alignment_reason": editorial_signal.get("busan_landmark_alignment_reason"),
        "representative_tourism_family_score": max(
            float(editorial_signal.get("representative_tourism_family_score") or 0.0),
            float(landmark_authority_signal.get("representative_tourism_family_score") or 0.0),
        ),
        "indoor_culture_fallback_demote": max(
            float(editorial_signal.get("indoor_culture_fallback_demote") or 0.0),
            float(landmark_authority_signal.get("indoor_culture_fallback_demote") or 0.0),
        ),
        "regional_landmark_density": max(
            float(editorial_signal.get("regional_landmark_density") or 0.0),
            float(landmark_authority_signal.get("regional_landmark_density") or 0.0),
        ),
        "first_place_representative_bonus": max(
            float(editorial_signal.get("first_place_representative_bonus") or 0.0),
            float(landmark_authority_signal.get("first_place_representative_bonus") or 0.0),
        ),
        "jinju_history_first_place_bonus": editorial_signal.get("jinju_history_first_place_bonus", 0.0),
        "tongyeong_same_city_bonus": editorial_signal.get("tongyeong_same_city_bonus", 0.0),
        "tongyeong_geoje_drift_demote": editorial_signal.get("tongyeong_geoje_drift_demote", 0.0),
        "gimhae_gaya_family_score": editorial_signal.get("gimhae_gaya_family_score", 0.0),
        "gimhae_support_slot_family_score": round(gimhae_support_slot_family_score, 4),
        "gimhae_support_slot_drift_demote": round(gimhae_support_slot_drift_demote, 4),
        "support_slot_coherence_score": round(support_slot_coherence_score, 4),
        "seoul_default_representative_score": round(seoul_default_representative_score, 4),
        "seoul_default_weak_first_place_demote": round(seoul_default_weak_first_place_demote, 4),
        "weak_museum_first_place_demote": editorial_signal.get("weak_museum_first_place_demote", 0.0),
        "landmark_authority_score": round(landmark_authority_score, 4),
        "popularity_signal": landmark_authority_signal.get("popularity_signal", 0.0),
        "popularity_authority_score": landmark_authority_signal.get("popularity_authority_score", 0.0),
        "landmark_confidence": landmark_authority_signal.get("landmark_confidence", 0.0),
        "representative_tourism_bonus": landmark_authority_signal.get("representative_tourism_bonus", 0.0),
        "tourism_representative_score": landmark_authority_signal.get("tourism_representative_score", 0.0),
        "normalized_popularity_hint": landmark_authority_signal.get("normalized_popularity_hint", 0.0),
        "external_verified_score": landmark_authority_signal.get("external_verified_score", 0.0),
        "external_popularity_score": landmark_authority_signal.get("external_popularity_score", 0.0),
        "public_data_weakness_penalty": landmark_authority_signal.get("public_data_weakness_penalty", 0.0),
        "public_data_weakness_reason": landmark_authority_signal.get("public_data_weakness_reason"),
        "representative_confidence_score": landmark_authority_signal.get("representative_confidence_score", 0.0),
        "image_density_score": landmark_authority_signal.get("image_density_score", 0.0),
        "review_density_hint": landmark_authority_signal.get("review_density_hint", 0.0),
        "landmark_authority_matches": landmark_authority_signal.get("landmark_authority_matches") or [],
        "landmark_authority_reason": landmark_authority_signal.get("landmark_authority_reason"),
        "landmark_authority_source_policy": landmark_authority_signal.get("landmark_authority_source_policy"),
        "alias_normalization_match": landmark_authority_signal.get("alias_normalization_match") or [],
        "region_aware_alias_guard": landmark_authority_signal.get("region_aware_alias_guard"),
        "wrong_region_alias_demote": round(wrong_region_alias_demote, 4),
        "family_candidate_lookup_bonus": round(family_candidate_lookup_bonus, 4),
        "representative_alias_pool_included": bool(landmark_authority_signal.get("representative_alias_pool_included")),
        "weak_generic_authority_demote": round(weak_generic_authority_demote, 4),
        "weak_generic_authority_reason": landmark_authority_signal.get("weak_generic_authority_reason"),
        "curated_representative_priority": round(curated_representative_priority, 4),
        "verified_api_candidate": bool(landmark_authority_signal.get("verified_api_candidate")),
        "public_fallback_used": bool(landmark_authority_signal.get("public_fallback_used")),
        "weak_public_contamination_demote": round(weak_public_contamination_demote, 4),
        "curated_support_slot_alignment": round(curated_support_slot_alignment, 4),
        "curated_representative_matches": landmark_authority_signal.get("curated_representative_matches") or [],
        "curated_representative_context": landmark_authority_signal.get("curated_representative_context"),
        "default_preset_mode": bool(default_preset_signal.get("default_preset_mode")),
        "representative_landmark_selected": bool(default_preset_signal.get("representative_landmark_selected")),
        "default_preset_landmark_bonus": round(default_preset_landmark_bonus, 4),
        "weird_candidate_demote": round(weird_candidate_demote, 4),
        "weird_candidate_demote_reason": default_preset_signal.get("weird_candidate_demote_reason"),
        "public_facility_demote": round(public_facility_demote, 4),
        "representative_tourism_fit": round(representative_tourism_fit, 4),
        "weak_public_facility_reason": public_facility_signal.get("weak_public_facility_reason"),
        "selected_anchor_family_id": anchor_family_signal.get("selected_anchor_family_id"),
        "selected_anchor_family_match_score": round(selected_anchor_family_match_score, 4),
        "selected_anchor_family_preserved": bool(anchor_family_signal.get("selected_anchor_family_preserved")),
        "selected_anchor_family_matched_terms": anchor_family_signal.get("selected_anchor_family_matched_terms") or [],
        "selected_anchor_family_drift_demote": round(selected_anchor_family_drift_demote, 4),
        "selected_anchor_drift_reason": anchor_family_signal.get("selected_anchor_drift_reason"),
        "fallback_level_used": anchor_family_signal.get("fallback_level_used"),
        "busan_oldtown_family_score": round(busan_oldtown_family_score, 4),
        "busan_oldtown_pool_included": bool(busan_oldtown_signal.get("busan_oldtown_pool_included")),
        "busan_oldtown_drift_demote": round(busan_oldtown_drift_demote, 4),
        "busan_oldtown_support_slot_score": round(busan_oldtown_support_slot_score, 4),
        "busan_oldtown_expected_landmark_visible": bool(busan_oldtown_signal.get("busan_oldtown_expected_landmark_visible")),
        "busan_oldtown_match_terms": busan_oldtown_signal.get("busan_oldtown_match_terms") or [],
        "exact_landmark_visibility_score": round(exact_landmark_visibility_score, 4),
        "exact_landmark_pool_included": bool(exact_landmark_signal.get("exact_landmark_pool_included")),
        "exact_landmark_support_slot_bonus": round(exact_landmark_support_slot_bonus, 4),
        "exact_support_slot_visibility_bonus": round(
            float(exact_landmark_signal.get("exact_support_slot_visibility_bonus") or exact_landmark_support_slot_bonus),
            4,
        ),
        "exact_support_slot_replacement_applied": False,
        "exact_landmark_final_route_visible": bool(exact_landmark_signal.get("exact_landmark_pool_included")),
        "oldtown_candidate_replaced": None,
        "support_slot_visibility_reason": (
            "exact_landmark_pool_included"
            if exact_landmark_signal.get("exact_landmark_pool_included")
            else exact_landmark_signal.get("exact_landmark_missing_reason")
        ),
        "exact_landmark_missing_reason": exact_landmark_signal.get("exact_landmark_missing_reason"),
        "weak_substitute_demote": round(weak_substitute_demote, 4),
        "exact_slot_alignment_bonus": round(exact_slot_alignment_bonus, 4),
        "exact_anchor_final_visibility": bool(exact_landmark_signal.get("exact_anchor_final_visibility")),
        "oldtown_substitute_demote": round(oldtown_substitute_demote, 4),
        "exact_landmark_match_terms": exact_landmark_signal.get("exact_landmark_match_terms") or [],
        "exact_landmark_focus_match_terms": exact_landmark_signal.get("exact_landmark_focus_match_terms") or [],
        "busan_east_coast_family_score": round(east_coast_family_score, 4),
        "east_coast_family_preserved": bool(east_coast_signal.get("east_coast_family_preserved")),
        "haeundae_gwangan_drift_demote": round(east_coast_drift_demote, 4),
        "east_coast_support_slot_score": round(east_coast_support_slot_score, 4),
        "east_coast_expected_landmark_visible": bool(east_coast_signal.get("east_coast_expected_landmark_visible")),
        "east_coast_match_terms": east_coast_signal.get("east_coast_match_terms") or [],
        "seomyeon_family_score": round(seomyeon_family_score, 4),
        "seomyeon_family_pool_included": bool(seomyeon_signal.get("seomyeon_family_pool_included")),
        "seomyeon_nightlife_pool_included": bool(seomyeon_signal.get("seomyeon_nightlife_pool_included")),
        "seomyeon_drift_demote": round(seomyeon_drift_demote, 4),
        "seomyeon_weak_candidate_demote": round(seomyeon_weak_candidate_demote, 4),
        "seomyeon_family_match_terms": seomyeon_signal.get("seomyeon_family_match_terms") or [],
        "seoul_broad_default_family_balance": round(seoul_broad_default_family_balance, 4),
        "bukchon_editorial_depth_score": round(bukchon_editorial_depth_score, 4),
        "seongsu_editorial_depth_score": round(seongsu_editorial_depth_score, 4),
        "lifestyle_support_slot_visibility": round(lifestyle_support_slot_visibility, 4),
        "representative_family_rotation_balance": round(representative_family_rotation_balance, 4),
        "seoul_broad_family_key": seoul_editorial_depth_signal.get("seoul_broad_family_key"),
        "seoul_broad_family_matches": seoul_editorial_depth_signal.get("seoul_broad_family_matches") or [],
        "bukchon_editorial_depth_matches": seoul_editorial_depth_signal.get("bukchon_editorial_depth_matches") or [],
        "seongsu_editorial_depth_matches": seoul_editorial_depth_signal.get("seongsu_editorial_depth_matches") or [],
        "seoul_editorial_weak_demote": round(seoul_editorial_weak_demote, 4),
        "seoul_editorial_depth_pool_included": bool(seoul_editorial_depth_signal.get("seoul_editorial_depth_pool_included")),
        "bukchon_editorial_candidate_exists": bool(seoul_editorial_depth_signal.get("bukchon_editorial_candidate_exists")),
        "bukchon_lifestyle_support_slot_score": round(bukchon_lifestyle_support_slot_score, 4),
        "seongsu_editorial_candidate_exists": bool(seoul_editorial_depth_signal.get("seongsu_editorial_candidate_exists")),
        "seongsu_support_slot_coherence": round(seongsu_support_slot_coherence, 4),
        "editorial_lifestyle_visibility_bonus": round(editorial_lifestyle_visibility_bonus, 4),
        "seoul_curated_district_priority": round(seoul_curated_district_priority, 4),
        "broad_seoul_demoted": round(broad_seoul_demoted, 4),
        "district_identity_alignment": round(district_identity_alignment, 4),
        "support_slot_role_diversity": round(support_slot_role_diversity, 4),
        "seoul_external_authority_boost": round(seoul_external_authority_boost, 4),
        "gangnam_family_score": round(gangnam_family_score, 4),
        "yeouido_family_score": round(yeouido_family_score, 4),
        "seoul_weak_lifestyle_demote": round(seoul_weak_lifestyle_demote, 4),
        "seoul_family_pool_included": bool(seoul_family_signal.get("seoul_family_pool_included")),
        "seoul_family_match_terms": seoul_family_signal.get("seoul_family_match_terms") or [],
        "gangnam_candidate_depth_score": round(gangnam_candidate_depth_score, 4),
        "gangnam_representative_pool_included": bool(seoul_family_signal.get("gangnam_representative_pool_included")),
        "gangnam_first_place_dominance_penalty": round(gangnam_first_place_dominance_penalty, 4),
        "yeouido_public_facility_final_demote": round(yeouido_public_facility_final_demote, 4),
        "family_candidate_depth_before_after": seoul_family_signal.get("family_candidate_depth_before_after"),
        "euljiro_night_family_score": round(euljiro_night_family_score, 4),
        "euljiro_nightlife_pool_included": bool(seoul_family_signal.get("euljiro_nightlife_pool_included")),
        "gangnam_editorial_representative_score": round(gangnam_editorial_representative_score, 4),
        "weak_editorial_first_place_demote": round(weak_editorial_first_place_demote, 4),
        "nightlife_coherence_score": round(nightlife_coherence_score, 4),
        "targeted_route_coherence_score": round(targeted_route_coherence_score, 4),
        "support_slot_family_alignment": round(support_slot_family_alignment, 4),
        "coherence_demote_reason": targeted_coherence_signal.get("coherence_demote_reason"),
        "broad_default_balance_score": round(broad_default_balance_score, 4),
        "editorial_route_alignment": round(editorial_route_alignment, 4),
        "targeted_coherence_positive_terms": targeted_coherence_signal.get("targeted_coherence_positive_terms") or [],
        "targeted_coherence_weak_terms": targeted_coherence_signal.get("targeted_coherence_weak_terms") or [],
        "targeted_coherence_demote": round(targeted_coherence_demote, 4),
        "support_slot_family_assembly_score": round(support_slot_family_assembly_score, 4),
        "representative_support_slot_alignment": round(representative_support_slot_alignment, 4),
        "weak_support_slot_demote": round(weak_support_slot_demote, 4),
        "support_slot_coherence_balance": round(support_slot_coherence_balance, 4),
        "editorial_support_slot_match": bool(support_slot_assembly_signal.get("editorial_support_slot_match")),
        "support_slot_family_match_terms": support_slot_assembly_signal.get("support_slot_family_match_terms") or [],
        "weak_support_slot_terms": support_slot_assembly_signal.get("weak_support_slot_terms") or [],
        "nightlife_support_slot_alignment": round(nightlife_support_slot_alignment, 4),
        "nightlife_family_depth": round(nightlife_family_depth, 4),
        "nightlife_replacement_applied": False,
        "nightlife_core_alignment": round(nightlife_support_slot_alignment, 4),
        "nightlife_core_match_terms": support_slot_assembly_signal.get("nightlife_core_match_terms") or [],
        "central_seoul_broad_demote": round(central_seoul_broad_demote, 4),
        "support_slot_purity_score": round(support_slot_purity_score, 4),
        "support_slot_editorial_contamination": bool(
            support_slot_assembly_signal.get("support_slot_editorial_contamination")
        ),
        "representative_support_purity_score": round(representative_support_purity_score, 4),
        "residual_support_slot_contamination": bool(
            support_slot_assembly_signal.get("support_slot_editorial_contamination")
        ),
        "support_slot_cleanup_applied": bool(support_slot_assembly_signal.get("support_slot_editorial_contamination")),
        "representative_support_slot_purity": round(representative_support_purity_score, 4),
        "bounded_support_slot_cleanup": False,
        "support_slot_family_coherence": round(support_slot_coherence_balance + representative_support_purity_score, 4),
        "representative_family_purity_score": round(representative_support_purity_score, 4),
        "support_slot_purity_cleanup": bool(support_slot_assembly_signal.get("support_slot_editorial_contamination")),
        "weak_contamination_demote": round(weak_support_slot_demote, 4),
        "representative_family_alignment": round(representative_support_slot_alignment, 4),
        "bounded_purity_replacement": False,
        "residual_cleanup_applied": bool(support_slot_assembly_signal.get("residual_cleanup_applied")),
        "weak_contamination_repeat": bool(support_slot_assembly_signal.get("weak_contamination_repeat")),
        "support_slot_minimal_cleanup": bool(support_slot_assembly_signal.get("support_slot_minimal_cleanup")),
        "runtime_stability_guard": bool(support_slot_assembly_signal.get("runtime_stability_guard", True)),
        "curated_night_family_applied": bool(curated_night_signal.get("curated_night_family_applied")),
        "night_representative_preference": round(night_representative_preference, 4),
        "nightlife_curated_alignment": round(nightlife_curated_alignment, 4),
        "night_vibe_coherence": round(night_vibe_coherence, 4),
        "curated_night_support_slot": round(curated_night_support_slot, 4),
        "curated_night_match_terms": curated_night_signal.get("curated_night_match_terms") or [],
        "curated_night_weak_demote": round(curated_night_weak_demote, 4),
        "image_available": bool(image_signal.get("image_available")),
        "image_quality_bonus": round(image_quality_bonus, 4),
        "no_image_first_place_demote": round(no_image_first_place_demote, 4),
        "placeholder_used": not bool(image_signal.get("image_available")),
        "indoor_leisure_demote": round(indoor_leisure_demote, 4),
        "indoor_leisure_reason": indoor_leisure_signal.get("indoor_leisure_reason"),
        "night_operating_confidence": round(night_operating_confidence, 4),
        "indoor_night_confidence_demote": round(indoor_night_confidence_demote, 4),
        "night_safe_outdoor_priority": round(night_safe_outdoor_priority, 4),
        "nightlife_suitability_alignment": round(nightlife_suitability_alignment, 4),
        "indoor_heavy_route_detected": bool(night_confidence_signal.get("indoor_heavy_route_detected")),
        "night_operating_confidence_reason": night_confidence_signal.get("night_operating_confidence_reason"),
        "operating_hours_known_closed": bool(night_confidence_signal.get("operating_hours_known_closed")),
        "night_indoor_strong_demote": round(night_indoor_strong_demote, 4),
        "relaxed_unknown_hours_allowed": bool(night_confidence_signal.get("relaxed_unknown_hours_allowed")),
        "known_closed_removed": bool(night_confidence_signal.get("known_closed_removed")),
        "night_safe_indoor_exception": bool(night_confidence_signal.get("night_safe_indoor_exception")),
        "indoor_semantic_detected": bool(night_confidence_signal.get("indoor_semantic_detected")),
        "known_closed_indoor_removed": bool(night_confidence_signal.get("known_closed_indoor_removed")),
        "night_indoor_semantic_demote": float(night_confidence_signal.get("night_indoor_semantic_demote") or 0.0),
        "indoor_closing_time_applied": bool(night_confidence_signal.get("indoor_closing_time_applied")),
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
                   rating, review_count, data_source, first_image_url, region_1 AS region, region_2, NULL::text AS address, NULL::text AS addr,
                   ai_summary, overview, category_id, opening_hours, indoor_outdoor
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
                   rating, review_count, data_source, first_image_url, region_1 AS region, region_2, NULL::text AS address, NULL::text AS addr,
                   ai_summary, overview, category_id, opening_hours, indoor_outdoor
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

    blocked = [r for r in result if _should_drop_candidate_for_role(r, roles)]
    if blocked:
        logger.info(
            "global tourism eligibility guard removed %d candidates -- region=%s roles=%s blocked=%s",
            len(blocked), region, roles,
            [
                {"name": r.get("name"), "reason": _get_unsuitable_reason(r.get("name", ""))}
                for r in blocked[:8]
            ],
        )
    result = [r for r in result if not _should_drop_candidate_for_role(r, roles)]

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
    # Anchor-driven requests should not let wide tourism-belt seeds override the selected start area.
    effective_r = zone_radius_km or pre_filter_radius_km or override_radius_km
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
               ai_summary, overview, category_id, opening_hours, indoor_outdoor
        FROM places
        WHERE region_1 = %(region)s
          AND category_id IN (12, 14, 38, 39)
          AND visit_role = ANY(%(roles)s)
          AND is_active = TRUE
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND name = ANY(%(seed_names)s){zone_clause}
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]

    if any(r in {"spot", "culture"} for r in roles):
        blocked = [r for r in rows if _is_globally_unsuitable_tourism_place(r.get("name", ""))]
        if blocked:
            logger.info(
                "global tourism eligibility guard removed belt seeds -- region=%s blocked=%s",
                region,
                [{"name": r.get("name"), "reason": _get_unsuitable_reason(r.get("name", ""))} for r in blocked[:8]],
            )
        rows = [r for r in rows if not _is_globally_unsuitable_tourism_place(r.get("name", ""))]
    return rows


def _seed_matches_selected_anchor_context(seed: dict, selected_anchor: str | dict | set | None, selected_tokens: set[str]) -> bool:
    if not selected_tokens:
        return True
    aliases = [seed.get("canonical_name"), *(seed.get("aliases") or [])]
    seed_tokens = {
        _normalize_city_token(value)
        for value in [*aliases, *(seed.get("belts") or []), *(seed.get("themes") or [])]
        if value
    }
    if any(
        token and seed_token and (token in seed_token or seed_token in token)
        for token in selected_tokens
        for seed_token in seed_tokens
    ):
        return True

    family = _resolve_selected_anchor_family(selected_anchor)
    family_tokens = set(family.get("normalized_tokens") or [])
    if family_tokens and any(
        family_token and seed_token and (family_token in seed_token or seed_token in family_token)
        for family_token in family_tokens
        for seed_token in seed_tokens
    ):
        return True

    family_id = str(family.get("family_id") or "")
    seed_belts = {_normalize_city_token(value) for value in (seed.get("belts") or []) if value}
    family_allowlist = {
        "seoul_bukchon": {"북촌", "광화문", "삼청", "경복궁"},
        "seoul_gwanghwamun_jongno": {"광화문", "북촌", "삼청", "경복궁", "을지로"},
        "seoul_gangnam": {"강남", "한강"},
        "seoul_yeouido": {"여의도", "한강"},
        "seoul_euljiro_night": {"을지로"},
    "busan_nampo_station": {"남포", "영도"},
    "busan_gwangan": {"광안리"},
    "busan_gijang_east_coast": {"기장", "해운대"},
    "jeonbuk_jeonju_hanok": {"전주한옥마을"},
        "gimhae_gaya": {"김해가야"},
    }
    allowed = {_normalize_city_token(value) for value in family_allowlist.get(family_id, set())}
    return bool(allowed and seed_belts and allowed & seed_belts)


def _fetch_landmark_authority_candidates(
    conn,
    region: str,
    roles: list,
    selected_anchor: str | dict | set | None = None,
    zone_center: tuple | None = None,
    zone_radius_km: float | None = None,
    pre_filter_radius_km: float | None = None,
    include_representative_roles: bool = False,
) -> list:
    """Fetch existing DB candidates matching governed landmark authority aliases.

    This is a candidate-preservation helper only. It does not create POIs and
    does not force insertion into the final route.
    """
    seeds = [seed for seed in iter_landmark_seeds() if seed.get("region") == region]
    if not seeds:
        return []

    selected_tokens = _selected_anchor_tokens(selected_anchor)
    names: list[str] = []
    for seed in seeds:
        aliases = [seed.get("canonical_name"), *(seed.get("aliases") or [])]
        if not _seed_matches_selected_anchor_context(seed, selected_anchor, selected_tokens):
            continue
        for alias in aliases:
            if alias and str(alias) not in names:
                names.append(str(alias))

    if not names:
        return []

    effective_roles = list(dict.fromkeys(roles or []))
    if include_representative_roles:
        for representative_role in ("spot", "culture"):
            if representative_role not in effective_roles:
                effective_roles.append(representative_role)

    name_patterns = [f"%{name}%" for name in names if len(str(name).strip()) >= 2]
    params: dict = {"region": region, "roles": effective_roles, "names": names, "name_patterns": name_patterns}
    zone_clause = ""
    radius_options = [
        float(value)
        for value in (zone_radius_km, pre_filter_radius_km)
        if value is not None and float(value) > 0
    ]
    effective_r = max(radius_options) if radius_options else None
    if zone_center and effective_r:
        zone_clause = """
          AND (6371.0 * 2 * ASIN(SQRT(
              POWER(SIN((RADIANS(latitude) - RADIANS(%(zc_lat)s)) / 2), 2) +
              COS(RADIANS(%(zc_lat)s)) * COS(RADIANS(latitude)) *
              POWER(SIN((RADIANS(longitude) - RADIANS(%(zc_lon)s)) / 2), 2)
          ))) <= %(zone_radius_km)s"""
        params["zc_lat"] = zone_center[0]
        params["zc_lon"] = zone_center[1]
        params["zone_radius_km"] = effective_r

    sql = f"""
        SELECT place_id, name, visit_role, estimated_duration,
               latitude, longitude, view_count, ai_tags, visit_time_slot,
               rating, review_count, data_source, first_image_url,
               ai_summary, overview, category_id, opening_hours, indoor_outdoor, region_1 AS region, region_2,
               NULL::text AS address, NULL::text AS addr
        FROM places
        WHERE region_1 = %(region)s
          AND category_id IN (12, 14, 39)
          AND visit_role = ANY(%(roles)s)
          AND is_active = TRUE
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND (
              name = ANY(%(names)s)
              OR name ILIKE ANY(%(name_patterns)s)
          ){zone_clause}
        ORDER BY
          CASE WHEN visit_role IN ('spot', 'culture') THEN 0 ELSE 1 END,
          CASE WHEN category_id IN (12, 14) THEN 0 ELSE 1 END,
          view_count DESC NULLS LAST,
          place_id
        LIMIT 40
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]

    for row in rows:
        row["_landmark_candidate_entered_pool"] = True
        row["_representative_landmark_pool_status"] = "entered_pool"
        row["_representative_candidate_pool_included"] = True
        row["_alias_normalization_match"] = True
        row["_region_aware_alias_guard"] = "same_region"
        row["_family_candidate_lookup_bonus"] = 0.025 if selected_tokens else 0.0
        row["_representative_alias_pool_included"] = True
        row["_representative_candidate_pool_reason"] = (
            "selected_anchor_same_city_authority_role_expansion"
            if include_representative_roles and selected_tokens
            else (
                "default_preset_representative_role_expansion"
                if include_representative_roles
                else "landmark_authority_alias_match"
            )
        )
    return rows


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


_GENERIC_COPY_PATTERNS = (
    "부담 없이",
    "둘러보기 좋은 관광지",
    "잠시 쉬어가기 좋은 카페",
    "코스 중간",
    "쉬어가기 좋은",
)


def _place_text_for_copy(place: dict) -> str:
    return " ".join(
        str(place.get(key) or "")
        for key in (
            "name",
            "visit_role",
            "category",
            "category_name",
            "overview",
            "ai_summary",
            "address",
            "addr",
            "region",
            "region_1",
            "region_2",
        )
    )


def _copy_variant_from_place(place: dict) -> tuple[str, str]:
    name = (place.get("name") or "장소").strip()
    role = str(place.get("visit_role") or "")
    text = _place_text_for_copy(place)
    basis = place.get("_selection_basis") or {}
    if isinstance(basis, dict):
        text = f"{text} {' '.join(str(v) for v in basis.values() if v)}"
    normalized = _normalize_city_token(text)

    if any(term in normalized for term in ("전주한옥마을", "경기전", "전동성당", "오목대", "향교", "전주부채문화관")):
        return "jeonju_hanok", f"{name}{_eun_neun(name)} 전주 한옥 골목과 전통 문화 흐름을 이어가기 좋은 대표 명소입니다."
    if any(term in normalized for term in ("북촌", "삼청", "한옥", "전통찻집", "궁궐", "창덕궁", "경복궁")):
        return "bukchon_heritage_walk", f"{name}{_eun_neun(name)} 한옥 골목과 전통적인 산책 분위기를 가까이 느끼기 좋은 북촌권 명소입니다."
    if any(term in normalized for term in ("광화문", "종로", "청계천", "인사동")):
        return "gwanghwamun_jongno_walk", f"{name}{_eun_neun(name)} 광화문과 종로의 역사 산책 흐름을 자연스럽게 이어주는 중심 코스입니다."
    if any(term in normalized for term in ("성수", "서울숲", "연무장", "로스터리", "카페거리", "디저트", "편집숍")):
        return "seongsu_cafe_street", f"{name}{_eun_neun(name)} 성수 특유의 카페 거리와 산책 감성을 이어가기 좋은 포인트입니다."
    if any(term in normalized for term in ("광안리", "광안대교", "민락", "수변", "야경")):
        return "gwangan_night_sea", f"{name}{_eun_neun(name)} 광안대교 야경과 바다 산책 흐름을 함께 살려주는 광안리권 장소입니다."
    if any(term in normalized for term in ("진주성", "촉석루", "남강")):
        return "jinju_history_river", f"{name}{_eun_neun(name)} 진주성의 역사 분위기와 남강 산책 감성을 함께 느끼기 좋은 대표 명소입니다."
    if any(term in normalized for term in ("통영", "동피랑", "강구안", "디피랑", "이순신공원", "케이블카")):
        return "tongyeong_harbor_walk", f"{name}{_eun_neun(name)} 통영 항구 풍경과 골목 산책 흐름을 이어가기 좋은 여행 포인트입니다."
    if any(term in normalized for term in ("김해", "가야", "수로왕릉", "대성동고분군", "봉황동", "국립김해박물관")):
        return "gimhae_gaya_history", f"{name}{_eun_neun(name)} 김해의 가야 역사 흐름을 따라가기 좋은 대표 문화 코스입니다."
    if any(term in normalized for term in ("해변", "바다", "오션", "항구", "해안", "등대")):
        return "coastal_view", f"{name}{_eun_neun(name)} 바다 풍경과 해안 산책 분위기를 코스 안에서 선명하게 만들어주는 장소입니다."
    if any(term in normalized for term in ("야경", "루프탑", "bar", "펍", "포차", "청계천")):
        return "night_view", f"{name}{_eun_neun(name)} 저녁 시간대의 조명과 분위기를 살려주는 야간 감성 포인트입니다."
    if any(term in normalized for term in ("역사", "문화재", "궁", "성곽", "유적", "사찰", "절")):
        return "heritage", f"{name}{_eun_neun(name)} 지역의 역사와 문화적 맥락을 코스 안에서 잡아주는 대표 명소입니다."
    if role == "cafe" or any(term in normalized for term in ("카페", "커피", "로스터리", "디저트", "찻집")):
        return "cafe_vibe", f"{name}{_eun_neun(name)} 주변 산책 흐름을 잠시 정리하며 지역 분위기를 느끼기 좋은 카페입니다."
    if role == "meal" or any(term in normalized for term in ("식당", "맛집", "시장", "국밥", "해산물", "브런치")):
        return "local_meal", f"{name}{_eun_neun(name)} 이동 동선 중간에 지역 식사 경험을 자연스럽게 이어주는 장소입니다."
    if any(term in normalized for term in ("공원", "숲", "호수", "산책", "정원")):
        return "walk_nature", f"{name}{_eun_neun(name)} 걷기 좋은 풍경과 여유로운 동선을 만들어주는 산책형 장소입니다."
    return "contextual_general", f"{name}{_eun_neun(name)} 지역의 분위기와 코스 흐름을 함께 잡아주는 여행 포인트입니다."


def _build_place_description_meta(place: dict) -> dict:
    overview = _summarize_overview(place.get("overview") or "")
    ai_summary = (place.get("ai_summary") or "").strip()
    candidate = overview or ai_summary
    generic_demote = 0.0
    variant = "source_overview" if overview else ("source_ai_summary" if ai_summary else None)
    if candidate and any(pattern in candidate for pattern in _GENERIC_COPY_PATTERNS):
        generic_demote = 1.0
        candidate = ""
        variant = None
    if not candidate or len(candidate) < 20:
        variant, candidate = _copy_variant_from_place(place)
        generic_demote = max(generic_demote, 1.0)
    if len(candidate) > 200:
        candidate = candidate[:197].rstrip() + "..."
    return {
        "description": candidate,
        "description_quality_variant": variant or "contextual_general",
        "generic_copy_demote": round(float(generic_demote or 0.0), 4),
    }


def _build_place_description(place: dict) -> str:
    return _build_place_description_meta(place)["description"]



def _attach_first_place_diversity_metadata(
    row: dict,
    *,
    pool_size: int,
    saturation_penalty: float = 0.0,
    rotation_bonus: float = 0.0,
    applied: bool = False,
    repeat_count: int = 0,
    family_pool_size: int = 0,
    family_saturation_penalty: float = 0.0,
    family_rotation_bonus: float = 0.0,
    family_diversity_applied: bool = False,
    family_first_place_repeat: int = 0,
) -> dict:
    row["_first_place_repeat_count"] = repeat_count
    row["_first_place_saturation_penalty"] = round(float(saturation_penalty or 0.0), 4)
    row["_diversity_rotation_bonus"] = round(float(rotation_bonus or 0.0), 4)
    row["_representative_pool_size"] = int(pool_size or 1)
    row["_regenerate_diversity_applied"] = bool(applied)
    row["_representative_family_pool_size"] = int(family_pool_size or 0)
    row["_representative_family_saturation_penalty"] = round(float(family_saturation_penalty or 0.0), 4)
    row["_representative_family_rotation_bonus"] = round(float(family_rotation_bonus or 0.0), 4)
    row["_representative_family_diversity_applied"] = bool(family_diversity_applied)
    row["_representative_family_first_place_repeat"] = int(family_first_place_repeat or 0)
    row["_regenerate_repeat_penalty"] = round(float(family_saturation_penalty or saturation_penalty or 0.0), 4)
    row["_representative_family_rotation_applied"] = bool(family_diversity_applied)
    return row


def _choose_diverse_first_place(
    scored_rows: list[tuple[float, dict, dict]],
    *,
    top_k: int = 5,
    score_window: float = 0.16,
    saturation_gap: float = 0.055,
    max_saturation_penalty: float = 0.075,
    rotation_bonus: float = 0.018,
    family_diversity: bool = False,
) -> tuple[dict, dict]:
    """Pick a first place from a tight representative pool, not a hard random shuffle."""
    if not scored_rows:
        return None, {}
    ordered = sorted(scored_rows, key=lambda item: item[0], reverse=True)
    top_score = float(ordered[0][0])
    pool = [item for item in ordered[:top_k] if top_score - float(item[0]) <= score_window]
    if len(pool) < 2 and len(ordered) > 1:
        pool = ordered[:2]
    if len(pool) <= 1:
        row = ordered[0][1]
        detail = dict(ordered[0][2] or {})
        return _attach_first_place_diversity_metadata(row, pool_size=1), detail

    second_score = float(ordered[1][0])
    saturation_penalty = min(max_saturation_penalty, max(0.0, (top_score - second_score) - saturation_gap))
    adjusted: list[tuple[float, dict, dict, float]] = []
    for idx, (score, row, detail) in enumerate(pool):
        adjusted_score = float(score)
        item_rotation_bonus = 0.0
        if idx == 0 and saturation_penalty:
            adjusted_score -= saturation_penalty
        elif idx > 0:
            item_rotation_bonus = rotation_bonus
            adjusted_score += item_rotation_bonus
        adjusted.append((adjusted_score, row, detail or {}, item_rotation_bonus))

    min_score = min(item[0] for item in adjusted)
    weights = [max(0.001, (item[0] - min_score) + 0.02) for item in adjusted]
    chosen_score, chosen_row, chosen_detail, chosen_rotation_bonus = random.choices(adjusted, weights=weights, k=1)[0]
    chosen_detail = dict(chosen_detail or {})
    chosen_detail["first_place_saturation_penalty"] = round(saturation_penalty, 4)
    chosen_detail["diversity_rotation_bonus"] = round(chosen_rotation_bonus, 4)
    chosen_detail["regenerate_repeat_penalty"] = round(saturation_penalty, 4)
    chosen_detail["representative_pool_size"] = len(pool)
    chosen_detail["regenerate_diversity_applied"] = True
    chosen_detail["first_place_repeat_count"] = 0
    if family_diversity:
        chosen_detail["representative_family_pool_size"] = len(pool)
        chosen_detail["representative_family_rotation_bonus"] = round(chosen_rotation_bonus, 4)
        chosen_detail["representative_family_saturation_penalty"] = round(saturation_penalty, 4)
        chosen_detail["representative_family_first_place_repeat"] = 0
        chosen_detail["representative_family_diversity_applied"] = True
        chosen_detail["representative_family_rotation_applied"] = True
    return _attach_first_place_diversity_metadata(
        chosen_row,
        pool_size=len(pool),
        saturation_penalty=saturation_penalty,
        rotation_bonus=chosen_rotation_bonus,
        applied=True,
        repeat_count=0,
        family_pool_size=(len(pool) if family_diversity else 0),
        family_saturation_penalty=(saturation_penalty if family_diversity else 0.0),
        family_rotation_bonus=(chosen_rotation_bonus if family_diversity else 0.0),
        family_diversity_applied=family_diversity,
        family_first_place_repeat=0,
    ), chosen_detail

def _select_anchor(
    conn, region: str, themes: list, first_role: str | list,
    zone_center: tuple | None = None, zone_radius_km: float | None = None,
    exclude_ids: set | None = None,
    selected_anchor: str | dict | None = None,
    region_identity: dict | None = None,
    flow_profile: dict | None = None,
    default_preset_mode: bool = False,
    selected_anchor_family: dict | None = None,
    late_context: bool = False,
    start_time: str | None = None,
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
               rating, review_count, data_source, first_image_url, region_1 AS region, region_2, NULL::text AS address, NULL::text AS addr, category_id, opening_hours, indoor_outdoor
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

    _authority_rows = _fetch_landmark_authority_candidates(
        conn,
        region,
        roles,
        selected_anchor=selected_anchor,
        zone_center=zone_center,
        zone_radius_km=zone_radius_km,
        pre_filter_radius_km=12.0 if (zone_center and selected_anchor and region == "서울") else (
            30.0 if (zone_center and not zone_radius_km) else None
        ),
        include_representative_roles=bool(selected_anchor) or (
            bool(default_preset_mode) and region == "서울"
        ),
    )
    if _authority_rows:
        _used = {r["place_id"] for r in rows}
        rows = rows + [r for r in _authority_rows if r["place_id"] not in _used]

    _seomyeon_rows = _fetch_busan_seomyeon_family_candidates(
        conn,
        region,
        roles,
        selected_anchor_family or _resolve_selected_anchor_family(selected_anchor),
        zone_center=zone_center,
        zone_radius_km=zone_radius_km or 12.0,
    )
    if _seomyeon_rows:
        _used = {r["place_id"] for r in rows}
        rows = rows + [r for r in _seomyeon_rows if r["place_id"] not in _used]

    _seoul_editorial_rows = _fetch_seoul_editorial_depth_candidates(
        conn,
        region,
        roles,
        selected_anchor_family or _resolve_selected_anchor_family(selected_anchor),
        selected_anchor=selected_anchor,
        default_preset_mode=default_preset_mode,
        zone_center=zone_center,
        zone_radius_km=zone_radius_km or 12.0,
    )
    if _seoul_editorial_rows:
        _used = {r["place_id"] for r in rows}
        rows = rows + [r for r in _seoul_editorial_rows if r["place_id"] not in _used]

    # anchor 후보에서는 대표 관광 부적합 시설까지 제거한다.
    # anchor ????? ?? ?? ?? ??? ??? ????.
    blocked_anchor_rows = [r for r in rows if _is_unsuitable_representative_spot(r["name"])]
    if blocked_anchor_rows:
        logger.info(
            "global tourism eligibility guard removed anchor candidates -- region=%s blocked=%s",
            region,
            [{"name": r.get("name"), "reason": _get_unsuitable_reason(r.get("name", ""))} for r in blocked_anchor_rows[:8]],
        )
    rows = [r for r in rows if not _is_unsuitable_representative_spot(r["name"])]
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
    else:
        rows.sort(key=lambda r: _normalize_city_token(r["name"]))

    family_signal_context = selected_anchor_family or _resolve_selected_anchor_family(selected_anchor)
    selected_anchor_tokens = _selected_anchor_tokens(selected_anchor)
    selected_anchor_tokens.update(family_signal_context.get("normalized_tokens") or [])
    if selected_anchor_tokens:
        scored_selected_anchor_rows: list[tuple[float, dict, dict]] = []
        for row in rows:
            normalized_text = _normalize_city_token(" ".join(_extract_city_terms(row)))
            has_anchor = 1 if any(token and token in normalized_text for token in selected_anchor_tokens) else 0
            authority_signal = score_landmark_authority(row, region_identity, flow_profile, target_slot="anchor")
            editorial_signal = score_editorial_route_fit(row, region_identity, flow_profile, target_slot="anchor")
            authority_score = (
                float(authority_signal.get("landmark_authority_score") or 0.0)
                + float(authority_signal.get("external_verified_score") or 0.0)
                + float(authority_signal.get("external_popularity_score") or 0.0)
                + float(authority_signal.get("representative_confidence_score") or 0.0)
                + float(authority_signal.get("family_candidate_lookup_bonus") or 0.0)
                - float(authority_signal.get("public_data_weakness_penalty") or 0.0)
                - float(authority_signal.get("wrong_region_alias_demote") or 0.0)
            )
            editorial_score = (
                float(editorial_signal.get("editorial_bonus") or 0.0)
                + float(editorial_signal.get("jinju_history_first_place_bonus") or 0.0)
                + float(editorial_signal.get("tongyeong_same_city_bonus") or 0.0)
                + float(editorial_signal.get("gimhae_gaya_family_score") or 0.0)
                - float(editorial_signal.get("editorial_demote") or 0.0)
                - float(editorial_signal.get("tongyeong_geoje_drift_demote") or 0.0)
                - float(editorial_signal.get("weak_museum_first_place_demote") or 0.0)
            )
            family_signal = _score_selected_anchor_family(
                row,
                family_signal_context,
                authority_signal,
                default_preset_mode=default_preset_mode,
                target_slot="anchor",
            )
            family_match_score = float(family_signal.get("selected_anchor_family_match_score") or 0.0)
            family_drift_demote = float(family_signal.get("selected_anchor_family_drift_demote") or 0.0)
            busan_oldtown_signal = _score_busan_oldtown_family(
                row,
                family_signal_context,
                region=region,
                target_slot="anchor",
            )
            busan_oldtown_family_score = float(busan_oldtown_signal.get("busan_oldtown_family_score") or 0.0)
            busan_oldtown_drift_demote = float(busan_oldtown_signal.get("busan_oldtown_drift_demote") or 0.0)
            busan_oldtown_support_slot_score = float(busan_oldtown_signal.get("busan_oldtown_support_slot_score") or 0.0)
            exact_landmark_signal = _score_exact_landmark_visibility(
                row,
                family_signal_context,
                authority_signal,
                region=region,
                target_slot="anchor",
            )
            exact_landmark_visibility_score = float(exact_landmark_signal.get("exact_landmark_visibility_score") or 0.0)
            exact_landmark_support_slot_bonus = float(exact_landmark_signal.get("exact_landmark_support_slot_bonus") or 0.0)
            weak_substitute_demote = float(exact_landmark_signal.get("weak_substitute_demote") or 0.0)
            exact_slot_alignment_bonus = float(exact_landmark_signal.get("exact_slot_alignment_bonus") or 0.0)
            oldtown_substitute_demote = float(exact_landmark_signal.get("oldtown_substitute_demote") or 0.0)
            east_coast_signal = _score_busan_east_coast_family(
                row,
                selected_anchor_family,
                region=region,
                target_slot="anchor",
            )
            east_coast_family_score = float(east_coast_signal.get("busan_east_coast_family_score") or 0.0)
            east_coast_drift_demote = float(east_coast_signal.get("haeundae_gwangan_drift_demote") or 0.0)
            east_coast_support_slot_score = float(east_coast_signal.get("east_coast_support_slot_score") or 0.0)
            east_coast_signal = _score_busan_east_coast_family(
                row,
                family_signal_context,
                region=region,
                target_slot="anchor",
            )
            east_coast_family_score = float(east_coast_signal.get("busan_east_coast_family_score") or 0.0)
            east_coast_drift_demote = float(east_coast_signal.get("haeundae_gwangan_drift_demote") or 0.0)
            east_coast_support_slot_score = float(east_coast_signal.get("east_coast_support_slot_score") or 0.0)
            seomyeon_signal = _score_busan_seomyeon_family(
                row,
                family_signal_context,
                authority_signal,
                region=region,
                target_slot="anchor",
            )
            seomyeon_family_score = float(seomyeon_signal.get("seomyeon_family_score") or 0.0)
            seomyeon_drift_demote = float(seomyeon_signal.get("seomyeon_drift_demote") or 0.0)
            seomyeon_weak_candidate_demote = float(seomyeon_signal.get("seomyeon_weak_candidate_demote") or 0.0)
            seoul_editorial_depth_signal = _score_seoul_editorial_depth(
                row,
                family_signal_context,
                authority_signal,
                region=region,
                target_slot="anchor",
                default_preset_mode=default_preset_mode,
            )
            seoul_broad_default_family_balance = float(seoul_editorial_depth_signal.get("seoul_broad_default_family_balance") or 0.0)
            bukchon_editorial_depth_score = float(seoul_editorial_depth_signal.get("bukchon_editorial_depth_score") or 0.0)
            seongsu_editorial_depth_score = float(seoul_editorial_depth_signal.get("seongsu_editorial_depth_score") or 0.0)
            lifestyle_support_slot_visibility = float(seoul_editorial_depth_signal.get("lifestyle_support_slot_visibility") or 0.0)
            representative_family_rotation_balance = float(seoul_editorial_depth_signal.get("representative_family_rotation_balance") or 0.0)
            seoul_editorial_weak_demote = float(seoul_editorial_depth_signal.get("seoul_editorial_weak_demote") or 0.0)
            seoul_family_signal = _score_seoul_gangnam_yeouido_family(
                row,
                family_signal_context,
                authority_signal,
                region=region,
                target_slot="anchor",
            )
            seoul_external_authority_boost = float(seoul_family_signal.get("seoul_external_authority_boost") or 0.0)
            gangnam_family_score = float(seoul_family_signal.get("gangnam_family_score") or 0.0)
            yeouido_family_score = float(seoul_family_signal.get("yeouido_family_score") or 0.0)
            seoul_weak_lifestyle_demote = float(seoul_family_signal.get("seoul_weak_lifestyle_demote") or 0.0)
            gangnam_candidate_depth_score = float(seoul_family_signal.get("gangnam_candidate_depth_score") or 0.0)
            gangnam_first_place_dominance_penalty = float(
                seoul_family_signal.get("gangnam_first_place_dominance_penalty") or 0.0
            )
            yeouido_public_facility_final_demote = float(
                seoul_family_signal.get("yeouido_public_facility_final_demote") or 0.0
            )
            euljiro_night_family_score = float(seoul_family_signal.get("euljiro_night_family_score") or 0.0)
            gangnam_editorial_representative_score = float(
                seoul_family_signal.get("gangnam_editorial_representative_score") or 0.0
            )
            weak_editorial_first_place_demote = float(seoul_family_signal.get("weak_editorial_first_place_demote") or 0.0)
            nightlife_coherence_score = float(seoul_family_signal.get("nightlife_coherence_score") or 0.0)
            public_facility_signal = _score_public_facility_tourism_fit(
                row,
                authority_signal,
                default_preset_mode=default_preset_mode,
                target_slot="anchor",
                first_place=True,
            )
            public_facility_demote = float(public_facility_signal.get("public_facility_demote") or 0.0)
            representative_tourism_fit = float(public_facility_signal.get("representative_tourism_fit") or 0.0)
            anchor_night_confidence_signal = _score_night_operating_confidence(
                row,
                flow_profile,
                "anchor",
                late_context=bool(late_context),
                current_minute=_parse_start_minute(start_time) if late_context else None,
            )
            anchor_night_indoor_strong_demote = float(anchor_night_confidence_signal.get("night_indoor_strong_demote") or 0.0)
            anchor_indoor_night_confidence_demote = float(anchor_night_confidence_signal.get("indoor_night_confidence_demote") or 0.0)
            anchor_night_safe_outdoor_priority = float(anchor_night_confidence_signal.get("night_safe_outdoor_priority") or 0.0)
            anchor_nightlife_suitability_alignment = float(anchor_night_confidence_signal.get("nightlife_suitability_alignment") or 0.0)
            representative_pool_included = bool(
                row.get("_representative_candidate_pool_included")
                or row.get("_landmark_candidate_entered_pool")
            )
            weak_museum_pool_demote = 0.0
            if (
                not representative_pool_included
                and float(editorial_signal.get("weak_museum_first_place_demote") or 0.0) > 0
                and family_signal_context.get("family_id") == "진주남강역사"
            ):
                weak_museum_pool_demote = min(
                    0.10,
                    float(editorial_signal.get("weak_museum_first_place_demote") or 0.0),
                )
            if (
                not representative_pool_included
                and family_signal_context.get("family_id") == "진주남강역사"
                and any(
                    _normalize_city_token(term) in normalized_text
                    for term in (
                        "남가람박물관",
                        "재봉틀",
                        "목공예전수관",
                        "와인갤러리",
                        "항공우주과학관",
                        "시립도서관",
                        "박물관",
                        "전수관",
                        "갤러리",
                        "도서관",
                    )
                )
            ):
                weak_museum_pool_demote = max(weak_museum_pool_demote, 0.08)
            dist = 0.0
            if zone_center:
                dist = _haversine(zone_center[0], zone_center[1], row["latitude"], row["longitude"])
            score = (
                (0.42 if has_anchor else 0.0)
                + authority_score
                + editorial_score
                + family_match_score
                - family_drift_demote
                + busan_oldtown_family_score
                + busan_oldtown_support_slot_score
                - busan_oldtown_drift_demote
                + exact_landmark_visibility_score
                + exact_landmark_support_slot_bonus
                + exact_slot_alignment_bonus
                - weak_substitute_demote
                - oldtown_substitute_demote
                + east_coast_family_score
                + east_coast_support_slot_score
                - east_coast_drift_demote
                + seomyeon_family_score
                - seomyeon_drift_demote
                - seomyeon_weak_candidate_demote
                + seoul_broad_default_family_balance
                + bukchon_editorial_depth_score
                + seongsu_editorial_depth_score
                + lifestyle_support_slot_visibility
                + representative_family_rotation_balance
                - seoul_editorial_weak_demote
                + seoul_external_authority_boost
                + gangnam_family_score
                + yeouido_family_score
                + gangnam_candidate_depth_score
                - seoul_weak_lifestyle_demote
                - gangnam_first_place_dominance_penalty
                - yeouido_public_facility_final_demote
                + euljiro_night_family_score
                + gangnam_editorial_representative_score
                + nightlife_coherence_score
                - weak_editorial_first_place_demote
                - public_facility_demote
                + representative_tourism_fit
                + anchor_night_safe_outdoor_priority
                + anchor_nightlife_suitability_alignment
                - anchor_indoor_night_confidence_demote
                - anchor_night_indoor_strong_demote
                - weak_museum_pool_demote
                - min(dist, 30.0) * 0.003
            )
            landmark_matches = authority_signal.get("landmark_authority_matches") or []
            exact_landmark_intent = bool(
                has_anchor
                and landmark_matches
                and any(
                    token and any(token in _normalize_city_token(str(match)) for match in landmark_matches)
                    for token in selected_anchor_tokens
                )
            )
            detail = {
                "place_id": row.get("place_id"),
                "place_name": row.get("name"),
                "selected_anchor_match": bool(has_anchor),
                "selected_anchor_authority_score": round(authority_score, 4),
                "selected_anchor_editorial_score": round(editorial_score, 4),
                "selected_anchor_distance_km": round(dist, 3),
                "selected_anchor_exact_landmark_intent": exact_landmark_intent,
                "landmark_authority_matches": landmark_matches,
                "alias_normalization_match": authority_signal.get("alias_normalization_match") or row.get("_alias_normalization_match") or [],
                "region_aware_alias_guard": authority_signal.get("region_aware_alias_guard") or row.get("_region_aware_alias_guard"),
                "wrong_region_alias_demote": authority_signal.get("wrong_region_alias_demote", 0.0),
                "family_candidate_lookup_bonus": authority_signal.get("family_candidate_lookup_bonus", row.get("_family_candidate_lookup_bonus", 0.0)),
                "representative_alias_pool_included": bool(
                    authority_signal.get("representative_alias_pool_included")
                    or row.get("_representative_alias_pool_included")
                ),
                "representative_candidate_pool_included": representative_pool_included,
                "representative_candidate_pool_reason": row.get("_representative_candidate_pool_reason"),
                "representative_pool_cutoff_score": None,
                "representative_pool_competitor_count": 0,
                "weak_museum_pool_demote": round(weak_museum_pool_demote, 4),
                "jinju_history_first_place_bonus": editorial_signal.get("jinju_history_first_place_bonus", 0.0),
                "tongyeong_same_city_bonus": editorial_signal.get("tongyeong_same_city_bonus", 0.0),
                "tongyeong_geoje_drift_demote": editorial_signal.get("tongyeong_geoje_drift_demote", 0.0),
                "gimhae_gaya_family_score": editorial_signal.get("gimhae_gaya_family_score", 0.0),
                "weak_museum_first_place_demote": editorial_signal.get("weak_museum_first_place_demote", 0.0),
                "editorial_demote_reason": editorial_signal.get("editorial_demote_reason"),
                "selected_anchor_family_id": family_signal.get("selected_anchor_family_id"),
                "selected_anchor_family_match_score": round(family_match_score, 4),
                "selected_anchor_family_preserved": bool(family_signal.get("selected_anchor_family_preserved")),
                "selected_anchor_family_drift_demote": round(family_drift_demote, 4),
                "selected_anchor_drift_reason": family_signal.get("selected_anchor_drift_reason"),
                "fallback_level_used": family_signal.get("fallback_level_used"),
                "busan_oldtown_family_score": round(busan_oldtown_family_score, 4),
                "busan_oldtown_pool_included": bool(busan_oldtown_signal.get("busan_oldtown_pool_included")),
                "busan_oldtown_drift_demote": round(busan_oldtown_drift_demote, 4),
                "busan_oldtown_support_slot_score": round(busan_oldtown_support_slot_score, 4),
                "busan_oldtown_expected_landmark_visible": bool(busan_oldtown_signal.get("busan_oldtown_expected_landmark_visible")),
                "busan_oldtown_match_terms": busan_oldtown_signal.get("busan_oldtown_match_terms") or [],
                "exact_landmark_visibility_score": round(exact_landmark_visibility_score, 4),
                "exact_landmark_pool_included": bool(exact_landmark_signal.get("exact_landmark_pool_included")),
                "exact_landmark_support_slot_bonus": round(exact_landmark_support_slot_bonus, 4),
                "exact_support_slot_visibility_bonus": round(
                    float(exact_landmark_signal.get("exact_support_slot_visibility_bonus") or exact_landmark_support_slot_bonus),
                    4,
                ),
                "exact_support_slot_replacement_applied": False,
                "exact_landmark_final_route_visible": bool(exact_landmark_signal.get("exact_landmark_pool_included")),
                "oldtown_candidate_replaced": None,
                "support_slot_visibility_reason": (
                    "exact_landmark_pool_included"
                    if exact_landmark_signal.get("exact_landmark_pool_included")
                    else exact_landmark_signal.get("exact_landmark_missing_reason")
                ),
                "exact_landmark_missing_reason": exact_landmark_signal.get("exact_landmark_missing_reason"),
                "weak_substitute_demote": round(weak_substitute_demote, 4),
                "exact_slot_alignment_bonus": round(exact_slot_alignment_bonus, 4),
                "exact_anchor_final_visibility": bool(exact_landmark_signal.get("exact_anchor_final_visibility")),
                "oldtown_substitute_demote": round(oldtown_substitute_demote, 4),
                "exact_landmark_match_terms": exact_landmark_signal.get("exact_landmark_match_terms") or [],
                "exact_landmark_focus_match_terms": exact_landmark_signal.get("exact_landmark_focus_match_terms") or [],
                "busan_east_coast_family_score": round(east_coast_family_score, 4),
                "east_coast_family_preserved": bool(east_coast_signal.get("east_coast_family_preserved")),
                "haeundae_gwangan_drift_demote": round(east_coast_drift_demote, 4),
                "east_coast_support_slot_score": round(east_coast_support_slot_score, 4),
                "east_coast_expected_landmark_visible": bool(east_coast_signal.get("east_coast_expected_landmark_visible")),
                "east_coast_match_terms": east_coast_signal.get("east_coast_match_terms") or [],
                "seomyeon_family_score": round(seomyeon_family_score, 4),
                "seomyeon_family_pool_included": bool(seomyeon_signal.get("seomyeon_family_pool_included")),
                "seomyeon_nightlife_pool_included": bool(seomyeon_signal.get("seomyeon_nightlife_pool_included")),
                "seomyeon_drift_demote": round(seomyeon_drift_demote, 4),
                "seomyeon_weak_candidate_demote": round(seomyeon_weak_candidate_demote, 4),
                "seomyeon_family_match_terms": seomyeon_signal.get("seomyeon_family_match_terms") or [],
                "seoul_broad_default_family_balance": round(seoul_broad_default_family_balance, 4),
                "bukchon_editorial_depth_score": round(bukchon_editorial_depth_score, 4),
                "seongsu_editorial_depth_score": round(seongsu_editorial_depth_score, 4),
                "lifestyle_support_slot_visibility": round(lifestyle_support_slot_visibility, 4),
                "representative_family_rotation_balance": round(representative_family_rotation_balance, 4),
                "seoul_broad_family_key": seoul_editorial_depth_signal.get("seoul_broad_family_key"),
                "seoul_broad_family_matches": seoul_editorial_depth_signal.get("seoul_broad_family_matches") or [],
                "bukchon_editorial_depth_matches": seoul_editorial_depth_signal.get("bukchon_editorial_depth_matches") or [],
                "seongsu_editorial_depth_matches": seoul_editorial_depth_signal.get("seongsu_editorial_depth_matches") or [],
                "seoul_editorial_weak_demote": round(seoul_editorial_weak_demote, 4),
                "seoul_editorial_depth_pool_included": bool(seoul_editorial_depth_signal.get("seoul_editorial_depth_pool_included")),
                "seoul_external_authority_boost": round(seoul_external_authority_boost, 4),
                "gangnam_family_score": round(gangnam_family_score, 4),
                "yeouido_family_score": round(yeouido_family_score, 4),
                "seoul_weak_lifestyle_demote": round(seoul_weak_lifestyle_demote, 4),
                "seoul_family_pool_included": bool(seoul_family_signal.get("seoul_family_pool_included")),
                "seoul_family_match_terms": seoul_family_signal.get("seoul_family_match_terms") or [],
                "gangnam_candidate_depth_score": round(gangnam_candidate_depth_score, 4),
                "gangnam_representative_pool_included": bool(seoul_family_signal.get("gangnam_representative_pool_included")),
                "gangnam_first_place_dominance_penalty": round(gangnam_first_place_dominance_penalty, 4),
                "yeouido_public_facility_final_demote": round(yeouido_public_facility_final_demote, 4),
                "family_candidate_depth_before_after": seoul_family_signal.get("family_candidate_depth_before_after"),
                "euljiro_night_family_score": round(euljiro_night_family_score, 4),
                "euljiro_nightlife_pool_included": bool(seoul_family_signal.get("euljiro_nightlife_pool_included")),
                "gangnam_editorial_representative_score": round(gangnam_editorial_representative_score, 4),
                "weak_editorial_first_place_demote": round(weak_editorial_first_place_demote, 4),
                "nightlife_coherence_score": round(nightlife_coherence_score, 4),
                "operating_hours_known_closed": bool(anchor_night_confidence_signal.get("operating_hours_known_closed")),
                "night_indoor_strong_demote": round(anchor_night_indoor_strong_demote, 4),
                "relaxed_unknown_hours_allowed": bool(anchor_night_confidence_signal.get("relaxed_unknown_hours_allowed")),
                "known_closed_removed": bool(anchor_night_confidence_signal.get("known_closed_removed")),
                "night_safe_indoor_exception": bool(anchor_night_confidence_signal.get("night_safe_indoor_exception")),
                "night_operating_confidence_reason": anchor_night_confidence_signal.get("night_operating_confidence_reason"),
                "indoor_semantic_detected": bool(anchor_night_confidence_signal.get("indoor_semantic_detected")),
                "known_closed_indoor_removed": bool(anchor_night_confidence_signal.get("known_closed_indoor_removed")),
                "night_indoor_semantic_demote": float(anchor_night_confidence_signal.get("night_indoor_semantic_demote") or 0.0),
                "indoor_closing_time_applied": bool(anchor_night_confidence_signal.get("indoor_closing_time_applied")),
                "public_facility_demote": round(public_facility_demote, 4),
                "representative_tourism_fit": round(representative_tourism_fit, 4),
                "weak_public_facility_reason": public_facility_signal.get("weak_public_facility_reason"),
                "first_anchor_score": round(score, 4),
            }
            scored_selected_anchor_rows.append((score, row, detail))
        scored_selected_anchor_rows.sort(key=lambda item: item[0], reverse=True)
        if late_context:
            anchor_start_min = _parse_start_minute(start_time)
            non_closed_selected_anchor_rows = [
                item for item in scored_selected_anchor_rows
                if not item[2].get("operating_hours_known_closed")
                and not (
                    anchor_start_min is not None
                    and (lambda close: close is not None and anchor_start_min >= close)(
                        _extract_known_close_min(item[1])[0]
                    )
                )
            ]
            if non_closed_selected_anchor_rows:
                scored_selected_anchor_rows = non_closed_selected_anchor_rows
        if scored_selected_anchor_rows:
            representative_rows = [
                item for item in scored_selected_anchor_rows
                if (item[2] or {}).get("representative_candidate_pool_included")
            ]
            cutoff_score = scored_selected_anchor_rows[min(len(scored_selected_anchor_rows), 8) - 1][0]
            competitor_count = max(0, len(scored_selected_anchor_rows) - len(representative_rows))
            for _, _, detail in scored_selected_anchor_rows:
                detail["representative_pool_cutoff_score"] = round(float(cutoff_score), 4)
                detail["representative_pool_competitor_count"] = competitor_count
            top_score, top_row, top_detail = scored_selected_anchor_rows[0]
            if (
                family_signal_context.get("family_id") == "seoul_gangnam"
                and float(top_detail.get("gangnam_first_place_dominance_penalty") or 0.0) > 0
            ):
                gangnam_alternate_rows = [
                    item for item in scored_selected_anchor_rows
                    if float((item[2] or {}).get("gangnam_candidate_depth_score") or 0.0) > 0
                    and float((item[2] or {}).get("gangnam_first_place_dominance_penalty") or 0.0) == 0
                ]
                if gangnam_alternate_rows:
                    chosen_row, chosen_detail = _choose_diverse_first_place(
                        gangnam_alternate_rows,
                        top_k=6,
                        score_window=1.4,
                        saturation_gap=0.02,
                        max_saturation_penalty=0.2,
                        rotation_bonus=0.11,
                        family_diversity=True,
                    )
                    chosen_detail["gangnam_first_place_dominance_penalty"] = float(top_detail.get("gangnam_first_place_dominance_penalty") or 0.0)
                    chosen_detail["representative_pool_cutoff_score"] = round(float(scored_selected_anchor_rows[min(len(scored_selected_anchor_rows), 8) - 1][0]), 4)
                    chosen_detail["representative_pool_competitor_count"] = max(0, len(scored_selected_anchor_rows) - len(gangnam_alternate_rows))
                    chosen_row["_first_anchor_candidate_scores"] = [item[2] for item in scored_selected_anchor_rows[:12]]
                    chosen_row["_first_anchor_candidate_scores"].insert(0, chosen_detail)
                    return chosen_row
            # Exact governed landmark requests, e.g. Haedong Yonggungsa, should not be rotated away.
            selected_anchor_exact_text = _normalize_city_token(selected_anchor) if isinstance(selected_anchor, str) else ""
            top_place_exact_text = _normalize_city_token(top_detail.get("place_name"))
            exact_anchor_name_match = bool(
                selected_anchor_exact_text
                and top_place_exact_text
                and (
                    selected_anchor_exact_text == top_place_exact_text
                    or top_place_exact_text in selected_anchor_exact_text
                )
            )
            if (
                top_detail.get("selected_anchor_exact_landmark_intent")
                and exact_anchor_name_match
                and float(top_detail.get("selected_anchor_authority_score") or 0.0) >= 0.18
            ):
                top_row["_first_anchor_candidate_scores"] = [item[2] for item in scored_selected_anchor_rows[:8]]
                return _attach_first_place_diversity_metadata(top_row, pool_size=1)
            family_preserved_rows = [
                item for item in scored_selected_anchor_rows
                if (item[2] or {}).get("selected_anchor_family_preserved")
                and not (item[2] or {}).get("selected_anchor_drift_reason")
                and float((item[2] or {}).get("public_facility_demote") or 0.0) < 0.08
            ]
            anchor_matched_rows = [item for item in scored_selected_anchor_rows if (item[2] or {}).get("selected_anchor_match")]
            if len(family_preserved_rows) >= 2:
                diversity_source_rows = family_preserved_rows
                family_diversity_applied = True
                family_top_k = 8
                family_score_window = 0.78
            elif family_signal_context.get("family_id") and len(family_preserved_rows) == 1:
                if family_signal_context.get("family_id") in {"seoul_gangnam", "seoul_yeouido"}:
                    diversity_source_rows = scored_selected_anchor_rows
                    family_diversity_applied = True
                    family_top_k = 6
                    family_score_window = 0.36
                else:
                    diversity_source_rows = family_preserved_rows
                    family_diversity_applied = False
                    family_top_k = 1
                    family_score_window = 0.0
            else:
                diversity_source_rows = anchor_matched_rows if len(anchor_matched_rows) >= 2 else scored_selected_anchor_rows
                family_diversity_applied = False
                family_top_k = 5
                family_score_window = 0.42
            chosen_row, chosen_detail = _choose_diverse_first_place(
                diversity_source_rows,
                top_k=family_top_k,
                score_window=family_score_window,
                saturation_gap=0.02 if family_diversity_applied else 0.05,
                max_saturation_penalty=0.44 if family_diversity_applied else 0.32,
                rotation_bonus=0.095 if family_diversity_applied else 0.04,
                family_diversity=family_diversity_applied,
            )
            chosen_row["_first_anchor_candidate_scores"] = [item[2] for item in scored_selected_anchor_rows[:8]]
            return chosen_row

    if region_identity and not selected_anchor_tokens and not selected_anchor:
        scored_anchor_rows: list[tuple[float, dict, dict]] = []
        for row in rows:
            dominant_signal = score_dominant_belt_affinity(row, region_identity)
            contamination_signal = score_route_contamination(row, region_identity, flow_profile, target_slot="anchor")
            suitability_signal = score_vibe_tourism_suitability(row, flow_profile, target_slot="anchor")
            editorial_signal = score_editorial_route_fit(row, region_identity, flow_profile, target_slot="anchor")
            landmark_authority_signal = score_landmark_authority(row, region_identity, flow_profile, target_slot="anchor")
            image_signal = _score_image_availability(row, flow_profile=flow_profile, target_slot="anchor", first_place=True)
            indoor_signal = _score_coastal_indoor_leisure(row, flow_profile=flow_profile, target_slot="anchor", first_place=True)
            flow_signal = score_flow_continuity(row, None, flow_profile)
            dom_bonus = float(dominant_signal.get("dominant_belt_bonus") or 0.0)
            suit_bonus = float(suitability_signal.get("suitability_bonus") or 0.0)
            flow_bonus = float(flow_signal.get("continuity_bonus") or 0.0)
            contamination_demote = float(contamination_signal.get("route_contamination_demote") or 0.0)
            editorial_bonus = float(editorial_signal.get("editorial_bonus") or 0.0)
            editorial_demote = float(editorial_signal.get("editorial_demote") or 0.0)
            seoul_default_representative_score = float(editorial_signal.get("seoul_default_representative_score") or 0.0)
            seoul_default_weak_first_place_demote = float(editorial_signal.get("seoul_default_weak_first_place_demote") or 0.0)
            landmark_authority_score = float(landmark_authority_signal.get("landmark_authority_score") or 0.0)
            external_verified_score = float(landmark_authority_signal.get("external_verified_score") or 0.0)
            external_popularity_score = float(landmark_authority_signal.get("external_popularity_score") or 0.0)
            public_data_weakness_penalty = float(landmark_authority_signal.get("public_data_weakness_penalty") or 0.0)
            representative_confidence_score = float(landmark_authority_signal.get("representative_confidence_score") or 0.0)
            weak_generic_authority_demote = float(landmark_authority_signal.get("weak_generic_authority_demote") or 0.0)
            family_candidate_lookup_bonus = float(landmark_authority_signal.get("family_candidate_lookup_bonus") or 0.0)
            wrong_region_alias_demote = float(landmark_authority_signal.get("wrong_region_alias_demote") or 0.0)
            default_preset_signal = _score_default_preset_landmark(
                row,
                landmark_authority_signal,
                default_preset_mode=default_preset_mode,
                target_slot="anchor",
            )
            default_preset_landmark_bonus = float(default_preset_signal.get("default_preset_landmark_bonus") or 0.0)
            weird_candidate_demote = float(default_preset_signal.get("weird_candidate_demote") or 0.0)
            public_facility_signal = _score_public_facility_tourism_fit(
                row,
                landmark_authority_signal,
                default_preset_mode=default_preset_mode,
                target_slot="anchor",
                first_place=True,
            )
            public_facility_demote = float(public_facility_signal.get("public_facility_demote") or 0.0)
            representative_tourism_fit = float(public_facility_signal.get("representative_tourism_fit") or 0.0)
            family_signal = _score_selected_anchor_family(
                row,
                selected_anchor_family,
                landmark_authority_signal,
                default_preset_mode=default_preset_mode,
                target_slot="anchor",
            )
            family_match_score = float(family_signal.get("selected_anchor_family_match_score") or 0.0)
            family_drift_demote = float(family_signal.get("selected_anchor_family_drift_demote") or 0.0)
            busan_oldtown_signal = _score_busan_oldtown_family(
                row,
                selected_anchor_family,
                region=region,
                target_slot="anchor",
            )
            busan_oldtown_family_score = float(busan_oldtown_signal.get("busan_oldtown_family_score") or 0.0)
            busan_oldtown_drift_demote = float(busan_oldtown_signal.get("busan_oldtown_drift_demote") or 0.0)
            busan_oldtown_support_slot_score = float(busan_oldtown_signal.get("busan_oldtown_support_slot_score") or 0.0)
            east_coast_signal = _score_busan_east_coast_family(
                row,
                selected_anchor_family,
                region=region,
                target_slot="anchor",
            )
            east_coast_family_score = float(east_coast_signal.get("busan_east_coast_family_score") or 0.0)
            east_coast_drift_demote = float(east_coast_signal.get("haeundae_gwangan_drift_demote") or 0.0)
            east_coast_support_slot_score = float(east_coast_signal.get("east_coast_support_slot_score") or 0.0)
            seoul_editorial_depth_signal = _score_seoul_editorial_depth(
                row,
                selected_anchor_family,
                landmark_authority_signal,
                region=region,
                target_slot="anchor",
                default_preset_mode=default_preset_mode,
            )
            seoul_broad_default_family_balance = float(seoul_editorial_depth_signal.get("seoul_broad_default_family_balance") or 0.0)
            bukchon_editorial_depth_score = float(seoul_editorial_depth_signal.get("bukchon_editorial_depth_score") or 0.0)
            seongsu_editorial_depth_score = float(seoul_editorial_depth_signal.get("seongsu_editorial_depth_score") or 0.0)
            lifestyle_support_slot_visibility = float(seoul_editorial_depth_signal.get("lifestyle_support_slot_visibility") or 0.0)
            representative_family_rotation_balance = float(seoul_editorial_depth_signal.get("representative_family_rotation_balance") or 0.0)
            seoul_editorial_weak_demote = float(seoul_editorial_depth_signal.get("seoul_editorial_weak_demote") or 0.0)
            anchor_late_context = bool(late_context)
            anchor_night_confidence_signal = _score_night_operating_confidence(
                row,
                flow_profile,
                "anchor",
                late_context=anchor_late_context,
                current_minute=_parse_start_minute(start_time) if anchor_late_context else None,
            )
            anchor_indoor_night_confidence_demote = float(anchor_night_confidence_signal.get("indoor_night_confidence_demote") or 0.0)
            anchor_night_indoor_strong_demote = float(anchor_night_confidence_signal.get("night_indoor_strong_demote") or 0.0)
            anchor_night_safe_outdoor_priority = float(anchor_night_confidence_signal.get("night_safe_outdoor_priority") or 0.0)
            anchor_nightlife_suitability_alignment = float(anchor_night_confidence_signal.get("nightlife_suitability_alignment") or 0.0)
            image_bonus = float(image_signal.get("image_quality_bonus") or 0.0)
            no_image_demote = float(image_signal.get("no_image_first_place_demote") or 0.0)
            indoor_demote = float(indoor_signal.get("indoor_leisure_demote") or 0.0)
            view_score = min((row.get("view_count") or 0) / max(POPULARITY_BASE, 1), 1.0) * 0.06
            score = (
                view_score
                + dom_bonus
                + suit_bonus
                + flow_bonus
                - contamination_demote
                + editorial_bonus
                - editorial_demote
                + seoul_default_representative_score
                - seoul_default_weak_first_place_demote
                + landmark_authority_score
                + external_verified_score
                + external_popularity_score
                + representative_confidence_score
                + family_candidate_lookup_bonus
                - public_data_weakness_penalty
                - wrong_region_alias_demote
                - weak_generic_authority_demote
                + default_preset_landmark_bonus
                - weird_candidate_demote
                - public_facility_demote
                + representative_tourism_fit
                + family_match_score
                - family_drift_demote
                + busan_oldtown_family_score
                + busan_oldtown_support_slot_score
                - busan_oldtown_drift_demote
                + east_coast_family_score
                + east_coast_support_slot_score
                - east_coast_drift_demote
                + seoul_broad_default_family_balance
                + bukchon_editorial_depth_score
                + seongsu_editorial_depth_score
                + lifestyle_support_slot_visibility
                + representative_family_rotation_balance
                - seoul_editorial_weak_demote
                + anchor_night_safe_outdoor_priority
                + anchor_nightlife_suitability_alignment
                - anchor_indoor_night_confidence_demote
                - anchor_night_indoor_strong_demote
                + image_bonus
                - no_image_demote
                - indoor_demote
            )
            detail = {
                "place_id": row.get("place_id"),
                "place_name": row.get("name"),
                "dominant_belt": dominant_signal.get("dominant_belt"),
                "dominant_belt_bonus": round(dom_bonus, 4),
                "dominant_belt_reasons": dominant_signal.get("dominant_belt_reasons") or [],
                "vibe_suitability_score": suitability_signal.get("vibe_suitability_score", 0.0),
                "tourism_suitability_score": suitability_signal.get("tourism_suitability_score", 0.0),
                "suitability_bonus": round(suit_bonus, 4),
                "route_contamination_demote": round(contamination_demote, 4),
                "route_contamination_flags": contamination_signal.get("route_contamination_flags") or [],
                "route_positive_matches": contamination_signal.get("route_positive_matches") or [],
                "religious_facility_demote": contamination_signal.get("religious_facility_demote", 0.0),
                "religious_tourism_exception": contamination_signal.get("religious_tourism_exception") or [],
                "editorial_bonus": round(editorial_bonus, 4),
                "editorial_demote": round(editorial_demote, 4),
                "editorial_demote_reason": editorial_signal.get("editorial_demote_reason"),
                "weak_first_place_reason": editorial_signal.get("weak_first_place_reason"),
                "central_drift_reason": editorial_signal.get("central_drift_reason"),
                "landmark_priority_score": editorial_signal.get("landmark_priority_score", 0.0),
                "representative_vibe_score": editorial_signal.get("representative_vibe_score", 0.0),
                "weak_indoor_demote": editorial_signal.get("weak_indoor_demote", 0.0),
                "landmark_alignment_reason": editorial_signal.get("landmark_alignment_reason"),
                "seongsu_vibe_score": editorial_signal.get("seongsu_vibe_score", 0.0),
                "cafe_street_alignment": editorial_signal.get("cafe_street_alignment", 0.0),
                "weak_meal_demote": editorial_signal.get("weak_meal_demote", 0.0),
                "editorial_first_place_bonus": editorial_signal.get("editorial_first_place_bonus", 0.0),
                "euljiro_night_score": editorial_signal.get("euljiro_night_score", 0.0),
                "hipjiro_alignment": editorial_signal.get("hipjiro_alignment", 0.0),
                "central_drift_demote": editorial_signal.get("central_drift_demote", 0.0),
                "night_vibe_bonus": editorial_signal.get("night_vibe_bonus", 0.0),
                "seoul_date_score": editorial_signal.get("seoul_date_score", 0.0),
                "date_vibe_alignment": editorial_signal.get("date_vibe_alignment", 0.0),
                "broad_seoul_drift_demote": editorial_signal.get("broad_seoul_drift_demote", 0.0),
                "romantic_walk_bonus": editorial_signal.get("romantic_walk_bonus", 0.0),
                "busan_night_meal_score": editorial_signal.get("busan_night_meal_score", 0.0),
                "waterfront_alignment": editorial_signal.get("waterfront_alignment", 0.0),
                "weak_daytime_meal_demote": editorial_signal.get("weak_daytime_meal_demote", 0.0),
                "night_meal_bonus": editorial_signal.get("night_meal_bonus", 0.0),
                "busan_landmark_priority_score": editorial_signal.get("busan_landmark_priority_score", 0.0),
                "busan_representative_bonus": editorial_signal.get("busan_representative_bonus", 0.0),
                "busan_landmark_alignment_reason": editorial_signal.get("busan_landmark_alignment_reason"),
                "representative_tourism_family_score": max(
                    float(editorial_signal.get("representative_tourism_family_score") or 0.0),
                    float(landmark_authority_signal.get("representative_tourism_family_score") or 0.0),
                ),
                "indoor_culture_fallback_demote": max(
                    float(editorial_signal.get("indoor_culture_fallback_demote") or 0.0),
                    float(landmark_authority_signal.get("indoor_culture_fallback_demote") or 0.0),
                ),
                "regional_landmark_density": max(
                    float(editorial_signal.get("regional_landmark_density") or 0.0),
                    float(landmark_authority_signal.get("regional_landmark_density") or 0.0),
                ),
                "first_place_representative_bonus": max(
                    float(editorial_signal.get("first_place_representative_bonus") or 0.0),
                    float(landmark_authority_signal.get("first_place_representative_bonus") or 0.0),
                ),
                "jinju_history_first_place_bonus": editorial_signal.get("jinju_history_first_place_bonus", 0.0),
                "tongyeong_same_city_bonus": editorial_signal.get("tongyeong_same_city_bonus", 0.0),
                "tongyeong_geoje_drift_demote": editorial_signal.get("tongyeong_geoje_drift_demote", 0.0),
                "gimhae_gaya_family_score": editorial_signal.get("gimhae_gaya_family_score", 0.0),
                "gimhae_support_slot_family_score": editorial_signal.get("gimhae_support_slot_family_score", 0.0),
                "gimhae_support_slot_drift_demote": editorial_signal.get("gimhae_support_slot_drift_demote", 0.0),
                "support_slot_coherence_score": editorial_signal.get("support_slot_coherence_score", 0.0),
                "seoul_default_representative_score": editorial_signal.get("seoul_default_representative_score", 0.0),
                "seoul_default_weak_first_place_demote": editorial_signal.get("seoul_default_weak_first_place_demote", 0.0),
                "weak_museum_first_place_demote": editorial_signal.get("weak_museum_first_place_demote", 0.0),
                "landmark_authority_score": round(landmark_authority_score, 4),
                "popularity_signal": landmark_authority_signal.get("popularity_signal", 0.0),
                "popularity_authority_score": landmark_authority_signal.get("popularity_authority_score", 0.0),
                "landmark_confidence": landmark_authority_signal.get("landmark_confidence", 0.0),
                "representative_tourism_bonus": landmark_authority_signal.get("representative_tourism_bonus", 0.0),
                "tourism_representative_score": landmark_authority_signal.get("tourism_representative_score", 0.0),
                "normalized_popularity_hint": landmark_authority_signal.get("normalized_popularity_hint", 0.0),
                "external_verified_score": landmark_authority_signal.get("external_verified_score", 0.0),
                "external_popularity_score": landmark_authority_signal.get("external_popularity_score", 0.0),
                "public_data_weakness_penalty": landmark_authority_signal.get("public_data_weakness_penalty", 0.0),
                "public_data_weakness_reason": landmark_authority_signal.get("public_data_weakness_reason"),
                "representative_confidence_score": landmark_authority_signal.get("representative_confidence_score", 0.0),
                "image_density_score": landmark_authority_signal.get("image_density_score", 0.0),
                "review_density_hint": landmark_authority_signal.get("review_density_hint", 0.0),
                "landmark_authority_matches": landmark_authority_signal.get("landmark_authority_matches") or [],
                "landmark_authority_reason": landmark_authority_signal.get("landmark_authority_reason"),
                "alias_normalization_match": landmark_authority_signal.get("alias_normalization_match") or [],
                "region_aware_alias_guard": landmark_authority_signal.get("region_aware_alias_guard"),
                "wrong_region_alias_demote": round(wrong_region_alias_demote, 4),
                "family_candidate_lookup_bonus": round(family_candidate_lookup_bonus, 4),
                "representative_alias_pool_included": bool(landmark_authority_signal.get("representative_alias_pool_included")),
                "weak_generic_authority_demote": round(weak_generic_authority_demote, 4),
                "weak_generic_authority_reason": landmark_authority_signal.get("weak_generic_authority_reason"),
                "default_preset_mode": bool(default_preset_signal.get("default_preset_mode")),
                "representative_landmark_selected": bool(default_preset_signal.get("representative_landmark_selected")),
                "default_preset_landmark_bonus": round(default_preset_landmark_bonus, 4),
                "weird_candidate_demote": round(weird_candidate_demote, 4),
                "weird_candidate_demote_reason": default_preset_signal.get("weird_candidate_demote_reason"),
                "public_facility_demote": round(public_facility_demote, 4),
                "representative_tourism_fit": round(representative_tourism_fit, 4),
                "weak_public_facility_reason": public_facility_signal.get("weak_public_facility_reason"),
                "selected_anchor_family_id": family_signal.get("selected_anchor_family_id"),
                "selected_anchor_family_match_score": round(family_match_score, 4),
                "selected_anchor_family_preserved": bool(family_signal.get("selected_anchor_family_preserved")),
                "selected_anchor_family_matched_terms": family_signal.get("selected_anchor_family_matched_terms") or [],
                "selected_anchor_family_drift_demote": round(family_drift_demote, 4),
                "selected_anchor_drift_reason": family_signal.get("selected_anchor_drift_reason"),
                "fallback_level_used": family_signal.get("fallback_level_used"),
                "busan_oldtown_family_score": round(busan_oldtown_family_score, 4),
                "busan_oldtown_pool_included": bool(busan_oldtown_signal.get("busan_oldtown_pool_included")),
                "busan_oldtown_drift_demote": round(busan_oldtown_drift_demote, 4),
                "busan_oldtown_support_slot_score": round(busan_oldtown_support_slot_score, 4),
                "busan_oldtown_expected_landmark_visible": bool(busan_oldtown_signal.get("busan_oldtown_expected_landmark_visible")),
                "busan_oldtown_match_terms": busan_oldtown_signal.get("busan_oldtown_match_terms") or [],
                "busan_east_coast_family_score": round(east_coast_family_score, 4),
                "east_coast_family_preserved": bool(east_coast_signal.get("east_coast_family_preserved")),
                "haeundae_gwangan_drift_demote": round(east_coast_drift_demote, 4),
                "east_coast_support_slot_score": round(east_coast_support_slot_score, 4),
                "east_coast_expected_landmark_visible": bool(east_coast_signal.get("east_coast_expected_landmark_visible")),
                "east_coast_match_terms": east_coast_signal.get("east_coast_match_terms") or [],
                "seoul_broad_default_family_balance": round(seoul_broad_default_family_balance, 4),
                "bukchon_editorial_depth_score": round(bukchon_editorial_depth_score, 4),
                "seongsu_editorial_depth_score": round(seongsu_editorial_depth_score, 4),
                "lifestyle_support_slot_visibility": round(lifestyle_support_slot_visibility, 4),
                "representative_family_rotation_balance": round(representative_family_rotation_balance, 4),
                "seoul_broad_family_key": seoul_editorial_depth_signal.get("seoul_broad_family_key"),
                "seoul_broad_family_matches": seoul_editorial_depth_signal.get("seoul_broad_family_matches") or [],
                "bukchon_editorial_depth_matches": seoul_editorial_depth_signal.get("bukchon_editorial_depth_matches") or [],
                "seongsu_editorial_depth_matches": seoul_editorial_depth_signal.get("seongsu_editorial_depth_matches") or [],
                "seoul_editorial_weak_demote": round(seoul_editorial_weak_demote, 4),
                "seoul_editorial_depth_pool_included": bool(seoul_editorial_depth_signal.get("seoul_editorial_depth_pool_included")),
                "operating_hours_known_closed": bool(anchor_night_confidence_signal.get("operating_hours_known_closed")),
                "night_indoor_strong_demote": round(anchor_night_indoor_strong_demote, 4),
                "relaxed_unknown_hours_allowed": bool(anchor_night_confidence_signal.get("relaxed_unknown_hours_allowed")),
                "known_closed_removed": bool(anchor_night_confidence_signal.get("known_closed_removed")),
                "night_safe_indoor_exception": bool(anchor_night_confidence_signal.get("night_safe_indoor_exception")),
                "night_operating_confidence_reason": anchor_night_confidence_signal.get("night_operating_confidence_reason"),
                "indoor_semantic_detected": bool(anchor_night_confidence_signal.get("indoor_semantic_detected")),
                "known_closed_indoor_removed": bool(anchor_night_confidence_signal.get("known_closed_indoor_removed")),
                "night_indoor_semantic_demote": float(anchor_night_confidence_signal.get("night_indoor_semantic_demote") or 0.0),
                "indoor_closing_time_applied": bool(anchor_night_confidence_signal.get("indoor_closing_time_applied")),
                "image_available": bool(image_signal.get("image_available")),
                "image_quality_bonus": round(image_bonus, 4),
                "no_image_first_place_demote": round(no_image_demote, 4),
                "placeholder_used": not bool(image_signal.get("image_available")),
                "indoor_leisure_demote": round(indoor_demote, 4),
                "indoor_leisure_reason": indoor_signal.get("indoor_leisure_reason"),
                "flow_alignment": flow_signal.get("slot_flow_alignment", 0.0),
                "first_anchor_score": round(score, 4),
            }
            scored_anchor_rows.append((score, row, detail))
        scored_anchor_rows.sort(key=lambda item: item[0], reverse=True)
        if late_context:
            anchor_start_min = _parse_start_minute(start_time)
            non_closed_anchor_rows = [
                item for item in scored_anchor_rows
                if not item[2].get("operating_hours_known_closed")
                and not (
                    anchor_start_min is not None
                    and (lambda close: close is not None and anchor_start_min >= close)(
                        _extract_known_close_min(item[1])[0]
                    )
                )
            ]
            if non_closed_anchor_rows:
                scored_anchor_rows = non_closed_anchor_rows
        if scored_anchor_rows:
            seoul_broad_default_anchor = (
                str(region or "") == "서울"
                and bool(default_preset_mode)
                and not selected_anchor
                and not selected_anchor_tokens
            )
            chosen_row, chosen_detail = _choose_diverse_first_place(
                scored_anchor_rows,
                top_k=8 if seoul_broad_default_anchor else 5,
                score_window=0.32 if seoul_broad_default_anchor else 0.18,
                saturation_gap=0.035 if seoul_broad_default_anchor else 0.055,
                max_saturation_penalty=0.14 if seoul_broad_default_anchor else 0.075,
                rotation_bonus=0.038 if seoul_broad_default_anchor else 0.018,
            )
            chosen_row["_first_anchor_candidate_scores"] = [item[2] for item in scored_anchor_rows[:8]]
            chosen_row["_first_anchor_belt_match"] = {
                "dominant_belt": chosen_detail.get("dominant_belt"),
                "dominant_belt_bonus": chosen_detail.get("dominant_belt_bonus"),
                "dominant_belt_reasons": chosen_detail.get("dominant_belt_reasons") or [],
            }
            chosen_row["_first_anchor_contamination"] = {
                "route_contamination_demote": chosen_detail.get("route_contamination_demote"),
                "route_contamination_flags": chosen_detail.get("route_contamination_flags") or [],
            }
            chosen_row["_first_anchor_replacement_attempted"] = False
            return chosen_row

    # Req 5: belt_seed 앵커 우선 선택 — belt_boost 가중 랜덤 (Top-5 풀)
    if region in REGION_TO_BELT_KEYS and not (selected_anchor_tokens or zone_center):
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

        description_meta = _build_place_description_meta(place)
        description = description_meta["description"]
        image_meta = _apply_haedong_yonggungsa_curated_image(place)

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
            "first_image_url":        image_meta.get("first_image_url"),
            "image_available":        image_meta.get("image_available"),
            "placeholder_used":       image_meta.get("placeholder_used"),
            "curated_image_used":     image_meta.get("curated_image_used"),
            "curated_image_source":   image_meta.get("curated_image_source"),
            "curated_image_reason":   image_meta.get("curated_image_reason"),
            "description":            description,
            "description_quality_variant": description_meta.get("description_quality_variant"),
            "generic_copy_demote":     description_meta.get("generic_copy_demote", 0.0),
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

def _summarize_description_quality(places: list[dict]) -> dict:
    variants = Counter(str(place.get("description_quality_variant") or "unknown") for place in (places or []))
    generic_count = sum(1 for place in (places or []) if float(place.get("generic_copy_demote") or 0.0) > 0)
    primary_variant = variants.most_common(1)[0][0] if variants else None
    return {
        "description_quality_variant": primary_variant,
        "description_quality_variants": dict(variants),
        "generic_copy_demote": int(generic_count),
    }


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
    region_original    = request["region"]
    region             = request.get("query_region_1") or region_original

    # 서비스 레벨 분기: BLOCKED 지역은 코스 생성 없이 즉시 반환
    if get_service_level(region) == "BLOCKED":
        logger.info("build_course skipped — region=%s is BLOCKED", region)
        return {"error": get_blocked_message(), "places": []}

    companion          = request.get("companion", "")
    themes             = request.get("themes", [])
    default_preset_mode = _is_default_preset_mode(request, themes)
    intended_city      = request.get("intended_city") or request.get("region")
    query_region_1     = request.get("query_region_1") or region_original
    identity_region_1  = request.get("identity_region_1") or query_region_1
    selected_anchor    = request.get("selected_anchor")
    selected_anchor_token_set = _selected_anchor_tokens(selected_anchor)
    selected_anchor_family = _resolve_selected_anchor_family(selected_anchor)
    selected_anchor_family_tokens = set(selected_anchor_family.get("normalized_tokens") or [])
    if selected_anchor_family_tokens:
        selected_anchor_token_set.update(selected_anchor_family_tokens)
    selected_anchor_debug = _normalize_selected_anchor_for_debug(selected_anchor)
    if selected_anchor and selected_anchor_family.get("family_id"):
        selected_anchor_debug["selected_anchor_family_id"] = selected_anchor_family.get("family_id")
        selected_anchor_debug["selected_anchor_family_tokens"] = sorted(selected_anchor_family_tokens)
        selected_anchor_debug["selected_anchor_family_matched_anchor_key"] = selected_anchor_family.get("matched_anchor_key")
    region_identity_debug = infer_region_belt(
        identity_region_1,
        selected_anchor=selected_anchor,
        text_terms=[
            intended_city,
            request.get("display_region"),
            request.get("zone_id"),
            " ".join(str(t) for t in (request.get("themes") or []) if t),
        ],
    )
    if isinstance(region_identity_debug, dict):
        region_identity_debug = {
            **region_identity_debug,
            "region": region_identity_debug.get("region") or identity_region_1,
            "query_region_1": query_region_1,
            "display_region": request.get("display_region") or region_original,
        }
    seoul_district_vibe_debug: dict = {}
    if not selected_anchor and isinstance(region_identity_debug, dict):
        seoul_district_vibe_debug = infer_seoul_district_vibe(
            region_identity_debug,
            themes=themes,
            movement_option=request.get("movement_option") or request.get("walk") or request.get("density"),
            companion=companion,
            source_terms=[
                intended_city,
                request.get("display_region"),
                request.get("zone_id"),
                request.get("theme"),
                " ".join(str(t) for t in (request.get("themes") or []) if t),
            ],
        )
        district_identity = seoul_district_vibe_debug.get("dominant_district_identity")
        dominant_district_token = _normalize_city_token(seoul_district_vibe_debug.get("dominant_district"))
        skip_seoul_broad_seongsu_override = (
            bool(default_preset_mode)
            and _normalize_city_token(identity_region_1) == _normalize_city_token("서울")
            and dominant_district_token == _normalize_city_token("성수")
        )
        if district_identity and not skip_seoul_broad_seongsu_override:
            region_identity_debug = {
                **region_identity_debug,
                **district_identity,
                "seoul_district_vibe_orchestration": {
                    "dominant_district": seoul_district_vibe_debug.get("dominant_district"),
                    "district_vibe_reason": seoul_district_vibe_debug.get("district_vibe_reason") or {},
                    "hard_lock": False,
                },
                "district_candidate_scores": seoul_district_vibe_debug.get("district_candidate_scores") or [],
                "inference_reason": "seoul_district_vibe_soft_selection",
            }
        elif skip_seoul_broad_seongsu_override:
            seoul_district_vibe_debug = {
                **seoul_district_vibe_debug,
                "district_vibe_reason": {
                    **(seoul_district_vibe_debug.get("district_vibe_reason") or {}),
                    "skipped_dominant_district": "성수",
                    "skip_reason": "broad_default_seongsu_radius_fallback_guard",
                    "hard_lock": False,
                },
            }
    broad_seoul_default_guard = (
        not selected_anchor
        and bool(default_preset_mode)
        and _normalize_city_token(identity_region_1) == _normalize_city_token("서울")
        and isinstance(region_identity_debug, dict)
    )
    force_broad_seoul_recovery = bool(request.get("force_broad_seoul_default_recovery"))
    broad_default_guard_belts = {"성수"} if not force_broad_seoul_recovery else {"성수", "북촌", "광화문", "을지로", "익선", "한남"}
    if (
        broad_seoul_default_guard
        and _normalize_city_token(region_identity_debug.get("inferred_belt")) in {
            _normalize_city_token(belt) for belt in broad_default_guard_belts
        }
    ):
        original_inferred_belt = region_identity_debug.get("inferred_belt")
        region_identity_debug = {
            **region_identity_debug,
            "region": identity_region_1,
            "query_region_1": query_region_1,
            "display_region": request.get("display_region") or region_original,
            "inferred_belt": "서울",
            "belt_confidence": 0.0,
            "belt_anchor_match": None,
            "matched_aliases": [],
            "tourism_keywords": ["서울", "광화문", "북촌", "한강", "을지로", "성수", "명동"],
            "representative_categories": ["spot", "culture", "walk", "cafe"],
            "mobility_traits": ["walking", "culture", "city"],
            "anchor": None,
            "broad_default_fallback_guard": True,
            "fallback_exhaustion_detected": bool(force_broad_seoul_recovery),
            "broad_family_recovery_applied": bool(force_broad_seoul_recovery),
            "nocourse_guard_applied": True,
            "original_inferred_belt_before_broad_guard": original_inferred_belt,
            "seoul_district_vibe_orchestration": {
                "dominant_district": original_inferred_belt,
                "skip_reason": "broad_default_radius_fallback_guard",
                "hard_lock": False,
            },
        }
    if selected_anchor and isinstance(region_identity_debug, dict):
        identity_anchor = region_identity_debug.get("anchor") or {}
        identity_terms = [
            region_identity_debug.get("inferred_belt"),
            region_identity_debug.get("belt_anchor_match"),
            *(region_identity_debug.get("matched_aliases") or []),
            *(region_identity_debug.get("tourism_keywords") or []),
            identity_anchor.get("name") if isinstance(identity_anchor, dict) else None,
        ]
        normalized_identity_terms = {
            _normalize_city_token(term)
            for term in identity_terms
            if _normalize_city_token(term)
        }
        if selected_anchor_family_tokens:
            preserved_identity_terms = normalized_identity_terms & selected_anchor_family_tokens
            selected_anchor_token_set.update(preserved_identity_terms)
            region_identity_debug = {
                **region_identity_debug,
                "inferred_belt": selected_anchor_family.get("family_id") or region_identity_debug.get("inferred_belt"),
                "belt_anchor_match": selected_anchor,
                "matched_aliases": list(selected_anchor_family.get("tokens") or []),
                "tourism_keywords": list(selected_anchor_family.get("tokens") or []),
                "selected_anchor_family_id": selected_anchor_family.get("family_id"),
                "selected_anchor_family_preservation": True,
                "selected_anchor_family_terms": sorted(selected_anchor_family_tokens),
                "selected_anchor_identity_terms_suppressed": sorted(normalized_identity_terms - preserved_identity_terms),
                "inference_reason": "selected_anchor_family_preservation",
            }
        else:
            selected_anchor_token_set.update(normalized_identity_terms)
        selected_anchor_debug["normalized_anchor_aliases"] = sorted(
            set(selected_anchor_debug.get("normalized_anchor_aliases") or []) | selected_anchor_token_set
        )
    flow_profile_debug = infer_course_flow_profile(
        region_identity_debug,
        themes=themes,
        movement_option=request.get("movement_option") or request.get("walk") or request.get("density"),
        companion=companion,
        source_terms=[
            selected_anchor,
            intended_city,
            request.get("display_region"),
            request.get("zone_id"),
        ],
    )
    request_id         = request.get("request_id")
    trace_top_candidate_city_distribution: dict[str, int] = {}
    trace_candidate_samples: list[dict] = []
    trace_rejected_candidates_count = 0
    trace_wrong_city_demote_count = 0
    trace_locality_bonus_count = 0
    trace_belt_match_count = 0
    trace_wrong_belt_match_count = 0
    trace_continuity_bonus_count = 0
    trace_flow_break_count = 0
    trace_suitability_bonus_count = 0
    trace_suitability_soft_demote_count = 0
    trace_meal_cafe_bonus_count = 0
    trace_meal_cafe_soft_demote_count = 0
    trace_route_contamination_count = 0
    trace_cross_flow_candidate_count = 0
    trace_lifestyle_mismatch_count = 0
    trace_night_operating_confidence_count = 0
    trace_indoor_night_confidence_demote_count = 0
    trace_night_safe_outdoor_priority_count = 0
    trace_nightlife_suitability_alignment_count = 0
    trace_indoor_heavy_route_detected_count = 0
    trace_operating_hours_known_closed_count = 0
    trace_night_indoor_strong_demote_count = 0
    trace_relaxed_unknown_hours_allowed_count = 0
    trace_known_closed_removed_count = 0
    trace_night_safe_indoor_exception_count = 0
    trace_indoor_semantic_detected_count = 0
    trace_known_closed_indoor_removed_count = 0
    trace_night_indoor_semantic_demote_count = 0
    trace_indoor_closing_time_applied_count = 0
    trace_curated_night_family_applied_count = 0
    trace_night_representative_preference_count = 0
    trace_nightlife_curated_alignment_count = 0
    trace_night_vibe_coherence_count = 0
    trace_curated_night_support_slot_count = 0
    trace_curated_representative_priority_count = 0
    trace_verified_api_candidate_count = 0
    trace_public_fallback_used_count = 0
    trace_weak_public_contamination_demote_count = 0
    trace_curated_support_slot_alignment_count = 0
    trace_seoul_curated_district_priority_count = 0
    trace_broad_seoul_demoted_count = 0
    trace_district_identity_alignment_count = 0
    trace_support_slot_role_diversity_count = 0
    trace_unsuitable_block_counts = {"hard_unsuitable": 0, "representative_limited": 0}
    trace_replacement_events: list[dict] = []

    def _maybe_replace_contaminated_choice(
        chosen_item: tuple,
        scored_items: list[tuple],
        *,
        slot_name: str,
    ) -> tuple:
        """Try one bounded same-belt replacement for a high-contamination pick.

        This does not rebuild the route and does not enforce a hard belt lock.
        It only swaps within the already-scored same-slot candidate pool when a
        cleaner candidate keeps enough score and better route coherence signals.
        """
        chosen_score, chosen_travel, chosen_dist, chosen_components, chosen_place = chosen_item
        chosen_flags = set(chosen_components.get("route_contamination_flags") or [])
        chosen_demote = float(chosen_components.get("route_contamination_demote") or 0.0)
        chosen_editorial_demote = float(chosen_components.get("editorial_demote") or 0.0)
        high_contamination = (
            chosen_demote >= 0.08
            or chosen_editorial_demote >= 0.06
            or bool({"kid_family_mismatch", "flow_contamination", "lifestyle_contamination", "belt_contamination"} & chosen_flags)
        )
        if not high_contamination:
            return chosen_item

        chosen_score_float = float(chosen_score or 0.0)
        best_item = None
        best_reason = None
        for item in scored_items:
            alt_score, alt_travel, alt_dist, alt_components, alt_place = item
            if alt_place.get("place_id") == chosen_place.get("place_id"):
                continue
            alt_flags = set(alt_components.get("route_contamination_flags") or [])
            alt_demote = float(alt_components.get("route_contamination_demote") or 0.0)
            alt_editorial_demote = float(alt_components.get("editorial_demote") or 0.0)
            if alt_demote + alt_editorial_demote >= chosen_demote + chosen_editorial_demote:
                continue
            if len(alt_flags) >= len(chosen_flags) and alt_demote > 0:
                continue
            if "belt_contamination" in alt_flags and "belt_contamination" in chosen_flags:
                continue
            if float(alt_score or 0.0) < chosen_score_float - 0.18:
                continue
            has_belt_affinity = (
                float(alt_components.get("belt_match_bonus") or 0.0) > 0
                or float(alt_components.get("dominant_belt_bonus") or 0.0) > 0
                or bool(alt_components.get("dominant_belt_reasons") or [])
            )
            if not has_belt_affinity and chosen_components.get("dominant_belt"):
                continue
            best_item = item
            best_reason = "lower_route_contamination_same_slot"
            break

        if not best_item:
            trace_replacement_events.append({
                "slot": slot_name,
                "replacement_attempted": True,
                "replacement_success": False,
                "replacement_reason": "no_safe_same_slot_candidate",
                "replaced_place": chosen_place.get("name"),
                "replacement_place": None,
                "route_coherence_delta": 0.0,
            })
            return chosen_item

        alt_score, alt_travel, alt_dist, alt_components, alt_place = best_item
        chosen_coherence = 1.0 - min(0.5, chosen_demote + chosen_editorial_demote)
        alt_coherence = 1.0 - min(
            0.5,
            float(alt_components.get("route_contamination_demote") or 0.0)
            + float(alt_components.get("editorial_demote") or 0.0),
        )
        alt_components = {
            **alt_components,
            "replacement_applied": True,
            "replacement_reason": best_reason,
            "replaced_place": chosen_place.get("name"),
            "route_coherence_delta": round(alt_coherence - chosen_coherence, 4),
        }
        trace_replacement_events.append({
            "slot": slot_name,
            "replacement_attempted": True,
            "replacement_success": True,
            "replacement_reason": best_reason,
            "replaced_place": chosen_place.get("name"),
            "replacement_place": alt_place.get("name"),
            "route_coherence_delta": round(alt_coherence - chosen_coherence, 4),
        })
        return alt_score, alt_travel, alt_dist, alt_components, alt_place

    def _maybe_replace_with_exact_support_landmark(
        chosen_item: tuple,
        scored_items: list[tuple],
        *,
        slot_name: str,
    ) -> tuple:
        """Prefer one visible Busan oldtown exact landmark within the same slot.

        This is a bounded support-slot pass. It only chooses from the already
        scored same-slot pool, keeps travel constraints from scoring, and does
        not force route insertion when the exact candidate is too weak.
        """
        family_id = str((selected_anchor_family or {}).get("family_id") or "")
        if family_id not in _BUSAN_OLDTOWN_FAMILY_IDS:
            return chosen_item

        chosen_score, chosen_travel, chosen_dist, chosen_components, chosen_place = chosen_item
        if bool(chosen_components.get("exact_landmark_pool_included")):
            chosen_components = {
                **chosen_components,
                "exact_landmark_final_route_visible": True,
            }
            return chosen_score, chosen_travel, chosen_dist, chosen_components, chosen_place

        chosen_score_float = float(chosen_score or 0.0)
        chosen_weak = float(chosen_components.get("weak_substitute_demote") or 0.0)
        chosen_oldtown = bool(chosen_components.get("busan_oldtown_pool_included"))
        anchor_key = str((selected_anchor_family or {}).get("matched_anchor_key") or "")
        focus_required = anchor_key in {"감천문화마을", "송도해상케이블카"}
        best_item = None
        best_rank = None
        for item in scored_items:
            alt_score, alt_travel, alt_dist, alt_components, alt_place = item
            if alt_place.get("place_id") == chosen_place.get("place_id"):
                continue
            if not bool(alt_components.get("exact_landmark_pool_included")):
                continue
            focus_match = bool(alt_components.get("exact_landmark_focus_match_terms") or [])
            if focus_required and not focus_match:
                continue
            if float(alt_components.get("busan_oldtown_drift_demote") or 0.0) > 0:
                continue
            if float(alt_components.get("wrong_city_demote") or 0.0) > 0:
                continue
            alt_score_float = float(alt_score or 0.0)
            score_floor = 0.8 if focus_required and focus_match else (0.52 if focus_match else 0.36)
            if alt_score_float < chosen_score_float - score_floor:
                continue
            alt_visibility = (
                float(alt_components.get("exact_landmark_visibility_score") or 0.0)
                + float(alt_components.get("exact_landmark_support_slot_bonus") or 0.0)
                + (0.12 if focus_match else 0.0)
            )
            rank = (
                1 if focus_match else 0,
                alt_visibility,
                alt_score_float,
                -float(alt_travel or 0.0),
            )
            if best_rank is None or rank > best_rank:
                best_item = item
                best_rank = rank

        if not best_item:
            return chosen_item

        alt_score, alt_travel, alt_dist, alt_components, alt_place = best_item
        replacement_reason = "exact_landmark_support_slot_visibility"
        if chosen_oldtown and chosen_weak <= 0:
            replacement_reason = "exact_landmark_balance_within_oldtown_family"
        alt_components = {
            **alt_components,
            "exact_support_slot_replacement_applied": True,
            "exact_support_slot_visibility_bonus": alt_components.get("exact_landmark_support_slot_bonus", 0.0),
            "exact_landmark_final_route_visible": True,
            "oldtown_candidate_replaced": chosen_place.get("name"),
            "support_slot_visibility_reason": replacement_reason,
            "replacement_applied": True,
            "replacement_reason": replacement_reason,
            "replaced_place": chosen_place.get("name"),
        }
        trace_replacement_events.append({
            "slot": slot_name,
            "replacement_attempted": True,
            "replacement_success": True,
            "replacement_reason": replacement_reason,
            "replaced_place": chosen_place.get("name"),
            "replacement_place": alt_place.get("name"),
            "exact_support_slot_replacement_applied": True,
            "oldtown_candidate_replaced": chosen_place.get("name"),
            "support_slot_visibility_reason": replacement_reason,
            "route_coherence_delta": 0.0,
        })
        return alt_score, alt_travel, alt_dist, alt_components, alt_place

    def _maybe_replace_with_support_slot_family_candidate(
        chosen_item: tuple,
        scored_items: list[tuple],
        *,
        slot_name: str,
    ) -> tuple:
        """Bounded support-slot replacement for Gangnam/Jinju residual coherence.

        The pass only considers already-scored candidates in the same slot. It
        does not change the first place, does not rebuild the route, and keeps
        the family preservation boundary intact.
        """
        family_id = str((selected_anchor_family or {}).get("family_id") or "")
        anchor_text = _normalize_city_token(str(selected_anchor or ""))
        is_gangnam = region == "서울" and (
            family_id == "seoul_gangnam"
            or any(token in anchor_text for token in ("강남", "신논현", "코엑스", "봉은사", "가로수길", "압구정", "청담"))
        )
        is_jinju = region == "경남" and (
            family_id == "gyeongnam_jinju_history"
            or any(token in anchor_text for token in ("진주", "촉석루", "남강", "진주성"))
        )
        is_seongsu = region == "서울" and (
            family_id == "seoul_seongsu_cafe"
            or any(token in anchor_text for token in ("성수", "서울숲", "연무장", "카페"))
        )
        is_gijang = region == "부산" and (
            family_id == "busan_gijang_east_coast"
            or any(token in anchor_text for token in ("기장", "해동용궁사", "용궁사", "송정", "오시리아"))
        )
        is_euljiro = region == "서울" and (
            family_id == "seoul_euljiro_night"
            or any(token in anchor_text for token in ("을지로", "힙지로", "청계천", "노가리", "야간"))
        )
        is_gwangan_night = region == "부산" and (
            family_id in {"busan_gwangan", "busan_gwangan_night"}
            or any(token in anchor_text for token in ("광안리", "광안대교", "민락", "야경"))
        )
        if not is_gangnam and not is_jinju and not is_seongsu and not is_gijang and not is_euljiro and not is_gwangan_night:
            return chosen_item

        chosen_score, chosen_travel, chosen_dist, chosen_components, chosen_place = chosen_item
        chosen_support_score = float(chosen_components.get("support_slot_family_assembly_score") or 0.0)
        chosen_alignment = float(chosen_components.get("representative_support_slot_alignment") or 0.0)
        chosen_weak = float(chosen_components.get("weak_support_slot_demote") or 0.0)
        chosen_route_demote = float(chosen_components.get("route_contamination_demote") or 0.0)
        chosen_editorial_demote = float(chosen_components.get("editorial_demote") or 0.0)
        chosen_flags = set(chosen_components.get("route_contamination_flags") or [])
        chosen_good_enough = (
            chosen_support_score >= 0.08
            and chosen_weak <= 0.02
            and chosen_route_demote + chosen_editorial_demote <= 0.06
        )
        if chosen_good_enough:
            return chosen_item

        best_item = None
        best_rank = None
        chosen_score_float = float(chosen_score or 0.0)
        for item in scored_items:
            alt_score, alt_travel, alt_dist, alt_components, alt_place = item
            if alt_place.get("place_id") == chosen_place.get("place_id"):
                continue
            alt_support_score = float(alt_components.get("support_slot_family_assembly_score") or 0.0)
            alt_alignment = float(alt_components.get("representative_support_slot_alignment") or 0.0)
            alt_weak = float(alt_components.get("weak_support_slot_demote") or 0.0)
            if alt_support_score <= 0 and alt_alignment <= 0:
                continue
            if is_jinju and not (alt_components.get("support_slot_family_match_terms") or []):
                continue
            if (is_seongsu or is_gijang or is_gwangan_night) and not (
                alt_components.get("support_slot_family_match_terms") or []
                or float(alt_components.get("representative_support_purity_score") or 0.0) > 0
            ):
                continue
            if is_euljiro and not (
                alt_components.get("nightlife_core_match_terms") or []
                or float(alt_components.get("nightlife_support_slot_alignment") or 0.0) > 0
            ):
                continue
            if alt_weak >= max(0.12, chosen_weak) and chosen_weak > 0:
                continue
            if float(alt_components.get("wrong_city_demote") or 0.0) > 0:
                continue
            if is_jinju and alt_components.get("wrong_belt_match"):
                continue
            alt_flags = set(alt_components.get("route_contamination_flags") or [])
            alt_route_demote = float(alt_components.get("route_contamination_demote") or 0.0)
            alt_editorial_demote = float(alt_components.get("editorial_demote") or 0.0)
            if len(alt_flags) > len(chosen_flags) and chosen_flags:
                continue
            if alt_route_demote + alt_editorial_demote > chosen_route_demote + chosen_editorial_demote + 0.04:
                continue
            score_floor = 0.42 if is_gangnam else 0.62
            if float(alt_score or 0.0) < chosen_score_float - score_floor:
                continue
            rank = (
                alt_alignment,
                alt_support_score,
                -alt_weak,
                -(alt_route_demote + alt_editorial_demote),
                float(alt_score or 0.0),
            )
            if best_rank is None or rank > best_rank:
                best_item = item
                best_rank = rank

        if not best_item:
            if chosen_weak > 0 or chosen_route_demote > 0:
                trace_replacement_events.append({
                    "slot": slot_name,
                    "replacement_attempted": True,
                    "replacement_success": False,
                    "replacement_reason": "no_safe_support_slot_family_candidate",
                    "replaced_place": chosen_place.get("name"),
                    "replacement_place": None,
                    "support_slot_family_assembly": True,
                    "route_coherence_delta": 0.0,
                })
            return chosen_item

        alt_score, alt_travel, alt_dist, alt_components, alt_place = best_item
        alt_components = {
            **alt_components,
            "support_slot_family_replacement_applied": True,
            "bounded_support_slot_cleanup": True,
            "bounded_purity_replacement": True,
            "support_slot_cleanup_applied": True,
            "residual_cleanup_applied": True,
            "support_slot_minimal_cleanup": True,
            "runtime_stability_guard": True,
            "nightlife_replacement_applied": bool(is_euljiro),
            "replacement_applied": True,
            "replacement_reason": "support_slot_family_assembly",
            "replaced_place": chosen_place.get("name"),
        }
        trace_replacement_events.append({
            "slot": slot_name,
            "replacement_attempted": True,
            "replacement_success": True,
            "replacement_reason": "support_slot_family_assembly",
            "replaced_place": chosen_place.get("name"),
            "replacement_place": alt_place.get("name"),
            "support_slot_family_assembly": True,
            "nightlife_replacement_applied": bool(is_euljiro),
            "route_coherence_delta": 0.0,
        })
        return alt_score, alt_travel, alt_dist, alt_components, alt_place
    template           = request.get("template", "standard")
    start_time         = request.get("start_time") or request.get("departure_time")
    region_travel_type = request.get("region_travel_type", "urban")
    zone_center        = request.get("zone_center")      # (lat, lon) tuple or None
    zone_radius_km     = request.get("zone_radius_km")   # float or None
    walk_max_radius    = request.get("walk_max_radius")  # float or None (urban 거리 부담)
    city_type          = _get_city_type(region)
    is_city_mode       = region in CITY_MODE_REGIONS
    city_cluster: dict | None = None

    if selected_anchor:
        logger.info(
            "selected_anchor normalized -- region=%s intended_city=%s selected_anchor=%s normalized_city=%s normalized_anchor=%s normalized_anchor_aliases=%s",
            region,
            intended_city,
            selected_anchor,
            selected_anchor_debug.get("normalized_city_token"),
            selected_anchor_debug.get("normalized_anchor_token"),
            selected_anchor_debug.get("normalized_anchor_aliases"),
        )

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
        if _sh is None or _sh < 18:
            if "cafe" in themes:
                _slot_map = CITY_MODE_CAFE_SLOTS
            elif "food" in themes:
                _slot_map = CITY_MODE_FOOD_SLOTS
            else:
                _slot_map = CITY_MODE_SLOTS
            slots = list(_slot_map.get(template, _slot_map["standard"]))

    start_hour = _parse_start_hour(start_time)
    start_min_override = start_hour * 60 if start_hour is not None else None
    time_bucket = "evening" if start_hour is not None and 18 <= start_hour < 20 else (
        "late_night" if start_hour is not None and start_hour >= 20 else "daytime"
    )
    late_scoring_context = bool(
        request.get("late_user_selected_mode")
        or request.get("night_late_safe_relaxed_mode")
        or request.get("night_friendly_mode")
        or _is_late_user_selected_request(request, start_time)
    )
    late_scoring_minute = _parse_start_minute(start_time) if late_scoring_context else None

    pop = _pop_base(conn, region)
    weights = _get_weights(themes)  # theme 활성화 시 theme_match 0.50 적용
    if is_city_mode:
        _theme_active = any(t in themes for t in _THEME_ROLE_BIAS)
        weights = CITY_MODE_CAFE_WEIGHTS if _theme_active else CITY_MODE_WEIGHTS

    # Step 1. 앵커 선택 (첫 슬롯 role 기준)
    anchor = _select_anchor(
        conn, region, themes, first_role=slots[0][1],
        zone_center=zone_center, zone_radius_km=zone_radius_km,
        selected_anchor=selected_anchor_token_set or selected_anchor,
        region_identity=region_identity_debug,
        flow_profile=flow_profile_debug,
        default_preset_mode=default_preset_mode,
        selected_anchor_family=selected_anchor_family,
        late_context=late_scoring_context,
        start_time=start_time,
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
            selected_anchor=selected_anchor_token_set or selected_anchor,
            region_identity=region_identity_debug,
            flow_profile=flow_profile_debug,
            default_preset_mode=default_preset_mode,
            selected_anchor_family=selected_anchor_family,
            late_context=late_scoring_context,
            start_time=start_time,
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
    _anchor_belt_signal = score_belt_match(anchor, region_identity_debug)
    _anchor_dominant_belt_signal = score_dominant_belt_affinity(anchor, region_identity_debug)
    _anchor_flow_signal = score_flow_continuity(anchor, None, flow_profile_debug)
    _anchor_suitability_signal = score_vibe_tourism_suitability(
        anchor,
        flow_profile_debug,
        target_slot=slots[0][0],
    )
    _anchor_meal_cafe_signal = score_meal_cafe_suitability(
        anchor,
        flow_profile_debug,
        target_slot=slots[0][0],
    )
    _anchor_route_contamination_signal = score_route_contamination(
        anchor,
        region_identity_debug,
        flow_profile_debug,
        target_slot=slots[0][0],
    )
    _anchor_editorial_signal = score_editorial_route_fit(
        anchor,
        region_identity_debug,
        flow_profile_debug,
        target_slot="anchor",
    )
    _anchor_landmark_authority_signal = score_landmark_authority(
        anchor,
        region_identity_debug,
        flow_profile_debug,
        target_slot="anchor",
    )
    _anchor_image_signal = _score_image_availability(
        anchor,
        flow_profile=flow_profile_debug,
        target_slot="anchor",
        first_place=True,
    )
    _anchor_indoor_leisure_signal = _score_coastal_indoor_leisure(
        anchor,
        flow_profile=flow_profile_debug,
        target_slot="anchor",
        first_place=True,
    )
    _anchor_suitability_bonus = float(_anchor_suitability_signal.get("suitability_bonus") or 0.0)
    _anchor_suitability_demote = float(_anchor_suitability_signal.get("suitability_soft_demote") or 0.0)
    _anchor_meal_cafe_bonus = float(_anchor_meal_cafe_signal.get("meal_cafe_bonus") or 0.0)
    _anchor_meal_cafe_demote = float(_anchor_meal_cafe_signal.get("meal_cafe_soft_demote") or 0.0)
    _anchor_route_contamination_demote = float(
        _anchor_route_contamination_signal.get("route_contamination_demote") or 0.0
    )
    _anchor_editorial_bonus = float(_anchor_editorial_signal.get("editorial_bonus") or 0.0)
    _anchor_editorial_demote = float(_anchor_editorial_signal.get("editorial_demote") or 0.0)
    _anchor_landmark_authority_score = float(
        _anchor_landmark_authority_signal.get("landmark_authority_score") or 0.0
    )
    _anchor_external_verified_score = float(
        _anchor_landmark_authority_signal.get("external_verified_score") or 0.0
    )
    _anchor_external_popularity_score = float(
        _anchor_landmark_authority_signal.get("external_popularity_score") or 0.0
    )
    _anchor_public_data_weakness_penalty = float(
        _anchor_landmark_authority_signal.get("public_data_weakness_penalty") or 0.0
    )
    _anchor_representative_confidence_score = float(
        _anchor_landmark_authority_signal.get("representative_confidence_score") or 0.0
    )
    _anchor_weak_generic_authority_demote = float(
        _anchor_landmark_authority_signal.get("weak_generic_authority_demote") or 0.0
    )
    _anchor_family_candidate_lookup_bonus = float(
        _anchor_landmark_authority_signal.get("family_candidate_lookup_bonus") or 0.0
    )
    _anchor_wrong_region_alias_demote = float(
        _anchor_landmark_authority_signal.get("wrong_region_alias_demote") or 0.0
    )
    _anchor_curated_representative_priority = float(
        _anchor_landmark_authority_signal.get("curated_representative_priority") or 0.0
    )
    _anchor_curated_support_slot_alignment = float(
        _anchor_landmark_authority_signal.get("curated_support_slot_alignment") or 0.0
    )
    _anchor_weak_public_contamination_demote = float(
        _anchor_landmark_authority_signal.get("weak_public_contamination_demote") or 0.0
    )
    _anchor_default_preset_signal = _score_default_preset_landmark(
        anchor,
        _anchor_landmark_authority_signal,
        default_preset_mode=default_preset_mode,
        target_slot="anchor",
    )
    _anchor_default_preset_landmark_bonus = float(_anchor_default_preset_signal.get("default_preset_landmark_bonus") or 0.0)
    _anchor_weird_candidate_demote = float(_anchor_default_preset_signal.get("weird_candidate_demote") or 0.0)
    _anchor_public_facility_signal = _score_public_facility_tourism_fit(
        anchor,
        _anchor_landmark_authority_signal,
        default_preset_mode=default_preset_mode,
        target_slot="anchor",
        first_place=True,
    )
    _anchor_public_facility_demote = float(_anchor_public_facility_signal.get("public_facility_demote") or 0.0)
    _anchor_representative_tourism_fit = float(_anchor_public_facility_signal.get("representative_tourism_fit") or 0.0)
    _anchor_family_signal = _score_selected_anchor_family(
        anchor,
        selected_anchor_family,
        _anchor_landmark_authority_signal,
        default_preset_mode=default_preset_mode,
        target_slot="anchor",
    )
    _anchor_family_match_score = float(_anchor_family_signal.get("selected_anchor_family_match_score") or 0.0)
    _anchor_family_drift_demote = float(_anchor_family_signal.get("selected_anchor_family_drift_demote") or 0.0)
    _anchor_busan_oldtown_signal = _score_busan_oldtown_family(
        anchor,
        selected_anchor_family,
        region=region,
        target_slot="anchor",
    )
    _anchor_busan_oldtown_family_score = float(_anchor_busan_oldtown_signal.get("busan_oldtown_family_score") or 0.0)
    _anchor_busan_oldtown_drift_demote = float(_anchor_busan_oldtown_signal.get("busan_oldtown_drift_demote") or 0.0)
    _anchor_busan_oldtown_support_slot_score = float(_anchor_busan_oldtown_signal.get("busan_oldtown_support_slot_score") or 0.0)
    _anchor_exact_landmark_signal = _score_exact_landmark_visibility(
        anchor,
        selected_anchor_family,
        _anchor_landmark_authority_signal,
        region=region,
        target_slot="anchor",
    )
    _anchor_exact_landmark_visibility_score = float(
        _anchor_exact_landmark_signal.get("exact_landmark_visibility_score") or 0.0
    )
    _anchor_exact_landmark_support_slot_bonus = float(
        _anchor_exact_landmark_signal.get("exact_landmark_support_slot_bonus") or 0.0
    )
    _anchor_weak_substitute_demote = float(_anchor_exact_landmark_signal.get("weak_substitute_demote") or 0.0)
    _anchor_exact_slot_alignment_bonus = float(_anchor_exact_landmark_signal.get("exact_slot_alignment_bonus") or 0.0)
    _anchor_oldtown_substitute_demote = float(_anchor_exact_landmark_signal.get("oldtown_substitute_demote") or 0.0)
    _anchor_east_coast_signal = _score_busan_east_coast_family(
        anchor,
        selected_anchor_family,
        region=region,
        target_slot="anchor",
    )
    _anchor_east_coast_family_score = float(_anchor_east_coast_signal.get("busan_east_coast_family_score") or 0.0)
    _anchor_east_coast_drift_demote = float(_anchor_east_coast_signal.get("haeundae_gwangan_drift_demote") or 0.0)
    _anchor_east_coast_support_slot_score = float(_anchor_east_coast_signal.get("east_coast_support_slot_score") or 0.0)
    _anchor_seomyeon_signal = _score_busan_seomyeon_family(
        anchor,
        selected_anchor_family,
        _anchor_landmark_authority_signal,
        region=region,
        target_slot="anchor",
    )
    _anchor_seomyeon_family_score = float(_anchor_seomyeon_signal.get("seomyeon_family_score") or 0.0)
    _anchor_seomyeon_drift_demote = float(_anchor_seomyeon_signal.get("seomyeon_drift_demote") or 0.0)
    _anchor_seomyeon_weak_candidate_demote = float(_anchor_seomyeon_signal.get("seomyeon_weak_candidate_demote") or 0.0)
    _anchor_seoul_editorial_depth_signal = _score_seoul_editorial_depth(
        anchor,
        selected_anchor_family,
        _anchor_landmark_authority_signal,
        region=region,
        target_slot="anchor",
        default_preset_mode=default_preset_mode,
    )
    _anchor_seoul_broad_default_family_balance = float(_anchor_seoul_editorial_depth_signal.get("seoul_broad_default_family_balance") or 0.0)
    _anchor_bukchon_editorial_depth_score = float(_anchor_seoul_editorial_depth_signal.get("bukchon_editorial_depth_score") or 0.0)
    _anchor_seongsu_editorial_depth_score = float(_anchor_seoul_editorial_depth_signal.get("seongsu_editorial_depth_score") or 0.0)
    _anchor_lifestyle_support_slot_visibility = float(_anchor_seoul_editorial_depth_signal.get("lifestyle_support_slot_visibility") or 0.0)
    _anchor_representative_family_rotation_balance = float(_anchor_seoul_editorial_depth_signal.get("representative_family_rotation_balance") or 0.0)
    _anchor_seoul_editorial_weak_demote = float(_anchor_seoul_editorial_depth_signal.get("seoul_editorial_weak_demote") or 0.0)
    _anchor_seoul_curated_district_priority = float(_anchor_seoul_editorial_depth_signal.get("seoul_curated_district_priority") or 0.0)
    _anchor_broad_seoul_demoted = float(_anchor_seoul_editorial_depth_signal.get("broad_seoul_demoted") or 0.0)
    _anchor_district_identity_alignment = float(_anchor_seoul_editorial_depth_signal.get("district_identity_alignment") or 0.0)
    _anchor_support_slot_role_diversity = float(_anchor_seoul_editorial_depth_signal.get("support_slot_role_diversity") or 0.0)
    _anchor_seoul_family_signal = _score_seoul_gangnam_yeouido_family(
        anchor,
        selected_anchor_family,
        _anchor_landmark_authority_signal,
        region=region,
        target_slot="anchor",
    )
    _anchor_seoul_external_authority_boost = float(_anchor_seoul_family_signal.get("seoul_external_authority_boost") or 0.0)
    _anchor_gangnam_family_score = float(_anchor_seoul_family_signal.get("gangnam_family_score") or 0.0)
    _anchor_yeouido_family_score = float(_anchor_seoul_family_signal.get("yeouido_family_score") or 0.0)
    _anchor_seoul_weak_lifestyle_demote = float(_anchor_seoul_family_signal.get("seoul_weak_lifestyle_demote") or 0.0)
    _anchor_gangnam_candidate_depth_score = float(_anchor_seoul_family_signal.get("gangnam_candidate_depth_score") or 0.0)
    _anchor_gangnam_first_place_dominance_penalty = float(
        _anchor_seoul_family_signal.get("gangnam_first_place_dominance_penalty") or 0.0
    )
    _anchor_yeouido_public_facility_final_demote = float(
        _anchor_seoul_family_signal.get("yeouido_public_facility_final_demote") or 0.0
    )
    _anchor_euljiro_night_family_score = float(_anchor_seoul_family_signal.get("euljiro_night_family_score") or 0.0)
    _anchor_gangnam_editorial_representative_score = float(
        _anchor_seoul_family_signal.get("gangnam_editorial_representative_score") or 0.0
    )
    _anchor_weak_editorial_first_place_demote = float(_anchor_seoul_family_signal.get("weak_editorial_first_place_demote") or 0.0)
    _anchor_nightlife_coherence_score = float(_anchor_seoul_family_signal.get("nightlife_coherence_score") or 0.0)
    _anchor_curated_night_signal = _score_curated_night_family(
        anchor,
        region=region,
        selected_anchor=selected_anchor,
        selected_anchor_family=selected_anchor_family,
        flow_profile=flow_profile_debug,
        target_slot="anchor",
        late_context=late_scoring_context,
    )
    _anchor_night_representative_preference = float(
        _anchor_curated_night_signal.get("night_representative_preference") or 0.0
    )
    _anchor_nightlife_curated_alignment = float(
        _anchor_curated_night_signal.get("nightlife_curated_alignment") or 0.0
    )
    _anchor_night_vibe_coherence = float(_anchor_curated_night_signal.get("night_vibe_coherence") or 0.0)
    _anchor_curated_night_support_slot = float(_anchor_curated_night_signal.get("curated_night_support_slot") or 0.0)
    _anchor_curated_night_weak_demote = float(_anchor_curated_night_signal.get("curated_night_weak_demote") or 0.0)
    _anchor_image_bonus = float(_anchor_image_signal.get("image_quality_bonus") or 0.0)
    _anchor_no_image_demote = float(_anchor_image_signal.get("no_image_first_place_demote") or 0.0)
    _anchor_indoor_leisure_demote = float(_anchor_indoor_leisure_signal.get("indoor_leisure_demote") or 0.0)
    _anchor_flow_bonus = float(_anchor_flow_signal.get("continuity_bonus") or 0.0)
    _anchor_identity_bonus = float(_anchor_belt_signal.get("belt_match_bonus") or 0.0)
    _anchor_dominant_belt_bonus = float(_anchor_dominant_belt_signal.get("dominant_belt_bonus") or 0.0)
    _anchor_final_score = (
        _a_final
        + _anchor_belt_b
        + _anchor_identity_bonus
        + _anchor_dominant_belt_bonus
        + _anchor_flow_bonus
        + _anchor_suitability_bonus
        - _anchor_suitability_demote
        + _anchor_meal_cafe_bonus
        - _anchor_meal_cafe_demote
        - _anchor_route_contamination_demote
        + _anchor_editorial_bonus
        - _anchor_editorial_demote
        + _anchor_landmark_authority_score
        + _anchor_external_verified_score
        + _anchor_external_popularity_score
        + _anchor_representative_confidence_score
        + _anchor_family_candidate_lookup_bonus
        + _anchor_curated_representative_priority
        + _anchor_curated_support_slot_alignment
        - _anchor_public_data_weakness_penalty
        - _anchor_wrong_region_alias_demote
        - _anchor_weak_generic_authority_demote
        - _anchor_weak_public_contamination_demote
        + _anchor_default_preset_landmark_bonus
        - _anchor_weird_candidate_demote
        - _anchor_public_facility_demote
        + _anchor_representative_tourism_fit
        + _anchor_family_match_score
        - _anchor_family_drift_demote
        + _anchor_busan_oldtown_family_score
        + _anchor_busan_oldtown_support_slot_score
        - _anchor_busan_oldtown_drift_demote
        + _anchor_exact_landmark_visibility_score
        + _anchor_exact_landmark_support_slot_bonus
        + _anchor_exact_slot_alignment_bonus
        - _anchor_weak_substitute_demote
        - _anchor_oldtown_substitute_demote
        + _anchor_east_coast_family_score
        + _anchor_east_coast_support_slot_score
        - _anchor_east_coast_drift_demote
        + _anchor_seomyeon_family_score
        - _anchor_seomyeon_drift_demote
        - _anchor_seomyeon_weak_candidate_demote
        + _anchor_seoul_broad_default_family_balance
        + _anchor_bukchon_editorial_depth_score
        + _anchor_seongsu_editorial_depth_score
        + _anchor_lifestyle_support_slot_visibility
        + _anchor_representative_family_rotation_balance
        + _anchor_seoul_curated_district_priority
        + _anchor_district_identity_alignment
        + _anchor_support_slot_role_diversity
        - _anchor_seoul_editorial_weak_demote
        - _anchor_broad_seoul_demoted
        + _anchor_seoul_external_authority_boost
        + _anchor_gangnam_family_score
        + _anchor_yeouido_family_score
        + _anchor_gangnam_candidate_depth_score
        - _anchor_seoul_weak_lifestyle_demote
        - _anchor_gangnam_first_place_dominance_penalty
        - _anchor_yeouido_public_facility_final_demote
        + _anchor_euljiro_night_family_score
        + _anchor_gangnam_editorial_representative_score
        + _anchor_nightlife_coherence_score
        + _anchor_night_representative_preference
        + _anchor_nightlife_curated_alignment
        + _anchor_night_vibe_coherence
        + _anchor_curated_night_support_slot
        - _anchor_weak_editorial_first_place_demote
        - _anchor_curated_night_weak_demote
        + _anchor_image_bonus
        - _anchor_no_image_demote
        - _anchor_indoor_leisure_demote
    )
    _anchor_scores: dict = {
        "travel_fit":         1.0,
        "theme_match":        round(_a_theme_sc, 4),
        "popularity_score":   round(_a_pop_sc, 4),
        "slot_fit":           1.0,
        "penalty_multiplier": 1.0,
        "inferred_belt": _anchor_belt_signal.get("inferred_belt"),
        "belt_confidence": _anchor_belt_signal.get("belt_confidence", 0.0),
        "belt_match_bonus": _anchor_belt_signal.get("belt_match_bonus", 0.0),
        "belt_match_reasons": _anchor_belt_signal.get("belt_match_reasons") or [],
        "dominant_belt": _anchor_dominant_belt_signal.get("dominant_belt"),
        "dominant_belt_bonus": round(_anchor_dominant_belt_bonus, 4),
        "dominant_belt_reasons": _anchor_dominant_belt_signal.get("dominant_belt_reasons") or [],
        "inferred_flow_profile": _anchor_flow_signal.get("inferred_flow_profile"),
        "slot_flow_alignment": _anchor_flow_signal.get("slot_flow_alignment", 0.0),
        "continuity_bonus": round(_anchor_flow_bonus, 4),
        "flow_match_reasons": _anchor_flow_signal.get("flow_match_reasons") or [],
        "suitability_profile": _anchor_suitability_signal.get("suitability_profile"),
        "vibe_suitability_score": _anchor_suitability_signal.get("vibe_suitability_score", 0.0),
        "tourism_suitability_score": _anchor_suitability_signal.get("tourism_suitability_score", 0.0),
        "suitability_bonus": round(_anchor_suitability_bonus, 4),
        "suitability_soft_demote": round(_anchor_suitability_demote, 4),
        "vibe_match_reasons": _anchor_suitability_signal.get("vibe_match_reasons") or [],
        "soft_demote_reason": _anchor_suitability_signal.get("soft_demote_reason"),
        "meal_cafe_profile": _anchor_meal_cafe_signal.get("meal_cafe_profile"),
        "meal_vibe_score": _anchor_meal_cafe_signal.get("meal_vibe_score", 0.0),
        "meal_experience_score": _anchor_meal_cafe_signal.get("meal_experience_score", 0.0),
        "meal_soft_demote_reason": _anchor_meal_cafe_signal.get("meal_soft_demote_reason"),
        "local_food_bonus": _anchor_meal_cafe_signal.get("local_food_bonus", 0.0),
        "view_bonus": _anchor_meal_cafe_signal.get("view_bonus", 0.0),
        "meal_cafe_bonus": round(_anchor_meal_cafe_bonus, 4),
        "meal_cafe_soft_demote": round(_anchor_meal_cafe_demote, 4),
        "meal_cafe_match_reasons": _anchor_meal_cafe_signal.get("meal_cafe_match_reasons") or [],
        "route_contamination_demote": round(_anchor_route_contamination_demote, 4),
        "route_contamination_flags": _anchor_route_contamination_signal.get("route_contamination_flags") or [],
        "route_contamination_reasons": _anchor_route_contamination_signal.get("route_contamination_reasons") or [],
        "route_positive_matches": _anchor_route_contamination_signal.get("route_positive_matches") or [],
        "coastal_vibe_score": _anchor_route_contamination_signal.get("coastal_vibe_score", 0.0),
        "night_view_score": _anchor_route_contamination_signal.get("night_view_score", 0.0),
        "harbor_alignment": _anchor_route_contamination_signal.get("harbor_alignment", 0.0),
        "sea_route_continuity": _anchor_route_contamination_signal.get("sea_route_continuity", 0.0),
        "inland_contamination_flags": _anchor_route_contamination_signal.get("inland_contamination_flags") or [],
        "religious_facility_demote": _anchor_route_contamination_signal.get("religious_facility_demote", 0.0),
        "religious_tourism_exception": _anchor_route_contamination_signal.get("religious_tourism_exception") or [],
        "editorial_bonus": round(_anchor_editorial_bonus, 4),
        "editorial_demote": round(_anchor_editorial_demote, 4),
        "editorial_demote_reason": _anchor_editorial_signal.get("editorial_demote_reason"),
        "weak_first_place_reason": _anchor_editorial_signal.get("weak_first_place_reason"),
        "central_drift_reason": _anchor_editorial_signal.get("central_drift_reason"),
        "landmark_priority_score": _anchor_editorial_signal.get("landmark_priority_score", 0.0),
        "representative_vibe_score": _anchor_editorial_signal.get("representative_vibe_score", 0.0),
        "weak_indoor_demote": _anchor_editorial_signal.get("weak_indoor_demote", 0.0),
        "landmark_alignment_reason": _anchor_editorial_signal.get("landmark_alignment_reason"),
        "seongsu_vibe_score": _anchor_editorial_signal.get("seongsu_vibe_score", 0.0),
        "cafe_street_alignment": _anchor_editorial_signal.get("cafe_street_alignment", 0.0),
        "weak_meal_demote": _anchor_editorial_signal.get("weak_meal_demote", 0.0),
        "editorial_first_place_bonus": _anchor_editorial_signal.get("editorial_first_place_bonus", 0.0),
        "euljiro_night_score": _anchor_editorial_signal.get("euljiro_night_score", 0.0),
        "hipjiro_alignment": _anchor_editorial_signal.get("hipjiro_alignment", 0.0),
        "central_drift_demote": _anchor_editorial_signal.get("central_drift_demote", 0.0),
        "night_vibe_bonus": _anchor_editorial_signal.get("night_vibe_bonus", 0.0),
        "seoul_date_score": _anchor_editorial_signal.get("seoul_date_score", 0.0),
        "date_vibe_alignment": _anchor_editorial_signal.get("date_vibe_alignment", 0.0),
        "broad_seoul_drift_demote": _anchor_editorial_signal.get("broad_seoul_drift_demote", 0.0),
        "romantic_walk_bonus": _anchor_editorial_signal.get("romantic_walk_bonus", 0.0),
        "busan_night_meal_score": _anchor_editorial_signal.get("busan_night_meal_score", 0.0),
        "waterfront_alignment": _anchor_editorial_signal.get("waterfront_alignment", 0.0),
        "weak_daytime_meal_demote": _anchor_editorial_signal.get("weak_daytime_meal_demote", 0.0),
        "night_meal_bonus": _anchor_editorial_signal.get("night_meal_bonus", 0.0),
        "busan_landmark_priority_score": _anchor_editorial_signal.get("busan_landmark_priority_score", 0.0),
        "busan_representative_bonus": _anchor_editorial_signal.get("busan_representative_bonus", 0.0),
        "busan_landmark_alignment_reason": _anchor_editorial_signal.get("busan_landmark_alignment_reason"),
        "representative_tourism_family_score": max(
            float(_anchor_editorial_signal.get("representative_tourism_family_score") or 0.0),
            float(_anchor_landmark_authority_signal.get("representative_tourism_family_score") or 0.0),
        ),
        "indoor_culture_fallback_demote": max(
            float(_anchor_editorial_signal.get("indoor_culture_fallback_demote") or 0.0),
            float(_anchor_landmark_authority_signal.get("indoor_culture_fallback_demote") or 0.0),
        ),
        "regional_landmark_density": max(
            float(_anchor_editorial_signal.get("regional_landmark_density") or 0.0),
            float(_anchor_landmark_authority_signal.get("regional_landmark_density") or 0.0),
        ),
        "first_place_representative_bonus": max(
            float(_anchor_editorial_signal.get("first_place_representative_bonus") or 0.0),
            float(_anchor_landmark_authority_signal.get("first_place_representative_bonus") or 0.0),
        ),
        "jinju_history_first_place_bonus": _anchor_editorial_signal.get("jinju_history_first_place_bonus", 0.0),
        "tongyeong_same_city_bonus": _anchor_editorial_signal.get("tongyeong_same_city_bonus", 0.0),
        "tongyeong_geoje_drift_demote": _anchor_editorial_signal.get("tongyeong_geoje_drift_demote", 0.0),
        "gimhae_gaya_family_score": _anchor_editorial_signal.get("gimhae_gaya_family_score", 0.0),
        "gimhae_support_slot_family_score": _anchor_editorial_signal.get("gimhae_support_slot_family_score", 0.0),
        "gimhae_support_slot_drift_demote": _anchor_editorial_signal.get("gimhae_support_slot_drift_demote", 0.0),
        "support_slot_coherence_score": _anchor_editorial_signal.get("support_slot_coherence_score", 0.0),
        "seoul_default_representative_score": _anchor_editorial_signal.get("seoul_default_representative_score", 0.0),
        "seoul_default_weak_first_place_demote": _anchor_editorial_signal.get("seoul_default_weak_first_place_demote", 0.0),
        "weak_museum_first_place_demote": _anchor_editorial_signal.get("weak_museum_first_place_demote", 0.0),
        "landmark_authority_score": round(_anchor_landmark_authority_score, 4),
        "popularity_signal": _anchor_landmark_authority_signal.get("popularity_signal", 0.0),
        "popularity_authority_score": _anchor_landmark_authority_signal.get("popularity_authority_score", 0.0),
        "landmark_confidence": _anchor_landmark_authority_signal.get("landmark_confidence", 0.0),
        "representative_tourism_bonus": _anchor_landmark_authority_signal.get("representative_tourism_bonus", 0.0),
        "tourism_representative_score": _anchor_landmark_authority_signal.get("tourism_representative_score", 0.0),
        "normalized_popularity_hint": _anchor_landmark_authority_signal.get("normalized_popularity_hint", 0.0),
        "external_verified_score": _anchor_landmark_authority_signal.get("external_verified_score", 0.0),
        "external_popularity_score": _anchor_landmark_authority_signal.get("external_popularity_score", 0.0),
        "public_data_weakness_penalty": _anchor_landmark_authority_signal.get("public_data_weakness_penalty", 0.0),
        "public_data_weakness_reason": _anchor_landmark_authority_signal.get("public_data_weakness_reason"),
        "representative_confidence_score": _anchor_landmark_authority_signal.get("representative_confidence_score", 0.0),
        "image_density_score": _anchor_landmark_authority_signal.get("image_density_score", 0.0),
        "review_density_hint": _anchor_landmark_authority_signal.get("review_density_hint", 0.0),
        "landmark_authority_matches": _anchor_landmark_authority_signal.get("landmark_authority_matches") or [],
        "landmark_authority_reason": _anchor_landmark_authority_signal.get("landmark_authority_reason"),
        "landmark_authority_source_policy": _anchor_landmark_authority_signal.get("landmark_authority_source_policy"),
        "alias_normalization_match": _anchor_landmark_authority_signal.get("alias_normalization_match") or [],
        "region_aware_alias_guard": _anchor_landmark_authority_signal.get("region_aware_alias_guard"),
        "wrong_region_alias_demote": round(_anchor_wrong_region_alias_demote, 4),
        "family_candidate_lookup_bonus": round(_anchor_family_candidate_lookup_bonus, 4),
        "representative_alias_pool_included": bool(_anchor_landmark_authority_signal.get("representative_alias_pool_included")),
        "weak_generic_authority_demote": round(_anchor_weak_generic_authority_demote, 4),
        "weak_generic_authority_reason": _anchor_landmark_authority_signal.get("weak_generic_authority_reason"),
        "curated_representative_priority": round(_anchor_curated_representative_priority, 4),
        "verified_api_candidate": bool(_anchor_landmark_authority_signal.get("verified_api_candidate")),
        "public_fallback_used": bool(_anchor_landmark_authority_signal.get("public_fallback_used")),
        "weak_public_contamination_demote": round(_anchor_weak_public_contamination_demote, 4),
        "curated_support_slot_alignment": round(_anchor_curated_support_slot_alignment, 4),
        "curated_representative_matches": _anchor_landmark_authority_signal.get("curated_representative_matches") or [],
        "curated_representative_context": _anchor_landmark_authority_signal.get("curated_representative_context"),
        "default_preset_mode": bool(_anchor_default_preset_signal.get("default_preset_mode")),
        "representative_landmark_selected": bool(_anchor_default_preset_signal.get("representative_landmark_selected")),
        "default_preset_landmark_bonus": round(_anchor_default_preset_landmark_bonus, 4),
        "weird_candidate_demote": round(_anchor_weird_candidate_demote, 4),
        "weird_candidate_demote_reason": _anchor_default_preset_signal.get("weird_candidate_demote_reason"),
        "public_facility_demote": round(_anchor_public_facility_demote, 4),
        "representative_tourism_fit": round(_anchor_representative_tourism_fit, 4),
        "weak_public_facility_reason": _anchor_public_facility_signal.get("weak_public_facility_reason"),
        "selected_anchor_family_id": _anchor_family_signal.get("selected_anchor_family_id"),
        "selected_anchor_family_match_score": round(_anchor_family_match_score, 4),
        "selected_anchor_family_preserved": bool(_anchor_family_signal.get("selected_anchor_family_preserved")),
        "selected_anchor_family_matched_terms": _anchor_family_signal.get("selected_anchor_family_matched_terms") or [],
        "selected_anchor_family_drift_demote": round(_anchor_family_drift_demote, 4),
        "selected_anchor_drift_reason": _anchor_family_signal.get("selected_anchor_drift_reason"),
        "fallback_level_used": _anchor_family_signal.get("fallback_level_used"),
        "busan_oldtown_family_score": round(_anchor_busan_oldtown_family_score, 4),
        "busan_oldtown_pool_included": bool(_anchor_busan_oldtown_signal.get("busan_oldtown_pool_included")),
        "busan_oldtown_drift_demote": round(_anchor_busan_oldtown_drift_demote, 4),
        "busan_oldtown_support_slot_score": round(_anchor_busan_oldtown_support_slot_score, 4),
        "busan_oldtown_expected_landmark_visible": bool(_anchor_busan_oldtown_signal.get("busan_oldtown_expected_landmark_visible")),
        "busan_oldtown_match_terms": _anchor_busan_oldtown_signal.get("busan_oldtown_match_terms") or [],
        "exact_landmark_visibility_score": round(_anchor_exact_landmark_visibility_score, 4),
        "exact_landmark_pool_included": bool(_anchor_exact_landmark_signal.get("exact_landmark_pool_included")),
        "exact_landmark_support_slot_bonus": round(_anchor_exact_landmark_support_slot_bonus, 4),
        "exact_landmark_missing_reason": _anchor_exact_landmark_signal.get("exact_landmark_missing_reason"),
        "weak_substitute_demote": round(_anchor_weak_substitute_demote, 4),
        "exact_slot_alignment_bonus": round(_anchor_exact_slot_alignment_bonus, 4),
        "exact_anchor_final_visibility": bool(_anchor_exact_landmark_signal.get("exact_anchor_final_visibility")),
        "oldtown_substitute_demote": round(_anchor_oldtown_substitute_demote, 4),
        "exact_landmark_match_terms": _anchor_exact_landmark_signal.get("exact_landmark_match_terms") or [],
        "busan_east_coast_family_score": round(_anchor_east_coast_family_score, 4),
        "east_coast_family_preserved": bool(_anchor_east_coast_signal.get("east_coast_family_preserved")),
        "haeundae_gwangan_drift_demote": round(_anchor_east_coast_drift_demote, 4),
        "east_coast_support_slot_score": round(_anchor_east_coast_support_slot_score, 4),
        "east_coast_expected_landmark_visible": bool(_anchor_east_coast_signal.get("east_coast_expected_landmark_visible")),
        "east_coast_match_terms": _anchor_east_coast_signal.get("east_coast_match_terms") or [],
        "seomyeon_family_score": round(_anchor_seomyeon_family_score, 4),
        "seomyeon_family_pool_included": bool(_anchor_seomyeon_signal.get("seomyeon_family_pool_included")),
        "seomyeon_nightlife_pool_included": bool(_anchor_seomyeon_signal.get("seomyeon_nightlife_pool_included")),
        "seomyeon_drift_demote": round(_anchor_seomyeon_drift_demote, 4),
        "seomyeon_weak_candidate_demote": round(_anchor_seomyeon_weak_candidate_demote, 4),
        "seomyeon_family_match_terms": _anchor_seomyeon_signal.get("seomyeon_family_match_terms") or [],
        "seoul_broad_default_family_balance": round(_anchor_seoul_broad_default_family_balance, 4),
        "bukchon_editorial_depth_score": round(_anchor_bukchon_editorial_depth_score, 4),
        "seongsu_editorial_depth_score": round(_anchor_seongsu_editorial_depth_score, 4),
        "lifestyle_support_slot_visibility": round(_anchor_lifestyle_support_slot_visibility, 4),
        "representative_family_rotation_balance": round(_anchor_representative_family_rotation_balance, 4),
        "seoul_curated_district_priority": round(_anchor_seoul_curated_district_priority, 4),
        "broad_seoul_demoted": round(_anchor_broad_seoul_demoted, 4),
        "district_identity_alignment": round(_anchor_district_identity_alignment, 4),
        "support_slot_role_diversity": round(_anchor_support_slot_role_diversity, 4),
        "seoul_broad_family_key": _anchor_seoul_editorial_depth_signal.get("seoul_broad_family_key"),
        "seoul_broad_family_matches": _anchor_seoul_editorial_depth_signal.get("seoul_broad_family_matches") or [],
        "bukchon_editorial_depth_matches": _anchor_seoul_editorial_depth_signal.get("bukchon_editorial_depth_matches") or [],
        "seongsu_editorial_depth_matches": _anchor_seoul_editorial_depth_signal.get("seongsu_editorial_depth_matches") or [],
        "seoul_editorial_weak_demote": round(_anchor_seoul_editorial_weak_demote, 4),
        "seoul_editorial_depth_pool_included": bool(_anchor_seoul_editorial_depth_signal.get("seoul_editorial_depth_pool_included")),
        "seoul_external_authority_boost": round(_anchor_seoul_external_authority_boost, 4),
        "gangnam_family_score": round(_anchor_gangnam_family_score, 4),
        "yeouido_family_score": round(_anchor_yeouido_family_score, 4),
        "seoul_weak_lifestyle_demote": round(_anchor_seoul_weak_lifestyle_demote, 4),
        "seoul_family_pool_included": bool(_anchor_seoul_family_signal.get("seoul_family_pool_included")),
        "seoul_family_match_terms": _anchor_seoul_family_signal.get("seoul_family_match_terms") or [],
        "gangnam_candidate_depth_score": round(_anchor_gangnam_candidate_depth_score, 4),
        "gangnam_representative_pool_included": bool(_anchor_seoul_family_signal.get("gangnam_representative_pool_included")),
        "gangnam_first_place_dominance_penalty": round(_anchor_gangnam_first_place_dominance_penalty, 4),
        "yeouido_public_facility_final_demote": round(_anchor_yeouido_public_facility_final_demote, 4),
        "family_candidate_depth_before_after": _anchor_seoul_family_signal.get("family_candidate_depth_before_after"),
        "euljiro_night_family_score": round(_anchor_euljiro_night_family_score, 4),
        "euljiro_nightlife_pool_included": bool(_anchor_seoul_family_signal.get("euljiro_nightlife_pool_included")),
        "gangnam_editorial_representative_score": round(_anchor_gangnam_editorial_representative_score, 4),
        "weak_editorial_first_place_demote": round(_anchor_weak_editorial_first_place_demote, 4),
        "nightlife_coherence_score": round(_anchor_nightlife_coherence_score, 4),
        "curated_night_family_applied": bool(_anchor_curated_night_signal.get("curated_night_family_applied")),
        "night_representative_preference": round(_anchor_night_representative_preference, 4),
        "nightlife_curated_alignment": round(_anchor_nightlife_curated_alignment, 4),
        "night_vibe_coherence": round(_anchor_night_vibe_coherence, 4),
        "curated_night_support_slot": round(_anchor_curated_night_support_slot, 4),
        "curated_night_match_terms": _anchor_curated_night_signal.get("curated_night_match_terms") or [],
        "curated_night_weak_demote": round(_anchor_curated_night_weak_demote, 4),
        "image_available": bool(_anchor_image_signal.get("image_available")),
        "image_quality_bonus": round(_anchor_image_bonus, 4),
        "no_image_first_place_demote": round(_anchor_no_image_demote, 4),
        "placeholder_used": not bool(_anchor_image_signal.get("image_available")),
        "indoor_leisure_demote": round(_anchor_indoor_leisure_demote, 4),
        "indoor_leisure_reason": _anchor_indoor_leisure_signal.get("indoor_leisure_reason"),
        "first_place_repeat_count": int(anchor.get("_first_place_repeat_count") or 0),
        "first_place_saturation_penalty": float(anchor.get("_first_place_saturation_penalty") or 0.0),
        "diversity_rotation_bonus": float(anchor.get("_diversity_rotation_bonus") or 0.0),
        "representative_pool_size": int(anchor.get("_representative_pool_size") or 1),
        "regenerate_diversity_applied": bool(anchor.get("_regenerate_diversity_applied")),
        "representative_family_pool_size": int(anchor.get("_representative_family_pool_size") or 0),
        "representative_family_rotation_bonus": float(anchor.get("_representative_family_rotation_bonus") or 0.0),
        "representative_family_saturation_penalty": float(anchor.get("_representative_family_saturation_penalty") or 0.0),
        "representative_family_first_place_repeat": int(anchor.get("_representative_family_first_place_repeat") or 0),
        "representative_family_diversity_applied": bool(anchor.get("_representative_family_diversity_applied")),
        "regenerate_repeat_penalty": float(anchor.get("_regenerate_repeat_penalty") or 0.0),
        "representative_family_rotation_applied": bool(anchor.get("_representative_family_rotation_applied")),
        "representative_candidate_pool_included": bool(anchor.get("_representative_candidate_pool_included")),
        "representative_candidate_pool_reason": anchor.get("_representative_candidate_pool_reason"),
        "representative_pool_cutoff_score": (
            (anchor.get("_first_anchor_candidate_scores") or [{}])[0].get("representative_pool_cutoff_score")
            if anchor.get("_first_anchor_candidate_scores") else None
        ),
        "representative_pool_competitor_count": (
            (anchor.get("_first_anchor_candidate_scores") or [{}])[0].get("representative_pool_competitor_count", 0)
            if anchor.get("_first_anchor_candidate_scores") else 0
        ),
        "weak_museum_pool_demote": (
            (anchor.get("_first_anchor_candidate_scores") or [{}])[0].get("weak_museum_pool_demote", 0.0)
            if anchor.get("_first_anchor_candidate_scores") else 0.0
        ),
        "final_score":        round(_anchor_final_score, 4),
    }
    if _anchor_belt_b > 0:
        _anchor_scores["belt_boost"]   = round(_anchor_belt_b, 4)
        _anchor_scores["matched_seed"] = _anchor_belt_seed
    first_anchor_reason = {
        "place_id": anchor.get("place_id"),
        "place_name": anchor.get("name"),
        "selected_by": "engine_anchor",
        "final_score": _anchor_scores.get("final_score"),
        "suitability_profile": _anchor_scores.get("suitability_profile"),
        "meal_cafe_profile": _anchor_scores.get("meal_cafe_profile"),
        "soft_demote_reason": _anchor_scores.get("soft_demote_reason")
        or _anchor_scores.get("meal_soft_demote_reason")
        or ",".join(_anchor_scores.get("route_contamination_flags") or []),
        "selected_anchor_family_id": _anchor_scores.get("selected_anchor_family_id"),
        "selected_anchor_family_preserved": bool(_anchor_scores.get("selected_anchor_family_preserved")),
        "selected_anchor_family_match_score": _anchor_scores.get("selected_anchor_family_match_score", 0.0),
        "selected_anchor_family_drift_demote": _anchor_scores.get("selected_anchor_family_drift_demote", 0.0),
        "selected_anchor_drift_reason": _anchor_scores.get("selected_anchor_drift_reason"),
        "fallback_level_used": _anchor_scores.get("fallback_level_used"),
        "public_facility_demote": _anchor_scores.get("public_facility_demote", 0.0),
        "representative_tourism_fit": _anchor_scores.get("representative_tourism_fit", 0.0),
        "weak_public_facility_reason": _anchor_scores.get("weak_public_facility_reason"),
        "first_place_repeat_count": _anchor_scores.get("first_place_repeat_count", 0),
        "first_place_saturation_penalty": _anchor_scores.get("first_place_saturation_penalty", 0.0),
        "diversity_rotation_bonus": _anchor_scores.get("diversity_rotation_bonus", 0.0),
        "representative_pool_size": _anchor_scores.get("representative_pool_size", 1),
        "regenerate_diversity_applied": bool(_anchor_scores.get("regenerate_diversity_applied")),
        "representative_family_pool_size": _anchor_scores.get("representative_family_pool_size", 0),
        "representative_family_rotation_bonus": _anchor_scores.get("representative_family_rotation_bonus", 0.0),
        "representative_family_saturation_penalty": _anchor_scores.get("representative_family_saturation_penalty", 0.0),
        "representative_family_first_place_repeat": _anchor_scores.get("representative_family_first_place_repeat", 0),
        "representative_family_diversity_applied": bool(_anchor_scores.get("representative_family_diversity_applied")),
        "regenerate_repeat_penalty": _anchor_scores.get("regenerate_repeat_penalty", 0.0),
        "representative_family_rotation_applied": bool(_anchor_scores.get("representative_family_rotation_applied")),
    }
    first_anchor_vibe_match = {
        "vibe_match_reasons": _anchor_scores.get("vibe_match_reasons") or [],
        "meal_cafe_match_reasons": _anchor_scores.get("meal_cafe_match_reasons") or [],
        "belt_match_reasons": _anchor_scores.get("belt_match_reasons") or [],
    }
    if _anchor_suitability_bonus > 0:
        trace_suitability_bonus_count += 1
    if _anchor_suitability_demote > 0:
        trace_suitability_soft_demote_count += 1
    if _anchor_meal_cafe_bonus > 0:
        trace_meal_cafe_bonus_count += 1
    if _anchor_meal_cafe_demote > 0:
        trace_meal_cafe_soft_demote_count += 1
    if _anchor_route_contamination_demote > 0:
        trace_route_contamination_count += 1
        _anchor_flags = set(_anchor_scores.get("route_contamination_flags") or [])
        if {"flow_contamination", "meal_flow_mismatch"} & _anchor_flags:
            trace_cross_flow_candidate_count += 1
        if {"lifestyle_contamination", "generic_commerce_mismatch"} & _anchor_flags:
            trace_lifestyle_mismatch_count += 1
    if _anchor_scores.get("operating_hours_known_closed"):
        trace_operating_hours_known_closed_count += 1
    if float(_anchor_scores.get("night_indoor_strong_demote") or 0.0) > 0:
        trace_night_indoor_strong_demote_count += 1
    if _anchor_scores.get("relaxed_unknown_hours_allowed"):
        trace_relaxed_unknown_hours_allowed_count += 1
    if _anchor_scores.get("known_closed_removed"):
        trace_known_closed_removed_count += 1
    if _anchor_scores.get("night_safe_indoor_exception"):
        trace_night_safe_indoor_exception_count += 1
    if _anchor_scores.get("indoor_semantic_detected"):
        trace_indoor_semantic_detected_count += 1
    if _anchor_scores.get("known_closed_indoor_removed"):
        trace_known_closed_indoor_removed_count += 1
    if float(_anchor_scores.get("night_indoor_semantic_demote") or 0.0) > 0:
        trace_night_indoor_semantic_demote_count += 1
    if _anchor_scores.get("indoor_closing_time_applied"):
        trace_indoor_closing_time_applied_count += 1
    if _anchor_scores.get("curated_night_family_applied"):
        trace_curated_night_family_applied_count += 1
    if float(_anchor_scores.get("night_representative_preference") or 0.0) > 0:
        trace_night_representative_preference_count += 1
    if float(_anchor_scores.get("nightlife_curated_alignment") or 0.0) > 0:
        trace_nightlife_curated_alignment_count += 1
    if float(_anchor_scores.get("night_vibe_coherence") or 0.0) > 0:
        trace_night_vibe_coherence_count += 1
    if float(_anchor_scores.get("curated_night_support_slot") or 0.0) > 0:
        trace_curated_night_support_slot_count += 1
    if float(_anchor_scores.get("curated_representative_priority") or 0.0) > 0:
        trace_curated_representative_priority_count += 1
    if _anchor_scores.get("verified_api_candidate"):
        trace_verified_api_candidate_count += 1
    if _anchor_scores.get("public_fallback_used"):
        trace_public_fallback_used_count += 1
    if float(_anchor_scores.get("weak_public_contamination_demote") or 0.0) > 0:
        trace_weak_public_contamination_demote_count += 1
    if float(_anchor_scores.get("curated_support_slot_alignment") or 0.0) > 0:
        trace_curated_support_slot_alignment_count += 1
    if float(_anchor_scores.get("seoul_curated_district_priority") or 0.0) > 0:
        trace_seoul_curated_district_priority_count += 1
    if float(_anchor_scores.get("broad_seoul_demoted") or 0.0) > 0:
        trace_broad_seoul_demoted_count += 1
    if float(_anchor_scores.get("district_identity_alignment") or 0.0) > 0:
        trace_district_identity_alignment_count += 1
    if float(_anchor_scores.get("support_slot_role_diversity") or 0.0) > 0:
        trace_support_slot_role_diversity_count += 1

    first_place_replacement_event: dict = {
        "first_place_replacement_attempted": False,
        "first_place_replacement_success": False,
        "first_place_replaced": None,
        "first_place_replacement_candidate": None,
        "first_place_coherence_delta": 0.0,
    }
    if selected_anchor and (
        _anchor_route_contamination_demote >= 0.08
        or _anchor_editorial_demote >= 0.06
        or _anchor_no_image_demote >= 0.055
        or _anchor_indoor_leisure_demote >= 0.08
        or _anchor_public_facility_demote >= 0.08
        or float(_anchor_scores.get("night_indoor_strong_demote") or 0.0) > 0
    ):
        first_place_replacement_event["first_place_replacement_attempted"] = True
        _first_place_excluded = {anchor["place_id"]}
        _replacement_anchor = _select_anchor(
            conn, region, themes, first_role=slots[0][1],
            zone_center=zone_center, zone_radius_km=zone_radius_km,
            exclude_ids=_first_place_excluded,
            selected_anchor=selected_anchor_token_set or selected_anchor,
            region_identity=region_identity_debug,
            flow_profile=flow_profile_debug,
            default_preset_mode=default_preset_mode,
            selected_anchor_family=selected_anchor_family,
            late_context=late_scoring_context,
            start_time=start_time,
        )
        if _replacement_anchor is not None:
            _replacement_route_signal = score_route_contamination(
                _replacement_anchor,
                region_identity_debug,
                flow_profile_debug,
                target_slot=slots[0][0],
            )
            _replacement_suitability_signal = score_vibe_tourism_suitability(
                _replacement_anchor,
                flow_profile_debug,
                target_slot=slots[0][0],
            )
            _replacement_editorial_signal = score_editorial_route_fit(
                _replacement_anchor,
                region_identity_debug,
                flow_profile_debug,
                target_slot="anchor",
            )
            _replacement_landmark_authority_signal = score_landmark_authority(
                _replacement_anchor,
                region_identity_debug,
                flow_profile_debug,
                target_slot="anchor",
            )
            _replacement_image_signal = _score_image_availability(
                _replacement_anchor,
                flow_profile=flow_profile_debug,
                target_slot="anchor",
                first_place=True,
            )
            _replacement_indoor_signal = _score_coastal_indoor_leisure(
                _replacement_anchor,
                flow_profile=flow_profile_debug,
                target_slot="anchor",
                first_place=True,
            )
            _replacement_public_facility_signal = _score_public_facility_tourism_fit(
                _replacement_anchor,
                _replacement_landmark_authority_signal,
                default_preset_mode=default_preset_mode,
                target_slot="anchor",
                first_place=True,
            )
            _replacement_demote = float(_replacement_route_signal.get("route_contamination_demote") or 0.0)
            _replacement_editorial_demote = float(_replacement_editorial_signal.get("editorial_demote") or 0.0)
            _replacement_no_image_demote = float(_replacement_image_signal.get("no_image_first_place_demote") or 0.0)
            _replacement_indoor_demote = float(_replacement_indoor_signal.get("indoor_leisure_demote") or 0.0)
            _replacement_public_facility_demote = float(_replacement_public_facility_signal.get("public_facility_demote") or 0.0)
            _replacement_suitability = float(_replacement_suitability_signal.get("suitability_bonus") or 0.0)
            _current_suitability = float(_anchor_suitability_signal.get("suitability_bonus") or 0.0)
            if (
                _replacement_demote
                + _replacement_editorial_demote
                + _replacement_no_image_demote
                + _replacement_indoor_demote
                + _replacement_public_facility_demote
                < _anchor_route_contamination_demote
                + _anchor_editorial_demote
                + _anchor_no_image_demote
                + _anchor_indoor_leisure_demote
                + _anchor_public_facility_demote
                and (_replacement_suitability >= _current_suitability - 0.03)
            ):
                first_place_replacement_event.update({
                    "first_place_replacement_success": True,
                    "first_place_replaced": anchor.get("name"),
                    "first_place_replacement_candidate": _replacement_anchor.get("name"),
                    "first_place_coherence_delta": round(
                        (1.0 - min(0.5, _replacement_demote))
                        - (1.0 - min(0.5, _anchor_route_contamination_demote + _anchor_editorial_demote)),
                        4,
                    ),
                })
                anchor = _replacement_anchor
                _anchor_belt_b, _anchor_belt_seed = get_belt_info(
                    region, anchor["name"], anchor["latitude"], anchor["longitude"]
                )
                _anchor_belt_signal = score_belt_match(anchor, region_identity_debug)
                _anchor_dominant_belt_signal = score_dominant_belt_affinity(anchor, region_identity_debug)
                _anchor_flow_signal = score_flow_continuity(anchor, None, flow_profile_debug)
                _anchor_suitability_signal = _replacement_suitability_signal
                _anchor_meal_cafe_signal = score_meal_cafe_suitability(
                    anchor,
                    flow_profile_debug,
                    target_slot=slots[0][0],
                )
                _anchor_route_contamination_signal = _replacement_route_signal
                _anchor_editorial_signal = _replacement_editorial_signal
                _anchor_landmark_authority_signal = _replacement_landmark_authority_signal
                _anchor_image_signal = _replacement_image_signal
                _anchor_indoor_leisure_signal = _replacement_indoor_signal
                _anchor_public_facility_signal = _replacement_public_facility_signal
                _anchor_suitability_bonus = float(_anchor_suitability_signal.get("suitability_bonus") or 0.0)
                _anchor_suitability_demote = float(_anchor_suitability_signal.get("suitability_soft_demote") or 0.0)
                _anchor_meal_cafe_bonus = float(_anchor_meal_cafe_signal.get("meal_cafe_bonus") or 0.0)
                _anchor_meal_cafe_demote = float(_anchor_meal_cafe_signal.get("meal_cafe_soft_demote") or 0.0)
                _anchor_route_contamination_demote = _replacement_demote
                _anchor_editorial_bonus = float(_anchor_editorial_signal.get("editorial_bonus") or 0.0)
                _anchor_editorial_demote = _replacement_editorial_demote
                _anchor_landmark_authority_score = float(
                    _anchor_landmark_authority_signal.get("landmark_authority_score") or 0.0
                )
                _anchor_external_verified_score = float(
                    _anchor_landmark_authority_signal.get("external_verified_score") or 0.0
                )
                _anchor_external_popularity_score = float(
                    _anchor_landmark_authority_signal.get("external_popularity_score") or 0.0
                )
                _anchor_public_data_weakness_penalty = float(
                    _anchor_landmark_authority_signal.get("public_data_weakness_penalty") or 0.0
                )
                _anchor_representative_confidence_score = float(
                    _anchor_landmark_authority_signal.get("representative_confidence_score") or 0.0
                )
                _anchor_weak_generic_authority_demote = float(
                    _anchor_landmark_authority_signal.get("weak_generic_authority_demote") or 0.0
                )
                _anchor_family_candidate_lookup_bonus = float(
                    _anchor_landmark_authority_signal.get("family_candidate_lookup_bonus") or 0.0
                )
                _anchor_wrong_region_alias_demote = float(
                    _anchor_landmark_authority_signal.get("wrong_region_alias_demote") or 0.0
                )
                _anchor_image_bonus = float(_anchor_image_signal.get("image_quality_bonus") or 0.0)
                _anchor_no_image_demote = _replacement_no_image_demote
                _anchor_indoor_leisure_demote = _replacement_indoor_demote
                _anchor_public_facility_demote = _replacement_public_facility_demote
                _anchor_representative_tourism_fit = float(_anchor_public_facility_signal.get("representative_tourism_fit") or 0.0)
                _anchor_busan_oldtown_signal = _score_busan_oldtown_family(
                    anchor,
                    selected_anchor_family,
                    region=region,
                    target_slot="anchor",
                )
                _anchor_busan_oldtown_family_score = float(_anchor_busan_oldtown_signal.get("busan_oldtown_family_score") or 0.0)
                _anchor_busan_oldtown_drift_demote = float(_anchor_busan_oldtown_signal.get("busan_oldtown_drift_demote") or 0.0)
                _anchor_busan_oldtown_support_slot_score = float(_anchor_busan_oldtown_signal.get("busan_oldtown_support_slot_score") or 0.0)
                _anchor_east_coast_signal = _score_busan_east_coast_family(
                    anchor,
                    selected_anchor_family,
                    region=region,
                    target_slot="anchor",
                )
                _anchor_east_coast_family_score = float(_anchor_east_coast_signal.get("busan_east_coast_family_score") or 0.0)
                _anchor_east_coast_drift_demote = float(_anchor_east_coast_signal.get("haeundae_gwangan_drift_demote") or 0.0)
                _anchor_east_coast_support_slot_score = float(_anchor_east_coast_signal.get("east_coast_support_slot_score") or 0.0)
                _anchor_seoul_family_signal = _score_seoul_gangnam_yeouido_family(
                    anchor,
                    selected_anchor_family,
                    _anchor_landmark_authority_signal,
                    region=region,
                    target_slot="anchor",
                )
                _anchor_seoul_external_authority_boost = float(_anchor_seoul_family_signal.get("seoul_external_authority_boost") or 0.0)
                _anchor_gangnam_family_score = float(_anchor_seoul_family_signal.get("gangnam_family_score") or 0.0)
                _anchor_yeouido_family_score = float(_anchor_seoul_family_signal.get("yeouido_family_score") or 0.0)
                _anchor_seoul_weak_lifestyle_demote = float(_anchor_seoul_family_signal.get("seoul_weak_lifestyle_demote") or 0.0)
                _anchor_gangnam_candidate_depth_score = float(_anchor_seoul_family_signal.get("gangnam_candidate_depth_score") or 0.0)
                _anchor_gangnam_first_place_dominance_penalty = float(
                    _anchor_seoul_family_signal.get("gangnam_first_place_dominance_penalty") or 0.0
                )
                _anchor_yeouido_public_facility_final_demote = float(
                    _anchor_seoul_family_signal.get("yeouido_public_facility_final_demote") or 0.0
                )
                _anchor_euljiro_night_family_score = float(_anchor_seoul_family_signal.get("euljiro_night_family_score") or 0.0)
                _anchor_gangnam_editorial_representative_score = float(
                    _anchor_seoul_family_signal.get("gangnam_editorial_representative_score") or 0.0
                )
                _anchor_weak_editorial_first_place_demote = float(_anchor_seoul_family_signal.get("weak_editorial_first_place_demote") or 0.0)
                _anchor_nightlife_coherence_score = float(_anchor_seoul_family_signal.get("nightlife_coherence_score") or 0.0)
                _anchor_curated_night_signal = _score_curated_night_family(
                    anchor,
                    region=region,
                    selected_anchor=selected_anchor,
                    selected_anchor_family=selected_anchor_family,
                    flow_profile=flow_profile_debug,
                    target_slot="anchor",
                    late_context=late_scoring_context,
                )
                _anchor_night_representative_preference = float(
                    _anchor_curated_night_signal.get("night_representative_preference") or 0.0
                )
                _anchor_nightlife_curated_alignment = float(
                    _anchor_curated_night_signal.get("nightlife_curated_alignment") or 0.0
                )
                _anchor_night_vibe_coherence = float(_anchor_curated_night_signal.get("night_vibe_coherence") or 0.0)
                _anchor_curated_night_support_slot = float(_anchor_curated_night_signal.get("curated_night_support_slot") or 0.0)
                _anchor_curated_night_weak_demote = float(_anchor_curated_night_signal.get("curated_night_weak_demote") or 0.0)
                _anchor_flow_bonus = float(_anchor_flow_signal.get("continuity_bonus") or 0.0)
                _anchor_identity_bonus = float(_anchor_belt_signal.get("belt_match_bonus") or 0.0)
                _anchor_dominant_belt_bonus = float(_anchor_dominant_belt_signal.get("dominant_belt_bonus") or 0.0)
                _anchor_final_score = (
                    _a_final
                    + _anchor_belt_b
                    + _anchor_identity_bonus
                    + _anchor_dominant_belt_bonus
                    + _anchor_flow_bonus
                    + _anchor_suitability_bonus
                    - _anchor_suitability_demote
                    + _anchor_meal_cafe_bonus
                    - _anchor_meal_cafe_demote
                    - _anchor_route_contamination_demote
                    + _anchor_editorial_bonus
                    - _anchor_editorial_demote
                    + _anchor_landmark_authority_score
                    + _anchor_external_verified_score
                    + _anchor_external_popularity_score
                    + _anchor_representative_confidence_score
                    + _anchor_family_candidate_lookup_bonus
                    - _anchor_public_data_weakness_penalty
                    - _anchor_wrong_region_alias_demote
                    - _anchor_weak_generic_authority_demote
                    + _anchor_image_bonus
                    - _anchor_no_image_demote
                    - _anchor_indoor_leisure_demote
                    - _anchor_public_facility_demote
                    + _anchor_representative_tourism_fit
                    + _anchor_busan_oldtown_family_score
                    + _anchor_busan_oldtown_support_slot_score
                    - _anchor_busan_oldtown_drift_demote
                    + _anchor_east_coast_family_score
                    + _anchor_east_coast_support_slot_score
                    - _anchor_east_coast_drift_demote
                    + _anchor_seoul_external_authority_boost
                    + _anchor_gangnam_family_score
                    + _anchor_yeouido_family_score
                    + _anchor_gangnam_candidate_depth_score
                    - _anchor_seoul_weak_lifestyle_demote
                    - _anchor_gangnam_first_place_dominance_penalty
                    - _anchor_yeouido_public_facility_final_demote
                    + _anchor_euljiro_night_family_score
                    + _anchor_gangnam_editorial_representative_score
                    + _anchor_nightlife_coherence_score
                    + _anchor_night_representative_preference
                    + _anchor_nightlife_curated_alignment
                    + _anchor_night_vibe_coherence
                    + _anchor_curated_night_support_slot
                    - _anchor_weak_editorial_first_place_demote
                    - _anchor_curated_night_weak_demote
                )
                _anchor_scores.update({
                    "inferred_belt": _anchor_belt_signal.get("inferred_belt"),
                    "belt_confidence": _anchor_belt_signal.get("belt_confidence", 0.0),
                    "belt_match_bonus": _anchor_belt_signal.get("belt_match_bonus", 0.0),
                    "belt_match_reasons": _anchor_belt_signal.get("belt_match_reasons") or [],
                    "dominant_belt": _anchor_dominant_belt_signal.get("dominant_belt"),
                    "dominant_belt_bonus": round(_anchor_dominant_belt_bonus, 4),
                    "dominant_belt_reasons": _anchor_dominant_belt_signal.get("dominant_belt_reasons") or [],
                    "inferred_flow_profile": _anchor_flow_signal.get("inferred_flow_profile"),
                    "slot_flow_alignment": _anchor_flow_signal.get("slot_flow_alignment", 0.0),
                    "continuity_bonus": round(_anchor_flow_bonus, 4),
                    "flow_match_reasons": _anchor_flow_signal.get("flow_match_reasons") or [],
                    "suitability_profile": _anchor_suitability_signal.get("suitability_profile"),
                    "vibe_suitability_score": _anchor_suitability_signal.get("vibe_suitability_score", 0.0),
                    "tourism_suitability_score": _anchor_suitability_signal.get("tourism_suitability_score", 0.0),
                    "suitability_bonus": round(_anchor_suitability_bonus, 4),
                    "suitability_soft_demote": round(_anchor_suitability_demote, 4),
                    "vibe_match_reasons": _anchor_suitability_signal.get("vibe_match_reasons") or [],
                    "soft_demote_reason": _anchor_suitability_signal.get("soft_demote_reason"),
                    "meal_cafe_profile": _anchor_meal_cafe_signal.get("meal_cafe_profile"),
                    "meal_vibe_score": _anchor_meal_cafe_signal.get("meal_vibe_score", 0.0),
                    "meal_experience_score": _anchor_meal_cafe_signal.get("meal_experience_score", 0.0),
                    "meal_soft_demote_reason": _anchor_meal_cafe_signal.get("meal_soft_demote_reason"),
                    "local_food_bonus": _anchor_meal_cafe_signal.get("local_food_bonus", 0.0),
                    "view_bonus": _anchor_meal_cafe_signal.get("view_bonus", 0.0),
                    "meal_cafe_bonus": round(_anchor_meal_cafe_bonus, 4),
                    "meal_cafe_soft_demote": round(_anchor_meal_cafe_demote, 4),
                    "meal_cafe_match_reasons": _anchor_meal_cafe_signal.get("meal_cafe_match_reasons") or [],
                    "route_contamination_demote": round(_anchor_route_contamination_demote, 4),
                    "route_contamination_flags": _anchor_route_contamination_signal.get("route_contamination_flags") or [],
                    "route_contamination_reasons": _anchor_route_contamination_signal.get("route_contamination_reasons") or [],
                    "route_positive_matches": _anchor_route_contamination_signal.get("route_positive_matches") or [],
                    "religious_facility_demote": _anchor_route_contamination_signal.get("religious_facility_demote", 0.0),
                    "religious_tourism_exception": _anchor_route_contamination_signal.get("religious_tourism_exception") or [],
                    "editorial_bonus": round(_anchor_editorial_bonus, 4),
                    "editorial_demote": round(_anchor_editorial_demote, 4),
                    "editorial_demote_reason": _anchor_editorial_signal.get("editorial_demote_reason"),
                    "weak_first_place_reason": _anchor_editorial_signal.get("weak_first_place_reason"),
                    "central_drift_reason": _anchor_editorial_signal.get("central_drift_reason"),
                    "landmark_priority_score": _anchor_editorial_signal.get("landmark_priority_score", 0.0),
                    "representative_vibe_score": _anchor_editorial_signal.get("representative_vibe_score", 0.0),
                    "weak_indoor_demote": _anchor_editorial_signal.get("weak_indoor_demote", 0.0),
                    "landmark_alignment_reason": _anchor_editorial_signal.get("landmark_alignment_reason"),
                    "seongsu_vibe_score": _anchor_editorial_signal.get("seongsu_vibe_score", 0.0),
                    "cafe_street_alignment": _anchor_editorial_signal.get("cafe_street_alignment", 0.0),
                    "weak_meal_demote": _anchor_editorial_signal.get("weak_meal_demote", 0.0),
                    "editorial_first_place_bonus": _anchor_editorial_signal.get("editorial_first_place_bonus", 0.0),
                    "euljiro_night_score": _anchor_editorial_signal.get("euljiro_night_score", 0.0),
                    "hipjiro_alignment": _anchor_editorial_signal.get("hipjiro_alignment", 0.0),
                    "central_drift_demote": _anchor_editorial_signal.get("central_drift_demote", 0.0),
                    "night_vibe_bonus": _anchor_editorial_signal.get("night_vibe_bonus", 0.0),
                    "seoul_date_score": _anchor_editorial_signal.get("seoul_date_score", 0.0),
                    "date_vibe_alignment": _anchor_editorial_signal.get("date_vibe_alignment", 0.0),
                    "broad_seoul_drift_demote": _anchor_editorial_signal.get("broad_seoul_drift_demote", 0.0),
                    "romantic_walk_bonus": _anchor_editorial_signal.get("romantic_walk_bonus", 0.0),
                    "busan_night_meal_score": _anchor_editorial_signal.get("busan_night_meal_score", 0.0),
                    "waterfront_alignment": _anchor_editorial_signal.get("waterfront_alignment", 0.0),
                    "weak_daytime_meal_demote": _anchor_editorial_signal.get("weak_daytime_meal_demote", 0.0),
                    "night_meal_bonus": _anchor_editorial_signal.get("night_meal_bonus", 0.0),
                    "busan_landmark_priority_score": _anchor_editorial_signal.get("busan_landmark_priority_score", 0.0),
                    "busan_representative_bonus": _anchor_editorial_signal.get("busan_representative_bonus", 0.0),
                    "busan_landmark_alignment_reason": _anchor_editorial_signal.get("busan_landmark_alignment_reason"),
                    "representative_tourism_family_score": max(
                        float(_anchor_editorial_signal.get("representative_tourism_family_score") or 0.0),
                        float(_anchor_landmark_authority_signal.get("representative_tourism_family_score") or 0.0),
                    ),
                    "indoor_culture_fallback_demote": max(
                        float(_anchor_editorial_signal.get("indoor_culture_fallback_demote") or 0.0),
                        float(_anchor_landmark_authority_signal.get("indoor_culture_fallback_demote") or 0.0),
                    ),
                    "regional_landmark_density": max(
                        float(_anchor_editorial_signal.get("regional_landmark_density") or 0.0),
                        float(_anchor_landmark_authority_signal.get("regional_landmark_density") or 0.0),
                    ),
                    "first_place_representative_bonus": max(
                        float(_anchor_editorial_signal.get("first_place_representative_bonus") or 0.0),
                        float(_anchor_landmark_authority_signal.get("first_place_representative_bonus") or 0.0),
                    ),
                    "jinju_history_first_place_bonus": _anchor_editorial_signal.get("jinju_history_first_place_bonus", 0.0),
                    "tongyeong_same_city_bonus": _anchor_editorial_signal.get("tongyeong_same_city_bonus", 0.0),
                    "tongyeong_geoje_drift_demote": _anchor_editorial_signal.get("tongyeong_geoje_drift_demote", 0.0),
                    "gimhae_gaya_family_score": _anchor_editorial_signal.get("gimhae_gaya_family_score", 0.0),
                    "weak_museum_first_place_demote": _anchor_editorial_signal.get("weak_museum_first_place_demote", 0.0),
                    "landmark_authority_score": round(_anchor_landmark_authority_score, 4),
                    "popularity_signal": _anchor_landmark_authority_signal.get("popularity_signal", 0.0),
                    "popularity_authority_score": _anchor_landmark_authority_signal.get("popularity_authority_score", 0.0),
                    "landmark_confidence": _anchor_landmark_authority_signal.get("landmark_confidence", 0.0),
                    "representative_tourism_bonus": _anchor_landmark_authority_signal.get("representative_tourism_bonus", 0.0),
                    "tourism_representative_score": _anchor_landmark_authority_signal.get("tourism_representative_score", 0.0),
                    "normalized_popularity_hint": _anchor_landmark_authority_signal.get("normalized_popularity_hint", 0.0),
                    "image_density_score": _anchor_landmark_authority_signal.get("image_density_score", 0.0),
                    "review_density_hint": _anchor_landmark_authority_signal.get("review_density_hint", 0.0),
                    "landmark_authority_matches": _anchor_landmark_authority_signal.get("landmark_authority_matches") or [],
                    "landmark_authority_reason": _anchor_landmark_authority_signal.get("landmark_authority_reason"),
                    "landmark_authority_source_policy": _anchor_landmark_authority_signal.get("landmark_authority_source_policy"),
                    "alias_normalization_match": _anchor_landmark_authority_signal.get("alias_normalization_match") or [],
                    "region_aware_alias_guard": _anchor_landmark_authority_signal.get("region_aware_alias_guard"),
                    "wrong_region_alias_demote": round(_anchor_wrong_region_alias_demote, 4),
                    "family_candidate_lookup_bonus": round(_anchor_family_candidate_lookup_bonus, 4),
                    "representative_alias_pool_included": bool(_anchor_landmark_authority_signal.get("representative_alias_pool_included")),
                    "weak_generic_authority_demote": round(_anchor_weak_generic_authority_demote, 4),
                    "weak_generic_authority_reason": _anchor_landmark_authority_signal.get("weak_generic_authority_reason"),
                    "public_facility_demote": round(_anchor_public_facility_demote, 4),
                    "representative_tourism_fit": round(_anchor_representative_tourism_fit, 4),
                    "weak_public_facility_reason": _anchor_public_facility_signal.get("weak_public_facility_reason"),
                    "busan_oldtown_family_score": round(_anchor_busan_oldtown_family_score, 4),
                    "busan_oldtown_pool_included": bool(_anchor_busan_oldtown_signal.get("busan_oldtown_pool_included")),
                    "busan_oldtown_drift_demote": round(_anchor_busan_oldtown_drift_demote, 4),
                    "busan_oldtown_support_slot_score": round(_anchor_busan_oldtown_support_slot_score, 4),
                    "busan_oldtown_expected_landmark_visible": bool(_anchor_busan_oldtown_signal.get("busan_oldtown_expected_landmark_visible")),
                    "busan_oldtown_match_terms": _anchor_busan_oldtown_signal.get("busan_oldtown_match_terms") or [],
                    "exact_landmark_visibility_score": round(_anchor_exact_landmark_visibility_score, 4),
                    "exact_landmark_pool_included": bool(_anchor_exact_landmark_signal.get("exact_landmark_pool_included")),
                    "exact_landmark_support_slot_bonus": round(_anchor_exact_landmark_support_slot_bonus, 4),
                    "exact_support_slot_visibility_bonus": round(
                        float(_anchor_exact_landmark_signal.get("exact_support_slot_visibility_bonus") or _anchor_exact_landmark_support_slot_bonus),
                        4,
                    ),
                    "exact_support_slot_replacement_applied": False,
                    "exact_landmark_final_route_visible": bool(_anchor_exact_landmark_signal.get("exact_landmark_pool_included")),
                    "oldtown_candidate_replaced": None,
                    "support_slot_visibility_reason": (
                        "exact_landmark_pool_included"
                        if _anchor_exact_landmark_signal.get("exact_landmark_pool_included")
                        else _anchor_exact_landmark_signal.get("exact_landmark_missing_reason")
                    ),
                    "exact_landmark_missing_reason": _anchor_exact_landmark_signal.get("exact_landmark_missing_reason"),
                    "weak_substitute_demote": round(_anchor_weak_substitute_demote, 4),
                    "exact_landmark_match_terms": _anchor_exact_landmark_signal.get("exact_landmark_match_terms") or [],
                    "exact_landmark_focus_match_terms": _anchor_exact_landmark_signal.get("exact_landmark_focus_match_terms") or [],
                    "busan_east_coast_family_score": round(_anchor_east_coast_family_score, 4),
                    "east_coast_family_preserved": bool(_anchor_east_coast_signal.get("east_coast_family_preserved")),
                    "haeundae_gwangan_drift_demote": round(_anchor_east_coast_drift_demote, 4),
                    "east_coast_support_slot_score": round(_anchor_east_coast_support_slot_score, 4),
                    "east_coast_expected_landmark_visible": bool(_anchor_east_coast_signal.get("east_coast_expected_landmark_visible")),
                    "east_coast_match_terms": _anchor_east_coast_signal.get("east_coast_match_terms") or [],
                    "seoul_external_authority_boost": round(_anchor_seoul_external_authority_boost, 4),
                    "gangnam_family_score": round(_anchor_gangnam_family_score, 4),
                    "yeouido_family_score": round(_anchor_yeouido_family_score, 4),
                    "seoul_weak_lifestyle_demote": round(_anchor_seoul_weak_lifestyle_demote, 4),
                    "seoul_family_pool_included": bool(_anchor_seoul_family_signal.get("seoul_family_pool_included")),
                    "seoul_family_match_terms": _anchor_seoul_family_signal.get("seoul_family_match_terms") or [],
                    "gangnam_candidate_depth_score": round(_anchor_gangnam_candidate_depth_score, 4),
                    "gangnam_representative_pool_included": bool(_anchor_seoul_family_signal.get("gangnam_representative_pool_included")),
                    "gangnam_first_place_dominance_penalty": round(_anchor_gangnam_first_place_dominance_penalty, 4),
                    "yeouido_public_facility_final_demote": round(_anchor_yeouido_public_facility_final_demote, 4),
                    "family_candidate_depth_before_after": _anchor_seoul_family_signal.get("family_candidate_depth_before_after"),
                    "euljiro_night_family_score": round(_anchor_euljiro_night_family_score, 4),
                    "euljiro_nightlife_pool_included": bool(_anchor_seoul_family_signal.get("euljiro_nightlife_pool_included")),
                    "gangnam_editorial_representative_score": round(_anchor_gangnam_editorial_representative_score, 4),
                    "weak_editorial_first_place_demote": round(_anchor_weak_editorial_first_place_demote, 4),
                    "nightlife_coherence_score": round(_anchor_nightlife_coherence_score, 4),
                    "curated_night_family_applied": bool(_anchor_curated_night_signal.get("curated_night_family_applied")),
                    "night_representative_preference": round(_anchor_night_representative_preference, 4),
                    "nightlife_curated_alignment": round(_anchor_nightlife_curated_alignment, 4),
                    "night_vibe_coherence": round(_anchor_night_vibe_coherence, 4),
                    "curated_night_support_slot": round(_anchor_curated_night_support_slot, 4),
                    "curated_night_match_terms": _anchor_curated_night_signal.get("curated_night_match_terms") or [],
                    "curated_night_weak_demote": round(_anchor_curated_night_weak_demote, 4),
                    "image_available": bool(_anchor_image_signal.get("image_available")),
                    "image_quality_bonus": round(_anchor_image_bonus, 4),
                    "no_image_first_place_demote": round(_anchor_no_image_demote, 4),
                    "placeholder_used": not bool(_anchor_image_signal.get("image_available")),
                    "indoor_leisure_demote": round(_anchor_indoor_leisure_demote, 4),
                    "indoor_leisure_reason": _anchor_indoor_leisure_signal.get("indoor_leisure_reason"),
                    "first_place_replacement_applied": True,
                    "first_place_replaced": first_place_replacement_event["first_place_replaced"],
                    "first_place_coherence_delta": first_place_replacement_event["first_place_coherence_delta"],
                    "final_score": round(_anchor_final_score, 4),
                })
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
    late_scoring_context = bool(
        request.get("late_user_selected_mode")
        or request.get("night_late_safe_relaxed_mode")
        or request.get("night_friendly_mode")
    )
    late_scoring_minute = _parse_start_minute(start_time) if late_scoring_context else None

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
        region2_hint_codes = _infer_region2_codes_for_intent(candidates, intended_city)

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
                intended_city=intended_city, query_region_1=query_region_1,
                selected_anchor=selected_anchor_token_set or selected_anchor,
                selected_anchor_coord=zone_center,
                region2_code_hints=region2_hint_codes,
                region_identity=region_identity_debug,
                flow_profile=flow_profile_debug,
                previous_place=selected[-1] if selected else None,
                default_preset_mode=default_preset_mode,
                selected_anchor_family=selected_anchor_family,
                late_context=late_scoring_context,
                late_current_minute=late_scoring_minute,
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
                        intended_city=intended_city, query_region_1=query_region_1,
                        selected_anchor=selected_anchor_token_set or selected_anchor,
                        selected_anchor_coord=zone_center,
                        region2_code_hints=region2_hint_codes,
                        region_identity=region_identity_debug,
                        flow_profile=flow_profile_debug,
                        previous_place=selected[-1] if selected else None,
                        default_preset_mode=default_preset_mode,
                        selected_anchor_family=selected_anchor_family,
                        late_context=late_scoring_context,
                        late_current_minute=late_scoring_minute,
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
        trace_rejected_candidates_count += max(0, len(candidates) - len(scored))
        trace_wrong_city_demote_count += sum(1 for item in scored if item[3].get("wrong_city_demote", 0.0) > 0)
        trace_locality_bonus_count += sum(1 for item in scored if item[3].get("locality_bonus", 0.0) > 0)
        trace_belt_match_count += sum(1 for item in scored if item[3].get("belt_match_bonus", 0.0) > 0)
        trace_wrong_belt_match_count += sum(1 for item in scored if item[3].get("wrong_belt_match"))
        trace_continuity_bonus_count += sum(1 for item in scored if item[3].get("continuity_bonus", 0.0) > 0)
        trace_flow_break_count += sum(1 for item in scored if item[3].get("flow_break_candidate"))
        trace_suitability_bonus_count += sum(1 for item in scored if item[3].get("suitability_bonus", 0.0) > 0)
        trace_suitability_soft_demote_count += sum(1 for item in scored if item[3].get("suitability_soft_demote", 0.0) > 0)
        trace_meal_cafe_bonus_count += sum(1 for item in scored if item[3].get("meal_cafe_bonus", 0.0) > 0)
        trace_meal_cafe_soft_demote_count += sum(1 for item in scored if item[3].get("meal_cafe_soft_demote", 0.0) > 0)
        trace_route_contamination_count += sum(1 for item in scored if item[3].get("route_contamination_demote", 0.0) > 0)
        trace_night_operating_confidence_count += sum(1 for item in scored if item[3].get("night_operating_confidence", 0.0) > 0)
        trace_indoor_night_confidence_demote_count += sum(1 for item in scored if item[3].get("indoor_night_confidence_demote", 0.0) > 0)
        trace_night_safe_outdoor_priority_count += sum(1 for item in scored if item[3].get("night_safe_outdoor_priority", 0.0) > 0)
        trace_nightlife_suitability_alignment_count += sum(1 for item in scored if item[3].get("nightlife_suitability_alignment", 0.0) > 0)
        trace_indoor_heavy_route_detected_count += sum(1 for item in scored if item[3].get("indoor_heavy_route_detected"))
        trace_operating_hours_known_closed_count += sum(1 for item in scored if item[3].get("operating_hours_known_closed"))
        trace_night_indoor_strong_demote_count += sum(1 for item in scored if item[3].get("night_indoor_strong_demote", 0.0) > 0)
        trace_relaxed_unknown_hours_allowed_count += sum(1 for item in scored if item[3].get("relaxed_unknown_hours_allowed"))
        trace_known_closed_removed_count += sum(1 for item in scored if item[3].get("known_closed_removed"))
        trace_night_safe_indoor_exception_count += sum(1 for item in scored if item[3].get("night_safe_indoor_exception"))
        trace_indoor_semantic_detected_count += sum(1 for item in scored if item[3].get("indoor_semantic_detected"))
        trace_known_closed_indoor_removed_count += sum(1 for item in scored if item[3].get("known_closed_indoor_removed"))
        trace_night_indoor_semantic_demote_count += sum(1 for item in scored if item[3].get("night_indoor_semantic_demote", 0.0) > 0)
        trace_indoor_closing_time_applied_count += sum(1 for item in scored if item[3].get("indoor_closing_time_applied"))
        trace_curated_night_family_applied_count += sum(1 for item in scored if item[3].get("curated_night_family_applied"))
        trace_night_representative_preference_count += sum(1 for item in scored if item[3].get("night_representative_preference", 0.0) > 0)
        trace_nightlife_curated_alignment_count += sum(1 for item in scored if item[3].get("nightlife_curated_alignment", 0.0) > 0)
        trace_night_vibe_coherence_count += sum(1 for item in scored if item[3].get("night_vibe_coherence", 0.0) > 0)
        trace_curated_night_support_slot_count += sum(1 for item in scored if item[3].get("curated_night_support_slot", 0.0) > 0)
        trace_curated_representative_priority_count += sum(1 for item in scored if item[3].get("curated_representative_priority", 0.0) > 0)
        trace_verified_api_candidate_count += sum(1 for item in scored if item[3].get("verified_api_candidate"))
        trace_public_fallback_used_count += sum(1 for item in scored if item[3].get("public_fallback_used"))
        trace_weak_public_contamination_demote_count += sum(1 for item in scored if item[3].get("weak_public_contamination_demote", 0.0) > 0)
        trace_curated_support_slot_alignment_count += sum(1 for item in scored if item[3].get("curated_support_slot_alignment", 0.0) > 0)
        trace_seoul_curated_district_priority_count += sum(1 for item in scored if item[3].get("seoul_curated_district_priority", 0.0) > 0)
        trace_broad_seoul_demoted_count += sum(1 for item in scored if item[3].get("broad_seoul_demoted", 0.0) > 0)
        trace_district_identity_alignment_count += sum(1 for item in scored if item[3].get("district_identity_alignment", 0.0) > 0)
        trace_support_slot_role_diversity_count += sum(1 for item in scored if item[3].get("support_slot_role_diversity", 0.0) > 0)
        trace_cross_flow_candidate_count += sum(
            1
            for item in scored
            if {"flow_contamination", "meal_flow_mismatch"} & set(item[3].get("route_contamination_flags") or [])
        )
        trace_lifestyle_mismatch_count += sum(
            1
            for item in scored
            if {"lifestyle_contamination", "generic_commerce_mismatch"} & set(item[3].get("route_contamination_flags") or [])
        )

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
                        intended_city=intended_city, query_region_1=query_region_1,
                        selected_anchor=selected_anchor_token_set or selected_anchor,
                        selected_anchor_coord=zone_center,
                        region2_code_hints=region2_hint_codes,
                        region_identity=region_identity_debug,
                        flow_profile=flow_profile_debug,
                        previous_place=selected[-1] if selected else None,
                        default_preset_mode=default_preset_mode,
                        selected_anchor_family=selected_anchor_family,
                        late_context=late_scoring_context,
                        late_current_minute=late_scoring_minute,
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
                        intended_city=intended_city, query_region_1=query_region_1,
                        selected_anchor=selected_anchor_token_set or selected_anchor,
                        selected_anchor_coord=zone_center,
                        region2_code_hints=region2_hint_codes,
                        region_identity=region_identity_debug,
                        flow_profile=flow_profile_debug,
                        previous_place=selected[-1] if selected else None,
                        default_preset_mode=default_preset_mode,
                        selected_anchor_family=selected_anchor_family,
                        late_context=late_scoring_context,
                        late_current_minute=late_scoring_minute,
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
                            intended_city=intended_city, query_region_1=query_region_1,
                            selected_anchor=selected_anchor_token_set or selected_anchor,
                            selected_anchor_coord=zone_center,
                            region2_code_hints=region2_hint_codes,
                            region_identity=region_identity_debug,
                            flow_profile=flow_profile_debug,
                            previous_place=selected[-1] if selected else None,
                            default_preset_mode=default_preset_mode,
                            selected_anchor_family=selected_anchor_family,
                            late_context=late_scoring_context,
                            late_current_minute=late_scoring_minute,
                        )
                        if result is not None:
                            s, travel_min, dist_km, components = result
                            scored.append((s, travel_min, dist_km, components, p))
                if not scored:
                    skips_since_last += 1
                    continue
                fallback_info = {"triggered": True, "reason": "slot_anchor_radius_fallback"}

        scored.sort(
            key=lambda x: (
                x[0],
                x[3].get("candidate_belt_affinity", 0.0),
                x[3].get("continuity_bonus", 0.0),
                x[3].get("slot_flow_alignment", 0.0),
                x[3].get("city_intent_score", 0.0),
                x[3].get("city_anchor_distance_score", 0.0),
                -x[1],
                -x[2],
            ),
            reverse=True,
        )
        if late_scoring_context:
            non_closed_scored = [
                item for item in scored
                if not item[3].get("operating_hours_known_closed")
                and not (
                    late_scoring_minute is not None
                    and (lambda close: close is not None and late_scoring_minute >= close)(
                        _extract_known_close_min(item[4])[0]
                    )
                )
            ]
            if non_closed_scored:
                closed_ids = {
                    item[4]["place_id"] for item in scored
                    if item[3].get("operating_hours_known_closed")
                    or (
                        late_scoring_minute is not None
                        and (lambda close: close is not None and late_scoring_minute >= close)(
                            _extract_known_close_min(item[4])[0]
                        )
                    )
                }
                scored = non_closed_scored
                if closed_ids:
                    tier1_scored = [item for item in tier1_scored if item[4]["place_id"] not in closed_ids]
                    tier2_scored = [item for item in tier2_scored if item[4]["place_id"] not in closed_ids]

        # ── Req 1: Tier 기반 가중치 선택 (이동 시간 페널티 포함, 확정 픽 없음) ──────
        if tier1_scored and not fallback_info:
            tier1_scored.sort(
                key=lambda x: (
                    x[0],
                    x[3].get("candidate_belt_affinity", 0.0),
                    x[3].get("continuity_bonus", 0.0),
                    x[3].get("slot_flow_alignment", 0.0),
                    x[3].get("locality_bonus", 0.0),
                    -x[3].get("wrong_city_demote", 0.0),
                    x[3].get("city_intent_score", 0.0),
                    x[3].get("city_anchor_distance_score", 0.0),
                    -x[1],
                    -x[2],
                ),
                reverse=True,
            )
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
        _, travel_min, dist_km, components, chosen = _maybe_replace_with_exact_support_landmark(
            (components.get("final_score", 0.0), travel_min, dist_km, components, chosen),
            scored,
            slot_name=slot,
        )
        _, travel_min, dist_km, components, chosen = _maybe_replace_with_support_slot_family_candidate(
            (components.get("final_score", 0.0), travel_min, dist_km, components, chosen),
            scored,
            slot_name=slot,
        )
        _, travel_min, dist_km, components, chosen = _maybe_replace_contaminated_choice(
            (components.get("final_score", 0.0), travel_min, dist_km, components, chosen),
            scored,
            slot_name=slot,
        )

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

    relaxed_night_mode = bool(request.get("night_late_safe_relaxed_mode") or request.get("night_friendly_mode"))
    late_user_selected_mode = bool(request.get("late_user_selected_mode"))
    late_relaxed_mode = bool(relaxed_night_mode or late_user_selected_mode)
    if late_relaxed_mode and selected:
        relaxed_start_hour = _parse_start_hour(start_time)
        compact_duration_limit = 30 if relaxed_start_hour is not None and relaxed_start_hour >= 22 else 45
        for place in selected:
            original_duration = place.get("estimated_duration") or 60
            place["_night_late_safe_original_duration"] = original_duration
            place["estimated_duration"] = min(original_duration, compact_duration_limit)
        request["night_safe_candidate_preserved"] = True
        request["nightlife_support_slot_fallback"] = len(selected) >= 2
        if late_user_selected_mode:
            request["night_support_slot_preserved"] = len(selected) >= 2
            request["short_course_prevented"] = len(selected) >= 2

    # Step 3. 시간표 생성
    schedule = _build_schedule(selected, start_min_override=start_min_override)

    # Step 4. 22:00 초과 제거. 야간/야경 의도가 명확한 요청은 24:00까지 compact route를 허용한다.
    start_hour_for_limit = _parse_start_hour(start_time)
    late_user_limit = min((start_hour_for_limit or 18) * 60 + 210, 24 * 60)
    end_hour_limit = late_user_limit if late_user_selected_mode else (24 * 60 if relaxed_night_mode else END_HOUR_LIMIT)
    if late_relaxed_mode:
        request["relaxed_operating_hour_filter"] = True
        request["strict_closed_filter_skipped"] = True
        request["night_safe_candidate_preserved"] = True
        request["nightlife_support_slot_fallback"] = True
        if late_user_selected_mode:
            request["late_cutoff_relaxed"] = True
    final = []
    for entry in schedule:
        h, m    = map(int, entry["scheduled_end"].split(":"))
        end_min = h * 60 + m
        if end_min > end_hour_limit:
            logger.warning("%s 초과로 '%s' 제외", "24:00" if relaxed_night_mode else "22:00", entry["name"])
            break
        final.append(entry)
    description_quality_summary = _summarize_description_quality(final)

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

    course_belt_coherence = summarize_course_belt_coherence(
        selected[:len(final)],
        region_identity_debug,
    )
    route_coherence = summarize_route_coherence(
        selected[:len(final)],
        region_identity_debug,
        flow_profile_debug,
    )
    inferred_belt = (
        region_identity_debug.get("inferred_belt")
        if isinstance(region_identity_debug, dict) else None
    )
    dominant_belt = course_belt_coherence.get("dominant_belt") or inferred_belt
    broad_candidates = (
        region_identity_debug.get("broad_region_belt_candidates")
        if isinstance(region_identity_debug, dict) else []
    ) or []
    belt_candidate_scores = [
        {
            "belt": candidate.get("belt"),
            "priority": candidate.get("priority"),
            "selected_as_inferred": candidate.get("belt") == inferred_belt,
            "selected_as_course_dominant": candidate.get("belt") == dominant_belt,
        }
        for candidate in broad_candidates
    ]
    route_level_warnings = []
    if inferred_belt and dominant_belt and inferred_belt != dominant_belt:
        route_level_warnings.append({
            "warning_type": "inferred_belt_course_dominant_mismatch",
            "inferred_belt": inferred_belt,
            "course_dominant_belt": dominant_belt,
        })
    cross_belt_transition_count = int(course_belt_coherence.get("cross_belt_candidate_count") or 0)
    dominant_district = (
        seoul_district_vibe_debug.get("dominant_district")
        if isinstance(seoul_district_vibe_debug, dict) else None
    )
    district_candidate_scores = (
        seoul_district_vibe_debug.get("district_candidate_scores")
        if isinstance(seoul_district_vibe_debug, dict) else []
    ) or []
    cross_district_transition_count = cross_belt_transition_count if dominant_district else 0
    route_level_warnings.extend(
        {
            "warning_type": "route_contamination",
            "place_name": flag.get("place_name"),
            "flags": flag.get("flags") or [],
            "reasons": flag.get("reasons") or [],
        }
        for flag in (route_coherence.get("contamination_flags") or [])
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
        "region":               region_original,
        "target_place_count":   len(slots),
        "actual_place_count":   len(final),
        "dropped_slots":        dropped_slots,
        "total_duration_min":   total_dur,
        "total_travel_min":     total_travel,
        "selected_radius_km":   eff_max_radius,
        "tier1_max_radius_km":  tier1_max_radius,
        "selection_basis":      {"weights": weights, "mode": "default_preset" if default_preset_mode else ("theme" if themes else "default")},
        "time_bucket":          time_bucket,
        "night_friendly_mode":  bool(request.get("night_friendly_mode")),
        "night_late_safe_relaxed_mode": bool(request.get("night_late_safe_relaxed_mode")),
        "relaxed_operating_hour_filter": bool(request.get("relaxed_operating_hour_filter")),
        "night_safe_candidate_preserved": bool(request.get("night_safe_candidate_preserved")),
        "nightlife_support_slot_fallback": bool(request.get("nightlife_support_slot_fallback")),
        "strict_closed_filter_skipped": bool(request.get("strict_closed_filter_skipped")),
        "late_user_selected_mode": bool(request.get("late_user_selected_mode")),
        "intentional_late_schedule": bool(request.get("intentional_late_schedule")),
        "late_cutoff_relaxed": bool(request.get("late_cutoff_relaxed")),
        "night_support_slot_preserved": bool(request.get("night_support_slot_preserved")),
        "short_course_prevented": bool(request.get("short_course_prevented")),
        "night_operating_confidence": trace_night_operating_confidence_count,
        "indoor_night_confidence_demote": trace_indoor_night_confidence_demote_count,
        "night_safe_outdoor_priority": trace_night_safe_outdoor_priority_count,
        "nightlife_suitability_alignment": trace_nightlife_suitability_alignment_count,
        "indoor_heavy_route_detected": trace_indoor_heavy_route_detected_count,
        "operating_hours_known_closed": trace_operating_hours_known_closed_count,
        "night_indoor_strong_demote": trace_night_indoor_strong_demote_count,
        "relaxed_unknown_hours_allowed": trace_relaxed_unknown_hours_allowed_count,
        "known_closed_removed": trace_known_closed_removed_count,
        "night_safe_indoor_exception": trace_night_safe_indoor_exception_count,
        "indoor_semantic_detected": trace_indoor_semantic_detected_count,
        "known_closed_indoor_removed": trace_known_closed_indoor_removed_count,
        "night_indoor_semantic_demote": trace_night_indoor_semantic_demote_count,
        "indoor_closing_time_applied": trace_indoor_closing_time_applied_count,
        "curated_night_family_applied": trace_curated_night_family_applied_count,
        "night_representative_preference": trace_night_representative_preference_count,
        "nightlife_curated_alignment": trace_nightlife_curated_alignment_count,
        "night_vibe_coherence": trace_night_vibe_coherence_count,
        "curated_night_support_slot": trace_curated_night_support_slot_count,
        "curated_representative_priority": trace_curated_representative_priority_count,
        "verified_api_candidate": trace_verified_api_candidate_count,
        "public_fallback_used": trace_public_fallback_used_count,
        "weak_public_contamination_demote": trace_weak_public_contamination_demote_count,
        "curated_support_slot_alignment": trace_curated_support_slot_alignment_count,
        "seoul_curated_district_priority": trace_seoul_curated_district_priority_count,
        "broad_seoul_demoted": trace_broad_seoul_demoted_count,
        "district_identity_alignment": trace_district_identity_alignment_count,
        "support_slot_role_diversity": trace_support_slot_role_diversity_count,
        "euljiro_mood_label_applied": bool(request.get("euljiro_mood_label_applied")),
        "euljiro_night_mode_removed": bool(request.get("euljiro_night_mode_removed")),
        "night_friendly_time_policy": request.get("night_friendly_time_policy") if isinstance(request, dict) else None,
        "fallback_mode":        "late_user_selected_mode" if request.get("late_user_selected_mode") else ("night_friendly_mode" if request.get("night_friendly_mode") else ("evening_safe_mode" if time_bucket == "evening" else None)),
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
        "selected_anchor_normalized": selected_anchor_debug if selected_anchor else None,
        "region_identity_layer": region_identity_debug,
        "course_belt_coherence": course_belt_coherence,
        "course_flow_profile": flow_profile_debug,
        "route_coherence": route_coherence,
        "description":          _build_description(region, themes, city_cluster),
        "missing_slot_reason":  missing_slot_reason,
        "option_notice":        _option_notice,
        "recommendation_trace": build_recommendation_trace(
            request_id=request_id,
            region=region,
            selected_anchor_raw=selected_anchor,
            selected_anchor_normalized=selected_anchor_debug if selected_anchor else None,
            top_candidate_city_distribution=trace_top_candidate_city_distribution,
            selected_places=[
                {
                    "place_id": p.get("place_id"),
                    "place_name": p.get("name"),
                    "city_token": infer_city_token(p),
                    "visit_role": p.get("visit_role"),
                    "category": p.get("category"),
                    "category_name": p.get("category_name"),
                    "description": p.get("description"),
                }
                for p in final
            ],
            rejected_candidates_count=trace_rejected_candidates_count,
            wrong_city_demote_applied_count=trace_wrong_city_demote_count,
            locality_bonus_applied_count=trace_locality_bonus_count,
            belt_match_applied_count=trace_belt_match_count,
            wrong_belt_match_count=trace_wrong_belt_match_count,
            continuity_bonus_applied_count=trace_continuity_bonus_count,
            flow_break_candidate_count=trace_flow_break_count,
            suitability_bonus_applied_count=trace_suitability_bonus_count,
            suitability_soft_demote_count=trace_suitability_soft_demote_count,
            meal_cafe_bonus_applied_count=trace_meal_cafe_bonus_count,
            meal_cafe_soft_demote_count=trace_meal_cafe_soft_demote_count,
            route_contamination_applied_count=trace_route_contamination_count,
            night_late_safe_relaxed_mode=bool(request.get("night_late_safe_relaxed_mode")),
            relaxed_operating_hour_filter=bool(request.get("relaxed_operating_hour_filter")),
            night_safe_candidate_preserved=bool(request.get("night_safe_candidate_preserved")),
            nightlife_support_slot_fallback=bool(request.get("nightlife_support_slot_fallback")),
            strict_closed_filter_skipped=bool(request.get("strict_closed_filter_skipped")),
            late_user_selected_mode=bool(request.get("late_user_selected_mode")),
            intentional_late_schedule=bool(request.get("intentional_late_schedule")),
            late_cutoff_relaxed=bool(request.get("late_cutoff_relaxed")),
            night_support_slot_preserved=bool(request.get("night_support_slot_preserved")),
            short_course_prevented=bool(request.get("short_course_prevented")),
            night_operating_confidence=trace_night_operating_confidence_count,
            indoor_night_confidence_demote=trace_indoor_night_confidence_demote_count,
            night_safe_outdoor_priority=trace_night_safe_outdoor_priority_count,
            nightlife_suitability_alignment=trace_nightlife_suitability_alignment_count,
            indoor_heavy_route_detected=trace_indoor_heavy_route_detected_count,
            operating_hours_known_closed=trace_operating_hours_known_closed_count,
            night_indoor_strong_demote=trace_night_indoor_strong_demote_count,
            relaxed_unknown_hours_allowed=trace_relaxed_unknown_hours_allowed_count,
            known_closed_removed=trace_known_closed_removed_count,
            night_safe_indoor_exception=trace_night_safe_indoor_exception_count,
            indoor_semantic_detected=trace_indoor_semantic_detected_count,
            known_closed_indoor_removed=trace_known_closed_indoor_removed_count,
            night_indoor_semantic_demote=trace_night_indoor_semantic_demote_count,
            indoor_closing_time_applied=trace_indoor_closing_time_applied_count,
            curated_night_family_applied=trace_curated_night_family_applied_count,
            night_representative_preference=trace_night_representative_preference_count,
            nightlife_curated_alignment=trace_nightlife_curated_alignment_count,
            night_vibe_coherence=trace_night_vibe_coherence_count,
            curated_night_support_slot=trace_curated_night_support_slot_count,
            curated_representative_priority=trace_curated_representative_priority_count,
            verified_api_candidate=trace_verified_api_candidate_count,
            public_fallback_used=trace_public_fallback_used_count,
            weak_public_contamination_demote=trace_weak_public_contamination_demote_count,
            curated_support_slot_alignment=trace_curated_support_slot_alignment_count,
            seoul_curated_district_priority=trace_seoul_curated_district_priority_count,
            broad_seoul_demoted=trace_broad_seoul_demoted_count,
            district_identity_alignment=trace_district_identity_alignment_count,
            support_slot_role_diversity=trace_support_slot_role_diversity_count,
            euljiro_mood_label_applied=bool(request.get("euljiro_mood_label_applied")),
            euljiro_night_mode_removed=bool(request.get("euljiro_night_mode_removed")),
            default_preset_mode=default_preset_mode,
            representative_landmark_selected=bool(_anchor_scores.get("representative_landmark_selected")),
            representative_pool_size=int(_anchor_scores.get("representative_pool_size") or 1),
            weird_candidate_demote=float(_anchor_scores.get("weird_candidate_demote") or 0.0),
            regenerate_diversity_applied=bool(_anchor_scores.get("regenerate_diversity_applied")),
            representative_family_pool_size=int(_anchor_scores.get("representative_family_pool_size") or 0),
            representative_family_rotation_bonus=float(_anchor_scores.get("representative_family_rotation_bonus") or 0.0),
            representative_family_saturation_penalty=float(_anchor_scores.get("representative_family_saturation_penalty") or 0.0),
            representative_family_first_place_repeat=int(_anchor_scores.get("representative_family_first_place_repeat") or 0),
            representative_family_diversity_applied=bool(_anchor_scores.get("representative_family_diversity_applied")),
            regenerate_repeat_penalty=float(_anchor_scores.get("representative_family_saturation_penalty") or _anchor_scores.get("first_place_saturation_penalty") or 0.0),
            representative_family_rotation_applied=bool(_anchor_scores.get("representative_family_diversity_applied")),
            description_quality_variant=description_quality_summary.get("description_quality_variant"),
            generic_copy_demote=float(description_quality_summary.get("generic_copy_demote") or 0.0),
            selected_anchor_family_id=_anchor_scores.get("selected_anchor_family_id"),
            selected_anchor_family_match_score=float(_anchor_scores.get("selected_anchor_family_match_score") or 0.0),
            selected_anchor_family_preserved=bool(_anchor_scores.get("selected_anchor_family_preserved")),
            selected_anchor_family_drift_demote=float(_anchor_scores.get("selected_anchor_family_drift_demote") or 0.0),
            selected_anchor_drift_reason=_anchor_scores.get("selected_anchor_drift_reason"),
            fallback_level_used=_anchor_scores.get("fallback_level_used"),
            cross_flow_candidate_count=route_coherence.get("cross_flow_candidate_count", trace_cross_flow_candidate_count),
            lifestyle_mismatch_count=route_coherence.get("lifestyle_mismatch_count", trace_lifestyle_mismatch_count),
            first_anchor_reason=first_anchor_reason,
            first_anchor_vibe_match=first_anchor_vibe_match,
            first_anchor_candidate_scores=anchor.get("_first_anchor_candidate_scores") or [],
            first_anchor_belt_match=anchor.get("_first_anchor_belt_match") or {},
            first_anchor_contamination=anchor.get("_first_anchor_contamination") or {},
            first_anchor_replacement_attempted=bool(anchor.get("_first_anchor_replacement_attempted")),
            first_place_replacement=first_place_replacement_event,
            broad_region_belt_candidates=broad_candidates,
            inferred_belt_confidence=(
                region_identity_debug.get("belt_confidence")
                if isinstance(region_identity_debug, dict) else None
            ),
            dominant_belt_reason={
                "dominant_belt": dominant_belt,
                "inferred_belt": inferred_belt,
                "reason": "assembled_course_belt_distribution",
            },
            belt_candidate_scores=belt_candidate_scores,
            cross_belt_transition_count=cross_belt_transition_count,
            dominant_district=dominant_district,
            district_candidate_scores=district_candidate_scores,
            cross_district_transition_count=cross_district_transition_count,
            district_vibe_reason=(
                seoul_district_vibe_debug.get("district_vibe_reason")
                if isinstance(seoul_district_vibe_debug, dict) else {}
            ),
            route_level_warnings=route_level_warnings,
            replacement_events=trace_replacement_events,
            unsuitable_block_counts=trace_unsuitable_block_counts,
            candidate_samples=trace_candidate_samples[:20],
            region_identity=region_identity_debug,
            course_belt_coherence=course_belt_coherence,
            flow_profile=flow_profile_debug,
            route_coherence=route_coherence,
        ),
        "places":               final,
    }

