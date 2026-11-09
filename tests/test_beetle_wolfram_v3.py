#!/usr/bin/env python3
"""V3 Wolfram math case, one-shot dedupe and immutable Zeno evidence contract."""
import json
import tempfile
import unittest
from pathlib import Path

from test_wolfram_numeric_verification import S
from wolfram_mcp_one_shot import one_shot, CASES
from universal_beetle import Budget, State, scout_wolfram_mcp_once


class V3Tests(unittest.TestCase):
    def test_one_new_n4_equation_is_not_old_n2_equation(self):
        v3=CASES["zeno_n4_unconditional_v3"]
        self.assertEqual(v3["query"],"(1+cos(pi/4)^4)/2")
        self.assertEqual(v3["public_reference"],0.625)
        self.assertNotEqual(v3["public_reference"],CASES["zeno_n2_verified_v1"]["public_reference"])
        self.assertTrue(v3["verify_numeric"])

    def test_new_case_math_matches_with_strict_mcp_reply(self):
        s=S("### Result\n5/8",case_id="zeno_n4_unconditional_v3")
        r=one_shot("zeno_n4_unconditional_v3",s)
        self.assertEqual(r["provider_math_verification_status"],"PROVIDER_MATH_MATCH_CONFIRMED")
        self.assertTrue(r["provider_math_answer_verified"])
        self.assertEqual(len(s.calls),4)
        self.assertNotIn("5/8",json.dumps(r))
        self.assertFalse(r["physical_retrocausality_proven"])

    def test_wrong_value_never_claims_math(self):
        r=one_shot("zeno_n4_unconditional_v3",
                   S("Result: 1/2",case_id="zeno_n4_unconditional_v3"))
        self.assertEqual(r["provider_math_verification_status"],"PROVIDER_MATH_DISAGREEMENT")
        self.assertFalse(r["provider_math_answer_verified"])

    def test_v3_receipt_distinct_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as td:
            state=State(Path(td))
            b=Budget(max_requests=10,max_new_items=3)
            d={"id":"wolfram_official_open_quantum::FORWARD",
               "title":"Zeno quantum Wolfram",
               "keywords":["quantum","zeno","wolfram"],
               "priority_keywords":["quantum"],
               "min_score":1}
            s=S("Result: 5/8",case_id="zeno_n4_unconditional_v3")
            config={"kind":"wolfram_mcp_once","case":"zeno_n4_unconditional_v3"}
            scout_wolfram_mcp_once(s,state,b,d,config)
            path=Path(td)/"wolfram_math"/"zeno_n4_unconditional_v3.json"
            self.assertTrue(path.is_file())
            saved=json.loads(path.read_text())
            self.assertEqual(saved["schema"],"janus.beetle.wolfram_ocean_math_attestation.v3")
            self.assertEqual(saved["experiment_id"],"JANUS-ZENO-TEMPORAL-002")
            self.assertEqual(saved["research_query"],"(1+cos(pi/4)^4)/2")
            self.assertEqual(saved["independent_reference"],0.625)
            self.assertTrue(saved["verified_arithmetic_match"])
            self.assertEqual(saved["physical_observable"],"N4_FINAL_ZERO_WITH_EARLIER_RESULTS_UNREAD")
            self.assertFalse(saved["older_v1_attestation_overwritten"])
            self.assertFalse(saved["provider_raw_result_retained"])
            self.assertFalse(saved["physical_retrocausality_proven"])
            self.assertEqual(len(saved["zeno_cpu_v3_report_sha256"]),64)
            self.assertNotIn("Result: 5/8",path.read_text())
            self.assertEqual(len(s.calls),4)
            scout_wolfram_mcp_once(s,state,b,d,config)
            self.assertEqual(len(s.calls),4)
            self.assertEqual(b.new_items,1)
            self.assertFalse((Path(td)/"wolfram_math"/"zeno_n2_verified_v1.json").exists())

    def test_nonmatch_is_recorded_without_physical_promotion(self):
        with tempfile.TemporaryDirectory() as td:
            state=State(Path(td))
            direction={"id":"wolfram_official_open_quantum::FORWARD",
                       "title":"Quantum Zeno", "keywords":["quantum","zeno"],
                       "priority_keywords":["quantum"],"min_score":1}
            scout_wolfram_mcp_once(
                S("no result from Wolfram",case_id="zeno_n4_unconditional_v3"),
                state, Budget(max_requests=10,max_new_items=3),direction,
                {"kind":"wolfram_mcp_once","case":"zeno_n4_unconditional_v3"})
            a=json.loads((Path(td)/"wolfram_math"/"zeno_n4_unconditional_v3.json").read_text())
            self.assertFalse(a["verified_arithmetic_match"])
            self.assertEqual(a["verification_status"],"PROVIDER_NUMERIC_RESULT_UNAVAILABLE")
            self.assertFalse(a["physical_retrocausality_proven"])


if __name__=="__main__":
    unittest.main(verbosity=2)
