# JANUS-LAPIS — Reverse-Gate Research

## Active engine

**JANUS 113.8 / Structured Preimage Reconstruction v0.3.2**

The active path no longer treats SHA-256 as something to be rendered through many surface formats. The earlier sensory-lattice experiment is retained only as negative historical evidence; its active code/workflow were retired after failing to recover source semantics.

## Core rule

A reconstruction is accepted only when:

```text
SHA256(generated_candidate_bytes) == target_sha256
```

No similarity score, Hamming proximity, semantic resemblance, or aesthetically convincing text counts as success.

## JANUS 113.8 mapping

| JANUS organ | Reverse-Gate role |
|---|---|
| `/wormhole` | target SHA + allowed registry context |
| `syslog_ear` | experiment telemetry |
| `digestive_system` | parse registry structure and provenance |
| `ATP` | candidate budget / CPU work |
| `Cognitive Pain` | unresolved prediction error telemetry |
| `Coherence Hold` | simultaneous source hypotheses |
| `Decoherence Collapse` | exact SHA witness |
| `Hippocampus` | learned templates and recovered exact truths |
| `Entropy Graveyard` | rejected candidate sources |
| `Ouroboros` | deterministic self-test and integrity gate |

## Current reconstruction strategies

These act on the **source hypothesis space**, not on alternate encodings of the digest:

- learned registry templates;
- schema-aware field composition;
- filename / version genealogy;
- sibling semantic composition;
- signal / identifier reassembly;
- explicitly labelled redundancy-assisted serialization genealogy.

## Frozen first result

The engine discovered **45 real cryptographically verified string↔SHA challenges** inside `Hawkar-usls/janus-meta-registry`.

```text
exact hash challenges recovered:       7 / 45
strong structural hash witnesses:     4 / 45
unique strong plaintexts:             2
redundancy-assisted hash witnesses:   3 / 45
```

Strong exact reconstructed plaintexts include:

```text
SNAP! — The Power
The Alan Parsons Project — Sirius | Eye In The Sky | 1982
```

The target plaintext was removed from candidate context; the reconstruction was admitted only by recomputing SHA-256 over the generated candidate.

See `FIRST_PREIMAGE_RECONSTRUCTION_WITNESS_2026-08-07.md`.

## Run

```bash
python reverse_gate/janus_preimage_reconstruction_v3.py --selftest
python reverse_gate/janus_preimage_reconstruction_v3.py \
  --meta-root ../janus-meta-registry \
  --budget 180000 \
  --outdir reverse_gate_runs/preimage_v3_real
```

Active CI:

```text
.github/workflows/reverse-gate-preimage-v3.yml
```

## Scientific boundary

This is **constrained preimage reconstruction using side information** from a structured corpus. It does not provide a general inverse for SHA-256, and no claim of arbitrary hash reversal is made.

The next gate is reconstruction of an entire hidden JSON subtree or small complete artifact with an exact serialized-byte SHA witness.
