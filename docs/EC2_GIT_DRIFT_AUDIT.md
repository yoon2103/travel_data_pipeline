# EC2 Git Drift Audit

## 목표

EC2 운영 서버 `/home/ubuntu/travel_data_pipeline`의 dirty working tree를 read-only로 분석하고, 배포 blocker 여부와 정리 전략을 분류했다.

## 최종 요약

현재 EC2 운영 서버는 production drift 상태다.

핵심:

- `git status --short`가 clean하지 않다.
- `api_server.py`, `course_builder.py`, `regional_zone_builder.py`는 대량 diff처럼 보이지만, `--ignore-space-at-eol` 기준으로는 실질 로직 변경이 확인되지 않았다.
- 실제 의미 있는 tracked diff는 frontend UI 관련 4개 파일이다.
- 운영에 필요한 `Dockerfile`, `docker-compose.yml`, `frontend/Dockerfile`이 git 기준으로 untracked 상태다.
- `travel_db.dump`, `travel_db.sql` 같은 DB dump가 운영 repo root에 untracked로 존재한다.
- 현재 상태에서는 `git pull --ff-only`와 frontend rebuild/recreate를 진행하면 안 된다.

판정:

```text
BLOCKED
```

## 확인 명령

read-only 명령만 실행했다.

```bash
cd /home/ubuntu/travel_data_pipeline
git status --short
git diff --stat
git diff --ignore-space-at-eol --stat
git diff --ignore-space-at-eol -- frontend/src/App.jsx frontend/src/components/common/MobileShell.jsx frontend/src/screens/day-trip/HomeScreen.jsx frontend/src/index.css
git ls-files --others --exclude-standard
ls -lh Dockerfile docker-compose.yml frontend/Dockerfile travel_db.dump travel_db.sql
file Dockerfile docker-compose.yml frontend/Dockerfile travel_db.dump travel_db.sql
```

실행하지 않은 명령:

- `git reset`
- `git clean`
- `git pull`
- `docker build`
- `docker compose build`
- `docker compose up`
- DB/migration 관련 명령

## Dirty 파일 분석

### 전체 tracked dirty 파일

```text
 M .gitignore
 M _anchor_test.txt
 M _course_quality_test.txt
 M _dq_diagnosis.txt
 M _enrich_test.txt
 M _template_test.txt
 M api_server.py
 M check_kid_out.txt
 M check_late_out.txt
 M check_schema_out.txt
 M check_selection_basis.py
 M course_builder.py
 M debug.py
 M frontend/src/App.jsx
 M frontend/src/components/common/MobileShell.jsx
 M frontend/src/index.css
 M frontend/src/screens/day-trip/HomeScreen.jsx
 M regional_zone_builder.py
 M run_fix_103.py
 M run_zone_verify.py
 M sql/verify/00_run_order.md
 M test_course.py
 M test_sokcho2.json
 M test_sokcho_a.json
 M test_sokcho_b.json
 M test_sokcho_course.json
```

### diff 통계

기본 diff:

```text
26 files changed, 5247 insertions(+), 5235 deletions(-)
```

하지만 `--ignore-space-at-eol` 기준으로는 주요 backend/engine 파일의 실질 diff가 사라진다.

```text
frontend/src/App.jsx                           |  8 ++--
frontend/src/components/common/MobileShell.jsx | 64 +++++++++++++++-----------
frontend/src/index.css                         |  4 +-
frontend/src/screens/day-trip/HomeScreen.jsx   |  6 +--
4 files changed, 47 insertions(+), 35 deletions(-)
```

### api_server.py

분류:

```text
줄바꿈/인코딩 drift
```

근거:

- 기본 diff: `586 insertions / 586 deletions`
- `--ignore-space-at-eol` 기준 실질 diff 없음
- 파일 타입: UTF-8, CRLF/LF mixed

위험도:

```text
MEDIUM
```

이유:

- 운영 backend 파일이 dirty 상태인 것 자체가 배포 blocker다.
- 다만 현재 확인 기준으로 로직 변경은 아니고 line ending drift 성격이 강하다.

정리 전략:

- 운영 서버에서 즉시 reset 금지
- 원본 백업 후 별도 로컬/브랜치에서 line ending 정책 정리
- `.gitattributes` 적용 여부 확인 후 정상화

### course_builder.py

분류:

```text
줄바꿈/인코딩 drift
```

근거:

- 기본 diff: `1764 insertions / 1764 deletions`
- `--ignore-space-at-eol` 기준 실질 diff 없음
- 파일 타입: UTF-8, CRLF/LF mixed

위험도:

```text
HIGH
```

이유:

- 추천 엔진 핵심 파일이다.
- 실질 로직 변경은 없어 보이지만 dirty 상태면 pull/build 판단이 위험하다.

정리 전략:

- 운영 서버에서 수정/정리 금지
- 반드시 백업 후 git 기준과 비교
- line ending drift로 확정되면 `.gitattributes` 기반으로 repo 차원에서 정리

### regional_zone_builder.py

분류:

```text
줄바꿈/인코딩 drift
```

근거:

- 기본 diff: `585 insertions / 585 deletions`
- `--ignore-space-at-eol` 기준 실질 diff 없음
- 파일 타입: UTF-8, CRLF

위험도:

```text
MEDIUM
```

이유:

- 출발지/권역 생성에 영향이 있는 파일이다.
- 실질 변경은 없어 보이나 dirty 상태가 배포 blocker다.

정리 전략:

- line ending drift로 분리
- 기능 변경으로 취급하지 않되, 운영 서버에서는 직접 reset 금지

### frontend/src/App.jsx

분류:

```text
운영 UI 수정 drift
```

실질 변경:

- `DayTripApp`에 `previewFrame` prop 추가
- `MobileShell`에 `previewFrame` 전달
- Overview preview에서만 mock frame 사용
- 실제 서비스 `IndividualPage` 배경을 흰색 full viewport로 변경

위험도:

```text
MEDIUM
```

의미:

- 목업 frame 제거 / 운영 화면 viewport 정리 작업으로 보인다.
- 운영 UX에 필요한 수정일 가능성이 높다.

정리 전략:

- 로컬 git 변경과 동일한지 확인
- 동일하면 commit 대상
- 다르면 운영 hotfix drift로 별도 백업 후 통합 필요

### frontend/src/components/common/MobileShell.jsx

분류:

```text
운영 UI 수정 drift
```

실질 변경:

- mock status bar `9:41`, battery/signal icon을 `previewFrame` + DEV/flag 조건으로 제한
- production 기본 화면은 browser viewport 전체 사용
- fixed mock frame 대신 실제 모바일 document scroll에 가깝게 변경
- bottom tab을 production에서는 sticky bottom으로 변경

위험도:

```text
MEDIUM
```

의미:

- 이전 모바일 목업 상태바 제거 / pull-to-refresh 정상화 작업과 일치한다.
- production UX 개선으로 보이며, 배포 후보일 가능성이 높다.

정리 전략:

- 반드시 git에 반영할지 결정
- 사주 링크 env injection과 함께 배포하려면 이 UI drift도 commit/merge 상태로 정리되어야 한다.

### frontend/src/index.css

분류:

```text
운영 UI 수정 drift
```

실질 변경:

- `body overflow: hidden` 제거
- `overflow-x: hidden`
- `overflow-y: auto`
- `overscroll-behavior-y: auto`

위험도:

```text
MEDIUM
```

의미:

- 모바일 pull-to-refresh / body scroll 복구 작업으로 보인다.

정리 전략:

- production UI fix로 commit 후보
- mobile smoke test 필요

### frontend/src/screens/day-trip/HomeScreen.jsx

분류:

```text
운영 UI 수정 drift
```

실질 변경:

- root container를 `height: 100%`/`overflow: hidden`에서 `minHeight: 100dvh`/`overflow: visible`로 변경
- main scroll area의 internal scroll 강제 제거
- safe-area/pull-to-refresh 대응으로 보임

위험도:

```text
MEDIUM
```

정리 전략:

- production UI fix로 commit 후보
- Android Chrome/iOS Safari smoke test 필요

### .gitignore 및 테스트/진단 산출물

대상:

```text
.gitignore
_anchor_test.txt
_course_quality_test.txt
_dq_diagnosis.txt
_enrich_test.txt
_template_test.txt
check_kid_out.txt
check_late_out.txt
check_schema_out.txt
check_selection_basis.py
debug.py
run_fix_103.py
run_zone_verify.py
sql/verify/00_run_order.md
test_course.py
test_sokcho2.json
test_sokcho_a.json
test_sokcho_b.json
test_sokcho_course.json
```

분류:

```text
대부분 줄바꿈 drift 또는 테스트/진단 산출물 drift
```

근거:

- `--ignore-space-at-eol` 기준 추가 실질 diff 없음
- QA/test output 성격의 파일명 다수

위험도:

```text
LOW to MEDIUM
```

정리 전략:

- 운영 서버에서 직접 삭제 금지
- 필요한 산출물은 `archive/` 또는 서버 외부로 백업
- 불필요하면 `.gitignore` 정책으로 정리

## Untracked 파일 분석

### Dockerfile

파일:

```text
Dockerfile
```

크기:

```text
209B
```

내용 요약:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

분류:

```text
운영 필수 배포 파일 가능성 높음
```

위험도:

```text
HIGH
```

이유:

- 현재 운영 `travel-backend` compose build에 사용될 가능성이 높다.
- git에 없으면 EC2 재구성/clone 기반 배포가 재현되지 않는다.

정리 전략:

- 로컬 repo의 운영 Dockerfile과 비교
- 운영 기준 파일로 채택할지 결정
- 채택 시 git commit 필요

### docker-compose.yml

파일:

```text
docker-compose.yml
```

크기:

```text
452B
```

내용 요약:

- `travel-backend`
  - build context `.`
  - env_file `.env`
  - expose `8000`
  - external network `saju_mbti_saju-net`
- `travel-frontend`
  - build context `./frontend`
  - expose `80`
  - external network `saju_mbti_saju-net`

분류:

```text
운영 필수 배포 파일
```

위험도:

```text
HIGH
```

이유:

- 현재 travel 서비스가 saju nginx external network에 붙는 핵심 파일이다.
- git에 없으면 EC2 pull 기반 배포가 불가능하거나 재현성이 깨진다.
- 현재 파일에는 `VITE_* build.args`가 없다.

정리 전략:

- 반드시 git 관리 대상으로 올릴지 결정
- `travel-frontend.build.args`를 포함한 최신 compose로 정리 필요
- 사주 nginx/network 설정은 유지해야 함

### frontend/Dockerfile

파일:

```text
frontend/Dockerfile
```

크기:

```text
184B
```

내용 요약:

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

분류:

```text
운영 필수 frontend build 파일
```

위험도:

```text
HIGH
```

이유:

- 현재 `travel-frontend` build에 사용되는 파일이다.
- git에 없으면 운영 frontend rebuild가 재현되지 않는다.
- 현재 파일에는 `VITE_* ARG/ENV`가 없다.

정리 전략:

- 로컬에서 만든 `frontend/Dockerfile`과 비교
- VITE env injection 반영본을 git으로 배포해야 함

### frontend/.dockerignore

내용:

```text
node_modules
dist
.vite
.env
```

분류:

```text
운영 build 보조 파일
```

위험도:

```text
MEDIUM
```

정리 전략:

- git 관리 후보
- frontend build context 최적화에 필요

### batch/update_all.sh

크기:

```text
8.5K
```

분류:

```text
운영 배치 wrapper 후보
```

위험도:

```text
MEDIUM
```

이유:

- 운영 데이터 업데이트 wrapper로 보인다.
- 현재 배포 작업과 직접 관련은 없지만 운영 entry point 문서와 연결될 수 있다.

정리 전략:

- 로컬 batch wrapper와 비교
- 운영에서 사용할 파일이면 git commit
- 아니면 archive

### batch/update_all.ps1

크기:

```text
3.5K
```

분류:

```text
Windows 개발환경 보조 wrapper 후보
```

위험도:

```text
LOW
```

정리 전략:

- 운영 EC2에는 필수 아님
- repo에 둘지는 로컬 정책으로 결정

### travel_db.dump

파일:

```text
travel_db.dump
```

크기:

```text
9.8M
```

타입:

```text
PostgreSQL custom database dump
```

MD5:

```text
f1dc80456e75b4a2ea7e386b84b08e80
```

분류:

```text
DB 백업/덤프 산출물
```

위험도:

```text
HIGH
```

이유:

- git에 올라가면 안 되는 데이터 파일이다.
- 운영 repo root에 있어서 실수로 commit/push될 위험이 있다.

정리 전략:

- 삭제 전 백업 위치로 이동 필요
- `.gitignore`에 `*.dump`, `travel_db*.dump`, `backups/` 정책 확인
- 운영자가 확인 후 archive 또는 안전한 backup directory로 이동

### travel_db.sql

파일:

```text
travel_db.sql
```

크기:

```text
36M
```

타입:

```text
UTF-8 PostgreSQL database dump
```

MD5:

```text
104fbae0334b829d4f92416e3b077c97
```

분류:

```text
DB SQL dump 산출물
```

위험도:

```text
HIGH
```

이유:

- DB dump가 git working tree root에 있음
- 민감 데이터/운영 데이터 유출 위험
- git status dirty blocker

정리 전략:

- 삭제 전 외부 백업 여부 확인
- git commit 금지
- 운영자가 명시적으로 archive 필요

## Production Drift 요약

### Drift 유형별 분류

| 유형 | 파일 | 위험도 | 배포 blocker |
| --- | --- | --- | --- |
| 운영 필수 compose/docker untracked | `Dockerfile`, `docker-compose.yml`, `frontend/Dockerfile` | HIGH | YES |
| DB dump untracked | `travel_db.dump`, `travel_db.sql` | HIGH | YES |
| 추천 엔진 line ending drift | `course_builder.py` | HIGH | YES |
| backend line ending drift | `api_server.py`, `regional_zone_builder.py` | MEDIUM | YES |
| frontend 실제 UX 수정 | `App.jsx`, `MobileShell.jsx`, `index.css`, `HomeScreen.jsx` | MEDIUM | YES |
| 테스트/진단 산출물 drift | `_*.txt`, `test_*.json`, `debug.py`, `run_*.py` | LOW/MEDIUM | YES |
| 배치 wrapper 후보 | `batch/update_all.*` | LOW/MEDIUM | NO for frontend deploy, YES for clean git |

### 핵심 문제

운영 서버가 git source of truth가 아니라, 운영 서버에서 직접 생성/수정된 파일을 포함하고 있다.

현재 상태에서 `git pull --ff-only`를 강행하면:

- 충돌 가능성
- 운영 compose/Dockerfile 유실 가능성
- DB dump 실수 commit 가능성
- frontend env injection 배포 실패 가능성
- backend/engine drift 원인 불명확 상태 지속

## 위험도

### HIGH

- `course_builder.py` dirty
- untracked `Dockerfile`
- untracked `docker-compose.yml`
- untracked `frontend/Dockerfile`
- untracked `travel_db.dump`
- untracked `travel_db.sql`

### MEDIUM

- `api_server.py` dirty
- `regional_zone_builder.py` dirty
- frontend UI drift 4개 파일
- `frontend/.dockerignore`
- `batch/update_all.sh`

### LOW

- 테스트 output txt/json
- Windows wrapper `batch/update_all.ps1`
- debug/test helper 파일

## 배포 blocker 여부

현재 상태는 배포 blocker다.

이유:

1. git clean 상태가 아니다.
2. 운영 Docker/compose 파일이 untracked다.
3. DB dump가 repo root에 있다.
4. frontend env injection 변경을 pull/build할 기준이 불명확하다.
5. `VITE_*` env도 아직 `.env`에서 확인되지 않았다.

## 권장 정리 순서

운영 서버에서 바로 reset/clean하지 말고 아래 순서로 처리한다.

### 1. 운영 상태 백업

읽기 전용 백업 계획:

```bash
tar -czf /tmp/travel_data_pipeline_drift_$(date +%Y%m%d_%H%M%S).tar.gz \
  Dockerfile docker-compose.yml frontend/Dockerfile frontend/.dockerignore \
  batch/update_all.sh batch/update_all.ps1 \
  travel_db.dump travel_db.sql
```

주의:

- 이 명령은 파일 생성이므로 현재 audit 단계에서는 실행하지 않았다.
- 실제 정리 단계에서만 운영자 승인 후 수행.

### 2. 운영 필수 Docker/compose 파일을 로컬 git과 비교

대상:

- `Dockerfile`
- `docker-compose.yml`
- `frontend/Dockerfile`
- `frontend/.dockerignore`

판단:

- 운영 기준 파일이면 git에 포함
- 로컬 최신 파일이 더 정확하면 운영 파일 교체는 배포 단계에서 수행

### 3. DB dump 분리

대상:

- `travel_db.dump`
- `travel_db.sql`

전략:

- git commit 금지
- `/home/ubuntu/backups/` 같은 repo 외부 경로로 archive
- `.gitignore`에 dump/sql 백업 패턴 추가 확인

### 4. line ending drift 정리

대상:

- `api_server.py`
- `course_builder.py`
- `regional_zone_builder.py`
- 테스트 산출물 다수

전략:

- `.gitattributes` 기준 확정
- 로컬 repo에서 line ending normalize
- 운영 서버에서 직접 reset하지 말고 pull 가능한 상태를 먼저 만든다.

### 5. frontend UI drift 통합

대상:

- `frontend/src/App.jsx`
- `frontend/src/components/common/MobileShell.jsx`
- `frontend/src/index.css`
- `frontend/src/screens/day-trip/HomeScreen.jsx`

전략:

- 이전 모바일 UI fix와 동일한지 로컬과 비교
- 동일하면 commit
- 다르면 별도 hotfix branch로 회수

### 6. EC2 clean 상태 달성

정리 후 목표:

```bash
git status --short
```

기대:

```text
<empty>
```

또는 운영에서 의도적으로 무시할 파일만 `.gitignore`에 의해 숨김 처리.

### 7. 그 다음 배포 재시도

clean 상태 + env 확인 후:

```bash
git pull --ff-only
docker compose build travel-frontend
docker compose up -d --no-deps travel-frontend
```

## 절대 금지 명령

현재 상태에서 아래 명령은 금지.

```bash
git reset --hard
git clean -fd
git checkout -- .
git pull --rebase
git merge
docker compose up -d --build
docker compose up -d
docker compose down
docker compose build
docker compose build travel-backend
docker restart saju-nginx
docker restart saju-frontend
docker restart saju-backend
sudo nginx -s reload
sudo systemctl restart nginx
psql -f travel_db.sql
pg_restore travel_db.dump
```

## 다음 작업 제안

1. EC2 drift 파일을 archive하는 별도 작업을 수행한다.
2. 운영 Docker/compose 파일을 로컬 repo에 정식 반영한다.
3. DB dump는 repo 외부 backup 위치로 이동하고 `.gitignore`를 강화한다.
4. line ending drift는 `.gitattributes` 기준으로 정리한다.
5. frontend UI drift가 로컬 최신 작업과 동일한지 비교한다.
6. clean 상태를 만든 뒤 `travel-frontend` only deploy를 재시도한다.
