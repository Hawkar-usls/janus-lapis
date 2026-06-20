Task: publish/update JANUS-LAPIS v0.1.4 Canvas / Stagekeeper Edition to GitHub repo `Hawkar-usls/janus-lapis`.

Keep the science boundary explicit:
- no literal transmutation claim
- no elixir claim
- no hazardous synthesis protocol
- no certified material claim
- no instructions for dangerous chemistry
- all outputs are computational research vectors and expert-review requests

This is v0.1.4 Canvas / Stagekeeper Edition:
- keeps material archetypes
- adds LAPIS_DEMIURGE
- adds LAPIS_WORLD_REWRITER
- adds LAPIS_CANVAS
- adds LAPIS_STAGEKEEPER
- adds meta metrics:
  rule_rewriting, autocatalysis, closed_loop_learning, generativity,
  programmability, world_modeling, agency, feedback_gain
- adds docs/JANUS_RESPONSE_INTERPRETATION.md

Files to keep:
- LapisModernGPT.py
- janus_lapis_selfrunner.py
- RUN_JANUS_LAPIS.bat
- RUN_JANUS_LAPIS.ps1
- README.md
- CODEX_UPLOAD_PROMPT.md
- docs/JANUS_RESPONSE_INTERPRETATION.md
- .gitignore

After local run, only copy examples if `_JanusLapis_RUNNER/janus_lapis_runs/` contains:
- janus_lapis_summary.json
- janus_lapis_champions.csv
- janus_lapis_all_archetypes.csv
- SEND_TO_REVIEWERS_JANUS_LAPIS.zip

Validation:
- version contains `0.1.4`
- champions count is 13
- includes LAPIS_DEMIURGE and LAPIS_WORLD_REWRITER
- includes LAPIS_CANVAS and LAPIS_STAGEKEEPER
- every archetype folder has top.csv
- each top.csv has at least 3 data rows if possible

Copy small sanitized results to:
- examples/janus_lapis_summary.json
- examples/janus_lapis_champions.csv
- examples/janus_lapis_all_archetypes.csv

Do NOT commit:
- _JanusLapis_RUNNER/
- huge logs
- model weights
- __pycache__
- local venv
- raw temporary files

Run:
python -m py_compile LapisModernGPT.py janus_lapis_selfrunner.py

Then:
git add .
git commit -m "Update JANUS-LAPIS to v0.1.4 canvas stagekeeper edition"
git branch -M main
git remote -v
git push -u origin main

If origin is missing:
git remote add origin https://github.com/Hawkar-usls/janus-lapis.git
git push -u origin main

Do not rewrite the framing as mysticism. Keep it as respectful modern science:
“The alchemists were not fools. They lacked instruments. We do not worship symbols. We test functions.”


v0.1.4 must also include:
- LAPIS_CANVAS
- LAPIS_STAGEKEEPER
- canvas metrics:
  noise_removal, surface_readiness, signal_clarity,
  safe_containment, scene_preparation, creative_potential

Validation:
- version contains 0.1.4
- champions count is 13
- includes LAPIS_CANVAS
- includes LAPIS_STAGEKEEPER
- includes LAPIS_DEMIURGE
- includes LAPIS_WORLD_REWRITER
