# Source Structure Map

생성일: 2026-05-08

## 목적

현재 여행 코스 추천 서비스의 소스 구조를 기능별로 정리한다.

주의:

- 이 문서는 읽기 전용 분석 결과다.
- 코드 수정, DB 수정, migration 실행, 배포는 수행하지 않았다.
- `places`를 직접 수정하는 파일과 추천 엔진에 영향 주는 파일은 별도로 표시했다.

## 전체 구조 요약

```text
D:\travel_data_pipeline
├─ api_server.py
├─ course_builder.py
├─ database.py
├─ db_client.py
├─ config.py
├─ tourism_belt.py
├─ tourapi_fetcher.py
├─ main.py
├─ enrichment_service.py
├─ batch/
│  ├─ update_pipeline.py
│  ├─ update_all.sh
│  ├─ update_all.ps1
│  ├─ steps/
│  ├─ external/
│  └─ place_enrichment/
├─ frontend/
│  ├─ src/
│  ├─ vite.config.js
│  ├─ Dockerfile.staging
│  └─ nginx.staging.conf
├─ docs/
├─ tests/
├─ sql/verify/
├─ migration_001_places_v2.sql
├─ migration_002_add_images.sql
├─ migration_003_add_culture_role.sql
├─ migration_004_add_indoor_outdoor.sql
├─ migration_005_add_saved_course_place_snapshots.sql
├─ migration_006_course_operation_logs.sql
├─ migration_007_data_update_pipeline.sql
├─ migration_008_external_places_pipeline.sql
├─ migration_009_place_enrichment.sql
└─ migration_010_representative_poi_candidates.sql
```

## Production 핵심 파일

아래 파일은 운영 동작에 직접 영향이 크므로 수정 전 별도 계획과 검증이 필요하다.

| 파일 | 역할 | places 수정 | 추천 엔진 영향 | 위험도 |
|---|---|---:|---:|---|
| `course_builder.py` | 실제 코스 추천 엔진 진입점 `build_course` | 아니오 | 예 | 매우 높음 |
| `api_server.py` | FastAPI 서버, 프론트 API, 코스 생성/교체/추가/재계산 | 간접 가능 | 예 | 매우 높음 |
| `database.py` | production 계열 DB connection/upsert helper | 예 | 간접 | 높음 |
| `db_client.py` | batch/staging 계열 DB connection/helper | 예 | 간접 | 높음 |
| `config.py` | DB/API 환경설정 | 아니오 | 간접 | 높음 |
| `tourism_belt.py` | 대표 seed/관광벨트 기준 | 아니오 | 예 | 높음 |
| `frontend/src/screens/day-trip/CourseResultScreen.jsx` | 코스 생성/결과/교체/추가/저장 UI | 아니오 | API 호출 영향 | 높음 |
| `frontend/src/screens/day-trip/HomeScreen.jsx` | 지역/출발지 선택 UI | 아니오 | API 호출 영향 | 중간 |
| `frontend/vite.config.js` | API proxy target | 아니오 | API 연결 영향 | 높음 |
| `staging_deploy.sh` | Git/Docker 배포 스크립트 | 아니오 | 운영 배포 영향 | 높음 |
| `docker-compose.staging.yml` | staging compose 구성 | 아니오 | 운영 배포 영향 | 높음 |
| `frontend/nginx.staging.conf` | 프론트 nginx serving/proxy | 아니오 | 운영 배포 영향 | 높음 |

## 기능별 파일 맵

### 추천 엔진

| 관련 파일 | 역할 | 운영 영향도 | 수정 시 위험도 | 상태 | places 수정 | 추천 엔진 영향 |
|---|---|---|---|---|---:|---:|
| `course_builder.py` | 추천 후보 pool, anchor, slot, role, 동선, option_notice, 최종 코스 생성 | 매우 높음 | 매우 높음 | production | 아니오 | 예 |
| `tourism_belt.py` | 지역별 관광 belt seed | 높음 | 높음 | production | 아니오 | 예 |
| `anchor_definitions.py` | anchor/출발지 정의 | 높음 | 높음 | production | 아니오 | 예 |
| `regional_zone_builder.py` | 지역 zone/권역 구성 | 중간 | 중간 | production | 아니오 | 예 |
| `city_clusters.py` | 도시/권역 cluster 정보 | 중간 | 중간 | production | 아니오 | 예 |
| `region_notices.py` | region status, option notice, 제한 안내 | 높음 | 중간 | production | 아니오 | 예 |
| `travel_utils.py` | 거리/시간 등 공통 유틸 | 중간 | 중간 | production | 아니오 | 예 |
| `enrichment_service.py` | 코스 품질 검증/보강 보조 | 중간 | 중간 | production | 아니오 | 간접 |

수정 주의:

- `course_builder.py`는 추천 엔진 핵심이므로 데이터 품질 문제를 엔진 로직으로 숨기면 안 된다.
- `tourism_belt.py` seed 수정은 강릉/경포대 같은 대표 POI 노출에 직접 영향을 준다.

### API 서버

| 관련 파일 | 역할 | 운영 영향도 | 수정 시 위험도 | 상태 | places 수정 | 추천 엔진 영향 |
|---|---|---|---|---|---:|---:|
| `api_server.py` | FastAPI app, `/api/regions`, `/api/course/generate`, 후보 조회, 교체, 저장, 재계산 | 매우 높음 | 매우 높음 | production | 아니오 | 예 |
| `main.py` | TourAPI/AI processing CLI 성격의 기존 실행 진입점 | 중간 | 중간 | dev/ops | 예 가능 | 간접 |
| `run_course_qa_report.py` | 통합 QA 판정/리포트 | 중간 | 중간 | dev/qa | 아니오 | 간접 |
| `run_integration_test.py` 등 `run_*.py` | 검증/진단 스크립트 | 낮음~중간 | 낮음~중간 | dev/qa | 대부분 아니오 | 간접 |

API 주요 route:

- `GET /api/regions`
- `GET /api/region/{region}/departures`
- `GET /api/region/{region}/zones`
- `POST /api/course/generate`
- `GET /api/course/{course_id}/candidates`
- `PATCH /api/course/{course_id}/replace`
- `POST /api/course/{course_id}/recalculate`
- `POST /api/course/{course_id}/save`

### DB / Database Layer

| 관련 파일 | 역할 | 운영 영향도 | 수정 시 위험도 | 상태 | places 수정 | 추천 엔진 영향 |
|---|---|---|---|---|---:|---:|
| `database.py` | DB 연결, `places` upsert, AI fields update | 높음 | 높음 | production/ops | 예 | 간접 |
| `db_client.py` | batch용 DB 연결 및 기본 helper | 높음 | 높음 | dev/ops | 예 가능 | 간접 |
| `schema.sql`, `schema_final.sql`, `schema_poc.sql` | DB schema 참고/초기화 | 높음 | 높음 | reference | 예 가능 | 간접 |
| `sql/verify/*.sql` | 데이터 품질 확인 SQL | 낮음 | 낮음 | qa/reference | 아니오 | 아니오 |

주의:

- `database.py`와 `db_client.py` 모두 DB write 가능 경로를 제공한다.
- `places`를 직접 바꾸는 실행은 반드시 migration/backup/QA/rollback이 동반되어야 한다.

### TourAPI 수집 / 기존 데이터 적재

| 관련 파일 | 역할 | 운영 영향도 | 수정 시 위험도 | 상태 | places 수정 | 추천 엔진 영향 |
|---|---|---|---|---|---:|---:|
| `tourapi_fetcher.py` | TourAPI fetcher | 중간 | 중간 | production/ops | 아니오 자체 | 간접 |
| `main.py` | TourAPI 수집/AI/DB 저장 흐름 | 높음 | 높음 | ops/dev | 예 | 간접 |
| `ai_processor.py` | AI 요약/태그/embedding 처리 | 중간 | 중간 | ops/dev | 예 가능 | 간접 |
| `ai_validator.py` | AI validation | 중간 | 중간 | ops/dev | 예 가능 | 간접 |
| `refetch_missing_overview.py` | 누락 overview 재수집 | 중간 | 중간 | ops/dev | 예 가능 | 간접 |
| `refetch_coord_outliers.py` | 좌표 이상치 재수집 | 중간 | 중간 | ops/dev | 예 가능 | 간접 |

### 공공데이터 업데이트 배치

| 관련 파일 | 역할 | 운영 영향도 | 수정 시 위험도 | 상태 | places 수정 | 추천 엔진 영향 |
|---|---|---|---|---|---:|---:|
| `batch/update_pipeline.py` | 데이터 업데이트 orchestration skeleton | 중간 | 중간 | dev/experimental | 기본 dry-run | 간접 |
| `batch/update_all.sh` | EC2/Linux wrapper, dry-run 기본, `--write` 지원 | 높음 | 높음 | ops/dev | write 시 가능 | 간접 |
| `batch/update_all.ps1` | Windows 보조 wrapper | 중간 | 중간 | dev | write 시 가능 | 간접 |
| `batch/steps/*.py` | backup, collect, clean, enrich, QA, promote skeleton | 중간 | 중간 | experimental | 대부분 skeleton | 간접 |
| `migration_007_data_update_pipeline.sql` | update pipeline tables | 높음 | 중간 | migration | 아니오 | 아니오 |

현재 상태:

- `batch/steps/*`는 대부분 dry-run skeleton이다.
- `promote_places.py`는 기본적으로 `dry_run` 또는 `promote=false`면 places upsert를 skip한다.

### Kakao/Naver External Enrichment

| 관련 파일 | 역할 | 운영 영향도 | 수정 시 위험도 | 상태 | places 수정 | 추천 엔진 영향 |
|---|---|---|---|---|---:|---:|
| `batch/external/collect_external_places.py` | Kakao/Naver external raw 수집 | 중간 | 중간 | experimental | raw write 가능 | 아니오 |
| `batch/external/clean_external_places.py` | raw external 정제/중복 제거 | 중간 | 중간 | experimental | clean/invalid write | 아니오 |
| `batch/external/enrich_external_places.py` | role/tag/description 보강 후 staging 적재 | 중간 | 중간 | experimental | staging write | 아니오 |
| `batch/external/qa_external_places.py` | 기존 QA 실행 및 FAIL 증가 차단 | 중간 | 중간 | experimental | QA result write | 간접 |
| `batch/external/promote_external_places.py` | staging_places를 places로 promote | 매우 높음 | 매우 높음 | experimental/blocked | 예 | 간접 |
| `migration_008_external_places_pipeline.sql` | external pipeline table DDL | 높음 | 중간 | migration | 아니오 | 아니오 |

주의:

- `promote_external_places.py`는 `INSERT INTO places` 경로가 있으므로 운영에서 특히 위험하다.
- 기본 원칙상 추천 요청 중 외부 API 호출은 금지다.

### Place Enrichment Staging

| 관련 파일 | 역할 | 운영 영향도 | 수정 시 위험도 | 상태 | places 수정 | 추천 엔진 영향 |
|---|---|---|---|---|---:|---:|
| `migration_009_place_enrichment.sql` | `place_enrichment_*` table DDL | 높음 | 중간 | migration/dev | 아니오 | 아니오 |
| `batch/place_enrichment/run_kakao_cafe_image_slice.py` | 서울 cafe 이미지 없는 place 대상 Kakao slice | 중간 | 중간 | experimental | staging write 가능 | 아니오 |
| `batch/place_enrichment/run_kakao_naver_cafe_compare_slice.py` | Kakao/Naver 후보 비교 slice | 중간 | 중간 | experimental | staging write 가능 | 아니오 |
| `batch/place_enrichment/adapters/kakao_adapter.py` | Kakao Local adapter | 중간 | 중간 | experimental | 아니오 | 아니오 |
| `batch/place_enrichment/adapters/naver_adapter.py` | Naver Local adapter | 중간 | 중간 | experimental | 아니오 | 아니오 |
| `batch/place_enrichment/matching/scoring.py` | match score, Korean normalization | 중간 | 중간 | experimental | 아니오 | 아니오 |
| `batch/place_enrichment/matching/decision_engine.py` | rule-based decision engine | 중간 | 중간 | experimental | 아니오 | 아니오 |
| `batch/place_enrichment/image_quality.py` | image quality score skeleton | 낮음 | 낮음 | experimental | 아니오 | 아니오 |
| `batch/place_enrichment/promote_dry_run.py` | place enrichment promote summary dry-run | 낮음 | 낮음 | experimental | 아니오 | 아니오 |

현재 구현 범위:

- Kakao/Naver Local candidate fetch/normalize 가능
- mock/dry-run 가능
- staging insert 가능
- recommend engine과 분리되어 있음
- `places.first_image_url` overwrite 없음

### Representative POI Workflow

| 관련 파일 | 역할 | 운영 영향도 | 수정 시 위험도 | 상태 | places 수정 | 추천 엔진 영향 |
|---|---|---|---|---|---:|---:|
| `migration_010_representative_poi_candidates.sql` | 대표 POI candidate staging DDL | 높음 | 중간 | migration/dev | 아니오 | 아니오 |
| `batch/place_enrichment/collect_representative_poi_candidates.py` | 대표 POI 후보 TourAPI/Kakao/Naver 수집, dry-run/write staging | 중간 | 중간 | experimental | staging write | 아니오 |
| `batch/place_enrichment/list_representative_candidates.py` | 대표 후보 조회 CLI | 낮음 | 낮음 | dev/ops | 아니오 | 아니오 |
| `batch/place_enrichment/review_representative_candidate.py` | 대표 후보 approve/reject/skip | 중간 | 중간 | dev/ops | review_status write | 아니오 |
| `batch/place_enrichment/representative_promote_dry_run.py` | 대표 후보 promote 영향 dry-run | 중간 | 중간 | experimental | 아니오 | 간접 분석 |
| `batch/place_enrichment/representative_enrichment_audit.py` | 대표 후보 image/overview audit | 낮음 | 낮음 | experimental/report | 아니오 | 아니오 |

현재 구현 범위:

- 경포대/불국사/성산일출봉/전주한옥마을 후보 staging 완료
- 경포대 representative candidate는 `APPROVED`
- 대표 후보 actual promote는 없음
- `places`와 `tourism_belt.py`는 미반영

주의:

- `representative_promote_dry_run.py`는 현재 manual overview candidate도 approved representative 후보처럼 집계할 수 있어 강화 필요가 있다.

### Manual Image / Manual Enrichment Workflow

| 관련 파일 | 역할 | 운영 영향도 | 수정 시 위험도 | 상태 | places 수정 | 추천 엔진 영향 |
|---|---|---|---|---|---:|---:|
| `batch/place_enrichment/add_manual_image_candidate.py` | 일반 place image manual candidate 등록 | 중간 | 중간 | experimental | staging write | 아니오 |
| `batch/place_enrichment/add_representative_manual_enrichment.py` | 대표 POI image/overview manual enrichment 등록 | 중간 | 중간 | experimental | representative staging write | 아니오 |
| `tests/test_manual_image_candidate.py` | manual image candidate 테스트 | 낮음 | 낮음 | test | 아니오 | 아니오 |

현재 구현 범위:

- 일반 place image 후보 등록 가능
- 대표 POI manual image/overview 후보 등록 가능
- dry-run 지원
- duplicate image skip
- empty overview reject
- approved representative candidate 없으면 reject
- `places` write 없음

경포대 현재 상태:

- representative place candidate `6`: `APPROVED`
- manual image candidate `115`: `REJECTED`
- manual overview candidate `116`: `APPROVED`
- image gap은 아직 남아 있음

### Review Workflow

| 관련 파일 | 역할 | 운영 영향도 | 수정 시 위험도 | 상태 | places 수정 | 추천 엔진 영향 |
|---|---|---|---|---|---:|---:|
| `batch/place_enrichment/list_review_candidates.py` | `place_enrichment_candidates` review list | 낮음 | 낮음 | dev/ops | 아니오 | 아니오 |
| `batch/place_enrichment/review_candidate.py` | place enrichment candidate approve/reject/skip | 중간 | 중간 | dev/ops | review_status write | 아니오 |
| `batch/place_enrichment/list_representative_candidates.py` | representative candidate list | 낮음 | 낮음 | dev/ops | 아니오 | 아니오 |
| `batch/place_enrichment/review_representative_candidate.py` | representative candidate approve/reject/skip | 중간 | 중간 | dev/ops | review_status write | 아니오 |
| `tests/test_review_candidate_workflow.py` | review workflow 테스트 | 낮음 | 낮음 | test | 아니오 | 아니오 |

### Promote Dry-run

| 관련 파일 | 역할 | 운영 영향도 | 수정 시 위험도 | 상태 | places 수정 | 추천 엔진 영향 |
|---|---|---|---|---|---:|---:|
| `batch/place_enrichment/promote_dry_run.py` | place enrichment candidate summary | 낮음 | 낮음 | experimental | 아니오 | 아니오 |
| `batch/place_enrichment/representative_promote_dry_run.py` | representative POI promote impact dry-run | 중간 | 중간 | experimental | 아니오 | 간접 분석 |
| `docs/REPRESENTATIVE_POI_PROMOTE_POLICY.md` | 대표 POI promote 정책 | 낮음 | 낮음 | report-only | 아니오 | 아니오 |

현재 actual promote는 구현하지 않았다.

### Frontend UI

| 관련 파일 | 역할 | 운영 영향도 | 수정 시 위험도 | 상태 | places 수정 | 추천 엔진 영향 |
|---|---|---|---|---|---:|---:|
| `frontend/src/App.jsx` | 화면 routing, dev screen review gate | 높음 | 중간 | production | 아니오 | API 호출 간접 |
| `frontend/src/components/common/MobileShell.jsx` | 모바일 shell, bottom nav, preview frame | 높음 | 중간 | production | 아니오 | 아니오 |
| `frontend/src/screens/day-trip/HomeScreen.jsx` | 지역/출발지/옵션 선택, `/api/regions`, departures 호출 | 높음 | 중간 | production | 아니오 | API 호출 간접 |
| `frontend/src/screens/day-trip/ConditionScreen.jsx` | 조건 선택 | 중간 | 낮음 | production | 아니오 | payload 영향 가능 |
| `frontend/src/screens/day-trip/CourseResultScreen.jsx` | 코스 생성, 결과 표시, 교체, 추가, 저장, 재계산 | 매우 높음 | 높음 | production | 아니오 | API 호출 영향 |
| `frontend/src/screens/day-trip/CourseEditScreen.jsx` | 코스 편집 UI | 중간 | 중간 | production/dev | 아니오 | API 호출 가능 |
| `frontend/src/screens/day-trip/MyScreen.jsx` | 저장/마이 화면 | 낮음 | 낮음 | production/placeholder | 아니오 | 아니오 |
| `frontend/src/index.css`, `frontend/src/App.css` | safe-area, layout, styling | 높음 | 중간 | production | 아니오 | 아니오 |
| `frontend/vite.config.js` | API proxy to travel API | 높음 | 높음 | production/dev | 아니오 | API 연결 영향 |

최근 UI 관련 상태:

- production에서 5화면 검증 UI는 `import.meta.env.DEV` 또는 `VITE_SHOW_SCREEN_REVIEW=true`로 gate.
- 저장 기능은 임시 비활성/준비중 상태로 정리된 이력이 있음.
- 모바일 safe-area / bottom CTA / pull-to-refresh 관련 수정 이력이 있다.

### Deployment / Nginx / Docker

| 관련 파일 | 역할 | 운영 영향도 | 수정 시 위험도 | 상태 | places 수정 | 추천 엔진 영향 |
|---|---|---|---|---|---:|---:|
| `Dockerfile.staging` | backend staging image | 높음 | 높음 | deployment | 아니오 | 배포 영향 |
| `frontend/Dockerfile.staging` | frontend staging image | 높음 | 높음 | deployment | 아니오 | 배포 영향 |
| `docker-compose.staging.yml` | compose 배포 구성 | 높음 | 높음 | deployment | 아니오 | 배포 영향 |
| `frontend/nginx.staging.conf` | static serving/proxy | 높음 | 높음 | deployment | 아니오 | API 연결 영향 |
| `staging_deploy.sh` | EC2 git pull/build/up 배포 | 높음 | 높음 | deployment | 아니오 | 배포 영향 |
| `.dockerignore` | Docker build exclude | 중간 | 중간 | deployment | 아니오 | 배포 영향 |
| `.gitignore` | 민감정보/덤프 제외 | 높음 | 중간 | repo safety | 아니오 | 아니오 |
| `.env.example`, `.env.staging.example` | env template | 중간 | 중간 | deployment | 아니오 | 설정 영향 |

### Docs / Reports

| 파일 | 역할 | 상태 |
|---|---|
| `docs/REPRESENTATIVE_POI_AUDIT.md` | 대표 POI 기준표/누락 감사 | report-only |
| `docs/REPRESENTATIVE_POI_CANDIDATE_DRY_RUN_REPORT.md` | 대표 후보 external dry-run 결과 | report-only |
| `docs/REPRESENTATIVE_POI_CANDIDATE_STAGING_WRITE_REPORT.md` | representative staging write 결과 | report-only |
| `docs/REPRESENTATIVE_POI_REVIEW_WORKFLOW_REPORT.md` | representative review workflow 결과 | report-only |
| `docs/REPRESENTATIVE_POI_PROMOTE_DRY_RUN_REPORT.md` | promote dry-run 결과 | report-only |
| `docs/REPRESENTATIVE_POI_ENRICHMENT_AUDIT_REPORT.md` | image/overview audit 결과 | report-only |
| `docs/REPRESENTATIVE_POI_MANUAL_ENRICHMENT_WORKFLOW_REPORT.md` | manual enrichment workflow 결과 | report-only |
| `docs/REPRESENTATIVE_POI_MANUAL_ENRICHMENT_REVIEW_REPORT.md` | manual enrichment review 결과 | report-only |
| `docs/REPRESENTATIVE_POI_PROMOTE_POLICY.md` | promote policy 설계 | report-only |
| `docs/SOURCE_STRUCTURE_MAP.md` | 현재 문서 | report-only |

### Migration

| 파일 | 역할 | 운영 영향도 | 상태 |
|---|---|---|---|
| `migration_001_places_v2.sql` | places v2 기본 schema | 높음 | migration |
| `migration_002_add_images.sql` | image 컬럼 추가 | 높음 | migration |
| `migration_002_incremental_sync.sql` | incremental sync | 중간 | migration |
| `migration_003_add_culture_role.sql` | culture role 추가 | 중간 | migration |
| `migration_004_add_indoor_outdoor.sql` | indoor/outdoor 추가 | 중간 | migration |
| `migration_005_add_saved_course_place_snapshots.sql` | saved course snapshot | 중간 | migration |
| `migration_006_course_operation_logs.sql` | course generation/extend logs | 중간 | migration |
| `migration_007_data_update_pipeline.sql` | data update pipeline tables | 중간 | migration/dev |
| `migration_008_external_places_pipeline.sql` | external places pipeline tables | 중간 | migration/dev |
| `migration_009_place_enrichment.sql` | place enrichment platform staging | 중간 | migration/dev |
| `migration_010_representative_poi_candidates.sql` | representative POI candidates | 중간 | migration/dev |

주의:

- migration 실행은 운영 DB에 직접 영향이 있으므로 별도 승인/백업/검증 필요.
- 현재 요청에서는 migration 실행하지 않았다.

## 개발 시 건드리면 안 되는 핵심 파일

특별한 작업 범위 없이 건드리면 안 되는 파일:

- `course_builder.py`
- `api_server.py`
- `database.py`
- `db_client.py`
- `tourism_belt.py`
- `anchor_definitions.py`
- `region_notices.py`
- `frontend/vite.config.js`
- `frontend/src/screens/day-trip/CourseResultScreen.jsx`
- `docker-compose.staging.yml`
- `staging_deploy.sh`
- `frontend/nginx.staging.conf`
- 모든 `migration_*.sql`

운영 데이터 변경 가능성이 있어 특히 주의할 파일:

- `database.py`
- `main.py`
- `batch/external/promote_external_places.py`
- `batch/steps/promote_places.py`
- `batch/update_all.sh --write`
- `batch/update_pipeline.py --no-dry-run --promote`
- `refetch_missing_overview.py`
- `refetch_coord_outliers.py`
- `repair_*.py`

## Dev / Experimental 파일

대표적으로 다음 파일은 아직 운영 핵심 경로가 아니라 staging/실험/검증 성격이다.

- `batch/update_pipeline.py`
- `batch/steps/*.py`
- `batch/external/*.py`
- `batch/place_enrichment/*.py`
- `batch/place_enrichment/adapters/*.py`
- `batch/place_enrichment/matching/*.py`
- `tests/*.py`
- `sql/verify/*.sql`
- `run_*verify*.py`
- `run_course_qa_report.py`
- `qa_diagnostic_runner.py`
- `docs/*.md`

단, experimental이라도 DB write가 가능한 파일은 실행 옵션을 조심해야 한다.

## Enrichment 관련 구현 현황

### 구현됨

- place enrichment staging DDL: `migration_009_place_enrichment.sql`
- representative POI staging DDL: `migration_010_representative_poi_candidates.sql`
- Kakao/Naver adapters
- Korean normalization / matching score / decision engine
- Kakao cafe image vertical slice
- Kakao/Naver compare slice
- manual image candidate CLI
- place enrichment review list/action CLI
- representative candidate collect/list/review CLI
- representative promote dry-run
- representative enrichment audit
- representative manual image/overview staging CLI
- representative manual enrichment review 결과 문서
- representative promote policy 문서

### 아직 미구현 또는 제한적

- actual representative promote
- approved image/overview를 결합한 강화 promote dry-run
- seed candidate staging table
- seed promote/rollback workflow
- production places insert/update workflow
- rollback snapshot table for representative promote
- real image quality verification
- manual curator UI
- Kakao/Naver image 수집: Local API 기준 부적합 확인

## 위험 파일 요약

| 위험 유형 | 파일 |
|---|---|
| 추천 결과 직접 변경 | `course_builder.py`, `tourism_belt.py`, `anchor_definitions.py`, `region_notices.py` |
| API 동작 변경 | `api_server.py`, `frontend/vite.config.js`, `CourseResultScreen.jsx` |
| places write | `database.py`, `main.py`, `batch/external/promote_external_places.py`, `batch/steps/promote_places.py`, `repair_*.py`, `refetch_*.py` |
| 배포 영향 | `staging_deploy.sh`, `docker-compose.staging.yml`, `Dockerfile.staging`, `frontend/nginx.staging.conf` |
| DB schema 변경 | `migration_*.sql`, `schema*.sql` |
| 외부 API/비용/쿼터 | `tourapi_fetcher.py`, `batch/external/collect_external_places.py`, `batch/place_enrichment/adapters/*.py` |

## 다음 개발 시 권장 작업 단위

1. `representative_promote_dry_run.py` 강화
   - representative place candidate와 manual enrichment candidate를 분리한다.
   - approved image/overview 결합 상태를 readiness에 반영한다.

2. 대표 이미지 후보 재등록
   - 경포대 image candidate 115는 reject되었으므로 실제 검증 가능한 이미지 후보를 manual workflow로 다시 등록한다.

3. representative promote snapshot 설계
   - actual promote 전 rollback snapshot table 또는 payload 구조를 먼저 설계한다.

4. seed candidate staging 설계
   - `tourism_belt.py` 직접 수정 대신 seed candidate/review/promote 단계를 만든다.

5. QA 영향 비교 도구
   - 기존 seed vs 대표 POI candidate가 코스 품질에 미치는 영향을 dry-run으로 비교한다.

6. 운영 반영은 마지막 단계
   - places insert/update, seed 변경은 별도 작업으로 분리하고 backup/QA/smoke/rollback을 선행한다.
