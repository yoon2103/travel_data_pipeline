# Gangnam Editorial Support Cleanup Phase1

## Scope

- Goal: define a read-only editorial support-slot cleanup proposal for 강남.
- Based on: `reports/gangnam_support_candidate_audit_phase1.md`.
- No production behavior change.
- No scoring change.
- No demote, replacement, migration, or production places write.

## Current Finding

강남 does not currently show a role repetition failure.

Observed 10-run audit:

- NO_COURSE: 0
- places_empty: 0
- role repetition: 0
- avg role balance: 1.0000
- avg route coherence: 0.7896

The remaining issue is editorial support quality:

- public/training/culture-style venues repeat as support slots
- generic meal candidates repeat
- some support slots feel weak compared with the expected 강남 representative flow

## Representative Support Taxonomy

Recommended 강남 support-slot families:

| Group | Examples | Support Role Intent |
|---|---|---|
| COEX-family | 코엑스, 코엑스동측광장, 별마당도서관, Starfield, 봉은사 인접 흐름 | urban landmark, indoor/outdoor landmark support |
| Garosugil walk | 신사동 가로수길, 가로수길 편집숍/카페 흐름 | lifestyle walk, cafe/walk support |
| Apgujeong/Cheongdam lifestyle | 압구정 로데오, 청담 패션/갤러리/라이프스타일 | editorial lifestyle, gallery/cafe support |
| Bongeunsa heritage support | 봉은사, 선정릉, 선릉과 정릉 | heritage support, calm walk |
| Starfield/urban landmark | 별마당도서관, 스타필드 계열, COEX urban flow | strong indoor landmark when verified |
| Curated cafe/walk support | representative cafe, walkable lifestyle streets | light support texture |

The target is not “tourist attraction only.” 강남 is an urban/lifestyle district, so curated lifestyle and walk support should remain valid.

## Weak Risk Taxonomy

### Public/Training Venue

Observed:

- 국기원(세계태권도본부)
- 국가무형유산전수교육관

Why it feels weak:

- It is institution/training-like rather than user-facing travel support.
- It can be legitimate as a place, but weak as a repeated itinerary support slot.
- It may dilute COEX/Garosugil/Apgujeong lifestyle flow.

When it may be allowed:

- If selected anchor explicitly requests martial arts/traditional culture.
- If no better same-family support candidate exists.
- If it appears as a low-frequency fallback, not a repeated route texture.

Hard-invalid? No.

- These are real places.
- They should not be globally excluded.

### Generic Indoor Education/Culture

Observed:

- 한생연 실험누리과학관
- 슈피겐홀

Why it feels weak:

- Indoor education/culture/brand venue may not match broad 강남 lifestyle expectation.
- It can feel like facility data rather than a representative route choice.

When it may be allowed:

- Family/date/indoor-specific context.
- Verified event/culture intent.
- Explicit anchor match.

Hard-invalid? No.

- Context-dependent.
- Should be softly ranked, not removed.

### Weak Lifestyle Slot

Observed:

- 반려문화

Why it feels weak:

- Low representative signal for a general 강남 route.
- The name/category does not clearly support a travel flow.

When it may be allowed:

- Pet-friendly intent.
- Specific lifestyle theme.
- Low-frequency fallback only.

Hard-invalid? No.

- Needs better context alignment, not deletion.

## Repeated Meal Support Analysis

Observed repeated meal/generic support candidates:

| Candidate | Count in 10 runs | Risk |
|---|---:|---|
| 진수사 | 8 | repeated meal support, weak 강남 identity texture |
| 콴안다오 | 5 | repeated generic meal/other support |
| 토말 본점 | 1 | low-frequency meal support |
| 알라프리마 | 1 | luxury meal, can feel overly restaurant-led |
| 압구정곱창 | first-place 1 | meal-first route start risk |

Assessment:

- A single meal slot is valid.
- The problem is not meal itself, but repeated generic meal candidates becoming the support texture.
- A global meal demote would be incorrect and risky.
- A future policy should be 강남 support-slot only and candidate-quality aware.

## Editorial-Fit Proposal

Proposal only. Not implemented.

### Candidate Preference

Prefer support slots that match one of:

- COEX/Starfield urban landmark
- Garosugil/Apgujeong/Cheongdam lifestyle walk
- Bongeunsa/Seonjeongneung heritage walk
- curated cafe/walk support
- gallery/editorial lifestyle when district-aligned

### Weak Candidate Tiny Penalty

Possible future rule:

- Scope: 강남 support-slot only
- Target: repeated public/training/weak culture support candidates
- Method: tiny soft demote
- First-place: untouched
- Hard exclusion: prohibited
- Replacement: prohibited unless a separate future phase proves it is safe

### Repeated Meal Guard

Possible future rule:

- Scope: 강남 support-slot only
- Target: repeated generic meal candidates with weak representative signal
- Method: tiny soft demote or saturation, not global meal demote
- Exception: strong/curated dining context, explicit food intent

## Bounded Cleanup Direction

Recommended if a future implementation phase is approved:

1. Add observability counters first:
   - `gangnam_editorial_support_fit`
   - `gangnam_weak_public_support_risk`
   - `gangnam_repeated_generic_meal_support`
2. Keep changes support-slot only.
3. Keep first-place selection untouched.
4. Apply tiny score delta only after another runtime accumulation window.
5. Run 강남 + 성수 + 북촌 regression before deployment.

## Still Prohibited

- Global public-facility demote
- Global meal demote
- Cafe repetition demote
- Hard exclusion
- Hard route lock
- Bounded replacement
- Broad scoring rewrite
- Production migration/write

## Recommendation

Do not implement demote yet.

The next safe step is a trace-only 강남 editorial support-fit counter. If that confirms repeated weak support candidates over a larger sample, implement a 강남-only tiny soft demote in a separate phase.
