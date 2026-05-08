# Docker/Compose Source-of-truth Preparation Report

## 최종 판정

**PREPARED**

운영 Docker/compose source-of-truth를 실제 Git 반영하기 직전 상태까지 로컬 repo에 준비했다.

수행하지 않음:

- git add
- git commit
- docker build
- deploy
- nginx 수정/재시작
- backend 수정
- DB 수정

## 최종 대상 파일

```text
Dockerfile
docker-compose.yml
frontend/Dockerfile
frontend/.dockerignore
```

현재 로컬 존재 여부:

| 파일 | 상태 |
| --- | --- |
| `Dockerfile` | 존재 |
| `docker-compose.yml` | 존재 |
| `frontend/Dockerfile` | 존재 |
| `frontend/.dockerignore` | 존재 |

## Preview 일치 여부

### Dockerfile

상태:

```text
MATCH
```

내용:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

판정:

- EC2 archive 운영 backend Dockerfile과 동일 구조
- backend command/port 유지

### docker-compose.yml

상태:

```text
MATCH
```

최종 구조:

```yaml
services:
  travel-backend:
    build:
      context: .
    container_name: travel-backend
    restart: unless-stopped
    env_file:
      - .env
    expose:
      - "8000"
    networks:
      - saju-net

  travel-frontend:
    build:
      context: ./frontend
      args:
        VITE_SHOW_SAJU_LINK: ${VITE_SHOW_SAJU_LINK:-false}
        VITE_SAJU_SERVICE_URL: ${VITE_SAJU_SERVICE_URL:-}
    container_name: travel-frontend
    restart: unless-stopped
    expose:
      - "80"
    networks:
      - saju-net

networks:
  saju-net:
    external: true
    name: saju_mbti_saju-net
```

판정:

- EC2 운영 compose 구조 유지
- `travel-frontend.build.args` 포함
- backend service untouched
- `saju_mbti_saju-net` 유지

### frontend/Dockerfile

상태:

```text
MATCH
```

최종 구조:

```dockerfile
FROM node:20 AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

ARG VITE_SHOW_SAJU_LINK=false
ARG VITE_SAJU_SERVICE_URL=

ENV VITE_SHOW_SAJU_LINK=$VITE_SHOW_SAJU_LINK
ENV VITE_SAJU_SERVICE_URL=$VITE_SAJU_SERVICE_URL

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
```

판정:

- nginx static serving 유지
- VITE build-time `ARG/ENV` 포함
- runtime nginx env 방식 사용하지 않음

### frontend/.dockerignore

상태:

```text
MATCH
```

최종 구조:

```text
node_modules
dist
.vite
.env
```

판정:

- EC2 archive 운영 파일과 동일
- `.env`는 build context에서 제외
- public VITE env는 compose build args로 전달

## 예상 git diff

현재 네 파일은 모두 untracked 상태다.

따라서 `git diff -- Dockerfile docker-compose.yml frontend/Dockerfile frontend/.dockerignore`는 출력이 없다.

실제 Git 반영 단계에서 예상되는 변경:

```text
new file: Dockerfile
new file: docker-compose.yml
new file: frontend/Dockerfile
new file: frontend/.dockerignore
```

핵심 내용:

- backend 운영 Dockerfile 추가
- 운영 compose 추가
- frontend 운영 Dockerfile 추가
- frontend Docker build context ignore 추가

## 예상 git status

현재 대상 파일 기준:

```text
?? Dockerfile
?? docker-compose.yml
?? frontend/.dockerignore
?? frontend/Dockerfile
```

다음 단계에서 `git add`하면 예상:

```text
A  Dockerfile
A  docker-compose.yml
A  frontend/.dockerignore
A  frontend/Dockerfile
```

주의:

- 아직 git add/commit은 수행하지 않았다.
- 전체 repo에는 이 외 다른 drift가 남아 있을 수 있다.

## VITE env 최종 확인

`frontend/Dockerfile`:

```text
ARG VITE_SHOW_SAJU_LINK=false
ARG VITE_SAJU_SERVICE_URL=
ENV VITE_SHOW_SAJU_LINK=$VITE_SHOW_SAJU_LINK
ENV VITE_SAJU_SERVICE_URL=$VITE_SAJU_SERVICE_URL
```

`docker-compose.yml`:

```text
VITE_SHOW_SAJU_LINK: ${VITE_SHOW_SAJU_LINK:-false}
VITE_SAJU_SERVICE_URL: ${VITE_SAJU_SERVICE_URL:-}
```

`docker compose config` 확인 결과:

```text
VITE_SAJU_SERVICE_URL: https://saju-mbti-service.duckdns.org/
VITE_SHOW_SAJU_LINK: "true"
```

판정:

```text
PASS
```

## Network 구조 확인

`docker-compose.yml`:

```yaml
networks:
  saju-net:
    external: true
    name: saju_mbti_saju-net
```

`docker compose config --services` 결과:

```text
travel-backend
travel-frontend
```

판정:

```text
PASS
```

유지 사항:

- `saju_mbti_saju-net` 유지
- `travel-backend` service 유지
- `travel-frontend` service 유지
- `saju-nginx` untouched

## line ending normalize와 충돌 여부

현재 작업은 신규 Docker/compose 파일 준비만 수행했다.

line ending normalize 대상과 분리된다.

분리 대상:

```text
api_server.py
course_builder.py
regional_zone_builder.py
frontend/src/App.jsx
frontend/src/components/common/MobileShell.jsx
frontend/src/index.css
frontend/src/screens/day-trip/HomeScreen.jsx
```

판정:

```text
NO CONFLICT
```

이유:

- 이번 대상은 Docker/compose source-of-truth 파일만이다.
- 추천 엔진/core backend 파일은 수정하지 않았다.
- line ending normalize는 별도 commit/단계로 분리해야 한다.

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

- 전체 repo clean 상태가 아직 아니다.
- line ending drift와 frontend UI drift가 별도로 남아 있다.
- EC2 clean 상태 확인 후에만 frontend-only deploy 재개 가능.

## 다음 실제 반영 단계

다음 요청에서 수행 가능한 최소 단계:

```bash
git add Dockerfile docker-compose.yml frontend/Dockerfile frontend/.dockerignore
git diff --cached -- Dockerfile docker-compose.yml frontend/Dockerfile frontend/.dockerignore
```

권장 commit 메시지:

```text
chore: add production docker compose source of truth
```

주의:

- commit 전 `git diff --cached` 확인 필수
- 이 commit에는 line ending normalize나 frontend UI drift를 섞지 않는다.
- deploy는 commit/push/EC2 clean 상태 확인 이후 별도 단계에서 수행한다.
