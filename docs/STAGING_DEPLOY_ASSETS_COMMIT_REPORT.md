# Staging / Deploy Assets Commit Report

## 최종 판정

**PASS**

staging/deploy 재현에 필요한 asset만 별도 commit했다.

수행하지 않음:

- deploy
- docker build
- docker compose up
- governance tooling staging
- migration staging
- line ending normalize

## staged 파일

실행:

```bash
git add -- \
  Dockerfile.staging \
  docker-compose.staging.yml \
  frontend/Dockerfile.staging \
  frontend/nginx.staging.conf \
  staging_deploy.sh \
  README.md \
  batch/update_all.sh \
  batch/update_all.ps1
```

staged 결과:

```text
A	Dockerfile.staging
A	README.md
A	batch/update_all.ps1
A	batch/update_all.sh
A	docker-compose.staging.yml
A	frontend/Dockerfile.staging
A	frontend/nginx.staging.conf
A	staging_deploy.sh
```

## git diff --cached 요약

```text
Dockerfile.staging          |  19 ++++
README.md                   | 116 +++++++++++++++++++++
batch/update_all.ps1        |  97 +++++++++++++++++
batch/update_all.sh         | 248 ++++++++++++++++++++++++++++++++++++++++++++
docker-compose.staging.yml  |  27 +++++
frontend/Dockerfile.staging |  20 ++++
frontend/nginx.staging.conf |  32 ++++++
staging_deploy.sh           |  98 +++++++++++++++++
8 files changed, 657 insertions(+)
```

## 포함하지 않은 핵심 파일

검증:

```text
NO_FORBIDDEN_FILES_IN_CACHED_DIFF
```

포함하지 않음:

```text
frontend/src/
api_server.py
course_builder.py
regional_zone_builder.py
batch/place_enrichment/
migration_*.sql
tourism_belt.py
```

## commit 결과

commit message:

```text
chore: add staging and deployment assets
```

commit hash:

```text
4f72111
```

최근 commit:

```text
4f72111 chore: add staging and deployment assets
d58b604 feat: add saved course and mobile UX improvements
259f247 chore: strengthen artifact and env policies
33965e2 chore: add production docker compose source of truth
```

## git status 후

staged diff:

```text
<empty>
```

남은 drift:

```text
?? batch/place_enrichment/
?? docs/
?? migration_009_place_enrichment.sql
?? migration_010_representative_poi_candidates.sql
?? migration_011_seed_candidates.sql
?? tests/
```

## deploy 미수행 확인

실행하지 않음:

```text
docker build
docker compose build
docker compose up
docker compose down
docker restart
nginx restart/reload
git push
```

## 남은 drift 요약

### governance/enrichment

```text
batch/place_enrichment/
migration_009_place_enrichment.sql
migration_010_representative_poi_candidates.sql
migration_011_seed_candidates.sql
```

### docs/tests

```text
docs/
tests/
```

## 다음 commit 단계

권장 분리:

1. enrichment governance commit
   - `batch/place_enrichment/`
   - `migration_009_place_enrichment.sql`
   - `migration_010_representative_poi_candidates.sql`
   - `migration_011_seed_candidates.sql`

2. docs/tests commit
   - `docs/`
   - `tests/`

deploy는 아직 금지 상태다.
