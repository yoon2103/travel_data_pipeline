"""
main.py — AI 여행 데이터 파이프라인 오케스트레이터

실행 모드
---------
  [PoC]
    python main.py --area 1 --type 39 --limit 10

  [Bulk — 2단계 수집 (일일 API 한도 대응)]
    1단계: python main.py --area 1 --type 39 --bulk --no-detail
           → areaBasedList2 목록만 수집 (페이지당 1회 호출, 빠름)
           → 기본 필드(name/좌표/카테고리)만 적재, overview=빈값
    2단계: python main.py --fill-overview --batch 900
           → DB에서 overview 빈 행만 추출해 detailCommon2 호출
           → 하루 최대 --batch 건씩 보충 (기본 900, 일일 한도 고려)

  [Bulk — 전통 방식 (일일 한도 여유 있을 때)]
    python main.py --area 1 --type 39 --bulk

  [AI 미처리 배치]
    python main.py --ai-only --area 1 --type 39 --limit 100
    → TourAPI 호출 없이 DB 미처리 건만 선택해 AI 가공
"""

import argparse
import json
import logging
import sys
import time
from typing import Optional

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import psycopg2

import config               # .env 로드 + 환경변수 검증
import database
import tourapi_fetcher
import ai_processor
from ai_validator import log_validation_errors

# area_code → places.region_1 매핑 (TourAPI areaCode 기준)
# 검증 완료: 실제 DB region_1='서울' (bytes=b'\xec\x84\x9c\xec\x9a\xb8') 일치 확인
_AREA_NAME = {
    1: "서울", 2: "인천", 3: "대전", 4: "대구",
    5: "광주", 6: "부산", 7: "울산", 8: "세종",
    31: "경기", 32: "강원", 33: "충북", 34: "충남",
    35: "경북", 36: "경남", 37: "전북", 38: "전남",
    39: "제주",
}

# ─────────────────────────────────────────────
# 로거 설정
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("pipeline")


# ─────────────────────────────────────────────
# 단계별 실행 함수
# ─────────────────────────────────────────────

def _step_ai(place: dict) -> dict:
    """
    Claude 태그/요약/역할/체류시간/시간대 생성 + 검증 + OpenAI 임베딩 생성.
    키 미설정 시 해당 필드만 None 으로 반환 (파이프라인 중단 없음).
    """
    result = {
        "ai_tags": None, "ai_summary": None, "embedding": None,
        "visit_role": None, "estimated_duration": None,
        "visit_time_slot": None,
        "ai_validation_status": "pending", "ai_validation_errors": [],
    }

    # Claude 태그·요약·역할·체류시간·시간대 (+ AIValidator 검증 포함)
    if config.ANTHROPIC_API_KEY:
        try:
            ai = ai_processor.generate_tags_and_summary(place)
            result.update(ai)
        except Exception as exc:
            log.warning("  [AI-tag]  FAIL — %s", exc)
    else:
        log.debug("  [AI-tag]  SKIP (ANTHROPIC_API_KEY 미설정)")

    # OpenAI 임베딩
    if config.OPENAI_API_KEY:
        try:
            result["embedding"] = ai_processor.generate_embedding(place)
        except Exception as exc:
            log.warning("  [AI-emb]  FAIL — %s", exc)
    else:
        log.debug("  [AI-emb]  SKIP (OPENAI_API_KEY 미설정)")

    return result


def _step_upsert(conn, place: dict, ai: dict) -> Optional[int]:
    """DB Upsert. 성공 시 place_id 반환, 실패 시 None (rollback 포함)."""
    merged = {**place, **ai}
    try:
        place_id = database.upsert_place(conn, merged)
        return place_id
    except psycopg2.Error as e:
        # ── psycopg2 DB 예외: 최대한 상세히 출력 ─────────────────
        diag     = getattr(e, "diag", None)
        primary  = (getattr(diag, "message_primary", None) or "").strip()
        pgerror  = (getattr(e, "pgerror", None) or "").strip()
        log.error(
            "[DB] FAIL  name=%r  category_id=%s  content_id=%s",
            place.get("name"),
            merged.get("category_id"),
            merged.get("tourapi_content_id"),
        )
        if primary:
            log.error("  [DB] diag : %s", primary)
        if pgerror and pgerror != primary:
            log.error("  [DB] pg   : %s", pgerror)
        log.error("  [DB] exc  : %s", e)
        return None
    except Exception as exc:
        log.error(
            "[DB] FAIL (unexpected)  name=%r  content_id=%s — %s",
            place.get("name"),
            place.get("tourapi_content_id"),
            exc,
        )
        return None


# ─────────────────────────────────────────────
# fill-overview 모드 (2단계 overview 보충)
# ─────────────────────────────────────────────

def run_fill_overview(batch_size: int = 900) -> None:
    """
    DB에서 overview가 비어있는 행만 추출 → detailCommon2 재호출 → overview 업데이트.

    Parameters
    ----------
    batch_size : 한 번에 처리할 최대 건수 (일일 API 한도 고려, 기본 900)
    """
    log.info("=" * 64)
    log.info("[fill-overview] 시작 — 최대 %d건 처리", batch_size)

    conn = database.get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT place_id, tourapi_content_id, name
            FROM places
            WHERE (overview IS NULL OR overview = '')
              AND tourapi_content_id IS NOT NULL
            ORDER BY place_id
            LIMIT %s
        """, (batch_size,))
        missing = [dict(r) for r in cur.fetchall()]

    total_missing = len(missing)
    log.info("[fill-overview] overview 누락 건: %d건", total_missing)

    if not missing:
        log.info("[fill-overview] 누락 없음 — 종료")
        conn.close()
        return

    ok = fail = 0
    for i, row in enumerate(missing, 1):
        cid, pid, name = row["tourapi_content_id"], row["place_id"], row["name"]
        log.info("[%d/%d] %s (%s)", i, total_missing, name, cid)

        try:
            detail   = tourapi_fetcher.fetch_detail(cid)
            overview = (detail.get("overview") or "").strip()

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE places SET overview=%s, updated_at=NOW() WHERE place_id=%s",
                    (overview, pid),
                )
            conn.commit()
            database.log_step(conn, pid, "fetch_overview", "success" if overview else "skip",
                              None if overview else "overview empty in API")

            log.info("  OK  overview=%d자", len(overview))
            ok += 1

        except Exception as exc:
            log.error("  FAIL — %s", exc)
            database.log_step(conn, pid, "fetch_overview", "fail", str(exc)[:300])
            fail += 1

        time.sleep(tourapi_fetcher._DETAIL_DELAY)

    conn.close()
    log.info("=" * 64)
    log.info("[fill-overview] 완료 — 성공: %d건 / 실패: %d건", ok, fail)
    log.info("=" * 64)


# ─────────────────────────────────────────────
# fill-images 모드 (대표 이미지 보강)
# ─────────────────────────────────────────────

def run_fill_images(
    area_codes: list[int],
    content_type_ids: list[int],
    batch_size: int = 900,
) -> None:
    """
    DB에서 first_image_url이 NULL인 행만 추출 → detailCommon2 재호출 → 이미지 업데이트.

    기존 AI 가공값·overview 등은 건드리지 않음.
    """
    region_names = [_AREA_NAME[c] for c in area_codes if c in _AREA_NAME]

    log.info("=" * 64)
    log.info("[fill-images] 시작 — 최대 %d건 처리", batch_size)
    log.info("  지역: %s  타입: %s", region_names or "전체", content_type_ids or "전체")
    log.info("=" * 64)

    conn = database.get_connection()

    sql = """
        SELECT place_id, tourapi_content_id, name
        FROM   places
        WHERE  first_image_url IS NULL
          AND  tourapi_content_id IS NOT NULL
    """
    params: list = []
    if region_names:
        sql += " AND region_1 = ANY(%s)"
        params.append(region_names)
    if content_type_ids:
        sql += " AND category_id = ANY(%s)"
        params.append(content_type_ids)
    sql += " ORDER BY place_id LIMIT %s"
    params.append(batch_size)

    with conn.cursor() as cur:
        cur.execute(sql, params)
        missing = [dict(r) for r in cur.fetchall()]

    total = len(missing)
    log.info("[fill-images] 이미지 누락 건: %d건", total)

    if not missing:
        log.info("[fill-images] 누락 없음 — 종료")
        conn.close()
        return

    ok = no_img = fail = 0
    for i, row in enumerate(missing, 1):
        cid  = row["tourapi_content_id"]
        pid  = row["place_id"]
        name = row["name"]
        log.info("[%d/%d] %s (%s)", i, total, name, cid)

        try:
            detail = tourapi_fetcher.fetch_detail(cid)
            img    = (detail.get("firstimage")  or "").strip() or None
            thumb  = (detail.get("firstimage2") or "").strip() or None

            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE places
                          SET first_image_url       = %s,
                              first_image_thumb_url = %s,
                              updated_at            = NOW()
                        WHERE place_id = %s""",
                    (img, thumb, pid),
                )
            conn.commit()

            if img:
                log.info("  OK  img=%s", img[:60])
                ok += 1
            else:
                log.info("  SKIP  API 응답에 이미지 없음")
                no_img += 1

        except Exception as exc:
            log.error("  FAIL — %s", exc)
            fail += 1

        time.sleep(tourapi_fetcher._DETAIL_DELAY)

    conn.close()
    log.info("=" * 64)
    log.info("[fill-images] 완료 — 성공: %d건 / 이미지없음: %d건 / 실패: %d건",
             ok, no_img, fail)
    log.info("=" * 64)


# ─────────────────────────────────────────────
# AI 미처리 배치 모드
# ─────────────────────────────────────────────

def run_ai_only(
    area_codes: list[int],
    content_type_ids: list[int],
    limit: int = 100,
) -> None:
    """
    TourAPI 호출 없이 DB에서 AI 미처리 건만 선택해 AI 가공 후 저장.

    조건: (visit_role IS NULL OR ai_validation_status IN ('pending','failed'))
          AND overview IS NOT NULL AND overview != ''
    """
    region_names = [_AREA_NAME[c] for c in area_codes if c in _AREA_NAME]

    log.info("=" * 64)
    log.info("[ai-only] 시작")
    log.info("  지역    : %s", region_names)
    log.info("  타입    : %s", content_type_ids)
    log.info("  최대건수: %d", limit)
    log.info("  Claude  : %s", "OK" if config.ANTHROPIC_API_KEY else "미설정 → SKIP")
    log.info("=" * 64)

    if not config.ANTHROPIC_API_KEY:
        log.error("[ai-only] ANTHROPIC_API_KEY 미설정 — 종료")
        return

    conn = database.get_connection()

    # ── 대상 선택 ──────────────────────────────────────────────────
    with conn.cursor() as cur:
        cur.execute("""
            SELECT place_id, name, category_id, region_1, region_2, overview
            FROM places
            WHERE (visit_role IS NULL OR ai_validation_status IN ('pending', 'failed'))
              AND overview IS NOT NULL AND overview != ''
              AND category_id = ANY(%(types)s)
              AND region_1    = ANY(%(regions)s)
            ORDER BY place_id ASC
            LIMIT %(limit)s
        """, {
            "types":   content_type_ids,
            "regions": region_names,
            "limit":   limit,
        })
        targets = [dict(r) for r in cur.fetchall()]

    total    = len(targets)
    passed   = 0
    fallback = 0
    failed   = 0
    anomalies = []

    log.info("[ai-only] 대상 %d건 선택", total)

    for i, place in enumerate(targets, 1):
        pid  = place["place_id"]
        name = place["name"]

        try:
            ai = ai_processor.generate_tags_and_summary(place)

            params = {
                "ai_summary":           ai["ai_summary"],
                "ai_tags":              json.dumps(ai["ai_tags"], ensure_ascii=False),
                "visit_role":           ai["visit_role"],
                "estimated_duration":   ai["estimated_duration"],
                "visit_time_slot":      ai["visit_time_slot"],
                "ai_validation_status": ai["ai_validation_status"],
                "ai_validation_errors": json.dumps(ai["ai_validation_errors"], ensure_ascii=False),
                "place_id":             pid,
            }

            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE places SET
                        ai_summary           = %(ai_summary)s,
                        ai_tags              = %(ai_tags)s::jsonb,
                        visit_role           = %(visit_role)s,
                        estimated_duration   = %(estimated_duration)s,
                        visit_time_slot      = %(visit_time_slot)s,
                        ai_validation_status = %(ai_validation_status)s,
                        ai_validation_errors = %(ai_validation_errors)s::jsonb,
                        updated_at           = NOW()
                    WHERE place_id = %(place_id)s
                """, params)
            conn.commit()

            log_validation_errors(conn, pid, ai["ai_validation_errors"], ai)

            status = ai["ai_validation_status"]
            if status == "passed":
                passed += 1
            else:
                fallback += 1
                if len(anomalies) < 5:
                    anomalies.append({
                        "place_id": pid, "name": name,
                        "status":   status,
                        "role":     ai["visit_role"],
                        "duration": ai["estimated_duration"],
                        "slots":    ai["visit_time_slot"],
                        "errors":   ai["ai_validation_errors"],
                    })

            if i % 10 == 0:
                log.info("  %d/%d 처리 중... passed=%d fallback=%d failed=%d",
                         i, total, passed, fallback, failed)

        except Exception as exc:
            failed += 1
            log.error("  [FAIL] %d/%d place_id=%d — %s", i, total, pid, exc)
            if len(anomalies) < 5:
                anomalies.append({
                    "place_id": pid, "name": name,
                    "status":   "failed",
                    "errors":   [str(exc)[:120]],
                })

        time.sleep(0.3)

    conn.close()

    # ── 결과 보고 ──────────────────────────────────────────────────
    log.info("=" * 64)
    log.info("[ai-only] 완료")
    log.info("  총 처리 : %d건", total)
    log.info("  passed  : %d건", passed)
    log.info("  fallback: %d건", fallback)
    log.info("  failed  : %d건", failed)
    log.info("=" * 64)

    if anomalies:
        log.info("[이상 샘플]")
        for a in anomalies:
            log.info("  place_id=%d  name=%s  status=%s  role=%s  dur=%s  slots=%s",
                     a["place_id"], a["name"], a["status"],
                     a.get("role"), a.get("duration"), a.get("slots"))
            log.info("    errors=%s", a["errors"])
    else:
        log.info("[이상 샘플] 없음 (전건 passed)")


# ─────────────────────────────────────────────
# 메인 파이프라인
# ─────────────────────────────────────────────

_BULK_LOG_INTERVAL = 50   # 벌크 모드에서 N건마다 중간 요약 출력


def run_pipeline(
    area_codes: list[int],
    content_type_ids: list[int],
    limit: Optional[int] = None,
    bulk: bool = False,
    no_detail: bool = False,
) -> None:
    """
    Parameters
    ----------
    area_codes        : 수집 지역 코드 목록 (1=서울 … 39=제주)
    content_type_ids  : 콘텐츠 타입 목록 (12=관광지 39=음식점 …)
    limit             : 최대 수집 건수 (bulk=True 이면 무시)
    bulk              : True 이면 totalCount 끝까지 전체 수집
    no_detail         : True 이면 detailCommon2 호출 생략 (목록만, 일일 한도 절약)
    """
    effective_limit = None if bulk else limit

    if no_detail:
        mode_label = "BULK 목록전용(--no-detail)"
    elif bulk:
        mode_label = "BULK 전체수집"
    else:
        mode_label = "일반"

    log.info("=" * 64)
    log.info("파이프라인 시작  [모드: %s]", mode_label)
    log.info("  지역코드    : %s", area_codes)
    log.info("  콘텐츠타입  : %s", content_type_ids)
    log.info("  최대건수    : %s", "전체(bulk)" if bulk else (effective_limit or "무제한"))
    log.info("  detailCommon2 : %s", "SKIP (목록만)" if no_detail else "호출")
    log.info("  Claude API  : %s", "OK" if config.ANTHROPIC_API_KEY else "미설정 → AI 태그 SKIP")
    log.info("  OpenAI API  : %s", "OK" if config.OPENAI_API_KEY  else "미설정 → 임베딩 SKIP")
    log.info("=" * 64)

    log.info("[초기화] DB 연결 중...")
    conn = database.get_connection()
    log.info("[초기화] DB 연결 OK")

    fetched = ai_ok = embed_ok = saved = failed = 0

    try:
        for place in tourapi_fetcher.iter_all_places(
            content_type_ids, area_codes, include_detail=not no_detail
        ):
            fetched += 1

            if effective_limit and fetched > effective_limit:
                log.info("[중단] 지정 한도 %d건 도달.", effective_limit)
                break

            name = place.get("name", "")
            cid  = place.get("tourapi_content_id", "")

            if bulk:
                if fetched % _BULK_LOG_INTERVAL == 0:
                    log.info(
                        "[Bulk 중간요약] 수집 %d건 / 저장 %d건 / 실패 %d건",
                        fetched, saved, failed,
                    )
            else:
                log.info("[%d] %s (%s)  overview=%d자",
                         fetched, name, cid,
                         len(place.get("overview") or ""))

            ai_result = _step_ai(place)
            if ai_result["ai_tags"]:
                ai_ok += 1
            if ai_result["embedding"]:
                embed_ok += 1

            place_id = _step_upsert(conn, place, ai_result)
            if place_id is None:
                failed += 1
                if not bulk:
                    log.error("  [DB] FAIL  %s", name)
                continue

            saved += 1
            if not bulk:
                log.info("  [DB] OK  place_id=%d", place_id)

            database.log_step(conn, place_id, "fetch", "success")
            if ai_result["ai_tags"]:
                database.log_step(conn, place_id, "ai_tag", "success")
            else:
                database.log_step(conn, place_id, "ai_tag", "skip",
                                  "no api key" if not config.ANTHROPIC_API_KEY else "fail")
            if ai_result["embedding"]:
                database.log_step(conn, place_id, "ai_embed", "success")
            else:
                database.log_step(conn, place_id, "ai_embed", "skip",
                                  "no api key" if not config.OPENAI_API_KEY else "fail")

    except KeyboardInterrupt:
        log.warning("[중단] Ctrl+C — 지금까지 수집한 데이터는 DB에 보존됩니다.")

    finally:
        conn.close()

    log.info("=" * 64)
    log.info("파이프라인 완료")
    log.info("  API 수집  : %d건", fetched)
    log.info("  AI 태그   : %d건", ai_ok)
    log.info("  임베딩    : %d건", embed_ok)
    log.info("  DB 저장   : %d건", saved)
    log.info("  실패      : %d건", failed)
    log.info("=" * 64)

    _print_results(min(saved, 10))


# ─────────────────────────────────────────────
# 결과 출력
# ─────────────────────────────────────────────

def _print_results(n: int) -> None:
    """저장된 최근 n건을 터미널 표로 출력."""
    if n == 0:
        return

    conn = database.get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT place_id,
                   name,
                   region_1,
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
                   COALESCE(
                       (ai_tags->>'themes')::TEXT,
                       '(AI 미처리)'
                   ) AS themes,
                   LEFT(COALESCE(ai_summary, overview, ''), 45) AS summary
            FROM places
            ORDER BY place_id DESC
            LIMIT %s
        """, (n,))
        rows = cur.fetchall()
    conn.close()

    sep = "─" * 100
    print()
    print("━" * 100)
    print(f"  적재 결과 - 최근 {n}건")
    print("━" * 100)
    print(f"  {'ID':>5}  {'장소명':<24}  {'지역':<5}  {'분류':<6}  {'AI 테마':<22}  요약")
    print(sep)
    for r in rows:
        themes = (r["themes"] or "").replace('"', "").replace("[", "").replace("]", "")[:20]
        summary = (r["summary"] or "")[:40]
        print(
            f"  {r['place_id']:>5}  {r['name']:<24}  {r['region_1']:<5}  "
            f"{r['category']:<6}  {themes:<22}  {summary}"
        )
    print("━" * 100)
    print()


# ─────────────────────────────────────────────
# 증분 동기화 파이프라인
# ─────────────────────────────────────────────

def run_incremental(
    area_codes: list[int],
    content_type_ids: list[int],
    dry_run: bool = False,
) -> None:
    """
    증분(list-first) 동기화.

    Phase 1  DB 기준 modifiedtime 조회 (비활성 행 포함)
    Phase 2  API 전체 스캔 — 변경·신규 건만 detailCommon2 호출
    Phase 3  변경건 AI 처리 + upsert  (dry_run 시 건너뜀)
    Phase 4  API에서 사라진 건 soft delete  (dry_run 시 목록만 출력)
    """
    region_names = [_AREA_NAME[c] for c in area_codes if c in _AREA_NAME]
    dry_label    = "  [DRY-RUN — 실제 변경 없음]" if dry_run else ""

    log.info("=" * 64)
    log.info("파이프라인 시작  [모드: 증분(incremental)]%s", dry_label)
    log.info("  지역코드    : %s", area_codes)
    log.info("  콘텐츠타입  : %s", content_type_ids)
    log.info("  Claude API  : %s", "OK" if config.ANTHROPIC_API_KEY else "미설정 → AI 태그 SKIP")
    log.info("  OpenAI API  : %s", "OK" if config.OPENAI_API_KEY  else "미설정 → 임베딩 SKIP")
    log.info("=" * 64)

    conn = database.get_connection()

    # ── Phase 1: DB 기준 modifiedtime 조회 ────────────────────────
    log.info("[Phase 1] DB 기준 modifiedtime 조회 중 (비활성 포함)...")
    stored_mod_times = database.get_stored_mod_times(conn, content_type_ids, region_names)
    log.info("  DB 보유 건수: %d건", len(stored_mod_times))

    null_mod_cnt = sum(1 for v in stored_mod_times.values() if not v)
    if null_mod_cnt > 0:
        log.warning(
            "  [주의] tourapi_modified_time 미설정 행 %d건 — "
            "해당 건은 이번 실행에서 전부 detailCommon2 + AI 재호출 발생 "
            "(migration 직후 첫 실행이면 전건이 이에 해당, full 수준 API 비용 예상)",
            null_mod_cnt,
        )

    # ── Phase 2: API 전체 스캔 → 변경·신규 감지 ──────────────────
    log.info("[Phase 2] API 전체 스캔 및 변경 감지 중...")
    seen_ids, changed_items, failed_scopes = tourapi_fetcher.fetch_changes(
        content_type_ids, area_codes, stored_mod_times
    )
    new_cnt     = sum(1 for p in changed_items
                      if p["tourapi_content_id"] not in stored_mod_times)
    updated_cnt = len(changed_items) - new_cnt
    log.info("  API 전체 : %d건  /  신규: %d건  /  변경: %d건",
             len(seen_ids), new_cnt, updated_cnt)
    if failed_scopes:
        for area_code, ctype in sorted(failed_scopes):
            log.warning("  [스캔 실패] area=%d  contentType=%d", area_code, ctype)
        log.warning("  → 실패 scope 존재 — Phase 4 soft delete 전체 건너뜀")

    # ── Phase 3: 변경건 AI 처리 + upsert ─────────────────────────
    ai_ok = embed_ok = saved = failed = 0

    if dry_run:
        log.info("[Phase 3] DRY-RUN — 저장 건너뜀, 대상 목록만 출력")
        for p in changed_items:
            action = "신규" if p["tourapi_content_id"] not in stored_mod_times else "변경"
            log.info("  [DRY] %-4s  %s (%s)",
                     action, p.get("name", ""), p.get("tourapi_content_id", ""))
    else:
        log.info("[Phase 3] 변경건 AI 처리 및 DB 저장 중 (%d건)...", len(changed_items))
        for i, place in enumerate(changed_items, 1):
            name = place.get("name", "")
            cid  = place.get("tourapi_content_id", "")
            log.info("[%d/%d] %s (%s)", i, len(changed_items), name, cid)

            ai_result = _step_ai(place)
            if ai_result["ai_tags"]:
                ai_ok += 1
            if ai_result["embedding"]:
                embed_ok += 1

            place_id = _step_upsert(conn, place, ai_result)
            if place_id is None:
                failed += 1
                continue

            saved += 1
            log.info("  [DB] OK  place_id=%d", place_id)
            database.log_step(conn, place_id, "fetch", "success")
            if ai_result["ai_tags"]:
                database.log_step(conn, place_id, "ai_tag", "success")
            if ai_result["embedding"]:
                database.log_step(conn, place_id, "ai_embed", "success")

    # ── Phase 4: soft delete ──────────────────────────────────────
    # 실패 scope 가 하나라도 있으면 seen_ids 가 불완전하므로 soft delete 를 실행하지 않는다.
    # 실행하면 수집되지 못한 페이지의 항목이 오삭제될 수 있다.
    deleted: list[dict] = []
    if failed_scopes:
        log.warning("[Phase 4] soft delete 건너뜀 — 스캔 실패 scope %d개 존재", len(failed_scopes))
    else:
        log.info("[Phase 4] soft delete 대상 감지 중...")
        deleted = database.soft_delete_missing(
            conn, seen_ids, content_type_ids, region_names, dry_run=dry_run
        )
        if deleted:
            label = "[DRY-SOFT]" if dry_run else "[SOFT-DELETE]"
            for row in deleted:
                log.info("  %s place_id=%d  %s (%s)",
                         label, row["place_id"], row["name"], row["tourapi_content_id"])
        else:
            log.info("  soft delete 대상 없음")

    conn.close()

    # ── 결과 요약 ──────────────────────────────────────────────────
    log.info("=" * 64)
    log.info("증분 파이프라인 완료%s", dry_label)
    log.info("  API 전체   : %d건", len(seen_ids))
    log.info("  신규       : %d건", new_cnt)
    log.info("  변경       : %d건", updated_cnt)
    if not dry_run:
        log.info("  AI 태그    : %d건", ai_ok)
        log.info("  임베딩     : %d건", embed_ok)
        log.info("  DB 저장    : %d건", saved)
        log.info("  실패       : %d건", failed)
    log.info("  soft delete: %d건%s", len(deleted), " (미적용)" if dry_run else "")
    log.info("=" * 64)


# ─────────────────────────────────────────────
# CLI 진입점
# ─────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="AI 여행 데이터 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
실행 예시:
  python main.py --area 1 --type 39 --limit 10              # PoC
  python main.py --area 1 --bulk --no-detail                # 1단계: 목록만 전수 적재
  python main.py --fill-overview --batch 900                # 2단계: overview 보충
  python main.py --area 1 --bulk                            # 전통 방식 (full)
  python main.py --ai-only --area 1 --type 39 --limit 100   # AI 미처리 배치
  python main.py --area 39 --type 12 39 --sync-mode incremental          # 증분 동기화
  python main.py --area 39 --type 12 39 --sync-mode incremental --dry-run # 사전 확인
        """,
    )
    p.add_argument("--area",  type=int, nargs="+", default=[1],
                   help="지역 코드 (기본: 1=서울)")
    p.add_argument("--type",  type=int, nargs="+", default=[39],
                   help="콘텐츠 타입 (기본: 39=음식점)")
    p.add_argument("--limit", type=int, default=None,
                   help="최대 처리 건수 (full 모드 전용)")
    p.add_argument("--bulk",  action="store_true",
                   help="totalCount 끝까지 전체 수집 (full 모드, limit 무시)")
    p.add_argument("--no-detail", action="store_true",
                   help="detailCommon2 생략 — 목록만 수집 (full 모드, 일일 API 한도 절약)")
    p.add_argument("--fill-overview", action="store_true",
                   help="overview 빈 행만 타겟 보충 (2단계 모드)")
    p.add_argument("--fill-images", action="store_true",
                   help="first_image_url 누락 행만 타겟 보충 — 전체 재적재 없이 이미지만 보강")
    p.add_argument("--batch", type=int, default=900,
                   help="--fill-overview / --fill-images 시 한 번에 처리할 최대 건수 (기본: 900)")
    p.add_argument("--ai-only", action="store_true",
                   help="DB 미처리 건만 AI 가공 — TourAPI 호출 없음")
    p.add_argument("--sync-mode", choices=["full", "incremental"], default="full",
                   help="수집 방식: full=전체 재수집(기본) / incremental=변경건만 수집")
    p.add_argument("--dry-run", action="store_true",
                   help="incremental 전용 — 실제 DB 변경 없이 대상 목록만 출력")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.dry_run and args.sync_mode != "incremental":
        log.error(
            "--dry-run은 --sync-mode incremental 전용 옵션입니다. "
            "현재 모드: %s — 종료합니다.",
            args.sync_mode,
        )
        sys.exit(1)

    if args.fill_overview:
        run_fill_overview(batch_size=args.batch)
    elif args.fill_images:
        run_fill_images(
            area_codes=args.area,
            content_type_ids=args.type,
            batch_size=args.batch,
        )
    elif args.ai_only:
        # 기존 동작 그대로 — sync-mode 무관
        run_ai_only(
            area_codes=args.area,
            content_type_ids=args.type,
            limit=args.limit or 100,
        )
    elif args.sync_mode == "incremental":
        run_incremental(
            area_codes=args.area,
            content_type_ids=args.type,
            dry_run=args.dry_run,
        )
    else:
        # full 모드 (기본) — 기존 run_pipeline 그대로
        run_pipeline(
            area_codes=args.area,
            content_type_ids=args.type,
            limit=args.limit,
            bulk=args.bulk,
            no_detail=args.no_detail,
        )
