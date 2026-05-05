"""
refetch_missing_overview.py — overview 누락 건만 타겟 재수집

일일 Rate Limit 소진 후 다음날 실행.
places 테이블에서 overview가 비어있는 행만 골라
detailCommon2를 재호출하여 overview를 채운다.
"""

import sys
import time
import logging
import psycopg2
import psycopg2.extras

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("refetch")

import database
import tourapi_fetcher

DETAIL_DELAY = 1.0   # 안전하게 1초 간격


def run():
    conn = database.get_connection()

    # overview 누락 건 조회
    with conn.cursor() as cur:
        cur.execute("""
            SELECT place_id, tourapi_content_id, name
            FROM places
            WHERE (overview IS NULL OR overview = '')
              AND tourapi_content_id IS NOT NULL
            ORDER BY place_id
        """)
        missing = [dict(r) for r in cur.fetchall()]

    log.info("overview 누락 건: %d건", len(missing))
    if not missing:
        log.info("누락 없음 — 종료")
        conn.close()
        return

    ok = fail = 0
    for i, row in enumerate(missing, 1):
        cid  = row["tourapi_content_id"]
        pid  = row["place_id"]
        name = row["name"]
        log.info("[%d/%d] %s (%s) 재수집 중...", i, len(missing), name, cid)

        try:
            detail = tourapi_fetcher.fetch_detail(cid)
            overview = (detail.get("overview") or "").strip()

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE places SET overview=%s, updated_at=NOW() WHERE place_id=%s",
                    (overview, pid)
                )
            conn.commit()

            if overview:
                log.info("  OK  overview=%d자", len(overview))
                ok += 1
            else:
                log.warning("  overview 여전히 없음 (API 미제공)")
                fail += 1

        except Exception as exc:
            log.error("  FAIL — %s", exc)
            fail += 1

        time.sleep(DETAIL_DELAY)

    conn.close()
    log.info("완료 — 성공: %d건 / 실패: %d건", ok, fail)


if __name__ == "__main__":
    run()
