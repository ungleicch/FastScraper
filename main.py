#!/usr/bin/env python3
import argparse
import asyncio
import sys
from urllib.parse import urlparse

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    UVLOOP = True
except ImportError:
    UVLOOP = False

from rich.console import Console

from config import ScraperConfig
from crawler import Crawler

console = Console()


def build_config(args) -> ScraperConfig:
    cfg = ScraperConfig(base_url=args.url)
    cfg.max_concurrent = args.threads
    cfg.max_depth = args.depth
    cfg.max_pages = args.pages
    if args.output and args.output != "./scraped_output":
        cfg.output_dir = args.output
    else:
        domain = urlparse(args.url).netloc or "site"
        cfg.output_dir = f"./scraped_output/{domain}"

    cfg.save_html = not args.no_html
    cfg.save_text = not args.no_text

    cfg.dl_images = not args.no_images
    cfg.dl_videos = not args.no_videos
    cfg.dl_gifs = not args.no_gifs

    cfg.delay_between_requests = args.delay
    cfg.respect_robots_txt = not args.ignore_robots
    if args.proxy:
        cfg.proxies = [args.proxy]
    if args.proxy_list:
        try:
            with open(args.proxy_list) as f:
                cfg.proxies = [line.strip() for line in f if line.strip()]
            console.print(
                f"  [dim]Loaded {len(cfg.proxies)} proxies from {args.proxy_list}[/dim]"
            )
        except FileNotFoundError:
            console.print(f"[red]Proxy list file not found: {args.proxy_list}[/red]")
            sys.exit(1)
    return cfg


def main():
    parser = argparse.ArgumentParser(
        description="FastScraper – async parallel web scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", help="Starting URL to crawl")
    parser.add_argument("--threads", type=int, default=50, help="Concurrent requests")
    parser.add_argument("--depth", type=int, default=3, help="Max crawl depth")
    parser.add_argument("--pages", type=int, default=500, help="Max pages to crawl")
    parser.add_argument("--output", default="./scraped_output", help="Output directory")
    parser.add_argument(
        "--delay", type=float, default=0.0, help="Delay between requests"
    )
    parser.add_argument("--proxy", default=None, help="Single proxy URL")
    parser.add_argument(
        "--proxy-list", default=None, help="Path to proxy list txt file"
    )

    parser.add_argument("--no-html", action="store_true", help="Skip saving HTML")
    parser.add_argument("--no-text", action="store_true", help="Skip saving text")
    parser.add_argument(
        "--no-images", action="store_true", help="Skip downloading Images"
    )
    parser.add_argument(
        "--no-videos", action="store_true", help="Skip downloading Videos"
    )
    parser.add_argument("--no-gifs", action="store_true", help="Skip downloading GIFs")

    parser.add_argument(
        "--ignore-robots", action="store_true", help="Ignore robots.txt"
    )

    args = parser.parse_args()
    cfg = build_config(args)

    if UVLOOP:
        console.print("  [dim]Using uvloop (fast C event loop)[/dim]")

    queue = asyncio.Queue()
    asyncio.run(Crawler(cfg, queue).run())


if __name__ == "__main__":
    main()
