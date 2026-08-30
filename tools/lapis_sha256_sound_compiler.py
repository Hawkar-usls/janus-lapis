#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compile the TRUMP SHA-256 JSON positive control after exact sound transport.

Route:
    SHA-256 JSON -> exact WAV carrier -> recovered JSON -> typed SHA-256 IR -> Python

This is a schema-aware positive-control compiler, not a generic theorem compiler.
It fails closed when the recovered JSON does not match the supported SHA-256
reference-machine contract.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping

HERE = Path(__file__).resolve().parent
ROUNDTRIP_PATH = HERE / "lapis_sound_roundtrip.py"
SPEC = importlib.util.spec_from_file_location("janus_lapis_sound_roundtrip", ROUNDTRIP_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load lapis_sound_roundtrip.py")
ROUNDTRIP = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ROUNDTRIP
SPEC.loader.exec_module(ROUNDTRIP)
BASE = ROUNDTRIP.BASE

IR_SCHEMA = "janus.lapis.sha256.executable_algorithm_ir.v1"
SUPPORTED_SOURCE_SCHEMA = "janus.trump.reference.sha256_json_machine.v1"


class SHACompilerError(ValueError):
    pass


def _hex_words(values: Any, expected: int, field: str) -> list[int]:
    if not isinstance(values, list) or len(values) != expected:
        raise SHACompilerError(f"{field}_COUNT_MISMATCH")
    out = []
    for value in values:
        if not isinstance(value, str) or len(value) != 8:
            raise SHACompilerError(f"{field}_BAD_HEX_WORD")
        try:
            n = int(value, 16)
        except ValueError as exc:
            raise SHACompilerError(f"{field}_BAD_HEX_WORD") from exc
        if not 0 <= n <= 0xFFFFFFFF:
            raise SHACompilerError(f"{field}_OUT_OF_UINT32")
        out.append(n)
    return out


def validate_sha_spec(data: Any) -> Dict[str, Any]:
    if not isinstance(data, Mapping):
        raise SHACompilerError("SOURCE_NOT_OBJECT")
    if data.get("schema") != SUPPORTED_SOURCE_SCHEMA:
        raise SHACompilerError("UNSUPPORTED_SOURCE_SCHEMA")

    typed = data.get("typed_semantics")
    required_typed = {
        "word_type": "uint32",
        "arithmetic": "mod_2^32",
        "shift": "logical_right",
        "rotate": "circular_right",
        "byte_order": "big_endian",
        "block_bits": 512,
        "digest_bits": 256,
        "rounds_per_block": 64,
    }
    if not isinstance(typed, Mapping) or any(typed.get(k) != v for k, v in required_typed.items()):
        raise SHACompilerError("TYPED_SEMANTICS_MISMATCH")

    initial = _hex_words(data.get("initial_hash_words_hex"), 8, "INITIAL_HASH")
    constants = _hex_words(data.get("round_constants_hex"), 64, "ROUND_CONSTANTS")

    functions = data.get("functions")
    expected_functions = {
        "Ch(x,y,z)": "(x AND y) XOR ((NOT x) AND z)",
        "Maj(x,y,z)": "(x AND y) XOR (x AND z) XOR (y AND z)",
        "Sigma0(x)": "ROTR2(x) XOR ROTR13(x) XOR ROTR22(x)",
        "Sigma1(x)": "ROTR6(x) XOR ROTR11(x) XOR ROTR25(x)",
        "sigma0(x)": "ROTR7(x) XOR ROTR18(x) XOR SHR3(x)",
        "sigma1(x)": "ROTR17(x) XOR ROTR19(x) XOR SHR10(x)",
    }
    if not isinstance(functions, Mapping) or dict(functions) != expected_functions:
        raise SHACompilerError("FUNCTION_CONTRACT_MISMATCH")

    pcner = data.get("pcner_positive_control")
    if not isinstance(pcner, Mapping):
        raise SHACompilerError("PCNER_CONTRACT_MISSING")
    if pcner.get("POLY_FIND", {}).get("candidate_count") != 1:
        raise SHACompilerError("POLY_FIND_NOT_UNIQUE")
    if pcner.get("POLY_HOLD", {}).get("working_words_upper_bound") != 72:
        raise SHACompilerError("POLY_HOLD_BOUND_MISMATCH")
    if pcner.get("POLY_ADVANCE", {}).get("rank_terminal") != 0:
        raise SHACompilerError("POLY_ADVANCE_TERMINAL_MISMATCH")

    boundary = data.get("scientific_boundary")
    if not isinstance(boundary, Mapping):
        raise SHACompilerError("SCIENTIFIC_BOUNDARY_MISSING")
    if boundary.get("SAT_transfer_claimed") is not False:
        raise SHACompilerError("SAT_TRANSFER_FIREWALL_MISSING")
    if boundary.get("P_equals_NP_proved") is not False or boundary.get("P_VS_NP") != "OPEN":
        raise SHACompilerError("P_VS_NP_FIREWALL_MISSING")

    return {
        "initial_words": initial,
        "round_constants": constants,
        "known_test_vectors": data.get("known_test_vectors", []),
        "pcner": pcner,
        "source_id": data.get("id"),
    }


def sha256_algorithm_ir(data: Any, carrier: Mapping[str, Any]) -> Dict[str, Any]:
    v = validate_sha_spec(data)
    ir = {
        "schema": IR_SCHEMA,
        "source_schema": SUPPORTED_SOURCE_SCHEMA,
        "source_id": v["source_id"],
        "carrier_provenance": dict(carrier),
        "machine": {
            "word_bits": 32,
            "block_bits": 512,
            "digest_bits": 256,
            "rounds_per_block": 64,
            "initial_words": v["initial_words"],
            "round_constants": v["round_constants"],
            "operators": ["ROTR", "SHR", "AND", "XOR", "NOT", "ADD32", "LOAD_BE32", "STORE_BE32"],
            "schedule": "W[0..15]=block words; W[t]=sigma1(W[t-2])+W[t-7]+sigma0(W[t-15])+W[t-16] mod 2^32",
            "round": "T1/T2 canonical SHA-256 compression transition",
            "finalize": "H[i]=(H[i]+working[i]) mod 2^32",
        },
        "progress": {
            "rank": "mu = 64*(B-current_block_index) - current_round_index",
            "strict_descent": "mu_next = mu - 1",
            "terminal": 0,
        },
        "resource_bounds": {
            "working_words_upper_bound": 72,
            "candidate_next_actions_per_round": 1,
            "rounds": "64*B = O(N)",
        },
        "known_test_vectors": v["known_test_vectors"],
        "scientific_boundary": {
            "schema_aware_positive_control_only": True,
            "sound_is_carrier_not_oracle": True,
            "SHA256_POLY_ROUTE_implies_SAT_POLY_ROUTE": False,
            "universal_GPEI_for_SAT_proved": False,
            "P_equals_NP_proved": False,
            "P_VS_NP": "OPEN",
        },
    }
    ir["algorithm_sha256"] = hashlib.sha256(BASE.canonical_json_bytes(ir)).hexdigest()
    return ir


def python_from_ir(ir: Mapping[str, Any]) -> str:
    if ir.get("schema") != IR_SCHEMA:
        raise SHACompilerError("UNSUPPORTED_IR_SCHEMA")
    machine = ir.get("machine", {})
    initial = machine.get("initial_words")
    constants = machine.get("round_constants")
    if not isinstance(initial, list) or len(initial) != 8 or not isinstance(constants, list) or len(constants) != 64:
        raise SHACompilerError("IR_CONSTANTS_INVALID")

    return f'''#!/usr/bin/env python3
# Generated by JANUS Lapis SHA-256 sound compiler.
# Source transport: exact WAV carrier; sound adds no semantic authority.

from __future__ import annotations
import hashlib
import json

MASK = 0xffffffff
H0 = {repr([int(x) for x in initial])}
K = {repr([int(x) for x in constants])}
ALGORITHM_SHA256 = {ir.get("algorithm_sha256")!r}


def rotr(x, n):
    x &= MASK
    return ((x >> n) | ((x << (32-n)) & MASK)) & MASK


def ch(x, y, z):
    return ((x & y) ^ ((~x) & z)) & MASK


def maj(x, y, z):
    return ((x & y) ^ (x & z) ^ (y & z)) & MASK


def big0(x): return rotr(x,2) ^ rotr(x,13) ^ rotr(x,22)
def big1(x): return rotr(x,6) ^ rotr(x,11) ^ rotr(x,25)
def small0(x): return rotr(x,7) ^ rotr(x,18) ^ (x >> 3)
def small1(x): return rotr(x,17) ^ rotr(x,19) ^ (x >> 10)


def pad(data: bytes) -> bytes:
    bit_len = len(data) * 8
    out = bytearray(data)
    out.append(0x80)
    while len(out) % 64 != 56:
        out.append(0)
    out.extend(bit_len.to_bytes(8, 'big'))
    return bytes(out)


def execute(data: bytes, round_receipts: bool=False):
    padded = pad(data)
    blocks = len(padded) // 64
    H = list(H0)
    receipts = []
    initial_rank = 64 * blocks
    round_global = 0
    max_words = 0

    for bi in range(blocks):
        block = padded[bi*64:(bi+1)*64]
        W = [int.from_bytes(block[i:i+4], 'big') for i in range(0,64,4)]
        for t in range(16,64):
            W.append((small1(W[t-2]) + W[t-7] + small0(W[t-15]) + W[t-16]) & MASK)
        a,b,c,d,e,f,g,h = H
        max_words = max(max_words, len(W) + 8)
        for t in range(64):
            mu_before = initial_rank - round_global
            T1 = (h + big1(e) + ch(e,f,g) + K[t] + W[t]) & MASK
            T2 = (big0(a) + maj(a,b,c)) & MASK
            a,b,c,d,e,f,g,h = (T1+T2)&MASK, a, b, c, (d+T1)&MASK, e, f, g
            round_global += 1
            mu_after = initial_rank - round_global
            if round_receipts:
                receipts.append({{'block':bi,'round':t,'mu_before':mu_before,'mu_after':mu_after}})
        work = [a,b,c,d,e,f,g,h]
        H = [(x+y)&MASK for x,y in zip(H, work)]

    digest = b''.join(x.to_bytes(4,'big') for x in H).hex()
    return {{
        'terminal':'LAPIS_SHA256_SOUND_COMPILED_PASS',
        'digest_hex':digest,
        'hashlib_digest_hex':hashlib.sha256(data).hexdigest(),
        'exact_match':digest == hashlib.sha256(data).hexdigest(),
        'padded_blocks':blocks,
        'rounds_executed':round_global,
        'initial_rank':initial_rank,
        'final_rank':initial_rank-round_global,
        'rank_strict_unit_descent': all(r['mu_after']==r['mu_before']-1 for r in receipts) if round_receipts else True,
        'max_working_words_observed':max_words,
        'declared_working_words_upper_bound':72,
        'candidate_next_action_count_per_round':1,
        'algorithm_sha256':ALGORITHM_SHA256,
        'round_receipts':receipts,
        'scientific_boundary':{{
            'SAT_transfer_claimed':False,
            'universal_GPEI_for_SAT_proved':False,
            'P_equals_NP_proved':False,
            'P_VS_NP':'OPEN'
        }}
    }}


def selftest():
    vectors = {json.dumps(ir.get("known_test_vectors", []), ensure_ascii=False)}
    passed = 0
    for row in vectors:
        data = row['message_utf8'].encode('utf-8')
        got = execute(data)
        if not got['exact_match'] or got['digest_hex'] != row['digest_hex']:
            raise AssertionError(row)
        passed += 1
    return {{'terminal':'LAPIS_SHA256_SOUND_COMPILER_SELFTEST_PASS','vectors_passed':passed,'P_VS_NP':'OPEN'}}


if __name__ == '__main__':
    print(json.dumps(selftest(), indent=2, sort_keys=True))
'''


def compile_sound(path: Path, *, repeat: int = ROUNDTRIP.DEFAULT_REPEAT) -> tuple[Dict[str, Any], str]:
    data, carrier = ROUNDTRIP.exact_wav_to_json(path, repeat=repeat)
    ir = sha256_algorithm_ir(data, carrier)
    code = python_from_ir(ir)
    return ir, code


def selftest_sound(path: Path, *, repeat: int = ROUNDTRIP.DEFAULT_REPEAT) -> Dict[str, Any]:
    ir, code = compile_sound(path, repeat=repeat)
    ns: Dict[str, Any] = {}
    exec(compile(code, "<lapis-sha256-sound-generated>", "exec"), ns, ns)
    result = ns["selftest"]()
    abc = ns["execute"](b"abc", round_receipts=True)
    if result["vectors_passed"] != 3:
        raise AssertionError("EXPECTED_3_VECTORS")
    if not abc["exact_match"] or abc["rounds_executed"] != 64 or abc["final_rank"] != 0:
        raise AssertionError("ABC_ROUTE_FAILED")
    if not abc["rank_strict_unit_descent"] or abc["max_working_words_observed"] > 72:
        raise AssertionError("PCNER_CONTROL_FAILED")
    return {
        "terminal": "LAPIS_SHA256_JSON_SOUND_ALGORITHM_CODE_SELFTEST_PASS",
        "vectors_passed": result["vectors_passed"],
        "abc_rounds": abc["rounds_executed"],
        "abc_rank_transitions_verified": len(abc["round_receipts"]),
        "abc_exact_match": abc["exact_match"],
        "max_working_words_observed": abc["max_working_words_observed"],
        "algorithm_sha256": ir["algorithm_sha256"],
        "carrier_payload_sha256": ir["carrier_provenance"]["payload_sha256"],
        "P_VS_NP": "OPEN",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile SHA-256 algorithm from an exact Lapis sound carrier")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("sound-to-sha256-algorithm")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--repeat", type=int, default=ROUNDTRIP.DEFAULT_REPEAT)

    p = sub.add_parser("sound-to-sha256-code")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--repeat", type=int, default=ROUNDTRIP.DEFAULT_REPEAT)

    p = sub.add_parser("selftest-sound")
    p.add_argument("input")
    p.add_argument("--repeat", type=int, default=ROUNDTRIP.DEFAULT_REPEAT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    path = Path(args.input)
    if args.command == "sound-to-sha256-algorithm":
        ir, _ = compile_sound(path, repeat=args.repeat)
        BASE.write_json(Path(args.output), ir)
        print(json.dumps({"status":"PASS","output":args.output,"algorithm_sha256":ir["algorithm_sha256"]}))
    elif args.command == "sound-to-sha256-code":
        _, code = compile_sound(path, repeat=args.repeat)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(code, encoding="utf-8")
        print(json.dumps({"status":"PASS","output":args.output,"sha256":hashlib.sha256(output.read_bytes()).hexdigest()}))
    elif args.command == "selftest-sound":
        print(json.dumps(selftest_sound(path, repeat=args.repeat), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
