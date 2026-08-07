#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JANUS-LAPIS v0.3.0 — Structured Preimage Reconstruction Engine.

Goal: recover REAL hidden plaintexts whose SHA-256 digests are recorded in
Hawkar-usls/janus-meta-registry.

This is deliberately not a general SHA-256 inverter. A target is admitted only
when the engine generates candidate bytes WITHOUT reading the hidden target
plaintext and hashlib.sha256(candidate).hexdigest() == target.

JANUS 113.8 mapping:
  /wormhole          -> target digest + allowed structural context
  Coherence Hold     -> competing candidate generators
  Entropy Graveyard  -> rejected exact-hash candidates
  Decoherence        -> exact SHA-256 witness
  Hippocampus        -> learned reconstruction templates + recovered truths
  Ouroboros          -> deterministic self-test and integrity summary
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import re
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

VERSION = "0.3.0-structured-preimage"
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
SEPARATORS = [" — ", " - ", " | ", ": ", " / ", " ", "_", "-", "|", "/"]
MAX_CANDIDATES_PER_TARGET = 120_000


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def encode_source(text: str, mode: str) -> bytes:
    if mode == "utf8":
        return text.encode("utf-8")
    if mode == "unicode_escape":
        return text.encode("unicode_escape")
    raise ValueError(mode)


def scalar_text(v: Any) -> Optional[str]:
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return None


def flatten_scalars(d: Dict[str, Any], prefix: str = "", depth: int = 1) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        s = scalar_text(v)
        if s is not None:
            out.append((key, s))
        elif depth > 0 and isinstance(v, dict):
            out.extend(flatten_scalars(v, key, depth - 1))
    return out


@dataclass
class Pair:
    file: str
    hash_path: str
    hash_key: str
    target_sha256: str
    source_path: str
    source_key: str
    plaintext: str
    encoding: str
    context: List[Tuple[str, str]]


def discover_pairs(meta_root: Path) -> List[Pair]:
    """Find only cryptographically VERIFIED string<->SHA pairs already present in JSON.

    Ground truth is used for scoring, then removed from the candidate context.
    We search the current dictionary plus up to two ancestor dictionaries because
    many JANUS manifests keep `hashes:{...}` beside the strings being hashed.
    """
    pairs: List[Pair] = []
    seen = set()

    def walk(obj: Any, file_rel: str, path: str, ancestors: List[Tuple[str, Dict[str, Any]]]):
        if isinstance(obj, dict):
            scopes = [(path, obj)] + ancestors[-2:]
            source_pool: List[Tuple[str, str, str]] = []  # fullpath, leafkey, value
            for scope_path, scope in scopes:
                for keypath, value in flatten_scalars(scope, depth=1):
                    leaf = keypath.split(".")[-1]
                    full = f"{scope_path}.{keypath}" if scope_path else keypath
                    if not (HEX64.fullmatch(value) and "sha" in leaf.lower()):
                        source_pool.append((full, leaf, value))

            for hk, hv in obj.items():
                if not (isinstance(hv, str) and HEX64.fullmatch(hv) and "sha256" in hk.lower()):
                    continue
                target = hv.lower()
                hash_path = f"{path}.{hk}" if path else hk
                for source_path, source_key, text in source_pool:
                    for mode in ("utf8", "unicode_escape"):
                        if sha256_bytes(encode_source(text, mode)) != target:
                            continue
                        sig = (file_rel, hash_path, target, source_path, mode)
                        if sig in seen:
                            continue
                        seen.add(sig)
                        # Blind context: remove target plaintext, duplicate copies of it,
                        # and all SHA-looking values. Structural keys and other values remain.
                        context: List[Tuple[str, str]] = []
                        for scope_path2, scope2 in scopes:
                            for keypath2, value2 in flatten_scalars(scope2, depth=1):
                                leaf2 = keypath2.split(".")[-1]
                                full2 = f"{scope_path2}.{keypath2}" if scope_path2 else keypath2
                                if value2 == text:
                                    continue
                                if HEX64.fullmatch(value2) and "sha" in leaf2.lower():
                                    continue
                                if full2 == source_path:
                                    continue
                                context.append((full2, value2))
                        # Add file provenance as side information; this is not plaintext.
                        context += [
                            ("__file__", file_rel),
                            ("__basename__", Path(file_rel).name),
                            ("__stem__", Path(file_rel).stem),
                        ]
                        pairs.append(Pair(file_rel, hash_path, hk, target, source_path,
                                          source_key, text, mode, dedupe_context(context)))
            for k, v in obj.items():
                child = f"{path}.{k}" if path else str(k)
                walk(v, file_rel, child, ancestors + [(path, obj)])
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, file_rel, f"{path}[{i}]", ancestors)

    for p in sorted(meta_root.rglob("*.json")):
        if ".git" in p.parts:
            continue
        try:
            obj = json.loads(p.read_text("utf-8"))
        except Exception:
            continue
        walk(obj, p.relative_to(meta_root).as_posix(), "", [])
    return pairs


def dedupe_context(items: Sequence[Tuple[str, str]]) -> List[Tuple[str, str]]:
    out = []
    seen = set()
    for k, v in items:
        if (k, v) not in seen:
            seen.add((k, v)); out.append((k, v))
    return out


def leaf_name(path: str) -> str:
    return path.split(".")[-1].split("[")[0]


def context_map(pair: Pair) -> Dict[str, List[str]]:
    m: Dict[str, List[str]] = {}
    for k, v in pair.context:
        m.setdefault(leaf_name(k), []).append(v)
    return m


# A learned template is a sequence of literal and field-key segments.
Segment = Tuple[str, str]  # ("lit"|"key", payload)


def induce_template(pair: Pair) -> Optional[Tuple[Segment, ...]]:
    text = pair.plaintext
    # Prefer longer values so e.g. full titles win over pieces.
    options: List[Tuple[str, str]] = []
    for k, v in pair.context:
        key = leaf_name(k)
        if not v or len(v) > len(text) or v == text:
            continue
        if v in text and key not in {"__file__", "__basename__", "__stem__"}:
            options.append((key, v))
    options.sort(key=lambda kv: (-len(kv[1]), kv[0]))
    if not options:
        return None

    segs: List[Segment] = []
    pos = 0
    lit = []
    used_keys = 0
    while pos < len(text):
        hit = None
        for key, value in options:
            if text.startswith(value, pos):
                hit = (key, value); break
        if hit:
            if lit:
                segs.append(("lit", "".join(lit))); lit = []
            segs.append(("key", hit[0])); used_keys += 1
            pos += len(hit[1])
        else:
            lit.append(text[pos]); pos += 1
    if lit:
        segs.append(("lit", "".join(lit)))
    if used_keys == 0:
        return None
    return tuple(segs)


def template_signature(pair: Pair, segs: Tuple[Segment, ...]) -> Tuple[str, str, Tuple[Segment, ...]]:
    return (pair.source_key, pair.encoding, segs)


def render_template(segs: Sequence[Segment], cmap: Dict[str, List[str]], limit: int = 5000) -> Iterator[str]:
    slots: List[List[str]] = []
    for kind, payload in segs:
        if kind == "lit":
            slots.append([payload])
        else:
            vals = cmap.get(payload, [])
            if not vals:
                return
            # cap duplicate/large context fan-out
            slots.append(list(dict.fromkeys(vals))[:8])
    n = 0
    for combo in itertools.product(*slots):
        yield "".join(combo)
        n += 1
        if n >= limit:
            return


def file_genealogy_candidates(pair: Pair) -> Iterator[str]:
    cmap = context_map(pair)
    for key in ("__basename__", "__stem__", "filename", "artifact_id", "artifact_uuid", "signal_id", "layer_id"):
        for v in cmap.get(key, []):
            yield v
            yield v.upper()
            yield v.lower()
            yield v.replace(".json", "")
            yield v.replace("-", "_")
            yield v.replace("_", "-")
            yield re.sub(r"\.sha256$", "", v, flags=re.I)
            yield re.sub(r"\.sha256\.json$", ".json", v, flags=re.I)


def sibling_join_candidates(pair: Pair) -> Iterator[str]:
    """Generate small compositions from immediate semantic atoms.

    This is constrained deliberately. It is not brute-forcing arbitrary bytes;
    it asks whether nearby registry metadata determines the hidden identifier.
    """
    atoms: List[str] = []
    banned_keys = {"__file__", "__basename__", "__stem__", "created_at_utc", "timestamp_utc"}
    for k, v in pair.context:
        leaf = leaf_name(k)
        if leaf in banned_keys or not v or len(v) > 120:
            continue
        if HEX64.fullmatch(v):
            continue
        if v not in atoms:
            atoms.append(v)
    atoms = atoms[:9]
    # Singletons with harmless wrappers/case conventions.
    for a in atoms:
        yield a
        yield a.upper()
        yield a.lower()
    # Two-field compositions are cheap and recover many identifier formats.
    for a, b in itertools.permutations(atoms, 2):
        for sep in SEPARATORS:
            yield a + sep + b
    # Three-field compositions with the most common JANUS separators.
    tri_seps = [(" — ", " | "), (" | ", " | "), (" - ", " | "), (" ", " "), ("_", "_")]
    for a, b, c in itertools.permutations(atoms[:7], 3):
        for s1, s2 in tri_seps:
            yield a + s1 + b + s2 + c
    # Four-field identifier convention: Artist — Track | Album | Year
    for a, b, c, d in itertools.permutations(atoms[:6], 4):
        yield f"{a} — {b} | {c} | {d}"


def signal_reassembly_candidates(pair: Pair) -> Iterator[str]:
    atoms = []
    for k, v in pair.context:
        if leaf_name(k) in {"__file__", "__basename__", "__stem__"}:
            continue
        if 1 <= len(v) <= 120 and not HEX64.fullmatch(v):
            atoms.extend(re.findall(r"[A-Za-z0-9]+", v))
    toks = list(dict.fromkeys(atoms))[:16]
    # Short deterministic windows, useful for SIGNAL / ID fields.
    for r in (2, 3, 4):
        for combo in itertools.combinations(toks, r):
            yield "_".join(t.upper() for t in combo)
            yield "-".join(t.upper() for t in combo)
            yield " ".join(combo)


def unique_candidates(gens: Sequence[Tuple[str, Iterable[str]]], budget: int) -> Iterator[Tuple[str, str]]:
    seen = set(); n = 0
    for method, gen in gens:
        for c in gen:
            if c in seen:
                continue
            seen.add(c); n += 1
            yield method, c
            if n >= budget:
                return


def exact_witness(pair: Pair, candidate: str) -> bool:
    return sha256_bytes(encode_source(candidate, pair.encoding)) == pair.target_sha256


@dataclass
class Result:
    index: int
    file: str
    hash_path: str
    source_path: str
    source_key: str
    encoding: str
    target_sha256: str
    recovered: bool
    method: str
    recovered_plaintext: str
    ground_truth_plaintext: str
    candidates_tested: int


def recover_pair(pair: Pair, all_pairs: Sequence[Pair], budget: int) -> Result:
    # Learn only from OTHER targets; remove duplicate plaintexts so the answer is
    # not simply copied from another record containing the same preimage.
    templates = []
    seen_templates = set()
    for other in all_pairs:
        if other.target_sha256 == pair.target_sha256 or other.plaintext == pair.plaintext:
            continue
        t = induce_template(other)
        if not t:
            continue
        sig = template_signature(other, t)
        if sig not in seen_templates:
            seen_templates.add(sig); templates.append(sig)

    cmap = context_map(pair)
    template_candidates: List[str] = []
    # Strongest first: same semantic source field + encoding.
    for source_key, enc, segs in templates:
        if source_key == pair.source_key and enc == pair.encoding:
            template_candidates.extend(render_template(segs, cmap, limit=2000))
    # Then same encoding, allowing cross-field transfer of a registry grammar.
    for source_key, enc, segs in templates:
        if source_key != pair.source_key and enc == pair.encoding:
            template_candidates.extend(render_template(segs, cmap, limit=300))

    gens: List[Tuple[str, Iterable[str]]] = [
        ("learned_template", template_candidates),
        ("file_genealogy", file_genealogy_candidates(pair)),
        ("sibling_composition", sibling_join_candidates(pair)),
        ("signal_reassembly", signal_reassembly_candidates(pair)),
    ]
    tested = 0
    for method, candidate in unique_candidates(gens, budget):
        tested += 1
        if exact_witness(pair, candidate):
            return Result(0, pair.file, pair.hash_path, pair.source_path, pair.source_key,
                          pair.encoding, pair.target_sha256, True, method, candidate,
                          pair.plaintext, tested)
    return Result(0, pair.file, pair.hash_path, pair.source_path, pair.source_key,
                  pair.encoding, pair.target_sha256, False, "", "", pair.plaintext, tested)


def init_db(path: Path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS truths(target_sha256 TEXT PRIMARY KEY, source_key TEXT, encoding TEXT, method TEXT, plaintext TEXT, file TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS graveyard(target_sha256 TEXT, candidates_tested INTEGER, source_key TEXT, file TEXT)")
    con.commit(); return con


def run(meta_root: Path, outdir: Path, budget: int) -> Dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    pairs = discover_pairs(meta_root)
    # Keep unique target/source/mode challenges. Prefer shorter textual preimages
    # for the first exact-reconstruction benchmark; long prose is a later tier.
    uniq: List[Pair] = []
    seen = set()
    for p in sorted(pairs, key=lambda x: (len(x.plaintext), x.target_sha256, x.file)):
        key = (p.target_sha256, p.plaintext, p.encoding)
        if key in seen: continue
        seen.add(key); uniq.append(p)

    con = init_db(outdir / "janus.db")
    results: List[Result] = []
    for i, pair in enumerate(uniq, 1):
        r = recover_pair(pair, uniq, budget); r.index = i; results.append(r)
        if r.recovered:
            con.execute("INSERT OR REPLACE INTO truths VALUES(?,?,?,?,?,?)",
                        (r.target_sha256, r.source_key, r.encoding, r.method, r.recovered_plaintext, r.file))
        else:
            con.execute("INSERT INTO graveyard VALUES(?,?,?,?)",
                        (r.target_sha256, r.candidates_tested, r.source_key, r.file))
    con.commit(); con.close()

    if results:
        with (outdir / "results.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
            w.writeheader(); [w.writerow(asdict(r)) for r in results]

    recovered = [r for r in results if r.recovered]
    by_method: Dict[str, int] = {}
    for r in recovered: by_method[r.method] = by_method.get(r.method, 0) + 1
    summary = {
        "experiment": "JANUS-LAPIS Structured Preimage Reconstruction",
        "version": VERSION,
        "janus_identity": "JANUS 113.8",
        "verified_real_hash_plaintext_pairs": len(results),
        "exact_preimages_recovered": len(recovered),
        "exact_recovery_rate": (len(recovered) / len(results)) if results else 0.0,
        "by_method": by_method,
        "candidate_budget_per_target": budget,
        "admission_rule": "Only SHA256(generated_candidate_bytes) == target is success.",
        "boundary": "This is constrained preimage reconstruction using Meta Registry structure/context, not arbitrary SHA-256 inversion."
    }
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")

    lines = [
        "# JANUS-LAPIS v0.3.0 — Structured Preimage Reconstruction", "",
        f"Verified real SHA↔plaintext challenges: **{len(results)}**",
        f"Exact hidden preimages recovered: **{len(recovered)}/{len(results)}**", "",
        "## Exact witnesses", ""
    ]
    for r in recovered[:100]:
        lines += [f"### {r.index:03d} — {r.method}", "",
                  f"- File: `{r.file}`", f"- Hash field: `{r.hash_path}`",
                  f"- SHA-256: `{r.target_sha256}`", f"- Encoding: `{r.encoding}`",
                  "", "```text", r.recovered_plaintext, "```", ""]
    if not recovered:
        lines += ["No exact hidden preimage was recovered. Gate remains closed.", ""]
    lines += ["## Boundary", "",
              "A recovered item is a genuine exact preimage witness inside a constrained registry-generated search space. It is not evidence of a general inverse for SHA-256."]
    (outdir / "REPORT.md").write_text("\n".join(lines), "utf-8")
    return summary


def selftest(outdir: Path):
    # Proves the exact witness rule and template mechanism without claiming more.
    fake = Pair("x.json", "h.sha256_identifier_utf8", "sha256_identifier_utf8",
                sha256_bytes("ERA — Ameno".encode()), "identifier", "identifier",
                "ERA — Ameno", "utf8", [("artist", "ERA"), ("track", "Ameno")])
    train = Pair("y.json", "h.sha256_identifier_utf8", "sha256_identifier_utf8",
                 sha256_bytes("SNAP! — The Power".encode()), "identifier", "identifier",
                 "SNAP! — The Power", "utf8", [("artist", "SNAP!"), ("track", "The Power")])
    r = recover_pair(fake, [fake, train], 5000)
    assert r.recovered and r.recovered_plaintext == "ERA — Ameno"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "selftest.json").write_text(json.dumps(asdict(r), indent=2), "utf-8")
    print(json.dumps({"selftest":"PASS","method":r.method,"plaintext":r.recovered_plaintext}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta-root", type=Path)
    ap.add_argument("--outdir", type=Path, default=Path("reverse_gate_runs/preimage"))
    ap.add_argument("--budget", type=int, default=MAX_CANDIDATES_PER_TARGET)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(a.outdir); return
    if not a.meta_root:
        ap.error("--meta-root required")
    print(json.dumps(run(a.meta_root, a.outdir, a.budget), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
