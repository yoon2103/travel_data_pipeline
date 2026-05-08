# Representative Image Visual Review Workflow Report

## 추가 파일

- `batch/place_enrichment/review_representative_image_candidate.py`

## CLI 사용법

Approve dry-run:

```bash
python -m batch.place_enrichment.review_representative_image_candidate \
  --candidate-id 117 \
  --action approve \
  --reviewer ops_001 \
  --note "landmark is identifiable and source/license metadata is present" \
  --quality-level GOOD \
  --landmark-identifiable \
  --dry-run
```

Reject dry-run:

```bash
python -m batch.place_enrichment.review_representative_image_candidate \
  --candidate-id 117 \
  --action reject \
  --reviewer ops_001 \
  --note "wrong place risk detected during visual QA" \
  --quality-level BLOCKED \
  --wrong-place-risk \
  --dry-run
```

Checklist 출력:

```bash
python -m batch.place_enrichment.review_representative_image_candidate \
  --candidate-id 117 \
  --action approve \
  --reviewer ops_001 \
  --note "visual QA dry-run" \
  --quality-level GOOD \
  --landmark-identifiable \
  --checklist \
  --dry-run
```

## Visual QA checklist

- landmark 식별 가능 여부
- wrong place 여부
- nearby business contamination 여부
- watermark 존재 여부
- advertisement 존재 여부
- image clarity
- representative suitability
- source/license metadata 유효성
- placeholder domain 여부
- duplicate URL 여부

## candidate 117 review 예시

Dry-run approve 결과:

- candidate_id: `117`
- expected_poi_name: `경포대`
- previous_status: `PENDING_REVIEW`
- dry-run review_status: `APPROVED`
- promote_status: `PENDING`
- image_url: `https://images.travel-planner.local/gyeongpodae-good.jpg`
- source_credit: `ops direct upload`
- image_source_url: `operator-upload://gyeongpodae/gyeongpodae-good-original.jpg`
- quality_level: `GOOD`
- duplicate_url_count: `1`
- source_validity: `VALID`
- license_validity: `VALID`

Approve validation:

- `quality_level=GOOD`
- `landmark_identifiable=true`
- review note 존재
- placeholder 아님
- source/license metadata 유효
- contamination flags 없음

Reject dry-run 결과:

- `--wrong-place-risk` 입력 시 dry-run review_status는 `REJECTED`
- readiness impact는 `READY_WITH_IMAGE_GAP`
- actual promote 없음
- places/seed 변경 없음

Approve 실패 조건 확인:

- `--landmark-identifiable` 없이 approve 시 `LANDMARK_IDENTIFIABLE_REQUIRED`로 차단됨

## review_payload 예시

```json
{
  "reviewer_id": "ops_001",
  "review_action": "approve",
  "review_note": "dry-run visual QA: landmark is identifiable and source/license metadata is present",
  "previous_status": "PENDING_REVIEW",
  "visual_review_passed": true,
  "reviewer_quality_grade": "GOOD",
  "landmark_identifiable": true,
  "contamination_flags": [],
  "final_quality_level": "GOOD",
  "qa_summary": {
    "source_validity": "VALID",
    "license_validity": "VALID",
    "placeholder_domain": false,
    "duplicate_url_count": 1,
    "quality_level": "GOOD"
  }
}
```

## 대표 readiness 영향

Dry-run approve 기준:

- IMAGE_MISSING 해소 가능
- next_readiness: `READY_FOR_SEED_OVERLAY_QA_RECHECK`
- 실제 DB 상태는 변경하지 않았으므로 candidate 117은 여전히 `PENDING_REVIEW`
- 실제 readiness 전환은 운영자가 visual QA 후 dry-run 없이 approve해야 가능

Dry-run reject 기준:

- IMAGE_MISSING 유지
- next_readiness: `READY_WITH_IMAGE_GAP`

## 검증 결과

실행한 검증:

```bash
python -m py_compile .\batch\place_enrichment\review_representative_image_candidate.py
python -m batch.place_enrichment.review_representative_image_candidate --candidate-id 117 --action approve --reviewer ops_001 --note "dry-run visual QA: landmark is identifiable and source/license metadata is present" --quality-level GOOD --landmark-identifiable --checklist --dry-run
python -m batch.place_enrichment.review_representative_image_candidate --candidate-id 117 --action approve --reviewer ops_001 --note "missing landmark flag should fail" --quality-level GOOD --dry-run
python -m batch.place_enrichment.review_representative_image_candidate --candidate-id 117 --action reject --reviewer ops_001 --note "dry-run reject: wrong place risk detected during visual QA" --quality-level BLOCKED --wrong-place-risk --dry-run
python -m batch.place_enrichment.list_representative_image_candidates --expected-name 경포대 --json
```

결과:

- py_compile: PASS
- approve dry-run: PASS
- approve 필수 조건 누락 차단: PASS
- reject dry-run: PASS
- candidate 117 actual status: `PENDING_REVIEW`
- candidate 117 promote_status: `PENDING`

## places/seed 변경 없음 확인

- places row count: `26371`
- `tourism_belt.py` 변경 없음
- `course_builder.py` 변경 없음
- `api_server.py` 변경 없음
- actual promote 실행 없음
- seed 변경 없음
- places update/insert 없음
- image download/store 없음

## 위험 요소

- CLI는 시각 검수를 돕는 도구이며, 실제 이미지 판정은 운영자가 수행해야 함
- 이미지 다운로드/메타데이터 추출은 하지 않으므로 width/height/checksum은 등록 시 제공된 값에 의존함
- dry-run approve는 readiness 가능성만 보여주며 실제 review_status를 변경하지 않음
- GOOD 등급이어도 wrong landmark, watermark, nearby business contamination이 발견되면 reject해야 함

## 다음 작업 제안

1. 운영자가 candidate 117 이미지를 실제 확인한 뒤 dry-run 없이 approve/reject 수행
2. approve 후 representative promote dry-run 재실행으로 IMAGE_MISSING 해소 확인
3. seed overlay QA simulation 재실행으로 경포대 overlay readiness 확인
