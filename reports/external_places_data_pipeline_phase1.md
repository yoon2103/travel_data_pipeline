# external_places_data_pipeline_phase1

작성 시각: 2026-05-18 KST

## 목표

여행 코스 추천 서비스의 개선 방향을 추천 요청 시점의 알고리즘/실시간 API 호출이 아니라, Kakao/Naver Places 기반 장소 데이터 품질 보강 플랫폼으로 전환하기 위한 1차 구조 점검과 설계안을 정리했다.

이번 phase에서는 운영 DB write, deploy, 추천 엔진 수정, places 직접 수정은 수행하지 않았다.

## 결론

현재 운영 구조에는 이미 외부 장소 pipeline의 1차 골격이 존재한다.

존재 확인:

- `raw_external_places`
- `clean_external_places`
- `staging_places`
- `raw_places`
- `clean_places`
- `invalid_places`
- `data_update_runs`
- `data_update_step_logs`
- `data_update_qa_results`
- `batch/external/*`
- `batch/update_all.sh`
- `batch/update_all.ps1`
- `.env.example`의 Kakao/Naver 환경변수

다만 “장소 데이터 품질 보강 플랫폼”으로 운영하려면 현재 구조는 아직 부족하다.

핵심 부족점:

- 외부 API 품질 신호가 raw/clean 정규 컬럼으로 충분히 보존되지 않음
- `rating`, `review_count`, `image_url`, `business_status`, `opening_hours`, `last_verified_at`가 `raw_external_places`/`clean_external_places`에 정규 컬럼으로 없음
- `staging_external_places` 같은 외부 후보 전용 review/gating 테이블이 없음
- 현재 `promote_external_places.py`는 QA 통과 시 `places`에 직접 upsert할 수 있는 구조라, 운영 플랫폼 방향에서는 위험함
- 호스트에서 `batch/update_all.sh` 실행 시 `psycopg2`가 없어 실패함. 컨테이너/venv 기준 실행 경로를 표준화해야 함

## 현재 구조 분석

### DB / Migration

운영 DB read-only 확인 결과:

```json
{
  "missing_tables": [],
  "missing_places_cols": [],
  "missing_staging_cols": []
}
```

확인된 주요 테이블:

| Table | 역할 | 상태 |
|---|---|---|
| `data_update_runs` | batch run 단위 추적 | 존재 |
| `data_update_step_logs` | step별 로그 | 존재 |
| `data_sync_state` | source별 sync 상태 | 존재 |
| `raw_places` | TourAPI raw | 존재 |
| `clean_places` | TourAPI clean | 존재 |
| `invalid_places` | reject/invalid 기록 | 존재 |
| `staging_places` | QA/promote 전 staging | 존재 |
| `data_update_qa_results` | QA 결과 저장 | 존재 |
| `raw_external_places` | Kakao/Naver raw | 존재 |
| `clean_external_places` | Kakao/Naver clean | 존재 |

`places` 주요 외부/품질 컬럼도 존재한다.

- `naver_place_id`
- `kakao_place_id`
- `opening_hours`
- `rating`
- `review_count`
- `source_confidence`
- `first_image_url`
- `first_image_thumb_url`
- `is_active`

### migration_008_external_places_pipeline.sql

현재 external pipeline migration은 아래 구조다.

```text
raw_external_places
  -> clean_external_places
  -> staging_places(source='external')
  -> QA
  -> places promote
```

장점:

- 외부 API를 추천 요청 시점에 호출하지 않음
- run_id 기반으로 raw/clean/staging 추적 가능
- `data_update_runs`와 연결되어 batch 단위 governance 가능
- `staging_places`에 먼저 올린 뒤 QA 후 promote 가능

한계:

- `raw_external_places`는 source/name/좌표/category/address/phone/url/raw_payload 중심
- `clean_external_places`는 role/duplicate_key 정도만 보존
- 평점/리뷰수/이미지/운영상태/마지막 검증시각이 정규 컬럼으로 빠져 있음
- `staging_places`는 기존 TourAPI staging과 외부 staging이 섞임
- review/approve/reject 상태를 표현하는 외부 후보 전용 테이블이 없음

## Batch 구조 분석

### batch/update_all.sh

현재 Linux entrypoint는 안전 기본값을 갖고 있다.

- 기본 mode: `dry-run`
- `--write`를 명시해야 DB write 수행
- `.env` 존재 확인
- required migration/table/column 존재 확인
- baseline QA 실행 또는 baseline JSON 사용
- external collect/clean/enrich/staging
- QA 결과에서 FAIL 증가 시 promote 차단
- QA 통과 후 `promote_external_places` 실행
- 최종 API smoke 실행

중요한 문제:

호스트에서 직접 실행하면 `psycopg2`가 없어 DB check에서 실패했다.

```text
ModuleNotFoundError: No module named 'psycopg2'
```

운영에서는 다음 중 하나로 표준화해야 한다.

- `PYTHON_BIN`을 venv Python으로 지정
- backend container 내부에서 batch 실행
- batch 전용 container/job image 구성

### batch/update_all.ps1

Windows wrapper는 안전하게 제한되어 있다.

- dry-run collection 가능
- write mode는 의도적으로 미구현
- production writes는 EC2/Linux wrapper를 사용하도록 제한

이 방향은 유지하는 편이 안전하다.

## External API 데이터 편입 설계안

### 원칙

추천 요청 중 Kakao/Naver API 실시간 호출은 금지한다.

권장 데이터 흐름:

```text
Kakao/Naver Places API
  -> raw_external_places
  -> clean_external_places
  -> staging_external_places
  -> QA / review gate
  -> promote candidate
  -> approved promote only
  -> existing places / existing engine
```

### Source별 수집 대상

초기 수집 대상:

- 카페
- 식당
- 실내 장소
- 문화시설
- 감성 장소
- nightlife/coastal/date 보조 후보

수집/보존 필드:

| Field | 목적 |
|---|---|
| `source` | kakao/naver 구분 |
| `external_id` | source 고유 ID |
| `name` | 장소명 |
| `address` | 주소 |
| `latitude` / `longitude` | 좌표 |
| `category` | 외부 카테고리 |
| `phone` | 운영 검증 보조 |
| `place_url` | review 화면 연결 |
| `image_url` | 대표 이미지 후보 |
| `rating` | popularity/quality signal |
| `review_count` | popularity/quality signal |
| `business_status` | 폐업/휴업/운영상태 |
| `opening_hours` | 야간/저녁 정책 신뢰도 |
| `last_verified_at` | stale 데이터 판단 |
| `raw_payload` | 재처리/감사 가능성 |

## 필요한 Migration 초안

운영 반영하지 않는 draft를 별도 파일로 작성했다.

파일:

```text
reports/external_places_data_pipeline_phase1_migration_draft.sql
```

초안 내용:

1. `raw_external_places` 확장
   - `rating`
   - `review_count`
   - `image_url`
   - `image_thumb_url`
   - `business_status`
   - `opening_hours`
   - `last_verified_at`
   - `source_confidence`

2. `clean_external_places` 확장
   - raw 품질 필드 보존
   - `duplicate_of_place_id`
   - `match_status`
   - `match_confidence`

3. `staging_external_places` 신규 초안
   - 외부 후보 전용 review/promote gate
   - `promotion_status`
   - `qa_status`
   - `reviewer`
   - `review_note`
   - `proposed_action`

이 초안은 실제 migration 디렉터리가 아니라 `reports/` 아래에 둔 이유가 있다. 현재 phase는 설계/준비 단계이며 운영 반영 금지 조건이 있기 때문이다.

## Batch 단계 추가안

현재 단계:

```text
collect_external_places
clean_external_places
enrich_external_places
qa_external_places
promote_external_places
```

권장 단계:

```text
collect_external_places
clean_external_places
match_external_places
stage_external_candidates
qa_external_places
review_external_candidates
promote_external_places
post_promote_smoke
```

### 새로 필요한 단계

#### 1. match_external_places

목적:

- 기존 `places`와 중복/동일 장소 매칭
- 이름+좌표+주소+source_id 기준으로 confidence 산출

출력:

- `duplicate_of_place_id`
- `match_status`
- `match_confidence`

#### 2. stage_external_candidates

목적:

- clean row를 바로 `staging_places`로 밀어 넣기보다, 외부 후보 전용 테이블에 적재
- review/QA/promotion 상태를 분리

출력:

- `staging_external_places`
- `promotion_status=pending_review`

#### 3. review_external_candidates

목적:

- low confidence / category risk / duplicate risk 후보를 사람이 확인
- fake POI나 wrong-region 후보 차단

#### 4. promote_external_places 변경

현재:

- `--qa-passed --write` 시 `places` upsert 가능

권장:

- `promotion_status='approved'`
- `qa_status='PASS'`
- `match_confidence` 안전 범위
- `business_status` active/open
- `duplicate_of_place_id` 처리 정책 명확

위 조건을 만족할 때만 promote 허용.

## 환경변수

원격 `.env.example`에는 이미 필요한 최소 외부 API 환경변수가 있다.

```text
KAKAO_REST_API_KEY=your_kakao_rest_api_key_here
NAVER_CLIENT_ID=your_naver_client_id_here
NAVER_CLIENT_SECRET=your_naver_client_secret_here
```

추가 권장 환경변수는 다음과 같다.

```text
EXTERNAL_PLACES_WRITE_ENABLED=false
EXTERNAL_PLACES_MAX_TOTAL=100
EXTERNAL_PLACES_DEFAULT_RADIUS_KM=10
EXTERNAL_PLACES_PROMOTE_REQUIRE_REVIEW=true
EXTERNAL_PLACES_PROMOTE_REQUIRE_QA_PASS=true
```

이번 phase에서는 `.env`나 운영 secret은 수정하지 않았다.

## 절대 수정하면 안 되는 영역

이번 전환 작업에서도 다음 영역은 건드리면 안 된다.

- 추천 요청 중 Kakao/Naver 실시간 호출
- production `places` 직접 insert/update
- 추천 엔진 대규모 rewrite
- representative family orchestration 제거
- drift 방지 로직 제거
- hardcoded route insertion
- fake POI 삽입
- DB schema 운영 반영
- `docker compose down`
- 사주 서비스 container/network

## 위험 지점

### 1. promote_external_places.py

현재 script는 QA 통과와 `--write`가 있으면 `places`에 upsert한다.

플랫폼 전환 관점에서는 이 구조가 가장 위험하다.  
다음 phase에서는 promote를 바로 막기보다, 기본값을 `dry-run`으로 유지하고 `approved` 후보만 promote하는 guard를 추가해야 한다.

### 2. external data 품질 신호 손실

현재 raw payload에는 정보가 들어올 수 있지만, 정규 컬럼으로 충분히 올라오지 않는다.  
추천 품질/야간 운영시간/이미지 품질 평가에 쓰려면 raw JSON 안에 묻어두는 것보다 정규 컬럼으로 승격해야 한다.

### 3. 호스트 실행 환경

EC2 호스트에서 `batch/update_all.sh --dry-run --no-network --skip-qa`를 실행하면 `psycopg2` import 실패가 발생했다.

이 문제는 기능 문제가 아니라 운영 실행 경로 문제다.  
다음 구현 전에 `PYTHON_BIN` 표준 또는 container job 실행 방식을 먼저 정해야 한다.

## 다음 구현 단계 제안

1. `reports/external_places_data_pipeline_phase1_migration_draft.sql` 리뷰
2. migration을 실제 migration 파일로 승격할지 결정
3. `match_external_places.py` 추가
4. `stage_external_candidates.py` 추가
5. `promote_external_places.py`에 review/QA hard guard 추가
6. `collect_external_places.py`에서 가능한 source fields를 정규 컬럼으로 저장
7. `clean_external_places.py`에서 rating/review/image/business_status/opening_hours 보존
8. `batch/update_all.sh`에 `--candidate-only` 또는 `--no-promote` 모드 추가
9. external candidate QA report 추가
10. 소규모 region slice로 dry-run 검증

## 이번 phase에서 수행하지 않은 것

- deploy 없음
- DB write 없음
- migration 실행 없음
- 운영 `places` 수정 없음
- 추천 엔진 수정 없음
- frontend 수정 없음
- saju 영향 없음

## 판정

현재 시스템은 외부 장소 데이터 보강 플랫폼으로 전환할 기반은 이미 있다.  
하지만 지금 상태로 `--write` 운영을 확대하면 QA 통과 후 곧바로 `places` upsert로 이어질 수 있으므로, 먼저 외부 후보 전용 staging/review gate를 추가하는 것이 맞다.

추천 알고리즘을 더 만지는 것보다, 다음 단계는 `staging_external_places`와 review/promote guard를 만드는 것이 우선순위다.

---

## 2026-05-18 추가: external candidate review/staging gate phase1

이번 추가 검토의 목적은 외부 장소 후보가 QA 통과 직후 운영 `places`로 곧바로 promote되는 위험을 줄이는 것이다.  
운영 DB 변경, migration 실행, 추천 엔진 수정, deploy는 수행하지 않았다.

### 현재 promote 위험

현재 `batch/external/promote_external_places.py`는 다음 조건만으로 운영 `places` upsert가 가능하다.

```text
staging_places(source='external')
  -> promote_external_places.py --qa-passed --write
  -> places upsert
```

이 구조는 데이터 품질 플랫폼 관점에서 충분히 안전하지 않다.  
QA는 코스 생성 실패 증가 여부를 보는 장치이고, 외부 후보가 실제 운영 장소로 들어가도 되는지 판단하는 human review gate가 아니다.

### review gate 목표 구조

권장 흐름은 다음과 같다.

```text
collect_external_places
  -> raw_external_places
  -> clean_external_places
  -> match_external_places
  -> stage_external_candidates
  -> staging_external_places
  -> QA
  -> reviewer approve/reject
  -> promote_external_places dry-run
  -> approved-only promote
```

핵심은 `staging_places`를 바로 promote 대상으로 쓰지 않고, 외부 후보 전용 `staging_external_places`를 별도로 두는 것이다.

### staging_external_places 역할

`staging_external_places`는 외부 후보의 운영 반영 전 검수 상태를 보존한다.

필수 분리 상태는 다음과 같다.

- `qa_status`: runtime QA 결과
- `promotion_status`: `pending_review`, `approved`, `rejected`, `promoted`, `blocked`
- `duplicate_review_status`: `unreviewed`, `unique`, `duplicate`, `needs_manual_review`
- `business_safety_status`: `unknown`, `safe`, `closed`, `suspicious`, `needs_manual_review`
- `proposed_action`: `candidate_insert`, `candidate_update`, `candidate_skip`
- `reviewer`, `review_note`, `reviewed_at`
- `promotion_block_reason`

draft SQL은 다음 파일에 반영했다.

```text
reports/external_places_data_pipeline_phase1_migration_draft.sql
```

해당 SQL은 proposal이며 실행하지 않았다.

### promote guard 설계

향후 `promote_external_places.py`는 최소한 아래 조건을 모두 만족하는 후보만 promote해야 한다.

```text
qa_status = 'PASS'
promotion_status = 'approved'
business_safety_status = 'safe'
duplicate_review_status IN ('unique', 'needs_manual_review')
proposed_action IN ('candidate_insert', 'candidate_update')
source IN ('kakao', 'naver')
external_id 존재
name 존재
region 존재
latitude / longitude 존재
visit_role 유효
```

중요한 점은 `--qa-passed` 하나만으로 promote를 허용하지 않는 것이다.  
`--write`를 넣더라도 기본 정책은 dry-run 우선이어야 하며, approved candidate query 결과가 명시적으로 출력된 뒤에만 운영 반영을 검토해야 한다.

### approve/reject workflow

최소 reviewer workflow는 CLI/report 수준이면 충분하다.

1. `stage_external_candidates.py`
   - `clean_external_places`에서 후보를 읽음
   - source id, 좌표, category, image, business_status, duplicate match를 정리
   - `staging_external_places`에 `pending_review`로 기록

2. `review_external_candidates.py --run-id ... --report`
   - reviewer용 CSV/Markdown 출력
   - duplicate 의심, 운영 종료, 좌표 이상, image 없음, category mismatch 표시

3. `review_external_candidates.py --approve <id>` 또는 `--reject <id>`
   - 실제 구현 시에는 reviewer, review_note 필수
   - bulk approve는 금지하거나 별도 `--i-understand-risk` guard 필요

4. `promote_external_places.py --run-id ... --dry-run`
   - promote 가능 후보와 block reason 출력

5. `promote_external_places.py --run-id ... --write`
   - approved + QA PASS + safety PASS 후보만 반영
   - 이번 phase에서는 구현하지 않음

### batch 단계 추가안

현재 `batch/update_all.sh`는 외부 후보 collect/clean/enrich/QA/promote 흐름을 이미 포함한다.  
다음 phase에서는 다음 단계로 분리하는 것이 맞다.

```text
collect_external_places
clean_external_places
match_external_places
stage_external_candidates
qa_external_places
review_external_candidates
promote_external_places
```

권장 CLI flag:

```text
--candidate-only
--no-promote
--review-required
--promote-approved-only
```

기본값은 다음이어야 한다.

```text
candidate-only = true
promote = false
review-required = true
```

### 운영 안전성 정책

유지해야 할 운영 원칙은 다음과 같다.

- 추천 요청 중 Kakao/Naver API 실시간 호출 금지
- external candidate는 `places`에 직접 insert/update 금지
- `staging_external_places` review 승인 전 promote 금지
- QA 실패 또는 QA 미실행 candidate promote 금지
- duplicate 의심 candidate는 수동 검토 전 promote 금지
- `business_status='closed'` 또는 폐업 의심 candidate promote 금지
- source id 없는 외부 후보 promote 금지
- fake POI 또는 임의 좌표 생성 금지

### 다음 단계

1. `staging_external_places` draft migration 리뷰
2. `stage_external_candidates.py` 설계/구현
3. `review_external_candidates.py` dry-run report 구현
4. `promote_external_places.py`를 `staging_external_places` 기반 approved-only 방식으로 변경
5. `batch/update_all.sh` 기본값을 candidate-only/no-promote로 조정
6. 소규모 region slice에서 dry-run 검증

이번 추가 작업에서도 운영 DB write, production `places` 수정, migration 실행, 추천 엔진 변경, frontend 변경, deploy, saju 영향은 없었다.

---

## 2026-05-18 추가: dry-run reviewer tooling 구현 결과

이번 구현은 external candidate review gate의 실제 코드 흐름을 dry-run 수준으로 만든 작업이다.  
운영 DB migration 실행, production `places` write, 추천 엔진 수정, deploy는 수행하지 않았다.

### 추가 파일

```text
batch/external/stage_external_candidates.py
batch/external/review_external_candidates.py
```

### 수정 파일

```text
batch/external/promote_external_places.py
batch/update_all.sh
```

### stage_external_candidates.py

역할:

- `clean_external_places` 후보 읽기
- 기존 `places`와 source id/name+거리 기준 duplicate risk 추정
- image 존재 여부 계산
- coordinate validity 계산
- category risk 계산
- business safety 상태 계산
- reviewer decision 산출

지원 옵션:

```text
--run-id
--region
--limit
--write
```

현재 `--write`는 명시해도 실제 write를 수행하지 않고 block message를 반환한다.  
`staging_external_places` migration이 아직 실행되지 않았기 때문에 기본 정책은 메모리/dry-run report다.

출력 summary 예:

```json
{
  "candidate_count": 5,
  "duplicate_suspicious_count": 5,
  "missing_image_count": 5,
  "missing_coordinate_count": 0,
  "category_mismatch_count": 0,
  "approve_candidate_count": 0,
  "review_required_count": 5,
  "blocked_count": 0
}
```

### review_external_candidates.py

역할:

- reviewer용 Markdown/CSV/JSON report 생성
- duplicate risk, business status, image, coordinate, proposed_action, block reason 표시
- approve/reject DB write는 아직 구현하지 않음

지원 옵션:

```text
--run-id
--region
--limit
--report
--output-dir
```

생성 report 예:

```text
qa_reports/external_candidate_review_smoke/
  external_candidate_review_72e04e7b-62e6-447b-a091-ceefe5560ec8_서울.csv
  external_candidate_review_72e04e7b-62e6-447b-a091-ceefe5560ec8_서울.md
  external_candidate_review_72e04e7b-62e6-447b-a091-ceefe5560ec8_서울.json
```

sample Markdown report에서는 5개 후보가 모두 `REVIEW_REQUIRED`로 분류되었다.

주요 원인:

- `BLOCK_DUPLICATE_RISK`
- `BLOCK_MISSING_IMAGE`

### promote_external_places.py guard 변경

실제 promote rewrite는 하지 않았다.  
대신 현재 legacy promote path가 위험하다는 warning과 approved-only TODO를 명시했다.

dry-run promote 출력에 다음 정보가 포함된다.

```text
safety_warning:
dry-run only; production promote requires future approved-only review gate

approved_only_promote_todo:
staging_external_places.qa_status = 'PASS'
staging_external_places.promotion_status = 'approved'
staging_external_places.business_safety_status = 'safe'
duplicate/manual review policy passed
required fields exist
```

`--write` 경로도 legacy path warning을 stderr/stdout에 남기도록 보강했다.  
단, 이번 phase에서는 `--write`를 실행하지 않았다.

### update_all.sh safety proposal 반영

추가 flag:

```text
--candidate-only
--no-promote
--review-required
--allow-promote
```

기본값:

```text
candidate_only=true
no_promote=true
review_required=true
```

write mode에서도 collect/clean/enrich/QA 이후 promote를 바로 수행하지 않고, candidate review report를 생성한 뒤 아래 상태로 종료하도록 설계했다.

```text
result: CANDIDATE_REVIEW_READY
```

legacy promote는 `--allow-promote`를 명시해야만 진행 가능하도록 안전 proposal을 반영했다.

### 검증 결과

검증은 실행 중인 `travel-backend-v2` 컨테이너 내부 Python으로 수행했다.  
EC2 host Python에는 `psycopg2`가 없어 batch 실행 표준은 container Python 기준이어야 한다.

수행:

```text
python -m py_compile
bash -n batch/update_all.sh
python -m batch.external.stage_external_candidates --help
python -m batch.external.review_external_candidates --help
stage_external_candidates dry-run
review_external_candidates --report
promote_external_places dry-run warning 확인
```

확인:

- 운영 DB write 없음
- migration 실행 없음
- production `places` 수정 없음
- 추천 엔진 영향 없음
- review report 생성 가능
- duplicate risk visibility 가능
- image missing visibility 가능
- promote dry-run warning 출력 확인
- saju 영향 없음

### 남은 위험 요소

1. `staging_external_places` migration이 아직 draft 상태라 실제 stage write는 비활성화 상태다.
2. approve/reject DB write tooling은 아직 구현되지 않았다.
3. `promote_external_places.py`는 아직 legacy `staging_places` read path를 유지한다.
4. EC2 host Python 의존성 문제 때문에 batch 실행은 container 기준으로 표준화해야 한다.
5. `update_all.sh --allow-promote`는 emergency/legacy escape hatch로만 취급해야 한다.

### 다음 단계

1. `staging_external_places` migration 승인 여부 결정
2. `stage_external_candidates.py --write`를 migration 적용 후에만 활성화
3. `review_external_candidates.py --approve/--reject` 구현
4. `promote_external_places.py`를 `staging_external_places` approved-only query 기반으로 전환
5. `batch/update_all.sh`의 candidate-only 흐름을 운영 표준으로 문서화

---

## 2026-05-18 추가: approved-only promote 전환 준비

이번 작업은 external review gate를 실제 approved-only promote 구조로 전환하기 위한 준비 단계다.  
운영 migration 실행, production `places` write, 추천 엔진 수정, deploy는 수행하지 않았다.

### staging_external_places migration final draft

`reports/external_places_data_pipeline_phase1_migration_draft.sql`을 final draft 수준으로 정리했다.

유지한 핵심 상태는 다음으로 제한했다.

- `promotion_status`: 운영 반영 승인 상태
- `qa_status`: QA 통과 여부
- `duplicate_review_status`: 중복 검토 상태
- `business_safety_status`: 폐업/영업 안전 상태
- `match_status`, `match_confidence`: 기존 places와의 match 상태
- `reviewer`, `review_note`, `reviewed_at`: 사람 검토 기록
- `promotion_block_reason`: promote 차단 사유

과도한 심사 시스템을 만들기보다 운영 DB 오염 방지에 필요한 최소 상태만 유지하는 방향이 맞다.

필수 인덱스는 다음 중심으로 유지했다.

- `(run_id, region, promotion_status, qa_status)`
- `(source, external_id)`
- `(run_id, duplicate_review_status, duplicate_of_place_id)`
- `(run_id, business_safety_status, promotion_status)`

### reviewer persistence 방향

`review_external_candidates.py`에 approve/reject persistence 인터페이스 초안을 추가했다.

추가 옵션:

```text
--approve <id>
--reject <id>
--reviewer <operator>
--review-note <note>
```

현재 동작은 dry-run payload 출력이다.  
`staging_external_places` migration이 적용되기 전까지 실제 DB update는 수행하지 않는다.

예상 update 방향:

```text
approve:
  promotion_status = 'approved'
  reviewer = ...
  review_note = ...
  reviewed_at = NOW()

reject:
  promotion_status = 'rejected'
  reviewer = ...
  review_note = ...
  reviewed_at = NOW()
```

`--reviewer`와 `--review-note`는 approve/reject에서 필수로 유지하는 것이 맞다.  
무기명 bulk approval은 운영 리스크가 크다.

### approved-only promote 설계

`promote_external_places.py`에 approved-only dry-run validator를 추가했다.

추가 옵션:

```text
--approved-only-dry-run
```

이 옵션은 `staging_external_places`가 존재하면 approved-only precondition을 검사하고, 없으면 migration draft 상태라 blocked로 반환한다.

필수 precondition:

```text
qa_status = 'PASS'
promotion_status = 'approved'
business_safety_status = 'safe'
duplicate_review_status IN ('unique', 'needs_manual_review')
source IN ('kakao', 'naver')
external_id 존재
name 존재
region 존재
latitude / longitude 존재
visit_role 유효
```

현재 legacy promote path는 아직 유지한다.  
다만 다음 phase에서는 `_load_staging()`의 `staging_places` read path를 제거하고, `staging_external_places` approved-only query만 남겨야 한다.

### legacy promote 제거 계획

권장 순서:

1. `staging_external_places` migration 적용
2. `stage_external_candidates.py --write` 활성화
3. `review_external_candidates.py --approve/--reject --write` 활성화
4. `promote_external_places.py --approved-only-dry-run` 운영 검증
5. legacy `staging_places` promote path 비활성화
6. `promote_external_places.py --write`가 approved-only query만 사용하도록 전환
7. `batch/update_all.sh --allow-promote`도 approved-only mode만 호출하도록 변경

legacy path를 즉시 삭제하지 않는 이유는 기존 batch 운영 의존성이 남아 있을 수 있기 때문이다.  
하지만 새 운영 표준은 `staging_external_places` 기반 approved-only promote여야 한다.

### update_all.sh safety 강화

`--allow-promote` 없이는 promote가 불가능한 구조를 유지했다.

추가로 `--allow-promote`가 있어도 candidate review report 생성이 확인되지 않으면 promote를 block하도록 guard를 추가했다.

현재 기본값:

```text
candidate_only=true
no_promote=true
review_required=true
```

`--allow-promote`는 legacy escape hatch로만 남겨야 한다.  
운영 표준으로 쓰면 안 된다.

### reviewer workflow 단순화 판단

검토 결과, review state를 더 늘리는 것은 좋지 않다.  
운영자가 실제로 관리 가능한 최소 상태는 다음 3개 축이다.

- `promotion_status`
- `duplicate_review_status`
- `business_safety_status`

`qa_status`는 reviewer 판단이 아니라 자동 QA 결과이므로 별도 축으로 유지한다.

이 정도면 운영 DB 오염 방지 목적에는 충분하다.  
완전한 CMS/심사 시스템을 지금 만들 필요는 없다.

### 검증 결과

수행한 검증:

```text
python -m py_compile
bash -n batch/update_all.sh
review_external_candidates --approve dry-run
review_external_candidates --reject dry-run
promote_external_places --approved-only-dry-run
```

확인:

- 운영 DB write 없음
- migration 실행 없음
- production `places` 수정 없음
- legacy path audit 가능
- approved-only precondition 설명 가능
- reviewer persistence 방향 설명 가능
- saju 영향 없음

### 남은 위험 요소

1. `staging_external_places` migration이 아직 실제 적용되지 않았다.
2. approve/reject persistence는 dry-run interface만 있고 실제 update는 비활성화다.
3. `promote_external_places.py`는 legacy `staging_places` read path를 아직 유지한다.
4. `--allow-promote`는 남아 있으므로 운영 문서에서 legacy escape hatch로 명확히 제한해야 한다.
5. EC2 host Python 의존성 문제는 여전히 남아 있어 batch 실행 기준을 container Python으로 고정해야 한다.

---

## 2026-05-18 추가: approved-only rehearsal mode

이번 작업은 실제 운영 전환 전에 approved-only promote 흐름을 운영 리허설 수준으로 검증 가능하게 만든 단계다.  
production migration 실행, production `places` write, 추천 엔진 수정, deploy는 수행하지 않았다.

### rehearsal mode 결과

`promote_external_places.py`에 다음 옵션을 추가했다.

```text
--approved-only-rehearsal
--limit
```

이 모드는 실제 promote 없이 다음 흐름을 simulation한다.

```text
clean_external_places
→ candidate risk calculation
→ PENDING_REVIEW
→ APPROVED / REVIEW_REQUIRED / REJECTED
→ PROMOTE_ELIGIBLE / BLOCKED
→ final promote candidate preview
```

현재 `staging_external_places` migration이 적용되지 않았기 때문에 rehearsal source는 `clean_external_places` 기반 simulation이다.  
migration 적용 이후에는 `staging_external_places` 기반 persistence validator로 전환한다.

sample rehearsal 결과:

```json
{
  "mode": "approved_only_rehearsal",
  "approve_candidate_count": 0,
  "blocked_candidate_count": 5,
  "duplicate_blocked_count": 5,
  "business_safety_blocked_count": 0,
  "missing_image_blocked_count": 5,
  "final_promote_candidate_preview": []
}
```

해석:

- sample 후보 5개 모두 duplicate risk와 image missing으로 promote eligible이 아님
- production `places` write 없음
- migration write 없음

### promote eligibility validator 강화점

`--approved-only-dry-run`은 `staging_external_places`가 존재할 때 실제 approved-only precondition을 검사한다.

강화된 출력:

- candidate별 `errors`
- candidate별 canonical `block_reasons`
- `approved_candidate_count`
- `blocked_candidate_count`
- `blocked_reason_counts`
- `approved_candidates`
- `blocked_candidates`

`staging_external_places`가 아직 없으면 다음처럼 안전하게 차단된다.

```json
{
  "blocked": "staging_external_places table does not exist; migration is still draft",
  "approved_candidate_count": 0
}
```

### blocked reason taxonomy

운영자가 봐야 할 block reason은 다음으로 정리했다.

```text
BLOCK_DUPLICATE_RISK
BLOCK_BUSINESS_STATUS
BLOCK_QA_FAIL
BLOCK_REVIEW_PENDING
BLOCK_MISSING_COORDINATE
BLOCK_INVALID_ROLE
BLOCK_REQUIRED_FIELD
BLOCK_UNSUPPORTED_SOURCE
BLOCK_CATEGORY_RISK
BLOCK_MISSING_IMAGE
```

여기서 `BLOCK_MISSING_IMAGE`는 즉시 hard reject가 아니라 review blocker에 가깝다.  
다만 실제 promote 전에는 reviewer가 image 품질을 확인해야 한다.

### reviewer simulation 흐름

rehearsal mode는 reviewer state transition을 candidate별로 출력한다.

예:

```text
PENDING_REVIEW
→ APPROVED
→ PROMOTE_ELIGIBLE
```

또는:

```text
PENDING_REVIEW
→ REVIEW_REQUIRED
→ BLOCKED
```

또는:

```text
PENDING_REVIEW
→ REJECTED
→ BLOCKED
```

이 흐름으로 운영자가 “어떤 후보가 왜 promote 대상이 아닌지”를 실제 write 없이 이해할 수 있다.

### migration readiness audit 결과

현재 migration draft는 운영 DB 오염 방지를 위한 최소 상태 중심으로 유지하는 것이 적절하다.

유지:

- `promotion_status`
- `duplicate_review_status`
- `business_safety_status`
- `qa_status`
- `match_status`, `match_confidence`
- `reviewer`, `review_note`, `reviewed_at`
- `promotion_block_reason`

과도하다고 판단한 방향:

- 세분화된 moderation state 다수 추가
- 별도 admin workflow용 복잡한 enum 확장
- review history table 즉시 추가

현재 목표는 완전한 moderation CMS가 아니라 운영 `places` 오염 방지다.  
따라서 단순한 상태 3축 + QA 상태가 맞다.

### update_all.sh rehearsal 방향

추가 flag:

```text
--rehearsal
--approved-only-rehearsal
```

동작:

```text
candidate review report
→ QA
→ approved-only rehearsal preview
→ blocked summary
→ final safety summary
→ exit
```

실제 promote는 수행하지 않는다.

현재 기본 안전 정책은 유지한다.

```text
candidate_only=true
no_promote=true
review_required=true
```

### 검증 결과

수행:

```text
python -m py_compile
bash -n batch/update_all.sh
promote_external_places --approved-only-rehearsal
promote_external_places --approved-only-dry-run
update_all.sh --help
```

확인:

- 운영 DB write 없음
- migration 실행 없음
- production `places` 수정 없음
- approved-only rehearsal 가능
- blocked reason visibility 가능
- reviewer state transition simulation 가능
- promote eligibility preview 가능
- saju 영향 없음

### 운영 전환 전 남은 blocker

1. `staging_external_places` migration 적용 승인 필요
2. `stage_external_candidates.py --write` 구현 필요
3. `review_external_candidates.py --approve/--reject --write` 구현 필요
4. `promote_external_places.py` legacy `staging_places` read path 제거 필요
5. `update_all.sh --allow-promote`가 approved-only promote만 호출하도록 전환 필요
6. batch 실행 기준을 EC2 host Python이 아니라 container Python으로 표준화 필요

---

## 2026-05-18 추가: migration rollout checklist / rollback plan

이번 정리는 approved-only promote 구조를 실제 운영 전환 가능한 상태로 만들기 위한 최종 운영 준비 문서다.  
추가 기능 개발, production migration 실행, production `places` write, deploy는 수행하지 않았다.

### 1. Rollout Checklist

목표는 migration 적용 자체가 아니라 `places` 오염을 막는 것이다.  
따라서 rollout은 반드시 promote freeze 상태에서 시작해야 한다.

#### Pre-check

1. 현재 서비스 상태 확인
   - `docker ps`
   - travel backend/frontend running
   - saju backend/frontend/mysql running
   - public API smoke

2. DB 연결 확인
   - container Python 기준으로 `db_client.get_connection()` 확인
   - EC2 host Python 직접 실행은 금지 또는 제한

3. 현재 external pipeline table 확인
   - `raw_external_places`
   - `clean_external_places`
   - `staging_places`
   - `data_update_runs`
   - `data_update_qa_results`

4. promote freeze 선언
   - `batch/update_all.sh` 기본값이 `candidate_only=true`, `no_promote=true`, `review_required=true`인지 확인
   - `--allow-promote` 사용 금지
   - legacy `promote_external_places.py --write` 직접 실행 금지

5. migration 파일 확인
   - `reports/external_places_data_pipeline_phase1_migration_draft.sql`
   - 실제 migration 파일로 승격할 경우 파일명과 적용 순서 확정

#### Backup / checkpoint

1. DB schema dump
   - 최소한 schema-only dump 필요
   - `staging_external_places` 적용 전 table list 저장

2. 코드 checkpoint
   - `batch/external/*`
   - `batch/update_all.sh`
   - migration SQL

3. 운영 상태 checkpoint
   - `docker ps`
   - `df -h`
   - `free -m`
   - current git hash/status

#### Migration apply sequence

1. promote freeze 확인
2. migration SQL dry-run review
3. transaction 가능한 방식으로 migration 적용
4. 적용 직후 table/index 확인

확인 대상:

```text
staging_external_places
idx_staging_external_places_review
idx_staging_external_places_source_id
idx_staging_external_places_duplicate_review
idx_staging_external_places_business_safety
```

5. `raw_external_places` / `clean_external_places` 추가 컬럼 확인
6. `stage_external_candidates.py --write`는 아직 실행하지 않음
7. 먼저 `--approved-only-dry-run`으로 table 존재 확인

#### Rehearsal validation

1. 기존 sample run_id로 rehearsal
   - `--approved-only-rehearsal`
2. migration 적용 후 validator
   - `--approved-only-dry-run`
3. 신규 외부 후보 소량 dry-run
4. `stage_external_candidates.py --write`는 별도 승인 후 1개 region/limit 소량만
5. review report 생성 확인
6. approve/reject persistence 소량 확인
7. approved-only dry-run에서 promote eligible count 확인

#### QA 조건

promote 전 최소 조건:

- QA 실행됨
- `qa_status='PASS'`
- FAIL 증가 없음
- candidate report 생성됨
- reviewer 승인 있음
- duplicate risk cleared
- business safety safe

#### Legacy path disable 시점

다음 조건을 모두 만족한 뒤에만 legacy path를 disable한다.

1. `staging_external_places` migration 적용 완료
2. `stage_external_candidates.py --write` 동작 확인
3. `review_external_candidates.py --approve/--reject --write` 동작 확인
4. `promote_external_places.py --approved-only-dry-run` 정상
5. shadow mode 비교 결과 문제 없음
6. 운영자가 approved-only report를 이해 가능

### 2. Rollback Strategy

rollback의 기준은 추천 엔진이 아니라 운영 데이터 보호다.

#### 즉시 rollback 또는 freeze 조건

- migration 적용 실패
- `staging_external_places` 생성은 됐지만 index/check constraint 이상
- approve/reject persistence가 잘못된 candidate를 승인
- approved-only validator가 위험 후보를 eligible로 표시
- legacy path가 여전히 `places` write 가능
- QA 없이 promote 가능성이 확인됨
- 운영자가 report를 해석하기 어려워 잘못 승인할 가능성이 큼

#### rollback 우선순위

1. promote freeze
   - 모든 promote 중단
   - `--allow-promote` 금지
   - legacy promote 직접 실행 금지

2. code rollback
   - `promote_external_places.py`를 직전 checkpoint로 복구
   - `batch/update_all.sh`를 candidate-only/no-promote 상태로 복구

3. migration rollback
   - migration이 table 추가만 수행했다면 즉시 drop보다 freeze 우선
   - 데이터가 들어갔다면 drop 금지, read-only quarantine 우선
   - schema rollback은 별도 백업 확인 후 진행

4. data rollback
   - `places`가 오염되지 않았다면 data rollback 불필요
   - `places` write가 발생했다면 `place_update_snapshots`와 external source id 기준으로 별도 복구 계획 필요

#### legacy path 복귀 가능성

legacy path로 “복귀”하는 것은 최후 수단이다.  
복귀하더라도 `--write` promote는 금지하고 dry-run/candidate-only만 허용해야 한다.

즉 rollback 목표는 legacy promote 재개가 아니라 promote freeze 상태 복구다.

### 3. Promote Cutover Sequence

big bang 전환은 금지한다.

권장 cutover:

```text
legacy staging path active but frozen
→ migration apply
→ approved-only dry-run
→ candidate review validation
→ approved-only shadow mode
→ legacy promote disabled
→ approved-only promote only
```

세부 단계:

1. Legacy path active but frozen
   - 기존 코드는 남기되 `--write` 사용 금지

2. Migration apply
   - `staging_external_places` 생성
   - raw/clean quality columns 추가

3. Approved-only dry-run
   - table 존재 확인
   - precondition validator 확인

4. Candidate review validation
   - stage/write 소량
   - review report 확인
   - approve/reject persistence 확인

5. Shadow mode
   - legacy would promote 후보와 approved-only would promote 후보 비교

6. Legacy promote disabled
   - `_load_staging()` 기반 `staging_places` path 제거 또는 hard block

7. Approved-only promote only
   - `staging_external_places` approved candidates만 promote

### 4. Shadow Mode 판단

shadow mode는 강하게 권장한다.

목표:

```text
legacy would promote X
approved-only would block X
```

이 차이를 운영자가 볼 수 있어야 한다.

필요 출력:

- legacy_candidate_count
- approved_eligible_count
- blocked_by_duplicate_count
- blocked_by_business_status_count
- blocked_by_review_pending_count
- blocked_by_missing_required_field_count
- legacy_only_candidates
- approved_only_candidates

shadow mode에서는 절대 write하지 않는다.  
결과가 안정적이면 그때 legacy promote path를 disable한다.

### 5. Migration Readiness Final Audit

현재 draft는 목적에 맞게 충분히 작다.

#### Nullable

외부 API source별로 제공 필드가 다르기 때문에 `rating`, `review_count`, `image_url`, `opening_hours`, `business_status`는 nullable이 맞다.  
반대로 `source`, `external_id`, `name`, `region`, `latitude`, `longitude`, `visit_role`은 promote precondition에서 필수로 검사한다.

#### Index

현재 index는 적절하다.

- review queue 조회
- source id lookup
- duplicate review
- business safety review

대규모 moderation CMS가 아니므로 더 많은 index는 아직 필요 없다.

#### Query complexity

approved-only query는 단순해야 한다.

```text
run_id
qa_status
promotion_status
business_safety_status
duplicate_review_status
required fields
```

복잡한 scoring query를 promote 단계에 넣으면 안 된다.

#### Status taxonomy

현재 상태 축은 충분하다.

- `promotion_status`
- `duplicate_review_status`
- `business_safety_status`
- `qa_status`

상태를 더 늘리면 운영자가 관리하기 어렵다.

#### Operator confusion

위험 지점:

- `BLOCK_MISSING_IMAGE`가 hard reject처럼 보일 수 있음
- `needs_manual_review`가 promote 가능한 상태처럼 오해될 수 있음
- `--allow-promote`가 안전한 옵션처럼 보일 수 있음

완화:

- report에 block reason 의미 명시
- `--allow-promote`는 legacy escape hatch로만 표기
- approved-only promote 전에는 final preview 필수

### 6. Container Execution Standard

현재 EC2 host Python에는 `psycopg2`가 없어 batch script 실행이 실패한다.  
따라서 운영 표준은 container Python 기준으로 잡아야 한다.

원칙:

```text
batch 실행은 travel-backend-v2 container 내부 Python 기준
host python 직접 실행 금지 또는 smoke/help 수준으로 제한
```

권장 실행 방식:

```text
docker exec -i travel-backend-v2 python -m batch.external.stage_external_candidates ...
docker exec -i travel-backend-v2 python -m batch.external.review_external_candidates ...
docker exec -i travel-backend-v2 python -m batch.external.promote_external_places --approved-only-rehearsal ...
```

`batch/update_all.sh`를 host에서 실행하려면 먼저 `PYTHON_BIN`이 container wrapper 또는 venv Python을 가리키도록 표준화해야 한다.

필수 dependency:

- `psycopg2`
- `requests`
- `python-dotenv` 또는 현재 config 로딩에 필요한 패키지
- backend repo import path

### 7. 실제 운영 전환 전 최종 blocker

1. migration 적용 승인
2. schema backup/checkpoint
3. migration 적용 후 table/index 확인
4. `stage_external_candidates.py --write` 구현 및 소량 검증
5. `review_external_candidates.py --approve/--reject --write` 구현 및 소량 검증
6. shadow mode 구현
7. legacy promote path disable
8. `update_all.sh --allow-promote`를 approved-only promote만 호출하도록 전환
9. container execution standard 확정
10. 운영자용 review report 해석 가이드 확정

---

## 2026-05-18 추가: migration go / no-go final gate

이번 정리는 실제 migration 적용 직전의 go/no-go 판단 기준이다.  
production migration 실행, production `places` write, 추천 엔진 수정, deploy는 수행하지 않았다.

### 1. Go / No-Go Checklist

판단 기준은 기능 완성도가 아니라 운영자가 실수로 `places`를 오염시킬 가능성이다.

#### GO 조건

다음 조건을 모두 만족해야 migration 적용 검토가 가능하다.

1. approved-only rehearsal 정상
   - `--approved-only-rehearsal`이 write 없이 실행됨
   - final promote candidate preview가 출력됨
   - blocked summary가 출력됨

2. blocked taxonomy 정상
   - `BLOCK_DUPLICATE_RISK`
   - `BLOCK_BUSINESS_STATUS`
   - `BLOCK_QA_FAIL`
   - `BLOCK_REVIEW_PENDING`
   - `BLOCK_MISSING_COORDINATE`
   - `BLOCK_INVALID_ROLE`
   - `BLOCK_REQUIRED_FIELD`
   - `BLOCK_UNSUPPORTED_SOURCE`
   - `BLOCK_CATEGORY_RISK`
   - `BLOCK_MISSING_IMAGE`

3. review report 이해 가능
   - reviewer가 후보 이름/source/category/image/coordinate/duplicate reason을 읽고 판단 가능
   - `REVIEW_REQUIRED`와 `BLOCKED` 차이가 명확함

4. legacy path freeze 가능
   - `--allow-promote` 사용 금지 상태 유지 가능
   - legacy `promote_external_places.py --write` 직접 실행 금지 가능

5. shadow mode 비교 가능
   - legacy would promote 후보와 approved-only would promote 후보 비교 가능
   - 차이 후보와 block reason이 출력됨

6. container execution standard 준비 완료
   - batch 실행은 `travel-backend-v2` container Python 기준
   - host Python 직접 실행을 운영 경로로 쓰지 않음

7. reviewer workflow 단순 유지 가능
   - `promotion_status`
   - `duplicate_review_status`
   - `business_safety_status`
   - `qa_status`

#### NO-GO 조건

아래 조건 중 하나라도 있으면 migration 적용을 미룬다.

1. operator confusion 가능
   - `BLOCK_MISSING_IMAGE`를 hard reject로 오해
   - `needs_manual_review`를 자동 승인으로 오해
   - `--allow-promote`를 일반 운영 옵션으로 오해

2. legacy path uncontrolled write 가능
   - `--allow-promote` 없이 promote 가능
   - review report 없이 promote 가능
   - QA 없이 promote 가능

3. duplicate/business safety validation 부족
   - 기존 `places`와 같은 source id/name+coordinate 중복을 못 잡음
   - 폐업/영업 종료 후보가 eligible로 표시됨

4. rollback 불명확
   - migration 실패 시 promote freeze로 돌아가는 방법이 없음
   - schema rollback과 data rollback 기준이 혼재됨

5. promote preview 불명확
   - final promote candidate preview가 없음
   - block reason summary가 없음
   - 운영자가 어떤 후보가 들어갈지 사전에 확인할 수 없음

### 2. Shadow Mode Final Spec

shadow mode는 migration 적용 후 legacy path를 제거하기 전 필수 검증 단계다.

#### 목적

```text
legacy would promote
vs
approved-only would promote
```

차이를 write 없이 비교한다.

#### 필수 출력

```json
{
  "legacy_candidate_count": 0,
  "approved_eligible_count": 0,
  "legacy_only_candidates": [],
  "approved_only_candidates": [],
  "blocked_reason_counts": {},
  "false_positive_risk": [],
  "false_negative_risk": []
}
```

#### legacy_only_candidates

legacy path라면 promote됐을 후보지만 approved-only에서 block된 후보.

이 목록이 가장 중요하다.  
여기에 duplicate, missing coordinate, closed business, review pending 후보가 있으면 approved-only 전환 가치가 확인된다.

#### approved_only_candidates

approved-only에서는 eligible이지만 legacy path에서는 누락되는 후보.

이 후보는 false negative risk 확인용이다.  
단, 운영 오염 방지 관점에서는 false negative보다 false positive가 더 위험하다.

#### false positive risk

운영에 들어가면 안 되는데 legacy가 promote하려는 후보.

예:

- duplicate risk
- closed/suspicious business
- missing coordinate
- unsupported source
- invalid role
- review pending

#### false negative risk

들어가도 되는 후보인데 approved-only가 과도하게 막는 후보.

예:

- image missing만 있는 우수 후보
- duplicate risk가 낮은데 이름 유사로 걸린 후보
- business status unknown이지만 source 신뢰도가 높은 후보

shadow mode에서는 절대 write하지 않는다.

### 3. Operator Guide 초안

운영자 판단 기준은 단순해야 한다.

#### REVIEW_REQUIRED

자동으로 승인하거나 거부하지 말고 사람이 봐야 한다.

주요 원인:

- duplicate 의심
- image 없음
- category 애매함
- business status unknown
- 좌표는 있으나 위치가 미심쩍음

#### APPROVED

reviewer가 운영 반영 가능하다고 승인한 상태다.  
단, `qa_status='PASS'`, `business_safety_status='safe'`, duplicate review clear가 같이 맞아야 promote eligible이다.

#### PROMOTE_ELIGIBLE

approved-only precondition을 모두 만족한 후보다.  
이 상태가 되어도 바로 write하지 말고 final preview를 확인해야 한다.

#### BLOCK_DUPLICATE_RISK

기존 `places`에 이미 같은 후보가 있을 가능성이 높다.

확인:

- 동일 source id
- 동일 이름
- 150m 이내 좌표
- 같은 region

처리:

- 같은 장소면 reject 또는 update candidate로 분류
- 다른 지점이면 review note에 근거 기록

#### BLOCK_MISSING_IMAGE

이미지가 없다는 뜻이다.  
즉시 reject는 아니지만 대표 후보 품질에는 리스크가 있다.

처리:

- 유명 장소이거나 source 신뢰도가 높으면 manual review
- 일반 카페/식당인데 이미지가 없으면 보류 또는 reject

#### BLOCK_BUSINESS_STATUS

폐업, 영업 종료, 의심 상태다.

처리:

- closed면 reject
- unknown이면 source payload 확인 후 manual review

#### BLOCK_MISSING_COORDINATE

좌표가 없거나 한국 좌표 범위 밖이다.

처리:

- reject
- 임의 좌표 생성 금지

#### BLOCK_CATEGORY_RISK

숙박, 병원, 학교, 행정시설 등 관광 후보로 부적합할 가능성이 있다.

처리:

- 관광 목적이 명확하지 않으면 reject
- 예외는 review note에 근거 기록

#### 언제 reject해야 하는가

- 폐업/영업 종료
- 좌표 없음
- 기존 장소와 명백한 중복
- 관광/여행 후보가 아닌 생활시설
- source id/name/address가 불명확
- fake 또는 substitute 가능성이 있음

#### 언제 manual review 해야 하는가

- image만 없음
- business status unknown
- duplicate 가능성은 있으나 다른 지점일 수 있음
- category는 애매하지만 실제 인기 장소일 수 있음

### 4. Migration Apply Rehearsal Procedure

실제 migration 실행 전 운영자가 따라야 할 절차다.

1. Pre-check
   - travel/saju container running 확인
   - DB connection 확인
   - current git status/hash 기록
   - promote freeze 확인

2. Checkpoint
   - schema-only backup
   - `batch/external/*` 백업
   - `batch/update_all.sh` 백업
   - migration SQL checksum 또는 파일 크기 기록

3. Migration dry review
   - `CREATE TABLE staging_external_places`
   - required CHECK constraint
   - required index
   - raw/clean added columns
   - destructive SQL 없음 확인

4. Apply
   - transaction 가능한 방식으로 적용
   - 실패 시 즉시 promote freeze 유지

5. Validator
   - table exists
   - index exists
   - `--approved-only-dry-run`

6. Rehearsal
   - `--approved-only-rehearsal`
   - review report 생성
   - block reason summary 확인

7. Shadow mode
   - legacy vs approved-only 비교
   - write 금지

8. Freeze 유지 확인
   - `--allow-promote` 금지
   - production `places` row count 변화 없음 확인

### 5. Legacy Promote 제거 조건

legacy promote path는 아래 조건을 모두 만족한 뒤 제거한다.

1. approved-only validator 안정
   - block reason이 정확히 출력됨
   - eligible 후보가 preview에 명확히 표시됨

2. reviewer workflow 안정
   - approve/reject write가 소량 후보에서 정상
   - reviewer note 필수
   - bulk approve 없음

3. rehearsal 결과 안정
   - blocked reason taxonomy가 운영자가 이해 가능
   - final promote preview가 실제 후보와 일치

4. shadow mode discrepancy 허용 범위
   - legacy_only 후보 대부분이 duplicate/review pending/business risk로 설명 가능
   - approved_only 후보가 예상 밖으로 많지 않음
   - false positive risk가 명확히 줄어듦

5. rollback 가능 상태
   - promote freeze로 즉시 돌아갈 수 있음
   - code checkpoint 있음
   - migration 적용 후에도 data write가 없으면 rollback 부담이 낮음

### 6. 최종 판단

현재 상태는 migration apply 직전 설계/리허설 준비는 충분하다.  
하지만 아직 GO는 아니다.

NO-GO 사유:

- `staging_external_places` migration 미적용
- approve/reject persistence 미활성화
- shadow mode 미구현
- legacy promote path 아직 존재

따라서 다음 액션은 migration 실행이 아니라 shadow mode spec 구현과 operator guide 검토다.  
운영자가 report를 보고 안전하게 승인/거부할 수 있다는 것이 확인된 뒤 migration 적용을 승인하는 편이 맞다.

---

## 2026-05-18 추가: small slice validation / shadow mode 준비

이번 정리는 approved-only promote 운영 전환 직전의 소량 운영 slice 검증 준비다.  
production migration 실행, production `places` write, 추천 엔진 수정, full reload, raw overwrite는 수행하지 않았다.

### 1. Small Slice Validation 계획

소량 검증의 목적은 대량 수집이 아니라 운영자가 approved-only 흐름을 실제 후보 기준으로 이해할 수 있는지 확인하는 것이다.

#### Slice A: 서울 카페 10개

목표:

- 카페/디저트 후보의 duplicate risk 확인
- image missing이 운영 판단에 미치는 영향 확인
- 기존 성수/북촌/한남 curated candidate와 충돌 여부 확인

적절한 이유:

- 서울 카페는 후보 밀도가 높아 duplicate risk가 높다.
- 이미지/리뷰 신호가 품질 판단에 중요하다.
- 운영자가 `BLOCK_DUPLICATE_RISK`와 `BLOCK_MISSING_IMAGE`를 구분하기 좋다.

예상 risk:

- duplicate risk 높음
- image missing 중간
- business status unknown 중간
- category mismatch 낮음

#### Slice B: 부산 식당 10개

목표:

- 식당 후보가 representative flow를 오염시킬 위험 확인
- 기존 부산 원도심/광안리/기장 family와 충돌 여부 확인
- 일반 식당과 여행 동선에 유효한 식당을 구분하는 reviewer 판단 확인

적절한 이유:

- 부산은 식당 후보가 많고 generic meal contamination 위험이 크다.
- 이미 광안리/기장/남포 family를 많이 다듬었기 때문에 source 품질을 보기 좋다.

예상 risk:

- duplicate risk 중간
- image missing 중간
- business status unknown 중간
- generic meal risk 높음

#### Slice C: 제주 실내 장소 10개

목표:

- indoor/culture 후보의 운영시간/실사용 적합성 확인
- 카페/실내/체험 계열이 야간/비 오는 날 후보로 쓸 만한지 판단
- public/culture fallback contamination 위험 확인

적절한 이유:

- 제주 실내 장소는 날씨 대응 후보로 중요하다.
- 공공데이터 기반 weak indoor 후보와 외부 API 후보 품질 차이를 비교하기 좋다.

예상 risk:

- duplicate risk 낮음~중간
- image missing 중간
- business status unknown 높음
- category mismatch 중간

### 2. Shadow Mode 준비 상태

shadow mode는 migration 적용 후 legacy path를 제거하기 전 반드시 수행한다.

비교:

```text
legacy would promote
vs
approved-only would promote
```

필수 출력:

```text
legacy_only_candidates
approved_only_candidates
blocked_reason_counts
false_positive_risk
false_negative_risk
```

#### legacy_only_candidates

legacy path에서는 promote될 수 있지만 approved-only에서는 block되는 후보.

운영 관점에서는 이 목록이 가장 중요하다.  
여기서 duplicate/business/review pending 후보가 확인되면 approved-only 전환 필요성이 검증된다.

#### approved_only_candidates

approved-only에서는 eligible이지만 legacy path에서는 누락되는 후보.

이 목록은 과도한 block 여부를 점검하는 용도다.

#### false_positive_risk

들어가면 안 되는데 legacy path가 promote하려는 후보.

예:

- duplicate
- closed/suspicious business
- missing coordinate
- invalid role
- review pending

#### false_negative_risk

들어가도 되는데 approved-only가 과도하게 막는 후보.

예:

- image missing만 있는 유명 장소
- business status unknown이지만 source 신뢰도가 높은 후보

write는 절대 금지한다.

### 3. Sample Operator Review Scenario

운영자용 판단 예시는 복잡한 CMS 문서가 아니라 실제 의사결정 기준이어야 한다.

#### Scenario 1: duplicate 후보

상황:

- 이름이 기존 `places`와 동일
- 좌표가 150m 이내
- source id도 같거나 유사

판단:

- 같은 장소면 reject 또는 update candidate
- 다른 지점이면 manual review
- review note에 “동명 다른 지점” 근거 필요

결정:

```text
REVIEW_REQUIRED → REJECTED
```

또는:

```text
REVIEW_REQUIRED → APPROVED(candidate_update)
```

#### Scenario 2: image missing 후보

상황:

- 좌표/주소/source id는 정상
- image 없음
- 유명 장소 또는 신뢰 source

판단:

- 유명 장소면 manual review 후 approve 가능
- 일반 카페/식당이면 보류 또는 reject

결정:

```text
REVIEW_REQUIRED → APPROVED
```

또는:

```text
REVIEW_REQUIRED → REJECTED
```

#### Scenario 3: business status unknown 후보

상황:

- 폐업은 아님
- 운영 상태가 unknown
- 리뷰/이미지/주소는 정상

판단:

- source payload 확인
- 최근성 또는 last_seen 확인
- 불확실하면 promote 보류

결정:

```text
REVIEW_REQUIRED → manual hold
```

#### Scenario 4: 정상 approved 후보

상황:

- 좌표 정상
- image 있음
- duplicate risk 없음
- business safety safe
- QA PASS
- category/role 정상

결정:

```text
PENDING_REVIEW → APPROVED → PROMOTE_ELIGIBLE
```

### 4. Migration 이후 운영 흐름 최종 점검

권장 흐름:

```text
collect
→ raw_external_places
→ clean_external_places
→ staging_external_places
→ review
→ approved-only validator
→ final preview
→ promote
```

점검 결과:

- unnecessary state: 현재 상태 축은 과하지 않음
- reviewer confusion: `BLOCK_MISSING_IMAGE`, `needs_manual_review` 의미를 문서로 명확히 해야 함
- promote freeze loophole: legacy `--allow-promote`가 남아 있어 제거 전까지 위험
- uncontrolled write 가능성: legacy path가 남아 있는 한 완전히 제거되지 않음

따라서 migration 적용보다 shadow mode와 legacy path freeze 검증이 먼저다.

### 5. Raw Immutable 정책

raw layer는 immutable에 가깝게 유지한다.

원칙:

- raw overwrite 금지
- full reload 금지
- source response snapshot 유지
- raw row는 수집 시점 증거로 보존
- 같은 source id가 다시 들어와도 기존 raw를 덮어쓰지 않고 새 run으로 저장

이유:

- 외부 API 응답은 시간에 따라 변한다.
- 후보 품질 문제가 생겼을 때 어떤 payload에서 나온 후보인지 추적해야 한다.
- curated correction / family alignment / visibility tuning을 보호해야 한다.

### 6. Delta Update 정책

운영 업데이트는 full reload가 아니라 delta update를 기준으로 한다.

권장 기준:

```text
source_id + source + normalized_name + coordinate
```

상태:

- `first_seen_at`
- `last_seen_at`
- `last_verified_at`
- `business_status`
- `source_confidence`

처리 방향:

- 새 후보: staging candidate
- 기존 후보 재확인: candidate update
- source에서 사라진 후보: 즉시 삭제 금지
- 장기간 미확인 후보: inactive_candidate 검토
- 폐업 확인 후보: business safety block

중요:

- 운영 `places`에서 즉시 삭제하지 않는다.
- inactive 처리는 별도 review 후 진행한다.
- 기존 curated correction과 family alignment를 덮어쓰면 안 된다.

### 7. 운영 Slice Rehearsal 방향

첫 운영 리허설은 아래 순서로 한다.

1. 서울 카페 10개
2. 부산 식당 10개
3. 제주 실내 장소 10개

각 slice마다 확인:

- candidate_count
- duplicate risk
- image missing
- business status unknown/closed
- category risk
- approved candidate preview
- blocked reason counts
- operator 판단 소요 시간
- false positive/false negative 후보

성공 기준:

- 운영자가 report를 이해함
- block reason이 납득 가능함
- promote eligible 후보가 preview에서 명확함
- legacy would promote와 approved-only would promote 차이가 설명 가능함
- production `places` write 없음

### 8. 실제 migration 적용 전 최종 위험 요소

1. shadow mode 미구현
2. approve/reject persistence 미활성화
3. legacy promote path 존재
4. `--allow-promote` 오사용 가능성
5. EC2 host Python 실행 혼선
6. `BLOCK_MISSING_IMAGE` 해석 혼선
7. source freshness / last_seen 정책 미구현
8. inactive_candidate 정책 미구현

현재 결론:

```text
small slice rehearsal 준비는 가능하다.
하지만 production migration apply는 아직 보류한다.
다음 구현 우선순위는 shadow mode와 operator review guide 확정이다.
```

---

## 2026-05-18 추가: shadow mode 구현

이번 작업은 approved-only promote 전환 전 legacy promote 후보와 approved-only 후보를 write 없이 비교하기 위한 shadow mode 구현이다.  
production migration 실행, production `places` write, raw overwrite, full reload, 추천 엔진 수정은 수행하지 않았다.

### 1. Shadow mode 구현 내역

`batch/external/promote_external_places.py`에 다음 옵션을 추가했다.

```text
--shadow-mode
--run-id
--region
--limit
```

역할:

```text
legacy would promote
vs
approved-only would promote
```

비교를 수행하고, 어떤 후보가 legacy path에서는 들어갈 수 있지만 approved-only gate에서는 막히는지 출력한다.

출력 필드:

- `legacy_candidate_count`
- `approved_eligible_count`
- `legacy_only_candidates`
- `approved_only_candidates`
- `blocked_reason_counts`
- `false_positive_risk`
- `false_negative_risk`
- `operator_report`
- `safety_summary`

`batch/update_all.sh`에도 다음 옵션을 추가했다.

```text
--shadow-mode
```

해당 옵션은 candidate review report와 QA 이후 shadow mode preview까지만 실행하고 종료한다.  
promote는 수행하지 않는다.

### 2. Approved-only 계산 방식

`staging_external_places`가 존재하면:

```text
staging_external_places 기반 approved-only precondition 검사
```

`staging_external_places`가 아직 없으면:

```text
clean_external_places 기반 simulation fallback
```

으로 동작한다.

simulation fallback임은 출력의 `approved_only_source`에 명시된다.

### 3. Sample Shadow Mode 출력

sample run:

```text
run_id = 72e04e7b-62e6-447b-a091-ceefe5560ec8
region = 서울
limit = 5
```

결과 요약:

```json
{
  "mode": "shadow_mode",
  "approved_only_source": "clean_external_places simulation",
  "legacy_candidate_count": 5,
  "approved_eligible_count": 0,
  "legacy_only_count": 5,
  "approved_only_count": 0,
  "blocked_reason_counts": {
    "BLOCK_DUPLICATE_RISK": 5,
    "BLOCK_MISSING_IMAGE": 5
  }
}
```

해석:

- legacy path 기준으로는 5개 후보가 promote 가능 후보로 보임
- approved-only simulation에서는 5개 모두 block
- block reason은 duplicate risk와 missing image
- production `places` write 없음

### 4. False Positive / False Negative 판단

#### false_positive_risk

legacy는 promote하려 하지만 approved-only가 block하는 후보.

위 sample에서는 legacy 후보 5개가 모두 false positive risk로 분류된다.

대표 block reason:

- `BLOCK_DUPLICATE_RISK`
- `BLOCK_MISSING_IMAGE`

운영 판단:

- duplicate risk는 반드시 수동 검토 필요
- image missing은 hard reject는 아니지만 품질 review 필요

#### false_negative_risk

approved-only가 과도하게 막을 수 있는 후보.

현재 sample에서는 image missing과 duplicate 단독 block 후보를 false negative risk 후보로도 볼 수 있다.  
다만 운영 DB 오염 방지 관점에서는 false negative보다 false positive가 더 위험하다.

### 5. Operator Report 개선

shadow mode candidate 출력에는 다음 필드를 포함한다.

- candidate name
- source
- category
- region
- block reason
- legacy decision
- approved-only decision
- recommended operator action

대표 action:

- `manual_duplicate_review_required`
- `manual_quality_review_required`
- `reviewer_approval_required`
- `reject_or_fix_source_before_review`
- `preview_only_no_write`

### 6. Small Slice Smoke 결과

이번 단계에서는 신규 API 수집 확대를 하지 않았다.  
이미 존재하는 `clean_external_places` / `staging_places` sample run 기준으로 smoke를 수행했다.

확인된 것:

- shadow mode 실행 가능
- legacy candidate 계산 가능
- approved-only simulation fallback 가능
- blocked reason visibility 가능
- false positive risk visibility 가능
- write 없음

아직 수행하지 않은 것:

- 서울 카페 10개 신규 slice 수집
- 부산 식당 10개 신규 slice 수집
- 제주 실내 장소 10개 신규 slice 수집

이 세 slice는 migration/persistence 전환 전 별도 운영 리허설에서 수행한다.

### 7. 검증 결과

수행:

```text
python -m py_compile
promote_external_places.py --shadow-mode --help
promote_external_places.py --shadow-mode --run-id ... --region 서울 --limit 5
update_all.sh --help
```

확인:

- shadow mode 실행 가능
- DB write 없음
- production `places` row write 없음
- migration 실행 없음
- raw overwrite 없음
- full reload 없음
- saju 영향 없음

### 8. 다음 단계 권고

1. operator review guide를 실제 운영자가 읽고 혼동 지점 확인
2. shadow mode 결과를 CSV/Markdown report로 저장하는 옵션 추가
3. small slice 3종을 실제 source 기준으로 dry-run 수집
4. migration 적용 전 `staging_external_places` 없는 fallback 결과와 migration 후 결과 비교
5. 그 다음에만 migration 적용 여부 판단

---

## 2026-05-18 추가: shadow report 저장 / small slice 준비

이번 작업은 shadow mode 결과를 운영자가 실제 검토 가능한 파일로 저장하고, small slice rehearsal 3종 실행 준비 상태를 정리한 단계다.  
production migration 실행, production `places` write, raw overwrite, full reload, 추천 엔진 수정은 수행하지 않았다.

### 1. Shadow Report 저장 구현 내역

`batch/external/promote_external_places.py`에 shadow mode report 저장 옵션을 추가했다.

옵션:

```text
--shadow-mode
--report
--output-dir qa_reports/shadow_mode
```

출력 형식:

- JSON
- CSV
- Markdown

파일명:

```text
shadow_mode_{run_id}_{region}_{timestamp}.json
shadow_mode_{run_id}_{region}_{timestamp}.csv
shadow_mode_{run_id}_{region}_{timestamp}.md
```

`batch/update_all.sh`에도 다음 옵션을 추가했다.

```text
--shadow-mode
--shadow-report
--shadow-output-dir
```

동작:

```text
candidate review report
→ QA
→ shadow mode
→ shadow report 저장
→ 종료
```

promote는 수행하지 않는다.

### 2. 생성된 Sample Report 경로

sample 실행:

```text
run_id = 72e04e7b-62e6-447b-a091-ceefe5560ec8
region = 서울
limit = 5
```

출력 경로:

```text
qa_reports/shadow_mode_smoke/
```

생성 파일:

```text
shadow_mode_72e04e7b-62e6-447b-a091-ceefe5560ec8_서울_YYYYMMDD_HHMMSS.json
shadow_mode_72e04e7b-62e6-447b-a091-ceefe5560ec8_서울_YYYYMMDD_HHMMSS.csv
shadow_mode_72e04e7b-62e6-447b-a091-ceefe5560ec8_서울_YYYYMMDD_HHMMSS.md
```

### 3. Markdown Report 예시 요약

Markdown report에는 다음이 포함된다.

- run_id
- region
- approved_only_source
- legacy_candidate_count
- approved_eligible_count
- legacy_only_count
- approved_only_count
- false_positive_risk_count
- false_negative_risk_count
- blocked_reason_counts
- candidate review table
- operator notes
- safety summary

sample 요약:

```text
legacy_candidate_count = 5
approved_eligible_count = 0
legacy_only_count = 5
approved_only_count = 0
BLOCK_DUPLICATE_RISK = 5
BLOCK_MISSING_IMAGE = 5
```

### 4. Operator Confusion 방지 문구

Markdown report 하단에 다음 문구를 넣었다.

```text
BLOCK_DUPLICATE_RISK: 기존 places와 중복 가능성. 자동 approve 금지.
BLOCK_MISSING_IMAGE: 즉시 reject는 아니지만 품질 review 필요.
REVIEW_REQUIRED: 사람이 판단해야 하며 자동 promote 금지.
PROMOTE_ELIGIBLE: final preview 확인 전 write 금지.
--allow-promote는 일반 운영 옵션이 아니라 legacy escape hatch.
```

### 5. Small Slice별 가능 / 불가 상태

이번 단계에서는 신규 API 수집 확대를 하지 않았다.  
기존 `clean_external_places` 기준으로 확인 가능한 범위만 본다.

#### 서울 카페 10개

상태:

- 부분 가능
- 현재 sample run에 서울 cafe 후보 일부 존재
- 다만 정확히 10개 slice를 만들려면 추가 dry-run/수집 필요

예상 확인 가능 항목:

- duplicate risk
- missing image
- source id
- category/role

#### 부산 식당 10개

상태:

- 현재 sample clean 데이터만으로는 부족 가능성 높음
- 추가 소량 수집 필요

주의:

- generic meal contamination 확인에 적합
- raw overwrite 없이 새 run으로 delta 수집해야 함

#### 제주 실내 장소 10개

상태:

- 현재 sample clean 데이터만으로는 부족 가능성 높음
- 추가 소량 수집 필요

주의:

- culture/indoor category risk 확인에 적합
- 운영시간/business status unknown 비율 확인 필요

### 6. 검증 결과

수행:

```text
python -m py_compile
promote_external_places.py --shadow-mode --report --help
promote_external_places.py --shadow-mode --report --output-dir qa_reports/shadow_mode_smoke
update_all.sh --help
places row count before/after
```

확인:

- shadow report JSON/CSV/MD 생성 가능
- production `places` row count 변화 없음
- migration 실행 없음
- raw overwrite 없음
- full reload 없음
- saju 영향 없음

### 7. 다음 단계 권고

1. shadow report를 운영자가 실제로 읽고 혼동 지점 확인
2. 서울 카페 10개 / 부산 식당 10개 / 제주 실내 10개를 새 run으로 소량 수집
3. 각 run에 대해 shadow report 생성
4. false positive / false negative를 사람이 검토
5. 그 결과가 안정적이면 migration 적용 여부 재판단

## 2026-05-18 추가: 서울 카페 small slice shadow validation

### 목적

approved-only promote 운영 전환 전 첫 번째 실제 small slice rehearsal로 `서울 + cafe` 후보를 shadow mode에서 검증했다. 이번 실행은 production migration, production places write, raw overwrite, full reload 없이 기존 `clean_external_places` / `staging_places` 데이터만 사용했다.

### 실행 범위

- run_id: `72e04e7b-62e6-447b-a091-ceefe5560ec8`
- region: `서울`
- visit_role: `cafe`
- limit: `10`
- output_dir: `qa_reports/shadow_mode_seoul_cafe`
- approved_only_source: `clean_external_places simulation`
- 신규 API 수집: 없음
- raw overwrite: 없음
- full reload: 없음
- production places write: 없음

기존 데이터에서 `서울 + cafe` 후보는 2건만 존재했다. 10건 slice를 채우려면 신규 소량 수집 write가 필요하지만, 이번 요청의 `DB write 없음` 조건과 충돌하므로 실제 검증은 2건으로 제한했다.

### Shadow Mode 결과

| 항목 | 값 |
|---|---:|
| legacy_candidate_count | 2 |
| approved_eligible_count | 0 |
| legacy_only_count | 2 |
| approved_only_count | 0 |
| false_positive_risk_count | 2 |
| false_negative_risk_count | 0 |

blocked reason:

| reason | count |
|---|---:|
| BLOCK_DUPLICATE_RISK | 2 |
| BLOCK_MISSING_IMAGE | 2 |

### 생성된 Report

EC2 host 기준:

```text
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe/shadow_mode_72e04e7b-62e6-447b-a091-ceefe5560ec8_서울_cafe_20260518_043939.json
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe/shadow_mode_72e04e7b-62e6-447b-a091-ceefe5560ec8_서울_cafe_20260518_043939.csv
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe/shadow_mode_72e04e7b-62e6-447b-a091-ceefe5560ec8_서울_cafe_20260518_043939.md
```

### 후보별 판단

| 후보 | legacy decision | approved-only decision | block reason | 권장 action |
|---|---|---|---|---|
| 만월다방 시네마 | WOULD_PROMOTE | BLOCKED | BLOCK_DUPLICATE_RISK, BLOCK_MISSING_IMAGE | manual duplicate review |
| 모센트 용산점 | WOULD_PROMOTE | BLOCKED | BLOCK_DUPLICATE_RISK, BLOCK_MISSING_IMAGE | manual duplicate review |

### False Positive Risk

이번 slice에서 legacy path의 위험이 실제로 확인됐다.

- 두 후보 모두 legacy 기준에서는 promote 가능 후보로 잡혔다.
- approved-only 기준에서는 중복 가능성과 이미지 부재 때문에 모두 block됐다.
- 따라서 legacy path를 그대로 열어두면 중복/품질 미확인 카페가 production places로 들어갈 수 있다.

### False Negative Risk

이번 slice에서는 `false_negative_risk`가 0건이었다.

다만 slice가 2건뿐이라 “approved-only가 과도하게 좋은 후보를 막고 있다”는 판단을 내리기에는 데이터가 부족하다. false negative 판단은 서울 카페 10건 이상, 부산 식당 10건, 제주 실내 10건 slice가 확보된 뒤 다시 보는 것이 맞다.

### Operator Review Simulation

1. 중복 후보: `만월다방 시네마`
   - 상태: `BLOCK_DUPLICATE_RISK`, `BLOCK_MISSING_IMAGE`
   - 판단: 자동 approve 금지
   - 운영 action: 기존 places와 이름/좌표/source id 비교 후 중복이면 reject, 다른 지점이면 image 품질 검토 후 manual approve 후보로 분류

2. 이미지 누락 후보: `모센트 용산점`
   - 상태: `BLOCK_DUPLICATE_RISK`, `BLOCK_MISSING_IMAGE`
   - 판단: 이미지 없음만으로 즉시 reject는 아니지만, 중복 risk가 같이 있으므로 manual review 필요
   - 운영 action: 기존 places 중복 여부를 먼저 확인하고, 중복이 아니면 이미지 보강 가능성 또는 대표성 기준으로 approve/reject 결정

3. 정상 후보
   - 이번 서울 카페 slice에는 `PROMOTE_ELIGIBLE` 정상 후보가 없었다.
   - fake 정상 예시를 만들지 않는다.
   - 다음 rehearsal에서 정상 후보가 포함되도록 소량 신규 수집 slice를 별도 run으로 준비해야 한다.

### Migration Readiness 재판단

이번 slice 기준 판단:

- approved-only gate 자체는 정상 작동한다.
- legacy path 위험은 실제 후보 기준으로 확인됐다.
- operator report는 후보별 block reason과 action을 읽을 수 있는 형태다.
- 하지만 서울 카페 기존 slice가 2건뿐이라 migration GO 판단에는 부족하다.
- migration apply 전 최소 조건은 “각 slice별 10건 내외 report + 정상 후보/blocked 후보가 모두 포함된 operator review”다.

현재 판단: migration apply는 계속 NO-GO.

### 검증

- `python -m py_compile`: 통과
- `promote_external_places.py --shadow-mode --report --visit-role cafe`: 정상
- `update_all.sh --help`: `--visit-role`, `--shadow-report`, `--shadow-output-dir` 확인
- production `places` row count: `26381`, 변화 없음
- migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- saju 영향 없음

### 다음 단계 권고

1. 서울 카페 10건을 채우기 위한 소량 delta 수집 run을 별도로 준비한다.
2. 단, raw overwrite/full reload 없이 새 run_id 기준으로만 수집한다.
3. 부산 식당 10건, 제주 실내 10건도 동일 방식으로 small slice를 만든다.
4. 세 slice에서 `PROMOTE_ELIGIBLE`, `BLOCK_DUPLICATE_RISK`, `BLOCK_MISSING_IMAGE`, `REVIEW_REQUIRED`가 모두 관찰될 때 migration go/no-go를 다시 판단한다.

## 2026-05-19 추가: 서울 카페 delta slice shadow validation

### 목적

서울 카페 후보가 기존 2건뿐이라, raw overwrite/full reload 없이 새 `run_id` 기반 소량 delta 수집을 수행하고 approved-only shadow validation을 다시 실행했다.

이번 단계의 목적은 `PROMOTE_ELIGIBLE` 정상 후보가 실제로 생기는지 확인하는 것이었다. production migration, production `places` write, legacy promote write는 수행하지 않았다.

### 실행 정보

- 신규 run_id: `b5ebd247-6601-4e81-9873-db07fd2c6d77`
- region: `서울`
- visit_role: `cafe`
- keywords: `카페,커피,디저트`
- anchor: 서울 중심 좌표
- radius: `12km`
- max_total: `15`
- source: `kakao,naver`
- output_dir: `qa_reports/shadow_mode_seoul_cafe_delta`

주의할 점:

- Kakao 요청은 `HTTP 401 Unauthorized`로 실패했다.
- 실제 후보는 Naver local search 기반으로만 수집됐다.
- raw row는 새 run_id 기준 append이며 기존 raw overwrite/full reload는 수행하지 않았다.

### 수집 / Clean / Stage 결과

| 단계 | 결과 |
|---|---:|
| fetched_count | 12 |
| raw inserted_count | 10 |
| clean_count | 7 |
| clean inserted_count | 7 |
| invalid_count | 3 |
| staged_count | 7 |
| staged cafe role count | 7 |

### Shadow Mode 결과

| 항목 | 값 |
|---|---:|
| legacy_candidate_count | 7 |
| approved_eligible_count | 0 |
| legacy_only_count | 7 |
| approved_only_count | 0 |
| false_positive_risk_count | 0 |
| false_negative_risk_count | 7 |

blocked reason:

| reason | count |
|---|---:|
| BLOCK_MISSING_IMAGE | 7 |

### 생성된 Report

EC2 host 기준:

```text
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe_delta/shadow_mode_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_222536.json
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe_delta/shadow_mode_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_222536.csv
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe_delta/shadow_mode_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_222536.md
```

로컬 workspace에도 동일 파일을 복사했다.

```text
qa_reports/shadow_mode_seoul_cafe_delta/
```

### 후보 목록

| 후보 | source | approved-only decision | block reason | operator action |
|---|---|---|---|---|
| 낫배드커피 도산 | naver | BLOCKED | BLOCK_MISSING_IMAGE | manual_quality_review_required |
| 젠젠 성수점 | naver | BLOCKED | BLOCK_MISSING_IMAGE | manual_quality_review_required |
| 레자미오네뜨 | naver | BLOCKED | BLOCK_MISSING_IMAGE | manual_quality_review_required |
| 카페 공명 연남점 | naver | BLOCKED | BLOCK_MISSING_IMAGE | manual_quality_review_required |
| 아쿠아산타 성수카페 | naver | BLOCKED | BLOCK_MISSING_IMAGE | manual_quality_review_required |
| 어퍼앤언더 | naver | BLOCKED | BLOCK_MISSING_IMAGE | manual_quality_review_required |
| 크림시크 | naver | BLOCKED | BLOCK_MISSING_IMAGE | manual_quality_review_required |

### PROMOTE_ELIGIBLE 확인

`PROMOTE_ELIGIBLE` 후보는 0건이다.

원인은 candidate 품질이 전부 나쁘다는 뜻이라기보다, 현재 Naver local search 수집 경로가 `image_url`을 공급하지 않는 구조이기 때문이다. approved-only gate는 `BLOCK_MISSING_IMAGE`를 review 필요 상태로 보고 promote eligible에서 제외한다.

따라서 현재 상태에서는 “서울 카페 후보를 더 모으는 것”만으로는 approved-only 정상 통과 후보를 만들기 어렵다. image availability를 별도 source에서 보강하거나, `BLOCK_MISSING_IMAGE`를 hard block이 아닌 reviewer-review state로 분리하는 정책 결정이 필요하다.

### False Positive / False Negative 분석

#### False Positive Risk

이번 delta slice의 `false_positive_risk`는 0건이다.

- 중복 위험 후보는 발견되지 않았다.
- closed/business risk 후보도 발견되지 않았다.
- legacy가 위험 후보를 promote하려는 케이스는 이번 slice에서는 확인되지 않았다.

#### False Negative Risk

이번 delta slice의 `false_negative_risk`는 7건이다.

- 모든 후보가 `BLOCK_MISSING_IMAGE` 단일 사유로 막혔다.
- 이미지가 없다는 이유만으로 유명/정상 카페까지 전부 promote eligible에서 제외될 가능성이 있다.
- 이 상태로 approved-only cutover를 진행하면 “운영 DB 오염 방지”는 강하지만, 정상 후보 유입이 과도하게 막힐 수 있다.

### Operator Review Simulation

1. 정상 approve 후보
   - 이번 delta slice에는 `PROMOTE_ELIGIBLE` 후보가 없다.
   - 정상 approve 시나리오는 아직 실제 후보로 검증하지 못했다.
   - fake 정상 후보를 만들지 않는다.

2. duplicate reject 후보
   - 이번 delta slice에는 duplicate risk 후보가 없다.
   - 직전 서울 카페 slice의 `만월다방 시네마`, `모센트 용산점`은 duplicate risk 예시로 유지한다.
   - 운영 action: 기존 places와 source/name/좌표 비교 후 중복이면 reject.

3. image review 후보
   - 이번 delta slice의 7건 전부 해당한다.
   - 예: `낫배드커피 도산`, `젠젠 성수점`, `카페 공명 연남점`
   - 운영 action: 즉시 reject보다는 이미지 보강 가능성, 대표성, 중복 여부를 수동 확인한 뒤 approve/reject 판단.

### Migration Readiness 판단 변화

현재 판단: migration apply는 계속 NO-GO.

이유:

1. approved-only gate는 정상 작동한다.
2. shadow report도 운영자가 읽을 수 있는 형태로 생성된다.
3. 하지만 image metadata가 비어 있어 `PROMOTE_ELIGIBLE`이 0건이다.
4. 이 상태로 cutover하면 external candidate 유입이 거의 막힐 가능성이 있다.

다음 의사결정이 필요하다.

- A안: Kakao/Naver 외부 후보에 image enrichment source를 추가한 뒤 다시 rehearsal
- B안: `BLOCK_MISSING_IMAGE`를 promote hard block이 아니라 `REVIEW_REQUIRED`로 남기되, reviewer가 명시 approve하면 통과 가능하도록 정책 완화
- C안: image 없는 후보는 계속 block하되, image source 확보 전까지 approved-only migration apply를 보류

운영 DB 오염 방지 관점에서는 C안이 가장 안전하다. 다만 후보 유입 플랫폼으로 전환하려면 A안 또는 B안 중 하나는 필요하다.

### 검증

- production `places` row count: `26381`, 변화 없음
- production migration 실행 없음
- production places write 없음
- legacy promote write 없음
- raw overwrite 없음
- full reload 없음
- shadow report JSON/CSV/MD 생성 확인
- travel/saju containers running 확인
- saju 영향 없음

## 2026-05-19 추가: image enrichment 공급망 초안

### 목적

approved-only promote 구조는 유지하되, 현재 최대 blocker인 `BLOCK_MISSING_IMAGE` 반복 문제를 해결하기 위한 image metadata 공급망을 설계한다. 이번 단계에서는 production migration, production places write, raw overwrite, full reload, approved-only 완화, 추천 엔진 수정은 수행하지 않았다.

### 현재 Image 공급 구조 Audit

#### DB 컬럼 상태

운영 DB 기준 image 관련 컬럼은 다음과 같다.

| table | image / quality column 상태 |
|---|---|
| `raw_external_places` | image 관련 컬럼 없음 |
| `clean_external_places` | image 관련 컬럼 없음 |
| `staging_places` | `first_image_url`, `first_image_thumb_url` 존재 |
| `places` | `first_image_url`, `first_image_thumb_url`, `rating`, `review_count`, `opening_hours`, `source_confidence` 존재 |

즉, production `places`와 legacy `staging_places`는 image를 받을 수 있지만, external raw/clean 단계에서 image metadata를 보존하는 통로가 아직 없다.

#### Delta raw payload 확인

서울 카페 delta run `b5ebd247-6601-4e81-9873-db07fd2c6d77` 기준 raw payload sample key:

```text
address
category
description
link
mapx
mapy
roadAddress
telephone
title
```

`image`, `thumbnail`, `photo`, `first_image_url` 계열 key는 없었다.

clean payload 확인:

```text
clean rows = 7
normalized_payload.image_url = 0
normalized_payload.first_image_url = 0
```

### Image Metadata 유실 지점

현재는 “중간 유실”보다 “원천 미공급”에 가깝다.

1. Naver local search 응답 자체에 image field가 없다.
2. Kakao local keyword/category 응답도 장소명, 주소, 좌표, 카테고리, 전화번호, 상세 URL 중심이다.
3. raw/clean migration draft에는 image 컬럼 proposal이 있지만 production DB에는 아직 적용되지 않았다.
4. `clean_external_places.py`는 raw payload에서 image를 보존하지 않는다.
5. `enrich_external_places.py`는 `staging_places.first_image_url`에 값을 넣을 경로가 없다.
6. `stage_external_candidates.py`는 `image_url`, `image_thumb_url`, `normalized_payload.image_url`, `normalized_payload.first_image_url` 중 하나가 있어야 image available로 판단한다.

결론: 현재 `BLOCK_MISSING_IMAGE`는 approved-only validator가 과도해서만 생기는 문제가 아니다. external candidate 공급망이 image metadata를 제공하지 못하는 구조적 blocker다.

### 외부 Source 후보

공식 문서 기준:

- Kakao Local keyword/category API는 장소 ID, 장소명, 카테고리, 전화번호, 주소, 좌표, `place_url` 중심으로 응답한다.
  - 참고: https://developers.kakao.com/docs/latest/ko/local/dev-guide
- Naver Search Image API는 이미지 검색 결과에서 `link`, `thumbnail`, size 정보를 제공한다.
  - 참고: https://developers.naver.com/docs/serviceapi/search/image/image.md

#### 후보 Source별 판단

| source | 가능성 | 장점 | 리스크 / 한계 | 권장 |
|---|---|---|---|---|
| Kakao Local `place_url` | 중간 | 장소 상세 URL 확보 가능 | 상세 페이지 scraping은 약관/운영 리스크 검토 필요 | 구현 보류, 법무/약관 확인 |
| Kakao Local image field | 낮음 | 장소 source와 동일 | local 응답 field에 image 없음 | source로 기대하지 않음 |
| Naver Local Search | 낮음 | 현재 사용 중 | local 응답에 image 없음 | image source로는 부족 |
| Naver Image Search API | 중간 | `thumbnail` 제공 | 장소 이미지 정확도 검증 필요, 저작권/출처/핫링크 정책 검토 필요 | 후보로 검토 |
| place_url scraping | 낮음 | 실제 장소 상세 image 가능성 | scraping/약관/차단/저장 리스크 큼 | 이번 phase 구현 금지 |
| curated fallback image | 중간 | 대표 landmark/district 품질 보강 가능 | generic/fake 이미지 위험, 장소별 정확도 낮음 | 대표 district/landmark 한정 |
| external media enrichment source | 중간 | 이미지/평점/리뷰 보강 가능 | 비용/약관/저장 정책 검토 필요 | 별도 PoC 후보 |

### Image Enrichment Pipeline 초안

권장 흐름:

```text
raw_external_places
→ clean_external_places
→ image_enrichment_candidates
→ image_validation
→ staging_external_places
→ review
→ approved-only promote preview
```

#### 추가 개념

image enrichment 단계에서 최소 다음 필드를 별도로 관리한다.

| 필드 | 목적 |
|---|---|
| `image_source` | naver_image, kakao_place_url, curated, external_media 등 |
| `image_url` | 원본 또는 사용 가능한 대표 URL |
| `image_thumb_url` | 카드용 thumbnail |
| `image_confidence` | 장소명/주소/카테고리 매칭 신뢰도 |
| `image_verified_at` | 검증 시각 |
| `image_hash` | 중복/변경 감지 |
| `is_curated_image` | curated fallback 여부 |
| `is_fallback_image` | 장소 exact image가 아닌 fallback 여부 |
| `image_license_note` | 저장/노출 가능성 및 출처 메모 |
| `image_review_status` | pending, approved, rejected, needs_manual_review |

#### 검증 조건

image candidate는 다음을 통과해야 한다.

1. 후보 장소명 또는 alias와 image title/source text가 맞는다.
2. region/address가 크게 벗어나지 않는다.
3. 금지 source나 불명확한 무단 저장 source가 아니다.
4. 이미지 URL이 실제 응답한다.
5. placeholder/fallback이면 정확한 장소 이미지로 오인되지 않도록 별도 flag를 둔다.

### `BLOCK_MISSING_IMAGE` 정책 비교

| 정책 | 설명 | 장점 | 단점 | 현재 판단 |
|---|---|---|---|---|
| A안: hard block 유지 | image 없으면 promote 불가 | 운영 DB 품질 보호 강함 | 정상 후보 유입 거의 차단 | 가장 안전하지만 플랫폼 전환 속도 낮음 |
| B안: `REVIEW_REQUIRED` + reviewer approve 가능 | image 없어도 사람이 명시 승인하면 통과 | 정상 후보 false negative 감소 | 운영자 판단 부담 증가, 이미지 없는 카드 품질 저하 가능 | image source 확보 전 임시 대안 |
| C안: 대표 district/landmark만 curated fallback 허용 | 대표 후보에 한해 curated image 사용 | UX 품질 보강 가능 | 장소 exact image가 아니면 신뢰 리스크 | 제한 적용 가능 |

권장:

1. migration 전에는 A안 유지.
2. image enrichment PoC 후에도 image가 부족하면 B안을 “reviewer 명시 승인 + 품질 note 필수” 조건으로만 허용.
3. C안은 해동용궁사처럼 대표 landmark 또는 district hero 성격에만 제한하고, 일반 카페 대량 후보에는 적용하지 않는다.

### 서울 카페 Delta Slice 재평가

서울 카페 delta 후보 7건:

- 낫배드커피 도산
- 젠젠 성수점
- 레자미오네뜨
- 카페 공명 연남점
- 아쿠아산타 성수카페
- 어퍼앤언더
- 크림시크

공통 상태:

- source: Naver
- role: cafe
- 좌표/카테고리 기본 valid
- duplicate risk 없음
- business closed risk 없음
- block reason: `BLOCK_MISSING_IMAGE`

운영자 관점:

- 이 후보들은 즉시 reject 대상이라기보다 image review 대상이다.
- 다만 이미지 없는 카페 후보를 production `places`로 promote하면 카드 품질 문제가 바로 발생한다.
- 현재 approved-only가 모두 막은 것은 운영 DB 오염 방지 관점에서는 맞다.
- 하지만 “정상 후보도 통과 가능한가”를 검증하려면 image enrichment가 선행돼야 한다.

### Migration Readiness 영향

현재 판단: migration apply 계속 NO-GO.

사유:

1. approved-only shadow/report는 작동한다.
2. duplicate/business/coordinate guard도 작동한다.
3. 하지만 image supply가 없어 정상 후보가 `PROMOTE_ELIGIBLE`로 전환되지 않는다.
4. 이 상태로 cutover하면 운영 DB 오염은 막지만 external data 유입 플랫폼은 사실상 멈춘다.

운영 전환 전 blocker:

- image enrichment source 결정
- image metadata 저장 컬럼/migration 확정
- `BLOCK_MISSING_IMAGE`를 hard block으로 유지할지, reviewer-approved 예외를 둘지 결정
- image 없는 후보의 UX 품질 기준 확정

### 다음 단계 권고

1. Naver Image Search API를 이용한 `image_enrichment_candidates` dry-run PoC를 만든다.
   - query: `{place_name} {region} 카페`
   - write 금지
   - image URL / thumbnail / title / source link / confidence만 report
2. Kakao key 401 문제를 먼저 해결한다.
   - Kakao Local은 image source는 아니지만 source diversity와 place_url 확보에 필요하다.
3. `BLOCK_MISSING_IMAGE`는 지금 바로 완화하지 않는다.
   - 먼저 image enrichment PoC 후 false negative를 다시 본다.
4. image enrichment 결과까지 포함한 서울 카페 slice shadow validation을 재실행한다.
5. 그 결과 `PROMOTE_ELIGIBLE` 정상 후보가 실제로 생길 때 migration readiness를 다시 판단한다.

### 검증

- production `places` row count: `26381`, 변화 없음
- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- approved-only 완화 없음
- 추천 엔진 수정 없음
- saju 영향 없음

## 2026-05-19 추가: image approve/reject write rehearsal

### 목표

image review persistence 구조를 실제 migration 없이 운영 전환 직전 수준으로 검증하기 위해 approve/reject write rehearsal을 추가했다. 이 rehearsal은 어떤 row가 어떤 상태로 저장될 예정인지 payload를 생성하지만 DB write는 수행하지 않는다.

### 구현 내용

대상:

- `batch/external/review_image_candidates.py`

추가 옵션:

- `--persistence-rehearsal`
- `--simulate-write`
- `--approve-image`
- `--reject-image`
- `--reviewer`
- `--review-note`
- `--image-license-note`

동작:

- `--simulate-write`는 이름 그대로 simulation only다.
- 실제 `--write`와 무관하게 DB write는 계속 차단한다.
- approve/reject 대상 후보를 report row에서 찾아 `planned_staging_external_places_update`와 `planned_image_enrichment_candidate_record`를 생성한다.
- approve rehearsal은 `image_review_status='approved'` payload를 만든다.
- reject rehearsal은 confidence/source risk에 따라 `rejected`, `blocked_license`, `low_confidence` payload를 만든다.

### approve rehearsal payload 예시

```json
{
  "write_mode": "SIMULATION_ONLY",
  "db_write": false,
  "action": "approve_image",
  "candidate": "낫배드커피 도산",
  "candidate_found": true,
  "image_review_status": "approved",
  "image_source": "naver_image_search",
  "image_license_note": "naver_image_search_preview_only",
  "image_reviewer": "operator_a",
  "image_review_note": "HIGH confidence thumbnail verified",
  "promote_validator_effect": {
    "block_missing_image_cleared": true
  }
}
```

### reject rehearsal payload 예시

```json
{
  "write_mode": "SIMULATION_ONLY",
  "db_write": false,
  "action": "reject_image",
  "candidate": "레자미오네뜨",
  "candidate_found": true,
  "image_review_status": "blocked_license",
  "image_block_reason": "license_source_risk",
  "promote_validator_effect": {
    "block_missing_image_cleared": false
  }
}
```

### validator 영향

정책은 유지했다.

```text
BLOCK_MISSING_IMAGE 직접 완화 금지.

다만 rehearsal상 approve payload가 아래 조건을 모두 만족하면
향후 approved-only validator에서 image block 해제 후보로 볼 수 있다.

image_review_status = approved
image_url exists
image_license_note exists
```

### 결과 report

로컬 report:

```text
qa_reports/image_review_persistence_rehearsal/
```

EC2 report:

```text
/home/ubuntu/travel_service_prod/qa_reports/image_review_persistence_rehearsal/
```

### 운영 판단

image persistence flow는 운영자가 이해 가능한 수준으로 리허설 가능해졌다.

하지만 migration apply는 아직 NO-GO다.

남은 blocker:

1. migration 적용 승인
2. 실제 `image_enrichment_candidates` / `staging_external_places` write 구현
3. reviewer action audit trail 확정
4. approved-only validator가 DB의 image review status를 직접 읽도록 전환

### 검증 상태

- `python -m py_compile batch/external/review_image_candidates.py`: 통과
- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- image 자동 approve 없음
- `BLOCK_MISSING_IMAGE` 직접 완화 없음
- saju 영향 없음

## 2026-05-19 추가: approved-only pre-cutover rehearsal

### 목표

approved-only promote cutover 직전 기준으로 운영자가 실제 전환을 안전하게 수행할 수 있는지 마지막 rehearsal을 수행했다.

이번 단계에서도 production migration, production places write, raw overwrite, full reload, scraping, docker compose down은 수행하지 않았다.

### pre-cutover checklist

| 항목 | 상태 |
|---|---|
| candidate_only=true | OK |
| no_promote=true | OK |
| review_required=true | OK |
| legacy promote freeze default | OK |
| shadow mode | OK |
| image review rehearsal | OK |
| container execution standard | OK |
| `--allow-promote` 완전 차단 | NO |

중요 판단:

`--allow-promote`는 기본값으로는 막혀 있지만 코드상 legacy escape hatch로 남아 있다. 따라서 cutover 전 “완전 차단”이라고 볼 수 없다. 운영 전환 전에는 이 경로를 제거하거나 별도 운영 승인 조건으로 더 잠가야 한다.

### promote cutover simulation

simulation flow:

```text
legacy staging path active but frozen
→ staging_external_places migration assumed
→ approved-only validator
→ image review persistence assumed
→ approved-only promote preview
→ no write
```

결과:

| 항목 | 결과 |
|---|---:|
| legacy_candidate_count | 7 |
| approved_eligible_count | 0 |
| image_review_adjusted_eligible_count | 4 |
| image_approved_candidate_count | 4 |
| remaining BLOCK_MISSING_IMAGE | 3 |

approved preview candidates:

- 낫배드커피 도산
- 젠젠 성수점
- 카페 공명 연남점
- 크림시크

blocked candidates:

- 레자미오네뜨
- 아쿠아산타 성수카페
- 어퍼앤언더

report:

```text
qa_reports/pre_cutover_staging_image_rehearsal/
```

### reviewer rollback simulation

검증한 rollback 흐름:

```text
approved → needs_manual_review
approved → blocked_license
approved → quarantine
```

판단:

- reviewer 실수는 places write 전에 staging row에서 되돌리는 것이 원칙이다.
- `image_review_status='approved'`를 `needs_manual_review`, `rejected`, `blocked_license`로 바꾸면 promote eligibility에서 제외된다.
- source/license 문제가 발견되면 `blocked_license`와 `image_block_reason`을 남기고 shadow mode를 재실행해야 한다.
- quarantine 상태는 `BLOCK_MISSING_IMAGE` 해제 대상이 아니다.

### final operator confusion points

- `BLOCK_MISSING_IMAGE`: image가 없거나 reviewer-approved image가 없다는 뜻이다. 즉시 reject는 아니지만 promote 금지.
- `IMAGE_APPROVED`: reviewer가 staging candidate image를 승인한 상태다. final preview 전 write 금지.
- `IMAGE_LOW_CONFIDENCE_REVIEW`: 낮은 confidence이므로 자동 승인 금지. manual review 또는 block.
- `blocked_license`: source/license risk. promote 금지, blacklist 업데이트 후보.
- `REVIEW_REQUIRED`: 사람 판단 전 자동 promote 금지.
- `PROMOTE_ELIGIBLE`: preview상 가능하다는 뜻이지 write 승인 의미가 아니다.
- `quarantine`: `needs_manual_review` 또는 `blocked_license`로 격리 후 shadow mode 재실행.

### migration GO/NO-GO 판단

최종 판단: 아직 NO-GO.

이유:

1. production migration 미적용
2. 실제 staging image review persistence write 미구현
3. legacy `--allow-promote` escape hatch 존재
4. migration 이후 DB-backed shadow mode 미검증

다만 staging-only 운영 방향은 충분하다. 별도 `image_enrichment_candidates` 테이블 없이 `staging_external_places` image columns만으로 다음 단계 진행이 가능하다.

### 다음 단계 권고

1. `--allow-promote` legacy escape hatch 제거 또는 별도 승인 파일/환경변수로 이중 잠금
2. staging image review columns migration 승인 여부 결정
3. migration 적용 후 promote freeze 유지
4. 실제 staging row approve/reject write 구현
5. DB-backed shadow mode 재실행
6. 그 결과가 안정되면 approved-only cutover 검토

### 검증 상태

- `python -m py_compile`: 통과
- JSON/CSV/MD pre-cutover report 생성 확인
- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- image 자동 approve 없음
- `BLOCK_MISSING_IMAGE` 직접 완화 없음
- docker compose down 없음
- saju 영향 없음

## 2026-05-20 추가: legacy promote escape hatch hardening

### 목표

approved-only cutover 전 마지막 핵심 blocker였던 legacy escape hatch를 이중 잠금했다.

기존 위험:

```text
update_all.sh --allow-promote
또는
promote_external_places.py --qa-passed --write
```

위 경로가 실수로 production `places` write에 진입할 수 있었다.

### hardening 결과

이제 legacy promote write는 단순 CLI flag만으로는 불가능하다.

필수 조건:

```text
EXTERNAL_PROMOTE_UNLOCK=true
AND
approval file exists
AND
approval file content == APPROVED_ONLY_EXTERNAL_PROMOTE_UNLOCK
AND
non-dry-run write path
```

기본 approval file:

```text
.external_promote_unlock
```

환경변수로 override 가능:

```text
EXTERNAL_PROMOTE_UNLOCK_FILE=/path/to/file
```

### promote freeze default

기본 정책은 유지했다.

```text
candidate_only=true
no_promote=true
review_required=true
```

`--allow-promote`가 들어와도 env+approval file 조건을 통과하지 못하면 candidate/review flow에서 write로 넘어갈 수 없다.

### legacy bypass audit

| 경로 | 결과 |
|---|---|
| `batch/update_all.sh --allow-promote` | env+approval file 없으면 차단 |
| `promote_external_places.py --qa-passed --write` | env+approval file 없으면 차단 |
| staging_places direct promote path | 코드상 남아 있지만 unlock 없으면 진입 불가 |
| approved-only shadow/rehearsal | read-only 유지 |

검증한 차단 케이스:

- no env + no file: BLOCKED
- env true + missing file: BLOCKED
- file token exists + env false: BLOCKED

### operator safety warning

help/warning 문구를 강화했다.

- legacy promote는 emergency path
- `--allow-promote`는 일반 운영 옵션 아님
- `--write`는 `EXTERNAL_PROMOTE_UNLOCK=true`와 approval file token 필요
- production write 전 final preview 필수

### report

```text
qa_reports/legacy_promote_hardening/
```

### migration readiness 변화

판단: 여전히 NO-GO.

다만 uncontrolled legacy write 가능성은 제거됐다.

남은 blocker:

1. `staging_external_places` image review columns migration 미적용
2. 실제 staging image review persistence write 미구현
3. migration 이후 DB-backed shadow mode 미검증
4. cutover 후 legacy `staging_places` promote path 제거/비활성화 필요

### 검증 상태

- `python -m py_compile`: 통과
- `update_all.sh --help`: 확인
- `promote_external_places.py --help`: 확인
- uncontrolled write path: unlock 없이는 차단 확인
- production migration 실행 없음
- production places write 없음
- production `places` row count: `26381`, 변화 없음
- raw overwrite 없음
- full reload 없음
- docker compose down 없음
- saju 영향 없음

## 2026-05-19 추가: staging image persistence write rehearsal

### 목표

approved-only 전환 직전 마지막 blocker인 `staging_external_places` image review persistence write 흐름을 실제 migration 없이 rehearsal했다.

이번 단계에서도 DB write는 수행하지 않았다.

### staging persistence payload 최종안

rehearsal payload는 `staging_external_places` update 기준으로 고정했다.

필드:

- `staging_external_place_id`
- `image_review_status`
- `image_source`
- `image_url`
- `image_thumb_url`
- `image_confidence`
- `image_license_note`
- `image_reviewer`
- `image_review_note`
- `image_reviewed_at`
- `image_block_reason`

`staging_external_place_id`는 migration/table 적용 전이므로 현재 rehearsal에서는 `null` 가능하다. migration 적용 후에는 실제 `staging_external_places.id`가 들어가야 한다.

### approve payload 예시

```json
{
  "staging_external_place_id": null,
  "image_review_status": "approved",
  "image_source": "naver_image_search",
  "image_url": "...",
  "image_thumb_url": "...",
  "image_confidence": "HIGH",
  "image_license_note": "naver_image_search_preview_only",
  "image_reviewer": "operator_a",
  "image_review_note": "staging image approve rehearsal",
  "image_reviewed_at": "2026-05-19T...Z",
  "image_block_reason": null
}
```

### reject/review payload 예시

```json
{
  "staging_external_place_id": null,
  "image_review_status": "blocked_license",
  "image_source": "naver_image_search",
  "image_url": "...",
  "image_thumb_url": "...",
  "image_confidence": "LOW",
  "image_license_note": null,
  "image_reviewer": "operator_a",
  "image_review_note": "staging image reject/review rehearsal",
  "image_reviewed_at": "2026-05-19T...Z",
  "image_block_reason": "license_source_risk"
}
```

### 서울 카페 7건 approve/reject rehearsal

approve rehearsal:

- 낫배드커피 도산: `approved`, validator clear 가능
- 젠젠 성수점: `approved`, validator clear 가능
- 카페 공명 연남점: `approved`, validator clear 가능
- 크림시크: `approved`, validator clear 가능

reject/review rehearsal:

- 레자미오네뜨: `blocked_license`, validator clear 불가
- 아쿠아산타 성수카페: `low_confidence`, validator clear 불가
- 어퍼앤언더: `low_confidence`, validator clear 불가

report:

```text
qa_reports/staging_image_persistence_write_rehearsal/
```

### promote validator staging simulation

조건:

```text
image_review_status = 'approved'
AND image_url IS NOT NULL
AND image_license_note IS NOT NULL
```

결과:

| 항목 | 결과 |
|---|---:|
| legacy_candidate_count | 7 |
| approved_eligible_count | 0 |
| image_review_adjusted_eligible_count | 4 |
| image_approved_candidate_count | 4 |
| remaining BLOCK_MISSING_IMAGE | 3 |

approved preview candidates:

- 낫배드커피 도산
- 젠젠 성수점
- 카페 공명 연남점
- 크림시크

still blocked:

- 레자미오네뜨
- 아쿠아산타 성수카페
- 어퍼앤언더

shadow report:

```text
qa_reports/shadow_mode_staging_image_persistence_rehearsal/
```

### rollback/freeze rehearsal 판단

운영 관점 판단:

1. reviewer mistake rollback
   - migration 적용 후에도 `image_review_status='approved'`를 `needs_manual_review` 또는 `rejected`로 되돌리면 promote eligibility에서 제외 가능하다.
   - rollback은 places를 건드리기 전에 staging row에서 처리하는 것이 원칙이다.

2. image source blacklist update
   - `blocked_license` / `image_block_reason` 기반으로 source blacklist rule을 추가할 수 있다.
   - blacklist 업데이트 후에는 해당 run의 image review report를 재생성하고 shadow mode를 다시 돌려야 한다.

3. approved image quarantine
   - approve 후 문제가 발견되면 `image_review_status='needs_manual_review'` 또는 `blocked_license`로 격리한다.
   - quarantine 상태 후보는 approved-only validator에서 `BLOCK_MISSING_IMAGE` 해제 대상이 아니다.

4. promote freeze
   - migration 직후에는 promote freeze 유지가 필요하다.
   - staging image persistence write가 실제 DB에서 검증되고 shadow mode 결과가 안정된 뒤에만 promote cutover를 검토한다.

### migration readiness

현재 판단: 아직 NO-GO.

좋아진 점:

- staging-only image persistence payload가 확정됨
- approve/reject rehearsal이 가능함
- validator simulation에서 4건 eligible 전환을 확인함

마지막 blocker:

1. `staging_external_places` image review columns migration 적용 승인
2. 실제 staging row update 구현
3. reviewer mistake rollback command/report 구현
4. staging DB 기반 shadow mode 재검증

### 검증 상태

- `python -m py_compile`: 통과
- JSON/CSV/MD rehearsal report 생성 확인
- production migration 실행 없음
- production places write 없음
- production `places` row count: `26381`, 변화 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- image 자동 approve 없음
- `BLOCK_MISSING_IMAGE` 직접 완화 없음
- saju 영향 없음

## 2026-05-19 추가: image persistence scope reduction

### 결정

image persistence 범위를 축소했다.

`image_enrichment_candidates` 별도 테이블은 이번 운영 전환 준비 단계에서 보류한다. 현재 blocker는 이미지 후보를 영구 저장하는 별도 workbench가 아니라, `staging_external_places` 후보가 reviewer image decision을 가진 상태로 approved-only validator를 통과할 수 있는지 검증하는 것이다.

따라서 다음 단계 기준은 아래로 단순화한다.

```text
staging_external_places
  image_source
  image_url
  image_thumb_url
  image_confidence
  image_license_note
  image_review_status
  image_reviewer
  image_review_note
  image_reviewed_at
  image_block_reason
```

### migration draft 변경

`reports/external_places_data_pipeline_phase1_migration_draft.sql`에서 `image_enrichment_candidates` 신규 테이블 draft와 관련 index를 제거했다.

유지한 것은 `staging_external_places` image review columns와 image review index뿐이다.

보류 사유:

1. 운영자가 관리해야 할 review surface를 줄이기 위해
2. migration 승인 범위를 최소화하기 위해
3. approved-only promote 전환 전에는 staging 후보 단위 review만으로 충분하기 때문에
4. 별도 image table은 운영 필요성이 입증된 뒤 추가해도 되기 때문에

### review_image_candidates.py 정리

`review_image_candidates.py` rehearsal payload를 `staging_external_places` update 기준으로 단순화했다.

제거/보류:

- `planned_image_enrichment_candidate_record`
- `image_enrichment_candidates` target option

유지:

- `--persistence-rehearsal`
- `--simulate-write`
- `--approve-image`
- `--reject-image`
- `--reviewer`
- `--review-note`
- `--image-license-note`
- 실제 `--write` 차단

### validator simulation 조건

`promote_external_places.py`의 image review override도 staging 기준 조건으로 정리했다.

simulation에서 `BLOCK_MISSING_IMAGE`가 해제되는 조건:

```text
image_review_status = 'approved'
AND image_url exists
AND image_license_note exists
```

기존 `IMAGE_APPROVED_SIMULATED`만으로는 더 이상 충분하지 않다.

### 서울 카페 7건 재검증 기준

대상:

- 낫배드커피 도산
- 젠젠 성수점
- 카페 공명 연남점
- 크림시크
- 레자미오네뜨
- 아쿠아산타 성수카페
- 어퍼앤언더

기대 결과:

- approved simulation: 4건
- blocked/review: 3건
  - license risk 1건
  - low confidence 2건
- DB write 없음

실행 결과:

| 항목 | 결과 |
|---|---:|
| candidate_count | 7 |
| image_approved_simulated_count | 4 |
| image_blocked_license_risk_count | 1 |
| image_low_confidence_review_count | 2 |
| production places write | 0 |
| production migration | 0 |

approved simulation 후보:

- 낫배드커피 도산
- 젠젠 성수점
- 카페 공명 연남점
- 크림시크

block/review 후보:

- 레자미오네뜨: `blocked_license`
- 아쿠아산타 성수카페: `low_confidence`
- 어퍼앤언더: `low_confidence`

report:

```text
qa_reports/image_review_staging_only_revalidation/
```

### validator simulation 결과

staging-only image review report를 `promote_external_places.py --shadow-mode --image-review-report`에 연결해 검증했다.

결과:

| 항목 | 결과 |
|---|---:|
| legacy_candidate_count | 7 |
| approved_eligible_count | 0 |
| image_review_adjusted_eligible_count | 4 |
| image_approved_candidate_count | 4 |
| remaining BLOCK_MISSING_IMAGE | 3 |

image review로 adjusted eligible이 된 후보:

- 낫배드커피 도산
- 젠젠 성수점
- 카페 공명 연남점
- 크림시크

계속 blocked 후보:

- 레자미오네뜨
- 아쿠아산타 성수카페
- 어퍼앤언더

shadow report:

```text
qa_reports/shadow_mode_seoul_cafe_staging_only_image_review/
```

### migration readiness 변화

범위 축소 후 판단:

- migration apply는 여전히 NO-GO
- 다만 필요한 migration 범위가 줄어 승인 부담은 낮아짐
- 다음 blocker는 `staging_external_places` image columns 적용 승인과 실제 approve/reject persistence 구현임

### 검증 상태

- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- image 자동 approve 없음
- `BLOCK_MISSING_IMAGE` 직접 완화 없음
- saju 영향 없음

## 2026-05-19 추가: image review persistence draft

### 목표

image review gate simulation 결과를 실제 운영 전환 가능한 persistence 구조로 확장하기 위한 준비를 진행했다. 이번 단계에서도 production migration, production places write, raw overwrite, full reload, scraping, approved-only 완화는 수행하지 않았다.

### image persistence 설계

권장 상태값:

- `pending`: image candidate가 생성되었지만 아직 사람이 검토하지 않음
- `approved`: reviewer가 production card image 후보로 승인
- `rejected`: reviewer가 부적합 판정
- `blocked_license`: source/license 위험으로 차단
- `low_confidence`: confidence가 낮아 자동 승인 불가
- `needs_manual_review`: 자동 판단이 어렵고 사람이 추가 확인 필요

권장 필드:

- `image_source`
- `image_url`
- `image_thumb_url`
- `image_confidence`
- `image_license_note`
- `image_reviewer`
- `image_review_note`
- `image_reviewed_at`
- `image_block_reason`

핵심 원칙:

- HIGH confidence라도 자동 approve하지 않는다.
- reviewer approve 없이 `BLOCK_MISSING_IMAGE`를 직접 완화하지 않는다.
- image URL만으로는 부족하며 `image_license_note`까지 있어야 promote validator에서 image gate 통과 후보로 볼 수 있다.

### migration draft 변경

`reports/external_places_data_pipeline_phase1_migration_draft.sql`에 아래를 draft로 추가했다.

1. `staging_external_places` image review 필드
   - `image_source`
   - `image_confidence`
   - `image_license_note`
   - `image_reviewer`
   - `image_review_note`
   - `image_reviewed_at`
   - `image_block_reason`
   - `image_review_status`

2. `image_enrichment_candidates` draft table
   - image candidate를 place promotion과 분리해서 검토하기 위한 workbench table
   - `run_id`, `clean_external_place_id`, `staging_external_place_id`, source/external id, query, image URL, confidence, mismatch reason, license note, review status 포함

3. index draft
   - `idx_staging_external_places_image_review`
   - `idx_image_enrichment_candidates_review`
   - `idx_image_enrichment_candidates_place`

주의: 이 SQL은 proposal이며 production에 적용하지 않았다.

### review_image_candidates.py 확장

`batch/external/review_image_candidates.py`에 persistence workflow placeholder를 추가했다.

추가 옵션:

- `--approve-image`
- `--reject-image`
- `--reviewer`
- `--review-note`
- `--write`

현재 동작:

- `--write`가 있어도 DB write는 차단한다.
- migration 적용 전에는 `image_enrichment_candidates` 또는 `staging_external_places` image review columns에 persistence할 수 없다는 blocked payload만 report summary에 출력한다.
- reviewer/review note 누락 여부를 dry-run payload로 표시한다.

### promote validator 연동 정책

`batch/external/promote_external_places.py`의 approved-only safety TODO를 보강했다.

정책:

```text
BLOCK_MISSING_IMAGE는 직접 완화하지 않는다.

단, 아래 조건을 모두 만족하면 image gate 통과 후보로 볼 수 있다.

image_review_status = 'approved'
image_url exists
image_license_note exists
```

현재 `--image-review-report` shadow override는 simulation 전용이며 production promote 조건을 완화하지 않는다.

### migration readiness 변화

현재 판단: migration apply는 아직 NO-GO.

변화:

- image 후보 생성 가능성은 확인됨
- image review simulation으로 eligible 후보 4건 발생 확인됨
- 이제 blocker는 image review persistence table/columns migration 적용 승인과 운영 reviewer 절차 확정임

다음 blocker:

1. `staging_external_places` / `image_enrichment_candidates` migration 승인
2. reviewer approve/reject 실제 persistence 구현
3. approved-only validator가 image review status를 실제 DB 기준으로 읽도록 전환
4. shadow mode에서 legacy path와 approved-only+image-reviewed path 비교 재실행

### 검증 상태

- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- approved-only 완화 없음
- 추천 엔진 수정 없음
- saju 영향 없음

## 2026-05-19 추가: image review gate simulation

### 목적

Naver Image Search PoC 결과를 바탕으로 reviewer가 image candidate를 검토하고 승인/거절하는 흐름을 report-only simulation으로 구현했다. 이 단계에서도 production migration, production `places` write, raw overwrite, full reload, scraping, image 자동 approve, `BLOCK_MISSING_IMAGE` 정책 완화는 수행하지 않았다.

### 추가 Script

```text
batch/external/review_image_candidates.py
```

역할:

- image enrichment PoC JSON report를 읽는다.
- HIGH/MEDIUM/LOW confidence와 mismatch/license risk를 분류한다.
- reviewer action simulation을 만든다.
- JSON/CSV/Markdown report를 생성한다.

입력 예:

```text
--input-report qa_reports/image_enrichment_poc/...
--simulate-approve-high
--output-dir qa_reports/image_review_gate
```

### Image Decision Taxonomy

| decision | 의미 |
|---|---|
| `IMAGE_REVIEW_REQUIRED` | reviewer가 image를 직접 봐야 함 |
| `IMAGE_APPROVED_SIMULATED` | HIGH confidence를 simulation에서만 승인 처리 |
| `IMAGE_REJECTED_SIMULATED` | usable image candidate 없음 |
| `IMAGE_BLOCKED_MISMATCH` | image/title/source mismatch risk |
| `IMAGE_BLOCKED_LICENSE_RISK` | Pinterest/pinimg 등 license/source risk |
| `IMAGE_LOW_CONFIDENCE_REVIEW` | low confidence라 reject 또는 manual review 필요 |

중요 원칙:

- HIGH confidence도 기본 자동 승인이 아니다.
- `--simulate-approve-high`가 있을 때만 simulation상 approve로 처리한다.
- 실제 DB persistence는 없다.

### Image Review Simulation 결과

대상:

- run_id: `b5ebd247-6601-4e81-9873-db07fd2c6d77`
- region: `서울`
- visit_role: `cafe`
- candidates: 7
- simulate_approve_high: true

summary:

| 항목 | 값 |
|---|---:|
| candidate_count | 7 |
| IMAGE_APPROVED_SIMULATED | 4 |
| IMAGE_BLOCKED_LICENSE_RISK | 1 |
| IMAGE_LOW_CONFIDENCE_REVIEW | 2 |

생성 report:

```text
/home/ubuntu/travel_service_prod/qa_reports/image_review_gate/image_review_gate_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_233158.json
/home/ubuntu/travel_service_prod/qa_reports/image_review_gate/image_review_gate_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_233158.csv
/home/ubuntu/travel_service_prod/qa_reports/image_review_gate/image_review_gate_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_233158.md
```

후보별 decision:

| 후보 | image decision |
|---|---|
| 낫배드커피 도산 | IMAGE_APPROVED_SIMULATED |
| 젠젠 성수점 | IMAGE_APPROVED_SIMULATED |
| 레자미오네뜨 | IMAGE_BLOCKED_LICENSE_RISK |
| 카페 공명 연남점 | IMAGE_APPROVED_SIMULATED |
| 아쿠아산타 성수카페 | IMAGE_LOW_CONFIDENCE_REVIEW |
| 어퍼앤언더 | IMAGE_LOW_CONFIDENCE_REVIEW |
| 크림시크 | IMAGE_APPROVED_SIMULATED |

### Image-approved Shadow Validation

`promote_external_places.py`에 shadow-mode 전용 옵션을 추가했다.

```text
--image-review-report qa_reports/image_review_gate/...
```

역할:

- image review report에서 `IMAGE_APPROVED_SIMULATED` 후보명을 읽는다.
- 해당 후보가 `BLOCK_MISSING_IMAGE` 단일 사유로만 막힌 경우, shadow simulation에서만 block을 제거한다.
- 실제 DB write나 정책 완화는 없다.

실행 결과:

| 항목 | 값 |
|---|---:|
| original approved_eligible_count | 0 |
| image_review_adjusted_eligible_count | 4 |
| image_approved_candidate_count | 4 |
| still_blocked_count | 3 |
| remaining `BLOCK_MISSING_IMAGE` | 3 |

생성 report:

```text
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe_image_review/shadow_mode_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_233158.json
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe_image_review/shadow_mode_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_233158.csv
/home/ubuntu/travel_service_prod/qa_reports/shadow_mode_seoul_cafe_image_review/shadow_mode_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_233158.md
```

image-approved simulated eligible:

- 낫배드커피 도산
- 젠젠 성수점
- 카페 공명 연남점
- 크림시크

still blocked:

- 레자미오네뜨: license risk
- 아쿠아산타 성수카페: low confidence
- 어퍼앤언더: low confidence

### 정책 판단

이번 simulation으로 확인된 점:

1. image review gate를 붙이면 `BLOCK_MISSING_IMAGE`를 직접 완화하지 않아도 eligible 후보가 생긴다.
2. LOW/blacklist 후보는 계속 막을 수 있다.
3. reviewer workload는 서울 카페 7건 기준으로 감당 가능하다.
   - approve simulation 4건
   - block/review 3건
4. 다만 image approval persistence가 없으므로 migration apply는 아직 NO-GO다.

### Migration Readiness 변화

이전 blocker:

- image metadata 공급망 부족

현재 blocker:

- image review decision persistence 부재
- image source/license policy 미확정
- approved image를 staging_external_places/promote validator에 반영하는 migration/persistence 구조 부재

따라서 migration apply는 여전히 NO-GO지만, approved-only 구조 자체는 viable해졌다.

### 다음 단계 권고

1. `image_enrichment_candidates` / `image_review_status` migration draft를 정리한다.
2. `IMAGE_APPROVED` 상태가 있는 후보만 `BLOCK_MISSING_IMAGE`를 해제하도록 promote validator를 설계한다.
3. image URL license/source note를 필수 review 필드로 둔다.
4. 서울 카페 외 부산 식당/제주 실내 slice에서도 image review simulation을 반복한다.
5. image review persistence까지 rehearsal된 뒤 migration go/no-go를 다시 판단한다.

### 검증

- `python -m py_compile`: 통과
- image review report JSON/CSV/MD 생성
- image-approved shadow validation JSON/CSV/MD 생성
- production `places` row count: `26381`, 변화 없음
- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- approved-only 완화 없음
- saju 영향 없음

## 2026-05-19 추가: Naver Image Search dry-run PoC

### 목적

서울 카페 delta 후보 7건에 대해 Naver Image Search API 기반 image enrichment가 현실적으로 가능한지 dry-run으로 검증했다. 이번 PoC는 image candidate report 생성만 수행했고, production migration, production `places` write, raw overwrite, full reload, scraping, approved-only 완화는 수행하지 않았다.

### 추가 Script

신규 dry-run script:

```text
batch/external/image_enrichment_poc.py
```

입력:

- `--run-id`
- `--region`
- `--visit-role`
- `--limit`
- `--display`
- `--keywords`
- `--report`
- `--output-dir`

동작:

1. `clean_external_places`에서 후보를 읽는다.
2. 후보별 query를 만든다.
   - 예: `{place_name} {region} 카페`
3. Naver Image Search API를 호출한다.
4. image candidate를 scoring한다.
5. JSON/CSV/Markdown report만 생성한다.

금지 사항:

- DB write 없음
- migration 없음
- scraping 없음
- 자동 approve 없음
- `BLOCK_MISSING_IMAGE` 정책 변경 없음

### Confidence Heuristic 초안

현재 heuristic은 단순 규칙 기반이다.

| 항목 | 설명 |
|---|---|
| `title_similarity` | image title에 place name token이 포함되는지 |
| `region_similarity` | title/source page에 region token이 포함되는지 |
| `category_similarity` | cafe/coffee/dessert/bakery 계열 keyword 포함 여부 |
| blacklist | `pinterest`, `pinimg`, `banner`, `logo`, `menu`, `coupon` 등 |

score:

```text
score = title_similarity * 0.65
      + region_similarity * 0.15
      + category_similarity * 0.20
```

confidence:

- `HIGH`: score >= 0.75 and no mismatch
- `MEDIUM`: score >= 0.45 and no mismatch
- `LOW`: score < 0.45 or mismatch

주의:

- `HIGH`도 자동 승인하지 않는다.
- `LOW` 또는 blacklist hit는 reject 또는 manual review 대상이다.

### 실행 결과

대상:

- run_id: `b5ebd247-6601-4e81-9873-db07fd2c6d77`
- region: `서울`
- visit_role: `cafe`
- candidates: 7
- display per query: 3

summary:

| 항목 | 값 |
|---|---:|
| candidate_count | 7 |
| places_with_image_candidates | 7 |
| high_confidence_count | 4 |
| medium_confidence_count | 0 |
| low_confidence_count | 3 |
| none_count | 0 |
| errors_count | 0 |

생성 report:

```text
/home/ubuntu/travel_service_prod/qa_reports/image_enrichment_poc/image_enrichment_poc_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_232445.json
/home/ubuntu/travel_service_prod/qa_reports/image_enrichment_poc/image_enrichment_poc_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_232445.csv
/home/ubuntu/travel_service_prod/qa_reports/image_enrichment_poc/image_enrichment_poc_b5ebd247-6601-4e81-9873-db07fd2c6d77_서울_cafe_20260518_232445.md
```

로컬 workspace:

```text
qa_reports/image_enrichment_poc/
```

### 후보별 결과

| 후보 | confidence | mismatch | recommended action |
|---|---|---|---|
| 낫배드커피 도산 | HIGH | none | REVIEW_IMAGE_CANDIDATE |
| 젠젠 성수점 | HIGH | none | REVIEW_IMAGE_CANDIDATE |
| 레자미오네뜨 | LOW | blacklist:pinimg | REJECT_OR_MANUAL_REVIEW |
| 카페 공명 연남점 | HIGH | none | REVIEW_IMAGE_CANDIDATE |
| 아쿠아산타 성수카페 | LOW | none, low score | REJECT_OR_MANUAL_REVIEW |
| 어퍼앤언더 | LOW | none, low score | REJECT_OR_MANUAL_REVIEW |
| 크림시크 | HIGH | none | REVIEW_IMAGE_CANDIDATE |

### Mismatch Risk 사례

1. `레자미오네뜨`
   - score는 높지만 thumbnail source가 `pinimg` 계열이라 blacklist 처리했다.
   - 장소명 매칭이 좋아도 Pinterest/CDN 계열 이미지는 license/source 신뢰 문제가 있어 자동 사용 금지.

2. `아쿠아산타 성수카페`
   - image candidate는 있으나 score가 낮다.
   - title/source alignment가 약하므로 reject 또는 manual review.

3. `어퍼앤언더`
   - image candidate는 있으나 score가 낮다.
   - query 결과가 broader cafe/article image로 흐를 가능성이 있어 manual review 필요.

### Usable Thumbnail 판단

7건 모두 thumbnail URL은 확보됐다. 다만 usable 판단은 confidence에 따라 다르다.

- 바로 review 후보로 볼 수 있는 수준: 4건
- manual review 또는 reject 후보: 3건
- 자동 approve 가능 후보: 0건

### Image Enrichment 현실성 판단

Naver Image Search API는 image metadata blocker를 풀 수 있는 가능성이 있다.

하지만 그대로 자동 연결하면 안 된다.

필요한 보완:

1. blacklist 강화
   - `pinimg`, blog collage, menu/banner/logo 계열
2. title/source matching 강화
   - place name exact token
   - district/region token
3. source reliability scoring
   - Naver place image/CDN 계열과 일반 블로그/이미지 검색 결과 분리
4. reviewer preview UI/report
   - thumbnail preview를 보고 승인/거절 가능해야 함
5. image license/source policy
   - 단순 검색 결과 link를 production 카드에 그대로 써도 되는지 정책 검토 필요

### `BLOCK_MISSING_IMAGE` 정책 영향

이번 PoC 결과만으로 `BLOCK_MISSING_IMAGE`를 제거하면 안 된다.

대신 다음 방향이 합리적이다.

1. image enrichment candidate가 `HIGH`이면 `IMAGE_REVIEW_REQUIRED`로 전환
2. reviewer가 image preview를 확인하고 approve하면 image missing block 해제
3. `LOW` 또는 mismatch는 계속 block
4. image source/license note 없이는 production promote 금지

즉, `BLOCK_MISSING_IMAGE`를 직접 완화하지 말고 image review gate를 추가하는 방식이 안전하다.

### Migration Readiness 영향

현재 판단: migration apply는 아직 NO-GO.

다만 이전보다 blocker가 더 구체화됐다.

- 이전: image supply 자체가 막혀 있음
- 현재: Naver Image Search로 image candidate 생성은 가능
- 남은 blocker: image validation/review/persistence 구조 부재

운영 전환 전 필요한 다음 단계:

1. `image_enrichment_candidates` draft table 또는 report-only workflow 설계
2. image review status 추가
3. `HIGH` image candidate를 포함한 shadow validation 재실행
4. image approve 후 `PROMOTE_ELIGIBLE`이 실제 생기는지 rehearsal

### 검증

- `python -m py_compile batch/external/image_enrichment_poc.py`: 통과
- production `places` row count: `26381`, 변화 없음
- production migration 실행 없음
- production places write 없음
- raw overwrite 없음
- full reload 없음
- scraping 없음
- approved-only 완화 없음
- 추천 엔진 수정 없음
- saju 영향 없음
