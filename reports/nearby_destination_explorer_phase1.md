# Nearby Destination Explorer Phase1

## Goal

Add a new screen for "목적지 주변 둘러보기" without modifying the existing recommendation screens directly.

## Implemented Scope

### New Backend APIs

Added read-only endpoints in `api_server.py`:

```text
GET /api/explore/destinations?query={query}&limit={limit}
GET /api/explore/nearby?lat={lat}&lon={lon}&radius_m={radius_m}&limit={limit}
```

Behavior:

- destination search uses active `places` rows with coordinates
- nearby lookup supports `500m`, `1km`, `3km`
- sorting prioritizes `view_count`, then `review_count`, then `rating`
- no DB write
- no migration
- no recommendation scoring change

Returned card fields:

- image URL
- name
- category
- distance
- rating if present
- review count if present
- operating label

Operating status note:

- restored DB currently has no populated `opening_hours` rows
- endpoint returns `운영 정보 확인 필요` unless explicit `open_now` data exists

### New Frontend Screen

Added:

```text
frontend/src/screens/day-trip/ExploreNearbyScreen.jsx
```

Features:

- destination search
- radius selector: `500m`, `1km`, `3km`
- nearby place cards
- bottom CTA: `이 주변으로 여행 코스 만들기`
- stay prompt: `숙박 예정이신가요?`
- `아니오`: enters existing day-trip condition flow
- `예`: enters accommodation-base 2+ day flow metadata through the existing condition flow

### New Route / Navigation

Updated:

```text
frontend/src/App.jsx
frontend/src/components/common/MobileShell.jsx
```

Added:

- bottom tab: `둘러보기`
- app screen: `explore`
- hash route support: `#/explore`

Existing recommendation screens were not directly edited:

- `HomeScreen.jsx`: unchanged
- `ConditionScreen.jsx`: unchanged
- `CourseResultScreen.jsx`: unchanged

## Local Runtime Prerequisite Fixes Included

The local restored runtime also required the previous backend startup fixes:

```text
region_identity_layer.py
landmark_authority.py
db_client.py
frontend/src/utils/telemetry.js
frontend/src/data/dayTripDummyData.js
```

Reason:

- `course_builder.py` imports real modules that were missing from the clean clone root
- restored DB lacks PostgreSQL `vector` type, so `db_client.py` now treats pgvector adapter registration as optional for non-vector endpoints
- frontend clean clone was missing telemetry and imported constants needed by `HomeScreen.jsx`

No fake POI or fake backend module was created.

## Verification

### Backend Compile

```text
python -m py_compile api_server.py db_client.py
```

Result: PASS

### Backend Smoke

| Check | Result |
|---|---|
| `GET /docs` | `200` |
| `GET /api/regions` | `200` |
| `GET /api/explore/destinations?query=성수&limit=3` | `200` |
| `GET /api/explore/nearby?lat=37.5443&lon=127.0558&radius_m=1000&limit=5` | `200` |

### Frontend Build

Command:

```text
docker compose -f docker-compose.staging.yml --env-file .env.staging.local build --no-cache travel-frontend
```

Result: PASS

### Frontend Smoke

| Check | Result |
|---|---|
| `GET http://127.0.0.1:4175/#/explore` | `200` |
| `travel-frontend-staging` | running |
| `travel-api-staging` | running |

## Known Follow-Up

The 신규 screen correctly enters the existing recommendation condition flow, but a direct local API smoke using a sample Seongsu coordinate returned `NO_COURSE_ALL_RADIUS` in one manual check. That is not caused by the new explorer APIs, but it means actual course generation quality from arbitrary searched destinations needs a separate bounded QA pass.

Recommended next step:

- run targeted course-generation smoke for 5 to 10 selected destination anchors
- if failures repeat, fix as a scoped recommendation fallback task, not inside this screen/API addition

## Safety

- No production DB write
- No migration
- No fake POI
- No existing recommendation engine rewrite
- No `docker compose down`
- `.env.staging.local` not committed
