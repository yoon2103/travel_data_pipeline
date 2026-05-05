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
from batch.external.common import log_step, role_payload  # noqa: E402


def stage(run_id: str, region: str | None, write: bool) -> dict:
    conn = db_client.get_connection()
    try:
        sql = """
            SELECT *
            FROM clean_external_places
            WHERE run_id = %s
        """
        params: list = [run_id]
        if region:
            sql += " AND region = %s"
            params.append(region)
        sql += " ORDER BY id"
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = list(cur.fetchall())

        prepared: list[dict] = []
        blocked = 0
        for row in rows:
            payload = role_payload(row["visit_role"], row["name"])
            if not payload["visit_role"] or not payload["ai_tags"] or not payload["ai_summary"]:
                blocked += 1
                continue
            prepared.append({
                **row,
                **payload,
                "tourapi_content_id": row["external_content_id"],
                "overview": payload["ai_summary"],
            })

        inserted = 0
        if write:
            with conn.cursor() as cur:
                for row in prepared:
                    cur.execute(
                        """
                        INSERT INTO staging_places (
                            run_id, source, external_source, external_id, external_content_id,
                            tourapi_content_id, name, category_id, region_1, region_2,
                            latitude, longitude, overview, ai_summary, ai_tags, embedding,
                            visit_role, estimated_duration, visit_time_slot,
                            ai_validation_status, ai_validation_errors, address, phone, place_url,
                            indoor_outdoor
                        )
                        VALUES (
                            %(run_id)s, 'external', %(source)s, %(external_id)s, %(external_content_id)s,
                            %(tourapi_content_id)s, %(name)s, %(category_id)s, %(region)s, NULL,
                            %(latitude)s, %(longitude)s, %(overview)s, %(ai_summary)s, %(ai_tags)s, NULL,
                            %(visit_role)s, %(estimated_duration)s, %(visit_time_slot)s,
                            %(ai_validation_status)s, %(ai_validation_errors)s, %(address)s, %(phone)s, %(place_url)s,
                            %(indoor_outdoor)s
                        )
                        ON CONFLICT (run_id, tourapi_content_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            category_id = EXCLUDED.category_id,
                            latitude = EXCLUDED.latitude,
                            longitude = EXCLUDED.longitude,
                            overview = EXCLUDED.overview,
                            ai_summary = EXCLUDED.ai_summary,
                            ai_tags = EXCLUDED.ai_tags,
                            visit_role = EXCLUDED.visit_role,
                            estimated_duration = EXCLUDED.estimated_duration,
                            visit_time_slot = EXCLUDED.visit_time_slot,
                            address = EXCLUDED.address,
                            phone = EXCLUDED.phone,
                            place_url = EXCLUDED.place_url,
                            indoor_outdoor = EXCLUDED.indoor_outdoor,
                            staged_at = NOW()
                        """,
                        {
                            **row,
                            "ai_tags": psycopg2.extras.Json(row["ai_tags"]),
                            "visit_time_slot": row["visit_time_slot"],
                            "ai_validation_errors": psycopg2.extras.Json(row["ai_validation_errors"]),
                        },
                    )
                    inserted += 1
            conn.commit()
            log_step(conn, run_id, "enrich_external_places", "SUCCESS", input_count=len(rows), output_count=inserted, metadata={"blocked_missing_ai_fields": blocked})

        role_counts: dict[str, int] = {}
        for row in prepared:
            role_counts[row["visit_role"]] = role_counts.get(row["visit_role"], 0) + 1
        return {"run_id": run_id, "write": write, "input_count": len(rows), "prepared_count": len(prepared), "staged_count": inserted, "blocked_count": blocked, "role_counts": role_counts}
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich clean external places and merge them into staging_places.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--region")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(json.dumps(stage(args.run_id, args.region, args.write), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
