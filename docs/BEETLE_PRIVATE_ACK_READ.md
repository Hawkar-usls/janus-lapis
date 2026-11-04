# Beetle: optional private SkinGPT inbox ACK read (least privilege)

Purpose: distinguish a truly missing ACK from an ACK in a private GitHub repository that public raw.githubusercontent.com cannot read. The public sender must **not** silently accept an unreadable ACK.

## Observed 2026-11-04

A read through the owner's authorized GitHub connection confirmed the SkinGPT receiver's private `beetle-memory/data/beetle-inbox/ACK.json` has sequence 1 and matches the sender's immutable one-entry batch queue by batch ID and SHA-256. The public sender still reports ACK_UNAVAILABLE because anonymous raw HTTP returns 404 on private repositories. Inbox ACK does not prove model/runtime consumption.

## Opt-in setup

Set a repository secret named `JANUS_BEETLE_PRIVATE_ACK_READ_TOKEN` in **Hawkar-usls/janus-lapis**. The recommended credential is a short-lived GitHub App installation token, or a fine-grained personal access token restricted **only** to `Hawkar-usls/SkinGPT`, with **Contents: Read**. No issue, actions, workflow, webhook, administrative or write permissions are required. Never put credentials into JSON, a source file, PR, log, or public issue.

If no credential is configured, the existing behavior remains: `ACK_UNAVAILABLE` / unknown. The workflow does not invent proof or increase the route budget.

A secret is available only to the scheduled / manual main-branch producer; no PR workflow receives the private ACK token. It is passed solely to the two read-only phases: pre-route backpressure gate and post-route health check. Code only requests the exact allowlisted SkinGPT ACK path via the GitHub Contents API, disallows redirects, requires base64 file metadata with bounded byte length, then independently verifies the ACK against the sender's immutable batch ID and SHA-256.

Public sender health omits private ACK timestamps and last batch fields; the private receipt body is never persisted in public artifacts. The public count may change from 1 pending to 0 after successful validation; that reports durable inbox delivery **only**.

### Safety & acceptance

- Private API 401/403/404, transport failure, invalid base64, missing token => unchanged `ACK_UNAVAILABLE`; no false clearance.
- Mismatched ACK batch, SHA-256, schema, sequence or target repository => `ACK_CONFLICT`.
- Verified inbox ACK => `UP_TO_DATE` with `SCOPED_PRIVATE_READ_INBOX_ONLY`, not CONSUMED or AUTONOMY_FULL.
- Nothing accesses other private repositories or reads content outside the fixed ACK.
- The operator or an appropriately scoped secret-management administrator must configure the credential. The connected ChatGPT GitHub app does not automatically grant the GitHub Actions worker that credential.

Offline test: `python -m unittest discover -s tests -p 'test_beetle_private_ack.py' -v`.
