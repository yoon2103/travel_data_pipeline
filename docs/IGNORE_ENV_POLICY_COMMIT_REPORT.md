# Ignore / Env Policy Commit Report

## 최종 판정

**PASS**

ignore/env/policy 파일만 Git commit했다.

수행하지 않음:

- deploy
- docker build
- docker compose up
- frontend UX/source staging
- line ending normalize
- batch/place_enrichment staging
- migration staging

## staged 파일

실행:

```bash
git add -- .gitignore .env.example .env.staging.example frontend/.env.example frontend/.env.staging.example .dockerignore .gitattributes
```

staged 결과:

```text
A	.dockerignore
M	.env.example
A	.env.staging.example
A	.gitattributes
M	.gitignore
A	frontend/.env.example
A	frontend/.env.staging.example
```

## git diff --cached 요약

```text
.dockerignore                 | 29 +++++++++++++++++++++++++
.env.example                  | 13 ++++++++---
.env.staging.example          | 28 ++++++++++++++++++++++++
.gitattributes                |  5 +++++
.gitignore                    | 50 +++++++++++++++++++++++++++++++++++--------
frontend/.env.example         |  5 +++++
frontend/.env.staging.example |  5 +++++
7 files changed, 123 insertions(+), 12 deletions(-)
```

## 포함하지 않은 핵심 파일 확인

검증 명령:

```bash
git diff --cached --name-only | rg "^(frontend/src/|api_server.py|course_builder.py|regional_zone_builder.py|batch/place_enrichment|migration_.*\.sql|tourism_belt.py)"
```

결과:

```text
NO_FORBIDDEN_FILES_IN_CACHED_DIFF
```

포함하지 않음:

```text
frontend/src/
api_server.py
course_builder.py
regional_zone_builder.py
batch/place_enrichment/
migration_*.sql
tourism_belt.py
```

## commit 결과

commit message:

```text
chore: strengthen artifact and env policies
```

commit hash:

```text
259f247
```

최근 commit:

```text
259f247 chore: strengthen artifact and env policies
33965e2 chore: add production docker compose source of truth
```

## git status 후

staged diff:

```text
<empty>
```

남은 drift:

```text
 M frontend/src/App.jsx
 M frontend/src/components/common/MobileShell.jsx
 M frontend/src/index.css
 M frontend/src/screens/day-trip/CourseResultScreen.jsx
 M frontend/src/screens/day-trip/HomeScreen.jsx
 M frontend/src/screens/day-trip/MyScreen.jsx
?? Dockerfile.staging
?? README.md
?? batch/place_enrichment/
?? batch/update_all.ps1
?? batch/update_all.sh
?? docker-compose.staging.yml
?? docs/
?? frontend/Dockerfile.staging
?? frontend/nginx.staging.conf
?? frontend/src/utils/
?? migration_009_place_enrichment.sql
?? migration_010_representative_poi_candidates.sql
?? migration_011_seed_candidates.sql
?? staging_deploy.sh
?? tests/
```

## deploy 미수행 확인

실행하지 않음:

```text
docker build
docker compose build
docker compose up
docker compose down
docker restart
nginx restart/reload
git push
```

## 남은 drift 요약

### frontend UX/source

```text
frontend/src/App.jsx
frontend/src/components/common/MobileShell.jsx
frontend/src/index.css
frontend/src/screens/day-trip/CourseResultScreen.jsx
frontend/src/screens/day-trip/HomeScreen.jsx
frontend/src/screens/day-trip/MyScreen.jsx
frontend/src/utils/
```

예상 성격:

- 모바일 safe-area/scroll
- mock frame 제거
- 저장/복원/regenerate
- 사주 링크
- 저장 utility

### staging/deploy files

```text
Dockerfile.staging
docker-compose.staging.yml
frontend/Dockerfile.staging
frontend/nginx.staging.conf
staging_deploy.sh
README.md
batch/update_all.sh
batch/update_all.ps1
```

### enrichment/governance

```text
batch/place_enrichment/
migration_009_place_enrichment.sql
migration_010_representative_poi_candidates.sql
migration_011_seed_candidates.sql
```

### docs/tests

```text
docs/
tests/
```

## 다음 commit 단계 제안

권장 분리:

1. frontend UX/source commit
   - saved courses
   - saju link
   - mobile shell/scroll
   - `frontend/src/utils`

2. staging/deploy assets commit
   - `Dockerfile.staging`
   - `docker-compose.staging.yml`
   - `frontend/Dockerfile.staging`
   - `frontend/nginx.staging.conf`
   - `staging_deploy.sh`
   - `README.md`

3. enrichment governance commit
   - `batch/place_enrichment`
   - migration 009/010/011

4. docs/tests commit
   - `docs/`
   - `tests/`

5. line ending normalize commit
   - only if still needed
   - keep separate from functional changes
