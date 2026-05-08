# Representative Manual Image Registration Hardening Report

생성일: 2026-05-08

## 작업 범위

- `add_representative_manual_enrichment.py`의 대표 이미지 등록 validation을 production-grade에 가깝게 강화했다.
- actual image promote, `places` update, seed 변경, CDN upload, image download/store는 수행하지 않았다.
- 대표 이미지 후보는 staging/review 대상으로만 등록된다.

## 수정 파일

- `batch/place_enrichment/add_representative_manual_enrichment.py`
- `docs/REPRESENTATIVE_MANUAL_IMAGE_REGISTRATION_HARDENING_REPORT.md`

## 강화된 Validation 규칙

대표 이미지 등록 시 필수값:

- `image_url`
- `image_source_url`
- `source_credit`
- `license_note`

추가 지원 옵션:

- `--width`
- `--height`
- `--mime-type`
- `--checksum`
- `--landmark-identifiable`

### URL 검증

`image_url`:

- `http` 또는 `https`만 허용
- placeholder domain 차단

`image_source_url`:

- 필수
- 허용 scheme:
  - `http`
  - `https`
  - `operator-upload`
  - `s3`
  - `gs`

### Placeholder Domain 차단

등록 단계에서 차단:

- `example.com`
- `example.org`
- `example.net`
- `localhost`
- `127.0.0.1`
- `dummyimage.com`
- `placehold.co`
- `placeholder.com`
- `via.placeholder.com`

### Metadata 검증

| 항목 | 규칙 |
|---|---|
| `width` | 있으면 양수 |
| `height` | 있으면 양수 |
| `mime_type` | 있으면 `image/*` 형식 |
| `checksum` | 있으면 SHA-256 64 hex, `sha256:` prefix 허용 |

### Duplicate 검증

중복 차단:

- 동일 `expected_poi_name` + 동일 `image_url`
- 동일 `expected_poi_name` + 동일 `checksum`

## Reject 사례

### Placeholder URL

```text
image_url: https://example.com/bad.jpg
status: ERROR
error_code: PLACEHOLDER_IMAGE_URL
```

### Missing license

```text
status: ERROR
error_code: LICENSE_NOTE_REQUIRED
reason: license_note is required for representative image
```

### Missing source_credit

```text
status: ERROR
error_code: SOURCE_CREDIT_REQUIRED
reason: source_credit is required for representative image
```

### Invalid mime

```text
mime_type: text/html
status: ERROR
error_code: INVALID_MIME_TYPE
```

### Duplicate checksum

```text
status: OK
result: SKIPPED
reason: DUPLICATE_IMAGE_CHECKSUM
duplicate.candidate_id: 117
```

## Quality Level 계산

초기 quality level은 등록 단계에서 계산되어 payload에 저장된다.

| 조건 | quality_level |
|---|---|
| placeholder / invalid URL | BLOCKED |
| source/license 누락 | BLOCKED 또는 reject |
| metadata 없음 | REVIEW_REQUIRED |
| metadata 존재, source/license 유효, landmark 식별 미확정 | GOOD |
| metadata 존재, source/license 유효, landmark 식별 true | REPRESENTATIVE_GRADE |

저장 위치:

- `source_payload.quality_summary`
- `source_payload.enrichment_payload.representative_image.quality_level`
- `validation_payload.quality_level`
- `validation_payload.quality_summary`
- `review_payload.quality_level`
- `review_payload.quality_summary`

## 경포대 예시 Payload

### GOOD 후보 등록

```bash
python -m batch.place_enrichment.add_representative_manual_enrichment \
  --expected-poi-name 경포대 \
  --image-url https://images.travel-planner.local/gyeongpodae-good.jpg \
  --image-source-url operator-upload://gyeongpodae/gyeongpodae-good-original.jpg \
  --source-credit "ops direct upload" \
  --license-note "owned_by_operator" \
  --width 1200 \
  --height 800 \
  --mime-type image/jpeg \
  --checksum sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --quality-note "metadata complete, needs visual review"
```

결과:

```text
status: OK
result: INSERTED
candidate_id: 117
quality_level: GOOD
review_status: PENDING_REVIEW
promote_status: PENDING
```

### REPRESENTATIVE_GRADE dry-run

```bash
python -m batch.place_enrichment.add_representative_manual_enrichment \
  --expected-poi-name 경포대 \
  --image-url https://images.travel-planner.local/gyeongpodae-grade.jpg \
  --image-source-url operator-upload://gyeongpodae/gyeongpodae-grade-original.jpg \
  --source-credit "ops direct upload" \
  --license-note "owned_by_operator" \
  --width 1600 \
  --height 1000 \
  --mime-type image/jpeg \
  --checksum sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
  --landmark-identifiable \
  --dry-run
```

결과:

```text
quality_level: REPRESENTATIVE_GRADE
dry_run: true
candidate_id: null
```

## 테스트 결과

### Compile

```text
python -m py_compile .\batch\place_enrichment\add_representative_manual_enrichment.py .\batch\place_enrichment\image_qa_policy.py
PASS
```

### Placeholder URL reject

```text
PASS
error_code: PLACEHOLDER_IMAGE_URL
```

### Missing license reject

```text
PASS
error_code: LICENSE_NOTE_REQUIRED
```

### Missing source_credit reject

```text
PASS
error_code: SOURCE_CREDIT_REQUIRED
```

### Invalid mime reject

```text
PASS
error_code: INVALID_MIME_TYPE
```

### GOOD candidate

```text
PASS
candidate_id: 117
quality_level: GOOD
review_status: PENDING_REVIEW
promote_status: PENDING
```

### Duplicate checksum

```text
PASS
status: SKIPPED
reason: DUPLICATE_IMAGE_CHECKSUM
duplicate.candidate_id: 117
```

### REVIEW_REQUIRED candidate

```text
PASS
metadata 없음
quality_level: REVIEW_REQUIRED
dry_run: true
```

### REPRESENTATIVE_GRADE dry-run

```text
PASS
landmark_identifiable=true
quality_level: REPRESENTATIVE_GRADE
dry_run: true
```

## 현재 경포대 Image Candidate 상태

| candidate_id | image_url | quality_level | review_status | promote_status |
|---:|---|---|---|---|
| 115 | `https://example.com/manual-enrichment/gyeongpodae-representative.jpg` | BLOCKED by QA tooling | REJECTED | PENDING |
| 117 | `https://images.travel-planner.local/gyeongpodae-good.jpg` | GOOD | PENDING_REVIEW | PENDING |

candidate 117은 아직 review 전이다. Actual promote 대상이 아니다.

## places/seed 변경 없음 확인

- `places` row count: `26371`
- `tourism_belt.py` diff: 없음
- `course_builder.py` diff: 없음
- `api_server.py` diff: 없음
- actual image promote 없음
- places write 없음
- seed write 없음
- CDN upload 없음
- image download/store 없음

## 위험 요소

- candidate 117은 테스트용 운영 업로드 형식 URL이며 실제 이미지 다운로드/시각 검증은 수행하지 않았다.
- `GOOD`은 metadata/source/license 기준의 초기 등급이며, landmark 식별 최종 판단은 review가 필요하다.
- checksum은 입력값 기준 검증이며 실제 파일 checksum 계산은 수행하지 않았다.
- `operator-upload://` source URL은 provenance 표현이며 실제 파일 저장소 연동은 아직 없다.

## 다음 작업 제안

1. candidate 117을 QA tooling으로 확인한 뒤 운영자가 실제 이미지 내용을 보고 approve/reject한다.
2. 실제 이미지 파일 기반 workflow에서는 width/height/mime/checksum을 업로드 단계에서 자동 추출한다.
3. `REPRESENTATIVE_GRADE` 후보만 seed overlay simulation의 image gap 해소 대상으로 인정하도록 dry-run을 강화한다.
4. candidate 117 approve 후 seed overlay simulation을 재실행한다.
