# Travel Frontend EC2 Apply Runbook

## 목적

EC2 운영 서버에서 `travel-frontend`만 안전하게 rebuild/recreate하여 Vite build-time env를 반영한다.

이번 절차의 대상은 `travel-frontend` container 하나뿐이다.

## 전제

- VITE env injection 코드 반영 완료
- Docker build 검증 PASS
- 실제 추천 엔진/backend/DB 변경 없음
- representative/seed governance actual overlay 미적용 유지
- 사주 서비스와 nginx는 건드리지 않음

## EC2 접속 절차

로컬 PowerShell 기준:

```powershell
ssh -i "D:\AWS\saju-key.pem" ubuntu@3.38.61.251
```

EC2 접속 후 작업 디렉터리 이동:

```bash
cd /home/ubuntu/travel_data_pipeline
```

현재 위치 확인:

```bash
pwd
```

기대값:

```text
/home/ubuntu/travel_data_pipeline
```

## 현재 상태 확인

컨테이너 상태 확인:

```bash
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
```

반드시 확인:

- `travel-frontend` Up
- `travel-backend` Up
- `saju-nginx` Up
- `saju-frontend` Up
- `saju-backend` Up

travel frontend image 확인:

```bash
docker inspect travel-frontend --format '{{.Image}}'
```

rollback용으로 현재 image id 기록:

```bash
docker inspect travel-frontend --format '{{.Image}}' > /tmp/travel-frontend-prev-image.txt
cat /tmp/travel-frontend-prev-image.txt
```

compose 서비스 확인:

```bash
docker compose config --services
```

기대 포함:

```text
travel-backend
travel-frontend
```

## env 확인

값 전체를 로그에 남길 필요는 없지만, public frontend env는 아래처럼 확인 가능하다.

```bash
grep -E '^VITE_SHOW_SAJU_LINK=|^VITE_SAJU_SERVICE_URL=' .env || true
```

기대값:

```env
VITE_SHOW_SAJU_LINK=true
VITE_SAJU_SERVICE_URL=https://saju-mbti-service.duckdns.org/
```

누락 시 `.env`에 위 두 public key를 추가해야 한다.

주의:

- `VITE_*`는 frontend bundle에 들어가는 public config다.
- DB password, API secret 같은 민감정보를 `VITE_*`로 만들면 안 된다.
- 사주 서비스 `.env`는 확인하거나 수정하지 않는다.

compose build args 해석 확인:

```bash
docker compose config | grep -A5 -B2 'VITE_SAJU'
```

기대:

```yaml
args:
  VITE_SAJU_SERVICE_URL: https://saju-mbti-service.duckdns.org/
  VITE_SHOW_SAJU_LINK: "true"
```

## git pull 절차

현재 변경 상태 확인:

```bash
git status --short
```

주의:

- 운영 서버에 local modified/untracked 파일이 있을 수 있다.
- `git reset --hard`, `git clean -fd`는 실행 금지.
- 충돌이 있으면 배포 중단 후 원인 확인.

원격 최신 반영:

```bash
git pull --ff-only
```

실패 시:

- merge/rebase를 EC2에서 즉석 처리하지 않는다.
- 배포 중단.
- `git status --short`와 에러 메시지를 기록한다.

## frontend only rebuild 절차

반드시 `travel-frontend`만 build한다.

```bash
docker compose build travel-frontend
```

build 결과에서 확인:

- frontend Dockerfile build stage 실행
- `npm run build` 성공
- backend image build가 실행되지 않아야 함
- nginx image/container recreate가 실행되지 않아야 함

## frontend only recreate 절차

반드시 `--no-deps`를 사용한다.

```bash
docker compose up -d --no-deps travel-frontend
```

적용 후 확인:

```bash
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" | grep -E 'travel-frontend|travel-backend|saju-nginx|saju-frontend|saju-backend'
```

기대:

- `travel-frontend` Up 상태
- `travel-backend` 재시작 없음
- `saju-nginx` 재시작 없음
- 사주 컨테이너 재시작 없음

## 안전 명령

이번 작업에서 허용되는 핵심 명령:

```bash
cd /home/ubuntu/travel_data_pipeline
docker ps
git status --short
git pull --ff-only
docker compose config
docker compose build travel-frontend
docker compose up -d --no-deps travel-frontend
docker compose logs --tail=80 travel-frontend
curl -I http://travel-planne.duckdns.org/
curl -s http://travel-planne.duckdns.org/api/regions | head
```

## 금지 명령

아래 명령은 실행 금지.

```bash
docker compose up -d --build
docker compose up -d
docker compose restart
docker compose down
docker restart saju-nginx
docker restart saju-frontend
docker restart saju-backend
docker restart travel-backend
sudo systemctl restart nginx
sudo nginx -s reload
git reset --hard
git clean -fd
```

금지 이유:

- `docker compose up -d --build`는 backend까지 재빌드/재생성할 수 있다.
- `docker compose up -d`는 의도치 않은 dependency recreate를 유발할 수 있다.
- nginx reload/restart는 사주/여행 두 도메인 모두에 영향을 줄 수 있다.
- `git reset/clean`은 운영 서버에 남아 있는 로컬 파일을 삭제할 수 있다.

## Smoke Test

### 1. 여행 도메인

```bash
curl -I http://travel-planne.duckdns.org/
```

PASS:

- `HTTP/1.1 200 OK`
- `Content-Type: text/html`

### 2. 여행 API 연결

```bash
curl -s http://travel-planne.duckdns.org/api/regions | head
```

PASS:

- JSON 응답
- region 목록 또는 정상 API 응답

### 3. built JS env 반영

컨테이너 내부 static asset에서 확인:

```bash
docker exec travel-frontend sh -c "grep -R 'saju-mbti-service.duckdns.org' -n /usr/share/nginx/html/assets | head"
```

PASS:

- built JS에서 `saju-mbti-service.duckdns.org` 문자열 확인

### 4. 브라우저 사용자 플로우

브라우저에서 확인:

- `http://travel-planne.duckdns.org/` 접속
- 홈 화면 정상 표시
- 지역 선택 가능
- 코스 생성 가능
- 결과 화면 표시
- 코스 저장 가능
- MyScreen 저장 목록 표시
- 저장 코스 상세 보기 가능
- 비슷한 코스 다시 만들기 진입 가능
- 사주/MBTI 버튼 노출
- 사주 버튼 클릭 시 `https://saju-mbti-service.duckdns.org/` 새 탭 이동

### 5. 모바일 확인

Android Chrome 기준:

- 홈 화면 safe-area 정상
- 하단 CTA가 브라우저 UI에 가려지지 않음
- MyScreen 스크롤 정상
- 저장 상세 스크롤 정상
- 사주 링크 버튼 표시/클릭 정상

iOS Safari 기준:

- 홈/결과/MyScreen safe-area 정상
- 저장/복원/regenerate 플로우 정상
- 사주 링크 새 탭 또는 외부 이동 정상

## 사주 영향 확인

사주 도메인 상태 확인:

```bash
curl -I http://saju-mbti-service.duckdns.org/result
```

PASS:

- 200/3xx/서비스가 기존과 동일한 응답
- 502/connection refused 발생하지 않음

컨테이너 상태 확인:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E 'saju-nginx|saju-frontend|saju-backend'
```

PASS:

- 사주 관련 container가 계속 Up
- 재시작 시간이 배포 시점으로 바뀌지 않음

## representative governance untouched 확인

이번 frontend 배포에서 확인할 원칙:

- `course_builder.py` 수정/배포 영향 없음
- `tourism_belt.py` 수정/배포 영향 없음
- representative overlay actual integration 없음
- seed overlay actual integration 없음
- `batch/place_enrichment`는 사용자 요청 중 호출되지 않음
- places DB write 없음

운영 서버에서 빠른 확인:

```bash
git diff --name-only | grep -E 'course_builder.py|tourism_belt.py|batch/place_enrichment|migration_' || true
```

PASS:

- 이번 frontend-only 배포 대상과 무관한 변경이 배포 절차에 포함되지 않음

## Rollback 절차

### 1. 즉시 상태 확인

```bash
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
docker compose logs --tail=120 travel-frontend
```

### 2. 이전 image id 확인

```bash
cat /tmp/travel-frontend-prev-image.txt
```

### 3. 이전 image로 travel-frontend 재생성

이전 image id를 확인한 뒤 임시 rollback container를 구성해야 한다.

가장 안전한 방식:

1. 현재 컨테이너 중지 전, 이전 image가 로컬에 존재하는지 확인

```bash
docker image inspect $(cat /tmp/travel-frontend-prev-image.txt)
```

2. compose 파일을 수정하지 않고 rollback이 필요하면 운영자가 명시적으로 이전 image tag를 붙인 뒤 `travel-frontend`만 recreate한다.

```bash
docker tag $(cat /tmp/travel-frontend-prev-image.txt) travel-frontend-rollback:latest
```

3. compose 수정이 필요한 rollback은 별도 승인 후 수행한다.

주의:

- rollback 중에도 `saju-nginx`, 사주 컨테이너, travel-backend는 건드리지 않는다.
- `docker compose down` 금지.

### 4. 빠른 실무 rollback 대안

배포 직후 문제가 frontend bundle 문제로 명확하면 이전 git commit으로 checkout 후 frontend만 rebuild한다.

```bash
git log --oneline -5
git checkout <previous_good_commit>
docker compose build travel-frontend
docker compose up -d --no-deps travel-frontend
```

주의:

- 이 방식은 작업트리 상태가 깨끗할 때만 사용.
- `git reset --hard` 사용 금지.
- rollback 후 다시 원래 브랜치/커밋으로 복구 계획을 기록해야 한다.

## Production Blocker

아래 중 하나라도 발생하면 배포 실패로 판단하고 중단한다.

- `travel-planne.duckdns.org` 접속 실패
- `/api/regions` 실패
- `travel-frontend` container가 반복 재시작
- built JS에 `saju-mbti-service.duckdns.org` 미포함
- 사주 도메인 오류 발생
- `saju-nginx` 또는 사주 container 재시작 발생
- 저장/복원/regenerate 핵심 플로우 실패
- 모바일 하단 CTA 또는 MyScreen 스크롤 심각한 깨짐
- representative overlay가 의도치 않게 활성화된 정황

## 최종 PASS 기준

배포 성공 판정:

- `travel-frontend`만 rebuild/recreate 완료
- `travel-backend` 재시작 없음
- `saju-nginx` 재시작 없음
- 사주 컨테이너 재시작 없음
- 여행 도메인 200 OK
- `/api/regions` 정상
- built JS에 `saju-mbti-service.duckdns.org` 포함
- MyScreen 사주 링크 노출
- 사주 링크 새 탭 이동 정상
- 코스 생성 정상
- 저장/복원/regenerate 정상
- Android Chrome 기본 smoke PASS
- iOS Safari 기본 smoke PASS
- representative/seed governance untouched

## 최종 운영 명령 요약

정상 적용 시 실행 순서:

```bash
ssh -i "D:\AWS\saju-key.pem" ubuntu@3.38.61.251
cd /home/ubuntu/travel_data_pipeline

docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
docker inspect travel-frontend --format '{{.Image}}' > /tmp/travel-frontend-prev-image.txt

grep -E '^VITE_SHOW_SAJU_LINK=|^VITE_SAJU_SERVICE_URL=' .env || true
docker compose config | grep -A5 -B2 'VITE_SAJU'

git status --short
git pull --ff-only

docker compose build travel-frontend
docker compose up -d --no-deps travel-frontend

docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
docker exec travel-frontend sh -c "grep -R 'saju-mbti-service.duckdns.org' -n /usr/share/nginx/html/assets | head"
curl -I http://travel-planne.duckdns.org/
curl -s http://travel-planne.duckdns.org/api/regions | head
curl -I http://saju-mbti-service.duckdns.org/result
```
