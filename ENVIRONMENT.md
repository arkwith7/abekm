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

## LangSmith / Tracing

This repo supports LangChain/LangGraph tracing via LangSmith.

### What you get
- **LangSmith UI (web)**: full traces (steps, tool calls, timings, inputs/outputs depending on settings)
- **Existing logs (terminal/file)**: you can keep your current logging as-is, and optionally mirror *summary* events (start/end/error) with `run_id` using a safe callback.

### Required env vars (set in `backend/.env`)
- `LANGCHAIN_TRACING_V2=true`
- `LANGSMITH_API_KEY=...` (keep secret)
- `LANGCHAIN_PROJECT=abekm` (or per-env project like `abekm-prod`)

Optional:
- `LANGCHAIN_ENDPOINT=https://api.smith.langchain.com` (default)
- `LANGCHAIN_TRACE_TO_LOG=true` (mirror minimal callback events into backend logs)

### Notes
- Even with LangSmith enabled, you **do not have to watch the web UI** during normal operation.
	Typically you log/return `run_id` in API responses and only open LangSmith when debugging.
- `LANGCHAIN_TRACE_TO_LOG=true` is meant for **summary visibility** in terminal/file logs.
	It does not replicate the full LangSmith trace data locally.
