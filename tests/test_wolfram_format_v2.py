#!/usr/bin/env python3
"""Offline Wolfram MCP provider-format regressions and anti-false-positive tests."""
from __future__ import annotations

import json
import unittest

from wolfram_mcp_numeric_verify import verify_numeric_content, safe_shape_summary
from wolfram_mcp_one_shot import one_shot, CASES
from test_wolfram_numeric_verification import S as FakeMCP


def text(value):
    return [{"type":"text","text":value}]


class Tests(unittest.TestCase):
    def test_result_forms_allowed(self):
        allowed=(
            "1/4",
            "0.25",
            "Result: 1/4",
            "### Result\n\n1/4",
            "**Result:** 1/4",
            "| Result | 0.25 |",
            "Result: \\(\\frac{1}{4}\\)",
            "Result:\n$$\\frac{1}{4}$$",
            ' {"result":"1/4"} ',
        )
        for s in allowed:
            verdict, status=verify_numeric_content(text(s),.25)
            self.assertTrue(verdict,(s,status))

    def test_structured_result_and_wolfram_pods(self):
        structures=(
            {"result":"1/4"},
            {"result":{"pods":[{"title":"Result","subpods":[{"plaintext":"1/4"}]}]}},
            {"pods":[{"title":"Input interpretation","subpods":[{"plaintext":"0.25"}]},
                     {"title":"Result","subpods":[{"plaintext":"1/4"}]}]},
        )
        for structure in structures:
            yes, status=verify_numeric_content(text("Not a result"),.25,structure)
            self.assertTrue(yes,(structure,status))

    def test_adversarial_context_does_not_fake_math_pass(self):
        untrusted=(
            "The input contains 0.25, but the provider did not compute an answer",
            "Input interpretation: 0.25\nNo result",
            "Model prediction 0.25",
            "### Input\n0.25",
            "| Input | 0.25 |",
            "Result: 0.25 and then more data",
            "Result: nothing\nInput: 0.25",
        )
        for s in untrusted:
            yes, code=verify_numeric_content(text(s),.25)
            self.assertFalse(yes,(s,code))

    def test_conflicting_or_unrelated_result_not_accepted(self):
        yes,code=verify_numeric_content(text("Result: 1/4\nResult: 1/2"),.25)
        self.assertFalse(yes)
        self.assertEqual(code,"PROVIDER_AMBIGUOUS_NUMERIC_RESULTS")
        yes,code=verify_numeric_content(text("Result: 1/2"),.25)
        self.assertFalse(yes)
        self.assertEqual(code,"PROVIDER_MATH_DISAGREEMENT")

    def test_noncontent_diagnostics_cannot_include_wolfram_text(self):
        provider="### Result\n\n1/4"
        shape=safe_shape_summary(text(provider))
        serialized=json.dumps(shape)
        self.assertNotIn(provider,serialized)
        self.assertNotIn("1/4",serialized)
        self.assertTrue(shape["numeric_candidate_recognized"])
        self.assertTrue(shape["contains_result_label"])

    def test_mcp_one_shot_formats_and_negative_control(self):
        fake=FakeMCP("### Result\n1/4")
        r=one_shot("zeno_format_probe_v2",fake)
        self.assertTrue(r["provider_math_answer_verified"])
        self.assertEqual(r["provider_math_verification_status"],
                         "PROVIDER_MATH_MATCH_CONFIRMED")
        self.assertTrue(r["noncontent_format_flags"]["numeric_candidate_recognized"])
        self.assertNotIn("### Result",json.dumps(r))
        self.assertNotIn("1/4",json.dumps(r))
        self.assertFalse(r["physical_retrocausality_proven"])
        self.assertEqual(r["public_question"],CASES["zeno_format_probe_v2"]["query"])

    def test_large_provider_text_fails_closed(self):
        yes,status=verify_numeric_content(text("x"*20001),.25)
        self.assertFalse(yes)
        self.assertEqual(status,"PROVIDER_FORMAT_OUTSIDE_BOUNDS")


if __name__=="__main__":
    unittest.main(verbosity=2)
