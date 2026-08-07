# JANUS-LAPIS — Reverse-Gate Research

## Active engine

**JANUS 113.8 / Provenance-Aware Structured Preimage Reconstruction v0.3.3**

The active path no longer treats SHA-256 as something to render through many surface formats. Failed conversion/object/file methods are preserved only as negative evidence in the Entropy Graveyard.

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
| `Cognitive Pain` | unresolved prediction-error telemetry |
| `Coherence Hold` | simultaneous source hypotheses |
| `Decoherence Collapse` | exact SHA witness |
| `Hippocampus` | learned templates and recovered exact truths |
| `Entropy Graveyard` | rejected candidates and retired methods |
| `Ouroboros` | deterministic self-test and integrity gate |

## Current reconstruction strategies

These act on the **source hypothesis space**, not on alternate encodings of the digest:

- schema-aware field composition;
- learned registry templates;
- explicit provenance extraction;
- filename / identifier genealogy;
- sibling semantic composition;
- explicitly labelled redundancy-assisted serialization genealogy.

## Frozen current result

The engine discovered **47 real cryptographically verified string↔SHA challenges** inside `Hawkar-usls/janus-meta-registry`.

```text
exact hash challenges recovered:  11 / 47
unique plaintexts recovered:       6
recovery rate:                     23.40%
```

Method contribution:

```text
schema_song_identifier            6
explicit_provenance_extraction    2
registry_serialization_genealogy  3
```

Unique recovered examples include:

```text
SNAP! — The Power
ERA — Ameno | Era I | 1996
R. Kelly — I Believe I Can Fly | Space Jam | 1996
The Alan Parsons Project — Sirius | Eye In The Sky | 1982
```

Two Solstice Relay representations are separately classified as redundancy-assisted because an alternate reversible serialization already exists in allowed registry context.

## Retired negative gates

```text
23 digest surface representations        -> no source semantic recovery
v0.4 whole-object schema projection      -> 0 / 2
v0.5 distributed object fragments        -> 0 / 2
v0.6 whole-file genealogy                -> 0 / 7
v0.7 companion template transfer         -> 0 / 4
```

These methods are removed from active CI.

## Run

```bash
python reverse_gate/janus_preimage_reconstruction_v4.py --selftest
python reverse_gate/janus_preimage_reconstruction_v4.py \
  --meta-root ../janus-meta-registry \
  --budget 180000 \
  --outdir reverse_gate_runs/preimage_v4_real
```

Active CI:

```text
.github/workflows/reverse-gate-preimage-v4.yml
```

## Scientific boundary

This is **constrained preimage reconstruction using side information** from a structured corpus. It does not provide a general inverse for SHA-256. The demonstrated mechanism is: use structure/provenance to collapse the possible source space, then use SHA-256 as an exact cryptographic witness.
