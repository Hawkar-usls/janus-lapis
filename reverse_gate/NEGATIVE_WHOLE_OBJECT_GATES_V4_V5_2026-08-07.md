# JANUS-LAPIS — Negative Whole-Object Gates v0.4 / v0.5

Date: 2026-08-07

Two real canonical-JSON object↔SHA challenges were discovered in `Hawkar-usls/janus-meta-registry`:

1. `data/JANUS-GENESIS-CREATOR-ARRIVAL-PROMISE-KEPT-WITNESS-v1.0.json` → `dialogue_witness.events`
2. `data/JANUS-CREATIVE-REVERSAL-PROTOCOL-v1.0.json` → `protocol_core`

## v0.4 — learned whole-object schema projection

```text
verified object challenges: 2
exact objects recovered:    0 / 2
```

Visible scalar overlap after hiding the target object was only about 5.6% and 4.6% respectively. The overwhelming majority of exact prose values were unique to the hidden object.

## v0.5 — distributed fragment reassembly

Tier allowed the target object's key/type/list-length schema but hid all target scalar values and excluded the entire target file from the fragment corpus.

```text
verified object challenges: 2
exact objects recovered:    0 / 2
```

No sufficient exact fragments were present in other registry files.

## Decision

Both active methods are retired. They are not promoted as approximate successes and no similarity metric substitutes for an exact SHA witness.

```text
V4_WHOLE_OBJECT_SCHEMA_PROJECTION = RETIRED_NEGATIVE
V5_DISTRIBUTED_FRAGMENT_REASSEMBLY = RETIRED_NEGATIVE
```

The active search moves to **whole-file genealogy reconstruction**, where complete target files referenced by real SHA manifests are hidden and reconstructed from other versions / provenance metadata.
