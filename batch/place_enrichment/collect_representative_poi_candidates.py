from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

import psycopg2.extras
from dotenv import load_dotenv

import db_client


load_dotenv()

KAKAO_LOCAL_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
NAVER_LOCAL_SEARCH_URL = "https://openapi.naver.com/v1/search/local.json"
TOURAPI_BASE_URL = "https://apis.data.go.kr/B551011/KorService2"


TOP20_TARGETS = [
    {"expected_poi_name": "경포대", "region_1": "강원", "region_label": "강릉/강원", "priority": 1},
    {"expected_poi_name": "오죽헌", "region_1": "강원", "region_label": "강릉/강원", "priority": 2},
    {"expected_poi_name": "선교장", "region_1": "강원", "region_label": "강릉/강원", "priority": 3},
    {"expected_poi_name": "불국사", "region_1": "경북", "region_label": "경주", "priority": 4},
    {"expected_poi_name": "국립경주박물관", "region_1": "경북", "region_label": "경주", "priority": 5},
    {"expected_poi_name": "간월암", "region_1": "충남", "region_label": "충남/태안", "priority": 6},
    {"expected_poi_name": "성산일출봉", "region_1": "제주", "region_label": "제주", "priority": 7},
    {"expected_poi_name": "전주한옥마을", "region_1": "전북", "region_label": "전주", "priority": 8},
    {"expected_poi_name": "한라산", "region_1": "제주", "region_label": "제주", "priority": 9},
    {"expected_poi_name": "오동도", "region_1": "전남", "region_label": "여수", "priority": 10},
    {"expected_poi_name": "향일암", "region_1": "전남", "region_label": "여수", "priority": 11},
    {"expected_poi_name": "전동성당", "region_1": "전북", "region_label": "전주", "priority": 12},
    {"expected_poi_name": "천마총(대릉원)", "region_1": "경북", "region_label": "경주", "priority": 13},
    {"expected_poi_name": "여수 해상케이블카", "region_1": "전남", "region_label": "여수", "priority": 14},
    {"expected_poi_name": "오목대", "region_1": "전북", "region_label": "전주", "priority": 15},
    {"expected_poi_name": "전주향교", "region_1": "전북", "region_label": "전주", "priority": 16},
    {"expected_poi_name": "안면암(태안)", "region_1": "충남", "region_label": "충남/태안", "priority": 17},
    {"expected_poi_name": "이순신광장", "region_1": "전남", "region_label": "여수", "priority": 18},
    {"expected_poi_name": "감천문화마을", "region_1": "부산", "region_label": "부산", "priority": 19},
    {"expected_poi_name": "태종대", "region_1": "부산", "region_label": "부산", "priority": 20},
]
CURRENT_WRITE_SCOPE_NAMES = {"경포대", "불국사", "성산일출봉", "전주한옥마을"}

SOURCE_TYPES = ("TOURAPI", "KAKAO", "NAVER")
RISK_KEYWORDS = {
    "광장": "REPRESENTATIVE_REVIEW_KEYWORD",
    "주차장": "PARKING_LOT_RISK",
    "호텔": "LODGING_RISK",
    "펜션": "LODGING_RISK",
    "모텔": "LODGING_RISK",
    "리조트": "LODGING_RISK",
    "마을": "VILLAGE_SCOPE_REVIEW",
    "서고": "INTERNAL_FACILITY_RISK",
    "도서관": "INTERNAL_FACILITY_RISK",
    "기념탑": "SUB_FACILITY_RISK",
    "탐방로": "TRAIL_SCOPE_REVIEW",
    "항": "PORT_SCOPE_REVIEW",
}
BAD_CATEGORY_KEYWORDS = (
    "숙박",
    "호텔",
    "펜션",
    "모텔",
    "음식",
    "음식점",
    "맛집",
    "카페",
    "식당",
    "한식",
    "생선회",
    "국수",
    "육류",
    "고기",
    "백반",
    "가정식",
    "전복",
    "치킨",
    "닭강정",
)
GOOD_CATEGORY_KEYWORDS = (
    "관광",
    "명소",
    "문화",
    "유적",
    "유산",
    "사찰",
    "공원",
    "해수욕장",
    "박물관",
    "전시",
    "여행",
    "자연",
)
REGION_ALIASES = {
    "강원": ("강원", "강원도", "강원특별자치도", "강릉", "속초"),
    "경북": ("경북", "경상북도", "경주"),
    "충남": ("충남", "충청남도", "태안", "서산"),
    "제주": ("제주", "제주도", "제주특별자치도", "서귀포"),
    "전북": ("전북", "전라북도", "전북특별자치도", "전주"),
    "전남": ("전남", "전라남도", "여수"),
    "부산": ("부산", "부산광역시"),
    "서울": ("서울", "서울특별시"),
}
TOURAPI_GOOD_CONTENT_TYPES = {"12", "14"}
TOURAPI_BAD_CONTENT_TYPES = {"32", "38", "39"}


@dataclass
class NormalizedRepresentativeCandidate:
    source_type: str
    source_place_id: str | None
    source_name: str
    category: str | None
    address: str | None
    road_address: str | None
    latitude: float | None
    longitude: float | None
    phone: str | None
    image_url: str | None
    overview: str | None
    source_payload: dict[str, Any]


def _normalize_name(value: str | None) -> str:
    text = value or ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[\s\-·().\[\],_/]", "", text)
    return text.lower()


def _strip_html(value: str | None) -> str:
    text = value or ""
    text = re.sub(r"<[^>]+>", "", text)
    return text.replace("&amp;", "&").strip()


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _naver_coord(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return int(value) / 10_000_000
    except (TypeError, ValueError):
        return None


def _request_json(url: str, headers: dict[str, str] | None = None, timeout: int = 8) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_kakao(target: dict[str, Any], limit: int) -> tuple[list[NormalizedRepresentativeCandidate], str | None]:
    api_key = os.getenv("KAKAO_REST_API_KEY")
    if not api_key:
        return [], "KAKAO_REST_API_KEY not set"
    query = f"{target['region_1']} {target['expected_poi_name']}"
    params = {"query": query, "size": min(max(limit, 1), 15)}
    url = KAKAO_LOCAL_SEARCH_URL + "?" + urllib.parse.urlencode(params)
    try:
        payload = _request_json(url, {"Authorization": f"KakaoAK {api_key}"})
    except Exception as exc:  # network/API errors must not stop the dry-run.
        return [], f"Kakao fetch failed: {exc}"
    rows = []
    for raw in payload.get("documents", []):
        rows.append(
            NormalizedRepresentativeCandidate(
                source_type="KAKAO",
                source_place_id=str(raw.get("id") or "") or None,
                source_name=(raw.get("place_name") or "").strip(),
                category=raw.get("category_name") or None,
                address=raw.get("address_name") or None,
                road_address=raw.get("road_address_name") or None,
                latitude=_to_float(raw.get("y")),
                longitude=_to_float(raw.get("x")),
                phone=raw.get("phone") or None,
                image_url=None,
                overview=None,
                source_payload=raw,
            )
        )
    return rows, None


def fetch_naver(target: dict[str, Any], limit: int) -> tuple[list[NormalizedRepresentativeCandidate], str | None]:
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        return [], "NAVER_CLIENT_ID/NAVER_CLIENT_SECRET not set"
    query = f"{target['region_1']} {target['expected_poi_name']}"
    params = {"query": query, "display": min(max(limit, 1), 5), "start": 1, "sort": "random"}
    url = NAVER_LOCAL_SEARCH_URL + "?" + urllib.parse.urlencode(params)
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    try:
        payload = _request_json(url, headers)
    except Exception as exc:
        return [], f"Naver fetch failed: {exc}"
    rows = []
    for raw in payload.get("items", []):
        name = _strip_html(raw.get("title"))
        rows.append(
            NormalizedRepresentativeCandidate(
                source_type="NAVER",
                source_place_id=raw.get("link") or f"{name}:{raw.get('mapx')}:{raw.get('mapy')}",
                source_name=name,
                category=raw.get("category") or None,
                address=raw.get("address") or None,
                road_address=raw.get("roadAddress") or None,
                latitude=_naver_coord(raw.get("mapy")),
                longitude=_naver_coord(raw.get("mapx")),
                phone=raw.get("telephone") or None,
                image_url=None,
                overview=None,
                source_payload=raw,
            )
        )
    return rows, None


def fetch_tourapi(target: dict[str, Any], limit: int) -> tuple[list[NormalizedRepresentativeCandidate], str | None]:
    service_key = os.getenv("TOURAPI_SERVICE_KEY")
    if not service_key:
        return [], "TOURAPI_SERVICE_KEY not set"
    params = {
        "serviceKey": service_key,
        "MobileOS": "ETC",
        "MobileApp": "travel_data_pipeline",
        "_type": "json",
        "numOfRows": min(max(limit, 1), 20),
        "pageNo": 1,
        "keyword": target["expected_poi_name"],
    }
    url = TOURAPI_BASE_URL + "/searchKeyword2?" + urllib.parse.urlencode(params)
    try:
        payload = _request_json(url)
    except Exception as exc:
        return [], f"TourAPI fetch failed: {exc}"
    body = payload.get("response", {}).get("body", {})
    items = body.get("items", {})
    raw_items = items.get("item", []) if isinstance(items, dict) else []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    rows = []
    for raw in raw_items:
        rows.append(
            NormalizedRepresentativeCandidate(
                source_type="TOURAPI",
                source_place_id=str(raw.get("contentid") or "") or None,
                source_name=(raw.get("title") or "").strip(),
                category=str(raw.get("contenttypeid") or "") or None,
                address=raw.get("addr1") or None,
                road_address=raw.get("addr2") or None,
                latitude=_to_float(raw.get("mapy")),
                longitude=_to_float(raw.get("mapx")),
                phone=raw.get("tel") or None,
                image_url=raw.get("firstimage") or raw.get("firstimage2") or None,
                overview=raw.get("overview") or None,
                source_payload=raw,
            )
        )
    return rows, None


def validate_candidate(target: dict[str, Any], candidate: NormalizedRepresentativeCandidate) -> dict[str, Any]:
    expected = target["expected_poi_name"]
    expected_norm = _normalize_name(expected)
    name_norm = _normalize_name(candidate.source_name)
    name_similarity = difflib.SequenceMatcher(None, expected_norm, name_norm).ratio() if name_norm else 0.0
    exact_or_contains = bool(expected_norm and (expected_norm in name_norm or name_norm in expected_norm))

    address_blob = " ".join(
        part for part in [candidate.address, candidate.road_address, candidate.source_name] if part
    )
    region_aliases = REGION_ALIASES.get(target["region_1"], (target["region_1"],))
    region_match = any(alias in address_blob or alias in candidate.source_name for alias in region_aliases)

    category = candidate.category or ""
    bad_category = (
        category in TOURAPI_BAD_CONTENT_TYPES
        or any(keyword in category or keyword in candidate.source_name for keyword in BAD_CATEGORY_KEYWORDS)
    )
    good_category = (
        category in TOURAPI_GOOD_CONTENT_TYPES
        or any(keyword in category or keyword in candidate.source_name for keyword in GOOD_CATEGORY_KEYWORDS)
    )

    risk_flags = []
    for keyword, flag in RISK_KEYWORDS.items():
        if keyword in candidate.source_name:
            risk_flags.append(flag)
    if not candidate.latitude or not candidate.longitude:
        risk_flags.append("MISSING_COORDINATES")
    if bad_category:
        risk_flags.append("CATEGORY_RISK")
    if not region_match:
        risk_flags.append("REGION_UNCLEAR")
    if not candidate.image_url:
        risk_flags.append("IMAGE_MISSING")
    if not candidate.overview:
        risk_flags.append("OVERVIEW_MISSING")

    score = 0.0
    score += 45.0 * name_similarity
    if exact_or_contains:
        score += 20.0
    if region_match:
        score += 10.0
    if candidate.latitude and candidate.longitude:
        score += 10.0
    if good_category:
        score += 8.0
    if candidate.image_url:
        score += 4.0
    if candidate.overview:
        score += 3.0
    if bad_category:
        score -= 25.0
    if any(flag in risk_flags for flag in ("LODGING_RISK", "PARKING_LOT_RISK", "CATEGORY_RISK")):
        score -= 15.0
    score = max(0.0, min(100.0, score))

    if (
        score >= 75
        and region_match
        and not any(flag in risk_flags for flag in ("LODGING_RISK", "PARKING_LOT_RISK", "CATEGORY_RISK"))
    ):
        result = "USABLE_CANDIDATE"
        recommendation = "stage_for_review"
    elif score >= 50:
        result = "NEEDS_MANUAL_REVIEW"
        recommendation = "manual_review"
    else:
        result = "REJECT_OR_LOW_CONFIDENCE"
        recommendation = "do_not_stage_without_review"

    return {
        "representative_score": round(score, 2),
        "name_similarity": round(name_similarity, 4),
        "region_match": region_match,
        "category_ok": good_category and not bad_category,
        "has_coordinates": bool(candidate.latitude and candidate.longitude),
        "has_image": bool(candidate.image_url),
        "has_overview": bool(candidate.overview),
        "validation_result": result,
        "risk_flags": sorted(set(risk_flags)),
        "action_recommendation": recommendation,
    }


def fetch_source(source: str, target: dict[str, Any], limit: int) -> tuple[list[NormalizedRepresentativeCandidate], str | None]:
    if source == "KAKAO":
        return fetch_kakao(target, limit)
    if source == "NAVER":
        return fetch_naver(target, limit)
    if source == "TOURAPI":
        return fetch_tourapi(target, limit)
    raise ValueError(f"Unsupported source: {source}")


def select_best(
    target: dict[str, Any], candidates: list[NormalizedRepresentativeCandidate]
) -> tuple[NormalizedRepresentativeCandidate | None, dict[str, Any] | None]:
    best_candidate = None
    best_validation = None
    for candidate in candidates:
        validation = validate_candidate(target, candidate)
        if best_validation is None or validation["representative_score"] > best_validation["representative_score"]:
            best_candidate = candidate
            best_validation = validation
    return best_candidate, best_validation


def _safe_exact_matched_place_id(conn, target: dict[str, Any], candidate: NormalizedRepresentativeCandidate) -> int | None:
    if not candidate.source_name:
        return None
    sql = """
        SELECT place_id
        FROM places
        WHERE region_1 = %(region_1)s
          AND name = %(name)s
          AND is_active = TRUE
          AND category_id IN (12, 14)
          AND visit_role IN ('spot', 'culture')
        ORDER BY place_id
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"region_1": target["region_1"], "name": candidate.source_name})
        row = cur.fetchone()
    return int(row[0]) if row else None


def insert_candidate(
    conn,
    target: dict[str, Any],
    candidate: NormalizedRepresentativeCandidate,
    validation: dict[str, Any],
) -> tuple[int | None, str]:
    if not candidate.source_name.strip():
        return None, "skipped_empty_source_name"
    matched_place_id = _safe_exact_matched_place_id(conn, target, candidate)
    representative_status = (
        "CANDIDATE"
        if validation["validation_result"] == "USABLE_CANDIDATE"
        else "NEEDS_REVIEW"
    )
    sql = """
        INSERT INTO representative_poi_candidates (
            expected_poi_name, region_1, region_2, matched_place_id,
            source_type, source_place_id, source_name, category,
            address, road_address, latitude, longitude, phone,
            image_url, overview, confidence_score,
            representative_status, review_status, promote_status,
            source_payload, validation_payload, review_payload,
            updated_at
        ) VALUES (
            %(expected_poi_name)s, %(region_1)s, %(region_2)s, %(matched_place_id)s,
            %(source_type)s, %(source_place_id)s, %(source_name)s, %(category)s,
            %(address)s, %(road_address)s, %(latitude)s, %(longitude)s, %(phone)s,
            %(image_url)s, %(overview)s, %(confidence_score)s,
            %(representative_status)s, 'PENDING_REVIEW', 'PENDING',
            %(source_payload)s, %(validation_payload)s, '{}'::jsonb,
            NOW()
        )
        ON CONFLICT (region_1, expected_poi_name, source_type, source_place_id)
            WHERE source_place_id IS NOT NULL
        DO UPDATE SET
            matched_place_id = EXCLUDED.matched_place_id,
            source_name = EXCLUDED.source_name,
            category = EXCLUDED.category,
            address = EXCLUDED.address,
            road_address = EXCLUDED.road_address,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            phone = EXCLUDED.phone,
            image_url = EXCLUDED.image_url,
            overview = EXCLUDED.overview,
            confidence_score = EXCLUDED.confidence_score,
            representative_status = EXCLUDED.representative_status,
            review_status = 'PENDING_REVIEW',
            promote_status = 'PENDING',
            source_payload = EXCLUDED.source_payload,
            validation_payload = EXCLUDED.validation_payload,
            updated_at = NOW()
        RETURNING candidate_id, (xmax = 0) AS inserted
    """
    params = {
        "expected_poi_name": target["expected_poi_name"],
        "region_1": target["region_1"],
        "region_2": None,
        "matched_place_id": matched_place_id,
        "source_type": candidate.source_type,
        "source_place_id": candidate.source_place_id,
        "source_name": candidate.source_name,
        "category": candidate.category,
        "address": candidate.address,
        "road_address": candidate.road_address,
        "latitude": candidate.latitude,
        "longitude": candidate.longitude,
        "phone": candidate.phone,
        "image_url": candidate.image_url,
        "overview": candidate.overview,
        "confidence_score": validation["representative_score"],
        "representative_status": representative_status,
        "source_payload": psycopg2.extras.Json(candidate.source_payload),
        "validation_payload": psycopg2.extras.Json(validation),
    }
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return int(row[0]), "inserted" if row[1] else "updated"


def build_targets(args: argparse.Namespace) -> list[dict[str, Any]]:
    targets = [t for t in TOP20_TARGETS if t["expected_poi_name"] in CURRENT_WRITE_SCOPE_NAMES]
    if args.region:
        targets = [t for t in targets if t["region_1"] == args.region or t["region_label"] == args.region]
    if args.expected_name:
        targets = [t for t in targets if t["expected_poi_name"] == args.expected_name]
    if args.limit:
        targets = targets[: args.limit]
    return targets


def run(args: argparse.Namespace) -> dict[str, Any]:
    write_mode = bool(args.write)
    dry_run = not write_mode

    sources = [args.source.upper()] if args.source else list(SOURCE_TYPES)
    invalid = [source for source in sources if source not in SOURCE_TYPES]
    if invalid:
        raise SystemExit(f"Unsupported source(s): {', '.join(invalid)}")

    targets = build_targets(args)
    report: dict[str, Any] = {
        "mode": "write" if write_mode else "dry-run",
        "db_write": write_mode,
        "places_changed": False,
        "seed_changed": False,
        "target_count": len(targets),
        "sources": sources,
        "results": [],
        "source_summary": {source: {"candidate_count": 0, "usable_count": 0, "error_count": 0} for source in sources},
        "write_summary": {"inserted": 0, "updated": 0, "skipped": 0},
    }

    conn = db_client.get_connection() if write_mode else None
    for target in targets:
        target_result = {
            "expected_poi_name": target["expected_poi_name"],
            "region_1": target["region_1"],
            "region_label": target["region_label"],
            "priority": target["priority"],
            "sources": [],
        }
        for source in sources:
            candidates, error = fetch_source(source, target, args.candidate_limit)
            validations = [validate_candidate(target, c) for c in candidates]
            best_candidate, best_validation = select_best(target, candidates)
            usable = sum(1 for v in validations if v["validation_result"] == "USABLE_CANDIDATE")
            report["source_summary"][source]["candidate_count"] += len(candidates)
            report["source_summary"][source]["usable_count"] += usable
            if error:
                report["source_summary"][source]["error_count"] += 1
            write_results = []
            if write_mode and conn is not None:
                for candidate, validation in zip(candidates, validations):
                    candidate_id, action = insert_candidate(conn, target, candidate, validation)
                    if action == "inserted":
                        report["write_summary"]["inserted"] += 1
                    elif action == "updated":
                        report["write_summary"]["updated"] += 1
                    else:
                        report["write_summary"]["skipped"] += 1
                    write_results.append({"candidate_id": candidate_id, "action": action})
            target_result["sources"].append(
                {
                    "source_type": source,
                    "candidate_count": len(candidates),
                    "error": error,
                    "best_candidate": asdict(best_candidate) if best_candidate else None,
                    "representative_score": best_validation["representative_score"] if best_validation else None,
                    "validation_result": best_validation["validation_result"] if best_validation else "NO_CANDIDATE",
                    "risk_flags": best_validation["risk_flags"] if best_validation else ["NO_CANDIDATE"],
                    "action_recommendation": best_validation["action_recommendation"] if best_validation else "collect_more_sources",
                    "write_results": write_results,
                    "candidates": [
                        {
                            "candidate": asdict(candidate),
                            "validation": validation,
                        }
                        for candidate, validation in zip(candidates, validations)
                    ],
                }
            )
        report["results"].append(target_result)
    if conn is not None:
        conn.commit()
        conn.close()
    return report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run representative POI candidate collection from TourAPI/Kakao/Naver."
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry-run mode. This is the default unless --write is used.")
    parser.add_argument("--write", action="store_true", help="Write candidates to representative_poi_candidates staging only.")
    parser.add_argument("--limit", type=int, help="Limit number of TOP20 expected POIs to process.")
    parser.add_argument("--candidate-limit", type=int, default=5, help="Candidate count per source and target.")
    parser.add_argument("--expected-name", help="Process a single expected POI name.")
    parser.add_argument("--source", choices=["tourapi", "kakao", "naver", "TOURAPI", "KAKAO", "NAVER"])
    parser.add_argument("--region", help="Filter by region_1 or region label.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")
    return parser.parse_args(argv)


def print_human(report: dict[str, Any]) -> None:
    title = "Write" if report["db_write"] else "Dry-run"
    print(f"[Representative POI Candidate Collection {title}]")
    print(f"- target_count: {report['target_count']}")
    print(f"- sources: {', '.join(report['sources'])}")
    print(f"- db_write: {str(report['db_write']).lower()}")
    print("- places_changed: false")
    print("- seed_changed: false")
    print()
    print("[Source Summary]")
    for source, summary in report["source_summary"].items():
        print(
            f"- {source}: candidates={summary['candidate_count']}, "
            f"usable={summary['usable_count']}, errors={summary['error_count']}"
        )
    if report["db_write"]:
        ws = report["write_summary"]
        print()
        print("[Write Summary]")
        print(f"- inserted: {ws['inserted']}")
        print(f"- updated: {ws['updated']}")
        print(f"- skipped: {ws['skipped']}")
    print()
    print("[Results]")
    for item in report["results"]:
        print(f"\n## {item['expected_poi_name']} ({item['region_label']}, priority={item['priority']})")
        for source in item["sources"]:
            best = source["best_candidate"] or {}
            print(
                f"- {source['source_type']}: count={source['candidate_count']}, "
                f"score={source['representative_score']}, result={source['validation_result']}, "
                f"action={source['action_recommendation']}"
            )
            if source.get("error"):
                print(f"  error: {source['error']}")
            if best:
                print(
                    "  best: "
                    f"{best.get('source_name')} | category={best.get('category')} | "
                    f"addr={best.get('road_address') or best.get('address')} | "
                    f"image={bool(best.get('image_url'))} | overview={bool(best.get('overview'))}"
                )
            print(f"  risk_flags: {', '.join(source['risk_flags'])}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report = run(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
