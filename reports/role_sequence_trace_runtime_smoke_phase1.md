# Role Sequence Trace Runtime Smoke Phase1

## Scope

- Goal: production-safe deployment of support-slot role sequence trace and small runtime smoke observation.
- Deploy target: travel backend only.
- Behavior change: none intended. This phase exposes observability fields only.
- Excluded changes: scoring changes, candidate removal, bounded replacement, route lock, fake diversity, DB migration, production places write.

## Deployment

- Backend files deployed:
  - `recommendation_observability.py`
  - `course_builder.py`
- Deploy command:
  - `docker compose -p travel_service_prod build travel-backend`
  - `docker compose -p travel_service_prod up -d --no-deps travel-backend`
- `docker compose down`: not used.
- Saju containers: untouched and running.

## Smoke Result

- `/api/regions`: 200
- `travel-backend-v2`: running
- `travel-frontend-v2`: running
- `saju_mbti-*`: running
- production `places` row count: 26381
- production migration: not executed
- production places write: not executed

## Runtime Trace Fields

The following fields were observed in actual `/api/course/generate` responses after redeploy:

- `support_slot_role_sequence`
- `support_slot_role_repetition`
- `support_slot_indoor_count`
- `support_slot_missing_preferred_roles`
- `support_slot_role_balance_score`

## Runtime Samples

| District | Runs | NO_COURSE | places_empty | Example role sequence | Repetition observed | Indoor count |
|---|---:|---:|---:|---|---|---:|
| 성수 | 2 | 0 | 0 | `other -> meal -> walk -> walk`, `cafe -> meal -> walk -> cafe` | walk repetition 1 sample | 0 |
| 북촌 | 2 | 0 | 0 | `gallery -> meal -> landmark_support -> cafe`, `gallery -> meal -> walk -> cafe` | none | 1 |
| 한남 | 2 | 0 | 0 | `walk -> meal -> meal -> cafe`, `meal -> meal -> walk -> cafe` | meal repetition 2 samples | 0 |
| 강남 | 2 | 0 | 0 | `gallery -> meal -> walk -> cafe`, `walk -> meal -> walk -> cafe` | none | 0-1 |

## Observations

- Trace fields are now visible in production runtime responses.
- The trace is useful for identifying role repetition without changing route output.
- 한남 showed repeated meal support-slot sequences in both small samples.
- 성수 showed one walk repetition sample, but no places-empty or NO_COURSE.
- 북촌 and 강남 showed usable role diversity in the smoke sample.
- Indoor-heavy was not observed in this small smoke; 북촌 had one indoor-classified support slot per sample.

## Safety Check

- Soft demote applied: no.
- Role replacement applied: no.
- Score changes: no.
- Candidate filtering changes: no.
- Response schema breakage: not observed.
- Frontend rendering risk: low; fields are nested in `recommendation_trace` and do not alter the existing result card payload.

## Next Step

Use the trace for a read-only accumulation window before applying any role diversity scoring. The first actionable target is 한남 meal repetition. Any future change should remain bounded to support-slot soft demote only and must keep representative family preservation intact.
