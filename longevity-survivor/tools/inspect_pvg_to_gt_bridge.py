#!/usr/bin/env python3
"""Inspect public old/new P. vanderplanki annotation layers for an explicit PvG -> g.t bridge.

Fail-closed rules:
- exact identifiers/cross-references are admissible;
- coordinate or sequence similarity is not silently promoted to identity;
- absence of a direct bridge is preserved as an evidence gap.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(os.environ.get("JANUS_PVG_BRIDGE_OUT", "pvg_bridge_inspection")).resolve()
OUT.mkdir(parents=True, exist_ok=True)

PINNED_COMMIT = "fe5064db5e999e0c868d4c8330a231b2da15f256"
SOURCES = {
    "geo_gse78799_gtf": "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE78nnn/GSE78799/suppl/GSE78799_pvan.gtf.gz",
    "geo_gse78799_counts": "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE78nnn/GSE78799/suppl/GSE78799_pvan.ds2.counts.txt.gz",
    "authors_pv5_gtf": f"https://raw.githubusercontent.com/Kikawada-Lab-UT-NARO/Pvanderplanki_chromosomal_genome/{PINNED_COMMIT}/Rplots/data/fig_s5h_Pv11_5.0_annotation.gtf.gz",
}
PVG = re.compile(r"\bPvG\d+\b")
GT = re.compile(r"\bg\d+(?:\.t\d+)?\b")
ATTR = re.compile(r"([A-Za-z0-9_.:-]+)\s+[\"']([^\"']+)[\"']")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(label: str, url: str) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent":"JANUS-LONGEVITY-SURVIVOR/1.0 public-bridge-inspection"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
        final = r.geturl()
        ctype = r.headers.get("Content-Type", "")
    if not data:
        raise RuntimeError(f"empty download: {label}")
    p = OUT / f"{label}.gz"
    p.write_bytes(data)
    meta = {"label":label,"requested_url":url,"final_url":final,"bytes":len(data),"sha256":sha256(data),"content_type":ctype}
    (OUT / f"{label}.provenance.json").write_text(json.dumps(meta, indent=2)+"\n", encoding="utf-8")
    print("ACQUIRED", label, len(data), meta["sha256"], flush=True)
    return p


def inspect_gtf(path: Path, label: str) -> dict:
    pvg_ids=set(); gt_ids=set(); seqnames=Counter(); attrs=Counter(); examples=[]; cross=[]; lines=0
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for raw in f:
            if raw.startswith("#") or not raw.strip():
                continue
            lines += 1
            cols = raw.rstrip("\n").split("\t")
            if len(cols) < 9:
                continue
            seqnames[cols[0]] += 1
            a = cols[8]
            pairs = ATTR.findall(a)
            for k,v in pairs:
                attrs[k]+=1
            pvs=set(PVG.findall(a)); gts=set(GT.findall(a))
            pvg_ids |= pvs; gt_ids |= gts
            if pvs and gts:
                cross.append({"seqname":cols[0],"feature":cols[2],"start":cols[3],"end":cols[4],"pvg":sorted(pvs),"gt":sorted(gts),"attributes":a})
            if len(examples) < 20 and (pvs or gts):
                examples.append(raw.rstrip("\n"))
    result={
        "label":label,"data_lines":lines,"unique_pvg_ids":len(pvg_ids),"unique_gt_ids":len(gt_ids),
        "pvg_examples":sorted(pvg_ids)[:25],"gt_examples":sorted(gt_ids)[:25],
        "attribute_keys":dict(attrs.most_common(30)),"seqname_examples":dict(seqnames.most_common(20)),
        "explicit_same_record_pvg_gt_crossrefs":len(cross),
    }
    (OUT/f"{label}.inspection.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    (OUT/f"{label}.identifier_examples.txt").write_text("\n".join(examples)+"\n",encoding="utf-8")
    with (OUT/f"{label}.explicit_crossrefs.tsv").open("w",encoding="utf-8") as o:
        o.write("seqname\tfeature\tstart\tend\tpvg\tgt\tattributes\n")
        for x in cross:
            o.write(f"{x['seqname']}\t{x['feature']}\t{x['start']}\t{x['end']}\t{','.join(x['pvg'])}\t{','.join(x['gt'])}\t{x['attributes'].replace(chr(9),' ')}\n")
    return result


def inspect_counts(path: Path) -> dict:
    ids=[]; header=""
    with gzip.open(path,"rt",encoding="utf-8",errors="replace") as f:
        header=f.readline().rstrip("\n")
        for raw in f:
            if not raw.strip(): continue
            ids.append(raw.split("\t",1)[0].strip())
    pvg=[x for x in ids if PVG.fullmatch(x)]
    gt=[x for x in ids if GT.fullmatch(x)]
    result={"rows":len(ids),"header":header,"exact_pvg_rows":len(pvg),"exact_gt_rows":len(gt),"pvg_examples":pvg[:25],"gt_examples":gt[:25]}
    (OUT/"geo_gse78799_counts.inspection.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result


def main() -> int:
    paths={k:download(k,u) for k,u in SOURCES.items()}
    old=inspect_gtf(paths["geo_gse78799_gtf"],"geo_gse78799_gtf")
    new=inspect_gtf(paths["authors_pv5_gtf"],"authors_pv5_gtf")
    counts=inspect_counts(paths["geo_gse78799_counts"])

    # Direct textual bridge only: a PvG and g.t identifier co-occurring in the same public GTF record.
    direct = old["explicit_same_record_pvg_gt_crossrefs"] + new["explicit_same_record_pvg_gt_crossrefs"]
    summary={
        "artifact_id":"JANUS-PVG-TO-GT-PUBLIC-BRIDGE-INSPECTION-V1",
        "sources":SOURCES,
        "pinned_author_commit":PINNED_COMMIT,
        "old_gtf":old,"new_gtf":new,"old_counts":counts,
        "direct_textual_bridge_records":direct,
        "admission": "DIRECT_PUBLIC_PVG_TO_GT_BRIDGE_PRESENT" if direct else "DIRECT_PUBLIC_PVG_TO_GT_BRIDGE_NOT_FOUND_IN_THESE_SOURCES",
        "next_if_absent":[
            "acquire authoritative old PvG transcript/protein sequences",
            "acquire authoritative Pv5.2.4 transcript/protein sequences",
            "perform deterministic sequence mapping with exact/unique and ambiguity tiers",
            "do not admit fuzzy identifier or accession-order mapping",
        ],
        "hard_boundaries":["MISSING_DATA_STAYS_MISSING","COORDINATE_SIMILARITY_NE_IDENTITY","SEQUENCE_SIMILARITY_NE_EXACT_IDENTITY","AMBIGUOUS_MAPS_STAY_AMBIGUOUS"],
    }
    (OUT/"bridge_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print("BRIDGE_SUMMARY",json.dumps(summary,sort_keys=True),flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
