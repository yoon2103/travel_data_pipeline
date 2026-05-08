# Docker/Compose Reconciliation Execution Plan

## 목표

운영 EC2에서 untracked 상태로 남아 있는 Docker/compose 파일을 로컬 Git source-of-truth 기준으로 정리하기 위한 실제 실행 계획을 정의한다.

현재 단계에서는 준비 계획만 작성한다.

금지:

- git add/commit
- 파일 수정
- docker build
- deploy
- git reset/clean

## 대상 파일

reconciliation 대상:

```text
Dockerfile
docker-compose.yml
frontend/Dockerfile
frontend/.dockerignore
```

각 파일의 역할:

| 파일 | 역할 | 현재 상태 | 우선순위 |
| --- | --- | --- | --- |
| `Dockerfile` | travel-backend 운영 image build | EC2 untracked | HIGH |
| `docker-compose.yml` | travel backend/frontend 운영 compose | EC2 untracked | HIGH |
| `frontend/Dockerfile` | travel-frontend Vite build + nginx static serving | EC2 untracked | HIGH |
| `frontend/.dockerignore` | frontend build context 보호 | EC2 untracked | MEDIUM |

## 비교 절차

### 1. EC2 archive 기준 파일 확인

이미 보존된 archive 경로:

```text
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked
```

대상:

```text
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/Dockerfile
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/docker-compose.yml
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/frontend/Dockerfile
/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021/untracked/frontend/.dockerignore
```

### 2. 로컬 최신 파일 확인

로컬 기준:

```text
D:\travel_data_pipeline\Dockerfile
D:\travel_data_pipeline\docker-compose.yml
D:\travel_data_pipeline\frontend\Dockerfile
D:\travel_data_pipeline\frontend\.dockerignore
```

확인할 것:

- `frontend/Dockerfile`에 `ARG/ENV VITE_*` 존재 여부
- `docker-compose.yml`에 `travel-frontend.build.args` 존재 여부
- `saju_mbti_saju-net` external network 유지 여부
- `travel-backend` expose `8000` 유지 여부
- `travel-frontend` expose `80` 유지 여부

### 3. 비교 명령 초안

EC2에서 read-only 비교:

```bash
cd /home/ubuntu/travel_data_pipeline
ARCHIVE_DIR=/home/ubuntu/backups/travel_data_pipeline/drift_20260508_100021

diff -u "$ARCHIVE_DIR/untracked/Dockerfile" Dockerfile || true
diff -u "$ARCHIVE_DIR/untracked/docker-compose.yml" docker-compose.yml || true
diff -u "$ARCHIVE_DIR/untracked/frontend/Dockerfile" frontend/Dockerfile || true
diff -u "$ARCHIVE_DIR/untracked/frontend/.dockerignore" frontend/.dockerignore || true
```

로컬에서 비교:

```powershell
git diff -- Dockerfile docker-compose.yml frontend/Dockerfile frontend/.dockerignore
Get-Content Dockerfile
Get-Content docker-compose.yml
Get-Content frontend\Dockerfile
Get-Content frontend\.dockerignore
```

## Reconcile 기준

### EC2 운영 기준 유지

아래 항목은 EC2 운영 구조를 source-of-truth로 유지한다.

```yaml
services:
  travel-backend:
    container_name: travel-backend
    expose:
      - "8000"
    networks:
      - saju-net

  travel-frontend:
    container_name: travel-frontend
    expose:
      - "80"
    networks:
      - saju-net

networks:
  saju-net:
    external: true
    name: saju_mbti_saju-net
```

유지 이유:

- 현재 `saju-nginx`가 docker network 내부에서 `travel-frontend:80`, `travel-backend:8000`으로 proxy한다.
- network 이름 변경 시 여행 도메인 502 위험이 있다.

### 로컬 최신 기준 유지

아래 항목은 로컬 최신 수정본을 source-of-truth로 유지한다.

- `frontend/Dockerfile`의 `ARG/ENV VITE_*`
- `docker-compose.yml`의 `travel-frontend.build.args`
- DB dump ignore 정책
- frontend build context에서 `.env` 제외

### merge 필요

merge 대상:

| 파일 | merge 방식 |
| --- | --- |
| `docker-compose.yml` | EC2 운영 service/network 구조 + 로컬 VITE build args |
| `frontend/Dockerfile` | EC2 nginx static serving 구조 + 로컬 VITE ARG/ENV |
| `Dockerfile` | EC2 backend uvicorn/port 구조 유지, Python version만 정책 검토 |
| `frontend/.dockerignore` | EC2 제외 패턴 유지, 필요 시 추가 |

### archive-only 후보

이번 source-of-truth 반영 대상에서 제외 가능한 것:

- `batch/update_all.sh`
- `batch/update_all.ps1`

이유:

- 운영 Docker/compose reconciliation 직접 대상은 아님
- 별도 batch governance 작업으로 분리 가능

## VITE env 반영 기준

### frontend/Dockerfile 최종 기준

build stage에는 반드시 아래가 포함되어야 한다.

```dockerfile
ARG VITE_SHOW_SAJU_LINK=false
ARG VITE_SAJU_SERVICE_URL=

ENV VITE_SHOW_SAJU_LINK=$VITE_SHOW_SAJU_LINK
ENV VITE_SAJU_SERVICE_URL=$VITE_SAJU_SERVICE_URL
```

위치:

```dockerfile
COPY package*.json ./
RUN npm install

ARG VITE_SHOW_SAJU_LINK=false
ARG VITE_SAJU_SERVICE_URL=

ENV VITE_SHOW_SAJU_LINK=$VITE_SHOW_SAJU_LINK
ENV VITE_SAJU_SERVICE_URL=$VITE_SAJU_SERVICE_URL

COPY . .
RUN npm run build
```

### docker-compose.yml 최종 기준

`travel-frontend.build.args`:

```yaml
travel-frontend:
  build:
    context: ./frontend
    args:
      VITE_SHOW_SAJU_LINK: ${VITE_SHOW_SAJU_LINK:-false}
      VITE_SAJU_SERVICE_URL: ${VITE_SAJU_SERVICE_URL:-}
```

### EC2 .env 기준

운영 `.env`에 아래 public env 필요:

```env
VITE_SHOW_SAJU_LINK=true
VITE_SAJU_SERVICE_URL=https://saju-mbti-service.duckdns.org/
```

주의:

- Vite env는 build-time 값이다.
- nginx runtime env로는 반영되지 않는다.
- secret 값은 `VITE_*`에 넣지 않는다.

## Network 유지 원칙

반드시 유지:

```yaml
networks:
  saju-net:
    external: true
    name: saju_mbti_saju-net
```

반드시 건드리지 않음:

- `saju-nginx`
- `/home/ubuntu/saju_mbti/nginx/default.conf`
- `saju-frontend`
- `saju-backend`
- 사주 compose/env
- nginx reload/restart

검증 기준:

```bash
docker compose config | grep -A5 -B2 saju_mbti_saju-net
docker compose config --services
```

기대:

```text
travel-backend
travel-frontend
```

## 예상 clean 상태

Docker/compose reconciliation 후 사라져야 할 untracked:

```text
?? Dockerfile
?? docker-compose.yml
?? frontend/Dockerfile
?? frontend/.dockerignore
```

DB dump는 이미 repo 밖으로 이동되어 사라진 상태:

```text
?? travel_db.dump
?? travel_db.sql
```

단, 이 작업만으로 전체 clean이 되지는 않는다.

남을 수 있는 blocker:

```text
 M api_server.py
 M course_builder.py
 M regional_zone_builder.py
 M frontend/src/App.jsx
 M frontend/src/components/common/MobileShell.jsx
 M frontend/src/index.css
 M frontend/src/screens/day-trip/HomeScreen.jsx
 M test/diagnostic artifacts
```

따라서 Docker/compose reconciliation 후에도 다음 작업이 필요하다.

- line ending normalize
- frontend UI drift reconcile
- 테스트/진단 산출물 정리

## Clean 상태 달성 절차

권장 순서:

1. Docker/compose source-of-truth 확정
2. 로컬 git에 반영
3. EC2에서 archive 기준과 최신 git 기준 비교
4. DB dump ignore 정책 확인
5. line ending normalize 별도 commit
6. frontend UI drift 별도 commit 또는 폐기
7. 테스트/진단 산출물 archive/ignore 처리
8. EC2에서 `git status --short` clean 확인

clean 기준:

```bash
git status --short
```

기대:

```text
<empty>
```

## Line ending normalize와 분리 이유

분리해야 하는 이유:

1. `course_builder.py`는 추천 엔진 핵심 파일이다.
2. line ending drift와 Docker/compose 운영 파일 반영을 한 commit에 섞으면 리뷰가 어려워진다.
3. 장애 발생 시 rollback 범위가 불명확해진다.
4. `--ignore-space-at-eol` 기준으로 backend/engine 로직 변경은 없어 보이므로 기능 변경으로 취급하면 안 된다.

권장 commit 단위:

1. Docker/compose source-of-truth commit
2. frontend VITE env injection commit
3. line ending normalize commit
4. frontend UI drift reconcile commit
5. artifact ignore/archive policy commit

## Deploy 재개 조건

배포 재개 전 필수 조건:

### Git

```bash
git status --short
```

결과:

```text
<empty>
```

### Env

```bash
grep -E '^VITE_SHOW_SAJU_LINK=|^VITE_SAJU_SERVICE_URL=' .env
```

기대:

```env
VITE_SHOW_SAJU_LINK=true
VITE_SAJU_SERVICE_URL=https://saju-mbti-service.duckdns.org/
```

### Compose

```bash
docker compose config | grep -A5 -B2 'VITE_SAJU'
docker compose config | grep -A5 -B2 'saju_mbti_saju-net'
```

기대:

- `travel-frontend.build.args` 존재
- `saju_mbti_saju-net` 유지

### Build safety

로컬 또는 staging에서:

```bash
npm run build
docker build --build-arg VITE_SHOW_SAJU_LINK=true --build-arg VITE_SAJU_SERVICE_URL=https://saju-mbti-service.duckdns.org/ -t travel-frontend-vite-env-check:prod ./frontend
```

기대:

- build PASS
- built JS에 `saju-mbti-service.duckdns.org` 포함

### 운영 safety

- `saju-nginx` untouched
- 사주 container restart 없음
- backend rebuild/restart 없음
- DB/migration 없음
- representative overlay actual OFF

## 금지 작업

아직 하면 안 되는 작업:

```bash
git add
git commit
git reset --hard
git clean -fd
git checkout -- .
git pull --rebase
docker compose build
docker compose up -d
docker compose up -d --build
docker compose down
docker compose build travel-backend
docker restart saju-nginx
sudo nginx -s reload
psql
pg_restore
```

추가 금지:

- nginx 설정 수정
- 사주 서비스 env/compose 수정
- backend/API 수정
- 추천 엔진 수정
- DB migration
- representative overlay actual 적용

## 다음 작업 제안

1. 로컬 최신 Docker/compose 파일과 EC2 archive 파일을 실제 diff로 비교한다.
2. `docker-compose.yml`은 EC2 운영 network 구조를 유지하면서 VITE build args만 추가한 형태로 확정한다.
3. `frontend/Dockerfile`은 EC2 nginx static 구조를 유지하면서 VITE ARG/ENV만 추가한 형태로 확정한다.
4. `Dockerfile`과 `frontend/.dockerignore`는 운영 기준을 우선한다.
5. 확정 후 별도 요청에서 실제 파일 반영을 수행한다.
6. 이후 line ending/frontend drift 정리와 분리해서 clean 상태를 만든다.
