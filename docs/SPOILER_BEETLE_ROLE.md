# JANUS SPOILER — durable background research collector

`Universal Beetle` is the implementation of the **SPOILER_BACKGROUND_COLLECTOR**
role.  It does not autonomously change JANUS executable code, scientific
verdicts, proof gates, model weights, NAS devices, or permissions.

The currently deployed route already exists:

1. Demiurge publishes research attention/priorities; it does not grant truth.
2. Beetle Scout searches public metadata, filters, deduplicates and emits
   `DISCOVERY_CANDIDATE__NOT_VERIFIED__NO_PROOF_AUTHORITY`.
3. Approved Grazer reads bounded portions of large scientific data with
   source-bound receipts/checkpoints.
4. Context projector generates FORWARD / REVERSE / COUNTEREVIDENCE / CONTROL
   discovery contexts, not independent confirmations.
5. Router generates addressed, bounded `mirrors/<owner__repo>/latest.json`
   packets on `beetle-state`.
6. Each repository's existing `JANUS Beetle Memory Receiver` may ingest its
   addressed packet into its separate `beetle-memory` branch. The batch stays
   unverified and never automatically mutates the repository's `main` branch.

## Durability and recovery

The formerly monolithic `candidates.jsonl`, `contexts.jsonl`, and
`receipts.jsonl` are migrated into `*.parts/part-NNNNNN.jsonl` using the
byte-for-byte verified `tools/beetle_shard_store.py` mechanism.

- Every part is at most **16,000,000 bytes**, much smaller than GitHub's
  100 MiB hard file limit.
- `migration.json` contains the original SHA-256, exact byte and record counts,
  and per-part SHA-256 receipts. Legacy content is preserved in the earlier
  Git commit, and the working-tree copy is removed **only after validation**.
- Initial historical shards remain immutable; subsequent discoveries append
  to new shards, even when the last historical shard has spare space.
- `index.json` tracks current part sizes, counts and hashes; `latest_storage_health.json`
  summarizes the sealed run.
- Before any push, the worker fails if any state file reaches **80,000,000
  bytes**. This guard also covers non-JSONL data that does not yet have a
  compatible shard adapter; it never silently drops or truncates them.
- GitHub Actions runners may disappear after any cycle; the next one starts
  from the most recent *pushed* `beetle-state`. An interrupted/unpushed run
  must not be represented as durable progress.
- The origin-to-shards conversion never uses force-push or history rewriting.

## Verification

```bash
python -m unittest discover -s tests -p 'test_beetle_shard_store.py' -v
python tools/beetle_shard_store.py migrate --state-dir /path/to/state
python tools/beetle_shard_store.py seal --state-dir /path/to/state
```

The workflow self-tests storage, migration, idempotency, corruption rejection,
and compatibility with the Genesis receiver's exact batch schema before
running discovery. It then seals state prior to the state-branch commit.

No JANUS component should parse `contexts.jsonl` after the migration. Use
`beetle_shard_store.iter_lines(state, "contexts")` or read ordered `*.parts`.

**SPOILER FINDS AND ROUTES. JANUS VERIFIES. DISCOVERY IS NEVER A PROOF.**
