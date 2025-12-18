
# Backend Environment (.env)

The backend container reads environment variables from `backend/.env` via `docker-compose.yml` / `docker-compose.prod.yml` (`env_file`).

## LangSmith tracing (optional)

To enable LangChain/LangGraph tracing in LangSmith:

- `LANGCHAIN_TRACING_V2=true`
- `LANGSMITH_API_KEY=...`
- `LANGCHAIN_PROJECT=abekm-dev` (or `abekm-prod`)

Optional:

- `LANGCHAIN_ENDPOINT=https://api.smith.langchain.com`

### Mirror trace summaries to logs (optional)

If you want minimal trace start/end/error events in existing backend logs (terminal/file), set:

- `LANGCHAIN_TRACE_TO_LOG=true`

This keeps your current logging pipeline intact, and you can still open the LangSmith web UI only when deeper debugging is needed.
