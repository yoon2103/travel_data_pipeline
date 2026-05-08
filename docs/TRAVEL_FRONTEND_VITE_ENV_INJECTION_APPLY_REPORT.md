# Travel Frontend VITE Env Injection Apply Report

## 목표

`travel-frontend` Docker build 시점에 아래 Vite public env가 실제 JavaScript bundle에 포함되도록 최소 수정했다.

- `VITE_SHOW_SAJU_LINK`
- `VITE_SAJU_SERVICE_URL`

## 수정 파일

- `frontend/Dockerfile`
  - EC2 운영 구조에서 확인한 production frontend Dockerfile 구조를 로컬에 반영
  - build stage에 `ARG`/`ENV` 추가

- `frontend/Dockerfile.staging`
  - staging build stage에 동일한 `ARG`/`ENV` 추가

- `docker-compose.yml`
  - EC2 운영 compose 구조를 로컬에 반영
  - `travel-frontend.build.args` 추가

- `docker-compose.staging.yml`
  - `travel-frontend.build.args` 추가

## 추가 ARG/ENV

Dockerfile build stage:

```dockerfile
ARG VITE_SHOW_SAJU_LINK=false
ARG VITE_SAJU_SERVICE_URL=

ENV VITE_SHOW_SAJU_LINK=$VITE_SHOW_SAJU_LINK
ENV VITE_SAJU_SERVICE_URL=$VITE_SAJU_SERVICE_URL
```

## compose build.args

운영/staging compose 모두 동일한 방식으로 주입한다.

```yaml
travel-frontend:
  build:
    context: ./frontend
    args:
      VITE_SHOW_SAJU_LINK: ${VITE_SHOW_SAJU_LINK:-false}
      VITE_SAJU_SERVICE_URL: ${VITE_SAJU_SERVICE_URL:-}
```

## build 결과

### npm run build

명령:

```powershell
npm run build
```

결과:

- PASS
- Vite production build 성공

### npm run build with VITE env

명령:

```powershell
$env:VITE_SHOW_SAJU_LINK='true'
$env:VITE_SAJU_SERVICE_URL='https://saju-mbti-service.duckdns.org/'
npm run build
```

결과:

- PASS
- built JS에서 `saju-mbti-service.duckdns.org` 문자열 확인

### production Docker build

명령:

```powershell
docker build `
  --build-arg VITE_SHOW_SAJU_LINK=true `
  --build-arg VITE_SAJU_SERVICE_URL=https://saju-mbti-service.duckdns.org/ `
  -t travel-frontend-vite-env-check:prod .
```

실행 위치:

```text
D:\travel_data_pipeline\frontend
```

결과:

- PASS

### staging Docker build

명령:

```powershell
docker build -f Dockerfile.staging `
  --build-arg VITE_SHOW_SAJU_LINK=true `
  --build-arg VITE_SAJU_SERVICE_URL=https://saju-mbti-service.duckdns.org/ `
  -t travel-frontend-vite-env-check:staging .
```

실행 위치:

```text
D:\travel_data_pipeline\frontend
```

결과:

- PASS

## built JS 확인 결과

production image:

```powershell
docker run --rm travel-frontend-vite-env-check:prod `
  sh -c "grep -R 'saju-mbti-service.duckdns.org' -n /usr/share/nginx/html/assets"
```

결과:

- PASS
- `/usr/share/nginx/html/assets/index-*.js`에 `https://saju-mbti-service.duckdns.org/` 포함 확인

staging image:

```powershell
docker run --rm travel-frontend-vite-env-check:staging `
  sh -c "grep -R 'saju-mbti-service.duckdns.org' -n /usr/share/nginx/html/assets"
```

결과:

- PASS
- `/usr/share/nginx/html/assets/index-*.js`에 `https://saju-mbti-service.duckdns.org/` 포함 확인

## compose config 확인

운영 compose:

```powershell
$env:VITE_SHOW_SAJU_LINK='true'
$env:VITE_SAJU_SERVICE_URL='https://saju-mbti-service.duckdns.org/'
docker compose -f docker-compose.yml config
```

결과:

- PASS
- `travel-frontend.build.args`에 두 값이 해석됨

staging compose:

```powershell
$env:APP_ENV_FILE='.env.example'
$env:VITE_SHOW_SAJU_LINK='true'
$env:VITE_SAJU_SERVICE_URL='https://saju-mbti-service.duckdns.org/'
docker compose -f docker-compose.staging.yml config
```

결과:

- PASS
- `travel-frontend.build.args`에 두 값이 해석됨

참고:

- 로컬에는 `.env.staging` 파일이 없어 staging compose config 확인 시 `APP_ENV_FILE=.env.example`를 사용했다.
- 실제 staging 환경에는 `.env.staging` 또는 `APP_ENV_FILE` 대상 파일이 있어야 한다.

## 사주 영향 없음 확인

이번 작업에서 수정하지 않은 항목:

- `saju-nginx`
- `/home/ubuntu/saju_mbti/nginx/default.conf`
- 사주 frontend/backend container
- 사주 env
- 사주 서비스 Docker/compose 파일

배포/재시작도 수행하지 않았다.

## backend/nginx 영향 없음 확인

이번 작업에서 수정하지 않은 항목:

- `api_server.py`
- `course_builder.py`
- `tourism_belt.py`
- DB/migration
- travel backend container
- nginx 설정

`docker build`는 로컬 image 생성 검증만 수행했고, `docker compose up`, container restart, nginx reload는 수행하지 않았다.

## representative governance 영향 없음 확인

이번 작업은 frontend Docker build env injection만 대상으로 했다.

수정하지 않은 영역:

- `batch/place_enrichment`
- representative candidate/review/promote workflow
- seed overlay/gate workflow
- places table
- actual overlay integration

## 다음 작업 제안

1. EC2 적용 전 `.env` 또는 배포용 env에 아래 public key가 있는지 확인한다.

```env
VITE_SHOW_SAJU_LINK=true
VITE_SAJU_SERVICE_URL=https://saju-mbti-service.duckdns.org/
```

2. EC2에서는 `travel-frontend`만 rebuild/recreate한다.

```bash
docker compose build travel-frontend
docker compose up -d --no-deps travel-frontend
```

3. 배포 후 `travel-planne.duckdns.org`에서 MyScreen 사주 링크 노출과 새 탭 이동을 확인한다.

4. `saju-nginx`, 사주 container, travel backend는 계속 건드리지 않는다.
