#!/usr/bin/env python3
"""Offline network-mocked contract tests for Wolfram Public Beetle integration."""
import json
import tempfile
import unittest
from pathlib import Path

from wolfram_public_sources import FEED_URL, REPO_URL, parse_feed, parse_repo, discover
from wolfram_mcp_one_shot import MCPHold, CASES, MCP_ENDPOINT, one_shot
from universal_beetle import Budget, State, scout_wolfram_public, scout_wolfram_mcp_once


class FakeResponse:
    def __init__(self, url, body, status=200, content_type="application/json", sid=None):
        self.url = url
        self.body = body
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        if sid:
            self.headers["Mcp-Session-Id"] = sid
        self.closed = False
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    def close(self): self.closed = True
    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i:i+chunk_size]


class FakeSession:
    def __init__(self, *, feed_override=None, repo_override=None, schema=None):
        self.posts = []
        self.gets = []
        self.schema = schema or {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
        self.feed_override = feed_override
        self.repo_override = repo_override
    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        if url == FEED_URL:
            body = self.feed_override or b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Wolfram Blog</title>
<item><title>Quantum Measurement and Simulation with Wolfram</title>
<link>https://blog.wolfram.com/2026/11/quantum-measurement/</link>
<pubDate>Mon, 09 Nov 2026 12:00:00 +0000</pubDate>
<description>SAMPLE_NOT_TO_COPY_FROM_PROVIDER</description></item></channel></rss>"""
        elif url == REPO_URL:
            body = self.repo_override or json.dumps({
                "full_name": "WolframResearch/QuantumFramework",
                "owner": {"login": "WolframResearch"},
                "private": False,
                "license": {"spdx_id": "MIT"},
                "html_url": "https://github.com/WolframResearch/QuantumFramework",
                "pushed_at": "2026-11-09T00:00:00Z",
            }).encode()
        else:
            raise AssertionError("OUTSIDE_FIXED_SOURCE_ALLOWLIST")
        return FakeResponse(url, body)
    def post(self, url, headers, json, **kwargs):
        self.posts.append((url, headers, json))
        if url != MCP_ENDPOINT:
            raise AssertionError("MCP_NOT_OFFICIAL_HOST")
        method = json["method"]
        if method == "initialize":
            return FakeResponse(url, __import__("json").dumps({
                "jsonrpc": "2.0", "id": 1,
                "result": {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": {"name":"fake","version":"0"}}
            }).encode(), sid="TESTSESSION")
        if method == "notifications/initialized":
            return FakeResponse(url, b"", status=202)
        if method == "tools/list":
            return FakeResponse(url, __import__("json").dumps({
                "jsonrpc": "2.0", "id": 2, "result": {
                    "tools": [{"name":"WolframAlpha","inputSchema":self.schema}]}
            }).encode())
        if method == "tools/call":
            assert json["params"]["name"] == "WolframAlpha"
            assert json["params"]["arguments"] == {"query": CASES["zeno_n2_analytic"]["query"]}
            return FakeResponse(url, __import__("json").dumps({
                "jsonrpc":"2.0","id":3,"result":{"isError":False,
                "content":[{"type":"text","text":"PROVIDER_OUTPUT_FAKE_NO_COPY"}]}
            }).encode())
        raise AssertionError("UNEXPECTED_MCP_METHOD")


class WolframTest(unittest.TestCase):
    def test_feed_titles_not_bodies(self):
        s = FakeSession()
        obj = s.get(FEED_URL).body
        rows = parse_feed(obj)
        self.assertEqual(len(rows),1)
        self.assertIn("Quantum Measurement",rows[0]["title"])
        self.assertNotIn("SAMPLE_NOT_TO_COPY_FROM_PROVIDER",json.dumps(rows))
        self.assertTrue(rows[0]["url"].startswith("https://blog.wolfram.com/"))

    def test_repo_requires_verified_mit_and_identity(self):
        s=FakeSession()
        rows=parse_repo(s.get(REPO_URL).body)
        self.assertEqual(rows[0]["license"],"MIT")
        self.assertFalse(rows[0]["full_repository_source_downloaded"])
        invalid=__import__("json").loads(s.get(REPO_URL).body)
        invalid["license"]["spdx_id"]="Unknown"
        with self.assertRaises(ValueError):
            parse_repo(__import__("json").dumps(invalid).encode())

    def test_mcp_no_credentials_and_only_digest(self):
        fake=FakeSession()
        b=[]
        report=one_shot("zeno_n2_analytic",fake,note_request=b.append)
        self.assertEqual(report["status"],"LIVE_MCP_TOOL_RESPONSE_RECEIVED")
        self.assertEqual(len(fake.posts),4)
        self.assertEqual(len(b),4)
        self.assertFalse(report["provider_math_answer_verified"])
        self.assertFalse(report["provider_response_cached"])
        self.assertFalse(report["api_appid_or_login_used"])
        self.assertNotIn("PROVIDER_OUTPUT_FAKE_NO_COPY",__import__("json").dumps(report))
        for url,headers,body in fake.posts:
            self.assertNotIn("Authorization",headers)
            self.assertEqual(url,MCP_ENDPOINT)
        self.assertEqual(fake.posts[-1][2]["params"]["arguments"],
                         {"query":"cos(pi/4)^4"})

    def test_mcp_rejects_arbitrary_query_and_schema(self):
        with self.assertRaisesRegex(MCPHold,"UNAPPROVED_RESEARCH_QUERY"):
            one_shot("predict_2040",FakeSession())
        fake=FakeSession(schema={"type":"object",
                                 "properties":{"code":{"type":"string"}},
                                 "required":["code"]})
        with self.assertRaisesRegex(MCPHold,"TOOL_SCHEMA_NOT_ALLOWED"):
            one_shot("zeno_n2_analytic",fake)

    def test_beetle_public_metadata_persist_deduplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=State(Path(tmp))
            budget=Budget(max_requests=10,max_new_items=8)
            direction={"id":"wolfram_public_quantum","title":"Wolfram Quantum",
                       "keywords":["wolfram","quantum"],
                       "priority_keywords":["quantum"],"min_score":1}
            sess=FakeSession()
            scout_wolfram_public(sess,state,budget,direction,{"kind":"wolfram_public_feed","max_results":3})
            scout_wolfram_public(sess,state,budget,direction,{"kind":"wolfram_public_repo","max_results":1})
            self.assertEqual(budget.requests,2)
            self.assertEqual(budget.new_items,2)
            self.assertEqual(len(state.seen),2)
            scout_wolfram_public(sess,state,budget,direction,{"kind":"wolfram_public_repo","max_results":1})
            self.assertEqual(budget.new_items,2)
            self.assertTrue(all(x["source"].startswith("wolfram_research") for x in state.seen.values()))

    def test_beetle_one_mcp_call_then_forever_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=State(Path(tmp))
            budget=Budget(max_requests=10,max_new_items=8)
            direction={"id":"wolfram_public_quantum","title":"Wolfram Quantum",
                       "keywords":["wolfram","quantum"],"priority_keywords":["quantum"],"min_score":1}
            sess=FakeSession()
            cfg={"kind":"wolfram_mcp_once","case":"zeno_n2_analytic"}
            scout_wolfram_mcp_once(sess,state,budget,direction,cfg)
            self.assertEqual(len(sess.posts),4)
            self.assertEqual(budget.requests,4)
            self.assertEqual(budget.new_items,1)
            scout_wolfram_mcp_once(sess,state,budget,direction,cfg)
            self.assertEqual(len(sess.posts),4)
            self.assertEqual(budget.new_items,1)
            self.assertIn("wolfram_mcp_once:zeno_n2_analytic:last_attempt",state.cursors)
            state.save()
            self.assertEqual(len(State(Path(tmp)).seen),1)

    def test_wrong_source_never_fetched(self):
        sess=FakeSession()
        with self.assertRaises(ValueError):
            discover("wolframalpha_site_scraper",b"not allowed")
        self.assertFalse(sess.posts)
        self.assertFalse(sess.gets)


if __name__=="__main__":
    unittest.main(verbosity=2)
