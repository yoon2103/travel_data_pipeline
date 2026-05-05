"""
enrichment_service.py — meal/cafe 런타임 보강 + 품질 검증 레이어

진입점:
  enrich_course_places(course) -> dict   # 외부 데이터 보강 (기존)
  validate_course_quality(course) -> dict # 노출 전 품질 검증 (신규)

제약:
- DB 저장 없음, 캐싱 없음 (1차 구현)
- 엔진 후보 선정/Hard Filter/scoring에 사용 금지
- 표시용 데이터 보강·검증 전용
- spot/culture는 절대 건드리지 않음

외부 API 우선순위: Kakao → Naver (Kakao가 category 정보 제공)
"""

import json
import logging
import re
import urllib.parse
import urllib.request
from math import atan2, cos, radians, sin, sqrt

import config

logger = logging.getLogger(__name__)

COORD_MATCH_KM = 1.0   # 좌표 기반 매칭 허용 반경


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    la1, lo1, la2, lo2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = la2 - la1
    dlon = lo2 - lo1
    a = sin(dlat / 2) ** 2 + cos(la1) * cos(la2) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _normalize(text: str) -> str:
    return re.sub(r"[\s\-·\(\)]", "", text).lower()


def _name_match(query: str, candidate: str) -> bool:
    q = _normalize(query)
    c = _normalize(candidate)
    return q == c or (len(q) >= 2 and (q in c or c in q))


def _coord_ok(lat: float | None, lon: float | None,
               cand_lat: float, cand_lon: float) -> bool:
    if lat is None or lon is None:
        return True  # 좌표 없으면 이름 매칭만으로 통과
    return _haversine(lat, lon, cand_lat, cand_lon) <= COORD_MATCH_KM


# ---------------------------------------------------------------------------
# Naver Local Search
# ---------------------------------------------------------------------------

def _fetch_naver(name: str, region: str,
                 lat: float | None, lon: float | None) -> dict | None:
    if not config.NAVER_CLIENT_ID or not config.NAVER_CLIENT_SECRET:
        return None
    try:
        query = urllib.parse.quote(f"{name} {region}")
        url   = f"https://openapi.naver.com/v1/search/local.json?query={query}&display=5"
        req   = urllib.request.Request(url, headers={
            "X-Naver-Client-Id":     config.NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
        })
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())

        for item in data.get("items", []):
            title = _strip_html(item.get("title", ""))
            if not _name_match(name, title):
                continue
            try:
                cand_lon = int(item["mapx"]) / 1e7
                cand_lat = int(item["mapy"]) / 1e7
                if not _coord_ok(lat, lon, cand_lat, cand_lon):
                    continue
            except (KeyError, ValueError, TypeError):
                pass  # 좌표 파싱 실패 시 이름 매칭만으로 수락

            return {
                "source":       "naver",
                "rating":       None,  # Naver Local 검색은 rating 미제공
                "review_count": None,
                "image_url":    item.get("image") or None,
                "address":      item.get("roadAddress") or item.get("address") or None,
                "is_open":      None,
            }
    except Exception as exc:
        logger.debug("Naver enrichment 실패 — %s: %s", name, exc)
    return None


# ---------------------------------------------------------------------------
# Kakao Keyword Search
# ---------------------------------------------------------------------------

def _fetch_kakao(name: str, region: str,
                 lat: float | None, lon: float | None) -> dict | None:
    if not config.KAKAO_REST_API_KEY:
        return None
    try:
        params: dict = {"query": f"{name} {region}", "size": 5}
        if lat is not None and lon is not None:
            params["x"]      = str(lon)
            params["y"]      = str(lat)
            params["radius"] = "1000"
        url = "https://dapi.kakao.com/v2/local/search/keyword.json?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "Authorization": f"KakaoAK {config.KAKAO_REST_API_KEY}",
        })
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())

        for doc in data.get("documents", []):
            place_name = doc.get("place_name", "")
            if not _name_match(name, place_name):
                continue
            try:
                cand_lon = float(doc["x"])
                cand_lat = float(doc["y"])
                if not _coord_ok(lat, lon, cand_lat, cand_lon):
                    continue
            except (KeyError, ValueError, TypeError):
                pass

            rating_raw = doc.get("rating")
            return {
                "source":              "kakao",
                "rating":              float(rating_raw) if rating_raw else None,
                "review_count":        None,
                "image_url":           None,
                "address":             doc.get("road_address_name") or doc.get("address_name") or None,
                "is_open":             None,
                "category_group_code": doc.get("category_group_code", ""),
                "category_name":       doc.get("category_name", ""),
            }
    except Exception as exc:
        logger.debug("Kakao enrichment 실패 — %s: %s", name, exc)
    return None


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def _fetch_external(name: str, region: str,
                    lat: float | None, lon: float | None) -> dict | None:
    """Kakao → Naver 순으로 시도. Kakao 우선 (category 정보 제공). 둘 다 실패하면 None."""
    result = _fetch_kakao(name, region, lat, lon)
    if result:
        return result
    return _fetch_naver(name, region, lat, lon)


# ---------------------------------------------------------------------------
# 품질 검증 (Quality Validation)
# ---------------------------------------------------------------------------

# 기관 부속 식당 / 구내식당 판별 키워드
_INSTITUTIONAL_HARD: tuple[str, ...] = (
    "구내식당", "직원식당", "교직원식당", "학생식당", "기관식당",
    "기숙사식당", "교내식당", "사원식당", "환자식당",
)

# Kakao category_group_code → expected visit_role
_KAKAO_ROLE_MAP: dict[str, str] = {
    "FD6": "meal",   # 음식점
    "CE7": "cafe",   # 카페
}


def is_institutional(name: str) -> bool:
    """구내식당/기관 부속 식당 여부 (이름 기반 로컬 판별)."""
    n = name.replace(" ", "")
    return any(kw in n for kw in _INSTITUTIONAL_HARD)


def _compute_quality(visit_role: str, name: str, ext: dict | None) -> tuple[float, list[str]]:
    """
    quality_score (0.0~1.0) 와 quality_reason 목록 반환.

    점수 기준:
    - 외부 검색 결과 없음:  -0.30
    - 기관 부속 식당:       -0.60 (이름 기반)
    - 카테고리 불일치:       -0.20
    점수는 0.0 미만으로 내려가지 않음.
    """
    reasons: list[str] = []
    score = 1.0

    # 기관 식당 로컬 판별 (API 없이도 적용)
    if visit_role == "meal" and is_institutional(name):
        reasons.append("기관/구내 식당으로 판별됨")
        score -= 0.60

    if ext is None:
        reasons.append("외부 검색 결과 없음")
        score -= 0.30
        return max(score, 0.0), reasons

    # Kakao category 매칭
    code = ext.get("category_group_code", "")
    if code:
        expected_role = _KAKAO_ROLE_MAP.get(code)
        if expected_role and expected_role != visit_role:
            reasons.append(f"카테고리 불일치 (kakao={code}, 기대={visit_role})")
            score -= 0.20

    return max(score, 0.0), reasons


def validate_course_quality(course: dict) -> dict:
    """
    course["places"] 내 meal/cafe 장소에 품질 검증 정보를 추가한다.

    추가 필드:
      place["quality_score"]  : float 0.0~1.0 (1.0=문제없음, <0.4=주의)
      place["quality_reason"] : list[str] | None  (문제 사유 목록)
      place["quality_source"] : "kakao" | "naver" | "local" | None

    외부 API 실패 시 코스 생성 중단 없음 — quality_score=None, reason=None 처리.
    """
    region = course.get("region", "")
    for place in course.get("places", []):
        role = place.get("visit_role", "")
        if role not in ("meal", "cafe"):
            continue

        name = place.get("name", "")
        lat  = place.get("latitude")
        lon  = place.get("longitude")

        ext = None
        try:
            ext = _fetch_external(name, region, lat, lon)
        except Exception as exc:
            logger.debug("quality 외부 API 실패 — %s: %s", name, exc)

        q_score, q_reasons = _compute_quality(role, name, ext)
        place["quality_score"]  = round(q_score, 2)
        place["quality_reason"] = q_reasons if q_reasons else None
        place["quality_source"] = ext.get("source") if ext else ("local" if is_institutional(name) else None)
        logger.debug(
            "quality 검증 — %s score=%.2f reason=%s",
            name, q_score, q_reasons,
        )

    return course


def enrich_course_places(course: dict) -> dict:
    """
    course["places"] 내 meal/cafe 장소에 외부 API 보강 정보를 추가한다.

    성공 시 place["external"] = {
        source, rating, review_count, image_url, address, is_open
    }
    실패(매칭 없음 / API 미설정) 시 external 필드 없음 유지.

    Parameters
    ----------
    course : build_course() 반환값 (places 배열 포함)

    Returns
    -------
    동일 course dict (in-place 수정 후 반환)
    """
    if not (config.NAVER_CLIENT_ID or config.KAKAO_REST_API_KEY):
        logger.debug("enrichment API 키 미설정 — pass-through")
        return course

    region = course.get("region", "")
    for place in course.get("places", []):
        if place.get("visit_role") not in ("meal", "cafe"):
            continue
        name = place.get("name", "")
        lat  = place.get("latitude")
        lon  = place.get("longitude")

        external = _fetch_external(name, region, lat, lon)
        if external:
            place["external"] = external
            logger.debug("enrichment 성공 — %s (%s)", name, external["source"])
        else:
            logger.debug("enrichment 매칭 실패 — %s", name)

    return course
