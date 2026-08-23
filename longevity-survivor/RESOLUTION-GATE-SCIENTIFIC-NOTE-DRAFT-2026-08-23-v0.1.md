# Cross-tissue kinetics of regenerative wound-state resolution

**Draft v0.1 — for technical review/data request only**  
**DO NOT SEND AS A DISCOVERY CLAIM**

## Working title

**Marker lifetime is not wound resolution: a falsification-first cross-tissue framework for regenerative versus fibrotic state trajectories in mammals**

## Abstract

Mammalian regeneration is often contrasted with fibrosis using the abundance or persistence of activated wound-cell markers, particularly α-smooth-muscle actin (αSMA). We tested a stricter cross-tissue hypothesis: that successful regeneration is characterized by a short-lived activated wound state followed by timely clearance, whereas scarring reflects persistence of the same state. Published temporal and lineage data from neonatal mouse spinal cord and tendon, regenerating adult *Acomys* skin, adult mouse myocardial infarction, and a 2026 neonatal cardiac-regeneration preprint were aligned by injury-state progression rather than chronological age. The simple persistence hypothesis fails. Adult cardiac αSMA+ myofibroblast identity resolves while lineage-traced fibroblasts and mature scar persist in a matrifibrocyte/ECM state, whereas a spatially distinct αSMA+ scaffold persists for weeks during successful *Acomys* panniculus regeneration. These counterexamples suggest that wound outcome should be modeled using state fate, spatial compartment, regenerative handoff, and persistence of profibrotic ECM output rather than marker lifetime alone. We propose a quantitative, falsifiable comparison of cell-state occupancy and profibrotic-output occupancy across regenerative and scar-forming systems.

## 1. Question

Can a common mammalian wound-resolution variable be identified across tissues without assuming that the same gene, marker or absolute time scale is shared?

The initial hypothesis was intentionally simple:

```text
regeneration → short wound-state lifetime → EXIT
fibrosis     → long wound-state lifetime  → persistence
```

We attempted to falsify this model rather than select examples that support it.

## 2. Alignment method

Systems are not aligned by postnatal age or by a shared molecular marker. They are compared using an injury trajectory:

```text
ENTRY
→ PEAK WOUND STATE
→ STATE TRANSITION / CLEARANCE
→ ECM OUTPUT RESOLUTION OR PERSISTENCE
→ FINAL ARCHITECTURE
```

For each system we distinguish:

1. **marker occupancy** — e.g. αSMA, Fn1, CD68;
2. **cell-state occupancy** — the transcriptional/functional wound state;
3. **lineage occupancy** — whether the same cells remain after marker loss;
4. **spatial compartment** — where that state resides;
5. **profibrotic output** — collagen deposition/crosslinking, periostin, matrix organization/stiffness, MMP/TIMP balance;
6. **architecture outcome** — restored tissue versus persistent scar.

Sparse temporal observations are treated as **interval-censored lifetimes**. We do not calculate a half-life unless the underlying quantitative time series supports one.

## 3. Falsification result

### Hypothesis H0

> A short activated-cell state is a general feature of regeneration, whereas persistence of the same activated-cell state is a general feature of fibrosis.

### Result

**H0 is rejected as a universal cross-tissue rule.**

Two observations are sufficient to break it:

- In adult myocardial infarction, αSMA+ myofibroblasts are maximal during the early scar-forming phase and lose αSMA by roughly day 10–14. The lineage does not disappear: fibroblasts remain within mature scar in a stable matrifibrocyte state while collagenous ECM persists.
- In regenerating adult *Acomys* full-thickness skin, dermal αSMA+ cells clear earlier than in scar-forming *Mus*, but another spatially distinct αSMA+ population forms a panniculus-associated scaffold that persists for weeks during successful muscle regeneration.

Thus:

```text
marker persistence != fibrosis
marker clearance   != regeneration
```

## 4. Cross-system observations

### Neonatal spinal cord

In P2 mouse spinal-cord injury, lesion-associated microglia organize a transient fibronectin-rich bridge. The Fn1/fibronectin repair state is prominent around 3 dpi, the bridge is no longer present by approximately 7 dpi, and microglial morphology/markers return toward a homeostatic state within the first week. Microglial depletion impairs bridge formation and axonal regrowth, while neonatal microglia can improve adult repair, giving this system unusually strong causal leverage.

**Interpretation:** timely state resolution and handoff are compatible with regeneration, but the relevant variable is a structured transition rather than simply disappearance of an inflammatory marker.

### Neonatal tendon

P5 neonatal Achilles injury recruits abundant αSMA+ extrinsic cells by ~3 dpi while intrinsic Scx-lineage tenocytes proliferate and subsequently populate a neo-tendon. αSMA staining is strongly reduced by ~14 dpi and scar-associated transcripts return toward control by ~28 dpi. Adult tendon instead fills the defect predominantly with extrinsic scar-forming cells and remains functionally impaired.

**Interpretation:** the regenerative system appears to use an early helper/fibrotic-like state and then hand off reconstruction to intrinsic tendon lineage. Direct selective manipulation of helper-cell EXIT remains an important missing experiment.

### *Acomys* ear pinna

Adult *Acomys* activates myofibroblasts during injury, but the state is transient during regeneration. Experimental YAP–TEAD inhibition prolongs myofibroblast persistence and shifts healing toward fibrosis.

**Interpretation:** this supplies causal evidence that improper resolution of a specific state can alter regenerative outcome, while also showing that wound/fibrotic programs need not be absent during regeneration.

### *Acomys* full-thickness skin

A 2026 comparison of *Acomys* and *Mus* reports strong αSMA induction in the upper wound compartment in both species at day 7. In *Acomys*, dermal αSMA largely clears earlier, but a strong αSMA+ bridge develops between panniculus carnosus ends and persists for weeks during complete muscle regeneration. In *Mus*, αSMA later declines while the collagenous scar persists.

**Interpretation:** spatial routing changes the meaning of persistence. A long-lived activated-cell marker can represent a useful regenerative scaffold rather than a fibrotic lock.

### Adult heart after myocardial infarction

Lineage tracing demonstrates a sequential resident-fibroblast → activated fibroblast → αSMA+ myofibroblast → matrifibrocyte trajectory. αSMA is transient, whereas the lineage and mature scar persist.

**Interpretation:** cellular marker EXIT is not equivalent to lineage EXIT or ECM/scar EXIT. This is a strong negative control for any half-life-only model.

### Neonatal heart — 2026 preprint

A bioRxiv study posted 4 August 2026 measures neonatal post-MI scar area at 4, 7, 10 and 21 dpi and perturbs Erbb4 in fibroblast or myeloid compartments. These manipulations alter scar-resolution kinetics while reported cardiomyocyte cell-cycle measures are not equivalently shifted.

**Interpretation:** the experiment supports a conceptual separation between **regenerative proliferation** and **scar-resolution kinetics**. Because the study is a preprint, it should be treated as provisional evidence.

## 5. Revised model

The surviving model is:

```text
ENTRY
  ↓
WOUND STATE
  ↓
SPATIAL ROUTING
  ↓
HANDOFF TO REBUILD ───────────────┐
  ↓                               ↓
STATE FATE                  PROFIBROTIC LOCK
  ↓                               ↓
OUTPUT TERMINATION           ECM MEMORY
  ↓                               ↓
RESTORED ARCHITECTURE            SCAR
```

Candidate quantitative variables:

```text
S(t) = cell-state occupancy
P(t) = profibrotic-output occupancy
R(t) = resident/rebuilding-lineage occupancy
E(t) = ECM/scar burden or irreversibility
```

The next test is not whether `S(t)` is universally shorter in regeneration. Instead:

> Does the coupled trajectory `[S(t), P(t), R(t), E(t)]`, including spatial compartment and state transitions, separate regenerative from scar-forming outcomes better than `S(t)` alone?

## 6. Predictions

The model is falsified or weakened if any of the following hold broadly across matched systems:

- raw marker lifetime alone predicts outcome as well as the full state/ECM model;
- spatially distinct wound states show no meaningful difference in downstream fate;
- regenerative handoff to resident/rebuilding populations is not temporally related to wound-state transition;
- profibrotic ECM output persists equally in regenerative and fibrotic systems despite divergent final architecture;
- manipulating wound-state fate or output resolution fails to alter outcome in additional tissues.

The model gains support if:

- profibrotic-output persistence predicts outcome better than αSMA duration;
- lineage tracing repeatedly reveals distinct post-marker-loss fates in regenerative versus fibrotic systems;
- causal changes to EXIT/routing alter regeneration without simply changing proliferation;
- the same wound marker exhibits different outcomes according to anatomical compartment and fate.

## 7. Requested quantitative data

A compact cross-tissue reconstruction would benefit most from:

- **spinal cord:** lesion-level Fn1/fibronectin and P2Y12/SPP1/CD68 values across 3/5/7 dpi, linked to GSE150871 state proportions;
- **neonatal tendon:** αSMA+ cell abundance at intermediate points between 3 and 14 dpi, plus fate of αSMA+ cells after marker loss;
- ***Acomys* ear:** numeric myofibroblast volume/intensity by week and perturbation condition;
- ***Acomys* skin:** per-animal αSMA intensity separately for upper dermal wound and panniculus scaffold at 7/14/21/28/35 dpi;
- **adult heart:** quantitative state occupancy and transition information from activated fibroblast to myofibroblast to matrifibrocyte with matched ECM maturation metrics;
- **neonatal heart 2026 preprint:** individual scar-area measurements at 4/7/10/21 dpi and matched collagen/MMP/capillary measurements.

## 8. What would be returned to contributing laboratories

If quantitative source data are available, the proposed output is deliberately simple and auditable:

1. normalized time axis within each injury model;
2. observed state-occupancy points with no interpolated biological claims;
3. interval-censored EXIT windows;
4. separate spatial compartments;
5. explicit lineage transition edges where known;
6. profibrotic-output trajectory alongside marker trajectory;
7. sensitivity analysis excluding each tissue in turn;
8. a falsification report showing which cross-tissue claims survive or fail.

The intention is not to re-label authors' biology under a new theory, but to test whether a common kinetic abstraction survives comparison across their independently generated systems.

## 9. Novelty and claim ceiling

Fibrosis-resolution biology, myofibroblast plasticity and ECM clearance are established research areas. This draft does **not** claim to discover those concepts.

The potentially useful contribution is the cross-tissue falsification framework:

```text
marker lifetime
!= lineage lifetime
!= profibrotic-output lifetime
!= scar lifetime
```

with spatial routing and regenerative handoff treated as explicit variables.

### Allowed claim

> Existing mammalian injury data contain causal examples and counterexamples showing that activated-cell marker duration alone is insufficient to classify regeneration versus fibrosis; state fate, spatial routing and persistence of profibrotic output form a stricter cross-tissue hypothesis worth quantitative testing.

### Not allowed

- universal mammalian RESOLUTION GATE discovered;
- universal numerical half-life discovered;
- therapeutic target established;
- human rejuvenation demonstrated.

## 10. Communication status

**READY FOR TECHNICAL REVIEW / SOURCE-DATA REQUEST**  
**NOT READY FOR DISCOVERY ANNOUNCEMENT**  
**NO EMAIL SENT**
