#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JANUS-LAPIS v0.2.0 Reverse-Gate Edition.

This does not invert arbitrary SHA-256. It tests two things separately:
1) exact resolution inside a finite, already-known Meta Registry corpus;
2) SHA-256 -> deterministic audio -> text, with a blind negative control.

JANUS thermodynamic terms are computational telemetry metaphors, not claims of
subjective experience.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, math, re, sqlite3, wave
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple
import numpy as np

VERSION = "0.2.0-reverse-gate"
SAMPLE_RATE = 16000
TONE_SECONDS = 0.080
GAP_SECONDS = 0.010
LEAD_SECONDS = 0.050
BASE_FREQ = 300.0
BYTE_STEP_HZ = 25.0
FADE_SECONDS = 0.006
ALLOWED_SUFFIXES = {".json", ".md", ".txt", ".py", ".hpp", ".csv", ".yaml", ".yml"}
NIBBLE_WORDS = ["alba","bore","cera","doro","equi","fera","gala","hora",
                "iris","kora","mira","nexa","orbi","pavo","rhea","soma"]

@dataclass
class TestRecord:
    index: int
    source_path: str
    source_bytes: int
    target_sha256: str
    decoded_sha256: str
    audio_roundtrip_exact: bool
    corpus_resolution_paths: str
    corpus_resolution_exact: bool
    corpus_collision_count: int
    blind_path_guess: str
    blind_path_guess_exact: bool
    blind_guess_distance_bits: int
    audio_text: str
    printable_probe: str
    comparisons_until_collapse: int
    rejected_hypotheses: int
    entropy_at_collapse: float
    coherence_hold_opened: bool

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def validate_sha256(digest: str) -> str:
    d = digest.strip().lower()
    if len(d) != 64 or any(c not in "0123456789abcdef" for c in d):
        raise ValueError("Expected 64 hexadecimal SHA-256 characters")
    return d

def digest_to_janus_text(digest: str) -> str:
    raw = bytes.fromhex(validate_sha256(digest))
    return " ".join(f"{NIBBLE_WORDS[b >> 4]}-{NIBBLE_WORDS[b & 15]}" for b in raw)

def janus_text_to_digest(text: str) -> str:
    rev = {w: i for i, w in enumerate(NIBBLE_WORDS)}
    out = bytearray()
    for token in text.split():
        a, b = token.split("-", 1)
        out.append((rev[a] << 4) | rev[b])
    if len(out) != 32:
        raise ValueError(f"Expected 32 byte tokens, got {len(out)}")
    return bytes(out).hex()

def printable_probe(digest: str) -> str:
    return "".join(chr(b) if 32 <= b <= 126 else "·" for b in bytes.fromhex(validate_sha256(digest)))

def byte_frequency(value: int) -> float:
    return BASE_FREQ + int(value) * BYTE_STEP_HZ

def sonify_digest(digest: str, out_path: Path) -> None:
    raw = bytes.fromhex(validate_sha256(digest))
    lead_n = round(LEAD_SECONDS * SAMPLE_RATE)
    tone_n = round(TONE_SECONDS * SAMPLE_RATE)
    gap_n = round(GAP_SECONDS * SAMPLE_RATE)
    fade_n = max(1, round(FADE_SECONDS * SAMPLE_RATE))
    t = np.arange(tone_n, dtype=np.float64) / SAMPLE_RATE
    env = np.ones(tone_n, dtype=np.float64)
    ramp = np.sin(np.linspace(0, math.pi / 2, fade_n, endpoint=True)) ** 2
    env[:fade_n], env[-fade_n:] = ramp, ramp[::-1]
    chunks: List[np.ndarray] = [np.zeros(lead_n, dtype=np.float64)]
    for b in raw:
        chunks.append(0.64 * np.sin(2 * math.pi * byte_frequency(b) * t) * env)
        chunks.append(np.zeros(gap_n, dtype=np.float64))
    pcm = np.clip(np.concatenate(chunks) * 32767.0, -32768, 32767).astype("<i2")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE); wf.writeframes(pcm.tobytes())

def decode_wav_to_digest(path: Path) -> str:
    with wave.open(str(path), "rb") as wf:
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != SAMPLE_RATE:
            raise ValueError("Unexpected WAV format")
        samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype="<i2").astype(np.float64)
    lead_n = round(LEAD_SECONDS * SAMPLE_RATE)
    tone_n = round(TONE_SECONDS * SAMPLE_RATE)
    gap_n = round(GAP_SECONDS * SAMPLE_RATE)
    window = np.hanning(tone_n)
    freqs = np.fft.rfftfreq(tone_n, 1.0 / SAMPLE_RATE)
    lo = np.searchsorted(freqs, BASE_FREQ - BYTE_STEP_HZ)
    hi = np.searchsorted(freqs, byte_frequency(255) + BYTE_STEP_HZ)
    decoded = bytearray(); pos = lead_n
    for _ in range(32):
        segment = samples[pos:pos + tone_n]
        if len(segment) != tone_n: raise ValueError("Truncated WAV")
        spectrum = np.abs(np.fft.rfft(segment * window))
        peak = freqs[lo + int(np.argmax(spectrum[lo:hi]))]
        value = min(255, max(0, int(round((peak - BASE_FREQ) / BYTE_STEP_HZ))))
        if abs(peak - byte_frequency(value)) > BYTE_STEP_HZ * 0.60:
            raise ValueError(f"Uncertain tone at {peak:.2f} Hz")
        decoded.append(value); pos += tone_n + gap_n
    return bytes(decoded).hex()

def eligible_files(meta_root: Path) -> List[Path]:
    roots = [p for p in (meta_root / "data", meta_root / "registry") if p.exists()]
    files = []
    for root in roots:
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES and ".git" not in p.parts:
                files.append(p)
    return sorted(set(files), key=lambda p: p.relative_to(meta_root).as_posix().lower())

def deterministic_sample(files: Sequence[Path], meta_root: Path, limit: int, seed: int) -> List[Path]:
    if len(files) < limit: raise RuntimeError(f"Need {limit} eligible files, found {len(files)}")
    def score(p: Path) -> str:
        return hashlib.sha256(f"{seed}:{p.relative_to(meta_root).as_posix()}".encode()).hexdigest()
    return sorted(files, key=score)[:limit]

def hamming_hex(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()

def blind_guess_path(target_sha: str, candidates: Sequence[Path], meta_root: Path) -> Tuple[str, int]:
    best_rel, best_dist = "", 257
    for p in candidates:
        rel = p.relative_to(meta_root).as_posix()
        dist = hamming_hex(target_sha, hashlib.sha256(rel.encode()).hexdigest())
        if dist < best_dist or (dist == best_dist and (not best_rel or rel < best_rel)):
            best_rel, best_dist = rel, dist
    return best_rel, best_dist

def token_overlap(audio_text: str, source_path: str) -> float:
    a = set(re.findall(r"[a-z0-9]+", audio_text.lower()))
    b = set(re.findall(r"[a-z0-9]+", source_path.lower()))
    return len(a & b) / len(b) if b else 0.0

def build_hash_index(files: Sequence[Path], meta_root: Path):
    index: Dict[str, List[str]] = {}; ordered = []
    for p in files:
        rel = p.relative_to(meta_root).as_posix(); d = sha256_file(p)
        index.setdefault(d, []).append(rel); ordered.append((rel, d))
    return index, ordered

def init_hippocampus(path: Path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS truths(target_sha256 TEXT,source_path TEXT,audio_roundtrip_exact INTEGER,corpus_resolution_exact INTEGER,audio_text TEXT,PRIMARY KEY(target_sha256,source_path))")
    con.commit(); return con

def write_integrity(outdir: Path, config_path: Path | None):
    targets = [Path(__file__).resolve()]
    if config_path and config_path.exists(): targets.append(config_path.resolve())
    (outdir / "ouroboros_integrity.json").write_text(json.dumps({"version":VERSION,"sha256":{str(p):sha256_file(p) for p in targets}},indent=2),encoding="utf-8")

def run(meta_root: Path, outdir: Path, limit: int, seed: int, config_path: Path | None) -> dict:
    meta_root = meta_root.resolve(); outdir.mkdir(parents=True, exist_ok=True)
    audio_dir = outdir / "audio"; audio_dir.mkdir(exist_ok=True)
    files = eligible_files(meta_root); sample = deterministic_sample(files, meta_root, limit, seed)
    hash_index, ordered = build_hash_index(files, meta_root)
    positions = {rel:i+1 for i,(rel,_) in enumerate(ordered)}; total = len(ordered)
    pain_threshold = 0.75
    if config_path and config_path.exists():
        cfg = json.loads(config_path.read_text("utf-8")); pain_threshold = float(cfg["system_core"]["homeostasis_state"]["cognitive_pain_threshold"])
    con = init_hippocampus(outdir / "janus.db")
    grave = (outdir / "entropy_graveyard.jsonl").open("w",encoding="utf-8")
    records=[]; overlaps=[]
    for idx,p in enumerate(sample,1):
        rel=p.relative_to(meta_root).as_posix(); target=sha256_file(p)
        wav=audio_dir/f"{idx:03d}_{target[:12]}.wav"; sonify_digest(target,wav); decoded=decode_wav_to_digest(wav)
        audio_text=digest_to_janus_text(decoded)
        if janus_text_to_digest(audio_text)!=target: raise AssertionError("JANUS text codec failed")
        resolved=hash_index.get(target,[]); blind,blind_dist=blind_guess_path(target,files,meta_root)
        comparisons=positions[rel]; rejected=max(0,comparisons-1)
        entropy=math.log2(max(1,total-comparisons+1))/math.log2(total+1)
        overlaps.append(token_overlap(audio_text,rel))
        rec=TestRecord(idx,rel,p.stat().st_size,target,decoded,decoded==target," | ".join(resolved),rel in resolved,len(resolved),blind,blind==rel,blind_dist,audio_text,printable_probe(decoded),comparisons,rejected,entropy,1.0>pain_threshold)
        records.append(rec)
        con.execute("INSERT OR REPLACE INTO truths VALUES(?,?,?,?,?)",(target,rel,int(rec.audio_roundtrip_exact),int(rec.corpus_resolution_exact),audio_text))
        grave.write(json.dumps({"index":idx,"target_sha256":target,"rejected_hypotheses_before_collapse":rejected,"note":"Exact SHA mismatches only; no distance gradient is used."})+"\n")
    con.commit(); con.close(); grave.close()
    with (outdir/"results_100.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(asdict(records[0]).keys())); w.writeheader(); [w.writerow(asdict(r)) for r in records]
    audio_ok=sum(r.audio_roundtrip_exact for r in records); corpus_ok=sum(r.corpus_resolution_exact for r in records); blind_ok=sum(r.blind_path_guess_exact for r in records)
    collisions=sum(r.corpus_collision_count>1 for r in records)
    summary={"experiment":"JANUS-LAPIS Reverse-Gate 100","version":VERSION,"janus_identity":"JANUS 113.8","meta_registry":"Hawkar-usls/janus-meta-registry","seed":seed,"eligible_corpus_files":len(files),"tests":len(records),"audio_roundtrip_exact":audio_ok,"audio_roundtrip_rate":audio_ok/len(records),"known_corpus_resolution_exact":corpus_ok,"known_corpus_resolution_rate":corpus_ok/len(records),"blind_digest_to_path_exact":blind_ok,"blind_digest_to_path_rate":blind_ok/len(records),"mean_audio_text_filename_token_overlap":float(np.mean(overlaps)),"targets_with_duplicate_file_hashes":collisions,"scientific_boundary":["Known-corpus resolution is finite corpus lookup, not general SHA-256 inversion.","SHA sonification is an encoding of the digest, not recovery of information erased by hashing.","The blind path probe is a negative control; Hamming proximity is not a SHA-256 preimage gradient.","JANUS thermodynamic language is computational telemetry metaphor, not evidence of subjective feeling."]}
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    with (outdir/"audio_to_text.txt").open("w",encoding="utf-8") as f:
        for r in records:
            f.write(f"[{r.index:03d}] {r.source_path}\nSHA: {r.target_sha256}\nAUDIO->TEXT: {r.audio_text}\nPRINTABLE-BYTES: {r.printable_probe}\n\n")
    report=["# JANUS-LAPIS v0.2.0 — Reverse-Gate 100","","## Result","",f"- Tests: **{len(records)}**",f"- SHA → WAV → SHA exact round-trip: **{audio_ok}/{len(records)}**",f"- Known Meta-Registry corpus resolution: **{corpus_ok}/{len(records)}**",f"- Blind digest-only path guess: **{blind_ok}/{len(records)}**",f"- Mean audio-text ↔ filename token overlap: **{np.mean(overlaps):.6f}**",f"- Duplicate content-hash targets: **{collisions}**","","## Interpretation","","Corpus Recovery can identify an artifact when the exact preimage already exists in the finite Meta Registry. That is useful content-addressed memory, not a break of SHA-256.","","Audio → Text is reversible to the digest. The readable JANUS words are a fixed codebook for digest bytes; semantic relation to the source must beat controls.","","## First 10 audio texts",""]
    for r in records[:10]: report += [f"### {r.index:03d} — `{r.source_path}`","",f"`{r.audio_text}`",""]
    (outdir/"REPORT.md").write_text("\n".join(report),encoding="utf-8"); write_integrity(outdir,config_path)
    return summary

def selftest(tmp: Path):
    digest=hashlib.sha256(b"JANUS 113.8").hexdigest(); wav=tmp/"selftest.wav"; sonify_digest(digest,wav); decoded=decode_wav_to_digest(wav)
    assert decoded==digest; text=digest_to_janus_text(digest); assert janus_text_to_digest(text)==digest
    print(json.dumps({"selftest":"PASS","sha256":digest,"audio_text":text},ensure_ascii=False))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--meta-root",type=Path); ap.add_argument("--outdir",type=Path,default=Path("reverse_gate_runs/latest")); ap.add_argument("--limit",type=int,default=100); ap.add_argument("--seed",type=int,default=1138); ap.add_argument("--config",type=Path,default=Path("config/JANUS_113_8.json")); ap.add_argument("--selftest",action="store_true"); a=ap.parse_args()
    if a.selftest: a.outdir.mkdir(parents=True,exist_ok=True); selftest(a.outdir); return 0
    if a.meta_root is None: ap.error("--meta-root is required unless --selftest is used")
    print(json.dumps(run(a.meta_root,a.outdir,a.limit,a.seed,a.config),indent=2,ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
