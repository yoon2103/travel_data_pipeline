# EC2 Travel Frontend Apply Report

## 목표

EC2에서 `travel-frontend`만 안전하게 rebuild/recreate하여 Vite env injection 변경을 적용하려 했다.

## 최종 판정

**BLOCKED**

이유:

1. EC2 `/home/ubuntu/travel_data_pipeline` 작업트리가 clean 상태가 아니다.
2. 요청 조건에 따라 `git status --short` 이상 발생 시 중단해야 하므로 `git pull --ff-only`, `docker compose build travel-frontend`, `docker compose up -d --no-deps travel-frontend`는 실행하지 않았다.
3. `.env`에서 `VITE_SHOW_SAJU_LINK`, `VITE_SAJU_SERVICE_URL` 값도 확인되지 않았다.

## 실행 명령

### EC2 접속 및 상태 확인

```powershell
ssh -i "D:\AWS\saju-key.pem" -o StrictHostKeyChecking=no ubuntu@3.38.61.251
```

실행 디렉터리:

```bash
cd /home/ubuntu/travel_data_pipeline
```

컨테이너 확인:

```bash
docker container ls --no-trunc
```

현재 image id 백업:

```bash
docker inspect travel-frontend --format '{{.Image}}' > /tmp/travel-frontend-prev-image.txt
cat /tmp/travel-frontend-prev-image.txt
```

env 확인:

```bash
grep -E '^VITE_SHOW_SAJU_LINK=|^VITE_SAJU_SERVICE_URL=' .env || true
```

git 상태 확인:

```bash
git status --short
```

컨테이너 inspect:

```bash
docker inspect -f '{{.Name}} {{.State.Status}} {{.State.StartedAt}} {{.RestartCount}} {{.Image}}' \
  travel-frontend travel-backend saju-nginx saju-frontend saju-backend
```

## 컨테이너 상태

확인 결과:

| container | status | restart count | image |
| --- | --- | ---: | --- |
| `travel-frontend` | running since `2026-05-07T12:46:09Z` | 0 | `sha256:3f63ab7e63cc...` |
| `travel-backend` | running since `2026-05-06T14:49:11Z` | 0 | `sha256:a74cbd9213...` |
| `saju-nginx` | running since `2026-05-06T15:06:02Z` | 0 | `sha256:5616878291...` |
| `saju-frontend` | running since `2026-05-07T13:25:24Z` | 0 | `sha256:581c3e2006...` |
| `saju-backend` | running since `2026-05-07T13:25:24Z` | 0 | `sha256:db07b35c63...` |

현재 실행 중인 컨테이너:

- `travel-frontend`: Up 20 hours
- `travel-backend`: Up 42 hours
- `saju-nginx`: Up 42 hours
- `saju-frontend`: Up 19 hours
- `saju-backend`: Up 19 hours

## frontend image backup

백업 파일:

```text
/tmp/travel-frontend-prev-image.txt
```

내용:

```text
sha256:3f63ab7e63ccde51f7ab4012367f21b18dfd4e01166ed89ab3451d34bd43deae
```

## env 확인 결과

명령:

```bash
grep -E '^VITE_SHOW_SAJU_LINK=|^VITE_SAJU_SERVICE_URL=' .env || true
```

결과:

- `VITE_SHOW_SAJU_LINK` 확인 안 됨
- `VITE_SAJU_SERVICE_URL` 확인 안 됨

조치 필요:

```env
VITE_SHOW_SAJU_LINK=true
VITE_SAJU_SERVICE_URL=https://saju-mbti-service.duckdns.org/
```

주의:

- 이 값은 frontend public config다.
- 사주 서비스 `.env`는 건드리지 않는다.

## git 상태

`git status --short` 결과 작업트리가 clean하지 않다.

주요 변경/미추적 파일:

```text
 M .gitignore
 M api_server.py
 M course_builder.py
 M frontend/src/App.jsx
 M frontend/src/components/common/MobileShell.jsx
 M frontend/src/index.css
 M frontend/src/screens/day-trip/HomeScreen.jsx
 M regional_zone_builder.py
?? Dockerfile
?? docker-compose.yml
?? frontend/Dockerfile
?? travel_db.dump
?? travel_db.sql
```

전체 출력에는 테스트 산출물, debug 파일, sql verify 파일, batch wrapper 파일도 포함되어 있다.

중단 사유:

- 사용자가 명시한 조건: `git status --short` 이상 있으면 중단
- 현재 상태에서 `git pull --ff-only`를 진행하면 local modifications/untracked 파일과 충돌하거나 운영 상태를 불명확하게 만들 위험이 있다.

## travel-frontend rebuild 결과

**미실행**

이유:

- `git status --short` dirty 상태로 중단
- env key 누락

실행하지 않은 명령:

```bash
git pull --ff-only
docker compose build travel-frontend
docker compose up -d --no-deps travel-frontend
```

## 사주 영향 여부

사주 관련 컨테이너 재시작 없음.

확인 기준:

- `saju-nginx` restart count: 0
- `saju-frontend` restart count: 0
- `saju-backend` restart count: 0

이번 작업에서 실행하지 않은 항목:

- nginx restart/reload
- saju container restart
- saju env 수정
- saju compose 수정

## Smoke test 결과

**미실행**

이유:

- 요청 순서상 smoke test는 rebuild/recreate 이후 단계다.
- `git status` dirty 상태로 중단했기 때문에 step 9까지 진행하지 않았다.

미실행 항목:

- `curl http://travel-planne.duckdns.org/`
- `curl http://travel-planne.duckdns.org/api/regions`
- `curl http://saju-mbti-service.duckdns.org/result`
- built JS `saju-mbti-service.duckdns.org` 문자열 확인

## Rollback 필요 여부

**필요 없음**

이유:

- `travel-frontend` rebuild 미실행
- `travel-frontend` recreate 미실행
- backend/nginx/saju/DB 변경 없음
- 현재 image id 백업만 수행

## 금지 명령 준수 여부

실행하지 않음:

- `docker compose up -d --build`
- `docker compose down`
- nginx restart/reload
- saju container restart
- backend rebuild
- migration
- DB write

## 다음 조치

배포를 진행하려면 먼저 EC2 작업트리를 정리해야 한다.

권장 순서:

1. EC2의 dirty 파일이 운영에 필요한 변경인지 식별한다.
2. 필요한 변경은 git에 반영하거나 별도 백업한다.
3. 불필요한 산출물은 운영자가 명시적으로 정리한다.
4. `.env`에 frontend public env를 추가한다.
5. `git status --short`가 clean인지 확인한다.
6. 그 다음에만 아래 명령을 실행한다.

```bash
git pull --ff-only
docker compose build travel-frontend
docker compose up -d --no-deps travel-frontend
```

## 최종 판정

**BLOCKED**

배포는 안전하게 중단되었다.
