# JANUS Universal Beetle — Wolfram public research, **no AppID**

**Scope:** Autonomous discovery of public Wolfram Research *metadata* on GitHub
and the official blog's intentionally syndicated RSS feed, to complement the
JANUS Ocean physics laboratory.

**Not a Wolfram|Alpha API bypass.** Wolfram|Alpha explicitly forbids automated
queries to its public website and requires a unique AppID for its developer
API. Beetle must **never** scrape wolframalpha.com, use proxy rotation or
unofficial endpoints, collect results for AI training, or impersonate a human.

Relevant terms:
- https://www.wolframalpha.com/termsofuse
- https://products.wolframalpha.com/api/termsofuse
- https://products.wolframalpha.com/api/documentation/

## Approved public sources

1. `https://blog.wolfram.com/feed/` — the publisher's official RSS feed.
   Save at most three science-related **titles, links and dates** per call;
   no article body, HTML, figures or copies of pages.
2. `https://api.github.com/repos/WolframResearch/QuantumFramework` —
   metadata of Wolfram Research's openly published MIT-licensed
   `QuantumFramework` repository. Verify owner, repository name, MIT SPDX
   license, public state, canonical URL on every fetch. Store repository
   link/description/update date only, never bulk clone its contents.

Both are public sources; fetching the GitHub metadata does not authenticate
to Wolfram Alpha. GitHub runner environment may have its ordinary GitHub
credentials for writing Beetle's **own** state, but Wolfram public fetches do
not send this token to Wolfram Research or Wolfram Alpha.

## Production integration

- `tools/wolfram_public_sources.py` is the strict parser and host/license
  allowlist.
- `tools/universal_beetle.py` has two additional `SCOUTERS` source kinds:
  `wolfram_public_feed` and `wolfram_public_repo`.
- `data/beetle/directions.json` defines
  `wolfram_official_open_quantum` (priority 91), with existing four
  research mirror lenses and destinations restricted to preapproved
  JANUS Meta Registry / Lapis repositories.
- Existing `universal-beetle-hourly.yml` schedule (three times/hour) is
  unchanged. Its existing bounded worker profile, request ceiling,
  deduplication, sharded receipts, GitHub `beetle-state` branch, routing
  checks and ACK gates remain active. This new lane uses no more than
  two outbound public requests **per selected mirror lane**.
- `tests/test_beetle_wolfram_public.py` executes with the existing
  Universal Beetle unit tests before any worker network activity.

Run manually using the existing standard workflow with `mode=scout` and
`direction=wolfram_official_open_quantum::FORWARD` *only when this lens
appears in the effective schedule*; otherwise let its existing scheduler
select the highest-priority direction automatically.

## What JANUS Ocean receives

Discovery candidate records include URLs, source identity, MIT licensing
where verified, research keywords, SHA-256 linked receipt provenance and
`DISCOVERY_CANDIDATE__NOT_VERIFIED__NO_PROOF_AUTHORITY`.

A discovery is **not** a new proven formula or a live Wolfram Alpha answer.
JANUS Ocean continues to run its Born, quantum-Zeno and non-signalling
calculations locally on CPU. When a Wolfram Alpha AppID eventually becomes
available, the separate manually opted-in scientific math API bridge may
verify specified expressions; no credentials are needed for this public
metadata scout.

No existing production model, private receiver, NAS container, Rowan witness
or historical experiment JSON is modified.
