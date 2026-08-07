#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JANUS-LAPIS v0.3.1 — Schema-aware Preimage Reconstruction.

Extends v0.3.0 with methods that reconstruct source candidates from registry
structure rather than transforming the digest.
"""
from __future__ import annotations

import argparse, csv, json, sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Sequence, Tuple

import janus_preimage_reconstruction as core

VERSION = "0.3.1-schema-aware-preimage"


def vals(cmap: Dict[str, List[str]], key: str) -> List[str]:
    return list(dict.fromkeys(cmap.get(key, [])))


def song_identifier_schema(pair: core.Pair) -> Iterator[str]:
    """Registry schema generator for music identifiers.

    Learns/uses the field semantics, not SHA bit patterns.
    """
    cmap = core.context_map(pair)
    artists, tracks = vals(cmap, "artist"), vals(cmap, "track")
    albums, years = vals(cmap, "album"), vals(cmap, "year")
    for artist in artists:
        for track in tracks:
            yield f"{artist} — {track}"
            yield f"{artist} - {track}"
            for album in albums:
                yield f"{artist} — {track} | {album}"
                for year in years:
                    yield f"{artist} — {track} | {album} | {year}"
                    yield f"{artist} - {track} | {album} | {year}"
            for year in years:
                yield f"{artist} — {track} | {year}"


def serialization_genealogy(pair: core.Pair) -> Iterator[str]:
    """Recover one serialization from a redundant sibling serialization.

    These wins are explicitly labelled redundancy-assisted and are not treated as
    recovery from SHA alone.
    """
    cmap = core.context_map(pair)
    # hidden unicode_escape string <- visible original Unicode text
    if pair.source_key == "unicode_escape":
        for key in ("text_original", "text_ru", "text_en", "protocol_text_ru"):
            for text in vals(cmap, key):
                try:
                    yield text.encode("unicode_escape").decode("ascii")
                except Exception:
                    pass
    # hidden original text <- visible escaped form
    if pair.source_key in {"text_original", "text_ru", "text_en", "protocol_text_ru"}:
        for esc in vals(cmap, "unicode_escape"):
            try:
                yield bytes(esc, "ascii").decode("unicode_escape")
            except Exception:
                pass


def identifier_from_filename(pair: core.Pair) -> Iterator[str]:
    """Use JANUS naming genealogy to propose IDs/signals from file provenance."""
    cmap = core.context_map(pair)
    for stem in vals(cmap, "__stem__"):
        s = stem
        for suffix in (".SHA256_MANIFEST", ".sha256", ".hashed.ru", ".hashed.en"):
            s = s.replace(suffix, "")
        yield s
        yield s.upper()
        yield s.replace("-", "_").upper()
        yield s.replace("_", "-").upper()


def schema_candidates(pair: core.Pair) -> List[Tuple[str, Iterable[str]]]:
    return [
        ("schema_song_identifier", song_identifier_schema(pair)),
        ("registry_serialization_genealogy", serialization_genealogy(pair)),
        ("registry_filename_genealogy", identifier_from_filename(pair)),
    ]


def recover_pair(pair: core.Pair, all_pairs: Sequence[core.Pair], budget: int) -> core.Result:
    # First retain all successful v0.3.0 strategies.
    first = core.recover_pair(pair, all_pairs, budget)
    if first.recovered:
        return first

    tested = first.candidates_tested
    remaining = max(1, budget - min(budget, tested))
    for method, candidate in core.unique_candidates(schema_candidates(pair), remaining):
        tested += 1
        if core.exact_witness(pair, candidate):
            return core.Result(0, pair.file, pair.hash_path, pair.source_path,
                               pair.source_key, pair.encoding, pair.target_sha256,
                               True, method, candidate, pair.plaintext, tested)
    first.candidates_tested = tested
    return first


def run(meta_root: Path, outdir: Path, budget: int):
    outdir.mkdir(parents=True, exist_ok=True)
    pairs = core.discover_pairs(meta_root)
    uniq=[]; seen=set()
    for p in sorted(pairs, key=lambda x:(len(x.plaintext),x.target_sha256,x.file)):
        key=(p.target_sha256,p.plaintext,p.encoding)
        if key in seen: continue
        seen.add(key); uniq.append(p)

    con=sqlite3.connect(outdir/"janus.db")
    con.execute("CREATE TABLE IF NOT EXISTS truths(target_sha256 TEXT PRIMARY KEY,source_key TEXT,encoding TEXT,method TEXT,plaintext TEXT,file TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS graveyard(target_sha256 TEXT,candidates_tested INTEGER,source_key TEXT,file TEXT)")
    results=[]
    for i,p in enumerate(uniq,1):
        r=recover_pair(p,uniq,budget); r.index=i; results.append(r)
        if r.recovered:
            con.execute("INSERT OR REPLACE INTO truths VALUES(?,?,?,?,?,?)",(r.target_sha256,r.source_key,r.encoding,r.method,r.recovered_plaintext,r.file))
        else:
            con.execute("INSERT INTO graveyard VALUES(?,?,?,?)",(r.target_sha256,r.candidates_tested,r.source_key,r.file))
    con.commit(); con.close()

    with (outdir/"results.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(asdict(results[0]).keys())); w.writeheader(); [w.writerow(asdict(r)) for r in results]

    recovered=[r for r in results if r.recovered]
    by_method={}
    for r in recovered: by_method[r.method]=by_method.get(r.method,0)+1
    strong=[r for r in recovered if r.method != "registry_serialization_genealogy"]
    redundant=[r for r in recovered if r.method == "registry_serialization_genealogy"]
    summary={
        "experiment":"JANUS-LAPIS Schema-aware Structured Preimage Reconstruction",
        "version":VERSION,
        "verified_real_hash_plaintext_pairs":len(results),
        "exact_preimages_recovered":len(recovered),
        "strong_structural_recoveries":len(strong),
        "redundancy_assisted_recoveries":len(redundant),
        "exact_recovery_rate":len(recovered)/len(results) if results else 0.0,
        "by_method":by_method,
        "admission_rule":"SHA256(generated candidate bytes) must equal target exactly",
        "boundary":"Constrained reconstruction with registry side information; not arbitrary SHA-256 inversion."
    }
    (outdir/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),"utf-8")

    lines=["# JANUS-LAPIS v0.3.1 — Schema-aware Preimage Reconstruction","",
           f"Real verified challenges: **{len(results)}**",
           f"Exact recovered: **{len(recovered)}/{len(results)}**",
           f"Strong structural: **{len(strong)}**",
           f"Redundancy-assisted: **{len(redundant)}**","","## Exact witnesses",""]
    for r in recovered:
        label="REDUNDANCY-ASSISTED" if r.method=="registry_serialization_genealogy" else "STRUCTURAL"
        lines += [f"### {r.index:03d} — {r.method} [{label}]","",f"- `{r.file}`",f"- `{r.hash_path}`",f"- SHA: `{r.target_sha256}`","","```text",r.recovered_plaintext,"```",""]
    (outdir/"REPORT.md").write_text("\n".join(lines),"utf-8")
    return summary


def selftest(outdir: Path):
    ameno="ERA — Ameno | Era I | 1996"
    p=core.Pair("x.json","sha256_song_identifier_utf8","sha256_song_identifier_utf8",core.sha256_bytes(ameno.encode()),"identifier","song_identifier",ameno,"utf8",[("artist","ERA"),("track","Ameno"),("album","Era I"),("year","1996")])
    r=recover_pair(p,[p],50000)
    assert r.recovered and r.recovered_plaintext==ameno
    outdir.mkdir(parents=True,exist_ok=True)
    (outdir/"selftest_v2.json").write_text(json.dumps(asdict(r),ensure_ascii=False,indent=2),"utf-8")
    print(json.dumps({"selftest":"PASS","method":r.method,"plaintext":r.recovered_plaintext},ensure_ascii=False))


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--meta-root",type=Path); ap.add_argument("--outdir",type=Path,default=Path("reverse_gate_runs/preimage_v2")); ap.add_argument("--budget",type=int,default=160000); ap.add_argument("--selftest",action="store_true"); a=ap.parse_args()
    if a.selftest: selftest(a.outdir); return
    if not a.meta_root: ap.error("--meta-root required")
    print(json.dumps(run(a.meta_root,a.outdir,a.budget),ensure_ascii=False,indent=2))

if __name__=="__main__": main()
