"""
analyze_data_priority.py
데이터 보강 우선순위 분석

QA 결과 + DB 실제 장소 수 기반 종합 분석
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

import db_client

# ── QA 결과 로드 ──────────────────────────────────────────────────────────────

QA_FILE = Path("qa_reports/qa_all_regions_20260504_221451.json")

with open(QA_FILE, encoding="utf-8") as f:
    qa = json.load(f)

results = qa["results"]

# ── DB에서 지역별 × role별 장소 수 조회 ───────────────────────────────────────

ROLE_CATEGORY_MAP = {
    "spot":    [12],          # 관광지
    "culture": [14],          # 문화시설
    "meal":    [39],          # 음식점
    "cafe":    [39],          # 카페 (ai_tags 기반 구분)
}

conn = db_client.get_connection()

# 지역별 카테고리별 장소 수
with conn.cursor() as cur:
    cur.execute("""
        SELECT
            region_1,
            category_id,
            visit_role,
            COUNT(*) AS cnt
        FROM places
        WHERE is_active = TRUE
          AND category_id IN (12, 14, 39)
          AND region_1 IS NOT NULL
        GROUP BY region_1, category_id, visit_role
        ORDER BY region_1, category_id, visit_role
    """)
    db_rows = cur.fetchall()

# 지역별 anchor 선택 분포 (QA 실행 결과에서 추출)
# anchor별 반경 10km 이내 장소 수 조회
with conn.cursor() as cur:
    cur.execute("""
        SELECT
            region_1,
            visit_role,
            COUNT(*) AS cnt,
            AVG(
                CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 ELSE 0 END
            ) AS coord_rate
        FROM places
        WHERE is_active = TRUE
          AND category_id IN (12, 14, 39)
          AND region_1 IS NOT NULL
        GROUP BY region_1, visit_role
        ORDER BY region_1, visit_role
    """)
    role_rows = cur.fetchall()

# 지역별 총 장소 수 (서비스 가능 여부 확인)
with conn.cursor() as cur:
    cur.execute("""
        SELECT
            region_1,
            COUNT(*) AS total,
            SUM(CASE WHEN category_id = 12 THEN 1 ELSE 0 END) AS spot_cnt,
            SUM(CASE WHEN category_id = 14 THEN 1 ELSE 0 END) AS culture_cnt,
            SUM(CASE WHEN category_id = 39 AND visit_role = 'cafe' THEN 1 ELSE 0 END) AS cafe_cnt,
            SUM(CASE WHEN category_id = 39 AND visit_role = 'meal' THEN 1 ELSE 0 END) AS meal_cnt,
            SUM(CASE WHEN category_id = 39 AND visit_role IS NULL THEN 1 ELSE 0 END) AS meal_untagged,
            SUM(CASE WHEN ai_validation_status = 'passed' THEN 1 ELSE 0 END) AS ai_ok,
            SUM(CASE WHEN visit_role IS NULL THEN 1 ELSE 0 END) AS role_null
        FROM places
        WHERE is_active = TRUE
          AND category_id IN (12, 14, 39)
          AND region_1 IS NOT NULL
        GROUP BY region_1
        ORDER BY region_1
    """)
    region_totals = {r["region_1"]: dict(r) for r in cur.fetchall()}

conn.close()

# ── QA 결과 파싱 ──────────────────────────────────────────────────────────────

fail_cases = [r for r in results if r["verdict"] == "FAIL"]
pass_cases = [r for r in results if r["verdict"] == "PASS"]
weak_cases = [r for r in results if r["verdict"] == "WEAK"]

# FAIL 유형 분류
blocked_fails = [r for r in fail_cases if "생성 실패" in " ".join(r.get("notes", []))]
slot_fails    = [r for r in fail_cases if "슬롯" in " ".join(r.get("notes", []))]

# 4장소 PASS (option_notice 처리된 케이스)
notice_pass = [r for r in pass_cases if r["place_count"] == 4]

# 지역별 집계
region_verdicts = defaultdict(lambda: {"PASS": 0, "WEAK": 0, "FAIL": 0, "total": 0})
for r in results:
    region_verdicts[r["region_label"]][r["verdict"]] += 1
    region_verdicts[r["region_label"]]["total"] += 1

# ── role 부족 분포 분석 ────────────────────────────────────────────────────────

# 실질적 FAIL (BLOCKED 제외)
real_fails = slot_fails

role_deficit = {"cafe": 0, "meal": 0, "spot_culture": 0}
for r in real_fails:
    # 목표 장소 수 대비 실제 수로 부족 role 추정
    if r["cafe_count"] == 0:
        role_deficit["cafe"] += 1
    if r["meal_count"] == 0:
        role_deficit["meal"] += 1
    if r["spot_culture"] <= 1:
        role_deficit["spot_culture"] += 1

# 4장소 PASS에서도 슬롯 미채움 role 분석
for r in notice_pass:
    # 표준 슬롯 기준: spot/culture 2개, meal 1개, cafe 1개 최소
    if r["cafe_count"] == 0:
        role_deficit["cafe"] += 1
    if r["meal_count"] == 0:
        role_deficit["meal"] += 1

# ── 앵커 유형 분류 ──────────────────────────────────────────────────────────────

ANCHOR_TYPE_KEYWORDS = {
    "사찰/종교": ["사", "암", "사지", "향교", "서원", "성당", "교회", "절"],
    "역사유적":  ["성", "궁", "터", "유적", "사적", "문화재"],
    "자연외곽":  ["산장", "선착장", "항", "도", "오름", "숲", "계곡", "폭포"],
    "도심상업":  ["카페", "커피", "식당", "백화점", "시장", "골목"],
    "공원/광장": ["공원", "광장", "호수", "해수욕장", "해변"],
    "문화시설":  ["박물관", "미술관", "도서관", "전시관", "문화원"],
}

def classify_anchor(name: str) -> str:
    for label, kws in ANCHOR_TYPE_KEYWORDS.items():
        if any(kw in name for kw in kws):
            return label
    return "기타"

# ── 출력 ─────────────────────────────────────────────────────────────────────

SEP = "=" * 70
SEP2 = "─" * 70

print(SEP)
print("  데이터 보강 우선순위 분석")
print(f"  QA 기준: {qa['generated_at']}  총 {qa['total']}케이스")
print(SEP)

# ── 1. QA 종합 현황 ──────────────────────────────────────────────────────────

total = len(results)
pass_n = len(pass_cases)
weak_n = len(weak_cases)
fail_n = len(fail_cases)

print(f"\n[1] QA 종합 현황")
print(f"  PASS={pass_n}  WEAK={weak_n}  FAIL={fail_n}  / {total}건")
print(f"  BLOCKED 지역 FAIL: {len(blocked_fails)}건  /  슬롯 미채움 FAIL: {len(real_fails)}건")
print(f"  4장소 PASS(option_notice 처리): {len(notice_pass)}건")

# ── 2. FAIL 케이스 상세 ───────────────────────────────────────────────────────

print(f"\n[2] FAIL 케이스 상세 분석")
print(f"\n  ▶ BLOCKED 지역 (코스 생성 불가, {len(blocked_fails)}건)")
blocked_regions = sorted(set(r["region_label"] for r in blocked_fails))
for reg in blocked_regions:
    cnt = sum(1 for r in blocked_fails if r["region_label"] == reg)
    db_info = region_totals.get(reg)
    if db_info:
        print(f"    {reg}: FAIL {cnt}건  DB장소={db_info['total']}개"
              f"  (spot={db_info['spot_cnt']} culture={db_info['culture_cnt']}"
              f" meal={db_info['meal_cnt']} cafe={db_info['cafe_cnt']})")
    else:
        print(f"    {reg}: FAIL {cnt}건  DB장소=0 (미적재)")

print(f"\n  ▶ 슬롯 미채움 FAIL ({len(real_fails)}건)")
for r in real_fails:
    anchor_type = classify_anchor(r["anchor_name"])
    db_info = region_totals.get(r["region_label"], {})
    print(f"    [{r['region_label']} / {r['option_label']}]  {r['place_count']}장소")
    print(f"      anchor: {r['anchor_name']}  유형={anchor_type}")
    print(f"      roles:  cafe={r['cafe_count']} meal={r['meal_count']}"
          f" spot/cu={r['spot_culture']}")
    print(f"      이동합계: {r['total_travel_min']}분")
    print(f"      DB 지역 현황: 총={db_info.get('total',0)}"
          f"  spot={db_info.get('spot_cnt',0)}"
          f"  culture={db_info.get('culture_cnt',0)}"
          f"  meal={db_info.get('meal_cnt',0)}"
          f"  cafe={db_info.get('cafe_cnt',0)}")
    # 부족 role 진단
    lacks = []
    if r["cafe_count"] == 0:
        lacks.append(f"cafe부족(DB cafe={db_info.get('cafe_cnt',0)})")
    if r["meal_count"] == 0:
        lacks.append(f"meal부족(DB meal={db_info.get('meal_cnt',0)})")
    if r["spot_culture"] <= 1:
        lacks.append(f"spot/culture부족(DB spot={db_info.get('spot_cnt',0)} cu={db_info.get('culture_cnt',0)})")
    print(f"      진단: {' / '.join(lacks) if lacks else 'place_count 부족'}")

# ── 3. 4장소 PASS 지역 분석 (잠재 위험) ──────────────────────────────────────

print(f"\n[3] 4장소 PASS 지역 (option_notice 처리, 잠재 위험)")
print(f"  {'지역':<6} {'옵션':<8} {'anchor':<22} {'유형':<10} cafe  meal  sp/cu  이동(분)")
print(f"  {SEP2}")
for r in notice_pass:
    atype = classify_anchor(r["anchor_name"])
    print(f"  {r['region_label']:<6} {r['option_label']:<8} {r['anchor_name'][:20]:<22}"
          f" {atype:<10}  {r['cafe_count']}     {r['meal_count']}     {r['spot_culture']}"
          f"      {r['total_travel_min']}")

# ── 4. 지역별 DB 장소 현황 ───────────────────────────────────────────────────

print(f"\n[4] 지역별 DB 장소 현황 (is_active=true, category 12/14/39)")
print(f"  {'지역':<6} {'총':<6} {'spot':<5} {'cu':<5} {'meal':<5} {'cafe':<5}"
      f" {'미태깅':<6} {'AI완료율':<8} {'QA'}")
print(f"  {SEP2}")
for region, info in sorted(region_totals.items()):
    vc = region_verdicts[region]
    pass_rate = vc["PASS"] / vc["total"] * 100 if vc["total"] else 0
    ai_rate = info["ai_ok"] / info["total"] * 100 if info["total"] else 0
    qa_str = f"P{vc['PASS']}W{vc['WEAK']}F{vc['FAIL']}"
    print(f"  {region:<6} {info['total']:<6} {info['spot_cnt']:<5} {info['culture_cnt']:<5}"
          f" {info['meal_cnt']:<5} {info['cafe_cnt']:<5}"
          f" {info['meal_untagged']:<6} {ai_rate:>5.0f}%   {qa_str}")

# ── 5. role 부족 분포 ─────────────────────────────────────────────────────────

print(f"\n[5] role 부족 분포 (FAIL + 4장소 PASS 합산)")
total_deficit_cases = len(real_fails) + len(notice_pass)
for role, cnt in sorted(role_deficit.items(), key=lambda x: -x[1]):
    bar = "█" * cnt
    print(f"  {role:<15}: {bar}  {cnt}건")

# ── 6. 앵커 유형별 FAIL 분포 ─────────────────────────────────────────────────

print(f"\n[6] 앵커 유형별 FAIL/약점 분포")
anchor_type_counts = defaultdict(int)
problem_cases = real_fails + notice_pass
for r in problem_cases:
    atype = classify_anchor(r["anchor_name"])
    anchor_type_counts[atype] += 1
for atype, cnt in sorted(anchor_type_counts.items(), key=lambda x: -x[1]):
    bar = "█" * cnt
    print(f"  {atype:<12}: {bar}  {cnt}건")

# ── 7. 데이터 보강 우선순위 TOP 5 ────────────────────────────────────────────

print(f"\n{SEP}")
print("  [데이터 보강 우선순위 TOP 5]")
print(SEP)

priorities = []

# 점수 계산: FAIL건수×10 + 4장소PASS건수×3 + role부족 심각도×5
for region, vc in region_verdicts.items():
    db_info = region_totals.get(region, {})
    fail_score = vc["FAIL"] * 10
    weak_score = sum(1 for r in notice_pass if r["region_label"] == region) * 3

    # role 부족 심각도
    role_gap = 0
    if db_info.get("cafe_cnt", 0) < 5:
        role_gap += 5
    if db_info.get("meal_cnt", 0) < 10:
        role_gap += 5
    if db_info.get("spot_cnt", 0) < 5:
        role_gap += 3
    if db_info.get("culture_cnt", 0) < 3:
        role_gap += 2

    total_score = fail_score + weak_score + role_gap

    if vc["FAIL"] > 0 or len([r for r in notice_pass if r["region_label"] == region]) > 0:
        priorities.append({
            "region":     region,
            "score":      total_score,
            "fail":       vc["FAIL"],
            "pass4":      len([r for r in notice_pass if r["region_label"] == region]),
            "total_db":   db_info.get("total", 0),
            "spot":       db_info.get("spot_cnt", 0),
            "culture":    db_info.get("culture_cnt", 0),
            "meal":       db_info.get("meal_cnt", 0),
            "cafe":       db_info.get("cafe_cnt", 0),
            "role_gap":   role_gap,
        })

priorities.sort(key=lambda x: -x["score"])

PRIORITY_LABELS = {
    "경남": "BLOCKED — category 12/14/39 전체 수집 필요 (현재 DB 0건에 준하는 서비스 불가)",
    "충북": "BLOCKED — category 12/14/39 전체 수집 필요 (현재 DB 데이터 부족, 서비스 불가)",
    "전남": "슬롯 FAIL 2건 — 사찰·역사유적 앵커 주변 meal/cafe 절대 부족 (특히 강진·화순·담양권)",
    "인천": "도서 지역 자연/힐링 FAIL — 무의도·영종도권 meal/spot 보강 필요",
    "강원": "외곽 산악 앵커(계방산장 등) 카페투어 FAIL — 비도심 권역 카페·meal 보강 필요",
    "경기": "광역 앵커 분산 — 성남·용인·고양 권역 spot/culture 집중 보강으로 4장소 → 5장소 전환 가능",
    "전북": "자연/힐링 4장소 — 고택·농촌 앵커 주변 spot/culture 보강 필요",
    "제주": "자연/힐링 4장소 — 오름 주변 카페 보강 (금오름 권역 10km 이내 cafe 부족)",
}

for i, p in enumerate(priorities[:5], 1):
    label = PRIORITY_LABELS.get(p["region"], "")
    print(f"\n  #{i}  {p['region']}  (우선순위 점수: {p['score']})")
    print(f"       QA: FAIL={p['fail']}건  4장소PASS={p['pass4']}건")
    print(f"       DB: 총={p['total_db']}  spot={p['spot']}  culture={p['culture']}"
          f"  meal={p['meal']}  cafe={p['cafe']}")
    print(f"       보강 필요: {label}")

# ── 8. 보강 action 요약 ───────────────────────────────────────────────────────

print(f"\n{SEP}")
print("  [지역별 보강 Action 요약]")
print(SEP)

actions = [
    ("경남",  "CRITICAL", "category 12(관광지), 14(문화시설), 39(음식점/카페) 전 권역 수집",
               "BLOCKED 해제 → 4옵션 PASS 전환 가능"),
    ("충북",  "CRITICAL", "category 12, 14, 39 전 권역 수집 (청주·충주·제천 중심)",
               "BLOCKED 해제 → 4옵션 PASS 전환 가능"),
    ("전남",  "HIGH",     "강진·화순·담양 권역 39(meal/cafe) 집중 수집",
               "슬롯 FAIL 2건 해소 → 전남 전 옵션 PASS 전환"),
    ("인천",  "HIGH",     "무의도·영종도 권역 39(meal), 12(spot) 보강",
               "자연/힐링 FAIL 해소, 기본 4장소 → 5장소 전환"),
    ("강원",  "MEDIUM",   "평창·홍천·속초 외곽 권역 39(cafe/meal) 보강",
               "카페투어 FAIL 해소 (계방산장 앵커 반경 확장 효과)"),
    ("경기",  "MEDIUM",   "성남·용인·고양·수원 권역 spot/culture 보강",
               "3개 옵션 4장소 → 5장소 전환 (PASS 품질 향상)"),
    ("전북",  "LOW",      "임실·순창·김제 농촌 권역 spot/culture 보강",
               "자연/힐링 4장소 → 5장소 전환"),
    ("제주",  "LOW",      "한림·애월 오름 권역 cafe 보강",
               "자연/힐링 4장소 → 5장소 전환"),
]

priority_label = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
for region, level, action, effect in actions:
    mark = priority_label[level]
    print(f"\n  {mark} [{level}] {region}")
    print(f"     보강: {action}")
    print(f"     효과: {effect}")

print(f"\n{SEP}")
print("  분석 완료")
print(SEP)
