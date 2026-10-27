#!/usr/bin/env python3
"""Lapis+Rowan+P/NP smoke controls, no provider API or credit spending."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools"/"lapis_rowan_pnp_bridge_smoke.py"
spec=importlib.util.spec_from_file_location("lapis_rowan_pnp_bridge_smoke",TOOL)
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)

class LapisRowanPnPBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=module.execute(smoke_live=False)
    def test_offline_converter_to_runner(self):
        c=self.result["converter"]
        self.assertEqual(c["generated_runner_status"],"PASS")
        self.assertEqual(c["translation_mode"],"heuristic_translation")
        self.assertFalse(c["formal_5d_tranception_run"])
    def test_unsupported_rowan_exactone_fails_closed(self):
        r=self.result["rowan"]
        self.assertEqual(r["unauthorized_operator_status"],"OPEN")
        self.assertEqual(r["unauthorized_operator_reason"],"UNKNOWN_OPERATOR")
        self.assertEqual(r["unauthorized_operator"],"ROWAN_SOLVE_EXACTONE")
        self.assertFalse(r["attempted_submission"])
        self.assertEqual(r["new_jobs"],0)
        self.assertEqual(r["credits_spent_by_test"],0)
    def test_five_exactone_reference_controls(self):
        cases=self.result["exactone_controls"]
        self.assertEqual(len(cases),5)
        self.assertEqual([(v["n"],v["count"]) for v in cases],[(9,0),(12,0),(12,3),(15,0),(15,3)])
        self.assertEqual(sum(v["states_exhaustively_enumerated"] for v in cases),74240)
        self.assertEqual([v["count"] for v in cases if v["n"]==12],[0,3])
    def test_no_polynomial_solver_claim(self):
        self.assertEqual(self.result["scientific_boundary"],"P_VS_NP_OPEN_NO_POLYNOMIAL_SOLVER")
        self.assertEqual(self.result["algorithmic_result"],"NO_NEW_PROVEN_SOLVER_OR_SUPPORT_C_CONSTRUCTION")

if __name__=="__main__":
    unittest.main()
