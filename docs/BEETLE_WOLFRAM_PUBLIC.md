# JANUS Universal Beetle — Wolfram public research, **no AppID**

**Scope:** Autonomous discovery of public Wolfram Research *metadata* on GitHub
and the official blog's intentionally syndicated RSS feed, to complement the
JANUS Ocean physics laboratory.

**Not a Wolfram|Alpha API bypass.** Wolfram|Alpha explicitly forbids automated
queries to its public website and requires a unique AppID for its conventional
Full Results API. Wolfram separately publishes a **free anonymous Cloud MCP**
endpoint for limited personal use. Beetle uses that distinct official MCP
route for one approved science query only. It must never scrape the website,
rotate proxy identities, harvest result corpora or train models on those results.

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

3. `https://agenttools.wolfram.com/mcp` — the *official Wolfram Cloud MCP*
   one-shot stateless service for small-scale personal use. Exactly one
   preapproved `zeno_n2_analytic` check is allowed, via MCP protocol,
   never through a scraped website or Wolfram Full Results API. Four bounded
   protocol requests at most (initialize, initialized, tools/list, tools/call),
   and **no raw Wolfram response content** is retained. A successful
   same-query candidate is deduplicated forever; network errors trigger
   a 7-day cooldown, not repeated quota consumption.

These are public sources; no request authenticates to Wolfram Alpha. GitHub runner environment may have its ordinary GitHub
credentials for writing Beetle's **own** state, but Wolfram public fetches do
not send this token to Wolfram Research or Wolfram Alpha.

## Production integration

- `tools/wolfram_public_sources.py` is the strict parser and host/license
  allowlist.
- `tools/universal_beetle.py` has three additional `SCOUTERS` source kinds:
  `wolfram_public_feed`, `wolfram_public_repo`, and `wolfram_mcp_once`.
  `tools/wolfram_mcp_one_shot.py` is the separate read-only MCP adapter.
- `data/beetle/directions.json` defines
  `wolfram_official_open_quantum` (priority 91), with existing four
  research mirror lenses and destinations restricted to preapproved
  JANUS Meta Registry / Lapis repositories.
- Existing `universal-beetle-hourly.yml` schedule (three times/hour) is
  unchanged. Its existing bounded worker profile, request ceiling,
  deduplication, sharded receipts, GitHub `beetle-state` branch, routing
  checks and ACK gates remain active. This new lane uses no more than
  two RSS/GitHub requests **per selected mirror lane**; MCP is a single
  separately throttled case and never a repeating 20-minute query.
- `tests/test_beetle_wolfram_public.py` and
  `tests/test_beetle_wolfram_mcp.py` execute with existing Beetle tests
  before any worker network activity.

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

## Official no-AppID MCP endpoint

Wolfram Support confirms `https://agenttools.wolfram.com/mcp` is free and
requires **no authentication**: https://support.wolfram.com/75237.
Wolfram's product description restricts this to **small-scale and casual
usage**: https://www.wolfram.com/ai/mcp/cloud/.

The Wolfram Alpha website itself still forbids robotic page scraping, and
its conventional Full Results API continues to require an AppID. These are
three distinct interfaces. An MCP receipt proves only that the provider
returned content to a specific fixed computation request; it does not yet
validate the provider's numerical answer, establish quantum hardware, or
provide a retrocausal signal. An external Wolfram MCP answer must never
be included in automated model training without specific permission.
