# Audit trail

Every run writes a receipt here: what was proposed, what the verifier accepted,
what actually changed, and under which autonomy level.

- `receipt-<timestamp>-<autonomy>.json` — the machine record, append-only
- `receipt.html` — the same run rendered for a human, no CDN required

`git log` over this directory is the governance record. Deleting a receipt
should be a reviewable decision, not a cleanup.
