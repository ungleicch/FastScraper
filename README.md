# ⚡ FastScraper

A fast, asynchronous web crawler and media downloader built in Python.

I made this because I got tired of slow scrapers that eat all your RAM and take forever. FastScraper uses proper async I/O and C-level libraries so it can rip through thousands of pages quickly while staying lightweight.

## ✨ Features

- 3-phase pipeline: BFS mapping → Parallel HTML fetching → Smart media downloading
- Blazing fast parsing with lxml + precompiled XPath
- Ultra-fast DNS with aiodns (c-ares)
- uvloop for maximum speed (auto-falls back on Windows)
- Real-time Web GUI with live stats and charts
- Clean CLI for headless use
- Built-in proxy discovery
- Bounded workers so it doesn't blow up your memory
- Granular control over images, videos, and GIFs

## 🚀 Quick Start

```bash
git clone https://github.com/ungleicch/FastScraper.git
cd FastScraper
pip install -r requirements.txt
```

### Web GUI (Recommended)

```bash
python server.py
```

Then open http://localhost:8765 in your browser.

### CLI Usage

```bash
# Basic crawl
python main.py https://example.com

# More power
python main.py https://example.com --threads 80 --depth 4 --pages 1500 --no-videos
```

## 📋 All CLI Options

| Argument          | Description                            | Default                     |
|-------------------|----------------------------------------|-----------------------------|
| `url`             | Starting URL                           | Required                    |
| `--threads`       | Concurrent connections                 | 50                          |
| `--depth`         | Max crawl depth                        | 3                           |
| `--pages`         | Max pages to scrape                    | 500                         |
| `--output`        | Output folder                          | `./scraped_output/<domain>` |
| `--delay`         | Delay between requests (seconds)       | 0.0                         |
| `--no-html`       | Don't save HTML files                  | False                       |
| `--no-text`       | Don't save extracted text              | False                       |
| `--no-images`     | Skip images                            | False                       |
| `--no-videos`     | Skip videos                            | False                       |
| `--no-gifs`       | Skip GIFs                              | False                       |
| `--ignore-robots` | Ignore robots.txt                      | False                       |
| `--proxy`         | Use single proxy                       | -                           |
| `--proxy-list`    | Text file with proxies (one per line)  | -                           |
