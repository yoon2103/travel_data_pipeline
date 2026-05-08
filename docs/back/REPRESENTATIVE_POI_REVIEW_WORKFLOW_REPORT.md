# Representative POI Review Workflow Report

작성일: 2026-05-08

## 작업 목표

`representative_poi_candidates`에 저장된 대표 POI 후보를 운영자가 조회하고, `approve`, `reject`, `skip` 할 수 있는 review workflow CLI를 구현했다.

## 준수한 금지 원칙

- `places` insert 없음
- `places` update 없음
- `tourism_belt.py` 수정 없음
- 추천 엔진 수정 없음
- `course_builder.py` 수정 없음
- promote 없음
- seed 변경 없음

## 추가 파일

| 파일 | 설명 |
|---|---|
| `batch/place_enrichment/list_representative_candidates.py` | representative candidate 목록 조회 CLI |
| `batch/place_enrichment/review_representative_candidate.py` | approve/reject/skip review action CLI |
| `docs/REPRESENTATIVE_POI_REVIEW_WORKFLOW_REPORT.md` | 작업 결과 보고서 |

## CLI 사용법

### 후보 목록 조회

```bash
python -m batch.place_enrichment.list_representative_candidates \
  --review-status PENDING_REVIEW \
  --limit 20
```

지원 옵션:

```bash
--review-status PENDING_REVIEW|IN_REVIEW|APPROVED|REJECTED|SKIPPED|PROMOTED
--promote-status PENDING|NOT_READY|READY|PROMOTED|SKIPPED|ROLLED_BACK
--representative-status CANDIDATE|NEEDS_REVIEW|APPROVED|REJECTED|PROMOTED
--source-type TOURAPI|KAKAO|NAVER|MANUAL
--expected-name 경포대
--limit 20
```

출력 필드:

- `candidate_id`
- `expected_poi_name`
- `source_type`
- `source_name`
- `confidence_score`
- `representative_status`
- `review_status`
- `promote_status`
- `risk_flags`
- `created_at`

### 후보 리뷰

Approve:

```bash
python -m batch.place_enrichment.review_representative_candidate \
  --candidate-id 6 \
  --action approve \
  --reviewer ops_001 \
  --note "exact landmark match"
```

Reject:

```bash
python -m batch.place_enrichment.review_representative_candidate \
  --candidate-id 12 \
  --action reject \
  --reviewer ops_001 \
  --note "duplicate source candidate kept for source comparison only"
```

Skip:

```bash
python -m batch.place_enrichment.review_representative_candidate \
  --candidate-id 21 \
  --action skip \
  --reviewer ops_001 \
  --note "skip during workflow test"
```

Dry-run:

```bash
python -m batch.place_enrichment.review_representative_candidate \
  --candidate-id 26 \
  --action approve \
  --reviewer ops_test \
  --note "dry run exact landmark match" \
  --dry-run
```

## 상태 변경 규칙

| action | review_status 변경 |
|---|---|
| approve | `APPROVED` |
| reject | `REJECTED` |
| skip | `SKIPPED` |

중요:

- `promote_status`는 변경하지 않는다.
- `places`는 변경하지 않는다.
- seed는 변경하지 않는다.
- 이미 review된 후보는 다시 변경하지 않는다.

## Review Payload 구조

`review_payload`에는 마지막 review 정보와 history를 같이 저장한다.

예시:

```json
{
  "reviewer_id": "ops_001",
  "reviewed_at": "2026-05-07T23:28:10.879247+00:00",
  "review_action": "approve",
  "review_note": "exact landmark match",
  "previous_status": "PENDING_REVIEW",
  "review_history": [
    {
      "reviewer_id": "ops_001",
      "reviewed_at": "2026-05-07T23:28:10.879247+00:00",
      "review_action": "approve",
      "review_note": "exact landmark match",
      "previous_status": "PENDING_REVIEW"
    }
  ]
}
```

## 테스트 결과

### py_compile

결과: PASS

```bash
python -m py_compile \
  batch/place_enrichment/list_representative_candidates.py \
  batch/place_enrichment/review_representative_candidate.py
```

### list CLI

명령:

```bash
python -m batch.place_enrichment.list_representative_candidates \
  --review-status PENDING_REVIEW \
  --limit 5
```

결과: PASS

상위 후보 예시:

| candidate_id | expected_poi_name | source_type | source_name | confidence_score | review_status | promote_status |
|---:|---|---|---|---:|---|---|
| 53 | 전주한옥마을 | NAVER | 전주 한옥마을 | 93.00 | PENDING_REVIEW | PENDING |
| 48 | 전주한옥마을 | KAKAO | 전주한옥마을 | 93.00 | PENDING_REVIEW | PENDING |
| 33 | 성산일출봉 | KAKAO | 성산일출봉 | 93.00 | PENDING_REVIEW | PENDING |
| 26 | 불국사 | NAVER | 불국사 | 93.00 | PENDING_REVIEW | PENDING |
| 21 | 불국사 | KAKAO | 불국사 | 93.00 | PENDING_REVIEW | PENDING |

### dry-run

명령:

```bash
python -m batch.place_enrichment.review_representative_candidate \
  --candidate-id 26 \
  --action approve \
  --reviewer ops_test \
  --note "dry run exact landmark match" \
  --dry-run
```

결과: PASS

- 실제 DB 상태 변경 없음
- 예상 `review_status=APPROVED`
- `promote_status=PENDING` 유지

### approve

명령:

```bash
python -m batch.place_enrichment.review_representative_candidate \
  --candidate-id 6 \
  --action approve \
  --reviewer ops_001 \
  --note "exact landmark match"
```

결과: PASS

| candidate_id | before | after | promote_status |
|---:|---|---|---|
| 6 | PENDING_REVIEW | APPROVED | PENDING |

### reject

명령:

```bash
python -m batch.place_enrichment.review_representative_candidate \
  --candidate-id 12 \
  --action reject \
  --reviewer ops_001 \
  --note "duplicate source candidate kept for source comparison only"
```

결과: PASS

| candidate_id | before | after | promote_status |
|---:|---|---|---|
| 12 | PENDING_REVIEW | REJECTED | PENDING |

### skip

명령:

```bash
python -m batch.place_enrichment.review_representative_candidate \
  --candidate-id 21 \
  --action skip \
  --reviewer ops_001 \
  --note "skip during workflow test"
```

결과: PASS

| candidate_id | before | after | promote_status |
|---:|---|---|---|
| 21 | PENDING_REVIEW | SKIPPED | PENDING |

### invalid candidate_id

명령:

```bash
python -m batch.place_enrichment.review_representative_candidate \
  --candidate-id 999999 \
  --action approve \
  --reviewer ops_001 \
  --note "invalid candidate test"
```

결과: PASS

응답:

```json
{
  "status": "ERROR",
  "reason": "candidate_id does not exist: 999999"
}
```

프로세스 exit code는 `2`로 반환된다.

### already reviewed

명령:

```bash
python -m batch.place_enrichment.review_representative_candidate \
  --candidate-id 6 \
  --action approve \
  --reviewer ops_001 \
  --note "already reviewed test"
```

결과: PASS

응답:

```json
{
  "status": "ALREADY_REVIEWED",
  "candidate_id": 6,
  "previous_status": "APPROVED",
  "review_status": "APPROVED",
  "promote_status": "PENDING"
}
```

이미 review된 후보는 상태를 다시 바꾸지 않는다.

## Review 상태 변경 결과

현재 representative candidate 상태:

| review_status | promote_status | count |
|---|---|---:|
| APPROVED | PENDING | 1 |
| PENDING_REVIEW | PENDING | 54 |
| REJECTED | PENDING | 1 |
| SKIPPED | PENDING | 1 |

검증 대상 후보:

| candidate_id | expected_poi_name | source_type | source_name | review_status | promote_status |
|---:|---|---|---|---|---|
| 6 | 경포대 | KAKAO | 경포대 | APPROVED | PENDING |
| 12 | 경포대 | NAVER | 경포대 | REJECTED | PENDING |
| 21 | 불국사 | KAKAO | 불국사 | SKIPPED | PENDING |
| 26 | 불국사 | NAVER | 불국사 | PENDING_REVIEW | PENDING |

## Places/Seed 변경 없음 확인

`places` row count:

| 시점 | count |
|---|---:|
| review 전 | 26371 |
| review 후 | 26371 |

Git diff 확인:

- `tourism_belt.py` 변경 없음
- `course_builder.py` 변경 없음

변경된 것은 representative candidate review 상태와 `review_payload`뿐이다.

## 위험 요소

1. `APPROVED`는 promote가 아니다.
   - `promote_status`는 계속 `PENDING`이다.
   - 운영 반영은 별도 promote 설계 후에만 가능하다.

2. source별 중복 후보가 많다.
   - 같은 대표 POI라도 Kakao/Naver/TourAPI 후보를 각각 검수해야 한다.

3. 수동 검수 실수 방지가 필요하다.
   - 추후 `approve` 시 `confidence_score`, `risk_flags`, `source_name`을 한 번 더 보여주는 confirm-free safety summary가 있으면 좋다.

## 다음 작업 제안

1. `list_representative_candidates`에 `--risk-flag` 필터 추가
2. `review_representative_candidate`에 `--json`/`--quiet` 옵션 추가
3. approved 후보를 대상으로만 promote dry-run 리포트 생성
4. promote는 여전히 `places`/seed 직접 반영 전 별도 검수 단계로 분리
