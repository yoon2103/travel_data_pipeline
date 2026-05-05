"""
서울 city_mode QA 검증 — 동일 파라미터 5회 반복
검증 항목:
  [1] city_mode 활성화 확인
  [2] 클러스터 선택 (city_cluster 필드)
  [3] 첫 슬롯 cafe 여부
  [4] 코스 내 중복 방지
  [5] 동선 자연성 (leg당 25분 이하)
  [6] 앵커 분산 (5회 중 ≥2 종류)
"""
import logging
import db_client
from course_builder import build_course

logging.disable(logging.CRITICAL)

REQUEST = {
    "region":             "서울",
    "themes":             ["카페", "문화"],
    "template":           "standard",
    "departure_time":     "09:00",
    "region_travel_type": "urban",
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
    p0 = places[0] if places else {}
    p1 = places[1] if len(places) > 1 else {}

    rows.append({
        "trial":        i,
        "city_mode":    r.get("city_mode"),
        "city_cluster": r.get("city_cluster"),
        "radius_km":    r.get("selected_radius_km"),
        "weights":      r.get("selection_basis", {}).get("weights", {}),
        "anchor":       p0.get("name", "—"),
        "anchor_role":  p0.get("visit_role", "—"),
        "t2_name":      p1.get("name", "—"),
        "travel_min":   p1.get("move_minutes_from_prev"),
        "dist_km":      p1.get("distance_km_from_prev"),
        "total_places": len(places),
        "all_place_ids": [p.get("place_id") for p in places],
        "all_names":    [p["name"] for p in places],
        "all_roles":    [p.get("visit_role") for p in places],
    })

SEP = "─" * 72
print(SEP)
print(f"  서울 city_mode QA  파라미터: 서울/카페+문화/standard/09:00 ×{TRIALS}회")
print(SEP)

header = f"{'Trial':>5}  {'Cluster':18}  {'Anchor (T1)':22}  {'이동':10}  코스 흐름"
print(header)
print("─" * 110)
for row in rows:
    travel = (f"{int(row['travel_min'])}분/{row['dist_km']:.1f}km"
              if row["travel_min"] is not None else "—")
    flow = " → ".join(
        f"{n}({r})"
        for n, r in zip(row["all_names"], row["all_roles"])
    )
    cluster = row["city_cluster"] or "—"
    print(f"{row['trial']:>5}  {cluster:18}  {row['anchor']:22}  {travel:10}  {flow}")

print()
print("── 모드 상세 ──────────────────────────────────────────────────")
for row in rows:
    w = row["weights"]
    print(f"Trial {row['trial']}  city_mode={row['city_mode']}  radius={row['radius_km']}km  "
          f"travel_fit={w.get('travel_fit')}  theme_match={w.get('theme_match')}")

from collections import Counter

print()
print(SEP)
print("  검증 항목 분석")
print(SEP)

# [1] city_mode 활성화
cm_pass = all(r["city_mode"] for r in rows)
print(f"[1] city_mode 활성화  {'PASS' if cm_pass else 'FAIL'}")
for row in rows:
    print(f"    Trial {row['trial']}: city_mode={row['city_mode']}  cluster={row['city_cluster']}")

# [2] 클러스터 선택 — None 없음
cluster_pass = all(r["city_cluster"] is not None for r in rows)
print(f"\n[2] 클러스터 선택     {'PASS' if cluster_pass else 'FAIL'}")
clusters_used = [r["city_cluster"] for r in rows]
for name, cnt in Counter(clusters_used).most_common():
    print(f"    {name}: {cnt}회")

# [3] 첫 슬롯 cafe 여부
cafe_first_pass = all(r["anchor_role"] == "cafe" for r in rows)
print(f"\n[3] 첫 슬롯 cafe 여부 {'PASS' if cafe_first_pass else 'FAIL'}")
for row in rows:
    flag = "OK" if row["anchor_role"] == "cafe" else "[!]"
    print(f"    Trial {row['trial']}: anchor={row['anchor']}  role={row['anchor_role']} {flag}")

# [4] 중복 방지 (Trial 내부)
intra_dups = [i+1 for i, ids in enumerate([r["all_place_ids"] for r in rows])
              if len(ids) != len(set(ids))]
nodup_pass = not intra_dups
print(f"\n[4] 중복 방지         {'PASS' if nodup_pass else 'FAIL'}")
print(f"    Trial 내 place_id 중복: {'없음' if not intra_dups else f'[!] Trial {intra_dups}'}")

# [5] 동선 자연성 (25분 이하)
travel_times = [r["travel_min"] for r in rows if r["travel_min"] is not None]
overlong = [rows[i]["trial"] for i, t in enumerate([r["travel_min"] for r in rows])
            if t is not None and t > 25]
mobility_pass = not overlong
print(f"\n[5] 동선 자연성 ≤25분  {'PASS' if mobility_pass else 'FAIL'}")
if travel_times:
    print(f"    T1→T2 이동: min={min(travel_times)}분  max={max(travel_times)}분  "
          f"avg={sum(travel_times)/len(travel_times):.1f}분")
print(f"    25분 초과: {'없음' if not overlong else f'[!] Trial {overlong}'}")

# [6] 앵커 분산 (≥2 종류)
anchors = [r["anchor"] for r in rows]
anchor_pass = len(set(anchors)) >= 2
print(f"\n[6] 앵커 분산         {'PASS' if anchor_pass else 'FAIL'}")
for name, cnt in Counter(anchors).most_common():
    print(f"    {name}: {cnt}회")

print()
overall = all([cm_pass, cluster_pass, cafe_first_pass, nodup_pass, mobility_pass, anchor_pass])
print(f"  종합: {'전 항목 PASS' if overall else '일부 FAIL — 위 내역 확인'}")
print(SEP)
