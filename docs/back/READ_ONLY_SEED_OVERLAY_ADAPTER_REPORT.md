# READ_ONLY_OVERLAY Adapter Report

## Adapter 구조

추가 파일:

- `batch/place_enrichment/seed_overlay_read_adapter.py`

제공 함수:

- `load_baseline_seeds(region=None)`
  - `tourism_belt.py`의 baseline seed를 읽는다.
  - seed 목록은 immutable baseline으로만 취급한다.

- `load_overlay_candidates(expected_name=None, region=None, limit=100)`
  - `seed_candidates`와 `representative_poi_candidates`를 read-only로 조회한다.
  - representative candidate, image, overview, seed candidate 상태를 함께 진단한다.

- `merge_seed_overlay(baseline_seeds, overlay_candidates, strategy)`
  - baseline seed와 eligible overlay candidate를 read-only view로 merge한다.
  - 실제 seed, places, engine에는 반영하지 않는다.

- CLI entry:

```bash
python -m batch.place_enrichment.seed_overlay_read_adapter \
  --expected-name 경포대 \
  --strategy COEXIST_WITH_EXISTING \
  --json
```

## Merge 전략

지원 전략:

- `ADDITIVE`
  - eligible overlay seed를 baseline 끝에 추가한다.

- `COEXIST_WITH_EXISTING`
  - 기존 baseline seed를 유지하면서 overlay seed를 함께 노출하는 read-only view를 만든다.
  - 초기 rollout에 가장 안전한 전략이다.

- `PRIORITY_OVERRIDE`
  - matching되는 existing seed를 read-only merged view에서 제거하고 overlay seed를 우선 배치한다.
  - 실제 엔진 integration 전까지는 diagnostics에서만 사용한다.

- `ALIAS_ONLY`
  - seed list 자체는 변경하지 않고 alias/diagnostic 후보로만 유지한다.

현재 경포대는 eligible 조건을 만족하지 못해 어떤 전략에서도 실제 merged seed view에 추가되지 않는다.

## Overlay candidate filtering

eligible overlay 조건:

- representative candidate `APPROVED`
- representative image `APPROVED`
- representative overview `APPROVED`
- seed candidate review_status `APPROVED`
- seed_status `APPROVED`, `READY_FOR_PROMOTE`, 또는 `COEXIST`
- hard risk flag 없음

hard risk flags:

- `REGION_UNCLEAR`
- `CATEGORY_RISK`
- `LODGING_RISK`
- `PARKING_LOT_RISK`
- `INTERNAL_FACILITY_RISK`
- `SUB_FACILITY_RISK`

gap flags:

- `IMAGE_MISSING`
- `OVERVIEW_MISSING`

## Overlay diagnostics payload

경포대 diagnostics 주요 결과:

```json
{
  "mode": "read-only-overlay-diagnostics",
  "db_write": false,
  "places_changed": false,
  "seed_changed": false,
  "engine_changed": false,
  "build_course_called": false,
  "strategy": "COEXIST_WITH_EXISTING",
  "baseline_seed_count": 23,
  "eligible_overlay_count": 0,
  "blocked_overlay_count": 1,
  "merged_seed_count": 23,
  "fallback_behavior": "baseline_only_on_overlay_error_or_ineligible_candidate"
}
```

Blocked overlay:

```json
{
  "expected_poi_name": "경포대",
  "existing_seed_name": "경포호수광장",
  "candidate_place_name": "경포대",
  "representative_review_status": "APPROVED",
  "image_candidate_id": null,
  "overview_candidate_id": 116,
  "overview_review_status": "APPROVED",
  "risk_flags": ["IMAGE_MISSING"],
  "eligible": false,
  "blockers": [
    "SEED_REVIEW_NOT_APPROVED",
    "SEED_STATUS_NOT_READY",
    "IMAGE_NOT_APPROVED"
  ],
  "duplicate_nearby": {
    "distance_km": 1.17,
    "risk": "MEDIUM"
  }
}
```

## 경포대 merge 예시

Baseline:

- `경포호수광장`
- source: `tourism_belt.py`
- belt_key: `강릉`
- lat/lon: `37.7978`, `128.9095`
- boost: `0.13`

Overlay candidate:

- `경포대`
- source: `seed_candidates`
- representative_candidate_id: `6`
- strategy: `COEXIST_WITH_EXISTING`
- lat/lon: `37.7950741626953`, `128.896636344738`

현재 merge 결과:

- baseline seed count: `23`
- eligible overlay count: `0`
- merged seed count: `23`
- 경포대는 merged view에 들어가지 않음

차단 이유:

- seed candidate가 아직 review `APPROVED`가 아님
- seed_status가 아직 ready 상태가 아님
- representative image가 아직 actual `APPROVED`가 아님

## Fallback 전략

adapter는 fail-closed 원칙을 따른다.

fallback 조건:

- `REPRESENTATIVE_OVERLAY_READ_ONLY=false`
- overlay candidate 조회 실패
- overlay candidate가 eligible 조건 미달
- hard risk flag 존재
- image/overview/review gap 존재

fallback 결과:

- baseline seed만 반환
- `build_course` 호출 없음
- 추천 엔진 영향 없음
- places/seed write 없음

검증 예시:

```bash
REPRESENTATIVE_OVERLAY_READ_ONLY=false \
python -m batch.place_enrichment.seed_overlay_read_adapter \
  --expected-name 경포대 \
  --strategy COEXIST_WITH_EXISTING \
  --json
```

결과:

- fallback_active: `true`
- fallback_reason: `REPRESENTATIVE_OVERLAY_READ_ONLY=false`
- merged_seed_count: `23`

## Feature flag 구조

초안 env:

```text
REPRESENTATIVE_OVERLAY_READ_ONLY=true
REPRESENTATIVE_OVERLAY_ENABLED=false
REPRESENTATIVE_OVERLAY_QA_ONLY=true
REPRESENTATIVE_OVERLAY_STRATEGY=COEXIST_WITH_EXISTING
```

현재 adapter 동작:

- `REPRESENTATIVE_OVERLAY_READ_ONLY=true`: diagnostics adapter 활성
- `REPRESENTATIVE_OVERLAY_ENABLED=false`: actual engine integration 비활성
- `REPRESENTATIVE_OVERLAY_QA_ONLY=true`: QA/diagnostics 목적 명시
- `REPRESENTATIVE_OVERLAY_STRATEGY`: CLI 기본 strategy로 사용 가능

## actual engine integration 금지 보호

현재 구현 보호 장치:

- `build_course` 호출 없음
- `course_builder.py` import 없음
- API 서버 import 없음
- `tourism_belt.py` 수정 없음
- DB write 없음
- `places` write 없음
- seed write 없음
- 출력 payload에 `engine_changed=false`, `build_course_called=false` 명시

## 검증 결과

실행:

```bash
python -m py_compile .\batch\place_enrichment\seed_overlay_read_adapter.py

python -m batch.place_enrichment.seed_overlay_read_adapter \
  --expected-name 경포대 \
  --strategy COEXIST_WITH_EXISTING \
  --json

python -m batch.place_enrichment.seed_overlay_read_adapter \
  --expected-name 경포대 \
  --strategy COEXIST_WITH_EXISTING
```

결과:

- py_compile: PASS
- 경포대 diagnostics: PASS
- eligible overlay count: `0`
- blocked overlay count: `1`
- merged seed count: `23`
- duplicate nearby risk: `MEDIUM`
- blockers: `SEED_REVIEW_NOT_APPROVED`, `SEED_STATUS_NOT_READY`, `IMAGE_NOT_APPROVED`

## places/seed 변경 없음 확인

- places row count: `26371`
- `tourism_belt.py` 변경 없음
- `course_builder.py` 변경 없음
- `api_server.py` 변경 없음
- actual overlay 적용 없음
- actual promote 없음
- places write 없음
- seed write 없음

## 위험 요소

- current eligible overlay가 없으므로 실제 merged seed 변화는 아직 없다.
- 경포대는 duplicate nearby risk가 `MEDIUM`이라 image/seed 승인 후에도 QA가 필요하다.
- `PRIORITY_OVERRIDE`는 route behavior를 크게 바꿀 수 있어 초기 rollout에는 부적합하다.
- region baseline filtering은 belt_key와 행정 region이 다를 수 있어 기본값은 baseline 전체 로드로 두었다.
- read adapter를 엔진에 직접 연결하면 rollback surface가 커지므로 별도 integration 단계가 필요하다.

## 다음 작업 제안

1. candidate `117` actual visual approve 여부 결정
2. seed candidate `1` review approve 여부 결정
3. approve 후 read adapter 재실행으로 경포대가 eligible overlay로 들어오는지 확인
4. 그 다음에도 actual engine integration 전에 QA_ONLY 비교 리포트 작성
