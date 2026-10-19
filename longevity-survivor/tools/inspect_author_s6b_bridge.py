#!/usr/bin/env python3
"""Inspect author-published Figure S6B files for a public PvG -> g.t bridge.

This is a schema/identifier audit only. It never infers identity from filename,
row order, coordinates, or approximate string similarity.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import re
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(os.environ.get("JANUS_S6B_OUT", "author_s6b_bridge_inspection")).resolve()
OUT.mkdir(parents=True, exist_ok=True)

AUTHOR_REPO = "Kikawada-Lab-UT-NARO/Pvanderplanki_chromosomal_genome"
PIN = "fe5064db5e999e0c868d4c8330a231b2da15f256"
FILES = {
    "s6b_tpm": "Rplots/data/fig_s6b_get_degs_from_both.pl.out.tpm.gz",
    "s6b_deg": "Rplots/data/fig_s6b_get_degs_from_both.pl.out.gz",
}
MODULE_TSV = Path("dra008948_acquisition/xlsx_extracted/pone.0230218.s004.modules/ModuleInclusion.tsv")
TPM_SCHEMA = Path("pv_authors_tpm_inspection/tpm_schema.json")
PVG = re.compile(r"(?<![A-Za-z0-9])PvG\d+(?:\.t\d+)?(?![A-Za-z0-9])")
GT = re.compile(r"(?<![A-Za-z0-9])g\d+(?:\.t\d+)?(?![A-Za-z0-9])", re.I)
REHY = re.compile(r"Pv11_Rehydration_(00|03|12|24|72)_rep([123])", re.I)


def h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def acquire(label: str, path: str) -> Path:
    url = f"https://raw.githubusercontent.com/{AUTHOR_REPO}/{PIN}/{path}"
    req = urllib.request.Request(url, headers={"User-Agent":"JANUS-LONGEVITY-SURVIVOR/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read(); final = r.geturl(); ctype = r.headers.get("Content-Type", "")
    if not data:
        raise RuntimeError(f"empty download {label}")
    p = OUT / Path(path).name
    p.write_bytes(data)
    meta = {"label":label,"repository":AUTHOR_REPO,"commit":PIN,"path":path,"requested_url":url,"final_url":final,"bytes":len(data),"sha256":h(data),"content_type":ctype}
    (OUT/f"{label}.provenance.json").write_text(json.dumps(meta,indent=2)+"\n",encoding="utf-8")
    print("ACQUIRED", label, len(data), meta["sha256"], flush=True)
    return p


def load_blue() -> tuple[set[str], set[str]]:
    if not MODULE_TSV.exists():
        raise RuntimeError(f"missing module table: {MODULE_TSV}")
    gene=set(); tx=set()
    with MODULE_TSV.open(encoding="utf-8",errors="replace") as f:
        for raw in f:
            parts=raw.rstrip("\n").split("\t")
            if len(parts)>=2 and parts[1].strip().lower()=="blue":
                x=parts[0].strip()
                gene.add(x.split(".t",1)[0])
                tx.add(x)
    return gene,tx


def sniff(path: Path, label: str) -> dict:
    with gzip.open(path,"rt",encoding="utf-8",errors="replace",newline="") as f:
        lines=[]
        for _ in range(40):
            x=f.readline()
            if not x: break
            lines.append(x.rstrip("\r\n"))
    (OUT/f"{label}.first40.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")
    if not lines: raise RuntimeError(f"empty decompressed {label}")
    counts={"TAB":lines[0].count("\t"),"COMMA":lines[0].count(","),"SEMICOLON":lines[0].count(";")}
    delim="\t" if counts["TAB"]>=max(counts["COMMA"],counts["SEMICOLON"]) else ("," if counts["COMMA"]>=counts["SEMICOLON"] else ";")
    header=next(csv.reader([lines[0]],delimiter=delim))
    return {"header":header,"delimiter":"TAB" if delim=="\t" else delim,"first_line":lines[0]}


def audit_rows(path: Path, label: str, blue_gene: set[str], blue_tx: set[str], has_header: bool) -> dict:
    widths=Counter(); first_col=Counter(); pvg_all=set(); gt_all=set(); exact_blue_gene=set(); exact_blue_tx=set(); same_row=[]; rehy_cols=[]; rows=0
    with gzip.open(path,"rt",encoding="utf-8",errors="replace",newline="") as f:
        first=f.readline().rstrip("\r\n")
        delim="\t" if first.count("\t")>=max(first.count(","),first.count(";")) else ("," if first.count(",")>=first.count(";") else ";")
        header=next(csv.reader([first],delimiter=delim))
        if has_header:
            for c in header:
                if REHY.fullmatch(c): rehy_cols.append(c)
        else:
            # rewind logically by processing the first record as data
            f = iter([first]+[x.rstrip("\r\n") for x in f])
        for raw in f:
            text=raw if isinstance(raw,str) else str(raw)
            text=text.rstrip("\r\n")
            if not text: continue
            row=next(csv.reader([text],delimiter=delim)); rows+=1; widths[len(row)]+=1
            rid=row[0].strip() if row else ""
            if re.fullmatch(r"PvG\d+(?:\.t\d+)?",rid): first_col["PvG"]+=1
            elif re.fullmatch(r"g\d+(?:\.t\d+)?",rid,re.I): first_col["g"]+=1
            else: first_col["other"]+=1
            pvs=set(PVG.findall(text)); gts=set(GT.findall(text)); pvg_all |= pvs; gt_all |= gts
            for x in pvs:
                base=x.split(".t",1)[0]
                if base in blue_gene: exact_blue_gene.add(base)
                if x in blue_tx: exact_blue_tx.add(x)
            if pvs and gts and len(same_row)<5000:
                same_row.append((sorted(pvs),sorted(gts),text[:2000]))
    with (OUT/f"{label}.same_row_pvg_gt.tsv").open("w",encoding="utf-8",newline="") as o:
        w=csv.writer(o,delimiter="\t",lineterminator="\n"); w.writerow(["pvg_ids","gt_ids","row_excerpt"])
        for a,b,t in same_row: w.writerow([",".join(a),",".join(b),t])
    result={
        "label":label,"rows":rows,"width_counts":dict(widths),"first_column_id_patterns":dict(first_col),
        "unique_pvg_tokens_anywhere":len(pvg_all),"unique_gt_tokens_anywhere":len(gt_all),
        "same_row_pvg_gt_records":len(same_row),"blue_gene_ids_seen_exact":len(exact_blue_gene),
        "blue_gene_coverage_fraction":len(exact_blue_gene)/len(blue_gene) if blue_gene else None,
        "blue_transcript_ids_seen_exact":len(exact_blue_tx),"rehydration_columns_explicit":rehy_cols,
        "pvg_examples":sorted(pvg_all)[:20],"gt_examples":sorted(gt_all)[:20],
    }
    (OUT/f"{label}.audit.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result


def main() -> int:
    blue_gene,blue_tx=load_blue()
    paths={k:acquire(k,v) for k,v in FILES.items()}
    tpm_sniff=sniff(paths["s6b_tpm"],"s6b_tpm")
    deg_sniff=sniff(paths["s6b_deg"],"s6b_deg")
    tpm=audit_rows(paths["s6b_tpm"],"s6b_tpm",blue_gene,blue_tx,True)
    deg=audit_rows(paths["s6b_deg"],"s6b_deg",blue_gene,blue_tx,False)

    direct=tpm["same_row_pvg_gt_records"]+deg["same_row_pvg_gt_records"]
    blue_seen=max(tpm["blue_gene_ids_seen_exact"],deg["blue_gene_ids_seen_exact"])
    summary={
        "artifact_id":"JANUS-AUTHOR-S6B-PVG-GT-BRIDGE-INSPECTION-V1",
        "author_repository":AUTHOR_REPO,"pinned_commit":PIN,"blue_gene_denominator":len(blue_gene),
        "s6b_tpm_schema":tpm_sniff,"s6b_deg_schema":deg_sniff,"s6b_tpm":tpm,"s6b_deg":deg,
        "direct_same_row_pvg_gt_records":direct,"blue_genes_seen_in_s6b":blue_seen,
        "bridge_admission":"DIRECT_AUTHOR_PVG_TO_GT_BRIDGE_PRESENT_IN_S6B" if direct else "DIRECT_AUTHOR_PVG_TO_GT_BRIDGE_NOT_PRESENT_IN_S6B",
        "trajectory_admission":"BLOCKED_UNTIL_ID_BRIDGE_FROZEN",
        "hard_boundaries":["FILENAME_IS_NOT_SEMANTICS","ROW_ORDER_IS_NOT_IDENTITY","EXACT_ID_OR_EXPLICIT_CROSSREF_REQUIRED","AMBIGUOUS_MAPS_STAY_AMBIGUOUS"],
    }
    (OUT/"s6b_bridge_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print("S6B_BRIDGE_SUMMARY",json.dumps(summary,sort_keys=True),flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
