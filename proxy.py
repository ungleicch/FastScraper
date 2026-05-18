import asyncio
import re
from typing import List

import aiohttp

# Active, high-refresh-rate proxy sources
SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http",
]

# Fast C-backed Regex for IP:PORT validation
IP_PORT_RE = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){3}:\d{1,5})$")


async def _fetch_candidates(
    session: aiohttp.ClientSession, fetch_timeout: int = 5
) -> set[str]:
    candidates = set()

    async def fetch_src(url):
        try:
            async with session.get(url, timeout=fetch_timeout) as resp:
                if resp.status == 200:
                    txt = await resp.text()
                    for line in txt.splitlines():
                        line = line.strip()
                        if IP_PORT_RE.match(line):
                            candidates.add(line)
        except Exception:
            pass

    # Fetch from all sources entirely in parallel
    await asyncio.gather(*(fetch_src(u) for u in SOURCES))
    return candidates


async def _validate_proxy(
    session: aiohttp.ClientSession,
    proxy: str,
    test_url: str = "http://gstatic.com/generate_204",
    timeout: int = 3,
) -> str | None:
    proxy_url = f"http://{proxy}"
    try:
        # Use Google's 204 No Content edge nodes for near-instant 0-byte validation
        async with session.get(
            test_url, proxy=proxy_url, timeout=timeout, allow_redirects=False
        ) as resp:
            if resp.status == 204:
                return proxy_url
    except Exception:
        return None


async def discover_proxies(
    limit: int = 20, timeout: int = 3, fetch_timeout: int = 5
) -> List[str]:
    """
    Discover and validate working HTTP proxies using extreme C-backed concurrency.
    """
    async with aiohttp.ClientSession() as session:
        candidates = await _fetch_candidates(session, fetch_timeout=fetch_timeout)
        if not candidates:
            return []

        # Crank up concurrency. uvloop easily handles 500+ sockets natively.
        sem = asyncio.Semaphore(500)

        async def test_one(p: str):
            async with sem:
                return await _validate_proxy(session, p, timeout=timeout)

        # Fire all connections asynchronously into the C-event loop
        pending = set(asyncio.create_task(test_one(p)) for p in candidates)
        results: List[str] = []

        # FIRST_COMPLETED Race - Grab results as they resolve instantly
        while pending and len(results) < limit:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                try:
                    res = task.result()
                    if res:
                        results.append(res)
                        if len(results) >= limit:
                            break
                except Exception:
                    pass

        # Clean up the C-loop by nuking all remaining slow requests.
        for task in pending:
            task.cancel()

        return results[:limit]
