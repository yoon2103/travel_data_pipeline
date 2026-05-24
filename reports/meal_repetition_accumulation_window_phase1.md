# Meal Repetition Accumulation Window Phase1

## Scope

- Goal: short accumulation observation after the 한남 meal repetition tiny soft demote.
- This is not an expansion phase.
- No new role demote, cafe repetition demote, indoor-heavy penalty, bounded replacement, or route lock was added.

Current penalty under observation:

- Target: `seoul_hannam` only
- Condition: support-slot candidate where previous selected semantic role is meal and current candidate semantic role is meal
- Delta: `0.018`
- Behavior: soft score demote only, no candidate removal

## Runtime Sample

- Date: 2026-05-24
- Endpoint: production `/api/course/generate`
- Districts: 한남, 성수, 북촌, 강남
- Runs: 6 each, 24 total
- Raw summary files:
  - `qa_reports/meal_repetition_accumulation_window_phase1/runtime_rows.csv`
  - `qa_reports/meal_repetition_accumulation_window_phase1/summary.json`

## Summary

| District | Runs | NO_COURSE | places_empty | meal repetition | cafe repetition | soft demote count sum | avg role balance | avg coherence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 한남 | 6 | 0 | 0 | 0 | 0 | 24 | 0.9700 | 0.7847 |
| 성수 | 6 | 0 | 0 | 0 | 0 | 0 | 0.8350 | 0.8573 |
| 북촌 | 6 | 0 | 0 | 0 | 0 | 0 | 1.0000 | 0.7920 |
| 강남 | 6 | 0 | 0 | 0 | 0 | 0 | 1.0000 | 0.7780 |

## 한남 Stability

한남은 6회 모두 `meal -> meal` repetition이 재발하지 않았다.

Observed sequences:

- `gallery -> meal -> gallery -> cafe`
- `gallery -> meal -> viewpoint -> cafe`
- `gallery -> meal -> walk -> meal`
- `gallery -> meal -> walk -> walk`
- `gallery -> meal -> viewpoint -> cafe`
- `gallery -> meal -> gallery -> cafe`

Interpretation:

- Meal repetition is reduced without forcing a fixed role sequence.
- One `walk -> walk` repetition appeared, but this phase intentionally does not target walk repetition.
- No route collapse, places-empty, or NO_COURSE occurred.
- No obvious family drift was observed.

## 성수 Side Effect Check

성수 is the key cafe-led district to protect.

Result:

- `same_role_soft_demote_count_sum = 0`
- No cafe repetition suppression was applied.
- Cafe/walk texture remained visible.
- No forced weak replacement was observed.

Observed sequences included:

- `walk -> meal -> walk -> walk`
- `cafe -> meal -> walk -> cafe`
- `walk -> meal -> walk -> cafe`
- `landmark_support -> meal -> walk -> other`

Interpretation:

- The Hannam-only guard is working.
- Cafe district identity was not affected by the meal repetition penalty.

## Residual Observations

These are not caused by the new penalty, but should remain visible for later quality work:

- 강남 still shows occasional weak/support candidates such as public/culture-style venues and luxury meal slots.
- 북촌 had one lower coherence sample, but no role repetition or places-empty issue.
- 성수 has repeated walk texture in some samples, but this is currently preferable to suppressing cafe-led identity too aggressively.

## Runtime Safety

- NO_COURSE: 0 / 24
- places_empty: 0 / 24
- production migration: not executed
- production places write: not executed
- `docker compose down`: not used
- saju impact: none
- frontend schema impact: none observed

## Future Safe Range

Current `0.018` penalty is safe enough to keep under observation.

Recommended:

- Keep the penalty Hannam-only for now.
- Do not expand to cafe repetition.
- Do not add indoor-heavy penalty yet.
- Do not add bounded replacement yet.
- Continue gathering trace data before applying to 강남/북촌/성수.

The next defensible expansion, if needed, would be a similarly tiny support-slot-only meal repetition demote for another district with repeated evidence. It should not be generalized globally.
