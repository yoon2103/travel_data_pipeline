# Representative Governance End-to-End Simulation Report

## Simulation 흐름

대상: `경포대`

이번 실행은 모두 dry-run/read-only 기준으로 수행했다.

1. representative image candidate `117` visual review dry-run approve
2. representative image/overview/candidate 상태 조회
3. `representative_promote_dry_run` 재실행
4. `simulate_seed_overlay_qa` 재실행
5. places/seed/engine 변경 없음 확인

실행 명령:

```bash
python -m batch.place_enrichment.review_representative_image_candidate \
  --candidate-id 117 \
  --action approve \
  --reviewer ops_001 \
  --note "end-to-end simulation: landmark identifiable, no contamination, GOOD quality" \
  --quality-level GOOD \
  --landmark-identifiable \
  --dry-run

python -m batch.place_enrichment.representative_promote_dry_run \
  --expected-name 경포대 \
  --approved-only \
  --json

python -m batch.place_enrichment.simulate_seed_overlay_qa \
  --expected-name 경포대 \
  --strategy COEXIST_WITH_EXISTING \
  --json
```

## Representative readiness 변화

### Visual review dry-run 기준

candidate `117` dry-run approve 결과:

- previous_status: `PENDING_REVIEW`
- dry-run review_status: `APPROVED`
- promote_status: `PENDING`
- quality_level: `GOOD`
- landmark_identifiable: `true`
- contamination_flags: `[]`
- source_validity: `VALID`
- license_validity: `VALID`
- duplicate_url_count: `1`
- places_changed: `false`
- seed_changed: `false`
- promote_executed: `false`

Dry-run readiness impact:

- image_gap_resolved: `true`
- next_readiness: `READY_FOR_SEED_OVERLAY_QA_RECHECK`
- 의미: 실제 visual approve를 수행하면 representative IMAGE_MISSING은 해소 가능한 상태다.

### 실제 DB 상태 기준

실제 write를 하지 않았기 때문에 현재 DB 상태는 그대로다.

- candidate `117`: `PENDING_REVIEW`
- candidate `116` overview: `APPROVED`
- candidate `6` Kakao representative: `APPROVED`
- candidate `117` actual approval 전까지 실제 readiness는 image gap을 계속 가진다.

## Overlay readiness 변화

`representative_promote_dry_run` 결과:

- candidate_count: `2`
- readiness_counts: `READY_FOR_MANUAL_PROMOTE = 2`
- 경포대 approved candidates:
  - candidate `116`: manual overview, `APPROVED`
  - candidate `6`: Kakao place match, `APPROVED`

주의:

- promote dry-run은 현재 승인된 representative candidate만 기준으로 계산한다.
- candidate `117` visual approve는 dry-run이므로 이 단계의 실제 DB 기반 계산에는 반영되지 않는다.

`simulate_seed_overlay_qa` 결과:

- strategy: `COEXIST_WITH_EXISTING`
- baseline seed: `경포호수광장`
- overlay candidate: `경포대`
- seed_candidate_id: `1`
- representative_candidate_id: `6`
- representative_review_status: `APPROVED`
- nearby_seed_distance_km: `1.172`
- duplicate_nearby_risk: `MEDIUM`
- overlay_risk: `MEDIUM`
- readiness: `NOT_READY`
- risk_flags: `IMAGE_MISSING`

QA warnings:

- approved representative image is missing
- baseline and overlay seed are nearby: duplicate risk `MEDIUM`
- spot/culture seed density may increase

## 경포대 end-to-end 상태

| Layer | Current State | Simulation State | Notes |
| --- | --- | --- | --- |
| Representative place candidate | `candidate 6 APPROVED` | 유지 | Kakao 경포대, confidence `93.00` |
| Representative overview | `candidate 116 APPROVED` | 유지 | manual overview approved |
| Representative image | `candidate 117 PENDING_REVIEW` | dry-run approve PASS | GOOD + landmark identifiable 조건 통과 |
| Seed candidate | `seed_candidate 1` | staging only | actual overlay 적용 없음 |
| Overlay QA | `NOT_READY` | image approve 후 재검증 필요 | 현재 DB 기준 `IMAGE_MISSING` |
| Final readiness | `NOT_READY` | simulated next: `READY_FOR_SEED_OVERLAY_QA_RECHECK` | actual visual approve 전까지 promote 불가 |

## 최종 readiness 정의

- `NOT_READY`: 실제 DB 기준 현재 상태. seed overlay QA에서 `IMAGE_MISSING` 때문에 유지.
- `READY_WITH_IMAGE_GAP`: image candidate가 없거나 reject된 상태.
- `READY_FOR_SEED_OVERLAY_QA_RECHECK`: candidate `117`이 실제 visual approve되면 도달 가능한 다음 상태.
- `READY_FOR_MANUAL_PROMOTE`: representative candidate, overview, image가 모두 승인되고 overlay QA 재검증이 통과한 뒤에만 고려 가능.

현재 결론:

- 실제 상태: `NOT_READY`
- dry-run optimistic state: `READY_FOR_SEED_OVERLAY_QA_RECHECK`
- actual promote 가능 상태: 아님

## actual promote blocker

현재 actual promote를 막는 요인:

1. candidate `117`은 아직 실제 `APPROVED`가 아님
2. seed overlay simulation이 DB 기준 `IMAGE_MISSING`으로 `NOT_READY`
3. baseline seed `경포호수광장`과 overlay `경포대` 거리가 `1.172km`로 duplicate nearby risk `MEDIUM`
4. COEXIST 전략 적용 시 spot/culture 권역 과밀 가능성 있음
5. actual overlay 적용 전 QA 재실행 필요
6. actual promote/seed 변경 정책은 아직 dry-run 단계

## places/seed 변경 없음 확인

- places row count: `26371`
- `tourism_belt.py` 변경 없음
- `course_builder.py` 변경 없음
- `api_server.py` 변경 없음
- places write 없음
- seed write 없음
- actual promote 없음
- actual overlay 적용 없음

## 위험 요소

- dry-run visual approve는 실제 review_status를 변경하지 않으므로 후속 dry-run 도구에는 자동 반영되지 않는다.
- candidate `117`이 실제 approve되어도 duplicate nearby risk `MEDIUM`은 별도 QA가 필요하다.
- 경포대와 경포호수광장을 공존시키면 같은 권역 내 대표 POI 밀도가 올라갈 수 있다.
- 현재 구조는 image download/store를 하지 않으므로 메타데이터는 등록 시 입력값에 의존한다.
- actual promote 전에는 대표 이미지 저작권/source/license 검수를 다시 확인해야 한다.

## 다음 작업 제안

1. 운영자가 candidate `117`을 실제 visual review approve 또는 reject
2. approve 후 `representative_promote_dry_run` 재실행
3. approve 후 `simulate_seed_overlay_qa --strategy COEXIST_WITH_EXISTING` 재실행
4. duplicate nearby risk와 spot/culture density risk가 허용 가능한지 QA 판단
5. 그 다음에야 manual promote/seed overlay 정책 검토
