# Docker/Compose Reconciliation Diff Preview

## 목표

운영 Docker/compose 파일을 실제 Git source-of-truth로 반영하기 전에, EC2 archive 파일과 로컬 최신 파일의 diff를 확인하고 최종 merge preview를 정리한다.

이번 작업은 file compare + planning only다.

수행하지 않음:

- git add
- git commit
- docker build
- deploy
- 파일 수정

## 비교 대상

EC2 archive 기준:

```text
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked
```

로컬 기준:

```text
D:\travel_data_pipeline
```

대상 파일:

```text
Dockerfile
docker-compose.yml
frontend/Dockerfile
frontend/.dockerignore
```

## 실제 diff 요약

### Dockerfile

로컬 상태:

```text
LOCAL_MISSING
```

EC2 archive 파일:

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

```text
EC2 운영 기준 유지
```

이유:

- 현재 운영 `travel-backend` image build source다.
- frontend-only 배포와 직접 관련은 없지만 운영 재현성에 필요하다.
- Git source-of-truth에 포함되어야 한다.

### docker-compose.yml

diff:

```diff
 services:
   travel-frontend:
     build:
       context: ./frontend
+      args:
+        VITE_SHOW_SAJU_LINK: ${VITE_SHOW_SAJU_LINK:-false}
+        VITE_SAJU_SERVICE_URL: ${VITE_SAJU_SERVICE_URL:-}
     container_name: travel-frontend
```

판정:

```text
merge 필요
```

유지할 EC2 구조:

- `travel-backend`
- `travel-frontend`
- `container_name`
- `restart: unless-stopped`
- `expose: "8000"`
- `expose: "80"`
- external network `saju_mbti_saju-net`

유지할 로컬 최신 수정:

- `travel-frontend.build.args`
- `VITE_SHOW_SAJU_LINK`
- `VITE_SAJU_SERVICE_URL`

제거할 drift:

- 없음

### frontend/Dockerfile

diff:

```diff
 COPY package*.json ./
 RUN npm install
 
+ARG VITE_SHOW_SAJU_LINK=false
+ARG VITE_SAJU_SERVICE_URL=
+
+ENV VITE_SHOW_SAJU_LINK=$VITE_SHOW_SAJU_LINK
+ENV VITE_SAJU_SERVICE_URL=$VITE_SAJU_SERVICE_URL
+
 COPY . .
 RUN npm run build
```

판정:

```text
merge 필요
```

유지할 EC2 구조:

- `FROM node:20 AS build`
- `npm install`
- `npm run build`
- `FROM nginx:alpine`
- static serving `/usr/share/nginx/html`
- `EXPOSE 80`

유지할 로컬 최신 수정:

- `ARG VITE_SHOW_SAJU_LINK=false`
- `ARG VITE_SAJU_SERVICE_URL=`
- `ENV VITE_SHOW_SAJU_LINK=$VITE_SHOW_SAJU_LINK`
- `ENV VITE_SAJU_SERVICE_URL=$VITE_SAJU_SERVICE_URL`

제거할 drift:

- 없음

### frontend/.dockerignore

로컬 상태:

```text
LOCAL_MISSING
```

EC2 archive 파일:

```text
node_modules
dist
.vite
.env
```

판정:

```text
EC2 운영 기준 유지
```

이유:

- frontend build context에서 local build output과 env를 제외한다.
- `.env`는 Docker context에 들어가지 않고 compose build args로만 전달하는 구조가 맞다.

## Merge preview

### 유지할 EC2 구조

- backend Dockerfile의 uvicorn `8000` 운영 구조
- compose service names
  - `travel-backend`
  - `travel-frontend`
- container names
  - `travel-backend`
  - `travel-frontend`
- `saju_mbti_saju-net` external network
- `travel-backend` expose `8000`
- `travel-frontend` expose `80`
- frontend nginx static serving
- frontend `.dockerignore`의 `.env` 제외

### 유지할 로컬 최신 수정

- `docker-compose.yml`
  - `travel-frontend.build.args`
- `frontend/Dockerfile`
  - VITE build-time `ARG/ENV`

### 제거할 drift

현재 Docker/compose 대상에서는 제거할 drift 없음.

다만 별도 작업에서 정리할 drift:

- backend/engine line ending drift
- frontend UI drift
- 테스트/진단 산출물 drift

## docker-compose.yml 최종 preview

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

확인:

- `saju_mbti_saju-net` 유지
- `travel-frontend.build.args` 포함
- backend service 구조 untouched
- host port publish 없음
- nginx 설정 변경 없음

## frontend/Dockerfile 최종 preview

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

확인:

- nginx static serving 유지
- VITE build-time env 주입 포함
- backend/API/proxy 구조 변경 없음

## .dockerignore preview

```text
node_modules
dist
.vite
.env
```

판정:

- 현재 EC2 운영 기준 그대로 유지 권장.
- `.env` 제외는 유지해야 한다.
- public frontend env는 `.env` 파일 copy가 아니라 compose build args로 전달한다.

## 예상 git 상태

Docker/compose source-of-truth 반영 후 사라져야 할 untracked:

```text
?? Dockerfile
?? docker-compose.yml
?? frontend/Dockerfile
?? frontend/.dockerignore
```

그러나 이 단계만으로 전체 clean은 아니다.

남을 가능성이 높은 항목:

```text
 M api_server.py
 M course_builder.py
 M regional_zone_builder.py
 M frontend/src/App.jsx
 M frontend/src/components/common/MobileShell.jsx
 M frontend/src/index.css
 M frontend/src/screens/day-trip/HomeScreen.jsx
 M test/diagnostic artifacts
?? batch/update_all.ps1
?? batch/update_all.sh
```

따라서 이후 별도 정리 필요:

- line ending normalize
- frontend UI drift reconcile
- batch wrapper source-of-truth 판단
- test/diagnostic artifact cleanup

## line ending normalize와 분리 유지 확인

Docker/compose reconciliation과 line ending normalize는 분리해야 한다.

이유:

- `course_builder.py`는 추천 엔진 핵심 파일이다.
- 현재 backend/engine drift는 `--ignore-space-at-eol` 기준 실질 로직 diff가 없는 것으로 확인됐다.
- Docker/compose 변경과 line ending 정리를 섞으면 리뷰와 rollback이 어려워진다.

권장 분리:

1. Docker/compose source-of-truth 반영
2. frontend VITE env injection 반영
3. line ending normalize
4. frontend UI drift reconcile
5. artifact cleanup

## deploy 금지 유지 확인

아직 deploy 금지 상태다.

실행 금지:

```bash
docker compose build
docker compose build travel-frontend
docker compose up -d
docker compose up -d --build
docker compose up -d --no-deps travel-frontend
docker compose down
docker restart saju-nginx
sudo nginx -s reload
```

이유:

- EC2 working tree가 아직 clean하지 않다.
- Docker/compose source-of-truth가 아직 git에 확정되지 않았다.
- line ending/frontend drift가 아직 남아 있다.

## 다음 실제 반영 단계

다음 요청에서 수행할 수 있는 최소 실제 반영 단위:

1. 로컬 repo에 `Dockerfile` 추가
   - EC2 운영 backend Dockerfile 기준
2. 로컬 repo에 `frontend/.dockerignore` 추가
   - EC2 운영 기준
3. `docker-compose.yml` 유지
   - 현재 로컬 파일이 최종 preview와 일치
4. `frontend/Dockerfile` 유지
   - 현재 로컬 파일이 최종 preview와 일치
5. `git diff -- Dockerfile docker-compose.yml frontend/Dockerfile frontend/.dockerignore` 확인
6. `npm run build` 확인
7. Docker build는 아직 별도 deploy 준비 단계에서 수행

주의:

- git add/commit은 별도 요청에서만 수행.
- EC2 반영은 clean 상태 확보 이후 수행.
