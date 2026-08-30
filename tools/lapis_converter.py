#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JANUS Lapis Universal Converter.

Deterministic, fail-closed lanes:
  JSON -> algorithm IR
  JSON -> Python code
  JSON -> WAV sonification
  JSON -> all outputs + provenance manifest

No eval/exec is performed on JSON content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Sequence, Tuple

SCHEMA = "janus.lapis.universal_converter.v1"
ALGORITHM_SCHEMA = "janus.lapis.algorithm_ir.v1"
SOUND_SCHEMA = "janus.lapis.json_sonification.v1"

CHAIN_TOKENS = ("chain", "steps", "sequence", "pipeline", "process", "protocol", "stages", "flow", "trajectory")
GATE_TOKENS = ("gate", "rule", "invariant", "boundary", "require", "constraint", "firewall", "condition", "law", "must")
FORMULA_TOKENS = ("formula", "equation", "index", "potential", "rank", "score")
INPUT_TOKENS = ("input", "source", "subject", "variables", "parameters")
OUTPUT_TOKENS = ("output", "result", "conclusion", "signal", "verdict", "status")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slug(text: str, fallback: str = "lapis_algorithm") -> str:
    text = re.sub(r"[^A-Za-z0-9_]+", "_", str(text)).strip("_").lower()
    return text or fallback


def is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def walk(value: Any, path: Tuple[str, ...] = ()) -> Iterator[Tuple[Tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key in sorted(value, key=lambda x: str(x)):
            yield from walk(value[key], path + (str(key),))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, path + (str(index),))


def ptext(path: Sequence[str]) -> str:
    return ".".join(path) if path else "$"


def path_has(path: Sequence[str], tokens: Sequence[str]) -> bool:
    joined = ".".join(path).lower()
    return any(t.lower() in joined for t in tokens)


def normalize_step(raw: Any, index: int) -> Dict[str, Any]:
    if isinstance(raw, str):
        return {"id": f"step_{index:03d}", "operator": "ANNOTATE", "args": {"text": raw}, "source": "explicit_string"}
    if not isinstance(raw, Mapping):
        return {"id": f"step_{index:03d}", "operator": "ANNOTATE", "args": {"value": raw}, "source": "explicit_scalar"}

    operator = str(raw.get("operator", raw.get("op", "ANNOTATE"))).upper()
    args = dict(raw.get("args", {})) if isinstance(raw.get("args"), Mapping) else {}
    for key in ("target", "value", "source_key", "amount", "predicate", "message", "text"):
        if key in raw and key not in args:
            args[key] = raw[key]

    out = {"id": str(raw.get("id", f"step_{index:03d}")), "operator": operator, "args": args, "source": "explicit_object"}
    for key in ("certificate", "requires", "progress"):
        if key in raw:
            out[key] = raw[key]
    return out


def explicit_algorithm(data: Any) -> Dict[str, Any] | None:
    if not isinstance(data, Mapping):
        return None
    lapis = data.get("$lapis")
    if not isinstance(lapis, Mapping):
        return None
    alg = lapis.get("algorithm")
    if not isinstance(alg, Mapping):
        return None

    raw_steps = alg.get("steps", [])
    if not isinstance(raw_steps, list):
        raise ValueError("$lapis.algorithm.steps must be an array")

    return {
        "name": str(alg.get("name", "lapis_explicit_algorithm")),
        "mode": "explicit_contract",
        "inputs": alg.get("inputs", []),
        "state": alg.get("state", {}),
        "invariants": alg.get("invariants", []),
        "steps": [normalize_step(step, i + 1) for i, step in enumerate(raw_steps)],
        "outputs": alg.get("outputs", []),
        "progress": alg.get("progress"),
        "resource_bounds": alg.get("resource_bounds", {}),
        "metadata": alg.get("metadata", {}),
    }


def heuristic_algorithm(data: Any, input_sha: str) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []
    invariants: List[Dict[str, Any]] = []
    formulas: List[Dict[str, Any]] = []
    inputs: List[Dict[str, Any]] = []
    outputs: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def add_step(path: Tuple[str, ...], payload: Any) -> None:
        signature = ptext(path) + "::" + json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        if signature in seen or len(steps) >= 512:
            return
        seen.add(signature)
        steps.append({
            "id": f"step_{len(steps)+1:03d}",
            "operator": "ANNOTATE",
            "args": {"source_path": ptext(path), "value": payload},
            "source": "heuristic_chain",
        })

    for path, value in walk(data):
        if not path:
            continue

        if path_has(path, CHAIN_TOKENS):
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if is_scalar(item):
                        add_step(path + (str(i),), item)
                    elif isinstance(item, Mapping):
                        add_step(path + (str(i),), item.get("signal") or item.get("meaning") or item.get("statement") or item)
            elif isinstance(value, Mapping):
                for key in sorted(value):
                    item = value[key]
                    if is_scalar(item):
                        add_step(path + (str(key),), item)
                    elif isinstance(item, Mapping):
                        add_step(path + (str(key),), item.get("signal") or item.get("meaning") or item.get("statement") or item)

        if path_has(path, GATE_TOKENS) and is_scalar(value) and len(invariants) < 256:
            invariants.append({"source_path": ptext(path), "statement": value})
        if path_has(path, FORMULA_TOKENS) and is_scalar(value) and len(formulas) < 128:
            formulas.append({"source_path": ptext(path), "expression": value, "evaluation": "NOT_EVALUATED"})
        if path_has(path, INPUT_TOKENS) and is_scalar(value) and len(inputs) < 128:
            inputs.append({"source_path": ptext(path), "value": value})
        if path_has(path, OUTPUT_TOKENS) and is_scalar(value) and len(outputs) < 128:
            outputs.append({"source_path": ptext(path), "value": value})

    if not steps:
        if isinstance(data, Mapping):
            for key in sorted(data):
                value = data[key]
                preview = value if is_scalar(value) else {"type": type(value).__name__, "size": len(value)}
                add_step((str(key),), preview)
        else:
            add_step(("$",), data)

    name = "lapis_" + input_sha[:12]
    if isinstance(data, Mapping):
        for key in ("algorithm_id", "artifact_id", "registry_id", "title", "name", "subject"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                name = slug(value)
                break

    return {
        "name": name,
        "mode": "heuristic_translation",
        "inputs": inputs,
        "state": {"input_sha256": input_sha, "translation_policy": "deterministic_fail_closed_no_eval"},
        "invariants": invariants,
        "steps": steps,
        "outputs": outputs,
        "progress": {
            "kind": "ordered_step_index",
            "definition": "progress = number_of_completed_steps",
            "note": "Domain-semantic progress requires an explicit $lapis.algorithm contract.",
        },
        "resource_bounds": {"max_steps": 512, "max_invariants": 256, "max_inputs": 128, "max_outputs": 128},
        "metadata": {"formulas": formulas, "heuristic_authority": False},
    }


def json_to_algorithm(data: Any) -> Dict[str, Any]:
    input_sha = sha256_hex(canonical_json_bytes(data))
    body = explicit_algorithm(data) or heuristic_algorithm(data, input_sha)
    result = {
        "schema": ALGORITHM_SCHEMA,
        "converter_schema": SCHEMA,
        "input_sha256": input_sha,
        "algorithm": body,
        "scientific_boundary": {
            "generated_algorithm_is_candidate": True,
            "heuristic_translation_is_proof": False,
            "generated_code_is_verified": False,
            "P_VS_NP": "OPEN",
        },
    }
    result["algorithm_sha256"] = sha256_hex(canonical_json_bytes(result))
    return result


def algorithm_to_python(ir: Mapping[str, Any]) -> str:
    payload = json.dumps(ir, ensure_ascii=False, sort_keys=True, indent=2)
    template = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Generated by JANUS Lapis Universal Converter.
# Unknown operators fail closed with status OPEN.

from __future__ import annotations
import copy
import json
from typing import Any, Mapping

ALGORITHM_IR = json.loads(__PAYLOAD__)


def _get_path(context: Mapping[str, Any], key: str) -> Any:
    cur: Any = context
    for part in str(key).split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            raise KeyError(key)
        cur = cur[part]
    return cur


def _set_path(context, key, value):
    parts = str(key).split(".")
    cur = context
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _predicate(context, pred):
    if isinstance(pred, bool):
        return pred
    if not isinstance(pred, Mapping) or "key" not in pred:
        return False
    try:
        actual = _get_path(context, str(pred["key"]))
    except KeyError:
        return bool(pred.get("missing_ok", False))
    if "equals" in pred:
        return actual == pred["equals"]
    if "not_equals" in pred:
        return actual != pred["not_equals"]
    if "lt" in pred:
        return actual < pred["lt"]
    if "lte" in pred:
        return actual <= pred["lte"]
    if "gt" in pred:
        return actual > pred["gt"]
    if "gte" in pred:
        return actual >= pred["gte"]
    return bool(actual)


def run(context=None, operators=None):
    ctx = copy.deepcopy(dict(context or {}))
    custom = dict(operators or {})
    trace = []

    for index, step in enumerate(ALGORITHM_IR["algorithm"].get("steps", []), start=1):
        op = str(step.get("operator", "ANNOTATE")).upper()
        args = step.get("args", {})
        event = {"index": index, "id": step.get("id"), "operator": op}

        if op in ("ANNOTATE", "NOOP"):
            event["status"] = "PASS"

        elif op == "SET":
            target = args.get("target")
            if not target:
                return {"status": "OPEN", "reason": "SET_MISSING_TARGET", "trace": trace}
            _set_path(ctx, str(target), copy.deepcopy(args.get("value")))
            event["status"] = "PASS"

        elif op == "COPY":
            target, source_key = args.get("target"), args.get("source_key")
            if not target or not source_key:
                return {"status": "OPEN", "reason": "COPY_MISSING_PATH", "trace": trace}
            try:
                value = copy.deepcopy(_get_path(ctx, str(source_key)))
            except KeyError:
                return {"status": "OPEN", "reason": "COPY_SOURCE_MISSING", "trace": trace}
            _set_path(ctx, str(target), value)
            event["status"] = "PASS"

        elif op in ("INCREMENT", "DECREMENT"):
            target = args.get("target")
            amount = args.get("amount", 1)
            if not target or not isinstance(amount, (int, float)):
                return {"status": "OPEN", "reason": op + "_BAD_ARGS", "trace": trace}
            try:
                current = _get_path(ctx, str(target))
            except KeyError:
                current = 0
            if not isinstance(current, (int, float)):
                return {"status": "OPEN", "reason": op + "_NON_NUMERIC_TARGET", "trace": trace}
            _set_path(ctx, str(target), current + (amount if op == "INCREMENT" else -amount))
            event["status"] = "PASS"

        elif op == "ASSERT":
            if not _predicate(ctx, args.get("predicate")):
                event["status"] = "REJECTED"
                trace.append(event)
                return {"status": "REJECTED", "reason": args.get("message", "ASSERT_FAILED"), "context": ctx, "trace": trace}
            event["status"] = "PASS"

        elif op == "EMIT":
            event["status"] = "PASS"
            event["value"] = copy.deepcopy(args.get("value"))

        elif op in custom:
            result = custom[op](ctx, args)
            if isinstance(result, Mapping):
                ctx = dict(result)
            event["status"] = "PASS_CUSTOM"

        else:
            event["status"] = "OPEN"
            trace.append(event)
            return {"status": "OPEN", "reason": "UNKNOWN_OPERATOR", "operator": op, "context": ctx, "trace": trace}

        trace.append(event)

    return {"status": "PASS", "context": ctx, "trace": trace, "algorithm_sha256": ALGORITHM_IR.get("algorithm_sha256")}


if __name__ == "__main__":
    print(json.dumps(run({}), ensure_ascii=False, indent=2))
"""
    return template.replace("__PAYLOAD__", repr(payload))


@dataclass(frozen=True)
class Tone:
    frequency: float
    duration: float
    amplitude: float


def leaf_tokens(data: Any) -> List[Tuple[str, Any]]:
    leaves = [(ptext(path), value) for path, value in walk(data) if path and is_scalar(value)]
    return leaves or [("$", "empty")]


def tone_for(path: str, value: Any, base_duration: float) -> Tone:
    digest = hashlib.sha256(canonical_json_bytes({"path": path, "value": value})).digest()
    semitones = (0, 2, 4, 7, 9, 12, 14, 16, 19, 21)
    midi = 60 + semitones[digest[0] % len(semitones)] + 12 * ((digest[1] % 3) - 1)
    frequency = 440.0 * (2.0 ** ((midi - 69) / 12.0))
    amplitude = 0.16 + (digest[2] / 255.0) * 0.12
    duration = base_duration * (0.75 + (digest[3] / 255.0) * 0.5)
    return Tone(frequency, duration, amplitude)


def json_to_wav(data: Any, path: Path, sample_rate: int = 22050, base_duration: float = 0.10, max_tones: int = 256) -> Dict[str, Any]:
    if sample_rate < 8000:
        raise ValueError("sample_rate must be >= 8000")
    if base_duration <= 0:
        raise ValueError("base_duration must be > 0")
    all_leaves = leaf_tokens(data)
    tones = [tone_for(p, v, base_duration) for p, v in all_leaves[:max_tones]]
    frames = bytearray()
    phase = 0.0

    for tone in tones:
        count = max(1, int(sample_rate * tone.duration))
        attack = max(1, int(count * 0.08))
        release = max(1, int(count * 0.12))
        for i in range(count):
            if i < attack:
                env = i / attack
            elif i >= count - release:
                env = max(0.0, (count - i - 1) / release)
            else:
                env = 1.0
            sample = math.sin(phase) * tone.amplitude * env
            phase += 2.0 * math.pi * tone.frequency / sample_rate
            frames.extend(struct.pack("<h", int(max(-1.0, min(1.0, sample)) * 32767)))

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(frames))

    return {
        "schema": SOUND_SCHEMA,
        "sample_rate": sample_rate,
        "tone_count": len(tones),
        "source_leaf_count": len(all_leaves),
        "duration_seconds": round(sum(t.duration for t in tones), 6),
        "wav_sha256": sha256_hex(path.read_bytes()),
        "mapping": "sha256(path,value) -> deterministic pentatonic tone",
    }


def build_manifest(source: Path, data: Any, outputs: Mapping[str, Path], metadata: Mapping[str, Any]) -> Dict[str, Any]:
    result = {
        "schema": SCHEMA,
        "source": {"path": str(source), "canonical_json_sha256": sha256_hex(canonical_json_bytes(data))},
        "outputs": {},
        "metadata": dict(metadata),
        "boundaries": {
            "no_eval": True,
            "no_exec_of_json": True,
            "heuristic_translation_has_theorem_authority": False,
            "generated_code_requires_target_domain_review": True,
        },
    }
    for name, path in outputs.items():
        if path.exists():
            result["outputs"][name] = {"path": str(path), "sha256": sha256_hex(path.read_bytes()), "bytes": path.stat().st_size}
    return result


def cmd_algorithm(args):
    source, output = Path(args.input), Path(args.output)
    ir = json_to_algorithm(load_json(source))
    write_json(output, ir)
    print(json.dumps({"status": "PASS", "output": str(output), "algorithm_sha256": ir["algorithm_sha256"]}, ensure_ascii=False))


def cmd_code(args):
    source, output = Path(args.input), Path(args.output)
    ir = json_to_algorithm(load_json(source))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(algorithm_to_python(ir), encoding="utf-8")
    print(json.dumps({"status": "PASS", "output": str(output), "sha256": sha256_hex(output.read_bytes())}, ensure_ascii=False))


def cmd_sound(args):
    source, output = Path(args.input), Path(args.output)
    meta = json_to_wav(load_json(source), output, args.sample_rate, args.base_duration, args.max_tones)
    print(json.dumps({"status": "PASS", "output": str(output), **meta}, ensure_ascii=False))


def cmd_all(args):
    source = Path(args.input)
    data = load_json(source)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = slug(source.stem)

    alg_path = outdir / f"{stem}.algorithm.json"
    code_path = outdir / f"{stem}.generated.py"
    wav_path = outdir / f"{stem}.wav"
    manifest_path = outdir / f"{stem}.manifest.json"

    ir = json_to_algorithm(data)
    write_json(alg_path, ir)
    code_path.write_text(algorithm_to_python(ir), encoding="utf-8")
    sound_meta = json_to_wav(data, wav_path, args.sample_rate, args.base_duration, args.max_tones)
    write_json(manifest_path, build_manifest(
        source, data,
        {"algorithm_ir": alg_path, "python_code": code_path, "wav": wav_path},
        {"algorithm_sha256": ir["algorithm_sha256"], "sound": sound_meta},
    ))
    print(json.dumps({"status": "PASS", "algorithm": str(alg_path), "code": str(code_path), "sound": str(wav_path), "manifest": str(manifest_path)}, ensure_ascii=False))


def build_parser():
    parser = argparse.ArgumentParser(description="JANUS Lapis: JSON -> algorithm / code / sound")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("json-to-algorithm")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(func=cmd_algorithm)

    p = sub.add_parser("json-to-code")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(func=cmd_code)

    p = sub.add_parser("json-to-sound")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--sample-rate", type=int, default=22050)
    p.add_argument("--base-duration", type=float, default=0.10)
    p.add_argument("--max-tones", type=int, default=256)
    p.set_defaults(func=cmd_sound)

    p = sub.add_parser("convert-all")
    p.add_argument("input")
    p.add_argument("--outdir", required=True)
    p.add_argument("--sample-rate", type=int, default=22050)
    p.add_argument("--base-duration", type=float, default=0.10)
    p.add_argument("--max-tones", type=int, default=256)
    p.set_defaults(func=cmd_all)

    return parser


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
