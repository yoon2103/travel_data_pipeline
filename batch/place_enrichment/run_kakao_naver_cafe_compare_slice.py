from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config  # noqa: E402,F401
from batch.place_enrichment.adapters.kakao_adapter import KakaoAdapter, NormalizedExternalPlace  # noqa: E402
from batch.place_enrichment.adapters.naver_adapter import NaverAdapter, NormalizedNaverPlace  # noqa: E402
from batch.place_enrichment.image_quality import score_image_candidate  # noqa: E402
from batch.place_enrichment.matching.decision_engine import MatchDecisionEngine  # noqa: E402
from batch.place_enrichment.matching.scoring import calculate_distance_meters, calculate_place_match_score, normalize_place_name  # noqa: E402


TARGET_SELECTION_SQL = """
    SELECT
        place_id,
        name,
        category_id,
        region_1,
        region_2,
        latitude,
        longitude,
        visit_role,
        first_image_url,
        view_count,
        kakao_place_id,
        naver_place_id
    FROM places
    WHERE is_active = TRUE
      AND region_1 = '서울'
      AND visit_role = 'cafe'
      AND (first_image_url IS NULL OR first_image_url = '')
      AND latitude IS NOT NULL
      AND longitude IS NOT NULL
    ORDER BY
        view_count DESC NULLS LAST,
        place_id
    LIMIT %(limit)s
"""


def select_targets(limit: int) -> list[dict[str, Any]]:
    import db_client

    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(TARGET_SELECTION_SQL, {"limit": limit})
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def create_run(conn, *, source_type: str, target_count: int, write: bool) -> str:
    run_id = str(uuid.uuid4())
    if not write:
        return run_id
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO place_enrichment_runs (
                run_id, enrichment_type, source_type, status,
                target_region, target_role, candidate_count, metadata
            )
            VALUES (%s, 'PLACE_MATCH', %s, 'RUNNING', '서울', 'cafe', %s, %s)
            """,
            (
                run_id,
                source_type,
                target_count,
                psycopg2.extras.Json({"slice": "kakao_naver_cafe_compare_seoul", "promote": False}),
            ),
        )
    conn.commit()
    return run_id


def finish_run(conn, run_id: str, *, write: bool, summary: dict[str, Any], status: str = "VALID") -> None:
    if not write:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE place_enrichment_runs
            SET status = %s,
                finished_at = NOW(),
                selected_count = 0,
                promoted_count = 0,
                skipped_count = %s,
                failed_count = %s,
                metadata = metadata || %s::jsonb
            WHERE run_id = %s
            """,
            (
                status,
                summary.get("no_candidate", 0),
                summary.get("rejected", 0),
                json.dumps({"dry_run_summary": summary}, ensure_ascii=False),
                run_id,
            ),
        )
    conn.commit()


def insert_place_match_candidate(conn, run_id: str, base_place: dict, external: dict, match_result, final_decision) -> int | None:
    review_status = review_status_for(final_decision.final_decision)
    validation_status = "INVALID" if final_decision.final_decision == "REJECT" else "VALID"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO place_enrichment_candidates (
                run_id, place_id, enrichment_type, source_type, source_place_id,
                source_category, source_confidence, external_rating, review_count,
                business_status, validity_status, indoor_outdoor,
                validation_status, promote_status, review_status,
                is_selected, is_place_valid, source_payload, enrichment_payload,
                validation_payload, review_payload, place_quality_score
            )
            VALUES (
                %(run_id)s, %(place_id)s, 'PLACE_MATCH', %(source_type)s, %(source_place_id)s,
                %(source_category)s, %(source_confidence)s, NULL, NULL,
                %(business_status)s, %(validity_status)s, %(indoor_outdoor)s,
                %(validation_status)s, 'PENDING', %(review_status)s,
                FALSE, %(is_place_valid)s, %(source_payload)s, %(enrichment_payload)s,
                %(validation_payload)s, %(review_payload)s, %(place_quality_score)s
            )
            ON CONFLICT DO NOTHING
            RETURNING candidate_id
            """,
            {
                "run_id": run_id,
                "place_id": base_place["place_id"],
                "source_type": external["source_type"],
                "source_place_id": external["source_place_id"],
                "source_category": external.get("category"),
                "source_confidence": round(match_result.score / 100, 3),
                "business_status": external.get("business_status") or "UNKNOWN",
                "validity_status": "INVALID" if final_decision.final_decision == "REJECT" else "VALID",
                "indoor_outdoor": "indoor",
                "validation_status": validation_status,
                "review_status": review_status,
                "is_place_valid": final_decision.final_decision != "REJECT",
                "source_payload": psycopg2.extras.Json(external.get("source_payload") or {}),
                "enrichment_payload": psycopg2.extras.Json({"normalized_external_place": external}),
                "validation_payload": psycopg2.extras.Json({
                    "match_result": asdict(match_result),
                    "final_decision": asdict(final_decision),
                }),
                "review_payload": psycopg2.extras.Json({
                    "previous_decision": match_result.decision,
                    "final_decision": final_decision.final_decision,
                    "review_required": final_decision.review_required,
                    "review_reasons": final_decision.review_reasons,
                    "block_reasons": final_decision.block_reasons,
                }),
                "place_quality_score": match_result.score,
            },
        )
        row = cur.fetchone()
        return row[0] if row else None


def insert_image_candidate(conn, run_id: str, base_place: dict, external: dict, final_decision) -> int | None:
    if not external.get("image_url"):
        return None
    image_score, image_payload = score_image_candidate(external, category="cafe")
    if image_score is None or final_decision.final_decision == "REJECT":
        return None
    review_status = "AUTO_APPROVED" if final_decision.final_decision == "AUTO_APPROVE" and image_score >= 85 else "PENDING_REVIEW"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO place_enrichment_candidates (
                run_id, place_id, enrichment_type, source_type, source_place_id,
                source_category, source_confidence, image_url, thumbnail_url,
                image_quality_score, business_status, validity_status, indoor_outdoor,
                validation_status, promote_status, review_status,
                is_selected, is_place_valid, source_payload, enrichment_payload,
                validation_payload, review_payload
            )
            VALUES (
                %(run_id)s, %(place_id)s, 'IMAGE', %(source_type)s, %(source_place_id)s,
                %(source_category)s, %(source_confidence)s, %(image_url)s, %(thumbnail_url)s,
                %(image_quality_score)s, %(business_status)s, 'VALID', 'indoor',
                'VALID', 'PENDING', %(review_status)s,
                FALSE, TRUE, %(source_payload)s, %(enrichment_payload)s,
                %(validation_payload)s, %(review_payload)s
            )
            ON CONFLICT DO NOTHING
            RETURNING candidate_id
            """,
            {
                "run_id": run_id,
                "place_id": base_place["place_id"],
                "source_type": external["source_type"],
                "source_place_id": external["source_place_id"],
                "source_category": external.get("category"),
                "source_confidence": round((final_decision.score or 0) / 100, 3),
                "image_url": external.get("image_url"),
                "thumbnail_url": external.get("thumbnail_url"),
                "image_quality_score": image_score,
                "business_status": external.get("business_status") or "UNKNOWN",
                "review_status": review_status,
                "source_payload": psycopg2.extras.Json(external.get("source_payload") or {}),
                "enrichment_payload": psycopg2.extras.Json({"image": {
                    "image_url": external.get("image_url"),
                    "thumbnail_url": external.get("thumbnail_url"),
                    "source_type": external["source_type"],
                }}),
                "validation_payload": psycopg2.extras.Json(image_payload),
                "review_payload": psycopg2.extras.Json({"final_decision": review_status}),
            },
        )
        row = cur.fetchone()
        return row[0] if row else None


def review_status_for(final_decision: str) -> str:
    if final_decision == "AUTO_APPROVE":
        return "AUTO_APPROVED"
    if final_decision == "REJECT":
        return "REJECTED"
    return "PENDING_REVIEW"


def normalized_to_dict(candidate: NormalizedExternalPlace | NormalizedNaverPlace) -> dict[str, Any]:
    return {
        "source_type": candidate.source_type,
        "source_place_id": candidate.source_place_id,
        "name": candidate.name,
        "category": candidate.category,
        "address": candidate.address,
        "road_address": candidate.road_address,
        "phone": candidate.phone,
        "latitude": candidate.latitude,
        "longitude": candidate.longitude,
        "place_url": candidate.place_url,
        "source_payload": candidate.source_payload,
        "image_url": candidate.image_url,
        "thumbnail_url": candidate.thumbnail_url,
        "business_status": "UNKNOWN",
    }


def source_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [r["score"] for r in rows]
    decisions: dict[str, int] = {}
    risk_flags: dict[str, int] = {}
    for row in rows:
        decisions[row["final_decision"]] = decisions.get(row["final_decision"], 0) + 1
        for flag in row.get("risk_flags", []):
            risk_flags[flag] = risk_flags.get(flag, 0) + 1
    return {
        "candidate_count": len(rows),
        "score_min": min(scores) if scores else None,
        "score_avg": round(sum(scores) / len(scores), 1) if scores else None,
        "score_max": max(scores) if scores else None,
        "decisions": decisions,
        "risk_flags": risk_flags,
        "manual_review_count": decisions.get("MANUAL_REVIEW", 0),
        "reject_count": decisions.get("REJECT", 0),
        "image_count": sum(1 for r in rows if r.get("has_image")),
    }


def compare_top_candidates(by_target: dict[int, dict[str, list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for place_id, sources in by_target.items():
        kakao = sources.get("KAKAO") or []
        naver = sources.get("NAVER") or []
        if not kakao or not naver:
            cases.append({"place_id": place_id, "status": "MISSING_SOURCE", "has_kakao": bool(kakao), "has_naver": bool(naver)})
            continue
        k = kakao[0]
        n = naver[0]
        name_sim = SequenceMatcher(None, normalize_place_name(k["external_name"]), normalize_place_name(n["external_name"])).ratio()
        distance = calculate_distance_meters(k["external_latitude"], k["external_longitude"], n["external_latitude"], n["external_longitude"])
        same = name_sim >= 0.90 and distance is not None and distance <= 100
        cases.append({
            "place_id": place_id,
            "status": "AGREE" if same else "DISAGREE",
            "kakao_name": k["external_name"],
            "naver_name": n["external_name"],
            "name_similarity": round(name_sim, 3),
            "distance_meters": None if distance is None else round(distance, 1),
            "kakao_score": k["score"],
            "naver_score": n["score"],
        })
    return cases


def process(limit: int, candidate_limit: int, radius_m: int, write: bool) -> dict[str, Any]:
    import db_client

    targets = select_targets(limit)
    kakao = KakaoAdapter()
    naver = NaverAdapter()
    engine = MatchDecisionEngine()
    processed: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    fetch_counts = {"KAKAO": 0, "NAVER": 0}
    no_candidate = {"KAKAO": 0, "NAVER": 0}
    by_target: dict[int, dict[str, list[dict[str, Any]]]] = {}

    conn = None
    run_ids = {"KAKAO": str(uuid.uuid4()), "NAVER": str(uuid.uuid4())}
    if write:
        conn = db_client.get_connection()
        run_ids = {
            "KAKAO": create_run(conn, source_type="KAKAO", target_count=len(targets), write=True),
            "NAVER": create_run(conn, source_type="NAVER", target_count=len(targets), write=True),
        }

    try:
        for base in targets:
            source_candidates: dict[str, list[NormalizedExternalPlace | NormalizedNaverPlace]] = {}
            try:
                source_candidates["KAKAO"] = kakao.fetch_candidates(base, radius_m=radius_m, limit=candidate_limit)
            except Exception as exc:
                source_candidates["KAKAO"] = []
                errors.append({"source_type": "KAKAO", "place_id": base["place_id"], "error": str(exc)})
            try:
                source_candidates["NAVER"] = naver.fetch_candidates(base, limit=candidate_limit)
            except Exception as exc:
                source_candidates["NAVER"] = []
                errors.append({"source_type": "NAVER", "place_id": base["place_id"], "error": str(exc)})

            for source_type, candidates in source_candidates.items():
                fetch_counts[source_type] += len(candidates)
                if not candidates:
                    no_candidate[source_type] += 1
                    continue
                for candidate in candidates:
                    external = normalized_to_dict(candidate)
                    match_result = calculate_place_match_score(base, external)
                    final_decision = engine.evaluate_match_decision(match_result)
                    row = {
                        "place_id": base["place_id"],
                        "place_name": base["name"],
                        "source_type": source_type,
                        "source_place_id": external["source_place_id"],
                        "external_name": external["name"],
                        "external_category": external.get("category"),
                        "external_latitude": external.get("latitude"),
                        "external_longitude": external.get("longitude"),
                        "score": match_result.score,
                        "name_similarity": round(match_result.name_similarity, 3),
                        "distance_meters": None if match_result.distance_meters is None else round(match_result.distance_meters, 1),
                        "final_decision": final_decision.final_decision,
                        "review_required": final_decision.review_required,
                        "risk_flags": match_result.risk_flags,
                        "has_image": bool(external.get("image_url")),
                    }
                    processed.append(row)
                    by_target.setdefault(base["place_id"], {}).setdefault(source_type, []).append(row)

                    if write and conn is not None:
                        insert_place_match_candidate(conn, run_ids[source_type], base, external, match_result, final_decision)
                        insert_image_candidate(conn, run_ids[source_type], base, external, final_decision)

        comparisons = compare_top_candidates(by_target)
        summary_by_source = {source: source_summary([r for r in processed if r["source_type"] == source]) for source in ("KAKAO", "NAVER")}
        disagreement_count = sum(1 for c in comparisons if c["status"] == "DISAGREE")
        summary = {
            "write": write,
            "target_count": len(targets),
            "run_ids": run_ids,
            "fetch_counts": fetch_counts,
            "fetch_success_rate": {
                "KAKAO": round((len(targets) - no_candidate["KAKAO"]) / len(targets), 3) if targets else 0,
                "NAVER": round((len(targets) - no_candidate["NAVER"]) / len(targets), 3) if targets else 0,
            },
            "no_candidate": no_candidate,
            "by_source": summary_by_source,
            "disagreement_count": disagreement_count,
            "disagreement_rate": round(disagreement_count / len(comparisons), 3) if comparisons else 0,
            "errors": errors,
        }

        if write and conn is not None:
            for source_type in ("KAKAO", "NAVER"):
                finish_run(conn, run_ids[source_type], write=True, summary={
                    **summary_by_source[source_type],
                    "no_candidate": no_candidate[source_type],
                    "rejected": summary_by_source[source_type]["reject_count"],
                })
            conn.commit()

        return {
            "summary": summary,
            "targets": targets,
            "candidates": processed[:50],
            "comparisons": comparisons,
        }
    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare Kakao/Naver cafe place enrichment candidates for Seoul.")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--candidate-limit", type=int, default=3)
    parser.add_argument("--radius-m", type=int, default=500)
    parser.add_argument("--write", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    limit = min(max(args.limit, 1), 10)
    candidate_limit = min(max(args.candidate_limit, 1), 5)
    result = process(limit=limit, candidate_limit=candidate_limit, radius_m=args.radius_m, write=args.write)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
