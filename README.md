# JANUS-LAPIS v0.1.5 — Birth-Gate Edition

A modern GPT-guided search space for the real functions behind the philosopher's stone.

## Principle

The alchemists were not fools. They lacked instruments.
We do not worship symbols. We test functions.

## v0.1.5

This version adds the Birth-Gate decision chain: a candidate must pass the scene before it can enter champions.

```text
The stone is not only a material.
The stone is the clean scene that lets a new game appear.
The stone is also the gate that decides whether a hypothesis is ready to be born.
The stone is also the engine that changes the search space.
```

## Archetypes

Material layer:

- `LAPIS_UNIVERSAL`
- `LAPIS_CATALYST`
- `LAPIS_PURIFIER`
- `LAPIS_HEALER`
- `LAPIS_STONE`
- `LAPIS_LIFE`
- `LAPIS_ENERGY`
- `LAPIS_BIOMINERAL`
- `LAPIS_LOWHAZARD`

Scene-preparation layer:

- `LAPIS_CANVAS`
- `LAPIS_STAGEKEEPER`

Meta layer:

- `LAPIS_DEMIURGE`
- `LAPIS_WORLD_REWRITER`

## Science boundary

- Not a claim of literal transmutation.
- Not an elixir claim.
- No hazardous synthesis protocol.
- Not a certified material claim.
- No instructions for dangerous chemistry.
- All outputs are computational research vectors and expert-review requests, not measured or validated materials.

## Run

```bash
RUN_JANUS_LAPIS.bat
```

Output:

```text
_JanusLapis_RUNNER\janus_lapis_runs\SEND_TO_REVIEWERS_JANUS_LAPIS.zip
```

Main files:

```text
janus_lapis_summary.json
janus_lapis_champions.csv
janus_lapis_all_archetypes.csv
lab_request\JANUS_LAPIS_EXTERNAL_RESEARCH_BRIEF.md
lab_request\janus_lapis_external_research_request.csv
docs\JANUS_RESPONSE_INTERPRETATION.md
```

## Optional environment variables

```text
JANUS_LAPIS_TRIALS_PER_ARCHETYPE=3000
JANUS_LAPIS_SEED=1618
JANUS_LAPIS_TOP_PER_ARCHETYPE=3
JANUS_LAPIS_REPLICATES=1
JANUS_LAPIS_NO_TRANSFORMER=0
```

## Canvas principle

Purification is not a lower stage. It prepares the clean canvas.

```text
LAPIS_PURIFIER cleans matter.
LAPIS_CANVAS prepares the clean surface.
LAPIS_STAGEKEEPER protects the scene.
LAPIS_DEMIURGE creates the new game.
BIRTH_GATE decides whether it is ready to be born.
```

## Birth-Gate principle

High material score is not enough.

```text
final_priority =
material_score
× scene_viability
× containment_integrity
× hypothesis_visibility
× expert_gate
```

A hypothesis must pass the scene before it can enter the world.

New outputs:

```text
janus_lapis_decision_chain.csv
janus_lapis_birth_gates.csv
janus_lapis_rejected_by_gate.csv
janus_lapis_birth_gate_summary.json
docs/BIRTH_GATE_METHOD.md
```

---

# Research branch — JANUS-LAPIS v0.3.2 Reverse-Gate

The historical Birth-Gate work remains intact. The active research branch `research/reverse-gate-v020` now hosts **JANUS 113.8 — Structured Preimage Reconstruction**.

The earlier 23 SHA representation / sensory-lattice methods were retired from active CI after demonstrating digest-preserving encodings but no useful source-semantic recovery.

The active question is now:

```text
TARGET SHA-256
    +
Meta Registry schema / genealogy / neighboring metadata
    ↓
Coherence Hold
    ↓
source hypotheses
    ↓
SHA256(candidate bytes)
    ↓
EXACT witness only
```

JANUS 113.8 mapping:

```text
/wormhole             -> target + allowed structural context
Chaos Spike           -> unresolved source uncertainty
Coherence Hold        -> competing preimage hypotheses
Entropy Graveyard     -> exact-hash failures
Decoherence Collapse  -> SHA256(candidate) == target
Hippocampus           -> learned templates + exact recovered truths
Ouroboros              -> deterministic self-tests / integrity gates
```

## First exact structured reconstruction

On **45 real, cryptographically verified string↔SHA challenges** discovered inside `Hawkar-usls/janus-meta-registry`, the engine produced:

```text
exact SHA challenges recovered:       7 / 45
strong structural hash witnesses:     4 / 45
unique strong plaintexts:             2
redundancy-assisted hash witnesses:   3 / 45
```

Two unique hidden plaintexts were reconstructed from neighboring structured metadata and admitted only after exact SHA equality:

```text
SNAP! — The Power

The Alan Parsons Project — Sirius | Eye In The Sky | 1982
```

The Solstice Relay text was additionally reconstructed through an alternate reversible sibling serialization and is therefore labelled **redundancy-assisted**, not a strong SHA reconstruction.

See:

```text
reverse_gate/FIRST_PREIMAGE_RECONSTRUCTION_WITNESS_2026-08-07.md
reverse_gate/janus_preimage_reconstruction.py
reverse_gate/janus_preimage_reconstruction_v2.py
reverse_gate/janus_preimage_reconstruction_v3.py
.github/workflows/reverse-gate-preimage-v3.yml
```

## Current gate state

```text
SHA surface-format conversion              = RETIRED
SHA -> hidden short structured plaintext   = ADMITTED IN RESTRICTED REGISTRY FAMILY
SHA -> arbitrary plaintext                 = NOT ADMITTED
SHA -> complete arbitrary file             = NOT ADMITTED
GENERAL SHA-256 INVERSION                  = NOT CLAIMED
```

## Next gate

The next target is whole-object reconstruction:

```text
hidden JSON subtree / complete small artifact
+ learned schema
+ version genealogy
+ sibling metadata
-> exact serialized bytes
-> exact SHA-256 witness
```

That is the next meaningful step toward recovering a larger original object rather than merely a short structured string.
