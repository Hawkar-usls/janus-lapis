#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "lapis_converter.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("lapis_converter", TOOL)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class LapisConverterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_tool()

    def test_explicit_contract_to_ir_is_deterministic(self):
        src = {
            "$lapis": {
                "algorithm": {
                    "name": "counter",
                    "steps": [
                        {"op": "SET", "target": "x", "value": 1},
                        {"op": "INCREMENT", "target": "x", "amount": 2},
                        {"op": "ASSERT", "predicate": {"key": "x", "equals": 3}},
                    ],
                }
            }
        }
        a = self.m.json_to_algorithm(src)
        b = self.m.json_to_algorithm(src)
        self.assertEqual(a["algorithm_sha256"], b["algorithm_sha256"])
        self.assertEqual(a["algorithm"]["mode"], "explicit_contract")

    def test_heuristic_translation_has_no_proof_authority(self):
        src = {
            "canonical_signal_chains": ["A -> B", "B -> C"],
            "gate_rule": "C must preserve A",
            "formula_ascii": "Phi = R*(T+1)+t",
        }
        ir = self.m.json_to_algorithm(src)
        self.assertEqual(ir["algorithm"]["mode"], "heuristic_translation")
        self.assertFalse(ir["algorithm"]["metadata"]["heuristic_authority"])
        self.assertFalse(ir["scientific_boundary"]["heuristic_translation_is_proof"])

    def test_generated_python_executes_builtin_contract(self):
        src = {
            "$lapis": {
                "algorithm": {
                    "name": "counter",
                    "steps": [
                        {"op": "SET", "target": "x", "value": 1},
                        {"op": "INCREMENT", "target": "x", "amount": 2},
                        {"op": "ASSERT", "predicate": {"key": "x", "equals": 3}},
                    ],
                }
            }
        }
        ir = self.m.json_to_algorithm(src)
        generated = self.m.algorithm_to_python(ir)
        ns = {}
        exec(compile(generated, "<generated>", "exec"), ns, ns)
        result = ns["run"]({})
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["context"]["x"], 3)

    def test_unknown_operator_fails_closed(self):
        src = {
            "$lapis": {
                "algorithm": {
                    "name": "unknown",
                    "steps": [{"op": "DO_MAGIC"}],
                }
            }
        }
        ir = self.m.json_to_algorithm(src)
        generated = self.m.algorithm_to_python(ir)
        ns = {}
        exec(compile(generated, "<generated>", "exec"), ns, ns)
        result = ns["run"]({})
        self.assertEqual(result["status"], "OPEN")
        self.assertEqual(result["reason"], "UNKNOWN_OPERATOR")

    def test_json_to_wav_writes_valid_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.wav"
            meta = self.m.json_to_wav({"a": 1, "b": "two"}, path, max_tones=8)
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 44)
            self.assertEqual(meta["tone_count"], 2)


if __name__ == "__main__":
    unittest.main()
