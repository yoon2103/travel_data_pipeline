"""
anchor_definitions.py — 지역별 대표 출발 기준점(start_anchor) 사전 정의

설계 원칙:
  - start_anchor는 place(방문 장소)가 아니라 코스 시작 기준점이다.
  - 역/터미널/공항/해변/중심상권/랜드마크 단위 좌표로 정의.
  - 음식점/공연장/회관 등 개별 시설 직접 사용 금지.
  - 실제 코스 생성 가능 여부는 runtime DB 검증 (generate_anchor_departures).
  - key = DB places.region_1 값 (display name 아님).
"""

# priority: 낮을수록 대표성 높음 (1 = 가장 대표적)
REGION_ANCHORS: dict[str, list[dict]] = {

    # ── 도시형 (urban) ──────────────────────────────────────────────
    "광주": [
        {"anchor_id": "gwangju_station",    "anchor_name": "광주역",       "display_name": "광주역 주변",       "latitude": 35.1600, "longitude": 126.9042, "priority": 1},
        {"anchor_id": "gwangju_chungjangno","anchor_name": "충장로",       "display_name": "충장로/동명동 주변","latitude": 35.1472, "longitude": 126.9148, "priority": 2},
        {"anchor_id": "gwangju_sangmu",     "anchor_name": "상무지구",     "display_name": "상무지구 주변",     "latitude": 35.1554, "longitude": 126.8499, "priority": 3},
    ],

    "대구": [
        {"anchor_id": "daegu_dongseongno",  "anchor_name": "동성로",       "display_name": "동성로 주변",       "latitude": 35.8703, "longitude": 128.5960, "priority": 1},
        {"anchor_id": "daegu_dongdaegu",    "anchor_name": "동대구역",     "display_name": "동대구역 주변",     "latitude": 35.8799, "longitude": 128.6291, "priority": 2},
        {"anchor_id": "daegu_suseongmot",   "anchor_name": "수성못",       "display_name": "수성못 주변",       "latitude": 35.8452, "longitude": 128.6280, "priority": 3},
        {"anchor_id": "daegu_seomun",       "anchor_name": "서문시장",     "display_name": "서문시장 주변",     "latitude": 35.8697, "longitude": 128.5772, "priority": 4},
    ],

    "대전": [
        {"anchor_id": "daejeon_station",    "anchor_name": "대전역",       "display_name": "대전역 주변",       "latitude": 36.3315, "longitude": 127.4346, "priority": 1},
        {"anchor_id": "daejeon_dunsan",     "anchor_name": "둔산/시청",    "display_name": "둔산/시청 주변",    "latitude": 36.3505, "longitude": 127.3849, "priority": 2},
        {"anchor_id": "daejeon_yuseong",    "anchor_name": "유성온천",     "display_name": "유성온천 주변",     "latitude": 36.3618, "longitude": 127.3386, "priority": 3},
        {"anchor_id": "daejeon_eunhaengno", "anchor_name": "으능정이",     "display_name": "으능정이거리 주변","latitude": 36.3262, "longitude": 127.4276, "priority": 4},
    ],

    "인천": [
        {"anchor_id": "incheon_chinatown",  "anchor_name": "차이나타운",   "display_name": "인천역/차이나타운 주변","latitude": 37.4738, "longitude": 126.6168, "priority": 1},
        {"anchor_id": "incheon_bupyeong",   "anchor_name": "부평역",       "display_name": "부평역 주변",       "latitude": 37.4901, "longitude": 126.7239, "priority": 2},
        {"anchor_id": "incheon_wolmi",      "anchor_name": "월미도",       "display_name": "월미도 주변",       "latitude": 37.4742, "longitude": 126.5983, "priority": 3},
        {"anchor_id": "incheon_songdo",     "anchor_name": "송도",         "display_name": "송도 주변",         "latitude": 37.3905, "longitude": 126.6478, "priority": 4},
        {"anchor_id": "incheon_ganghwa",    "anchor_name": "강화읍",       "display_name": "강화도 주변",       "latitude": 37.7479, "longitude": 126.4874, "priority": 5},
    ],

    "서울": [
        {"anchor_id": "seoul_gangnam",      "anchor_name": "강남역",       "display_name": "강남역 주변",       "latitude": 37.4979, "longitude": 127.0276, "priority": 1},
        {"anchor_id": "seoul_hongdae",      "anchor_name": "홍대입구",     "display_name": "홍대입구 주변",     "latitude": 37.5563, "longitude": 126.9236, "priority": 2},
        {"anchor_id": "seoul_myeongdong",   "anchor_name": "명동",         "display_name": "명동/을지로 주변",  "latitude": 37.5636, "longitude": 126.9826, "priority": 3},
        {"anchor_id": "seoul_gwanghwamun",  "anchor_name": "광화문",       "display_name": "광화문/종로 주변",  "latitude": 37.5759, "longitude": 126.9769, "priority": 4},
        {"anchor_id": "seoul_jamsil",       "anchor_name": "잠실",         "display_name": "잠실 주변",         "latitude": 37.5133, "longitude": 127.1002, "priority": 5},
        {"anchor_id": "seoul_yeouido",      "anchor_name": "여의도",       "display_name": "여의도 주변",       "latitude": 37.5247, "longitude": 126.9240, "priority": 6},
        {"anchor_id": "seoul_seongsu",      "anchor_name": "성수동",       "display_name": "성수동/건대 주변",  "latitude": 37.5443, "longitude": 127.0558, "priority": 7},
        {"anchor_id": "seoul_itaewon",      "anchor_name": "이태원",       "display_name": "이태원/한남 주변",  "latitude": 37.5345, "longitude": 126.9944, "priority": 8},
    ],

    "부산": [
        {"anchor_id": "busan_haeundae",     "anchor_name": "해운대",       "display_name": "해운대 주변",       "latitude": 35.1588, "longitude": 129.1604, "priority": 1},
        {"anchor_id": "busan_gwanganli",    "anchor_name": "광안리",       "display_name": "광안리 주변",       "latitude": 35.1527, "longitude": 129.1183, "priority": 2},
        {"anchor_id": "busan_seomyeon",     "anchor_name": "서면",         "display_name": "서면 주변",         "latitude": 35.1569, "longitude": 129.0587, "priority": 3},
        {"anchor_id": "busan_nampodong",    "anchor_name": "남포동",       "display_name": "남포동/부산역 주변","latitude": 35.1038, "longitude": 129.0317, "priority": 4},
        {"anchor_id": "busan_gijang",       "anchor_name": "기장",         "display_name": "기장 주변",         "latitude": 35.2444, "longitude": 129.2245, "priority": 5},
        {"anchor_id": "busan_songdo",       "anchor_name": "송도",         "display_name": "송도/암남 주변",    "latitude": 35.0742, "longitude": 129.0102, "priority": 6},
    ],

    # ── 광역 도 (regional) ───────────────────────────────────────────
    "제주": [
        {"anchor_id": "jeju_city",          "anchor_name": "제주공항",     "display_name": "제주공항 주변",     "latitude": 33.5113, "longitude": 126.4941, "priority": 1},
        {"anchor_id": "jeju_aewol",         "anchor_name": "애월",         "display_name": "애월 주변",         "latitude": 33.4640, "longitude": 126.3175, "priority": 2},
        {"anchor_id": "jeju_hyeopjae",      "anchor_name": "협재",         "display_name": "협재 주변",         "latitude": 33.3938, "longitude": 126.2393, "priority": 3},
        {"anchor_id": "jeju_jungmun",       "anchor_name": "중문",         "display_name": "중문 주변",         "latitude": 33.2541, "longitude": 126.4122, "priority": 4},
        {"anchor_id": "jeju_seogwipo",      "anchor_name": "서귀포",       "display_name": "서귀포 주변",       "latitude": 33.2541, "longitude": 126.5601, "priority": 5},
        {"anchor_id": "jeju_seongsan",      "anchor_name": "성산",         "display_name": "성산 주변",         "latitude": 33.4580, "longitude": 126.9405, "priority": 6},
        {"anchor_id": "jeju_hamdeok",       "anchor_name": "함덕",         "display_name": "함덕 주변",         "latitude": 33.5432, "longitude": 126.6685, "priority": 7},
    ],

    "강원": [
        {"anchor_id": "gangwon_gangneung",  "anchor_name": "강릉역",       "display_name": "강릉역 주변",       "latitude": 37.7750, "longitude": 128.9400, "priority": 1},
        {"anchor_id": "gangwon_gyeongpo",   "anchor_name": "경포해변",     "display_name": "경포해변 주변",     "latitude": 37.7988, "longitude": 128.9046, "priority": 2},
        {"anchor_id": "gangwon_anmok",      "anchor_name": "안목해변",     "display_name": "안목해변 주변",     "latitude": 37.7695, "longitude": 128.9624, "priority": 3},
        {"anchor_id": "gangwon_sokcho",     "anchor_name": "속초",         "display_name": "속초 주변",         "latitude": 38.2070, "longitude": 128.5918, "priority": 4},
        {"anchor_id": "gangwon_chuncheon",  "anchor_name": "춘천",         "display_name": "춘천 주변",         "latitude": 37.8813, "longitude": 127.7298, "priority": 5},
        {"anchor_id": "gangwon_jeongseon",  "anchor_name": "정동진",       "display_name": "정동진 주변",       "latitude": 37.6923, "longitude": 129.0551, "priority": 6},
    ],

    "경북": [
        {"anchor_id": "gyeongbuk_gyeongju", "anchor_name": "경주역",       "display_name": "경주역 주변",       "latitude": 35.8392, "longitude": 129.2101, "priority": 1},
        {"anchor_id": "gyeongbuk_hwangni",  "anchor_name": "황리단길",     "display_name": "황리단길/대릉원 주변","latitude": 35.8342, "longitude": 129.2259, "priority": 2},
        {"anchor_id": "gyeongbuk_bulguksa", "anchor_name": "불국사",       "display_name": "불국사 주변",       "latitude": 35.7888, "longitude": 129.3315, "priority": 3},
        {"anchor_id": "gyeongbuk_pohang",   "anchor_name": "포항",         "display_name": "포항 주변",         "latitude": 36.0190, "longitude": 129.3435, "priority": 4},
        {"anchor_id": "gyeongbuk_andong",   "anchor_name": "안동",         "display_name": "안동 주변",         "latitude": 36.5684, "longitude": 128.7294, "priority": 5},
    ],

    "전북": [
        {"anchor_id": "jeonbuk_hanok",      "anchor_name": "전주한옥마을", "display_name": "전주한옥마을 주변","latitude": 35.8180, "longitude": 127.1524, "priority": 1},
        {"anchor_id": "jeonbuk_station",    "anchor_name": "전주역",       "display_name": "전주역 주변",       "latitude": 35.8178, "longitude": 127.1490, "priority": 2},
        {"anchor_id": "jeonbuk_nambu",      "anchor_name": "남부시장",     "display_name": "남부시장 주변",     "latitude": 35.8107, "longitude": 127.1472, "priority": 3},
        {"anchor_id": "jeonbuk_gunsan",     "anchor_name": "군산",         "display_name": "군산 주변",         "latitude": 35.9675, "longitude": 126.7368, "priority": 4},
    ],

    "경기": [
        {"anchor_id": "gyeonggi_suwon",     "anchor_name": "수원역",       "display_name": "수원역 주변",       "latitude": 37.2636, "longitude": 127.0286, "priority": 1},
        {"anchor_id": "gyeonggi_hwaseong",  "anchor_name": "수원화성",     "display_name": "수원화성 주변",     "latitude": 37.2849, "longitude": 127.0116, "priority": 2},
        {"anchor_id": "gyeonggi_gapyeong",  "anchor_name": "가평",         "display_name": "가평 주변",         "latitude": 37.8316, "longitude": 127.5092, "priority": 3},
        {"anchor_id": "gyeonggi_ilsan",     "anchor_name": "일산",         "display_name": "일산/고양 주변",    "latitude": 37.6577, "longitude": 126.7670, "priority": 4},
    ],

    "경남": [
        {"anchor_id": "gyeongnam_tongyeong","anchor_name": "통영",         "display_name": "통영 주변",         "latitude": 34.8538, "longitude": 128.4330, "priority": 1},
        {"anchor_id": "gyeongnam_geoje",    "anchor_name": "거제",         "display_name": "거제 주변",         "latitude": 34.8808, "longitude": 128.6270, "priority": 2},
        {"anchor_id": "gyeongnam_changwon", "anchor_name": "창원",         "display_name": "창원 주변",         "latitude": 35.2280, "longitude": 128.6820, "priority": 3},
        {"anchor_id": "gyeongnam_namhae",   "anchor_name": "남해",         "display_name": "남해 주변",         "latitude": 34.8375, "longitude": 127.8922, "priority": 4},
    ],

    "전남": [
        {"anchor_id": "jeonnam_yeosu",      "anchor_name": "여수",         "display_name": "여수 주변",         "latitude": 34.7604, "longitude": 127.6622, "priority": 1},
        {"anchor_id": "jeonnam_suncheon",   "anchor_name": "순천",         "display_name": "순천/순천만 주변",  "latitude": 34.9507, "longitude": 127.4870, "priority": 2},
        {"anchor_id": "jeonnam_mokpo",      "anchor_name": "목포",         "display_name": "목포 주변",         "latitude": 34.8118, "longitude": 126.3922, "priority": 3},
        {"anchor_id": "jeonnam_damyang",    "anchor_name": "담양",         "display_name": "담양 주변",         "latitude": 35.3232, "longitude": 126.9882, "priority": 4},
    ],

    "충남": [
        {"anchor_id": "chungnam_gongju",    "anchor_name": "공주",         "display_name": "공주/공산성 주변",  "latitude": 36.4600, "longitude": 127.1192, "priority": 1},
        {"anchor_id": "chungnam_buyeo",     "anchor_name": "부여",         "display_name": "부여 주변",         "latitude": 36.2756, "longitude": 126.9100, "priority": 2},
        {"anchor_id": "chungnam_taean",     "anchor_name": "태안",         "display_name": "태안/안면도 주변",  "latitude": 36.7455, "longitude": 126.2984, "priority": 3},
        {"anchor_id": "chungnam_cheonan",   "anchor_name": "천안",         "display_name": "천안 주변",         "latitude": 36.7986, "longitude": 127.0444, "priority": 4},
    ],

    "충북": [
        {"anchor_id": "chungbuk_cheongju",  "anchor_name": "청주",         "display_name": "청주 주변",         "latitude": 36.6424, "longitude": 127.4890, "priority": 1},
        {"anchor_id": "chungbuk_chungju",   "anchor_name": "충주",         "display_name": "충주 주변",         "latitude": 36.9910, "longitude": 127.9260, "priority": 2},
        {"anchor_id": "chungbuk_danyang",   "anchor_name": "단양",         "display_name": "단양 주변",         "latitude": 37.0034, "longitude": 128.3632, "priority": 3},
        {"anchor_id": "chungbuk_jecheon",   "anchor_name": "제천",         "display_name": "제천 주변",         "latitude": 37.1320, "longitude": 128.1910, "priority": 4},
    ],

    "울산": [
        {"anchor_id": "ulsan_samsan",       "anchor_name": "삼산",         "display_name": "삼산/울산 중심 주변", "latitude": 35.5388, "longitude": 129.3310, "priority": 1},
        {"anchor_id": "ulsan_taehwa",       "anchor_name": "태화강",       "display_name": "태화강국가정원 주변","latitude": 35.5386, "longitude": 129.3296, "priority": 2},
        {"anchor_id": "ulsan_station",      "anchor_name": "울산역",       "display_name": "울산역 주변",       "latitude": 35.5588, "longitude": 129.2390, "priority": 3},
        {"anchor_id": "ulsan_jangsaengpo",  "anchor_name": "장생포",       "display_name": "장생포/남구 주변",  "latitude": 35.4927, "longitude": 129.3863, "priority": 4},
    ],

    "세종": [
        {"anchor_id": "sejong_government",  "anchor_name": "세종정부청사", "display_name": "정부청사/세종 중심 주변","latitude": 36.4800, "longitude": 127.2890, "priority": 1},
        {"anchor_id": "sejong_lake",        "anchor_name": "세종호수공원", "display_name": "세종호수공원 주변", "latitude": 36.5023, "longitude": 127.2730, "priority": 2},
        {"anchor_id": "sejong_jochiwon",    "anchor_name": "조치원",       "display_name": "조치원역 주변",     "latitude": 36.5987, "longitude": 127.2939, "priority": 3},
    ],
}
