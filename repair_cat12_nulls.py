#!/usr/bin/env python3
"""
repair_cat12_nulls.py
cat12(관광지) 중 가공 필드(visit_role / visit_time_slot / estimated_duration / indoor_outdoor)
하나라도 NULL인 행을 classify_place()로 재계산하여 NULL 필드만 채운다.

안전장치:
  - COALESCE로 기존 비-NULL 값 보호 (덮어쓰기 없음)
  - UPDATE WHERE 조건에 place_id + 필드 NULL 체크 포함 (재실행 안전)
  - visit_role 이미 있어도 다른 필드가 NULL이면 해당 필드만 보정

실행:
  python repair_cat12_nulls.py --dry-run
  python repair_cat12_nulls.py
"""

import argparse
import sys

import psycopg2
import psycopg2.extras

import config
from batch_rules import classify_place

TARGET_CATEGORY = 12
ALLOWED_FIELDS  = ("visit_role", "visit_time_slot", "estimated_duration", "indoor_outdoor")


def main() -> None:
    parser = argparse.ArgumentParser(description="cat12 가공 필드 NULL 보정 배치")
    parser.add_argument("--dry-run", action="store_true", help="변경 없이 결과만 출력")
    args  = parser.parse_args()
    dry   = args.dry_run
    label = "[DRY-RUN]" if dry else "[APPLY]"

    conn = psycopg2.connect(
        host=config.DB_HOST, port=config.DB_PORT,
        dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

    with conn.cursor() as cur:
        cur.execute("""
            SELECT place_id, name, overview,
                   visit_role, visit_time_slot, estimated_duration, indoor_outdoor
            FROM   places
            WHERE  is_active    = TRUE
              AND  category_id  = %s
              AND  (
                  visit_role         IS NULL
                  OR visit_time_slot  IS NULL
                  OR estimated_duration IS NULL
                  OR indoor_outdoor   IS NULL
              )
            ORDER BY place_id
        """, (TARGET_CATEGORY,))
        rows = [dict(r) for r in cur.fetchall()]

    total = len(rows)
    print(f"\n{'=' * 60}")
    print(f"  cat12 가공 필드 NULL 보정  {label}")
    print(f"{'=' * 60}")
    print(f"\n{label} 대상: {total}건  (cat12, 가공 필드 하나라도 NULL)\n")

    if total == 0:
        print(f"  보정 대상 없음 — 종료")
        conn.close()
        return

    ok = fail = 0

    for i, r in enumerate(rows, 1):
        result = classify_place(r["name"], r["overview"], TARGET_CATEGORY)

        null_fields = [f for f in ALLOWED_FIELDS if r[f] is None]

        print(f"  [{i}/{total}] place_id={r['place_id']:>6}  {r['name'][:24]}")
        print(f"    NULL 필드 : {null_fields}")
        print(f"    보정값    : role={result['visit_role']}  "
              f"dur={result['estimated_duration']}  "
              f"io={result['indoor_outdoor']}  "
              f"slot={result['visit_time_slot']}")

        if dry:
            continue

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE places
                       SET visit_role         = COALESCE(visit_role,         %(role)s),
                           visit_time_slot    = COALESCE(visit_time_slot,    %(slots)s),
                           estimated_duration = COALESCE(estimated_duration, %(dur)s),
                           indoor_outdoor     = COALESCE(indoor_outdoor,     %(io)s),
                           updated_at         = NOW()
                     WHERE place_id    = %(pid)s
                       AND (
                           visit_role         IS NULL
                           OR visit_time_slot  IS NULL
                           OR estimated_duration IS NULL
                           OR indoor_outdoor   IS NULL
                       )
                """, {
                    "role":  result["visit_role"],
                    "slots": result["visit_time_slot"],
                    "dur":   result["estimated_duration"],
                    "io":    result["indoor_outdoor"],
                    "pid":   r["place_id"],
                })
            conn.commit()
            ok += 1
        except Exception as exc:
            conn.rollback()
            print(f"    FAIL — {exc}", file=sys.stderr)
            fail += 1

    conn.close()

    print(f"\n{'=' * 60}")
    if dry:
        print(f"  [DRY-RUN] 완료 — 실제 변경 없음  (예상 보정 대상: {total}건)")
    else:
        print(f"  [APPLY] 완료 — 성공: {ok}건 / 실패: {fail}건")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
