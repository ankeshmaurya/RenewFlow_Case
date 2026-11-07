# RenewFlow case analysis

Student renewal to class scheduling pipeline. The figures below use the sample data at
an as-of time of 2026-11-04 09:00 IST.

## What the data shows

The sample has 13 invoices, 12 payment-confirmed invoices, 1 failed invoice, 12
teacher forms, 4 booking requests, 2 schedule rows, and 13 reference rows. Only 1 of
13 renewals is fully scheduled, with 2 of 24 sessions on the calendar. Rs 126,850 is
paid on invoices that are not scheduled.

### Per-invoice ground truth

| Invoice | Ground truth |
|---|---|
| 84901 | Complete. Form 3301, booking 5501, and schedule rows 990101 and 990102. Advisory: 24 sessions bought, 2 scheduled. |
| 84902 | Paid and approved. Booking 5502 is stuck in `Pending_Batch_Allocation` for about 64 hours. Same-batch renewal should proceed. |
| 84903 | Paid. Form 3303 has been pending for 47.5 hours. Clean same-batch renewal; the delay is the Ops queue. |
| 84904 | Paid by a different mobile, email, and parent name. Student and user IDs match; the payer difference is not a risk. |
| 84905 | Booking 5505 is marked `Failed_Batch_Full` although the student already holds a seat in the batch. This is a false capacity failure. |
| 84906 | Paid via Stripe from the GCC. No teacher form exists; the case has been orphaned for 41 hours. |
| 84907 | Paid with a 20% discount: Rs 9,500 list and Rs 7,600 net. A retention scholarship is mentioned, but the schema has no approval trail. |
| 84908 | Forms 3308 and 3309 are duplicate submissions five minutes apart. The underlying renewal is otherwise clean. |
| 84909 | Partially paid: installment 1 of 2, Rs 5,250 collected of Rs 10,500. The form says Rs 10,500 and 24 sessions. |
| 84910 | Paid with no teacher form. The case has been orphaned for about 22 hours. |
| 84911 | Payment is failed with no gateway payment ID, but a teacher form was filed after a parent showed a UPI processing screenshot. |
| 84912 | Paid, batch change requested for a weekend Gita class, and no matching available batch exists for class 301 at that slot. |
| 84913 | Form 3313 has invoice ID 84931 instead of 84913. The parent name also contains two Cyrillic lookalikes; normalization and evidence-based healing recover the link. |

### Headline insights

1. Only 1 of 13 renewals is scheduled, and it has 2 of 24 sessions on the calendar.
   Rs 126,850 is collected on renewals that are not scheduled.
2. Teachers are not the bottleneck. Payment-to-form lag is 15 to 50 minutes, with a
   median of about 27 minutes. Eight of 12 forms are pending after 16 to 48 hours.
3. The Ops queue has no reliable ordering or ownership. Form 3303 waited 47.5 hours
   while a later form was approved.
4. Approval alone is not progress: 3 of 4 human approvals stalled at the next table.
5. `Batch full` is a logic error for a same-batch renewal when the student already
   holds the seat.
6. The teacher form re-types user, student, class, and educator data already present
   on the invoice. Retyping creates typos, duplicates, and orphan links.

## Failure mode catalog

- **F1 Orphaned invoice:** paid, but no teacher form; 84906 and 84910. The parent has
  paid and the case is silent.
- **F2 Invoice ID typo:** form 3313 uses 84931 for invoice 84913. An exact join loses
  the case.
- **F3 Duplicate submission:** forms 3308 and 3309 create a double-booking risk.
- **F4 Form on failed payment:** form 3311 exists for failed invoice 84911. Re-poll
  before asking the parent to pay again.
- **F5 Partial payment treated as full:** form 3310 promises 24 sessions for half the
  invoice value.
- **F6 Untracked discount:** form 3307 records a 20% discount without an approver.
- **F7 Payer or text mismatch:** payer details can differ from the registered parent;
  masked values can also contain lookalike characters.
- **F8 Unordered pending queue:** form 3303 waited while a later form was approved.
- **F9 Approval without validation:** form 3312 was approved without a batch decision.
- **F10 Weekend coverage gap:** Sunday activity indicates dependence on individuals,
  not a defined rota.
- **F11 Black-hole allocation:** booking 5502 remains unallocated despite a valid
  same-batch renewal.
- **F12 False batch-full:** booking 5505 rejects a student who already occupies a
  seat.
- **F13 Batch change without availability:** booking 5512 has no batch for the
  requested class and slot.
- **F14 Silent coverage gap:** booking 5501 has only 2 of 24 sessions scheduled.
- **F15 No parent-facing status:** parents learn about a problem only when a class
  does not happen.
- **F16 Gateway and currency friction:** GCC and US parents use INR through Stripe.
  This should be tracked, not treated as a renewal blocker.

## Metrics and SLAs

The primary metric is Payment-to-Schedule Turnaround (PST): payment captured to the
renewed term's sessions existing in `class_schedule_bookings`.

| Measure | Baseline in sample | Target |
|---|---:|---:|
| Fully scheduled renewals | 1 of 13 | P90 under 4 hours for clean renewals |
| Touchless approvals | 6 of 13 (46%) | 60% after removing the form |
| Parent-only follow-up | 2 of 13 (15%) | Resolve within 4 hours |
| Paid but unscheduled value | Rs 126,850 | Zero older than 24 hours |
| Forms pending over threshold | 8 of 12 | Under 2 hours while the form remains |
| Approval turnaround | 0.75 to 2.5 hours for approved forms | Under 1 hour now; under 15 minutes automated |
| Payment-to-form turnaround | Median about 27 minutes | 2 hours now; zero when the form is optional |
| Booking allocation | 1 of 4 completed | Under 30 minutes after a clean decision |
| Schedule coverage | 2 of 24 sessions for the complete case | All proposed sessions have a schedule row |

Exception cases target completion within 24 hours and never later than the last
session of the expiring term. The dashboard exposes the 12-hour ageing threshold,
owner, oldest item, and value-times-age priority.

## Redesigned workflow

Payment capture is the trigger and the source of truth. An idempotent webhook upserts
the invoice, a renewal case joins the reference data, and deterministic rules check
payment, identity, amount, linkage, capacity, and downstream state. A 15-minute
sweeper catches missed webhooks and ageing cases.

- **Green:** clean, same-batch renewals are approved automatically and produce
  proposed schedule rows. The parent receives a confirmation and the teacher receives
  an FYI.
- **Orange:** paid renewals without a teacher form receive a one-tap parent choice:
  continue the same batch or request a change.
- **Red:** discounts, partial payments, unavailable batch changes, and other
  exceptions go to a named owner with a timer and a drafted message.
- **Blocked:** failed or unconfirmed payments are re-polled and held. The parent is
  told not to pay again when a debit may be pending.

Rules decide money, IDs, capacity, and SLA clocks. Gemini is optional and handles
remark intent, message wording, and the morning brief. Template and keyword fallbacks
remain available. Sends are simulated, state is in memory, and the SQL and n8n
artifacts were not run on live systems.

### Why the teacher form is questioned

The invoice already contains user, student, class, and educator information. The form
adds intent and remarks, but retyping known fields introduces the exact failures found
in the sample. The proposed replacement captures parent intent directly, defaults to
same batch, keeps an optional teacher note, and retains teacher attribution. A
pre-filled form is a transitional control while the parent choice flow is validated.

## Hours-saved model (assumptions)

These are planning assumptions, not measured production results:

- 400 renewals per week.
- Current Ops handling is 18 minutes per renewal: 6 minutes to verify, 3 to approve,
  4 to allocate, and 5 to chase. Teacher form time is 4 minutes.
- Target mix is 60% touchless at 0.5 minutes, 25% parent one-tap at 2 minutes, and
  15% exceptions at 15 minutes. The weighted average is 3.05 minutes.
- The model moves Ops effort from 120 hours per week to about 20 hours, a modelled
  saving of roughly 100 hours. Teacher form effort falls by about 27 hours per week.
- The sample's 46% touchless rate is observed in this run; the 60% target is an
  assumption for the form-removal scenario.

## 30-60-90 plan

### Days 1-30: see and stabilise

Run read-only shadow comparisons, publish the baseline SLAs and morning dashboard,
add an invoice picker and duplicate-submit guard, correct same-batch capacity logic,
and sweep orphan cases to Slack. Pilot with 10 volunteer teachers and 2 Ops agents.

### Days 31-60: assist

Create cases from payment webhooks, make the form pre-filled and optional, let Ops
bulk-approve the green list, send parent confirmations, and establish an Exception
Desk with named owners and timers. Target 40% touchless and no paid invoice
unscheduled for more than 24 hours.

### Days 61-90: controlled autopilot

Write clean same-batch green-path renewals to booking and schedule tables, add
one-tap batch-change and orphan flows, remove the renewal form while retaining an
optional note, and expand to all teachers and Ops. Target 65% touchless and P90
payment-to-schedule under 4 hours.

Every gate requires at least 95% agreement with human decisions, zero wrong schedules
in the previous two weeks, a kill switch, and a 10% audit sample during the first
two weeks of automatic approvals. Cohorts should be rolled out by subject and region,
with freezes around term ends and festival peaks.

## Open policy questions

1. Should partial payments remain held, or should a paid share receive provisional
   sessions? The current default is `HOLD`.
2. Who can approve a discount, and where should that approval be recorded?
3. Should parent one-tap choices default to the current batch or require explicit
   confirmation?
4. What is the live source for available batches and class schedule IDs?
5. What is the after-hours escalation rota and the maximum response time for a failed
   payment with a possible pending debit?
6. Which production system should own the audit log and idempotency key?
