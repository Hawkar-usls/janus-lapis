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

# Research branch: JANUS-LAPIS v0.2.0 — Reverse-Gate Edition

The v0.1.5 history remains intact. The `research/reverse-gate-v020` branch adds a separate experiment built around **JANUS 113.8 — Thermodynamic Cognitive Organism**.

```text
/wormhole
   ↓
SHA-256 target
   ↓
CHAOS SPIKE
   ↓
COHERENCE HOLD
   ├── corpus hypotheses
   ├── audio representation
   └── blind negative control
   ↓
EXACT SHA WITNESS
   ↓
DECOHERENCE COLLAPSE
   ├── Hippocampus: successful mappings
   └── Entropy Graveyard: rejected hypotheses
```

The first CI experiment uses **100 real files from `Hawkar-usls/janus-meta-registry`**, computes their SHA-256 from exact file bytes, converts every digest into WAV, decodes the sound back into 256 bits and renders the recovered digest as JANUS text.

Initial frozen result:

```text
eligible Meta Registry corpus: 371 files
tests:                         100
SHA → WAV → SHA exact:         100 / 100
known-corpus resolution:       100 / 100
blind digest-only path guess:    1 / 100
audio-text/source token overlap: 0.000000
```

This result supports **content-addressed memory inside a known corpus** and a lossless SHA audio codec. It does **not** demonstrate general SHA-256 inversion or semantic information leaking from the digest. The blind control is intentionally kept next to the successful corpus result so a false victory cannot pass the gate.

See `reverse_gate/README.md` and workflow `JANUS Reverse-Gate 100`.
