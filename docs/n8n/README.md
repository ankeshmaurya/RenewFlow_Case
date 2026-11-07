# n8n workflow notes

`renewflow_workflow.json` is an importable n8n workflow (Workflows, Import from file). It was generated and checked structurally (unique node names, every connection points at an existing node). It has not been run against a live n8n instance, so expect to set credentials and adjust node versions to your n8n release.

## What it does
1. Two triggers: a payment-captured webhook (Razorpay or Stripe, posted to `/webhook/renewflow-payment-captured`) and a 15-minute sweeper that catches missed webhooks.
2. The webhook path first upserts the invoice (idempotent on `gateway_payment_id`).
3. Both paths call the RenewFlow API: `POST /api/reconcile`, then `GET /api/results`, then split into one item per invoice.
4. A notification log check (`renewal_notifications`) stops the same message being sent every 15 minutes.
5. A Switch routes by decision:
   - AUTO_APPROVE: approve in the engine, insert schedule rows (this node is DISABLED, shadow mode), WhatsApp the parent confirmation.
   - FAST_TRACK_PENDING_PARENT: WhatsApp the one-tap choice.
   - FLAGGED and BLOCKED: post the drafted message to the owner's Slack channel.
6. An Error Trigger alerts Slack.

## Before enabling
- Set the `RENEWFLOW_URL` and `WHATSAPP_PHONE_NUMBER_ID` environment variables in n8n.
- Create credentials: MySQL, WhatsApp Business, Slack. The JSON intentionally contains
  `REPLACE_ME` credential IDs; replace them only in the n8n instance.
- Create the table:
  ```sql
  CREATE TABLE renewal_notifications (
    id BIGINT AUTO_INCREMENT PRIMARY KEY, invoice_id BIGINT NOT NULL, decision VARCHAR(40) NOT NULL,
    reason_codes VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL, KEY (invoice_id, decision));
  ```
- Real parent numbers come from the invoice row at send time. The RenewFlow app itself only ever sees masked values.
- The demo app reads CSV data. In production point the engine at the MySQL tables or run the SQL views in `docs/sql/` for the dashboard.
- Keep "Insert Schedule Rows" disabled until the rollout gate in `docs/ROLLOUT.md` is met.
