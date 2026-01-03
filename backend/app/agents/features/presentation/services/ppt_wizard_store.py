"""Lightweight persistence for template-first PPT wizard state.

This is a pragmatic Phase-2 step for the Template workflow:
- `generate-content` produces deck_spec/slide_matches/mappings.
- `build-from-data` may need those artifacts to rebuild deterministically.

We persist per (user_id, session_id, template_id) in Redis with a TTL.

Note:
- This is intentionally independent of LangGraph checkpointers.
- It is backwards-compatible: if session_id is missing or nothing is stored,
  callers can proceed with best-effort reconstruction from UI data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import quote

from loguru import logger

try:
    import redis.asyncio as redis
except Exception:  # pragma: no cover
    redis = None  # type: ignore

from app.core.config import settings


@dataclass(frozen=True)
class PPTWizardKey:
    user_id: str
    session_id: str
    template_id: str

    def as_redis_key(self) -> str:
        safe_template_id = quote(self.template_id, safe="")
        safe_session_id = quote(self.session_id, safe="")
        safe_user_id = quote(self.user_id, safe="")
        return f"ppt:wizard:{safe_user_id}:{safe_session_id}:{safe_template_id}"


class PPTWizardStateStore:
    def __init__(self, *, redis_url: str, ttl_seconds: int = 60 * 60 * 24):
        self._redis_url = redis_url
        self._ttl_seconds = ttl_seconds

    def _client(self):
        if redis is None:
            raise RuntimeError("redis package not available")
        return redis.from_url(self._redis_url, encoding="utf-8", decode_responses=True)

    async def save(
        self,
        *,
        key: PPTWizardKey,
        state: Dict[str, Any],
    ) -> None:
        redis_key = key.as_redis_key()
        payload = json.dumps(state, ensure_ascii=False)
        client = self._client()
        try:
            await client.set(redis_key, payload, ex=self._ttl_seconds)
            logger.info("🧠 [PPTWizardStore] saved: %s (ttl=%ss)", redis_key, self._ttl_seconds)
        finally:
            await client.aclose()

    async def load(self, *, key: PPTWizardKey) -> Optional[Dict[str, Any]]:
        redis_key = key.as_redis_key()
        client = self._client()
        try:
            raw = await client.get(redis_key)
            if not raw:
                return None
            try:
                return json.loads(raw)
            except Exception as e:
                logger.warning("🧠 [PPTWizardStore] corrupted JSON for %s: %s", redis_key, e)
                return None
        finally:
            await client.aclose()


ppt_wizard_store = PPTWizardStateStore(redis_url=settings.redis_url)
