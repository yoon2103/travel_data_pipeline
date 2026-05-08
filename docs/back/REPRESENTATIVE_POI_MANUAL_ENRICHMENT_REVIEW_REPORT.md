# Representative POI Manual Enrichment Review Report

생성일: 2026-05-08

## 작업 범위

- 경포대 manual enrichment candidate 115, 116을 review workflow로 검수했다.
- `places`, `tourism_belt.py`, `course_builder.py`는 수정하지 않았다.
- actual promote는 수행하지 않았다.

## Review 결과

| candidate_id | enrichment_type | 판단 | review_status | promote_status | 이유 |
|---:|---|---|---|---|---|
| 115 | REPRESENTATIVE_IMAGE | reject | REJECTED | PENDING | `example.com` placeholder URL이라 실제 대표 이미지 품질/라이선스 검증 불가 |
| 116 | REPRESENTATIVE_OVERVIEW | approve | APPROVED | PENDING | 자연스러운 한국어 설명이며 대표 맥락이 명확하고 홍보 문구 없음 |

## Candidate 115 상태

```text
candidate_id: 115
expected_poi_name: 경포대
source_type: MANUAL
category: REPRESENTATIVE_IMAGE
image_url: https://example.com/manual-enrichment/gyeongpodae-representative.jpg
review_status: REJECTED
promote_status: PENDING
```

판단:

- URL 형식 자체는 유효하지만 실제 이미지 품질을 확인할 수 없는 placeholder URL이다.
- 대표 landmark exterior 여부, 저작권, source credit 신뢰성을 검증할 수 없다.
- 따라서 운영 반영 후보로 approve하지 않고 reject 처리했다.

## Candidate 116 상태

```text
candidate_id: 116
expected_poi_name: 경포대
source_type: MANUAL
category: REPRESENTATIVE_OVERVIEW
overview: 경포대는 강릉 경포호 인근의 대표 누정으로, 호수와 바다를 함께 둘러보기 좋은 강릉의 상징적인 역사 명소입니다.
review_status: APPROVED
promote_status: PENDING
```

판단:

- 20자 이상이다.
- 자연스러운 한국어 문장이다.
- `대표 관광지입니다` 같은 무의미한 문장이 아니다.
- 강릉/경포호/역사 명소 맥락이 포함되어 있다.
- 과장된 홍보 표현이 없다.

## Review Payload 예시

### Candidate 115

```json
{
  "reviewer_id": "ops_001",
  "reviewed_at": "2026-05-08T01:07:39.429048+00:00",
  "review_action": "reject",
  "review_note": "reject: placeholder example.com image URL; representative landmark image quality and license cannot be verified",
  "previous_status": "PENDING_REVIEW"
}
```

### Candidate 116

```json
{
  "reviewer_id": "ops_001",
  "reviewed_at": "2026-05-08T01:07:39.445180+00:00",
  "review_action": "approve",
  "review_note": "approve: natural Korean overview, representative context is clear, no promotional wording",
  "previous_status": "PENDING_REVIEW"
}
```

## Representative 상태

| 구분 | candidate_id | 상태 |
|---|---:|---|
| representative place candidate | 6 | APPROVED / PENDING |
| representative image candidate | 115 | REJECTED / PENDING |
| representative overview candidate | 116 | APPROVED / PENDING |

## Promote Readiness 변화

### 기존 상태

- 경포대 representative candidate 6: `APPROVED`
- image: 없음
- overview: 없음
- audit readiness: `NEEDS_MANUAL_CURATION`
- gap: `IMAGE_MISSING`, `OVERVIEW_MISSING`

### Review 후 상태

- overview 후보 116이 `APPROVED` 되어 overview gap은 해소 가능 상태가 되었다.
- image 후보 115는 `REJECTED` 되어 image gap은 유지된다.
- `representative_enrichment_audit` 결과:

```text
readiness: READY_WITH_IMAGE_GAP
manual_curation_required: true
```

### IMAGE / OVERVIEW Gap

| gap | 상태 | 설명 |
|---|---|---|
| IMAGE_MISSING | 미해소 | candidate 115 reject. 새 대표 이미지 후보 필요 |
| OVERVIEW_MISSING | 해소 가능 | candidate 116 approve. promote 전 payload 결합 필요 |

## representative_promote_dry_run 재실행 결과

`representative_promote_dry_run --expected-name 경포대 --json` 실행 결과:

```text
candidate_count: 2
readiness_counts:
- READY_FOR_MANUAL_PROMOTE: 2
```

주의:

- 현재 promote dry-run은 `APPROVED` 된 manual overview candidate 116도 대표 후보처럼 집계한다.
- 이는 manual enrichment 후보와 representative place 후보를 구분하지 못하는 현 dry-run의 한계다.
- 실제 promote 판단에서는 candidate 6을 representative place 후보로 보고, 116은 overview enrichment로 결합해야 한다.
- image 후보가 reject되었으므로 실제 운영 promote readiness는 `READY_FOR_MANUAL_PROMOTE`가 아니라 `READY_WITH_IMAGE_GAP`으로 보는 것이 안전하다.

## places/seed 변경 없음 확인

- `places` row count: `26371`
- `tourism_belt.py` diff: 없음
- `course_builder.py` diff: 없음
- actual promote: 미실행
- places insert/update: 없음
- seed 변경: 없음

## 위험 요소

- candidate 115는 placeholder URL이라 운영에 쓸 수 없다.
- candidate 116은 overview로는 적합하지만, 별도 image 후보 없이 대표 POI promote를 진행하면 이미지 품질 문제가 남는다.
- 현재 promote dry-run은 enrichment 후보와 대표 place 후보를 분리하지 못한다.
- 실제 promote 전에는 `REPRESENTATIVE_IMAGE`, `REPRESENTATIVE_OVERVIEW`, 대표 `PLACE` 후보를 별도 역할로 결합하는 dry-run 강화가 필요하다.

## 다음 작업 제안

1. 경포대의 실제 대표 이미지 후보를 manual curator workflow로 다시 등록한다.
2. 새 image 후보를 review approve한 뒤 enrichment audit을 재실행한다.
3. `representative_promote_dry_run.py`를 강화해 manual enrichment 후보를 대표 place 후보로 오인하지 않도록 분리한다.
4. `READY_WITH_IMAGE_GAP` 상태에서는 actual promote를 계속 금지한다.
