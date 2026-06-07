"""Retry destekli, saygılı HTTP istemcisi."""
import asyncio
import random
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]


def make_headers(extra: dict | None = None) -> dict:
    h = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if extra:
        h.update(extra)
    return h


class RespectfulClient:
    """Aynı domain'e ardışık istekler arasında min bekleme süresi enforce eder."""

    def __init__(self, min_delay: float = 2.0, max_delay: float = 5.0,
                 timeout: float = 30.0, proxy: str | None = None):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            proxy=proxy,
            verify=True,
        )
        self._lock = asyncio.Lock()
        self._last_request_at: float = 0.0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    async def _throttle(self):
        async with self._lock:
            elapsed = asyncio.get_event_loop().time() - self._last_request_at
            wait_for = random.uniform(self.min_delay, self.max_delay)
            if elapsed < wait_for:
                await asyncio.sleep(wait_for - elapsed)
            self._last_request_at = asyncio.get_event_loop().time()

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get(self, url: str, **kwargs) -> httpx.Response:
        await self._throttle()
        kwargs.setdefault("headers", make_headers())
        r = await self._client.get(url, **kwargs)
        r.raise_for_status()
        return r

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    )
    async def post(self, url: str, **kwargs) -> httpx.Response:
        await self._throttle()
        kwargs.setdefault("headers", make_headers())
        r = await self._client.post(url, **kwargs)
        r.raise_for_status()
        return r
