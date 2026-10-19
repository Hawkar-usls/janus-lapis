#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "lapis_sha256_sound_compiler.py"
ROUNDTRIP = ROOT / "tools" / "lapis_sound_roundtrip.py"
FIXTURE = ROOT / "examples" / "sha256_json_reference_machine.v1.json"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class LapisSHA256SoundCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler = load(TOOL, "lapis_sha256_sound_compiler")
        cls.roundtrip = load(ROUNDTRIP, "lapis_sound_roundtrip_for_sha_test")
        cls.src = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def make_wav(self, td):
        path = Path(td) / "sha.wav"
        self.roundtrip.json_to_exact_wav(self.src, path, repeat=4)
        return path

    def test_sound_compiles_to_executable_sha256(self):
        with tempfile.TemporaryDirectory() as td:
            wav = self.make_wav(td)
            ir, code = self.compiler.compile_sound(wav, repeat=4)
            ns = {}
            exec(compile(code, "<compiled-sha>", "exec"), ns, ns)
            receipt = ns["execute"](b"abc", round_receipts=True)
            self.assertTrue(receipt["exact_match"])
            self.assertEqual(receipt["digest_hex"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
            self.assertEqual(receipt["rounds_executed"], 64)
            self.assertEqual(receipt["final_rank"], 0)
            self.assertEqual(ir["resource_bounds"]["working_words_upper_bound"], 72)

    def test_three_fixed_vectors_survive_full_chain(self):
        with tempfile.TemporaryDirectory() as td:
            wav = self.make_wav(td)
            result = self.compiler.selftest_sound(wav, repeat=4)
            self.assertEqual(result["terminal"], "LAPIS_SHA256_JSON_SOUND_ALGORITHM_CODE_SELFTEST_PASS")
            self.assertEqual(result["vectors_passed"], 3)
            self.assertEqual(result["abc_rank_transitions_verified"], 64)
            self.assertTrue(result["abc_exact_match"])
            self.assertEqual(result["P_VS_NP"], "OPEN")

    def test_schema_change_fails_closed(self):
        bad = dict(self.src)
        bad["schema"] = "something.else"
        with self.assertRaises(self.compiler.SHACompilerError):
            self.compiler.validate_sha_spec(bad)


if __name__ == "__main__":
    unittest.main()
