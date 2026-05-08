# Overlay Rollout Gate Checker Report

## 추가 파일

- `batch/place_enrichment/check_overlay_rollout_gate.py`

## CLI 사용법

JSON 출력:

```bash
python -m batch.place_enrichment.check_overlay_rollout_gate \
  --expected-name 경포대 \
  --json
```

사람이 읽는 요약 출력:

```bash
python -m batch.place_enrichment.check_overlay_rollout_gate \
  --expected-name 경포대
```

region 필터:

```bash
python -m batch.place_enrichment.check_overlay_rollout_gate \
  --expected-name 경포대 \
  --region 강원 \
  --json
```

## Representative Gate 결과

자동 판정 기준:

- representative candidate `APPROVED`
- representative image `APPROVED`
- representative overview `APPROVED`
- hard risk 없음

상태:

- `PASS`: 모든 조건 충족
- `QA_REQUIRED`: 대표 후보는 있으나 image/overview 등 보강 검수 필요
- `BLOCKED`: 대표 후보 없음, 대표 후보 미승인, hard risk 존재

경포대 결과:

```json
{
  "status": "QA_REQUIRED",
  "warnings": ["IMAGE_NOT_APPROVED"],
  "representative_candidate": {
    "candidate_id": 6,
    "source_type": "KAKAO",
    "source_name": "경포대",
    "review_status": "APPROVED"
  },
  "image_candidate": {
    "candidate_id": 117,
    "review_status": "PENDING_REVIEW"
  },
  "overview_candidate": {
    "candidate_id": 116,
    "review_status": "APPROVED"
  }
}
```

## Seed Gate 결과

자동 판정 기준:

- seed candidate 존재
- seed candidate review_status `APPROVED`
- seed_status가 rollout 가능 상태
- duplicate nearby risk `HIGH` 아님
- hard risk 없음

rollout 가능 seed_status:

- `APPROVED`
- `READY_FOR_PROMOTE`
- `COEXIST`

경포대 결과:

```json
{
  "status": "QA_REQUIRED",
  "warnings": [
    "SEED_REVIEW_NOT_APPROVED",
    "SEED_STATUS_NOT_READY",
    "DUPLICATE_NEARBY_RISK_MEDIUM"
  ],
  "seed_candidate": {
    "seed_candidate_id": 1,
    "existing_seed_name": "경포호수광장",
    "candidate_place_name": "경포대",
    "promote_strategy": "COEXIST_WITH_EXISTING",
    "seed_status": "NEEDS_REVIEW",
    "review_status": "PENDING_REVIEW"
  },
  "duplicate_nearby": {
    "distance_km": 1.17,
    "risk": "MEDIUM"
  }
}
```

## Overlay Gate 결과

자동 판정 기준:

- overlay diagnostics PASS
- eligible overlay count > 0
- blocked overlay 없음
- fail-closed 상태 정상

경포대 결과:

```json
{
  "status": "QA_REQUIRED",
  "eligible_overlay_count": 0,
  "blocked_overlay_count": 1,
  "merged_seed_count": 23,
  "warnings": [
    "ELIGIBLE_OVERLAY_COUNT_ZERO",
    "BLOCKED_OVERLAY_EXISTS",
    "SEED_REVIEW_NOT_APPROVED",
    "SEED_STATUS_NOT_READY",
    "IMAGE_NOT_APPROVED"
  ]
}
```

## 최종 Rollout Gate

지원 상태:

- `BLOCKED`
- `QA_REQUIRED`
- `READY_FOR_QA_ONLY`
- `READY_FOR_READ_ONLY_OVERLAY`
- `READY_FOR_LIMITED_ROLLOUT`
- `READY_FOR_MANUAL_PROMOTE`

현재 경포대 최종 판정:

```text
QA_REQUIRED
```

판정 이유:

- representative image candidate `117`이 아직 actual `APPROVED`가 아님
- seed candidate `1`이 아직 `PENDING_REVIEW`
- seed_status가 `NEEDS_REVIEW`
- eligible overlay count가 `0`
- duplicate nearby risk가 `MEDIUM`

## Blocker Summary

경포대 blocker/warning summary:

- `IMAGE_NOT_APPROVED`
- `SEED_REVIEW_NOT_APPROVED`
- `SEED_STATUS_NOT_READY`
- `DUPLICATE_NEARBY_RISK_MEDIUM`
- `ELIGIBLE_OVERLAY_COUNT_ZERO`
- `BLOCKED_OVERLAY_EXISTS`

## 경포대 Gate 결과

요약:

```text
representative_gate: QA_REQUIRED
seed_gate: QA_REQUIRED
overlay_gate: QA_REQUIRED
final_rollout_gate: QA_REQUIRED
```

다음 action:

```text
Approve or reject representative image through visual review before overlay rollout.
```

## Fail-closed 상태

경포대 기본 실행:

```json
{
  "db_write_disabled": true,
  "places_unchanged": true,
  "seed_unchanged": true,
  "engine_unchanged": true,
  "build_course_not_called": true,
  "fallback_behavior": "baseline_only_on_overlay_error_or_ineligible_candidate"
}
```

`REPRESENTATIVE_OVERLAY_READ_ONLY=false` 테스트:

- fallback_active: `true`
- fallback_reason: `REPRESENTATIVE_OVERLAY_READ_ONLY=false`
- eligible_overlay_count: `0`
- merged_seed_count: `23`
- final_rollout_gate: `QA_REQUIRED`

## 테스트 결과

실행:

```bash
python -m py_compile .\batch\place_enrichment\check_overlay_rollout_gate.py
python -m batch.place_enrichment.check_overlay_rollout_gate --expected-name 경포대 --json
python -m batch.place_enrichment.check_overlay_rollout_gate --expected-name 불국사 --json
python -m batch.place_enrichment.check_overlay_rollout_gate --expected-name __없는대표POI__ --json
```

결과:

- py_compile: PASS
- 경포대: `QA_REQUIRED`
- 불국사: `BLOCKED`
  - `REPRESENTATIVE_NOT_APPROVED`
  - `IMAGE_NOT_APPROVED`
  - `OVERVIEW_NOT_APPROVED`
  - `NO_SEED_CANDIDATE`
- 없는 대표 POI: `BLOCKED`
  - `REPRESENTATIVE_NOT_FOUND`
  - `NO_SEED_CANDIDATE`
  - `ELIGIBLE_OVERLAY_COUNT_ZERO`
- 경포대 read-only flag off fallback: PASS

## places/seed 변경 없음 확인

- places row count: `26371`
- `tourism_belt.py` 변경 없음
- `course_builder.py` 변경 없음
- `api_server.py` 변경 없음
- actual rollout 없음
- actual approve/write 없음
- actual overlay 없음
- build_course 호출 없음
- places write 없음
- seed write 없음

## 위험 요소

- gate checker는 현재 DB 상태만 판정하므로 dry-run approve 결과는 actual approved로 계산하지 않는다.
- duplicate nearby risk `MEDIUM`은 blocker가 아니라 QA warning으로 유지했다.
- final gate는 rollout을 열지 않고 readiness만 표시한다.
- `READY_FOR_LIMITED_ROLLOUT`, `READY_FOR_MANUAL_PROMOTE`는 향후 QA/smoke/rollback snapshot 검증이 추가되어야 자동 판정 가능하다.

## 다음 작업 제안

1. candidate `117` actual visual review approve 여부 결정
2. seed candidate `1` review approve 여부 결정
3. approvals 이후 gate checker 재실행
4. eligible overlay count > 0이 되면 QA-only 비교 리포트 구현
