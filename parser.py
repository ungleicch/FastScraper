from __future__ import annotations

import re
from typing import List, Tuple
from urllib.parse import urldefrag, urljoin, urlparse

from lxml import html as lxml_html
from lxml.etree import ParserError, XPath

CLEAN_XPATH = XPath("//script|//style|//noscript|//head/meta|//head/link")
LINKS_XPATH = XPath("//a[@href]")
MEDIA_XPATH = XPath("//img | //video | //source")
SRCSET_XPATH = XPath("//*[@srcset]")


def normalize_url(href: str, base_url: str) -> str:
    href = href.strip()
    parsed = urlparse(href)
    if parsed.scheme in ("http", "https"):
        url, _ = urldefrag(href)
        return url
    url, _ = urldefrag(urljoin(base_url, href))
    return url


def same_domain(url: str, base_host: str) -> bool:
    host = urlparse(url).netloc.lstrip("www.")
    base = base_host.lstrip("www.")
    return host == base or host.endswith("." + base)


def url_extension(url: str) -> str:
    path = urlparse(url).path
    dot = path.rfind(".")
    return path[dot:].lower() if dot != -1 else ""


def parse_page(raw_html: bytes, page_url: str) -> Tuple[str, List[str], List[str]]:
    try:
        doc = lxml_html.fromstring(raw_html)
    except (ParserError, ValueError):
        return "", [], []

    for tag in CLEAN_XPATH(doc):
        tag.getparent().remove(tag)

    body = doc.find("body")
    text = ""
    if body is not None:
        text = " ".join(body.text_content().split())

    links: List[str] = []
    for el in LINKS_XPATH(doc):
        href = el.get("href", "").strip()
        if href and not href.startswith(("javascript:", "mailto:", "tel:", "#")):
            links.append(normalize_url(href, page_url))

    media: List[str] = []
    for el in MEDIA_XPATH(doc):
        for attr in ("src", "data-src", "poster"):
            val = el.get(attr)
            if val:
                media.append(normalize_url(val, page_url))

    for el in SRCSET_XPATH(doc):
        for part in el.get("srcset", "").split(","):
            src = part.strip().split()[0]
            if src:
                media.append(normalize_url(src, page_url))

    return text, list(dict.fromkeys(links)), list(dict.fromkeys(media))
