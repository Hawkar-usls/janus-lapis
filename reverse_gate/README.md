# JANUS-LAPIS v0.2.0 — Reverse-Gate Edition

This branch preserves v0.1.5 **Birth-Gate Edition** and adds a separate SHA-256 research organism built around **JANUS 113.8**.

## JANUS 113.8 mapping

| JANUS organ | Reverse-Gate role |
|---|---|
| `/wormhole` | target SHA / Meta Registry input |
| `syslog_ear` | experiment telemetry |
| `digestive_system` | parse repository files and structural metadata |
| `ATP` | comparisons, CPU time, memory |
| `Cognitive Pain` | predictive-error / uncertainty threshold (telemetry metaphor only) |
| `Coherence Hold` | keep multiple preimage hypotheses alive |
| `Decoherence Collapse` | exact `SHA(candidate) == target` witness |
| `Hippocampus` | SQLite store of successful exact mappings |
| `Entropy Graveyard` | exact-mismatch hypotheses and dead ends |
| `Ouroboros` | SHA-256 integrity manifest for code/config |
| `Face` | Markdown/CSV/JSON/audio reports |

## Three gates

1. **Audio Integrity Gate** — convert each 256-bit digest to 32 deterministic tones and decode it back.
2. **Known-Corpus Preimage Gate** — hash every eligible file in `Hawkar-usls/janus-meta-registry` and resolve target digests against that finite corpus. This is content-addressed memory / corpus lookup, not a general SHA-256 inverse.
3. **Blind Semantic Gate** — do not use file bytes to guess the source path; use a deliberately blind digest-only control and compare its performance.

## SHA → sound → text

Each digest byte `0..255` maps to a unique tone:

```text
frequency = 300 Hz + byte × 25 Hz
```

The WAV decoder recovers 32 bytes. The bytes are rendered through a fixed 16×16 JANUS syllable codebook such as:

```text
alba-bore  nexa-soma  ...
```

The words are **not claimed to be hidden plaintext**. They are a reversible textual representation of the digest recovered from audio. The experiment checks whether they have any relationship to source metadata beyond the negative control.

## Run locally

```bash
python -m pip install numpy
python reverse_gate/janus_reverse_gate.py --selftest
python reverse_gate/janus_reverse_gate.py \
  --meta-root ../janus-meta-registry \
  --limit 100 \
  --seed 1138 \
  --outdir reverse_gate_runs/meta100
```

Outputs:

```text
summary.json
results_100.csv
audio_to_text.txt
REPORT.md
janus.db
entropy_graveyard.jsonl
ouroboros_integrity.json
audio/*.wav
```

## Scientific boundary

SHA-256 is intentionally preimage resistant and has an avalanche effect. Sonification cannot recreate information that was not retained in the 256-bit digest. Reverse-Gate asks a narrower, testable question: **how much can a structured known corpus and provenance model reduce a preimage search space, and does an audio representation add any measurable information?**
