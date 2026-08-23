# Polypedilum / Pv11 staged re-entry — technical outreach packet v1.0

**Status:** technical hypothesis + source-data request. Not a discovery claim, not a therapeutic proposal.

## Question

Across independently evolved reversible stress-recovery systems, do low-risk functions resume on an earlier clock than high-risk processes such as genome replication, germline transmission, or sustained growth?

We preregistered a simple threshold before the Polypedilum pass: **>=3 independent lineages showing temporal separation between basic-function recovery and high-risk restart** would promote the pattern to a kinetic survivor. Causal promotion would still require a perturbation showing that repair/checkpoint status changes restart timing.

## Three-lineage result

| Lineage | Early/basic function | Damage-repair phase | High-risk restart | Evidence status |
|---|---|---|---|---|
| *Bacillus subtilis* spores | germination/outgrowth begins rapidly | DNA-repair/checkpoint activity during early outgrowth | first replication/division follows damage processing; repair/checkpoint defects delay outgrowth and disrupt chromosome segregation | causal |
| *Adineta vaga* | mobility can recover while DSBs remain | somatic repair continues; germline repair is delayed to a specific oogenesis window | heritable genome transmission is handled under a separate high-fidelity repair regime | strong independent |
| *Polypedilum vanderplanki* / Pv11 | larval physiological activity <~1 h; Pv11 functional recovery begins within 1–24 h | rehydration-associated DNA-repair programs at ~3–24 h | Pv11 live-cell number remains essentially flat through 48 h; significant proliferation is first detected at ~72 h | kinetic third lineage |

Result:

`THREE_LINEAGE_KINETIC_THRESHOLD = MET`

but

`CAUSAL_REPAIR_CHECKPOINT = OPEN`

## Why Polypedilum is decisive

Published Polypedilum/Pv11 studies now provide three separated clocks:

1. **basic function:** minutes to hours after rehydration;
2. **repair/recovery program:** prominent during ~3–24 h;
3. **significant proliferation:** first detected around ~72 h in a 2025 Pv11 time series.

Classic whole-larva work also reports nuclear-DNA integrity recovering on a much slower ~72–96 h scale than behavioral recovery. These observations support temporal separation, but they do not establish that unresolved DNA damage *causes* the proliferation delay because the relevant measurements come from different experiments and, in part, different biological levels (whole larva vs Pv11 cell line).

## Falsification boundary

We explicitly reject the stronger interpretations:

- `FULL_REPAIR_BEFORE_ANY_FUNCTION` — refuted.
- `ONE_REENTRY_CLOCK` — refuted.
- `BASIC_FUNCTION_RETURN = FULL_RECOVERY` — refuted.
- `POLYPEDILUM_PROVES_A_UNIVERSAL_DAMAGE_CHECKPOINT` — not supported.

The surviving claim is narrower:

> In three independently evolved systems, basic functional recovery and high-risk restart are temporally separable; Polypedilum/Pv11 provides the third kinetic lineage, but direct causal gating by DNA-repair/checkpoint status remains untested.

## Single highest-value experiment / data request

A matched Pv11 rehydration series from **0–96 h** measuring, in the same experiment:

- DNA-damage burden;
- DNA-repair/checkpoint state;
- cell-cycle phase or S-phase entry;
- live-cell number / proliferation onset;
- viability;
- one early functional-recovery readout.

Then perturb a relevant repair/checkpoint component or experimentally alter unresolved damage and ask whether the onset of S phase/proliferation shifts.

### Kill rule

If proliferation onset remains unchanged despite a controlled increase in unresolved DNA damage or impairment of the relevant repair/checkpoint machinery, the causal high-risk permission-gate hypothesis is weakened or rejected for Polypedilum.

## What we are asking the Polypedilum team

1. Are there unpublished or machine-readable **0–96 h Pv11 cell-cycle / proliferation data** at denser time points than the published growth series?
2. Has the group measured **EdU/BrdU incorporation, flow-cytometric cell-cycle state, mitotic index, or equivalent proliferation-entry readouts** during rehydration?
3. Are there experiments in which **damage load or repair capacity** was varied and the timing of proliferation restart was measured quantitatively?
4. If source data are available, we would return a normalized, auditable comparison separating early function, repair state, proliferation onset, and uncertainty rather than treating them as one recovery clock.

## Relevant project artifacts

- `POLYPEDILUM-THIRD-LINEAGE-GATE-CLOSEOUT-2026-08-23-v1.3.json`
- `POLYPEDILUM-REENTRY-KINETICS-2026-08-23-v1.3.csv`
- `EXTREMOPHILE-STAGED-REENTRY-NOTE-2026-08-23-v1.2.md`
- `EXTREMOPHILE-RECOVERY-GATE-KILLER-TEST-2026-08-23-v1.0.json`

## Claim ceiling

Kinetic separation is not causal checkpoint evidence. Pv11 is not the whole larva. Cross-kingdom functional similarity is not molecular homology. No human longevity or therapeutic claim is made.