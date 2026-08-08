# Docker Compose Files

Each file declares its own Compose `name:` (salesflow-dev /
salesflow-prod) so the two can never collide on container/volume names.
If you tested an earlier version of this repo before that was added,
run `docker compose -f docker/docker-compose.prod.yml down -v` once to
remove the old shared `docker-*` containers/volumes before continuing.

Two compose files, both under `docker/`, both reference `../.env`:

## `docker-compose.yml` — development

- Builds with `requirements/dev.txt`
- Bind-mounts the repo into the container (live reload via `runserver`)
- Includes MinIO as the local S3-compatible stand-in
  (docs/06-architecture.md §2)
- Includes `postgres` and `redis` containers directly — fine for local
  dev where losing the volume on `docker compose down -v` is expected

```bash
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml exec web python manage.py migrate
```

## `docker-compose.prod.yml` — production

- Builds with `requirements/prod.txt` (gunicorn, no dev/debug tooling)
- No bind-mount — the built image is the deployable artifact
- No MinIO — production points `django-storages` at real AWS S3 via
  `.env` (docs/06-architecture.md §2); no compose service needed for that
- Postgres/Redis are **external by default** (e.g. RDS, ElastiCache) —
  set `DATABASE_URL` / `REDIS_URL` / `CELERY_BROKER_URL` /
  `CELERY_RESULT_BACKEND` in `.env` accordingly. Self-hosted container
  alternatives are included commented-out in the file if you'd rather
  run them yourself.

```bash
docker compose -f docker/docker-compose.prod.yml build
docker compose -f docker/docker-compose.prod.yml up -d
docker compose -f docker/docker-compose.prod.yml exec web python manage.py migrate
```

`web` is the only horizontally-scalable service
(docs/06-architecture.md §6):

```bash
docker compose -f docker/docker-compose.prod.yml up -d --scale web=3
```

Compose itself isn't a production orchestrator (no rolling deploys,
no health-based rescheduling) — put a load balancer in front, or adapt
these service definitions for Swarm/K8s/ECS if you need that. Which
orchestrator to use is outside `docs/06-architecture.md`'s scope.

`beat` must never run more than one replica — running two Beat
processes double-fires every scheduled job.


## Static files & nginx (production only)

`docker-compose.prod.yml` includes an `nginx` service that is the
single public entry point (port 80) — `web` no longer publishes 8000
to the host. Nginx serves `/static/*` directly from a shared
`static_volume`; everything else is proxied to `web:8000`.

`collectstatic` runs automatically on every `web` container start
(`docker/entrypoint.sh`) — no manual step needed, and it never runs for
`worker`/`beat`/dev's `runserver`.

TLS is **not configured** — nginx listens on plain HTTP only. Until you
add a 443 server block with real certificates (or put another
TLS-terminating layer in front), keep `SECURE_SSL_REDIRECT=False` in
`.env`, or every request will 301-redirect to a nonexistent HTTPS
endpoint.

