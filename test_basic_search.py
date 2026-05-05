"""
test_basic_search.py — 거리 기반 검색 로직 검증 스크립트
Haversine 공식을 SQL에 직접 적용하여 반경 N km 이내 장소를 거리순 조회.
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import database

# ─────────────────────────────────────────────
# Haversine SQL 기반 거리 검색
# ─────────────────────────────────────────────

_SEARCH_SQL = """
SELECT
    place_id,
    name,
    CASE category_id
        WHEN 12 THEN '관광지'
        WHEN 14 THEN '문화시설'
        WHEN 15 THEN '축제'
        WHEN 28 THEN '레포츠'
        WHEN 32 THEN '숙박'
        WHEN 38 THEN '쇼핑'
        WHEN 39 THEN '음식점'
        ELSE category_id::TEXT
    END AS category,
    region_1,
    region_2,
    latitude,
    longitude,
    ai_summary,
    embedding,
    -- Haversine 공식 (단위: km)
    6371.0 * 2 * ASIN(SQRT(
        POWER(SIN(RADIANS(latitude  - %(lat)s) / 2), 2) +
        COS(RADIANS(%(lat)s)) * COS(RADIANS(latitude)) *
        POWER(SIN(RADIANS(longitude - %(lng)s) / 2), 2)
    )) AS distance_km
FROM places
WHERE is_active = TRUE
  AND latitude  IS NOT NULL
  AND longitude IS NOT NULL
  AND 6371.0 * 2 * ASIN(SQRT(
        POWER(SIN(RADIANS(latitude  - %(lat)s) / 2), 2) +
        COS(RADIANS(%(lat)s)) * COS(RADIANS(latitude)) *
        POWER(SIN(RADIANS(longitude - %(lng)s) / 2), 2)
      )) <= %(radius_km)s
ORDER BY distance_km ASC
LIMIT %(limit)s
"""


def search_by_distance(
    conn,
    lat: float,
    lng: float,
    radius_km: float = 10.0,
    limit: int = 10,
) -> list[dict]:
    """
    기준 좌표로부터 반경 radius_km 이내 장소를 거리 오름차순으로 반환.

    Parameters
    ----------
    lat, lng   : 기준 위경도
    radius_km  : 검색 반경 (km)
    limit      : 최대 반환 건수
    """
    with conn.cursor() as cur:
        cur.execute(_SEARCH_SQL, {"lat": lat, "lng": lng,
                                  "radius_km": radius_km, "limit": limit})
        return [dict(r) for r in cur.fetchall()]


# ─────────────────────────────────────────────
# 결과 출력
# ─────────────────────────────────────────────

def _print_results(rows: list[dict], lat: float, lng: float,
                   radius_km: float) -> None:
    BORDER = "━" * 92
    SEP    = "─" * 92

    print()
    print(BORDER)
    print(f"  거리 기반 검색 결과")
    print(f"  기준점: 위도 {lat}, 경도 {lng}  |  반경: {radius_km} km  |  결과: {len(rows)}건")
    print(BORDER)

    if not rows:
        print("  검색 결과 없음 — 반경을 넓히거나 데이터를 더 수집하세요.")
        print(BORDER)
        return

    print(f"  {'#':>3}  {'장소명':<26}  {'분류':<6}  {'지역':<5}  "
          f"{'거리(km)':>9}  {'ai_summary':^10}  {'embedding':^10}")
    print(SEP)

    for i, r in enumerate(rows, 1):
        ai_status  = "None ⚠" if r["ai_summary"] is None else "OK"
        emb_status = "None ⚠" if r["embedding"]  is None else "OK"
        dist       = f"{r['distance_km']:.2f}"

        print(
            f"  {i:>3}  {r['name']:<26}  {r['category']:<6}  "
            f"{r['region_1']:<5}  {dist:>9}  "
            f"{ai_status:^10}  {emb_status:^10}"
        )

    print(BORDER)
    print("  * ai_summary / embedding 이 None 인 것은 의도된 상태입니다.")
    print("    → .env 에 ANTHROPIC_API_KEY / OPENAI_API_KEY 추가 후 main.py 재실행 시 채워집니다.")
    print(BORDER)
    print()


# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # 기준점: 서울 강남구 (가나돈까스의집·가담과 인접)
    REF_LAT   = 37.5172
    REF_LNG   = 127.0473
    RADIUS_KM = 10.0
    LIMIT     = 5

    print(f"\n[검색 조건] 위도={REF_LAT}, 경도={REF_LNG}, "
          f"반경={RADIUS_KM}km, 최대={LIMIT}건")

    conn = database.get_connection()
    try:
        rows = search_by_distance(conn, REF_LAT, REF_LNG, RADIUS_KM, LIMIT)
    finally:
        conn.close()

    _print_results(rows, REF_LAT, REF_LNG, RADIUS_KM)
