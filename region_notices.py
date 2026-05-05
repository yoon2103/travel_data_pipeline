"""
region_notices.py — 지역·옵션별 품질 안내 문구 및 서비스 레벨

QA 결과 기반으로 관리. 코스 생성 로직과 무관.

구조:
  REGION_SERVICE_LEVEL : region_1 → "FULL" | "LIMITED" | "BLOCKED"
  REGION_OPTION_NOTICE : (region_1, theme) → 문구  (테마 특화 안내)
  REGION_NOTICE        : region_1 → 문구           (테마 무관 지역 수준 안내)

서비스 레벨:
  FULL    : 정상 서비스 (PASS율 80%+, FAIL 없거나 산발적)
  LIMITED : 안내 포함 서비스 (FAIL 존재, 데이터 부족 고지 필요)
  BLOCKED : 코스 생성 제한 (PASS 0~8%, 전 옵션 FAIL)

우선순위 (안내 문구): REGION_OPTION_NOTICE > REGION_NOTICE > None (표시 없음)

QA 기준일: 2026-05-03 (전지역 204케이스, PASS=152 WEAK=27 FAIL=25)
"""

# ── 서비스 레벨 ──────────────────────────────────────────────────────────────
# QA 기준: FULL=PASS율 80%+, LIMITED=FAIL 존재 but 일부 옵션 서비스 가능, BLOCKED=서비스 불가
REGION_SERVICE_LEVEL: dict[str, str] = {
    # FULL: 정상 서비스
    "서울":  "FULL",
    "부산":  "FULL",
    "대구":  "FULL",
    "광주":  "FULL",
    "세종":  "FULL",
    "울산":  "FULL",
    "경북":  "FULL",
    "충남":  "FULL",
    "제주":  "FULL",
    "대전":  "FULL",
    "전북":  "FULL",
    "강원":  "FULL",
    # LIMITED: 안내 포함 서비스
    "경기":  "LIMITED",
    "인천":  "LIMITED",
    "전남":  "LIMITED",
    # BLOCKED: 코스 생성 제한
    "경남":  "BLOCKED",
    "충북":  "BLOCKED",
}

_BLOCKED_MESSAGE = "현재 해당 지역은 추천 코스를 제공하기 어렵습니다. 더 많은 지역 데이터를 확보한 후 서비스를 열 예정입니다."


def get_service_level(region: str) -> str:
    """지역 서비스 레벨 반환. 미등록 지역은 FULL 처리."""
    return REGION_SERVICE_LEVEL.get(region, "FULL")


def get_blocked_message() -> str:
    return _BLOCKED_MESSAGE


# ── 테마 특화 안내 ────────────────────────────────────────────────────────────
# (region_1, theme) → 사용자 안내 문구
# theme: "walk" | "cafe" | "nature" | "food" | "history" | "urban" | "healing"
REGION_OPTION_NOTICE: dict[tuple[str, str], str] = {

    # 충남 (태안 등 해안 단일축): 카페가 특정 구간에 집중
    ("충남", "cafe"):    "이 지역은 카페 후보가 일부 구간에 몰려 있어, 동선이 자연스러운 카페 위주로 구성됩니다.",
    ("충남", "nature"):  "이 지역은 자연 명소 중심 코스로 구성되며, 카페·편의시설이 일부 제한될 수 있습니다.",
    ("충남", "walk"):    "이 지역은 자연 명소 중심 코스로 구성되며, 카페·편의시설이 일부 제한될 수 있습니다.",

    # 강원: 외곽 자연 앵커 선택 시 주변 편의시설 부족
    ("강원", "cafe"):    "이 지역은 카페가 일부 지역에 집중되어 있어, 카페 구성이 제한될 수 있습니다.",
    ("강원", "nature"):  "일부 외곽 자연 명소는 주변 편의시설이 적어 코스가 짧아질 수 있습니다.",

    # 경기: 광역 지역, 앵커 선택에 따라 코스 편차 발생
    ("경기", "walk"):    "이 지역은 넓은 광역 지역이라 선택된 거점에 따라 코스 구성에 차이가 있을 수 있습니다.",
    ("경기", "nature"):  "이 지역은 넓은 광역 지역이라 선택된 거점에 따라 코스 구성에 차이가 있을 수 있습니다.",
    ("경기", "cafe"):    "이 지역은 카페가 일부 권역에 집중되어 있어, 거점에 따라 카페 위주 코스 구성이 제한될 수 있습니다.",
    ("경기", "food"):    "이 지역은 음식점이 특정 권역에 집중되어 있어, 거점에 따라 다양한 맛집 코스 구성이 어려울 수 있습니다.",

    # 전북: 맛집 데이터 부족
    ("전북", "food"):    "이 지역은 음식점 데이터가 충분하지 않아 맛집 코스가 간소화될 수 있습니다.",
}

# ── 지역 수준 안내 (테마 무관, 데이터 부족 지역) ─────────────────────────────
# FAIL 빈발 지역 — 장소 데이터 부족으로 슬롯 채우기 실패 발생
REGION_NOTICE: dict[str, str] = {
    "경기": "이 지역은 넓은 광역 지역이라 선택된 거점에 따라 코스 구성에 차이가 있을 수 있습니다.",
    "경남": "이 지역은 장소 데이터가 충분하지 않아 일부 코스는 간소화된 형태로 제공될 수 있습니다.",
    "전남": "이 지역은 장소 데이터가 충분하지 않아 일부 코스는 간소화된 형태로 제공될 수 있습니다.",
    "인천": "이 지역은 장소 데이터가 충분하지 않아 일부 코스는 간소화된 형태로 제공될 수 있습니다.",
    "충북": "이 지역은 장소 데이터가 충분하지 않아 일부 코스는 간소화된 형태로 제공될 수 있습니다.",
}


def get_option_notice(region: str, themes: list) -> str | None:
    """
    region + themes 조합에 해당하는 안내 문구를 반환. 없으면 None.

    우선순위:
      1. REGION_OPTION_NOTICE[(region, theme)] — 테마 특화 안내
      2. REGION_NOTICE[region]                 — 지역 수준 데이터 부족 안내
      3. None                                  — 표시 없음
    """
    for theme in themes:
        notice = REGION_OPTION_NOTICE.get((region, theme))
        if notice:
            return notice
    return REGION_NOTICE.get(region)
