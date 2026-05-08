# Seed Candidates Staging Workflow Report

생성일: 2026-05-08

## 작업 범위

- `seed_candidates` staging/review dry-run workflow 1차 구현
- dev/local DB에 migration 적용
- 경포대 seed candidate dry-run 및 staging write 검증
- `tourism_belt.py`, 추천 엔진, API, `places`는 수정하지 않음
- actual overlay/promote는 수행하지 않음

## 추가 파일

- `migration_011_seed_candidates.sql`
- `batch/place_enrichment/create_seed_candidate.py`
- `batch/place_enrichment/list_seed_candidates.py`
- `batch/place_enrichment/review_seed_candidate.py`
- `docs/SEED_CANDIDATES_STAGING_WORKFLOW_REPORT.md`

## Migration 적용 DB

```text
host: localhost
port: 5432
dbname: travel_db
user: postgres
```

로컬/dev DB 기준으로 적용했다.

## Migration 요약

생성 테이블:

- `seed_candidates`

주요 컬럼:

- `seed_candidate_id`
- `region_1`
- `region_2`
- `expected_poi_name`
- `existing_seed_name`
- `representative_candidate_id`
- `source_type`
- `candidate_place_name`
- `promote_strategy`
- `seed_status`
- `review_status`
- `risk_flags JSONB`
- `source_payload JSONB`
- `validation_payload JSONB`
- `review_payload JSONB`
- `dry_run_payload JSONB`
- `rollback_payload JSONB`
- `created_at`
- `updated_at`

주요 제약:

- `promote_strategy`
  - `KEEP_EXISTING_ONLY`
  - `COEXIST_WITH_EXISTING`
  - `REPLACE_EXISTING`
  - `REPRESENTATIVE_ALIAS_ONLY`

- `seed_status`
  - `CANDIDATE`
  - `NEEDS_REVIEW`
  - `APPROVED`
  - `REJECTED`
  - `COEXIST`
  - `READY_FOR_PROMOTE`
  - `PROMOTED`
  - `ROLLED_BACK`

- `review_status`
  - `PENDING_REVIEW`
  - `IN_REVIEW`
  - `APPROVED`
  - `REJECTED`
  - `SKIPPED`

중복 방지:

- active 상태의 동일 region / expected POI / candidate place / strategy 조합은 unique 처리

## CLI 사용법

### Seed candidate 생성 dry-run

```bash
python -m batch.place_enrichment.create_seed_candidate \
  --expected-name 경포대 \
  --strategy COEXIST_WITH_EXISTING \
  --region 강원 \
  --dry-run \
  --json
```

### Seed candidate staging write

```bash
python -m batch.place_enrichment.create_seed_candidate \
  --expected-name 경포대 \
  --strategy COEXIST_WITH_EXISTING \
  --region 강원 \
  --write \
  --json
```

### Seed candidate 목록 조회

```bash
python -m batch.place_enrichment.list_seed_candidates \
  --expected-name 경포대 \
  --limit 10
```

### Seed candidate review dry-run

```bash
python -m batch.place_enrichment.review_seed_candidate \
  --seed-candidate-id 1 \
  --action approve \
  --reviewer ops_001 \
  --note "dry-run review only: image gap remains, do not promote" \
  --dry-run
```

지원 action:

- `approve`
- `reject`
- `skip`

## 경포대 Seed Candidate Dry-run 결과

입력:

```text
expected_poi_name: 경포대
existing_seed_name: 경포호수광장
strategy: COEXIST_WITH_EXISTING
region: 강원
```

출력 요약:

```json
{
  "expected_poi_name": "경포대",
  "existing_seed": {
    "name": "경포호수광장",
    "place_id": 11269
  },
  "overlay_candidate": {
    "representative_candidate_id": 6,
    "candidate_place_name": "경포대",
    "source_type": "KAKAO",
    "confidence_score": "93.00"
  },
  "strategy": "COEXIST_WITH_EXISTING",
  "risk_flags": [
    "IMAGE_MISSING"
  ],
  "qa_required": true,
  "duplicate_nearby_risk": "MEDIUM",
  "existing_seed_distance_km": 1.172,
  "readiness": "NOT_READY",
  "readiness_reasons": [
    "approved representative image is missing"
  ],
  "enrichment_status": {
    "has_approved_image": false,
    "approved_image_candidate_id": null,
    "has_approved_overview": true,
    "approved_overview_candidate_id": 116
  }
}
```

판단:

- `경포대` 대표 후보 자체는 `APPROVED` 상태다.
- 기존 seed `경포호수광장`과 약 `1.172km` 거리라 duplicate nearby risk는 `MEDIUM`이다.
- overview는 candidate `116`으로 승인되어 있다.
- 대표 image는 아직 승인 후보가 없으므로 `IMAGE_MISSING`이 남아 있다.
- 따라서 seed candidate는 생성 가능하지만 readiness는 `NOT_READY`다.
- actual overlay/promote는 계속 금지다.

## Write 결과

```text
status: INSERTED
seed_candidate_id: 1
expected_poi_name: 경포대
promote_strategy: COEXIST_WITH_EXISTING
seed_status: NEEDS_REVIEW
review_status: PENDING_REVIEW
risk_flags: [IMAGE_MISSING]
```

## Duplicate 방지 확인

동일 명령을 다시 실행한 결과:

```text
status: SKIPPED
reason: DUPLICATE_SEED_CANDIDATE
duplicate.seed_candidate_id: 1
```

## Invalid 케이스 테스트

### invalid strategy

```text
BAD_STRATEGY 입력 시 argparse invalid choice로 실패
PASS
```

### invalid expected name

```text
expected-name=없는명소
status: ERROR
reason: approved representative candidate does not exist
PASS
```

### invalid seed_candidate_id

```text
seed_candidate_id=999999
status: ERROR
reason: seed_candidate_id does not exist
PASS
```

## Seed 상태 구조

현재 구현 상태:

| status | 의미 |
|---|---|
| `CANDIDATE` | 일반 후보 |
| `NEEDS_REVIEW` | gap 또는 warning이 있어 검수 필요 |
| `APPROVED` | review 승인 |
| `REJECTED` | review 거절 |
| `COEXIST` | 공존 전략 확정용 상태 |
| `READY_FOR_PROMOTE` | promote 가능 전 단계 |
| `PROMOTED` | 실제 반영 완료 |
| `ROLLED_BACK` | rollback 완료 |

경포대는 image gap이 있어 `NEEDS_REVIEW`로 생성했다.

## Review Workflow 초안

추가 CLI:

- `list_seed_candidates.py`
- `review_seed_candidate.py`

검증:

```text
approve dry-run: PASS
reject dry-run: PASS
skip dry-run: PASS
```

실제 review update는 수행하지 않았다.

현재 DB 상태:

```text
seed_candidate_id: 1
seed_status: NEEDS_REVIEW
review_status: PENDING_REVIEW
promote_strategy: COEXIST_WITH_EXISTING
risk_flags: [IMAGE_MISSING]
```

## places/seed 변경 없음 확인

- `places` row count: `26371`
- `tourism_belt.py` diff: 없음
- `course_builder.py` diff: 없음
- `api_server.py` diff: 없음
- actual overlay 적용 없음
- actual promote 없음
- places insert/update 없음

## 테스트 결과

```text
python -m py_compile .\batch\place_enrichment\create_seed_candidate.py .\batch\place_enrichment\list_seed_candidates.py .\batch\place_enrichment\review_seed_candidate.py
PASS

migration_011_seed_candidates.sql
applied to local/dev DB
PASS

create_seed_candidate --dry-run
PASS

create_seed_candidate --write
PASS

duplicate write
PASS, SKIPPED

list_seed_candidates
PASS

review_seed_candidate approve/reject/skip --dry-run
PASS
```

## 위험 요소

- `seed_candidates`는 staging이지만 DB write가 발생하므로 운영 DB에서는 적용 금지다.
- 경포대는 image gap이 있어 actual overlay/promote 금지 상태다.
- duplicate nearby risk가 `MEDIUM`이라 경포대와 경포호수광장 공존 시 QA가 필요하다.
- 현재 workflow는 seed candidate까지만 만들며, 엔진 overlay 적용은 구현하지 않았다.
- `tourism_belt.py` 직접 수정 우회는 rollback 추적을 깨뜨린다.

## 다음 작업 제안

1. 경포대 대표 이미지 후보를 실제 검증 가능한 URL로 다시 등록하고 approve한다.
2. image gap 해소 후 `create_seed_candidate` dry-run을 다시 실행한다.
3. seed candidate review는 image gap 해소 전까지 approve하지 않는다.
4. seed overlay 영향 분석 CLI를 별도 구현한다.
5. actual overlay/promote는 QA와 rollback snapshot 설계 후 별도 작업으로 분리한다.
