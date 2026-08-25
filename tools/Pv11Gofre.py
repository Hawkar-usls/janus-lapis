#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pv11Gofre — OdontoForge-derived transient-state recovery gate for Pv11.

Purpose:
  Convert the abstract OdontoForge cycle
    ENTER -> GROW -> TEST -> CRYSTALLIZE -> EXIT / REGENERATE
  into an evidence-disciplined biological state machine for the
  anhydrobiotic Pv11 cell line of Polypedilum vanderplanki.

Scientific boundary:
  * This is a hypothesis/test harness, not a biological mechanism proof.
  * Literature observations and raw-expression measurements remain distinct.
  * A repair-first ordering is not equivalent to proof that repair causally
    gates the first S phase.
  * Private/unpublished observations are forbidden from public fixtures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

VERSION = "0.1.0-pv11gofre-public-evidence-gate"


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_obj(obj) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


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
    odonto_cycle: List[str]
    pv11_cycle: List[str]
    earliest_repair_evidence_h: Optional[float]
    latest_repair_evidence_h: Optional[float]
    first_direct_s_phase_h: Optional[float]
    first_direct_population_proliferation_h: Optional[float]
    timecourse_r0_r72_available: bool
    repair_first_precursor_supported: bool
    causal_cell_cycle_release_proven: bool
    gate_status: str
    missing_evidence: List[str]
    forbidden_inference_triggered: bool
    notes: List[str]


PUBLIC_FIXTURE: List[Observation] = [
    Observation(
        "R0", 0.0, "state", "anhydrobiosis", "AMETABOLIC_BASELINE",
        "published_protocol", True, "Yamada2020_DRA008948",
        "R0 is the desiccated state before rehydration in the published RNA-seq time course.",
    ),
    Observation(
        "R3", 3.0, "DNA_REPAIR", "Pv.07646_RAD16_like", "UPREGULATED",
        "CAGE_seq_plus_RT_qPCR", True, "Yamada2018_SciRep",
        "Pv.07646 is strongly induced at R3 and has RAD16-like domain similarity; authors propose a DNA-repair role.",
    ),
    Observation(
        "R24", 24.0, "DNA_REPAIR", "Pv.10801_XPA_like", "UPREGULATED",
        "CAGE_seq_DEG", True, "Yamada2018_SciRep",
        "XPA-like Pv.10801 is significantly upregulated in R24 versus D10d.",
    ),
    Observation(
        "R24", 24.0, "DNA_REPAIR", "Pv.01957_CCNH_like", "UPREGULATED",
        "CAGE_seq_DEG", True, "Yamada2018_SciRep",
        "CCNH-like Pv.01957 is significantly upregulated in R24 versus D10d.",
    ),
    Observation(
        "R0_R72", 72.0, "TIMECOURSE", "DRA008948", "AVAILABLE_TRIPLICATE_SERIES",
        "RNA_seq_accession", True, "DRA008948",
        "Published Pv11 series: T0,T12,T24,T36,T48,R0,R3,R12,R24,R72, biological triplicate.",
    ),
    Observation(
        "D1_D7", 24.0, "PROLIFERATION", "population_cell_count", "MEASURED_DAY_SCALE",
        "published_cell_counts", True, "Mazin2018_PNAS_Pv11_assay",
        "Population proliferation was assessed after rehydration on a day-scale; this is not a first-S-phase measurement.",
    ),
]

ODONTO_CYCLE = [
    "ENTER_TRANSIENT_STATE",
    "GROW_OR_ACCUMULATE_STRUCTURE",
    "TEST_LOCAL_CONSISTENCY_OR_VIABILITY",
    "CRYSTALLIZE_IF_VERIFIED",
    "EXIT_IF_TERMINAL",
    "REGENERATE_OR_REPLACE_IF_FAILED",
    "PRESERVE_LINEAGE_AND_COST",
]

PV11_CYCLE = [
    "REHYDRATE_ENTER_RECOVERY",
    "ACCUMULATE_REPAIR_AND_RECOVERY_ACTIVITY",
    "TEST_GENOME_INTEGRITY_AND_CELL_CYCLE_COMPETENCE",
    "CRYSTALLIZE_STABLE_RECOVERED_STATE_IF_SUPPORTED",
    "RELEASE_CELL_CYCLE_ONLY_IF_DIRECTLY_MEASURED",
    "REPAIR_OR_REPLACE_FAILED_STATE",
    "PRESERVE_TIMEPOINT_REPLICATE_PROVENANCE",
]


def analyse(observations: List[Observation]) -> GateResult:
    public_only = all(o.public for o in observations)
    forbidden = not public_only

    repair_times = sorted(
        o.hours_after_rehydration
        for o in observations
        if o.layer == "DNA_REPAIR" and o.state == "UPREGULATED" and o.public
    )
    s_phase_times = sorted(
        o.hours_after_rehydration
        for o in observations
        if o.layer == "S_PHASE" and o.evidence_type in {"BrdU", "EdU", "direct_DNA_synthesis"} and o.public
    )
    proliferation_times = sorted(
        o.hours_after_rehydration
        for o in observations
        if o.layer == "PROLIFERATION" and o.public
    )
    timecourse = any(
        o.feature == "DRA008948" and o.state == "AVAILABLE_TRIPLICATE_SERIES" and o.public
        for o in observations
    )

    earliest_repair = min(repair_times) if repair_times else None
    latest_repair = max(repair_times) if repair_times else None
    first_s = min(s_phase_times) if s_phase_times else None
    first_prolif = min(proliferation_times) if proliferation_times else None

    precursor = bool(repair_times and timecourse)
    causal = bool(first_s is not None and earliest_repair is not None and earliest_repair < first_s)

    missing = []
    if not timecourse:
        missing.append("R0/R3/R12/R24/R72 expression time course")
    if first_s is None:
        missing.append("direct public first-S-phase measurement after rehydration")
    missing.append("raw DRA008948 run-to-condition manifest + expression matrix imported into this engine")
    missing.append("prospective perturbation showing repair-state manipulation shifts cell-cycle restart")

    if forbidden:
        status = "REJECT_PRIVATE_OR_NONPUBLIC_INPUT"
    elif causal:
        status = "ORDERING_OBSERVED_CAUSAL_GATE_STILL_OPEN"
    elif precursor:
        status = "REPAIR_FIRST_PRECURSOR_SUPPORTED_CELL_CYCLE_GATE_OPEN"
    else:
        status = "INSUFFICIENT_PUBLIC_EVIDENCE"

    fixture = [asdict(o) for o in observations]
    return GateResult(
        engine="Pv11Gofre",
        version=VERSION,
        fixture_sha256=sha256_obj(fixture),
        public_only=public_only,
        odonto_cycle=ODONTO_CYCLE,
        pv11_cycle=PV11_CYCLE,
        earliest_repair_evidence_h=earliest_repair,
        latest_repair_evidence_h=latest_repair,
        first_direct_s_phase_h=first_s,
        first_direct_population_proliferation_h=first_prolif,
        timecourse_r0_r72_available=timecourse,
        repair_first_precursor_supported=precursor,
        causal_cell_cycle_release_proven=False,
        gate_status=status,
        missing_evidence=missing,
        forbidden_inference_triggered=forbidden,
        notes=[
            "CRYSTALLIZE is bookkeeping for a supported stable state, not literal mineralization.",
            "Population proliferation timing must not be substituted for first-S-phase timing.",
            "No private BrdU observation is present in the public fixture.",
            "The next decisive run requires DRA008948 bytes and a frozen repair/licensing/S-phase/mitosis panel.",
        ],
    )


def load_observations(path: Path) -> List[Observation]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["observations"] if isinstance(data, dict) else data
    return [Observation(**row) for row in rows]


def selftest() -> None:
    r = analyse(PUBLIC_FIXTURE)
    assert r.public_only
    assert r.earliest_repair_evidence_h == 3.0
    assert r.latest_repair_evidence_h == 24.0
    assert r.first_direct_s_phase_h is None
    assert r.timecourse_r0_r72_available
    assert r.repair_first_precursor_supported
    assert not r.causal_cell_cycle_release_proven
    assert r.gate_status == "REPAIR_FIRST_PRECURSOR_SUPPORTED_CELL_CYCLE_GATE_OPEN"

    poisoned = PUBLIC_FIXTURE + [
        Observation("PRIVATE", 48.0, "S_PHASE", "private_marker", "DETECTED", "BrdU", False, "PRIVATE")
    ]
    rp = analyse(poisoned)
    assert rp.gate_status == "REJECT_PRIVATE_OR_NONPUBLIC_INPUT"
    assert rp.forbidden_inference_triggered
    print("PASS: Pv11Gofre public-evidence selftest")


def main() -> None:
    p = argparse.ArgumentParser(description="Pv11Gofre public-evidence recovery gate")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    run = sub.add_parser("run")
    run.add_argument("--input", type=Path)
    run.add_argument("--out", type=Path, default=Path("pv11gofre_report.json"))
    args = p.parse_args()

    if args.cmd == "selftest":
        selftest()
        return

    obs = load_observations(args.input) if args.input else PUBLIC_FIXTURE
    result = analyse(obs)
    payload = {
        "result": asdict(result),
        "observations": [asdict(o) for o in obs],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
