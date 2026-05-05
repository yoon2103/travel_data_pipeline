#!/usr/bin/env python3
"""
batch_rules.py — 규칙 기반 visit_role / visit_time_slot / estimated_duration 배치 가공

대상: category_id IN (12, 14, 39), visit_role IS NULL 인 행만 처리
원칙: 이미 가공된 행(visit_role IS NOT NULL) 보호
      원본 컬럼(name, overview 등) 수정 없음

실행:
  python batch_rules.py --dry-run              # 변경 없이 결과 미리보기
  python batch_rules.py --area 1 --dry-run     # 서울만 preview
  python batch_rules.py --area 1 --limit 50   # 서울 50건 적용
  python batch_rules.py --area 1              # 서울 전체 적용
  python batch_rules.py                       # 전 지역 전체 적용

가공 순서 규칙:
  1. visit_role 결정
  2. visit_time_slot 결정  (SLOT_BY_ROLE[role] 기반)
  3. estimated_duration 계산  (DURATION_RULES + DURATION_CLAMP, role 기반)
  duration은 visit_role 기반으로 계산한다.
  role이 잘못된 상태에서 duration을 단독 보정하면 안 된다.

주의:
  visit_role 허용값: spot / culture / meal / cafe
  cat14는 반드시 'culture', cat39는 'meal' 또는 'cafe'만 허용
"""

import argparse
import io
import logging
import sys

import psycopg2
import psycopg2.extras

import config  # .env 로드

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("batch_rules.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("batch_rules")


# ─────────────────────────────────────────────────────────────────────────────
# 규칙 정의
# ─────────────────────────────────────────────────────────────────────────────

TARGET_CATEGORIES = [12, 14, 39]

# cat39 cafe 판정 — name 또는 overview에 하나라도 포함되면 cafe
CAFE_KEYWORDS = [
    "카페", "커피", "디저트", "베이커리", "크레페", "빙수",
    "아이스크림", "티하우스", "브런치카페", "브런치 카페",
]

# indoor_outdoor 분류 키워드 — 우선순위: mixed > indoor > outdoor > category 기본값
MIXED_KEYWORDS = [
    "복합문화공간", "테마파크", "놀이공원", "리조트", "워터파크",
]

# 전 카테고리 공통 indoor 키워드
INDOOR_KEYWORDS_COMMON = [
    "박물관", "미술관", "갤러리", "공연장", "극장", "스파", "찜질", "수족관", "실내",
]

# cat14(문화시설) 전용 indoor 키워드
# cat12/cat39에 적용하면 야외 장소 오분류 증가 — cat14에만 적용
INDOOR_KEYWORDS_CAT14 = [
    "기념관", "과학관", "도서관", "전시관", "문학관", "홍보관",
]

# 하위 호환용 통합 참조 (외부에서 INDOOR_KEYWORDS를 직접 참조하는 코드용)
INDOOR_KEYWORDS = INDOOR_KEYWORDS_COMMON

# 규칙 B: OUTDOOR_KEYWORDS 확장 — 사찰/자연 장소 outdoor 정확도 향상
OUTDOOR_KEYWORDS = [
    "공원", "숲", "등산", "계곡", "트레킹", "해수욕장", "해변", "야외",
    "자연휴양림", "수목원", "산책로", "둘레길", "사찰", "암자", "사원", "산성", "고분",
]

# indoor_outdoor category 기본값 (키워드 미매치 시 적용)
DEFAULT_INDOOR_OUTDOOR: dict[int, str] = {12: "outdoor", 14: "indoor", 39: "indoor"}

# cat39 전용: 음식점 자체가 야외임을 직접 서술하는 강한 키워드만 outdoor 허용
# 공원·숲·해변 등 위치 맥락 키워드는 indoor default 유지
STRONG_OUTDOOR_KEYWORDS: list[str] = ["야외", "해수욕장"]

# duration 보정 규칙: 우선순위 순 (첫 번째 매치 적용, 이후 건너뜀)
DURATION_RULES: dict[int, list[tuple[list[str], int]]] = {
    12: [
        (["스파", "찜질", "온천"],                                        180),
        (["궁", "경복", "창덕", "덕수", "경희궁", "창경궁", "궁궐"],       120),
        (["해수욕장", "해변", "바다", "섬"],                               120),
        (["공원", "숲", "등산", "계곡", "트레킹", "생태"],                   90),
        (["거리", "골목", "마을", "타운"],                                   60),
        (["전망대", "타워", "전망"],                                         60),
    ],
    14: [
        (["공연장", "극장", "오페라", "콘서트홀", "아트센터"],               120),
        (["박물관", "미술관"],                                               90),
        (["갤러리"],                                                         45),
        (["도서관", "문화원", "기념관", "전시관", "사당"],                    60),
    ],
    39: [
        (["뷔페", "코스", "오마카세", "파인다이닝"],                          90),
        (["고기", "갈비", "삼겹살", "소고기", "양고기", "돼지갈비"],          90),
        (["카페", "커피", "디저트", "베이커리", "크레페", "빙수",
          "아이스크림", "티하우스", "브런치"],                                40),
        (["분식", "김밥", "떡볶이", "라면", "면", "우동", "국수", "냉면"],    35),
    ],
}

# visit_role 기본값 (cat39는 classify_place에서 동적 결정)
# 주의: 'culture'는 ai_validator.ALLOWED_ROLES 미포함 — AI 재처리 시 'spot'으로 덮어써질 수 있음
#       나중에 AI 배치 전 ALLOWED_ROLES에 'culture' 추가 여부를 결정해야 함
DEFAULT_ROLE: dict[int, str] = {12: "spot", 14: "culture", 39: "meal"}

# estimated_duration 기본값 (category_id별)
DEFAULT_DURATION: dict[int, int] = {12: 90, 14: 75, 39: 60}

# SOT clamp 기준: cat12=60~120 / cat14=45~100 / cat39=40~90
DURATION_CLAMP: dict[int, tuple[int, int]] = {12: (60, 120), 14: (45, 100), 39: (40, 90)}

# visit_time_slot 기본값 (role별)
SLOT_BY_ROLE: dict[str, list[str]] = {
    "spot":    ["morning", "afternoon"],
    "culture": ["morning", "afternoon"],
    "meal":    ["lunch", "dinner"],
    "cafe":    ["morning", "afternoon"],
}


# ─────────────────────────────────────────────────────────────────────────────
# 분류 로직
# ─────────────────────────────────────────────────────────────────────────────

def _contains(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def classify_place(name: str, overview: str | None, category_id: int) -> dict:
    """
    규칙 기반으로 visit_role / estimated_duration / visit_time_slot / indoor_outdoor 결정.

    - overview 없으면 name 기준만으로 적용
    - 반환 키: visit_role, estimated_duration, visit_time_slot, indoor_outdoor
    """
    text = f"{name} {overview or ''}"

    # ── visit_role ────────────────────────────────────────────────────
    if category_id == 39 and _contains(text, CAFE_KEYWORDS):
        role = "cafe"
    else:
        role = DEFAULT_ROLE.get(category_id, "spot")

    # ── estimated_duration ────────────────────────────────────────────
    duration = DEFAULT_DURATION.get(category_id, 60)
    for keywords, dur in DURATION_RULES.get(category_id, []):
        if _contains(text, keywords):
            duration = dur
            break
    if category_id in DURATION_CLAMP:
        lo, hi = DURATION_CLAMP[category_id]
        duration = max(lo, min(hi, duration))

    # ── visit_time_slot ───────────────────────────────────────────────
    time_slot = SLOT_BY_ROLE.get(role, ["morning", "afternoon"])

    # ── indoor_outdoor ────────────────────────────────────────────────
    # cat14 전용 indoor 키워드를 통합 (cat14에서만 확장 적용)
    indoor_kw = (
        INDOOR_KEYWORDS_COMMON + INDOOR_KEYWORDS_CAT14
        if category_id == 14
        else INDOOR_KEYWORDS_COMMON
    )

    if _contains(text, MIXED_KEYWORDS):
        io_val = "mixed"
    elif category_id != 39 and _contains(text, OUTDOOR_KEYWORDS):
        # 규칙 B: 야외 성격 키워드 우선 판정 (INDOOR_KEYWORDS보다 먼저)
        # 사찰, 공원, 산책로 등 "야외" 단어 없이도 야외 장소를 outdoor로 판정
        # cat39는 STRONG_OUTDOOR 로직으로만 outdoor 허용 — 여기서 제외
        io_val = "outdoor"
    elif "야외" in text:
        # 규칙 A: "야외" 단어가 있으면 outdoor (cat39 포함 전 카테고리)
        io_val = "outdoor"
    elif _contains(text, indoor_kw):
        io_val = "indoor"
    elif category_id == 39:
        # cat39: "야외" 없고 INDOOR 미매치 → "해수욕장"만 outdoor 허용
        io_val = "outdoor" if "해수욕장" in text else DEFAULT_INDOOR_OUTDOOR.get(category_id)
    else:
        io_val = DEFAULT_INDOOR_OUTDOOR.get(category_id)

    return {
        "visit_role":         role,
        "estimated_duration": duration,
        "visit_time_slot":    time_slot,
        "indoor_outdoor":     io_val,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 배치 실행
# ─────────────────────────────────────────────────────────────────────────────

_AREA_NAME: dict[int, str] = {
    1: "서울", 2: "인천", 3: "대전",  4: "대구",
    5: "광주", 6: "부산", 7: "울산",  8: "세종",
    31: "경기", 32: "강원", 33: "충북", 34: "충남",
    35: "경북", 36: "경남", 37: "전북", 38: "전남",
    39: "제주",
}

_LOG_INTERVAL = 500


def run_batch(
    dry_run: bool = False,
    area_codes: list[int] | None = None,
    type_ids: list[int] | None = None,
    limit: int | None = None,
) -> None:
    region_names = [_AREA_NAME[c] for c in (area_codes or []) if c in _AREA_NAME]
    active_cats  = [c for c in (type_ids or TARGET_CATEGORIES) if c in TARGET_CATEGORIES]
    dry_label    = "  [DRY-RUN — 변경 없음]" if dry_run else ""

    log.info("=" * 64)
    log.info("[batch_rules] 시작%s", dry_label)
    log.info("  대상 카테고리 : %s", active_cats)
    log.info("  지역 필터     : %s", region_names or "전체")
    log.info("  최대 건수     : %s", limit or "전체")
    log.info("=" * 64)

    conn = psycopg2.connect(
        host=config.DB_HOST, port=config.DB_PORT,
        dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

    # ── 대상 조회 ────────────────────────────────────────────────────
    params: dict = {"cats": active_cats}
    if region_names:
        params["regions"] = region_names

    sql = """
        SELECT place_id, name, overview, category_id, region_1
        FROM   places
        WHERE  category_id = ANY(%(cats)s)
          AND  visit_role IS NULL
          AND  is_active  = TRUE
    """
    if region_names:
        sql += "  AND  region_1 = ANY(%(regions)s)\n"
    sql += "ORDER BY category_id, place_id"
    if limit:
        sql += "\nLIMIT %(limit)s"
        params["limit"] = limit

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]

    total = len(rows)
    log.info("[batch_rules] 처리 대상: %d건", total)

    if total == 0:
        log.info("[batch_rules] 처리 대상 없음 (이미 전부 가공되었거나 조건 없음) — 종료")
        conn.close()
        return

    # ── 분류 및 업데이트 ─────────────────────────────────────────────
    role_stats: dict[str, int] = {}
    cat_stats:  dict[int, int] = {c: 0 for c in active_cats}
    ok = fail = 0

    for i, row in enumerate(rows, 1):
        pid      = row["place_id"]
        name     = row["name"]
        overview = row["overview"]
        cat_id   = row["category_id"]

        result   = classify_place(name, overview, cat_id)
        role     = result["visit_role"]
        duration = result["estimated_duration"]
        slots    = result["visit_time_slot"]
        io_val   = result["indoor_outdoor"]

        role_stats[role] = role_stats.get(role, 0) + 1
        cat_stats[cat_id] = cat_stats.get(cat_id, 0) + 1

        # dry-run 또는 처음 10건은 항상 출력
        if dry_run or i <= 10:
            log.info(
                "  [%d/%d] cat=%d  %-24s → role=%-7s  dur=%3d  io=%-7s  slot=%s",
                i, total, cat_id, name[:24], role, duration, io_val, slots,
            )

        if dry_run:
            continue

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE places
                       SET visit_role         = %(role)s,
                           estimated_duration = %(dur)s,
                           visit_time_slot    = %(slots)s,
                           indoor_outdoor     = %(io_val)s,
                           updated_at         = NOW()
                     WHERE place_id  = %(pid)s
                       AND visit_role IS NULL
                    """,
                    {"role": role, "dur": duration, "slots": slots, "io_val": io_val, "pid": pid},
                )
            conn.commit()
            ok += 1
        except Exception as exc:
            conn.rollback()
            log.error("  FAIL  place_id=%d  %s — %s", pid, name, exc)
            fail += 1

        if i % _LOG_INTERVAL == 0:
            log.info("  [중간] %d/%d 완료 — ok=%d  fail=%d", i, total, ok, fail)

    conn.close()

    # ── 결과 요약 ─────────────────────────────────────────────────────
    log.info("=" * 64)
    log.info("[batch_rules] 완료%s", dry_label)
    if dry_run:
        log.info("  예상 처리 건수: %d건 (실제 변경 없음)", total)
    else:
        log.info("  성공: %d건 / 실패: %d건", ok, fail)
    log.info("  visit_role 분포:")
    for role, cnt in sorted(role_stats.items(), key=lambda x: -x[1]):
        log.info("    %-6s: %4d건", role, cnt)
    log.info("  카테고리별 처리 건수:")
    cat_label = {12: "관광지", 14: "문화시설", 39: "음식"}
    for cat, cnt in sorted(cat_stats.items()):
        log.info("    cat%d (%s): %4d건", cat, cat_label.get(cat, ""), cnt)
    log.info("=" * 64)


# ─────────────────────────────────────────────────────────────────────────────
# indoor_outdoor 전용 배치 (visit_role 이미 완료된 행 대상)
# ─────────────────────────────────────────────────────────────────────────────

def run_indoor_outdoor_batch(
    dry_run: bool = False,
    area_codes: list[int] | None = None,
    type_ids: list[int] | None = None,
    limit: int | None = None,
) -> None:
    region_names = [_AREA_NAME[c] for c in (area_codes or []) if c in _AREA_NAME]
    active_cats  = [c for c in (type_ids or TARGET_CATEGORIES) if c in TARGET_CATEGORIES]
    dry_label    = "  [DRY-RUN — 변경 없음]" if dry_run else ""

    log.info("=" * 64)
    log.info("[fill-io] indoor_outdoor 배치 시작%s", dry_label)
    log.info("  대상 카테고리 : %s", active_cats)
    log.info("  지역 필터     : %s", region_names or "전체")
    log.info("  최대 건수     : %s", limit or "전체")
    log.info("=" * 64)

    conn = psycopg2.connect(
        host=config.DB_HOST, port=config.DB_PORT,
        dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

    params: dict = {"cats": active_cats}
    if region_names:
        params["regions"] = region_names

    sql = """
        SELECT place_id, name, overview, category_id, region_1
        FROM   places
        WHERE  category_id    = ANY(%(cats)s)
          AND  indoor_outdoor IS NULL
          AND  is_active      = TRUE
    """
    if region_names:
        sql += "  AND  region_1 = ANY(%(regions)s)\n"
    sql += "ORDER BY category_id, place_id"
    if limit:
        sql += "\nLIMIT %(limit)s"
        params["limit"] = limit

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]

    total = len(rows)
    log.info("[fill-io] 처리 대상: %d건", total)

    if total == 0:
        log.info("[fill-io] 처리 대상 없음 — 종료")
        conn.close()
        return

    io_stats: dict[str, int] = {}
    cat_stats: dict[int, int] = {c: 0 for c in active_cats}
    ok = fail = 0

    for i, row in enumerate(rows, 1):
        pid      = row["place_id"]
        name     = row["name"]
        overview = row["overview"]
        cat_id   = row["category_id"]

        result = classify_place(name, overview, cat_id)
        io_val = result["indoor_outdoor"]

        io_stats[io_val or "None"] = io_stats.get(io_val or "None", 0) + 1
        cat_stats[cat_id] = cat_stats.get(cat_id, 0) + 1

        if dry_run or i <= 10:
            log.info(
                "  [%d/%d] cat=%d  %-24s → io=%-7s",
                i, total, cat_id, name[:24], io_val,
            )

        if dry_run:
            continue

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE places
                       SET indoor_outdoor = %(io_val)s,
                           updated_at    = NOW()
                     WHERE place_id         = %(pid)s
                       AND indoor_outdoor IS NULL
                    """,
                    {"io_val": io_val, "pid": pid},
                )
            conn.commit()
            ok += 1
        except Exception as exc:
            conn.rollback()
            log.error("  FAIL  place_id=%d  %s — %s", pid, name, exc)
            fail += 1

        if i % _LOG_INTERVAL == 0:
            log.info("  [중간] %d/%d 완료 — ok=%d  fail=%d", i, total, ok, fail)

    conn.close()

    log.info("=" * 64)
    log.info("[fill-io] 완료%s", dry_label)
    if dry_run:
        log.info("  예상 처리 건수: %d건 (실제 변경 없음)", total)
    else:
        log.info("  성공: %d건 / 실패: %d건", ok, fail)
    log.info("  indoor_outdoor 분포:")
    for val, cnt in sorted(io_stats.items(), key=lambda x: -x[1]):
        log.info("    %-7s: %4d건", val, cnt)
    log.info("  카테고리별 처리 건수:")
    cat_label = {12: "관광지", 14: "문화시설", 39: "음식"}
    for cat, cnt in sorted(cat_stats.items()):
        log.info("    cat%d (%s): %4d건", cat, cat_label.get(cat, ""), cnt)
    log.info("=" * 64)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="규칙 기반 visit_role / visit_time_slot / estimated_duration / indoor_outdoor 배치",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python batch_rules.py --dry-run                     # 전체 preview (변경 없음)
  python batch_rules.py --area 1 --dry-run            # 서울만 preview
  python batch_rules.py --area 1 --limit 50          # 서울 50건 테스트 적용
  python batch_rules.py --area 1                     # 서울 전체 적용
  python batch_rules.py                              # 전 지역 전체 적용
  python batch_rules.py --fill-io --area 1 --dry-run # 서울 indoor_outdoor preview
  python batch_rules.py --fill-io --area 1           # 서울 indoor_outdoor 적용
  python batch_rules.py --fill-io                    # 전국 indoor_outdoor 적용
        """,
    )
    p.add_argument("--dry-run", action="store_true",
                   help="변경 없이 결과만 미리보기")
    p.add_argument("--fill-io", action="store_true",
                   help="indoor_outdoor 전용 배치 (visit_role 완료 행 대상)")
    p.add_argument("--area", type=int, nargs="+", default=None,
                   help="지역 코드 (예: 1=서울 6=부산). 미지정 시 전체")
    p.add_argument("--type", type=int, nargs="+", default=None,
                   help="카테고리 코드 (12/14/39 중 선택). 미지정 시 전체")
    p.add_argument("--limit", type=int, default=None,
                   help="최대 처리 건수 (테스트용)")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.fill_io:
        run_indoor_outdoor_batch(
            dry_run=args.dry_run,
            area_codes=args.area,
            type_ids=args.type,
            limit=args.limit,
        )
    else:
        run_batch(
            dry_run=args.dry_run,
            area_codes=args.area,
            type_ids=args.type,
            limit=args.limit,
        )
