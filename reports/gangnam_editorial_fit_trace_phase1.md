# Gangnam Editorial Fit Trace Phase1

## Scope

- Goal: add trace-only observability for 강남 editorial support quality.
- This phase does not score, demote, filter, replace, or lock routes.
- Implementation location: `recommendation_observability.py`.
- Runtime target: 강남역 주변.

## Added Trace Fields

The following fields are exposed in `recommendation_trace`:

- `gangnam_editorial_support_fit`
- `gangnam_weak_public_support_risk`
- `gangnam_repeated_generic_meal_support`
- `gangnam_support_candidate_tags`

These are computed from final selected route places only. They do not affect ranking or selection.

## Support Candidate Tags

Trace-only tags:

| Tag | Meaning |
|---|---|
| `coex_family` | COEX, Starfield, 별마당/urban landmark family |
| `garosugil_walk` | 신사동/가로수길/로데오 walk texture |
| `apgujeong_cheongdam_lifestyle` | 압구정/청담 lifestyle/gallery support |
| `bongeunsa_heritage` | 봉은사/선정릉/선릉과 정릉 heritage support |
| `curated_cafe_walk_support` | cafe/walk support texture |
| `weak_public_training` | 국기원/전수교육관/training-style support risk |
| `weak_indoor_education` | education/science/indoor public support risk |
| `weak_culture_hall` | hall/culture venue support risk |
| `weak_lifestyle` | weak lifestyle support risk |
| `weak_generic_meal` | repeated generic/luxury meal support risk |

## Runtime Smoke

- Runs: 6
- Endpoint: production `/api/course/generate`
- District: 강남역 주변
- Raw output:
  - `qa_reports/gangnam_editorial_fit_trace_phase1/runtime_rows.csv`
  - `qa_reports/gangnam_editorial_fit_trace_phase1/summary.json`

| Metric | Result |
|---|---:|
| runs | 6 |
| NO_COURSE | 0 |
| places_empty | 0 |
| avg editorial support fit ratio | 0.2917 |
| weak public support risk total | 6 |
| generic meal support risk total | 11 |
| production places row count | 26381 |

## Observed Runtime Samples

| Run | Places | Fit ratio | Weak public risk | Generic meal risk |
|---:|---|---:|---:|---:|
| 1 | 코엑스동측광장, 국가무형유산전수교육관, 송화유수, 신사동 가로수길, 콴안다오 | 0.25 | 1 | 2 |
| 2 | 코엑스 아쿠아리움, 슈피겐홀, 토말 본점, 신사동 가로수길, 콴안다오 | 0.25 | 1 | 2 |
| 3 | 압구정곱창, 신사동 가로수길, 알라프리마, 서울 선릉과 정릉, 에이비카페 | 0.75 | 0 | 1 |
| 4 | 코엑스동측광장, 국가무형유산전수교육관, 진수사, 국기원, 콴안다오 | 0.00 | 2 | 2 |
| 5 | 코엑스 아쿠아리움, 슈피겐홀, 토말 본점, 신사동 가로수길, 콴안다오 | 0.25 | 1 | 2 |
| 6 | 신사동 가로수길, 국기원, 송화유수, 플랫폼엘, 콴안다오 | 0.25 | 1 | 2 |

## Weak Support Risk Frequency

Weak public/training/culture risk appeared in every run except run 3.

Observed candidates:

- 국가무형유산전수교육관
- 슈피겐홀
- 국기원(세계태권도본부)

These remain real places and are not hard-invalid. The risk is repeated support-slot editorial weakness.

## Repeated Generic Meal Support Frequency

Generic meal/luxury meal risk appeared in all 6 runs.

Observed candidates:

- 송화유수
- 콴안다오
- 토말 본점
- 알라프리마
- 진수사

This supports the previous audit finding: the issue is not role repetition, but repeated weak meal support texture.

## Safety Verification

- Behavior change: none intended.
- Scoring change: none.
- Filtering change: none.
- Replacement: none.
- NO_COURSE: 0
- places_empty: 0
- frontend schema issue: not observed.
- production migration: not executed.
- production places write: not executed.
- `docker compose down`: not used.
- saju impact: none.

## Future Bounded Demote Possibility

Do not implement a demote yet.

If a future phase is approved, the safest direction is:

1. Keep it 강남 support-slot only.
2. Do not touch first-place.
3. Do not apply global public-facility or global meal demote.
4. Start with a tiny soft demote for repeated weak public/training support risk only.
5. Keep generic meal handling separate and evidence-based.

Still prohibited:

- global penalty
- hard exclusion
- bounded replacement
- cafe repetition demote
- broad scoring rewrite

## Conclusion

Trace-only observability is working and confirms the weak support quality problem:

- editorial fit ratio is often low
- weak public/training risk is frequent
- generic meal support risk is frequent

The next step should remain observability accumulation or a separate proposal. Immediate demote is not yet justified.
