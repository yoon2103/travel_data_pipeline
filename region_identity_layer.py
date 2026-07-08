"""Region Identity Layer seed definitions.

This module describes tourism belts and local ecosystem identity. It is a
metadata/normalization layer only; it must not rank, filter, or mutate course
selection results.
"""
from __future__ import annotations

import re
from typing import Any


def normalize_identity_token(value: Any) -> str:
    """Return a compact token for belt/anchor alias matching."""
    return re.sub(r"[\s\-\(\)\[\],./·ㆍ|]", "", str(value or "").strip().lower())


REGION_IDENTITY_BELTS: dict[str, dict[str, dict[str, Any]]] = {
    "서울": {
        "성수": {
            "vibe_tags": ["카페", "편집숍", "서울숲", "감성", "도보"],
            "tourism_keywords": ["성수동", "서울숲", "연무장길", "뚝섬"],
            "representative_poi_aliases": ["성수동", "서울숲", "연무장길", "뚝섬역", "서울숲역"],
            "representative_categories": ["cafe", "culture", "walk"],
            "anchor": {"name": "성수동", "lat": 37.5443, "lng": 127.0558},
            "nearby_anchor_aliases": ["서울숲", "뚝섬", "건대", "연무장길"],
            "mobility_traits": ["walking", "cafe", "lifestyle"],
        },
        "익선": {
            "vibe_tags": ["한옥", "골목", "데이트", "카페", "야간"],
            "tourism_keywords": ["익선동", "종로3가", "한옥거리"],
            "representative_poi_aliases": ["익선동", "익선동한옥거리", "종로3가", "운현궁"],
            "representative_categories": ["culture", "cafe", "walk"],
            "anchor": {"name": "익선동", "lat": 37.5726, "lng": 126.9896},
            "nearby_anchor_aliases": ["종로3가", "인사동", "운현궁", "낙원상가"],
            "mobility_traits": ["walking", "date", "night"],
        },
        "을지로": {
            "vibe_tags": ["노포", "야장", "도심", "야간", "레트로", "골목", "bar"],
            "tourism_keywords": ["을지로", "힙지로", "청계천", "세운상가", "노가리골목", "충무로"],
            "representative_poi_aliases": ["을지로", "을지로3가", "힙지로", "청계천", "세운상가", "을지로 노가리골목", "충무로 인쇄골목"],
            "representative_categories": ["meal", "culture", "night"],
            "anchor": {"name": "을지로3가", "lat": 37.5663, "lng": 126.9911},
            "nearby_anchor_aliases": ["명동", "청계천", "종로", "충무로", "세운상가", "노가리골목"],
            "mobility_traits": ["walking", "night", "food"],
        },
        "홍대": {
            "vibe_tags": ["청년", "공연", "카페", "쇼핑", "야간"],
            "tourism_keywords": ["홍대", "연남", "상수", "합정"],
            "representative_poi_aliases": ["홍대", "홍대입구", "연남동", "상수", "합정"],
            "representative_categories": ["cafe", "culture", "night"],
            "anchor": {"name": "홍대입구", "lat": 37.5563, "lng": 126.9236},
            "nearby_anchor_aliases": ["연남", "상수", "합정", "망원"],
            "mobility_traits": ["walking", "night", "youth"],
        },
        "잠실": {
            "vibe_tags": ["호수", "쇼핑", "가족", "도심", "야경"],
            "tourism_keywords": ["잠실", "석촌호수", "롯데월드타워"],
            "representative_poi_aliases": ["잠실", "석촌호수", "롯데월드", "롯데월드타워"],
            "representative_categories": ["spot", "family", "city"],
            "anchor": {"name": "잠실", "lat": 37.5133, "lng": 127.1002},
            "nearby_anchor_aliases": ["석촌", "송리단길", "방이"],
            "mobility_traits": ["family", "walking", "night"],
        },
        "북촌": {
            "vibe_tags": ["한옥", "역사", "궁궐", "골목", "도보"],
            "tourism_keywords": ["북촌", "삼청동", "안국", "경복궁"],
            "representative_poi_aliases": ["북촌", "북촌한옥마을", "삼청동", "안국", "경복궁"],
            "representative_categories": ["culture", "history", "walk"],
            "anchor": {"name": "북촌한옥마을", "lat": 37.5826, "lng": 126.9836},
            "nearby_anchor_aliases": ["안국", "삼청동", "경복궁", "창덕궁"],
            "mobility_traits": ["walking", "history", "heritage"],
        },
        "한남": {
            "vibe_tags": ["갤러리", "브런치", "편집숍", "감성", "도보"],
            "tourism_keywords": ["한남동", "이태원", "리움", "브런치", "갤러리", "편집숍", "독서당로", "카페", "산책"],
            "representative_poi_aliases": ["한남", "한남동", "이태원", "리움미술관", "독서당로", "블루스퀘어"],
            "representative_categories": ["cafe", "culture", "meal"],
            "anchor": {"name": "한남동", "lat": 37.5345, "lng": 127.0009},
            "nearby_anchor_aliases": ["이태원", "리움", "독서당로"],
            "mobility_traits": ["walking", "date", "lifestyle"],
        },
        "강남": {
            "vibe_tags": ["도심", "쇼핑", "전시", "카페", "야간"],
            "tourism_keywords": ["강남역", "신논현", "코엑스", "별마당도서관", "봉은사", "가로수길", "압구정", "청담", "선정릉"],
            "representative_poi_aliases": ["강남역", "신논현", "코엑스", "별마당도서관", "봉은사", "가로수길", "압구정", "청담", "선정릉"],
            "representative_categories": ["city", "cafe", "walk"],
            "anchor": {"name": "강남역", "lat": 37.4979, "lng": 127.0276},
            "nearby_anchor_aliases": ["신논현", "코엑스", "봉은사", "가로수길", "압구정", "선정릉"],
            "mobility_traits": ["walking", "city", "date"],
        },
        "여의도": {
            "vibe_tags": ["한강", "공원", "도심", "쇼핑", "전망"],
            "tourism_keywords": ["여의도", "여의도한강공원", "더현대서울", "IFC몰", "여의도공원", "샛강생태공원", "63빌딩"],
            "representative_poi_aliases": ["여의도", "여의도한강공원", "더현대서울", "IFC몰", "여의도공원", "샛강생태공원", "63빌딩"],
            "representative_categories": ["walk", "city", "family"],
            "anchor": {"name": "여의도한강공원", "lat": 37.5284, "lng": 126.9326},
            "nearby_anchor_aliases": ["더현대", "IFC", "여의도공원", "샛강", "63빌딩"],
            "mobility_traits": ["walking", "river", "family"],
        },
    },
    "부산": {
        "해운대": {
            "vibe_tags": ["바다", "해변", "고층", "야경", "가족"],
            "tourism_keywords": ["해운대", "동백섬", "달맞이", "달맞이길", "오륙도", "Oryukdo", "Dalmaji Road"],
            "representative_poi_aliases": ["해운대", "해운대해수욕장", "동백섬", "달맞이길", "오륙도", "Oryukdo Skywalk", "Dalmaji Road"],
            "representative_categories": ["spot", "cafe", "walk"],
            "anchor": {"name": "해운대해수욕장", "lat": 35.1587, "lng": 129.1604},
            "nearby_anchor_aliases": ["동백섬", "달맞이", "센텀"],
            "mobility_traits": ["walking", "sea", "night"],
        },
        "광안리": {
            "vibe_tags": ["바다", "야경", "카페", "데이트", "도보"],
            "tourism_keywords": ["광안리", "광안대교", "민락"],
            "representative_poi_aliases": ["광안리", "광안리해수욕장", "광안대교", "민락수변공원"],
            "representative_categories": ["spot", "cafe", "night"],
            "anchor": {"name": "광안리해수욕장", "lat": 35.1532, "lng": 129.1187},
            "nearby_anchor_aliases": ["광안대교", "민락", "수영"],
            "mobility_traits": ["walking", "night", "sea"],
        },
        "영도": {
            "vibe_tags": ["항구", "카페", "전망", "드라이브", "해양"],
            "tourism_keywords": ["영도", "흰여울", "태종대", "봉래동", "Huinnyeoul", "Taejongdae"],
            "representative_poi_aliases": ["영도", "흰여울문화마을", "Huinnyeoul Culture Village", "태종대", "Taejongdae", "봉래동"],
            "representative_categories": ["spot", "culture", "cafe"],
            "anchor": {"name": "흰여울문화마을", "lat": 35.0797, "lng": 129.0456},
            "nearby_anchor_aliases": ["태종대", "남항", "봉래동"],
            "mobility_traits": ["drive", "sea", "view"],
        },
        "서면": {
            "vibe_tags": ["도심", "쇼핑", "맛집", "야간", "대중교통"],
            "tourism_keywords": ["서면", "전포", "전리단길"],
            "representative_poi_aliases": ["서면", "전포", "전리단길", "부전"],
            "representative_categories": ["meal", "cafe", "city"],
            "anchor": {"name": "서면", "lat": 35.1577, "lng": 129.0592},
            "nearby_anchor_aliases": ["전포", "부전", "범내골"],
            "mobility_traits": ["walking", "food", "night"],
        },
        "남포": {
            "vibe_tags": ["시장", "항구", "원도심", "먹거리", "도보"],
            "tourism_keywords": ["남포", "부산역", "자갈치", "국제시장", "BIFF광장", "비프광장", "보수동", "용두산", "용두산공원", "부산타워", "감천문화마을", "Gamcheon Culture Village", "흰여울문화마을", "흰여울해안터널", "깡깡이예술마을", "송도해상케이블카", "송도해수욕장", "Songdo Marine Cable Car"],
            "representative_poi_aliases": ["남포", "부산역", "자갈치시장", "국제시장", "BIFF광장", "비프광장", "용두산공원", "부산타워", "보수동", "감천문화마을", "Gamcheon Culture Village", "흰여울문화마을", "흰여울해안터널", "깡깡이예술마을", "송도해상케이블카", "송도해수욕장", "Songdo Marine Cable Car"],
            "representative_categories": ["meal", "culture", "market"],
            "anchor": {"name": "남포동", "lat": 35.0979, "lng": 129.0344},
            "nearby_anchor_aliases": ["자갈치", "국제시장", "BIFF", "용두산", "감천", "흰여울", "송도", "깡깡이", "보수동"],
            "mobility_traits": ["walking", "food", "heritage"],
        },
        "기장": {
            "vibe_tags": ["바다", "드라이브", "카페", "가족", "해안"],
            "tourism_keywords": ["기장", "해동용궁사", "해동 용궁사", "용궁사", "Haedong Yonggungsa", "Haedong Yonggung Temple", "오시리아", "Osiria", "일광", "송정", "송정해수욕장", "Songjeong", "기장해안", "기장해안도로", "죽성성당", "아난티", "청사포", "기장카페거리", "드라이브"],
            "representative_poi_aliases": ["기장", "해동용궁사", "해동 용궁사", "용궁사", "Haedong Yonggungsa Temple", "Haedong Yonggung Temple", "오시리아", "Osiria", "일광", "송정", "송정해수욕장", "Songjeong Beach", "기장해안", "기장해안도로", "죽성성당", "아난티", "청사포", "기장카페거리"],
            "representative_categories": ["spot", "cafe", "drive"],
            "anchor": {"name": "해동용궁사", "lat": 35.1883, "lng": 129.2233},
            "nearby_anchor_aliases": ["오시리아", "일광", "송정", "송정해수욕장", "죽성성당", "아난티", "청사포", "기장해안"],
            "mobility_traits": ["drive", "sea", "family"],
        },
    },
    "제주": {
        "애월": {
            "vibe_tags": ["해안도로", "카페", "드라이브", "노을", "감성"],
            "tourism_keywords": ["애월", "한담", "곽지"],
            "representative_poi_aliases": ["애월", "한담해변", "한담해안산책로", "곽지해수욕장"],
            "representative_categories": ["cafe", "spot", "drive"],
            "anchor": {"name": "애월한담", "lat": 33.4627, "lng": 126.3097},
            "nearby_anchor_aliases": ["한담", "곽지", "협재"],
            "mobility_traits": ["drive", "sea", "cafe"],
        },
        "성산": {
            "vibe_tags": ["일출", "오름", "해안", "가족", "드라이브"],
            "tourism_keywords": ["성산", "성산일출봉", "섭지코지"],
            "representative_poi_aliases": ["성산", "성산일출봉", "섭지코지", "광치기해변"],
            "representative_categories": ["spot", "nature", "drive"],
            "anchor": {"name": "성산일출봉", "lat": 33.4581, "lng": 126.9425},
            "nearby_anchor_aliases": ["섭지코지", "광치기", "우도"],
            "mobility_traits": ["drive", "nature", "family"],
        },
        "중문": {
            "vibe_tags": ["리조트", "해변", "가족", "전망", "드라이브"],
            "tourism_keywords": ["중문", "색달", "주상절리"],
            "representative_poi_aliases": ["중문", "중문색달해변", "주상절리", "천제연"],
            "representative_categories": ["spot", "family", "nature"],
            "anchor": {"name": "중문색달해변", "lat": 33.2450, "lng": 126.4115},
            "nearby_anchor_aliases": ["색달", "주상절리", "천제연"],
            "mobility_traits": ["drive", "family", "sea"],
        },
        "서귀포": {
            "vibe_tags": ["폭포", "시장", "항구", "도심", "가족"],
            "tourism_keywords": ["서귀포", "천지연", "이중섭거리", "올레시장"],
            "representative_poi_aliases": ["서귀포", "천지연폭포", "이중섭거리", "서귀포매일올레시장"],
            "representative_categories": ["culture", "meal", "spot"],
            "anchor": {"name": "서귀포매일올레시장", "lat": 33.2501, "lng": 126.5639},
            "nearby_anchor_aliases": ["천지연", "정방폭포", "이중섭거리"],
            "mobility_traits": ["walking", "food", "family"],
        },
        "함덕": {
            "vibe_tags": ["바다", "해변", "카페", "가족", "동부"],
            "tourism_keywords": ["함덕", "조천", "서우봉"],
            "representative_poi_aliases": ["함덕", "함덕해수욕장", "서우봉", "조천"],
            "representative_categories": ["spot", "cafe", "walk"],
            "anchor": {"name": "함덕해수욕장", "lat": 33.5431, "lng": 126.6690},
            "nearby_anchor_aliases": ["서우봉", "조천", "김녕"],
            "mobility_traits": ["walking", "sea", "family"],
        },
        "협재": {
            "vibe_tags": ["바다", "비양도", "노을", "카페", "서부"],
            "tourism_keywords": ["협재", "금능", "비양도"],
            "representative_poi_aliases": ["협재", "협재해수욕장", "금능해수욕장", "비양도"],
            "representative_categories": ["spot", "cafe", "drive"],
            "anchor": {"name": "협재해수욕장", "lat": 33.3947, "lng": 126.2397},
            "nearby_anchor_aliases": ["금능", "비양도", "한림"],
            "mobility_traits": ["drive", "sea", "sunset"],
        },
    },
    "전북": {
        "전주": {
            "vibe_tags": ["한옥", "역사", "디저트", "도보", "가족"],
            "tourism_keywords": ["전주", "한옥마을", "경기전", "객리단길"],
            "representative_poi_aliases": ["전주", "전주한옥마을", "경기전", "객리단길", "객사"],
            "representative_categories": ["culture", "cafe", "history"],
            "anchor": {"name": "전주한옥마을", "lat": 35.8151, "lng": 127.1530},
            "nearby_anchor_aliases": ["경기전", "객리단길", "남부시장"],
            "mobility_traits": ["walking", "heritage", "cafe"],
        },
        "군산": {
            "vibe_tags": ["근대문화", "항구", "빵집", "도보", "레트로"],
            "tourism_keywords": ["군산", "근대거리", "월명동", "초원사진관"],
            "representative_poi_aliases": ["군산", "군산근대거리", "근대문화거리", "월명동", "초원사진관"],
            "representative_categories": ["culture", "history", "meal"],
            "anchor": {"name": "군산근대문화거리", "lat": 35.9893, "lng": 126.7110},
            "nearby_anchor_aliases": ["월명동", "초원사진관", "이성당"],
            "mobility_traits": ["walking", "heritage", "food"],
        },
        "익산": {
            "vibe_tags": ["백제", "역사", "공원", "가족", "드라이브"],
            "tourism_keywords": ["익산", "미륵사지", "왕궁리"],
            "representative_poi_aliases": ["익산", "미륵사지", "왕궁리", "익산역"],
            "representative_categories": ["history", "culture", "family"],
            "anchor": {"name": "미륵사지", "lat": 36.0120, "lng": 127.0311},
            "nearby_anchor_aliases": ["왕궁리", "익산역", "중앙동"],
            "mobility_traits": ["drive", "history", "family"],
        },
        "남원": {
            "vibe_tags": ["춘향", "광한루", "정원", "가족", "전통"],
            "tourism_keywords": ["남원", "광한루", "춘향테마파크"],
            "representative_poi_aliases": ["남원", "광한루", "광한루원", "춘향테마파크"],
            "representative_categories": ["culture", "history", "family"],
            "anchor": {"name": "광한루원", "lat": 35.4050, "lng": 127.3849},
            "nearby_anchor_aliases": ["춘향", "요천", "남원역"],
            "mobility_traits": ["walking", "heritage", "family"],
        },
        "고창": {
            "vibe_tags": ["고인돌", "읍성", "자연", "드라이브", "가족"],
            "tourism_keywords": ["고창", "고인돌", "고창읍성", "선운사"],
            "representative_poi_aliases": ["고창", "고창읍성", "고인돌유적", "선운사"],
            "representative_categories": ["history", "nature", "drive"],
            "anchor": {"name": "고창읍성", "lat": 35.4358, "lng": 126.7048},
            "nearby_anchor_aliases": ["고인돌", "선운사", "상하농원"],
            "mobility_traits": ["drive", "nature", "history"],
        },
        "부안": {
            "vibe_tags": ["해안", "채석강", "변산", "드라이브", "노을"],
            "tourism_keywords": ["부안", "변산", "채석강", "격포"],
            "representative_poi_aliases": ["부안", "변산반도", "채석강", "격포항"],
            "representative_categories": ["nature", "spot", "drive"],
            "anchor": {"name": "채석강", "lat": 35.6227, "lng": 126.4695},
            "nearby_anchor_aliases": ["변산", "격포", "내소사"],
            "mobility_traits": ["drive", "sea", "sunset"],
        },
        "정읍": {
            "vibe_tags": ["내장산", "단풍", "자연", "드라이브", "가족"],
            "tourism_keywords": ["정읍", "내장산", "쌍화차거리"],
            "representative_poi_aliases": ["정읍", "내장산", "내장산국립공원", "쌍화차거리"],
            "representative_categories": ["nature", "cafe", "family"],
            "anchor": {"name": "내장산", "lat": 35.4780, "lng": 126.8890},
            "nearby_anchor_aliases": ["쌍화차거리", "정읍역", "내장사"],
            "mobility_traits": ["drive", "nature", "seasonal"],
        },
    },
    "전남": {
        "여수밤바다": {
            "vibe_tags": ["바다", "야경", "해양", "산책", "카페"],
            "tourism_keywords": ["여수", "여수밤바다", "해양공원", "낭만포차", "오션뷰", "카페"],
            "representative_poi_aliases": ["여수", "여수밤바다", "종포해양공원", "해양공원", "낭만포차"],
            "representative_categories": ["spot", "cafe", "walk"],
            "anchor": {"name": "여수밤바다", "lat": 34.7380, "lng": 127.7420},
            "nearby_anchor_aliases": ["종포", "해양공원", "이순신광장", "오동도"],
            "mobility_traits": ["walking", "night", "sea_view", "cafe_relaxed"],
        },
        "이순신광장": {
            "vibe_tags": ["광장", "먹거리", "도보", "해양", "카페"],
            "tourism_keywords": ["여수", "이순신광장", "중앙동", "해양공원", "디저트"],
            "representative_poi_aliases": ["이순신광장", "중앙동", "여수당", "여수돌게빵"],
            "representative_categories": ["spot", "meal", "cafe"],
            "anchor": {"name": "이순신광장", "lat": 34.7384, "lng": 127.7361},
            "nearby_anchor_aliases": ["중앙동", "해양공원", "진남관"],
            "mobility_traits": ["walking", "food", "cafe_relaxed"],
        },
        "오동도": {
            "vibe_tags": ["섬", "산책", "바다", "자연", "카페"],
            "tourism_keywords": ["여수", "오동도", "동백", "해상케이블카", "바다"],
            "representative_poi_aliases": ["오동도", "동백섬", "여수해상케이블카"],
            "representative_categories": ["spot", "walk", "cafe"],
            "anchor": {"name": "오동도", "lat": 34.7442, "lng": 127.7666},
            "nearby_anchor_aliases": ["자산공원", "해상케이블카", "돌산"],
            "mobility_traits": ["walking", "nature", "sea_view"],
        },
        "돌산": {
            "vibe_tags": ["드라이브", "오션뷰", "카페", "노을", "해안"],
            "tourism_keywords": ["여수", "돌산", "돌산대교", "오션뷰", "드라이브", "카페"],
            "representative_poi_aliases": ["돌산", "돌산대교", "돌산공원", "모이핀", "로스티아"],
            "representative_categories": ["cafe", "spot", "drive"],
            "anchor": {"name": "돌산", "lat": 34.6960, "lng": 127.7520},
            "nearby_anchor_aliases": ["돌산공원", "돌산대교", "무슬목"],
            "mobility_traits": ["drive", "sea_view", "cafe_relaxed"],
        },
        "해양공원": {
            "vibe_tags": ["해양", "산책", "밤바다", "카페", "도보"],
            "tourism_keywords": ["여수", "해양공원", "종포", "밤바다", "카페", "디저트"],
            "representative_poi_aliases": ["해양공원", "종포해양공원", "여수밤바다"],
            "representative_categories": ["spot", "cafe", "walk"],
            "anchor": {"name": "종포해양공원", "lat": 34.7380, "lng": 127.7420},
            "nearby_anchor_aliases": ["종포", "이순신광장", "낭만포차"],
            "mobility_traits": ["walking", "night_sea", "cafe_relaxed"],
        },
    },
    "강원": {
        "영랑호": {
            "vibe_tags": ["호수", "산책", "카페", "감성", "속초"],
            "tourism_keywords": ["속초", "영랑호", "호수뷰", "산책", "카페", "로컬"],
            "representative_poi_aliases": ["영랑호", "영랑호수윗길", "영랑호 카페", "속초 카페"],
            "representative_categories": ["cafe", "walk", "spot"],
            "anchor": {"name": "영랑호", "lat": 38.2165, "lng": 128.5907},
            "nearby_anchor_aliases": ["장사항", "속초등대", "동명항"],
            "mobility_traits": ["walking", "cafe_relaxed", "lake_view"],
        },
        "속초해수욕장": {
            "vibe_tags": ["바다", "해변", "카페", "오션뷰", "속초"],
            "tourism_keywords": ["속초", "속초해수욕장", "바다", "해변", "오션뷰", "카페"],
            "representative_poi_aliases": ["속초해수욕장", "속초아이", "속초 바다", "해변 카페"],
            "representative_categories": ["cafe", "spot", "sea"],
            "anchor": {"name": "속초해수욕장", "lat": 38.1905, "lng": 128.6031},
            "nearby_anchor_aliases": ["외옹치", "청호동", "속초아이"],
            "mobility_traits": ["walking", "sea_view", "cafe_relaxed"],
        },
        "대포항": {
            "vibe_tags": ["항구", "해산물", "바다", "로컬", "드라이브"],
            "tourism_keywords": ["속초", "대포항", "항구", "해산물", "바다", "로컬"],
            "representative_poi_aliases": ["대포항", "대포항전망대", "대포항 카페", "대포항 수산시장"],
            "representative_categories": ["meal", "spot", "cafe"],
            "anchor": {"name": "대포항", "lat": 38.1744, "lng": 128.6066},
            "nearby_anchor_aliases": ["외옹치", "롯데리조트속초", "대포동"],
            "mobility_traits": ["drive", "seafood_local", "sea_view"],
        },
        "중앙시장": {
            "vibe_tags": ["시장", "먹거리", "로컬", "도보", "속초"],
            "tourism_keywords": ["속초", "중앙시장", "관광수산시장", "먹거리", "로컬"],
            "representative_poi_aliases": ["속초중앙시장", "속초관광수산시장", "중앙시장", "닭강정거리"],
            "representative_categories": ["meal", "market", "walk"],
            "anchor": {"name": "속초중앙시장", "lat": 38.2043, "lng": 128.5908},
            "nearby_anchor_aliases": ["갯배", "아바이마을", "청초호"],
            "mobility_traits": ["walking", "seafood_local", "food"],
        },
        "청초호": {
            "vibe_tags": ["호수", "엑스포", "산책", "카페", "속초"],
            "tourism_keywords": ["속초", "청초호", "엑스포", "호수", "산책", "카페"],
            "representative_poi_aliases": ["청초호", "청초호수공원", "엑스포타워", "청초호 카페"],
            "representative_categories": ["cafe", "walk", "spot"],
            "anchor": {"name": "청초호", "lat": 38.1996, "lng": 128.5874},
            "nearby_anchor_aliases": ["엑스포", "속초중앙시장", "아바이마을"],
            "mobility_traits": ["walking", "cafe_relaxed", "lake_view"],
        },
        "강릉경포": {
            "vibe_tags": ["바다", "호수", "카페", "산책", "강릉"],
            "tourism_keywords": ["강릉", "경포", "경포대", "경포호", "해변", "카페"],
            "representative_poi_aliases": ["경포대", "경포호", "경포해변", "강릉 경포"],
            "representative_categories": ["cafe", "spot", "sea"],
            "anchor": {"name": "경포해변", "lat": 37.8050, "lng": 128.9089},
            "nearby_anchor_aliases": ["초당", "안목", "강문"],
            "mobility_traits": ["walking", "sea_view", "cafe_relaxed"],
        },
        "안목커피거리": {
            "vibe_tags": ["커피", "바다", "카페", "오션뷰", "강릉"],
            "tourism_keywords": ["강릉", "안목", "커피거리", "카페", "오션뷰", "바다"],
            "representative_poi_aliases": ["안목커피거리", "안목해변", "강릉 커피거리", "안목 카페"],
            "representative_categories": ["cafe", "walk", "sea"],
            "anchor": {"name": "안목커피거리", "lat": 37.7715, "lng": 128.9471},
            "nearby_anchor_aliases": ["강문", "송정", "초당"],
            "mobility_traits": ["walking", "sea_view", "cafe_relaxed"],
        },
        "주문진": {
            "vibe_tags": ["항구", "바다", "로컬", "드라이브", "강릉"],
            "tourism_keywords": ["강릉", "주문진", "항구", "해변", "수산시장", "바다"],
            "representative_poi_aliases": ["주문진", "주문진항", "주문진해변", "주문진수산시장"],
            "representative_categories": ["meal", "spot", "drive"],
            "anchor": {"name": "주문진항", "lat": 37.8937, "lng": 128.8294},
            "nearby_anchor_aliases": ["소돌", "영진", "향호"],
            "mobility_traits": ["drive", "seafood_local", "sea_view"],
        },
    },
}


def _iter_belts(region: str | None = None):
    regions = [region] if region and region in REGION_IDENTITY_BELTS else REGION_IDENTITY_BELTS.keys()
    for region_name in regions:
        for belt_name, meta in REGION_IDENTITY_BELTS.get(region_name, {}).items():
            yield region_name, belt_name, meta


def get_region_identity(region: str | None) -> dict[str, dict[str, Any]]:
    """Return region belt metadata without exposing mutable internals."""
    return dict(REGION_IDENTITY_BELTS.get(str(region or ""), {}))


_BROAD_REGION_BELT_PRIORITIES: dict[str, list[str]] = {
    "서울": ["북촌", "익선", "성수", "한남", "을지로", "홍대", "잠실"],
    "부산": ["해운대", "광안리", "남포", "영도", "기장", "서면"],
    "제주": ["애월", "성산", "중문", "서귀포", "함덕", "협재"],
    "강원": ["속초해수욕장", "영랑호", "청초호", "대포항", "중앙시장", "강릉경포", "안목커피거리", "주문진"],
    "전남": ["여수밤바다", "이순신광장", "해양공원", "오동도", "돌산"],
}

REGION_IDENTITY_BELTS.setdefault("강원", {}).update({
    "양양서핑": {
        "vibe_tags": ["서핑", "바다", "오션뷰", "카페", "양양"],
        "tourism_keywords": ["양양", "죽도해변", "인구해변", "서핑", "서피비치", "바다", "카페"],
        "representative_poi_aliases": ["죽도해변", "인구해변", "서피비치", "양양 서핑"],
        "representative_categories": ["spot", "cafe", "sea"],
        "anchor": {"name": "죽도해변", "lat": 37.9720, "lng": 128.7600},
        "nearby_anchor_aliases": ["인구해변", "현남", "서피비치"],
        "mobility_traits": ["sea_view", "cafe_relaxed", "surf"],
    },
})

REGION_IDENTITY_BELTS.setdefault("경남", {}).update({
    "통영동피랑": {
        "vibe_tags": ["항구", "벽화마을", "산책", "바다", "통영"],
        "tourism_keywords": ["통영", "동피랑", "강구안", "항구", "벽화마을", "바다"],
        "representative_poi_aliases": ["동피랑", "동피랑벽화마을", "강구안", "통영항"],
        "representative_categories": ["spot", "walk", "cafe"],
        "anchor": {"name": "동피랑", "lat": 34.8466, "lng": 128.4240},
        "nearby_anchor_aliases": ["강구안", "중앙시장", "통영항"],
        "mobility_traits": ["walking", "sea_view", "cafe_relaxed"],
    },
    "통영미륵산": {
        "vibe_tags": ["전망", "케이블카", "바다", "드라이브", "통영"],
        "tourism_keywords": ["통영", "미륵산", "케이블카", "전망", "한려수도"],
        "representative_poi_aliases": ["미륵산", "통영케이블카", "한려수도조망"],
        "representative_categories": ["spot", "nature", "drive"],
        "anchor": {"name": "통영케이블카", "lat": 34.8272, "lng": 128.4264},
        "nearby_anchor_aliases": ["미수동", "도남동", "한려수도"],
        "mobility_traits": ["drive", "sea_view", "family"],
    },
    "거제바람의언덕": {
        "vibe_tags": ["바다", "바람", "드라이브", "오션뷰", "거제"],
        "tourism_keywords": ["거제", "바람의언덕", "외도", "해금강", "오션뷰", "드라이브"],
        "representative_poi_aliases": ["바람의언덕", "외도", "해금강", "도장포"],
        "representative_categories": ["spot", "drive", "sea"],
        "anchor": {"name": "바람의언덕", "lat": 34.7445, "lng": 128.6630},
        "nearby_anchor_aliases": ["도장포", "해금강", "외도"],
        "mobility_traits": ["drive", "sea_view", "cafe_relaxed"],
    },
    "남해독일마을": {
        "vibe_tags": ["해안", "마을", "감성", "드라이브", "남해"],
        "tourism_keywords": ["남해", "독일마을", "다랭이마을", "해안도로", "오션뷰"],
        "representative_poi_aliases": ["독일마을", "다랭이마을", "남해 해안도로"],
        "representative_categories": ["spot", "cafe", "drive"],
        "anchor": {"name": "남해독일마을", "lat": 34.7995, "lng": 128.0396},
        "nearby_anchor_aliases": ["물건리", "다랭이마을", "상주은모래비치"],
        "mobility_traits": ["drive", "sea_view", "walk_emotional"],
    },
})

REGION_IDENTITY_BELTS.setdefault("경북", {}).update({
    "경주황리단길": {
        "vibe_tags": ["역사", "한옥", "카페", "산책", "경주"],
        "tourism_keywords": ["경주", "황리단길", "첨성대", "대릉원", "역사", "한옥"],
        "representative_poi_aliases": ["황리단길", "첨성대", "대릉원", "동궁과월지"],
        "representative_categories": ["history", "culture", "cafe"],
        "anchor": {"name": "황리단길", "lat": 35.8366, "lng": 129.2118},
        "nearby_anchor_aliases": ["첨성대", "대릉원", "교촌마을"],
        "mobility_traits": ["history_walk", "walking", "cafe_relaxed"],
    },
    "포항영일대": {
        "vibe_tags": ["바다", "야경", "해변", "카페", "포항"],
        "tourism_keywords": ["포항", "영일대", "호미곶", "바다", "해변", "오션뷰"],
        "representative_poi_aliases": ["영일대", "영일대해수욕장", "호미곶", "포항 바다"],
        "representative_categories": ["spot", "cafe", "sea"],
        "anchor": {"name": "영일대해수욕장", "lat": 36.0610, "lng": 129.3787},
        "nearby_anchor_aliases": ["환호공원", "죽도시장", "호미곶"],
        "mobility_traits": ["sea_view", "cafe_relaxed", "night_sea"],
    },
})

REGION_IDENTITY_BELTS.setdefault("경기", {}).update({
    "수원화성": {
        "vibe_tags": ["역사", "성곽", "행궁", "산책", "수원"],
        "tourism_keywords": ["수원", "수원화성", "행궁동", "화성행궁", "역사", "성곽"],
        "representative_poi_aliases": ["수원화성", "화성행궁", "행궁동", "장안문"],
        "representative_categories": ["history", "culture", "walk"],
        "anchor": {"name": "화성행궁", "lat": 37.2819, "lng": 127.0142},
        "nearby_anchor_aliases": ["행궁동", "수원화성", "장안문"],
        "mobility_traits": ["history_walk", "walking", "cafe_relaxed"],
    },
    "가평북한강": {
        "vibe_tags": ["자연", "드라이브", "강변", "카페", "가평"],
        "tourism_keywords": ["가평", "북한강", "남이섬", "아침고요수목원", "자연", "드라이브"],
        "representative_poi_aliases": ["북한강", "남이섬", "아침고요수목원", "가평 자연"],
        "representative_categories": ["nature", "drive", "cafe"],
        "anchor": {"name": "남이섬", "lat": 37.7919, "lng": 127.5255},
        "nearby_anchor_aliases": ["자라섬", "청평", "쁘띠프랑스"],
        "mobility_traits": ["drive", "nature", "family"],
    },
})

REGION_IDENTITY_BELTS.setdefault("충남", {}).update({
    "공주공산성": {
        "vibe_tags": ["백제", "역사", "성곽", "산책", "공주"],
        "tourism_keywords": ["공주", "공산성", "백제", "무령왕릉", "역사", "산책"],
        "representative_poi_aliases": ["공산성", "무령왕릉", "송산리고분군", "공주 역사"],
        "representative_categories": ["history", "culture", "walk"],
        "anchor": {"name": "공산성", "lat": 36.4623, "lng": 127.1248},
        "nearby_anchor_aliases": ["무령왕릉", "국립공주박물관", "제민천"],
        "mobility_traits": ["history_walk", "walking", "family"],
    },
})

REGION_IDENTITY_BELTS.setdefault("대전", {}).update({
    "소제성심당": {
        "vibe_tags": ["카페", "빵집", "도심", "산책", "대전"],
        "tourism_keywords": ["대전", "성심당", "소제동", "카페", "카이스트", "도심"],
        "representative_poi_aliases": ["성심당", "소제동", "대전역", "카이스트"],
        "representative_categories": ["cafe", "meal", "city"],
        "anchor": {"name": "성심당", "lat": 36.3276, "lng": 127.4271},
        "nearby_anchor_aliases": ["소제동", "대흥동", "은행동"],
        "mobility_traits": ["cafe_relaxed", "walking", "food"],
    },
})

REGION_IDENTITY_BELTS.setdefault("전남", {}).update({
    "목포근대거리": {
        "vibe_tags": ["근대", "항구", "야경", "케이블카", "목포", "수변", "카페"],
        "tourism_keywords": ["목포", "근대거리", "해상케이블카", "유달산", "항구", "야경", "평화광장", "갓바위", "수변", "목포항"],
        "representative_poi_aliases": ["목포근대역사거리", "목포근대역사관", "목포해상케이블카", "유달산", "평화광장", "갓바위", "목포항"],
        "representative_categories": ["history", "spot", "night"],
        "anchor": {"name": "목포근대역사거리", "lat": 34.7870, "lng": 126.3828},
        "nearby_anchor_aliases": ["유달산", "목포항", "삼학도", "평화광장", "갓바위", "해상케이블카"],
        "mobility_traits": ["history_walk", "night_sea", "walking", "sea_view", "cafe_relaxed"],
    },
    "순천만정원": {
        "vibe_tags": ["정원", "습지", "산책", "자연", "순천"],
        "tourism_keywords": ["순천", "국가정원", "순천만", "습지", "산책", "자연"],
        "representative_poi_aliases": ["순천만국가정원", "순천만습지", "순천만", "국가정원"],
        "representative_categories": ["nature", "walk", "spot"],
        "anchor": {"name": "순천만국가정원", "lat": 34.9294, "lng": 127.5090},
        "nearby_anchor_aliases": ["순천만습지", "동천", "드라마촬영장"],
        "mobility_traits": ["walking", "nature", "family"],
    },
})

_BROAD_REGION_BELT_PRIORITIES.update({
    "강원": ["속초해수욕장", "영랑호", "청초호", "대포항", "중앙시장", "양양서핑", "강릉경포", "안목커피거리", "주문진"],
    "경남": ["통영동피랑", "통영미륵산", "거제바람의언덕", "남해독일마을"],
    "경북": ["경주황리단길", "포항영일대"],
    "경기": ["수원화성", "가평북한강"],
    "충남": ["공주공산성"],
    "대전": ["소제성심당"],
    "전남": ["여수밤바다", "이순신광장", "해양공원", "오동도", "돌산", "목포근대거리", "순천만정원"],
})


_SEOUL_DISTRICT_INTENT_WEIGHTS: dict[str, dict[str, Any]] = {
    "cafe": {
        "positive": ["cafe", "카페", "coffee", "디저트", "브런치", "lifestyle"],
        "preferred_categories": {"cafe", "culture", "walk"},
        "preferred_traits": {"cafe", "walking", "lifestyle", "date"},
    },
    "date": {
        "positive": ["date", "데이트", "감성", "골목", "한옥", "night"],
        "preferred_categories": {"cafe", "culture", "meal"},
        "preferred_traits": {"date", "walking", "night", "lifestyle", "heritage"},
    },
    "night": {
        "positive": ["night", "야경", "야간", "bar", "city"],
        "preferred_categories": {"night", "meal", "cafe", "city", "culture"},
        "preferred_traits": {"night", "food", "walking", "youth"},
    },
    "history": {
        "positive": ["history", "역사", "heritage", "한옥", "궁", "문화"],
        "preferred_categories": {"history", "culture", "walk"},
        "preferred_traits": {"history", "heritage", "walking"},
    },
    "family": {
        "positive": ["family", "가족", "leisure", "kids"],
        "preferred_categories": {"family", "spot", "city", "culture"},
        "preferred_traits": {"family", "walking", "night"},
    },
    "default": {
        "positive": ["walk", "walking", "산책", "culture", "문화", "cafe", "카페"],
        "preferred_categories": {"culture", "walk", "cafe", "history"},
        "preferred_traits": {"walking", "date", "lifestyle", "heritage"},
    },
}


def _broad_region_belt_candidates(region: str | None) -> list[dict[str, Any]]:
    belts = get_region_identity(region)
    priorities = _BROAD_REGION_BELT_PRIORITIES.get(str(region or ""), [])
    if not priorities:
        priorities = sorted(belts.keys())
    candidates = []
    for idx, belt_name in enumerate(priorities):
        meta = belts.get(belt_name)
        if not meta:
            continue
        candidates.append({
            "belt": belt_name,
            "priority": idx + 1,
            "anchor": dict(meta.get("anchor") or {}),
            "vibe_tags": list(meta.get("vibe_tags") or [])[:5],
            "mobility_traits": list(meta.get("mobility_traits") or [])[:5],
        })
    return candidates


def _broad_region_default_identity(region: str | None) -> dict[str, Any] | None:
    if str(region or "") not in _BROAD_REGION_BELT_PRIORITIES:
        return None
    candidates = _broad_region_belt_candidates(region)
    if not candidates:
        return None
    belt_name = candidates[0]["belt"]
    meta = get_region_identity(region).get(belt_name, {})
    return {
        "region": region,
        "inferred_belt": belt_name,
        "belt_confidence": 0.42,
        "belt_anchor_match": "broad_region_representative_seed",
        "matched_aliases": [belt_name],
        "vibe_tags": list(meta.get("vibe_tags") or []),
        "tourism_keywords": list(meta.get("tourism_keywords") or []),
        "representative_categories": list(meta.get("representative_categories") or []),
        "mobility_traits": list(meta.get("mobility_traits") or []),
        "anchor": dict(meta.get("anchor") or {}),
        "available_belts": sorted(get_region_identity(region).keys()),
        "broad_region_belt_candidates": candidates,
        "inference_reason": "broad_region_default_representative_belt",
    }


def _infer_seoul_intent_key(
    *,
    themes: list[Any] | None = None,
    movement_option: Any = None,
    companion: Any = None,
    source_terms: list[Any] | None = None,
) -> str:
    terms: list[Any] = []
    terms.extend(themes or [])
    terms.append(movement_option)
    terms.append(companion)
    terms.extend(source_terms or [])
    joined = normalize_identity_token(" ".join(str(term) for term in terms if term))
    if any(token in joined for token in ("cafe", "카페", "coffee", "디저트", "브런치")):
        return "cafe"
    if any(token in joined for token in ("date", "데이트")):
        return "date"
    if any(token in joined for token in ("night", "야경", "야간")):
        return "night"
    if any(token in joined for token in ("history", "역사", "heritage", "한옥", "궁", "문화")):
        return "history"
    if any(token in joined for token in ("family", "가족", "kids")):
        return "family"
    return "default"


def infer_seoul_district_vibe(
    region_identity: dict[str, Any] | None,
    *,
    themes: list[Any] | None = None,
    movement_option: Any = None,
    companion: Any = None,
    source_terms: list[Any] | None = None,
) -> dict[str, Any]:
    """Infer a soft dominant Seoul district for broad Seoul requests.

    Seoul is treated as a district/vibe ecosystem. The returned signal is
    advisory and should only be used as a small coherence preference, never as
    a hard district lock.
    """
    if not isinstance(region_identity, dict):
        return {}
    region = region_identity.get("region")
    if str(region or "") != "서울":
        return {}

    belts = get_region_identity(str(region))
    if not belts:
        return {}

    intent_key = _infer_seoul_intent_key(
        themes=themes,
        movement_option=movement_option,
        companion=companion,
        source_terms=source_terms,
    )
    intent = _SEOUL_DISTRICT_INTENT_WEIGHTS.get(intent_key) or _SEOUL_DISTRICT_INTENT_WEIGHTS["default"]
    priorities = _BROAD_REGION_BELT_PRIORITIES.get("서울", list(belts.keys()))
    source_text = normalize_identity_token(" ".join(str(term) for term in (source_terms or []) if term))

    scored: list[dict[str, Any]] = []
    for idx, district in enumerate(priorities):
        meta = belts.get(district)
        if not meta:
            continue

        categories = {str(value) for value in (meta.get("representative_categories") or [])}
        traits = {str(value) for value in (meta.get("mobility_traits") or [])}
        aliases = [
            district,
            *(meta.get("tourism_keywords") or []),
            *(meta.get("representative_poi_aliases") or []),
            *(meta.get("nearby_anchor_aliases") or []),
            dict(meta.get("anchor") or {}).get("name"),
        ]
        alias_matches = _alias_matches(source_text, aliases) if source_text else []
        category_matches = sorted(categories & set(intent.get("preferred_categories") or set()))
        trait_matches = sorted(traits & set(intent.get("preferred_traits") or set()))

        score = 0.30 + max(0, 7 - idx) * 0.01
        reasons = [f"priority:{idx + 1}"]
        if alias_matches:
            score += 0.22
            reasons.append("district_alias:" + ",".join(alias_matches[:3]))
        if category_matches:
            score += min(0.18, 0.06 * len(category_matches))
            reasons.append("district_category:" + ",".join(category_matches[:3]))
        if trait_matches:
            score += min(0.16, 0.05 * len(trait_matches))
            reasons.append("district_trait:" + ",".join(trait_matches[:3]))

        scored.append({
            "district": district,
            "score": round(min(score, 0.95), 4),
            "matched_reasons": reasons,
            "anchor": dict(meta.get("anchor") or {}),
            "vibe_tags": list(meta.get("vibe_tags") or [])[:5],
            "representative_categories": list(meta.get("representative_categories") or [])[:5],
            "mobility_traits": list(meta.get("mobility_traits") or [])[:5],
            "selected_as_dominant": False,
        })

    scored.sort(key=lambda row: (-float(row.get("score") or 0.0), str(row.get("district") or "")))
    if not scored:
        return {}

    dominant = scored[0]["district"]
    for row in scored:
        row["selected_as_dominant"] = row.get("district") == dominant
    dominant_meta = belts.get(str(dominant), {})
    return {
        "dominant_district": dominant,
        "district_candidate_scores": scored,
        "district_vibe_reason": {
            "intent_key": intent_key,
            "reason": "seoul_broad_district_vibe_soft_selection",
            "hard_lock": False,
            "fallback_allowed": True,
        },
        "dominant_district_identity": {
            "inferred_belt": dominant,
            "belt_confidence": max(float(region_identity.get("belt_confidence") or 0.0), float(scored[0].get("score") or 0.0)),
            "belt_anchor_match": "seoul_district_vibe_soft_selection",
            "matched_aliases": [dominant],
            "vibe_tags": list(dominant_meta.get("vibe_tags") or []),
            "tourism_keywords": list(dominant_meta.get("tourism_keywords") or []),
            "representative_categories": list(dominant_meta.get("representative_categories") or []),
            "mobility_traits": list(dominant_meta.get("mobility_traits") or []),
            "anchor": dict(dominant_meta.get("anchor") or {}),
        },
    }


def infer_region_belt(
    region: str | None,
    *,
    selected_anchor: Any = None,
    text_terms: list[Any] | None = None,
) -> dict[str, Any]:
    """Infer a tourism belt from anchor/text evidence.

    The result is intentionally advisory. It is suitable for request tracing,
    QA fixtures, and future orchestration, but not for hard locality filtering.
    """
    terms = [selected_anchor] if selected_anchor else []
    terms.extend(text_terms or [])
    normalized_terms = [normalize_identity_token(term) for term in terms if normalize_identity_token(term)]
    if not normalized_terms:
        broad_default = _broad_region_default_identity(region)
        if broad_default:
            return broad_default
        return {
            "region": region,
            "inferred_belt": None,
            "belt_confidence": 0.0,
            "belt_anchor_match": None,
            "matched_aliases": [],
            "available_belts": sorted(get_region_identity(region).keys()),
            "broad_region_belt_candidates": _broad_region_belt_candidates(region),
        }

    best: tuple[float, str, str, dict[str, Any], list[str]] | None = None
    for region_name, belt_name, meta in _iter_belts(region):
        aliases = [belt_name]
        aliases.extend(meta.get("tourism_keywords") or [])
        aliases.extend(meta.get("representative_poi_aliases") or [])
        aliases.extend(meta.get("nearby_anchor_aliases") or [])
        anchor = meta.get("anchor") or {}
        aliases.append(anchor.get("name"))

        matched = []
        for alias in aliases:
            alias_token = normalize_identity_token(alias)
            if alias_token and any(alias_token in term or term in alias_token for term in normalized_terms):
                matched.append(str(alias))

        if not matched:
            continue

        score = min(0.95, 0.55 + 0.1 * len(set(matched)))
        if any(normalize_identity_token(belt_name) in term for term in normalized_terms):
            score = min(0.98, score + 0.15)

        if best is None or score > best[0]:
            best = (score, region_name, belt_name, meta, sorted(set(matched)))

    if best is None:
        broad_default = _broad_region_default_identity(region)
        if broad_default:
            return broad_default
        return {
            "region": region,
            "inferred_belt": None,
            "belt_confidence": 0.0,
            "belt_anchor_match": None,
            "matched_aliases": [],
            "available_belts": sorted(get_region_identity(region).keys()),
            "broad_region_belt_candidates": _broad_region_belt_candidates(region),
        }

    score, region_name, belt_name, meta, matched = best
    return {
        "region": region_name,
        "inferred_belt": belt_name,
        "belt_confidence": round(score, 4),
        "belt_anchor_match": matched[0] if matched else None,
        "matched_aliases": matched,
        "vibe_tags": list(meta.get("vibe_tags") or []),
        "tourism_keywords": list(meta.get("tourism_keywords") or []),
        "representative_categories": list(meta.get("representative_categories") or []),
        "mobility_traits": list(meta.get("mobility_traits") or []),
        "anchor": dict(meta.get("anchor") or {}),
        "broad_region_belt_candidates": _broad_region_belt_candidates(region_name),
    }


def _place_identity_text(place: dict[str, Any]) -> str:
    terms: list[str] = []
    for key in (
        "name",
        "region_1",
        "region_2",
        "region",
        "city",
        "category",
        "address",
        "addr",
        "address_name",
        "overview",
        "visit_role",
        "data_source",
    ):
        value = place.get(key)
        if value:
            terms.append(str(value))

    ai_tags = place.get("ai_tags")
    if isinstance(ai_tags, dict):
        for tag_key in ("themes", "mood", "companion", "keywords"):
            for value in ai_tags.get(tag_key, []) or []:
                terms.append(str(value))

    return normalize_identity_token(" ".join(terms))


def _alias_matches(text: str, aliases: list[Any]) -> list[str]:
    matches: list[str] = []
    for alias in aliases:
        alias_token = normalize_identity_token(alias)
        if alias_token and alias_token in text:
            matches.append(str(alias))
    return sorted(set(matches))


_GENERIC_BELT_CATEGORY_TOKENS = {
    "spot",
    "culture",
    "walk",
    "walking",
    "drive",
    "nature",
    "family",
    "city",
    "view",
    "lifestyle",
}


def score_belt_match(place: dict[str, Any], region_identity: dict[str, Any] | None) -> dict[str, Any]:
    """Return small advisory belt-aware soft boost for a candidate.

    This is not a filter. Wrong-belt evidence is reported for observability
    only and does not demote the candidate.
    """
    if not isinstance(place, dict) or not isinstance(region_identity, dict):
        return {
            "inferred_belt": None,
            "belt_confidence": 0.0,
            "belt_match_bonus": 0.0,
            "belt_match_reasons": [],
            "wrong_belt_match": None,
        }

    region = region_identity.get("region")
    inferred_belt = region_identity.get("inferred_belt")
    if not region or not inferred_belt:
        return {
            "inferred_belt": inferred_belt,
            "belt_confidence": float(region_identity.get("belt_confidence") or 0.0),
            "belt_match_bonus": 0.0,
            "belt_match_reasons": [],
            "wrong_belt_match": None,
        }

    belt_meta = REGION_IDENTITY_BELTS.get(str(region), {}).get(str(inferred_belt), {})
    if not belt_meta:
        return {
            "inferred_belt": inferred_belt,
            "belt_confidence": float(region_identity.get("belt_confidence") or 0.0),
            "belt_match_bonus": 0.0,
            "belt_match_reasons": ["belt_metadata_missing"],
            "wrong_belt_match": None,
        }

    text = _place_identity_text(place)
    alias_matches = _alias_matches(
        text,
        [inferred_belt]
        + list(belt_meta.get("representative_poi_aliases") or [])
        + list(belt_meta.get("nearby_anchor_aliases") or [])
        + [dict(belt_meta.get("anchor") or {}).get("name")],
    )
    keyword_matches = _alias_matches(
        text,
        list(belt_meta.get("tourism_keywords") or [])
        + list(belt_meta.get("vibe_tags") or []),
    )
    category_matches = _alias_matches(
        text,
        [
            value for value in (
                list(belt_meta.get("representative_categories") or [])
                + list(belt_meta.get("mobility_traits") or [])
            )
            if normalize_identity_token(value) not in _GENERIC_BELT_CATEGORY_TOKENS
        ],
    )

    bonus = 0.0
    reasons: list[str] = []
    if alias_matches:
        bonus += 0.10
        reasons.append("belt_alias_match:" + ",".join(alias_matches[:3]))
    if keyword_matches:
        bonus += 0.05
        reasons.append("belt_keyword_match:" + ",".join(keyword_matches[:3]))
    if category_matches:
        bonus += 0.04
        reasons.append("belt_category_match:" + ",".join(category_matches[:3]))

    wrong_belt_match = None
    for other_belt, other_meta in REGION_IDENTITY_BELTS.get(str(region), {}).items():
        if other_belt == inferred_belt:
            continue
        other_matches = _alias_matches(
            text,
            [other_belt]
            + list(other_meta.get("tourism_keywords") or [])
            + list(other_meta.get("representative_poi_aliases") or [])
            + list(other_meta.get("nearby_anchor_aliases") or []),
        )
        if other_matches:
            wrong_belt_match = {
                "belt": other_belt,
                "matched_aliases": other_matches[:5],
            }
            break

    return {
        "inferred_belt": inferred_belt,
        "belt_confidence": round(float(region_identity.get("belt_confidence") or 0.0), 4),
        "belt_match_bonus": round(bonus, 4),
        "belt_match_reasons": reasons,
        "belt_alias_matches": alias_matches[:5],
        "belt_keyword_matches": keyword_matches[:5],
        "belt_category_matches": category_matches[:5],
        "wrong_belt_match": wrong_belt_match,
    }


def score_dominant_belt_affinity(
    place: dict[str, Any],
    region_identity: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a small broad-region dominant-belt affinity signal.

    The signal is advisory and deliberately small. It should improve course
    coherence for broad region requests without blocking cross-belt fallback.
    """
    if not isinstance(place, dict) or not isinstance(region_identity, dict):
        return {
            "dominant_belt": None,
            "dominant_belt_bonus": 0.0,
            "dominant_belt_reasons": [],
        }

    dominant_belt = region_identity.get("inferred_belt")
    candidates = region_identity.get("broad_region_belt_candidates") or []
    if not dominant_belt or not candidates:
        return {
            "dominant_belt": dominant_belt,
            "dominant_belt_bonus": 0.0,
            "dominant_belt_reasons": [],
        }

    text = _place_identity_text(place)
    region = region_identity.get("region")
    meta = REGION_IDENTITY_BELTS.get(str(region), {}).get(str(dominant_belt), {})
    aliases = [
        dominant_belt,
        *(meta.get("tourism_keywords") or []),
        *(meta.get("representative_poi_aliases") or []),
        *(meta.get("nearby_anchor_aliases") or []),
        dict(meta.get("anchor") or {}).get("name"),
    ]
    alias_matches = _alias_matches(text, aliases)
    category_matches = _alias_matches(
        text,
        list(meta.get("representative_categories") or [])
        + list(meta.get("mobility_traits") or []),
    )

    bonus = 0.0
    reasons: list[str] = []
    if alias_matches:
        bonus += 0.075
        reasons.append("dominant_belt_alias:" + ",".join(alias_matches[:3]))
    if category_matches:
        bonus += 0.025
        reasons.append("dominant_belt_category:" + ",".join(category_matches[:3]))

    return {
        "dominant_belt": dominant_belt,
        "dominant_belt_bonus": round(min(0.10, bonus), 4),
        "dominant_belt_reasons": reasons[:5],
    }


def summarize_course_belt_coherence(
    places: list[dict[str, Any]] | None,
    region_identity: dict[str, Any] | None,
) -> dict[str, Any]:
    """Summarize assembled course belt coherence for shadow observability."""
    places = [p for p in (places or []) if isinstance(p, dict)]
    inferred_belt = (region_identity or {}).get("inferred_belt") if isinstance(region_identity, dict) else None
    if not places:
        return {
            "inferred_belt": inferred_belt,
            "assembled_course_belt_distribution": {},
            "dominant_belt": None,
            "cross_belt_candidate_count": 0,
            "belt_affinity_score": 0.0,
            "belt_matched_place_count": 0,
            "total_place_count": 0,
        }

    distribution: dict[str, int] = {}
    matched = 0
    cross_belt = 0
    affinity_sum = 0.0

    for place in places:
        signal = score_belt_match(place, region_identity)
        if signal.get("belt_match_bonus", 0.0) > 0:
            matched += 1
            distribution[str(signal.get("inferred_belt") or inferred_belt or "unknown")] = (
                distribution.get(str(signal.get("inferred_belt") or inferred_belt or "unknown"), 0) + 1
            )
        if signal.get("wrong_belt_match"):
            cross_belt += 1
            other = str((signal.get("wrong_belt_match") or {}).get("belt") or "other")
            distribution[other] = distribution.get(other, 0) + 1
        affinity_sum += float(signal.get("belt_match_bonus") or 0.0)

    dominant_belt = None
    if distribution:
        dominant_belt = sorted(distribution.items(), key=lambda item: (-item[1], item[0]))[0][0]

    return {
        "inferred_belt": inferred_belt,
        "assembled_course_belt_distribution": distribution,
        "dominant_belt": dominant_belt,
        "cross_belt_candidate_count": cross_belt,
        "belt_affinity_score": round(affinity_sum / max(len(places), 1), 4),
        "belt_matched_place_count": matched,
        "total_place_count": len(places),
    }


FLOW_PROFILES: dict[str, dict[str, Any]] = {
    "walk_emotional": {
        "keywords": ["감성", "골목", "한옥", "산책", "데이트", "카페", "전시", "편집숍", "한남", "이태원", "리움", "독서당로"],
        "roles": ["spot", "culture", "cafe"],
        "transitions": [("culture", "cafe"), ("spot", "cafe"), ("cafe", "culture")],
    },
    "cafe_relaxed": {
        "keywords": ["카페", "디저트", "브런치", "감성", "서울숲", "오션뷰", "한담", "연무장", "한남", "이태원", "리움", "편집숍", "갤러리"],
        "roles": ["cafe", "spot", "culture"],
        "transitions": [("spot", "cafe"), ("culture", "cafe"), ("cafe", "spot")],
    },
    "sea_drive": {
        "keywords": ["바다", "해안", "오션뷰", "드라이브", "노을", "해변", "수변"],
        "roles": ["spot", "cafe", "meal"],
        "transitions": [("spot", "cafe"), ("cafe", "spot"), ("spot", "meal")],
    },
    "history_walk": {
        "keywords": ["역사", "근대", "문화", "한옥", "궁궐", "읍성", "거리", "도보"],
        "roles": ["culture", "spot", "cafe", "meal"],
        "transitions": [("culture", "cafe"), ("spot", "culture"), ("culture", "meal")],
    },
    "night_city": {
        "keywords": ["야경", "야간", "도심", "바", "카페", "수변", "광안대교"],
        "roles": ["spot", "cafe", "meal", "culture"],
        "transitions": [("meal", "spot"), ("spot", "cafe"), ("cafe", "spot")],
    },
    "family_leisure": {
        "keywords": ["가족", "공원", "해변", "호수", "시장", "체험", "여유"],
        "roles": ["spot", "culture", "meal", "cafe"],
        "transitions": [("spot", "meal"), ("culture", "meal"), ("meal", "cafe")],
    },
}


def infer_course_flow_profile(
    region_identity: dict[str, Any] | None,
    *,
    themes: list[Any] | None = None,
    movement_option: Any = None,
    companion: Any = None,
    source_terms: list[Any] | None = None,
) -> dict[str, Any]:
    """Infer a soft course flow profile from belt, theme, and movement intent."""
    identity = region_identity or {}
    terms: list[Any] = []
    terms.extend(themes or [])
    terms.append(movement_option)
    terms.append(companion)
    terms.extend(source_terms or [])
    terms.extend(identity.get("vibe_tags") or [])
    terms.extend(identity.get("tourism_keywords") or [])
    terms.extend(identity.get("mobility_traits") or [])
    terms.extend(identity.get("representative_categories") or [])
    joined = normalize_identity_token(" ".join(str(t) for t in terms if t))

    profile = "walk_emotional"
    reasons: list[str] = []

    explicit_terms: list[Any] = []
    explicit_terms.extend(source_terms or [])
    explicit_terms.extend(themes or [])
    explicit_terms.append(movement_option)
    explicit_terms.append(companion)
    explicit = normalize_identity_token(" ".join(str(t) for t in explicit_terms if t))

    if any(token in explicit for token in ("family", "가족")):
        profile = "family_leisure"
        reasons.append("explicit_family_intent")
    elif any(token in explicit for token in ("date", "데이트")):
        profile = "walk_emotional"
        reasons.append("explicit_date_intent")
    elif any(token in explicit for token in ("night", "야경", "야간")):
        profile = "night_city"
        reasons.append("explicit_night_intent")
    elif any(token in explicit for token in ("sea", "nature", "drive", "바다", "자연", "드라이브", "해변", "해안")):
        profile = "sea_drive"
        reasons.append("explicit_sea_or_drive_intent")
    elif any(token in joined for token in ("night", "야경", "야간")):
        profile = "night_city"
        reasons.append("night_intent")
    elif any(token in joined for token in ("drive", "드라이브", "바다", "해안", "오션뷰", "sea")):
        profile = "sea_drive"
        reasons.append("sea_or_drive_intent")
    elif any(token in joined for token in ("history", "역사", "근대", "한옥", "궁궐", "heritage")):
        profile = "history_walk"
        reasons.append("history_or_heritage_intent")
    elif any(token in joined for token in ("family", "가족", "leisure")):
        profile = "family_leisure"
        reasons.append("family_intent")
    elif any(token in joined for token in ("cafe", "카페", "디저트", "브런치")):
        profile = "cafe_relaxed"
        reasons.append("cafe_intent")
    elif any(token in joined for token in ("date", "데이트", "감성", "골목")):
        profile = "walk_emotional"
        reasons.append("emotional_walk_intent")

    return {
        "inferred_flow_profile": profile,
        "flow_profile_reasons": reasons or ["default_walk_emotional"],
        "profile_keywords": list(FLOW_PROFILES[profile]["keywords"]),
        "profile_roles": list(FLOW_PROFILES[profile]["roles"]),
    }


def score_flow_continuity(
    place: dict[str, Any],
    previous_place: dict[str, Any] | None,
    flow_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a small soft continuity bonus for tourist-experience flow."""
    profile_name = (flow_profile or {}).get("inferred_flow_profile")
    profile = FLOW_PROFILES.get(str(profile_name or ""))
    if not isinstance(place, dict) or not profile:
        return {
            "inferred_flow_profile": profile_name,
            "slot_flow_alignment": 0.0,
            "continuity_bonus": 0.0,
            "flow_break_candidate": False,
            "flow_match_reasons": [],
        }

    text = _place_identity_text(place)
    keyword_matches = _alias_matches(text, profile.get("keywords") or [])
    role = str(place.get("visit_role") or "")
    role_alignment = role in set(profile.get("roles") or [])
    slot_flow_alignment = 0.0
    reasons: list[str] = []

    if keyword_matches:
        slot_flow_alignment += 0.04
        reasons.append("flow_keyword_match:" + ",".join(keyword_matches[:3]))
    if role_alignment:
        slot_flow_alignment += 0.02
        reasons.append(f"flow_role_match:{role}")

    transition_bonus = 0.0
    if isinstance(previous_place, dict):
        prev_role = str(previous_place.get("visit_role") or "")
        if (prev_role, role) in set(tuple(t) for t in profile.get("transitions") or []):
            transition_bonus = 0.03
            reasons.append(f"flow_transition:{prev_role}->{role}")

        prev_text = _place_identity_text(previous_place)
        shared_keywords = [
            kw for kw in (profile.get("keywords") or [])
            if normalize_identity_token(kw) in prev_text and normalize_identity_token(kw) in text
        ]
        if shared_keywords:
            transition_bonus = max(transition_bonus, 0.02)
            reasons.append("flow_shared_context:" + ",".join(shared_keywords[:3]))

    continuity_bonus = min(0.08, slot_flow_alignment + transition_bonus)
    flow_break_candidate = bool(previous_place) and continuity_bonus == 0.0

    return {
        "inferred_flow_profile": profile_name,
        "slot_flow_alignment": round(slot_flow_alignment, 4),
        "continuity_bonus": round(continuity_bonus, 4),
        "flow_break_candidate": flow_break_candidate,
        "flow_match_reasons": reasons,
    }


_SUITABILITY_PROFILES: dict[str, dict[str, Any]] = {
    "cafe_vibe": {
        "flow_profiles": {"cafe_relaxed"},
        "positive": ["카페", "디저트", "브런치", "로스터", "커피", "감성", "서울숲", "연무장", "오션뷰", "테라스", "한남", "이태원", "리움"],
        "tourism": ["전시", "거리", "숲", "공방", "편집숍", "갤러리", "산책", "독서당로", "블루스퀘어"],
        "soft_demote": ["감자탕", "해장", "순두부", "반점", "갈치", "오징어", "센터", "체험센터", "행정", "관공서", "교육청", "오피스"],
    },
    "emotional_walk": {
        "flow_profiles": {"walk_emotional"},
        "positive": ["골목", "한옥", "감성", "데이트", "찻집", "카페", "갤러리", "공방", "거리", "한남", "이태원", "리움", "편집숍"],
        "tourism": ["문화", "전시", "역사", "산책", "마을", "독서당로", "블루스퀘어"],
        "soft_demote": ["해장", "감자탕", "센터", "행정", "관공서", "교육청", "본점", "지점", "오피스"],
    },
    "night_view": {
        "flow_profiles": {"night_city"},
        "positive": ["야경", "야간", "전망", "루프", "바", "광안", "대교", "수변", "해변", "카페"],
        "tourism": ["바다", "공원", "거리", "산책", "전망대"],
        "soft_demote": ["해장", "순두부", "감자탕", "맷돌", "센터", "행정", "오피스"],
    },
    "sea_drive": {
        "flow_profiles": {"sea_drive"},
        "positive": ["바다", "해안", "오션뷰", "드라이브", "노을", "해변", "수변", "포구", "항"],
        "tourism": ["전망", "마을", "해수욕장", "돌염전", "어촌", "산책"],
        "soft_demote": ["해장", "순두부", "감자탕", "반점", "센터", "행정", "오피스"],
    },
    "history_walk": {
        "flow_profiles": {"history_walk"},
        "positive": ["한옥", "역사", "근대", "문화", "박물관", "고택", "전통", "거리", "궁", "읍성"],
        "tourism": ["전시", "마을", "사당", "유적", "문화재", "찻집"],
        "soft_demote": ["해장", "감자탕", "오피스", "행정", "센터", "체육"],
    },
    "family_leisure": {
        "flow_profiles": {"family_leisure"},
        "positive": ["가족", "공원", "체험", "해변", "호수", "시장", "여유", "마을"],
        "tourism": ["문화", "전시", "산책", "자연", "광장"],
        "soft_demote": ["술집", "바", "마사지", "모텔", "사우나", "오피스"],
    },
}


def _suitability_profile_for_flow(flow_profile: dict[str, Any] | None) -> tuple[str | None, dict[str, Any]]:
    profile_name = str((flow_profile or {}).get("inferred_flow_profile") or "")
    for suitability_name, meta in _SUITABILITY_PROFILES.items():
        if profile_name in set(meta.get("flow_profiles") or []):
            return suitability_name, meta
    return None, {}


def score_vibe_tourism_suitability(
    place: dict[str, Any],
    flow_profile: dict[str, Any] | None,
    *,
    target_slot: str | None = None,
) -> dict[str, Any]:
    """Return advisory tourism/vibe suitability signals.

    This intentionally uses small soft boosts/demotes only. It is designed to
    reduce low-suitability candidates in already-local courses without adding a
    hard locality or belt filter.
    """
    profile_name, profile = _suitability_profile_for_flow(flow_profile)
    if not isinstance(place, dict) or not profile_name:
        return {
            "suitability_profile": profile_name,
            "vibe_suitability_score": 0.0,
            "tourism_suitability_score": 0.0,
            "suitability_bonus": 0.0,
            "suitability_soft_demote": 0.0,
            "vibe_match_reasons": [],
            "soft_demote_reason": None,
        }

    text = _place_identity_text(place)
    role = str(place.get("visit_role") or "")
    slot = str(target_slot or "")

    positive_matches = _alias_matches(text, profile.get("positive") or [])
    tourism_matches = _alias_matches(text, profile.get("tourism") or [])
    demote_matches = _alias_matches(text, profile.get("soft_demote") or [])

    vibe_score = min(0.06, 0.025 * len(set(positive_matches)))
    tourism_score = min(0.05, 0.02 * len(set(tourism_matches)))

    reasons: list[str] = []
    if positive_matches:
        reasons.append("vibe_match:" + ",".join(positive_matches[:3]))
    if tourism_matches:
        reasons.append("tourism_match:" + ",".join(tourism_matches[:3]))
    if role in {"spot", "culture", "cafe"}:
        vibe_score = min(0.07, vibe_score + 0.01)
        reasons.append(f"role_suitable:{role}")

    soft_demote = 0.0
    demote_reason = None
    if demote_matches:
        soft_demote = 0.045
        demote_reason = "low_vibe_keyword:" + ",".join(demote_matches[:3])

    # Meal slots are allowed in a day course, but heavy generic meals should not
    # dominate cafe/night/emotional flows unless they carry a local/tourism cue.
    if role == "meal" and profile_name in {"cafe_vibe", "night_view", "emotional_walk"}:
        if not positive_matches and not tourism_matches:
            soft_demote = max(soft_demote, 0.055)
            demote_reason = demote_reason or "generic_meal_low_flow_fit"
        elif slot != "meal":
            soft_demote = max(soft_demote, 0.035)
            demote_reason = demote_reason or "meal_in_non_meal_flow_slot"

    if role in {"spot", "culture"} and profile_name in {"cafe_vibe", "night_view"}:
        if not positive_matches and not tourism_matches:
            soft_demote = max(soft_demote, 0.05)
            demote_reason = demote_reason or "generic_spot_low_vibe_fit"

    return {
        "suitability_profile": profile_name,
        "vibe_suitability_score": round(vibe_score, 4),
        "tourism_suitability_score": round(tourism_score, 4),
        "suitability_bonus": round(min(0.08, vibe_score + tourism_score), 4),
        "suitability_soft_demote": round(min(0.09, soft_demote), 4),
        "vibe_match_reasons": reasons[:6],
        "soft_demote_reason": demote_reason,
    }


_MEAL_CAFE_SUITABILITY_PROFILES: dict[str, dict[str, Any]] = {
    "cafe_vibe": {
        "flow_profiles": {"cafe_relaxed"},
        "positive": ["카페", "커피", "로스터", "디저트", "베이커리", "브런치", "감성", "테라스", "서울숲", "한남", "이태원", "리움"],
        "experience": ["거리", "산책", "전시", "갤러리", "공방", "편집숍", "뷰", "독서당로", "블루스퀘어"],
        "local_food": ["성수", "서울숲", "연무장", "한남", "이태원", "브런치"],
        "view": ["뷰", "테라스", "루프"],
        "generic": ["해장", "순두부", "감자탕", "국밥", "중국집", "반점", "프랜차이즈", "분식", "기사식당"],
    },
    "emotional_meal": {
        "flow_profiles": {"walk_emotional"},
        "positive": ["찻집", "카페", "디저트", "한옥", "골목", "감성", "데이트", "베이커리", "브런치", "한남", "이태원"],
        "experience": ["거리", "산책", "문화", "전시", "마을", "전통", "갤러리", "편집숍"],
        "local_food": ["익선", "인사동", "종로", "한옥", "한남", "이태원", "브런치"],
        "view": ["루프", "테라스", "정원"],
        "generic": ["해장", "감자탕", "국밥", "중국집", "반점", "프랜차이즈", "기사식당", "본점"],
    },
    "ocean_view_meal": {
        "flow_profiles": {"sea_drive"},
        "positive": ["바다", "해안", "오션뷰", "포구", "항", "해변", "노을", "수변", "카페"],
        "experience": ["드라이브", "전망", "마을", "돌염전", "어촌", "산책"],
        "local_food": ["해물", "라면", "회", "물회", "갈치", "전복", "고등어"],
        "view": ["오션뷰", "바다", "해안", "노을", "전망"],
        "generic": ["해장", "순두부", "감자탕", "중국집", "반점", "프랜차이즈", "분식", "기사식당"],
    },
    "night_meal": {
        "flow_profiles": {"night_city"},
        "positive": ["야경", "야간", "바", "펍", "포차", "루프", "루프탑", "라운지", "수변", "해변", "카페", "바다뷰"],
        "experience": ["전망", "대교", "거리", "산책", "공원", "바다", "테라스"],
        "local_food": ["광안", "민락", "수변", "해산물", "회", "조개", "포차"],
        "view": ["야경", "전망", "광안대교", "수변", "루프", "루프탑", "바다뷰"],
        "generic": ["해장", "순두부", "감자탕", "국밥", "중국집", "반점", "맷돌", "프랜차이즈", "기사식당"],
    },
    "traditional_meal": {
        "flow_profiles": {"history_walk"},
        "positive": ["한옥", "전통", "찻집", "팥죽", "비빔", "정식", "문화", "고택", "박물관"],
        "experience": ["거리", "마을", "역사", "근대", "산책", "전시"],
        "local_food": ["전주", "비빔밥", "콩나물", "막걸리", "한정식", "팥죽", "전통"],
        "view": ["정원", "한옥", "마당"],
        "generic": ["해장", "감자탕", "중국집", "반점", "프랜차이즈", "기사식당"],
    },
    "local_experience": {
        "flow_profiles": {"family_leisure"},
        "positive": ["시장", "공원", "체험", "로컬", "마을", "가족", "카페", "베이커리"],
        "experience": ["산책", "자연", "문화", "전시", "광장"],
        "local_food": ["시장", "로컬", "향토", "해물", "전통"],
        "view": ["공원", "호수", "바다", "전망"],
        "generic": ["프랜차이즈", "기사식당", "오피스", "분식"],
    },
}


def _meal_cafe_profile_for_flow(flow_profile: dict[str, Any] | None) -> tuple[str | None, dict[str, Any]]:
    profile_name = str((flow_profile or {}).get("inferred_flow_profile") or "")
    for suitability_name, meta in _MEAL_CAFE_SUITABILITY_PROFILES.items():
        if profile_name in set(meta.get("flow_profiles") or []):
            return suitability_name, meta
    return None, {}


def score_meal_cafe_suitability(
    place: dict[str, Any],
    flow_profile: dict[str, Any] | None,
    *,
    target_slot: str | None = None,
) -> dict[str, Any]:
    """Return meal/cafe-specific tourism-vibe signals.

    This helper only adjusts score softly. It never removes a restaurant/cafe
    candidate, so meal-slot coverage is preserved.
    """
    role = str((place or {}).get("visit_role") or "")
    slot = str(target_slot or "")
    if role not in {"meal", "cafe"}:
        return {
            "meal_cafe_profile": None,
            "meal_vibe_score": 0.0,
            "meal_experience_score": 0.0,
            "local_food_bonus": 0.0,
            "view_bonus": 0.0,
            "meal_cafe_bonus": 0.0,
            "meal_cafe_soft_demote": 0.0,
            "meal_soft_demote_reason": None,
            "meal_cafe_match_reasons": [],
        }

    profile_name, profile = _meal_cafe_profile_for_flow(flow_profile)
    if not isinstance(place, dict) or not profile_name:
        return {
            "meal_cafe_profile": profile_name,
            "meal_vibe_score": 0.0,
            "meal_experience_score": 0.0,
            "local_food_bonus": 0.0,
            "view_bonus": 0.0,
            "meal_cafe_bonus": 0.0,
            "meal_cafe_soft_demote": 0.0,
            "meal_soft_demote_reason": None,
            "meal_cafe_match_reasons": [],
        }

    text = _place_identity_text(place)
    positive_matches = _alias_matches(text, profile.get("positive") or [])
    experience_matches = _alias_matches(text, profile.get("experience") or [])
    local_matches = _alias_matches(text, profile.get("local_food") or [])
    view_matches = _alias_matches(text, profile.get("view") or [])
    generic_matches = _alias_matches(text, profile.get("generic") or [])

    meal_vibe_score = min(0.055, 0.02 * len(set(positive_matches)))
    meal_experience_score = min(0.055, 0.02 * len(set(experience_matches)))
    local_food_bonus = min(0.04, 0.02 * len(set(local_matches)))
    view_bonus = min(0.04, 0.02 * len(set(view_matches)))

    reasons: list[str] = []
    if positive_matches:
        reasons.append("meal_vibe:" + ",".join(positive_matches[:3]))
    if experience_matches:
        reasons.append("meal_experience:" + ",".join(experience_matches[:3]))
    if local_matches:
        reasons.append("local_food:" + ",".join(local_matches[:3]))
    if view_matches:
        reasons.append("view:" + ",".join(view_matches[:3]))

    demote = 0.0
    demote_reason = None
    if generic_matches:
        demote = 0.065
        demote_reason = "generic_meal_cafe_keyword:" + ",".join(generic_matches[:3])

    if role == "meal":
        has_experience = bool(positive_matches or experience_matches or local_matches or view_matches)
        if not has_experience:
            demote = max(demote, 0.075)
            demote_reason = demote_reason or "meal_lacks_travel_context"
        if slot != "meal" and profile_name in {"cafe_vibe", "night_meal", "emotional_meal"}:
            demote = max(demote, 0.05)
            demote_reason = demote_reason or "meal_in_vibe_forward_slot"

    if role == "cafe":
        meal_vibe_score = min(0.065, meal_vibe_score + 0.015)
        reasons.append("role_cafe_fit")
        if profile_name in {"ocean_view_meal", "night_meal"} and not (view_matches or experience_matches):
            demote = max(demote, 0.035)
            demote_reason = demote_reason or "cafe_lacks_view_or_experience_context"

    bonus = min(
        0.10,
        meal_vibe_score + meal_experience_score + local_food_bonus + view_bonus,
    )
    return {
        "meal_cafe_profile": profile_name,
        "meal_vibe_score": round(meal_vibe_score, 4),
        "meal_experience_score": round(meal_experience_score, 4),
        "local_food_bonus": round(local_food_bonus, 4),
        "view_bonus": round(view_bonus, 4),
        "meal_cafe_bonus": round(bonus, 4),
        "meal_cafe_soft_demote": round(min(0.11, demote), 4),
        "meal_soft_demote_reason": demote_reason,
        "meal_cafe_match_reasons": reasons[:8],
    }


_ROUTE_CONTAMINATION_RULES: dict[str, dict[str, Any]] = {
    "cafe_relaxed": {
        "flow": "cafe_relaxed",
        "positive": ["카페", "커피", "로스터", "디저트", "베이커리", "브런치", "서울숲", "성수", "한남", "이태원", "리움", "갤러리", "편집숍"],
        "contamination": ["키즈월드", "체험센터", "감자탕", "해장", "순두부", "체육", "행정", "관공서", "교육청", "주민센터", "구청", "시청", "오피스", "상가"],
        "lifestyle": ["감자탕", "해장", "순두부", "기사식당", "체육", "행정", "관공서", "교육청", "오피스"],
    },
    "night_city": {
        "flow": "night_city",
        "positive": ["야경", "야간", "광안", "바다", "해변", "수변", "루프", "전망", "거리", "카페", "포차", "바"],
        "contamination": ["키즈월드", "어린이", "체험센터", "행정", "오피스", "사우나", "모텔", "해장", "순두부", "국밥", "감자탕"],
        "kid_family_mismatch": ["키즈월드", "어린이", "체험센터"],
        "lifestyle": ["해장", "순두부", "국밥", "감자탕", "기사식당", "오피스", "상가"],
    },
    "sea_drive": {
        "flow": "sea_drive",
        "positive": ["바다", "해안", "오션뷰", "포구", "항구", "드라이브", "노을", "해변", "전망"],
        "contamination": ["행정", "오피스", "사우나", "모텔", "체육", "기사식당"],
        "lifestyle": ["기사식당", "오피스", "상가", "행정"],
    },
    "history_walk": {
        "flow": "history_walk",
        "positive": ["한옥", "역사", "문화", "근대", "마을", "골목", "전통", "박물관", "성곽", "고택"],
        "contamination": ["키즈월드", "체험센터", "오피스", "사우나", "모텔", "체육", "행정"],
        "lifestyle": ["오피스", "상가", "행정", "체육"],
    },
    "walk_emotional": {
        "flow": "walk_emotional",
        "positive": ["골목", "한옥", "데이트", "감성", "카페", "전시", "갤러리", "거리", "산책", "한남", "이태원", "리움", "편집숍"],
        "contamination": ["해장", "감자탕", "순두부", "오피스", "행정", "관공서", "교육청", "체육", "사우나", "모텔"],
        "lifestyle": ["해장", "감자탕", "순두부", "기사식당", "오피스", "상가", "관공서", "교육청"],
    },
    "family_leisure": {
        "flow": "family_leisure",
        "positive": ["가족", "공원", "체험", "해변", "시장", "광장", "자연", "전시"],
        "contamination": ["모텔", "사우나", "마사지", "유흥", "오피스"],
        "lifestyle": ["오피스", "상가"],
    },
}


_PUBLIC_OFFICE_SOFT_DEMOTE_TERMS = [
    "교육청",
    "관공서",
    "주민센터",
    "행정복지센터",
    "구청",
    "시청",
    "경찰서",
    "소방서",
    "우체국",
    "세무서",
    "법원",
    "평생학습관",
]

_RELIGIOUS_REPRESENTATIVE_SOFT_DEMOTE_TERMS = [
    "교회",
    "성당",
    "성지",
    "성전",
    "사찰",
    "절",
    "암자",
]

_RELIGIOUS_TOURISM_EXCEPTION_TERMS = [
    "해동용궁사",
    "해동 용궁사",
    "용궁사",
    "낙산사",
    "불국사",
    "봉은사",
    "조계사",
    "범어사",
    "석굴암",
]

_COASTAL_VIBE_TERMS = [
    "바다",
    "해변",
    "해안",
    "오션뷰",
    "수변",
    "항구",
    "포구",
    "해양",
    "스카이워크",
    "케이블카",
    "갓바위",
    "영일대",
    "호미곶",
    "갯바위",
    "몽돌",
    "다랭이",
    "독일마을",
    "해수욕장",
    "광장",
    "낭만",
    "야경",
]

_HARBOR_MEAL_TERMS = [
    "횟집",
    "회센터",
    "선어",
    "새조개",
    "하모",
    "장어",
    "전복",
    "물회",
    "해물",
    "대게",
    "돌게",
    "생선",
    "수산",
    "포차",
    "시장",
]


def _score_coastal_night_signal(text: str, profile_name: str, role: str) -> dict[str, Any]:
    """Return advisory coastal/night coherence signals.

    This is intentionally small and soft. It prevents coastal-local meals and
    waterfront spots from being treated like generic contamination, but it does
    not force any candidate into the route.
    """
    if profile_name not in {"sea_drive", "night_city", "cafe_relaxed", "walk_emotional"}:
        return {
            "coastal_vibe_score": 0.0,
            "night_view_score": 0.0,
            "harbor_alignment": 0.0,
            "sea_route_continuity": 0.0,
            "inland_contamination_flags": [],
            "coastal_positive_matches": [],
        }

    coastal_matches = _alias_matches(text, _COASTAL_VIBE_TERMS)
    meal_matches = _alias_matches(text, _HARBOR_MEAL_TERMS)
    night_matches = _alias_matches(text, ["야경", "야간", "밤바다", "낭만", "스카이워크", "케이블카", "포차"])
    inland_flags = _alias_matches(text, ["내륙", "오피스", "관공서", "행정", "산업단지", "공단"])

    coastal_score = min(0.08, 0.025 * len(set(coastal_matches)))
    night_score = min(0.06, 0.025 * len(set(night_matches))) if profile_name == "night_city" else 0.0
    harbor_score = min(0.07, 0.025 * len(set(meal_matches))) if role in {"meal", "cafe", "spot"} else 0.0
    continuity = min(0.08, coastal_score + max(night_score, harbor_score) * 0.5)

    return {
        "coastal_vibe_score": round(coastal_score, 4),
        "night_view_score": round(night_score, 4),
        "harbor_alignment": round(harbor_score, 4),
        "sea_route_continuity": round(continuity, 4),
        "inland_contamination_flags": inland_flags[:5],
        "coastal_positive_matches": sorted(set(coastal_matches + meal_matches + night_matches))[:8],
    }


def score_route_contamination(
    place: dict[str, Any],
    region_identity: dict[str, Any] | None,
    flow_profile: dict[str, Any] | None,
    *,
    target_slot: str | None = None,
) -> dict[str, Any]:
    """Return advisory route-level contamination signals for one candidate.

    The result is a soft demote and trace-only flags. It must not be used as a
    hard exclusion because fallback coverage is still required.
    """
    profile_name = str((flow_profile or {}).get("inferred_flow_profile") or "")
    rules = _ROUTE_CONTAMINATION_RULES.get(profile_name, {})
    if not isinstance(place, dict) or not rules:
        return {
            "route_contamination_demote": 0.0,
            "route_contamination_flags": [],
            "route_contamination_reasons": [],
            "route_positive_matches": [],
            "religious_facility_demote": 0.0,
            "religious_tourism_exception": [],
        }

    text = _place_identity_text(place)
    role = str(place.get("visit_role") or "")
    slot = str(target_slot or "")
    inferred_belt = str((region_identity or {}).get("inferred_belt") or "")
    positive_matches = _alias_matches(text, rules.get("positive") or [])
    coastal_signal = _score_coastal_night_signal(text, profile_name, role)
    if coastal_signal.get("coastal_positive_matches"):
        positive_matches = sorted(set(positive_matches + list(coastal_signal.get("coastal_positive_matches") or [])))
    contamination_matches = _alias_matches(text, rules.get("contamination") or [])
    lifestyle_matches = _alias_matches(text, rules.get("lifestyle") or [])
    kid_matches = _alias_matches(text, rules.get("kid_family_mismatch") or [])
    public_office_matches = _alias_matches(text, _PUBLIC_OFFICE_SOFT_DEMOTE_TERMS)
    religious_matches = _alias_matches(text, _RELIGIOUS_REPRESENTATIVE_SOFT_DEMOTE_TERMS)
    religious_exception_matches = _alias_matches(text, _RELIGIOUS_TOURISM_EXCEPTION_TERMS)
    inland_flags = list(coastal_signal.get("inland_contamination_flags") or [])

    flags: list[str] = []
    reasons: list[str] = []
    demote = 0.0
    heritage_exception_matches: list[str] = []
    if inferred_belt == "진주남강역사" and role in {"spot", "culture"}:
        heritage_exception_matches = _alias_matches(
            text,
            [
                "진주성",
                "촉석루",
                "진주향교",
                "국립진주박물관",
                "남강",
                "소망진산",
                "유등테마공원",
                "의암",
            ],
        )
    nightlife_core_exception_matches: list[str] = []
    if profile_name == "night_city" and role in {"spot", "culture", "cafe", "meal"} and (
        inferred_belt == "을지로" or any(term in text for term in ("을지로", "힙지로", "노가리골목", "충무로", "세운상가", "청계천"))
    ):
        nightlife_core_exception_matches = _alias_matches(
            text,
            [
                "을지로",
                "을지로3가",
                "을지로4가",
                "힙지로",
                "노가리골목",
                "세운상가",
                "충무로 인쇄골목",
                "청계천",
                "노포",
                "야장",
                "루프탑",
            ],
        )

    if contamination_matches:
        flags.append("flow_contamination")
        reasons.append("flow_contamination:" + ",".join(contamination_matches[:3]))
        demote = max(demote, 0.05)

    if lifestyle_matches:
        flags.append("lifestyle_contamination")
        reasons.append("lifestyle_mismatch:" + ",".join(lifestyle_matches[:3]))
        demote = max(demote, 0.045)

    if contamination_matches and lifestyle_matches:
        demote = max(demote, 0.13)
        reasons.append("severe_route_lifestyle_overlap")

    if inland_flags:
        flags.append("inland_contamination")
        reasons.append("inland_contamination:" + ",".join(inland_flags[:3]))
        demote = max(demote, 0.045)

    if kid_matches and profile_name == "night_city":
        flags.append("kid_family_mismatch")
        reasons.append("kid_family_mismatch:" + ",".join(kid_matches[:3]))
        demote = max(demote, 0.14)

    if public_office_matches and role in {"spot", "culture"}:
        if not nightlife_core_exception_matches and not heritage_exception_matches:
            flags.append("public_office_representative_mismatch")
            reasons.append("public_office_mismatch:" + ",".join(public_office_matches[:3]))
            demote = max(demote, 0.12)

    religious_demote_profiles = {"cafe_relaxed", "night_city", "walk_emotional", "sea_drive", "family_leisure"}
    if religious_exception_matches:
        flags.append("religious_tourism_exception")
        reasons.append("religious_tourism_exception:" + ",".join(religious_exception_matches[:3]))
    elif (
        religious_matches
        and role in {"spot", "culture"}
        and profile_name in religious_demote_profiles
        and not nightlife_core_exception_matches
        and not heritage_exception_matches
    ):
        flags.append("religious_representative_mismatch")
        reasons.append("religious_representative_mismatch:" + ",".join(religious_matches[:3]))
        demote = max(demote, 0.13 if slot in {"anchor", "morning", "morning_2"} else 0.1)

    if (
        role in {"spot", "culture"}
        and profile_name in {"cafe_relaxed", "night_city"}
        and not positive_matches
        and not heritage_exception_matches
        and not nightlife_core_exception_matches
    ):
        flags.append("generic_commerce_mismatch")
        reasons.append(f"generic_{role}_low_route_fit")
        demote = max(demote, 0.035)

    if role == "meal" and slot != "meal" and profile_name in {"cafe_relaxed", "night_city", "walk_emotional"}:
        if not positive_matches:
            flags.append("meal_flow_mismatch")
            reasons.append("meal_without_route_context")
            demote = max(demote, 0.08)

    wrong_belt = score_belt_match(place, region_identity).get("wrong_belt_match") if region_identity else None
    if wrong_belt and not heritage_exception_matches and not nightlife_core_exception_matches:
        flags.append("belt_contamination")
        reasons.append("wrong_belt:" + str((wrong_belt or {}).get("belt") or "unknown"))
        demote = max(demote, 0.075)

    return {
        "route_contamination_demote": round(min(0.18, demote), 4),
        "route_contamination_flags": sorted(set(flags)),
        "route_contamination_reasons": reasons[:6],
        "route_positive_matches": positive_matches[:5],
        "heritage_family_exception": sorted(set(heritage_exception_matches)),
        "nightlife_core_exception": sorted(set(nightlife_core_exception_matches)),
        "coherence_false_positive_removed": bool(heritage_exception_matches or nightlife_core_exception_matches),
        "nightlife_false_positive_removed": bool(nightlife_core_exception_matches),
        "heritage_false_positive_removed": bool(heritage_exception_matches),
        "coastal_vibe_score": coastal_signal.get("coastal_vibe_score", 0.0),
        "night_view_score": coastal_signal.get("night_view_score", 0.0),
        "harbor_alignment": coastal_signal.get("harbor_alignment", 0.0),
        "sea_route_continuity": coastal_signal.get("sea_route_continuity", 0.0),
        "inland_contamination_flags": inland_flags,
        "religious_facility_demote": round(
            min(0.18, demote) if "religious_representative_mismatch" in flags else 0.0,
            4,
        ),
        "religious_tourism_exception": sorted(set(religious_exception_matches)),
    }


_SEOUL_CENTRAL_DRIFT_TERMS_BY_BELT: dict[str, list[str]] = {
    "을지로": [
        "영등포", "남산", "남대문", "전쟁기념관", "전쟁", "기념관", "현충", "추모", "올림픽공원",
        "잠실", "석촌", "코엑스", "세종문화회관", "롯데호텔", "시청", "서울역", "용산",
    ],
    "익선": ["영등포", "남산", "남대문", "세종문화회관", "전쟁기념관", "올림픽공원", "잠실", "석촌", "코엑스"],
    "북촌": ["경리단", "이태원", "한남", "남산", "남대문", "세종문화회관", "롯데호텔", "명동", "시청", "전쟁기념관", "국립극장", "올림픽공원", "잠실", "코엑스"],
}

_SEOUL_DISTRICT_POSITIVE_TERMS_BY_BELT: dict[str, list[str]] = {
    "을지로": ["을지로", "힙지로", "청계천", "종로", "명동", "노포", "야장", "골목", "야간"],
    "익선": ["익선", "익선동", "종로3가", "한옥", "골목", "데이트", "카페", "운현궁", "인사동"],
    "북촌": ["북촌", "삼청", "안국", "한옥", "궁궐", "경복궁", "창덕궁", "전통", "산책"],
}

_SEOUL_LANDMARK_PRIORITY_TERMS_BY_BELT: dict[str, list[str]] = {
    "성수": [
        "성수", "성수동", "서울숲", "연무장길", "뚝섬", "성수동카페거리", "카페거리", "감성카페",
        "로스터리", "디저트", "베이커리", "전시", "갤러리", "편집숍", "골목", "산책",
    ],
    "북촌": [
        "북촌한옥마을", "북촌", "삼청동", "삼청", "안국", "한옥", "전통찻집", "찻집", "한옥카페",
        "공방", "궁궐뷰", "궁궐", "경복궁", "창덕궁", "골목", "산책", "전통문화",
    ],
    "익선": [
        "익선", "익선동", "익선동한옥거리", "한옥골목", "한옥", "골목", "감성카페", "데이트",
        "전통", "현대", "종로3가", "찻집", "디저트",
    ],
    "을지로": [
        "을지로", "힙지로", "골목", "노포", "야간", "야장", "조명", "사진", "바", "청계천",
        "을지로3가", "을지로4가", "노가리골목", "세운상가", "충무로", "인쇄골목", "루프탑",
        "레트로", "bar",
    ],
    "한남": [
        "한남", "한남동", "브런치", "갤러리", "편집숍", "리움", "독서당로", "감성", "산책",
        "카페",
    ],
}

_WEAK_INDOOR_CORPORATE_TERMS = [
    "보험", "생명보험", "교육문화센터", "문화센터", "기업", "본사", "사옥", "컨벤션", "세미나",
    "교육장", "연수", "강당", "다목적", "복합문화센터", "커뮤니티센터", "협회", "재단", "회관",
    "사무", "오피스",
]

_WEAK_INDOOR_EXEMPT_TERMS = [
    "한옥", "전통", "궁", "궁궐", "고궁", "문화재", "공방", "찻집", "갤러리", "전시", "박물관",
    "미술관", "역사",
]

_SEONGSU_WEAK_MEAL_TERMS = [
    "감자탕", "국밥", "해장", "순두부", "기사식당", "백반", "분식", "중국집", "반점", "오피스",
    "상가", "구내", "점심", "본점", "별관",
]

_EULJIRO_NIGHT_VIBE_TERMS = [
    "을지로", "을지로3가", "힙지로", "골목", "노포", "야장", "야간", "밤", "조명", "사진", "바",
    "와인바", "펍", "루프탑", "음악", "청계천", "충무로", "인쇄골목", "포차",
]

_EULJIRO_WEAK_NIGHT_MEAL_TERMS = [
    "백반", "기사식당", "구내", "점심", "해장", "순두부", "감자탕", "분식", "푸드코트", "오피스",
    "상가",
]

_SEOUL_DATE_VIBE_TERMS = [
    "한남", "한남동", "익선", "익선동", "성수", "성수동", "서울숲", "북촌", "삼청", "홍대",
    "연남", "을지로", "힙지로", "감성카페", "카페", "브런치", "디저트", "베이커리", "한옥",
    "골목", "산책", "조명", "야간", "갤러리", "전시", "편집숍", "루프탑", "바", "데이트",
]

_SEOUL_DATE_BROAD_DRIFT_TERMS = [
    "전쟁기념관", "전쟁", "기념관", "현충", "추모", "오피스", "업무", "비즈니스", "상공회의소",
    "컨벤션", "세미나", "교육장", "연수", "관공서", "행정", "구청", "시청", "주민센터", "세무서",
    "법원", "남대문", "서울역", "용산", "여의도", "영등포", "코엑스", "무역센터",
]

_SEOUL_DATE_WEAK_MEAL_TERMS = [
    "기사식당", "백반", "구내", "점심", "해장", "감자탕", "순두부", "국밥", "분식", "푸드코트",
    "오피스", "본점",
]

_BUSAN_NIGHT_MEAL_VIBE_TERMS = [
    "광안", "광안리", "광안대교", "민락", "수변", "해변", "바다", "바다뷰", "야경", "야간",
    "루프", "루프탑", "바", "펍", "포차", "라운지", "테라스", "해산물", "회", "조개",
]

_BUSAN_REPRESENTATIVE_LANDMARK_TERMS = [
    "해동용궁사", "해동 용궁사", "용궁사", "Haedong Yonggungsa", "Haedong Yonggung Temple",
    "기장", "기장해안", "오시리아", "Osiria", "송정", "Songjeong", "해운대", "해운대해수욕장",
    "달맞이길", "달맞이", "Dalmaji Road", "광안리", "광안대교", "감천문화마을",
    "Gamcheon Culture Village", "태종대", "Taejongdae", "송도해상케이블카", "Songdo Marine Cable Car",
    "흰여울문화마을", "Huinnyeoul Culture Village", "오륙도", "Oryukdo",
]

_BUSAN_GIJANG_LANDMARK_TERMS = [
    "해동용궁사", "해동 용궁사", "용궁사", "Haedong Yonggungsa", "Haedong Yonggung Temple",
    "기장", "기장해안", "오시리아", "Osiria", "송정", "Songjeong",
]

_BUSAN_WEAK_DAYTIME_MEAL_TERMS = [
    "국밥", "감자탕", "순두부", "해장", "기사식당", "백반", "구내", "점심", "분식", "푸드코트",
    "오피스", "상가", "프랜차이즈",
]

_SEONGSAN_FIRST_PLACE_POSITIVE_TERMS = [
    "성산일출봉",
    "성산",
    "광치기",
    "섭지코지",
    "오름",
    "해변",
    "바다",
    "일출",
    "자연",
    "산책",
]

_SEONGSAN_WEAK_FIRST_PLACE_TERMS = [
    "족욕",
    "마사지",
    "테라피",
    "웰니스",
    "체험",
    "공방",
    "박물관",
]


_GYEONGNAM_TOURISM_FAMILY_TERMS = [
    "창원", "마산", "진해", "진해해양공원", "여좌천", "경화역", "마산어시장", "저도콰이강",
    "저도연륙교", "콰이강의다리", "주남저수지", "통영", "동피랑", "이순신공원",
    "통영케이블카", "강구안", "디피랑", "거제", "바람의언덕", "외도", "구조라",
    "학동몽돌해변", "남해", "독일마을", "다랭이마을", "보리암", "진주", "진주성",
    "남강", "촉석루", "김해", "국립김해박물관", "수로왕릉", "대성동고분군",
    "김해가야테마파크", "봉황동유적",
]

_GYEONGNAM_INDOOR_CULTURE_FALLBACK_TERMS = [
    "도립미술관", "시립미술관", "미술관", "성산아트홀", "아트홀", "문화회관",
    "문예회관", "문화센터", "교육문화센터", "생활문화", "복합문화", "공연장",
    "전시관", "컨벤션", "센터",
]

_GYEONGNAM_INDOOR_CULTURE_EXEMPT_TERMS = [
    "동피랑", "디피랑", "국립김해박물관", "김해박물관", "진주성", "촉석루",
    "가야테마파크", "대성동고분군", "수로왕릉", "감천문화마을", "흰여울문화마을",
]

_GYEONGNAM_CONTEXT_TERMS = [
    "경남", "창원", "마산", "진해", "통영", "거제", "남해", "진주", "김해",
]

_JINJU_HISTORY_REPRESENTATIVE_TERMS = [
    "진주성", "촉석루", "남강", "진주성길", "진주성 주변", "남가람", "진주역사",
]

_JINJU_WEAK_FIRST_PLACE_TERMS = [
    "재봉틀", "전시관", "박물관", "미술관", "문화관", "문화센터", "아트홀", "생활문화",
    "연구소", "바이오", "소재연구", "산림바이오", "체험관", "프로스트맥주", "맥주협동조합",
    "맥주", "공방", "목공예",
]

_TONGYEONG_SAME_CITY_TERMS = [
    "통영", "동피랑", "강구안", "이순신공원", "통영케이블카", "디피랑", "중앙시장", "서피랑", "항구",
]

_TONGYEONG_GEOJE_DRIFT_TERMS = [
    "거제", "구조라", "바람의언덕", "외도", "학동몽돌", "지세포", "와현", "해금강",
]

_GIMHAE_GAYA_FAMILY_TERMS = [
    "김해", "가야", "국립김해박물관", "김해박물관", "수로왕릉", "수로왕비릉",
    "대성동고분", "대성동고분군", "봉황동유적", "김해가야테마파크", "분산성", "김해읍성",
]

_GIMHAE_GAYA_WEAK_DRIFT_TERMS = [
    "주남", "창원", "진해", "마산", "통영", "거제", "남해", "카페", "돈까스", "수제비",
]

_GIMHAE_SUPPORT_SLOT_TERMS = [
    "김해가야테마파크", "국립김해박물관", "김해박물관", "수로왕릉", "수로왕비릉",
    "대성동고분", "대성동고분군", "봉황동유적", "김해읍성", "분산성",
    "가야", "왕릉", "고분", "유적", "역사", "전통", "산성",
]

_GIMHAE_SUPPORT_SLOT_WEAK_TERMS = [
    "글로벌푸드", "푸드타운", "수제비", "돈까스", "생국수", "국수", "수산",
    "카페", "라운지", "브런치", "식당", "중식", "치킨", "고기", "회관",
]

_SEOUL_DEFAULT_REPRESENTATIVE_TERMS = [
    "경복궁", "광화문", "북촌", "삼청", "청계천", "서울숲", "성수",
    "한강", "한강공원", "명동", "남산", "인사동", "덕수궁", "창덕궁",
]

_SEOUL_DEFAULT_WEAK_FIRST_PLACE_TERMS = [
    "메종", "사우스케이프", "브랜드", "플래그십", "쇼룸", "편집숍", "럭셔리",
    "백화점", "몰", "호텔", "라운지", "부티크", "스튜디오",
]


def score_editorial_route_fit(
    place: dict[str, Any],
    region_identity: dict[str, Any] | None,
    flow_profile: dict[str, Any] | None,
    *,
    target_slot: str | None = None,
) -> dict[str, Any]:
    """Return soft editorial polish signals for route purity.

    These signals are advisory only. They should demote obvious editorial drift
    and weak first-place candidates without blocking fallback coverage.
    """
    if not isinstance(place, dict) or not isinstance(region_identity, dict):
        return {
            "editorial_bonus": 0.0,
            "editorial_demote": 0.0,
            "editorial_demote_reason": None,
            "weak_first_place_reason": None,
            "central_drift_reason": None,
            "landmark_priority_score": 0.0,
            "representative_vibe_score": 0.0,
            "weak_indoor_demote": 0.0,
            "landmark_alignment_reason": None,
            "seongsu_vibe_score": 0.0,
            "cafe_street_alignment": 0.0,
            "weak_meal_demote": 0.0,
            "editorial_first_place_bonus": 0.0,
            "euljiro_night_score": 0.0,
            "hipjiro_alignment": 0.0,
            "central_drift_demote": 0.0,
            "night_vibe_bonus": 0.0,
            "seoul_date_score": 0.0,
            "date_vibe_alignment": 0.0,
            "broad_seoul_drift_demote": 0.0,
            "romantic_walk_bonus": 0.0,
            "busan_night_meal_score": 0.0,
            "waterfront_alignment": 0.0,
            "weak_daytime_meal_demote": 0.0,
            "night_meal_bonus": 0.0,
            "busan_landmark_priority_score": 0.0,
            "busan_representative_bonus": 0.0,
            "busan_landmark_alignment_reason": None,
            "representative_tourism_family_score": 0.0,
            "indoor_culture_fallback_demote": 0.0,
            "regional_landmark_density": 0.0,
            "first_place_representative_bonus": 0.0,
            "jinju_history_first_place_bonus": 0.0,
            "tongyeong_same_city_bonus": 0.0,
            "tongyeong_geoje_drift_demote": 0.0,
            "gimhae_gaya_family_score": 0.0,
            "gimhae_support_slot_family_score": 0.0,
            "gimhae_support_slot_drift_demote": 0.0,
            "support_slot_coherence_score": 0.0,
            "seoul_default_representative_score": 0.0,
            "seoul_default_weak_first_place_demote": 0.0,
            "weak_museum_first_place_demote": 0.0,
        }

    text = _place_identity_text(place)
    inferred_belt = str(region_identity.get("inferred_belt") or "")
    profile_name = str((flow_profile or {}).get("inferred_flow_profile") or "")
    slot = str(target_slot or "")
    role = str(place.get("visit_role") or place.get("role") or "")

    bonus = 0.0
    demote = 0.0
    demote_reasons: list[str] = []
    weak_first_place_reason = None
    central_drift_reason = None
    landmark_priority_score = 0.0
    representative_vibe_score = 0.0
    weak_indoor_demote = 0.0
    landmark_alignment_reason = None
    seongsu_vibe_score = 0.0
    cafe_street_alignment = 0.0
    weak_meal_demote = 0.0
    editorial_first_place_bonus = 0.0
    euljiro_night_score = 0.0
    hipjiro_alignment = 0.0
    central_drift_demote = 0.0
    night_vibe_bonus = 0.0
    seoul_date_score = 0.0
    date_vibe_alignment = 0.0
    broad_seoul_drift_demote = 0.0
    romantic_walk_bonus = 0.0
    busan_night_meal_score = 0.0
    waterfront_alignment = 0.0
    weak_daytime_meal_demote = 0.0
    night_meal_bonus = 0.0
    busan_landmark_priority_score = 0.0
    busan_representative_bonus = 0.0
    busan_landmark_alignment_reason = None
    representative_tourism_family_score = 0.0
    indoor_culture_fallback_demote = 0.0
    regional_landmark_density = 0.0
    first_place_representative_bonus = 0.0
    jinju_history_first_place_bonus = 0.0
    tongyeong_same_city_bonus = 0.0
    tongyeong_geoje_drift_demote = 0.0
    gimhae_gaya_family_score = 0.0
    gimhae_support_slot_family_score = 0.0
    gimhae_support_slot_drift_demote = 0.0
    support_slot_coherence_score = 0.0
    seoul_default_representative_score = 0.0
    seoul_default_weak_first_place_demote = 0.0
    weak_museum_first_place_demote = 0.0

    if inferred_belt in _SEOUL_CENTRAL_DRIFT_TERMS_BY_BELT:
        positive_matches = _alias_matches(text, _SEOUL_DISTRICT_POSITIVE_TERMS_BY_BELT.get(inferred_belt) or [])
        drift_matches = _alias_matches(text, _SEOUL_CENTRAL_DRIFT_TERMS_BY_BELT.get(inferred_belt) or [])
        if positive_matches:
            bonus = max(bonus, min(0.035, 0.015 * len(set(positive_matches))))
        if drift_matches and not positive_matches:
            central_drift_reason = f"{inferred_belt}_central_drift:" + ",".join(drift_matches[:3])
            central_drift_demote = 0.095 if inferred_belt == "을지로" and profile_name == "night_city" else 0.075
            demote = max(demote, central_drift_demote)
            demote_reasons.append(central_drift_reason)
        elif drift_matches:
            central_drift_reason = f"{inferred_belt}_mixed_central_drift:" + ",".join(drift_matches[:3])
            central_drift_demote = 0.05 if inferred_belt == "을지로" and profile_name == "night_city" else 0.035
            demote = max(demote, central_drift_demote)
            demote_reasons.append(central_drift_reason)

    if inferred_belt in _SEOUL_LANDMARK_PRIORITY_TERMS_BY_BELT:
        landmark_matches = _alias_matches(text, _SEOUL_LANDMARK_PRIORITY_TERMS_BY_BELT.get(inferred_belt) or [])
        weak_indoor_matches = _alias_matches(text, _WEAK_INDOOR_CORPORATE_TERMS)
        exempt_matches = _alias_matches(text, _WEAK_INDOOR_EXEMPT_TERMS)

        if landmark_matches:
            distinct_landmarks = sorted(set(landmark_matches))
            landmark_priority_score = min(0.07, 0.022 * len(distinct_landmarks))
            representative_vibe_score = min(0.05, 0.016 * len(distinct_landmarks))
            bonus = max(bonus, min(0.09, landmark_priority_score + representative_vibe_score))
            landmark_alignment_reason = f"{inferred_belt}_landmark:" + ",".join(distinct_landmarks[:4])
            if inferred_belt == "성수":
                seongsu_vibe_score = min(0.08, 0.02 * len(distinct_landmarks))
                cafe_street_alignment = min(
                    0.08,
                    0.025
                    * len(
                        set(distinct_landmarks)
                        & {"성수", "성수동", "서울숲", "연무장길", "성수동카페거리", "카페거리", "감성카페", "로스터리"}
                    ),
                )
                if slot in {"anchor", "morning", "morning_2"} and profile_name in {"cafe_relaxed", "walk_emotional"}:
                    editorial_first_place_bonus = min(0.04, seongsu_vibe_score + cafe_street_alignment)
                    bonus = max(bonus, min(0.11, bonus + editorial_first_place_bonus))

        if weak_indoor_matches and not landmark_matches and not exempt_matches:
            weak_indoor_demote = 0.09 if slot in {"anchor", "morning", "morning_2"} else 0.07
            weak_reason = f"{inferred_belt}_weak_indoor_corporate:" + ",".join(weak_indoor_matches[:3])
            demote = max(demote, weak_indoor_demote)
            demote_reasons.append(weak_reason)
        elif weak_indoor_matches and not landmark_matches:
            weak_indoor_demote = 0.035
            weak_reason = f"{inferred_belt}_mixed_weak_indoor:" + ",".join(weak_indoor_matches[:3])
            demote = max(demote, weak_indoor_demote)
            demote_reasons.append(weak_reason)

        first_place_profile = profile_name in {"history_walk", "walk_emotional", "night_city"}
        first_place_slot = slot in {"anchor", "morning", "morning_2"}
        if (
            first_place_slot
            and first_place_profile
            and inferred_belt in {"북촌", "익선", "을지로"}
            and not landmark_matches
            and not weak_indoor_matches
        ):
            gap_reason = f"{inferred_belt}_weak_landmark_first_place"
            demote = max(demote, 0.065)
            demote_reasons.append(gap_reason)

        if inferred_belt == "성수":
            weak_meal_matches = _alias_matches(text, _SEONGSU_WEAK_MEAL_TERMS)
            seongsu_cafe_profile = profile_name in {"cafe_relaxed", "walk_emotional"}
            if weak_meal_matches and seongsu_cafe_profile:
                weak_meal_demote = 0.115 if slot in {"anchor", "morning", "morning_2"} else 0.08
                weak_meal_reason = "seongsu_weak_meal_contamination:" + ",".join(weak_meal_matches[:3])
                demote = max(demote, weak_meal_demote)
                demote_reasons.append(weak_meal_reason)
            elif (
                slot in {"anchor", "morning", "morning_2"}
                and seongsu_cafe_profile
                and not landmark_matches
                and not weak_meal_matches
            ):
                weak_reason = "seongsu_weak_first_place_vibe"
                demote = max(demote, 0.055)
                demote_reasons.append(weak_reason)

        if inferred_belt == "을지로" and profile_name == "night_city":
            euljiro_matches = _alias_matches(text, _EULJIRO_NIGHT_VIBE_TERMS)
            weak_night_meal_matches = _alias_matches(text, _EULJIRO_WEAK_NIGHT_MEAL_TERMS)
            if euljiro_matches:
                distinct_euljiro = sorted(set(euljiro_matches))
                euljiro_night_score = min(0.085, 0.023 * len(distinct_euljiro))
                hipjiro_alignment = min(
                    0.075,
                    0.026 * len(set(distinct_euljiro) & {"을지로", "을지로3가", "힙지로", "골목", "노포", "청계천", "인쇄골목"}),
                )
                night_vibe_bonus = min(0.055, euljiro_night_score + hipjiro_alignment)
                bonus = max(bonus, min(0.11, bonus + night_vibe_bonus))
            if weak_night_meal_matches and role == "meal":
                weak_meal_demote = max(weak_meal_demote, 0.075)
                weak_reason = "euljiro_weak_daytime_meal:" + ",".join(weak_night_meal_matches[:3])
                demote = max(demote, weak_meal_demote)
                demote_reasons.append(weak_reason)
            elif (
                slot in {"anchor", "morning", "morning_2"}
                and not euljiro_matches
                and not drift_matches
            ):
                demote = max(demote, 0.055)
                demote_reasons.append("euljiro_weak_night_first_place")

    seoul_date_flow = (
        region_identity.get("region") == "서울"
        and profile_name in {"walk_emotional", "cafe_relaxed"}
        and inferred_belt in {"한남", "익선", "성수", "북촌", "을지로", "홍대"}
    )
    if seoul_date_flow:
        date_matches = _alias_matches(text, _SEOUL_DATE_VIBE_TERMS)
        broad_drift_matches = _alias_matches(text, _SEOUL_DATE_BROAD_DRIFT_TERMS)
        weak_date_meal_matches = _alias_matches(text, _SEOUL_DATE_WEAK_MEAL_TERMS)
        if date_matches:
            distinct_date_matches = sorted(set(date_matches))
            seoul_date_score = min(0.08, 0.02 * len(distinct_date_matches))
            date_vibe_alignment = min(
                0.075,
                0.022
                * len(
                    set(distinct_date_matches)
                    & {"한남", "익선", "성수", "서울숲", "북촌", "삼청", "홍대", "연남", "감성카페", "브런치", "갤러리", "전시", "골목", "조명", "데이트"}
                ),
            )
            romantic_walk_bonus = min(0.055, seoul_date_score + date_vibe_alignment)
            bonus = max(bonus, min(0.11, bonus + romantic_walk_bonus))

        if broad_drift_matches and not date_matches:
            broad_seoul_drift_demote = 0.085 if slot in {"anchor", "morning", "morning_2"} else 0.065
            drift_reason = "seoul_date_broad_drift:" + ",".join(broad_drift_matches[:3])
            demote = max(demote, broad_seoul_drift_demote)
            demote_reasons.append(drift_reason)
        elif broad_drift_matches:
            broad_seoul_drift_demote = 0.035
            drift_reason = "seoul_date_mixed_broad_drift:" + ",".join(broad_drift_matches[:3])
            demote = max(demote, broad_seoul_drift_demote)
            demote_reasons.append(drift_reason)

        if weak_date_meal_matches and role == "meal":
            weak_meal_demote = max(weak_meal_demote, 0.075)
            meal_reason = "seoul_date_weak_daytime_meal:" + ",".join(weak_date_meal_matches[:3])
            demote = max(demote, weak_meal_demote)
            demote_reasons.append(meal_reason)
        elif (
            slot in {"anchor", "morning", "morning_2"}
            and not date_matches
            and not broad_drift_matches
        ):
            demote = max(demote, 0.045)
            demote_reasons.append("seoul_date_weak_first_place_vibe")

    if region_identity.get("region") == "부산":
        busan_landmark_matches = _alias_matches(text, _BUSAN_REPRESENTATIVE_LANDMARK_TERMS)
        if busan_landmark_matches:
            distinct_busan_landmarks = sorted(set(busan_landmark_matches))
            busan_landmark_priority_score = min(0.085, 0.022 * len(distinct_busan_landmarks))
            busan_representative_bonus = min(0.06, busan_landmark_priority_score)
            gijang_matches = sorted(set(distinct_busan_landmarks) & set(_BUSAN_GIJANG_LANDMARK_TERMS))
            if inferred_belt == "기장" and gijang_matches:
                busan_representative_bonus = max(busan_representative_bonus, 0.075)
            if slot in {"anchor", "morning", "morning_2"}:
                busan_representative_bonus = min(0.085, busan_representative_bonus + 0.015)
            bonus = max(bonus, min(0.12, busan_landmark_priority_score + busan_representative_bonus))
            busan_landmark_alignment_reason = "busan_landmark:" + ",".join(distinct_busan_landmarks[:4])

    busan_night_flow = region_identity.get("region") == "부산" and profile_name == "night_city"
    if busan_night_flow:
        night_meal_matches = _alias_matches(text, _BUSAN_NIGHT_MEAL_VIBE_TERMS)
        weak_daytime_matches = _alias_matches(text, _BUSAN_WEAK_DAYTIME_MEAL_TERMS)
        if night_meal_matches:
            distinct_night_meal = sorted(set(night_meal_matches))
            busan_night_meal_score = min(0.085, 0.023 * len(distinct_night_meal))
            waterfront_alignment = min(
                0.08,
                0.026
                * len(
                    set(distinct_night_meal)
                    & {"광안", "광안리", "광안대교", "민락", "수변", "해변", "바다", "바다뷰", "야경", "루프탑"}
                ),
            )
            night_meal_bonus = min(0.06, busan_night_meal_score + waterfront_alignment)
            bonus = max(bonus, min(0.11, bonus + night_meal_bonus))

        if weak_daytime_matches and role == "meal":
            weak_daytime_meal_demote = 0.095
            weak_reason = "busan_night_weak_daytime_meal:" + ",".join(weak_daytime_matches[:3])
            demote = max(demote, weak_daytime_meal_demote)
            demote_reasons.append(weak_reason)
        elif role == "meal" and not night_meal_matches:
            weak_daytime_meal_demote = 0.055
            demote = max(demote, weak_daytime_meal_demote)
            demote_reasons.append("busan_night_meal_lacks_waterfront_context")

    if inferred_belt == "성산" and slot in {"anchor", "morning", "morning_2"}:
        positive_matches = _alias_matches(text, _SEONGSAN_FIRST_PLACE_POSITIVE_TERMS)
        weak_matches = _alias_matches(text, _SEONGSAN_WEAK_FIRST_PLACE_TERMS)
        if positive_matches:
            bonus = max(bonus, min(0.045, 0.02 * len(set(positive_matches))))
        if weak_matches and not positive_matches:
            weak_first_place_reason = "seongsan_weak_first_place:" + ",".join(weak_matches[:3])
            demote = max(demote, 0.09)
            demote_reasons.append(weak_first_place_reason)
        elif weak_matches:
            weak_first_place_reason = "seongsan_mixed_weak_first_place:" + ",".join(weak_matches[:3])
            demote = max(demote, 0.04)
            demote_reasons.append(weak_first_place_reason)

    gyeongnam_context = (
        region_identity.get("region") == "경남"
        or any(term in text for term in _GYEONGNAM_CONTEXT_TERMS)
    )
    if gyeongnam_context:
        tourism_matches = _alias_matches(text, _GYEONGNAM_TOURISM_FAMILY_TERMS)
        indoor_matches = _alias_matches(text, _GYEONGNAM_INDOOR_CULTURE_FALLBACK_TERMS)
        indoor_exempt_matches = _alias_matches(text, _GYEONGNAM_INDOOR_CULTURE_EXEMPT_TERMS)

        if tourism_matches:
            distinct_tourism_matches = sorted(set(tourism_matches))
            representative_tourism_family_score = min(0.085, 0.022 * len(distinct_tourism_matches))
            regional_landmark_density = min(0.06, 0.014 * len(distinct_tourism_matches))
            if slot in {"anchor", "morning", "morning_2"}:
                first_place_representative_bonus = min(
                    0.045,
                    representative_tourism_family_score * 0.65 + 0.012,
                )
            bonus = max(
                bonus,
                min(
                    0.12,
                    representative_tourism_family_score
                    + regional_landmark_density
                    + first_place_representative_bonus,
                ),
            )
            landmark_alignment_reason = landmark_alignment_reason or (
                "gyeongnam_representative_tourism:" + ",".join(distinct_tourism_matches[:4])
            )

        if indoor_matches and not tourism_matches and not indoor_exempt_matches:
            indoor_culture_fallback_demote = 0.115 if slot in {"anchor", "morning", "morning_2"} else 0.085
            if profile_name in {"sea_drive", "walk_emotional", "family_leisure", "cafe_relaxed"}:
                indoor_culture_fallback_demote = max(indoor_culture_fallback_demote, 0.105)
            weak_indoor_demote = max(weak_indoor_demote, indoor_culture_fallback_demote)
            demote = max(demote, indoor_culture_fallback_demote)
            demote_reasons.append(
                "gyeongnam_indoor_culture_fallback:" + ",".join(indoor_matches[:3])
            )
        elif indoor_matches and not tourism_matches:
            indoor_culture_fallback_demote = 0.045
            weak_indoor_demote = max(weak_indoor_demote, indoor_culture_fallback_demote)
            demote = max(demote, indoor_culture_fallback_demote)
            demote_reasons.append(
                "gyeongnam_mixed_indoor_culture:" + ",".join(indoor_matches[:3])
            )

    first_place_slot = slot in {"anchor", "morning", "morning_2"}

    if inferred_belt == "진주남강역사":
        jinju_matches = _alias_matches(text, _JINJU_HISTORY_REPRESENTATIVE_TERMS)
        weak_jinju_matches = _alias_matches(text, _JINJU_WEAK_FIRST_PLACE_TERMS)
        if jinju_matches:
            distinct_jinju = sorted(set(jinju_matches))
            jinju_history_first_place_bonus = min(
                0.08,
                0.022 * len(distinct_jinju) + (0.025 if first_place_slot else 0.0),
            )
            bonus = max(bonus, min(0.12, jinju_history_first_place_bonus))
            landmark_alignment_reason = landmark_alignment_reason or (
                "jinju_history_representative:" + ",".join(distinct_jinju[:4])
            )
        if first_place_slot and weak_jinju_matches and not jinju_matches:
            weak_museum_first_place_demote = max(weak_museum_first_place_demote, 0.14)
            demote = max(demote, weak_museum_first_place_demote)
            demote_reasons.append("jinju_weak_museum_first_place:" + ",".join(weak_jinju_matches[:3]))

    if inferred_belt in {"통영동피랑", "통영항구동피랑", "통영미륵산"}:
        tongyeong_matches = _alias_matches(text, _TONGYEONG_SAME_CITY_TERMS)
        geoje_drift_matches = _alias_matches(text, _TONGYEONG_GEOJE_DRIFT_TERMS)
        if tongyeong_matches:
            distinct_tongyeong = sorted(set(tongyeong_matches))
            tongyeong_same_city_bonus = min(
                0.085,
                0.021 * len(distinct_tongyeong) + (0.018 if first_place_slot else 0.0),
            )
            bonus = max(bonus, min(0.12, tongyeong_same_city_bonus))
            landmark_alignment_reason = landmark_alignment_reason or (
                "tongyeong_same_city:" + ",".join(distinct_tongyeong[:4])
            )
        if geoje_drift_matches and not tongyeong_matches:
            tongyeong_geoje_drift_demote = 0.14 if first_place_slot else 0.1
            demote = max(demote, tongyeong_geoje_drift_demote)
            demote_reasons.append("tongyeong_geoje_drift:" + ",".join(geoje_drift_matches[:3]))
        elif geoje_drift_matches:
            tongyeong_geoje_drift_demote = 0.04
            demote = max(demote, tongyeong_geoje_drift_demote)
            demote_reasons.append("tongyeong_mixed_geoje_drift:" + ",".join(geoje_drift_matches[:3]))

    if inferred_belt == "김해가야":
        gimhae_matches = _alias_matches(text, _GIMHAE_GAYA_FAMILY_TERMS)
        weak_gimhae_matches = _alias_matches(text, _GIMHAE_GAYA_WEAK_DRIFT_TERMS)
        support_gimhae_matches = _alias_matches(text, _GIMHAE_SUPPORT_SLOT_TERMS)
        weak_support_gimhae_matches = _alias_matches(text, _GIMHAE_SUPPORT_SLOT_WEAK_TERMS)
        if gimhae_matches:
            distinct_gimhae = sorted(set(gimhae_matches))
            gimhae_gaya_family_score = min(
                0.09,
                0.022 * len(distinct_gimhae) + (0.02 if first_place_slot else 0.0),
            )
            bonus = max(bonus, min(0.12, gimhae_gaya_family_score))
            landmark_alignment_reason = landmark_alignment_reason or (
                "gimhae_gaya_family:" + ",".join(distinct_gimhae[:4])
            )
        if weak_gimhae_matches and not gimhae_matches:
            demote_value = 0.09 if first_place_slot else 0.06
            demote = max(demote, demote_value)
            demote_reasons.append("gimhae_gaya_family_drift:" + ",".join(weak_gimhae_matches[:3]))
        if not first_place_slot:
            if support_gimhae_matches:
                distinct_support = sorted(set(support_gimhae_matches))
                gimhae_support_slot_family_score = min(
                    0.11,
                    0.028 * len(distinct_support),
                )
                support_slot_coherence_score = max(
                    support_slot_coherence_score,
                    gimhae_support_slot_family_score,
                )
                bonus = max(bonus, min(0.12, gimhae_support_slot_family_score))
                landmark_alignment_reason = landmark_alignment_reason or (
                    "gimhae_support_slot_family:" + ",".join(distinct_support[:4])
                )
            if weak_support_gimhae_matches and not support_gimhae_matches:
                gimhae_support_slot_drift_demote = max(
                    gimhae_support_slot_drift_demote,
                    0.075 if role in {"meal", "cafe"} else 0.055,
                )
                demote = max(demote, gimhae_support_slot_drift_demote)
                demote_reasons.append(
                    "gimhae_support_slot_drift:" + ",".join(weak_support_gimhae_matches[:3])
                )

    if str(region_identity.get("region") or "") == "서울":
        seoul_rep_matches = _alias_matches(text, _SEOUL_DEFAULT_REPRESENTATIVE_TERMS)
        seoul_weak_matches = _alias_matches(text, _SEOUL_DEFAULT_WEAK_FIRST_PLACE_TERMS)
        if first_place_slot and seoul_rep_matches:
            distinct_seoul_rep = sorted(set(seoul_rep_matches))
            seoul_default_representative_score = min(
                0.08,
                0.022 * len(distinct_seoul_rep) + 0.02,
            )
            bonus = max(bonus, min(0.1, seoul_default_representative_score))
            landmark_alignment_reason = landmark_alignment_reason or (
                "seoul_default_representative:" + ",".join(distinct_seoul_rep[:4])
            )
        if first_place_slot and not seoul_rep_matches and role in {"meal", "cafe"}:
            seoul_default_weak_first_place_demote = max(
                seoul_default_weak_first_place_demote,
                0.085,
            )
            demote = max(demote, seoul_default_weak_first_place_demote)
            demote_reasons.append("seoul_default_weak_first_place:generic_meal_cafe")
        if first_place_slot and seoul_weak_matches and not seoul_rep_matches:
            seoul_default_weak_first_place_demote = max(seoul_default_weak_first_place_demote, 0.12)
            demote = max(demote, seoul_default_weak_first_place_demote)
            demote_reasons.append(
                "seoul_default_weak_first_place:" + ",".join(seoul_weak_matches[:3])
            )

    return {
        "editorial_bonus": round(min(0.09, bonus), 4),
        "editorial_demote": round(min(0.14, demote), 4),
        "editorial_demote_reason": ";".join(demote_reasons) if demote_reasons else None,
        "weak_first_place_reason": weak_first_place_reason,
        "central_drift_reason": central_drift_reason,
        "landmark_priority_score": round(landmark_priority_score, 4),
        "representative_vibe_score": round(representative_vibe_score, 4),
        "weak_indoor_demote": round(weak_indoor_demote, 4),
        "landmark_alignment_reason": landmark_alignment_reason,
        "seongsu_vibe_score": round(seongsu_vibe_score, 4),
        "cafe_street_alignment": round(cafe_street_alignment, 4),
        "weak_meal_demote": round(weak_meal_demote, 4),
        "editorial_first_place_bonus": round(editorial_first_place_bonus, 4),
        "euljiro_night_score": round(euljiro_night_score, 4),
        "hipjiro_alignment": round(hipjiro_alignment, 4),
        "central_drift_demote": round(central_drift_demote, 4),
        "night_vibe_bonus": round(night_vibe_bonus, 4),
        "seoul_date_score": round(seoul_date_score, 4),
        "date_vibe_alignment": round(date_vibe_alignment, 4),
        "broad_seoul_drift_demote": round(broad_seoul_drift_demote, 4),
        "romantic_walk_bonus": round(romantic_walk_bonus, 4),
        "busan_night_meal_score": round(busan_night_meal_score, 4),
        "waterfront_alignment": round(waterfront_alignment, 4),
        "weak_daytime_meal_demote": round(weak_daytime_meal_demote, 4),
        "night_meal_bonus": round(night_meal_bonus, 4),
        "busan_landmark_priority_score": round(busan_landmark_priority_score, 4),
        "busan_representative_bonus": round(busan_representative_bonus, 4),
        "busan_landmark_alignment_reason": busan_landmark_alignment_reason,
        "representative_tourism_family_score": round(representative_tourism_family_score, 4),
        "indoor_culture_fallback_demote": round(indoor_culture_fallback_demote, 4),
        "regional_landmark_density": round(regional_landmark_density, 4),
        "first_place_representative_bonus": round(first_place_representative_bonus, 4),
        "jinju_history_first_place_bonus": round(jinju_history_first_place_bonus, 4),
        "tongyeong_same_city_bonus": round(tongyeong_same_city_bonus, 4),
        "tongyeong_geoje_drift_demote": round(tongyeong_geoje_drift_demote, 4),
        "gimhae_gaya_family_score": round(gimhae_gaya_family_score, 4),
        "gimhae_support_slot_family_score": round(gimhae_support_slot_family_score, 4),
        "gimhae_support_slot_drift_demote": round(gimhae_support_slot_drift_demote, 4),
        "support_slot_coherence_score": round(support_slot_coherence_score, 4),
        "seoul_default_representative_score": round(seoul_default_representative_score, 4),
        "seoul_default_weak_first_place_demote": round(seoul_default_weak_first_place_demote, 4),
        "weak_museum_first_place_demote": round(weak_museum_first_place_demote, 4),
        "editorial_profile": profile_name,
    }


def summarize_route_coherence(
    places: list[dict[str, Any]],
    region_identity: dict[str, Any] | None,
    flow_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """Summarize course-level route coherence without mutating selection."""
    places = [p for p in (places or []) if isinstance(p, dict)]
    if not places:
        return {
            "route_coherence_score": 0.0,
            "route_purity_score": 0.0,
            "same_region_ratio": 0.0,
            "same_belt_ratio": 0.0,
            "contamination_region_pairs": [],
            "contamination_flags": [],
            "cross_flow_candidate_count": 0,
            "lifestyle_mismatch_count": 0,
            "route_contamination_count": 0,
            "route_coherence_notes": ["empty_course"],
        }

    flags: list[dict[str, Any]] = []
    cross_flow_count = 0
    lifestyle_count = 0
    contamination_count = 0
    same_belt_count = 0
    cross_belt_count = 0
    contamination_region_pairs: list[dict[str, Any]] = []
    continuity_sum = 0.0
    prev: dict[str, Any] | None = None
    for idx, place in enumerate(places):
        signal = score_route_contamination(place, region_identity, flow_profile)
        belt_signal = score_belt_match(place, region_identity)
        if float(belt_signal.get("belt_match_bonus") or 0.0) > 0:
            same_belt_count += 1
        wrong_belt = belt_signal.get("wrong_belt_match")
        if wrong_belt:
            cross_belt_count += 1
            contamination_region_pairs.append({
                "place_order": idx + 1,
                "place_name": place.get("name"),
                "expected_belt": (region_identity or {}).get("inferred_belt") if isinstance(region_identity, dict) else None,
                "detected_belt": (wrong_belt or {}).get("belt"),
                "matched_aliases": (wrong_belt or {}).get("matched_aliases") or [],
            })
        place_flags = signal.get("route_contamination_flags") or []
        if place_flags:
            pure_belt_drift = set(place_flags) == {"belt_contamination"}
            if not pure_belt_drift:
                contamination_count += 1
            if "flow_contamination" in place_flags or "meal_flow_mismatch" in place_flags:
                cross_flow_count += 1
            if "lifestyle_contamination" in place_flags or "generic_commerce_mismatch" in place_flags:
                lifestyle_count += 1
            flags.append({
                "place_order": idx + 1,
                "place_name": place.get("name"),
                "visit_role": place.get("visit_role"),
                "flags": place_flags,
                "reasons": signal.get("route_contamination_reasons") or [],
                "trace_only": pure_belt_drift,
            })
        continuity_sum += float(score_flow_continuity(place, prev, flow_profile).get("continuity_bonus") or 0.0)
        prev = place

    same_belt_ratio = round(same_belt_count / max(len(places), 1), 4)
    same_region_ratio = round((len(places) - cross_belt_count) / max(len(places), 1), 4)
    purity_penalty = min(0.18, 0.05 * cross_belt_count)
    route_purity_score = max(0.0, min(1.0, 0.72 + (0.22 * same_belt_ratio) - purity_penalty))
    penalty = min(
        0.45,
        0.10 * contamination_count
        + 0.04 * cross_flow_count
        + 0.04 * lifestyle_count
        + 0.03 * cross_belt_count,
    )
    continuity_score = min(0.20, continuity_sum / max(len(places), 1))
    route_score = max(0.0, min(1.0, 0.82 + continuity_score - penalty))
    return {
        "route_coherence_score": round(route_score, 4),
        "route_purity_score": round(route_purity_score, 4),
        "same_region_ratio": same_region_ratio,
        "same_belt_ratio": same_belt_ratio,
        "contamination_region_pairs": contamination_region_pairs[:8],
        "contamination_flags": flags,
        "cross_flow_candidate_count": int(cross_flow_count),
        "lifestyle_mismatch_count": int(lifestyle_count),
        "route_contamination_count": int(contamination_count),
        "route_coherence_notes": [] if not flags else ["soft_contamination_detected"],
    }


# NATIONWIDE_AUDIT_FIX_PHASE1_SEEDS
# Advisory identity metadata only: no hard city/belt lock and no route insertion.
REGION_IDENTITY_BELTS.setdefault("충북", {}).update({
    "청주도심역사": {
        "vibe_tags": ["역사", "도심", "산책", "카페", "청주"],
        "tourism_keywords": ["청주", "상당산성", "수암골", "청남대", "국립현대미술관 청주", "성안길"],
        "representative_poi_aliases": ["상당산성", "수암골", "청남대", "국립현대미술관 청주", "성안길", "청주"],
        "representative_categories": ["history", "culture", "walk", "cafe"],
        "anchor": {"name": "수암골 벽화마을", "lat": 36.6473, "lng": 127.4943},
        "nearby_anchor_aliases": ["수암골", "성안길", "청남대"],
        "mobility_traits": ["history_walk", "walking", "family"],
    },
    "단양자연": {
        "vibe_tags": ["자연", "강", "전망", "드라이브", "단양"],
        "tourism_keywords": ["단양", "도담삼봉", "만천하스카이워크", "단양강잔도", "고수동굴", "사인암"],
        "representative_poi_aliases": ["도담삼봉", "만천하스카이워크", "단양강잔도", "고수동굴", "사인암", "단양"],
        "representative_categories": ["nature", "spot", "drive"],
        "anchor": {"name": "만천하 경관", "lat": 36.9769, "lng": 128.3372},
        "nearby_anchor_aliases": ["만천하스카이워크", "단양강잔도", "고수동굴", "사인암"],
        "mobility_traits": ["drive", "nature", "family"],
    },
})
REGION_IDENTITY_BELTS.setdefault("강원", {}).update({
    "대관령목장": {
        "vibe_tags": ["고원", "목장", "자연", "드라이브", "대관령"],
        "tourism_keywords": ["대관령", "양떼목장", "삼양목장", "하늘목장", "선자령", "평창", "고원"],
        "representative_poi_aliases": ["대관령", "대관령양떼목장", "삼양목장", "하늘목장", "선자령"],
        "representative_categories": ["nature", "drive", "family"],
        "anchor": {"name": "대관령양떼목장", "lat": 37.6881, "lng": 128.7545},
        "nearby_anchor_aliases": ["삼양목장", "하늘목장", "선자령", "평창"],
        "mobility_traits": ["drive", "nature", "family"],
    },
    "속초해안": {
        "vibe_tags": ["바다", "호수", "카페", "시장", "속초"],
        "tourism_keywords": ["속초", "속초해수욕장", "속초 바다", "영랑호", "청초호", "대포항", "중앙시장"],
        "representative_poi_aliases": ["속초해수욕장", "영랑호", "청초호", "대포항", "속초중앙시장"],
        "representative_categories": ["sea", "spot", "cafe"],
        "anchor": {"name": "속초해수욕장", "lat": 38.1909, "lng": 128.6037},
        "nearby_anchor_aliases": ["영랑호", "청초호", "대포항", "중앙시장"],
        "mobility_traits": ["sea_view", "cafe_relaxed", "walk_emotional"],
    },
    "양양해변": {
        "vibe_tags": ["서핑", "바다", "오션뷰", "카페", "양양"],
        "tourism_keywords": ["양양", "죽도해변", "인구해변", "서피비치", "낙산", "양양 바다"],
        "representative_poi_aliases": ["죽도해변", "인구해변", "서피비치", "낙산사", "낙산해변"],
        "representative_categories": ["sea", "spot", "cafe"],
        "anchor": {"name": "죽도해변", "lat": 37.9720, "lng": 128.7600},
        "nearby_anchor_aliases": ["인구해변", "서피비치", "낙산"],
        "mobility_traits": ["sea_view", "cafe_relaxed", "surf"],
    },
})
REGION_IDENTITY_BELTS.setdefault("경남", {}).update({
    "김해가야": {
        "vibe_tags": ["가야", "역사", "박물관", "유적", "김해"],
        "tourism_keywords": ["김해", "가야", "김해가야테마파크", "국립김해박물관", "수로왕릉", "봉황동유적", "대성동고분군"],
        "representative_poi_aliases": ["김해가야테마파크", "국립김해박물관", "수로왕릉", "봉황동유적", "대성동고분군", "김해"],
        "representative_categories": ["history", "culture", "family"],
        "anchor": {"name": "김해가야테마파크", "lat": 35.2497, "lng": 128.8726},
        "nearby_anchor_aliases": ["국립김해박물관", "수로왕릉", "봉황동유적", "대성동고분군"],
        "mobility_traits": ["history_walk", "family", "walking"],
    },
})
for _region_name, _belt_names in {
    "충북": ["청주도심역사", "단양자연"],
    "강원": ["속초해안", "양양해변", "대관령목장"],
    "경남": ["김해가야"],
}.items():
    _existing = _BROAD_REGION_BELT_PRIORITIES.setdefault(_region_name, [])
    for _belt_name in reversed(_belt_names):
        if _belt_name in _existing:
            _existing.remove(_belt_name)
        _existing.insert(0, _belt_name)

# GYEONGNAM_REPRESENTATIVE_TOURISM_POLISH_PHASE1
# Advisory metadata only. This improves identity inference and soft ranking
# without inserting fake POIs, hard-locking routes, or blocking fallback.
REGION_IDENTITY_BELTS.setdefault("경남", {}).update({
    "창원마산해양산책": {
        "vibe_tags": ["해양공원", "벚꽃", "항구", "시장", "저수지", "산책"],
        "tourism_keywords": ["창원", "마산", "진해", "진해해양공원", "여좌천", "경화역", "마산어시장", "저도콰이강", "주남저수지"],
        "representative_poi_aliases": ["진해해양공원", "여좌천", "경화역", "마산어시장", "저도콰이강", "저도연륙교", "콰이강의다리", "주남저수지"],
        "representative_categories": ["sea", "walk", "market", "nature"],
        "anchor": {"name": "진해해양공원", "lat": 35.0896, "lng": 128.7259},
        "nearby_anchor_aliases": ["진해", "마산", "여좌천", "경화역", "마산어시장", "저도콰이강", "주남저수지"],
        "mobility_traits": ["walk_emotional", "sea_drive", "family"],
    },
    "통영항구동피랑": {
        "vibe_tags": ["항구", "벽화마을", "전망", "야간", "바다"],
        "tourism_keywords": ["통영", "동피랑", "이순신공원", "통영케이블카", "강구안", "디피랑"],
        "representative_poi_aliases": ["동피랑", "이순신공원", "통영케이블카", "강구안", "디피랑"],
        "representative_categories": ["sea", "spot", "walk", "night"],
        "anchor": {"name": "동피랑", "lat": 34.8466, "lng": 128.4240},
        "nearby_anchor_aliases": ["통영", "강구안", "디피랑", "케이블카"],
        "mobility_traits": ["sea_drive", "walk_emotional", "night_city"],
    },
    "거제해안드라이브": {
        "vibe_tags": ["오션뷰", "드라이브", "해변", "섬", "전망"],
        "tourism_keywords": ["거제", "바람의언덕", "외도", "구조라", "학동몽돌해변"],
        "representative_poi_aliases": ["바람의언덕", "외도", "외도보타니아", "구조라", "학동몽돌해변"],
        "representative_categories": ["sea", "drive", "spot"],
        "anchor": {"name": "바람의언덕", "lat": 34.7443, "lng": 128.6635},
        "nearby_anchor_aliases": ["거제", "외도", "구조라", "학동몽돌"],
        "mobility_traits": ["sea_drive", "drive", "nature"],
    },
    "남해해안감성": {
        "vibe_tags": ["해안도로", "마을", "전망", "감성", "사찰"],
        "tourism_keywords": ["남해", "독일마을", "다랭이마을", "보리암"],
        "representative_poi_aliases": ["독일마을", "남해독일마을", "다랭이마을", "보리암"],
        "representative_categories": ["sea", "drive", "spot", "walk"],
        "anchor": {"name": "남해독일마을", "lat": 34.7970, "lng": 128.0391},
        "nearby_anchor_aliases": ["남해", "다랭이", "보리암"],
        "mobility_traits": ["sea_drive", "walk_emotional", "drive"],
    },
    "진주남강역사": {
        "vibe_tags": ["역사", "강변", "야경", "산책"],
        "tourism_keywords": ["진주", "진주성", "남강", "촉석루"],
        "representative_poi_aliases": ["진주성", "남강", "촉석루"],
        "representative_categories": ["history", "walk", "night"],
        "anchor": {"name": "진주성", "lat": 35.1898, "lng": 128.0766},
        "nearby_anchor_aliases": ["진주", "촉석루", "남강"],
        "mobility_traits": ["history_walk", "walk_emotional", "night_city"],
    },
    "김해가야": {
        "vibe_tags": ["가야", "역사", "박물관", "유적", "가족"],
        "tourism_keywords": ["김해", "김해가야테마파크", "국립김해박물관", "수로왕릉", "봉황동유적", "대성동고분군"],
        "representative_poi_aliases": ["김해가야테마파크", "국립김해박물관", "수로왕릉", "봉황동유적", "대성동고분군"],
        "representative_categories": ["history", "culture", "family"],
        "anchor": {"name": "김해가야테마파크", "lat": 35.2497, "lng": 128.8726},
        "nearby_anchor_aliases": ["김해", "가야", "수로왕릉", "국립김해박물관"],
        "mobility_traits": ["history_walk", "family", "walking"],
    },
})
for _region_name, _belt_names in {
    "경남": [
        "창원마산해양산책",
        "통영항구동피랑",
        "통영동피랑",
        "통영미륵산",
        "거제해안드라이브",
        "거제바람의언덕",
        "남해해안감성",
        "남해독일마을",
        "진주남강역사",
        "김해가야",
    ],
}.items():
    _existing = _BROAD_REGION_BELT_PRIORITIES.setdefault(_region_name, [])
    for _belt_name in reversed(_belt_names):
        if _belt_name in _existing:
            _existing.remove(_belt_name)
        _existing.insert(0, _belt_name)
