#!/usr/bin/env python3
"""
refetch_coord_outliers.py — 좌표 이상치 49건 TourAPI 단건 재조회 배치

detailCommon2 + mapinfoYN=Y 로 좌표를 재조회한다.

분기 규칙:
  - 한국 범위(lat 33~38.7 / lon 124.5~131.9) → UPDATE
  - 클러스터 동일(lat≈19.694/lon≈117.992) → skip (API 원본 오류 지속)
  - NULL / 0 / 범위 밖 기타               → skip (API 원본 미제공 또는 오류)
  - API 호출 실패                         → skip (API 오류)

UPDATE 안전장치:
  WHERE place_id = %(pid)s
    AND (latitude NOT BETWEEN 33.0 AND 38.7
         OR longitude NOT BETWEEN 124.5 AND 131.9
         OR latitude IS NULL OR longitude IS NULL)
  → 이미 보정된 행은 재실행 시 자동 skip

실행:
  python refetch_coord_outliers.py --dry-run
  python refetch_coord_outliers.py
"""

import argparse
import sys
import time

import psycopg2
import psycopg2.extras

import config
from tourapi_fetcher import _get

KR_LAT  = (33.0, 38.7)
KR_LON  = (124.5, 131.9)
GA_LAT  = (19.693, 19.695)
GA_LON  = (117.991, 117.993)
DELAY   = 0.5   # API 호출 간 딜레이(초) — 429 방지


# ── 유틸 ──────────────────────────────────────────────────────────

def is_valid_kr(lat, lon) -> bool:
    if lat is None or lon is None:
        return False
    return KR_LAT[0] <= lat <= KR_LAT[1] and KR_LON[0] <= lon <= KR_LON[1]


def classify_new_coord(lat, lon) -> str:
    """분기 규칙에 따라 skip 사유를 반환. 정상이면 'ok'."""
    if is_valid_kr(lat, lon):
        return "ok"
    if lat is None or lon is None:
        return "API 원본 미제공 (NULL)"
    if lat == 0.0 and lon == 0.0:
        return "API 원본 미제공 (0/0)"
    if (GA_LAT[0] <= lat <= GA_LAT[1]) and (GA_LON[0] <= lon <= GA_LON[1]):
        return "API 원본 오류 지속 — 클러스터 동일"
    return "API 원본 오류 지속 — 범위 외"


def fetch_coords(content_id: str) -> tuple[float | None, float | None]:
    """detailCommon2 + mapinfoYN=Y 로 단건 좌표 재조회."""
    data = _get("detailCommon2", {
        "contentId": content_id,
        "mapinfoYN": "Y",
        "defaultYN": "Y",
    })
    raw = data["response"]["body"].get("items") or {}
    items = raw.get("item") or []
    if isinstance(items, dict):
        items = [items]
    if not items:
        return None, None
    item = items[0]
    try:
        lat = float(item["mapy"]) if item.get("mapy") else None
    except (ValueError, TypeError):
        lat = None
    try:
        lon = float(item["mapx"]) if item.get("mapx") else None
    except (ValueError, TypeError):
        lon = None
    return lat, lon


def get_outliers(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT place_id, tourapi_content_id, category_id, name,
                   latitude, longitude
            FROM   places
            WHERE  is_active IS TRUE
              AND (
                   (latitude  BETWEEN %s AND %s AND longitude BETWEEN %s AND %s)
                OR  latitude  < %s OR latitude  > %s
                OR  longitude < %s OR longitude > %s
                OR  latitude  IS NULL
                OR  longitude IS NULL
              )
            ORDER BY place_id
        """, (*GA_LAT, *GA_LON, *KR_LAT, *KR_LON))
        return [dict(r) for r in cur.fetchall()]


# ── 메인 ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="좌표 이상치 TourAPI 단건 재조회 배치")
    parser.add_argument("--dry-run", action="store_true",
                        help="변경 없이 결과만 출력")
    args = parser.parse_args()
    dry = args.dry_run
    label = "[DRY-RUN]" if dry else "[APPLY]"

    conn = psycopg2.connect(
        host=config.DB_HOST, port=config.DB_PORT,
        dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

    rows = get_outliers(conn)
    total = len(rows)

    print(f"\n{'=' * 60}")
    print(f"  coord outlier refetch  {label}")
    print(f"{'=' * 60}")
    print(f"\n{label} 재조회 대상: {total}건\n")

    updated = []   # 정상 좌표 복구 → UPDATE
    skipped = []   # API 원본 오류/미제공 지속 → skip
    errors  = []   # API 호출 실패

    for i, r in enumerate(rows, 1):
        cid = r["tourapi_content_id"]
        pid = r["place_id"]
        print(f"  [{i:>2}/{total}] place_id={pid:<6} cid={cid}  {str(r['name'])[:24]}", end="  ")

        if not cid:
            reason = "content_id 없음"
            skipped.append({**r, "new_lat": None, "new_lon": None, "reason": reason})
            print(f"→ skip ({reason})")
            continue

        try:
            new_lat, new_lon = fetch_coords(cid)
        except Exception as exc:
            reason = f"API 오류: {exc}"
            errors.append({**r, "reason": reason})
            print(f"→ ERROR ({exc})")
            time.sleep(DELAY)
            continue

        verdict = classify_new_coord(new_lat, new_lon)

        if verdict == "ok":
            updated.append({**r, "new_lat": new_lat, "new_lon": new_lon})
            print(f"→ UPDATE  ({r['latitude']},{r['longitude']}) → ({new_lat},{new_lon})")
            if not dry:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE places
                               SET latitude   = %(lat)s,
                                   longitude  = %(lon)s,
                                   updated_at = NOW()
                             WHERE place_id   = %(pid)s
                               AND (
                                    latitude  NOT BETWEEN 33.0 AND 38.7
                                 OR longitude NOT BETWEEN 124.5 AND 131.9
                                 OR latitude  IS NULL
                                 OR longitude IS NULL
                               )
                        """, {"lat": new_lat, "lon": new_lon, "pid": pid})
                    conn.commit()
                except Exception as exc:
                    conn.rollback()
                    print(f"    FAIL DB UPDATE — {exc}", file=sys.stderr)
        else:
            skipped.append({**r, "new_lat": new_lat, "new_lon": new_lon, "reason": verdict})
            print(f"→ skip ({verdict})")

        time.sleep(DELAY)

    # ── 결과 요약 ────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  결과 요약  {label}")
    print(f"{'=' * 60}")
    print(f"  재조회 총 대상  : {total:>4}건")
    print(f"  UPDATE 대상     : {len(updated):>4}건  (정상 좌표 복구)")
    print(f"  skip            : {len(skipped):>4}건  (API 원본 오류/미제공 지속)")
    print(f"  API 오류        : {len(errors):>4}건")

    if skipped:
        from collections import Counter
        reason_dist = Counter(e["reason"] for e in skipped)
        print(f"\n  [skip 사유별 분포]")
        for reason, cnt in reason_dist.most_common():
            print(f"    {reason:<42}  {cnt:>3}건")

    if errors:
        print(f"\n  [API 오류 목록]")
        for e in errors:
            print(f"    place_id={e['place_id']:>6}  {e['reason'][:60]}")

    if dry:
        print(f"\n{label} 완료 — 실제 변경 없음")
    else:
        print(f"\n{label} 완료")

    conn.close()


if __name__ == "__main__":
    main()
