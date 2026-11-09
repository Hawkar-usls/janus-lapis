# JANUS Universal Beetle → official Wolfram research sources (no AppID)

This is a **small-scale, bounded research scout** in `janus-lapis`. It
does not scrape `wolframalpha.com`, bypass any developer portal, harvest
Wolfram Alpha's database, or retrieve paid Full Results API without authorization.

## Two independent no-login channels

1. **Public source discovery**: official `https://blog.wolfram.com/feed/`
   (article titles, links and dates only), plus official
   `WolframResearch/QuantumFramework` GitHub MIT-license metadata. At most
   one request per source per 24 hours; at most three metadata hits from RSS
   and one source repository entry. RSS bodies and repository contents are
   not copied or ingested into model training.
2. **Official keyless Wolfram Cloud MCP**:
   `https://agenttools.wolfram.com/mcp`.
   Wolfram confirms this is free without authentication for **limited
   personal use**, unlike the Wolfram|Alpha Results API.
   A source-bound one-shot client discovers only the `WolframAlpha` tool
   through MCP JSON-RPC and submits the fixed public Zeno formula
   `cos(pi/4)^4` once, only while the approved direction is active.
   The provider response is hashed **in memory**, never written to
   a candidates ledger or copied as training data. The receipt explicitly
   states `REMOTE_RESPONSE_RECEIVED_NOT_MATH_VERIFIED`.

A persisted candidate ID prevents any more calls to that case once
the first accepted receipt is stored in `beetle-state`. On error, cooldown
is **seven days**. There are at most four MCP transport POSTs for one
allowed case (initialize, notification, list, call) and no OAuth token,
AppID, cookie, or session data saved.

## Configuration and lifecycle

`data/beetle/directions.json` contains `wolfram_public_quantum`:
FORWARD, REVERSE, COUNTEREVIDENCE, CONTROL mirror lenses. The original
hourly Beetle workflow *already* runs every 20 minutes and rotates
directions with fairness. The new direction is discovered when scheduled,
with hard per-source daily gates even though workers may run often.
Do not add a separate polling job.

Candidates and SHA-chained receipts are stored only through the existing
`State.receipt`, `record_candidate` and shard storage contracts. Source
discoveries have no proof authority. They do not modify production Ocean
weights, Rowan credit budgets, private ACK gates or Metaregistry history.

The MCP tool response is NOT a verified mathematical equality. To establish
agreement between external Wolfram values and JANUS analytical calculations,
the dedicated authenticated or directly verified research council must
perform a separate predeclared numerical comparison.

## Tests

```sh
PYTHONPATH=tools python -m unittest discover -s tests -p test_wolfram_public_beetle.py -v
```

No live network is used by PR tests. On merge, existing
`universal-beetle-hourly.yml` persists the first approved MCP receipt
automatically if the source is selected and the remote service responds.
Whether the first connection succeeds can only be confirmed by that
run's `SCOUT_SOURCE_ERROR`, `WOLFRAM_MCP_ONE_SHOT_HOLD`, or
`WOLFRAM_MCP_KEYLESS_RECEIVED` receipts on the `beetle-state` branch.

Official references:
- https://support.wolfram.com/75237 — auth-free Cloud MCP
- https://www.wolfram.com/ai/mcp/cloud/ — limited personal-use boundary
- https://www.wolframalpha.com/termsofuse — no systematic harvesting/scraping
- https://github.com/WolframResearch/QuantumFramework — verified MIT source
