#!/usr/bin/env python3
"""
verify_runner.py - 검증 SQL 세트 실행기 (read-only)

실행:
  python verify_runner.py
  python verify_runner.py --limit 20
"""

import argparse
import os
import sys

import psycopg2
import psycopg2.extras

import config

SQL_DIR = os.path.join(os.path.dirname(__file__), "sql", "verify")

SQL_ORDER = [
    ("v01_category_count.sql",      "category별 건수"),
    ("v12_sync_status.sql",         "synced_at 기준 적재 완료 여부"),
    ("v02_null_check.sql",          "주요 필드 NULL·빈문자 현황"),
    ("v04_coordinate_outlier.sql",  "좌표 NULL 및 한국 범위 이탈 행"),
    ("v05_image_rate.sql",          "category별 대표 이미지 보유율"),
    ("v06_visit_role_dist.sql",     "visit_role 분포"),
    ("v07_time_slot_dist.sql",      "visit_time_slot 분포"),
    ("v08_duration_dist.sql",       "estimated_duration 분포"),
    ("v09_indoor_outdoor_dist.sql", "indoor_outdoor 분포"),
    ("v10a_misclassify_count.sql",  "오분류 건수 집계"),
    ("v10b_misclassify_sample.sql", "오분류 샘플 조회"),
    ("v11_ai_status_dist.sql",      "ai_validation_status 분포"),
    ("v03_duplicate_suspect.sql",   "이름+지역 기준 1차 중복 의심 탐지"),
]


def split_statements(sql_text: str) -> list[str]:
    parts = sql_text.split(";")
    stmts = []
    for part in parts:
        stripped = part.strip()
        non_comment = "\n".join(
            line for line in stripped.splitlines()
            if not line.strip().startswith("--")
        ).strip()
        if non_comment:
            stmts.append(stripped)
    return stmts


def fmt_rows(rows: list[dict], limit: int) -> str:
    if not rows:
        return "  (결과 없음)"
    cols = list(rows[0].keys())
    widths = {
        c: min(40, max(len(str(c)), max(len(str(r.get(c, "") or "")) for r in rows)))
        for c in cols
    }
    sep    = "  " + "-+-".join("-" * widths[c] for c in cols)
    header = "  " + " | ".join(str(c).ljust(widths[c]) for c in cols)
    out    = [header, sep]
    for row in rows[:limit]:
        out.append(
            "  " + " | ".join(
                str(row.get(c, "") or "")[:widths[c]].ljust(widths[c]) for c in cols
            )
        )
    if len(rows) > limit:
        out.append(f"  ... ({len(rows) - limit}행 생략, --limit 으로 조정 가능)")
    return "\n".join(out)


def run_sql_file(conn, filename: str, purpose: str, limit: int) -> tuple[str, str]:
    path = os.path.join(SQL_DIR, filename)
    print(f"\n{'=' * 62}")
    print(f"  {filename}")
    print(f"  목적: {purpose}")
    print(f"{'=' * 62}")
    try:
        with open(path, encoding="utf-8") as f:
            sql_text = f.read()
    except FileNotFoundError:
        msg = f"파일 없음: {path}"
        print(f"  [ERROR] {msg}")
        return "error", msg
    stmts = split_statements(sql_text)
    all_rows: list[dict] = []
    errors:   list[str]  = []
    for i, stmt in enumerate(stmts, 1):
        label = f"[쿼리 {i}/{len(stmts)}] " if len(stmts) > 1 else ""
        try:
            with conn.cursor() as cur:
                cur.execute(stmt)
                rows = [dict(r) for r in cur.fetchall()]
            if label:
                print(f"\n  {label}")
            print(fmt_rows(rows, limit))
            all_rows.extend(rows)
        except psycopg2.Error as e:
            conn.rollback()
            msg = str(e).strip().splitlines()[0]
            print(f"  [ERROR] {label}{msg}")
            errors.append(msg)
    if errors:
        return "error", errors[0]
    row_count = len(all_rows)
    if filename == "v04_coordinate_outlier.sql" and row_count > 0:
        detail = f"좌표 이상치 {row_count}건"
        print(f"\n  → [즉시 점검 필요] {detail}")
        return "critical", detail
    if filename == "v10a_misclassify_count.sql":
        total = sum(int(r.get("suspicious_count") or 0) for r in all_rows)
        if total > 0:
            detail = f"오분류 의심 합계 {total}건"
            print(f"\n  → [확인 필요] {detail}")
            return "warn", detail
    if filename == "v03_duplicate_suspect.sql" and row_count > 0:
        detail = f"중복 의심 {row_count}건"
        print(f"\n  → [확인 필요] {detail}")
        return "warn", detail
    return "ok", f"{row_count}행"


def main() -> None:
    parser = argparse.ArgumentParser(description="read-only 검증 SQL 실행기")
    parser.add_argument("--limit", type=int, default=10,
                        help="결과 최대 표시 행수 (기본 10)")
    args = parser.parse_args()
    try:
        conn = psycopg2.connect(
            host=config.DB_HOST, port=config.DB_PORT,
            dbname=config.DB_NAME, user=config.DB_USER,
            password=config.DB_PASSWORD,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        conn.set_session(readonly=True, autocommit=True)
    except psycopg2.Error as e:
        print(f"[DB 연결 실패] {e}", file=sys.stderr)
        sys.exit(1)
    results: list[tuple[str, str, str, str]] = []
    for filename, purpose in SQL_ORDER:
        status, detail = run_sql_file(conn, filename, purpose, args.limit)
        results.append((filename, purpose, status, detail))
    conn.close()
    ok       = [(f, d) for f, _, s, d in results if s == "ok"]
    warn     = [(f, d) for f, _, s, d in results if s == "warn"]
    critical = [(f, d) for f, _, s, d in results if s == "critical"]
    errors   = [(f, d) for f, _, s, d in results if s == "error"]
    print(f"\n{'=' * 62}")
    print("  최종 요약")
    print(f"{'=' * 62}")
    print(f"\n[통과]            {len(ok)}건")
    for f, d in ok:
        print(f"    v  {f}  ({d})")
    print(f"\n[확인 필요]       {len(warn)}건")
    for f, d in warn:
        print(f"    !  {f}  - {d}")
    print(f"\n[즉시 점검 필요]  {len(critical)}건")
    for f, d in critical:
        print(f"    !! {f}  - {d}")
    if errors:
        print(f"\n[실행 오류]       {len(errors)}건")
        for f, d in errors:
            print(f"    X  {f}  - {d}")
    print()


if __name__ == "__main__":
    main()
