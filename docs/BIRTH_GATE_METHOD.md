# BIRTH-GATE METHOD

JANUS-LAPIS v0.1.5 adds the Birth-Gate decision chain.

## Principle

A powerful candidate is not automatically a champion.

A hypothesis must pass the scene before it can enter the world.

```text
final_priority =
material_score
× scene_viability
× containment_integrity
× hypothesis_visibility
× expert_gate
```

This is a multiplicative barrier. If containment is weak, visibility is low, or the expert gate is not satisfied, the candidate is downgraded even if its raw material score is high.

## Why this matters

Earlier versions generated and ranked candidates.

v0.1.5 adds judgment:

```text
CANVAS asks: is the signal visible?
STAGEKEEPER asks: can the scene safely hold it?
DEMIURGE asks: can the system learn from it?
BIRTH-GATE asks: is it ready to be born?
```

## Safety rule

If:

```text
creative_potential > 0.8
safe_containment < 0.3
```

then the candidate is marked as an unstable birth candidate.

The project does not chase miracles. It seeks verifiable evidence.

## Astronomy metaphor

Imagine taking an image of a distant planet.

```text
PURIFIER removes light pollution.
CANVAS stabilizes the background.
STAGEKEEPER holds the telescope still.
DEMIURGE focuses the search.
BIRTH-GATE decides whether the signal is clean enough to enter the discovery catalog.
```

If the light pollution is still too high, the image does not enter the catalog, even if the model predicts a planet.

First clarity. Then discovery.

## Outputs

```text
janus_lapis_decision_chain.csv
janus_lapis_birth_gates.csv
janus_lapis_rejected_by_gate.csv
```

Rejected hypotheses are not failures. They are part of the map.
Negative results save time, money, and confusion.

## Science boundary

- No literal transmutation claim.
- No elixir claim.
- No hazardous synthesis protocol.
- No certified material claim.
- No instructions for dangerous chemistry.
- All outputs are computational research vectors and expert-review requests.
