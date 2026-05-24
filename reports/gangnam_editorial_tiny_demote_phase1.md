# Gangnam Editorial Tiny Demote Phase1

## Scope

This phase moved from proposal-only work to a small bounded runtime implementation.

Implemented:

- Gangnam support-slot only editorial tiny demote
- no first-place demote
- no hard exclusion
- no replacement
- no global public-facility demote
- no global meal demote

Files changed:

- `course_builder.py`
- `recommendation_observability.py`
- `travel_service_handoff_master_2026-05-18.md`

## Applied Target

The tiny demote applies only when all conditions are true:

- `selected_anchor_family_id == seoul_gangnam`
- candidate is not first-place
- candidate is a support-slot candidate, detected by `previous_place` existing
- candidate name/category text matches a weak public/training/culture-style term

Target terms:

- 국가무형유산전수교육관
- 전수교육관
- 국기원
- 태권도본부
- 슈피겐홀
- 한생연
- 실험누리과학관

Excluded:

- generic meal demote
- cafe repetition demote
- indoor-heavy penalty
- bounded replacement
- first-place changes

## Score Delta

Final applied delta:

```text
gangnam_editorial_soft_demote_delta = 0.028
```

This is subtracted from candidate score only for the scoped support-slot candidates above.

The initial `0.014` delta was smoke-tested first but had no observable effect, so the delta was adjusted to `0.028` while keeping the same scope.

## Trace

Existing trace fields are preserved:

- `gangnam_editorial_support_fit`
- `gangnam_weak_public_support_risk`
- `gangnam_repeated_generic_meal_support`

Added runtime trace:

- `gangnam_editorial_soft_demote_applied`
- `gangnam_editorial_soft_demote_count`
- `gangnam_editorial_soft_demote_delta`

## Runtime Smoke

Runtime smoke was executed after backend-only deploy.

Targets:

- 강남역 주변: 10 runs
- 성수 감성 카페: 5 runs
- 북촌 한옥 산책: 5 runs

Output artifacts:

- `qa_reports/gangnam_editorial_tiny_demote_phase1/runtime_rows.csv`
- `qa_reports/gangnam_editorial_tiny_demote_phase1/summary.json`

## Final Smoke Result

| Case | Runs | NO_COURSE | places_empty | editorial demote count | weak public total | generic meal total |
|---|---:|---:|---:|---:|---:|---:|
| 강남역 주변 | 10 | 0 | 0 | 20 | 14 | 20 |
| 성수 감성 카페 | 5 | 0 | 0 | 0 | 0 | 0 |
| 북촌 한옥 산책 | 5 | 0 | 0 | 0 | 0 | 0 |
| Total | 20 | 0 | 0 | 20 | 14 | 20 |

## Before / After

Previous trace baseline:

| Metric | Baseline |
|---|---:|
| 강남 runs | 6 |
| NO_COURSE | 0 |
| places_empty | 0 |
| weak public support risk | 6 |
| generic meal support risk | 11 |
| avg weak public per run | 1.00 |

After tiny demote:

| Metric | After |
|---|---:|
| 강남 runs | 10 |
| NO_COURSE | 0 |
| places_empty | 0 |
| weak public support risk | 14 |
| generic meal support risk | 20 |
| avg weak public per run | 1.40 |

Interpretation:

- Stability improved or remained safe: yes.
- Weak public support reduction: not confirmed.
- The tiny demote is being applied, but weak candidates can still win when the candidate pool does not offer a stronger same-family support alternative.

## First-Place Stability

강남 first-place distribution after final smoke:

| First place | Count |
|---|---:|
| 코엑스 아쿠아리움 | 6 |
| 압구정곱창 | 2 |
| 코엑스동측광장 | 2 |

No family drift was observed in the smoke sample.

## Side Effect Check

### 성수

- `NO_COURSE=0`
- `places_empty=0`
- `gangnam_editorial_soft_demote_count=0`
- cafe district identity remained active.
- No Gangnam policy leakage observed.

### 북촌

- `NO_COURSE=0`
- `places_empty=0`
- `gangnam_editorial_soft_demote_count=0`
- heritage/walk route flow remained active.
- No Gangnam policy leakage observed.

## Rollback Need

Rollback is not required for runtime stability:

- no NO_COURSE increase
- no places_empty
- no observed family drift
- no frontend schema impact
- production places row count unchanged

However, the quality effect is not sufficient yet.

Do not expand this into global demote. Do not increase broadly.

## Recommendation

The result shows that a tiny score delta alone is not enough to clean up Gangnam weak support candidates.

The safer next step is not a stronger global penalty. The safer next step is:

1. keep this scoped trace/demote as a small guard
2. inspect whether weak candidates enter through support replacement/family alignment
3. reinforce better Gangnam representative support candidates
4. only then consider another Gangnam-only support-slot adjustment

Still prohibited:

- global public-facility demote
- global meal demote
- hard exclusion
- bounded replacement
- first-place changes
- recommendation engine rewrite

## Safety

- production migration: not executed
- production places write: not executed
- docker compose down: not used
- saju impact: none

