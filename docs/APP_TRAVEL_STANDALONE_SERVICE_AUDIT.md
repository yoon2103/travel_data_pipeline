# /app/travel Standalone Service Audit

## 목표

EC2의 `/app/travel` standalone uvicorn `:5000` 프로세스가 현재 운영 travel 서비스에 영향을 주는지 read-only로 확인했다.

수행하지 않음:

- process kill
- systemctl stop/disable/restart
- nginx 수정/reload/restart
- docker 수정/build/restart
- 파일 삭제

## :5000 사용 여부

현재 `:5000` listener는 존재한다.

```text
0.0.0.0:5000 users:(("uvicorn",pid=69677,fd=13))
```

프로세스:

```text
PID 69677
CMD /app/travel/.venv/bin/python3 /app/travel/.venv/bin/uvicorn api_server:app --host 0.0.0.0 --port 5000
```

cwd/env:

```text
cwd=/app/travel
PWD=/app/travel
VIRTUAL_ENV=/app/travel/.venv
```

직접 localhost access:

```text
curl http://127.0.0.1:5000/api/regions -> 200
```

판정:

```text
:5000 standalone API is alive
```

## nginx route 사용 여부

### Docker nginx route

현재 active public route로 추정되는 nginx config:

```text
/home/ubuntu/saju_mbti/nginx/default.conf
```

travel route:

```nginx
server {
    listen 80;
    server_name travel-planne.duckdns.org;

    location /api/ {
        proxy_pass http://travel-backend:8000;
    }

    location / {
        proxy_pass http://travel-frontend:80;
    }
}
```

즉 `travel-planne.duckdns.org`는 `:5000`이 아니라 Docker compose service를 사용한다.

### Host nginx legacy route

host nginx config에도 legacy route가 있다.

```text
/etc/nginx/sites-enabled/travel
```

내용:

```nginx
server {
    listen 80;
    server_name saju-mbti.duckdns.org;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

주의:

- 이 config는 `travel-planne.duckdns.org`가 아니라 `saju-mbti.duckdns.org` 대상이다.
- `nginx.service`는 현재 failed 상태이며, host port 80/443은 Docker proxy/nginx가 잡고 있다.

## systemd/service 여부

systemd service file 존재:

```text
/etc/systemd/system/travel-api.service
```

내용:

```ini
[Unit]
Description=Travel API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/app/travel
EnvironmentFile=/app/travel/.env
ExecStart=/app/travel/.venv/bin/uvicorn api_server:app --host 0.0.0.0 --port 5000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

service status:

```text
travel-api.service loaded inactive dead
enabled
Stopped since Tue 2026-05-05 13:45:40 UTC
```

판정:

```text
service file exists, enabled, but currently inactive
```

현재 pid `69677`은 PPID 1이지만 `systemctl status travel-api.service`의 active main process는 아니다.

## crontab/pm2/supervisor 여부

확인 결과:

```text
crontab: no relevant output
pm2: NO_PM2
supervisor: NO_SUPERVISOR
```

판정:

```text
No pm2/supervisor/crontab management found
```

## public domain 영향 여부

확인:

```text
curl -H 'Host: travel-planne.duckdns.org' http://127.0.0.1/            -> 200
curl -H 'Host: travel-planne.duckdns.org' http://127.0.0.1/api/regions -> 200
curl http://127.0.0.1:5000/api/regions                                -> 200
curl http://127.0.0.1/api/regions                                      -> 404
```

해석:

- Host header `travel-planne.duckdns.org` 요청은 Docker nginx route를 통해 정상 응답한다.
- Docker nginx config는 `/api/`를 `travel-backend:8000`으로 보낸다.
- `:5000` standalone API는 직접 접근하면 살아 있지만 `travel-planne.duckdns.org` route에는 연결되어 있지 않다.

판정:

```text
public travel domain does not appear to use :5000
```

## docker compose와 충돌 여부

Docker compose labels:

```text
travel-frontend:
  config_files=/home/ubuntu/travel_data_pipeline/docker-compose.yml
  working_dir=/home/ubuntu/travel_data_pipeline
  service=travel-frontend

travel-backend:
  config_files=/home/ubuntu/travel_data_pipeline/docker-compose.yml
  working_dir=/home/ubuntu/travel_data_pipeline
  service=travel-backend
```

Docker backend:

```text
travel-backend uvicorn api_server:app --host 0.0.0.0 --port 8000
```

Standalone backend:

```text
/app/travel uvicorn api_server:app --host 0.0.0.0 --port 5000
```

충돌 여부:

```text
No port conflict
```

위험:

- 동일 서비스가 두 경로에서 다른 commit으로 실행 중이라 운영 혼선 가능성이 있다.
- `/app/travel`은 commit `89d3619`, Docker compose source는 `/home/ubuntu/travel_data_pipeline` commit `ea95976`.
- `travel-api.service`가 enabled 상태라 부팅/수동 start 시 legacy `:5000`이 재등장할 가능성이 있다.

## /app/travel 상태 판정

상태:

```text
LEGACY_ONLY
```

근거:

- `/app/travel`은 오래된 commit `89d3619`.
- `:5000` 프로세스는 살아 있고 직접 호출 가능.
- 그러나 `travel-planne.duckdns.org` public route는 Docker compose `travel-backend:8000`, `travel-frontend:80`를 사용.
- host nginx legacy config는 `saju-mbti.duckdns.org -> 127.0.0.1:5000`이지만 현재 nginx.service는 failed이고 Docker nginx가 host 80/443을 점유.

`STILL_USED`로 보기에는 근거 부족.

`UNUSED`로 단정하기에는 `:5000` direct listener와 enabled systemd service가 남아 있어 아직 위험하다.

## 제거 가능 여부

현재 판단:

```text
REMOVABLE_LATER_AFTER_CONFIRMATION
```

즉시 제거는 금지.

제거 전 확인 필요:

1. `travel-planne.duckdns.org`가 Docker nginx route만 사용하는지 staging/production smoke test로 재확인.
2. `saju-mbti.duckdns.org` 도메인이 더 이상 사용되지 않는지 확인.
3. `/etc/nginx/sites-enabled/travel` legacy config가 실제 active path가 아닌지 확인.
4. `travel-api.service enabled` 상태를 어떻게 처리할지 결정.
5. `/app/travel/.env`에 운영 DB/secret이 있으면 안전하게 archive.
6. `/app/travel` 삭제 전 tar/archive.
7. rollback 필요 시 `:5000`을 다시 살릴 계획이 필요한지 결정.

## 제거 전 필요 조건

반드시 충족해야 할 조건:

- Docker compose route smoke PASS
- `travel-planne.duckdns.org/` PASS
- `travel-planne.duckdns.org/api/regions` PASS
- `saju-mbti-service.duckdns.org/result` 영향 없음
- `/app/travel` archive 완료
- `travel-api.service` disable/stop 계획 승인
- host nginx legacy config 처리 계획 승인
- 운영 DB backup 확인

주의:

- 이 audit에서는 stop/disable/remove를 수행하지 않았다.

## 다음 작업 제안

1. `/app/travel` legacy service retirement plan 작성.
2. `travel-api.service` enabled 상태를 어떻게 처리할지 runbook 작성.
3. `/etc/nginx/sites-enabled/travel` legacy config가 더 이상 필요 없는지 별도 audit.
4. `saju-mbti.duckdns.org`와 `saju-mbti-service.duckdns.org` 도메인 용도 정리.
5. Docker compose source-of-truth cleanup을 먼저 완료한 뒤 `/app/travel` 제거 여부를 결정.
