# Artifact Cleanup / Ignore Policy Plan

## 목표

운영에 불필요한 artifact가 다시 Git drift를 만들지 않도록 cleanup/ignore 정책을 정리한다.

현재 단계는 planning only다.

수행하지 않음:

- 파일 삭제
- git commit
- deploy
- docker build/up
- archive 실행

## 현재 상태

완료:

- Docker/compose source-of-truth commit 완료
- DB dump repo 밖 이동 완료
- `/app/travel`은 `LEGACY_ONLY`로 확인

남은 drift:

```text
 M .env.example
 M .gitignore
 M frontend/src/App.jsx
 M frontend/src/components/common/MobileShell.jsx
 M frontend/src/index.css
 M frontend/src/screens/day-trip/CourseResultScreen.jsx
 M frontend/src/screens/day-trip/HomeScreen.jsx
 M frontend/src/screens/day-trip/MyScreen.jsx
?? .dockerignore
?? .env.staging.example
?? .gitattributes
?? Dockerfile.staging
?? README.md
?? batch/place_enrichment/
?? batch/update_all.ps1
?? batch/update_all.sh
?? docker-compose.staging.yml
?? docs/
?? frontend/.env.example
?? frontend/.env.staging.example
?? frontend/Dockerfile.staging
?? frontend/nginx.staging.conf
?? frontend/src/utils/
?? migration_009_place_enrichment.sql
?? migration_010_representative_poi_candidates.sql
?? migration_011_seed_candidates.sql
?? staging_deploy.sh
?? tests/
```

## Artifact 분류

### test outputs

패턴:

```text
*_out.txt
_*.txt
test_*.json
qa_reports/
qa_output.txt
qa_results.json
```

상태:

- 운영 서버 drift 원인 중 하나
- 대부분 재생성 가능한 산출물

정책:

```text
ignore + archive optional
```

주의:

- 정식 regression fixture가 아닌 output만 ignore한다.
- 정식 테스트 입력 파일이면 `tests/fixtures/`로 이동해야 한다.

### QA reports

대상:

```text
docs/*REPORT.md
docs/*RUNBOOK.md
docs/*CHECKLIST.md
qa_reports/
```

정책:

- `qa_reports/` raw output은 ignore
- `docs/*.md` 형태로 정리한 최종 보고서는 git 유지 후보

기준:

```text
운영 의사결정/인수인계에 필요한 문서 = 유지
일회성 실행 raw output = ignore/archive
```

### debug scripts

대상 예:

```text
debug.py
run_fix_103.py
run_zone_verify.py
check_selection_basis.py
test_course.py
```

정책:

```text
archive or formalize
```

판단 기준:

- 재사용할 운영 도구라면 `tools/` 또는 `scripts/`로 명명 정리 후 유지
- 일회성 진단이면 archive 후 ignore/삭제 후보
- 직접 DB write/fix 성격이면 운영 repo root에 두지 않음

### local generated files

대상:

```text
node_modules/
frontend/node_modules/
dist/
frontend/dist/
.vite/
frontend/.vite/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
logs/
*.log
pipeline.log
```

정책:

```text
ignore
```

### DB dumps / backups

대상:

```text
*.dump
*.backup
*.bak
travel_db.sql
travel_db*.sql
travel_db*.dump
backups/
```

정책:

```text
ignore + repo 밖 보관
```

주의:

- migration SQL과 dump SQL을 반드시 구분한다.
- `migration_*.sql`은 유지 대상이다.
- `travel_db.sql` 같은 dump만 ignore한다.

### archive 대상

archive 후보:

```text
_anchor_test.txt
_course_quality_test.txt
_dq_diagnosis.txt
_enrich_test.txt
_template_test.txt
check_*_out.txt
test_sokcho*.json
debug.py
run_fix_103.py
```

정책:

```text
삭제 전 archive
```

이미 EC2 drift archive에는 tracked/untracked patch가 보존되어 있으나, 로컬 cleanup 전에도 필요 시 별도 archive 가능.

### git 유지 대상

유지 후보:

```text
Dockerfile
docker-compose.yml
frontend/Dockerfile
frontend/.dockerignore
Dockerfile.staging
docker-compose.staging.yml
frontend/Dockerfile.staging
frontend/nginx.staging.conf
staging_deploy.sh
README.md
.dockerignore
.gitattributes
.env.example
.env.staging.example
frontend/.env.example
frontend/.env.staging.example
docs/*.md
tests/
frontend/src/utils/
batch/place_enrichment/
migration_009_place_enrichment.sql
migration_010_representative_poi_candidates.sql
migration_011_seed_candidates.sql
```

단, 유지하려면 별도 commit 단위로 분리해야 한다.

## .gitignore preview

현재 `.gitignore`는 이미 아래 방향으로 강화되어 있다.

권장 최종 preview:

```gitignore
# IDE / temp
.history/
.claude/
.vscode/
.idea/

# Python
.venv/
venv/
__pycache__/
*.py[cod]
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Frontend
node_modules/
frontend/node_modules/
dist/
frontend/dist/
.vite/
frontend/.vite/

# QA / local outputs
qa_reports/
qa_output.txt
qa_results.json
*_out.txt
_*.txt
test_*.json

# logs
logs/
*.log
pipeline.log

# env / secrets
.env
.env.*
!.env.example
!.env.*.example
frontend/.env
frontend/.env.*
!frontend/.env.example
!frontend/.env.*.example

# DB dumps / backups
backups/
*.dump
*.backup
*.bak
travel_db.sql
travel_db*.sql
travel_db*.dump

# OS
Thumbs.db
.DS_Store
```

추가 검토:

- `test_*.json`을 ignore하면 정식 fixture 파일도 무시될 수 있다.
- 정식 fixture가 필요하면 `tests/fixtures/*.json` 예외를 추가한다.

예:

```gitignore
test_*.json
!tests/fixtures/*.json
```

## migration/sql과 dump 구분 정책

### 유지 대상

반드시 git 유지:

```text
migration_*.sql
sql/**/*.sql
```

단, `sql/` 안에 dump를 넣지 않는다.

### ignore 대상

무조건 git 제외:

```text
travel_db.sql
travel_db*.sql
*.dump
*.backup
*.bak
```

### 정책

- schema migration은 repo에서 관리
- DB snapshot/dump는 repo 밖 `/home/ubuntu/backups/...`에서 관리
- dump 파일명에는 날짜/환경을 포함

예:

```text
/home/ubuntu/backups/travel_data_pipeline/db_dumps/travel_db_20260508.dump
```

## 유지 대상

### docs/report 기준

유지할 문서:

- 배포 runbook
- staging smoke test
- EC2 audit
- drift archive report
- source-of-truth reconciliation report
- production readiness QA checklist

유지 기준:

```text
운영자가 재사용하거나 의사결정 근거로 삼는 문서
```

archive-only 문서:

```text
일회성 중간 출력, raw command log
```

현재 `docs/`의 다수 문서는 운영 복구 과정의 근거이므로 유지 후보로 본다.

### frontend/src/utils

상태:

```text
untracked
```

예상 역할:

- localStorage 저장/복원/regenerate MVP 유틸

정책:

```text
git 유지 후보
```

이유:

- 사용자-facing 저장 기능 구현에 필요한 runtime source일 가능성이 높다.
- ignore 대상이 아니다.
- frontend UI commit과 함께 묶는 것이 적절하다.

### batch/place_enrichment

상태:

```text
untracked
```

정책:

```text
git 유지 후보, but dev/experimental commit 분리
```

이유:

- representative/place enrichment governance 구현 파일
- 운영 추천 요청 path와 분리되어야 함
- production runtime과 혼동되지 않도록 별도 commit/문서 필요

권장:

- `batch/place_enrichment`는 frontend deploy commit과 분리
- migration 009/010/011과 함께 별도 governance commit 후보

### migration_009/010/011

상태:

```text
untracked
```

정책:

```text
git 유지 후보
```

주의:

- migration 실행은 별도 승인 전 금지
- commit해도 적용은 하지 않는다.

## archive 대상

삭제 전 archive 권장:

```text
_*.txt
*_out.txt
test_sokcho*.json
debug.py
run_fix_103.py
```

정책:

1. archive
2. `.gitignore`로 재발 방지
3. 정식 test로 승격할 파일만 `tests/`로 이동

## cleanup 후 예상 상태

### .gitignore commit 후 사라질 가능성이 높은 항목

```text
_*.txt
*_out.txt
test_*.json
qa_reports/
*.log
*.dump
travel_db*.sql
```

### 여전히 남아야 하는 항목

```text
.env.example
.env.staging.example
.gitattributes
.dockerignore
Dockerfile.staging
README.md
docker-compose.staging.yml
frontend/.env.example
frontend/.env.staging.example
frontend/Dockerfile.staging
frontend/nginx.staging.conf
frontend/src/utils/
batch/place_enrichment/
migration_009_place_enrichment.sql
migration_010_representative_poi_candidates.sql
migration_011_seed_candidates.sql
staging_deploy.sh
tests/
docs/
```

### 별도 commit 대상

1. ignore/env/docs policy
2. frontend saved/saju/UI feature
3. batch place enrichment governance
4. staging deploy files
5. migrations
6. line ending normalize

## clean 상태까지 남은 작업

1. `.gitignore` 강화 commit
2. `.env.example` / frontend env examples 정리 commit
3. frontend UI/storage/saju changes commit
4. docs/runbook commit 여부 결정
5. staging deploy files commit 여부 결정
6. batch/place_enrichment + migrations commit 여부 결정
7. line ending normalize separate commit
8. EC2와 로컬 source-of-truth sync
9. `git status --short` clean 확인

## deploy 금지 유지 확인

아직 deploy 금지.

실행 금지:

```bash
docker build
docker compose build
docker compose up
docker compose down
docker restart
nginx restart/reload
git clean
git reset
DB migration
```

이유:

- frontend UI drift와 line ending drift가 아직 정리되지 않았다.
- source-of-truth commit은 일부 완료됐지만 repo 전체는 clean 상태가 아니다.

## 다음 commit 단계

권장 다음 commit:

```text
chore: strengthen gitignore for deployment artifacts
```

포함 후보:

```text
.gitignore
.env.example
.env.staging.example
frontend/.env.example
frontend/.env.staging.example
.dockerignore
.gitattributes
```

주의:

- 이 commit에는 frontend UI source 변경을 넣지 않는다.
- batch/place_enrichment와 migration도 넣지 않는다.
- line ending normalize를 넣지 않는다.

그 다음 commit 후보:

```text
feat: add local saved courses and saju link UX
chore: add staging deploy assets
chore: add place enrichment governance tooling
chore: normalize line endings
```
