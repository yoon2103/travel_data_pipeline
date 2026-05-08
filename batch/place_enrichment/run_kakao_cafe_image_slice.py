from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from batch.place_enrichment.adapters.kakao_adapter import KakaoAdapter, NormalizedExternalPlace  # noqa: E402
from batch.place_enrichment.image_quality import score_image_candidate  # noqa: E402
from batch.place_enrichment.matching.decision_engine import MatchDecisionEngine  # noqa: E402
from batch.place_enrichment.matching.scoring import calculate_place_match_score  # noqa: E402
from batch.place_enrichment.promote_dry_run import summarize  # noqa: E402


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
      AND (region_1 LIKE %(region_like)s OR region_1 = %(region)s)
      AND (first_image_url IS NULL OR first_image_url = '')
      AND (
          visit_role = 'cafe'
          OR name ILIKE %(cafe_keyword)s
          OR category_id = 39
      )
      AND latitude IS NOT NULL
      AND longitude IS NOT NULL
    ORDER BY
        CASE WHEN visit_role = 'cafe' THEN 0 ELSE 1 END,
        view_count DESC NULLS LAST,
        place_id
    LIMIT %(limit)s
"""


def select_targets(limit: int, *, mock_targets: bool = False) -> list[dict[str, Any]]:
    if mock_targets:
        return [
            {
                "place_id": 900001,
                "name": "샘플카페 서울점",
                "category_id": 39,
                "region_1": "서울",
                "region_2": None,
                "latitude": 37.5665,
                "longitude": 126.9780,
                "visit_role": "cafe",
                "first_image_url": None,
                "view_count": 100,
                "kakao_place_id": None,
                "naver_place_id": None,
            }
        ][:limit]

    import db_client

    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                TARGET_SELECTION_SQL,
                {
                    "region": "서울",
                    "region_like": "%서울%",
                    "cafe_keyword": "%카페%",
                    "limit": limit,
                },
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def create_run(conn, run_id: str, *, write: bool, use_mock: bool, target_count: int) -> None:
    if not write:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO place_enrichment_runs (
                run_id, enrichment_type, source_type, status,
                target_region, target_role, candidate_count, metadata
            )
            VALUES (%s, 'PLACE_MATCH', 'KAKAO', 'RUNNING', '서울', 'cafe', %s, %s)
            """,
            (
                run_id,
                target_count,
                psycopg2.extras.Json({"slice": "kakao_cafe_image_seoul_50", "mock_mode": use_mock}),
            ),
        )
    conn.commit()


def finish_run(conn, run_id: str, *, write: bool, summary: dict, status: str = "SUCCESS") -> None:
    if not write:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE place_enrichment_runs
            SET status = %s,
                finished_at = NOW(),
                selected_count = %s,
                skipped_count = %s,
                failed_count = %s,
                metadata = metadata || %s::jsonb
            WHERE run_id = %s
            """,
            (
                status,
                summary.get("promote_candidates", 0),
                summary.get("no_candidate", 0),
                summary.get("rejected", 0),
                json.dumps({"dry_run_summary": summary}, ensure_ascii=False),
                run_id,
            ),
        )
    conn.commit()


def insert_place_match_candidate(conn, run_id: str, base_place: dict, external: dict, match_result, final_decision) -> int:
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
                %(run_id)s, %(place_id)s, 'PLACE_MATCH', 'KAKAO', %(source_place_id)s,
                %(source_category)s, %(source_confidence)s, NULL, NULL,
                %(business_status)s, %(validity_status)s, %(indoor_outdoor)s,
                %(validation_status)s, 'PENDING', %(review_status)s,
                FALSE, %(is_place_valid)s, %(source_payload)s, %(enrichment_payload)s,
                %(validation_payload)s, %(review_payload)s, %(place_quality_score)s
            )
            RETURNING candidate_id
            """,
            {
                "run_id": run_id,
                "place_id": base_place["place_id"],
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
                "enrichment_payload": psycopg2.extras.Json({"external_place": external}),
                "validation_payload": psycopg2.extras.Json({
                    "match_result": asdict(match_result),
                    "final_decision": asdict(final_decision),
                }),
                "review_payload": psycopg2.extras.Json({
                    "previous_decision": match_result.decision,
                    "final_decision": final_decision.final_decision,
                    "review_required": final_decision.review_required,
                }),
                "place_quality_score": match_result.score,
            },
        )
        return cur.fetchone()[0]


def insert_image_candidate(conn, run_id: str, base_place: dict, external: dict, image_score: int, image_payload: dict, final_decision) -> int:
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
                %(run_id)s, %(place_id)s, 'IMAGE', 'KAKAO', %(source_place_id)s,
                %(source_category)s, %(source_confidence)s, %(image_url)s, %(thumbnail_url)s,
                %(image_quality_score)s, %(business_status)s, 'VALID', 'indoor',
                'VALID', 'PENDING', %(review_status)s,
                FALSE, TRUE, %(source_payload)s, %(enrichment_payload)s,
                %(validation_payload)s, %(review_payload)s
            )
            RETURNING candidate_id
            """,
            {
                "run_id": run_id,
                "place_id": base_place["place_id"],
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
                    "source_type": "KAKAO",
                }}),
                "validation_payload": psycopg2.extras.Json(image_payload),
                "review_payload": psycopg2.extras.Json({"final_decision": review_status}),
            },
        )
        return cur.fetchone()[0]


def review_status_for(final_decision: str) -> str:
    if final_decision == "AUTO_APPROVE":
        return "AUTO_APPROVED"
    if final_decision == "REJECT":
        return "REJECTED"
    return "PENDING_REVIEW"


def process_targets(targets: list[dict], *, write: bool, radius_m: int, candidate_limit: int) -> dict:
    adapter = KakaoAdapter()
    engine = MatchDecisionEngine()
    use_mock = not adapter.has_api_key
    run_id = str(uuid.uuid4())
    processed_candidates: list[dict] = []
    no_candidate_count = 0

    conn = None
    if write:
        import db_client

        conn = db_client.get_connection()
        create_run(conn, run_id, write=write, use_mock=use_mock, target_count=len(targets))

    try:
        for base_place in targets:
            candidates = adapter.fetch_candidates(base_place, radius_m=radius_m, limit=candidate_limit)
            if not candidates:
                no_candidate_count += 1
                continue

            for candidate in candidates:
                external = normalized_to_dict(candidate)
                match_result = calculate_place_match_score(base_place, external)
                final_decision = engine.evaluate_match_decision(match_result)
                processed = {
                    "place_id": base_place["place_id"],
                    "place_name": base_place["name"],
                    "source_type": "KAKAO",
                    "source_place_id": external["source_place_id"],
                    "external_name": external["name"],
                    "score": match_result.score,
                    "final_decision": final_decision.final_decision,
                    "review_required": final_decision.review_required,
                    "risk_flags": match_result.risk_flags,
                    "distance_meters": match_result.distance_meters,
                    "has_image": bool(external.get("image_url")),
                }
                processed_candidates.append(processed)

                if write and conn is not None:
                    insert_place_match_candidate(conn, run_id, base_place, external, match_result, final_decision)
                    image_score, image_payload = score_image_candidate(external, category="cafe")
                    if image_score is not None and final_decision.final_decision != "REJECT":
                        insert_image_candidate(conn, run_id, base_place, external, image_score, image_payload, final_decision)

        summary = summarize(processed_candidates)
        summary["no_candidate"] = no_candidate_count
        summary["target_count"] = len(targets)
        summary["candidate_count"] = len(processed_candidates)
        summary["run_id"] = run_id
        summary["write"] = write
        summary["mock_mode"] = use_mock

        if write and conn is not None:
            conn.commit()
            finish_run(conn, run_id, write=write, summary=summary)

        return {"summary": summary, "candidates": processed_candidates[:20]}
    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()


def normalized_to_dict(candidate: NormalizedExternalPlace) -> dict:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seoul Kakao cafe image enrichment vertical slice.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--radius-m", type=int, default=500)
    parser.add_argument("--candidate-limit", type=int, default=5)
    parser.add_argument("--write", action="store_true", help="Write staging candidates. Default is dry-run.")
    parser.add_argument("--mock-targets", action="store_true", help="Use local mock target rows instead of DB target selection.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    limit = min(max(args.limit, 1), 50)
    targets = select_targets(limit, mock_targets=args.mock_targets)
    result = process_targets(targets, write=args.write, radius_m=args.radius_m, candidate_limit=args.candidate_limit)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
