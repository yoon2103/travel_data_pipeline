# Representative POI Promote Policy

생성일: 2026-05-08

## 목적

대표 POI 후보를 실제 운영 데이터에 반영하기 위한 promote 정책을 정의한다.

현재까지 완료된 구조:

- representative candidate staging
- representative review workflow
- representative promote dry-run
- representative enrichment audit
- manual representative enrichment staging

아직 하지 않는 것:

- `places` insert/update
- `tourism_belt.py` seed 변경
- 추천 엔진 수정
- actual promote

## Promote 정책

### 기본 원칙

- 자동 promote는 금지한다.
- promote는 항상 dry-run, review, snapshot, manual approve 이후에만 수행한다.
- 기존 seed는 즉시 제거하지 않는다.
- 대표 POI 후보와 기존 seed는 일정 기간 coexist 가능해야 한다.
- `places` overwrite는 최소화한다.
- image/overview는 NULL overwrite 금지 원칙을 유지한다.
- 추천 엔진 로직으로 데이터 품질 문제를 숨기지 않는다.

### Promote 최소 조건

대표 POI를 운영 반영 대상으로 올리려면 아래 조건을 모두 만족해야 한다.

| 조건 | 기준 |
|---|---|
| 대표 후보 | `representative_poi_candidates.review_status = APPROVED` |
| 후보 confidence | `confidence_score >= 85` 권장 |
| promote status | `PENDING` 또는 `READY` |
| hard risk | 없어야 함 |
| 좌표 | latitude / longitude 존재 |
| 지역 | expected region과 source region 일치 |
| 카테고리 | 관광지/문화/명소 계열이어야 함 |
| 이미지 | `APPROVED` 된 `REPRESENTATIVE_IMAGE` 후보 필요 |
| 설명 | `APPROVED` 된 `REPRESENTATIVE_OVERVIEW` 후보 필요 |
| review checkpoint | 운영자 최종 승인 필요 |
| dry-run | 영향 분석 PASS 필요 |
| rollback snapshot | promote 전 snapshot 필수 |

### Ready 상태 판정

| 상태 | 의미 |
|---|---|
| `NOT_READY` | 필수 조건 미충족. promote 금지 |
| `READY_FOR_MANUAL_PROMOTE` | 필수 조건 충족. 수동 promote 가능 |
| `READY_WITH_WARNING` | 대표성은 충분하지만 image/overview/source conflict 등 경고 존재. 추가 검수 필요 |
| `PROMOTED` | 운영 반영 완료 |
| `ROLLED_BACK` | promote 후 rollback 완료 |

### Risk Flag 기준

아래 risk가 있으면 promote 금지 또는 review 강제다.

| risk flag | 처리 |
|---|---|
| `INTERNAL_FACILITY_RISK` | 자동 promote 금지, 수동 검수 필수 |
| `SUB_FACILITY_RISK` | 자동 promote 금지, 수동 검수 필수 |
| `LODGING_RISK` | promote 금지 |
| `PARKING_LOT_RISK` | promote 금지 |
| `CATEGORY_RISK` | promote 금지 |
| `REGION_UNCLEAR` | promote 금지 |
| `IMAGE_MISSING` | promote 금지 |
| `OVERVIEW_MISSING` | promote 금지 |
| `VILLAGE_SCOPE_REVIEW` | 자동 promote 금지, 대표 범위 검수 필수 |
| `PORT_SCOPE_REVIEW` | 자동 promote 금지, 대표 범위 검수 필수 |

## Promote 대상 정의

### 1. places 신규 insert

사용 조건:

- expected 대표 POI가 `places`에 exact match로 없음
- 대표 후보가 `APPROVED`
- image와 overview enrichment가 모두 `APPROVED`
- hard risk 없음
- 운영자가 신규 POI 등록을 명시 승인

반영 방식:

- 신규 `places` row를 생성하는 별도 promote workflow 필요
- `source_type`, `source_place_id`, `source_payload`는 audit용 로그에 남김
- 첫 반영 후 바로 seed 교체하지 않고 seed candidate로만 올림

금지:

- 후보가 없다는 이유로 주변 광장/주차장/호텔/상점을 신규 대표 POI로 생성 금지
- image/overview 없는 상태에서 신규 insert 금지

### 2. existing place update

사용 조건:

- `places`에 동일 대표 POI exact match 존재
- 기존 row가 inactive가 아님
- 좌표/카테고리/지역 충돌 없음
- image/overview만 보강하거나 대표성 메타데이터를 보강하는 경우

반영 방식:

- NULL 또는 빈 값만 보강하는 것을 우선한다.
- 기존 정상 image/overview는 품질 비교 없이 overwrite 금지
- 기존 이미지가 GOOD 이상이면 교체 금지

### 3. seed candidate only

사용 조건:

- 대표 POI 후보는 승인되었지만 places 반영 전
- 기존 seed와 대표 후보를 비교 검수해야 하는 경우

반영 방식:

- `tourism_belt.py`를 바로 수정하지 않는다.
- 별도 seed review 목록 또는 문서에 올린다.
- QA에서 기존 seed와 신규 대표 후보의 예상 코스 영향을 비교한다.

### 4. representative alias only

사용 조건:

- 같은 장소의 명칭 차이만 존재
- 예: `강릉 경포대`와 `경포대`
- 실제 row 생성보다 alias 매핑이 안전한 경우

반영 방식:

- alias table 또는 metadata 설계 후 반영한다.
- 추천 엔진 직접 수정 없이 candidate matching 품질 개선에 먼저 활용한다.

## 기존 Seed 보호 전략

### 보호 원칙

- 기존 seed는 promote와 동시에 삭제하지 않는다.
- 신규 대표 POI는 먼저 coexist 상태로 둔다.
- 최소 1회 이상 QA와 smoke test를 통과해야 seed 교체를 검토한다.
- 기존 seed가 코스 품질을 해치지 않으면 즉시 제거하지 않는다.

### 경포호수광장 사례

현재:

- 기대 대표 POI: `경포대`
- 현재 약한 대체 seed: `경포호수광장`
- `경포대`는 approved representative candidate 존재
- image/overview는 manual enrichment 후보가 staging 되었지만 아직 review 전

정책:

- `경포호수광장` 즉시 제거 금지
- `경포대`를 places 후보로 먼저 수동 promote 검토
- 이후 seed QA에서 `경포대`와 `경포호수광장` coexist 또는 교체 여부 판단
- 경포호수광장은 주변/하위 POI로 남길 수 있음

## Rollback 전략

### Snapshot 대상

promote 전 반드시 아래를 snapshot으로 저장한다.

- 변경 대상 `places` row 전체
- 신규 insert 예정 candidate payload
- seed 변경 예정 diff
- image/overview 변경 전 값
- promote 실행자 / 실행 시각 / 사유
- dry-run report id 또는 파일 경로

### Rollback 기준

다음 상황이면 rollback 대상이다.

- 대표 POI 오매칭 확인
- 잘못된 이미지 연결
- 저작권/출처 문제
- 사용자 코스 QA 품질 저하
- 기존 seed 제거 후 대표 coverage 악화
- 지역/좌표 오류 발견
- 운영자가 reject 또는 rollback 요청

### Rollback 방식

| promote 유형 | rollback 방식 |
|---|---|
| 신규 places insert | row inactive 처리 또는 삭제 금지 후 `is_active=false` |
| existing place update | snapshot 값으로 복원 |
| seed 변경 | 이전 seed 목록으로 복원 |
| image/overview 변경 | 이전 image/overview로 복원 |
| alias 추가 | alias 비활성화 |

운영 삭제는 원칙적으로 금지하고, 비활성화와 rollback log를 우선한다.

## Promote Payload 예시

```json
{
  "promote_type": "NEW_PLACE_AND_SEED_CANDIDATE",
  "expected_poi_name": "경포대",
  "representative_candidate_id": 6,
  "representative_image_candidate_id": 115,
  "representative_overview_candidate_id": 116,
  "source_type": "KAKAO",
  "source_place_id": "10158575",
  "confidence_score": 93.0,
  "risk_flags": [],
  "current_seed": {
    "name": "경포호수광장",
    "action": "KEEP",
    "reason": "existing seed protection; no immediate removal"
  },
  "proposed_place": {
    "name": "경포대",
    "region_1": "강원",
    "region_2": "강릉",
    "latitude": 37.7950741626953,
    "longitude": 128.896636344738,
    "category": "문화유적",
    "image_url": "manual approved image url",
    "overview": "manual approved overview text"
  },
  "review": {
    "required": true,
    "reviewer_id": "ops_001",
    "approved_at": null,
    "checkpoints": [
      "representative candidate approved",
      "image approved",
      "overview approved",
      "dry-run passed",
      "rollback snapshot created"
    ]
  },
  "dry_run": {
    "status": "PASS",
    "places_write": false,
    "seed_write": false,
    "qa_required": true
  },
  "rollback": {
    "snapshot_required": true,
    "rollback_supported": true
  }
}
```

## Representative Image / Overview 반영 정책

### Image

대표 이미지 반영 조건:

- `REPRESENTATIVE_IMAGE` 후보가 `APPROVED`
- 출처와 license note 검수 완료
- landmark exterior 또는 대표 전경 식별 가능
- 주차장/호텔/상점/내부시설 이미지가 아님
- 기존 이미지가 있으면 품질 비교에서 명확히 우위

반영 금지:

- 이미지 없음
- 광고/워터마크/상업시설 중심
- 내부시설만 보여주는 이미지
- 위치나 랜드마크 식별 불가
- 출처 불명확

### Overview

대표 overview 반영 조건:

- `REPRESENTATIVE_OVERVIEW` 후보가 `APPROVED`
- 한국어 자연문
- 최소 20자 이상
- 과장 표현, 홍보 문구, 저작권 복붙 없음
- 위치/대표성/방문 맥락을 간단히 설명

반영 금지:

- 공백 또는 짧은 문장
- `대표 관광지입니다`류의 무의미한 문장
- 출처 불명확한 장문 복사
- 사실 검증이 필요한 역사 설명을 검수 없이 사용

## Promote Dry-run 강화안

현재 dry-run에 추가해야 할 항목:

1. approved representative candidate 확인
2. approved representative image 확인
3. approved representative overview 확인
4. 기존 places exact match 여부
5. 기존 seed와 conflict 여부
6. 신규 insert vs existing update vs seed candidate only 분기
7. rollback snapshot 가능 여부
8. QA 영향 예측
9. image/overview gap 해소 여부
10. absolute block risk 존재 여부

출력 예:

```json
{
  "expected_poi_name": "경포대",
  "readiness": "READY_WITH_WARNING",
  "promote_type": "NEW_PLACE_AND_SEED_CANDIDATE",
  "blocks": [],
  "warnings": [
    "existing weak seed will be preserved",
    "new places insert requires manual approval"
  ],
  "required_checkpoints": [
    "approved image",
    "approved overview",
    "snapshot",
    "QA",
    "smoke test"
  ]
}
```

## 운영 Review Checkpoint

promote 전 체크리스트:

1. 대표 후보가 기대 POI와 동일 장소인가?
2. 이름만 같은 다른 지역/다른 시설은 아닌가?
3. 좌표가 대표 지점으로 적절한가?
4. 이미지가 대표 랜드마크를 식별 가능한가?
5. overview가 자연스럽고 사실 오류가 없는가?
6. 기존 seed와 coexist가 가능한가?
7. 기존 seed 제거가 필요한가, 아니면 보조 POI로 유지할 것인가?
8. QA에서 동선/역할/장소 수가 악화되지 않는가?
9. rollback snapshot이 존재하는가?
10. 운영자가 promote 사유를 남겼는가?

## 절대 자동 Promote 금지 조건

아래 중 하나라도 해당하면 자동 promote 금지다.

- `INTERNAL_FACILITY_RISK`
- `SUB_FACILITY_RISK`
- `LODGING_RISK`
- `PARKING_LOT_RISK`
- `CATEGORY_RISK`
- `REGION_UNCLEAR`
- `IMAGE_MISSING`
- `OVERVIEW_MISSING`
- 승인된 대표 후보 없음
- 승인된 대표 이미지 없음
- 승인된 대표 overview 없음
- 좌표 없음
- 이름 유사도만 높고 주소/지역 근거 부족
- 기존 seed 제거가 동반되는 변경
- 신규 places insert가 필요한 변경
- 저작권/출처 확인 안 된 이미지
- 운영 QA 미실행
- rollback snapshot 없음

## 대표 POI 반영 시나리오

### 경포대 현재 상태

- approved representative candidate: 있음
- candidate_id: `6`
- source: `KAKAO`
- confidence_score: `93.00`
- current weak seed: `경포호수광장`
- places exact match: 없음
- manual image candidate: 있음, `candidate_id=115`, `PENDING_REVIEW`
- manual overview candidate: 있음, `candidate_id=116`, `PENDING_REVIEW`
- promote readiness: 아직 실제 promote 불가

### 경포대 promote 전 필요 작업

1. candidate 115 이미지 검수
2. candidate 116 overview 검수
3. 둘 다 approve
4. promote dry-run 재실행
5. 신규 places insert 후보 payload 생성
6. seed candidate only 상태로 QA
7. 기존 `경포호수광장` seed는 유지
8. QA 통과 후 별도 seed review에서 coexist 또는 교체 판단

### 경포대 promote 후 예상

안전한 1차 promote:

- `경포대`를 신규 representative place 후보로 수동 반영
- `경포호수광장`은 삭제하지 않음
- seed는 바로 교체하지 않고 candidate로만 등록
- QA에서 강릉 대표 코스에 `경포대`가 포함 가능한지 확인

예상 효과:

- 대표 명소 coverage 개선
- 경포호수광장 같은 주변/하위 POI가 대표 명소를 대체하는 문제 완화
- 사용자 기대와 실제 코스의 간극 감소

### Rollback 가능 여부

- 신규 places insert라면 `is_active=false`로 rollback 가능
- image/overview는 snapshot 기반 복원 가능
- seed 변경을 하지 않는 1차 promote라면 seed rollback 부담 없음
- seed 교체는 별도 단계에서만 수행해야 rollback 리스크가 작다

## 위험 요소

- 대표 POI 후보가 places에 없을 때 신규 insert가 필요하므로 운영 부담이 크다.
- 이미지/overview 후보가 승인되어도 저작권/사실 검증이 필요하다.
- 기존 seed를 제거하면 기존 코스 동선이 변할 수 있다.
- 대표 POI가 너무 강하게 우선되면 지역 다양성이 줄어들 수 있다.
- `tourism_belt.py` 직접 수정은 배포/rollback 관리가 어렵다.
- 대표 POI와 하위 POI가 공존할 때 중복 노출 방지 정책이 필요하다.

## 다음 작업 제안

1. manual enrichment 후보 115, 116을 review workflow로 approve/reject한다.
2. promote dry-run을 image/overview approved 여부까지 반영하도록 강화한다.
3. 실제 write 전용 promote CLI는 별도 단계로 만들고 기본값을 `--dry-run`으로 둔다.
4. `representative_poi_promotions` 또는 별도 promotion log/snapshot 테이블 설계를 추가한다.
5. seed 변경은 `tourism_belt.py` 직접 수정이 아니라 seed candidate staging 구조로 분리한다.
