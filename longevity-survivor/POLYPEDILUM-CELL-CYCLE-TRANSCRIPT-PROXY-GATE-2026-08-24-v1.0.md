# POLYPEDILUM / Pv11 CELL-CYCLE TRANSCRIPT PROXY GATE v1.0

Status: **P0 PREREGISTERED / NO PROXY RESULT YET**

## Purpose

Use public Pv11 rehydration transcriptomes to ask whether a reproducible molecular transition consistent with cell-cycle rebuilding appears between early rehydration and R72, while preserving the hard boundary:

`CELL_CYCLE_TRANSCRIPT_PROXY != DIRECT_S_PHASE_OR_MITOSIS`

This lane can prioritize future experiments and test whether the bulk-growth transition has a molecular precursor. It cannot establish the first cell-cycle event.

## Public inputs

### DRA007433
CAGE-seq, biological triplicate, including Pv11 R3 and R24 after rehydration.

### DRA008948
RNA-seq, biological triplicate, including Pv11 R3, R12, R24 and R72 after rehydration.

### SRP070984
Public Pv11 RNA-seq associated with the Hsf/desiccation-rehydration perturbation study. Use only where sample metadata can be unambiguously matched.

## Frozen gene/process families

The primary proxy panel must be frozen before looking at rehydration trajectories and should cover orthogonal functions rather than a cherry-picked single marker:

- DNA replication licensing / initiation: `ORC`, `CDC6`, `CDT1`, `MCM2-7` homologs where identifiable;
- replication processivity / synthesis: `PCNA`, replicative polymerase-family homologs;
- S/G2 transition and checkpoint context: Cyclin/CDK homologs, `CDC25`, `WEE1`, `CHK1/CHK2`-like homologs where identifiable;
- mitotic machinery: condensin/cohesin, spindle/kinetochore and mitotic cyclin homologs where identifiable;
- quiescence/stress/recovery controls;
- mitochondrial/translation recovery controls;
- DNA-repair families analysed separately from cell-cycle families.

Homology uncertainty must be retained. A gene is not assigned a canonical cell-cycle role merely because its name resembles a vertebrate ortholog.

## Frozen time comparison

For DRA008948, the primary trajectory is:

`R3 -> R12 -> R24 -> R72`

T0 is a reference normal-culture state, not a post-rehydration timepoint. Trehalose/desiccation states may be used as context but must not be silently inserted into the rehydration clock.

DRA007433 provides an independent platform/context check at `R3 -> R24`, not a substitute for missing R12/R72 points.

## Required analysis outputs

For every admitted homolog/process family:

1. accession and sample identifiers;
2. annotation source and homology confidence;
3. normalized expression trajectory by biological replicate;
4. effect size and uncertainty for preregistered contrasts;
5. whether direction replicates across datasets/platforms where comparable;
6. mitochondrial-read fraction / mapping-quality caveats for early rehydration;
7. explicit missingness.

## Primary contrasts

- `R3 -> R12`
- `R12 -> R24`
- `R24 -> R72`
- `R3 -> R72`
- `R72 -> T0` as a recovery-to-reference comparison, not a time interval.

## Competing patterns

### P0_NO_COHERENT_TRANSITION
Cell-cycle-associated families do not show a coherent reproducible transition.

Result: `NO_TRANSCRIPT_PROXY_SUPPORT_FOR_DISCRETE_REENTRY_TRANSITION`.

### P1_EARLY_REBUILD
A coherent cell-cycle-associated program rises by R12/R24, substantially before the published ~72 h significant bulk-growth boundary.

Result: `TRANSCRIPT_PROXY_PRECEDES_BULK_GROWTH`.

This would prioritize direct early S-phase measurements but would **not** establish early proliferation.

### P2_LATE_REBUILD
A coherent transition appears mainly from R24 to R72.

Result: `LATE_TRANSCRIPT_PROXY_ALIGNS_WITH_BULK_GROWTH_WINDOW`.

This remains association, not a repair checkpoint.

### P3_REPAIR_CELL_CYCLE_DISSOCIATION
Repair-associated programs and cell-cycle-associated proxy programs peak/shift on different trajectories.

Result: `REPAIR_PROGRAM_AND_CELL_CYCLE_PROXY_ARE_TEMPORALLY_DISSOCIABLE`.

### P4_GLOBAL_RECOVERY_CONFOUND
Cell-cycle-associated changes are not distinguishable from broad mitochondrial/translation/global recovery.

Result: `CELL_CYCLE_SPECIFICITY_NOT_ESTABLISHED`.

## Falsification rules

- If the apparent transition disappears after replicate-level analysis or mapping-quality controls, reject it.
- If the same pattern is equally strong in broad housekeeping/global-recovery families, do not call it cell-cycle-specific.
- If homolog annotation is ambiguous, keep the gene out of the primary panel or mark it exploratory.
- No post-hoc timepoint deletion to sharpen a transition.
- No converting transcript abundance into percentages of cells in S phase.
- No use of this lane to overwrite `CX_FIRST_CELL_CYCLE_ENTRY = UNKNOWN`.

## Promotion ceiling

The strongest allowed result is:

`REPRODUCIBLE_CELL_CYCLE_TRANSCRIPT_PROXY_TRANSITION_WITHIN_PV11_REHYDRATION`

It does **not** establish direct S phase, mitosis, a causal DNA-repair permission gate, tissue-wide timing, longevity, or therapeutic relevance.
