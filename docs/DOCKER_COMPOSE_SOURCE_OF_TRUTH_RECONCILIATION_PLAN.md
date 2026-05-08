# Docker/Compose Source-of-truth Reconciliation Plan

## 목표

EC2 운영 서버에서 untracked 상태인 Docker/compose 파일을 Git source-of-truth로 안전하게 복구한다.

현재 상태:

- drift archive 완료
- DB dump repo 밖 이동 완료
- 운영 Docker/compose 파일은 아직 EC2에서 untracked
- frontend deploy는 `BLOCKED`

이 문서는 planning/reconciliation only다. 코드 수정, git add/commit, docker build, deploy는 수행하지 않는다.

## Reconciliation 대상

대상 파일:

```text
Dockerfile
docker-compose.yml
frontend/Dockerfile
frontend/.dockerignore
```

### Dockerfile

역할:

- `travel-backend` container build
- `uvicorn api_server:app --host 0.0.0.0 --port 8000`

EC2 운영 파일 상태:

```text
untracked
```

위험도:

```text
HIGH
```

이유:

- 운영 backend container 재현에 필요
- Git에 없으면 clone/pull 기반 배포가 불완전

### docker-compose.yml

역할:

- `travel-backend`
- `travel-frontend`
- external network `saju_mbti_saju-net`

EC2 운영 파일 상태:

```text
untracked
```

위험도:

```text
HIGH
```

이유:

- travel 서비스가 `saju-nginx`와 연결되는 핵심 운영 compose
- 현재 파일에는 `travel-frontend.build.args`가 없어 VITE env injection 미반영

### frontend/Dockerfile

역할:

- React/Vite build
- nginx static serving

EC2 운영 파일 상태:

```text
untracked
```

위험도:

```text
HIGH
```

이유:

- `travel-frontend` image build source
- 현재 파일에는 `ARG/ENV VITE_*`가 없어 사주 링크 env가 bundle에 안정적으로 들어가지 않음

### frontend/.dockerignore

역할:

- frontend Docker build context 정리
- `node_modules`, `dist`, `.vite`, `.env` 제외

EC2 운영 파일 상태:

```text
untracked
```

위험도:

```text
MEDIUM
```

이유:

- build context 안정화에 필요
- `.env`가 image build context에 들어가지 않도록 보호

## 비교 전략

### 1. EC2 운영 파일 기준 확보

이미 archive 완료:

```text
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/
```

보존된 파일:

```text
untracked/Dockerfile
untracked/docker-compose.yml
untracked/frontend/Dockerfile
untracked/frontend/.dockerignore
```

비교 기준으로 이 archive copy를 사용한다.

### 2. 로컬 최신 파일 기준 확보

로컬 repo 기준 확인 대상:

```text
D:\travel_data_pipeline\Dockerfile
D:\travel_data_pipeline\docker-compose.yml
D:\travel_data_pipeline\frontend\Dockerfile
D:\travel_data_pipeline\frontend\.dockerignore
```

현재 로컬 최신 작업에는 다음이 포함되어야 한다.

- `frontend/Dockerfile`에 `ARG/ENV VITE_*`
- `docker-compose.yml`에 `travel-frontend.build.args`
- EC2 운영 network `saju_mbti_saju-net` 유지

### 3. 구조 비교

비교 항목:

| 항목 | EC2 운영 파일 | 로컬 최신 파일 | 판단 |
| --- | --- | --- | --- |
| backend port | `8000` | 동일해야 함 | 운영 기준 유지 |
| backend command | `uvicorn api_server:app ... --port 8000` | 동일해야 함 | 운영 기준 유지 |
| frontend serving | nginx static | 동일해야 함 | 운영 기준 유지 |
| compose network | `saju_mbti_saju-net` external | 동일해야 함 | 운영 기준 유지 |
| frontend build args | 없음 | 있어야 함 | 로컬 최신 기준 반영 |
| `.env` build context 제외 | `frontend/.dockerignore` 포함 | 유지 | 운영 기준 유지 |

### 4. diff 검토 방식

실제 reconciliation 단계에서 사용할 read-only 비교 명령:

```bash
diff -u /home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/Dockerfile Dockerfile
diff -u /home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/docker-compose.yml docker-compose.yml
diff -u /home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/frontend/Dockerfile frontend/Dockerfile
diff -u /home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/frontend/.dockerignore frontend/.dockerignore
```

주의:

- 이 문서 작성 단계에서는 실행하지 않는다.
- 비교 결과를 보고 source-of-truth를 결정한다.

## VITE env 반영 전략

Vite env는 runtime nginx env가 아니라 build-time에 bundle에 들어간다.

따라서 source-of-truth 파일에는 아래 구조가 반드시 포함되어야 한다.

### frontend/Dockerfile

build stage:

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

### docker-compose.yml

`travel-frontend.build.args`:

```yaml
travel-frontend:
  build:
    context: ./frontend
    args:
      VITE_SHOW_SAJU_LINK: ${VITE_SHOW_SAJU_LINK:-false}
      VITE_SAJU_SERVICE_URL: ${VITE_SAJU_SERVICE_URL:-}
```

### EC2 .env

운영 `.env`에는 public frontend env가 있어야 한다.

```env
VITE_SHOW_SAJU_LINK=true
VITE_SAJU_SERVICE_URL=https://saju-mbti-service.duckdns.org/
```

주의:

- `VITE_*`에는 public 값만 둔다.
- DB password, API key, secret을 `VITE_*`로 만들면 안 된다.

## compose/network 유지 원칙

반드시 유지:

```yaml
networks:
  saju-net:
    external: true
    name: saju_mbti_saju-net
```

이유:

- `saju-nginx`가 같은 docker network에서 `travel-frontend`, `travel-backend`로 proxy한다.
- network 이름이 바뀌면 travel domain routing이 깨질 수 있다.

반드시 유지:

```yaml
travel-backend:
  expose:
    - "8000"

travel-frontend:
  expose:
    - "80"
```

이유:

- host port publish가 아니라 nginx container가 internal network로 접근하는 구조다.
- 운영 nginx route는 `travel-backend:8000`, `travel-frontend:80` 기준이다.

절대 변경 금지:

- `saju-nginx` config
- `saju_mbti_saju-net` external network
- 사주 compose
- 사주 frontend/backend container
- travel backend port
- nginx reload/restart

## source-of-truth 기준

### 운영 기준으로 유지할 항목

운영 EC2 파일을 기준으로 유지:

- `travel-backend` service name
- `travel-frontend` service name
- container name
  - `travel-backend`
  - `travel-frontend`
- external network
  - `saju_mbti_saju-net`
- backend expose port
  - `8000`
- frontend expose port
  - `80`
- frontend nginx static serving
- backend uvicorn command

### 로컬 최신 기준으로 반영할 항목

로컬 최신 작업을 기준으로 반영:

- `frontend/Dockerfile` `ARG/ENV VITE_*`
- `docker-compose.yml` `travel-frontend.build.args`
- `.gitignore`의 dump ignore 정책
- `.dockerignore` 유지/보강

### merge 필요 항목

merge 필요:

| 파일 | merge 기준 |
| --- | --- |
| `docker-compose.yml` | EC2 운영 network/service 구조 + 로컬 VITE build args |
| `frontend/Dockerfile` | EC2 nginx static build 구조 + 로컬 VITE ARG/ENV |
| `Dockerfile` | EC2 backend 운영 port/command 유지 + 로컬 Python 버전 정책 검토 |
| `frontend/.dockerignore` | EC2 제외 패턴 유지 + 필요 시 추가 |

## frontend-only deploy 영향 분석

reconciliation 후 frontend-only deploy 대상:

```bash
docker compose build travel-frontend
docker compose up -d --no-deps travel-frontend
```

영향 범위:

- `travel-frontend` image rebuild
- `travel-frontend` container recreate

영향 없어야 하는 범위:

- `travel-backend` rebuild/restart 없음
- `saju-nginx` restart 없음
- `saju-frontend` restart 없음
- `saju-backend` restart 없음
- DB/migration 없음
- representative overlay actual 적용 없음

위험:

- compose service name이 바뀌면 nginx routing 장애
- external network 누락 시 travel domain 502
- frontend build args 누락 시 사주 링크 미노출
- `.env` 누락 시 build args 기본값으로 사주 링크 OFF

완화:

- `docker compose config`로 service/network/build.args 확인
- `docker compose build travel-frontend`만 실행
- `docker compose up -d --no-deps travel-frontend`만 실행
- built JS에서 `saju-mbti-service.duckdns.org` 확인

## rollback 고려사항

reconciliation 전 보존 완료:

```text
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021
```

추가로 deploy 전 저장 필요:

```bash
docker inspect travel-frontend --format '{{.Image}}' > /tmp/travel-frontend-prev-image.txt
```

rollback 시나리오:

1. frontend build 성공 후 화면 blank
   - 이전 frontend image로 복구
2. 사주 링크 미노출
   - compose build args/env 확인 후 frontend-only rebuild
3. travel domain 502
   - `travel-frontend` container/network 확인
   - nginx restart는 금지
4. `/api/regions` 실패
   - backend status 확인
   - backend restart는 금지, 원인만 진단

rollback에서 금지:

- `docker compose down`
- `docker compose up -d --build`
- nginx restart/reload
- backend rebuild
- git reset/clean

## clean 상태 목표

최종 EC2 상태:

```bash
git status --short
```

기대:

```text
<empty>
```

또는 `.env`처럼 gitignore 대상인 운영 파일만 존재하고 status에 표시되지 않아야 한다.

clean 상태 달성을 위해 처리해야 하는 항목:

1. 운영 Docker/compose 파일 git 반영
2. DB dump repo 밖 이동 완료 상태 유지
3. `.gitignore` dump 패턴 반영
4. backend/engine line ending drift 정리
5. frontend UI drift commit 또는 폐기
6. 테스트/진단 산출물 archive/ignore/정리

## reconcile 후 예상 git status 상태

운영 Docker/compose 파일을 git source-of-truth에 반영한 뒤:

사라져야 할 untracked:

```text
?? Dockerfile
?? docker-compose.yml
?? frontend/Dockerfile
?? frontend/.dockerignore
```

이미 사라진 untracked:

```text
?? travel_db.dump
?? travel_db.sql
```

남을 수 있는 항목:

```text
 M api_server.py
 M course_builder.py
 M regional_zone_builder.py
 M frontend/src/App.jsx
 M frontend/src/components/common/MobileShell.jsx
 M frontend/src/index.css
 M frontend/src/screens/day-trip/HomeScreen.jsx
```

따라서 Docker/compose reconciliation만으로는 전체 clean이 되지 않는다.

추가 필요:

- line ending normalize
- frontend drift reconcile
- test/diagnostic artifacts 정리

## deploy 재개 조건

아래 조건을 모두 만족해야 한다.

### Git 조건

```bash
git status --short
```

결과가 clean이어야 한다.

### Env 조건

```bash
grep -E '^VITE_SHOW_SAJU_LINK=|^VITE_SAJU_SERVICE_URL=' .env
```

기대:

```env
VITE_SHOW_SAJU_LINK=true
VITE_SAJU_SERVICE_URL=https://saju-mbti-service.duckdns.org/
```

### Compose 조건

```bash
docker compose config | grep -A5 -B2 'VITE_SAJU'
docker compose config --services
```

기대:

- `travel-frontend.build.args`에 VITE 값 존재
- `travel-backend`
- `travel-frontend`
- external network `saju_mbti_saju-net`

### Build 조건

로컬/staging에서 이미 확인된 조건:

- `npm run build` PASS
- Docker build PASS
- built JS에 `saju-mbti-service.duckdns.org` 포함

### Safety 조건

- `saju-nginx` untouched
- backend untouched
- DB untouched
- representative overlay actual OFF

## 배포 재개 절차

조건 충족 후에만 실행:

```bash
cd /home/ubuntu/travel_data_pipeline

git status --short
git pull --ff-only

docker inspect travel-frontend --format '{{.Image}}' > /tmp/travel-frontend-prev-image.txt

docker compose build travel-frontend
docker compose up -d --no-deps travel-frontend

docker exec travel-frontend sh -c "grep -R 'saju-mbti-service.duckdns.org' -n /usr/share/nginx/html/assets | head"
curl -I http://travel-planne.duckdns.org/
curl -s http://travel-planne.duckdns.org/api/regions | head
curl -I http://saju-mbti-service.duckdns.org/result
```

## 다음 작업 제안

1. 로컬 repo의 운영 Docker/compose 파일과 EC2 archive 파일을 비교한다.
2. `docker-compose.yml`은 EC2 운영 network/service 구조를 유지하면서 VITE build args를 추가한 형태로 확정한다.
3. `frontend/Dockerfile`은 EC2 nginx static 구조를 유지하면서 VITE ARG/ENV를 추가한 형태로 확정한다.
4. 확정본을 git에 반영한다.
5. EC2 line ending/frontend drift 정리를 별도 단계로 진행한다.
6. clean 상태 확인 후 frontend-only deploy를 재개한다.
