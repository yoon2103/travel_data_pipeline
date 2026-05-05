"""
diag_taeahn.py — 태안/안면도 코스 생성 파이프라인 진단 트레이서
DEBUG 플래그 기반 — 운영 코드 무수정, 이 파일만 실행

실행: python diag_taeahn.py
"""
import os, sys, math, logging, random
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))

import psycopg2, psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# ── DEBUG 제어 플래그 ─────────────────────────────────
DEBUG_CANDIDATE_POOL  = True   # fetch 후 후보 풀 전체 로그
DEBUG_HARD_FILTER     = True   # is_unsuitable 등 하드 필터 탈락 로그
DEBUG_SCORING         = True   # 장소별 세부 점수 로그
DEBUG_TARGET_FOCUS    = True   # GOOD/BAD 타겟 집중 추적
DEBUG_ANCHOR          = True   # 앵커 선택 상세 로그
# ─────────────────────────────────────────────────────

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s | %(message)s")
log = logging.getLogger("DIAG")

# ── 진단 대상 장소 목록 ───────────────────────────────
GOOD_TARGETS = {"백사장항", "안면암", "꽃지해수욕장", "안면도수목원", "안면암(태안)",
                "간월도마을", "간월도 해양경관 탐방로", "간월도 어리굴젓 기념탑"}
BAD_TARGETS  = {"어촌계", "펜션", "리조트", "온천", "사우나", "찜질"}

def _is_bad(name: str) -> bool:
    return any(kw in name for kw in BAD_TARGETS)

def _is_good(name: str) -> bool:
    return name in GOOD_TARGETS or any(g in name for g in GOOD_TARGETS)

# ── DB 연결 ──────────────────────────────────────────
conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 5432)),
    dbname=os.getenv("DB_NAME", "travel_db"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", ""),
)

# ── 운영 모듈 임포트 (패치 전) ──────────────────────────
from course_builder import (
    _fetch_candidates, _score, _select_anchor, _is_unsuitable_spot,
    _slot_db_name, _haversine, _weighted_choice, _pop_base,
    _get_city_type, _resolve_theme_slots,
    MOBILITY_PROFILE, URBAN_STEP_TRAVEL, WEIGHTS_DEFAULT,
    DIVERSITY_TOP_K, _SPOT_UNSUITABLE_PATTERNS,
)
from tourism_belt import get_belt_info, TOURISM_BELT
from enrichment_service import is_institutional

# ── 시뮬레이션 요청 파라미터 ────────────────────────────
# 태안읍 anchor 기준 (태안읍 중심 추정 좌표)
REQUEST = {
    "region":             "충남",
    "companion":          "",
    "themes":             [],           # 기본 테마 없음
    "template":           "standard",
    "start_time":         "오늘 10:00",
    "region_travel_type": "urban",
    "zone_center":        (36.7453, 126.2981),   # 태안읍 추정 중심
    "zone_radius_km":     None,
    "walk_max_radius":    18,           # "조금 멀어도 좋아요"
}

# ─────────────────────────────────────────────────────
def fmt(v, w=8): return f"{v:{w}.4f}" if isinstance(v, float) else str(v)

def run_diagnostic():
    region      = REQUEST["region"]
    themes      = REQUEST.get("themes", [])
    companion   = REQUEST.get("companion", "")
    template    = REQUEST.get("template", "standard")
    start_time  = REQUEST.get("start_time")
    zone_center = REQUEST.get("zone_center")
    zone_radius_km = REQUEST.get("zone_radius_km")
    walk_max_radius = REQUEST.get("walk_max_radius")
    city_type   = _get_city_type(region)

    mob = MOBILITY_PROFILE[city_type]
    if walk_max_radius is not None:
        r = float(walk_max_radius)
        eff_max_radius = r
        eff_max_travel = URBAN_STEP_TRAVEL.get(int(r), mob["max_travel"])
    else:
        eff_max_radius = mob["max_radius"]
        eff_max_travel = mob["max_travel"]

    if zone_center and not zone_radius_km:
        pre_filter_r = min(max(eff_max_radius * 3.0, 30.0), 60.0)
    else:
        pre_filter_r = None

    pop = _pop_base(conn, region)
    weights = WEIGHTS_DEFAULT

    print("\n" + "="*70)
    print(f"  DIAGNOSTIC: region={region}  city_type={city_type}")
    print(f"  eff_max_radius={eff_max_radius}km  eff_max_travel={eff_max_travel}min")
    print(f"  pre_filter_r={pre_filter_r}km  pop_base={pop:.1f}")
    print(f"  zone_center={zone_center}")
    print("="*70)

    # ── STEP 1: 앵커 선택 ───────────────────────────────
    slots = _resolve_theme_slots(template, themes, start_time, REQUEST, city_type)
    first_role = slots[0][1]
    print(f"\n[ANCHOR] 첫 슬롯 role={first_role}  slot={slots[0][0]}")

    anchor = _select_anchor(conn, region, themes, first_role,
                            zone_center=zone_center, zone_radius_km=zone_radius_km)
    if anchor is None:
        print("[ANCHOR] ★ FAIL: 앵커 선택 실패")
        return

    belt_b, belt_seed = get_belt_info(region, anchor["name"], anchor["latitude"], anchor["longitude"])
    print(f"[ANCHOR] 선택됨: [{anchor['place_id']}] {anchor['name']}")
    print(f"         lat={anchor['latitude']:.4f}  lon={anchor['longitude']:.4f}")
    print(f"         view_count={anchor['view_count']}  ai_tags={anchor['ai_tags']}")
    print(f"         belt_boost={belt_b:.4f}  matched_seed={belt_seed}")
    if _is_good(anchor["name"]):
        print(f"         ★ GOOD TARGET 앵커!")
    elif _is_bad(anchor["name"]):
        print(f"         ✗ BAD TARGET 앵커 선택됨!")

    prev_coord = (anchor["latitude"], anchor["longitude"])
    prev_role  = anchor["visit_role"]
    selected_names = [anchor["name"]]

    # ── STEP 2: 슬롯별 후보 파이프라인 추적 ─────────────
    for slot, role in slots[1:]:
        role_str = role if isinstance(role, str) else (role[0] if role else "")
        print(f"\n{'─'*60}")
        print(f"[SLOT] {slot}  role={role}")
        print(f"       prev_coord={prev_coord}  prev_role={prev_role}")

        # ── fetch ───────────────────────────────────────
        candidates = _fetch_candidates(
            conn, region, role, slot,
            zone_center=zone_center, zone_radius_km=zone_radius_km,
            relax_slot=False, themes=themes,
            pre_filter_radius_km=pre_filter_r,
        )
        if DEBUG_CANDIDATE_POOL:
            print(f"\n  [POOL] fetch 반환 {len(candidates)}건")
            good_in_pool = [p["name"] for p in candidates if _is_good(p["name"])]
            bad_in_pool  = [p["name"] for p in candidates if _is_bad(p["name"])]
            print(f"  [POOL] GOOD 포함({len(good_in_pool)}): {good_in_pool}")
            print(f"  [POOL] BAD  포함({len(bad_in_pool)}): {bad_in_pool}")

            # GOOD 타겟이 풀에 없는 이유 추적
            for gt in GOOD_TARGETS:
                if not any(gt in p["name"] for p in candidates):
                    # 전체 DB에서 해당 이름 검색해 왜 빠졌는지 확인
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
                        c.execute("""SELECT place_id, name, latitude, longitude, view_count,
                                            visit_time_slot, is_active, category_id
                                     FROM places WHERE region_1=%s AND name ILIKE %s""",
                                  (region, f"%{gt}%"))
                        rows = c.fetchall()
                    if rows:
                        for r in rows:
                            dist = _haversine(prev_coord[0], prev_coord[1],
                                              r["latitude"] or 0, r["longitude"] or 0) if r["latitude"] else 999
                            slot_ok = _slot_db_name(slot) in (r["visit_time_slot"] or [])
                            in_30km = dist <= (pre_filter_r or 999)
                            print(f"  [MISS] {r['name']} id={r['place_id']}"
                                  f" view={r['view_count']} dist={dist:.1f}km"
                                  f" slot_ok={slot_ok} in_30km={in_30km}"
                                  f" active={r['is_active']} cat={r['category_id']}"
                                  f"  → POOL에서 누락됨(LIMIT 50 초과 또는 필터)")

        # ── 하드 필터 ────────────────────────────────────
        if role_str in ("spot", "culture") or (isinstance(role, list) and
                any(r in {"spot","culture"} for r in role)):
            pre = len(candidates)
            if DEBUG_HARD_FILTER:
                for p in candidates:
                    if _is_unsuitable_spot(p.get("name","")):
                        print(f"  [HF-UNSUITABLE] 제거: {p['name']}")
            candidates = [p for p in candidates if not _is_unsuitable_spot(p.get("name",""))]
            if DEBUG_HARD_FILTER and pre != len(candidates):
                print(f"  [HF] unsuitable 필터: {pre}→{len(candidates)}건")

            # BAD 타겟 중 필터 통과한 것 (현재 패턴에서 잡지 못하는 것)
            if DEBUG_HARD_FILTER:
                still_bad = [p["name"] for p in candidates if _is_bad(p["name"])]
                if still_bad:
                    print(f"  [HF-WARN] 현재 패턴으로 걸러지지 않은 BAD 후보: {still_bad}")

        # ── 스코어링 ─────────────────────────────────────
        scored = []
        allow_same_role = False
        for p in candidates:
            if p["place_id"] in {a["place_id"] for a in [anchor]}:
                continue

            result = _score(p, prev_coord, themes, companion, slot, pop,
                            max_radius_km=eff_max_radius, max_travel_min=eff_max_travel,
                            relax_slot=False, weights=weights)

            belt_b, belt_seed = get_belt_info(region, p["name"], p["latitude"], p["longitude"])
            is_good_p = _is_good(p["name"])
            is_bad_p  = _is_bad(p["name"])

            if result is None:
                # 하드 필터 탈락 사유 분석
                if DEBUG_SCORING and (is_good_p or is_bad_p):
                    dist_km = _haversine(prev_coord[0], prev_coord[1],
                                         p["latitude"], p["longitude"])
                    sf_val  = 1.0 if _slot_db_name(slot) in (p["visit_time_slot"] or []) else 0.0
                    reason  = ("dist_exceed" if dist_km > eff_max_radius else
                               "slot_mismatch" if sf_val == 0.0 else "travel_exceed")
                    marker  = "★GOOD" if is_good_p else "✗BAD"
                    print(f"  [FILTERED] {marker} {p['name'][:24]:<24}"
                          f" dist={dist_km:.1f}km slot_ok={sf_val>0}"
                          f" reason={reason} belt={belt_b:.3f}")
                continue

            s, travel_min, dist_km, components = result
            if belt_b > 0:
                s += belt_b
                components = {**components, "belt_boost": round(belt_b,4),
                               "matched_seed": belt_seed}

            scored.append((s, travel_min, dist_km, components, p))

            if DEBUG_SCORING and (is_good_p or is_bad_p):
                marker = "★GOOD" if is_good_p else "✗BAD"
                print(f"  [SCORED] {marker} {p['name'][:24]:<24}"
                      f" total={s:.4f} tf={components['travel_fit']:.3f}"
                      f" tm={components['theme_match']:.3f}"
                      f" pop={components['popularity_score']:.3f}"
                      f" belt={belt_b:.3f} dist={dist_km:.1f}km")

        # ── 최종 선택 ────────────────────────────────────
        if not scored:
            print(f"  [SELECT] ✗ 후보 없음 — 슬롯 스킵")
            continue

        scored.sort(key=lambda x: x[0], reverse=True)
        top5 = scored[:DIVERSITY_TOP_K]

        print(f"\n  [TOP-5 후보]")
        for i, (s, tm, dk, comp, p) in enumerate(top5):
            belt_b = comp.get("belt_boost", 0.0)
            marker = "★" if _is_good(p["name"]) else ("✗" if _is_bad(p["name"]) else " ")
            print(f"    #{i+1} {marker} [{p['place_id']}] {p['name'][:24]:<24}"
                  f" score={s:.4f} tf={comp['travel_fit']:.3f}"
                  f" pop={comp['popularity_score']:.3f}"
                  f" belt={belt_b:.3f} dist={dk:.1f}km")

        _, travel_min, dist_km, components, chosen = _weighted_choice(scored, DIVERSITY_TOP_K)
        belt_b = components.get("belt_boost", 0.0)
        marker = "★GOOD" if _is_good(chosen["name"]) else ("✗BAD" if _is_bad(chosen["name"]) else "OK ")
        print(f"\n  [SELECTED] {marker} [{chosen['place_id']}] {chosen['name']}"
              f"  score={components['final_score']:.4f}  belt={belt_b:.3f}"
              f"  dist={dist_km:.1f}km  travel={travel_min}min")

        prev_coord = (chosen["latitude"], chosen["longitude"])
        prev_role  = chosen["visit_role"]
        selected_names.append(chosen["name"])

    # ── 최종 결과 요약 ────────────────────────────────────
    print("\n" + "="*70)
    print("  FINAL COURSE SUMMARY")
    print("="*70)
    for i, n in enumerate(selected_names, 1):
        marker = "★" if _is_good(n) else ("✗" if _is_bad(n) else " ")
        print(f"  {i}. {marker} {n}")

    # ── 벨트 시드 중 DB 미진입 확인 ──────────────────────
    print("\n[BELT SEEDS IN DB CHECK]")
    belt_seeds = TOURISM_BELT.get(region, [])
    for seed in belt_seeds:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute("SELECT place_id, name, view_count, ai_tags FROM places "
                      "WHERE region_1=%s AND name ILIKE %s AND is_active=TRUE",
                      (region, f"%{seed['name']}%"))
            rows = c.fetchall()
        if rows:
            for r in rows:
                print(f"  OK  [{r['place_id']}] {r['name']} view={r['view_count']} tags={r['ai_tags']}")
        else:
            print(f"  MISS  '{seed['name']}' — DB에 없음")

    # ── POOL 누락 통계 요약 ──────────────────────────────
    print("\n[POOL MISS SUMMARY — 30km LIMIT 50 기준]")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
        c.execute("""
            SELECT COUNT(*) as cnt
            FROM places
            WHERE region_1=%s AND category_id IN (12,14,39)
              AND visit_role=ANY(%s) AND is_active=TRUE AND latitude IS NOT NULL
              AND (6371.0*2*ASIN(SQRT(
                  POWER(SIN((RADIANS(latitude)-RADIANS(%s))/2),2)+
                  COS(RADIANS(%s))*COS(RADIANS(latitude))*
                  POWER(SIN((RADIANS(longitude)-RADIANS(%s))/2),2)
              ))) <= %s
        """, (region, ["spot","culture"],
              REQUEST["zone_center"][0], REQUEST["zone_center"][0],
              REQUEST["zone_center"][1], pre_filter_r or 30.0))
        total_in_range = c.fetchone()["cnt"]
    print(f"  30km 반경 내 전체: {total_in_range}건")
    print(f"  LIMIT 50 적용 시 노출: 50건 ({50/total_in_range*100:.1f}%)")
    print(f"  누락: {total_in_range - 50}건 ({(total_in_range-50)/total_in_range*100:.1f}%)")
    print(f"  → 꽃지(rank≈125), 백사장항(rank≈262), 안면암(rank≈446) 모두 LIMIT 50 초과")


if __name__ == "__main__":
    try:
        run_diagnostic()
    finally:
        conn.close()
