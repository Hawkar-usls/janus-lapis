#!/usr/bin/env python3
"""Offline Rowan -> Lapis -> Fundamentum typed translator, v1.

Accept only known JANUS Rowan *receipt* schemas. No Rowan client import,
network, secrets, arbitrary-code execution, external writeback, or spending.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path

from lapis_converter import json_to_algorithm

SCHEMA = "janus.lapis.rowan_fundamentum_candidate.v1"
MAX_INPUT_BYTES = 512_000
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MUTATION = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY][1-9][0-9]*[ACDEFGHIKLMNPQRSTVWY]$")
RESEARCH = "janus.rowan.research_receipt.v1"
BBC1 = "janus.rowan.bbc1.stratified_8_mutant_pilot.v1"
EVENTS = {
    "PLANNED_NO_EXTERNAL_EFFECT",
    "ROWAN_ACCOUNT_CHECKED_NO_COMPUTATION",
    "ROWAN_DRAFT_CREATED_NO_EXECUTION",
    "ROWAN_SUBMITTED_RESULT_UNVERIFIED",
    "ROWAN_RESULT_PENDING",
    "ROWAN_RESULT_COLLECTED_UNVERIFIED",
}
STATES = {"NOT_SUBMITTED", "PENDING_OR_FAILED", "RESULT_UNREADABLE", "PROVIDER_RESULT_RETURNED"}


class TranslationBlocked(ValueError):
    pass


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_sha(value: object, regex: re.Pattern, key: str) -> str:
    if not isinstance(value, str) or not regex.fullmatch(value):
        raise TranslationBlocked("INVALID_" + key.upper())
    return value


def finite(value: object, name: str, *, low=None, high=None, allow_none=False):
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise TranslationBlocked("INVALID_" + name.upper())
    if (low is not None and value < low) or (high is not None and value > high):
        raise TranslationBlocked("OUT_OF_RANGE_" + name.upper())
    return value


def pka_projection(src: dict) -> dict:
    if src.get("schema_id") != RESEARCH:
        raise TranslationBlocked("WRONG_PKA_SCHEMA")
    if not isinstance(src.get("case_id"), str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", src["case_id"]):
        raise TranslationBlocked("INVALID_CASE_ID")
    event = src.get("event")
    if event not in EVENTS:
        raise TranslationBlocked("UNRECOGNIZED_EVENT")
    require_sha(src.get("input_sha256"), HEX64, "input_sha")
    provider = src.get("provider")
    if not isinstance(provider, dict) or provider.get("name") != "Rowan" or provider.get("workflow_type") != "pka":
        raise TranslationBlocked("PROVIDER_WORKFLOW_MISMATCH")
    method = provider.get("method")
    if method not in {"starling", "chemprop_nevolianis2025"}:
        raise TranslationBlocked("UNSUPPORTED_METHOD")
    workflow_id = src.get("workflow_uuid")
    if workflow_id is not None and (not isinstance(workflow_id, str)
                                    or not re.fullmatch(r"[0-9a-fA-F-]{32,40}", workflow_id)):
        raise TranslationBlocked("INVALID_WORKFLOW_ID")
    predicted = src.get("result")
    if event == "ROWAN_RESULT_COLLECTED_UNVERIFIED":
        if workflow_id is None or not isinstance(predicted, dict) or predicted.get("kind") != "MODEL_PREDICTION_NOT_EXPERIMENT":
            raise TranslationBlocked("COLLECTED_RESULT_PROVENANCE_MISSING")
        acid = finite(predicted.get("strongest_acid_pka"), "acid_pka", allow_none=True)
        base = finite(predicted.get("strongest_base_pka"), "base_pka", allow_none=True)
        if acid is None and base is None:
            raise TranslationBlocked("NO_PREDICTION_NUMBERS")
        state = "MODEL_PREDICTION_UNVERIFIED"
    else:
        if predicted is not None:
            raise TranslationBlocked("RESULT_WITHOUT_COLLECTED_EVENT")
        acid, base = None, None
        state = "NO_RESULT"
    billed = provider.get("credits_charged_reported")
    if billed is not None:
        billed = finite(billed, "reported_credits", low=0)
    return {
        "source_class": "ROWAN_PKA",
        "source_input_sha256": src["input_sha256"],
        "case_id": src["case_id"], "event": event,
        "workflow_uuid": workflow_id, "method": method,
        "data_status": state,
        "values": {"strongest_acid_pka": acid, "strongest_base_pka": base},
        "provider_reported_credits": billed,
        "scientific_note": "pKa MODEL prediction; not experiment, SAT witness or theorem",
    }


def bbc1_projection(src: dict) -> dict:
    if src.get("schema_id") != BBC1:
        raise TranslationBlocked("WRONG_BBC1_SCHEMA")
    require_sha(src.get("source_commit"), HEX40, "source_commit")
    require_sha(src.get("source_sha256"), HEX64, "source_sha256")
    cases = src.get("pilot_cases")
    if not isinstance(cases, list) or len(cases) != 8:
        raise TranslationBlocked("BBC1_EIGHT_CASES_REQUIRED")
    wildtype = src.get("wildtype")
    if not isinstance(wildtype, dict) or wildtype.get("state") not in STATES:
        raise TranslationBlocked("INVALID_WILDTYPE")
    entries = []
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise TranslationBlocked("INVALID_BBC1_CASE")
        mut = case.get("mutation")
        if not isinstance(mut, str) or not MUTATION.fullmatch(mut) or mut in seen:
            raise TranslationBlocked("INVALID_OR_DUPLICATE_MUTATION")
        seen.add(mut)
        status = case.get("provider_state")
        if status not in STATES:
            raise TranslationBlocked("INVALID_BBC1_PROVIDER_STATE")
        item = {"mutation": mut, "state": status}
        if status == "PROVIDER_RESULT_RETURNED":
            item["ptm"] = finite(case.get("ptm"), "ptm", low=0, high=1, allow_none=True)
            item["avg_lddt"] = finite(case.get("avg_lddt"), "avg_lddt", low=0, high=1, allow_none=True)
        entries.append(item)
    def ready(x: dict) -> bool:
        return x["state"] == "PROVIDER_RESULT_RETURNED" and x.get("ptm") is not None and x.get("avg_lddt") is not None
    wt_compact = {"state": wildtype["state"]}
    if wildtype["state"] == "PROVIDER_RESULT_RETURNED":
        wt_compact["ptm"] = finite(wildtype.get("ptm"), "wt_ptm", low=0, high=1, allow_none=True)
        wt_compact["avg_lddt"] = finite(wildtype.get("avg_lddt"), "wt_lddt", low=0, high=1, allow_none=True)
    all_ready = all(ready(x) for x in entries) and ready(wt_compact)
    if src.get("all_eight_ready_for_descriptive_association") is not all_ready:
        raise TranslationBlocked("BBC1_READINESS_CONTRADICTION")
    if src.get("protein_stability_or_fitness_inferred") is not False:
        raise TranslationBlocked("FITNESS_AUTHORITY_ESCALATION")
    if src.get("signed_label_direction_verified_against_original_raw_assay") is not False:
        raise TranslationBlocked("RAW_ASSAY_AUTHORITY_ESCALATION")
    if src.get("topa_scientific_review") != "OPEN":
        raise TranslationBlocked("TOPA_REVIEW_UNVERIFIED")
    return {
        "source_class": "ROWAN_BBC1_STRATIFIED",
        "source_commit": src["source_commit"],
        "source_sha256": src["source_sha256"],
        "data_status": "MODEL_DESCRIPTIVE_UNVERIFIED" if all_ready else "INCOMPLETE_OR_PENDING",
        "ready_count": sum(ready(x) for x in entries),
        "expected_count": 8,
        "wildtype": wt_compact,
        "samples": entries,
        "scientific_note": "pTM/lddt structural confidence, not DeltaDeltaG, fitness, SAT or theorem",
    }


def normalize(receipt: object) -> dict:
    if not isinstance(receipt, dict):
        raise TranslationBlocked("INPUT_MUST_BE_OBJECT")
    name = receipt.get("schema_id")
    if name == RESEARCH:
        return pka_projection(receipt)
    if name == BBC1:
        return bbc1_projection(receipt)
    raise TranslationBlocked("UNSUPPORTED_ROWAN_RECEIPT_SCHEMA")


def transform(receipt: dict, language: str = "ru") -> tuple[dict, dict, str, dict]:
    if language not in ("ru", "en"):
        raise TranslationBlocked("UNKNOWN_LANGUAGE")
    fingerprint = digest(canonical(receipt))
    facts = normalize(receipt)
    code = facts["source_class"]
    if code == "ROWAN_PKA":
        question = "Compare predicted pKa against an independently sourced experimental control"
        next_gate = "INDEPENDENT_PKA_MEASUREMENT_AND_TOPA_REVIEW"
    else:
        question = "Test whether BBC1 structural confidence differences transfer to independent protein holdouts"
        next_gate = "RAW_ASSAY_ALIGNMENT_AND_BLIND_PROTEIN_HOLDOUT"
    candidate = {
        "schema": SCHEMA,
        "source": {"repository": "Hawkar-usls/Janus",
                   "adapter": "integrations/rowan" if code == "ROWAN_PKA" else "integrations/tranception_rowan",
                   "receipt_sha256": fingerprint, "schema_id": receipt["schema_id"]},
        "facts": facts,
        "hypothesis_candidate": {"text": question, "category": "EMPIRICAL_FALSIFICATION_PROPOSAL",
                                 "next_gate": next_gate, "status": "UNTESTED"},
        "for_fundamentum": {
            "consume_as": "REPLAYABLE_EVIDENCE_CANDIDATE_ONLY",
            "proof_or_exact_sat_witness": False,
            "scientific_status": "UNVERIFIED",
            "rowan_job_created_by_translation": False,
            "rowan_credits_spent_by_translation": 0,
            "independent_source_authentication": False,
            "P_VS_NP": "OPEN",
        },
    }
    # Existing Lapis converter supplies an inspectable IR, never inferred executable semantics.
    safe_ir_input = {"$lapis": {"algorithm": {
        "name": "rowan_fundamentum_evidence_annotation",
        "steps": [{"operator": "ANNOTATE", "args": {"text": question}},
                  {"operator": "ANNOTATE", "args": {"text": next_gate}}],
        "metadata": {"domain": "empirical_science_only", "receipt_sha256": fingerprint},
        "outputs": ["candidate_only", "no_theorem_or_sat_authority"],
    }}}
    ir = json_to_algorithm(safe_ir_input)
    if ir["algorithm"]["mode"] != "explicit_contract" or any(
        step["operator"] != "ANNOTATE" for step in ir["algorithm"]["steps"]
    ):
        raise TranslationBlocked("UNEXPECTED_ALGORITHM_SEMANTICS")
    msg = {
        "ru": {
            "ROWAN_PKA": "ROWAN→LAPIS→FUNDAMENTUM: pKa",
            "ROWAN_BBC1_STRATIFIED": "ROWAN→LAPIS→FUNDAMENTUM: BBC1",
            "status": "Статус", "gate": "Следующий контроль", "boundary": "Не является SAT-решением или доказательством",
        },
        "en": {
            "ROWAN_PKA": "ROWAN→LAPIS→FUNDAMENTUM: pKa",
            "ROWAN_BBC1_STRATIFIED": "ROWAN→LAPIS→FUNDAMENTUM: BBC1",
            "status": "Status", "gate": "Next gate", "boundary": "Not a SAT solution or proof",
        },
    }[language]
    brief = (f"{msg[code]} | {fingerprint[:12]}\n"
             f"{msg['status']}: {facts['data_status']}"
             + (f"; {facts['ready_count']}/8" if code == "ROWAN_BBC1_STRATIFIED" else "")
             + f"\n{msg['gate']}: {next_gate}\n{msg['boundary']}\n")
    manifest = {
        "schema": "janus.lapis.rowan_translation_manifest.v1",
        "source_receipt_canonical_sha256": fingerprint,
        "candidate_sha256": digest(canonical(candidate)),
        "algorithm_ir_sha256": digest(canonical(ir)),
        "brief_sha256": digest(brief.encode("utf-8")),
        "language": language,
        "status": "OFFLINE_TRANSLATION_ONLY",
        "rowan_api_calls": 0, "credits_spent_by_translator": 0,
        "proof_authority": False, "independent_authentication": False,
    }
    return candidate, ir, brief, manifest


def translate_file(source: Path, outdir: Path, language: str = "ru") -> str:
    size = source.stat().st_size
    if size > MAX_INPUT_BYTES:
        raise TranslationBlocked("INPUT_TOO_LARGE")
    raw = source.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise TranslationBlocked("INPUT_TOO_LARGE")
    try:
        receipt = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise TranslationBlocked("INVALID_JSON") from None
    candidate, ir, brief, manifest = transform(receipt, language)
    fingerprint = manifest["source_receipt_canonical_sha256"]
    outdir.mkdir(parents=True, exist_ok=True)
    target = outdir / (fingerprint + "-" + language)
    payload = {
        "candidate.json": json.dumps(candidate, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        "algorithm_ir.json": json.dumps(ir, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        "brief.txt": brief,
        "manifest.json": json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    }
    if target.exists():
        if not target.is_dir() or any(
            not (target / key).is_file() or (target / key).read_bytes() != value.encode("utf-8")
            for key, value in payload.items()
        ):
            raise TranslationBlocked("CACHE_CONFLICT_REFUSE_OVERWRITE")
        return "CACHE_HIT_SAME_CONTENT"
    with tempfile.TemporaryDirectory(prefix=".rowan-lapis-", dir=outdir) as staging:
        root = Path(staging)
        for key, text in payload.items():
            (root / key).write_text(text, encoding="utf-8")
        try:
            root.rename(target)
        except OSError:
            raise TranslationBlocked("CACHE_DESTINATION_RACE") from None
    return "TRANSLATED_NEW"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, required=True, help="Existing local JANUS Rowan receipt")
    ap.add_argument("--outdir", type=Path, required=True, help="Content-addressed local outputs")
    ap.add_argument("--language", choices=("ru", "en"), default="ru")
    args = ap.parse_args()
    try:
        status = translate_file(args.input, args.outdir, args.language)
    except (OSError, TranslationBlocked, TypeError, OverflowError):
        print("ROWAN_LAPIS_TRANSLATION=BLOCKED")
        return 2
    print("ROWAN_LAPIS_TRANSLATION=" + status)
    print("ROWAN_API_CALLS=0; PROVIDER_CREDITS=0; PROOF_AUTHORITY=NONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
