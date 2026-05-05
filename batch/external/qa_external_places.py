from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import db_client  # noqa: E402
from batch.external.common import log_step  # noqa: E402
import psycopg2.extras  # noqa: E402


def _latest_qa_json() -> Path | None:
    qa_dir = ROOT_DIR / "qa_reports"
    files = sorted(qa_dir.glob("qa_all_regions_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _count_verdicts(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        rows = payload.get("rows") or payload.get("results") or []
    else:
        rows = payload
    counts = {"PASS": 0, "WEAK": 0, "FAIL": 0}
    for row in rows or []:
        verdict = row.get("verdict")
        if verdict in counts:
            counts[verdict] += 1
    return counts


def run_qa(run_id: str, baseline_json: str | None, repeat: int) -> dict:
    before_counts = _count_verdicts(Path(baseline_json)) if baseline_json else None
    cmd = [sys.executable, str(ROOT_DIR / "run_course_qa_report.py"), "--repeat", str(repeat)]
    subprocess.run(cmd, cwd=ROOT_DIR, check=True)
    after_path = _latest_qa_json()
    if after_path is None:
        raise RuntimeError("QA result JSON was not generated.")
    after_counts = _count_verdicts(after_path)
    fail_increased = before_counts is not None and after_counts["FAIL"] > before_counts["FAIL"]
    status = "FAIL" if fail_increased else "PASS"

    conn = db_client.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data_update_qa_results (
                    run_id, status, pass_count, weak_count, fail_count,
                    place_count_distribution, report_path, result_payload
                )
                VALUES (%s, %s, %s, %s, %s, '{}'::jsonb, %s, %s)
                """,
                (
                    run_id,
                    status,
                    after_counts["PASS"],
                    after_counts["WEAK"],
                    after_counts["FAIL"],
                    str(after_path),
                    psycopg2.extras.Json({"baseline": before_counts, "after": after_counts, "fail_increased": fail_increased}),
                ),
            )
        conn.commit()
        log_step(conn, run_id, "qa_external_places", "SUCCESS" if status == "PASS" else "FAILED", metadata={"baseline": before_counts, "after": after_counts})
    finally:
        conn.close()
    return {"run_id": run_id, "status": status, "baseline": before_counts, "after": after_counts, "fail_increased": fail_increased, "report_path": str(after_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run existing course QA and block promotion if FAIL increases.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--baseline-json")
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(run_qa(args.run_id, args.baseline_json, args.repeat), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
