#!/usr/bin/env python3
"""Proof-carrying public-data acquisition for Pv11 DRA008948.

Downloads exact public DDBJ SRA metadata and selected PLOS supplementary XLSX
files, hashes the raw bytes, joins Experiment<->Run<->Sample metadata, and
extracts XLSX worksheets to TSV using only the Python standard library.

Hard boundaries:
- No condition is assigned from accession ordering.
- A condition is admitted only when an exact expected token is explicitly
  present in public metadata text.
- Transcript/module evidence is a proxy and never establishes first S phase or
  mitosis.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

BASE = Path(os.environ.get("JANUS_ACQ_OUT", "dra008948_acquisition")).resolve()
RAW = BASE / "raw"
EXTRACTED = BASE / "xlsx_extracted"
RAW.mkdir(parents=True, exist_ok=True)
EXTRACTED.mkdir(parents=True, exist_ok=True)

DDBJ_BASE = "https://ddbj.nig.ac.jp/public/ddbj_database/dra/fastq/DRA008/DRA008948"
PLOS_FILE = "https://journals.plos.org/plosone/article/file?type=supplementary&id=info:doi/10.1371/journal.pone.0230218.{}"

INPUTS = {
    "DRA008948.experiment.xml": f"{DDBJ_BASE}/DRA008948.experiment.xml",
    "DRA008948.run.xml": f"{DDBJ_BASE}/DRA008948.run.xml",
    "DRA008948.sample.xml": f"{DDBJ_BASE}/DRA008948.sample.xml",
    "DRA008948.study.xml": f"{DDBJ_BASE}/DRA008948.study.xml",
    "pone.0230218.s001.mapping.xlsx": PLOS_FILE.format("s001"),
    "pone.0230218.s003.degs.xlsx": PLOS_FILE.format("s003"),
    "pone.0230218.s004.modules.xlsx": PLOS_FILE.format("s004"),
    "pone.0230218.s005.go.xlsx": PLOS_FILE.format("s005"),
}

EXPECTED_CONDITIONS = ["T0", "T12", "T24", "T36", "T48", "R0", "R3", "R12", "R24", "R72"]
REHYDRATION_CONDITIONS = ["R0", "R3", "R12", "R24", "R72"]
CONDITION_RE = re.compile(r"(?<![A-Za-z0-9])(T0|T12|T24|T36|T48|R0|R3|R12|R24|R72)(?![A-Za-z0-9])", re.I)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(name: str, url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "JANUS-LONGEVITY-SURVIVOR/1.0 public-evidence-acquisition",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = resp.read()
        final_url = resp.geturl()
        content_type = resp.headers.get("Content-Type", "")
        content_length_header = resp.headers.get("Content-Length")
    if not data:
        raise RuntimeError(f"empty download: {url}")
    path = RAW / name
    path.write_bytes(data)
    return {
        "name": name,
        "requested_url": url,
        "final_url": final_url,
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "content_type": content_type,
        "content_length_header": content_length_header,
    }


def lname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def first_text(node: ET.Element, wanted: str) -> str:
    for e in node.iter():
        if lname(e.tag) == wanted and (e.text or "").strip():
            return (e.text or "").strip()
    return ""


def all_text(node: ET.Element) -> str:
    parts = []
    for e in node.iter():
        if e.text and e.text.strip():
            parts.append(e.text.strip())
        if e.tail and e.tail.strip():
            parts.append(e.tail.strip())
        for k, v in e.attrib.items():
            if v:
                parts.append(str(v))
    return " | ".join(parts)


def direct_children(root: ET.Element, name: str):
    for e in root.iter():
        if lname(e.tag) == name:
            yield e


def parse_samples(path: Path) -> dict[str, dict]:
    root = ET.parse(path).getroot()
    out = {}
    for s in direct_children(root, "SAMPLE"):
        acc = s.attrib.get("accession", "")
        if not acc:
            continue
        attrs = []
        for a in s.iter():
            if lname(a.tag) != "SAMPLE_ATTRIBUTE":
                continue
            tag = first_text(a, "TAG")
            value = first_text(a, "VALUE")
            if tag or value:
                attrs.append(f"{tag}={value}")
        out[acc] = {
            "sample_accession": acc,
            "sample_alias": s.attrib.get("alias", ""),
            "sample_title": first_text(s, "TITLE"),
            "sample_description": first_text(s, "DESCRIPTION"),
            "sample_attributes": " | ".join(attrs),
            "sample_all_text": all_text(s),
        }
    return out


def parse_experiments(path: Path) -> dict[str, dict]:
    root = ET.parse(path).getroot()
    out = {}
    for e in direct_children(root, "EXPERIMENT"):
        acc = e.attrib.get("accession", "")
        if not acc:
            continue
        sample_acc = ""
        for x in e.iter():
            if lname(x.tag) in {"SAMPLE_DESCRIPTOR", "SAMPLE_REF"}:
                sample_acc = x.attrib.get("accession", "") or x.attrib.get("refname", "")
                if sample_acc:
                    break
        lib_name = first_text(e, "LIBRARY_NAME")
        lib_strategy = first_text(e, "LIBRARY_STRATEGY")
        lib_source = first_text(e, "LIBRARY_SOURCE")
        lib_selection = first_text(e, "LIBRARY_SELECTION")
        protocol = first_text(e, "LIBRARY_CONSTRUCTION_PROTOCOL")
        instrument = ""
        platform = ""
        for x in e.iter():
            n = lname(x.tag)
            if n == "INSTRUMENT_MODEL":
                instrument = (x.text or "").strip()
            if n in {"ILLUMINA", "OXFORD_NANOPORE", "PACBIO_SMRT", "ION_TORRENT", "BGISEQ", "LS454"}:
                platform = n
        out[acc] = {
            "experiment_accession": acc,
            "experiment_alias": e.attrib.get("alias", ""),
            "experiment_title": first_text(e, "TITLE"),
            "sample_accession": sample_acc,
            "library_name": lib_name,
            "library_strategy": lib_strategy,
            "library_source": lib_source,
            "library_selection": lib_selection,
            "library_construction_protocol": protocol,
            "platform": platform,
            "instrument_model": instrument,
            "experiment_all_text": all_text(e),
        }
    return out


def parse_runs(path: Path) -> list[dict]:
    root = ET.parse(path).getroot()
    out = []
    for r in direct_children(root, "RUN"):
        acc = r.attrib.get("accession", "")
        if not acc:
            continue
        exp_acc = ""
        for x in r.iter():
            if lname(x.tag) == "EXPERIMENT_REF":
                exp_acc = x.attrib.get("accession", "") or x.attrib.get("refname", "")
                if exp_acc:
                    break
        out.append({
            "run_accession": acc,
            "run_alias": r.attrib.get("alias", ""),
            "run_title": first_text(r, "TITLE"),
            "experiment_accession": exp_acc,
            "run_all_text": all_text(r),
        })
    return out


def explicit_condition(text: str) -> tuple[str, str]:
    hits = []
    for m in CONDITION_RE.finditer(text or ""):
        token = m.group(1).upper()
        if token not in hits:
            hits.append(token)
    if len(hits) == 1:
        return hits[0], "EXPLICIT_METADATA_TOKEN"
    if len(hits) > 1:
        return "", "AMBIGUOUS_MULTIPLE_METADATA_TOKENS:" + ",".join(hits)
    return "", "NOT_EXPLICITLY_BOUND"


def join_manifest(exps: dict[str, dict], runs: list[dict], samples: dict[str, dict]) -> list[dict]:
    rows = []
    for run in sorted(runs, key=lambda x: x["run_accession"]):
        exp = exps.get(run["experiment_accession"], {})
        sample = samples.get(exp.get("sample_accession", ""), {})
        evidence_parts = [
            exp.get("experiment_alias", ""), exp.get("experiment_title", ""),
            exp.get("library_name", ""), exp.get("library_construction_protocol", ""),
            run.get("run_alias", ""), run.get("run_title", ""),
            sample.get("sample_alias", ""), sample.get("sample_title", ""),
            sample.get("sample_description", ""), sample.get("sample_attributes", ""),
        ]
        evidence = " | ".join(x for x in evidence_parts if x)
        condition, binding = explicit_condition(evidence)
        row = {
            "run_accession": run.get("run_accession", ""),
            "experiment_accession": run.get("experiment_accession", ""),
            "sample_accession": exp.get("sample_accession", ""),
            "condition": condition,
            "condition_binding": binding,
            "condition_evidence_text": evidence,
            "run_alias": run.get("run_alias", ""),
            "run_title": run.get("run_title", ""),
            "experiment_alias": exp.get("experiment_alias", ""),
            "experiment_title": exp.get("experiment_title", ""),
            "library_name": exp.get("library_name", ""),
            "library_strategy": exp.get("library_strategy", ""),
            "library_source": exp.get("library_source", ""),
            "library_selection": exp.get("library_selection", ""),
            "platform": exp.get("platform", ""),
            "instrument_model": exp.get("instrument_model", ""),
            "sample_alias": sample.get("sample_alias", ""),
            "sample_title": sample.get("sample_title", ""),
            "sample_description": sample.get("sample_description", ""),
            "sample_attributes": sample.get("sample_attributes", ""),
        }
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def col_to_idx(ref: str) -> int:
    m = re.match(r"([A-Z]+)", ref or "A")
    letters = m.group(1) if m else "A"
    n = 0
    for c in letters:
        n = n * 26 + (ord(c) - 64)
    return n - 1


def read_shared_strings(z: zipfile.ZipFile) -> list[str]:
    try:
        data = z.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(data)
    out = []
    for si in root:
        if lname(si.tag) != "si":
            continue
        texts = []
        for e in si.iter():
            if lname(e.tag) == "t" and e.text is not None:
                texts.append(e.text)
        out.append("".join(texts))
    return out


def workbook_sheet_paths(z: zipfile.ZipFile) -> list[tuple[str, str]]:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = {}
    for r in rels:
        rid = r.attrib.get("Id", "")
        target = r.attrib.get("Target", "")
        if target.startswith("/"):
            target = target.lstrip("/")
        elif not target.startswith("xl/"):
            target = "xl/" + target
        relmap[rid] = target
    out = []
    for e in wb.iter():
        if lname(e.tag) != "sheet":
            continue
        name = e.attrib.get("name", "sheet")
        rid = ""
        for k, v in e.attrib.items():
            if lname(k) == "id":
                rid = v
        if rid in relmap:
            out.append((name, relmap[rid]))
    return out


def parse_sheet(z: zipfile.ZipFile, path: str, shared: list[str]) -> list[list[str]]:
    root = ET.fromstring(z.read(path))
    rows_dict = {}
    max_col = -1
    for row in root.iter():
        if lname(row.tag) != "row":
            continue
        values = {}
        for c in row:
            if lname(c.tag) != "c":
                continue
            ref = c.attrib.get("r", "A1")
            idx = col_to_idx(ref)
            max_col = max(max_col, idx)
            typ = c.attrib.get("t", "")
            value = ""
            if typ == "inlineStr":
                ts = [x.text or "" for x in c.iter() if lname(x.tag) == "t"]
                value = "".join(ts)
            else:
                v = next((x for x in c if lname(x.tag) == "v"), None)
                raw = (v.text or "") if v is not None else ""
                if typ == "s" and raw:
                    try:
                        value = shared[int(raw)]
                    except Exception:
                        value = raw
                elif typ == "b":
                    value = "TRUE" if raw == "1" else "FALSE"
                else:
                    value = raw
                f = next((x for x in c if lname(x.tag) == "f"), None)
                if f is not None and (f.text or ""):
                    value = value if value else "=" + (f.text or "")
            values[idx] = value
        rnum = int(row.attrib.get("r", len(rows_dict) + 1))
        rows_dict[rnum] = values
    if not rows_dict:
        return []
    out = []
    for rnum in range(1, max(rows_dict) + 1):
        vals = rows_dict.get(rnum, {})
        out.append([vals.get(i, "") for i in range(max_col + 1)])
    return out


def safe_sheet_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "sheet"


def extract_xlsx(path: Path, label: str) -> dict:
    outdir = EXTRACTED / label
    outdir.mkdir(parents=True, exist_ok=True)
    inventory = {"file": path.name, "sheets": []}
    with zipfile.ZipFile(path) as z:
        shared = read_shared_strings(z)
        for sheet_name, sheet_path in workbook_sheet_paths(z):
            rows = parse_sheet(z, sheet_path, shared)
            outpath = outdir / f"{safe_sheet_name(sheet_name)}.tsv"
            with outpath.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter="\t", lineterminator="\n")
                w.writerows(rows)
            max_cols = max((len(r) for r in rows), default=0)
            inventory["sheets"].append({
                "sheet": sheet_name,
                "sheet_xml": sheet_path,
                "rows": len(rows),
                "columns": max_cols,
                "preview": rows[:5],
                "tsv": str(outpath.relative_to(BASE)),
            })
    return inventory


def keyword_scan() -> list[dict]:
    wanted = ["R3", "R12", "R24", "R72", "Blue", "DNA replication", "PvG"]
    hits = []
    for p in sorted(EXTRACTED.rglob("*.tsv")):
        with p.open(encoding="utf-8", errors="replace") as f:
            for line_no, line in enumerate(f, 1):
                for word in wanted:
                    if word.lower() in line.lower():
                        hits.append({
                            "file": str(p.relative_to(BASE)),
                            "line": line_no,
                            "keyword": word,
                            "text": line.rstrip("\n")[:4000],
                        })
    return hits


def main() -> int:
    provenance = []
    errors = []
    for name, url in INPUTS.items():
        try:
            rec = download(name, url)
            provenance.append(rec)
            print("ACQUIRED", name, rec["bytes"], rec["sha256"], rec["content_type"], flush=True)
        except Exception as exc:
            errors.append({"name": name, "url": url, "error": repr(exc)})
            print("ACQUIRE_ERROR", name, repr(exc), file=sys.stderr, flush=True)

    (BASE / "provenance.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(BASE / "hashes.csv", provenance)
    (BASE / "acquisition_errors.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")

    required_xml = [RAW / "DRA008948.experiment.xml", RAW / "DRA008948.run.xml", RAW / "DRA008948.sample.xml"]
    manifest_rows = []
    validation = {}
    if all(p.exists() for p in required_xml):
        samples = parse_samples(required_xml[2])
        experiments = parse_experiments(required_xml[0])
        runs = parse_runs(required_xml[1])
        manifest_rows = join_manifest(experiments, runs, samples)
        write_csv(BASE / "dra008948_run_condition_manifest.csv", manifest_rows)
        cond_counts = Counter(r["condition"] for r in manifest_rows if r["condition"])
        unresolved = [r["run_accession"] for r in manifest_rows if not r["condition"]]
        missing_exp_links = [r["run_accession"] for r in manifest_rows if not r["experiment_accession"] or r["experiment_accession"] not in experiments]
        missing_sample_links = [r["experiment_accession"] for r in manifest_rows if not r["sample_accession"] or r["sample_accession"] not in samples]
        exact_10x3 = all(cond_counts.get(c) == 3 for c in EXPECTED_CONDITIONS) and len(cond_counts) == 10
        validation = {
            "experiments": len(experiments),
            "runs": len(runs),
            "samples": len(samples),
            "joined_rows": len(manifest_rows),
            "condition_counts": dict(sorted(cond_counts.items())),
            "unresolved_condition_runs": unresolved,
            "missing_experiment_links": missing_exp_links,
            "missing_sample_links": missing_sample_links,
            "expected_design_from_paper": "10 conditions x 3 biological replicates = 30 libraries",
            "condition_binding_10x3_explicitly_verified": exact_10x3,
            "condition_binding_status": "PASS_EXPLICIT_10x3" if exact_10x3 else "CONDITION_BINDING_UNRESOLVED_OR_INCOMPLETE",
            "hard_boundary": "ACCESSION_ORDER_IS_NOT_CONDITION_BINDING",
        }
        (BASE / "manifest_validation.json").write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
        print("MANIFEST_VALIDATION", json.dumps(validation, sort_keys=True), flush=True)
        for r in manifest_rows[:30]:
            print("MANIFEST_ROW", r["run_accession"], r["experiment_accession"], r["sample_accession"], r["condition"] or "UNKNOWN", r["condition_binding"], flush=True)

    inventories = []
    for filename in [
        "pone.0230218.s001.mapping.xlsx",
        "pone.0230218.s003.degs.xlsx",
        "pone.0230218.s004.modules.xlsx",
        "pone.0230218.s005.go.xlsx",
    ]:
        p = RAW / filename
        if p.exists():
            try:
                inv = extract_xlsx(p, filename.replace(".xlsx", ""))
                inventories.append(inv)
                print("XLSX_EXTRACTED", filename, [(s["sheet"], s["rows"], s["columns"]) for s in inv["sheets"]], flush=True)
            except Exception as exc:
                errors.append({"name": filename, "error": "xlsx_parse:" + repr(exc)})
                print("XLSX_PARSE_ERROR", filename, repr(exc), file=sys.stderr, flush=True)
    (BASE / "xlsx_inventory.json").write_text(json.dumps(inventories, indent=2, ensure_ascii=False), encoding="utf-8")

    hits = keyword_scan()
    write_csv(BASE / "keyword_hits.csv", hits)
    print("KEYWORD_HITS", len(hits), flush=True)
    for h in hits[:80]:
        print("KEYWORD_HIT", h["file"], h["line"], h["keyword"], h["text"][:600], flush=True)

    summary = {
        "artifact_id": "JANUS-PV11-DRA008948-ACQUISITION-V1",
        "raw_inputs_requested": len(INPUTS),
        "raw_inputs_acquired": len(provenance),
        "acquisition_errors": errors,
        "manifest_validation": validation,
        "xlsx_files_extracted": len(inventories),
        "keyword_hits": len(hits),
        "analysis_status": "INPUT_ACQUISITION_AND_SCHEMA_INSPECTION_ONLY",
        "cell_cycle_proxy_result": "NOT_RUN",
        "first_cell_cycle_entry": "UNKNOWN",
        "hard_boundaries": [
            "ACCESSION_ORDER_IS_NOT_CONDITION_BINDING",
            "MODULE_ENRICHMENT_IS_NOT_TIMEPOINT_DIRECTION",
            "CELL_CYCLE_TRANSCRIPT_PROXY_IS_NOT_DIRECT_S_PHASE_OR_MITOSIS",
            "MISSING_DATA_STAYS_MISSING",
        ],
    }
    (BASE / "acquisition_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("JANUS_ACQUISITION_SUMMARY", json.dumps(summary, sort_keys=True), flush=True)

    # Download failure is a real acquisition failure. An unresolved condition binding is
    # not a tooling failure; it is preserved as an evidence result and the job succeeds.
    if len(provenance) != len(INPUTS):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
