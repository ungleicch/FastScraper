from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import aiofiles

SAFE_CHARS_RE = re.compile(r"[^\w._-]")


def safe_filename(url: str, max_len: int = 180) -> str:
    parsed = urlparse(url)
    name = (parsed.netloc + parsed.path).replace("/", "_")
    name = SAFE_CHARS_RE.sub("_", name)
    return name[:max_len] or "index"


class OutputManager:
    def __init__(self, output_dir: str):
        self.root = Path(output_dir)
        self.html = self.root / "html"
        self.text = self.root / "text"
        self.media = self.root / "media"
        self.data = self.root / "data"
        for d in (self.html, self.text, self.media, self.data):
            d.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def save_html(self, url: str, content: bytes) -> None:
        name = safe_filename(url) + ".html"
        async with aiofiles.open(self.html / name, "wb") as f:
            await f.write(content)

    async def save_text(self, url: str, text: str) -> None:
        name = safe_filename(url) + ".txt"
        async with aiofiles.open(self.text / name, "w", encoding="utf-8") as f:
            await f.write(f"URL: {url}\n{'=' * 60}\n{text}\n")

    async def save_media(self, url: str, data: bytes) -> str:
        ext = Path(urlparse(url).path).suffix or ".bin"
        name = safe_filename(url) + ext
        path = self.media / name
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return str(path)

    async def write_report(self, results: List[Dict[str, Any]], stats: Dict) -> None:
        async with aiofiles.open(self.data / "results.json", "w") as f:
            await f.write(json.dumps(results, indent=2, default=str))

        ok = sum(1 for r in results if r.get("success"))
        fail = len(results) - ok
        elapsed = stats.get("elapsed", 0)
        throughput = ok / max(elapsed, 0.001)

        lines = [
            "=" * 60,
            "  CRAWL REPORT",
            "=" * 60,
            f"  Base URL   : {stats.get('base_url')}",
            f"  Pages OK   : {ok}",
            f"  Pages fail : {fail}",
            f"  Media Files: {stats.get('media', 0)}",
            f"  Elapsed    : {elapsed:.1f}s",
            f"  Throughput : {throughput:.1f} pages/s",
            "=" * 60,
            "",
            "PAGES:",
        ]
        for r in results:
            status = "✓" if r.get("success") else "✗"
            lines.append(
                f"  [{status}] {r.get('status', 0):3d}  {r.get('response_ms', 0):5d}ms  {r.get('url', '')}"
            )
            if not r.get("success") and r.get("error"):
                lines.append(f"       Error: {r['error']}")

        async with aiofiles.open(self.root / "report.txt", "w") as f:
            await f.write("\n".join(lines) + "\n")
