# EXTREMOPHILE STAGED RE-ENTRY — KILLER TEST v1.2

**Status:** cross-kingdom falsification result. This is a comparative-biology abstraction, not evidence of a conserved molecular pathway and not a human intervention proposal.

## Frozen prediction

After reversible dormancy/extreme stress, biologically risky functions should not necessarily restart on the same clock as movement, hydration or basal metabolism. In particular, genome replication, germline transmission and sustained growth may be subject to stronger damage-resolution constraints.

Systems were aligned at `tau0 = rehydration / germination` rather than by absolute organismal age.

## Result in one line

**Recovery is multi-stage and risk-structured, but the strongest “high-risk restart checkpoint” claim has only two strong independent lines so far and is not promoted to hard P0.**

## Evidence matrix

| System | Early function | Damage / repair clock | High-risk restart evidence | Grade |
|---|---|---|---|---|
| *Bacillus subtilis* spores | germination/outgrowth begins rapidly | repair/replication programs ~5–25 min, second repair wave ~40–50 min | oxidative lesions activate checkpoint mechanisms; repair/checkpoint defects delay replication/outgrowth and disrupt first chromosome segregation | **A causal** |
| *Adineta vaga* | full mobility can recover by ~8 h despite remaining DSBs | somatic repair continues through 48 h | germline damage is not repaired immediately; repair is delayed to a specific oogenesis window and accurate genome structure is restored in progeny | **A− strong** |
| *Polypedilum vanderplanki* | heart/pharynx ~7–12 min; active behavior ~20–60 min | some oxidative lesions resolve within hours, whole nuclear DNA integrity may require ~72–96 h | no matched clean replication/developmental restart readout found | **B+ kinetic** |
| tardigrades | *R. varieornatus* moves ~5 min and is normally active/feeding ~15 min | matched DNA-repair trajectory missing | no clean replication/reproduction checkpoint series | **B incomplete** |
| *Craterostigma plantagineum* | molecular rehydration program unfolds during first day | transcriptome near hydrated state ~24 h; proteome/physiology continue toward recovery through ~48 h | cell-cycle/growth restart is not sufficiently matched to damage kinetics | **B+ staged recovery** |

## Strongest causal system — Bacillus

During *B. subtilis* spore germination/outgrowth, rehydration and renewed aerobic metabolism generate oxidative DNA lesions. BER defects produce delayed outgrowth. DisA and additional damage-responsive checkpoint mechanisms influence the return to vegetative growth; checkpoint/repair-defective backgrounds show increased lesions and chromosome-segregation defects during the first round of replication. Wild-type cells can have undergone multiple chromosome replication/division cycles by ~90 min.

This is direct support for:

```text
DAMAGE LOAD
   ↓
CHECKPOINT / REPAIR
   ↓
REPLICATION PERMISSION
   ↓
VEGETATIVE GROWTH
```

## Strongest multicellular system — Adineta

*Adineta vaga* falsifies the simple rule `full DNA repair before function`.

After severe genome fragmentation, mobility can return while DSBs remain. Somatic repair begins rapidly but remains incomplete in some assays at 48 h. Germline repair behaves differently: damaged primary oocytes do not immediately enter the same repair program; accurate repair is delayed to a specific oogenesis window in which chromosomes are organized for high-fidelity reconstitution, and the parental genomic pattern is recovered in offspring.

Thus the same animal appears to use different permission logic for:

```text
SOMA / MOVEMENT
vs
GERMLINE / HERITABLE GENOME TRANSMISSION
```

This is a particularly strong example of **risk-structured recovery** without implying molecular homology to bacterial checkpoints or mammalian wound healing.

## Polypedilum is the key missing bridge

*P. vanderplanki* restarts organ function extremely rapidly: heart/pharyngeal activity is reported within ~7–12 min and normal larval activity in roughly ~20–60 min. Yet nuclear DNA integrity after anhydrobiosis can take ~72–96 h to recover in comet/TEM assays. A newer oxidative-stress study indicates that some post-rehydration oxidative lesions are repaired within hours.

These observations are not contradictory if molecular damage is layered:

```text
FAST: selected oxidative lesions / metabolic restart
SLOW: restoration of whole nuclear-DNA integrity
```

The missing experiment is a matched readout of **cell proliferation or developmental progression** during that 0–96 h window.

## Tardigrades do not currently prove the checkpoint prediction

In *Ramazzottius varieornatus*, movement begins at ~5 min after rehydration and normal activity, feeding and several ultrastructural features approach hydrated controls by ~15 min. In *Paramacrobiotus experimentalis*, the fraction of animals returning to coordinated activity changes across 2/6/24/48 h and depends strongly on age and prior anhydrobiosis history.

However, without a matched quantitative genome-damage/repair plus replication/reproduction series, tardigrades cannot honestly be counted as a high-risk checkpoint replication.

## Craterostigma supports staged recovery, not yet a replication gate

In *C. plantagineum*, rehydration-specific transcriptional changes appear around ~12–15 h. Modern multi-omics work shows a global transcriptome close to the fully hydrated state after ~24 h, whereas protein and physiological recovery continues: at 48 h photosynthetic carbon assimilation is ~71% of control while stomatal conductance and transpiration are reported fully restored.

Related *Craterostigma wilmsii* experiments provide a useful causal control: if rapid dehydration creates extra damage, inhibiting new transcription or translation during rehydration prevents recovery, showing that post-stress repair synthesis can become essential when protection fails.

## TOPA

Refuted:

```text
FULL_REPAIR_BEFORE_ANY_FUNCTION = REFUTED
ONE_REENTRY_CLOCK              = REFUTED
DORMANCY_REQUIRES_CONTINUOUS_REPAIR = REFUTED
```

Survives:

```text
STAGED_DAMAGE_AWARE_REENTRY = P0_CROSS_KINGDOM_SURVIVOR
```

But the stronger claim remains below P0:

```text
HIGH_RISK_FUNCTIONS_REQUIRE_STRONGER_DAMAGE_RESOLUTION_GATE
= P1_STRONG_CANDIDATE
```

Reason: the preregistered threshold of **>=3 independent lineages with a matched high-risk restart readout** has not been met. *Bacillus* is causal; *Adineta* is strong and independent; *Polypedilum* is kinetic but still lacks the decisive replication/development measurement.

## Revised abstraction

```text
SAFE_REENTRY_IS_A_PERMISSIONS_GRAPH_NOT_A_TIMER
```

A system may restore different functions on different clocks:

```text
REHYDRATION
   ↓
BASIC FUNCTION
   ↓
ONGOING REPAIR
   ├── SOMATIC / LOW-RISK PERMISSION
   └── HIGH-RISK CHECKPOINT
          ↓
     REPLICATION / GERMLINE / GROWTH
          ↓
     STABLE HOMEOSTASIS
```

## Next killer test

The shortest route to a hard result is not another organism list. It is one decisive third lineage with matched curves:

```text
DAMAGE(t)
REPAIR(t)
BASIC_FUNCTION(t)
REPLICATION_OR_GROWTH(t)
```

Best current targets:

1. *Polypedilum* — add cell proliferation/developmental-progression timing to the known 0–96 h recovery window.
2. *Adineta* — put mobility, somatic DSB repair, oocyte repair, egg laying and viable progeny on one normalized tau axis.
3. Resurrection plants — recover cell-cycle/growth restart alongside transcriptome/proteome/physiology.
4. Future *Chroococcidiopsis* rehydration multi-omics — prospective test, not retrospective fitting.

## Claim ceiling

This experiment supports a cross-kingdom temporal-control abstraction. It does **not** establish a conserved molecular checkpoint, a mammalian regeneration mechanism, a longevity intervention or a human rejuvenation strategy.
