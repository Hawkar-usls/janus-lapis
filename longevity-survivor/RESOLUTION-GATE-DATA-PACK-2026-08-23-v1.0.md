# RESOLUTION GATE DATA PACK v1.0

**Status:** shareable hypothesis packet — **not** a discovery claim and **not** a therapeutic proposal.

## Frozen question

Across independent mammalian injury models, is regenerative outcome better separated by **wound-state fate, spatial routing, handoff and profibrotic-output resolution** than by the lifetime of a single activated-cell marker such as αSMA?

## What this pass deliberately does not do

- It does not infer a numerical half-life from sparse sampling.
- It does not equate marker loss with disappearance of a lineage.
- It does not equate cell-state exit with ECM/scar exit.
- It does not merge anatomically distinct αSMA+ populations.
- It does not claim a universal mammalian regeneration switch.

## Falsification result

The initial model was:

```text
REGENERATION = short controlled wound state + timely EXIT
SCAR         = persistence of the same wound state
```

That model is **refuted as a universal rule**.

Two counterexamples are decisive:

1. **Adult infarcted heart:** αSMA+ myofibroblast identity is maximal at ~3–7 days and lost by roughly day 10–14, but the same lineage persists in a stable scar-associated matrifibrocyte state and the mature ECM scar remains.
2. **Regenerating Acomys full-thickness skin:** upper-wound dermal αSMA clears earlier than in Mus, yet a separate αSMA+ scaffold adjacent to the panniculus carnosus persists for weeks while muscle regenerates.

Therefore:

```text
αSMA half-life alone != regeneration/scar classifier
```

## Revised P0 survivor

### WOUND_STATE_FATE_ROUTING_AND_RESOLUTION_GATE

```text
ENTRY
  ↓
WOUND STATE
  ↓
SPATIAL ROUTING
  ↓
HANDOFF TO REBUILD  ───────┐
  │                        │
  ↓                        ↓
STATE FATE           PROFIBROTIC LOCK
  │                        │
  ↓                        ↓
OUTPUT TERMINATION     ECM MEMORY
  │                        │
  ↓                        ↓
RESTORED ARCHITECTURE     SCAR
```

The candidate common variable is no longer raw activated-cell persistence. It is the combined trajectory:

```text
state occupancy(t)
× spatial compartment
× lineage fate
× handoff success
× profibrotic output(t)
× final architecture
```

## Cross-tissue kinetic evidence

| System | Regenerative outcome | Wound-state timing | EXIT / fate observation | Evidence status |
|---|---|---|---|---|
| Neonatal spinal cord | strong scar-free/scar-reduced repair + axon regrowth | Fn1/fibronectin bridge prominent ~3 dpi | bridge gone by ~7 dpi; microglia return toward homeostatic phenotype within first week | **A; causal depletion/transplantation evidence** |
| Neonatal tendon | neo-tendon + functional recovery | αSMA+ extrinsic cells abundant ~3 dpi; scar transcripts rise ~7 dpi | αSMA strongly reduced by ~14 dpi; scar-associated transcripts return toward control by ~28 dpi; intrinsic Scx-lineage cells rebuild tendon | **A−; lineage evidence, EXIT perturbation incomplete** |
| Acomys ear | adult complex tissue regeneration | myofibroblasts arise in weeks 1–2 | resolve during weeks 3–4; experimentally delaying resolution with YAP–TEAD inhibition shifts healing toward fibrosis | **A; causal resolution evidence** |
| Acomys full-thickness skin | skin + panniculus regeneration | ~75% αSMA+ cells in upper wound at day 7 in both Acomys and Mus | Acomys dermal αSMA largely gone by day 14, but a spatially distinct panniculus αSMA+ bridge persists for weeks during regeneration | **A−; decisive spatial counterexample** |
| Adult heart after MI | stable scar | fibroblast proliferation peaks 2–4 dpi; αSMA myofibroblast state ~3–7 dpi | αSMA is lost ~7–10/14 dpi, but lineage persists as matrifibrocytes and ECM scar remains | **A; decisive counterexample to marker-exit = scar-exit** |
| Neonatal heart MI, 2026 preprint | near-complete scar resolution in WT | scar quantified 4/7/10/21 dpi | fibroblast- or myeloid-specific Erbb4 loss changes scar-resolution kinetics while cardiomyocyte cell-cycle measures remain broadly similar | **B+ preprint; causal and highly relevant** |

## Fresh 2026 cardiac result

A bioRxiv preprint posted **4 August 2026**, *ERBB4 coordinates fibroblast and myeloid cell function during neonatal cardiac regeneration*, is especially useful because it separates **resolution kinetics** from simple cardiomyocyte proliferation.

The study uses P1 mouse myocardial infarction and samples scars at **4, 7, 10 and 21 dpi**. Fibroblast-specific Erbb4 loss leaves a larger residual scar during the resolving phase and at day 21; myeloid-specific Erbb4 loss causes an earlier resolution defect. The reported cardiomyocyte cell-cycle measures do not simply track these scar-resolution delays.

For this project the important point is not ERBB4 as a proposed master target. It is the experimental separation:

```text
PROLIFERATION CAPACITY != SCAR-RESOLUTION CAPACITY
```

Because this is a **preprint**, it remains below peer-reviewed causal evidence until independently reviewed/replicated.

## Highest-value variable for the next pass

Instead of fitting only:

```text
αSMA(t)
```

fit two coupled trajectories:

```text
CELL-STATE OCCUPANCY(t)
PROFIBROTIC-OUTPUT OCCUPANCY(t)
```

where profibrotic output should include, where available:

- collagen I/III deposition and turnover;
- collagen crosslinking / LOX-associated maturation;
- periostin or comparable matrix-production states;
- ECM alignment and stiffness;
- fibronectin/provisional-matrix persistence;
- MMP:TIMP balance or equivalent matrix-remodeling measures;
- final tissue geometry/function.

### Why this matters

Adult heart demonstrates that a canonical myofibroblast marker can disappear while scar memory persists in **lineage state + ECM**. Acomys demonstrates that a long-lived αSMA+ population can be compatible with regeneration if it is **spatially routed into a useful scaffold**. Thus the discriminator must sit above marker duration.

## Killer predictions

The revised model makes falsifiable predictions:

1. **Marker-exit prediction:** αSMA clearance alone will poorly classify regenerative versus fibrotic outcomes across tissues.
2. **Output-resolution prediction:** the duration of irreversible/profibrotic ECM output should classify outcome better than αSMA duration alone.
3. **Routing prediction:** identical marker states in different spatial compartments can have opposite outcomes.
4. **Handoff prediction:** successful regeneration should show measurable transfer from stabilization/scaffold states to resident or recruited rebuilding populations.
5. **State-fate prediction:** non-regenerative tissues can show timely marker loss yet transition into another scar-maintaining cellular state.
6. **Counterfactual prediction:** experimentally delaying resolution of a genuinely profibrotic state should worsen regenerative outcome, while extending a spatially useful scaffold state need not do so.

## Data already public enough for reconstruction

### Neonatal spinal cord
- Single-cell RNA-seq: **GEO GSE150871**, including 0/3/5 dpi samples.
- Article source-data files accompany the Nature paper.
- Immediate task: reconstruct MG-state occupancy and connect it to Fn1/fibronectin bridge histology.

### Adult cardiac scar
- Published lineage-tracing and stage-resolved fibroblast data allow a state chain:

```text
resident fibroblast
→ activated/proliferative fibroblast
→ αSMA myofibroblast
→ matrifibrocyte
```

- Immediate task: distinguish **marker decay**, **lineage-state transition**, and **ECM maturation**.

### Acomys full-thickness skin
- Published time points: 0/7/14/21/28/35/70 d.
- The authors report image-based αSMA quantification.
- Immediate task: obtain or reconstruct per-animal intensity separately for **upper wound dermis** and **panniculus bridge**.

## Data requests that would materially improve the test

1. **Acomys ear:** numeric Acta2+/Myh11− myofibroblast volumes by week and verteporfin condition.
2. **Acomys full-thickness skin:** raw/per-animal αSMA intensity by spatial compartment and time point.
3. **Neonatal tendon:** intermediate αSMA cell abundance between d3 and d14 plus fate after marker loss.
4. **Neonatal spinal cord:** lesion-level Fn1/fibronectin + P2Y12/SPP1/CD68 quantitative values linked to GSE150871 cell-state proportions.
5. **Adult heart:** quantitative occupancy/transition data across activated fibroblast → myofibroblast → matrifibrocyte and matched ECM metrics.
6. **2026 neonatal cardiac preprint:** per-animal scar-area values at 4/7/10/21 dpi plus matching collagen/MMP/capillary measurements.

## Mechanical-lock status

The separate **ECM/mechanical maturation lock** remains a strong P0 candidate, but it is **not promoted to hard P0** here. Native cardiac experiments provide compelling causal evidence, and skin mechanotransduction is strong, but the strict requirement of a third independent tissue where natural developmental mechanics are causally manipulated has not yet been satisfied. Engineered scaffold-stiffness experiments in tendon or spinal cord are supportive but are not counted as the missing native-tissue causal replication.

## Novelty boundary

The literature already recognizes that fibrosis resolution involves combinations of myofibroblast apoptosis, dedifferentiation/reprogramming and ECM degradation, and Acomys work already emphasizes transient activation of wound/fibrotic programs during regeneration.

Therefore this packet **does not claim discovery of fibrosis resolution**.

The potentially useful contribution is narrower:

> A falsification-first cross-tissue kinetic framework that explicitly separates **marker lifetime, lineage lifetime, spatial compartment, profibrotic-output lifetime and scar lifetime**, and uses causal counterexamples to reject a half-life-only model.

## Share threshold

**Current:** `TECHNICAL_HYPOTHESIS_NOTE + DATA_REQUEST`

Appropriate now:
- ask authors for quantitative source data;
- ask whether lineage fate after marker loss is known;
- invite criticism of the cross-tissue normalization;
- offer to return normalized state-occupancy analysis.

Not appropriate yet:
- “we discovered a universal mammalian resolution gate”;
- therapeutic claims;
- human rejuvenation claims;
- a universal numerical wound-state half-life.

## Safe one-sentence statement

> Across several mammalian injury models, regenerative versus fibrotic outcome is not classified by the lifetime of a single activated-cell marker; a more testable cross-tissue model tracks state fate, spatial routing, handoff to rebuilding cells, and persistence of profibrotic ECM output.
