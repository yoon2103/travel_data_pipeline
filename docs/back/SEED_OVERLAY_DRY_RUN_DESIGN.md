# Seed Overlay Dry-run Design

생성일: 2026-05-08

## 목적

`tourism_belt.py`를 baseline source of truth로 유지하면서, approved seed overlay candidate를 가정한 dry-run 구조와 영향 분석 방법을 설계한다.

이번 문서는 설계와 분석 전용이다.

- `tourism_belt.py` 수정 없음
- 추천 엔진 actual 변경 없음
- overlay actual 적용 없음
- `places` write 없음
- dry-run only

## Overlay 구조

### 기본 개념

```text
baseline seeds
  = tourism_belt.py

overlay seeds
  = approved seed_candidates

simulation seeds
  = baseline seeds + overlay seeds
```

운영 원칙:

- baseline은 항상 유지 가능한 fallback이어야 한다.
- overlay는 승인된 후보만 dry-run 대상이 된다.
- overlay가 있다고 baseline seed를 즉시 삭제하지 않는다.
- actual 추천 엔진에 반영하기 전 QA와 rollback 설계가 필요하다.

### Overlay 입력

overlay seed candidate는 다음 조건을 만족해야 한다.

- `seed_candidates.review_status = APPROVED`
- `seed_candidates.seed_status IN ('APPROVED', 'COEXIST', 'READY_FOR_PROMOTE')`
- `representative_candidate_id`가 approved representative candidate를 가리킴
- image/overview gap 없음
- hard risk 없음
- dry-run QA 수행 가능

현재는 `seed_candidates` 테이블이 아직 미구현이므로, 경포대 시나리오는 설계 가정으로만 분석한다.

## Overlay 전략 비교

| 전략 | 설명 | 장점 | 단점 | 권장 상황 |
|---|---|---|---|---|
| `ADDITIVE` | baseline seed에 overlay seed를 단순 추가 | 가장 안전, 기존 seed 보호 | 후보 중복/편향 가능 | 초기 dry-run |
| `COEXIST` | 기존 seed와 overlay를 함께 유지하되 중복 위험을 표시 | 대표성 개선과 보호 균형 | 엔진이 둘 다 강하게 선택할 수 있음 | 경포대 1차 검증 |
| `PRIORITY_OVERRIDE` | overlay seed를 baseline보다 높은 우선순위로 취급 | 대표 POI 노출 가능성 증가 | 추천 편향/동선 변화 큼 | QA 통과 후 제한 적용 |
| `ALIAS_ONLY` | seed 추가 없이 명칭/매칭 보조만 사용 | 엔진 영향 최소 | 대표 POI 노출 개선 제한 | 동일 장소 명칭 차이 |

### 기본 권장값

초기 overlay dry-run 기본값:

- `COEXIST`
- 기존 seed 보호
- duplicate nearby risk 표시
- priority override 금지

## 경포대 Overlay Dry-run

### 현재 상태

| 항목 | 값 |
|---|---|
| region | 강원 / 강릉 |
| baseline seed | 경포호수광장 |
| overlay candidate | 경포대 |
| representative candidate | candidate_id 6, APPROVED |
| representative overview | candidate_id 116, APPROVED |
| representative image | 없음 |
| current readiness | READY_WITH_IMAGE_GAP |

### Coexist 시 예상

가정:

```text
baseline: 경포호수광장
overlay:  경포대
strategy: COEXIST
```

예상 효과:

- 경포대가 대표 후보로 dry-run pool에 포함된다.
- 경포호수광장은 즉시 제거되지 않는다.
- 경포 권역 대표성이 개선될 가능성이 있다.
- 사용자가 기대하는 대표 명소와 코스 결과의 간극이 줄어든다.

예상 위험:

- 두 장소가 가까우면 같은 권역 POI가 중복 후보로 잡힐 수 있다.
- 코스가 경포 권역에 과도하게 치우칠 수 있다.
- image gap이 남아 있어 실제 사용자 체감 품질은 아직 불완전하다.

판정:

- 현재 단계에서는 actual overlay 적용 금지
- image gap 해소 후 dry-run 가능
- 초기 전략은 `COEXIST`가 안전

### Priority Override 시 예상

가정:

```text
baseline: 경포호수광장
overlay:  경포대
strategy: PRIORITY_OVERRIDE
```

예상 효과:

- 경포대 선택 확률이 높아진다.
- 경포호수광장이 대표 역할을 대체하던 문제는 빠르게 완화될 수 있다.

예상 위험:

- 기존 seed 기반 코스 안정성이 흔들릴 수 있다.
- 경포대가 너무 강하게 anchor 역할을 하면서 다른 강릉 명소 다양성이 줄 수 있다.
- image/overview가 완전히 준비되지 않으면 UX 품질이 애매해진다.

판정:

- 지금은 금지
- image/overview 모두 approved
- QA 통과
- duplicate nearby risk 낮음
- rollback snapshot 존재

위 조건이 모두 충족된 뒤에만 검토 가능하다.

### Duplicate Nearby Risk

경포대와 경포호수광장은 같은 경포 권역에 있다.

확인해야 할 것:

- 두 seed 간 거리
- 같은 코스에 둘 다 들어갈 가능성
- 둘 중 하나가 anchor이고 다른 하나가 selected place로 들어가는지
- 주변 POI 후보가 경포 권역으로 과도하게 몰리는지
- spot/culture role 중복 여부

리스크:

- `MEDIUM`

완화:

- overlay dry-run에서 same-area duplicate warning 출력
- QA에서 같은 권역 반복 여부 확인
- priority override 전 coexist로 검증

### Representative Quality 변화

예상 개선:

- `경포호수광장`보다 `경포대`가 사용자 기대 대표 POI에 더 부합한다.
- 대표 명소 누락 문제를 데이터 레벨에서 해결할 수 있다.
- seed 교체가 아니라 overlay로 시작하면 rollback 부담이 작다.

남은 gap:

- 대표 이미지 미승인
- existing places exact match 없음
- actual places insert/promote 없음
- seed candidate table 미구현

## QA 영향 예측

### place_count 변화

가능성:

- FULL 지역에서는 큰 변화 없을 가능성이 높다.
- 경포대가 anchor/seed로 추가되면 후보 pool 구성은 더 안정될 수 있다.
- 다만 가까운 중복 POI가 늘면 같은 권역 후보가 과도하게 선택될 수 있다.

예상:

- `place_count`: 유지 또는 안정화
- `PASS/WEAK`: 대표성 기준 개선 가능

### slot 변화

가능성:

- 경포대가 culture/spot 성격으로 들어가면 spot/culture slot 점유 가능성이 있다.
- 기존 경포호수광장과 역할이 겹치면 spot 비중이 높아질 수 있다.

확인 항목:

- role 분포
- spot/culture 연속 여부
- meal/cafe slot이 밀려나는지

### 이동시간 변화

가능성:

- 경포대와 경포호수광장은 같은 권역이라 이동시간 증가는 크지 않을 수 있다.
- 그러나 overlay가 anchor 우선순위를 바꾸면 전체 동선 중심이 달라질 수 있다.

확인 항목:

- total_travel_minutes
- max segment minutes
- anchor to selected places 거리
- 경포 권역 외 장소 다양성

### 특정 지역 편향 증가 여부

위험:

- 경포 권역 POI가 강하게 묶이면 강릉 코스가 경포 주변으로만 치우칠 수 있다.

확인 항목:

- 선택된 장소의 좌표 분산
- 권역별 place count
- 같은 이름 prefix 반복
- 같은 관광 belt 중복

## Overlay Adapter 초안

actual 엔진 변경 없이 simulation을 위한 adapter 구조 초안이다.

```python
def load_baseline_seeds(region: str) -> list[dict]:
    # tourism_belt.py의 TOURISM_BELT에서 현재 seed 로드
    return TOURISM_BELT.get(region, [])


def load_overlay_candidates(region: str, *, strategy: str = "COEXIST") -> list[dict]:
    # seed_candidates에서 approved/dry-run 가능한 overlay 후보만 조회
    # 아직 actual 구현 금지
    return [
        {
            "name": "경포대",
            "region_1": "강원",
            "region_2": "강릉",
            "strategy": "COEXIST",
            "representative_candidate_id": 6,
            "risk_flags": [],
        }
    ]


def merge_seed_overlay(
    baseline: list[dict],
    overlay: list[dict],
    *,
    strategy: str,
) -> list[dict]:
    if strategy in {"ADDITIVE", "COEXIST"}:
        return baseline + overlay
    if strategy == "PRIORITY_OVERRIDE":
        return overlay + baseline
    if strategy == "ALIAS_ONLY":
        return baseline
    return baseline
```

### Simulation 전용 구조

추천 엔진 actual 변경 없이 가능한 방식:

1. `TOURISM_BELT`를 직접 수정하지 않는다.
2. dry-run script 내부에서 baseline seed를 복사한다.
3. overlay seed를 메모리에서만 합성한다.
4. 후보 pool/anchor 분석만 수행한다.
5. 실제 `course_builder.build_course` 호출에는 overlay를 주입하지 않는다.
6. 또는 별도 experimental branch에서 monkey patch로만 비교하고 결과를 저장하지 않는다.

안전한 1차 simulation:

- 코스 생성이 아니라 seed 후보 거리/권역/중복 분석
- 기존 seed와 overlay 후보의 거리 비교
- 후보 pool 포함 가능성 분석
- QA 영향 예측 리포트 생성

엔진 비교 simulation은 별도 작업으로 분리해야 한다.

## Overlay Rollback 개념

### Dry-run 단계

rollback 필요 없음.

- actual 적용 없음
- seed file 변경 없음
- DB write 없음

### Staging 단계

rollback:

- `seed_candidates.seed_status = ROLLED_BACK`
- review/dry-run payload 유지
- 실제 seed에는 영향 없음

### Actual overlay 적용 단계

rollback 대상:

- overlay registry row 비활성화
- seed overlay cache 제거
- previous overlay snapshot 복원
- QA 결과 rollback log 저장

원칙:

- baseline `tourism_belt.py`가 항상 fallback이므로 rollback 시 baseline으로 즉시 복귀 가능해야 한다.

## 절대 금지 조건

아래 조건이 있으면 overlay actual 적용 금지다.

- `IMAGE_MISSING`
- `OVERVIEW_MISSING`
- `REGION_UNCLEAR`
- `INTERNAL_FACILITY_RISK`
- `SUB_FACILITY_RISK`
- `LODGING_RISK`
- `PARKING_LOT_RISK`
- `CATEGORY_RISK`
- approved representative candidate 없음
- approved representative image 없음
- approved representative overview 없음
- QA 미실행
- rollback snapshot 없음
- existing places exact match 없음인 상태에서 places promote도 안 됨
- 기존 seed 제거가 포함됨
- `tourism_belt.py` 직접 수정 필요

경포대 현재 상태:

- image gap이 있으므로 actual overlay 적용 금지

## Hybrid Registry 평가

### 장점

- `tourism_belt.py` baseline 안정성을 유지한다.
- overlay는 DB/staging으로 검수와 rollback이 가능하다.
- 대표 POI 후보를 실제 엔진에 반영하기 전 충분히 dry-run 가능하다.
- 지역별로 점진 적용 가능하다.
- 기존 seed 보호 정책을 유지할 수 있다.

### 단점

- baseline과 overlay 중복/우선순위 정책이 필요하다.
- 추천 엔진이 overlay를 읽는 순간 엔진 변경이 발생한다.
- seed source of truth가 둘로 보일 수 있다.
- 운영자가 상태 모델을 이해해야 한다.
- QA 자동화가 없으면 promote 판단이 느려진다.

### 결론

단기:

- `tourism_belt.py` 유지
- overlay는 문서/dry-run/staging으로만 관리

중기:

- `seed_candidates` + dry-run QA 도구 구현
- overlay read adapter를 엔진 외부에서 simulation

장기:

- baseline + approved overlay를 합성하는 read-only adapter 도입
- 안정화 후 DB seed registry 전환 검토

## 향후 실제 Overlay Rollout 전략

### Phase 1: Design / Dry-run

- seed governance 문서 확정
- `seed_candidates` migration 초안
- 경포대 seed overlay dry-run 리포트

### Phase 2: Staging

- `seed_candidates` 테이블 적용
- 경포대 `COEXIST_WITH_EXISTING` 후보 생성
- seed candidate review workflow
- seed overlay dry-run CLI

### Phase 3: QA Simulation

- baseline vs overlay 후보 pool 비교
- 경포대/경포호수광장 중복 위험 분석
- 이동시간/role/권역 분포 영향 예측
- QA report 저장

### Phase 4: Read-only Overlay Adapter

- 엔진 내부 변경 없이 adapter에서 seed 합성 결과만 출력
- 실제 코스 생성에는 반영하지 않음
- 운영자가 overlay impact를 검토

### Phase 5: Controlled Engine Integration

- feature flag 기반
- 지역 단위 allowlist
- 기본 OFF
- QA 통과 지역만 ON
- 즉시 rollback 가능

## 위험 요소

- overlay가 실제 엔진에 들어가면 추천 결과가 변한다.
- 경포대/경포호수광장처럼 가까운 후보는 중복 노출 위험이 있다.
- image gap이 있는 대표 POI를 우선 노출하면 UX 품질이 낮아질 수 있다.
- seed overlay가 많아지면 특정 권역 편향이 생길 수 있다.
- baseline과 overlay의 source of truth 충돌 가능성이 있다.
- dry-run 결과를 actual 적용으로 오해하면 위험하다.

## 다음 작업 제안

1. `migration_011_seed_candidates.sql` 초안 작성
2. `create_seed_candidate.py --dry-run` 설계/구현
3. 경포대 `COEXIST_WITH_EXISTING` seed candidate dry-run 생성
4. seed candidate list/review CLI 구현
5. baseline seed와 overlay seed 거리/중복 분석 CLI 구현
6. actual overlay 적용은 image gap 해소와 QA 완료 전까지 금지
