# Representative Overlay Rollout Gate Checklist

## Rollout Gate 모델

rollout gate는 실제 운영 반영 전 상태를 명확히 나누기 위한 모델이다.

### BLOCKED

운영 rollout 금지.

조건:

- representative candidate 미승인
- image 미승인
- overview 미승인
- seed candidate 미승인
- hard risk 존재
- duplicate nearby risk `HIGH`
- overlay diagnostics 실패
- fail-closed 동작 미확인
- rollback 준비 없음

### QA_REQUIRED

대표 후보는 일부 준비되었지만 QA가 더 필요하다.

조건:

- representative candidate는 approved
- image/overview 중 하나가 dry-run 또는 pending
- seed candidate가 `NEEDS_REVIEW`
- duplicate nearby risk `MEDIUM`
- overlay simulation warning 존재

### READY_FOR_QA_ONLY

실제 반영 없이 QA simulation만 수행 가능.

조건:

- representative candidate approved
- image approved
- overview approved
- seed candidate 최소 `PENDING_REVIEW` 이상
- hard risk 없음
- QA simulation 입력값 충분

### READY_FOR_READ_ONLY_OVERLAY

read-only adapter diagnostics에서 overlay merged view를 검증할 수 있는 상태.

조건:

- seed candidate approved
- representative/image/overview approved
- overlay diagnostics PASS
- fail-closed 확인 완료
- eligible overlay count > 0

### READY_FOR_LIMITED_ROLLOUT

feature flag allowlist 기반 limited rollout 검토 가능.

조건:

- READ_ONLY_OVERLAY PASS
- QA 결과 PASS
- duplicate nearby risk `LOW` 또는 `MEDIUM` 운영 승인 메모 존재
- rollback snapshot 준비
- smoke test plan 준비
- monitoring 항목 준비

### READY_FOR_MANUAL_PROMOTE

실제 manual promote 의사결정 가능 단계.

조건:

- limited rollout 결과 문제 없음
- rollback trigger 미발생
- 운영 승인자 최종 확인
- promote payload와 rollback payload 준비

## Representative Gate

필수 조건:

- representative candidate `APPROVED`
- representative image `APPROVED`
- representative overview `APPROVED`
- no hard risk
- source/license/provenance 확인
- wrong landmark risk 없음
- nearby business contamination 없음

Hard risk:

- `REGION_UNCLEAR`
- `CATEGORY_RISK`
- `LODGING_RISK`
- `PARKING_LOT_RISK`
- `INTERNAL_FACILITY_RISK`
- `SUB_FACILITY_RISK`
- wrong landmark image
- source/license 불명확

판정:

- 모든 조건 충족: representative gate PASS
- image 또는 overview 미승인: QA_REQUIRED 또는 BLOCKED
- hard risk 존재: BLOCKED

## Seed Gate

필수 조건:

- seed candidate review_status `APPROVED`
- seed_status `APPROVED`, `READY_FOR_PROMOTE`, 또는 `COEXIST`
- promote_strategy 확인
- duplicate nearby risk 평가
- baseline seed 보호 전략 확인

권장 초기 strategy:

- `COEXIST_WITH_EXISTING`

차단 조건:

- seed candidate `NEEDS_REVIEW`
- seed review_status `PENDING_REVIEW`
- duplicate nearby risk `HIGH`
- existing seed 제거가 필요한 전략
- QA 미수행

## Overlay Gate

필수 조건:

- overlay diagnostics PASS
- fail-closed 정상
- eligible overlay count > 0
- blocked overlay count = 0 또는 blocker가 모두 해소됨
- merged seed view가 의도대로 생성됨
- build_course 호출 없음
- engine_changed=false
- places_changed=false
- seed_changed=false

차단 조건:

- eligible overlay count = 0
- `IMAGE_NOT_APPROVED`
- `OVERVIEW_NOT_APPROVED`
- `SEED_REVIEW_NOT_APPROVED`
- `SEED_STATUS_NOT_READY`
- `REPRESENTATIVE_NOT_APPROVED`
- hard risk flags

## Rollout Blockers

대표 blocker:

- `IMAGE_NOT_APPROVED`
- `OVERVIEW_NOT_APPROVED`
- `SEED_REVIEW_NOT_APPROVED`
- `SEED_STATUS_NOT_READY`
- `REPRESENTATIVE_NOT_APPROVED`
- `HARD_RISK_FLAGS`
- duplicate risk `HIGH`
- QA FAIL 증가
- rollback snapshot 없음
- smoke test plan 없음
- feature flag rollback 미검증
- source/license 문제
- actual visual QA 미수행
- production monitoring 준비 없음

## 운영 Checklist

rollout 전 운영자가 확인할 항목:

- representative candidate가 `APPROVED`인가?
- representative image가 실제 visual QA 후 `APPROVED`인가?
- representative overview가 `APPROVED`인가?
- seed candidate가 `APPROVED`인가?
- seed_status가 rollout 가능한 상태인가?
- hard risk flag가 없는가?
- duplicate nearby risk가 `LOW`인가?
- `MEDIUM`이면 운영 승인 메모가 있는가?
- overlay diagnostics에서 eligible overlay count > 0인가?
- blocked overlay count가 0인가?
- fail-closed 테스트를 수행했는가?
- feature flag OFF 시 baseline only로 돌아가는가?
- baseline QA 결과를 저장했는가?
- overlay QA 결과를 저장했는가?
- smoke test 대상 region/option이 정의되었는가?
- rollback snapshot 또는 rollback payload가 준비되었는가?
- rollout 후 monitoring 항목이 준비되었는가?
- 실제 production enable은 별도 승인 단계로 분리되어 있는가?

## 경포대 현재 Gate 상태

현재 확인된 상태:

- representative candidate: `APPROVED`
- representative overview: `APPROVED`
- representative image: GOOD이지만 actual approve 아님, dry-run visual approve만 PASS
- seed candidate: `NEEDS_REVIEW`
- seed review_status: `PENDING_REVIEW`
- eligible overlay count: `0`
- blocked overlay count: `1`
- duplicate nearby risk: `MEDIUM`
- overlay diagnostics: fail-closed 정상
- actual rollout: 없음

현재 blocker:

- `IMAGE_NOT_APPROVED`
- `SEED_REVIEW_NOT_APPROVED`
- `SEED_STATUS_NOT_READY`
- eligible overlay count = 0
- duplicate nearby risk `MEDIUM`

현재 gate 판정:

```text
QA_REQUIRED
```

설명:

- representative place와 overview는 준비됐지만 image는 dry-run approve 상태일 뿐 실제 approved가 아니다.
- seed candidate도 아직 review/promotion 가능 상태가 아니다.
- overlay read adapter 기준 eligible overlay가 0이므로 READ_ONLY_OVERLAY 단계로 갈 수 없다.
- duplicate nearby risk가 `MEDIUM`이라 image/seed 승인 후에도 QA 판단이 필요하다.

다음 gate로 가기 위한 조건:

1. candidate `117` actual visual review approve
2. seed candidate `1` review approve
3. seed_status를 rollout 가능한 상태로 전환
4. overlay diagnostics 재실행
5. eligible overlay count > 0 확인
6. duplicate nearby risk `MEDIUM`에 대한 운영 승인 메모 작성

## Rollout 승인 흐름

권장 승인 흐름:

1. Reviewer
   - representative candidate/image/overview 검수
   - visual QA note 작성
   - source/license 확인

2. QA
   - representative promote dry-run
   - seed overlay QA simulation
   - duplicate nearby risk 평가

3. Overlay diagnostics
   - read adapter 실행
   - eligible overlay 확인
   - fail-closed 확인

4. Rollout approval
   - region/POI allowlist 확정
   - strategy 확정
   - risk approval note 기록

5. Smoke test
   - baseline vs overlay 결과 비교
   - 주요 옵션별 코스 생성 확인
   - duplicate/동선/role bias 확인

6. Rollback readiness
   - feature flag OFF 확인
   - baseline only 복귀 확인
   - rollback reason/log 준비

## Fail-closed 원칙

원칙:

- overlay 오류가 발생하면 baseline seed만 사용한다.
- candidate가 eligible하지 않으면 merged view에 넣지 않는다.
- feature flag가 꺼져 있으면 baseline only로 동작한다.
- engine integration 전까지 `build_course`는 호출하지 않는다.
- diagnostics 실패가 추천 엔진에 영향을 주면 안 된다.

확인 기준:

- `places_changed=false`
- `seed_changed=false`
- `engine_changed=false`
- `build_course_called=false`
- fallback reason이 payload에 남아야 함

## 위험 요소

- dry-run approve를 actual approve로 오해하면 rollout gate가 잘못 열릴 수 있다.
- duplicate nearby risk `MEDIUM`은 실제 코스에서 중복 체감으로 이어질 수 있다.
- seed candidate 상태와 representative candidate 상태를 분리해서 봐야 한다.
- feature flag 없이 engine에 직접 연결하면 rollback이 어려워진다.
- image/source/license 검수 없이 대표 POI를 노출하면 운영 리스크가 커진다.

## 다음 작업 제안

1. candidate `117` actual visual review 승인 여부 결정
2. seed candidate `1` review approve 여부 결정
3. gate checker CLI 설계
4. gate checker가 `BLOCKED`, `QA_REQUIRED`, `READY_FOR_READ_ONLY_OVERLAY`를 자동 산출하도록 구현
5. production enable 전 smoke test template 작성
