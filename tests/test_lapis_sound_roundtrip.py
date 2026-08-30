#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "lapis_sound_roundtrip.py"
SHA_FIXTURE = ROOT / "examples" / "sha256_json_reference_machine.v1.json"


def load_tool():
    spec = importlib.util.spec_from_file_location("lapis_sound_roundtrip", TOOL)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class LapisSoundRoundtripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_tool()

    def test_small_json_exact_roundtrip(self):
        src = {"z": [3, 2, 1], "a": {"signal": "POWER", "rank": 64}}
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "carrier.wav"
            meta = self.m.json_to_exact_wav(src, wav, repeat=4)
            recovered, decoded = self.m.exact_wav_to_json(wav, repeat=4)
            self.assertEqual(recovered, src)
            self.assertEqual(meta["source_canonical_json_sha256"], decoded["payload_sha256"])
            self.assertEqual(decoded["integrity"], "PASS")

    def test_sha256_reference_json_survives_sound_byte_exact(self):
        src = json.loads(SHA_FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "sha.wav"
            self.m.json_to_exact_wav(src, wav, repeat=4)
            recovered, meta = self.m.exact_wav_to_json(wav, repeat=4)
            self.assertEqual(self.m.canonical_json_bytes(src), self.m.canonical_json_bytes(recovered))
            self.assertEqual(recovered["pcner_positive_control"]["POLY_FIND"]["candidate_count"], 1)
            self.assertEqual(recovered["pcner_positive_control"]["POLY_HOLD"]["working_words_upper_bound"], 72)
            self.assertEqual(recovered["scientific_boundary"]["P_VS_NP"], "OPEN")
            self.assertEqual(meta["integrity"], "PASS")

    def test_sound_to_algorithm_keeps_no_theorem_authority(self):
        src = json.loads(SHA_FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "sha.wav"
            self.m.json_to_exact_wav(src, wav, repeat=4)
            ir = self.m.sound_to_algorithm(wav, repeat=4)
            self.assertFalse(ir["scientific_boundary"]["sound_carrier_adds_semantic_authority"])
            self.assertFalse(ir["scientific_boundary"]["sound_roundtrip_is_sat_transfer_proof"])
            self.assertEqual(ir["scientific_boundary"]["P_VS_NP"], "OPEN")

    def test_generated_code_from_sound_executes_fail_closed_ir(self):
        src = {
            "$lapis": {
                "algorithm": {
                    "name": "sound_counter",
                    "steps": [
                        {"op": "SET", "target": "x", "value": 1},
                        {"op": "INCREMENT", "target": "x", "amount": 2},
                        {"op": "ASSERT", "predicate": {"key": "x", "equals": 3}}
                    ]
                }
            }
        }
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "carrier.wav"
            self.m.json_to_exact_wav(src, wav, repeat=4)
            ir = self.m.sound_to_algorithm(wav, repeat=4)
            code = self.m.BASE.algorithm_to_python(ir)
            ns = {}
            exec(compile(code, "<sound-generated>", "exec"), ns, ns)
            result = ns["run"]({})
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["context"]["x"], 3)

    def test_pcm_tamper_fails_closed(self):
        src = {"a": 1, "b": 2}
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "carrier.wav"
            bad = Path(td) / "tampered.wav"
            self.m.json_to_exact_wav(src, wav, repeat=4)
            with wave.open(str(wav), "rb") as r:
                params = r.getparams()
                frames = bytearray(r.readframes(r.getnframes()))
            # Flip one complete repeated PCM symbol enough to map to a different byte.
            symbol_index = 60
            start = symbol_index * 4 * 2
            for j in range(4):
                off = start + j * 2
                if off + 1 < len(frames):
                    sample = int.from_bytes(frames[off:off+2], "little", signed=True)
                    sample = max(-32768, min(32767, sample + 257))
                    frames[off:off+2] = int(sample).to_bytes(2, "little", signed=True)
            with wave.open(str(bad), "wb") as w:
                w.setparams(params)
                w.writeframes(bytes(frames))
            with self.assertRaises(self.m.SoundCarrierError):
                self.m.exact_wav_to_json(bad, repeat=4)


if __name__ == "__main__":
    unittest.main()
