# LAPIS OCEAN BEETLE

`tools/ocean_beetle.py` is a resumable, chunked reader for very large remote HDF5 / MATLAB v7.3 scientific files. It was created for the JANUS Ocean Reader / KUSTO work so a 100–300+ MB `.mat` does not have to be downloaded as one object before inspection.

Core loop:

`DISCOVER -> BITE -> DIGEST -> RECEIPT -> CHECKPOINT -> NEXT`

## Why this exists

The UWA Channel Library stores real underwater-acoustic channel files as MATLAB v7.3/HDF5. Upstream UWA tooling documents `h_hat` as a large compound `{real, imag}` dataset whose physical HDF5 dimensions are reversed relative to logical MATLAB order. The Lapis Beetle therefore walks the on-disk time axis in bounded bites rather than materializing the whole tensor.

This is intentionally compatible with the KUSTO discipline used in `Hawkar-usls/Janus-Cosmos`, especially the `feature/kusto-frozen-point-morphology-gen4` lineage: freeze the target, probe a bounded piece, emit a receipt, preserve provenance, then continue. Lapis owns the ingestion utility; KUSTO may consume its receipts but its scientific verdict remains separate.

## Install

```bash
python -m pip install -r requirements-ocean-beetle.txt
```

## 1. Inspect only metadata

```bash
python tools/ocean_beetle.py inspect "https://.../blue_1.mat"
```

`inspect` walks the HDF5 object tree and reports shapes, dtypes, chunking, compression and UWA axis hints. It does not intentionally read the full dataset body.

## 2. Eat a UWA channel file in bounded bites

```bash
python tools/ocean_beetle.py uwa-channel "https://.../blue_1.mat" \
  --bite 64 \
  --include-tracking \
  --max-bites 4
```

The program reads at most four 64-frame bites, then exits cleanly. Run the same command again and it resumes from the checkpoint.

For each bite it records:

- exact source URL and remote fingerprint;
- `[t0,t1)` disk slice;
- magnitude/energy summary;
- receiver-wise energy;
- peak delay index per receiver;
- UWA parameters (`fs_delay`, `fs_time`, `fc`, version, `f_resamp` when present);
- matching `phi_hat`/`theta_hat` interval when `--include-tracking` is used;
- SHA-256-linked JSONL receipt chain.

By default only summaries are saved. Add `--save-npz` to persist the selected bite itself.

## 3. Eat a UWA noise file

```bash
python tools/ocean_beetle.py uwa-noise "https://.../blue_noise.mat" \
  --bite 256 \
  --max-bites 4
```

For UWA noise data, the expected logical tensor is `[M,M,K]` and the physical HDF5 order is `[K,M,M]`, so Beetle advances along `K`.

## Checkpoint layout

Runs are written under `.ocean_beetle/<run-id>/`:

```text
checkpoint.json
receipts.jsonl
chunks/              # only when --save-npz is requested
```

A checkpoint binds resume to source fingerprint, mode, dataset, axis, bite size and requested interval. If ETag/size/mtime changes, Beetle refuses an unsafe resume.

Each JSONL receipt contains `prev_receipt_sha256`, and its own canonical SHA-256 is written as `receipt_sha256`. That gives a simple append-only provenance chain over bites.

## Full-download guard

For HTTP(S), Beetle first sends a one-byte `Range: bytes=0-0` probe. A normal remote run is allowed only when the server replies `206 Partial Content`. This is deliberate: if range access is unavailable, a library might silently pull the entire file.

`--allow-full-download` disables this guard. Do not use it for large files unless a full download is explicitly acceptable.

## UWA-specific axis note

Upstream UWA browser tooling documents a MATLAB v7.3 storage quirk: logical `h_hat[delay, receiver, time]` is represented on disk as `[time, receiver, delay]`. Ocean Beetle follows the physical order for efficient hyperslab reads and reports both physical and logical shapes in receipts.

## JANUS / Ocean Reader boundary

The ingestion tool does **not** establish that the ocean is a literal server, that a natural global reader exists, or that any received physical state carries semantics. It only makes large measured datasets tractable for reproducible tests of:

`SOURCE -> OCEAN CHANNEL/STATE -> RECEIVER -> DECODER -> SOURCE_ESTIMATE`

The relevant distinction remains:

`RECEIVE != UNDERSTAND`

`OBSERVE != IDENTIFY`

`MORE EARS != RESTORED LOST PROVENANCE`

## Next raw-field gate

For the UWA Channel Library, use Beetle first on one channel/noise pair and preserve the receipt chain. Once the bounded reads are validated, those bites can feed the already frozen JANUS endpoints: 64-way source recovery, 16-way BA16 quotient-class recovery, erased-`j` leakage control, matched/mismatched channel-state decoding, receiver-array diversity, and packet `42` against all 63 controls.
