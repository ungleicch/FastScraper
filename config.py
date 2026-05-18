from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ScraperConfig:
    # ── Target ──────────────────────────────────────────────
    base_url: str = "https://example.com"

    # ── Output ──────────────────────────────────────────────
    output_dir: str = "./scraped_output"
    save_html: bool = True
    save_text: bool = True

    # ── Media Filters ───────────────────────────────────────
    dl_images: bool = True
    dl_videos: bool = True
    dl_gifs: bool = True

    # ── Performance ─────────────────────────────────────────
    max_concurrent: int = 50  # simultaneous HTTP requests
    max_pages: int = 1000
    max_depth: int = 4
    request_timeout: int = 15  # seconds
    connect_timeout: int = 5

    # ── Crawl behaviour ─────────────────────────────────────
    same_domain_only: bool = True
    allowed_extensions: List[str] = field(
        default_factory=lambda: ["", ".html", ".htm", ".php", ".asp", ".aspx"]
    )
    exclude_patterns: List[str] = field(
        default_factory=lambda: ["logout", "signout", "delete", "remove"]
    )

    # ── Proxies ─────────────────────────────────────────────
    proxies: List[str] = field(default_factory=list)

    # ── Rate limiting ───────────────────────────────────────
    delay_between_requests: float = 0.0  # seconds; set >0 to throttle
    respect_robots_txt: bool = True

    # ── User-agent rotation ──────────────────────────────────
    user_agents: List[str] = field(
        default_factory=lambda: [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Edge/124.0.0.0",
        ]
    )
