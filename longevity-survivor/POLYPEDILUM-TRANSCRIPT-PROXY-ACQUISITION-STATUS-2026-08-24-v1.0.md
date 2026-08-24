# Pv11 transcript-proxy acquisition status — 2026-08-24 v1.0

## Current state

`INPUT_IDENTITIES_RESOLVED / PRIMARY_BYTES_NOT_MATERIALIZED / ANALYSIS_BLOCKED`

The public 2020 Pv11 RNA-seq paper defines a biological-triplicate time course including R3, R12, R24 and R72 and deposits the sequencing data as DRA008948. Its published WGCNA table reports a 1222-gene Blue module with `DNA replication` (`GO:0006260`) as the representative enriched term (`p = 1.20e-12`). This is a valid **module-level public anchor**, but it does not reveal whether that module rises early, late, transiently, or monotonically during rehydration.

## Inputs identified

- DRA008948 — raw/public sequencing archive for the 2020 Pv11 study.
- PLOS S1 Data — supporting expression/DEG data associated with DOI `10.1371/journal.pone.0230218`.
- PLOS S2 Data — supporting gene/module membership data associated with the same article.
- DRA007433 — independent CAGE-seq recovery context at R3/R24.
- SRP070984 — HSF/desiccation-rehydration perturbation transcriptomic context.

## Acquisition result in this pass

The public identities, archive directory and supplement identities were located. Exact primary XLSX/XML/count-matrix bytes were **not materialized into the analysis environment in this pass**, so no hashes, workbook inspection, run-to-condition binding, gene-level trajectories or proxy scores are reported.

This is a technical input-acquisition state, not a biological negative result.

## Fail-closed boundary

The analysis must not infer sample labels from accession order, digitize a published heatmap as a substitute for the matrix, infer time direction from GO enrichment, or treat transcript abundance as direct S-phase/mitosis evidence.

The next legal transition is:

`ACQUIRE EXACT BYTES -> HASH -> VERIFY SAMPLE MANIFEST -> FREEZE EXACT HOMOLOG PANEL -> RUN REPLICATE-LEVEL PROXY ANALYSIS`

Until that transition completes:

`CX_FIRST_CELL_CYCLE_ENTRY = UNKNOWN`

and

`CELL_CYCLE_TRANSCRIPT_PROXY_RESULT = NOT_RUN`.
