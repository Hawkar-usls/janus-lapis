# JANUS Lapis × Rowan → Fundamentum: typed translator v1

**Status:** offline bridge in a Draft PR, not deployed.

The existing Lapis universal converter transforms structured JSON to algorithm IR, Python skeletons and WAV. This lane uses its **ANNOTATE-only** IR mode so model results cannot become executable operators or mathematical proof.

## Purpose

Take existing, previously collected JANUS Rowan receipts, produce (a) short RU/EN vocabulary brief for agents, (b) strict factual/hypothesis candidate packet for Fundamentum, (c) safe Lapis algorithm IR, and (d) content-addressed provenance manifest. Repeated identical source + language returns a checked cache hit.

Supported read-only input schemas:

- janus.rowan.research_receipt.v1: from Hawkar-usls/Janus/integrations/rowan/janus_rowan_bridge.py (pKa; separate planning, pending, collected).
- janus.rowan.bbc1.stratified_8_mutant_pilot.v1: from Hawkar-usls/Janus/integrations/tranception_rowan/rowan_bbc1_s2_collect.py (8 cases, status and score consistency; not protein fitness).

Do not fabricate provider receipts. Test fixtures do not represent real Rowan results.

## Usage

~~~bash
python tools/rowan_fundamentum_translate.py --input /secure/rowan.receipt.json --outdir /secure/lapis-cache --language ru
python -m unittest discover -s tests -p test_rowan_fundamentum_translate.py -v
~~~

Output folder: outdir/canonical-source-sha256-language/

- candidate.json: whitelisted numeric metrics, status, method, provenance pointers, untested hypothesis, no original prompt or account fields.
- algorithm_ir.json: existing Lapis converter with only ANNOTATE operators, never a SolveLinearCubicXSAT solver.
- brief.txt: short RU/EN controlled-language summary, not free-form model generation.
- manifest.json: source and output SHA-256 fingerprints. These are **not authenticated signatures**.

No provider credentials, Rowan import, network, public upload, writeback into other repositories or new workflow submissions. Does not independently authenticate provider results.

## Correct accounting

Rowan charges **credits for computing time**, not the count of output words/tokens. Local compaction reduces downstream LLM context and repeated local transformations, not credits already spent on a Rowan job. A Rowan credit-saving upstream cache would need separate authoritative checks: provider workflow UUID/project, exact input/model/method, settings, completion, permissions, and budget; no blind resubmission after errors.

## Fundamentum receiving contract

Candidate schema: janus.lapis.rowan_fundamentum_candidate.v1. The source SHA binds canonical input JSON for integrity only. A candidate is UNTESTED; no empirical proof, exact SAT witness, or P versus NP advancement. Formal and biological pipelines remain separate. Private raw inputs should stay in authorized storage. Output may include mutation labels and metrics: review before public distribution.

References: https://docs.rowansci.com/api/python/v3/ , https://docs.rowansci.com/api/python/v3/api/workflow/ , https://docs.rowansci.com/tutorials/account/credits-and-billing
