# Travel Data Pipeline

FastAPI + React + PostgreSQL 기반 국내 당일 여행 코스 추천 서비스입니다.

## Git 기반 Staging 배포

이 저장소는 private repository 기준으로 운영합니다. 운영 키와 DB dump는 Git에 올리지 않습니다.

### 1. EC2에서 clone

```bash
cd /home/ubuntu
git clone <PRIVATE_REPOSITORY_URL> travel_data_pipeline
cd travel_data_pipeline
```

이미 clone되어 있으면 이후 배포는 `git pull` 기준으로 진행합니다.

### 2. env 설정

```bash
cp .env.staging.example .env.staging
vi .env.staging
```

필수 값:

```bash
TOURAPI_SERVICE_KEY=...
DB_HOST=host.docker.internal
DB_PORT=5432
DB_NAME=travel_db
DB_USER=postgres
DB_PASSWORD=...
API_PORT=5000
FRONTEND_PORT=4175
```

선택 값:

```bash
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
KAKAO_REST_API_KEY=
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
```

`.env`, `.env.staging`은 `.gitignore`에 포함되어 있으므로 push하지 않습니다.

### 3. Docker compose build

```bash
docker compose --env-file .env.staging -f docker-compose.staging.yml build
```

### 4. migration

배포 스크립트는 migration SQL을 순서대로 적용합니다.

```bash
RUN_MIGRATIONS=true ./staging_deploy.sh
```

수동으로 migration을 건너뛰려면:

```bash
RUN_MIGRATIONS=false ./staging_deploy.sh
```

### 5. up -d

수동 실행:

```bash
docker compose --env-file .env.staging -f docker-compose.staging.yml up -d
```

Git pull부터 build, migration, up, smoke test까지 한 번에 실행:

```bash
chmod +x staging_deploy.sh
BRANCH=main ./staging_deploy.sh
```

### 6. smoke 확인

```bash
curl -I http://127.0.0.1:4175/
curl -I http://127.0.0.1:5000/docs
curl http://127.0.0.1:5000/api/regions
```

## Push 금지 항목

아래 항목은 `.gitignore`로 제외합니다.

- `.env`, `.env.*`
- `backups/`, `backups/*.dump`
- `*.dump`, `travel_db.sql`, `travel_db*.sql`
- `__pycache__/`, `*.pyc`
- `frontend/node_modules/`, `frontend/dist/`
- `qa_reports/`, QA output/log files

## 배포 흐름

```text
local development
  -> git commit
  -> git push
  -> EC2: git pull
  -> docker compose build
  -> migration
  -> docker compose up -d
  -> smoke test
```
