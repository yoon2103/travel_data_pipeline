"""
run_course_qa_report.py
코스 생성 QA 자동화 리포트

대상: DB 전체 region_1 × 4옵션 × N회 (기본 3회)
출력: qa_reports/qa_all_regions_<timestamp>.md
      qa_reports/qa_all_regions_<timestamp>.json

실행 예시:
  python run_course_qa_report.py              # 전체 지역 × 3회
  python run_course_qa_report.py --repeat 5   # 전체 지역 × 5회
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import db_client
from course_builder import build_course

logging.disable(logging.CRITICAL)
sys.stdout.reconfigure(encoding="utf-8")

# ── 고정 옵션 매트릭스 ───────────────────────────────────────────────────────

OPTION_CONFIGS = [
    {"label": "기본",      "themes": ["walk"],   "template": "standard"},
    {"label": "카페투어",  "themes": ["cafe"],   "template": "standard"},
    {"label": "자연/힐링", "themes": ["nature"], "template": "standard"},
    {"label": "맛집",      "themes": ["food"],   "template": "standard"},
]

DEPARTURE = "09:00"

# city_mode(서울 등 대도시) 와 rural 분기용 — course_builder 내부 _get_city_type 과 동일 기준
_URBAN_REGIONS: set[str] = {"서울", "부산", "대구", "대전", "광주", "인천"}

# 코스에 포함되면 이상(anomaly)으로 분류할 키워드
ANOMALY_KW = [
    "폰케이스", "케이스샵", "핸드폰케이스",
    "구내식당", "학생식당", "교직원식당",
    "찜질방", "사우나",
    "모텔", "여관",
]

# 역할-이름 불일치 탐지: {visit_role: [이름에 포함되면 의심되는 키워드]}
ROLE_MISMATCH_KW: dict[str, list[str]] = {
    "cafe": ["횟집", "국밥집", "돈까스", "갈비집", "삼겹살"],
    "spot": ["폰케이스", "케이스", "부동산", "인쇄", "편의점"],
}


# ── DB에서 테스트 지역 목록 동적 조회 ────────────────────────────────────────

def _load_region_configs() -> list[dict]:
    """
    DB places 테이블에서 활성 장소가 있는 region_1 목록을 조회해
    REGION_CONFIGS 형식으로 반환.

    region_travel_type:
      - "regional" 은 zone_radius_km 필수라 전체 스캔 대상 부적합 → 사용 안 함
      - 모든 지역: "urban" (course_builder 내부에서 city_type으로 재결정)
    """
    conn = db_client.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT region_1
                FROM places
                WHERE is_active = TRUE
                  AND category_id IN (12, 14, 39)
                  AND region_1 IS NOT NULL
                ORDER BY region_1
            """)
            regions = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()

    configs = []
    for region in regions:
        configs.append({
            "label":              region,
            "region":             region,
            "region_travel_type": "urban",   # non-regional → MOBILITY_PROFILE 기반
            "zone_center":        None,
            "zone_radius_km":     None,
        })
    return configs


# ── 단일 케이스 실행 ─────────────────────────────────────────────────────────

def run_one(region_cfg: dict, option_cfg: dict, trial: int) -> dict:
    req: dict = {
        "region":             region_cfg["region"],
        "themes":             option_cfg["themes"],
        "template":           option_cfg["template"],
        "departure_time":     DEPARTURE,
        "region_travel_type": region_cfg["region_travel_type"],
    }
    if region_cfg["zone_center"]:
        req["zone_center"] = region_cfg["zone_center"]
    if region_cfg["zone_radius_km"]:
        req["zone_radius_km"] = region_cfg["zone_radius_km"]

    conn = db_client.get_connection()
    try:
        result = build_course(conn, req)
    finally:
        conn.close()

    if "error" in result and not result.get("places"):
        return _error_row(region_cfg, option_cfg, trial, result["error"])

    places       = result.get("places", [])
    city_mode    = bool(result.get("city_mode", False))
    city_cluster = result.get("city_cluster")
    tier1        = bool(result.get("tier1_in_course", False))
    total_travel = int(result.get("total_travel_min") or 0)

    role_counts: dict[str, int] = {"cafe": 0, "meal": 0, "spot": 0, "culture": 0}
    place_ids:   list           = []
    anomaly_hits: list[str]     = []

    for p in places:
        role = p.get("visit_role", "")
        if role in role_counts:
            role_counts[role] += 1

        pid = p.get("place_id")
        if pid is not None:
            place_ids.append(pid)

        name = p.get("name", "")
        for kw in ANOMALY_KW:
            if kw in name:
                anomaly_hits.append(f"{name}(키워드:{kw})")
                break
        mismatch_kws = ROLE_MISMATCH_KW.get(role, [])
        for kw in mismatch_kws:
            if kw in name:
                anomaly_hits.append(f"{name}({role}에 '{kw}' 포함)")
                break

    spot_culture = role_counts["spot"] + role_counts["culture"]
    has_dup      = len(place_ids) != len(set(place_ids))

    row = {
        "region_label":     region_cfg["label"],
        "option_label":     option_cfg["label"],
        "themes":           option_cfg["themes"],
        "trial":            trial,
        "place_count":      len(places),
        "anchor_name":      places[0]["name"] if places else "—",
        "flow":             " → ".join(p["name"] for p in places),
        "cafe_count":       role_counts["cafe"],
        "meal_count":       role_counts["meal"],
        "spot_culture":     spot_culture,
        "tier1":            tier1,
        "city_mode":        city_mode,
        "city_cluster":     city_cluster,
        "duplicate_ids":    has_dup,
        "anomaly_found":    bool(anomaly_hits),
        "anomaly_details":  anomaly_hits,
        "total_travel_min": total_travel,
        "option_notice":    result.get("option_notice"),
        "missing_slot_reason": result.get("missing_slot_reason"),
        "has_option_notice": bool(result.get("option_notice")),
    }
    verdict, notes = _judge(row)
    row["verdict"] = verdict
    row["notes"]   = notes
    return row


def _error_row(region_cfg: dict, option_cfg: dict, trial: int, msg: str) -> dict:
    row = {
        "region_label": region_cfg["label"], "option_label": option_cfg["label"],
        "themes": option_cfg["themes"], "trial": trial, "place_count": 0,
        "anchor_name": "—", "flow": "—",
        "cafe_count": 0, "meal_count": 0, "spot_culture": 0,
        "tier1": False, "city_mode": False, "city_cluster": None,
        "duplicate_ids": False, "anomaly_found": False, "anomaly_details": [],
        "total_travel_min": 0,
        "option_notice": None,
        "missing_slot_reason": None,
        "has_option_notice": False,
        "verdict": "FAIL", "notes": [f"생성 실패: {msg}"],
    }
    return row


# ── 판정 로직 ────────────────────────────────────────────────────────────────

def _judge(row: dict) -> tuple[str, list[str]]:
    notes: list[str] = []
    n = row["place_count"]
    has_notice = bool(row.get("option_notice"))

    weak = False

    if n <= 3:
        desc = f"장소 {n}개 — 슬롯 채우기 실패" if n > 0 else "코스 생성 완전 실패"
        if has_notice:
            notes.append(f"{desc}(option_notice로 안내됨)")
            weak = True
        else:
            return "FAIL", [desc]

    if n == 4:
        if has_notice:
            notes.append("장소 4개(option_notice로 안내됨)")
        else:
            notes.append("장소 4개(1슬롯 미채움)")
            weak = True

    if row["duplicate_ids"]:
        notes.append("place_id 중복")
        weak = True

    if row["anomaly_found"]:
        notes.append("이상 장소: " + " / ".join(row["anomaly_details"]))
        weak = True

    if "food" in row["themes"] and row["meal_count"] <= 1:
        notes.append(f"food 테마인데 meal={row['meal_count']}")
        weak = True

    if "cafe" in row["themes"] and row["cafe_count"] <= 1:
        notes.append(f"cafe 테마인데 cafe={row['cafe_count']}")
        weak = True

    return ("WEAK" if weak else "PASS"), notes


# ── Markdown 생성 ─────────────────────────────────────────────────────────────

def _write_md(f, rows: list[dict], ts: str, trials: int) -> None:
    counts = {"PASS": 0, "WEAK": 0, "FAIL": 0}
    for r in rows:
        counts[r["verdict"]] += 1
    total = len(rows)

    seen_labels: list[str] = []
    for r in rows:
        if r["region_label"] not in seen_labels:
            seen_labels.append(r["region_label"])

    f.write("# 코스 생성 QA 리포트 (전지역)\n\n")
    f.write(f"- 생성 시각: `{ts}`\n")
    f.write(f"- 대상 지역: {len(seen_labels)}개\n")
    f.write(f"- 반복 횟수: {trials}회\n")
    f.write(f"- 총 케이스: {total}건 — "
            f"PASS={counts['PASS']} / WEAK={counts['WEAK']} / FAIL={counts['FAIL']}\n\n")

    for rl in seen_labels:
        region_rows = [r for r in rows if r["region_label"] == rl]
        rc = {"PASS": 0, "WEAK": 0, "FAIL": 0}
        for r in region_rows:
            rc[r["verdict"]] += 1

        f.write(f"## {rl}  _(PASS={rc['PASS']} WEAK={rc['WEAK']} FAIL={rc['FAIL']})_\n\n")

        f.write("| 옵션 | # | 장소 | cafe | meal | spot/cu | Tier1 | city | 중복 | 이상 | 이동(분) | 판정 | 비고 |\n")
        f.write("|------|---|------|------|------|---------|-------|------|------|------|----------|------|------|\n")
        for r in region_rows:
            notes_str = "; ".join(r["notes"]) if r["notes"] else "—"
            f.write(
                f"| {r['option_label']} | {r['trial']} | {r['place_count']}"
                f" | {r['cafe_count']} | {r['meal_count']} | {r['spot_culture']}"
                f" | {'Y' if r['tier1'] else 'N'}"
                f" | {'Y' if r['city_mode'] else 'N'}"
                f" | {'Y' if r['duplicate_ids'] else 'N'}"
                f" | {'Y' if r['anomaly_found'] else 'N'}"
                f" | {r['total_travel_min']}"
                f" | **{r['verdict']}** | {notes_str} |\n"
            )
        f.write("\n")

        f.write("<details><summary>코스 흐름 상세</summary>\n\n")
        for r in region_rows:
            cluster_str = f" [{r['city_cluster']}]" if r["city_cluster"] else ""
            f.write(f"**{r['option_label']} Trial{r['trial']}**"
                    f"  anchor={r['anchor_name']}{cluster_str}\n\n")
            f.write(f"> {r['flow'] or '—'}\n\n")
        f.write("</details>\n\n")

    f.write("---\n\n## 종합 요약\n\n")
    f.write(f"| 판정 | 건수 | 비율 |\n|------|------|------|\n")
    for v in ("PASS", "WEAK", "FAIL"):
        pct = counts[v] / total * 100 if total else 0
        f.write(f"| {v} | {counts[v]} | {pct:.0f}% |\n")
    f.write("\n")

    fail_rows = [r for r in rows if r["verdict"] == "FAIL"]
    weak_rows = [r for r in rows if r["verdict"] == "WEAK"]

    if fail_rows:
        f.write("### FAIL 케이스\n\n")
        for r in fail_rows:
            f.write(f"- **{r['region_label']} / {r['option_label']} Trial{r['trial']}**: "
                    f"{'; '.join(r['notes'])}\n")
        f.write("\n")

    if weak_rows:
        f.write("### WEAK 케이스\n\n")
        for r in weak_rows:
            f.write(f"- **{r['region_label']} / {r['option_label']} Trial{r['trial']}**: "
                    f"{'; '.join(r['notes'])}\n")
        f.write("\n")


# ── 콘솔 요약 ────────────────────────────────────────────────────────────────

def _print_summary(rows: list[dict]) -> None:
    counts = {"PASS": 0, "WEAK": 0, "FAIL": 0}
    for r in rows:
        counts[r["verdict"]] += 1
    total = len(rows)
    sep = "─" * 64

    print(f"\n{sep}")
    print(f"  QA 종합  PASS={counts['PASS']}  WEAK={counts['WEAK']}  FAIL={counts['FAIL']}  / {total}건")
    print(sep)

    non_pass = [r for r in rows if r["verdict"] != "PASS"]
    if non_pass:
        for r in non_pass:
            notes_str = "; ".join(r["notes"]) if r["notes"] else ""
            cluster   = f" [{r['city_cluster']}]" if r["city_cluster"] else ""
            print(f"  [{r['verdict']}] {r['region_label']} / {r['option_label']}"
                  f" Trial{r['trial']}{cluster}  {notes_str}")
    else:
        print("  전 케이스 PASS")
    print(sep)


# ── 메인 ─────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="코스 생성 QA — 전지역 자동 리포트")
    p.add_argument(
        "--repeat", type=int, default=3,
        help="각 지역×옵션 조합 반복 횟수 (기본: 3)",
    )
    return p.parse_args()


def main() -> None:
    args   = _parse_args()
    trials = args.repeat
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = Path("qa_reports")
    outdir.mkdir(exist_ok=True)

    print("DB에서 테스트 지역 목록 조회 중...", flush=True)
    region_configs = _load_region_configs()
    print(f"  → {len(region_configs)}개 지역 확인: "
          f"{', '.join(rc['label'] for rc in region_configs)}\n", flush=True)

    total    = len(region_configs) * len(OPTION_CONFIGS) * trials
    all_rows: list[dict] = []
    done     = 0

    for rc in region_configs:
        for oc in OPTION_CONFIGS:
            for t in range(1, trials + 1):
                done += 1
                label = (f"[{done:3d}/{total}]"
                         f" {rc['label']:6s} / {oc['label']:6s} Trial{t}")
                print(f"{label} ...", end=" ", flush=True)

                try:
                    row = run_one(rc, oc, t)
                except Exception as exc:
                    row = _error_row(rc, oc, t, str(exc))

                all_rows.append(row)
                cluster = f" [{row['city_cluster']}]" if row["city_cluster"] else ""
                print(f"{row['verdict']:4s}  {row['place_count']}장소  "
                      f"anchor={row['anchor_name']}{cluster}")

    # ── JSON 저장 ────────────────────────────────────────────────────────────
    json_path = outdir / f"qa_all_regions_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at":   ts,
                "total":          total,
                "trials":         trials,
                "region_count":   len(region_configs),
                "regions":        [rc["label"] for rc in region_configs],
                "results":        all_rows,
            },
            f, ensure_ascii=False, indent=2,
        )

    # ── Markdown 저장 ────────────────────────────────────────────────────────
    md_path = outdir / f"qa_all_regions_{ts}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        _write_md(f, all_rows, ts, trials)

    print(f"\n저장 완료:")
    print(f"  JSON → {json_path}")
    print(f"  MD   → {md_path}")

    _print_summary(all_rows)


if __name__ == "__main__":
    main()
