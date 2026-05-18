# Core HTTP and Async Data handling
aiohttp>=3.9
aiofiles>=23.0

# Ultra-fast C-backed HTML parsing
lxml>=5.0

# Web Server & GUI WebSockets
fastapi>=0.100
uvicorn>=0.22
pydantic>=2.0

# CLI and Styling tools
rich>=13.0
tqdm>=4.66

# C-Level Network & Event Loop Optimizations
aiodns>=3.1         # C-Ares DNS bindings for ultra-fast multi-domain lookups
uvloop>=0.19        # Fast C event loop (Note: Linux/macOS only; Windows falls back to default asyncio loop natively)
--- END OF FILE requirements.txt ---

README.md

--- START OF FILE README.md ---
# ⚡ FastScraper

FastScraper is a high-performance, fully asynchronous web crawler and media downloader built in Python. 

By leveraging native C-extensions (`uvloop`, `aiodns`, `lxml`), strict memory-efficient worker pools, and asynchronous network I/O, FastScraper is capable of mapping and scraping thousands of pages in seconds while idling at near 0% CPU.

It comes with a **Beautiful Real-Time Web GUI** (driven by WebSockets) and a robust **Headless CLI**.

## ✨ Features

* **3-Phase Execution Pipeline:**
  * **Phase 1 (BFS Mapping):** Breadth-First Search site traversal to map all target URLs.
  * **Phase 2 (Parallel Fetch):** Concurrent HTML downloading and text extraction.
  * **Phase 3 (Media Download):** Parallel, automatically deduplicated downloading of Images, Videos, and GIFs.
* **C-Level Optimizations:** 
  * Uses `aiodns` (c-ares) for zero-latency multi-domain DNS resolution.
  * Uses `lxml` with precompiled C-level XPaths for instant HTML node extraction.
  * Replaces Python's default event loop with `uvloop` (the C engine behind Node.js).
* **Smart Media Filtering:** Granular toggles to download or ignore `.jpg/.png`, `.mp4/.webm`, and `.gif`.
* **Built-in Auto Proxy Discovery:** Uses an extreme-concurrency async race against Google's `204 No Content` edge servers to discover and validate public proxies in milliseconds.
* **Zero-Spike Worker Pools:** Uses bounded `asyncio.Queue` worker pools instead of dynamic task spawning to completely eliminate RAM exhaustion on massive websites.

---

## 🚀 Installation

1. Clone this repository or download the source files.
2. Ensure you have Python 3.9+ installed.
3. Install the dependencies:

```bash
pip install -r requirements.txt

(Note for Windows users: uvloop is only available for Linux/macOS. If you are on
Windows, FastScraper will automatically detect this and safely fall back to the
default Windows ProactorEventLoop).

🖥️ Web GUI Mode (Recommended)

FastScraper features a completely local, WebSocket-driven dashboard with
real-time throughput charts, status distributions, and live URL feeds.

To launch the GUI, simply run the server:

python server.py

  - The server runs on http://localhost:8765.
  - A browser window will open automatically.
  - You can configure threads, URLs, proxy discovery, and media toggles directly
    from the sidebar.

💻 CLI Mode (Headless)

If you prefer the terminal or want to run FastScraper on a remote server, use
main.py.

Basic crawl:

python main.py https://example.com

Advanced crawl (100 concurrent threads, max depth 5, 2000 pages):

python main.py https://example.com --threads 100 --depth 5 --pages 2000

Media & Output control:

python main.py https://example.com --no-videos --no-gifs --output ./my_custom_folder

Proxy usage:

# Using a single proxy
python main.py https://example.com --proxy http://user:pass@host:port

# Using a list of proxies from a text file
python main.py https://example.com --proxy-list proxies.txt

Full CLI Options

| Argument          | Description                                 | Default                     |
| ----------------- | ------------------------------------------- | --------------------------- |
| `url`             | Starting URL to crawl                       | *(Required)*                |
| `--threads`       | Number of concurrent network connections    | `50`                        |
| `--depth`         | Maximum BFS depth to traverse               | `3`                         |
| `--pages`         | Maximum total pages to crawl                | `500`                       |
| `--output`        | Output directory                            | `./scraped_output/<domain>` |
| `--delay`         | Politeness delay (seconds) between requests | `0.0`                       |
| `--no-html`       | Skip saving `.html` source code             | `False`                     |
| `--no-text`       | Skip saving extracted plaintext             | `False`                     |
| `--no-images`     | Skip downloading Images                     | `False`                     |
| `--no-videos`     | Skip downloading Videos                     | `False`                     |
| `--no-gifs`       | Skip downloading GIFs                       | `False`                     |
| `--ignore-robots` | Do not check `robots.txt` rules             | `False`                     |

📁 Output Structure

By default, FastScraper creates an organized directory based on the target
website's domain:

./scraped_output/
└── example.com/
    ├── html/          # Raw HTML source of every page
    ├── text/          # Clean, noise-free text extracted via lxml
    ├── media/         # All deduplicated images, videos, and GIFs
    ├── data/
    │   └── results.json  # Complete programmatic JSON dump of the crawl
    └── report.txt     # Human-readable summary and error log



