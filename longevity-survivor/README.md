# LONGEVITY SURVIVOR

Comparative-biology research lane for JANUS Lapis.

## Frozen question

What functional architecture repeatedly appears in organisms that show exceptional longevity, negligible senescence, unusually preserved function, or repeated rejuvenation?

This lane does **not** assume that a single gene, telomerase, slow metabolism, regeneration, or any animal mechanism is sufficient for human life extension.

## Current survivor model

```text
PREVENT EXCESS DAMAGE
        ↓
DETECT DAMAGE
        ↓
REPAIR WHAT IS REPAIRABLE
        ↓
CLEAR DAMAGED PROTEINS / ORGANELLES
        ↓
REMOVE IRREPARABLE OR DANGEROUS CELLS
        ↓
REPLACE REQUIRED CELLS
        ↓
VERIFY CELL IDENTITY + TISSUE ARCHITECTURE
        ↓
SUPPRESS MALIGNANT ESCAPE
        ↓
RESTORE SYSTEMIC HOMEOSTASIS
        ↺
```

Conceptual condition:

```text
DAMAGE_RATE < EFFECTIVE_MAINTENANCE_CAPACITY
AND
CANCER_ESCAPE remains controlled
```

## Expanded gates

1. Damage-rate control
2. Genome repair and chromatin stability
3. Controlled telomere / replicative capacity
4. Proteostasis, autophagy and organelle quality control
5. Irreparable-cell removal
6. Correct-cell replacement
7. Cancer suppression
8. Epigenetic identity preservation or safe reset
9. Tissue and systemic homeostasis

## Reverse → HUMAN

The human pass changes the question from **what regeneration machinery is missing?** to **which permission states allow a specific tissue to renew while preserving identity, geometry and tumour suppression?**

```text
HUMANS_HAVE_MOST_COMPONENT_CLASSES = SUPPORTED
ONE_GLOBAL_REGENERATION_SWITCH      = NOT_SUPPORTED
SAFE_RENEWAL                        = PERMISSION + CONTROL + STOP
```

The strongest within-human control is the contrast between tissues that share the same genome but have very different regenerative behavior. This produces an emergent cross-cutting gate:

```text
SPATIOTEMPORAL_ORCHESTRATION_AND_TERMINATION
```

A renewal program must be local, temporary, lineage-preserving, damage-aware, spatially instructed, cancer-surveilled and reliably terminable.

## Lock-aligned cross-tissue pass — v2.1

The developmental pass aligns HEART / COCHLEA / SPINAL CORD / SKIN / TENDON by the **relative loss of regenerative capacity** rather than by chronological age:

```text
BEFORE_LOCK → LOCK_TRANSITION → AFTER_LOCK
       tau<0       tau≈0            tau>0
```

### P0-A — RESIDENT_REGENERATIVE_COMPETENCE_COLLAPSE

Strong independent support: heart, cochlea, tendon; supportive parallels: spinal cord and skin.

### P0-B — TEMPORARY_WOUND_STATE / RESOLUTION

Strong support: spinal cord, skin, tendon; supportive cardiac parallel.

### P0-C — NICHE_MECHANICAL_MATURATION

Heart and skin provide strong causal support. A third clean developmental native-mechanics perturbation is still required before promotion.

## Resolution-gate kinetic killer test — v2.2

The half-life hypothesis was tested directly against published time courses. The simple rule

```text
REGENERATION = SHORT WOUND STATE
SCAR         = SAME STATE PERSISTS
```

**does not survive as a universal rule.**

### What survives

- **Neonatal spinal cord:** transient microglial/Fn1-fibronectin bridge followed by return toward homeostasis, with causal depletion/transplantation evidence.
- **Neonatal tendon:** early alpha-SMA+ helper/fibrotic state followed by intrinsic Scx-lineage recruitment and neo-tendon formation.
- **Acomys ear:** transient myofibroblast state; experimentally delaying resolution shifts regeneration toward fibrosis.

### What kills the half-life-only model

- **Adult heart:** alpha-SMA myofibroblast identity is transient, but lineage-traced fibroblasts persist as matrifibrocytes and the mature ECM scar remains.
- **Acomys full-thickness skin (29 July 2026):** dermal alpha-SMA clears early, while a distinct panniculus-associated alpha-SMA+ bridge persists for weeks during successful muscle regeneration.

Therefore persistence time alone is not the invariant.

### Revised P0 survivor

```text
WOUND_STATE_FATE_ROUTING_AND_RESOLUTION_GATE
=
ENTRY
→ WOUND STATE
→ SPATIAL ROUTING
→ HANDOFF TO REBUILD
→ STATE FATE
→ TERMINATE PROFIBROTIC OUTPUT
→ RESTORE ARCHITECTURE
```

Required measurements now include duration, spatial compartment, state identity, lineage fate, ECM reversibility, profibrotic-output duration, regenerative handoff and final tissue architecture.

## Resolution Gate Data Pack v1.0

The next stage is now packaged as an auditable scientific-data request rather than a broad hypothesis pitch.

Core distinction:

```text
marker lifetime
!= lineage lifetime
!= profibrotic-output lifetime
!= scar lifetime
```

The pack contains interval-censored kinetics for neonatal spinal cord, neonatal tendon, Acomys ear, 2026 Acomys full-thickness skin, adult post-MI heart and a new **4 August 2026 neonatal-heart bioRxiv preprint** with 4/7/10/21-dpi scar-resolution measurements and fibroblast/myeloid Erbb4 perturbations.

The preprint is especially useful because it provides a provisional causal separation:

```text
CARDIOMYOCYTE PROLIFERATION
!=
SCAR-RESOLUTION KINETICS
```

It remains preprint evidence and is not promoted to settled mechanism.

### Current quantitative target

Instead of fitting only `alpha-SMA(t)`, the P0 test now compares:

```text
CELL_STATE_OCCUPANCY(t)
vs
PROFIBROTIC_OUTPUT_OCCUPANCY(t)
```

with spatial compartment, lineage transition and final architecture carried as explicit variables.

## Current falsification state

```text
TELOMERASE_ALONE                    = REFUTED_AS_SUFFICIENT
LOW_METABOLISM_ALONE                = REFUTED_AS_SUFFICIENT
DNA_REPAIR_ALONE                    = REFUTED_AS_SUFFICIENT
SINGLE_MASTER_GENE                  = NOT_SUPPORTED
ALL_SIX_AXES_SYNC_GLOBALLY          = REFUTED
HALF_LIFE_ONLY_RESOLUTION_RULE      = REFUTED
SCAR_EQUALS_SAME_ALPHA_SMA_STATE    = REFUTED
MULTI_GATE_ARCHITECTURE             = SURVIVES
WOUND_STATE_FATE_ROUTING            = CURRENT_P0_REVISED_SURVIVOR
DIRECT_HUMAN_TRANSLATION            = NOT_ESTABLISHED
```

## Canonical artifacts

- [`LONGEVITY-SURVIVOR-TRANCEPTION-2026-08-23-v1.0.json`](LONGEVITY-SURVIVOR-TRANCEPTION-2026-08-23-v1.0.json)
- [`TELOMERASE-CANCER-TRADEOFF-TRANCEPTION-2026-08-23-v1.0.json`](TELOMERASE-CANCER-TRADEOFF-TRANCEPTION-2026-08-23-v1.0.json)
- [`HUMAN-SAFE-RENEWAL-FULL-JANUS-COUNCIL-2026-08-23-v1.0.json`](HUMAN-SAFE-RENEWAL-FULL-JANUS-COUNCIL-2026-08-23-v1.0.json)
- [`HUMAN-TISSUE-RENEWAL-PERMISSION-MATRIX-2026-08-23-v1.0.json`](HUMAN-TISSUE-RENEWAL-PERMISSION-MATRIX-2026-08-23-v1.0.json)
- [`DEVELOPMENTAL-PERMISSION-MATRIX-LONGEVITY-SURVIVOR-2026-08-23-v2.0.json`](DEVELOPMENTAL-PERMISSION-MATRIX-LONGEVITY-SURVIVOR-2026-08-23-v2.0.json)
- [`LOCK-ALIGNED-OVERLAY-LONGEVITY-SURVIVOR-2026-08-23-v2.1.json`](LOCK-ALIGNED-OVERLAY-LONGEVITY-SURVIVOR-2026-08-23-v2.1.json)
- [`RESOLUTION-GATE-KINETIC-KILLER-TEST-2026-08-23-v2.2.json`](RESOLUTION-GATE-KINETIC-KILLER-TEST-2026-08-23-v2.2.json)
- [`RESOLUTION-GATE-DATA-PACK-2026-08-23-v1.0.json`](RESOLUTION-GATE-DATA-PACK-2026-08-23-v1.0.json)
- [`RESOLUTION-GATE-DATA-PACK-2026-08-23-v1.0.md`](RESOLUTION-GATE-DATA-PACK-2026-08-23-v1.0.md)
- [`RESOLUTION-GATE-SCIENTIFIC-NOTE-DRAFT-2026-08-23-v0.1.md`](RESOLUTION-GATE-SCIENTIFIC-NOTE-DRAFT-2026-08-23-v0.1.md)
- [`SCIENTIFIC-OUTREACH-QUEUE-RESOLUTION-GATE-2026-08-23-v1.0.json`](SCIENTIFIC-OUTREACH-QUEUE-RESOLUTION-GATE-2026-08-23-v1.0.json)

## Scientific-sharing boundary

The current result is suitable to share as a **cross-tissue technical hypothesis note and quantitative-data request**, not as a new experimental discovery or universal regeneration mechanism.

No email is sent from this branch. Outreach remains blocked until the packet is judged sufficiently valuable and specific.

## Next gates

- reconstruct normalized state-occupancy curves from public source data;
- extract per-animal/time-point values where legally/publicly available rather than digitize figures when source data exist;
- track lineage fate after marker loss;
- measure profibrotic-output persistence separately from alpha-SMA marker lifetime;
- test whether `[state + output + routing]` separates outcomes better than marker lifetime alone;
- seek a third clean causal native-tissue test for the ECM/mechanical maturation lock;
- preserve **marker loss != cell clearance**, **cell clearance != ECM clearance**, **animal regeneration != human therapy**.

## Boundary

This branch is an exploratory hypothesis-ranking and comparative-biology lane. It is not a medical protocol, treatment recommendation, gene-editing guide, self-experimentation guide, or claim that human lifespan extension has been achieved.
