"""JANUS Beetle keyless Wolfram Cloud MCP bounded one-shot protocol tests."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import universal_beetle as beetle
import wolfram_mcp_one_shot as mcp


class R:
    def __init__(self, msg, code=200):
        self.status_code=code
        self.headers={"Content-Type":"application/json","Mcp-Session-Id":"MOCK-SESSION"}
        self.url=mcp.MCP_ENDPOINT
        self.body=json.dumps(msg).encode() if msg else b""
    def iter_content(self, chunk_size=8192):
        for start in range(0,len(self.body),chunk_size):
            yield self.body[start:start+chunk_size]
    def close(self):
        pass


class Session:
    def __init__(self):
        self.calls=[]
    def post(self, url, *, json=None, headers=None, **kwargs):
        self.calls.append({"url":url,"payload":json,"headers":headers,"kwargs":kwargs})
        method=json["method"]
        if method=="initialize":
            return R({"jsonrpc":"2.0","id":1,"result":{"protocolVersion":mcp.PROTOCOL,"capabilities":{},"serverInfo":{"name":"Wolfram"}}})
        if method=="notifications/initialized":
            return R(None,202)
        if method=="tools/list":
            return R({"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"WolframAlpha","inputSchema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}]}})
        if method=="tools/call":
            return R({"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"0.25"}],"isError":False}})
        raise AssertionError(method)


class FailingSession(Session):
    def post(self,url,**kwargs):
        self.calls.append({"url":url,**kwargs})
        raise ConnectionError("simulated network outage")


class Tests(unittest.TestCase):
    def test_one_shot_no_credentials_or_provider_body_retained(self):
        s=Session()
        req_bytes=[]
        receipt=mcp.one_shot("zeno_n2_analytic",s,note_request=req_bytes.append)
        self.assertEqual(len(s.calls),4)
        self.assertEqual(len(req_bytes),4)
        self.assertEqual(receipt["status"],"LIVE_MCP_TOOL_RESPONSE_RECEIVED")
        self.assertFalse(receipt["provider_response_cached"])
        self.assertFalse(receipt["provider_math_answer_verified"])
        self.assertNotIn("0.25",json.dumps(receipt["provider_content_part_count"]))
        self.assertTrue(all(call["url"]==mcp.MCP_ENDPOINT for call in s.calls))
        self.assertTrue(all("Authorization" not in call["headers"] for call in s.calls))
        self.assertTrue(s.calls[-1]["payload"]["params"]["arguments"]=={"query":"cos(pi/4)^4"})

    def test_unknown_free_query_rejected_before_network(self):
        s=Session()
        with self.assertRaisesRegex(mcp.MCPHold,"UNAPPROVED"):
            mcp.one_shot("user-entered-query",s)
        self.assertEqual(s.calls,[])

    def test_worker_success_dedup_never_polls_again(self):
        with tempfile.TemporaryDirectory() as folder:
            state=beetle.State(Path(folder))
            budget=beetle.Budget(max_requests=5,max_new_items=5)
            s=Session()
            d={"id":"wolfram_official_open_quantum::FORWARD",
                "keywords":["quantum","wolfram"],"priority_keywords":["wolfram"],"min_score":1}
            source={"kind":"wolfram_mcp_once","case":"zeno_n2_analytic"}
            beetle.scout_wolfram_mcp_once(s,state,budget,d,source)
            self.assertEqual(budget.requests,4)
            self.assertEqual(budget.new_items,1)
            self.assertEqual(len(state.seen),1)
            beetle.scout_wolfram_mcp_once(s,state,budget,d,source)
            self.assertEqual(len(s.calls),4)

    def test_network_error_cools_off_before_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            state=beetle.State(Path(folder))
            budget=beetle.Budget(max_requests=6,max_new_items=5)
            s=FailingSession()
            d={"id":"wolfram","keywords":["wolfram"],"priority_keywords":[],"min_score":1}
            source={"kind":"wolfram_mcp_once","case":"zeno_n2_analytic"}
            beetle.scout_wolfram_mcp_once(s,state,budget,d,source)
            first=len(s.calls)
            self.assertEqual(first,1)
            beetle.scout_wolfram_mcp_once(s,state,budget,d,source)
            self.assertEqual(len(s.calls),first)
            self.assertIn("wolfram_mcp_once:zeno_n2_analytic:"+mcp.MCP_CLIENT_REVISION+":last_attempt",state.cursors)


if __name__=="__main__":
    unittest.main(verbosity=2)
