#!/usr/bin/env python3
"""
repair_cat39_role_mismatch.py
cat39(음식)에서 visit_role이 음식 카테고리 허용값(meal / cafe) 밖인 행을
classify_place()로 재분류하고 4개 가공 필드를 함께 보정한다.

패턴:
  cat39의 정상 role = 'meal' 또는 'cafe' (batch_rules.DEFAULT_ROLE/CAFE_KEYWORDS 기준)
  'spot' / 'culture' / 'rest' 등은 다른 카테고리 기본값이 잘못 배정된 것으로 본다.
  role 오분류 시 duration도 잘못된 clamp가 적용되어 이탈값이 된다.

처리 대상:
  category_id = 39, is_active = TRUE,
  visit_role NOT IN ('meal', 'cafe')  AND visit_role IS NOT NULL

처리 방식:
  classify_place() 재계산 → 4개 필드 모두 보정
  (기존 값이 잘못된 role 기반으로 산출되었으므로 전체 교체가 맞음)

안전장치:
  UPDATE WHERE 조건에 AND visit_role = %(old_role)s
                       AND estimated_duration = %(old_dur)s 포함 → 재실행 안전

실행:
  python repair_cat39_role_mismatch.py --dry-run
  python repair_cat39_role_mismatch.py
"""

import argparse
import sys

import psycopg2
import psycopg2.extras

import config
from batch_rules import classify_place

TARGET_CATEGORY    = 39
CAT39_VALID_ROLES  = {"meal", "cafe"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="cat39 role mismatch(meal/cafe 외) → 규칙 기반 재분류 및 4필드 보정")
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
                   visit_role, estimated_duration, visit_time_slot, indoor_outdoor
            FROM   places
            WHERE  is_active     = TRUE
              AND  category_id   = %s
              AND  visit_role    IS NOT NULL
              AND  visit_role    NOT IN ('meal', 'cafe')
            ORDER BY place_id
        """, (TARGET_CATEGORY,))
        rows = [dict(r) for r in cur.fetchall()]

    total = len(rows)
    print(f"\n{'=' * 60}")
    print(f"  cat39 role mismatch 보정  {label}")
    print(f"  대상: category_id=39, visit_role NOT IN (meal/cafe)")
    print(f"{'=' * 60}")
    print(f"\n{label} 대상: {total}건\n")

    if total == 0:
        print(f"  보정 대상 없음 — 종료")
        conn.close()
        return

    ok = fail = 0

    for i, r in enumerate(rows, 1):
        result = classify_place(r["name"], r["overview"], TARGET_CATEGORY)

        old_role = r["visit_role"]
        old_dur  = r["estimated_duration"]
        new_role = result["visit_role"]
        new_dur  = result["estimated_duration"]
        new_slot = result["visit_time_slot"]
        new_io   = result["indoor_outdoor"]

        print(f"  [{i}/{total}] place_id={r['place_id']:>6}  {r['name'][:30]}")
        print(f"    role     : {old_role!r:>10}  ->  {new_role!r}")
        print(f"    duration : {old_dur!r:>10}  ->  {new_dur!r}")
        print(f"    slot     : {r['visit_time_slot']}  ->  {new_slot}")
        print(f"    io       : {r['indoor_outdoor']!r:>10}  ->  {new_io!r}")

        if dry:
            continue

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE places
                       SET visit_role         = %(new_role)s,
                           estimated_duration = %(new_dur)s,
                           visit_time_slot    = %(new_slot)s,
                           indoor_outdoor     = %(new_io)s,
                           updated_at         = NOW()
                     WHERE place_id           = %(pid)s
                       AND visit_role         = %(old_role)s
                       AND estimated_duration = %(old_dur)s
                """, {
                    "new_role": new_role,
                    "new_dur":  new_dur,
                    "new_slot": new_slot,
                    "new_io":   new_io,
                    "pid":      r["place_id"],
                    "old_role": old_role,
                    "old_dur":  old_dur,
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
        print(f"  [DRY-RUN] 완료 — 실제 변경 없음  (예상 보정: {total}건)")
    else:
        print(f"  [APPLY] 완료 — 성공: {ok}건 / 실패: {fail}건")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
