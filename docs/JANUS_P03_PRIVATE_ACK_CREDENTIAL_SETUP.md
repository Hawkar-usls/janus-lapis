# JANUS P0.3 — private SkinGPT ACK read credential

Status: **CONFIGURATION REQUIRED, NOT INSTALLED BY THIS PR**.

The sender already supports the secret JANUS_BEETLE_PRIVATE_ACK_READ_TOKEN
in Hawkar-usls/janus-lapis (.github/workflows/universal-beetle-hourly.yml).
The sender currently sees ACK_UNAVAILABLE, despite a direct authorized
receiver-side read matching the two sender batches. GitHub Actions and the
connected ChatGPT GitHub session are DIFFERENT security principals.

## Separate credential-owner action

1. Use a fine-grained PAT or preferably a short-lived GitHub App installation
   token with access to ONLY Hawkar-usls/SkinGPT and Contents: Read.
   No write, workflows, Actions, issues, admin or other repository permissions.
2. In Hawkar-usls/janus-lapis → Settings → Secrets and variables →
   Actions, create the repository secret named exactly
   JANUS_BEETLE_PRIVATE_ACK_READ_TOKEN. Never commit or log its value.
   Administrator/operator approval is mandatory.
3. Review the existing trusted main producer before enabling a live run.
   Its routing gate and post-route health stages already consume this secret.
   Do not forward it to fork PRs or untrusted feature branches.
4. Check a NEW trusted main-branch producer result. Only a private inbox
   batch ID + SHA match may change ACK_UNAVAILABLE to UP_TO_DATE.
   Preserve HOLD on conflicts, API errors or missing authorization.
5. Separately prove actual downstream consumption in Genesis. An inbox ACK
   is only durable inbox persistence, not model consumption.

The new readiness workflow runs under contents:read with NO token and
deliberately reports HOLD_READ_CREDENTIAL_NOT_CONFIGURED against the real
public sender queue. The unit tests cover a simulated valid/partial/conflict
ACK without printing private batch identity or SHA.

The connected GitHub tool cannot set or rotate repository secrets from this
session, so a repository credential administrator must perform step 2.
Do not reenable Terminal fork expansion or promote the P0.3 checkpoint.
