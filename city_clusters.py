"""
서울/대도심 city_mode 클러스터 정의 및 슬롯 구성.
기존 belt_mode와 완전 분리 — course_builder.py 에서만 import.
"""

CITY_CLUSTERS: dict[str, list[dict]] = {
    "서울": [
        {"name": "홍대·합정",     "center": (37.5579, 126.9235), "mood": ["카페", "인디", "젊음"]},
        {"name": "성수·건대",     "center": (37.5445, 127.0558), "mood": ["카페", "힙", "예술"]},
        {"name": "이태원·한남",   "center": (37.5347, 126.9940), "mood": ["이국적", "힙", "문화"]},
        {"name": "강남·선릉",     "center": (37.5042, 127.0490), "mood": ["세련", "쇼핑", "비즈니스"]},
        {"name": "명동·을지로",   "center": (37.5637, 126.9825), "mood": ["쇼핑", "도심", "문화"]},
        {"name": "종로·광화문",   "center": (37.5714, 126.9764), "mood": ["역사", "문화", "전통"]},
        {"name": "잠실·송파",     "center": (37.5133, 127.1001), "mood": ["가족", "쇼핑", "엔터"]},
        {"name": "여의도·마포",   "center": (37.5245, 126.9211), "mood": ["공원", "한강", "힐링"]},
        {"name": "신촌·연남",     "center": (37.5570, 126.9368), "mood": ["카페", "젊음", "거리"]},
        {"name": "을지로·충무로", "center": (37.5659, 126.9878), "mood": ["힙", "인쇄", "문화"]},
    ],
}

CITY_MODE_REGIONS: set[str] = {"서울"}

# theme 키워드 → 연관 클러스터 mood 키워드 (영문/한글 theme 모두 지원)
THEME_TO_CLUSTER_MOOD: dict[str, list[str]] = {
    "자연":    ["한강", "공원", "힐링"],
    "힐링":    ["한강", "공원", "힐링"],
    "카페":    ["카페", "인디", "젊음"],
    "역사":    ["역사", "문화", "전통"],
    "문화":    ["문화", "예술", "힙"],
    "쇼핑":    ["쇼핑", "도심", "비즈니스"],
    "nature":  ["한강", "공원", "힐링"],
    "history": ["역사", "문화", "전통"],
    "urban":   ["힙", "이국적", "예술"],
    "food":    ["도심", "쇼핑", "비즈니스"],
    "cafe":    ["카페", "인디", "젊음"],
    "walk":    ["공원", "한강", "거리"],
}

# city_mode 전용 슬롯 — cafe 선발, 짧은 도보권 코스 흐름
CITY_MODE_SLOTS: dict[str, list] = {
    "light": [
        ("morning",   "cafe"),
        ("lunch",     "meal"),
        ("afternoon", ["spot", "culture"]),
    ],
    "standard": [
        ("morning",        "cafe"),
        ("morning_2",      ["spot", "culture"]),
        ("lunch",          "meal"),
        ("afternoon",      ["spot", "culture"]),
        ("afternoon_cafe", "cafe"),
    ],
    "full": [
        ("morning",        "cafe"),
        ("morning_2",      ["spot", "culture"]),
        ("lunch",          "meal"),
        ("afternoon",      ["spot", "culture"]),
        ("afternoon_cafe", "cafe"),
        ("dinner",         "meal"),
    ],
}

# cafe 테마 전용 city_mode 슬롯 — morning_2에 cafe 허용하여 cafe ≥ 3 유도
# CITY_MODE_SLOTS와 슬롯 수·순서 동일, morning_2 허용 role만 확장
CITY_MODE_CAFE_SLOTS: dict[str, list] = {
    "light": [
        ("morning",   "cafe"),
        ("lunch",     "meal"),
        ("afternoon", ["cafe", "spot", "culture"]),
    ],
    "standard": [
        ("morning",        "cafe"),
        ("morning_2",      ["cafe", "spot", "culture"]),
        ("lunch",          "meal"),
        ("afternoon",      ["spot", "culture"]),
        ("afternoon_cafe", "cafe"),
    ],
    "full": [
        ("morning",        "cafe"),
        ("morning_2",      ["cafe", "spot", "culture"]),
        ("lunch",          "meal"),
        ("afternoon",      ["spot", "culture"]),
        ("afternoon_cafe", "cafe"),
        ("dinner",         "meal"),
    ],
}

# food 테마 전용 city_mode 슬롯 — afternoon_cafe에 meal 허용하여 meal ≥ 2 유도
# CITY_MODE_SLOTS와 슬롯 수·순서 동일, afternoon_cafe 허용 role만 확장
CITY_MODE_FOOD_SLOTS: dict[str, list] = {
    "light": [
        ("morning",   "cafe"),
        ("lunch",     "meal"),
        ("afternoon", ["spot", "culture"]),
    ],
    "standard": [
        ("morning",        "cafe"),
        ("morning_2",      ["spot", "culture"]),
        ("lunch",          "meal"),
        ("afternoon",      ["spot", "culture"]),
        ("afternoon_cafe", ["meal", "cafe"]),
    ],
    "full": [
        ("morning",        "cafe"),
        ("morning_2",      ["spot", "culture"]),
        ("lunch",          "meal"),
        ("afternoon",      ["spot", "culture"]),
        ("afternoon_cafe", ["meal", "cafe"]),
        ("dinner",         "meal"),
    ],
}
