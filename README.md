<div align="center">

# JANUS Lapis
### Computational hypothesis-ranking sandbox

`candidate generation` · `explicit gates` · `expert review required`

</div>

JANUS Lapis is an exploratory software tool inspired by historical alchemical archetypes. It ranks computational candidates and records gate decisions so that ideas can be reviewed later by qualified experts.

It does **not** validate a material, reaction or synthesis procedure.

## Current scope

The tool produces:

- candidate/ranking tables;
- archetype comparisons;
- gate/rejection records;
- machine-readable summaries;
- an external-review brief.

Machine-readable project boundary: [`PROJECT_STATUS.json`](PROJECT_STATUS.json)

## Scientific boundary

```text
LITERAL_TRANSMUTATION = NOT_CLAIMED
ELIXIR_OR_LIFE_EXTENSION = NOT_CLAIMED
VALIDATED_MATERIAL = NOT_ESTABLISHED
LABORATORY_EFFICACY = NOT_ESTABLISHED
SAFE_SYNTHESIS_PROCEDURE = NOT_PROVIDED
HAZARDOUS_SYNTHESIS_INSTRUCTIONS = FORBIDDEN
```

Names such as `LAPIS_DEMIURGE` or `BIRTH_GATE` are internal search/archetype labels. They are not claims about physics, chemistry or metaphysical agency.

## Run

```bash
RUN_JANUS_LAPIS.bat
```

Primary review outputs include:

```text
janus_lapis_summary.json
janus_lapis_champions.csv
janus_lapis_all_archetypes.csv
janus_lapis_decision_chain.csv
janus_lapis_birth_gates.csv
janus_lapis_rejected_by_gate.csv
lab_request/JANUS_LAPIS_EXTERNAL_RESEARCH_BRIEF.md
lab_request/janus_lapis_external_research_request.csv
docs/BIRTH_GATE_METHOD.md
```

## Interpretation

A high computational score means only that a candidate ranked highly under the implemented scoring/gating model. Any real material claim requires separate chemistry, safety review, experimental protocol, measurements and independent interpretation.
