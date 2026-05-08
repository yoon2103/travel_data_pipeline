# Travel Frontend VITE Env Injection Design

## 목표

`travel-frontend` production/staging Docker build 시 `VITE_*` 환경값이 Vite bundle에 안전하게 반영되도록 최소 수정 방향을 설계한다.

이번 문서는 설계/진단 중심이다. 실제 배포, nginx 수정, backend 수정, DB 수정은 수행하지 않는다.

## 현재 frontend build 구조

### EC2 운영 구조 기준

EC2 진단 결과:

- travel frontend path: `/home/ubuntu/travel_data_pipeline/frontend`
- travel frontend container: `travel-frontend`
- serving 방식: nginx static
- static root: `/usr/share/nginx/html`
- upstream nginx:
  - `travel-planne.duckdns.org/` → `travel-frontend:80`
  - `travel-planne.duckdns.org/api/` → `travel-backend:8000`

EC2 travel frontend Dockerfile:

```dockerfile
FROM node:20 AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
```

EC2 travel compose:

```yaml
services:
  travel-frontend:
    build:
      context: ./frontend
    container_name: travel-frontend
    restart: unless-stopped
    expose:
      - "80"
    networks:
      - saju-net
```

확인 결과:

- `build.args` 없음
- frontend 전용 `env_file` 없음
- runtime env로 `VITE_*` 없음
- `/home/ubuntu/travel_data_pipeline/frontend/.env` 없음

### 로컬 staging 구조 기준

로컬 `frontend/Dockerfile.staging`:

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.staging.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
```

로컬 `docker-compose.staging.yml`:

```yaml
travel-frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile.staging
  container_name: travel-frontend-staging
  depends_on:
    - travel-api
  ports:
    - "${FRONTEND_PORT:-4175}:80"
  restart: unless-stopped
```

확인 결과:

- staging Dockerfile도 `ARG VITE_*` 없음
- staging compose도 `build.args` 없음
- `frontend/.env.example`, `frontend/.env.staging.example`에는 값 예시가 있으나 Docker build에 연결되어 있지 않음

## VITE env 문제 원인

Vite의 `import.meta.env.VITE_*` 값은 런타임 nginx container env가 아니라 build 시점에 JavaScript bundle로 주입된다.

현재 구조의 문제:

1. frontend Docker build 단계에서 `VITE_SHOW_SAJU_LINK`, `VITE_SAJU_SERVICE_URL`을 전달하지 않는다.
2. nginx static runtime container에 env를 넣어도 이미 빌드된 JS에는 반영되지 않는다.
3. EC2 travel frontend에는 `frontend/.env`도 없고 compose `build.args`도 없다.
4. 따라서 사주 링크 구현이 코드에 있어도 production build 결과물에는 기본적으로 `undefined`로 들어갈 가능성이 높다.

결론:

- 현재 EC2 travel-frontend production build에는 사주 링크 env가 안정적으로 반영되지 않는다.
- 해결은 frontend image build 단계에서만 해야 한다.

## 권장 env 주입 방식

권장 방식: Dockerfile `ARG` + compose `build.args`

이유:

- Vite env는 build-time 값이므로 Docker build arg가 가장 직접적이다.
- nginx runtime/env를 수정할 필요가 없다.
- `saju-nginx`를 건드리지 않는다.
- `travel-backend`를 건드리지 않는다.
- `travel-frontend`만 rebuild 가능하다.
- 값이 public frontend config라는 점과 맞다.

### 권장 Dockerfile 변경안

`frontend/Dockerfile` 또는 운영에서 사용하는 frontend Dockerfile build stage에 추가:

```dockerfile
ARG VITE_SHOW_SAJU_LINK=false
ARG VITE_SAJU_SERVICE_URL=

ENV VITE_SHOW_SAJU_LINK=$VITE_SHOW_SAJU_LINK
ENV VITE_SAJU_SERVICE_URL=$VITE_SAJU_SERVICE_URL
```

적용 위치:

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
```

staging Dockerfile도 동일하게 적용한다.

### 권장 compose 변경안

운영 compose의 `travel-frontend.build.args`에 추가:

```yaml
travel-frontend:
  build:
    context: ./frontend
    args:
      VITE_SHOW_SAJU_LINK: ${VITE_SHOW_SAJU_LINK:-false}
      VITE_SAJU_SERVICE_URL: ${VITE_SAJU_SERVICE_URL:-}
```

staging compose도 동일하게 적용:

```yaml
travel-frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile.staging
    args:
      VITE_SHOW_SAJU_LINK: ${VITE_SHOW_SAJU_LINK:-false}
      VITE_SAJU_SERVICE_URL: ${VITE_SAJU_SERVICE_URL:-}
```

### env file 전략

운영 EC2에서 사용할 수 있는 선택지:

1. `/home/ubuntu/travel_data_pipeline/.env`에 frontend public env key 추가
2. 또는 frontend 전용 `.env.production`/`.env.staging`를 두고 compose 실행 시 `--env-file` 사용

권장:

- backend secrets가 있는 `.env`에 frontend public env를 섞는 것도 가능하지만 운영 혼선을 줄이려면 frontend 전용 env file이 더 명확하다.
- 단, 현재 compose는 root `.env`를 자동으로 읽으므로 최소 수정만 보면 root `.env`에 아래 key를 추가하는 방식이 가장 작다.

필요 key:

```env
VITE_SHOW_SAJU_LINK=true
VITE_SAJU_SERVICE_URL=https://saju-mbti-service.duckdns.org/
```

값은 public bundle에 포함되므로 secret을 넣으면 안 된다.

## 최소 수정 파일

운영 구조 기준 최소 수정:

1. `/home/ubuntu/travel_data_pipeline/frontend/Dockerfile`
   - `ARG VITE_SHOW_SAJU_LINK`
   - `ARG VITE_SAJU_SERVICE_URL`
   - build stage `ENV` 추가

2. `/home/ubuntu/travel_data_pipeline/docker-compose.yml`
   - `travel-frontend.build.args` 추가

3. `/home/ubuntu/travel_data_pipeline/.env`
   - public frontend key 추가
   - 값 출력/commit 금지

로컬/staging 구조까지 맞추려면:

4. `frontend/Dockerfile.staging`
   - 동일한 `ARG`/`ENV` 추가

5. `docker-compose.staging.yml`
   - 동일한 `build.args` 추가

6. `frontend/.env.staging.example`
   - 이미 있음. 현재 값은 적절함.

## 사주 영향 여부

권장 방식은 사주 서비스에 직접 영향이 없다.

영향 없는 이유:

- `saju-nginx` 설정을 수정하지 않는다.
- `saju-nginx`를 restart하지 않는다.
- `saju-frontend`, `saju-backend`를 rebuild/restart하지 않는다.
- `travel-backend`를 rebuild/restart하지 않는다.
- Docker network는 기존 `saju_mbti_saju-net`을 그대로 사용한다.
- travel domain routing은 그대로 유지된다.

주의:

- `saju-nginx`가 두 도메인을 모두 라우팅하므로 nginx 파일 수정은 금지한다.
- `docker compose up -d --build`를 전체로 실행하면 불필요한 서비스 재생성 위험이 있다.
- 반드시 `travel-frontend` 단일 서비스만 대상으로 해야 한다.

## Rollback 영향

frontend-only rollback 범위:

- 이전 `travel-frontend` image/build로 되돌리면 된다.
- DB rollback 불필요
- backend rollback 불필요
- nginx rollback 불필요
- 사주 서비스 rollback 불필요

rollback trigger:

- travel 화면 blank
- JS/CSS asset 404
- 사주 버튼 env OFF인데 노출
- 사주 버튼 env ON인데 미노출
- 사주 링크 URL 오동작
- `/api/regions` proxy 실패
- 코스 생성 실패

rollback 전 준비:

- 기존 `travel-frontend` image id 확인
- 기존 container 상태 확인
- 새 image build 전 tag 또는 image id 기록

## Rollout 위험 분석

| 위험 | 가능성 | 영향 | 대응 |
| --- | --- | --- | --- |
| Vite env가 여전히 미반영 | 중간 | 사주 버튼 미노출 | build artifact에서 `saju-mbti-service` 문자열 확인 |
| compose 전체 재시작 실수 | 중간 | 사주/여행 영향 | `docker compose up -d --build travel-frontend`만 사용 |
| nginx 재시작 | 낮음 | 두 도메인 영향 | nginx untouched 원칙 유지 |
| env에 secret 추가 | 낮음 | secret bundle 노출 | `VITE_*`에는 public 값만 허용 |
| cache로 이전 asset 유지 | 중간 | 변경 미노출 | asset hash 확인, 강력 새로고침 |
| frontend build 실패 | 중간 | 배포 지연 | 로컬/staging에서 lint/build 선검증 |

## 안전한 적용 순서

실제 적용 시 권장 절차:

1. 로컬에서 Dockerfile/compose 최소 수정
2. `npm run lint`
3. `npm run build`
4. Docker build args가 반영되는지 로컬/staging build 확인
5. build 결과에서 사주 도메인 문자열 확인
   - 예: built JS에 `saju-mbti-service.duckdns.org` 존재 확인
6. Git commit/push
7. EC2 `/home/ubuntu/travel_data_pipeline`에서 pull
8. EC2 `.env` 또는 frontend env file에 public key 존재 확인
9. 기존 `travel-frontend` image id 기록
10. `travel-frontend`만 rebuild/recreate
    - 예: `docker compose up -d --build travel-frontend`
11. nginx/saju 컨테이너 상태 변경 없는지 확인
12. smoke test
    - `http://travel-planne.duckdns.org/`
    - `http://travel-planne.duckdns.org/api/regions`
    - MyScreen 사주 버튼 노출
    - 사주 링크 이동
13. 사주 smoke
    - `http://saju-mbti-service.duckdns.org/result`

## 건드리면 안 되는 항목

이번 env 주입 작업에서 수정/재시작 금지:

- `/home/ubuntu/saju_mbti/nginx/default.conf`
- `saju-nginx`
- `saju-frontend`
- `saju-backend`
- `/home/ubuntu/saju_mbti/.env`
- `/home/ubuntu/saju_mbti/.env.production`
- `travel-backend`
- `api_server.py`
- `course_builder.py`
- `tourism_belt.py`
- `migration_*.sql`
- 운영 DB
- places table
- representative/seed promote actual workflow

## 다음 작업 제안

1. `frontend/Dockerfile.staging`와 운영 `frontend/Dockerfile`에 `ARG/ENV VITE_*` 구조를 추가한다.
2. `docker-compose.staging.yml`와 운영 `docker-compose.yml`에 `travel-frontend.build.args`를 추가한다.
3. 로컬/staging에서 Docker build 후 built JS에 사주 도메인이 포함되는지 확인한다.
4. EC2에서는 `travel-frontend`만 rebuild/recreate한다.
5. 배포 후 사주 도메인과 여행 도메인을 모두 smoke test한다.
