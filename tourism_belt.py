"""
tourism_belt.py — 지방/관광지형 지역 핵심 장소 시드

관광벨트는 코스를 고정하는 것이 아니라 후보 우선순위 보정 시드입니다.
엔진의 hard filter/scoring은 유지되며, 벨트 부스트는 소폭의 가중치 가산입니다.

## 벨트 구조 원칙
- 시드는 반드시 단일 POI (내비게이션 목적지로 설정 가능한 명확한 1개 장소)
- 광역 행정구역명 (예: "안면도", "태안", "강릉") 불가
- 각 벨트 내 시드 간 최대 직선거리 ≤ 40km (당일치기 동선)
- 벨트당 4~6개 유지
- 시드 간 관광 축(해변/사찰/자연/문화 등) 혼합 필수

## 광역 지역 → 서브벨트 분기
region_1이 "강원"인 경우, 장소 좌표 기준으로 '강릉' 또는 '속초' 서브벨트를 자동 선택.
엔진은 region="강원"으로 호출 → REGION_TO_BELT_KEYS로 서브벨트 탐색.
"""

import re
from math import atan2, cos, radians, sin, sqrt

# ---------------------------------------------------------------------------
# 광역 지역 → 서브벨트 매핑
# ---------------------------------------------------------------------------
# 값이 1개: 해당 키를 직접 사용
# 값이 2개+: 장소 좌표와 가장 가까운 서브벨트 자동 선택
REGION_TO_BELT_KEYS: dict[str, list[str]] = {
    "충남": ["충남"],
    "강원": ["강릉", "속초"],   # 출발/장소 좌표로 자동 분기
    "경북": ["경북"],
}

# ---------------------------------------------------------------------------
# 관광벨트 시드 데이터
# ---------------------------------------------------------------------------
# 각 시드: {name, lat, lon, boost}
# boost: score 가산값 (0.0~0.20)
# 이름은 places 테이블 name 컬럼과 정확히 일치 (DB 실존 확인 완료)
# ---------------------------------------------------------------------------

TOURISM_BELT: dict[str, list[dict]] = {

    # ===== 충남 — 태안/안면도 해안권 =====
    # span: 꽃지(남)~만리포(북) 직선 35km
    "충남": [
        {"name": "꽃지해수욕장",    "lat": 36.4094, "lon": 126.3263, "boost": 0.15},  # 해변/낙조 대표
        {"name": "백사장항",        "lat": 36.4481, "lon": 126.3313, "boost": 0.14},  # 항구/어시장
        {"name": "안면암(태안)",    "lat": 36.5594, "lon": 126.3750, "boost": 0.13},  # 사찰/일출
        {"name": "안면도수목원",    "lat": 36.4231, "lon": 126.3490, "boost": 0.12},  # 자연/수목
        {"name": "간월도마을",      "lat": 36.6193, "lon": 126.4227, "boost": 0.11},  # 어촌마을
        {"name": "만리포해수욕장",  "lat": 36.7167, "lon": 126.2333, "boost": 0.12},  # 해변(북태안)
    ],

    # ===== 강릉 — 강릉 도심·해안 =====
    # span: 정동진(동남)~구룡폭포(서북) 직선 33km
    "강릉": [
        {"name": "정동진",              "lat": 37.6914, "lon": 129.0326, "boost": 0.14},  # 해변/일출 명소
        {"name": "강릉 굴산사지",       "lat": 37.7073, "lon": 128.8918, "boost": 0.12},  # 역사/불교유산
        {"name": "경포호수광장",        "lat": 37.7978, "lon": 128.9095, "boost": 0.13},  # 자연/호수
        {"name": "강릉올림픽뮤지엄",    "lat": 37.7794, "lon": 128.8971, "boost": 0.12},  # 현대문화/박물관
        {"name": "구룡폭포(소금강)",    "lat": 37.8027, "lon": 128.6835, "boost": 0.13},  # 자연/계곡·폭포
    ],

    # ===== 속초 — 속초·설악·양양 =====
    # span: 낙산사(남)~설악산케이블카(서) 직선 13km (타이트 클러스터)
    "속초": [
        {"name": "속초해수욕장",        "lat": 38.1906, "lon": 128.6020, "boost": 0.13},  # 해변
        {"name": "설악산 케이블카",     "lat": 38.1732, "lon": 128.4892, "boost": 0.15},  # 산/자연
        {"name": "아바이마을",          "lat": 38.2007, "lon": 128.5949, "boost": 0.12},  # 전통마을
        {"name": "대포항",              "lat": 38.1750, "lon": 128.6075, "boost": 0.11},  # 항구/어시장
        {"name": "낙산사",              "lat": 38.1249, "lon": 128.6274, "boost": 0.14},  # 사찰(양양)
        {"name": "국립산악박물관",      "lat": 38.2026, "lon": 128.5405, "boost": 0.11},  # 문화/박물관
    ],

    # ===== 경북 — 경주 역사문화권 =====
    # span: 첨성대(도심)~문무대왕릉(동해) 직선 27km
    "경북": [
        {"name": "경주 첨성대",                      "lat": 35.8344, "lon": 129.2186, "boost": 0.15},  # 신라 천문대
        {"name": "천마총(대릉원)",                   "lat": 35.8387, "lon": 129.2105, "boost": 0.15},  # 고분군
        {"name": "경주 동궁과 월지",                 "lat": 35.8352, "lon": 129.2284, "boost": 0.14},  # 야경 명소
        {"name": "경주 석굴암 [유네스코 세계유산]",  "lat": 35.7894, "lon": 129.3508, "boost": 0.15},  # UNESCO 사찰
        {"name": "국립경주박물관 신라천년서고",       "lat": 35.8293, "lon": 129.2269, "boost": 0.12},  # 박물관
        {"name": "경주 문무대왕릉",                  "lat": 35.7381, "lon": 129.4868, "boost": 0.13},  # 해상왕릉(동해)
    ],
}

BELT_PROXIMITY_KM = 3.0
BELT_PROXIMITY_RATIO = 0.5   # proximity 부스트는 name 매칭 부스트의 최대 50%


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    la1, lo1, la2, lo2 = map(radians, [lat1, lon1, lat2, lon2])
    a = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _normalize(text: str) -> str:
    return re.sub(r"[\s\-·\(\)\.\[\],]", "", text).lower()


def _names_match(seed_norm: str, place_norm: str) -> bool:
    """
    시드명 ↔ 장소명 매칭 판정.
    - 시드명이 장소명 안에 포함되면 True (예: '꽃지해수욕장' in '꽃지해수욕장 앞바다')
    - 장소명이 시드명 안에 포함되는 경우 길이 비율 ≥ 0.65 요구
      → '안면도'(4)/'안면도수목원'(7)=0.57 < 0.65 → False (광역명 차단)
      → '아바이마을'(5)/'아바이마을상회'(7)=0.71 ≥ 0.65 → True (축약명 허용)
    """
    if seed_norm in place_norm:
        return True
    if place_norm in seed_norm:
        return len(place_norm) / len(seed_norm) >= 0.65
    return False


def _nearest_belt_key(belt_keys: list[str], lat: float, lon: float) -> str:
    """belt_keys 중 lat/lon 좌표에 가장 가까운 서브벨트 키 반환."""
    if len(belt_keys) == 1:
        return belt_keys[0]
    best_key, best_dist = belt_keys[0], float("inf")
    for key in belt_keys:
        seeds = TOURISM_BELT.get(key, [])
        if not seeds:
            continue
        cx = sum(s["lat"] for s in seeds) / len(seeds)
        cy = sum(s["lon"] for s in seeds) / len(seeds)
        d = _haversine(lat, lon, cx, cy)
        if d < best_dist:
            best_dist = d
            best_key = key
    return best_key


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def get_belt_info(region: str, name: str, lat: float, lon: float) -> tuple[float, str | None]:
    """
    관광벨트 부스트값과 매칭된 시드 이름을 반환.

    - 광역 지역(강원 등)은 lat/lon 기준 가장 가까운 서브벨트를 자동 선택.
    - 이름 매칭: full boost / 거리 근접: partial boost

    Returns
    -------
    (boost, matched_seed_name)  — 매칭 없으면 (0.0, None)
    """
    keys = REGION_TO_BELT_KEYS.get(region, [region])
    belt_key = _nearest_belt_key(keys, lat, lon)
    belt = TOURISM_BELT.get(belt_key, [])
    if not belt:
        return 0.0, None

    n_norm = _normalize(name)
    best = 0.0
    best_seed: str | None = None

    for seed in belt:
        s_norm = _normalize(seed["name"])
        if _names_match(s_norm, n_norm):
            if seed["boost"] > best:
                best = seed["boost"]
                best_seed = seed["name"]
            continue

        dist = _haversine(lat, lon, seed["lat"], seed["lon"])
        if dist <= BELT_PROXIMITY_KM:
            ratio = 1.0 - (dist / BELT_PROXIMITY_KM)
            prox_boost = seed["boost"] * ratio * BELT_PROXIMITY_RATIO
            if prox_boost > best:
                best = prox_boost
                best_seed = f"{seed['name']}(근접 {dist:.1f}km)"

    return best, best_seed


def get_belt_boost(region: str, name: str, lat: float, lon: float) -> float:
    """get_belt_info 의 boost 값만 반환하는 하위 호환 wrapper."""
    boost, _ = get_belt_info(region, name, lat, lon)
    return boost


def is_belt_seed_name(
    region: str,
    name: str,
    lat: float | None = None,
    lon: float | None = None,
) -> bool:
    """
    이름 매칭 기준 belt_seed 여부 판별 (proximity 제외 — tier1 판별 전용).

    lat/lon 제공 시: 가장 가까운 서브벨트만 확인 (강원 → 강릉 or 속초)
    lat/lon 없음:   해당 region의 모든 서브벨트 통합 확인 (하위 호환)
    """
    keys = REGION_TO_BELT_KEYS.get(region, [region])
    if lat is not None and lon is not None:
        keys = [_nearest_belt_key(keys, lat, lon)]
    n_norm = _normalize(name)
    return any(
        any(
            _names_match(_normalize(s["name"]), n_norm)
            for s in TOURISM_BELT.get(k, [])
        )
        for k in keys
    )


def list_belt_regions() -> list[str]:
    """관광벨트가 정의된 region_1 목록 (REGION_TO_BELT_KEYS 기준)."""
    return list(REGION_TO_BELT_KEYS.keys())
