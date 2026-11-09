"""Strictly public Wolfram Research metadata scout for JANUS Universal Beetle.

NOT a Wolfram|Alpha query client. Its webpage prohibits robotic querying;
the Wolfram Alpha API requires an AppID. Read only intentional public RSS
and a verified, MIT-licensed open GitHub repository; record short metadata
and links only, never copy article bodies or train model on provider output.
"""
from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

FEED_URL = "https://blog.wolfram.com/feed/"
REPO_URL = "https://api.github.com/repos/WolframResearch/QuantumFramework"
FEED_MAX_BYTES = 262_144
REPO_MAX_BYTES = 65_536
KEYWORDS = (
    "quantum", "physics", "time", "mathemat", "computation",
    "probabil", "measurement", "wolfram", "simulation", "entangle",
)


def validate_final_url(requested: str, final: str) -> None:
    a, b = urllib.parse.urlsplit(requested), urllib.parse.urlsplit(final)
    if a.scheme != "https" or b.scheme != "https" or (a.hostname, a.path) != (b.hostname, b.path):
        raise ValueError("WOLFRAM_PUBLIC_SOURCE_REDIRECT_REFUSED")


def parse_feed(content: bytes, max_results: int = 3) -> list[dict[str, Any]]:
    if len(content) > FEED_MAX_BYTES:
        raise ValueError("WOLFRAM_FEED_OVERSIZE")
    if not 1 <= max_results <= 5:
        raise ValueError("WOLFRAM_FEED_RESULT_LIMIT")
    root = ET.fromstring(content)
    if root.tag not in ("rss", "feed", "{http://www.w3.org/2005/Atom}feed"):
        raise ValueError("WOLFRAM_UNEXPECTED_FEED")
    items = []
    for e in root.findall(".//item")[:15]:
        title = re.sub(r"\s+", " ", e.findtext("title") or "").strip()[:240]
        link = (e.findtext("link") or "").strip()
        if link.startswith("http://blog.wolfram.com/"):
            link = "https://" + link[7:]
        u = urllib.parse.urlsplit(link)
        if u.scheme != "https" or u.hostname != "blog.wolfram.com" or not title:
            continue
        if not any(word in title.casefold() for word in KEYWORDS):
            continue
        items.append({
            "source": "wolfram_research_official_rss",
            "url": link,
            "title": title,
            "summary": "Official Wolfram Research blog article metadata (no copied body)",
            "published": (e.findtext("pubDate") or "")[:80],
            "tags": ["research", "official-wolfram", "public-rss"],
            "license": "LINK_AND_METADATA_ONLY",
            "provider_is_wolfram_alpha_api": False,
        })
        if len(items) >= max_results:
            return items
    return items


def parse_repo(content: bytes) -> list[dict[str, Any]]:
    if len(content) > REPO_MAX_BYTES:
        raise ValueError("WOLFRAM_REPO_METADATA_OVERSIZE")
    import json
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("WOLFRAM_BAD_REPO_METADATA")
    repo = str(data.get("full_name", ""))
    owner = data.get("owner", {})
    if repo.casefold() != "wolframresearch/quantumframework" or str(owner.get("login", "")).casefold() != "wolframresearch":
        raise ValueError("WOLFRAM_UNTRUSTED_REPO")
    if data.get("private") is not False or data.get("license", {}).get("spdx_id") != "MIT":
        raise ValueError("WOLFRAM_REPO_LICENSE_NOT_CONFIRMED")
    if data.get("html_url", "").lower() != "https://github.com/wolframresearch/quantumframework":
        raise ValueError("WOLFRAM_REPO_URL_MISMATCH")
    return [{
        "source": "wolfram_research_official_github",
        "url": "https://github.com/WolframResearch/QuantumFramework",
        "title": "WolframResearch/QuantumFramework — quantum computation framework",
        "summary": "Verified public MIT project metadata; symbolic quantum operations, measurements, and simulations",
        "updated": str(data.get("pushed_at", ""))[:40],
        "tags": ["quantum", "wolfram", "measurement", "simulation"],
        "license": "MIT",
        "provider_is_wolfram_alpha_api": False,
        "full_repository_source_downloaded": False,
    }]


def discover(kind: str, response_body: bytes, max_results: int = 3) -> list[dict[str, Any]]:
    if kind == "wolfram_public_feed":
        return parse_feed(response_body, max_results)
    if kind == "wolfram_public_repo":
        return parse_repo(response_body)
    raise ValueError("UNAPPROVED_WOLFRAM_SOURCE_KIND")
