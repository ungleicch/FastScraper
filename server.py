from __future__ import annotations

import asyncio
import json
from typing import List, Optional
from urllib.parse import urlparse

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from config import ScraperConfig
from crawler import Crawler
from proxy import discover_proxies

app = FastAPI(title="FastScraper")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", encoding="utf-8") as f:
        return f.read()


_crawler: Optional[Crawler] = None
_task: Optional[asyncio.Task] = None
_queue: asyncio.Queue = asyncio.Queue()
_clients: set[WebSocket] = set()
_discover_task: Optional[asyncio.Task] = None
_last_discovered_proxies: List[str] = []


class StartRequest(BaseModel):
    url: str
    threads: int = 50
    depth: int = 3
    max_pages: int = 500
    delay: float = 0.0
    proxy: str = ""

    # Updated Media Configs
    dl_images: bool = True
    dl_videos: bool = True
    dl_gifs: bool = True

    save_html: bool = True
    save_text: bool = True
    ignore_robots: bool = False
    output_dir: str = "./scraped_output"


@app.post("/start")
async def start_crawl(req: StartRequest):
    global _crawler, _task, _queue

    if _task and not _task.done():
        return JSONResponse({"error": "A crawl is already running"}, status_code=400)

    out_dir = req.output_dir or "./scraped_output"
    if not out_dir.strip() or out_dir.strip() == "./scraped_output":
        domain = urlparse(req.url).netloc or "site"
        out_dir = f"./scraped_output/{domain}"

    proxy_list = []
    if req.proxy and req.proxy.strip():
        proxy_list = [p.strip() for p in req.proxy.split(",") if p.strip()]

    cfg = ScraperConfig(
        base_url=req.url,
        max_concurrent=req.threads,
        max_depth=req.depth,
        max_pages=req.max_pages,
        delay_between_requests=req.delay,
        dl_images=req.dl_images,
        dl_videos=req.dl_videos,
        dl_gifs=req.dl_gifs,
        save_html=req.save_html,
        save_text=req.save_text,
        respect_robots_txt=not req.ignore_robots,
        output_dir=out_dir,
        proxies=proxy_list,
    )

    _queue = asyncio.Queue()
    _crawler = Crawler(cfg, _queue)
    _task = asyncio.create_task(_run_and_broadcast())
    return {"status": "started"}


@app.post("/discover")
async def start_discover_proxies():
    global _discover_task, _last_discovered_proxies
    if _discover_task and not _discover_task.done():
        return {"status": "running"}

    async def _bg():
        try:
            proxies = await discover_proxies(limit=20, timeout=3, fetch_timeout=5)
            _last_discovered_proxies[:] = proxies
        except Exception:
            _last_discovered_proxies[:] = []

    _discover_task = asyncio.create_task(_bg())
    return {"status": "started"}


@app.get("/discover/status")
async def discover_proxies_status():
    return {
        "running": bool(_discover_task and not _discover_task.done()),
        "proxies": _last_discovered_proxies,
    }


@app.post("/stop")
async def stop_crawl():
    global _crawler
    if _crawler:
        _crawler.stop()
    return {"status": "stopping"}


async def _run_and_broadcast():
    global _crawler, _queue
    crawl_task = asyncio.create_task(_crawler.run())

    async def fan_out():
        while True:
            msg = await _queue.get()
            if msg is None:
                break
            dead = set()
            for ws in list(_clients):
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.add(ws)
            _clients.difference_update(dead)

    await asyncio.gather(crawl_task, fan_out())


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _clients.discard(ws)
    except Exception:
        _clients.discard(ws)


if __name__ == "__main__":
    import threading
    import time
    import webbrowser

    import uvicorn

    def _open():
        time.sleep(1.2)
        webbrowser.open("http://localhost:8765")

    threading.Thread(target=_open, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="warning")
