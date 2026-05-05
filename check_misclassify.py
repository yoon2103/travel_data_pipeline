#!/usr/bin/env python3
"""
check_misclassify.py — 오분류 의심 샘플 확대 조회 + 키워드 매칭 분석 (read-only)

대상:
  cat12 indoor  (관광지인데 indoor)
  cat14 outdoor (문화시설인데 outdoor)
  cat39 outdoor (음식점인데 outdoor)

각 케이스마다:
  - 샘플 50건 조회
  - 어떤 키워드로 분류됐는지 역추적
  - 정상/오분류 추정 근거 출력
"""

import psycopg2
import psycopg2.extras
import config

# batch_rules.py 의 키워드 그대로 복사 (read-only 참조용)
MIXED_KEYWORDS   = ["복합문화공간", "테마파크", "놀이공원", "리조트", "워터파크"]
INDOOR_KEYWORDS  = ["박물관", "미술관", "갤러리", "공연장", "극장", "스파", "찜질", "수족관", "실내"]
OUTDOOR_KEYWORDS = ["공원", "숲", "등산", "계곡", "트레킹", "해수욕장", "해변", "야외"]

# 강한 직접 서술 vs 약한 위치 맥락 분리
STRONG_INDOOR  = ["수족관", "박물관", "미술관", "스파", "찜질", "실내"]
WEAK_INDOOR    = ["갤러리", "공연장", "극장"]
STRONG_OUTDOOR = ["야외", "해수욕장"]
WEAK_OUTDOOR   = ["공원", "숲", "계곡", "트레킹", "등산", "해변"]

SAMPLE_LIMIT = 50


def matched_keywords(text: str, keywords: list) -> list:
    return [kw for kw in keywords if kw in text]


def classify_entry(text: str, expected_io: str) -> tuple[str, str]:
    """
    (verdict, triggered_by) 반환.
    verdict: "정상가능" | "판단유보" | "오분류의심"
    """
    m_mixed   = matched_keywords(text, MIXED_KEYWORDS)
    m_indoor  = matched_keywords(text, INDOOR_KEYWORDS)
    m_outdoor = matched_keywords(text, OUTDOOR_KEYWORDS)

    if expected_io == "indoor":
        strong = matched_keywords(text, STRONG_INDOOR)
        weak   = matched_keywords(text, WEAK_INDOOR)
        if strong:
            return "정상가능", f"strong indoor={strong}"
        if weak:
            return "판단유보", f"weak indoor={weak}"
        return "오분류의심", "키워드 없음(default 의심)"

    else:  # expected_io == "outdoor"
        strong = matched_keywords(text, STRONG_OUTDOOR)
        weak   = matched_keywords(text, WEAK_OUTDOOR)
        if strong:
            return "정상가능", f"strong outdoor={strong}"
        if weak:
            return "판단유보", f"weak outdoor(위치맥락)={weak}"
        return "오분류의심", "키워드 없음(default 의심)"


def analyze(rows: list, expected_io: str, label: str, full_count: int) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {label}")
    print(f"  샘플 {len(rows)}건  /  전체 {full_count}건")
    print(f"{'=' * 70}")

    legit   = []
    hold    = []
    suspect = []

    for r in rows:
        text    = f"{r['name']} {r['overview'] or ''}"
        verdict, triggered = classify_entry(text, expected_io)
        entry = {
            "place_id":  r["place_id"],
            "name":      r["name"],
            "region":    r["region_1"],
            "triggered": triggered,
            "overview":  (r["overview"] or "")[:80],
        }
        if verdict == "정상가능":
            legit.append(entry)
        elif verdict == "판단유보":
            hold.append(entry)
        else:
            suspect.append(entry)

    def print_entries(entries: list, tag: str) -> None:
        for e in entries[:8]:
            print(f"    place_id={e['place_id']:>6}  {e['name'][:22]:<22}  {e['region']:<4}"
                  f"  [{tag}] {e['triggered']}")
            if e["overview"]:
                print(f"           {e['overview'][:75]}")

    print(f"\n  [정상 가능  : {len(legit):>3}건]")
    print_entries(legit, "OK")
    print(f"\n  [판단 유보  : {len(hold):>3}건]")
    print_entries(hold, "?")
    print(f"\n  [오분류 의심: {len(suspect):>3}건]")
    print_entries(suspect, "X")

    total = len(rows)
    print(f"\n  ── 샘플 {total}건 기준 비율 ──")
    print(f"    정상 가능  : {len(legit):>3}건  ({100*len(legit)/total:.0f}%)")
    print(f"    판단 유보  : {len(hold):>3}건  ({100*len(hold)/total:.0f}%)")
    print(f"    오분류 의심: {len(suspect):>3}건  ({100*len(suspect)/total:.0f}%)")

    # 전체 건수 추정
    suspect_rate = len(suspect) / total
    hold_rate    = len(hold)    / total
    print(f"\n  ── 전체 {full_count}건 외삽 추정 ──")
    print(f"    오분류 의심 추정: ~{int(full_count * suspect_rate)}건")
    print(f"    판단 유보  추정 : ~{int(full_count * hold_rate)}건")


conn = psycopg2.connect(
    host=config.DB_HOST, port=config.DB_PORT,
    dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
    cursor_factory=psycopg2.extras.RealDictCursor,
)
conn.set_session(readonly=True, autocommit=True)

# ── cat12 indoor ──────────────────────────────────────────────
with conn.cursor() as cur:
    cur.execute("""
        SELECT place_id, name, region_1, overview
        FROM   places
        WHERE  is_active = TRUE AND category_id = 12 AND indoor_outdoor = 'indoor'
        ORDER BY place_id
        LIMIT %s
    """, (SAMPLE_LIMIT,))
    rows12 = [dict(r) for r in cur.fetchall()]

# ── cat14 outdoor ─────────────────────────────────────────────
with conn.cursor() as cur:
    cur.execute("""
        SELECT place_id, name, region_1, overview
        FROM   places
        WHERE  is_active = TRUE AND category_id = 14 AND indoor_outdoor = 'outdoor'
        ORDER BY place_id
        LIMIT %s
    """, (SAMPLE_LIMIT,))
    rows14 = [dict(r) for r in cur.fetchall()]

# ── cat39 outdoor ─────────────────────────────────────────────
with conn.cursor() as cur:
    cur.execute("""
        SELECT place_id, name, region_1, overview
        FROM   places
        WHERE  is_active = TRUE AND category_id = 39 AND indoor_outdoor = 'outdoor'
        ORDER BY place_id
        LIMIT %s
    """, (SAMPLE_LIMIT,))
    rows39 = [dict(r) for r in cur.fetchall()]

conn.close()

analyze(rows12, "indoor",  "cat12(관광지) indoor 의심",   full_count=476)
analyze(rows14, "outdoor", "cat14(문화시설) outdoor 의심", full_count=124)
analyze(rows39, "outdoor", "cat39(음식점) outdoor 의심",   full_count=1871)
