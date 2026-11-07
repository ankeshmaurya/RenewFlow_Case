# Architecture

```
Browser (HTML, CSS, vanilla JavaScript ES modules, Chart.js)
        |  JSON over HTTP
FastAPI (app/main.py)  <->  in-memory Store (app/store.py)
        |
Engine (app/engine, pure Python, no web or LLM imports)
        |                          |
CSV loader (app/loader.py)    Gemini layer (app/llm) with template fallback
```

## Engine pipeline

`app/engine/pipeline.py` runs two stages.

Stage 1 (`run_stage1`): link, payment, identity.
1. `link.py` matches forms to invoices by invoice id, then by the invoice number inside the link, then heals typos by scoring candidates (same user 0.30, same student 0.30, same educator 0.10, same amount 0.15, id within 2 edits 0.15). A heal needs exactly one candidate scoring 0.9 or more, so a near-identical id is always part of the evidence. Identical forms within 24 hours collapse to the earliest, differing forms raise FORM_CONFLICT. All lookups use dictionaries, so the stage is linear (a 5,000-invoice test runs in about 2 seconds).
2. `payment.py` is the gate: Paid with a gateway id and paid_at, otherwise PAY_PARTIAL or PAY_NOT_CONFIRMED.
3. `identity.py` requires user and student ids to agree across invoice, form and student record. Payer name, mobile and email differences are soft (the payment link is bound to the student id). Look-alike characters are folded (Cyrillic and Greek) before matching, using masked comparison that compares visible prefixes and suffixes.

Stage 2: amount, batch, remarks, downstream, decide, schedule, SLA, metrics.
- `amount.py`: form amount versus invoice net, invoice amount versus standard fee, discount needs approval.
- `batch.py`: same-batch renewals are seat-neutral. Batch changes search the same class for matching days, time and free seats, and list nearby alternatives with a caveat when the class differs.
- `remarks.py`: keyword intent extraction and contradiction rules. Gemini can supply the intents instead.
- `downstream.py`: stuck bookings and schedule coverage.
- `decide.py`: precedence BLOCKED, FLAGGED, FAST_TRACK_PENDING_PARENT, ALREADY_COMPLETE, AUTO_APPROVE. Owner comes from the priority list in `codes.py`.
- `schedule.py`: proposes class_schedule_bookings rows (24 sessions by default, 50 minutes each, starting after the as-of date).
- `sla.py`, `metrics.py`: clocks, tracker states, dashboard numbers.

## Where AI is used

`app/llm` calls Gemini through the `google-genai` SDK, server-side only. The key is read from `GEMINI_API_KEY`, the model from `GEMINI_MODEL` (default alias `gemini-flash-latest`).
- Remark intent extraction (`remarks.py`), cross-checked by deterministic rules.
- Message rewriting (`messages.py`): the template text is always the base. A Gemini version is accepted only if every number, date and id in the base appears in the output and WhatsApp length stays within 600 characters.
- Morning brief (`brief.py`): same number guard.
Only masked names and the minimum facts are sent. Calls have a 15 second timeout, at most 3 run at once, and results are cached by input hash. Any failure falls back to templates and keyword rules, and the UI marks each item AI or Template.

The self-test (`/api/selftest`) always runs deterministically with default settings so Gemini cannot change it.

## State

Everything lives in memory per process (approvals, parent replies, messages, audit log). Restarting clears it. A production version would write decisions to a staging table first.

## Design decisions worth knowing

- `classschedule_id` in proposed rows is left empty and replaced by a lookup key (`classbatch_id|class_date|start_time`) because the live class schedule table is not in the dataset. The CSV export keeps the table's columns in order and adds one helper column for that key.
- Parent replies are simulated by creating a virtual form (id 9,000,000 + invoice id) marked `source = parent_reply`, so the same engine path handles it.
- The self-test golden file is `data/sample/expected_results.json`.
