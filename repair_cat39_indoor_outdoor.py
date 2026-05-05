#!/usr/bin/env python3
"""
repair_cat39_indoor_outdoor.py
cat39(음식) 중 indoor_outdoor = 'outdoor' 인 행을
최신 classify_place() 규칙(STRONG_OUTDOOR_KEYWORDS 기반)으로 재계산한다.

결과:
  - new = 'indoor' → UPDATE (기존 outdoor → indoor 보정)
  - new = 'outdoor' → 유지 (STRONG_OUTDOOR_KEYWORDS 직접 매치, 정상)

안전장치:
  - indoor_outdoor 컬럼만 업데이트 (visit_role / duration 미변경)
  - UPDATE 조건에 AND indoor_outdoor = 'outdoor' 추가 (재실행 안전)

실행:
  python repair_cat39_indoor_outdoor.py --dry-run
  python repair_cat39_indoor_outdoor.py
"""

import argparse
import sys

import psycopg2
import psycopg2.extras

import config
from batch_rules import classify_place

TARGET_CATEGORY = 39


def main() -> None:
    parser = argparse.ArgumentParser(
        description="cat39 indoor_outdoor outdoor->indoor 보정 배치")
    parser.add_argument("--dry-run", action="store_true",
                        help="변경 없이 결과만 출력")
    args = parser.parse_args()
    dry = args.dry_run
    label = "[DRY-RUN]" if dry else "[APPLY]"

    conn = psycopg2.connect(
        host=config.DB_HOST, port=config.DB_PORT,
        dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

    with conn.cursor() as cur:
        cur.execute("""
            SELECT place_id, name, overview, category_id, indoor_outdoor
            FROM   places
            WHERE  is_active       = TRUE
              AND  category_id     = %s
              AND  indoor_outdoor  = 'outdoor'
            ORDER BY place_id
        """, (TARGET_CATEGORY,))
        rows = [dict(r) for r in cur.fetchall()]

    total = len(rows)
    print(f"\n{'=' * 60}")
    print(f"  cat39 indoor_outdoor repair  {label}")
    print(f"{'=' * 60}")
    print(f"\n{label} 대상: {total}건  (cat39, indoor_outdoor='outdoor')\n")

    to_indoor  = []   # new = 'indoor'  → update
    keep_outer = []   # new = 'outdoor' → 유지 (정상 분류)

    for r in rows:
        result  = classify_place(r["name"], r["overview"], TARGET_CATEGORY)
        new_io  = result["indoor_outdoor"]

        entry = {
            "place_id": r["place_id"],
            "name":     r["name"],
            "new_io":   new_io,
        }
        if new_io == "indoor":
            to_indoor.append(entry)
        else:
            keep_outer.append(entry)

    print(f"  {'=' * 54}")
    print(f"  total 대상           : {total:>5}건")
    print(f"  outdoor -> indoor    : {len(to_indoor):>5}건  (보정 대상)")
    print(f"  outdoor 유지         : {len(keep_outer):>5}건  "
          f"(STRONG_OUTDOOR 직접 매치, 정상)")

    if keep_outer:
        print(f"\n  [outdoor 유지 샘플 (최대 10건)]")
        for e in keep_outer[:10]:
            print(f"    place_id={e['place_id']:>6}  {e['name'][:30]}")

    if dry:
        print(f"\n{label} dry-run 완료 — 실제 변경 없음")
        conn.close()
        return

    ok = fail = 0
    for e in to_indoor:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE places
                       SET indoor_outdoor = 'indoor',
                           updated_at     = NOW()
                     WHERE place_id       = %(pid)s
                       AND indoor_outdoor = 'outdoor'
                """, {"pid": e["place_id"]})
            conn.commit()
            ok += 1
        except Exception as exc:
            conn.rollback()
            print(f"  FAIL place_id={e['place_id']} — {exc}", file=sys.stderr)
            fail += 1

    conn.close()
    print(f"\n{label} 완료 — 성공: {ok}건 / 실패: {fail}건")


if __name__ == "__main__":
    main()
