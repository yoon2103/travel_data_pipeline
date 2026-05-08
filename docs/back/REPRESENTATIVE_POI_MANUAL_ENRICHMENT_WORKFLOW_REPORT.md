# Representative POI Manual Enrichment Workflow Report

생성일: 2026-05-08

## 작업 범위

- 대표 POI 전용 manual enrichment CLI를 추가했다.
- 대상은 `representative_poi_candidates` staging이며, `places`, `tourism_belt.py`, 추천 엔진은 수정하지 않았다.
- 실제 promote는 수행하지 않았다.
- manual enrichment는 `source_type='MANUAL'`, `review_status='PENDING_REVIEW'`, `promote_status='PENDING'`으로만 등록된다.

## 추가 파일

- `batch/place_enrichment/add_representative_manual_enrichment.py`
- `docs/REPRESENTATIVE_POI_MANUAL_ENRICHMENT_WORKFLOW_REPORT.md`

## CLI 사용법

### Image 후보 등록

```bash
python -m batch.place_enrichment.add_representative_manual_enrichment \
  --expected-poi-name 경포대 \
  --image-url "https://example.com/manual-enrichment/gyeongpodae-representative.jpg" \
  --thumbnail-url "https://example.com/manual-enrichment/gyeongpodae-representative-thumb.jpg" \
  --source-credit "manual curator" \
  --curator-note "representative landmark exterior candidate" \
  --quality-note "landmark exterior review required"
```

### Overview 후보 등록

```bash
python -m batch.place_enrichment.add_representative_manual_enrichment \
  --expected-poi-name 경포대 \
  --overview "경포대는 강릉 경포호 인근의 대표 누정으로, 호수와 바다를 함께 둘러보기 좋은 강릉의 상징적인 역사 명소입니다." \
  --source-credit "manual curator" \
  --curator-note "representative overview draft"
```

### Dry-run

```bash
python -m batch.place_enrichment.add_representative_manual_enrichment \
  --expected-poi-name 경포대 \
  --image-url "https://example.com/manual-test/gyeongpodae-dry-run.jpg" \
  --source-credit "manual test" \
  --curator-note "dry-run image validation" \
  --dry-run
```

## Insert 대상

테이블:

- `representative_poi_candidates`

공통 저장 규칙:

- `source_type='MANUAL'`
- `representative_status='CANDIDATE'`
- `review_status='PENDING_REVIEW'`
- `promote_status='PENDING'`
- `confidence_score=100.00`
- `places` write 없음
- seed write 없음
- promote 없음

`enrichment_type`은 별도 컬럼이 없으므로 다음 위치에 분리 저장한다.

- `category`: `REPRESENTATIVE_IMAGE` 또는 `REPRESENTATIVE_OVERVIEW`
- `validation_payload.enrichment_type`
- `review_payload.enrichment_type`
- `source_payload.enrichment_payload`

## Representative Enrichment Payload 예시

### Representative Image

```json
{
  "source_payload": {
    "workflow": "representative_manual_enrichment",
    "enrichment_type": "REPRESENTATIVE_IMAGE",
    "expected_poi_name": "경포대",
    "approved_representative_candidate_id": 6,
    "source_type": "MANUAL",
    "source_credit": "manual curator",
    "curator_note": "representative landmark exterior candidate",
    "enrichment_payload": {
      "representative_image": {
        "image_url": "https://example.com/manual-enrichment/gyeongpodae-representative.jpg",
        "thumbnail_url": "https://example.com/manual-enrichment/gyeongpodae-representative-thumb.jpg",
        "source_credit": "manual curator",
        "intended_role": "primary",
        "quality_note": "landmark exterior review required"
      }
    }
  },
  "validation_payload": {
    "enrichment_type": "REPRESENTATIVE_IMAGE",
    "risk_flags": [],
    "validation_result": "MANUAL_ENRICHMENT_PENDING_REVIEW",
    "approved_representative_candidate_exists": true,
    "places_write": false,
    "seed_write": false,
    "promote": false
  },
  "review_payload": {
    "review_status": "PENDING_REVIEW",
    "review_required": true,
    "review_reason": "REPRESENTATIVE_IMAGE requires curator review before any promote.",
    "enrichment_type": "REPRESENTATIVE_IMAGE"
  }
}
```

### Representative Overview

```json
{
  "source_payload": {
    "workflow": "representative_manual_enrichment",
    "enrichment_type": "REPRESENTATIVE_OVERVIEW",
    "expected_poi_name": "경포대",
    "approved_representative_candidate_id": 6,
    "source_type": "MANUAL",
    "source_credit": "manual curator",
    "curator_note": "representative overview draft",
    "enrichment_payload": {
      "representative_overview": {
        "overview_text": "경포대는 강릉 경포호 인근의 대표 누정으로, 호수와 바다를 함께 둘러보기 좋은 강릉의 상징적인 역사 명소입니다.",
        "source_credit": "manual curator",
        "curator_note": "representative overview draft",
        "summary_length": 65,
        "language": "ko"
      }
    }
  },
  "validation_payload": {
    "enrichment_type": "REPRESENTATIVE_OVERVIEW",
    "risk_flags": [
      "IMAGE_MISSING"
    ],
    "validation_result": "MANUAL_ENRICHMENT_PENDING_REVIEW",
    "approved_representative_candidate_exists": true,
    "places_write": false,
    "seed_write": false,
    "promote": false
  },
  "review_payload": {
    "review_status": "PENDING_REVIEW",
    "review_required": true,
    "review_reason": "REPRESENTATIVE_OVERVIEW requires curator review before any promote.",
    "enrichment_type": "REPRESENTATIVE_OVERVIEW"
  }
}
```

## Validation 규칙

- `expected_poi_name`은 `representative_poi_candidates`에 존재해야 한다.
- 해당 `expected_poi_name`에 `APPROVED` 대표 후보가 있어야 한다.
- `image_url`은 절대 `http(s)` URL이어야 한다.
- `thumbnail_url`이 있으면 절대 `http(s)` URL이어야 한다.
- `overview`가 전달되면 공백만 있는 값은 reject한다.
- 같은 `expected_poi_name` + 같은 `image_url`은 duplicate로 skip한다.
- `intended_role`은 `primary`, `gallery`만 허용한다.

## 테스트 결과

### py_compile

```text
python -m py_compile .\batch\place_enrichment\add_representative_manual_enrichment.py
PASS
```

### 경포대 image candidate

```text
status: OK
result: INSERTED
enrichment_type: REPRESENTATIVE_IMAGE
candidate_id: 115
review_status: PENDING_REVIEW
promote_status: PENDING
```

### 경포대 overview candidate

```text
status: OK
result: INSERTED
enrichment_type: REPRESENTATIVE_OVERVIEW
candidate_id: 116
review_status: PENDING_REVIEW
promote_status: PENDING
```

### duplicate image

```text
status: OK
result: SKIPPED
reason: DUPLICATE_IMAGE_URL
duplicate_candidate_id: 115
```

### empty overview

```text
status: ERROR
reason: overview must not be empty
```

### invalid expected_poi_name

```text
status: ERROR
reason: expected_poi_name does not exist in staging
```

### approved representative candidate 없음

```text
status: ERROR
reason: approved representative candidate does not exist
```

### dry-run

```text
status: OK
dry_run: true
candidate_id: null
places_changed: false
seed_changed: false
promote_executed: false
```

## 대표 POI Enrichment 상태

현재 `경포대` manual enrichment staging 상태:

| expected_poi_name | enrichment_type | review_status | promote_status | count |
|---|---|---|---:|
| 경포대 | REPRESENTATIVE_IMAGE | PENDING_REVIEW | PENDING | 1 |
| 경포대 | REPRESENTATIVE_OVERVIEW | PENDING_REVIEW | PENDING | 1 |

`representative_enrichment_audit` 기준:

- `MANUAL` image 후보: `1`
- `MANUAL` overview 후보: `1`
- 아직 `APPROVED` 된 enrichment 후보가 아니므로 대표 후보 자체의 readiness는 계속 `NEEDS_MANUAL_CURATION`
- 다음 단계는 candidate 115, 116을 review workflow로 approve/reject하는 것이다.

## places/seed 변경 없음 확인

- `places` row count: `26371`
- `tourism_belt.py` diff: 없음
- `course_builder.py` diff: 없음
- CLI 결과: `places_changed=false`
- CLI 결과: `seed_changed=false`
- CLI 결과: `promote_executed=false`

## 위험 요소

- 현재 image URL은 staging 검증용 manual URL이며, 실제 운영 반영 전 저작권/출처/이미지 품질 검수가 필요하다.
- `representative_poi_candidates`에 별도 `enrichment_payload` 컬럼이 없기 때문에 payload는 `source_payload.enrichment_payload`에 보존한다.
- manual overview는 운영자 작성 문구이므로 과장 표현, 부정확한 역사 정보, 저작권 복붙 여부를 검수해야 한다.
- enrichment 후보 approve가 곧 places 반영을 의미하지 않는다. 별도 promote 설계가 필요하다.

## 다음 작업 제안

1. `list_representative_candidates.py --source-type MANUAL --expected-name 경포대`로 candidate 115, 116을 검수 목록에 노출한다.
2. `review_representative_candidate.py`로 image/overview 후보를 approve한다.
3. approve된 manual enrichment 후보를 대상으로 대표 POI promote dry-run이 image/overview gap을 해소하는지 분석한다.
4. 실제 places 반영 전 `REPRESENTATIVE_IMAGE`, `REPRESENTATIVE_OVERVIEW` 전용 promote policy를 별도 설계한다.
