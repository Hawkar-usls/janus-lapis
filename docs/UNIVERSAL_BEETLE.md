# JANUS Universal Beetle

The Universal Beetle is a persistent, bounded research ingestion organ for JANUS/Lapis.
It separates **direction** from **execution**:

- `data/beetle/directions.json` says what to look for and which large objects are approved to graze.
- `tools/universal_beetle.py` performs bounded discovery and bounded reads.
- `.github/workflows/universal-beetle-hourly.yml` runs the Beetle in GitHub Actions.
- branch `beetle-state` is the Beetle's append-oriented memory: candidates, receipts, cursors and large-object checkpoints.

## Core loop

`DIRECTION -> DISCOVER -> SCORE -> DEDUPE -> BITE -> RECEIPT -> CHECKPOINT -> NEXT`

The Beetle never turns a discovery candidate into evidence by itself.

## Two jaws

### Scout

Searches configured public metadata sources (currently arXiv, Zenodo, GitHub repository search, and generic RSS/Atom feeds). It stores only candidates that match a frozen direction and are not already seen.

### Grazer

Continues approved large objects with bounded reads. The first specialized grazer is `uwa_hdf5_channel`, which delegates to `tools/ocean_beetle.py`. A generic `http_range_text` adapter is also available for large text/JSONL/CSV-like objects.

## State branch

GitHub runners are ephemeral, so durable state is not kept in an Actions workspace. The workflow checks out the `beetle-state` branch into a second directory. After each run it commits only state changes back to that branch.

This makes the Beetle resumable across unrelated GitHub runners.

## Directing the Beetle

Edit `data/beetle/directions.json` on `main`.

A direction contains:

- `id`
- `keywords` and optional `priority_keywords`
- `min_score`
- enabled discovery sources

A grazer task contains an explicit URL and a bounded bite size. Large objects are **not** auto-approved from search results.

## Manual runs

```bash
python tools/universal_beetle.py \
  --config data/beetle/directions.json \
  --state-dir ./beetle-state \
  --mode both
```

You can restrict it:

```bash
python tools/universal_beetle.py --state-dir ./beetle-state --mode scout --direction ocean_reader
python tools/universal_beetle.py --state-dir ./beetle-state --mode graze --grazer-task uwa_blue_1_raw_channel
```

## Safety / epistemic boundaries

- HTTPS only for network sources.
- Discovery is metadata-first and budget-limited.
- Search results are `DISCOVERY_CANDIDATE__NOT_VERIFIED__NO_PROOF_AUTHORITY`.
- Large-body reading requires an explicit grazer task.
- `http_range_text` refuses an oversized whole body when a server ignores a resumed Range request.
- UWA HDF5 uses the existing Ocean Beetle range guard and checkpoints.
- No discovery changes JANUS/TRUMP proof status.

## Adding new jaws

Add a new scout adapter to `SCOUTERS` or a new grazer `kind` in `run_grazers()`. Keep the receipt/checkpoint contract unchanged so new formats remain replayable.
