#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JANUS Lapis exact sound-carrier bridge.

This module complements ``tools/lapis_converter.py`` with a theorem-safe carrier
lane:

    canonical JSON -> exact PCM WAV -> canonical JSON -> algorithm IR -> code

The existing musical sonification in lapis_converter is intentionally lossy and
human-facing.  This lane is different: WAV is only a reversible carrier.  It
adds no semantic authority.  Decoding fails closed unless framing, canonical
JSON and SHA-256 integrity all verify exactly.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import struct
import sys
import wave
from pathlib import Path
from typing import Any, Dict, Tuple

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "lapis_converter.py"
SPEC = importlib.util.spec_from_file_location("janus_lapis_converter_base", BASE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load lapis_converter.py")
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)

SCHEMA = "janus.lapis.exact_sound_carrier.v1"
PIPELINE_SCHEMA = "janus.lapis.sha_json_sound_algorithm_pipeline.v1"
MAGIC = b"JLW1"
HEADER_BYTES = 4 + 8 + 32
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_REPEAT = 4


class SoundCarrierError(ValueError):
    pass


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(data: Any) -> bytes:
    return BASE.canonical_json_bytes(data)


def _frame(payload: bytes) -> bytes:
    return MAGIC + struct.pack(">Q", len(payload)) + hashlib.sha256(payload).digest() + payload


def _byte_to_sample(value: int) -> int:
    # Exact affine map: 0 -> -32768 and 255 -> 32767.
    return value * 257 - 32768


def _sample_to_byte(sample: int, tolerance: int = 1) -> int:
    estimate = int(round((int(sample) + 32768) / 257.0))
    if not 0 <= estimate <= 255:
        raise SoundCarrierError("PCM_SYMBOL_OUT_OF_RANGE")
    expected = _byte_to_sample(estimate)
    if abs(int(sample) - expected) > tolerance:
        raise SoundCarrierError("PCM_SYMBOL_NOT_EXACT")
    return estimate


def json_to_exact_wav(
    data: Any,
    path: Path,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    repeat: int = DEFAULT_REPEAT,
) -> Dict[str, Any]:
    if sample_rate < 8000:
        raise ValueError("sample_rate must be >= 8000")
    if repeat < 1 or repeat > 64:
        raise ValueError("repeat must be in 1..64")

    payload = canonical_json_bytes(data)
    framed = _frame(payload)
    samples = []
    for byte in framed:
        sample = _byte_to_sample(byte)
        samples.extend([sample] * repeat)

    pcm = struct.pack("<" + "h" * len(samples), *samples)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)

    return {
        "schema": SCHEMA,
        "mode": "EXACT_REVERSIBLE_PCM_CARRIER",
        "sample_rate": sample_rate,
        "repeat": repeat,
        "payload_bytes": len(payload),
        "frame_bytes": len(framed),
        "source_canonical_json_sha256": sha256_hex(payload),
        "wav_sha256": sha256_hex(path.read_bytes()),
        "semantic_authority": False,
        "lossless_for_generated_pcm": True,
    }


def exact_wav_to_json(
    path: Path,
    *,
    repeat: int = DEFAULT_REPEAT,
    tolerance: int = 1,
) -> Tuple[Any, Dict[str, Any]]:
    if repeat < 1 or repeat > 64:
        raise ValueError("repeat must be in 1..64")

    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        count = wav.getnframes()
        raw = wav.readframes(count)

    if channels != 1:
        raise SoundCarrierError("CARRIER_REQUIRES_MONO")
    if width != 2:
        raise SoundCarrierError("CARRIER_REQUIRES_PCM16")
    if count % repeat != 0:
        raise SoundCarrierError("CARRIER_REPEAT_ALIGNMENT_FAILED")

    samples = struct.unpack("<" + "h" * count, raw)
    decoded = bytearray()
    for i in range(0, len(samples), repeat):
        group = samples[i : i + repeat]
        median = int(statistics.median(group))
        # Exact lane: all repeated symbols must remain close to their median.
        if max(abs(int(x) - median) for x in group) > tolerance:
            raise SoundCarrierError("CARRIER_REPEAT_DISAGREEMENT")
        decoded.append(_sample_to_byte(median, tolerance=tolerance))

    frame = bytes(decoded)
    if len(frame) < HEADER_BYTES:
        raise SoundCarrierError("CARRIER_FRAME_TOO_SHORT")
    if frame[:4] != MAGIC:
        raise SoundCarrierError("CARRIER_MAGIC_MISMATCH")

    payload_len = struct.unpack(">Q", frame[4:12])[0]
    expected_digest = frame[12:44]
    expected_total = HEADER_BYTES + payload_len
    if len(frame) != expected_total:
        raise SoundCarrierError("CARRIER_LENGTH_MISMATCH")

    payload = frame[44:]
    actual_digest = hashlib.sha256(payload).digest()
    if actual_digest != expected_digest:
        raise SoundCarrierError("CARRIER_SHA256_MISMATCH")

    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SoundCarrierError("CARRIER_JSON_DECODE_FAILED") from exc

    canonical = canonical_json_bytes(data)
    if canonical != payload:
        raise SoundCarrierError("CARRIER_JSON_NOT_CANONICAL")

    return data, {
        "schema": SCHEMA,
        "mode": "EXACT_REVERSIBLE_PCM_CARRIER",
        "sample_rate": sample_rate,
        "repeat": repeat,
        "payload_bytes": len(payload),
        "payload_sha256": sha256_hex(payload),
        "wav_sha256": sha256_hex(path.read_bytes()),
        "integrity": "PASS",
        "semantic_authority": False,
    }


def sound_to_algorithm(path: Path, *, repeat: int = DEFAULT_REPEAT) -> Dict[str, Any]:
    data, carrier = exact_wav_to_json(path, repeat=repeat)
    ir = BASE.json_to_algorithm(data)
    # Bind the decoded carrier provenance into the candidate IR, then reseal it.
    ir.pop("algorithm_sha256", None)
    ir["carrier_provenance"] = carrier
    ir["scientific_boundary"]["sound_carrier_adds_semantic_authority"] = False
    ir["scientific_boundary"]["sound_roundtrip_is_sat_transfer_proof"] = False
    ir["algorithm_sha256"] = sha256_hex(canonical_json_bytes(ir))
    return ir


def exact_roundtrip(source: Path, outdir: Path, *, sample_rate: int, repeat: int) -> Dict[str, Any]:
    data = BASE.load_json(source)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = BASE.slug(source.stem)
    wav_path = outdir / f"{stem}.exact-carrier.wav"
    recovered_path = outdir / f"{stem}.recovered.json"
    algorithm_path = outdir / f"{stem}.sound.algorithm.json"
    code_path = outdir / f"{stem}.sound.generated.py"
    manifest_path = outdir / f"{stem}.sound-roundtrip.manifest.json"

    source_payload = canonical_json_bytes(data)
    encode_meta = json_to_exact_wav(data, wav_path, sample_rate=sample_rate, repeat=repeat)
    recovered, decode_meta = exact_wav_to_json(wav_path, repeat=repeat)
    recovered_payload = canonical_json_bytes(recovered)
    if recovered_payload != source_payload:
        raise SoundCarrierError("ROUNDTRIP_CANONICAL_BYTES_MISMATCH")

    BASE.write_json(recovered_path, recovered)
    ir = sound_to_algorithm(wav_path, repeat=repeat)
    BASE.write_json(algorithm_path, ir)
    code_path.write_text(BASE.algorithm_to_python(ir), encoding="utf-8")

    manifest = {
        "schema": PIPELINE_SCHEMA,
        "route": [
            "SHA256_REFERENCE_MACHINE_JSON_OR_OTHER_CANONICAL_JSON",
            "EXACT_PCM_WAV_CARRIER",
            "EXACT_JSON_RECOVERY",
            "LAPIS_ALGORITHM_IR",
            "FAIL_CLOSED_PYTHON_CODE",
        ],
        "source": {
            "path": str(source),
            "canonical_json_sha256": sha256_hex(source_payload),
        },
        "carrier": encode_meta,
        "decode": decode_meta,
        "roundtrip": {
            "canonical_bytes_equal": True,
            "source_sha256": sha256_hex(source_payload),
            "recovered_sha256": sha256_hex(recovered_payload),
        },
        "algorithm": {
            "algorithm_sha256": ir["algorithm_sha256"],
            "mode": ir["algorithm"]["mode"],
        },
        "outputs": {
            "wav": str(wav_path),
            "recovered_json": str(recovered_path),
            "algorithm_ir": str(algorithm_path),
            "python_code": str(code_path),
        },
        "scientific_boundary": {
            "sound_is_carrier_not_oracle": True,
            "musical_sonification_is_not_used_for_exact_decode": True,
            "heuristic_json_translation_is_proof": False,
            "SHA256_POLY_ROUTE_implies_SAT_POLY_ROUTE": False,
            "P_equals_NP_proved": False,
            "P_VS_NP": "OPEN",
        },
    }
    BASE.write_json(manifest_path, manifest)
    return manifest


def cmd_json_to_sound(args: argparse.Namespace) -> None:
    data = BASE.load_json(Path(args.input))
    meta = json_to_exact_wav(data, Path(args.output), sample_rate=args.sample_rate, repeat=args.repeat)
    print(json.dumps({"status": "PASS", "output": args.output, **meta}, ensure_ascii=False))


def cmd_sound_to_json(args: argparse.Namespace) -> None:
    data, meta = exact_wav_to_json(Path(args.input), repeat=args.repeat)
    BASE.write_json(Path(args.output), data)
    print(json.dumps({"status": "PASS", "output": args.output, **meta}, ensure_ascii=False))


def cmd_sound_to_algorithm(args: argparse.Namespace) -> None:
    ir = sound_to_algorithm(Path(args.input), repeat=args.repeat)
    BASE.write_json(Path(args.output), ir)
    print(json.dumps({"status": "PASS", "output": args.output, "algorithm_sha256": ir["algorithm_sha256"]}, ensure_ascii=False))


def cmd_sound_to_code(args: argparse.Namespace) -> None:
    ir = sound_to_algorithm(Path(args.input), repeat=args.repeat)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(BASE.algorithm_to_python(ir), encoding="utf-8")
    print(json.dumps({"status": "PASS", "output": args.output, "sha256": sha256_hex(output.read_bytes())}, ensure_ascii=False))


def cmd_roundtrip(args: argparse.Namespace) -> None:
    manifest = exact_roundtrip(Path(args.input), Path(args.outdir), sample_rate=args.sample_rate, repeat=args.repeat)
    print(json.dumps({"status": "PASS", **manifest}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JANUS Lapis exact JSON <-> sound carrier -> algorithm bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("json-to-exact-sound")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE)
    p.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    p.set_defaults(func=cmd_json_to_sound)

    p = sub.add_parser("exact-sound-to-json")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    p.set_defaults(func=cmd_sound_to_json)

    p = sub.add_parser("exact-sound-to-algorithm")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    p.set_defaults(func=cmd_sound_to_algorithm)

    p = sub.add_parser("exact-sound-to-code")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    p.set_defaults(func=cmd_sound_to_code)

    p = sub.add_parser("exact-roundtrip")
    p.add_argument("input")
    p.add_argument("--outdir", required=True)
    p.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE)
    p.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    p.set_defaults(func=cmd_roundtrip)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
