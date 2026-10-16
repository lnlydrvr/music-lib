"""Lazy HTTP access to lucida.to."""

from __future__ import annotations

import asyncio
import importlib
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Any

class LucidaAccessRequired(RuntimeError):
    """Lucida clearance is missing, expired, or rejected by the service."""
MAX_RETRY_DELAY = 30.0


class LucidaClient:
    """Async client with bounded GET retries and explicit clearance errors."""

    def __init__(self, *, transport: Any = None, retries: int = 3, retry_delay: float = 0.25):
        httpx = importlib.import_module("httpx")
        self.retries = max(0, retries)
        self.retry_delay = retry_delay
        cf = importlib.import_module("src.lucida.cf")
        clearance, ua = cf.load_clearance()
        if not clearance or not ua:
            raise LucidaAccessRequired("Lucida clearance is required.")
        headers = {"Cookie": f"cf_clearance={clearance}", "User-Agent": ua}
        self._client = httpx.AsyncClient(http2=True, headers=headers, transport=transport)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.aclose()

    async def aclose(self):
        await self._client.aclose()

    async def get(self, url: str, **kwargs):
        return await self._request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs):
        return await self._request("POST", url, **kwargs)

    async def _request(self, method: str, url: str, **kwargs):
        httpx = importlib.import_module("httpx")
        for attempt in range(self.retries + 1):
            try:
                response = await getattr(self._client, method.lower())(url, **kwargs)
            except httpx.RequestError:
                if attempt >= self.retries:
                    raise
                await asyncio.sleep(min(self.retry_delay * (2**attempt), MAX_RETRY_DELAY))
                continue
            if response.status_code == 403:
                raise LucidaAccessRequired("Lucida access has expired; prepare access again.")
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < self.retries:
                    delay = _retry_after(response.headers.get("Retry-After"))
                    if delay is None:
                        delay = self.retry_delay * (2**attempt)
                    await asyncio.sleep(min(delay, MAX_RETRY_DELAY))
                    continue
            response.raise_for_status()
            return response
        raise RuntimeError("Unreachable retry state")

    async def stream(self, url: str, **kwargs):
        """Open and validate a streaming GET response without reading its body."""
        httpx = importlib.import_module("httpx")
        for attempt in range(self.retries + 1):
            try:
                request = self._client.build_request("GET", url, **kwargs)
                response = await self._client.send(request, stream=True)
            except httpx.RequestError:
                if attempt >= self.retries:
                    raise
                await asyncio.sleep(min(self.retry_delay * (2**attempt), MAX_RETRY_DELAY))
                continue
            if response.status_code == 403:
                await response.aclose()
                raise LucidaAccessRequired("Lucida access has expired; prepare access again.")
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < self.retries:
                    delay = _retry_after(response.headers.get("Retry-After"))
                    if delay is None:
                        delay = self.retry_delay * (2**attempt)
                    await response.aclose()
                    await asyncio.sleep(min(delay, MAX_RETRY_DELAY))
                    continue
            try:
                response.raise_for_status()
            except BaseException:
                await response.aclose()
                raise
            return _StreamingResponse(response)
        raise RuntimeError("Unreachable retry state")


class _StreamingResponse:
    """Expose httpx streaming without buffering the response body."""

    def __init__(self, response):
        self._response = response
        self.headers = response.headers

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self._response.aclose()

    async def aiter_bytes(self, *args, **kwargs):
        async for chunk in self._response.aiter_bytes(*args, **kwargs):
            yield chunk


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None
