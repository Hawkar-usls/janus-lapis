#!/usr/bin/env python3
"""JANUS Lapis -> archived Rowan evidence -> Fundamentum Exact-One smoke test.

READ-ONLY FROZEN-SOURCE INTEGRATION. No Rowan account/API connection, no
submission, no credits, no biological score transferred to SAT. The smoke test
checks whether the converter can parse and execute a 5D semantic research
record; it deliberately tests that it cannot dispatch an unsupported Rowan
SAT solver operator. All exact SAT counts are independently obtained by
exponential enumeration, and cannot constitute a polynomial algorithm.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
META_COMMIT = "bb4c5552926f01cf40a9cb601aa4ad5897a2417a"
META_ROOT = (
    "https://raw.githubusercontent.com/Hawkar-usls/"
    f"janus-meta-registry/{META_COMMIT}/"
)
SOURCES = {
    "spiral": {
        "path": "registry/p_vs_np/JANUS_FIELD_PARADIGM_TRUE_5D_TRANCEPTION_REVERSE_SPIRAL_2026-10-28_v5.0.json",
        "blob_sha": "708ec77e8e4520519252dc306f49117491c1a3cb",
    },
    "rowan": {
        "path": "data/rowan/CANONICAL_STATE.json",
        "blob_sha": "57d2005b9b518986376fc2a4cbf1c326271d8c0a",
    },
    "pipeline": {
        "path": "data/rowan/health/PIPELINE_STATE.json",
        "blob_sha": None,
    },
}
MAX_SOURCE_BYTES = 120_000
SCIENTIFIC_BOUNDARY = "P_VS_NP_OPEN_NO_POLYNOMIAL_SOLVER"

def _load_converter():
    spec = importlib.util.spec_from_file_location("janus_lapis_converter", HERE / "lapis_converter.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("CONVERTER_MODULE_MISSING")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def _read_pinned(name: str) -> dict:
    info = SOURCES[name]
    url = META_ROOT + info["path"]
    if not url.startswith(META_ROOT):
        raise ValueError("NON_ALLOWLISTED_SOURCE")
    with urlopen(Request(url, headers={"User-Agent": "JANUS-LAPIS-ROWAN-PNP-SMOKE/1"}), timeout=25) as res:
        data = res.read(MAX_SOURCE_BYTES + 1)
    if not data or len(data) > MAX_SOURCE_BYTES:
        raise ValueError("SOURCE_SIZE_HOLD")
    blob_sha = _blob_sha(data)
    if info["blob_sha"] and blob_sha != info["blob_sha"]:
        raise ValueError("SOURCE_BLOB_SHA_MISMATCH_" + name)
    return json.loads(data)


def exactone_count(n: int, shifts: tuple[int, ...]) -> tuple[int, int]:
    """Exponential reference oracle; the loop performs exactly 2**n checks."""
    rows = [sum(1 << ((i+s) % n) for s in shifts) for i in range(n)]
    if len(set(shifts)) != 3:
        raise ValueError("CHECK_NOT_CUBIC")
    if any(r.bit_count() != 3 for r in rows):
        raise ValueError("CHECK_NOT_CUBIC")
    count = 0
    port_union = 0
    for assignment in range(1 << n):
        if all((assignment & row).bit_count() == 1 for row in rows):
            count += 1
            port_union |= assignment & rows[0]
    return count, port_union


def _generated_runner(converter, ir: dict) -> dict:
    # The code template comes from a trusted local converter and contains
    # JSON data only. It is not arbitrary code obtained from the uploaded JSON.
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "lapis_runner.py"
        p.write_text(converter.algorithm_to_python(ir), encoding="utf-8")
        cp = subprocess.run(
            [sys.executable, "-I", str(p)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", check=False, timeout=15,
        )
        if cp.returncode != 0:
            raise RuntimeError("GENERATED_RUNNER_FAILED:" + cp.stderr[-500:])
        return json.loads(cp.stdout)


def execute(smoke_live: bool = False) -> dict:
    converter = _load_converter()
    spiral = _read_pinned("spiral") if smoke_live else {
        "schema": "janus.5d.smoke_fixture",
        "PATH_HISTORY_SPIRAL": [{"RETURN": "EXACT_REQUIREMENT_NOT_MET"}],
        "scientific_boundary": "P_VS_NP_OPEN",
    }
    rowan = _read_pinned("rowan") if smoke_live else {
        "schema_id": "janus.rowan.observer_state.v1",
        "last_completed_mutants": 8,
        "latest_scientific_status": "EXPLORATORY_STRATIFIED_DESCRIPTIVE_ONLY",
    }
    pipeline = _read_pinned("pipeline") if smoke_live else {
        "completed_mutants": 8,
        "science_gates": {"new_billing_authorized_by_watchdog": False, "model_production_promotion": False},
        "credit_cap_violations": [],
    }
    assert spiral.get("schema", "").startswith("janus.")
    assert rowan.get("schema_id") == "janus.rowan.observer_state.v1"
    assert rowan.get("last_completed_mutants") == 8
    assert pipeline.get("completed_mutants") == 8
    gates = pipeline.get("science_gates", {})
    assert gates.get("new_billing_authorized_by_watchdog") is False
    assert gates.get("model_production_promotion") is False
    assert pipeline.get("credit_cap_violations") == []
    if smoke_live:
        assert len(spiral.get("INLINE_5D_BRANCHES_IN_LOGICAL_ANCHOR_ORDER", [])) == 22

    ir = converter.json_to_algorithm(spiral)
    assert ir["algorithm"]["mode"] == "heuristic_translation"
    assert ir["scientific_boundary"]["heuristic_translation_is_proof"] is False
    assert all(step.get("operator") == "ANNOTATE" for step in ir["algorithm"]["steps"])
    run = _generated_runner(converter, ir)
    assert run["status"] == "PASS"
    assert len(run["trace"]) == len(ir["algorithm"]["steps"])

    # Negative control: an explicitly requested Rowan SAT-solving operation
    # must NOT silently translate to a valid chemistry job or a fake theorem.
    unsupported = {"$lapis": {"algorithm": {
        "name": "rowan_solve_linear_cubic_xsat",
        "steps": [{"op": "ROWAN_SOLVE_EXACTONE", "args": {
            "scientific_domain": "complexity_theory",
            "provider": "Rowan",
            "allow_credit_spend": False,
        }}],
    }}}
    explicit_ir = converter.json_to_algorithm(unsupported)
    unsupported_result = _generated_runner(converter, explicit_ir)
    assert unsupported_result["status"] == "OPEN"
    assert unsupported_result["reason"] == "UNKNOWN_OPERATOR"
    assert unsupported_result.get("operator") == "ROWAN_SOLVE_EXACTONE"

    cases = [
        {"name": "n9_unsat", "n": 9, "shifts": (0,1,3), "expected": 0},
        {"name": "n12_unsat", "n": 12, "shifts": (0,1,3), "expected": 0},
        {"name": "n12_sat", "n": 12, "shifts": (0,1,5), "expected": 3},
        {"name": "n15_unsat", "n": 15, "shifts": (0,1,4), "expected": 0},
        {"name": "n15_sat", "n": 15, "shifts": (0,1,5), "expected": 3},
    ]
    out = []
    for case in cases:
        count, support = exactone_count(case["n"], case["shifts"])
        assert count == case["expected"]
        out.append({
            "name": case["name"], "n": case["n"], "count": count,
            "support_c0_variable_bitmask": support,
            "states_exhaustively_enumerated": 1 << case["n"],
            "method": "EXPONENTIAL_REFERENCE_NOT_NEW_SOLVER",
        })
    return {
        "schema": "janus.lapis_rowan_pnp_readonly_integration_test.v1",
        "test_status": "PASS_EXPECTED_LIMITS",
        "mode": "PINNED_META_REGISTRY_SOURCES" if smoke_live else "OFFLINE_FIXTURES",
        "source_meta_commit": META_COMMIT if smoke_live else None,
        "converter": {
            "name": "janus-lapis",
            "translation_mode": ir["algorithm"]["mode"],
            "algorithm_sha256": ir["algorithm_sha256"],
            "generated_runner_status": run["status"],
            "annotation_steps": len(ir["algorithm"]["steps"]),
            "formal_5d_tranception_run": False,
        },
        "rowan": {
            "source": "ARCHIVED_META_REGISTRY_PROVIDER_RECEIPTS_NOT_LIVE_ROWAN_JOB",
            "completed_bbc1_mutants": rowan["last_completed_mutants"],
            "science_status": rowan.get("latest_scientific_status"),
            "provider_workflow_for_exactone": "UNSUPPORTED",
            "attempted_submission": False,
            "new_jobs": 0,
            "credits_spent_by_test": 0,
            "unauthorized_operator": unsupported_result.get("operator"),
            "unauthorized_operator_status": unsupported_result["status"],
            "unauthorized_operator_reason": unsupported_result["reason"],
        },
        "exactone_controls": out,
        "algorithmic_result": "NO_NEW_PROVEN_SOLVER_OR_SUPPORT_C_CONSTRUCTION",
        "scientific_boundary": SCIENTIFIC_BOUNDARY,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pinned-source-smoke", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    result = execute(smoke_live=args.pinned_source_smoke)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
