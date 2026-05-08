# Seed Candidate Governance Design

생성일: 2026-05-08

## 목적

`tourism_belt.py`에 하드코딩된 seed를 직접 수정하지 않고, 대표 POI 후보를 seed 후보로 staging / review / promote / rollback 할 수 있는 governance 구조를 설계한다.

현재 문제:

- `경포대` 같은 대표 POI 후보와 기존 seed `경포호수광장`이 coexist 상태다.
- representative POI staging/review는 있지만 seed 자체의 lifecycle이 없다.
- seed 변경은 추천 결과에 직접 영향을 주므로 파일 직접 수정 방식은 위험하다.

이번 문서는 설계 전용이다.

- `tourism_belt.py` 수정 없음
- actual seed promote 없음
- 추천 엔진 수정 없음
- DB migration 실행 없음

## Seed Candidate 구조

### 제안 테이블

테이블명:

- `seed_candidates`

목적:

- 기존 seed와 대표 POI 후보를 비교 검수한다.
- seed 교체/공존/alias-only 전략을 staging 상태로 관리한다.
- actual promote 전 dry-run, QA, rollback 준비 상태를 기록한다.

### DDL 초안

```sql
CREATE TABLE IF NOT EXISTS seed_candidates (
    seed_candidate_id          BIGSERIAL PRIMARY KEY,

    region_1                   VARCHAR(50) NOT NULL,
    region_2                   VARCHAR(50),

    expected_poi_name          VARCHAR(255) NOT NULL,
    existing_seed_name         VARCHAR(255),
    representative_candidate_id BIGINT REFERENCES representative_poi_candidates(candidate_id) ON DELETE SET NULL,

    source_type                VARCHAR(30) NOT NULL DEFAULT 'REPRESENTATIVE_POI',
    candidate_place_name       VARCHAR(255) NOT NULL,

    promote_strategy           VARCHAR(40) NOT NULL DEFAULT 'COEXIST_WITH_EXISTING',
    seed_status                VARCHAR(40) NOT NULL DEFAULT 'CANDIDATE',
    review_status              VARCHAR(40) NOT NULL DEFAULT 'PENDING_REVIEW',

    risk_flags                 JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    review_payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
    dry_run_payload            JSONB NOT NULL DEFAULT '{}'::jsonb,
    rollback_payload           JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (source_type IN ('REPRESENTATIVE_POI', 'MANUAL', 'TOURAPI', 'KAKAO', 'NAVER')),
    CHECK (promote_strategy IN (
        'KEEP_EXISTING_ONLY',
        'COEXIST_WITH_EXISTING',
        'REPLACE_EXISTING',
        'REPRESENTATIVE_ALIAS_ONLY'
    )),
    CHECK (seed_status IN (
        'CANDIDATE',
        'NEEDS_REVIEW',
        'APPROVED',
        'REJECTED',
        'COEXIST',
        'READY_FOR_PROMOTE',
        'PROMOTED',
        'ROLLED_BACK'
    )),
    CHECK (review_status IN (
        'PENDING_REVIEW',
        'IN_REVIEW',
        'APPROVED',
        'REJECTED',
        'SKIPPED'
    )),
    CHECK (length(trim(expected_poi_name)) > 0),
    CHECK (length(trim(candidate_place_name)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_seed_candidates_region_status
    ON seed_candidates(region_1, region_2, seed_status, review_status);

CREATE INDEX IF NOT EXISTS idx_seed_candidates_expected_name
    ON seed_candidates(expected_poi_name);

CREATE INDEX IF NOT EXISTS idx_seed_candidates_representative
    ON seed_candidates(representative_candidate_id)
    WHERE representative_candidate_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_seed_candidates_active_candidate
    ON seed_candidates(region_1, COALESCE(region_2, ''), expected_poi_name, candidate_place_name, promote_strategy)
    WHERE seed_status NOT IN ('REJECTED', 'ROLLED_BACK');
```

### 주요 컬럼 설명

| 컬럼 | 의미 |
|---|---|
| `expected_poi_name` | 사용자가 기대하는 대표 명소명. 예: `경포대` |
| `existing_seed_name` | 현재 `tourism_belt.py`에 있는 seed. 예: `경포호수광장` |
| `representative_candidate_id` | 승인된 representative POI 후보 |
| `candidate_place_name` | seed 후보로 올릴 장소명 |
| `promote_strategy` | 기존 seed 유지/공존/교체/alias-only 전략 |
| `seed_status` | seed 후보 lifecycle |
| `review_status` | 운영자 검수 상태 |
| `risk_flags` | seed 교체 위험 플래그 |
| `dry_run_payload` | 예상 추천 영향/QA 결과 |
| `rollback_payload` | promote 이전 seed snapshot과 rollback 방법 |

## Seed 상태 모델

| 상태 | 의미 | 다음 단계 |
|---|---|---|
| `CANDIDATE` | seed 후보가 생성됨 | 검증 또는 review |
| `NEEDS_REVIEW` | 위험 플래그나 정보 부족으로 검수 필요 | approve/reject |
| `APPROVED` | 운영자가 seed 후보를 승인 | dry-run |
| `REJECTED` | seed 후보 부적합 | 종료 |
| `COEXIST` | 기존 seed와 신규 대표 후보 공존 권장 | QA 비교 |
| `READY_FOR_PROMOTE` | QA와 dry-run 통과 | 수동 promote 가능 |
| `PROMOTED` | 실제 seed 반영 완료 | monitoring |
| `ROLLED_BACK` | promote 후 rollback 완료 | 종료 또는 재검토 |

상태 전이:

```text
CANDIDATE
  -> NEEDS_REVIEW
  -> APPROVED
  -> COEXIST
  -> READY_FOR_PROMOTE
  -> PROMOTED
  -> ROLLED_BACK

CANDIDATE / NEEDS_REVIEW / APPROVED
  -> REJECTED

COEXIST
  -> READY_FOR_PROMOTE
  -> REJECTED
```

## Promote 전략

### KEEP_EXISTING_ONLY

의미:

- 기존 seed만 유지한다.
- 신규 대표 후보는 seed로 반영하지 않는다.

사용 조건:

- 신규 후보가 대표성이 불충분
- 기존 seed가 충분히 대표적
- 신규 후보가 오매칭/중복/품질 문제 있음

### COEXIST_WITH_EXISTING

의미:

- 기존 seed와 신규 대표 후보를 함께 유지한다.
- 즉시 교체하지 않고 QA에서 노출/동선 영향을 비교한다.

사용 조건:

- 기존 seed가 완전히 틀린 것은 아니지만 대표성이 약함
- 신규 대표 후보가 강하지만 실제 코스 영향 검증 전
- 사용자 기대 POI와 주변 POI가 모두 방문 가치가 있음

예:

- `경포대`와 `경포호수광장`

### REPLACE_EXISTING

의미:

- 기존 seed를 신규 대표 후보로 교체한다.

사용 조건:

- 기존 seed가 대표성이 낮고 하위/부속/오염 POI임이 확인됨
- 신규 후보가 approved representative candidate
- image/overview/좌표/카테고리 검수 완료
- QA에서 개선 확인
- rollback snapshot 존재

주의:

- 자동 실행 금지
- 최초 promote 전략으로 권장하지 않음

### REPRESENTATIVE_ALIAS_ONLY

의미:

- seed 자체는 바꾸지 않고 alias/matching만 보강한다.

사용 조건:

- `강릉 경포대`와 `경포대`처럼 같은 장소의 명칭 차이
- 새 places row가 필요 없고 alias로 충분한 경우
- 추천 엔진 변경 없이 데이터 검수/매칭 안정화가 우선인 경우

## 기존 Seed 보호 정책

### 기본 원칙

- 기존 seed는 자동 삭제하지 않는다.
- 신규 대표 후보가 생겨도 즉시 replace하지 않는다.
- 처음에는 `COEXIST_WITH_EXISTING`을 기본 전략으로 둔다.
- 기존 seed가 실제 방문 가치가 있으면 보조 POI로 유지 가능하다.
- seed 제거는 별도 QA와 rollback snapshot이 있는 경우만 허용한다.

### 보호 대상

아래 seed는 바로 제거하지 않는다.

- 기존 QA에서 안정적으로 코스를 생성하던 seed
- 대표 POI 주변이지만 실제 방문 가치가 있는 장소
- 동선 anchor로 기능하던 장소
- 데이터가 충분하지 않은 지역에서 후보 pool 안정성을 제공하던 seed

### 교체 검토 대상

아래 seed는 review 후 교체 검토 가능하다.

- 광장/주차장/호텔/펜션/상점이 대표 명소를 대체하는 경우
- 내부시설/서고/도서관/기념탑이 본체 명소를 대체하는 경우
- 이름은 비슷하지만 다른 지역 또는 다른 시설
- 이미지/overview가 없고 대표성도 낮은 seed

## Rollback 전략

### Snapshot 기준

actual seed promote 전 반드시 아래를 저장한다.

- 기존 seed 목록 전체
- 변경 대상 region의 seed 목록
- seed candidate payload
- promote strategy
- review 승인자/승인 시각
- dry-run 결과
- QA 결과
- smoke test 결과
- rollback 명령 또는 복원 payload

### Rollback 단위

| 변경 유형 | rollback |
|---|---|
| seed 추가 | 추가 seed 제거 또는 inactive 처리 |
| seed 교체 | 이전 seed 복원 |
| coexist 적용 | 신규 seed만 비활성화 |
| alias 추가 | alias 비활성화 |
| DB registry 변경 | 이전 registry snapshot 복원 |

### Rollback 조건

- QA FAIL 증가
- 대표 seed가 실제 코스에 과도하게 반복 노출
- 동선이 악화됨
- 대표 POI 오매칭 확인
- 사용자 기대와 다른 장소가 노출
- 기존 seed 제거 후 지역 coverage 저하
- 운영자가 rollback 요청

## Seed Dry-run 예시

### 경포대 promote dry-run

입력:

```json
{
  "region_1": "강원",
  "region_2": "강릉",
  "expected_poi_name": "경포대",
  "existing_seed_name": "경포호수광장",
  "representative_candidate_id": 6,
  "candidate_place_name": "경포대",
  "promote_strategy": "COEXIST_WITH_EXISTING"
}
```

dry-run 출력 예:

```json
{
  "seed_candidate_id": 1,
  "expected_poi_name": "경포대",
  "existing_seed_name": "경포호수광장",
  "candidate_place_name": "경포대",
  "promote_strategy": "COEXIST_WITH_EXISTING",
  "existing_seed_action": "KEEP",
  "candidate_seed_action": "ADD_AS_CANDIDATE",
  "qa_required": true,
  "expected_recommendation_impact": {
    "representative_quality_improvement": true,
    "route_stability_risk": "LOW_TO_MEDIUM",
    "duplicate_nearby_poi_risk": "MEDIUM"
  },
  "blocks": [],
  "warnings": [
    "existing weak seed preserved",
    "image gap must be resolved before actual promote",
    "coexist may create near-duplicate 경포 권역 candidates"
  ],
  "readiness": "NEEDS_REVIEW"
}
```

### 경포대 기준 판단

현재 상태:

- representative candidate `6`: APPROVED
- representative overview `116`: APPROVED
- representative image: 없음
- candidate image `115`: REJECTED
- existing seed: `경포호수광장`

결론:

- seed promote는 아직 금지
- `COEXIST_WITH_EXISTING` 후보 생성까지는 가능
- actual seed promote 전 image gap 해소 필요
- 기존 `경포호수광장`은 유지

## QA 체크리스트

seed promote dry-run 또는 actual promote 전 아래를 확인한다.

### 데이터 QA

- representative candidate가 APPROVED인가?
- image/overview gap이 없는가?
- 좌표가 정확한가?
- 카테고리가 관광지/문화/명소 계열인가?
- existing seed와 거리상 중복인가?
- 기존 seed가 하위/부속 POI인가?
- candidate가 호텔/펜션/주차장/상점이 아닌가?

### 추천 QA

- 해당 region/option 전체 QA PASS/WEAK/FAIL 변화
- 대표 seed 추가 후 place_count 변화
- 이동시간 증가 여부
- role 분포 변화
- 특정 seed 과다 노출 여부
- 기존 대표 코스 품질 저하 여부
- LIMITED/BLOCKED 지역 영향 없음

### 운영 QA

- dry-run report 저장 여부
- review_payload 존재 여부
- rollback_payload 존재 여부
- 운영자 reviewer_id 존재 여부
- smoke test 결과
- 배포 전 diff 확인

## 절대 자동 Promote 금지 조건

아래 조건 중 하나라도 있으면 seed 자동 promote 금지다.

- approved representative candidate 없음
- approved representative image 없음
- approved representative overview 없음
- `IMAGE_MISSING`
- `OVERVIEW_MISSING`
- `REGION_UNCLEAR`
- `CATEGORY_RISK`
- `LODGING_RISK`
- `PARKING_LOT_RISK`
- `INTERNAL_FACILITY_RISK`
- `SUB_FACILITY_RISK`
- 기존 seed 삭제가 포함됨
- QA 미실행
- rollback snapshot 없음
- `tourism_belt.py` 직접 수정 필요
- 후보가 신규 places insert 전 상태
- 운영자 승인 없음

## tourism_belt 장기 구조 제안

### Option A: 파일 하드코딩 유지

구조:

- `tourism_belt.py`를 계속 source of truth로 사용
- seed 변경은 PR/diff 기반으로 관리

장점:

- 단순함
- 추천 엔진 변경 최소
- 런타임 DB 의존 없음

단점:

- 운영자가 seed를 UI/DB에서 관리하기 어려움
- rollback이 Git 배포 단위에 묶임
- review/promote workflow와 연결이 약함

권장도:

- 단기 유지 가능
- 장기 운영에는 한계

### Option B: DB 기반 seed registry

구조:

- `seed_registry` 또는 `tourism_belt_seeds` 테이블을 source of truth로 사용
- 추천 엔진은 DB에서 active seeds를 조회

장점:

- review/promote/rollback 관리 쉬움
- 운영 dashboard 확장 가능
- region별 seed 상태 관리 가능

단점:

- 추천 엔진 DB query 변경 필요
- 장애 시 seed 로딩 리스크
- migration과 cache 전략 필요

권장도:

- 중장기 권장
- 단, 엔진 변경은 최소화하고 read-only adapter부터 시작

### Option C: Hybrid seed registry

구조:

- `tourism_belt.py`는 baseline seed로 유지
- DB `seed_candidates` 또는 `seed_registry`는 overlay layer로 사용
- 추천 엔진은 baseline + approved overlay를 합성

장점:

- 기존 안정성 유지
- 신규 seed 실험 가능
- rollback이 쉬움
- 점진 전환 가능

단점:

- 중복/우선순위 정책 필요
- 엔진에 overlay read adapter가 필요

권장도:

- 가장 현실적인 단계적 전환안

### 권장 로드맵

1. `tourism_belt.py` 유지
2. `seed_candidates` staging/review/dry-run 구현
3. seed QA report 구현
4. approved seed overlay를 별도 read-only 파일 또는 DB view로 생성
5. 추천 엔진에 overlay를 읽는 adapter를 최소 변경으로 추가
6. 안정화 후 DB registry 전환 검토

## Representative Workflow와 연결 방식

### 연결 조건

`seed_candidates`는 아래 조건을 만족할 때 생성한다.

- `representative_poi_candidates.review_status = APPROVED`
- 대표 후보가 hard risk 없음
- expected POI와 existing seed 관계가 명확함
- promote strategy가 정해짐

### 연결 흐름

```text
representative_poi_candidates
  -> review approve
  -> enrichment audit
  -> image/overview approve
  -> representative promote dry-run
  -> seed_candidates 생성
  -> seed review
  -> seed dry-run
  -> QA
  -> manual promote
  -> rollback snapshot
```

### Payload 연결 예

```json
{
  "source_payload": {
    "representative_candidate_id": 6,
    "representative_image_candidate_id": null,
    "representative_overview_candidate_id": 116,
    "existing_seed": {
      "name": "경포호수광장",
      "source": "tourism_belt.py"
    },
    "expected_poi": {
      "name": "경포대",
      "region_1": "강원",
      "region_2": "강릉"
    }
  }
}
```

## 위험 요소

- seed 변경은 추천 결과를 크게 바꿀 수 있다.
- 대표 POI가 추가되면 anchor/slot/동선 결과가 예상보다 강하게 편향될 수 있다.
- 기존 seed 제거는 지역 coverage 저하를 만들 수 있다.
- DB 기반 seed registry로 바로 전환하면 추천 엔진 복잡도가 증가한다.
- 파일 기반 seed와 DB 후보가 동시에 존재하면 중복/우선순위 정책이 필요하다.
- representative candidate가 places에 아직 없으면 seed promote도 실제로는 불가능하다.
- seed governance를 우회해 `tourism_belt.py`를 직접 수정하면 rollback 추적이 깨진다.

## 다음 작업 제안

1. `migration_011_seed_candidates.sql` 초안을 작성한다.
2. `batch/place_enrichment/create_seed_candidate.py` dry-run CLI를 설계한다.
3. 경포대 기준 `COEXIST_WITH_EXISTING` seed candidate dry-run을 구현한다.
4. seed candidate list/review CLI를 representative review workflow와 같은 방식으로 만든다.
5. seed promote는 구현하지 말고 dry-run/QA/report만 먼저 만든다.
6. 장기적으로 baseline `tourism_belt.py` + DB overlay 구조를 검토한다.
