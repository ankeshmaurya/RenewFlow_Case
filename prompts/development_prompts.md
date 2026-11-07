# RenewFlow development prompts

Prompts used with an AI coding assistant during development.

## Build the foundation

Build RenewFlow as a reconciliation and auto-approval engine for student renewals.
Use Python 3.11+ with FastAPI, plain HTML, CSS, vanilla JavaScript, JSON, CSV, and
Markdown. Model the five official tables with exact CSV column names, parse nulls,
IDs, amounts, and Asia/Kolkata timestamps, and expose health, loading, upload, summary,
and settings endpoints. Add the Data and Run page and a runnable README.

## Build the linking and checks

Implement pure Python engine functions for normalization, masked matching, typo
healing, duplicate suppression, payment checks, and identity checks. Match forms by
invoice ID or invoice link, then heal only one strong candidate. Preserve evidence and
reason codes in each invoice case.

## Build decisions and schedules

Complete amount, discount, batch, downstream, decision, schedule, SLA, metrics, and
self-test logic. Same-batch renewals are seat-neutral. Produce proposed schedule rows
for automatic approvals, export the result bundle, and add the CLI.

## Add optional language assistance

Add a server-side Gemini client with JSON schemas, a 15-second timeout, bounded
concurrency, input caching, and deterministic fallback behavior. Use it for teacher
remark intent, operational messages, and the morning brief. Rules remain authoritative
for money, identity, capacity, and decisions.

## Build the pipeline view

Build the pipeline page and record-chain drawer. Show invoice, form, booking, schedule,
checks, reason codes, owner, SLA, and proposed actions without changing engine behavior.

## Build the morning dashboard

Build the Ops Head dashboard with KPIs, funnel, ageing, exception Pareto, owner
workload, needs-action ordering, hours-saved assumptions, and the five-line brief.

## Build queues and exports

Build the auto-approved queue, exceptions queue, messages center, and CSV/JSON export
views. Include reason codes, named owners, SLA clocks, simulated sends, and template
fallback labels.

## Build process and self-test views

Build the process, shadow mode, self-test, and settings views. Explain as-is and
to-be routing, make the self-test deterministic, and preserve in-memory state limits.

## Harden and document

Add focused tests for matching, linking, golden results, decisions, proposed rows,
partial payment policy, parent replies, optional Gemini behavior, loader errors, API
endpoints, and scale. Write the README and operational documentation from the actual
sample run.

## Add workflow documentation

Add SQL views, an n8n workflow export, and a diagram as documentation artifacts only.
Keep live credentials out of the repository, preserve simulated sends, and state which
artifacts were not run against live systems.
