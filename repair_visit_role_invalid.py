#!/usr/bin/env python3
"""
repair_visit_role_invalid.py
visit_role이 허용값(spot / culture / meal / cafe) 밖인 행을
classify_place() 규칙 기반으로 재분류한다.

안전장치:
  - classify_place() 재계산 결과 사용
  - UPDATE WHERE 조건에 AND visit_role = %(old_role)s 포함 (재실행 안전)
  - 재계산 결과와 무관하게 old_role 기록 후 리포트

실행:
  python repair_visit_role_invalid.py --dry-run
  python repair_visit_role_invalid.py
"""

import argparse
import sys

import psycopg2
import psycopg2.extras

import config
from batch_rules import classify_place

ALLOWED_ROLES = {"spot", "culture", "meal", "cafe"}


def main() -> None:
    parser = argparse.ArgumentParser(description="visit_role 이상값 규칙 기반 재분류 배치")
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
            SELECT place_id, name, overview, category_id,
                   visit_role, visit_time_slot, estimated_duration, indoor_outdoor
            FROM   places
            WHERE  is_active  = TRUE
              AND  visit_role IS NOT NULL
              AND  visit_role NOT IN ('spot', 'culture', 'meal', 'cafe')
            ORDER BY category_id, place_id
        """)
        rows = [dict(r) for r in cur.fetchall()]

    total = len(rows)
    print(f"\n{'=' * 60}")
    print(f"  visit_role 이상값 재분류  {label}")
    print(f"{'=' * 60}")
    print(f"\n{label} 대상: {total}건  (visit_role 허용값 외)\n")

    if total == 0:
        print(f"  보정 대상 없음 — 종료")
        conn.close()
        return

    ok = fail = 0

    for i, r in enumerate(rows, 1):
        result   = classify_place(r["name"], r["overview"], r["category_id"])
        new_role = result["visit_role"]
        new_slots = result["visit_time_slot"]
        old_role = r["visit_role"]

        print(f"  [{i}/{total}] place_id={r['place_id']:>6}  cat={r['category_id']}  "
              f"{r['name'][:24]}")
        print(f"    visit_role : {old_role!r}  ->  {new_role!r}")
        print(f"    time_slot  : {r['visit_time_slot']}  ->  {new_slots}  "
              f"(NULL이면 같이 보정)")

        if dry:
            continue

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE places
                       SET visit_role      = %(new_role)s,
                           visit_time_slot = COALESCE(visit_time_slot, %(new_slots)s),
                           updated_at      = NOW()
                     WHERE place_id   = %(pid)s
                       AND visit_role = %(old_role)s
                """, {
                    "new_role":  new_role,
                    "new_slots": new_slots,
                    "pid":       r["place_id"],
                    "old_role":  old_role,
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
