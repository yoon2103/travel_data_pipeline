# Representative POI Promote Dry-run Report

생성일: 2026-05-08

## 작업 범위

- `representative_poi_candidates`의 `APPROVED` 후보를 실제 운영 반영한다고 가정한 dry-run 분석 CLI를 추가했다.
- `places`, `tourism_belt.py`, `course_builder.py`는 수정하지 않았다.
- 실제 promote, seed 변경, places insert/update는 수행하지 않았다.

## 추가 파일

- `batch/place_enrichment/representative_promote_dry_run.py`

## CLI 사용법

```bash
python -m batch.place_enrichment.representative_promote_dry_run
python -m batch.place_enrichment.representative_promote_dry_run --expected-name 경포대
python -m batch.place_enrichment.representative_promote_dry_run --source-type KAKAO --limit 5 --json
python -m batch.place_enrichment.representative_promote_dry_run --expected-name 불국사
python -m batch.place_enrichment.representative_promote_dry_run --expected-name 성산일출봉
python -m batch.place_enrichment.representative_promote_dry_run --expected-name 전주한옥마을
```

지원 옵션:

- `--expected-name`
- `--source-type`
- `--approved-only`
- `--json`
- `--limit`

기본 동작은 `APPROVED` 후보만 대상으로 하는 dry-run이다.

## Dry-run 결과

전체 approved 후보 기준:

```json
{
  "mode": "dry-run",
  "db_write": false,
  "places_changed": false,
  "seed_changed": false,
  "engine_changed": false,
  "approved_only": true,
  "candidate_count": 1,
  "readiness_counts": {
    "READY_FOR_MANUAL_PROMOTE": 1
  }
}
```

### 경포대

- 후보 상태: `APPROVED`
- candidate_id: `6`
- source_type: `KAKAO`
- source_name: `경포대`
- source_place_id: `10158575`
- confidence_score: `93.00`
- category: `여행 > 관광,명소 > 문화유적`
- address: `강원특별자치도 강릉시 경포로 365`
- latitude / longitude: `37.7950741626953`, `128.896636344738`
- current_seed_exists: `false`
- current_seed_name: `경포호수광장`
- current_seed_is_weak_substitute: `true`
- matched_place_id: `null`
- DB exact match: `false`
- representative risks: `IMAGE_MISSING`, `OVERVIEW_MISSING`
- expected_action: `manual place staging then seed review`
- promote_readiness: `READY_FOR_MANUAL_PROMOTE`

추천 영향 예측:

- 현재 seed인 `경포호수광장`은 유지된다.
- `경포대` 후보를 별도 manual place staging 대상으로 준비하면, 기존 약한 대체 seed와 실제 기대 랜드마크를 운영자가 비교 검수할 수 있다.
- 대표성 개선 가능성은 높지만, 현재 DB에 exact match가 없으므로 자동 promote가 아니라 manual promote 전용 검수 단계가 필요하다.

### 불국사

- approved 후보 수: `0`
- dry-run 대상 없음
- 현재 상태: `PENDING_REVIEW` 후보와 `SKIPPED` 후보만 존재
- 다음 action: 대표 후보를 수동 검수 후 approve해야 promote dry-run 판단 가능

### 성산일출봉

- approved 후보 수: `0`
- dry-run 대상 없음
- 현재 상태: `PENDING_REVIEW` 후보만 존재
- 다음 action: 대표 후보를 수동 검수 후 approve해야 promote dry-run 판단 가능

### 전주한옥마을

- approved 후보 수: `0`
- dry-run 대상 없음
- 현재 상태: `PENDING_REVIEW` 후보만 존재
- 다음 action: 대표 후보를 수동 검수 후 approve해야 promote dry-run 판단 가능

## Promote Readiness 결과

| expected_poi_name | approved 후보 | readiness | 이유 |
|---|---:|---|---|
| 경포대 | 1 | READY_FOR_MANUAL_PROMOTE | DB exact match는 없지만 높은 confidence의 대표 POI 후보이며 hard risk 없음 |
| 불국사 | 0 | 대상 없음 | 아직 APPROVED 후보 없음 |
| 성산일출봉 | 0 | 대상 없음 | 아직 APPROVED 후보 없음 |
| 전주한옥마을 | 0 | 대상 없음 | 아직 APPROVED 후보 없음 |

## 대표성 개선 예상

- 경포대는 현재 강릉 대표 seed가 `경포호수광장`으로 잡혀 있는 문제를 보완할 수 있는 후보다.
- 다만 `places`에 `경포대` exact match가 없으므로 바로 seed 교체가 아니라, 신규 대표 POI 후보를 운영 검수하고 별도 promote 절차를 거쳐야 한다.
- 불국사, 성산일출봉, 전주한옥마을은 후보 수집은 되어 있으나 아직 승인되지 않았으므로 현재 단계에서는 영향 예측 대상에서 제외했다.

## 위험 요소

- `경포대` 후보는 이미지와 overview가 없어, 대표 POI 자체의 존재성은 좋지만 사용자 체감 품질 보강은 추가로 필요하다.
- DB exact match가 없기 때문에 자동 seed 교체나 자동 places 생성으로 이어지면 안 된다.
- `경포호수광장`은 아직 유지되어야 하며, 기존 seed 제거는 별도 seed review 이후에만 검토해야 한다.
- 나머지 대표 POI는 승인 전이므로 dry-run 결과가 없다는 점을 운영자가 오해하지 않도록 list/review 단계를 먼저 수행해야 한다.

## 검증 결과

### py_compile

```text
python -m py_compile .\batch\place_enrichment\representative_promote_dry_run.py
PASS
```

### CLI 실행

```text
python -m batch.place_enrichment.representative_promote_dry_run --json
PASS

python -m batch.place_enrichment.representative_promote_dry_run --expected-name 경포대
PASS

python -m batch.place_enrichment.representative_promote_dry_run --expected-name 불국사
PASS, candidate_count=0

python -m batch.place_enrichment.representative_promote_dry_run --expected-name 성산일출봉
PASS, candidate_count=0

python -m batch.place_enrichment.representative_promote_dry_run --expected-name 전주한옥마을
PASS, candidate_count=0
```

### Review 상태 확인

```text
경포대: APPROVED 1, PENDING_REVIEW 13, REJECTED 1
불국사: PENDING_REVIEW 14, SKIPPED 1
성산일출봉: PENDING_REVIEW 12
전주한옥마을: PENDING_REVIEW 15
```

## places/seed 변경 없음 확인

- `places` row count: `26371`
- CLI 결과: `places_changed=false`
- CLI 결과: `seed_changed=false`
- CLI 결과: `engine_changed=false`
- `tourism_belt.py` diff: 없음
- `course_builder.py` diff: 없음

## 다음 작업 제안

1. 불국사, 성산일출봉, 전주한옥마을 후보를 `list_representative_candidates.py`로 확인한 뒤 대표 후보만 approve한다.
2. approve 이후 `representative_promote_dry_run.py`를 다시 실행해 readiness를 비교한다.
3. `READY_FOR_MANUAL_PROMOTE` 후보를 실제 places 반영이 아니라 별도 manual promote 설계 문서로 넘긴다.
4. 이미지/overview가 부족한 대표 POI는 TourAPI detail 또는 manual curator 기반 보강 후보로 분리한다.
