# Gangnam Weak Support Candidate Action Plan Phase1

## Scope

This phase is read-only documentation based on the existing Gangnam editorial fit trace.

No implementation was applied:

- no demote
- no score change
- no replacement
- no filtering
- no DB write
- no migration

Current baseline from `gangnam_editorial_fit_trace_phase1`:

| Metric | Value |
|---|---:|
| smoke runs | 6 |
| NO_COURSE | 0 |
| places_empty | 0 |
| weak_public_support_risk | 6 |
| generic_meal_support_risk | 11 |
| avg editorial support fit ratio | 0.2917 |

## Cause-Based Candidate Classification

### Public / Training

| Candidate | Observed Pattern | Why It Feels Weak | Direction |
|---|---|---|---|
| 국가무형유산전수교육관 | repeated support slot | Real institution, but not a natural Gangnam trip support slot for casual/mobile recommendations | future tiny demote candidate |
| 국기원(세계태권도본부) | repeated support slot | Iconic but context-dependent; can feel like a public/training venue rather than lifestyle support | soft observe |

Decision:

- Do not hard-exclude.
- Keep as valid real places.
- If cleanup is approved later, apply only Gangnam support-slot tiny penalty, not global public-facility demote.

### Generic Meal

| Candidate | Observed Pattern | Why It Feels Weak | Direction |
|---|---|---|---|
| 콴안다오 | repeated in support slot | Repeated cafe/meal-like support texture; weak Gangnam representative identity | future tiny demote candidate |
| 진수사 | repeated in previous audit and trace | Meal-first slot; can weaken COEX/Garosugil/Cheongdam flow when repeated | soft observe |
| 토말 본점 | repeated in trace | Good real meal candidate, but generic support role if it replaces landmark/walk/culture texture | soft observe |
| 송화유수 | repeated in trace | Meal-first texture, weak as representative support | soft observe |
| 알라프리마 | observed once in trace | High-end dining can fit Gangnam, but may feel luxury-meal-first rather than district support | keep / soft observe |

Decision:

- No global meal demote.
- Do not suppress meals broadly; Gangnam still needs meal/cafe options.
- Future cleanup should only target repeated generic meal support when better same-family support exists.

### Weak Indoor / Culture

| Candidate | Observed Pattern | Why It Feels Weak | Direction |
|---|---|---|---|
| 슈피겐홀 | repeated support slot | Indoor hall/culture venue; weak travel support unless event-specific intent exists | future tiny demote candidate |
| 한생연 실험누리과학관 | previous audit weak candidate | Indoor education/science texture; not a broad Gangnam representative support slot | future tiny demote candidate |
| 반려문화 | previous audit weak candidate | Weak lifestyle/public texture; unclear tourist intent | soft observe |

Decision:

- Keep valid but treat as context-dependent.
- Do not globally demote indoor/culture venues.
- Future policy, if any, should be support-slot only and Gangnam scoped.

### Weak Lifestyle

| Candidate | Observed Pattern | Why It Feels Weak | Direction |
|---|---|---|---|
| 플랫폼엘 | positive tagged in trace as Apgujeong/Cheongdam lifestyle | Can support Gangnam lifestyle if paired well; not currently a cleanup target | keep |
| 에이비카페 | positive tagged as curated cafe/walk support | Useful cafe/walk support texture | keep |

Decision:

- Do not demote these.
- These are examples of the direction Gangnam support slots should move toward: lifestyle, cafe/walk, gallery, urban landmark texture.

## Candidate-Level Action Direction

| Candidate | Cause Group | Suggested Action | Notes |
|---|---|---|---|
| 국가무형유산전수교육관 | public/training | future tiny demote candidate | support-slot only, Gangnam only |
| 국기원(세계태권도본부) | public/training | soft observe | iconic but context-dependent |
| 슈피겐홀 | weak indoor/culture | future tiny demote candidate | event/hall context risk |
| 한생연 실험누리과학관 | weak indoor/culture | future tiny demote candidate | previous audit candidate |
| 반려문화 | weak lifestyle/public | soft observe | weak representative intent |
| 콴안다오 | generic meal | future tiny demote candidate | repeated heavily |
| 진수사 | generic meal | soft observe | repeated, but do not global-demote meal |
| 토말 본점 | generic meal | soft observe | acceptable meal, weak if overused |
| 송화유수 | generic meal | soft observe | weak representative texture |
| 알라프리마 | generic/luxury meal | keep / soft observe | premium dining may fit Gangnam in some contexts |
| 플랫폼엘 | lifestyle support | keep | useful curated lifestyle support |
| 에이비카페 | cafe/walk support | keep | useful support texture |
| 신사동 가로수길 | Garosugil walk | keep | strong representative support |
| 서울 선릉과 정릉 | heritage support | keep | strong heritage support |

## Representative Support Reinforcement Direction

The safer next step is candidate reinforcement and editorial preference definition before demote.

Priority support families:

| Family | Desired Support Texture |
|---|---|
| COEX | Starfield, COEX mall/plaza, urban landmark, book/culture texture |
| Bongeunsa / Seonjeongneung | heritage walk, calm landmark support, historical contrast |
| Garosugil | walk, cafe, lifestyle street, small gallery/store texture |
| Apgujeong / Cheongdam | lifestyle, fashion, gallery, curated cafe |
| Curated cafe / walk | cafe plus walk support, not meal-only support |

Reinforcement should focus on:

- increasing same-family representative support candidates
- improving support slot texture diversity
- avoiding meal-first collapse
- keeping first-place selection untouched

## Recommended Future Policy, Not Yet Implemented

If the next phase is approved, the smallest safe policy would be:

1. Scope to Gangnam support slots only.
2. Do not touch first-place.
3. Do not apply global public-facility or global meal demote.
4. Apply only a tiny editorial-risk penalty after repeated observation.
5. Allow the current candidate to remain when no better same-family support candidate exists.
6. Keep trace fields active to compare before/after.

Suggested candidate order for future cleanup:

1. `국가무형유산전수교육관`
2. `슈피겐홀`
3. `콴안다오`
4. `한생연 실험누리과학관`

Do not start with `국기원`, `알라프리마`, or all meals globally. Those are more context-dependent and have higher false-positive risk.

## Still Prohibited

- demote in this phase
- score change in this phase
- bounded replacement
- hard exclusion
- global public-facility demote
- global meal demote
- production migration
- production places write

## Conclusion

The trace confirms the issue is not role repetition. The current weak points are:

- public/training-style support candidates
- repeated generic meal support
- weak indoor/culture venues

The recommended direction is not immediate demote. The safer order is:

1. keep trace accumulation
2. reinforce representative Gangnam support candidate families
3. then test a Gangnam-only, support-slot-only tiny cleanup if repeated risk persists

