# Docker/Compose Source-of-truth Commit Report

## 최종 판정

**PASS**

Docker/compose source-of-truth 파일 4개만 Git commit했다.

수행하지 않음:

- deploy
- docker build
- docker compose up
- git reset/clean
- line ending normalize
- frontend UI drift staging/commit

## git status 전

commit 전 `git status --short`에는 여러 변경이 있었지만, staged 대상은 Docker/compose 4개 파일로 제한했다.

주요 상태:

```text
A  Dockerfile
A  docker-compose.yml
A  frontend/.dockerignore
A  frontend/Dockerfile
 M frontend/src/App.jsx
 M frontend/src/components/common/MobileShell.jsx
 M frontend/src/index.css
 M frontend/src/screens/day-trip/CourseResultScreen.jsx
 M frontend/src/screens/day-trip/HomeScreen.jsx
 M frontend/src/screens/day-trip/MyScreen.jsx
?? batch/place_enrichment/
?? migration_009_place_enrichment.sql
?? migration_010_representative_poi_candidates.sql
?? migration_011_seed_candidates.sql
```

## staged 파일

실행:

```bash
git add -- Dockerfile docker-compose.yml frontend/Dockerfile frontend/.dockerignore
```

staged 결과:

```text
A	Dockerfile
A	docker-compose.yml
A	frontend/.dockerignore
A	frontend/Dockerfile
```

## git diff --cached 요약

```text
Dockerfile             | 12 ++++++++++++
docker-compose.yml     | 30 ++++++++++++++++++++++++++++++
frontend/.dockerignore |  4 ++++
frontend/Dockerfile    | 21 +++++++++++++++++++++
4 files changed, 67 insertions(+)
```

포함 내용:

- production backend Dockerfile
- production docker-compose
- production frontend Dockerfile
- frontend Docker build context ignore
- `travel-frontend.build.args`
- `VITE_SHOW_SAJU_LINK`
- `VITE_SAJU_SERVICE_URL`
- `saju_mbti_saju-net` 유지

## 포함하지 않은 파일 확인

cached diff에 포함되지 않음:

```text
api_server.py
course_builder.py
regional_zone_builder.py
tourism_belt.py
frontend/src/
batch/place_enrichment/
migration_*
```

검증 결과:

```text
NO_FORBIDDEN_FILES_IN_CACHED_DIFF
```

## commit 결과

commit message:

```text
chore: add production docker compose source of truth
```

commit hash:

```text
33965e2
```

commit summary:

```text
33965e2 chore: add production docker compose source of truth
```

## git status 후

commit 후 staged diff는 비어 있다.

```text
git diff --cached --name-status
<empty>
```

남은 변경은 이번 commit 범위에서 의도적으로 제외했다.

남은 주요 변경:

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

## 다음 작업 제안

1. `.gitignore`와 DB dump ignore 정책을 별도 commit으로 정리한다.
2. frontend UI drift를 별도 commit으로 분리한다.
3. line ending normalize는 backend/engine과 분리해 별도 commit으로 처리한다.
4. 필요한 경우 docs/report 파일 commit 여부를 별도 판단한다.
5. push 전 `git log --oneline -3`와 `git status --short`를 다시 확인한다.
