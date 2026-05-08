# Representative Image QA Tooling Report

생성일: 2026-05-08

## 작업 범위

- 대표 이미지 후보를 운영자가 검수하기 쉽게 조회하는 QA tooling을 구현했다.
- 실제 이미지 다운로드, 저장, CDN 업로드, promote, `places` update는 수행하지 않았다.
- `tourism_belt.py`, 추천 엔진, seed는 수정하지 않았다.

## 추가 파일

- `batch/place_enrichment/image_qa_policy.py`
- `batch/place_enrichment/list_representative_image_candidates.py`
- `docs/REPRESENTATIVE_IMAGE_QA_TOOLING_REPORT.md`

## CLI 사용법

### 대표 이미지 후보 목록

```bash
python -m batch.place_enrichment.list_representative_image_candidates
```

### 경포대 후보 조회

```bash
python -m batch.place_enrichment.list_representative_image_candidates \
  --expected-name 경포대
```

### QA checklist 포함 JSON 출력

```bash
python -m batch.place_enrichment.list_representative_image_candidates \
  --expected-name 경포대 \
  --checklist \
  --json
```

### 품질 등급 필터

```bash
python -m batch.place_enrichment.list_representative_image_candidates \
  --quality-level BLOCKED \
  --json
```

지원 옵션:

- `--expected-name`
- `--review-status`
- `--quality-level`
- `--checklist`
- `--json`
- `--limit`

## QA Summary Payload

CLI는 각 image candidate에 대해 다음 payload를 출력한다.

```json
{
  "landmark_identifiable": null,
  "wrong_place_risk": false,
  "nearby_business_risk": false,
  "watermark_detected": false,
  "advertisement_detected": false,
  "resolution": {
    "width": null,
    "height": null,
    "mime_type": null,
    "checksum": null,
    "metadata_extraction": "NOT_PERFORMED_NO_DOWNLOAD"
  },
  "source_validity": "REVIEW_REQUIRED",
  "license_validity": "REVIEW_REQUIRED",
  "source_credit": "manual curator",
  "license_note": null,
  "image_source_url": null,
  "placeholder_domain": true,
  "duplicate_url_count": 1,
  "url_fingerprint": "sha256...",
  "risk_flags": [
    "LICENSE_NOTE_MISSING",
    "PLACEHOLDER_IMAGE_URL"
  ],
  "quality_level": "BLOCKED"
}
```

## Quality Grading 구조

등급:

| quality_level | 의미 |
|---|---|
| `BLOCKED` | 운영 사용 금지 |
| `LOW` | 품질 낮음 |
| `REVIEW_REQUIRED` | source/license/metadata 등 검수 필요 |
| `GOOD` | 사용 가능 후보 |
| `REPRESENTATIVE_GRADE` | 대표 이미지 후보로 적합 |

현재 grading 기준:

- placeholder domain, invalid URL, wrong place, nearby business, watermark, advertisement, source/license invalid는 `BLOCKED`
- source/license 정보가 부족하면 `REVIEW_REQUIRED`
- width/height metadata가 없으면 `REVIEW_REQUIRED`
- 최소 해상도 미만이면 `LOW`
- landmark 식별 가능하고 품질 조건을 충족하면 `REPRESENTATIVE_GRADE`

## QA Checklist 출력

CLI의 `--checklist` 옵션은 아래 항목을 출력한다.

- `landmark_identifiable`
- `wrong_place_risk`
- `nearby_business_risk`
- `watermark_detected`
- `advertisement_detected`
- `resolution`
- `source_validity`
- `license_validity`
- `placeholder_domain`
- `duplicate_checksum`

## Placeholder Domain Detect

현재 차단 도메인:

- `example.com`
- `example.org`
- `example.net`
- `localhost`
- `127.0.0.1`
- `dummyimage.com`
- `placehold.co`
- `placeholder.com`
- `via.placeholder.com`

경포대 candidate 115는 `example.com` URL이므로 `PLACEHOLDER_IMAGE_URL`로 분류된다.

## Duplicate Checksum Detect 설계

현재 구현:

- 실제 이미지 다운로드 금지 원칙에 따라 checksum 계산은 수행하지 않는다.
- 대신 `image_url` 기준 duplicate count와 `url_fingerprint`를 출력한다.
- payload에 `checksum`이 들어오면 향후 checksum 기반 중복 탐지가 가능하다.

향후 강화:

- 운영 업로드 시점에 checksum 생성
- 동일 checksum 후보 자동 warning
- 동일 URL 또는 동일 checksum 후보는 review 단계에서 중복 표시

## Image Metadata Extraction 설계

현재 구현:

- 실제 다운로드/store 금지
- metadata extraction은 `NOT_PERFORMED_NO_DOWNLOAD`로 표시
- payload에 width/height/mime_type/checksum이 있으면 그대로 표시

향후 강화:

- 운영 업로드 파일에서 width/height/mime_type/checksum 추출
- 외부 URL은 HEAD만 허용할지 별도 정책 필요
- production promote 전에는 metadata 필수화 권장

## Representative Image Review Helper

approve 전 운영자가 확인할 수 있는 요약:

- `quality_level`
- `risk_flags`
- `source_validity`
- `license_validity`
- `resolution`
- `placeholder_domain`
- `duplicate_url_count`
- `url_fingerprint`

현재 CLI는 review action을 직접 수행하지 않는다.
검수 결과에 따라 기존 `review_representative_candidate.py`로 approve/reject를 수행한다.

## 경포대 QA 예시

대상:

- candidate_id: `115`
- expected_poi_name: `경포대`
- image_url: `https://example.com/manual-enrichment/gyeongpodae-representative.jpg`
- review_status: `REJECTED`
- promote_status: `PENDING`

QA 결과:

```text
quality_level: BLOCKED
risk_flags:
- LICENSE_NOTE_MISSING
- PLACEHOLDER_IMAGE_URL
source_validity: REVIEW_REQUIRED
license_validity: REVIEW_REQUIRED
resolution.metadata_extraction: NOT_PERFORMED_NO_DOWNLOAD
```

판단:

- placeholder URL이므로 운영 대표 이미지로 사용할 수 없다.
- license_note가 없다.
- image_source_url이 없다.
- 실제 이미지 metadata는 다운로드하지 않았으므로 알 수 없다.
- 기존 reject 판단이 맞다.

## 테스트 결과

```text
python -m py_compile .\batch\place_enrichment\image_qa_policy.py .\batch\place_enrichment\list_representative_image_candidates.py
PASS
```

```text
python -m batch.place_enrichment.list_representative_image_candidates --expected-name 경포대 --checklist --json
PASS
```

```text
python -m batch.place_enrichment.list_representative_image_candidates --quality-level BLOCKED --json
PASS
```

## places/seed 변경 없음 확인

- `places` row count: `26371`
- `tourism_belt.py` diff: 없음
- `course_builder.py` diff: 없음
- `api_server.py` diff: 없음
- promote 미실행
- places write 없음
- seed write 없음

## 위험 요소

- 현재 tooling은 실제 이미지 내용을 보지 않는다. landmark 식별 여부는 payload 또는 운영자 검수에 의존한다.
- 외부 URL metadata를 자동 추출하지 않으므로 width/height/checksum은 비어 있을 수 있다.
- source/license payload가 기존 후보에 없으면 `REVIEW_REQUIRED` 또는 `BLOCKED`가 많아질 수 있다.
- quality_level은 운영 보조 판단이며, actual promote 조건이 아니다.

## 다음 작업 제안

1. `add_representative_manual_enrichment.py`에 `image_source_url`, `license_note`, width/height/mime_type/checksum 입력 옵션을 추가한다.
2. placeholder domain 후보는 등록 단계에서 reject하도록 강화한다.
3. 실제 경포대 대표 이미지 후보를 source/license 포함해 다시 등록한다.
4. QA tooling으로 `GOOD` 또는 `REPRESENTATIVE_GRADE`인지 확인한 뒤 review approve한다.
5. image gap 해소 후 seed overlay simulation을 재실행한다.
