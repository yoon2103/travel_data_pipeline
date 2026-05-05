"""
강릉(강원) 관광벨트 최종 QA 검증 — 동일 파라미터 5회 반복
강릉 전용 추가 검증: 속초 서브벨트로 오분기 없는지 확인
"""
import logging
import db_client
from course_builder import build_course

logging.disable(logging.CRITICAL)

# 강릉 서브벨트 시드명
GANGNEUNG_SEEDS = {
    "정동진", "강릉 굴산사지", "경포호수광장",
    "강릉올림픽뮤지엄", "구룡폭포(소금강)",
}
# 속초 서브벨트 시드명 — 오분기 감지용
SOKCHO_SEEDS = {
    "속초해수욕장", "설악산 케이블카", "아바이마을",
    "대포항", "낙산사", "국립산악박물관",
}

REQUEST = {
    "region":             "강원",
    "themes":             ["자연", "힐링"],
    "template":           "standard",
    "departure_time":     "09:00",
    "region_travel_type": "urban",
    "zone_center":        (37.78, 128.90),   # 강릉역 인근 — 속초(38.21)와 명확히 분리
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

    # 강릉 시드 매칭 수
    gangneung_hits = [n for n in belt_matched_names if any(s in n for s in GANGNEUNG_SEEDS)]
    # 속초 시드 오분기 감지
    sokcho_hits    = [n for n in belt_matched_names if any(s in n for s in SOKCHO_SEEDS)]

    tier1_in_course = r.get("tier1_in_course", False)

    base = {
        "trial":           i,
        "tier1_in_course": tier1_in_course,
        "belt_applied":    r.get("tourism_belt_applied"),
        "belt_sum":        r.get("belt_boost_sum"),
        "belt_matched":    belt_matched_names,
        "gangneung_hits":  gangneung_hits,
        "sokcho_hits":     sokcho_hits,
        "total_places":    len(places),
        "all_place_ids":   [p.get("place_id") for p in places],
        "all_names":       [p["name"] for p in places],
        "all_roles":       [p.get("visit_role") for p in places],
    }

    if len(places) < 2:
        rows.append({**base,
            "anchor": places[0]["name"] if places else "—",
            "anchor_id": places[0].get("place_id") if places else None,
            "t1_role": "—", "t2_name": "—", "t2_role": "—",
            "travel_min": None, "dist_km": None,
        })
        continue

    p0, p1 = places[0], places[1]
    rows.append({**base,
        "anchor":     p0["name"],
        "anchor_id":  p0.get("place_id"),
        "t1_role":    p0.get("visit_role", "?"),
        "t2_name":    p1["name"],
        "t2_role":    p1.get("visit_role", "?"),
        "travel_min": p1.get("move_minutes_from_prev"),
        "dist_km":    p1.get("distance_km_from_prev"),
    })

# ── 출력 ──────────────────────────────────────────────────────────────
SEP = "─" * 72
print(SEP)
print(f"  강릉(강원) 관광벨트 검증  파라미터: 강원/자연힐링/standard/09:00 ×{TRIALS}회")
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
    g_hits = row["gangneung_hits"] or ["(없음)"]
    s_hits = row["sokcho_hits"]
    mismatch = " [!] 속초 오분기" if s_hits else ""
    print(f"Trial {row['trial']}  Tier1={'YES' if row['tier1_in_course'] else 'NO '}  "
          f"boost={row.get('belt_sum','?')}  "
          f"강릉={g_hits}  속초={s_hits or '없음'}{mismatch}")

# ── 검증 분석 ─────────────────────────────────────────────────────────
from collections import Counter

print()
print(SEP)
print("  검증 항목 분석")
print(SEP)

anchors = [r["anchor"] for r in rows]

# [1] 앵커 분산
anchor_pass = len(set(anchors)) >= 2
print(f"[1] 앵커 분산       {'PASS' if anchor_pass else 'FAIL'}")
for name, cnt in Counter(anchors).most_common():
    print(f"    {name}: {cnt}회")

# [2] 카테고리 다양성
coastal_kw = ["해수욕", "해변", "항", "포구", "해안"]
coastal_count = sum(1 for a in anchors if any(k in a for k in coastal_kw))
coastal_ratio = coastal_count / len(rows)
diversity_pass = coastal_ratio < 0.8
print(f"\n[2] 카테고리 다양성  {'PASS' if diversity_pass else 'FAIL'}")
print(f"    T1 roles: {Counter(r['t1_role'] for r in rows).most_common()}")
print(f"    T2 roles: {Counter(r['t2_role'] for r in rows).most_common()}")
print(f"    Anchor 해안 계열: {coastal_count}/{len(rows)} ({coastal_ratio*100:.0f}%)")

# [3] 중복 방지
intra_dups = [i+1 for i, ids in enumerate([r.get("all_place_ids",[]) for r in rows])
              if len(ids) != len(set(ids))]
anchor_reappear = [row["trial"] for row in rows
                   if row.get("anchor_id") in row.get("all_place_ids", [])[1:]]
nodup_pass = not intra_dups and not anchor_reappear
print(f"\n[3] 중복 방지       {'PASS' if nodup_pass else 'FAIL'}")
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

# [5] Tier1 포함 여부
tier1_pass_count = sum(1 for r in rows if r["tier1_in_course"])
tier1_pass = tier1_pass_count == TRIALS
print(f"\n[5] Tier1 포함 여부 {'PASS' if tier1_pass else 'FAIL'} ({tier1_pass_count}/{TRIALS}회)")
for row in rows:
    print(f"    Trial {row['trial']}: Tier1={'YES' if row['tier1_in_course'] else 'NO '}")

# [6] 강릉 전용 — 속초 서브벨트 오분기 없음
all_sokcho_hits = [row["trial"] for row in rows if row["sokcho_hits"]]
nobranch_pass = not all_sokcho_hits
print(f"\n[6] 속초 오분기 없음 {'PASS' if nobranch_pass else 'FAIL'}  (강릉 전용)")
if all_sokcho_hits:
    for row in rows:
        if row["sokcho_hits"]:
            print(f"    [!] Trial {row['trial']}: 속초 시드 감지 → {row['sokcho_hits']}")
else:
    print(f"    전 Trial 강릉 서브벨트 정상 적용 확인")
    all_g = [n for row in rows for n in row["gangneung_hits"]]
    print(f"    강릉 시드 매칭: {Counter(all_g).most_common()}")

print()
overall = all([anchor_pass, diversity_pass, nodup_pass, mobility_pass, tier1_pass, nobranch_pass])
print(f"  종합: {'전 항목 PASS' if overall else '일부 FAIL — 위 내역 확인'}")
print(SEP)
