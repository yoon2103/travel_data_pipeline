# Meal Repetition Soft Demote Phase1

## Scope

- Goal: test a very small bounded soft demote for support-slot `meal -> meal` repetition.
- Target phase: support-slot role diversity phase3.
- Primary runtime target: 한남 감성.
- Side-effect check: 성수 감성 카페.

## Applied Rule

The rule is intentionally narrow:

- Applies only when `selected_anchor_family_id == seoul_hannam`.
- Applies only after the first place, because it requires a previous selected place.
- Applies only when both the previous selected place and the current candidate are meal-like.
- Does not remove candidates.
- Does not force replacement.
- Does not alter first-place selection.
- Does not change cafe repetition, indoor-heavy handling, walk/viewpoint boost, or family preservation.

Penalty:

- `same_role_soft_demote_delta = 0.018`

This is deliberately tiny. It only gives nearby same-family non-meal support candidates a small chance to win naturally.

## Trace Fields

Added or exposed:

- `same_role_soft_demote_applied`
- `same_role_soft_demote_role`
- `same_role_soft_demote_delta`
- `same_role_soft_demote_applied_count`

Candidate score samples also include:

- `same_role_soft_demote_applied`
- `same_role_soft_demote_role`
- `same_role_soft_demote_delta`

## Before Signal

Previous runtime trace smoke for 한남 showed meal repetition in both small samples:

| Phase | Runs | Meal repetition samples |
|---|---:|---:|
| role sequence trace runtime smoke | 2 | 2 |

Observed examples:

- `walk -> meal -> meal -> cafe`
- `meal -> meal -> walk -> cafe`

## After Smoke

Runtime after backend redeploy:

| District | Runs | NO_COURSE | places_empty | Meal repetition samples | Trace applied |
|---|---:|---:|---:|---:|---|
| 한남 감성 | 5 | 0 | 0 | 0 | yes |
| 성수 감성 카페 | 3 | 0 | 0 | 0 | no |

## 한남 Samples

| Run | Places | Role sequence | Repetition | Coherence |
|---:|---|---|---|---:|
| 1 | 플랜트, 아티스푼, 부다스벨리 이태원, 알부스갤러리, 르몽블랑 | `gallery -> meal -> gallery -> cafe` | none | 0.876 |
| 2 | Summer Lane, 달맞이근린공원, 두에꼬제, 어반아트, 레인리포트 경리단 | `walk -> meal -> market -> cafe` | none | 0.880 |
| 3 | 플랜트, 아티스푼, 베라 한남점, 달맞이근린공원, 크레이트커피 | `gallery -> meal -> walk -> cafe` | none | 0.884 |
| 4 | Summer Lane, 알부스갤러리, 뇨끼바, 달맞이근린공원, 오엔 | `gallery -> meal -> walk -> walk` | walk repetition only | 0.880 |
| 5 | Summer Lane, 해방촌마을, 부다스벨리 이태원, 알부스갤러리, 크레이트커피 | `other -> meal -> gallery -> cafe` | none | 0.880 |

Result:

- `meal -> meal` decreased from `2/2` in the previous small smoke to `0/5`.
- One `walk -> walk` repetition remained. This phase intentionally does not target walk repetition.
- No places-empty or NO_COURSE occurred.

## 성수 Side Effect Check

| Run | Places | Role sequence | Trace applied |
|---:|---|---|---|
| 1 | 성수동 카페거리, 아방베이커리 서울숲점, 계자람, 헬로우뮤지움, 원기옥 | `cafe -> meal -> gallery -> walk` | false |
| 2 | 크림라벨 서울숲 본점, 성수동 수제화거리, 뚝도지기, 성수동 카페거리, 우오보 | `walk -> meal -> walk -> other` | false |
| 3 | 서울숲 곤충식물원, 레이더, 뚝도지기, 성수동 카페거리, 에이치커피로스터스 | `cafe -> meal -> walk -> cafe` | false |

Result:

- 성수 cafe identity was not penalized.
- `same_role_soft_demote_applied=false` for all 성수 samples.
- No forced walk/weak slot insertion was observed.

## Runtime Safety

- NO_COURSE: 0
- places_empty: 0
- production places write: none
- production migration: none
- `docker compose down`: not used
- saju impact: none
- frontend schema break: not observed

## Future Safe Range

This penalty size is safe enough for continued observation, but it should not be expanded yet.

Recommended next step:

- Keep the `0.018` Hannam-only meal repetition demote.
- Collect more runtime traces before applying to other districts.
- Do not apply cafe repetition demote to cafe-led districts such as 성수.
- Do not add bounded replacement until trace data shows a persistent failure that soft scoring cannot reduce.
