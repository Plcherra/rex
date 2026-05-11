import asyncio
from typing import Optional

import httpx


_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    global _client

    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
            ),
        )

    return _client


async def startup_http_client() -> None:
    get_http_client()


async def shutdown_http_client() -> None:
    global _client

    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


async def request_with_retries(
    method: str,
    url: str,
    retries: int = 2,
    **kwargs,
) -> httpx.Response:
    client = get_http_client()
    last_error: Optional[httpx.RequestError] = None

    for attempt in range(retries + 1):
        try:
            response = await client.request(method, url, **kwargs)
            if response.status_code < 500:
                return response
        except httpx.RequestError as error:
            last_error = error
            if attempt == retries:
                raise

        if attempt < retries:
            await asyncio.sleep(0.25 * (attempt + 1))

    if last_error is not None:
        raise last_error

    return response
