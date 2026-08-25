#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pv11Gofre — OdontoForge-derived transient-state recovery gate for Pv11.

Scientific boundary:
* hypothesis/test harness, not a mechanism proof;
* public literature and numerical matrix evidence stay separate;
* population growth != first S phase;
* DEG workbook != per-sample trajectory matrix unless its schema proves that;
* unpublished/private observations are excluded from public fixtures.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

VERSION = "0.2.0-pv11gofre-manifest-matrix-gate"
RECOVERY_CONDITIONS = ("R0", "R3", "R12", "R24", "R72")


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_obj(obj) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


@dataclass(frozen=True)
class Observation:
    timepoint: str
    hours_after_rehydration: float
    layer: str
    feature: str
    state: str
    evidence_type: str
    public: bool
    source_id: str
    note: str = ""


@dataclass
class GateResult:
    engine: str
    version: str
    fixture_sha256: str
    public_only: bool
    earliest_repair_evidence_h: Optional[float]
    latest_repair_evidence_h: Optional[float]
    first_direct_s_phase_h: Optional[float]
    earliest_population_assay_time_h: Optional[float]
    proliferation_onset_h: Optional[float]
    timecourse_r0_r72_available: bool
    repair_first_precursor_supported: bool
    causal_cell_cycle_release_proven: bool
    gate_status: str
    missing_evidence: List[str]


@dataclass
class ManifestGateResult:
    engine: str
    version: str
    manifest_sha256: str
    ledger_sha256: str
    manifest_rows: int
    recovery_rows: int
    conditions: dict
    exact_triplicate_manifest: bool
    explicit_metadata_binding: bool
    s1_degs_byte_record_present: bool
    s1_degs_bytes: Optional[int]
    s1_degs_sha256: Optional[str]
    matrix_bytes_supplied: bool
    matrix_sha256: Optional[str]
    matrix_schema_validated: bool
    trajectory_run_permitted: bool
    gate_status: str
    missing_evidence: List[str]
    notes: List[str]


PUBLIC_FIXTURE: List[Observation] = [
    Observation("R0", 0.0, "state", "anhydrobiosis", "AMETABOLIC_BASELINE",
                "published_protocol", True, "Yamada2020_DRA008948"),
    Observation("R3", 3.0, "DNA_REPAIR", "Pv.07646_RAD16_like", "UPREGULATED",
                "CAGE_seq_plus_RT_qPCR", True, "Yamada2018_SciRep"),
    Observation("R24", 24.0, "DNA_REPAIR", "Pv.10801_XPA_like", "UPREGULATED",
                "CAGE_seq_DEG", True, "Yamada2018_SciRep"),
    Observation("R24", 24.0, "DNA_REPAIR", "Pv.01957_CCNH_like", "UPREGULATED",
                "CAGE_seq_DEG", True, "Yamada2018_SciRep"),
    Observation("R0_R72", 72.0, "TIMECOURSE", "DRA008948", "AVAILABLE_TRIPLICATE_SERIES",
                "RNA_seq_accession", True, "DRA008948"),
    Observation("D1_D7", 24.0, "PROLIFERATION", "population_cell_count", "MEASURED_DAY_SCALE",
                "published_cell_counts", True, "Mazin2018_PNAS_Pv11_assay"),
]


def analyse(observations: List[Observation]) -> GateResult:
    public_only = all(o.public for o in observations)
    repair_times = sorted(o.hours_after_rehydration for o in observations
                          if o.layer == "DNA_REPAIR" and o.state == "UPREGULATED" and o.public)
    s_phase_times = sorted(o.hours_after_rehydration for o in observations
                           if o.layer == "S_PHASE" and o.evidence_type in
                           {"BrdU", "EdU", "direct_DNA_synthesis"} and o.public)
    proliferation_times = sorted(o.hours_after_rehydration for o in observations
                                 if o.layer == "PROLIFERATION" and o.public)
    timecourse = any(o.feature == "DRA008948" and o.state == "AVAILABLE_TRIPLICATE_SERIES"
                     and o.public for o in observations)
    earliest_repair = min(repair_times) if repair_times else None
    latest_repair = max(repair_times) if repair_times else None
    first_s = min(s_phase_times) if s_phase_times else None
    first_assay = min(proliferation_times) if proliferation_times else None
    precursor = bool(repair_times and timecourse)
    missing = []
    if first_s is None:
        missing.append("direct public first-S-phase measurement after rehydration")
    missing.append("numerical R0/R3/R12/R24/R72 expression matrix with provenance")
    missing.append("prospective perturbation for a causal-release claim")
    if not public_only:
        status = "REJECT_PRIVATE_OR_NONPUBLIC_INPUT"
    elif precursor:
        status = "REPAIR_FIRST_PRECURSOR_SUPPORTED_CELL_CYCLE_GATE_OPEN"
    else:
        status = "INSUFFICIENT_PUBLIC_EVIDENCE"
    return GateResult(
        "Pv11Gofre", VERSION, sha256_obj([asdict(o) for o in observations]), public_only,
        earliest_repair, latest_repair, first_s, first_assay, None, timecourse, precursor,
        False, status, missing,
    )


def read_csv(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def validate_manifest(manifest_path: Path, ledger_path: Path,
                      matrix_path: Optional[Path] = None) -> ManifestGateResult:
    rows = read_csv(manifest_path)
    ledger = read_csv(ledger_path)
    manifest_sha = sha256_file(manifest_path)
    ledger_sha = sha256_file(ledger_path)
    conditions = {}
    recovery_rows = []
    explicit = True
    for condition in RECOVERY_CONDITIONS:
        selected = [r for r in rows if r.get("condition") == condition]
        recovery_rows.extend(selected)
        conditions[condition] = {
            "runs": [r.get("run_accession") for r in selected],
            "experiments": [r.get("experiment_accession") for r in selected],
            "samples": [r.get("sample_accession") for r in selected],
            "replicates": [r.get("sample_name") for r in selected],
        }
        explicit = explicit and all(r.get("condition_binding") == "EXPLICIT_METADATA_TOKEN"
                                    for r in selected)
    exact_triplicate = all(len(conditions[c]["runs"]) == 3 for c in RECOVERY_CONDITIONS)
    exact_triplicate = exact_triplicate and len({r.get("run_accession") for r in recovery_rows}) == 15

    s1 = next((r for r in ledger if "s003" in (r.get("name") or "") and
               "degs" in (r.get("name") or "").lower()), None)
    s1_present = s1 is not None and bool(s1.get("sha256")) and bool(s1.get("bytes"))
    s1_bytes = int(s1["bytes"]) if s1_present else None
    s1_sha = s1.get("sha256") if s1_present else None

    matrix_supplied = bool(matrix_path and matrix_path.exists())
    matrix_sha = sha256_file(matrix_path) if matrix_supplied else None
    # We deliberately do not infer schema from file name or from a DEG ledger entry.
    matrix_schema_validated = False
    trajectory_permitted = exact_triplicate and explicit and matrix_supplied and matrix_schema_validated

    missing = []
    if not exact_triplicate:
        missing.append("exact R0/R3/R12/R24/R72 x3 manifest")
    if not explicit:
        missing.append("explicit condition binding")
    if not s1_present:
        missing.append("byte-provenance record for PLOS S1 Data")
    if not matrix_supplied:
        missing.append("accessible numerical expression-matrix bytes")
    if matrix_supplied and not matrix_schema_validated:
        missing.append("validated matrix schema proving per-sample/timepoint numerical values")

    if not exact_triplicate or not explicit:
        status = "MANIFEST_FAIL"
    elif not matrix_supplied:
        status = "MANIFEST_PASS_BYTE_PROVENANCE_PASS_MATRIX_BYTES_REQUIRED"
    else:
        status = "MATRIX_BYTES_PRESENT_SCHEMA_VALIDATION_REQUIRED"

    return ManifestGateResult(
        engine="Pv11Gofre",
        version=VERSION,
        manifest_sha256=manifest_sha,
        ledger_sha256=ledger_sha,
        manifest_rows=len(rows),
        recovery_rows=len(recovery_rows),
        conditions=conditions,
        exact_triplicate_manifest=exact_triplicate,
        explicit_metadata_binding=explicit,
        s1_degs_byte_record_present=s1_present,
        s1_degs_bytes=s1_bytes,
        s1_degs_sha256=s1_sha,
        matrix_bytes_supplied=matrix_supplied,
        matrix_sha256=matrix_sha,
        matrix_schema_validated=matrix_schema_validated,
        trajectory_run_permitted=trajectory_permitted,
        gate_status=status,
        missing_evidence=missing,
        notes=[
            "S1 Data is recorded as a DEG workbook; it is not promoted to a trajectory matrix without schema inspection.",
            "The exact run-to-condition manifest is a provenance gate, not an expression result.",
            "No private/unpublished observation is used by this gate.",
            "No repair->cell-cycle temporal ordering is claimed until numerical trajectories are available.",
        ],
    )


def selftest() -> None:
    r = analyse(PUBLIC_FIXTURE)
    assert r.public_only and r.earliest_repair_evidence_h == 3.0
    assert r.latest_repair_evidence_h == 24.0 and r.first_direct_s_phase_h is None
    assert r.proliferation_onset_h is None and r.repair_first_precursor_supported
    poisoned = PUBLIC_FIXTURE + [Observation("PRIVATE", 48.0, "S_PHASE", "private_marker",
                                             "DETECTED", "BrdU", False, "PRIVATE")]
    assert analyse(poisoned).gate_status == "REJECT_PRIVATE_OR_NONPUBLIC_INPUT"
    print("PASS: Pv11Gofre public-evidence selftest")


def main() -> None:
    p = argparse.ArgumentParser(description="Pv11Gofre evidence-disciplined recovery gate")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    run = sub.add_parser("run")
    run.add_argument("--out", type=Path, default=Path("pv11gofre_report.json"))
    mg = sub.add_parser("manifest-gate")
    mg.add_argument("--manifest", type=Path, required=True)
    mg.add_argument("--ledger", type=Path, required=True)
    mg.add_argument("--matrix", type=Path)
    mg.add_argument("--out", type=Path, default=Path("pv11gofre_manifest_gate.json"))
    args = p.parse_args()
    if args.cmd == "selftest":
        selftest(); return
    if args.cmd == "run":
        payload = {"result": asdict(analyse(PUBLIC_FIXTURE)),
                   "observations": [asdict(o) for o in PUBLIC_FIXTURE]}
    else:
        payload = {"result": asdict(validate_manifest(args.manifest, args.ledger, args.matrix))}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(json.dumps(payload["result"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
