"""Wolfram public metadata Beetle: no credentials, no Wolfram Alpha scraping."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import universal_beetle as beetle
import wolfram_public_sources as source


FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Wolfram Blog</title>
<item><title>Quantum Simulation and Measurement in Practice</title>
<link>https://blog.wolfram.com/2026/11/09/quantum-simulation/</link>
<pubDate>Mon, 09 Nov 2026 10:00:00 +0000</pubDate>
<description>Long article that must NOT be stored or copied</description></item>
<item><title>Gardening stories from another host</title>
<link>https://untrusted.example/redirect</link></item>
</channel></rss>"""


def github_data():
    return {
        "full_name": "WolframResearch/QuantumFramework",
        "owner": {"login": "WolframResearch"},
        "private": False,
        "license": {"spdx_id": "MIT"},
        "html_url": "https://github.com/WolframResearch/QuantumFramework",
        "pushed_at": "2026-11-09T10:00:00Z",
        "description": "Public metadata only",
    }


class FakeResponse:
    def __init__(self, data, url):
        self.content = data
        self.url = url
    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self):
        self.requests = []
    def get(self, url, timeout=None, **kwargs):
        self.requests.append((url, kwargs))
        if url == source.FEED_URL:
            return FakeResponse(FEED, url)
        if url == source.REPO_URL:
            return FakeResponse(json.dumps(github_data()).encode(), url)
        raise AssertionError(f"Forbidden network target: {url}")


class WolframOpenTests(unittest.TestCase):
    def test_official_feed_only_short_metadata(self):
        rows = source.parse_feed(FEED)
        self.assertEqual(len(rows), 1)
        self.assertIn("quantum", rows[0]["title"].lower())
        self.assertNotIn("Long article that must NOT", json.dumps(rows))
        self.assertFalse(rows[0]["provider_is_wolfram_alpha_api"])

    def test_verified_open_repo_license(self):
        rows = source.parse_repo(json.dumps(github_data()).encode())
        self.assertEqual(rows[0]["license"], "MIT")
        self.assertFalse(rows[0]["full_repository_source_downloaded"])
        r = github_data()
        r["license"]["spdx_id"] = "NOASSERTION"
        with self.assertRaisesRegex(ValueError, "LICENSE"):
            source.parse_repo(json.dumps(r).encode())

    def test_lookalike_owner_and_external_urls_rejected(self):
        r = github_data()
        r["owner"]["login"] = "WolframResearcH-fake"
        with self.assertRaises(ValueError):
            source.parse_repo(json.dumps(r).encode())
        with self.assertRaisesRegex(ValueError, "REDIRECT_REFUSED"):
            source.validate_final_url(source.FEED_URL, "https://wolframalpha.com/input?i=secret")
        with self.assertRaisesRegex(ValueError, "UNAPPROVED"):
            source.discover("wolframalpha_html_scraper", b"")

    def test_limits_protect_against_bulk_collection(self):
        with self.assertRaises(ValueError):
            source.parse_feed(b"x" * (source.FEED_MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            source.parse_feed(FEED, 99)
        with self.assertRaises(ValueError):
            source.parse_repo(b"x" * (source.REPO_MAX_BYTES + 1))

    def test_real_beetle_receipt_uses_same_deduped_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = beetle.State(Path(tmp))
            budget = beetle.Budget(max_requests=2, max_new_items=5)
            sess = FakeSession()
            direction = {
                "id": "wolfram_official_open_quantum::FORWARD",
                "title": "Wolfram public metadata",
                "keywords": ["quantum", "simulation", "measurement"],
                "priority_keywords": ["wolfram"],
                "min_score": 1,
            }
            beetle.scout_wolfram_public(sess, state, budget, direction,
                {"kind": "wolfram_public_feed", "max_results": 3})
            beetle.scout_wolfram_public(sess, state, budget, direction,
                {"kind": "wolfram_public_repo", "max_results": 1})
            self.assertEqual(budget.requests, 2)
            self.assertEqual(budget.new_items, 2)
            self.assertEqual(len(state.seen), 2)
            self.assertTrue(all(url in (source.FEED_URL, source.REPO_URL)
                                for url, _ in sess.requests))
            self.assertTrue(all(kwargs.get("allow_redirects") is False
                                for _, kwargs in sess.requests))
            self.assertNotIn("wolframalpha.com", json.dumps(state.seen).lower())

    def test_budget_exhaustion_fails_before_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = beetle.State(Path(tmp))
            budget = beetle.Budget(max_requests=0)
            sess = FakeSession()
            with self.assertRaisesRegex(RuntimeError, "budget"):
                beetle.scout_wolfram_public(sess, state, budget, {
                    "id": "wolfram", "keywords": ["quantum"],
                    "priority_keywords": [], "min_score": 1
                }, {"kind": "wolfram_public_feed"})
            self.assertEqual(sess.requests, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
