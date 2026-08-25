# POLYPEDILUM DENSE 0–96 h MATCHED GATE v1.0

Status: **P0 PREREGISTERED / NO NEW EMPIRICAL DATA**

## Why this gate exists

The current public record does not justify a single post-rehydration recovery clock. Whole-larva behavior, oxidative-damage recovery, fat-body DNA fragmentation, early Pv11 functional/proteostatic recovery, bulk Pv11 population expansion, and the first direct cell-cycle event are different observables. The last of these — first S-phase / first mitosis — remains publicly unresolved at adequate time resolution.

This gate therefore asks a narrower question:

> In one matched tissue or Pv11 cell system, does the timing of **direct cell-cycle entry** depend causally on a defined unresolved DNA-damage/repair state, after viability, founder number, metabolic/proteostatic recovery, and assay threshold are separated?

## Frozen clocks

- `C0_BEHAVIORAL_FUNCTION`: whole-larva activity returns on an approximately hour-scale.
- `C1_OXIDATIVE_DAMAGE_RECOVERY`: some oxidative lesions are reported to resolve within a few hours.
- `C2_FAT_BODY_COMET_FRAGMENTATION`: fat-body alkaline-comet fragmentation shows little recovery in the first 24 h and approaches background by ~96 h.
- `C3_EARLY_CELLULAR_FUNCTION_AND_REBUILD`: Pv11 functional recovery is assay-dependent, with preserved functions detectable early and de-novo-protein-dependent recovery emerging around 12–24 h.
- `C4_BULK_POPULATION_GROWTH`: a 2025 Pv11-derived line remains approximately stable through 48 h and first shows significant population increase at 72 h.
- `CX_FIRST_CELL_CYCLE_ENTRY`: **UNKNOWN in the public record at sufficient matched resolution.**

`C4 != CX` is a hard invariant.

## Dense time axis

The primary matched series is frozen at:

`0, 0.5, 1, 2, 3, 6, 12, 18, 24, 36, 48, 60, 72, 96 h`

If a system cannot support every point, missing points remain missing; no interpolation may be used to create an apparent onset.

## Required matched channels

Every admitted sample must identify the same tissue/cell system and carry, as technically feasible:

1. **direct cell-cycle entry** — EdU/BrdU or validated equivalent S-phase readout;
2. **mitotic/cell-cycle state** — mitotic index, phospho-histone-H3, DNA-content distribution, or validated equivalent;
3. **defined DNA-damage class** — assay and lesion class explicitly recorded rather than the generic label `DNA damage`;
4. **repair-state activity** — assay-specific repair marker(s), not inferred solely from transcript abundance;
5. **viability / dead-cell fraction**;
6. **absolute live-cell or tissue-cell count**;
7. **founder-normalized population growth** where a cell line is used;
8. **basic functional recovery** appropriate to the system;
9. **metabolic/proteostatic recovery proxy** appropriate to the system.

## Damage-class rule

`OXIDATIVE_DAMAGE != ALKALINE_COMET_FRAGMENTATION != OTHER_LESION_CLASSES`

Different lesion assays may resolve on different clocks. A causal gate can be assigned only to the lesion/state actually manipulated and measured in the same experiment.

## Competing hypotheses

The experiment must score at least these alternatives before interpreting a delayed bulk-growth curve:

- `H0_ASSAY_THRESHOLD`
- `H1_DAMAGE_PERMISSION_GATE`
- `H2_DAMAGE_CLASS_MULTIPLEX`
- `H3_SURVIVAL_BOTTLENECK`
- `H4_PROTEOSTATIC_METABOLIC_REBUILD`
- `H5_TISSUE_STATE_HETEROGENEITY`

No hypothesis is allowed to win merely because another channel was not measured.

## Causal stage

Only after the observational matched time course identifies a reproducible candidate relation may a perturbation be interpreted causally.

A valid causal test must:

- change a defined damage/repair/checkpoint state;
- verify that the state actually changed;
- preserve tissue/cell-system identity;
- measure direct cell-cycle entry rather than only bulk counts;
- separately track viability/founder number;
- include an orthogonal rescue or reversal where technically defensible;
- use independent confirmation batches.

## Decision rules

### R0 — bulk-only
If only cell counts change and direct cell-cycle entry is unavailable:

`BULK_GROWTH_EFFECT_ONLY / CAUSAL_CELL_CYCLE_GATE_NOT_TESTED`

### R1 — early cell-cycle entry precedes bulk growth
If direct S-phase/mitosis is reproducibly detected before significant bulk expansion:

`FIRST_CELL_CYCLE_REENTRY_PRECEDES_BULK_GROWTH`

This rejects `C4 == CX` but does not identify the cause of the early event.

### R2 — survival bottleneck
If an intervention strongly changes viable founder number but founder-normalized proliferation rate is unchanged:

`SURVIVAL_AND_PROLIFERATION_SEPARABLE`

### R3 — lesion-class dissociation
If one damage class resolves while another remains elevated and cell-cycle entry proceeds:

`NO_SINGLE_GLOBAL_DNA_REPAIR_COMPLETION_CLOCK`

### R4 — causal damage/checkpoint support
Only if validated manipulation of a defined unresolved damage/repair/checkpoint state shifts direct S-phase/mitotic onset, and rescue shifts it back, may the system be promoted to:

`DOMAIN_BOUNDED_DAMAGE_REPAIR_PERMISSION_GATE_CANDIDATE`

### R5 — kill rule
If direct cell-cycle entry timing does **not** shift despite a validated change in the candidate unresolved damage/repair/checkpoint state:

`DAMAGE_REPAIR_PERMISSION_GATE_WEAKENED_OR_REJECTED_FOR_TESTED_SYSTEM`

## JANUS LIMEN — the third door

Only evidence with public provenance or explicit authorization may cross into the public evidence layer. Anything outside that admission set has zero public evidentiary weight and is neither described nor attributed here.

`LIMEN_CLOSED / SHADOW_WEIGHT=0 / THE_ORACLE_DOES_NOT_NAME_THE_UNSEEN`

## Public anchors

- DOI `10.1371/journal.pone.0014008` — fat-body comet fragmentation and rapid larval revival.
- DOI `10.1016/j.mito.2023.11.002` — rapid post-rehydration oxidative damage and hours-scale repair.
- DOI `10.1073/pnas.1719493115` — Hsf knockdown strongly lowers survival while post-day-1 proliferation rate is not significantly altered.
- DOI `10.1038/s41598-018-36124-6` — rehydration-associated Pv11 DNA-repair transcriptional program.
- DOI `10.1038/s41598-025-19627-x` — early functional recovery and delayed significant bulk population growth.

## Claim ceiling

Passing this gate in one system would **not** establish a universal checkpoint, cross-tissue identity, cross-kingdom molecular homology, longevity mechanism, or therapeutic effect.
