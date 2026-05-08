# EC2 Local Path Mismatch Audit

## 목표

EC2 운영 경로와 로컬 최신 repo 기준 불일치 원인을 read-only로 확인했다.

수행하지 않음:

- 파일 수정
- git reset/clean
- git pull
- docker build/up/restart
- DB 작업

## EC2 repo remote/branch/commit

작업 경로:

```text
/home/ubuntu/travel_data_pipeline
```

remote:

```text
origin https://github.com/yoon2103/travel_data_pipeline.git (fetch)
origin https://github.com/yoon2103/travel_data_pipeline.git (push)
```

branch:

```text
main
```

HEAD:

```text
ea95976716535f5eafe0667cad2326c3fcd155c7
```

최근 commit:

```text
ea95976 Update travel frontend UI
89d3619 initial travel service deployment
```

## 로컬 repo remote/branch/commit

작업 경로:

```text
D:\travel_data_pipeline
```

remote:

```text
origin https://github.com/yoon2103/travel_data_pipeline.git (fetch)
origin https://github.com/yoon2103/travel_data_pipeline.git (push)
```

branch:

```text
main
```

HEAD:

```text
ea95976716535f5eafe0667cad2326c3fcd155c7
```

최근 commit:

```text
ea95976 Update travel frontend UI
89d3619 initial travel service deployment
```

현재 로컬 특이사항:

```text
A  Dockerfile
A  docker-compose.yml
A  frontend/.dockerignore
A  frontend/Dockerfile
```

이 4개 파일은 이전 Docker/compose source-of-truth staging 검증 작업에서 staged 상태다.

## 경로 불일치 여부

Git 기준으로는 EC2 `/home/ubuntu/travel_data_pipeline`과 로컬 `D:\travel_data_pipeline`이 같은 remote/branch/HEAD를 보고 있다.

```text
remote: same
branch: same
HEAD: same
```

하지만 EC2 안에 별도 travel app 경로가 존재한다.

```text
/app/travel
```

`/app/travel` git 정보:

```text
remote: https://github.com/yoon2103/travel_data_pipeline.git
branch: main
HEAD: 89d36195631e26ff1b2509ef6722f5a2e4f86aae
commit: 89d3619 initial travel service deployment
```

즉:

```text
/home/ubuntu/travel_data_pipeline = 최신 EC2 compose 기준 repo, HEAD ea95976
/app/travel = 과거 standalone 실행 경로, HEAD 89d3619
```

## 다른 실행 경로 존재 여부

`/home/ubuntu` 주요 경로:

```text
/home/ubuntu/saju-app
/home/ubuntu/saju_mbti
/home/ubuntu/travel_data_pipeline
/home/ubuntu/backups
```

`/app`:

```text
/app/travel
```

프로세스 확인:

```text
ubuntu  /app/travel/.venv/bin/uvicorn api_server:app --host 0.0.0.0 --port 5000
root    /usr/local/bin/uvicorn api_server:app --host 0.0.0.0 --port 8000
root    nginx master/worker processes
root    dockerd
```

포트 확인:

```text
0.0.0.0:5000  uvicorn from /app/travel
0.0.0.0:80    docker-proxy/nginx
0.0.0.0:443   docker-proxy/nginx
```

해석:

- `/app/travel`은 별도 standalone FastAPI 서버로 `5000` 포트에서 떠 있다.
- Docker compose 기반 travel backend는 container 내부 `8000` 기준이다.
- 현재 public travel domain은 nginx/docker compose 경로를 사용하는 것으로 추정된다.

## docker compose source path 추정

`docker inspect travel-frontend --format '{{json .Config.Labels}}'` 결과 핵심:

```json
{
  "com.docker.compose.project": "travel_data_pipeline",
  "com.docker.compose.project.config_files": "/home/ubuntu/travel_data_pipeline/docker-compose.yml",
  "com.docker.compose.project.working_dir": "/home/ubuntu/travel_data_pipeline",
  "com.docker.compose.service": "travel-frontend"
}
```

`docker inspect travel-backend --format '{{json .Config.Labels}}'` 결과 핵심:

```json
{
  "com.docker.compose.project": "travel_data_pipeline",
  "com.docker.compose.project.config_files": "/home/ubuntu/travel_data_pipeline/docker-compose.yml",
  "com.docker.compose.project.working_dir": "/home/ubuntu/travel_data_pipeline",
  "com.docker.compose.service": "travel-backend"
}
```

mounts:

```text
travel-frontend mounts: []
travel-backend mounts: []
```

해석:

- 현재 Docker container는 bind mount로 소스 경로를 읽는 구조가 아니다.
- image build 당시 `/home/ubuntu/travel_data_pipeline/docker-compose.yml` 기준으로 생성됐다.
- compose source path는 명확히 `/home/ubuntu/travel_data_pipeline`이다.

## 결론

### 1. 로컬과 EC2 repo commit 불일치는 아니다

로컬과 EC2 `/home/ubuntu/travel_data_pipeline`은 같은 remote/branch/HEAD다.

```text
ea95976716535f5eafe0667cad2326c3fcd155c7
```

### 2. 실제 불일치 원인은 EC2 working tree drift다

불일치의 주 원인:

- EC2 `/home/ubuntu/travel_data_pipeline`에 untracked 운영 Docker/compose 파일 존재
- line ending drift
- frontend UI drift
- test/debug artifact drift
- DB dump는 repo 밖으로 이동 완료

### 3. 또 다른 혼선 원인은 `/app/travel` standalone 경로다

`/app/travel`은 같은 repo이지만 오래된 commit이다.

```text
89d3619 initial travel service deployment
```

현재 `5000` 포트 uvicorn은 이 경로에서 실행 중이다.

이 경로는 현재 Docker compose label 기준 운영 travel domain의 source path가 아니다. 다만 과거 테스트/운영 혼선의 원인이 될 수 있다.

### 4. Docker compose 기준 운영 경로는 명확하다

현재 `travel-frontend`, `travel-backend` container는 아래 compose path 기준으로 만들어졌다.

```text
/home/ubuntu/travel_data_pipeline/docker-compose.yml
```

### 5. 다음 판단

배포 재개 기준은 `/home/ubuntu/travel_data_pipeline`을 clean/source-of-truth 상태로 만드는 것이다.

`/app/travel`은 현재 작업 대상에서 제외하고, 별도 단계에서:

- 유지할지
- 중지할지
- archive할지
- 문서화할지

를 결정해야 한다.

## 다음 작업 제안

1. `/home/ubuntu/travel_data_pipeline` 기준으로 Docker/compose source-of-truth commit을 완료한다.
2. line ending drift와 frontend UI drift를 별도 단계로 정리한다.
3. `/app/travel` standalone service의 용도를 별도 audit한다.
4. public travel domain이 Docker compose backend `8000`만 사용하는지 nginx config 기준으로 다시 확인한다.
5. clean 상태 달성 후 `travel-frontend` only deploy를 재시도한다.
