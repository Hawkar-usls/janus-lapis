# JANUS-LAPIS — Current Working Reverse-Gate Result

**Date:** 2026-08-07  
**Engine:** JANUS 113.8  
**Champion:** v0.3.3 Provenance-Aware Structured Preimage Reconstruction

## Benchmark

The engine discovers real string↔SHA pairs by independently verifying that a recorded SHA-256 actually hashes a string present in `Hawkar-usls/janus-meta-registry`. The target plaintext is then removed from candidate context before reconstruction.

Current benchmark:

```text
verified real string↔SHA challenges: 47
exact SHA challenges recovered:      11
unique plaintexts recovered:          6
exact challenge recovery rate:       23.40%
```

## Working exact methods

```text
schema_song_identifier            6 hash witnesses
explicit_provenance_extraction    2 hash witnesses
registry_serialization_genealogy  3 hash witnesses
```

Every success is admitted only when:

```text
SHA256(generated_candidate_bytes) == recorded_target_sha256
```

## Unique recovered plaintexts

Strong / provenance-driven source strings include:

```text
SNAP! — The Power
ERA — Ameno | Era I | 1996
R. Kelly — I Believe I Can Fly | Space Jam | 1996
The Alan Parsons Project — Sirius | Eye In The Sky | 1982
```

The remaining two unique recovered plaintext representations belong to the Solstice Relay branch and are classified as **redundancy-assisted serialization recovery**, because an alternate reversible representation of the same information is present in allowed registry context.

## Retired paths

The following paths are not active research methods:

```text
23 SHA surface representations              -> no semantic source recovery
v0.4 whole-object schema projection         -> 0 / 2
v0.5 cross-file object fragment reassembly  -> 0 / 2
v0.6 whole-file genealogy                   -> 0 / 7
v0.7 companion template transfer            -> 0 / 4
v0.3.4 scalar Hippocampus                    -> 0 incremental new preimages
```

Negative results remain documented so they are not repeated.

## What this means

The project has demonstrated a real constrained inverse workflow:

```text
structured side information / explicit provenance
        ↓
source candidate generation
        ↓
SHA-256 exact witness
        ↓
recovered preimage
```

This does **not** establish a universal inverse for SHA-256. The successful mechanism reduces the possible source space using information about how JANUS artifacts are generated and recorded, then uses SHA-256 as a perfect equality gate.

The closest achieved analogue to “reconstructing the chicken from mince” is therefore a restricted family of structured source strings, not arbitrary files.
