# Docker/Compose Git Staging Verification Report

## 최종 판정

**PASS**

Docker/compose source-of-truth 파일만 git staging 되었고, backend/core engine, frontend UI drift, representative/overlay workflow는 staged diff에 포함되지 않았다.

수행하지 않음:

- git commit
- docker build
- deploy
- nginx/backend/DB 작업

## git add 대상

실행:

```bash
git add -- Dockerfile docker-compose.yml frontend/Dockerfile frontend/.dockerignore
```

대상:

```text
Dockerfile
docker-compose.yml
frontend/Dockerfile
frontend/.dockerignore
```

## git diff --cached 결과 요약

cached name-status:

```text
A	Dockerfile
A	docker-compose.yml
A	frontend/.dockerignore
A	frontend/Dockerfile
```

cached stat:

```text
Dockerfile             | 12 ++++++++++++
docker-compose.yml     | 30 ++++++++++++++++++++++++++++++
frontend/.dockerignore |  4 ++++
frontend/Dockerfile    | 21 +++++++++++++++++++++
4 files changed, 67 insertions(+)
```

`git diff --cached --check`:

```text
PASS
```

출력 없음. whitespace error 없음.

## 포함 파일

### Dockerfile

신규 backend 운영 Dockerfile.

핵심:

```dockerfile
FROM python:3.11-slim
EXPOSE 8000
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

신규 운영 compose.

핵심:

```yaml
travel-backend:
  expose:
    - "8000"

travel-frontend:
  build:
    context: ./frontend
    args:
      VITE_SHOW_SAJU_LINK: ${VITE_SHOW_SAJU_LINK:-false}
      VITE_SAJU_SERVICE_URL: ${VITE_SAJU_SERVICE_URL:-}
  expose:
    - "80"

networks:
  saju-net:
    external: true
    name: saju_mbti_saju-net
```

### frontend/.dockerignore

신규 frontend build context ignore.

```text
node_modules
dist
.vite
.env
```

### frontend/Dockerfile

신규 frontend production Dockerfile.

핵심:

```dockerfile
ARG VITE_SHOW_SAJU_LINK=false
ARG VITE_SAJU_SERVICE_URL=

ENV VITE_SHOW_SAJU_LINK=$VITE_SHOW_SAJU_LINK
ENV VITE_SAJU_SERVICE_URL=$VITE_SAJU_SERVICE_URL
```

nginx static serving 유지:

```dockerfile
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

## 포함되지 않은 핵심 파일

cached diff에 포함되지 않음:

```text
api_server.py
course_builder.py
regional_zone_builder.py
tourism_belt.py
frontend/src/App.jsx
frontend/src/components/common/MobileShell.jsx
frontend/src/index.css
frontend/src/screens/day-trip/HomeScreen.jsx
frontend/src/screens/day-trip/CourseResultScreen.jsx
frontend/src/screens/day-trip/MyScreen.jsx
batch/place_enrichment/
migration_009_place_enrichment.sql
migration_010_representative_poi_candidates.sql
migration_011_seed_candidates.sql
```

검증 명령:

```bash
git diff --cached --name-only | rg "^(api_server.py|course_builder.py|regional_zone_builder.py|frontend/src/|batch/place_enrichment|migration_|tourism_belt.py)"
```

결과:

```text
NO_CORE_OR_FRONTEND_UI_IN_CACHED_DIFF
```

## commit 범위 판정

판정:

```text
SAFE_TO_COMMIT_AS_DOCKER_COMPOSE_SOURCE_OF_TRUTH
```

commit 범위:

- production backend Dockerfile 추가
- production docker-compose 추가
- production frontend Dockerfile 추가
- frontend Docker build context ignore 추가
- VITE env build-time injection 포함
- `saju_mbti_saju-net` 유지

commit 범위에 없는 것:

- 추천 엔진 수정
- backend API 수정
- frontend UI 수정
- DB/migration 수정
- representative/seed governance 수정

권장 commit message:

```text
chore: add production docker compose source of truth
```

## line ending normalize 분리 확인

line ending normalize 대상은 staged diff에 포함되지 않았다.

분리 유지 대상:

```text
api_server.py
course_builder.py
regional_zone_builder.py
```

판정:

```text
PASS
```

Docker/compose source-of-truth commit과 line ending normalize commit을 분리할 수 있다.

## frontend UI drift 미포함 확인

frontend UI drift는 staged diff에 포함되지 않았다.

미포함:

```text
frontend/src/App.jsx
frontend/src/components/common/MobileShell.jsx
frontend/src/index.css
frontend/src/screens/day-trip/HomeScreen.jsx
frontend/src/screens/day-trip/CourseResultScreen.jsx
frontend/src/screens/day-trip/MyScreen.jsx
```

판정:

```text
PASS
```

UI drift는 별도 commit/검증 단계로 분리된다.

## deploy 금지 유지 확인

실행하지 않음:

```text
docker build
docker compose build
docker compose up
docker compose down
docker restart
nginx restart/reload
git commit
```

판정:

```text
DEPLOY STILL BLOCKED
```

이유:

- 전체 working tree dirty 상태는 아직 남아 있다.
- EC2 clean 상태 복구 전까지 production deploy 금지.

## rollback 관점

이번 staged diff는 source-of-truth 파일 추가만 포함한다.

rollback이 필요한 경우:

- commit 전이면 `git restore --staged Dockerfile docker-compose.yml frontend/Dockerfile frontend/.dockerignore`로 staging만 해제 가능.
- 파일 자체 삭제/폐기는 별도 판단 필요.
- production 배포가 아직 없으므로 runtime rollback은 필요 없다.

운영 배포 시 rollback 기준:

- `travel-frontend` image id를 배포 전 저장
- frontend-only recreate 실패 시 이전 image 기준 복구
- nginx/backend/saju는 rollback 대상 아님

## 다음 commit 단계

다음 단계에서 수행할 최소 명령:

```bash
git diff --cached -- Dockerfile docker-compose.yml frontend/Dockerfile frontend/.dockerignore
git commit -m "chore: add production docker compose source of truth"
```

주의:

- commit 전 cached diff 재확인.
- 다른 dirty 파일을 추가하지 않는다.
- line ending normalize, frontend UI drift, docs/report는 별도 commit으로 분리한다.
