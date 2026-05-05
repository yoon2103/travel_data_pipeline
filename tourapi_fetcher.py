import math
import sys
import time
import logging
from datetime import datetime
from typing import Generator

import requests

import config

sys.stdout.reconfigure(encoding="utf-8", errors="replace") if hasattr(sys.stdout, "reconfigure") else None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

AREA_NAMES: dict[int, str] = {
    1: "서울", 2: "인천", 3: "대전",  4: "대구",
    5: "광주", 6: "부산", 7: "울산",  8: "세종",
    31: "경기", 32: "강원", 33: "충북", 34: "충남",
    35: "경북", 36: "경남", 37: "전북", 38: "전남",
    39: "제주",
}

ALL_AREA_CODES: list[int] = list(AREA_NAMES.keys())

ALL_CONTENT_TYPES: list[int] = [12, 14, 15, 28, 32, 38, 39]
# 12:관광지 14:문화시설 15:축제행사 28:레포츠 32:숙박 38:쇼핑 39:음식점

_FIXED_PARAMS = {
    "MobileOS":  "WEB",
    "MobileApp": "TravelApp",
    "_type":     "json",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

_MAX_RETRIES        = 3
_RETRY_BASE_DELAY   = 2    # 초 — 지수 백오프
_PAGE_SIZE          = 100
_INTER_PAGE_DELAY   = 0.5  # 페이지 간 딜레이
_DETAIL_DELAY       = 0.4  # detailCommon2 아이템 간 딜레이 (429 방지)
_MAX_CONSEC_FAILS   = 3    # 연속 실패 허용 횟수 초과 시 해당 타입 중단


# ---------------------------------------------------------------------------
# 내부 HTTP 헬퍼
# ---------------------------------------------------------------------------

def _mask_key(url: str) -> str:
    """로그 출력용 — 서비스 키 중간을 ***로 마스킹."""
    if "serviceKey=" not in url:
        return url
    before, rest = url.split("serviceKey=", 1)
    key_part = rest.split("&")[0]
    masked = key_part[:6] + "***" + key_part[-4:] if len(key_part) > 12 else "***"
    return url.replace(key_part, masked)


def _get(endpoint: str, params: dict) -> dict:
    # ③ 최신 엔드포인트(KorService1) + serviceKey URL 직접 조립
    #    params dict 경유 시 requests 가 키를 이중 인코딩하는 문제 방지
    base = f"{config.TOURAPI_BASE_URL}/{endpoint}?serviceKey={config.TOURAPI_SERVICE_KEY}"
    all_params = {**_FIXED_PARAMS, **params}

    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.get(base, params=all_params, headers=_HEADERS, timeout=15)

            # 실패 시 진단용 전체 URL 출력 (키 마스킹)
            if resp.status_code != 200:
                logger.error("HTTP %s — 실제 요청 URL: %s",
                             resp.status_code, _mask_key(resp.url))

            resp.raise_for_status()
            data = resp.json()

            header = data.get("response", {}).get("header", {})
            if header.get("resultCode") != "0000":
                raise ValueError(
                    f"TourAPI error [{header.get('resultCode')}]: {header.get('resultMsg')}"
                )
            return data

        except (requests.RequestException, ValueError) as exc:
            if attempt == _MAX_RETRIES - 1:
                raise
            # 429 Rate Limit은 더 길게 대기
            if hasattr(exc, 'response') and getattr(exc.response, 'status_code', 0) == 429:
                wait = 10 * (attempt + 1)
                logger.warning(f"429 Rate Limit — {wait}s 대기 후 재시도 ({attempt+1}/{_MAX_RETRIES})")
            else:
                wait = _RETRY_BASE_DELAY * (attempt + 1)
                logger.warning(f"Attempt {attempt + 1}/{_MAX_RETRIES} failed ({exc}). Retry in {wait}s…")
            time.sleep(wait)


# ---------------------------------------------------------------------------
# 공개 API 래퍼
# ---------------------------------------------------------------------------

def fetch_area_list(
    content_type_id: int,
    area_code: int,
    page: int = 1,
    num_rows: int = _PAGE_SIZE,
) -> tuple[list[dict], int]:
    """areaBasedList2 — 지역·타입별 목록 한 페이지를 반환."""
    data = _get("areaBasedList2", {
        "numOfRows":     num_rows,
        "pageNo":        page,
        "arrange":       "A",
        "contentTypeId": content_type_id,
        "areaCode":      area_code,
    })
    body = data["response"]["body"]
    total = int(body.get("totalCount", 0))
    raw_items = body.get("items") or {}
    items = raw_items.get("item") or []
    if isinstance(items, dict):      # 결과가 1건이면 dict로 내려오는 경우
        items = [items]
    return items, total


def fetch_detail(content_id: str) -> dict:
    """detailCommon2 — 장소 1건의 상세 정보(overview 포함)를 반환."""
    data = _get("detailCommon2", {
        "contentId": content_id,
    })
    raw_items = data["response"]["body"].get("items") or {}
    items = raw_items.get("item") or []
    if isinstance(items, dict):
        items = [items]
    return items[0] if items else {}


# ---------------------------------------------------------------------------
# 파이프라인용 제너레이터
# ---------------------------------------------------------------------------

def iter_all_places(
    content_type_ids: list[int] | None = None,
    area_codes: list[int] | None = None,
    include_detail: bool = True,
) -> Generator[dict, None, None]:
    """
    지정한 content_type × area 조합을 완전 탐색하며 정규화된 place dict를 yield한다.

    Parameters
    ----------
    include_detail : True(기본)면 각 아이템마다 detailCommon2 호출하여 overview 포함.
                     False면 areaBasedList2 목록만 수집 (일일 API 호출 절약 모드).
                     → 1단계: --no-detail 로 기본 데이터 전수 수집 (페이지당 1회 호출)
                     → 2단계: fill-overview 로 overview만 별도 보충

    동작 특성
    ---------
    - 첫 페이지에서 totalCount 파악 → 전체 페이지 수 계산 및 로그 출력
    - 페이지 실패 시 해당 페이지만 건너뛰고 진행 (연속 실패 _MAX_CONSEC_FAILS 초과 시 중단)
    - include_detail=True 일 때 아이템 간 _DETAIL_DELAY(0.4s) 슬립으로 429 방지
    """
    target_types = content_type_ids or ALL_CONTENT_TYPES
    target_areas = area_codes or ALL_AREA_CODES

    for area_code in target_areas:
        region_1 = AREA_NAMES.get(area_code, str(area_code))

        for content_type_id in target_types:
            page          = 1
            fetched       = 0
            total         = None
            total_pages   = None
            consec_fails  = 0

            while True:
                # ── 페이지 단위 fetch ─────────────────────────────────
                try:
                    items, total_count = fetch_area_list(
                        content_type_id, area_code, page, _PAGE_SIZE
                    )
                    consec_fails = 0

                    if total is None:
                        total       = total_count
                        total_pages = max(1, math.ceil(total / _PAGE_SIZE))
                        mode_label  = "목록전용" if not include_detail else "상세포함"
                        logger.info(
                            "[Bulk][%s] %s contentType=%d - 총 %d건 / %d 페이지",
                            mode_label, region_1, content_type_id, total, total_pages,
                        )

                    logger.info(
                        "[Bulk] %s  %d/%d 페이지 수집 중... (%d건)",
                        region_1, page, total_pages, len(items),
                    )

                except Exception as exc:
                    consec_fails += 1
                    logger.warning(
                        "[Bulk] %s contentType=%d page=%d 실패 → 건너뜀 (%d/%d회) | %s",
                        region_1, content_type_id, page,
                        consec_fails, _MAX_CONSEC_FAILS, exc,
                    )
                    if consec_fails >= _MAX_CONSEC_FAILS:
                        logger.error(
                            "[Bulk] 연속 %d회 실패. %s contentType=%d 중단.",
                            _MAX_CONSEC_FAILS, region_1, content_type_id,
                        )
                        break
                    page += 1
                    time.sleep(_RETRY_BASE_DELAY)
                    continue

                # ── 아이템 처리 ───────────────────────────────────────
                for item in items:
                    content_id = str(item.get("contentid", "")).strip()
                    if not content_id:
                        continue

                    if include_detail:
                        try:
                            detail = fetch_detail(content_id)
                        except Exception as exc:
                            logger.warning(
                                "[Bulk] detailCommon2 실패 contentid=%s — overview 없이 진행: %s",
                                content_id, exc,
                            )
                            detail = {}
                        time.sleep(_DETAIL_DELAY)
                    else:
                        detail = {}   # overview 없이 기본 필드만

                    yield _normalize(item, detail, region_1, content_type_id)

                fetched += len(items)

                if not items or fetched >= total:
                    logger.info(
                        "[Bulk] %s contentType=%d 완료 — %d/%d건",
                        region_1, content_type_id, fetched, total,
                    )
                    break

                page += 1
                time.sleep(_INTER_PAGE_DELAY)


def _parse_tourapi_dt(s: str | None) -> datetime | None:
    """TourAPI modifiedtime/createdtime 문자열 → datetime (파싱 실패 시 None)."""
    if not s or len(s) < 14:
        return None
    try:
        return datetime.strptime(s[:14], "%Y%m%d%H%M%S")
    except ValueError:
        return None


def _normalize(item: dict, detail: dict, region_1: str, content_type_id: int) -> dict:
    """TourAPI 원시 응답 → places 테이블 컬럼 매핑."""
    try:
        lat = float(item["mapy"]) if item.get("mapy") else None
    except (ValueError, TypeError):
        lat = None
    try:
        lon = float(item["mapx"]) if item.get("mapx") else None
    except (ValueError, TypeError):
        lon = None

    return {
        "tourapi_content_id":    str(item.get("contentid", "")),
        "name":                  (item.get("title") or "").strip(),
        "category_id":           content_type_id,
        "region_1":              region_1,
        "region_2":              str(item.get("sigungucode", "") or ""),
        "latitude":              lat,
        "longitude":             lon,
        "overview":              (detail.get("overview") or "").strip(),
        "first_image_url":       (item.get("firstimage") or "").strip() or None,
        "first_image_thumb_url": (item.get("firstimage2") or "").strip() or None,
        "tourapi_modified_time": _parse_tourapi_dt(item.get("modifiedtime")),
    }


def fetch_changes(
    content_type_ids: list[int],
    area_codes: list[int],
    stored_mod_times: dict[str, str],
) -> tuple[set[str], list[dict], set[tuple[int, int]]]:
    """
    증분 동기화용 변경 감지.

    모든 페이지를 list-only(detailCommon2 없이)로 읽어:
    - seen_ids      : API에 현재 존재하는 모든 contentid 집합 (soft-delete 비교용)
    - changed       : DB에 없거나 modifiedtime이 바뀐 아이템 목록 (detail 포함 정규화)
    - failed_scopes : 페이지 연속 실패로 중단된 (area_code, content_type_id) 집합

    soft_delete_missing() 호출자는 failed_scopes 가 비어있을 때만 soft delete를 실행해야
    한다. 부분 수집된 scope 의 seen_ids 는 불완전하므로, 그 scope 기준으로 soft delete 를
    실행하면 수집되지 못한 페이지의 항목이 오삭제된다.

    Parameters
    ----------
    stored_mod_times : {contentid: "YYYYMMDDHHMMSS"} — DB에 저장된 최종 수정시각 문자열
    """
    seen_ids: set[str] = set()
    changed: list[dict] = []
    failed_scopes: set[tuple[int, int]] = set()

    for area_code in area_codes:
        region_1 = AREA_NAMES.get(area_code, str(area_code))

        for content_type_id in content_type_ids:
            page = 1
            fetched = 0
            total = None
            total_pages = None
            consec_fails = 0
            scope_failed = False
            scope_changed_start = len(changed)  # 이 scope 시작 시점의 changed 인덱스

            logger.info("[Incremental][List] %s contentType=%d 변경 스캔 시작",
                        region_1, content_type_id)

            while True:
                try:
                    items, total_count = fetch_area_list(
                        content_type_id, area_code, page, _PAGE_SIZE
                    )
                    consec_fails = 0

                    if total is None:
                        total = total_count
                        total_pages = max(1, math.ceil(total / _PAGE_SIZE))
                        logger.info("[Incremental] %s contentType=%d — 총 %d건 / %d 페이지",
                                    region_1, content_type_id, total, total_pages)

                except Exception as exc:
                    consec_fails += 1
                    logger.warning("[Incremental] %s contentType=%d page=%d 실패 (%d/%d) | %s",
                                   region_1, content_type_id, page,
                                   consec_fails, _MAX_CONSEC_FAILS, exc)
                    if consec_fails >= _MAX_CONSEC_FAILS:
                        logger.error(
                            "[Incremental] 연속 %d회 실패. %s contentType=%d 중단 — soft delete 건너뜀.",
                            _MAX_CONSEC_FAILS, region_1, content_type_id,
                        )
                        scope_failed = True
                        break
                    page += 1
                    time.sleep(_RETRY_BASE_DELAY)
                    continue

                for item in items:
                    cid = str(item.get("contentid", "")).strip()
                    if not cid:
                        continue
                    seen_ids.add(cid)

                    api_mod = (item.get("modifiedtime") or "")[:14]
                    db_mod  = stored_mod_times.get(cid, "")

                    if api_mod == db_mod and db_mod:
                        continue  # 변경 없음 — 건너뜀

                    try:
                        detail = fetch_detail(cid)
                    except Exception as exc:
                        logger.warning("[Incremental] detailCommon2 실패 cid=%s — overview 없이 진행: %s",
                                       cid, exc)
                        detail = {}
                    time.sleep(_DETAIL_DELAY)

                    changed.append(_normalize(item, detail, region_1, content_type_id))

                fetched += len(items)
                if not items or fetched >= total:
                    scope_changed = changed[scope_changed_start:]
                    new_cnt     = sum(1 for p in scope_changed
                                      if p["tourapi_content_id"] not in stored_mod_times)
                    updated_cnt = len(scope_changed) - new_cnt
                    logger.info(
                        "[Incremental] %s contentType=%d 완료 — 전체 %d건 / 신규 %d건 / 변경 %d건",
                        region_1, content_type_id, total, new_cnt, updated_cnt,
                    )
                    break

                page += 1
                time.sleep(_INTER_PAGE_DELAY)

            if scope_failed:
                failed_scopes.add((area_code, content_type_id))

    return seen_ids, changed, failed_scopes
