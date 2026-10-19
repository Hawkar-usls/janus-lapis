#!/usr/bin/env python3
"""Inspect an author-published Pv11 RSEM TPM matrix at an immutable Git commit.

This script is schema/provenance inspection only. It does not infer cell-cycle
entry and does not map identifiers heuristically. Exact identifier overlap with
the 2020 S2 Blue-module membership is reported separately from any candidate
normalization/mapping idea.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import re
import urllib.request
from collections import Counter
from pathlib import Path

OUT = Path(os.environ.get("JANUS_TPM_OUT", "pv_authors_tpm_inspection")).resolve()
OUT.mkdir(parents=True, exist_ok=True)

AUTHOR_REPO = "Kikawada-Lab-UT-NARO/Pvanderplanki_chromosomal_genome"
PINNED_COMMIT = "fe5064db5e999e0c868d4c8330a231b2da15f256"
TPM_PATH = "Rplots/data/fig_s6a_RSEM.isoform.TPM.not_cross_norm.gz"
TPM_URL = f"https://raw.githubusercontent.com/{AUTHOR_REPO}/{PINNED_COMMIT}/{TPM_PATH}"
MODULE_TSV = Path("dra008948_acquisition/xlsx_extracted/pone.0230218.s004.modules/ModuleInclusion.tsv")
EXPECTED_TOKENS = ["T0", "T12", "T24", "T36", "T48", "R0", "R3", "R12", "R24", "R72"]
DRR_RE = re.compile(r"DRR\d+")
PVG_RE = re.compile(r"^PvG\d+$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download() -> tuple[Path, dict]:
    req = urllib.request.Request(
        TPM_URL,
        headers={"User-Agent": "JANUS-LONGEVITY-SURVIVOR/1.0 public-evidence-inspection"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
        final_url = resp.geturl()
        ctype = resp.headers.get("Content-Type", "")
    if not data:
        raise RuntimeError("empty TPM download")
    path = OUT / "fig_s6a_RSEM.isoform.TPM.not_cross_norm.gz"
    path.write_bytes(data)
    prov = {
        "source_repository": AUTHOR_REPO,
        "source_commit": PINNED_COMMIT,
        "source_path": TPM_PATH,
        "requested_url": TPM_URL,
        "final_url": final_url,
        "bytes": len(data),
        "sha256": sha256(data),
        "content_type": ctype,
    }
    return path, prov


def load_blue() -> set[str]:
    if not MODULE_TSV.exists():
        raise RuntimeError(f"missing S2 module TSV: {MODULE_TSV}")
    blue = set()
    with MODULE_TSV.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2 and parts[1].strip().lower() == "blue":
                blue.add(parts[0].strip())
    return blue


def detect_delimiter(line: str) -> str:
    counts = {"\t": line.count("\t"), ",": line.count(","), ";": line.count(";")}
    delim, count = max(counts.items(), key=lambda kv: kv[1])
    if count == 0:
        raise RuntimeError("cannot detect delimiter from TPM header")
    return delim


def exact_token_hits(header: list[str]) -> dict[str, list[str]]:
    out = {t: [] for t in EXPECTED_TOKENS}
    for col in header:
        for token in EXPECTED_TOKENS:
            # exact standalone token in a column label; no accession-order inference.
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", col, re.I):
                out[token].append(col)
    return {k: v for k, v in out.items() if v}


def main() -> int:
    gzpath, prov = download()
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    print("TPM_ACQUIRED", prov["bytes"], prov["sha256"], prov["source_commit"], flush=True)

    blue = load_blue()
    print("BLUE_MEMBERS_S2", len(blue), flush=True)

    first_lines = []
    row_ids = []
    row_count = 0
    width_counts = Counter()
    pv_exact_rows = 0
    with gzip.open(gzpath, "rt", encoding="utf-8", errors="replace", newline="") as f:
        header_line = f.readline().rstrip("\n\r")
        if not header_line:
            raise RuntimeError("empty decompressed TPM matrix")
        delim = detect_delimiter(header_line)
        header = next(csv.reader([header_line], delimiter=delim))
        first_lines.append(header_line)
        for line in f:
            text = line.rstrip("\n\r")
            if len(first_lines) < 20:
                first_lines.append(text)
            if not text:
                continue
            row = next(csv.reader([text], delimiter=delim))
            width_counts[len(row)] += 1
            row_count += 1
            rid = row[0].strip() if row else ""
            row_ids.append(rid)
            if PVG_RE.fullmatch(rid):
                pv_exact_rows += 1

    (OUT / "first_20_lines.txt").write_text("\n".join(first_lines) + "\n", encoding="utf-8")
    (OUT / "header.tsv").write_text("\t".join(header) + "\n", encoding="utf-8")

    id_counts = Counter()
    for rid in row_ids:
        if PVG_RE.fullmatch(rid):
            id_counts["PvG_exact"] += 1
        elif rid.startswith("PvG"):
            id_counts["PvG_prefixed_nonexact"] += 1
        elif re.match(r"^g\d+", rid, re.I):
            id_counts["g_numeric"] += 1
        elif re.match(r"^[A-Za-z]{2,}\d+", rid):
            id_counts["alpha_numeric"] += 1
        else:
            id_counts["other"] += 1

    row_set = set(row_ids)
    exact_blue = sorted(blue & row_set)
    with (OUT / "blue_exact_id_overlap.tsv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["gene_id", "match_type"])
        for gene in exact_blue:
            w.writerow([gene, "EXACT_STRING_MATCH"])

    # Candidate-only prefix relation: report statistics but DO NOT use for admission.
    prefix_blue = []
    if exact_blue != sorted(blue):
        for rid in row_ids:
            for gene in blue:
                if rid != gene and rid.startswith(gene):
                    prefix_blue.append((gene, rid))
                    if len(prefix_blue) >= 200:
                        break
            if len(prefix_blue) >= 200:
                break
    with (OUT / "blue_candidate_prefix_examples.tsv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["blue_gene_id", "matrix_row_id", "status"])
        for gene, rid in prefix_blue:
            w.writerow([gene, rid, "CANDIDATE_ONLY_NOT_ADMITTED"])

    header_text = " | ".join(header)
    drrs = sorted(set(DRR_RE.findall(header_text)))
    token_hits = exact_token_hits(header)
    rehydration_cols = {k: v for k, v in token_hits.items() if k in {"R0", "R3", "R12", "R24", "R72"}}

    schema = {
        "artifact_id": "JANUS-PV-AUTHORS-TPM-SCHEMA-INSPECTION-V1",
        "provenance": prov,
        "decompressed_rows_excluding_header": row_count,
        "columns": len(header),
        "delimiter": "TAB" if delim == "\t" else delim,
        "header": header,
        "header_condition_token_hits": token_hits,
        "header_rehydration_condition_hits": rehydration_cols,
        "header_drr_accessions": drrs,
        "row_width_counts": dict(width_counts),
        "row_id_pattern_counts": dict(id_counts),
        "s2_blue_members": len(blue),
        "exact_blue_id_overlap": len(exact_blue),
        "exact_blue_overlap_fraction": (len(exact_blue) / len(blue)) if blue else None,
        "candidate_prefix_examples_written": len(prefix_blue),
        "sample_axis_admission": (
            "EXPLICIT_REHYDRATION_COLUMNS_PRESENT"
            if all(x in rehydration_cols for x in ["R3", "R12", "R24", "R72"])
            else "REHYDRATION_COLUMNS_NOT_FULLY_EXPLICIT"
        ),
        "id_axis_admission": (
            "EXACT_BLUE_IDS_PRESENT"
            if exact_blue
            else "NO_EXACT_BLUE_ID_OVERLAP"
        ),
        "analysis_status": "SCHEMA_AND_EXACT_ID_COMPATIBILITY_ONLY",
        "blue_trajectory_status": "NOT_RUN",
        "cell_cycle_proxy_result": "NOT_RUN",
        "first_cell_cycle_entry": "UNKNOWN",
        "hard_boundaries": [
            "SOURCE_PINNED_TO_EXACT_GIT_COMMIT",
            "EXACT_ID_MATCH_IS_ADMITTED_PREFIX_MATCH_IS_NOT",
            "COLUMN_ORDER_IS_NOT_CONDITION_BINDING",
            "TPM_TRAJECTORY_IS_NOT_DIRECT_S_PHASE_OR_MITOSIS",
        ],
    }
    (OUT / "tpm_schema.json").write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("TPM_SCHEMA", json.dumps(schema, sort_keys=True), flush=True)
    print("TPM_HEADER", " | ".join(header[:80]), flush=True)
    print("BLUE_EXACT_OVERLAP", len(exact_blue), "OF", len(blue), flush=True)

    # Schema inspection itself succeeds even if axes are incompatible; incompatibility is evidence.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
