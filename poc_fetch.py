"""
PoC 수집 스크립트 — 서울 음식점 5건
TourAPI fetch -> DB upsert -> 결과 출력
(API 키 미설정으로 AI 단계는 skip)
"""
import os
import sys
import time
import json
import logging
import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── 설정 ──────────────────────────────────────────────────────────────────────
DB = dict(
    host=os.environ["DB_HOST"],
    port=int(os.environ.get("DB_PORT", 5432)),
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
)
TOURAPI_KEY = os.environ["TOURAPI_SERVICE_KEY"]
BASE_URL    = "http://apis.data.go.kr/B551011/KorService1"
LIMIT       = 5   # PoC: 5건만 수집


# ── TourAPI ────────────────────────────────────────────────────────────────────
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

def _mask(url: str) -> str:
    if "serviceKey=" not in url:
        return url
    before, rest = url.split("serviceKey=", 1)
    k = rest.split("&")[0]
    masked = k[:6] + "***" + k[-4:] if len(k) > 12 else "***"
    return url.replace(k, masked)

def _api_get(endpoint: str, params: dict) -> dict:
    # serviceKey URL 직접 조립 + User-Agent 헤더 추가 + MobileApp=TravelApp
    base = f"{BASE_URL}/{endpoint}?serviceKey={TOURAPI_KEY}"
    p = {"MobileOS": "ETC", "MobileApp": "TravelApp", "_type": "json", **params}
    for attempt in range(3):
        try:
            r = requests.get(base, params=p, headers=_HEADERS, timeout=15)
            if r.status_code != 200:
                log.error("HTTP %s — 실제 요청 URL: %s", r.status_code, _mask(r.url))
            r.raise_for_status()
            data = r.json()
            rc = data["response"]["header"]["resultCode"]
            if rc != "0000":
                raise ValueError(f"TourAPI {rc}: {data['response']['header']['resultMsg']}")
            return data
        except Exception as e:
            if attempt == 2:
                log.error("최종 실패 — 실제 요청 URL: %s", _mask(r.url) if 'r' in dir() else base)
                raise
            log.warning(f"재시도 {attempt+1}/3: {e}")
            time.sleep(2 * (attempt + 1))


def fetch_list(area_code: int, content_type_id: int, num: int) -> list[dict]:
    data = _api_get("areaBasedList1", {
        "numOfRows": num, "pageNo": 1,
        "listYN": "Y", "arrange": "A",
        "contentTypeId": content_type_id,
        "areaCode": area_code,
    })
    items = data["response"]["body"].get("items", {}).get("item", [])
    return items if isinstance(items, list) else [items]


def fetch_detail(content_id: str) -> dict:
    data = _api_get("detailCommon1", {
        "contentId": content_id,
        "defaultYN": "Y", "firstImageYN": "Y",
        "areainfoYN": "Y", "addrinfoYN": "Y",
        "mapinfoYN": "Y", "overviewYN": "Y",
    })
    items = data["response"]["body"].get("items", {}).get("item", [])
    if isinstance(items, dict):
        return items
    return items[0] if items else {}


# ── DB ─────────────────────────────────────────────────────────────────────────
UPSERT_SQL = """
INSERT INTO places
    (name, category_id, region_1, region_2, latitude, longitude,
     overview, tourapi_content_id)
VALUES
    (%(name)s, %(category_id)s, %(region_1)s, %(region_2)s,
     %(latitude)s, %(longitude)s, %(overview)s, %(tourapi_content_id)s)
ON CONFLICT (tourapi_content_id)
    WHERE tourapi_content_id IS NOT NULL
DO UPDATE SET
    name        = EXCLUDED.name,
    overview    = EXCLUDED.overview,
    updated_at  = NOW()
RETURNING place_id
"""

LOG_SQL = """
INSERT INTO ai_processing_log (target_table, target_id, step, status, message)
VALUES (%(target_table)s, %(target_id)s, %(step)s, %(status)s, %(message)s)
"""

def upsert(cur, row: dict) -> int:
    cur.execute(UPSERT_SQL, row)
    return cur.fetchone()[0]

def write_log(cur, place_id: int, step: str, status: str, msg: str = None):
    cur.execute(LOG_SQL, dict(target_table="places", target_id=place_id,
                              step=step, status=status, message=msg))


# ── 결과 출력 ──────────────────────────────────────────────────────────────────
RESULT_SQL = """
SELECT
    place_id,
    name,
    region_1 || ' ' || COALESCE(region_2,'') AS region,
    category_id,
    COALESCE(ai_tags::text, '(미처리)') AS ai_tags,
    LEFT(COALESCE(overview,''), 60) || '...' AS overview_snippet,
    created_at::text AS created_at
FROM places
ORDER BY place_id DESC
LIMIT %s
"""

def print_results(cur, n: int):
    cur.execute(RESULT_SQL, (n,))
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]

    sep = "─" * 110
    print(f"\n{'━'*110}")
    print(f"  ✅  places 테이블 적재 결과 — 최신 {n}건")
    print(f"{'━'*110}")
    print(f"  {'place_id':<10}{'name':<24}{'region':<18}{'cat':<6}{'ai_tags':<16}overview")
    print(sep)
    for r in rows:
        print(f"  {str(r[0]):<10}{str(r[1]):<24}{str(r[2]):<18}"
              f"{str(r[3]):<6}{str(r[4]):<16}{r[5]}")
    print(f"{'━'*110}\n")


# ── 메인 ───────────────────────────────────────────────────────────────────────
def main():
    log.info("=== PoC 파이프라인 시작 (서울 음식점 %d건) ===", LIMIT)

    # 1. TourAPI 수집
    log.info("Step 1: TourAPI 수집 중 (areaCode=1, contentTypeId=39)...")
    raw_items = fetch_list(area_code=1, content_type_id=39, num=LIMIT)[:LIMIT]
    log.info("  목록 %d건 수신", len(raw_items))

    places = []
    for item in raw_items:
        cid = str(item.get("contentid", ""))
        try:
            detail = fetch_detail(cid)
        except Exception as e:
            log.warning("  detailCommon 실패 contentid=%s: %s", cid, e)
            detail = {}

        try:
            lat = float(item["mapy"]) if item.get("mapy") else None
            lon = float(item["mapx"]) if item.get("mapx") else None
        except (ValueError, TypeError):
            lat = lon = None

        places.append({
            "tourapi_content_id": cid,
            "name":               (item.get("title") or "").strip(),
            "category_id":        39,
            "region_1":           "서울",
            "region_2":           str(item.get("sigungucode", "") or ""),
            "latitude":           lat,
            "longitude":          lon,
            "overview":           (detail.get("overview") or "").strip(),
        })
        log.info("  수집 완료: %s (%s)", item.get("title"), cid)
        time.sleep(0.1)

    # 2. DB Upsert
    log.info("Step 2: DB 적재 중...")
    conn = psycopg2.connect(**DB, cursor_factory=psycopg2.extras.DictCursor)
    try:
        with conn.cursor() as cur:
            for p in places:
                place_id = upsert(cur, p)
                write_log(cur, place_id, "fetch", "success")
                write_log(cur, place_id, "ai_process", "skip",
                          "API key not configured")
                log.info("  DB 저장 OK — place_id=%d  %s", place_id, p["name"])
        conn.commit()

        # 3. 결과 조회
        log.info("Step 3: 결과 조회...")
        with conn.cursor() as cur:
            print_results(cur, LIMIT)
    finally:
        conn.close()

    log.info("=== PoC 완료 ===")


if __name__ == "__main__":
    main()
