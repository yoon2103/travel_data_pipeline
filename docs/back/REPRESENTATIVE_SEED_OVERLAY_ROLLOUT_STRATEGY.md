# Representative / Seed Overlay Rollout Strategy

## Rollout 단계

### 1. STAGING_ONLY

목적:

- representative candidate, image, overview, seed candidate를 staging/review 상태로만 관리한다.
- 추천 엔진과 `tourism_belt.py`에는 영향이 없다.

허용:

- candidate 수집
- manual enrichment 등록
- review approve/reject
- promote dry-run
- overlay QA simulation

금지:

- places insert/update
- seed 변경
- actual overlay 적용
- 추천 엔진 integration

현재 상태:

- 경포대는 이 단계에 있다.

### 2. QA_ONLY

목적:

- approved candidate만 대상으로 overlay 적용을 가정한 QA simulation을 반복한다.
- 실제 추천 요청에는 overlay를 반영하지 않는다.

진입 조건:

- representative candidate `APPROVED`
- representative overview `APPROVED`
- representative image `APPROVED`
- seed candidate `APPROVED` 또는 `READY_FOR_PROMOTE`

검증:

- duplicate nearby risk
- route instability
- spot/culture density
- place_count 변화 예상
- 이동시간 영향 예상

### 3. READ_ONLY_OVERLAY

목적:

- 운영 데이터는 바꾸지 않고 overlay registry를 읽을 수 있는 adapter만 검증한다.
- API 응답이나 추천 결과에는 아직 반영하지 않는다.

허용:

- baseline seed + approved overlay seed를 read-only로 merge하는 내부 diagnostics
- overlay diff report
- rollout allowlist dry-run

금지:

- 사용자 추천 결과 반영
- `tourism_belt.py` 직접 수정
- places overwrite

### 4. LIMITED_REGION_ROLLOUT

목적:

- feature flag로 특정 지역/POI만 overlay를 제한적으로 켠다.
- 최초 대상은 경포대 같은 단일 region/expected POI 단위가 적합하다.

진입 조건:

- QA_ONLY PASS
- READ_ONLY_OVERLAY diagnostics PASS
- rollback snapshot 준비
- smoke test plan 준비
- monitoring 항목 정의 완료

운영 방식:

- region allowlist: 예 `강원`, `강릉`
- expected POI allowlist: 예 `경포대`
- strategy: `COEXIST_WITH_EXISTING`부터 시작
- rollout percentage는 사용하지 않고 명시 allowlist만 사용

### 5. FULL_OVERLAY_ENABLED

목적:

- representative overlay를 여러 지역에 확장한다.

진입 조건:

- LIMITED_REGION_ROLLOUT에서 일정 기간 문제 없음
- rollback trigger 미발생
- QA pass 유지
- 대표 POI 후보군의 image/overview coverage 안정화

주의:

- FULL_OVERLAY_ENABLED는 tourism_belt 장기 migration 전까지도 feature flag로 끌 수 있어야 한다.

## Feature Flag 전략

초기 feature flag는 config/env 기반으로 시작하고, 장기적으로 DB-backed rollout config로 확장한다.

권장 flag:

```text
REPRESENTATIVE_OVERLAY_ENABLED=false
REPRESENTATIVE_OVERLAY_QA_ONLY=true
REPRESENTATIVE_OVERLAY_REGION_ALLOWLIST=강원
REPRESENTATIVE_OVERLAY_POI_ALLOWLIST=경포대
REPRESENTATIVE_OVERLAY_STRATEGY=COEXIST_WITH_EXISTING
REPRESENTATIVE_OVERLAY_READ_ONLY=true
REPRESENTATIVE_OVERLAY_FAIL_CLOSED=true
```

flag 의미:

- `REPRESENTATIVE_OVERLAY_ENABLED`: 실제 overlay 사용 여부
- `REPRESENTATIVE_OVERLAY_QA_ONLY`: QA simulation 전용 모드
- `REPRESENTATIVE_OVERLAY_REGION_ALLOWLIST`: region 제한
- `REPRESENTATIVE_OVERLAY_POI_ALLOWLIST`: expected POI 제한
- `REPRESENTATIVE_OVERLAY_STRATEGY`: `ADDITIVE`, `COEXIST_WITH_EXISTING`, `PRIORITY_OVERRIDE`, `ALIAS_ONLY`
- `REPRESENTATIVE_OVERLAY_READ_ONLY`: overlay read adapter만 활성화
- `REPRESENTATIVE_OVERLAY_FAIL_CLOSED`: overlay 오류 시 baseline seed만 사용

초기 권장값:

- production: overlay disabled
- staging: QA only
- dev/local: read-only overlay diagnostics 허용

## Rollout 대상 우선순위

1. 경포대
   - 현재 대표 seed가 `경포호수광장`이라 대표성 개선 효과가 크다.
   - 다만 duplicate nearby risk가 `MEDIUM`이므로 image approve 후 QA 재검증 필요.

2. 불국사
   - 대표성 기대치가 높고 사용자 인지도가 높다.
   - existing seed/DB exact match 여부와 image/overview 상태 확인 필요.

3. 성산일출봉
   - 제주 대표 POI로 우선순위 높음.
   - 관광지 TourAPI baseline 품질 확인 필요.

4. 전주한옥마을
   - 전주 seed coverage 보강 우선순위 높음.
   - 마을 단위 POI라 boundary/nearby business contamination 검수 필요.

초기 rollout은 한 번에 여러 지역을 켜지 않고 `경포대` 단일 케이스부터 시작한다.

## Rollout 전 필수 조건

대표 POI 단위 필수 조건:

- representative candidate `APPROVED`
- representative image `APPROVED`
- representative overview `APPROVED`
- seed candidate `APPROVED`
- overlay QA simulation `PASS`
- duplicate nearby risk `LOW` 또는 운영자가 `MEDIUM` 허용 사유 기록
- region ambiguity 없음
- lodging/parking/internal facility risk 없음
- rollback snapshot 준비
- baseline QA 결과 보관
- rollout 후 smoke test plan 준비

금지 조건:

- `IMAGE_MISSING`
- `OVERVIEW_MISSING`
- `REGION_UNCLEAR`
- `LODGING_RISK`
- `PARKING_LOT_RISK`
- `INTERNAL_FACILITY_RISK`
- wrong landmark image
- source/license 불명확
- overlay QA 미수행

## Rollout Risk 모델

### LOW

조건:

- candidate/image/overview 모두 approved
- exact or high-confidence representative match
- duplicate nearby risk LOW
- overlay QA warning 없음
- route/time 영향 LOW

조치:

- LIMITED_REGION_ROLLOUT 가능

### MEDIUM

조건:

- duplicate nearby risk MEDIUM
- 동일 권역 spot/culture density 증가 가능
- baseline seed와 overlay가 공존해야 함
- 이동시간 영향 LOW_TO_MEDIUM

조치:

- QA_ONLY 또는 READ_ONLY_OVERLAY 유지
- 운영자 승인 메모 필요
- limited rollout 시 단일 POI만 허용

### HIGH

조건:

- 대표성은 있으나 region/category ambiguity 존재
- image/overview 중 하나가 부족
- nearby business contamination 가능
- route instability 예상

조치:

- rollout 금지
- manual curation 또는 candidate 재검수 필요

### BLOCKED

조건:

- wrong place
- lodging/parking/internal facility substitute
- source/license 불명확한 이미지
- IMAGE_MISSING 또는 OVERVIEW_MISSING
- seed rollback 불가능

조치:

- reject 또는 staging 유지

## Monitoring 항목

rollout 중 확인할 항목:

- place_count 변화
- option별 place_count 분포
- route total_travel_minutes 변화
- 이동시간 한도 초과 여부
- duplicate nearby POI 발생 여부
- spot/culture density 변화
- 동일 권역 과밀 여부
- 대표 POI 선택 빈도
- 기존 seed 선택 빈도
- option_notice/missing_slot_reason 변화
- QA PASS/WEAK/FAIL 변화
- 사용자 화면에서 카드 중복/동선 이상 여부
- API 오류율
- course_generation_logs의 region/option별 변화

## Rollback 전략

rollback 원칙:

- feature flag OFF가 1차 rollback이다.
- overlay registry는 보존하고, 실제 적용만 비활성화한다.
- `tourism_belt.py`를 직접 수정하지 않았기 때문에 baseline으로 즉시 복귀 가능해야 한다.

rollback trigger:

- QA FAIL 증가
- route total_travel_minutes 급증
- duplicate nearby POI가 실제 코스에 반복 노출
- representative POI가 잘못된 장소로 확인
- image/license 문제 발견
- region bias 증가
- 사용자-facing 결과에서 대표 POI가 오히려 품질을 떨어뜨림
- API 오류 또는 overlay read adapter 장애

rollback 절차:

1. `REPRESENTATIVE_OVERLAY_ENABLED=false`
2. overlay 관련 cache가 있으면 clear
3. baseline smoke test
4. rollout log에 rollback reason 기록
5. affected seed candidate status를 `ROLLED_BACK` 또는 `NEEDS_REVIEW`로 변경하는 후속 운영 절차 수행

## Coexist 운영 전략

초기 전략은 `COEXIST_WITH_EXISTING`이 가장 안전하다.

경포대 예:

- baseline seed: `경포호수광장`
- overlay candidate: `경포대`
- 초기에는 기존 seed 제거 금지
- 두 seed를 공존시키고 QA에서 duplicate nearby risk를 측정
- 문제가 없고 대표성 개선이 확인되면 장기적으로 `PRIORITY_OVERRIDE` 검토

전략 비교:

| Strategy | 설명 | 초기 추천 여부 |
| --- | --- | --- |
| `KEEP_EXISTING_ONLY` | baseline만 유지 | 안전하지만 개선 없음 |
| `COEXIST_WITH_EXISTING` | 기존 seed와 representative overlay 공존 | 초기 추천 |
| `PRIORITY_OVERRIDE` | overlay를 우선 적용 | 충분한 QA 후 가능 |
| `REPLACE_EXISTING` | 기존 seed 대체 | 초기 금지 |
| `ALIAS_ONLY` | 대표 POI를 alias/검색 보조로만 사용 | 엔진 영향 최소 |

## actual engine integration 시점 기준

actual engine integration은 아래 조건을 모두 만족한 뒤 검토한다.

- 단일 POI limited rollout dry-run PASS
- approved image/overview coverage 확보
- overlay QA PASS
- rollback flag 동작 확인
- production smoke test plan 확보
- baseline 대비 QA FAIL 증가 없음
- 추천 엔진 변경 범위가 seed loader/read adapter에 한정됨

권장 integration 방식:

- `tourism_belt.py` 직접 수정이 아니라 seed loader adapter 추가
- adapter는 baseline seed를 먼저 읽고, feature flag가 켜진 경우 approved overlay를 merge
- 오류 발생 시 baseline seed만 반환
- course selection/scoring/fallback 로직은 변경하지 않음

## tourism_belt.py 장기 migration 전략

단기:

- `tourism_belt.py`를 baseline source of truth로 유지
- overlay는 staging/read-only/feature flag 기반

중기:

- `seed_registry` 또는 `seed_candidates` approved view를 도입
- baseline seed와 overlay seed를 함께 로드하는 adapter 구성
- audit/review/rollback metadata를 DB에서 관리

장기:

- hardcoded seed를 DB-backed seed registry로 migration
- `tourism_belt.py`는 fallback baseline 또는 initial seed fixture로 축소
- 모든 seed 변경은 staging/review/promote/rollback workflow를 거치게 함

## 운영 checklist

rollout 전:

- representative candidate approved 확인
- representative image approved 확인
- representative overview approved 확인
- seed candidate approved 확인
- overlay QA PASS 확인
- risk level LOW 또는 MEDIUM 승인 메모 확인
- rollback snapshot 및 flag 준비
- baseline QA 결과 저장
- smoke test 대상 region/option 정의

rollout 중:

- feature flag allowlist 확인
- 단일 region/POI만 활성화
- QA 재실행
- route sample 3~5개 시각 확인
- course_generation_logs 변화 확인
- duplicate nearby POI 확인

rollout 후:

- FAIL 증가 여부 확인
- WEAK 증가 여부 확인
- 대표 POI 노출이 실제 품질 개선인지 확인
- rollback trigger 미발생 확인
- 운영 로그 기록

## 경포대 rollout 시나리오

현재 상태:

- representative candidate: candidate `6`, Kakao `경포대`, `APPROVED`
- representative overview: candidate `116`, `APPROVED`
- representative image: candidate `117`, `GOOD`, dry-run approve PASS, actual `PENDING_REVIEW`
- seed candidate: seed_candidate `1`
- baseline seed: `경포호수광장`
- overlay strategy: `COEXIST_WITH_EXISTING`
- current overlay readiness: `NOT_READY`
- current blocker: `IMAGE_MISSING`

1단계:

- candidate `117` 실제 visual review approve
- representative promote dry-run 재실행
- seed overlay QA simulation 재실행

2단계:

- duplicate nearby risk가 여전히 `MEDIUM`이면 QA_ONLY 유지
- image/overview gap이 해소되고 route risk가 허용 가능하면 READ_ONLY_OVERLAY 진입

3단계:

- feature flag로 `강원/경포대`만 allowlist
- `COEXIST_WITH_EXISTING` 전략으로 limited rollout 검토
- 기존 `경포호수광장` 즉시 제거 금지

예상 효과:

- 대표 POI coverage 개선
- 경포호수광장만 노출되던 약한 대표성 문제 완화
- 단, 동일 권역 과밀과 spot/culture bias는 계속 모니터링 필요

## 위험 요소

- representative image가 실제 approve되지 않으면 rollout 불가
- 경포대와 경포호수광장 거리가 가까워 duplicate nearby risk가 존재
- 대표 POI를 추가하면 spot/culture 비중이 증가할 수 있음
- feature flag 없이 엔진에 직접 연결하면 rollback이 어려움
- `tourism_belt.py` 직접 수정은 검수/rollback 이력을 잃게 함
- 대표 POI coverage 문제를 엔진 로직으로 숨기면 장기 품질 관리가 어려워짐

## 다음 작업 제안

1. candidate `117` 실제 visual review approve 여부 결정
2. approve 후 경포대 representative promote dry-run 재실행
3. approve 후 seed overlay QA simulation 재실행
4. feature flag config 초안 설계
5. READ_ONLY_OVERLAY adapter 설계로 넘어가기
