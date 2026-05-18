from __future__ import annotations

import asyncio
import json
import random
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import aiohttp
from aiohttp.resolver import AsyncResolver

from config import ScraperConfig
from output import OutputManager
from parser import parse_page, same_domain, url_extension
from proxy import discover_proxies


def evt(kind: str, **kw) -> str:
    return json.dumps({"type": kind, **kw})


class Crawler:
    def __init__(self, cfg: ScraperConfig, event_queue: asyncio.Queue):
        self.cfg = cfg
        self.q = event_queue
        self.base_host = urlparse(cfg.base_url).netloc
        self.output = OutputManager(cfg.output_dir)
        self._stop = False
        self._robots: Optional[RobotFileParser] = None
        self._results: List[Dict[str, Any]] = []
        self._media_count = 0
        self._bytes = 0
        self._proxy_idx = 0
        self._failed_proxies = set()

    def stop(self):
        self._stop = True

    async def run(self):
        t0 = time.perf_counter()
        await self._emit("status", phase=0, text="Connecting…")

        resolver = AsyncResolver()
        connector = aiohttp.TCPConnector(
            limit=self.cfg.max_concurrent,
            ttl_dns_cache=300,
            ssl=False,
            resolver=resolver,
        )
        timeout = aiohttp.ClientTimeout(
            total=self.cfg.request_timeout,
            connect=self.cfg.connect_timeout,
        )

        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout
        ) as session:
            self._session = session

            if not self.cfg.proxies:
                try:
                    await self._emit(
                        "log", level="dim", msg="Discovering public proxies…"
                    )
                    found = await discover_proxies(limit=10, timeout=4)
                    if found:
                        self.cfg.proxies = found
                        await self._emit(
                            "log",
                            level="ok",
                            msg=f"Loaded {len(found)} working proxies",
                        )
                    else:
                        await self._emit(
                            "log", level="dim", msg="No working public proxies found"
                        )
                except Exception as e:
                    await self._emit(
                        "log", level="err", msg=f"Proxy discovery failed: {e}"
                    )

            if self.cfg.respect_robots_txt:
                await self._load_robots()

            await self._emit("phase", phase=1, text="BFS site mapping…")
            url_map = await self._bfs_discover()
            if self._stop:
                return await self._finish(t0, stopped=True)

            all_urls = list(url_map.keys())
            await self._emit("phase1_done", total=len(all_urls))
            await self._emit(
                "log",
                level="ok",
                msg=f"Phase 1 complete — {len(all_urls)} URLs discovered",
            )

            await self._emit("phase", phase=2, text="Parallel page fetch…")
            await self._parallel_fetch(all_urls)
            if self._stop:
                return await self._finish(t0, stopped=True)

            ok = sum(1 for r in self._results if r.get("success"))
            errs = len(self._results) - ok
            await self._emit(
                "log",
                level="ok",
                msg=f"Phase 2 complete — {ok} pages OK, {errs} errors",
            )

            # ── Media Filtering Logic ──
            if self.cfg.dl_images or self.cfg.dl_videos or self.cfg.dl_gifs:
                all_media: Set[str] = set()

                for r in self._results:
                    for url in r.get("media_urls", []):
                        ext = url_extension(url)
                        if ext == ".gif":
                            if self.cfg.dl_gifs:
                                all_media.add(url)
                        elif ext in {
                            ".mp4",
                            ".webm",
                            ".ogg",
                            ".mov",
                            ".avi",
                            ".mkv",
                            ".m4v",
                        }:
                            if self.cfg.dl_videos:
                                all_media.add(url)
                        else:
                            # Treat standard image extensions + extensionless urls as Images
                            if self.cfg.dl_images:
                                all_media.add(url)

                media_list = list(all_media)
                if media_list:
                    await self._emit(
                        "phase",
                        phase=3,
                        text=f"Downloading {len(media_list)} media files…",
                    )
                    await self._download_media(media_list)

        await self._finish(t0)

    async def _bfs_discover(self) -> Dict[str, int]:
        visited: Dict[str, int] = {self.cfg.base_url: 0}
        queue: deque = deque([(self.cfg.base_url, 0)])
        sem = asyncio.Semaphore(self.cfg.max_concurrent)

        while queue and len(visited) < self.cfg.max_pages and not self._stop:
            batch = []
            while queue and len(batch) < self.cfg.max_concurrent:
                url, depth = queue.popleft()
                if depth < self.cfg.max_depth:
                    batch.append((url, depth))
            if not batch:
                break

            async def discover_one(url: str, depth: int):
                async with sem:
                    return depth, await self._fetch_links(url)

            results = await asyncio.gather(
                *[discover_one(u, d) for u, d in batch], return_exceptions=True
            )

            for (url, depth), res in zip(batch, results):
                if isinstance(res, Exception):
                    continue
                _, links = res
                for link in links:
                    if (
                        link not in visited
                        and len(visited) < self.cfg.max_pages
                        and self._is_allowed(link)
                    ):
                        visited[link] = depth + 1
                        queue.append((link, depth + 1))

            await self._emit(
                "bfs_progress",
                found=len(visited),
                queue=len(queue),
                pct=min(100, int(len(visited) / self.cfg.max_pages * 100)),
            )

        return visited

    async def _fetch_links(self, url: str) -> List[str]:
        try:
            headers = {
                "User-Agent": random.choice(self.cfg.user_agents),
                "Accept-Encoding": "gzip, deflate",
            }
            proxy = self._get_proxy()
            async with self._session.get(
                url, headers=headers, proxy=proxy, allow_redirects=True
            ) as resp:
                if resp.status != 200 or "html" not in resp.headers.get(
                    "Content-Type", ""
                ):
                    return []
                raw = await resp.read()
                _, links, _ = parse_page(raw, url)
                return links
        except Exception:
            return []

    async def _parallel_fetch(self, urls: List[str]):
        total, done, q = len(urls), 0, asyncio.Queue()
        for u in urls:
            q.put_nowait(u)

        async def worker():
            nonlocal done
            while not q.empty():
                try:
                    url = q.get_nowait()
                except asyncio.QueueEmpty:
                    break

                result = await self._full_fetch(url)
                self._results.append(result)
                done += 1
                await self._emit(
                    "page_done",
                    url=url,
                    status=result["status"],
                    ms=result["response_ms"],
                    success=result["success"],
                    error=result.get("error", ""),
                    done=done,
                    total=total,
                    pct=int(done / total * 100),
                )
                q.task_done()

        workers = [
            asyncio.create_task(worker()) for _ in range(self.cfg.max_concurrent)
        ]
        await asyncio.gather(*workers)

    async def _full_fetch(self, url: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "url": url,
            "success": False,
            "status": 0,
            "response_ms": 0,
            "error": "",
            "media_urls": [],
        }
        try:
            headers = {
                "User-Agent": random.choice(self.cfg.user_agents),
                "Accept-Encoding": "gzip, deflate",
            }
            proxy = self._get_proxy()

            if self.cfg.delay_between_requests > 0:
                await asyncio.sleep(self.cfg.delay_between_requests)

            t0 = time.perf_counter()
            try:
                async with self._session.get(
                    url, headers=headers, proxy=proxy, allow_redirects=True
                ) as resp:
                    result["status"] = resp.status
                    result["response_ms"] = int((time.perf_counter() - t0) * 1000)

                    if resp.status < 200 or resp.status >= 300:
                        result["error"] = f"HTTP {resp.status}"
                        return result

                    ct = resp.headers.get("Content-Type", "")
                    raw = await resp.read()
                    self._bytes += len(raw)
            except Exception as e:
                if proxy:
                    self._mark_proxy_failed(proxy)
                raise

            if "html" in ct:
                text, links, media = parse_page(raw, url)
                result["media_urls"] = media
                if self.cfg.save_html:
                    await self.output.save_html(url, raw)
                if self.cfg.save_text and text:
                    await self.output.save_text(url, text)

            result["success"] = True

        except asyncio.TimeoutError:
            result["error"] = "Timeout"
        except Exception as e:
            result["error"] = str(e)
        return result

    async def _download_media(self, media_urls: List[str]):
        total, done, q = len(media_urls), 0, asyncio.Queue()
        for u in media_urls:
            q.put_nowait(u)

        async def worker():
            nonlocal done
            while not q.empty():
                try:
                    url = q.get_nowait()
                except asyncio.QueueEmpty:
                    break
                try:
                    headers = {
                        "User-Agent": random.choice(self.cfg.user_agents),
                        "Accept-Encoding": "gzip, deflate",
                    }
                    proxy = self._get_proxy()
                    async with self._session.get(
                        url, headers=headers, proxy=proxy
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            await self.output.save_media(url, data)
                            self._media_count += 1
                            done += 1
                            await self._emit(
                                "media_done",
                                url=url,
                                done=done,
                                total=total,
                                pct=int(done / total * 100),
                            )
                except Exception:
                    pass
                q.task_done()

        workers = [
            asyncio.create_task(worker()) for _ in range(self.cfg.max_concurrent)
        ]
        await asyncio.gather(*workers)

    async def _finish(self, t0: float, stopped: bool = False):
        elapsed = time.perf_counter() - t0
        ok = sum(1 for r in self._results if r.get("success"))

        await self.output.write_report(
            self._results,
            {
                "base_url": self.cfg.base_url,
                "elapsed": elapsed,
                "media": self._media_count,
            },
        )
        await self._emit(
            "done",
            stopped=stopped,
            pages=ok,
            total=len(self._results),
            media=self._media_count,
            bytes=self._bytes,
            elapsed=round(elapsed, 2),
        )
        await self.q.put(None)

    async def _emit(self, kind: str, **kw):
        await self.q.put(evt(kind, **kw))

    def _is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if self.cfg.same_domain_only and not same_domain(url, self.base_host):
            return False

        ext = url_extension(url)
        if ext:
            is_gif = ext == ".gif"
            is_vid = ext in {".mp4", ".webm", ".ogg", ".mov", ".avi", ".mkv", ".m4v"}
            is_img = ext in {".jpg", ".jpeg", ".png", ".webp", ".svg", ".ico", ".bmp"}

            # If it's a direct media link, respect the user's config toggles
            if is_gif:
                return self.cfg.dl_gifs
            if is_vid:
                return self.cfg.dl_videos
            if is_img:
                return self.cfg.dl_images

            # If not media, check general allowed extensions
            if ext not in self.cfg.allowed_extensions:
                return False

        for pat in self.cfg.exclude_patterns:
            if pat.lower() in url.lower():
                return False
        if self._robots and not self._robots.can_fetch("*", url):
            return False
        return True

    async def _load_robots(self):
        robots_url = (
            f"{urlparse(self.cfg.base_url).scheme}://{self.base_host}/robots.txt"
        )
        try:
            async with self._session.get(
                robots_url, headers={"Accept-Encoding": "gzip, deflate"}
            ) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    rp = RobotFileParser()
                    rp.set_url(robots_url)
                    rp.parse(text.splitlines())
                    self._robots = rp
                    await self._emit(
                        "log", level="dim", msg=f"robots.txt loaded from {robots_url}"
                    )
        except Exception:
            pass

    def _get_proxy(self) -> Optional[str]:
        if not self.cfg.proxies:
            return None
        attempts, max_attempts = 0, len(self.cfg.proxies)
        while attempts < max_attempts:
            p = self.cfg.proxies[self._proxy_idx % len(self.cfg.proxies)]
            self._proxy_idx += 1
            if p not in self._failed_proxies:
                return p
            attempts += 1
        self._failed_proxies.clear()
        self._proxy_idx = 0
        return self.cfg.proxies[0] if self.cfg.proxies else None

    def _mark_proxy_failed(self, proxy: Optional[str]):
        if proxy:
            self._failed_proxies.add(proxy)
