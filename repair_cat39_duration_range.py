#!/usr/bin/env python3
"""
repair_cat39_duration_range.py
cat39(음식) 중 estimated_duration < 40 OR > 90 인 행을
classify_place() 규칙(DURATION_CLAMP 포함)으로 재계산하여 보정한다.

기존 repair_cat39_duration.py(< 40), repair_duration_anomaly.py(> 90) 이후
잔존하거나 새로 발생한 이탈 건을 통합 처리한다.

안전장치:
  - stored_role == new_role 인 행만 estimated_duration 업데이트
  - stored_role != new_role 인 행은 mismatch 리포트, 업데이트 없음
  - UPDATE 조건에 AND estimated_duration = %(old_dur)s 포함 (재실행 안전)

실행:
  python repair_cat39_duration_range.py --dry-run
  python repair_cat39_duration_range.py
"""

import argparse
import sys

import psycopg2
import psycopg2.extras

import config
from batch_rules import classify_place

TARGET_CATEGORY = 39
DURATION_MIN    = 40
DURATION_MAX    = 90


def main() -> None:
    parser = argparse.ArgumentParser(
        description="cat39 estimated_duration 범위 이탈(< 40 OR > 90) 보정 배치")
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
            SELECT place_id, name, overview, visit_role, estimated_duration
            FROM   places
            WHERE  is_active           = TRUE
              AND  category_id         = %s
              AND  estimated_duration  IS NOT NULL
              AND  (estimated_duration < %s OR estimated_duration > %s)
            ORDER BY place_id
        """, (TARGET_CATEGORY, DURATION_MIN, DURATION_MAX))
        rows = [dict(r) for r in cur.fetchall()]

    total = len(rows)
    print(f"\n{'=' * 60}")
    print(f"  cat39 duration 범위 이탈 보정  {label}")
    print(f"  기준: SOT clamp {DURATION_MIN}~{DURATION_MAX}  (< {DURATION_MIN} OR > {DURATION_MAX})")
    print(f"{'=' * 60}")
    print(f"\n{label} 대상: {total}건\n")

    if total == 0:
        print(f"  보정 대상 없음 — 종료")
        conn.close()
        return

    to_update  = []
    no_change  = []
    mismatches = []

    for r in rows:
        result      = classify_place(r["name"], r["overview"], TARGET_CATEGORY)
        new_role    = result["visit_role"]
        new_dur     = result["estimated_duration"]
        stored_role = r["visit_role"]
        old_dur     = r["estimated_duration"]

        entry = {
            "place_id":    r["place_id"],
            "name":        r["name"],
            "stored_role": stored_role,
            "new_role":    new_role,
            "old_dur":     old_dur,
            "new_dur":     new_dur,
        }

        if stored_role != new_role:
            mismatches.append(entry)
        elif old_dur == new_dur:
            no_change.append(entry)
        else:
            to_update.append(entry)

    dist: dict[tuple, int] = {}
    for e in to_update:
        key = (e["old_dur"], e["new_dur"])
        dist[key] = dist.get(key, 0) + 1

    print(f"  {'=' * 54}")
    print(f"  total 대상            : {total:>5}건")
    print(f"  실제 업데이트 대상    : {len(to_update):>5}건  (role 일치 + 값 변경)")
    print(f"  값 동일 skip          : {len(no_change):>5}건  (이미 정상)")
    print(f"  role mismatch skip    : {len(mismatches):>5}건  (업데이트 보류)")

    print(f"\n  old_dur -> new_dur 분포 (업데이트 대상):")
    for (old, new), cnt in sorted(dist.items()):
        print(f"    {old:>4} -> {new:>4}  :  {cnt}건")

    if mismatches:
        print(f"\n  [role mismatch 리포트] — 업데이트 없음")
        for e in mismatches:
            print(f"    place_id={e['place_id']:>6}  "
                  f"stored={e['stored_role']:<8}  new={e['new_role']:<8}  "
                  f"dur={e['old_dur']}->{e['new_dur']}  {e['name'][:24]}")

    if no_change:
        print(f"\n  [값 동일 skip 샘플 (최대 5건)] — classify_place() 결과도 이탈값 반환 중")
        for e in no_change[:5]:
            print(f"    place_id={e['place_id']:>6}  dur={e['old_dur']}  {e['name'][:24]}")
        if len(no_change) > 5:
            print(f"    ... ({len(no_change) - 5}건 생략)")

    if dry:
        print(f"\n{label} dry-run 완료 — 실제 변경 없음")
        conn.close()
        return

    ok = fail = 0
    for e in to_update:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE places
                       SET estimated_duration = %(new_dur)s,
                           updated_at         = NOW()
                     WHERE place_id           = %(pid)s
                       AND estimated_duration = %(old_dur)s
                """, {"new_dur": e["new_dur"], "pid": e["place_id"],
                      "old_dur": e["old_dur"]})
            conn.commit()
            ok += 1
        except Exception as exc:
            conn.rollback()
            print(f"    FAIL place_id={e['place_id']} — {exc}", file=sys.stderr)
            fail += 1

    conn.close()
    print(f"\n{label} 완료 — 성공: {ok}건 / 실패: {fail}건")


if __name__ == "__main__":
    main()
