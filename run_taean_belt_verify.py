"""
태안(충남) 관광벨트 최종 QA 검증 — 동일 파라미터 5회 반복
검증 항목: 앵커 분산 / 카테고리 다양성 / 중복 방지 / 동선 자연성 / Tier1 포함 여부
"""
import logging
import db_client
from course_builder import build_course

logging.disable(logging.CRITICAL)

# 충남 벨트 핵심 시드명 (tier1 포함 여부 판단 기준)
TAEAN_BELT_SEEDS = {
    "꽃지해수욕장", "백사장항", "안면암(태안)", "안면도수목원",
    "간월도마을", "만리포해수욕장",
}

REQUEST = {
    "region":             "충남",
    "themes":             ["자연", "힐링"],
    "template":           "standard",
    "departure_time":     "09:00",
    "region_travel_type": "urban",
    "zone_center":        (36.52, 126.33),   # 태안/안면도 해안축 중심
}

TRIALS = 5

rows = []
for i in range(1, TRIALS + 1):
    conn = db_client.get_connection()
    try:
        r = build_course(conn, REQUEST)
    finally:
        conn.close()

    places = r.get("places", [])
    belt_matched_names = [b["name"] for b in r.get("belt_matched_places", [])]

    # Tier1: belt_matched 중 핵심 시드 포함 여부 (course_builder tier1_in_course 필드)
    tier1_in_course = r.get("tier1_in_course", False)

    if len(places) < 2:
        rows.append({
            "trial": i, "anchor": places[0]["name"] if places else "—",
            "anchor_id": places[0].get("place_id") if places else None,
            "t1_name": "—", "t1_role": "—", "t1_id": None,
            "t2_name": "—", "t2_role": "—", "t2_id": None,
            "travel_min": None, "dist_km": None,
            "belt_applied": r.get("tourism_belt_applied"),
            "belt_sum": r.get("belt_boost_sum"),
            "belt_matched": belt_matched_names,
            "tier1_in_course": tier1_in_course,
            "total_places": len(places),
            "all_place_ids": [p.get("place_id") for p in places],
            "all_names": [p["name"] for p in places],
            "all_roles": [p.get("visit_role") for p in places],
        })
        continue

    p0, p1 = places[0], places[1]
    rows.append({
        "trial":         i,
        "anchor":        p0["name"],
        "anchor_id":     p0.get("place_id"),
        "t1_name":       p0["name"],
        "t1_role":       p0.get("visit_role", "?"),
        "t1_id":         p0.get("place_id"),
        "t2_name":       p1["name"],
        "t2_role":       p1.get("visit_role", "?"),
        "t2_id":         p1.get("place_id"),
        "travel_min":    p1.get("move_minutes_from_prev"),
        "dist_km":       p1.get("distance_km_from_prev"),
        "belt_applied":  r.get("tourism_belt_applied"),
        "belt_sum":      r.get("belt_boost_sum"),
        "belt_matched":  belt_matched_names,
        "tier1_in_course": tier1_in_course,
        "total_places":  len(places),
        "all_place_ids": [p.get("place_id") for p in places],
        "all_names":     [p["name"] for p in places],
        "all_roles":     [p.get("visit_role") for p in places],
    })

# ── 출력 ──────────────────────────────────────────────────────────────
SEP = "─" * 72
print(SEP)
print(f"  태안(충남) 관광벨트 검증  파라미터: 충남/자연힐링/standard/09:00 ×{TRIALS}회")
print(SEP)

header = f"{'Trial':>5}  {'Anchor (T1)':22}  {'T1→T2 이동':12}  코스 흐름"
print(header)
print("─" * 100)
for row in rows:
    travel = f"{int(row['travel_min'])}분/{row['dist_km']:.1f}km" if row["travel_min"] is not None else "—"
    flow = " → ".join(
        f"{n}({r})"
        for n, r in zip(row.get("all_names", []), row.get("all_roles", []))
    )
    print(f"{row['trial']:>5}  {row['anchor']:22}  {travel:12}  {flow}")

print()
print("── 벨트 매칭 상세 ─────────────────────────────────────────────")
for row in rows:
    tier1_flag = "Tier1=YES" if row["tier1_in_course"] else "Tier1=NO "
    print(f"Trial {row['trial']}  {tier1_flag}  boost={row.get('belt_sum','?')}  "
          f"matched={row.get('belt_matched', [])}")

# ── 검증 분석 ─────────────────────────────────────────────────────────
from collections import Counter

print()
print(SEP)
print("  검증 항목 분석")
print(SEP)

anchors = [r["anchor"] for r in rows]

# [1] 앵커 분산
unique_anchors = set(anchors)
anchor_pass = len(unique_anchors) >= 2
print(f"[1] 앵커 분산       {'PASS' if anchor_pass else 'FAIL'}")
for name, cnt in Counter(anchors).most_common():
    print(f"    {name}: {cnt}회")

# [2] 카테고리 다양성
coastal_kw = ["해수욕", "해변", "항", "포구"]
coastal_count = sum(1 for a in anchors if any(k in a for k in coastal_kw))
coastal_ratio = coastal_count / len(rows)
diversity_pass = coastal_ratio < 0.8
all_t1_roles = [r["t1_role"] for r in rows]
all_t2_roles = [r["t2_role"] for r in rows]
print(f"\n[2] 카테고리 다양성  {'PASS' if diversity_pass else 'FAIL'}")
print(f"    T1 roles: {Counter(all_t1_roles).most_common()}")
print(f"    T2 roles: {Counter(all_t2_roles).most_common()}")
print(f"    Anchor 해안/항구 계열: {coastal_count}/{len(rows)} ({coastal_ratio*100:.0f}%)")

# [3] 중복 방지 (Trial 내부 기준)
all_ids_per_trial = [r.get("all_place_ids", []) for r in rows]
intra_dups = [i+1 for i, ids in enumerate(all_ids_per_trial) if len(ids) != len(set(ids))]
anchor_reappear = [
    row["trial"] for row in rows
    if row.get("anchor_id") in (row.get("all_place_ids", [])[1:])
]
nodup_pass = not intra_dups and not anchor_reappear
print(f"\n[3] 중복 방지       {'PASS' if nodup_pass else 'FAIL'}")
print(f"    기준: Trial 내부 place_id 중복 / Anchor 후속 재등장")
print(f"    Trial 내 place_id 중복: {'없음' if not intra_dups else f'[!] Trial {intra_dups}'}")
print(f"    Anchor 후속 재등장:     {'없음' if not anchor_reappear else f'[!] Trial {anchor_reappear}'}")
print(f"    (Trial 간 동일 앵커 반복은 정상 확률 현상 — 검사 제외)")

# [4] 동선 자연성
travel_times = [r["travel_min"] for r in rows if r["travel_min"] is not None]
overlong = [rows[i]["trial"] for i, t in enumerate([r["travel_min"] for r in rows])
            if t is not None and t > 60]
mobility_pass = not overlong
print(f"\n[4] 동선 자연성     {'PASS' if mobility_pass else 'FAIL'}")
if travel_times:
    print(f"    T1→T2 이동: min={min(travel_times)}분  max={max(travel_times)}분  "
          f"avg={sum(travel_times)/len(travel_times):.1f}분")
print(f"    60분 초과: {'없음' if not overlong else f'[!] Trial {overlong}'}")

# [5] Tier1 포함 여부 (태안 전용)
tier1_results = [(row["trial"], row["tier1_in_course"]) for row in rows]
tier1_pass_count = sum(1 for _, ok in tier1_results if ok)
tier1_pass = tier1_pass_count == TRIALS
print(f"\n[5] Tier1 포함 여부 {'PASS' if tier1_pass else 'FAIL'} "
      f"({tier1_pass_count}/{TRIALS}회)")
for trial, ok in tier1_results:
    flag = "YES" if ok else "NO "
    print(f"    Trial {trial}: Tier1={flag}")

print()
overall = all([anchor_pass, diversity_pass, nodup_pass, mobility_pass, tier1_pass])
print(f"  종합: {'전 항목 PASS' if overall else '일부 FAIL — 위 내역 확인'}")
print(SEP)
