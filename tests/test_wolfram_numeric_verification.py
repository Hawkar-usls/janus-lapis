#!/usr/bin/env python3
"""Fail-closed Wolfram MCP numeric verdict and one-off Ocean receipt tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wolfram_mcp_numeric_verify import verify_numeric_content
from wolfram_mcp_one_shot import one_shot, CASES, MCP_ENDPOINT
from universal_beetle import Budget, State, scout_wolfram_mcp_once


class R:
    def __init__(self, body, status=200):
        self.status_code = status
        self.headers = {"Content-Type": "application/json", "Mcp-Session-Id": "FAKE"}
        self.url = MCP_ENDPOINT
        self.body = json.dumps(body).encode() if body else b""
    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i:i+chunk_size]
    def close(self):
        pass


class S:
    def __init__(self, result_text="Result: 1/4", negotiated="2025-03-26"):
        self.calls = []
        self.result_text = result_text
        self.negotiated = negotiated
    def post(self, url, *, headers, json, **kwargs):
        if url != MCP_ENDPOINT or "Authorization" in headers:
            raise AssertionError("UNEXPECTED_ENDPOINT_OR_AUTH")
        self.calls.append(json["method"])
        m = json["method"]
        if m == "initialize":
            return R({"id":1,"jsonrpc":"2.0","result":{
                "protocolVersion":self.negotiated,"serverInfo":{"name":"fake"},
                "capabilities":{}}})
        if m == "notifications/initialized":
            return R(None,status=202)
        if m == "tools/list":
            return R({"id":2,"jsonrpc":"2.0","result":{
                "tools":[{"name":"WolframAlpha","inputSchema":{
                    "properties":{"query":{"type":"string"}},"required":["query"]}}]}})
        if m == "tools/call":
            if json["params"]["arguments"] != {"query": CASES["zeno_n2_verified_v1"]["query"]}:
                raise AssertionError("UNAPPROVED_QUERY")
            return R({"id":3,"jsonrpc":"2.0","result":{
                "isError":False,
                "content":[{"type":"text","text":self.result_text}]}})
        raise AssertionError("UNKNOWN_MCP_METHOD")


class NumericTests(unittest.TestCase):
    def test_only_scalar_or_labelled_result_is_eligible(self):
        for val in ("1/4", "0.25", "Result: 1/4", "Result\n0.25",
                    "Decimal approximation: 0.25", "Wolfram|Alpha Result: 1/4"):
            ok, why = verify_numeric_content([{"type":"text","text":val}],0.25)
            self.assertTrue(ok,(val,why))
        for val, why in (
            ("This example mentions 0.25 but did not calculate anything",
             "PROVIDER_NUMERIC_RESULT_UNAVAILABLE"),
            ("Result: 1/3", "PROVIDER_MATH_DISAGREEMENT"),
            ("Result: 1/4\nResult: 2/3","PROVIDER_AMBIGUOUS_NUMERIC_RESULTS"),
            ("Result: hello", "PROVIDER_NUMERIC_RESULT_UNAVAILABLE"),
        ):
            self.assertEqual(verify_numeric_content([{"type":"text","text":val}],0.25),(False,why))

    def test_old_probe_remains_receipt_only(self):
        old=one_shot("zeno_n2_analytic",S())
        self.assertFalse(old["provider_math_answer_verified"])
        self.assertEqual(old["provider_math_verification_status"],
                         "NUMERIC_VERIFICATION_NOT_REQUESTED")

    def test_new_verification_creates_no_provider_body_in_result(self):
        s=S("Result: 1/4")
        result=one_shot("zeno_n2_verified_v1",s)
        self.assertEqual(result["status"],"LIVE_MCP_MATH_VERIFIED")
        self.assertTrue(result["provider_math_answer_verified"])
        self.assertEqual(result["provider_math_verification_status"],
                         "PROVIDER_MATH_MATCH_CONFIRMED")
        self.assertEqual(len(s.calls),4)
        self.assertNotIn("Result: 1/4",json.dumps(result))
        self.assertFalse(result["provider_response_cached"])

    def test_ambiguous_or_unparseable_does_not_get_certified(self):
        for text in ("Result: 1/4\nResult: 2/3", "the number 0.25 appears in text"):
            result=one_shot("zeno_n2_verified_v1",S(text))
            self.assertFalse(result["provider_math_answer_verified"])
            self.assertEqual(result["status"],"LIVE_MCP_TOOL_RESPONSE_RECEIVED")

    def test_beetle_persists_only_small_sha_bound_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            state=State(root)
            budget=Budget(max_requests=20,max_new_items=5)
            direction={"id":"wolfram_official_open_quantum::FORWARD",
                       "title":"Wolfram Quantum",
                       "keywords":["wolfram","quantum"],"priority_keywords":["quantum"],
                       "min_score":1}
            cfg={"kind":"wolfram_mcp_once","case":"zeno_n2_verified_v1"}
            sess=S()
            scout_wolfram_mcp_once(sess,state,budget,direction,cfg)
            p=root/"wolfram_math"/"zeno_n2_verified_v1.json"
            self.assertTrue(p.is_file())
            receipt=json.loads(p.read_text())
            self.assertTrue(receipt["verified_arithmetic_match"])
            self.assertEqual(receipt["experiment_id"],"JANUS-ZENO-TEMPORAL-001")
            self.assertEqual(receipt["research_query"],"cos(pi/4)^4")
            self.assertEqual(receipt["independent_reference"],.25)
            self.assertFalse(receipt["provider_raw_result_retained"])
            self.assertFalse(receipt["physical_retrocausality_proven"])
            self.assertEqual(len(receipt["beetle_receipt_sha256"]),64)
            self.assertNotIn("Result: 1/4",p.read_text())
            self.assertEqual(budget.requests,4)
            scout_wolfram_mcp_once(sess,state,budget,direction,cfg)
            self.assertEqual(len(sess.calls),4)
            self.assertEqual(budget.new_items,1)

    def test_false_result_cannot_claim_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=State(Path(tmp))
            direction={"id":"wolfram_official_open_quantum::FORWARD",
                       "keywords":["wolfram","quantum"],"priority_keywords":["quantum"],
                       "min_score":1}
            scout_wolfram_mcp_once(S("Result: 2/3"),state,Budget(max_requests=6),
                                  direction,{"kind":"wolfram_mcp_once","case":"zeno_n2_verified_v1"})
            receipt=json.loads((Path(tmp)/"wolfram_math"/"zeno_n2_verified_v1.json").read_text())
            self.assertFalse(receipt["verified_arithmetic_match"])
            self.assertEqual(receipt["verification_status"],"PROVIDER_MATH_DISAGREEMENT")

    def test_invalid_input_does_not_start_network(self):
        s=S()
        with self.assertRaises(ValueError):
            scout_wolfram_mcp_once(s,State(Path(tempfile.mkdtemp())),
                                  Budget(),{"id":"x"},
                                  {"kind":"wolfram_mcp_once","case":"arbitrary_user_query"})
        self.assertEqual(s.calls,[])


if __name__=="__main__":
    unittest.main(verbosity=2)
