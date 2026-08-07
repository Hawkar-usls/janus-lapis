# JANUS-LAPIS — Negative Whole-File Gates v0.6 / v0.7

Date: 2026-08-07

## v0.6 — Whole-File Genealogy Reconstruction

Real manifest-backed complete files were hidden and reconstructed from other registry versions / filename genealogy / manifest metadata.

```text
verified real file SHA challenges: 7
exact complete files recovered:    0 / 7
```

Targets included JSON, Python and C++ header companions with exact byte counts and real manifest SHA-256 values.

## v0.7 — Leave-One-Artifact Companion Reconstruction

Target `.py/.hpp` files were excluded. JANUS learned JSON→companion textual templates only from other artifact bundles and applied them to the visible target JSON.

```text
verified hidden companion challenges: 4
exact complete files recovered:        0 / 4
```

The companion files contain enough hand-authored / artifact-specific structure that cross-artifact template transfer did not reproduce exact bytes.

## Decision

```text
V6_WHOLE_FILE_GENEALOGY = RETIRED_NEGATIVE
V7_COMPANION_TEMPLATE_TRANSFER = RETIRED_NEGATIVE
```

No approximate output is promoted. The active Reverse-Gate returns to the demonstrated working domain: structured plaintext preimage reconstruction with exact SHA witnesses.
