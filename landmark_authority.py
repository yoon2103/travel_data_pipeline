"""Advisory landmark authority signals for travel recommendations.

This module does not fetch external data at runtime and does not create POIs.
It provides a normalization layer and a small authority score for candidates
that already exist in the DB. External popularity/authority references are
represented as governed seed metadata and must be refreshed through approved
ingestion/audit tooling.
"""
from __future__ import annotations

import re
from typing import Any


def _norm(value: Any) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", str(value or "")).lower()


def _identity_text(place: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "name",
        "category",
        "category_name",
        "visit_role",
        "region",
        "region_1",
        "region_2",
        "address",
        "addr",
        "address_name",
        "overview",
        "description",
    ):
        value = place.get(key)
        if value:
            parts.append(str(value))
    tags = place.get("ai_tags") or {}
    if isinstance(tags, dict):
        for value in tags.values():
            if isinstance(value, list):
                parts.extend(str(v) for v in value if v)
            elif value:
                parts.append(str(value))
    return " ".join(parts)


LANDMARK_AUTHORITY_SEEDS: dict[str, list[dict[str, Any]]] = {
    "부산": [
        {
            "landmark_id": "haedong_yonggungsa",
            "canonical_name": "해동용궁사",
            "aliases": ["해동용궁사", "해동 용궁사", "용궁사", "Haedong Yonggung Temple", "Haedong Yonggungsa", "기장 용궁사"],
            "authority": 1.0,
            "belts": ["기장"],
            "themes": ["drive", "sea", "family", "history"],
            "source_policy": "official_tourism_or_verified_place_reference",
        },
        {
            "landmark_id": "gamcheon_culture_village",
            "canonical_name": "감천문화마을",
            "aliases": ["감천문화마을", "감천 문화마을", "Gamcheon Culture Village"],
            "authority": 0.92,
            "belts": ["남포"],
            "themes": ["culture", "walk", "family"],
            "source_policy": "official_tourism_or_verified_place_reference",
        },
        {
            "landmark_id": "huinnyeoul_culture_village",
            "canonical_name": "흰여울문화마을",
            "aliases": ["흰여울문화마을", "흰여울 문화마을", "Huinnyeoul Culture Village"],
            "authority": 0.88,
            "belts": ["영도"],
            "themes": ["culture", "sea", "walk"],
            "source_policy": "official_tourism_or_verified_place_reference",
        },
        {
            "landmark_id": "oryukdo",
            "canonical_name": "오륙도",
            "aliases": ["오륙도", "오륙도 스카이워크", "Oryukdo", "Oryukdo Skywalk"],
            "authority": 0.88,
            "belts": ["해운대"],
            "themes": ["sea", "walk", "family"],
            "source_policy": "official_tourism_or_verified_place_reference",
        },
        {
            "landmark_id": "gwanganri_beach",
            "canonical_name": "광안리해변",
            "aliases": ["광안리해변", "광안리해수욕장", "광안리", "광안대교", "Gwanganri Beach"],
            "authority": 0.92,
            "belts": ["광안리"],
            "themes": ["night", "sea", "date"],
            "source_policy": "official_tourism_or_verified_place_reference",
        },
        {
            "landmark_id": "taejongdae",
            "canonical_name": "태종대",
            "aliases": ["태종대", "Taejongdae"],
            "authority": 0.9,
            "belts": ["영도"],
            "themes": ["nature", "sea", "family"],
            "source_policy": "official_tourism_or_verified_place_reference",
        },
        {
            "landmark_id": "songdo_cablecar",
            "canonical_name": "송도해상케이블카",
            "aliases": ["송도해상케이블카", "송도 해상 케이블카", "Songdo Marine Cable Car"],
            "authority": 0.86,
            "belts": ["남포"],
            "themes": ["sea", "family", "date"],
            "source_policy": "official_tourism_or_verified_place_reference",
        },
        {
            "landmark_id": "dalmaji_road",
            "canonical_name": "달맞이길",
            "aliases": ["달맞이길", "달맞이고개", "달맞이동산", "Dalmaji Road"],
            "authority": 0.82,
            "belts": ["해운대"],
            "themes": ["walk", "date", "sea"],
            "source_policy": "official_tourism_or_verified_place_reference",
        },
    ],
    "서울": [
        {"landmark_id": "bukchon_hanok", "canonical_name": "북촌한옥마을", "aliases": ["북촌한옥마을", "북촌 한옥마을", "북촌", "삼청동"], "authority": 0.95, "belts": ["북촌"], "themes": ["history", "walk"]},
        {"landmark_id": "ikseon", "canonical_name": "익선동", "aliases": ["익선동", "익선동한옥거리", "익선"], "authority": 0.86, "belts": ["익선"], "themes": ["date", "cafe"]},
        {"landmark_id": "seongsu_cafe_street", "canonical_name": "성수동 카페거리", "aliases": ["성수동 카페거리", "성수카페거리", "성수동", "연무장길"], "authority": 0.86, "belts": ["성수"], "themes": ["cafe", "date"]},
        {"landmark_id": "seoul_forest", "canonical_name": "서울숲", "aliases": ["서울숲", "서울숲공원"], "authority": 0.88, "belts": ["성수"], "themes": ["walk", "family"]},
        {"landmark_id": "cheonggyecheon", "canonical_name": "청계천", "aliases": ["청계천", "청계천 야간"], "authority": 0.82, "belts": ["을지로"], "themes": ["night", "walk"]},
        {"landmark_id": "euljiro_nogari_alley", "canonical_name": "을지로 노가리골목", "aliases": ["을지로 노가리골목", "노가리골목", "을지로 노포", "힙지로 노포"], "authority": 0.78, "belts": ["을지로"], "themes": ["night", "walk", "date"]},
        {"landmark_id": "sewoon_plaza", "canonical_name": "세운상가", "aliases": ["세운상가", "세운상가 옥상", "세운상가 야경", "세운"], "authority": 0.76, "belts": ["을지로"], "themes": ["night", "walk", "city"]},
        {"landmark_id": "chungmuro_printing_alley", "canonical_name": "충무로 인쇄골목", "aliases": ["충무로 인쇄골목", "인쇄골목", "충무로 골목"], "authority": 0.72, "belts": ["을지로"], "themes": ["night", "walk", "city"]},
        {"landmark_id": "hangang_park", "canonical_name": "한강공원", "aliases": ["한강공원", "여의도한강공원", "뚝섬한강공원"], "authority": 0.82, "belts": ["한강"], "themes": ["walk", "family"]},
    ],
    "제주": [
        {"landmark_id": "seongsan_ilchulbong", "canonical_name": "성산일출봉", "aliases": ["성산일출봉", "성산 일출봉"], "authority": 1.0, "belts": ["성산"], "themes": ["nature", "sea"]},
        {"landmark_id": "hyeopjae", "canonical_name": "협재해변", "aliases": ["협재해변", "협재해수욕장", "협재"], "authority": 0.9, "belts": ["협재"], "themes": ["sea", "drive"]},
        {"landmark_id": "aewol_coastal_road", "canonical_name": "애월해안도로", "aliases": ["애월해안도로", "애월 해안도로", "애월", "한담해변"], "authority": 0.9, "belts": ["애월"], "themes": ["drive", "cafe", "sea"]},
        {"landmark_id": "osulloc", "canonical_name": "오설록", "aliases": ["오설록", "오설록 티뮤지엄", "Osulloc"], "authority": 0.84, "belts": ["중문"], "themes": ["cafe", "family"]},
        {"landmark_id": "seopjikoji", "canonical_name": "섭지코지", "aliases": ["섭지코지", "Seopjikoji"], "authority": 0.88, "belts": ["성산"], "themes": ["nature", "sea"]},
    ],
    "강원": [
        {"landmark_id": "gyeongpo_beach", "canonical_name": "경포해변", "aliases": ["경포해변", "경포대", "경포호"], "authority": 0.9, "belts": ["경포"], "themes": ["sea", "walk"]},
        {"landmark_id": "anmok_coffee", "canonical_name": "안목커피거리", "aliases": ["안목커피거리", "안목해변", "강릉 커피거리"], "authority": 0.86, "belts": ["안목"], "themes": ["cafe", "sea"]},
        {"landmark_id": "sokcho_beach", "canonical_name": "속초해수욕장", "aliases": ["속초해수욕장", "속초해변", "속초아이"], "authority": 0.86, "belts": ["속초해수욕장"], "themes": ["sea", "cafe"]},
        {"landmark_id": "yeongnang_lake", "canonical_name": "영랑호", "aliases": ["영랑호", "영랑호수윗길"], "authority": 0.82, "belts": ["영랑호"], "themes": ["walk", "cafe"]},
        {"landmark_id": "daegwallyeong_sheep_ranch", "canonical_name": "대관령양떼목장", "aliases": ["대관령양떼목장", "대관령", "삼양목장", "하늘목장", "선자령"], "authority": 0.88, "belts": ["대관령목장"], "themes": ["nature", "drive", "family"]},
        {"landmark_id": "yangyang_jukdo", "canonical_name": "죽도해변", "aliases": ["죽도해변", "인구해변", "서피비치", "양양 바다"], "authority": 0.86, "belts": ["양양해변"], "themes": ["sea", "cafe", "drive"]},
    ],
    "충북": [
        {"landmark_id": "cheongju_sangdangsanseong", "canonical_name": "상당산성", "aliases": ["상당산성", "청주 상당산성"], "authority": 0.86, "belts": ["청주도심역사"], "themes": ["history", "walk", "family"]},
        {"landmark_id": "cheongju_suamgol", "canonical_name": "수암골", "aliases": ["수암골", "청주 수암골"], "authority": 0.78, "belts": ["청주도심역사"], "themes": ["walk", "cafe", "date"]},
        {"landmark_id": "danyang_dodamsambong", "canonical_name": "도담삼봉", "aliases": ["도담삼봉", "단양 도담삼봉"], "authority": 0.92, "belts": ["단양자연"], "themes": ["nature", "drive", "family"]},
        {"landmark_id": "danyang_skywalk", "canonical_name": "만천하스카이워크", "aliases": ["만천하스카이워크", "단양 만천하스카이워크"], "authority": 0.86, "belts": ["단양자연"], "themes": ["nature", "drive", "family"]},
    ],
    "경남": [
        {"landmark_id": "gimhae_gaya_themepark", "canonical_name": "김해가야테마파크", "aliases": ["김해가야테마파크", "가야테마파크"], "authority": 0.88, "belts": ["김해가야"], "themes": ["history", "family"]},
        {"landmark_id": "gimhae_national_museum", "canonical_name": "국립김해박물관", "aliases": ["국립김해박물관", "김해박물관"], "authority": 0.86, "belts": ["김해가야"], "themes": ["history", "culture"]},
        {"landmark_id": "gimhae_suro_tomb", "canonical_name": "수로왕릉", "aliases": ["수로왕릉", "김해 수로왕릉"], "authority": 0.84, "belts": ["김해가야"], "themes": ["history", "walk"]},
    ],
}

_WEAK_AUTHORITY_MISMATCH_TERMS = (
    "온천",
    "찜질",
    "사우나",
    "모텔",
    "호텔",
    "리조트",
    "펜션",
    "주차장",
    "매표소",
    "휴게소",
)

_PHASE2_PRIORITY_LANDMARK_IDS = {
    "haedong_yonggungsa",
    "gamcheon_culture_village",
    "huinnyeoul_culture_village",
    "bukchon_hanok",
    "seongsan_ilchulbong",
    "anmok_coffee",
    "hyeopjae",
    "osulloc",
    "gwanganri_beach",
    "seoul_forest",
    "seongsu_cafe_street",
}

LANDMARK_AUTHORITY_SEEDS.setdefault("경남", []).extend([
    {"landmark_id": "jinhae_marine_park", "canonical_name": "진해해양공원", "aliases": ["진해해양공원", "진해 해양공원"], "authority": 0.86, "belts": ["창원마산해양산책"], "themes": ["sea", "family", "walk"]},
    {"landmark_id": "yeojwacheon", "canonical_name": "여좌천", "aliases": ["여좌천", "진해 여좌천", "여좌천 로망스다리"], "authority": 0.84, "belts": ["창원마산해양산책"], "themes": ["walk", "date", "nature"]},
    {"landmark_id": "gyeonghwa_station", "canonical_name": "경화역", "aliases": ["경화역", "경화역공원", "진해 경화역"], "authority": 0.83, "belts": ["창원마산해양산책"], "themes": ["walk", "family"]},
    {"landmark_id": "masan_fish_market", "canonical_name": "마산어시장", "aliases": ["마산어시장", "마산 어시장"], "authority": 0.82, "belts": ["창원마산해양산책"], "themes": ["market", "food"]},
    {"landmark_id": "jeodo_quai_bridge", "canonical_name": "저도콰이강의다리", "aliases": ["저도콰이강", "저도콰이강의다리", "콰이강의다리", "저도연륙교"], "authority": 0.82, "belts": ["창원마산해양산책"], "themes": ["sea", "walk", "drive"]},
    {"landmark_id": "junam_reservoir", "canonical_name": "주남저수지", "aliases": ["주남저수지", "창원 주남저수지"], "authority": 0.81, "belts": ["창원마산해양산책"], "themes": ["nature", "walk", "family"]},
    {"landmark_id": "dongpirang", "canonical_name": "동피랑", "aliases": ["동피랑", "동피랑마을", "통영 동피랑"], "authority": 0.9, "belts": ["통영항구동피랑", "통영동피랑"], "themes": ["sea", "walk", "date"]},
    {"landmark_id": "yisunsin_park_tongyeong", "canonical_name": "이순신공원", "aliases": ["이순신공원", "통영 이순신공원"], "authority": 0.86, "belts": ["통영항구동피랑", "통영동피랑"], "themes": ["sea", "history", "walk"]},
    {"landmark_id": "tongyeong_cable_car", "canonical_name": "통영케이블카", "aliases": ["통영케이블카", "통영 케이블카", "미륵산케이블카"], "authority": 0.88, "belts": ["통영항구동피랑", "통영미륵산"], "themes": ["sea", "family", "nature"]},
    {"landmark_id": "gangguan_harbor", "canonical_name": "강구안", "aliases": ["강구안", "강구안항", "통영 강구안"], "authority": 0.82, "belts": ["통영항구동피랑", "통영동피랑"], "themes": ["sea", "walk", "night"]},
    {"landmark_id": "dipirang", "canonical_name": "디피랑", "aliases": ["디피랑", "통영 디피랑"], "authority": 0.84, "belts": ["통영항구동피랑", "통영동피랑"], "themes": ["night", "family"]},
    {"landmark_id": "geoje_windy_hill", "canonical_name": "바람의언덕", "aliases": ["바람의언덕", "거제 바람의언덕"], "authority": 0.9, "belts": ["거제해안드라이브", "거제바람의언덕"], "themes": ["sea", "drive", "nature"]},
    {"landmark_id": "oedo_botania", "canonical_name": "외도", "aliases": ["외도", "외도보타니아", "거제 외도"], "authority": 0.88, "belts": ["거제해안드라이브", "거제바람의언덕"], "themes": ["sea", "nature", "family"]},
    {"landmark_id": "gujora_beach", "canonical_name": "구조라해수욕장", "aliases": ["구조라", "구조라해수욕장", "거제 구조라"], "authority": 0.82, "belts": ["거제해안드라이브"], "themes": ["sea", "family"]},
    {"landmark_id": "hakdong_mongdol", "canonical_name": "학동몽돌해변", "aliases": ["학동몽돌해변", "학동몽돌", "거제 학동몽돌"], "authority": 0.84, "belts": ["거제해안드라이브"], "themes": ["sea", "drive"]},
    {"landmark_id": "namhae_german_village", "canonical_name": "남해독일마을", "aliases": ["남해독일마을", "독일마을"], "authority": 0.9, "belts": ["남해해안감성", "남해독일마을"], "themes": ["sea", "date", "walk"]},
    {"landmark_id": "daraengi_village", "canonical_name": "다랭이마을", "aliases": ["다랭이마을", "남해 다랭이마을"], "authority": 0.86, "belts": ["남해해안감성", "남해독일마을"], "themes": ["sea", "walk", "nature"]},
    {"landmark_id": "boriam", "canonical_name": "보리암", "aliases": ["보리암", "남해 보리암"], "authority": 0.86, "belts": ["남해해안감성", "남해독일마을"], "themes": ["nature", "history", "sea"]},
    {"landmark_id": "jinju_fortress", "canonical_name": "진주성", "aliases": ["진주성", "진주 진주성"], "authority": 0.9, "belts": ["진주남강역사"], "themes": ["history", "walk", "family"]},
    {"landmark_id": "namgang", "canonical_name": "남강", "aliases": ["남강", "진주 남강"], "authority": 0.82, "belts": ["진주남강역사"], "themes": ["walk", "night"]},
    {"landmark_id": "chokseoknu", "canonical_name": "촉석루", "aliases": ["촉석루", "진주 촉석루"], "authority": 0.87, "belts": ["진주남강역사"], "themes": ["history", "walk"]},
    {"landmark_id": "daeseongdong_tombs", "canonical_name": "대성동고분군", "aliases": ["대성동고분군", "김해 대성동고분군"], "authority": 0.84, "belts": ["김해가야"], "themes": ["history", "walk"]},
])

_PHASE2_PRIORITY_LANDMARK_IDS.update({
    "jinhae_marine_park",
    "yeojwacheon",
    "gyeonghwa_station",
    "masan_fish_market",
    "jeodo_quai_bridge",
    "junam_reservoir",
    "dongpirang",
    "yisunsin_park_tongyeong",
    "tongyeong_cable_car",
    "gangguan_harbor",
    "dipirang",
    "geoje_windy_hill",
    "oedo_botania",
    "gujora_beach",
    "hakdong_mongdol",
    "namhae_german_village",
    "daraengi_village",
    "boriam",
    "jinju_fortress",
    "namgang",
    "chokseoknu",
    "gimhae_gaya_themepark",
    "gimhae_national_museum",
    "gimhae_suro_tomb",
    "daeseongdong_tombs",
})

LANDMARK_AUTHORITY_SEEDS.setdefault("부산", []).extend([
    {"landmark_id": "gamcheon_culture_village_ko", "canonical_name": "감천문화마을", "aliases": ["감천문화마을", "감천 문화마을", "Gamcheon Culture Village"], "authority": 0.92, "belts": ["남포"], "themes": ["culture", "walk", "family"]},
    {"landmark_id": "biff_square", "canonical_name": "BIFF광장", "aliases": ["BIFF광장", "비프광장", "BIFF", "부산 BIFF광장", "BIFF Square"], "authority": 0.86, "belts": ["남포"], "themes": ["walk", "market", "family"]},
    {"landmark_id": "minrak_waterfront_park", "canonical_name": "민락수변공원", "aliases": ["민락수변공원", "민락 수변공원", "민락", "민락수변", "Millak Waterfront Park"], "authority": 0.84, "belts": ["광안리"], "themes": ["night", "sea", "walk"]},
    {"landmark_id": "jagalchi_market", "canonical_name": "자갈치시장", "aliases": ["자갈치시장", "자갈치", "Jagalchi Market"], "authority": 0.88, "belts": ["남포"], "themes": ["market", "food", "walk"]},
    {"landmark_id": "huinnyeoul_culture_village_ko", "canonical_name": "흰여울문화마을", "aliases": ["흰여울문화마을", "흰여울", "Huinnyeoul Culture Village"], "authority": 0.88, "belts": ["영도", "남포"], "themes": ["sea", "walk", "date"]},
    {"landmark_id": "songdo_cablecar_ko", "canonical_name": "부산 송도해상케이블카", "aliases": ["부산 송도해상케이블카", "송도해상케이블카", "송도 케이블카"], "authority": 0.9, "belts": ["남포"], "themes": ["sea", "family", "date"]},
    {"landmark_id": "yongdusan_park", "canonical_name": "용두산공원", "aliases": ["용두산공원", "용두산", "부산타워", "Yongdusan Park"], "authority": 0.86, "belts": ["남포"], "themes": ["walk", "history", "family"]},
    {"landmark_id": "gukje_market", "canonical_name": "국제시장", "aliases": ["국제시장", "부산국제시장", "Gukje Market"], "authority": 0.86, "belts": ["남포"], "themes": ["market", "food", "walk"]},
    {"landmark_id": "kkangkangi_art_village", "canonical_name": "깡깡이예술마을", "aliases": ["깡깡이예술마을", "깡깡이 예술마을", "Kangkangee Arts Village"], "authority": 0.82, "belts": ["남포", "영도"], "themes": ["culture", "walk", "sea"]},
    {"landmark_id": "songdo_beach_busan", "canonical_name": "부산 송도해수욕장", "aliases": ["송도해수욕장", "부산 송도해수욕장", "송도해변", "Songdo Beach"], "authority": 0.84, "belts": ["남포"], "themes": ["sea", "walk", "family"]},
    {"landmark_id": "huinnyeoul_coastal_tunnel", "canonical_name": "영도 흰여울해안터널", "aliases": ["흰여울해안터널", "영도 흰여울해안터널", "흰여울문화마을", "흰여울"], "authority": 0.84, "belts": ["영도", "남포"], "themes": ["sea", "walk", "date"]},
    {"landmark_id": "songjeong_beach_busan", "canonical_name": "송정해수욕장", "aliases": ["송정해수욕장", "송정", "부산 송정해수욕장", "Songjeong Beach"], "authority": 0.86, "belts": ["기장"], "themes": ["sea", "drive", "family"]},
    {"landmark_id": "osiria", "canonical_name": "오시리아", "aliases": ["오시리아", "오시리아관광단지", "Osiria"], "authority": 0.82, "belts": ["기장"], "themes": ["drive", "family"]},
    {"landmark_id": "jukseong_church", "canonical_name": "죽성성당", "aliases": ["죽성성당", "드림성당", "기장 죽성성당"], "authority": 0.8, "belts": ["기장"], "themes": ["sea", "drive", "date"]},
    {"landmark_id": "cheongsapo", "canonical_name": "청사포", "aliases": ["청사포", "청사포다릿돌전망대", "청사포 해변열차"], "authority": 0.82, "belts": ["기장", "해운대"], "themes": ["sea", "drive", "walk"]},
    {"landmark_id": "gijang_coastal_road", "canonical_name": "기장해안도로", "aliases": ["기장해안도로", "기장 해안도로", "기장해안", "기장 카페거리", "기장카페거리"], "authority": 0.8, "belts": ["기장"], "themes": ["sea", "drive", "cafe"]},
])

LANDMARK_AUTHORITY_SEEDS.setdefault("서울", []).extend([
    {"landmark_id": "gyeongbokgung", "canonical_name": "경복궁", "aliases": ["경복궁", "경복궁 동측", "Gyeongbokgung"], "authority": 0.94, "belts": ["북촌", "광화문"], "themes": ["history", "walk", "family"]},
    {"landmark_id": "samcheongdong_gil", "canonical_name": "삼청동길", "aliases": ["삼청동길", "삼청동", "삼청", "Samcheongdong-gil"], "authority": 0.84, "belts": ["북촌"], "themes": ["walk", "cafe", "date"]},
    {"landmark_id": "coex", "canonical_name": "코엑스", "aliases": ["코엑스", "COEX", "무역센터", "스타필드 코엑스"], "authority": 0.86, "belts": ["강남"], "themes": ["city", "family", "date"]},
    {"landmark_id": "starfield_library", "canonical_name": "별마당도서관", "aliases": ["별마당도서관", "별마당 도서관", "스타필드 별마당"], "authority": 0.84, "belts": ["강남"], "themes": ["city", "date", "family"]},
    {"landmark_id": "bongeunsa", "canonical_name": "봉은사", "aliases": ["봉은사", "Bongeunsa"], "authority": 0.82, "belts": ["강남"], "themes": ["history", "walk"]},
    {"landmark_id": "seonjeongneung", "canonical_name": "선정릉", "aliases": ["선정릉", "선릉과 정릉", "선릉", "정릉"], "authority": 0.8, "belts": ["강남"], "themes": ["history", "walk"]},
    {"landmark_id": "garosu_gil", "canonical_name": "가로수길", "aliases": ["가로수길", "신사동 가로수길", "Sinsa Garosu-gil", "Garosu-gil"], "authority": 0.8, "belts": ["강남"], "themes": ["cafe", "date", "walk"]},
    {"landmark_id": "apgujeong_cheongdam", "canonical_name": "압구정/청담", "aliases": ["압구정", "청담", "도산공원", "청담동"], "authority": 0.76, "belts": ["강남"], "themes": ["date", "cafe", "city"]},
    {"landmark_id": "namsan_seoul", "canonical_name": "남산", "aliases": ["남산", "남산서울타워", "N서울타워", "Namsan Seoul Tower"], "authority": 0.86, "belts": ["명동"], "themes": ["night", "walk", "family"]},
    {"landmark_id": "yeouido_hangang_park", "canonical_name": "여의도한강공원", "aliases": ["여의도한강공원", "여의도 한강공원", "한강공원", "Hangang Park"], "authority": 0.86, "belts": ["여의도", "한강"], "themes": ["walk", "family", "date"]},
    {"landmark_id": "the_hyundai_seoul", "canonical_name": "더현대서울", "aliases": ["더현대서울", "더현대", "The Hyundai Seoul"], "authority": 0.82, "belts": ["여의도"], "themes": ["city", "date", "family"]},
    {"landmark_id": "ifc_mall", "canonical_name": "IFC몰", "aliases": ["IFC몰", "IFC", "아이에프씨몰"], "authority": 0.78, "belts": ["여의도"], "themes": ["city", "family"]},
    {"landmark_id": "yeouido_park", "canonical_name": "여의도공원", "aliases": ["여의도공원", "여의도 공원"], "authority": 0.8, "belts": ["여의도"], "themes": ["walk", "family"]},
    {"landmark_id": "saetgang_ecological_park", "canonical_name": "샛강생태공원", "aliases": ["샛강생태공원", "샛강", "여의도샛강"], "authority": 0.76, "belts": ["여의도"], "themes": ["walk", "nature"]},
    {"landmark_id": "building_63", "canonical_name": "63빌딩", "aliases": ["63빌딩", "63스퀘어", "63아트", "63 Square"], "authority": 0.78, "belts": ["여의도"], "themes": ["view", "family", "city"]},
])

LANDMARK_AUTHORITY_SEEDS.setdefault("전북", []).extend([
    {"landmark_id": "gyeonggijeon", "canonical_name": "경기전", "aliases": ["경기전", "전주 경기전", "Gyeonggijeon"], "authority": 0.92, "belts": ["전주한옥마을"], "themes": ["history", "walk", "family"]},
    {"landmark_id": "jeondong_cathedral", "canonical_name": "전동성당", "aliases": ["전동성당", "전주 전동성당", "Jeondong Cathedral"], "authority": 0.88, "belts": ["전주한옥마을"], "themes": ["history", "walk", "date"]},
    {"landmark_id": "omokdae", "canonical_name": "오목대", "aliases": ["오목대", "오목대와 이목대", "전주 오목대"], "authority": 0.88, "belts": ["전주한옥마을"], "themes": ["history", "walk"]},
    {"landmark_id": "jeonju_nambu_market", "canonical_name": "남부시장", "aliases": ["남부시장", "전주남부시장", "전주 남부시장", "Nambu Market"], "authority": 0.84, "belts": ["전주한옥마을"], "themes": ["market", "food", "history"]},
    {"landmark_id": "jeonju_hyanggyo", "canonical_name": "전주향교", "aliases": ["전주향교", "전주 향교"], "authority": 0.86, "belts": ["전주한옥마을"], "themes": ["history", "walk"]},
    {"landmark_id": "jeonju_fan_culture_center", "canonical_name": "전주부채문화관", "aliases": ["전주부채문화관", "부채문화관"], "authority": 0.82, "belts": ["전주한옥마을"], "themes": ["history", "culture", "walk"]},
])

LANDMARK_AUTHORITY_SEEDS.setdefault("경남", []).extend([
    {"landmark_id": "gimhae_suro_tomb_alias", "canonical_name": "수로왕릉", "aliases": ["수로왕릉", "김해 수로왕릉", "수로왕릉역", "Tomb of King Suro"], "authority": 0.84, "belts": ["김해가야"], "themes": ["history", "walk"]},
    {"landmark_id": "daeseongdong_tombs_alias", "canonical_name": "대성동고분군", "aliases": ["대성동고분군", "대성동 고분군", "대성동고분박물관", "김해 대성동고분군"], "authority": 0.84, "belts": ["김해가야"], "themes": ["history", "walk"]},
])

_PHASE2_PRIORITY_LANDMARK_IDS.update({
    "biff_square",
    "minrak_waterfront_park",
    "jagalchi_market",
    "yongdusan_park",
    "gukje_market",
    "kkangkangi_art_village",
    "songdo_beach_busan",
    "huinnyeoul_coastal_tunnel",
    "songjeong_beach_busan",
    "osiria",
    "jukseong_church",
    "cheongsapo",
    "gijang_coastal_road",
    "gyeongbokgung",
    "samcheongdong_gil",
    "coex",
    "starfield_library",
    "bongeunsa",
    "seonjeongneung",
    "garosu_gil",
    "apgujeong_cheongdam",
    "namsan_seoul",
    "yeouido_hangang_park",
    "the_hyundai_seoul",
    "ifc_mall",
    "yeouido_park",
    "saetgang_ecological_park",
    "building_63",
    "jeondong_cathedral",
    "jeonju_nambu_market",
    "gimhae_suro_tomb_alias",
    "daeseongdong_tombs_alias",
})

_WEAK_GENERIC_REPRESENTATIVE_TERMS = (
    "문화센터",
    "교육문화",
    "교육관",
    "복지관",
    "센터",
    "회관",
    "오피스",
    "상가",
    "빌딩",
    "사옥",
    "주민센터",
    "교육청",
    "체육센터",
    "수영장",
    "찜질",
    "사우나",
)

_EXTERNAL_VERIFIED_SOURCE_TERMS = (
    "naver", "kakao", "google", "tourapi", "visitbusan", "official", "busan_tourism",
)

_WEAK_GENERIC_REPRESENTATIVE_TERMS = _WEAK_GENERIC_REPRESENTATIVE_TERMS + (
    "도립미술관",
    "시립미술관",
    "미술관",
    "성산아트홀",
    "아트홀",
    "문화회관",
    "문예회관",
    "문화센터",
    "교육문화센터",
    "생활문화",
    "복합문화",
    "공연장",
    "전시관",
    "컨벤션",
)

_WEAK_GENERIC_REPRESENTATIVE_TERMS = _WEAK_GENERIC_REPRESENTATIVE_TERMS + (
    "도서관",
    "작은도서관",
    "공공도서관",
    "구민회관",
    "시민회관",
    "공공강당",
    "강당",
    "국기원",
    "태권도장",
    "훈련원",
    "연수센터",
    "생활체육",
    "국민체육센터",
)

_GYEONGNAM_WEAK_INDOOR_CONTEXT_TERMS = (
    "경남", "창원", "마산", "진해", "통영", "거제", "남해", "진주", "김해", "성산",
)

_GYEONGNAM_REPRESENTATIVE_EXCEPTION_TERMS = (
    "동피랑", "디피랑", "진주성", "촉석루", "국립김해박물관", "김해박물관",
    "김해가야테마파크", "수로왕릉", "대성동고분군", "보리암",
)

_PUBLIC_DATA_SOURCE_TERMS = (
    "tourapi", "public", "gonggong", "data.go.kr",
)

_PHASE3_WEAK_PUBLIC_DATA_TERMS = (
    "????", "??????", "????", "????", "???", "????", "??????",
    "???", "??", "??", "???", "??", "???", "??", "???", "??", "??", "??",
)

_PHASE3_TOURISM_EXCEPTION_TERMS = (
    "?????", "???", "???", "???", "???", "???", "???", "???",
    "??", "???", "??", "???", "???", "????", "??", "???", "?????",
    "????", "????", "??",
)

_CURATED_REPRESENTATIVE_FAMILY_TERMS: dict[str, tuple[str, ...]] = {
    "서울": (
        "을지로", "힙지로", "노가리골목", "청계천", "익선동", "한남", "성수",
        "서울숲", "한강", "북촌", "삼청", "가로수길", "코엑스", "스타필드",
        "별마당", "봉은사",
    ),
    "부산": (
        "광안리", "광안대교", "민락수변", "청사포", "송정", "기장", "해동용궁사",
        "용궁사", "흰여울", "해운대", "남포", "자갈치", "BIFF", "비프", "송도",
    ),
    "제주": (
        "애월", "함덕", "협재", "중문", "성산", "섭지코지", "해안도로", "밤바다",
    ),
    "강원": (
        "안목", "경포", "속초", "영랑호", "양양", "밤바다", "해변", "커피거리",
    ),
    "전북": (
        "전주한옥마을", "한옥마을", "남부시장", "야시장", "경기전", "전동성당", "오목대",
    ),
    "경남": (
        "진주성", "촉석루", "남강", "유등", "동피랑", "디피랑", "강구안",
        "이순신공원", "바람의언덕", "독일마을", "다랭이마을",
    ),
    "대구": (
        "수성못", "김광석거리", "동성로", "서문시장", "앞산",
    ),
}

_CURATED_NIGHT_CONTEXT_TERMS = (
    "야간", "야경", "밤", "night", "nightlife", "노포", "루프탑", "bar", "바",
    "수변", "밤바다", "데이트", "감성", "드라이브", "coastal",
)

_CURATED_WEAK_PUBLIC_CONTAMINATION_TERMS = (
    "cts아트홀", "아트홀", "공공", "문화센터", "문화회관", "교육문화센터",
    "생활문화", "복합문화", "구민회관", "시민회관", "공연장", "전시관",
    "체험관", "공예관", "박물관", "도서관", "행정", "청사",
)




def _source_text(place: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("data_source", "source", "source_name", "tourapi_content_id", "external_source"):
        value = place.get(key)
        if value:
            parts.append(str(value))
    return " ".join(parts).lower()


def _external_verified_score(place: dict[str, Any], *, source_exists: bool, image_exists: bool) -> float:
    source = _source_text(place)
    score = 0.0
    if any(term in source for term in _EXTERNAL_VERIFIED_SOURCE_TERMS):
        score += 0.04
    elif source_exists:
        score += 0.022
    if image_exists:
        score += 0.018
    if int(place.get("review_count") or 0) > 0:
        score += 0.012
    if float(place.get("rating") or 0.0) >= 4.0:
        score += 0.01
    return min(0.07, score)


def _external_popularity_score(place: dict[str, Any]) -> float:
    review_count = int(place.get("review_count") or 0)
    view_count = int(place.get("view_count") or 0)
    rating = float(place.get("rating") or 0.0)
    score = min(0.034, (review_count / 1200.0) * 0.034)
    score += min(0.032, (view_count / 60000.0) * 0.032)
    if rating >= 4.2:
        score += 0.014
    elif rating >= 4.0:
        score += 0.008
    return min(0.075, score)


def _public_data_weakness_penalty(place: dict[str, Any], *, target_slot: str | None = None, has_authority_match: bool = False) -> tuple[float, str | None]:
    joined = _norm(_identity_text(place))
    if not joined:
        return 0.0, None
    if any(_norm(term) in joined for term in _PHASE3_TOURISM_EXCEPTION_TERMS):
        return 0.0, None
    weak_terms = [term for term in _PHASE3_WEAK_PUBLIC_DATA_TERMS if _norm(term) in joined]
    if not weak_terms:
        return 0.0, None
    source = _source_text(place)
    image_exists = any(place.get(key) for key in ("first_image_url", "image_url", "thumbnail", "firstimage", "firstimage2"))
    external_source = any(term in source for term in ("naver", "kakao", "google"))
    if has_authority_match:
        return 0.0, None
    penalty = 0.038
    if any(term in source for term in _PUBLIC_DATA_SOURCE_TERMS) and not external_source:
        penalty += 0.022
    if not image_exists:
        penalty += 0.014
    if str(target_slot or "") in {"anchor", "morning", "morning_2"}:
        penalty += 0.026
    return min(0.1, penalty), "public_data_weak_candidate:" + ",".join(weak_terms[:3])


def _score_curated_representative_layer(
    place: dict[str, Any],
    region: str,
    flow_profile: dict[str, Any] | None,
    *,
    target_slot: str | None = None,
    has_authority_match: bool = False,
    external_verified_score: float = 0.0,
    external_popularity_score: float = 0.0,
) -> dict[str, Any]:
    text = _norm(_identity_text(place))
    flow = _norm((flow_profile or {}).get("inferred_flow_profile") or "")
    slot = str(target_slot or "")
    source = _source_text(place)
    image_exists = any(place.get(key) for key in ("first_image_url", "image_url", "thumbnail", "firstimage", "firstimage2"))
    region_terms = _CURATED_REPRESENTATIVE_FAMILY_TERMS.get(region) or ()
    matched_terms = [term for term in region_terms if _norm(term) and _norm(term) in text]
    night_context = bool(
        {"night_city", "sea_drive", "walk_emotional"} & {str((flow_profile or {}).get("inferred_flow_profile") or "")}
        or any(_norm(term) in text or _norm(term) in flow for term in _CURATED_NIGHT_CONTEXT_TERMS)
        or slot in {"evening", "dinner", "night"}
    )
    curated_priority = 0.0
    support_alignment = 0.0
    if matched_terms:
        curated_priority = 0.032
        if has_authority_match:
            curated_priority += 0.018
        if external_verified_score > 0 or external_popularity_score > 0:
            curated_priority += 0.012
        if image_exists:
            curated_priority += 0.008
        if night_context:
            curated_priority += 0.018
        if slot not in {"anchor", "morning", "morning_2"}:
            support_alignment = 0.022 + (0.014 if night_context else 0.0)

    weak_terms = [
        term
        for term in _CURATED_WEAK_PUBLIC_CONTAMINATION_TERMS
        if _norm(term) and _norm(term) in text
    ]
    weak_demote = 0.0
    if weak_terms and not matched_terms and not has_authority_match:
        weak_demote = 0.038
        if any(term in source for term in _PUBLIC_DATA_SOURCE_TERMS):
            weak_demote += 0.024
        if night_context:
            weak_demote += 0.032
        if slot in {"anchor", "morning", "morning_2"}:
            weak_demote += 0.018

    public_source = any(term in source for term in _PUBLIC_DATA_SOURCE_TERMS)
    external_source = any(term in source for term in _EXTERNAL_VERIFIED_SOURCE_TERMS)
    return {
        "curated_representative_priority": round(min(0.095, curated_priority), 4),
        "verified_api_candidate": bool(external_source or external_verified_score > 0),
        "public_fallback_used": bool(public_source and not external_source and not matched_terms),
        "weak_public_contamination_demote": round(min(0.13, weak_demote), 4),
        "curated_support_slot_alignment": round(min(0.05, support_alignment), 4),
        "curated_representative_matches": matched_terms[:6],
        "curated_representative_context": "night_or_evening" if night_context else "default",
        "weak_public_contamination_reason": (
            "weak_public_contamination:" + ",".join(weak_terms[:3])
            if weak_terms and weak_demote
            else None
        ),
    }

def iter_landmark_seeds() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for region, seeds in LANDMARK_AUTHORITY_SEEDS.items():
        for seed in seeds:
            rows.append({"region": region, **seed})
    return rows


def score_landmark_authority(
    place: dict[str, Any],
    region_identity: dict[str, Any] | None = None,
    flow_profile: dict[str, Any] | None = None,
    *,
    target_slot: str | None = None,
) -> dict[str, Any]:
    """Return small advisory authority signals for an existing candidate."""
    if not isinstance(place, dict):
        return _empty_score()

    region = str((region_identity or {}).get("region") or place.get("region_1") or place.get("region") or "")
    place_region = str(place.get("region_1") or place.get("region") or "")
    text = _norm(_identity_text(place))
    if not text:
        return _empty_score()

    name_norm = _norm(place.get("name"))
    weak_generic_demote = _score_weak_generic_demote(name_norm, place, target_slot)
    region_mismatch = bool(region and place_region and region != place_region)
    matches: list[dict[str, Any]] = []
    for seed in LANDMARK_AUTHORITY_SEEDS.get(region, []):
        aliases = [seed.get("canonical_name"), *(seed.get("aliases") or [])]
        alias_matches = [alias for alias in aliases if _norm(alias) and _norm(alias) in text]
        name_alias_matches = [alias for alias in aliases if _norm(alias) and _norm(alias) in name_norm]
        exact_name_match = any(_norm(alias) and _norm(alias) == name_norm for alias in aliases)
        weak_surrounding_facility = any(term in name_norm for term in _WEAK_AUTHORITY_MISMATCH_TERMS)
        if alias_matches and weak_surrounding_facility and not exact_name_match:
            continue
        if alias_matches and region_mismatch:
            continue
        if alias_matches and not name_alias_matches and not exact_name_match:
            continue
        if alias_matches:
            matches.append({**seed, "matched_aliases": alias_matches, "name_alias_matches": name_alias_matches})

    if not matches:
        image_exists = any(place.get(key) for key in ("first_image_url", "image_url", "thumbnail", "firstimage", "firstimage2"))
        source_exists = bool(place.get("tourapi_content_id") or place.get("data_source"))
        external_verified_score = _external_verified_score(place, source_exists=source_exists, image_exists=image_exists)
        external_popularity_score = _external_popularity_score(place)
        public_data_weakness_penalty, public_data_weakness_reason = _public_data_weakness_penalty(
            place,
            target_slot=target_slot,
            has_authority_match=False,
        )
        curated_signal = _score_curated_representative_layer(
            place,
            region,
            flow_profile,
            target_slot=target_slot,
            has_authority_match=False,
            external_verified_score=external_verified_score,
            external_popularity_score=external_popularity_score,
        )
        score = _empty_score()
        score["weak_generic_authority_demote"] = weak_generic_demote
        score["weak_generic_authority_reason"] = (
            "weak_generic_representative_candidate" if weak_generic_demote else None
        )
        score["public_facility_demote"] = round(weak_generic_demote, 4)
        score["representative_tourism_fit"] = 0.0
        score["weak_public_facility_reason"] = (
            "weak_public_facility_candidate" if weak_generic_demote else None
        )
        score["indoor_culture_fallback_demote"] = round(weak_generic_demote, 4)
        score["external_verified_score"] = round(external_verified_score, 4)
        score["external_popularity_score"] = round(external_popularity_score, 4)
        score["public_data_weakness_penalty"] = round(
            public_data_weakness_penalty + float(curated_signal.get("weak_public_contamination_demote") or 0.0),
            4,
        )
        score["public_data_weakness_reason"] = (
            curated_signal.get("weak_public_contamination_reason") or public_data_weakness_reason
        )
        score["representative_confidence_score"] = round(
            min(
                0.065,
                external_verified_score * 0.45
                + external_popularity_score * 0.35
                + float(curated_signal.get("curated_representative_priority") or 0.0) * 0.35,
            ),
            4,
        )
        score.update(curated_signal)
        if region_mismatch:
            score["region_aware_alias_guard"] = f"wrong_region:{place_region}->{region}"
            score["wrong_region_alias_demote"] = 0.12
        return score

    best = max(matches, key=lambda item: float(item.get("authority") or 0.0))
    authority = float(best.get("authority") or 0.0)
    role = str(place.get("visit_role") or place.get("role") or "")
    slot = str(target_slot or "")
    flow = str((flow_profile or {}).get("inferred_flow_profile") or "")
    belt = str((region_identity or {}).get("inferred_belt") or (region_identity or {}).get("dominant_belt") or "")

    image_exists = any(place.get(key) for key in ("first_image_url", "image_url", "thumbnail", "firstimage", "firstimage2"))
    review_count = int(place.get("review_count") or 0)
    view_count = int(place.get("view_count") or 0)
    rating = float(place.get("rating") or 0.0)
    source_exists = bool(place.get("tourapi_content_id") or place.get("data_source"))
    external_verified_score = _external_verified_score(place, source_exists=source_exists, image_exists=image_exists)
    external_popularity_score = _external_popularity_score(place)
    public_data_weakness_penalty, public_data_weakness_reason = _public_data_weakness_penalty(
        place,
        target_slot=target_slot,
        has_authority_match=True,
    )
    curated_signal = _score_curated_representative_layer(
        place,
        region,
        flow_profile,
        target_slot=target_slot,
        has_authority_match=True,
        external_verified_score=external_verified_score,
        external_popularity_score=external_popularity_score,
    )
    best_id = str(best.get("landmark_id") or "")
    priority_landmark = best_id in _PHASE2_PRIORITY_LANDMARK_IDS

    exact_name_match = any(
        _norm(alias) and _norm(alias) == name_norm
        for alias in [best.get("canonical_name"), *(best.get("aliases") or [])]
    )
    landmark_confidence = min(
        1.0,
        0.52 * authority
        + (0.18 if exact_name_match else 0.0)
        + (0.1 if image_exists else 0.0)
        + (0.08 if source_exists else 0.0)
        + min(0.07, review_count / 1000.0 * 0.07)
        + min(0.05, view_count / 50000.0 * 0.05),
    )

    tourism_score = 0.075 * authority
    if role in {"spot", "culture"}:
        tourism_score += 0.026
    if slot in {"anchor", "morning", "morning_2"}:
        tourism_score += 0.045
    if belt and belt in set(best.get("belts") or []):
        tourism_score += 0.025
    if flow and set(best.get("themes") or []) & _flow_theme_tokens(flow):
        tourism_score += 0.018
    if priority_landmark:
        tourism_score += 0.028
    family_candidate_lookup_bonus = 0.025 if (belt and belt in set(best.get("belts") or [])) else 0.0

    image_density_score = 0.028 if image_exists else 0.0
    review_density_hint = min(0.03, (review_count / 1000.0) * 0.03)
    popularity_signal = min(0.045, (view_count / 50000.0) * 0.032 + (0.013 if rating >= 4.0 else 0.0))
    normalized_popularity_hint = min(1.0, (view_count / 50000.0) * 0.55 + (review_count / 1000.0) * 0.35 + (rating / 5.0) * 0.1)
    representative_tourism_bonus = min(0.09, tourism_score * 0.55 + (0.025 if slot in {"anchor", "morning", "morning_2"} else 0.0))
    representative_confidence_score = min(
        0.09,
        representative_tourism_bonus * 0.55
        + external_verified_score * 0.45
        + (0.018 if exact_name_match else 0.0),
    )
    total = min(
        0.32,
        tourism_score
        + image_density_score
        + review_density_hint
        + popularity_signal
        + external_verified_score
        + external_popularity_score
        + representative_confidence_score
        + family_candidate_lookup_bonus
        + float(curated_signal.get("curated_representative_priority") or 0.0)
        + float(curated_signal.get("curated_support_slot_alignment") or 0.0)
        - public_data_weakness_penalty,
    )

    result = {
        "landmark_authority_score": round(total, 4),
        "popularity_signal": round(popularity_signal, 4),
        "popularity_authority_score": round(min(0.08, popularity_signal + review_density_hint + image_density_score), 4),
        "landmark_confidence": round(landmark_confidence, 4),
        "representative_tourism_bonus": round(representative_tourism_bonus, 4),
        "tourism_representative_score": round(min(0.16, tourism_score), 4),
        "normalized_popularity_hint": round(normalized_popularity_hint, 4),
        "external_verified_score": round(external_verified_score, 4),
        "external_popularity_score": round(external_popularity_score, 4),
        "public_data_weakness_penalty": round(public_data_weakness_penalty, 4),
        "public_data_weakness_reason": public_data_weakness_reason,
        "representative_confidence_score": round(representative_confidence_score, 4),
        "image_density_score": round(image_density_score, 4),
        "review_density_hint": round(review_density_hint, 4),
        "landmark_authority_matches": [
            {
                "landmark_id": item.get("landmark_id"),
                "canonical_name": item.get("canonical_name"),
                "matched_aliases": item.get("matched_aliases")[:4],
            }
            for item in matches[:3]
        ],
        "landmark_authority_reason": f"{region}:{best.get('canonical_name')}:{','.join(best.get('matched_aliases')[:3])}",
        "landmark_authority_source_policy": best.get("source_policy") or "governed_authority_seed",
        "alias_normalization_match": best.get("matched_aliases")[:4],
        "region_aware_alias_guard": "same_region",
        "wrong_region_alias_demote": 0.0,
        "family_candidate_lookup_bonus": round(family_candidate_lookup_bonus, 4),
        "representative_alias_pool_included": True,
        "weak_generic_authority_demote": 0.0,
        "weak_generic_authority_reason": None,
        "public_facility_demote": 0.0,
        "representative_tourism_fit": round(min(0.06, representative_tourism_bonus), 4),
        "weak_public_facility_reason": None,
        "representative_tourism_family_score": round(min(0.1, tourism_score), 4),
        "regional_landmark_density": round(min(0.075, representative_confidence_score + image_density_score), 4),
        "first_place_representative_bonus": round(
            0.035 if slot in {"anchor", "morning", "morning_2"} and priority_landmark else 0.0,
            4,
        ),
        "indoor_culture_fallback_demote": 0.0,
    }
    result.update(curated_signal)
    return result


def _flow_theme_tokens(flow: str) -> set[str]:
    mapping = {
        "sea_drive": {"sea", "drive", "nature"},
        "night_city": {"night", "date"},
        "cafe_relaxed": {"cafe", "date"},
        "walk_emotional": {"walk", "date", "history"},
        "history_walk": {"history", "walk"},
        "family_leisure": {"family", "nature"},
    }
    return mapping.get(flow, {flow})


def _empty_score() -> dict[str, Any]:
    return {
        "landmark_authority_score": 0.0,
        "popularity_signal": 0.0,
        "popularity_authority_score": 0.0,
        "landmark_confidence": 0.0,
        "representative_tourism_bonus": 0.0,
        "tourism_representative_score": 0.0,
        "normalized_popularity_hint": 0.0,
        "external_verified_score": 0.0,
        "external_popularity_score": 0.0,
        "public_data_weakness_penalty": 0.0,
        "public_data_weakness_reason": None,
        "representative_confidence_score": 0.0,
        "image_density_score": 0.0,
        "review_density_hint": 0.0,
        "landmark_authority_matches": [],
        "landmark_authority_reason": None,
        "landmark_authority_source_policy": None,
        "alias_normalization_match": [],
        "region_aware_alias_guard": None,
        "wrong_region_alias_demote": 0.0,
        "family_candidate_lookup_bonus": 0.0,
        "representative_alias_pool_included": False,
        "weak_generic_authority_demote": 0.0,
        "weak_generic_authority_reason": None,
        "public_facility_demote": 0.0,
        "representative_tourism_fit": 0.0,
        "weak_public_facility_reason": None,
        "representative_tourism_family_score": 0.0,
        "regional_landmark_density": 0.0,
        "first_place_representative_bonus": 0.0,
        "indoor_culture_fallback_demote": 0.0,
        "curated_representative_priority": 0.0,
        "verified_api_candidate": False,
        "public_fallback_used": False,
        "weak_public_contamination_demote": 0.0,
        "curated_support_slot_alignment": 0.0,
        "curated_representative_matches": [],
        "curated_representative_context": None,
        "weak_public_contamination_reason": None,
    }


def _score_weak_generic_demote(name_norm: str, place: dict[str, Any], target_slot: str | None) -> float:
    slot = str(target_slot or "")
    role = str(place.get("visit_role") or place.get("role") or "")
    if slot not in {"anchor", "morning", "morning_2"} or role not in {"spot", "culture"}:
        return 0.0
    if not any(term in name_norm for term in _WEAK_GENERIC_REPRESENTATIVE_TERMS):
        return 0.0
    joined = _norm(_identity_text(place))
    if any(_norm(term) in joined for term in _GYEONGNAM_REPRESENTATIVE_EXCEPTION_TERMS):
        return 0.0
    gyeongnam_context = any(_norm(term) in joined for term in _GYEONGNAM_WEAK_INDOOR_CONTEXT_TERMS)
    if gyeongnam_context:
        return 0.115
    return 0.055
