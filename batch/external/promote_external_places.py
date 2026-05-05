from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import db_client  # noqa: E402
from batch.external.common import finish_run, log_step  # noqa: E402


def _load_staging(conn, run_id: str, region: str | None) -> list[dict]:
    sql = """
        SELECT *
        FROM staging_places
        WHERE run_id = %s
          AND source = 'external'
          AND external_source IN ('kakao', 'naver')
          AND external_id IS NOT NULL
    """
    params: list = [run_id]
    if region:
        sql += " AND region_1 = %s"
        params.append(region)
    sql += " ORDER BY id"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def _snapshot_existing(conn, run_id: str, row: dict) -> int:
    id_column = "kakao_place_id" if row["external_source"] == "kakao" else "naver_place_id"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM places WHERE {id_column} = %s LIMIT 1", (row["external_id"],))
        existing = cur.fetchone()
        if not existing:
            return 0
        cur.execute(
            """
            INSERT INTO place_update_snapshots (
                run_id, place_id, tourapi_content_id, before_payload
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (run_id, place_id) DO NOTHING
            """,
            (
                run_id,
                existing["place_id"],
                existing["tourapi_content_id"],
                psycopg2.extras.Json(json.loads(json.dumps(dict(existing), ensure_ascii=False, default=str))),
            ),
        )
        return cur.rowcount


def _upsert_external(conn, row: dict) -> int:
    if row["external_source"] == "kakao":
        external_column = "kakao_place_id"
        conflict = "ON CONFLICT (kakao_place_id) WHERE kakao_place_id IS NOT NULL"
    else:
        external_column = "naver_place_id"
        conflict = "ON CONFLICT (naver_place_id) WHERE naver_place_id IS NOT NULL"

    sql = f"""
        INSERT INTO places (
            name, category_id, region_1, region_2, latitude, longitude, overview,
            first_image_url, first_image_thumb_url, ai_summary, ai_tags, embedding,
            visit_role, estimated_duration, visit_time_slot,
            ai_validation_status, ai_validation_errors,
            data_source, {external_column}, source_confidence, indoor_outdoor,
            is_active, synced_at
        )
        VALUES (
            %(name)s, %(category_id)s, %(region_1)s, %(region_2)s, %(latitude)s, %(longitude)s, %(overview)s,
            %(first_image_url)s, %(first_image_thumb_url)s, %(ai_summary)s, %(ai_tags)s, NULL,
            %(visit_role)s, %(estimated_duration)s, %(visit_time_slot)s,
            %(ai_validation_status)s, %(ai_validation_errors)s,
            'external', %(external_id)s, 0.85, %(indoor_outdoor)s,
            TRUE, NOW()
        )
        {conflict}
        DO UPDATE SET
            name = EXCLUDED.name,
            category_id = EXCLUDED.category_id,
            region_1 = EXCLUDED.region_1,
            region_2 = EXCLUDED.region_2,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            overview = COALESCE(NULLIF(EXCLUDED.overview, ''), places.overview),
            ai_summary = CASE
                WHEN places.data_source = 'external' THEN EXCLUDED.ai_summary
                ELSE COALESCE(EXCLUDED.ai_summary, places.ai_summary)
            END,
            ai_tags = CASE
                WHEN places.data_source = 'external' THEN EXCLUDED.ai_tags
                ELSE COALESCE(EXCLUDED.ai_tags, places.ai_tags)
            END,
            visit_role = COALESCE(EXCLUDED.visit_role, places.visit_role),
            estimated_duration = COALESCE(EXCLUDED.estimated_duration, places.estimated_duration),
            visit_time_slot = COALESCE(EXCLUDED.visit_time_slot, places.visit_time_slot),
            ai_validation_status = EXCLUDED.ai_validation_status,
            ai_validation_errors = EXCLUDED.ai_validation_errors,
            data_source = 'external',
            source_confidence = GREATEST(COALESCE(places.source_confidence, 0), 0.85),
            indoor_outdoor = COALESCE(EXCLUDED.indoor_outdoor, places.indoor_outdoor),
            is_active = TRUE,
            synced_at = NOW(),
            updated_at = NOW()
        RETURNING place_id
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            {
                "name": row["name"],
                "category_id": row["category_id"],
                "region_1": row["region_1"],
                "region_2": row["region_2"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "overview": row["overview"],
                "first_image_url": row.get("first_image_url"),
                "first_image_thumb_url": row.get("first_image_thumb_url"),
                "ai_summary": row["ai_summary"],
                "ai_tags": psycopg2.extras.Json(row["ai_tags"]),
                "visit_role": row["visit_role"],
                "estimated_duration": row["estimated_duration"],
                "visit_time_slot": row["visit_time_slot"],
                "ai_validation_status": row["ai_validation_status"],
                "ai_validation_errors": psycopg2.extras.Json(row["ai_validation_errors"]),
                "external_id": row["external_id"],
                "indoor_outdoor": row.get("indoor_outdoor"),
            },
        )
        cur.fetchone()
        return 1


def promote(run_id: str, region: str | None, qa_passed: bool, write: bool) -> dict:
    if not qa_passed:
        return {"run_id": run_id, "write": write, "promoted_count": 0, "blocked": "qa_passed flag is required"}
    conn = db_client.get_connection()
    try:
        rows = _load_staging(conn, run_id, region)
        if not write:
            role_counts: dict[str, int] = {}
            for row in rows:
                role_counts[row["visit_role"]] = role_counts.get(row["visit_role"], 0) + 1
            return {"run_id": run_id, "write": False, "candidate_count": len(rows), "role_counts": role_counts}

        promoted = 0
        snapshotted = 0
        try:
            for row in rows:
                snapshotted += _snapshot_existing(conn, run_id, row)
                promoted += _upsert_external(conn, row)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        log_step(conn, run_id, "promote_external_places", "SUCCESS", input_count=len(rows), output_count=promoted, metadata={"snapshot_count": snapshotted})
        finish_run(conn, run_id, "SUCCESS", {"external_promoted_count": promoted})
        return {"run_id": run_id, "write": True, "candidate_count": len(rows), "promoted_count": promoted, "snapshot_count": snapshotted}
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote external staging_places into production places.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--region")
    parser.add_argument("--qa-passed", action="store_true", help="Required guard after QA confirms FAIL did not increase.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(json.dumps(promote(args.run_id, args.region, args.qa_passed, args.write), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
