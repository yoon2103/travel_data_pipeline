# Seed Overlay QA Simulation Report

생성일: 2026-05-08

## 작업 범위

- baseline `tourism_belt.py` seed와 `seed_candidates` overlay 후보가 coexist할 때의 추천 품질 영향을 dry-run으로 분석하는 CLI를 구현했다.
- actual overlay 적용, 추천 엔진 변경, `tourism_belt.py` 수정, `places` write는 수행하지 않았다.

## 추가 파일

- `batch/place_enrichment/simulate_seed_overlay_qa.py`
- `docs/SEED_OVERLAY_QA_SIMULATION_REPORT.md`

## CLI 사용법

```bash
python -m batch.place_enrichment.simulate_seed_overlay_qa \
  --expected-name 경포대 \
  --strategy COEXIST_WITH_EXISTING \
  --region 강원
```

JSON 출력:

```bash
python -m batch.place_enrichment.simulate_seed_overlay_qa \
  --expected-name 경포대 \
  --strategy COEXIST_WITH_EXISTING \
  --region 강원 \
  --json
```

전략 비교:

```bash
python -m batch.place_enrichment.simulate_seed_overlay_qa \
  --expected-name 경포대 \
  --strategy PRIORITY_OVERRIDE \
  --region 강원 \
  --json
```

지원 옵션:

- `--expected-name`
- `--strategy`
- `--region`
- `--json`
- `--limit`

## 경포대 Simulation 결과

입력:

```text
expected_name: 경포대
baseline: tourism_belt.py
baseline seed: 경포호수광장
overlay source: seed_candidates
overlay candidate: 경포대
strategy: COEXIST_WITH_EXISTING
```

출력 요약:

```json
{
  "mode": "dry-run/simulation",
  "db_write": false,
  "places_changed": false,
  "seed_changed": false,
  "engine_changed": false,
  "baseline_source": "tourism_belt.py",
  "overlay_source": "seed_candidates",
  "strategy": "COEXIST_WITH_EXISTING",
  "baseline_seed_count_loaded": 23,
  "candidate_count": 1,
  "risk_counts": {
    "MEDIUM": 1
  },
  "readiness_counts": {
    "NOT_READY": 1
  }
}
```

경포대 상세:

| 항목 | 결과 |
|---|---|
| baseline seed | 경포호수광장 |
| baseline place_id | 11269 |
| overlay candidate | 경포대 |
| seed_candidate_id | 1 |
| representative_candidate_id | 6 |
| representative_review_status | APPROVED |
| nearby_seed_distance_km | 1.172 |
| duplicate_nearby_risk | MEDIUM |
| overlay_risk | MEDIUM |
| risk_flags | IMAGE_MISSING |
| readiness | NOT_READY |
| recommendation | 대표 이미지 승인 전까지 overlay는 staging only 유지 |

## Overlay QA Payload 예시

```json
{
  "expected_poi_name": "경포대",
  "strategy": "COEXIST_WITH_EXISTING",
  "baseline_seed": {
    "name": "경포호수광장",
    "place": {
      "place_id": 11269,
      "region_1": "강원",
      "latitude": 37.7977913781,
      "longitude": 128.9095224784,
      "visit_role": "spot",
      "category_id": 12
    },
    "tourism_belt_matches": [
      {
        "belt_key": "강릉",
        "name": "경포호수광장",
        "source": "tourism_belt.py"
      }
    ]
  },
  "overlay_candidate": {
    "seed_candidate_id": 1,
    "candidate_place_name": "경포대",
    "representative_candidate_id": 6,
    "representative_review_status": "APPROVED",
    "source_type": "KAKAO",
    "source_name": "경포대",
    "confidence_score": "93.00"
  },
  "nearby_seed_distance_km": 1.172,
  "duplicate_nearby_risk": "MEDIUM",
  "overlay_risk": "MEDIUM",
  "risk_flags": [
    "IMAGE_MISSING"
  ],
  "role_distribution_impact": {
    "baseline_role": "spot",
    "overlay_role_estimate": "culture",
    "spot_culture_bias_risk": "MEDIUM"
  },
  "expected_route_impact": {
    "place_count_change": "NONE_EXPECTED_WITHOUT_ENGINE_INTEGRATION",
    "place_count_change_if_applied": "LOW",
    "slot_change_risk": "MEDIUM",
    "travel_time_impact": "LOW_TO_MEDIUM",
    "regional_bias_risk": "MEDIUM",
    "same_area_density_risk": "MEDIUM"
  },
  "qa_warnings": [
    "approved representative image is missing",
    "baseline and overlay seed are nearby: duplicate risk MEDIUM",
    "spot/culture seed density may increase"
  ],
  "readiness": "NOT_READY"
}
```

## Duplicate / 권역 위험 분석

경포대와 경포호수광장은 약 `1.172km` 떨어져 있다.

판단:

- 같은 경포 권역 내 근접 후보로 볼 수 있다.
- `COEXIST_WITH_EXISTING`에서는 duplicate nearby risk가 `MEDIUM`이다.
- baseline role은 `spot`, overlay role estimate는 `culture`로 spot/culture 계열 밀도가 증가할 수 있다.

위험:

- 경포 권역 장소가 코스에 과도하게 몰릴 가능성
- 경포대와 경포호수광장이 같은 코스에 함께 노출될 가능성
- spot/culture slot이 meal/cafe를 밀어낼 가능성

완화:

- actual overlay 전 대표 이미지 승인 필요
- overlay QA에서 같은 권역 과밀 여부 확인
- `PRIORITY_OVERRIDE`는 아직 금지

## 추천 품질 영향 예상

### 긍정 영향

- 경포대는 경포호수광장보다 기대 대표 POI에 더 부합한다.
- 대표 명소 누락 문제를 seed governance 레이어에서 해결할 수 있다.
- 기존 seed를 제거하지 않고 coexist로 검증하면 rollback 부담이 낮다.

### 부정 / 주의 영향

- 현재 `IMAGE_MISSING`이 남아 있어 actual 적용 불가다.
- 가까운 seed가 중복되어 권역 편향이 커질 수 있다.
- 실제 코스 생성은 수행하지 않았으므로 place_count/이동시간 변화는 예측치다.

### Strategy 비교

| strategy | overlay_risk | readiness | 판단 |
|---|---|---|---|
| COEXIST_WITH_EXISTING | MEDIUM | NOT_READY | image gap 해소 후 read-only QA 가능 |
| PRIORITY_OVERRIDE | HIGH | NOT_READY | 현재 금지. 추천 변화가 클 수 있음 |

## 테스트 결과

```text
python -m py_compile .\batch\place_enrichment\simulate_seed_overlay_qa.py
PASS
```

경포대:

```text
python -m batch.place_enrichment.simulate_seed_overlay_qa --expected-name 경포대 --strategy COEXIST_WITH_EXISTING --region 강원 --json
PASS
```

invalid strategy:

```text
python -m batch.place_enrichment.simulate_seed_overlay_qa --expected-name 경포대 --strategy BAD_STRATEGY --region 강원 --json
status: ERROR
reason: invalid strategy
PASS
```

missing overlay candidate:

```text
python -m batch.place_enrichment.simulate_seed_overlay_qa --expected-name 불국사 --strategy COEXIST_WITH_EXISTING --region 경북 --json
status: ERROR
reason: overlay seed candidate does not exist for the requested filters
PASS
```

missing approved representative candidate:

- 현재 seed overlay candidate는 approved representative candidate 기반으로만 생성되어 있다.
- overlay candidate가 없는 expected name은 simulation 진입 전 `missing overlay candidate`로 차단된다.
- 추후 seed_candidates에 잘못된 representative reference가 들어오는 경우 `representative_review_status != APPROVED`이면 readiness가 `BLOCKED`로 평가된다.

## places / seed 변경 없음 확인

- `places` row count: `26371`
- `tourism_belt.py` diff: 없음
- `course_builder.py` diff: 없음
- `api_server.py` diff: 없음
- actual overlay 적용 없음
- actual build_course 호출 없음
- places insert/update 없음
- seed write 없음

## 위험 요소

- 이 simulation은 실제 코스 생성 없이 seed 간 거리/역할/권역 위험을 추정한다.
- 실제 place_count, 이동시간, slot 변화는 엔진 비교 QA 없이는 확정할 수 없다.
- 경포대는 image gap이 남아 있어 actual overlay 금지 상태다.
- `PRIORITY_OVERRIDE`는 현재 HIGH risk로만 분석해야 하며 적용하면 안 된다.
- seed overlay가 엔진에 연결되는 순간 추천 결과가 바뀌므로 별도 feature flag와 rollback이 필요하다.

## 다음 작업 제안

1. 경포대 대표 이미지 후보를 실제 검증 가능한 URL로 다시 등록하고 approve한다.
2. image gap 해소 후 seed overlay simulation을 재실행한다.
3. `simulate_seed_overlay_qa.py`에 baseline vs overlay 후보 pool 비교 기능을 추가한다.
4. actual `build_course`를 호출하지 않는 범위에서 role/권역 분산 분석을 더 정교화한다.
5. 실제 엔진 overlay는 feature flag, QA, rollback snapshot 이후 별도 작업으로 분리한다.
