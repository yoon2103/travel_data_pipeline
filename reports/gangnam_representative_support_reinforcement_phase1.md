# Gangnam Representative Support Reinforcement Phase1

## Scope

This phase improves Gangnam support-slot quality by reinforcing representative support candidates, not by expanding penalties.

Implemented:

- Gangnam support-slot only representative support boost
- first-place untouched
- family preservation retained
- existing tiny editorial demote retained
- no replacement
- no hard exclusion
- no global demote

Changed files:

- `course_builder.py`
- `recommendation_observability.py`
- `travel_service_handoff_master_2026-05-18.md`

## Reinforcement Target

The representative boost applies only when:

- `selected_anchor_family_id == seoul_gangnam`
- candidate is a support slot, detected by `previous_place` existing
- candidate matches a Gangnam representative support texture

Representative support terms:

- COEX / Starfield / 별마당
- Garosugil / 신사동
- Apgujeong / Rodeo / Cheongdam
- Bongeunsa / Seonjeongneung / Seolleung / Jeongneung
- Platform-L
- AB Cafe

Support texture direction:

- walk
- cafe/walk
- lifestyle
- urban landmark
- heritage support

## Score Delta

Applied boost:

```text
gangnam_representative_support_boost = +0.035
```

This is support-slot only. It does not apply to first-place scoring.

The existing weak public support tiny demote remains:

```text
gangnam_editorial_soft_demote_delta = -0.028
```

## Observability

Existing trace retained:

- `gangnam_editorial_support_fit`
- `gangnam_weak_public_support_risk`
- `gangnam_repeated_generic_meal_support`
- `gangnam_editorial_soft_demote_applied`

Added trace:

- `gangnam_representative_support_boost_applied`
- `gangnam_representative_support_boost_count`
- `gangnam_representative_support_boost`

## Runtime Smoke

Backend-only deploy was performed.

Smoke targets:

- 강남역 주변: 12 runs
- 성수 감성 카페: 5 runs
- 북촌 한옥 산책: 5 runs

Artifacts:

- `qa_reports/gangnam_representative_support_reinforcement_phase1/runtime_rows.csv`
- `qa_reports/gangnam_representative_support_reinforcement_phase1/summary.json`

## Smoke Summary

| Case | Runs | NO_COURSE | places_empty | representative boost count | weak public total | generic meal total |
|---|---:|---:|---:|---:|---:|---:|
| 강남역 주변 | 12 | 0 | 0 | 271 | 14 | 24 |
| 성수 감성 카페 | 5 | 0 | 0 | 0 | 0 | 0 |
| 북촌 한옥 산책 | 5 | 0 | 0 | 0 | 0 | 0 |
| Total | 22 | 0 | 0 | 271 | 14 | 24 |

## Representative Support Increase

Representative boost was active for Gangnam candidates only.

Observed Gangnam representative texture in final routes:

- COEX first-place/support family appeared frequently.
- `서울 선릉과 정릉 [유네스코 세계유산]` appeared in 10/12 Gangnam runs as heritage support.
- `신사동 가로수길` appeared as first-place in 1/12 runs.

However, support-slot editorial fit did not improve enough:

| Metric | Result |
|---|---:|
| avg Gangnam fit ratio | 0.2083 |
| weak public support avg per run | 1.17 |
| generic meal support avg per run | 2.00 |

Interpretation:

- Representative support candidates are present and boosted.
- The selected route still often keeps `국가무형유산전수교육관` and generic meal slots.
- This suggests the issue is not only scoring preference. It likely includes support-slot assembly ordering, candidate depth, and the absence of stronger same-family alternatives in the same slot window.

## Weak Support Change

Previous tiny-demote phase:

- weak public total: 14 / 10 runs
- avg weak public per run: 1.40

This phase:

- weak public total: 14 / 12 runs
- avg weak public per run: 1.17

Result:

- There is a small directional improvement versus the immediate previous phase.
- It is not strong enough to call the issue solved.

## Side Effect Check

### 성수

- `NO_COURSE=0`
- `places_empty=0`
- Gangnam boost count: 0
- cafe district identity remained active.
- No Gangnam policy leakage observed.

### 북촌

- `NO_COURSE=0`
- `places_empty=0`
- Gangnam boost count: 0
- heritage/walk flow remained active.
- No Gangnam policy leakage observed.

## First-Place Stability

Gangnam first-place distribution:

| First Place | Count |
|---|---:|
| 코엑스동측광장 | 5 |
| 코엑스 아쿠아리움 | 3 |
| 압구정곱창 | 3 |
| 신사동 가로수길 | 1 |

No family drift was observed in the smoke sample.

## Rollback Need

Rollback is not required for stability:

- no NO_COURSE
- no places_empty
- no side effect in 성수/북촌
- no production DB write
- no migration
- no saju impact

But the quality improvement is partial. Do not expand this by raising penalties globally.

## Next Direction

Recommended next step:

1. Keep the representative support boost.
2. Do not increase global or public-facility demote.
3. Inspect why `국가무형유산전수교육관` remains the first support slot even when boosted representative supports exist.
4. Focus on support-slot assembly order or stronger same-family candidate depth.
5. Avoid replacement until the candidate ordering cause is confirmed.

Still prohibited:

- global demote
- penalty expansion
- hard exclusion
- replacement
- first-place changes
- recommendation engine rewrite

## Safety

- production migration: not executed
- production places write: not executed
- docker compose down: not used
- saju impact: none

