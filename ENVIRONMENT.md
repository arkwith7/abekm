# Environment and Deployment

This repository is simplified to two environments:

- Development: `.env.development` + `docker-compose.yml`
- Production: `.env.production` + `docker-compose.prod.yml`

Helper scripts (now organized under `./shell-script/`, legacy wrappers kept at root for compatibility):
- `./shell-script/dev.sh up|down|logs SERVICE` – run local dev stack
- `./shell-script/deploy.sh up|down|restart|logs SERVICE` – run production stack on server

Frontend build uses `frontend/Dockerfile.prod` and reads `REACT_APP_*` from the environment at build time.

Log tips:
- `./shell-script/check-logs.sh backend --since 10m --tail 200`
- `./shell-script/check-logs.sh nginx --since 10m --tail 200`
