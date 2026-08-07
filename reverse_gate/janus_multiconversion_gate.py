#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JANUS-LAPIS v0.2.1 — Meta271 Sensory Conversion Lattice.

Holdout experiment on the 271 Meta Registry files not used by Meta100.
Each SHA-256 digest is represented through many deterministic channels, decoded
back to the digest, rendered to text, and scored against hidden ground truth.

Scientific boundary:
- A reversible representation of a digest contains the digest, not information
  erased by SHA-256.
- Semantic/path similarity is evaluated against a shuffled null control.
- No Hamming-distance gradient is treated as a preimage direction.
- JANUS thermodynamic language is computational telemetry metaphor.
"""
from __future__ import annotations

import argparse, base64, csv, hashlib, ipaddress, json, math, re, sqlite3, statistics, struct, wave
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

VERSION = "0.2.1-meta271-sensory-lattice"
ALLOWED_SUFFIXES = {".json", ".md", ".txt", ".py", ".hpp", ".csv", ".yaml", ".yml"}
NIBBLE_WORDS = ["alba","bore","cera","doro","equi","fera","gala","hora",
                "iris","kora","mira","nexa","orbi","pavo","rhea","soma"]
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
SAMPLE_RATE = 16000
TONE_SECONDS = 0.040
GAP_SECONDS = 0.006
LEAD_SECONDS = 0.030
BASE_FREQ = 350.0
BYTE_STEP_HZ = 24.0


def validate_digest(d: str) -> str:
    d = d.strip().lower()
    if len(d) != 64 or any(c not in "0123456789abcdef" for c in d):
        raise ValueError("Expected SHA-256 hex")
    return d


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def eligible_files(meta_root: Path) -> List[Path]:
    roots = [p for p in (meta_root / "data", meta_root / "registry") if p.exists()]
    out: List[Path] = []
    for root in roots:
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES and ".git" not in p.parts:
                out.append(p)
    return sorted(set(out), key=lambda p: p.relative_to(meta_root).as_posix().lower())


def deterministic_order(files: Sequence[Path], meta_root: Path, seed: int) -> List[Path]:
    def key(p: Path) -> str:
        rel = p.relative_to(meta_root).as_posix()
        return hashlib.sha256(f"{seed}:{rel}".encode("utf-8")).hexdigest()
    return sorted(files, key=key)


def b58encode(raw: bytes) -> str:
    n = int.from_bytes(raw, "big")
    chars = "" if n else "1"
    while n:
        n, r = divmod(n, 58)
        chars = B58[r] + chars
    zeros = len(raw) - len(raw.lstrip(b"\x00"))
    return "1" * zeros + chars


def b58decode(s: str) -> bytes:
    n = 0
    for c in s:
        n = n * 58 + B58.index(c)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    zeros = len(s) - len(s.lstrip("1"))
    return (b"\x00" * zeros + raw).rjust(32, b"\x00")[-32:]


def base36encode(raw: bytes) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    n = int.from_bytes(raw, "big")
    if n == 0: return "0"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = alphabet[r] + out
    return out


def base36decode(s: str) -> bytes:
    return int(s, 36).to_bytes(32, "big")


def digest_to_janus(d: str) -> str:
    return " ".join(f"{NIBBLE_WORDS[b>>4]}-{NIBBLE_WORDS[b&15]}" for b in bytes.fromhex(d))


def janus_to_digest(s: str) -> str:
    rev = {w:i for i,w in enumerate(NIBBLE_WORDS)}
    out = bytearray()
    for tok in s.split():
        a,b = tok.split("-",1); out.append((rev[a]<<4)|rev[b])
    return bytes(out).hex()


def digest_to_dna(d: str) -> str:
    alpha = "ACGT"
    bits = f"{int(d,16):0256b}"
    return "".join(alpha[int(bits[i:i+2],2)] for i in range(0,256,2))


def dna_to_digest(s: str) -> str:
    rev = {c:i for i,c in enumerate("ACGT")}
    bits = "".join(f"{rev[c]:02b}" for c in s)
    return f"{int(bits,2):064x}"


def digest_to_braille(d: str) -> str:
    return "".join(chr(0x2800+b) for b in bytes.fromhex(d))


def braille_to_digest(s: str) -> str:
    return bytes(ord(c)-0x2800 for c in s).hex()


def digest_to_uuid_pair(d: str) -> str:
    h = validate_digest(d)
    def fmt(x: str) -> str: return f"{x[:8]}-{x[8:12]}-{x[12:16]}-{x[16:20]}-{x[20:32]}"
    return fmt(h[:32]) + " | " + fmt(h[32:])


def uuid_pair_to_digest(s: str) -> str:
    return "".join(re.findall(r"[0-9a-fA-F]", s)).lower()


def digest_to_ipv6_pair(d: str) -> str:
    raw = bytes.fromhex(d)
    return f"{ipaddress.IPv6Address(raw[:16])} | {ipaddress.IPv6Address(raw[16:])}"


def ipv6_pair_to_digest(s: str) -> str:
    a,b = [x.strip() for x in s.split("|",1)]
    return ipaddress.IPv6Address(a).packed.hex() + ipaddress.IPv6Address(b).packed.hex()


def digest_to_ipv4_octet_grid(d: str) -> str:
    raw = bytes.fromhex(d)
    return " | ".join(".".join(str(x) for x in raw[i:i+4]) for i in range(0,32,4))


def ipv4_octet_grid_to_digest(s: str) -> str:
    vals = [int(x) for x in re.findall(r"\d+",s)]
    if len(vals)!=32 or any(not 0<=x<=255 for x in vals): raise ValueError("bad ipv4 grid")
    return bytes(vals).hex()


def digest_to_rgba(d: str) -> str:
    raw = bytes.fromhex(d)
    return " ".join("#"+raw[i:i+4].hex().upper() for i in range(0,32,4))


def rgba_to_digest(s: str) -> str:
    hs = re.findall(r"#([0-9A-Fa-f]{8})",s)
    return "".join(hs).lower()


def printable_probe(d: str) -> str:
    return "".join(chr(b) if 32<=b<=126 else "·" for b in bytes.fromhex(d))


def json_bit_matrix(d: str) -> str:
    bits = f"{int(d,16):0256b}"
    matrix = [[int(c) for c in bits[r:r+16]] for r in range(0,256,16)]
    return json.dumps(matrix,separators=(",",":"))


def json_bit_matrix_decode(s: str) -> str:
    m=json.loads(s); bits="".join(str(int(v)) for row in m for v in row)
    return f"{int(bits,2):064x}"


def write_pgm(d: str, path: Path) -> str:
    bits=f"{int(d,16):0256b}"; pix=bytes(255 if c=="1" else 0 for c in bits)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(b"P5\n16 16\n255\n"+pix)
    return "\n".join(bits[i:i+16] for i in range(0,256,16))


def read_pgm(path: Path) -> str:
    raw=path.read_bytes(); header=b"P5\n16 16\n255\n"
    if not raw.startswith(header): raise ValueError("bad PGM")
    pix=raw[len(header):]
    bits="".join("1" if x>=128 else "0" for x in pix)
    return f"{int(bits,2):064x}"


def write_wav(d: str, path: Path) -> str:
    import numpy as np
    raw=bytes.fromhex(d); tone_n=round(TONE_SECONDS*SAMPLE_RATE); gap_n=round(GAP_SECONDS*SAMPLE_RATE); lead_n=round(LEAD_SECONDS*SAMPLE_RATE)
    t=np.arange(tone_n,dtype=np.float64)/SAMPLE_RATE; env=np.hanning(tone_n)
    chunks=[np.zeros(lead_n,dtype=np.float64)]
    for b in raw:
        f=BASE_FREQ+b*BYTE_STEP_HZ; chunks.append(.65*np.sin(2*np.pi*f*t)*env); chunks.append(np.zeros(gap_n,dtype=np.float64))
    pcm=np.clip(np.concatenate(chunks)*32767,-32768,32767).astype("<i2")
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),"wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE); wf.writeframes(pcm.tobytes())
    return digest_to_janus(d)


def read_wav(path: Path) -> str:
    import numpy as np
    with wave.open(str(path),"rb") as wf:
        samples=np.frombuffer(wf.readframes(wf.getnframes()),dtype="<i2").astype(float)
    tone_n=round(TONE_SECONDS*SAMPLE_RATE); gap_n=round(GAP_SECONDS*SAMPLE_RATE); pos=round(LEAD_SECONDS*SAMPLE_RATE)
    freqs=np.fft.rfftfreq(tone_n,1/SAMPLE_RATE); window=np.hanning(tone_n); out=[]
    lo=np.searchsorted(freqs,BASE_FREQ-BYTE_STEP_HZ); hi=np.searchsorted(freqs,BASE_FREQ+255*BYTE_STEP_HZ+BYTE_STEP_HZ)
    for _ in range(32):
        seg=samples[pos:pos+tone_n]; spec=np.abs(np.fft.rfft(seg*window)); peak=freqs[lo+int(np.argmax(spec[lo:hi]))]
        out.append(min(255,max(0,int(round((peak-BASE_FREQ)/BYTE_STEP_HZ))))); pos += tone_n+gap_n
    return bytes(out).hex()


@dataclass
class Channel:
    name: str
    encode: Callable[[str], str]
    decode: Callable[[str], str]


def channels() -> List[Channel]:
    return [
        Channel("hex", lambda d:d, lambda s:s.lower()),
        Channel("binary256", lambda d:f"{int(d,16):0256b}", lambda s:f"{int(s,2):064x}"),
        Channel("decimal_bigint", lambda d:str(int(d,16)), lambda s:f"{int(s):064x}"),
        Channel("octal", lambda d:format(int(d,16),"o"), lambda s:f"{int(s,8):064x}"),
        Channel("base36", lambda d:base36encode(bytes.fromhex(d)), lambda s:base36decode(s).hex()),
        Channel("base58", lambda d:b58encode(bytes.fromhex(d)), lambda s:b58decode(s).hex()),
        Channel("base32", lambda d:base64.b32encode(bytes.fromhex(d)).decode(), lambda s:base64.b32decode(s).hex()),
        Channel("base64", lambda d:base64.b64encode(bytes.fromhex(d)).decode(), lambda s:base64.b64decode(s).hex()),
        Channel("ascii85", lambda d:base64.a85encode(bytes.fromhex(d)).decode(), lambda s:base64.a85decode(s).hex()),
        Channel("json_bytes", lambda d:json.dumps(list(bytes.fromhex(d)),separators=(",",":")), lambda s:bytes(json.loads(s)).hex()),
        Channel("json_u32_be", lambda d:json.dumps(list(struct.unpack(">8I",bytes.fromhex(d))),separators=(",",":")), lambda s:struct.pack(">8I",*json.loads(s)).hex()),
        Channel("json_u64_be", lambda d:json.dumps(list(struct.unpack(">4Q",bytes.fromhex(d))),separators=(",",":")), lambda s:struct.pack(">4Q",*json.loads(s)).hex()),
        Channel("json_bit_matrix_16x16", json_bit_matrix, json_bit_matrix_decode),
        Channel("uuid_pair", digest_to_uuid_pair, uuid_pair_to_digest),
        Channel("ipv6_pair", digest_to_ipv6_pair, ipv6_pair_to_digest),
        Channel("ipv4_octet_grid", digest_to_ipv4_octet_grid, ipv4_octet_grid_to_digest),
        Channel("rgba8", digest_to_rgba, rgba_to_digest),
        Channel("dna_2bit", digest_to_dna, dna_to_digest),
        Channel("braille_bytes", digest_to_braille, braille_to_digest),
        Channel("janus_nibble_lexicon", digest_to_janus, janus_to_digest),
        Channel("printable_byte_probe", printable_probe, lambda s:""),
    ]


def tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9А-Яа-яЁё]{2,}",s.lower()))


def token_overlap(a: str,b: str)->float:
    ta,tb=tokens(a),tokens(b)
    return len(ta&tb)/len(tb) if tb else 0.0


def trigram_jaccard(a: str,b: str)->float:
    norm=lambda x: re.sub(r"\s+"," ",x.lower())
    a,b=norm(a),norm(b)
    A={a[i:i+3] for i in range(max(0,len(a)-2))}; B={b[i:i+3] for i in range(max(0,len(b)-2))}
    return len(A&B)/len(A|B) if A and B else 0.0


def sequence_ratio(a: str,b: str)->float:
    return SequenceMatcher(None,a.lower()[:2048],b.lower()[:2048]).ratio()


def semantic_score(projection: str, target_text: str)->float:
    return .50*token_overlap(projection,target_text)+.30*trigram_jaccard(projection,target_text)+.20*sequence_ratio(projection,target_text)


def safe_source_text(path: Path, limit: int=12000)->str:
    try: return path.read_text("utf-8",errors="ignore")[:limit]
    except Exception: return ""


def init_db(path: Path):
    con=sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS lattice_truths(target_sha256 TEXT,source_path TEXT,channel TEXT,roundtrip_exact INTEGER,path_score REAL,content_score REAL,PRIMARY KEY(target_sha256,channel))")
    con.commit(); return con


def run(meta_root: Path,outdir: Path,seed:int,holdout_start:int,config_path:Path|None)->dict:
    meta_root=meta_root.resolve(); outdir.mkdir(parents=True,exist_ok=True)
    wav_dir=outdir/"audio"; img_dir=outdir/"bitmap"; wav_dir.mkdir(exist_ok=True); img_dir.mkdir(exist_ok=True)
    files=eligible_files(meta_root); ordered=deterministic_order(files,meta_root,seed)
    holdout=ordered[holdout_start:]
    if len(holdout)!=len(files)-holdout_start: raise AssertionError("holdout error")
    # Fixed null permutation, independent of channels.
    null_order=deterministic_order(holdout,meta_root,seed+1_000_003)
    null_map={p:q for p,q in zip(holdout,null_order)}
    chs=channels()
    rows=[]; con=init_db(outdir/"janus.db")
    grave=(outdir/"entropy_graveyard.jsonl").open("w",encoding="utf-8")
    text_dump=(outdir/"conversion_to_text.txt").open("w",encoding="utf-8")
    for idx,p in enumerate(holdout,1):
        rel=p.relative_to(meta_root).as_posix(); digest=sha256_file(p); source=safe_source_text(p); null_p=null_map[p]; null_rel=null_p.relative_to(meta_root).as_posix(); null_source=safe_source_text(null_p)
        text_dump.write(f"\n===== [{idx:03d}] HIDDEN-GROUND-TRUTH: {rel} =====\nSHA256: {digest}\n")
        # File-producing channels
        wav=wav_dir/f"{idx:03d}_{digest[:12]}.wav"; wav_projection=write_wav(digest,wav); wav_decoded=read_wav(wav)
        pgm=img_dir/f"{idx:03d}_{digest[:12]}.pgm"; pgm_projection=write_pgm(digest,pgm); pgm_decoded=read_pgm(pgm)
        extra=[("wav_fsk",wav_projection,wav_decoded),("pgm_bitmap_16x16",pgm_projection,pgm_decoded)]
        current=[]
        for ch in chs:
            projection=ch.encode(digest)
            if ch.name=="printable_byte_probe": decoded=""
            else: decoded=ch.decode(projection)
            current.append((ch.name,projection,decoded))
        current += extra
        for name,projection,decoded in current:
            reversible=(decoded==digest) if decoded else False
            pscore=semantic_score(projection,rel); cscore=semantic_score(projection,source)
            null_pscore=semantic_score(projection,null_rel); null_cscore=semantic_score(projection,null_source)
            rows.append({"index":idx,"source_path":rel,"target_sha256":digest,"channel":name,"reversible":int(reversible),"path_score":pscore,"content_score":cscore,"null_path_score":null_pscore,"null_content_score":null_cscore,"path_signal_delta":pscore-null_pscore,"content_signal_delta":cscore-null_cscore,"projection_text":projection[:4096]})
            con.execute("INSERT OR REPLACE INTO lattice_truths VALUES(?,?,?,?,?,?)",(digest,rel,name,int(reversible),pscore,cscore))
            text_dump.write(f"\n[{name}]\n{projection[:4096]}\n")
        grave.write(json.dumps({"index":idx,"target_sha256":digest,"source_hidden_during_conversion":True,"channels":len(current),"note":"Representation scores are compared with fixed shuffled ground truth; no digest-distance preimage gradient."},ensure_ascii=False)+"\n")
    con.commit(); con.close(); grave.close(); text_dump.close()

    with (outdir/"results_271_channels.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    scores=[]
    for name in [c.name for c in chs]+["wav_fsk","pgm_bitmap_16x16"]:
        rr=[r for r in rows if r["channel"]==name]
        scores.append({
            "channel":name,
            "tests":len(rr),
            "roundtrip_exact":sum(r["reversible"] for r in rr),
            "roundtrip_rate":sum(r["reversible"] for r in rr)/len(rr),
            "mean_path_score":statistics.fmean(r["path_score"] for r in rr),
            "mean_null_path_score":statistics.fmean(r["null_path_score"] for r in rr),
            "mean_path_signal_delta":statistics.fmean(r["path_signal_delta"] for r in rr),
            "mean_content_score":statistics.fmean(r["content_score"] for r in rr),
            "mean_null_content_score":statistics.fmean(r["null_content_score"] for r in rr),
            "mean_content_signal_delta":statistics.fmean(r["content_signal_delta"] for r in rr),
        })
    scores.sort(key=lambda x:(x["mean_content_signal_delta"]+x["mean_path_signal_delta"]),reverse=True)
    with (outdir/"channel_scores.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(scores[0])); w.writeheader(); w.writerows(scores)

    # A result is called a candidate only if it beats shuffled control in both path and content means.
    candidates=[s for s in scores if s["mean_path_signal_delta"]>0 and s["mean_content_signal_delta"]>0]
    summary={
        "experiment":"JANUS-LAPIS Meta271 Sensory Conversion Lattice",
        "version":VERSION,"janus_identity":"JANUS 113.8","meta_registry":"Hawkar-usls/janus-meta-registry",
        "seed":seed,"eligible_corpus_files":len(files),"calibration_meta100":holdout_start,"holdout_tests":len(holdout),
        "channels":len(scores),"channel_names":[s["channel"] for s in scores],
        "fully_reversible_channels":sum(s["roundtrip_rate"]==1.0 for s in scores),
        "candidate_semantic_channels":[s["channel"] for s in candidates],
        "ranking":scores,
        "scientific_boundary":[
            "All reversible channels are representations of the same 256 digest bits; representation alone cannot recreate information erased before hashing.",
            "Semantic scores are exploratory and must beat a fixed shuffled-ground-truth control before being treated as a candidate signal.",
            "A positive exploratory delta is not proof of preimage recovery; repeated holdouts and external corpora would be required.",
            "Known-corpus exact lookup is content-addressed memory, not general SHA-256 inversion."
        ]
    }
    (outdir/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    report=["# JANUS-LAPIS v0.2.1 — Meta271 Sensory Conversion Lattice","",f"Holdout files: **{len(holdout)}** of **{len(files)}**; first {holdout_start} were reserved as Meta100 calibration.",f"Channels: **{len(scores)}**; fully reversible: **{summary['fully_reversible_channels']}**.","","## Channel ranking","","| Channel | Round-trip | Δ path vs shuffled | Δ content vs shuffled |","|---|---:|---:|---:|"]
    for s in scores:
        report.append(f"| {s['channel']} | {s['roundtrip_exact']}/{s['tests']} | {s['mean_path_signal_delta']:+.6f} | {s['mean_content_signal_delta']:+.6f} |")
    report += ["","## Interpretation gate","",f"Exploratory channels positive on both deltas: **{', '.join(summary['candidate_semantic_channels']) if summary['candidate_semantic_channels'] else 'none'}**.","","Positive deltas are only candidates, not evidence that SHA-256 was inverted. The decisive question is whether any signal replicates under new holdouts/corpora and predicts hidden source information above null controls."]
    (outdir/"REPORT.md").write_text("\n".join(report),encoding="utf-8")
    integrity={"version":VERSION,"sha256":{str(Path(__file__).name):sha256_file(Path(__file__))}}
    if config_path and config_path.exists(): integrity["sha256"][str(config_path)]=sha256_file(config_path)
    (outdir/"ouroboros_integrity.json").write_text(json.dumps(integrity,indent=2),encoding="utf-8")
    return summary


def selftest(tmp: Path):
    d=hashlib.sha256(b"JANUS 113.8 sensory lattice").hexdigest()
    for ch in channels():
        if ch.name=="printable_byte_probe": continue
        x=ch.encode(d); assert ch.decode(x)==d,(ch.name,x)
    wav=tmp/"x.wav"; write_wav(d,wav); assert read_wav(wav)==d
    pgm=tmp/"x.pgm"; write_pgm(d,pgm); assert read_pgm(pgm)==d
    print(json.dumps({"selftest":"PASS","digest":d,"channels":len(channels())+2}))


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--meta-root",type=Path); ap.add_argument("--outdir",type=Path,default=Path("reverse_gate_runs/meta271")); ap.add_argument("--seed",type=int,default=1138); ap.add_argument("--holdout-start",type=int,default=100); ap.add_argument("--config",type=Path,default=Path("config/JANUS_113_8.json")); ap.add_argument("--selftest",action="store_true"); a=ap.parse_args()
    a.outdir.mkdir(parents=True,exist_ok=True)
    if a.selftest: selftest(a.outdir); return
    if not a.meta_root: raise SystemExit("--meta-root required")
    print(json.dumps(run(a.meta_root,a.outdir,a.seed,a.holdout_start,a.config),ensure_ascii=False,indent=2))

if __name__=="__main__": main()
