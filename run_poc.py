"""
PoC 러너 — 서울(1) 음식점(39) 5건 수집 → AI 가공(키 있을 때만) → DB 적재 → 결과 출력
"""
import json
import logging
import sys

import psycopg2
import psycopg2.extras

import config
import db_client
import tourapi_fetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("poc")

POC_LIMIT = 5
AREA_CODE = 1       # 서울
CONTENT_TYPE = 39   # 음식점


def _try_ai(place_data: dict) -> tuple[dict | None, str | None]:
    """AI 태깅·요약 시도. 키 없으면 None 반환."""
    try:
        import ai_processor
        tags, summary = ai_processor.generate_tags_and_summary(place_data)
        return tags, summary
    except RuntimeError as e:
        logger.warning(f"AI skip: {e}")
        return None, None
    except Exception as e:
        logger.error(f"AI error: {e}")
        return None, None


def run():
    # ── DB 연결 ──────────────────────────────────────────────────
    logger.info("DB 연결 중...")
    conn = db_client.get_connection()
    logger.info("DB 연결 OK")

    collected = []

    # ── 수집 ─────────────────────────────────────────────────────
    logger.info(f"TourAPI 수집 시작 — 서울(1) 음식점(39) 최대 {POC_LIMIT}건")
    for place_data in tourapi_fetcher.iter_all_places([CONTENT_TYPE], [AREA_CODE]):
        if len(collected) >= POC_LIMIT:
            break

        name = place_data.get("name", "")
        cid  = place_data.get("tourapi_content_id", "")

        # Fetch → DB upsert
        try:
            place_id = db_client.upsert_place(conn, place_data)
            db_client.log_processing(conn, "places", place_id, "fetch", "success")
            logger.info(f"[{len(collected)+1}] fetch OK  id={place_id}  {name}  ({cid})")
        except Exception as e:
            logger.error(f"upsert 실패 {name}: {e}")
            continue

        # AI 태깅·요약 (선택)
        if place_data.get("overview"):
            ai_tags, ai_summary = _try_ai(place_data)
            if ai_tags is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE places SET ai_tags=%s, ai_summary=%s WHERE place_id=%s",
                            (psycopg2.extras.Json(ai_tags), ai_summary, place_id),
                        )
                    conn.commit()
                    db_client.log_processing(conn, "places", place_id, "ai_process", "success")
                    logger.info(f"    AI OK  tags={list(ai_tags.keys())}")
                except Exception as e:
                    logger.error(f"    AI 저장 실패: {e}")
            else:
                db_client.log_processing(conn, "places", place_id, "ai_process", "skip", "no api key")
        else:
            db_client.log_processing(conn, "places", place_id, "ai_process", "skip", "no overview")

        collected.append(place_id)

    conn.close()
    logger.info(f"수집 완료 — {len(collected)}건 적재")

    # ── 결과 출력 ─────────────────────────────────────────────────
    if not collected:
        logger.error("적재된 데이터가 없습니다.")
        return

    conn2 = db_client.get_connection()
    with conn2.cursor() as cur:
        cur.execute(
            """
            SELECT place_id, name,
                   CASE category_id
                       WHEN 12 THEN '관광지'
                       WHEN 14 THEN '문화시설'
                       WHEN 15 THEN '축제행사'
                       WHEN 28 THEN '레포츠'
                       WHEN 32 THEN '숙박'
                       WHEN 38 THEN '쇼핑'
                       WHEN 39 THEN '음식점'
                       ELSE category_id::TEXT
                   END AS category,
                   ai_tags
            FROM places
            WHERE place_id = ANY(%s)
            ORDER BY place_id
            """,
            (collected,),
        )
        rows = cur.fetchall()
    conn2.close()

    # 표 출력
    print()
    print("=" * 80)
    print(f"{'ID':>6}  {'장소명':<28}  {'카테고리':<8}  AI 태그")
    print("-" * 80)
    for r in rows:
        pid, name, cat, tags = r["place_id"], r["name"], r["category"], r["ai_tags"]
        tag_str = ""
        if tags:
            themes = tags.get("themes", [])
            mood   = tags.get("mood", [])
            tag_str = ", ".join(themes + mood)
        print(f"{pid:>6}  {name:<28}  {cat:<8}  {tag_str or '(AI 키 미설정)'}")
    print("=" * 80)
    print()

    ai_done = sum(1 for r in rows if r["ai_tags"])
    print(f"결과: {len(rows)}건 적재  |  AI 태깅 완료: {ai_done}건")
    if not config.ANTHROPIC_API_KEY:
        print()
        print("[!] ANTHROPIC_API_KEY 미설정 — .env 에 키를 추가하면 AI 태깅이 활성화됩니다.")
    if not config.OPENAI_API_KEY:
        print("[!] OPENAI_API_KEY 미설정 — .env 에 키를 추가하면 벡터 임베딩이 활성화됩니다.")


if __name__ == "__main__":
    run()
