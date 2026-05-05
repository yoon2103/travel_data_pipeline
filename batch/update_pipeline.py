from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import db_client  # noqa: E402
from batch.steps import (  # noqa: E402
    backup_db,
    build_clean_places,
    collect_tourapi,
    enrich_ai,
    load_raw_places,
    load_staging_places,
    normalize_places,
    promote_places,
    run_qa,
    smoke_test,
    validate_places,
)
from batch.steps.common import PipelineStop, StepResult  # noqa: E402

logger = logging.getLogger("data_update_pipeline")


STEPS = [
    backup_db,
    collect_tourapi,
    load_raw_places,
    normalize_places,
    validate_places,
    build_clean_places,
    enrich_ai,
    load_staging_places,
    run_qa,
    promote_places,
    smoke_test,
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def get_last_sync_time(conn) -> datetime | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT last_sync_time
            FROM data_sync_state
            WHERE source = 'tourapi'
            """
        )
        row = cur.fetchone()
        return row[0] if row else None


def create_run(conn, run_id: uuid.UUID, args, last_sync_time: datetime | None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO data_update_runs (
                run_id, mode, dry_run, promote, status,
                last_sync_time_at_start, metadata
            )
            VALUES (%s, %s, %s, %s, 'RUNNING', %s, %s)
            """,
            (
                str(run_id),
                args.mode,
                args.dry_run,
                args.promote,
                last_sync_time,
                psycopg2.extras.Json({
                    "requested_at": _utc_now().isoformat(),
                    "notes": "first skeleton implementation",
                }),
            ),
        )
    conn.commit()


def finish_run(
    conn,
    run_id: uuid.UUID,
    status: str,
    error_message: str | None = None,
    update_last_sync_time: bool = False,
) -> None:
    finished_at = _utc_now()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE data_update_runs
            SET status = %s,
                finished_at = %s,
                error_message = %s
            WHERE run_id = %s
            """,
            (status, finished_at, error_message, str(run_id)),
        )
        if update_last_sync_time:
            cur.execute(
                """
                INSERT INTO data_sync_state (
                    source, last_sync_time, last_success_run_id, updated_at
                )
                VALUES ('tourapi', %s, %s, %s)
                ON CONFLICT (source)
                DO UPDATE SET
                    last_sync_time = EXCLUDED.last_sync_time,
                    last_success_run_id = EXCLUDED.last_success_run_id,
                    updated_at = EXCLUDED.updated_at
                """,
                (finished_at, str(run_id), finished_at),
            )
    conn.commit()


def log_step(conn, run_id: uuid.UUID, result: StepResult) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO data_update_step_logs (
                run_id, step_name, status, started_at, finished_at,
                input_count, output_count, message, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(run_id),
                result.name,
                result.status,
                result.started_at or _utc_now(),
                result.finished_at or _utc_now(),
                result.input_count,
                result.output_count,
                result.message,
                psycopg2.extras.Json(result.metadata),
            ),
        )
    conn.commit()


def _mark_step_times(result: StepResult, started_at: datetime) -> StepResult:
    result.started_at = started_at
    result.finished_at = _utc_now()
    return result


def run_pipeline(args) -> dict:
    run_id = uuid.uuid4()
    conn = db_client.get_connection()
    executed_steps: list[dict] = []
    try:
        last_sync_time = get_last_sync_time(conn)
        create_run(conn, run_id, args, last_sync_time)

        context = {
            "run_id": str(run_id),
            "mode": args.mode,
            "dry_run": args.dry_run,
            "promote": args.promote,
            "last_sync_time": last_sync_time.isoformat() if last_sync_time else None,
            "api_base_url": args.api_base_url,
        }

        for step in STEPS:
            started_at = _utc_now()
            result = step.run(context)
            result = _mark_step_times(result, started_at)
            log_step(conn, run_id, result)
            executed_steps.append({
                "name": result.name,
                "status": result.status,
                "message": result.message,
                "input_count": result.input_count,
                "output_count": result.output_count,
            })
            if result.status == "FAILED":
                raise PipelineStop(result.message or f"{result.name} failed")

        should_update_last_sync = bool(args.promote and not args.dry_run and args.smoke_passed)
        final_status = "DRY_RUN_SUCCESS" if args.dry_run else "SUCCESS"
        finish_run(
            conn,
            run_id,
            final_status,
            update_last_sync_time=should_update_last_sync,
        )
        return {
            "run_id": str(run_id),
            "status": final_status,
            "last_sync_time_updated": should_update_last_sync,
            "steps": executed_steps,
        }
    except Exception as exc:
        conn.rollback()
        finish_run(conn, run_id, "FAILED", error_message=str(exc))
        raise
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Travel public-data update pipeline")
    parser.add_argument("--mode", default="incremental", choices=["incremental", "full"])
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    parser.add_argument("--promote", action="store_true", default=False)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:5000")
    parser.add_argument(
        "--smoke-passed",
        action="store_true",
        default=False,
        help="Internal guard used by later implementation; false by default.",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args(argv)
    result = run_pipeline(args)
    print(_json_dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
