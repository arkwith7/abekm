# Environment and Deployment

This repository is simplified to two environments:

- Development: `docker-compose.yml` + `backend/.env`
- Production: `docker-compose.prod.yml` + `backend/.env`

Helper scripts (kept minimal under `./shell-script/`):
- `./shell-script/dev-start-backend.sh` – run backend + celery-worker (dev)
- `./shell-script/dev-start-frontend.sh` – run frontend (dev)
- `./shell-script/deploy.sh up|down|restart|rebuild|logs SERVICE|ps` – run production stack on server

See `shell-script/GUIDE.md` for the canonical usage.

Frontend build uses `frontend/Dockerfile.prod` and reads `REACT_APP_*` from the environment at build time.

Log tips:
- `docker compose -f docker-compose.prod.yml logs -f --tail=200 backend`
- `docker compose -f docker-compose.prod.yml logs -f --tail=200 nginx`
