"""
Request guards shared by the API routes.

* Rate limiting — every AI endpoint spends Anthropic credits, and the API is
  public, so each client IP gets a sliding-window budget per bucket. In-memory
  is enough for the single-instance deployment; swap for Redis if you scale out.
* Client ID — an anonymous, browser-generated UUID sent as `X-Client-Id`. It is
  not authentication; it scopes the history list so visitors only see their own
  generations instead of every candidate's name and role.
* Concurrency — a cap on simultaneous pipelines so a burst of requests queues
  instead of exhausting memory on a small instance.
"""
import asyncio
import re
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

from app.config import settings

_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9-]{16,64}$")


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> None:
        if self.limit <= 0:
            return  # disabled
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            retry_after = int(self.window - (now - hits[0])) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit reached ({self.limit} requests per {self.window // 60} min). "
                       f"Try again in {max(1, retry_after // 60)} min.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)

    def prune(self) -> None:
        """Drop idle keys so the table doesn't grow without bound."""
        now = time.monotonic()
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window]:
            del self._hits[key]


# Full pipeline runs (generate, refine, enhance) — each is several Claude calls.
_pipeline_limiter = SlidingWindowLimiter(settings.rate_limit_generations_per_hour, 3600)
# Single-call AI endpoints (extract, cover letter, quality check, analysis).
_ai_limiter = SlidingWindowLimiter(settings.rate_limit_ai_calls_per_hour, 3600)


def _client_ip(request: Request) -> str:
    # uvicorn runs with --proxy-headers, so request.client is the real caller
    # behind Render's proxy rather than the proxy itself.
    return request.client.host if request.client else "unknown"


async def limit_pipeline(request: Request) -> None:
    _pipeline_limiter.hit(_client_ip(request))


async def limit_ai(request: Request) -> None:
    _ai_limiter.hit(_client_ip(request))


def prune_limiters() -> None:
    _pipeline_limiter.prune()
    _ai_limiter.prune()


async def client_id(x_client_id: str | None = Header(default=None)) -> str | None:
    if x_client_id and _CLIENT_ID_RE.match(x_client_id):
        return x_client_id
    return None


_generation_slots = asyncio.Semaphore(max(1, settings.max_concurrent_generations))


def generation_slots() -> asyncio.Semaphore:
    return _generation_slots
