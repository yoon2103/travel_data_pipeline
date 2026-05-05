"""
run_integration_test.py — 서비스 흐름 자동 통합 테스트

POST http://localhost:8000/api/course/generate 를 직접 호출해
백엔드 응답 품질과 프론트 표시 가능 필드를 검증한다.

실행:
    python run_integration_test.py [--repeat N] [--base-url URL]
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------

FULL_REGIONS    = ["서울", "부산", "대구", "광주", "세종", "울산", "경북", "충남", "제주", "대전", "전북", "강원"]
LIMITED_REGIONS = ["경기", "인천", "전남"]
BLOCKED_REGIONS = ["경남", "충북"]
ALL_REGIONS     = FULL_REGIONS + LIMITED_REGIONS + BLOCKED_REGIONS

CITY_MODE_REGIONS = {"서울"}

OPTIONS = [
    {"label": "기본",    "themes": []},
    {"label": "카페투어", "themes": ["cafe"]},
    {"label": "자연/힐링","themes": ["nature"]},
    {"label": "맛집",    "themes": ["food"]},
]

# 내부 role 노출 패턴 — description / option_notice에 포함되면 FAIL
_ROLE_LEAK_PATTERNS = [
    r"\bspot\s*장소",
    r"\bcafe\s*장소",
    r"\bmeal\s*장소",
    r"\bculture\s*장소",
    r"visit_role",
    r"selection_basis",
]

_BLOCKED_KEYWORDS = ["추천 코스를 제공하기 어렵", "NO_COURSE", "BLOCKED"]


# ---------------------------------------------------------------------------
# HTTP 호출
# ---------------------------------------------------------------------------

def _post(url: str, payload: dict, timeout: int = 30) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req  = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except Exception:
            return {"error": f"HTTP {e.code}: {raw[:200]}", "places": []}
    except Exception as exc:
        return {"error": str(exc), "places": []}


# ---------------------------------------------------------------------------
# 검증 함수
# ---------------------------------------------------------------------------

def _has_role_leak(text: str | None) -> str | None:
    """role 내부 문구가 노출되면 해당 패턴 반환, 없으면 None."""
    if not text:
        return None
    for pat in _ROLE_LEAK_PATTERNS:
        if re.search(pat, text):
            return pat
    return None


def _is_blocked_response(data: dict) -> bool:
    err = data.get("error", "") or ""
    code = data.get("error_code", "") or ""
    return (
        not data.get("places")
        and (
            any(kw in err for kw in _BLOCKED_KEYWORDS)
            or any(kw in code for kw in _BLOCKED_KEYWORDS)
        )
    )


def _count_roles(places: list) -> dict:
    counts = {"cafe": 0, "meal": 0, "spot": 0, "culture": 0, "other": 0}
    for p in places:
        role = p.get("visit_role", "other")
        counts[role] = counts.get(role, 0) + 1
    return counts


def _check_duplicate_ids(places: list) -> list:
    seen, dups = set(), []
    for p in places:
        pid = p.get("place_id")
        if pid in seen:
            dups.append(pid)
        seen.add(pid)
    return dups


def _check_blocked(region: str, data: dict) -> dict:
    """BLOCKED 지역 검증 — places=[], error 반환 여부 확인."""
    issues = []
    notes  = []

    places = data.get("places", [])
    error  = data.get("error")

    if places:
        issues.append(f"BLOCKED 지역인데 places={len(places)}개 반환됨")

    if error:
        notes.append(f"error={error!r}")
        # 원래 BLOCKED 메시지 대신 fallback 에러가 왔는지 체크
        if "NO_COURSE" in (data.get("error_code") or ""):
            notes.append("[경고] BLOCKED 메시지 유실 — fallback 에러로 대체됨 (서버 분기 버그)")
    else:
        if not places:
            issues.append("error 필드도 없고 places도 없음 — 응답 형식 불명확")

    verdict = "FAIL" if issues else "PASS"
    return {"verdict": verdict, "issues": issues, "notes": notes}


def _check_normal(region: str, option: dict, data: dict, service_level: str) -> dict:
    """FULL / LIMITED 지역 검증."""
    themes  = option["themes"]
    label   = option["label"]
    places  = data.get("places", [])
    n       = len(places)
    issues  = []
    warnings = []
    notes   = []

    # ── 에러 응답 ────────────────────────────────────────────────────────────
    if data.get("error"):
        return {
            "verdict": "FAIL",
            "issues":  [f"error 반환: {data['error']!r}"],
            "warnings": [],
            "notes":   [],
        }

    # ── 장소 수 ──────────────────────────────────────────────────────────────
    if n < 4:
        issues.append(f"places={n} (기준 4개 미만)")
    elif n == 4:
        if not data.get("missing_slot_reason") and not data.get("option_notice"):
            warnings.append("places=4이지만 missing_slot_reason/option_notice 둘 다 없음")

    # ── description ──────────────────────────────────────────────────────────
    desc = data.get("description")
    if not desc:
        issues.append("description 없음")
    else:
        leak = _has_role_leak(desc)
        if leak:
            issues.append(f"description에 내부 role 문구 노출: {leak}")

    # ── option_notice ────────────────────────────────────────────────────────
    opt_notice = data.get("option_notice")
    if opt_notice:
        leak = _has_role_leak(opt_notice)
        if leak:
            issues.append(f"option_notice에 내부 role 문구 노출: {leak}")
    else:
        if service_level == "LIMITED":
            issues.append("LIMITED 지역 option_notice 없음 — 사용자 안내 누락")

    # ── 중복 place_id ────────────────────────────────────────────────────────
    dups = _check_duplicate_ids(places)
    if dups:
        issues.append(f"중복 place_id: {dups}")

    # ── 역할 비율 검증 ────────────────────────────────────────────────────────
    if n >= 4:
        roles = _count_roles(places)
        is_city = region in CITY_MODE_REGIONS

        if "cafe" in themes:
            cafe_min = 3 if is_city else 2
            if roles["cafe"] < cafe_min:
                if opt_notice:
                    notes.append(f"cafe={roles['cafe']} < {cafe_min} (option_notice로 안내됨)")
                else:
                    warnings.append(f"카페투어인데 cafe={roles['cafe']} < {cafe_min}")

        if "food" in themes:
            meal_min = 2 if is_city else 1
            if roles["meal"] < meal_min:
                issues.append(f"맛집 테마인데 meal={roles['meal']} < {meal_min}")

        if "nature" in themes:
            spot_culture = roles["spot"] + roles["culture"]
            if spot_culture < 2:
                if n <= 3:
                    issues.append(f"자연/힐링 코스 {n}개 이하 + spot/culture={spot_culture} < 2")
                else:
                    warnings.append(f"자연/힐링인데 spot/culture={spot_culture} < 2")

    # ── 최종 판정 ─────────────────────────────────────────────────────────────
    if issues:
        verdict = "FAIL"
    elif warnings:
        verdict = "WEAK"
    else:
        verdict = "PASS"

    return {"verdict": verdict, "issues": issues, "warnings": warnings, "notes": notes}


# ---------------------------------------------------------------------------
# 메인 테스트 루프
# ---------------------------------------------------------------------------

def run_tests(base_url: str, repeat: int) -> dict:
    endpoint = f"{base_url}/api/course/generate"
    results  = []
    total    = (len(FULL_REGIONS) + len(LIMITED_REGIONS) + len(BLOCKED_REGIONS)) * len(OPTIONS) * repeat

    counters = {"PASS": 0, "WEAK": 0, "FAIL": 0}
    desc_missing     = []
    opt_notice_missing = []
    role_leak_list   = []
    blocked_results  = []

    idx = 0
    for region in ALL_REGIONS:
        if region in FULL_REGIONS:
            service_level = "FULL"
        elif region in LIMITED_REGIONS:
            service_level = "LIMITED"
        else:
            service_level = "BLOCKED"

        for opt in OPTIONS:
            for trial in range(1, repeat + 1):
                idx += 1
                label = opt["label"]
                themes = opt["themes"]

                payload = {
                    "region":         region,
                    "departure_time": "오늘 09:00",
                    "themes":         themes,
                    "template":       "standard",
                    "companion":      "",
                    "region_travel_type": "urban",
                }

                t0   = time.time()
                data = _post(endpoint, payload)
                elapsed = round(time.time() - t0, 2)

                places = data.get("places", [])
                n_places = len(places)
                anchor = data.get("anchor") or (places[0]["name"] if places else "—")

                if service_level == "BLOCKED":
                    check = _check_blocked(region, data)
                    verdict = check["verdict"]
                    issues  = check["issues"]
                    warnings = []
                    notes    = check["notes"]
                    blocked_results.append({
                        "region": region, "option": label, "trial": trial,
                        "verdict": verdict, "issues": issues, "notes": notes,
                        "error": data.get("error"), "error_code": data.get("error_code"),
                        "places_count": n_places,
                    })
                else:
                    check    = _check_normal(region, opt, data, service_level)
                    verdict  = check["verdict"]
                    issues   = check["issues"]
                    warnings = check.get("warnings", [])
                    notes    = check.get("notes", [])

                    # description 누락 수집
                    if not data.get("description") and not data.get("error"):
                        desc_missing.append({"region": region, "option": label, "trial": trial})

                    # option_notice 누락 수집 (LIMITED만)
                    if service_level == "LIMITED" and not data.get("option_notice") and not data.get("error"):
                        opt_notice_missing.append({"region": region, "option": label, "trial": trial})

                    # role leak 수집
                    for field in ["description", "option_notice", "missing_slot_reason"]:
                        leak = _has_role_leak(data.get(field))
                        if leak:
                            role_leak_list.append({
                                "region": region, "option": label, "trial": trial,
                                "field": field, "pattern": leak, "value": data.get(field),
                            })

                counters[verdict] += 1

                row = {
                    "idx":           idx,
                    "region":        region,
                    "service_level": service_level,
                    "option":        label,
                    "trial":         trial,
                    "verdict":       verdict,
                    "places_count":  n_places,
                    "anchor":        anchor,
                    "description":   bool(data.get("description")),
                    "option_notice": data.get("option_notice"),
                    "missing_slot_reason": data.get("missing_slot_reason"),
                    "issues":        issues,
                    "warnings":      warnings,
                    "notes":         notes,
                    "elapsed_s":     elapsed,
                }
                results.append(row)

                status_str = f"[{idx:>3}/{total}] {region:<6} / {label:<6} Trial{trial} ... {verdict:<4}  {n_places}장소  {elapsed}s"
                print(status_str)
                sys.stdout.flush()

    return {
        "results":           results,
        "counters":          counters,
        "desc_missing":      desc_missing,
        "opt_notice_missing": opt_notice_missing,
        "role_leak_list":    role_leak_list,
        "blocked_results":   blocked_results,
    }


# ---------------------------------------------------------------------------
# 리포트 생성
# ---------------------------------------------------------------------------

def _region_summary(results: list) -> dict:
    summary = {}
    for r in results:
        key = r["region"]
        if key not in summary:
            summary[key] = {"PASS": 0, "WEAK": 0, "FAIL": 0, "service_level": r["service_level"]}
        summary[key][r["verdict"]] += 1
    return summary


def _write_json(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _write_md(path: str, data: dict, ts: str, repeat: int):
    counters     = data["counters"]
    results      = data["results"]
    region_sum   = _region_summary(results)
    blocked      = data["blocked_results"]
    desc_missing = data["desc_missing"]
    opt_missing  = data["opt_notice_missing"]
    role_leaks   = data["role_leak_list"]

    fails = [r for r in results if r["verdict"] == "FAIL" and r["service_level"] != "BLOCKED"]
    weaks = [r for r in results if r["verdict"] == "WEAK"]

    lines = [
        f"# 서비스 흐름 통합 테스트  {ts}",
        "",
        f"> repeat={repeat}  /  총 {len(results)}건",
        "",
        "---",
        "",
        "## 종합",
        "",
        f"| 판정 | 건수 |",
        f"|------|------|",
        f"| PASS | {counters['PASS']} |",
        f"| WEAK | {counters['WEAK']} |",
        f"| FAIL | {counters['FAIL']} |",
        "",
        "---",
        "",
        "## 지역별 PASS / WEAK / FAIL",
        "",
        "| 지역 | 레벨 | PASS | WEAK | FAIL |",
        "|------|------|------|------|------|",
    ]
    for region in ALL_REGIONS:
        s = region_sum.get(region, {"PASS": 0, "WEAK": 0, "FAIL": 0, "service_level": "?"})
        lines.append(f"| {region} | {s['service_level']} | {s['PASS']} | {s['WEAK']} | {s['FAIL']} |")

    lines += [
        "",
        "---",
        "",
        "## FAIL 상세 (FULL/LIMITED 지역)",
        "",
    ]
    if fails:
        for r in fails:
            lines.append(f"- **[{r['region']} / {r['option']} Trial{r['trial']}]**  "
                         f"places={r['places_count']}  anchor={r['anchor']}")
            for iss in r["issues"]:
                lines.append(f"  - {iss}")
    else:
        lines.append("없음")

    lines += ["", "---", "", "## WEAK 상세", ""]
    if weaks:
        for r in weaks:
            lines.append(f"- [{r['region']} / {r['option']} Trial{r['trial']}]  "
                         f"places={r['places_count']}")
            for w in r["warnings"]:
                lines.append(f"  - {w}")
    else:
        lines.append("없음")

    lines += ["", "---", "", "## description 누락", ""]
    if desc_missing:
        for d in desc_missing:
            lines.append(f"- {d['region']} / {d['option']} Trial{d['trial']}")
    else:
        lines.append("없음")

    lines += ["", "---", "", "## option_notice 누락 (LIMITED 지역)", ""]
    if opt_missing:
        for d in opt_missing:
            lines.append(f"- {d['region']} / {d['option']} Trial{d['trial']}")
    else:
        lines.append("없음")

    lines += ["", "---", "", "## 내부 role 문구 노출", ""]
    if role_leaks:
        for d in role_leaks:
            lines.append(f"- {d['region']} / {d['option']} Trial{d['trial']}  "
                         f"field={d['field']}  pattern={d['pattern']}")
            lines.append(f"  - 값: {d['value']!r}")
    else:
        lines.append("없음")

    lines += ["", "---", "", "## BLOCKED 지역 처리 결과", ""]
    if blocked:
        for b in blocked:
            lines.append(f"- **{b['region']} / {b['option']} Trial{b['trial']}**  "
                         f"verdict={b['verdict']}  places={b['places_count']}")
            if b.get("error"):
                lines.append(f"  - error: {b['error']!r}")
            if b.get("error_code"):
                lines.append(f"  - error_code: {b['error_code']!r}")
            for iss in b.get("issues", []):
                lines.append(f"  - [FAIL] {iss}")
            for note in b.get("notes", []):
                lines.append(f"  - [주의] {note}")
    else:
        lines.append("없음")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat",   type=int, default=3, help="지역+옵션별 반복 횟수 (기본 3)")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000", help="백엔드 base URL")
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = "qa_reports"

    total_cases = (len(FULL_REGIONS) + len(LIMITED_REGIONS) + len(BLOCKED_REGIONS)) * len(OPTIONS) * args.repeat
    print(f"통합 테스트 시작: {total_cases}건 ({args.repeat}회 반복) → {args.base_url}")
    print()

    data = run_tests(args.base_url, args.repeat)

    json_path = f"{out_dir}/integration_service_flow_{ts}.json"
    md_path   = f"{out_dir}/integration_service_flow_{ts}.md"

    _write_json(json_path, data)
    _write_md(md_path, data, ts, args.repeat)

    c = data["counters"]
    print()
    print(f"저장 완료:")
    print(f"  JSON → {json_path}")
    print(f"  MD   → {md_path}")
    print()
    print("─" * 64)
    print(f"  통합 테스트  PASS={c['PASS']}  WEAK={c['WEAK']}  FAIL={c['FAIL']}  / {total_cases}건")
    print("─" * 64)

    # 핵심 이슈 요약
    fails  = [r for r in data["results"] if r["verdict"] == "FAIL" and r["service_level"] != "BLOCKED"]
    weaks  = [r for r in data["results"] if r["verdict"] == "WEAK"]
    leaks  = data["role_leak_list"]
    opt_m  = data["opt_notice_missing"]

    if fails:
        print(f"\n  [FAIL 상세 - {len(fails)}건]")
        for r in fails:
            print(f"  {r['region']} / {r['option']} Trial{r['trial']}  places={r['places_count']}")
            for iss in r["issues"]:
                print(f"    -> {iss}")

    if weaks:
        print(f"\n  [WEAK 상세 - {len(weaks)}건]")
        for r in weaks:
            print(f"  {r['region']} / {r['option']} Trial{r['trial']}  places={r['places_count']}")
            for w in r["warnings"]:
                print(f"    -> {w}")

    if leaks:
        print(f"\n  [role 문구 노출 - {len(leaks)}건]")
        for d in leaks:
            print(f"  {d['region']} / {d['option']} field={d['field']}")

    if opt_m:
        print(f"\n  [LIMITED 지역 option_notice 누락 - {len(opt_m)}건]")
        for d in opt_m:
            print(f"  {d['region']} / {d['option']} Trial{d['trial']}")

    # BLOCKED 지역 경고 요약
    blocked_issues = [b for b in data["blocked_results"] if b["verdict"] == "FAIL"]
    blocked_notes  = [b for b in data["blocked_results"] if b.get("notes")]
    if blocked_issues:
        print(f"\n  [BLOCKED 지역 FAIL — {len(blocked_issues)}건]")
        for b in blocked_issues:
            print(f"  {b['region']} / {b['option']} : {b['issues']}")
    if blocked_notes:
        # 중복 제거: 동일 지역+옵션 조합의 첫 번째만 출력
        seen_blocked = set()
        for b in blocked_notes:
            key = (b["region"], b["option"])
            if key not in seen_blocked:
                seen_blocked.add(key)
                for note in b["notes"]:
                    print(f"  [BLOCKED 주의] {b['region']} / {b['option']}: {note}")

    print("─" * 64)


if __name__ == "__main__":
    main()
