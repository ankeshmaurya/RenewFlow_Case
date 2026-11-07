# Reason Codes

Generated from `app/engine/codes.py`. Severity: block stops everything, warn needs a human decision, notice is handled automatically and reported, info is advisory.

Owner priority when several codes fail (first wins): PAY_NOT_CONFIRMED, ID_STUDENT_MISMATCH, PAY_PARTIAL, PAY_AMOUNT_MISMATCH, FEE_MISMATCH, DISCOUNT_UNAPPROVED, BATCH_CHANGE_NO_MATCH, BATCH_RECORD_MISMATCH, BATCH_SLOT_MISMATCH, ORPHAN_FORM, FORM_CONFLICT, REMARK_CONTRADICTION, LINK_ORPHAN_INVOICE, BATCH_CHANGE_PARENT_SELECTION.

## PAY_NOT_CONFIRMED

- Severity: block
- Owner: FINANCE_OPS
- Stage: PAYMENT
- Channel: slack + whatsapp
- SLA: 2 hours
- Meaning: The invoice is not Paid (failed, pending, or no gateway payment id). A teacher form may still exist.
- Fix: Re-poll the gateway by order id. If captured, update the invoice and re-run. If not, tell the parent we are checking and not to pay again if money was debited.
- Recommended action shown to the owner: Re-check the payment with the gateway before anything else. Tell the parent not to pay again; UPI payments can settle late.

## PAY_PARTIAL

- Severity: warn
- Owner: FINANCE_OPS
- Stage: PAYMENT
- Channel: slack
- SLA: 4 hours
- Meaning: Only part of the fee has been collected (for example installment 1 of 2).
- Fix: Hold full scheduling, or schedule pro-rata sessions if the Head of Ops enables that policy. Remind the parent about installment 2.
- Recommended action shown to the owner: Confirm the installment plan. Schedule only the paid share if policy allows; otherwise hold and remind the parent.

## PAY_AMOUNT_MISMATCH

- Severity: warn
- Owner: FINANCE_OPS
- Stage: AMOUNT
- Channel: slack + whatsapp
- SLA: 4 hours
- Meaning: The amount the teacher typed on the form is not the net amount collected on the invoice.
- Fix: Trust the invoice. Ask the teacher to correct the form.
- Recommended action shown to the owner: Use the invoice net amount as the truth and ask the teacher to correct the form.

## FEE_MISMATCH

- Severity: warn
- Owner: FINANCE_OPS
- Stage: AMOUNT
- Channel: slack
- SLA: 4 hours
- Meaning: The invoice amount is not the standard fee for the sessions bought.
- Fix: Check whether the invoice was created with a wrong price or a custom plan.
- Recommended action shown to the owner: Verify the invoice price against the standard fee before scheduling.

## DISCOUNT_UNAPPROVED

- Severity: warn
- Owner: OPS_LEAD
- Stage: AMOUNT
- Channel: slack
- SLA: 4 hours
- Meaning: The invoice carries a discount but the schema has no approver or approval reference.
- Fix: Ops Lead approves or rejects and records the approval reference. Add an approver field to invoices.
- Recommended action shown to the owner: Ops Lead to approve or reject the discount and record an approval reference.

## LINK_ORPHAN_INVOICE

- Severity: warn
- Owner: PARENT
- Stage: LINK
- Channel: whatsapp
- SLA: 4 hours
- Meaning: Payment is confirmed but no teacher form exists, so nothing downstream will start.
- Fix: Send the parent a one-tap choice (continue same batch or change). Teacher gets an FYI, not a task. Escalate to an Ops agent after 4 hours.
- Recommended action shown to the owner: Send the parent the one-tap WhatsApp choice. Escalate to an Ops agent if there is no reply in 4 hours.

## LINK_ID_TYPO_HEALED

- Severity: notice
- Owner: NONE
- Stage: LINK
- Channel: whatsapp (teacher FYI)
- SLA: FYI only
- Meaning: The form pointed at an invoice id that does not exist. One invoice matched on user, student, amount and a near-identical id.
- Fix: Nothing to do. Teacher gets a gentle note. Product fix: replace the pasted id with an invoice picker.
- Recommended action shown to the owner: Form linked automatically. Send the teacher an FYI.

## LINK_DUPLICATE_FORM

- Severity: notice
- Owner: NONE
- Stage: LINK
- Channel: whatsapp (teacher FYI)
- SLA: FYI only
- Meaning: The teacher submitted the same renewal more than once.
- Fix: Earliest form kept, later copies suppressed. Product fix: duplicate-submit guard.
- Recommended action shown to the owner: Duplicate suppressed. Send the teacher an FYI.

## ORPHAN_FORM

- Severity: warn
- Owner: DATA_DESK
- Stage: LINK
- Channel: slack
- SLA: 8 hours
- Meaning: The form points at an invoice id that does not exist and no single invoice matches well enough to heal it.
- Fix: Data Desk finds the payment or contacts the teacher.
- Recommended action shown to the owner: Find the real invoice for this form or contact the teacher.

## FORM_CONFLICT

- Severity: warn
- Owner: DATA_DESK
- Stage: LINK
- Channel: slack
- SLA: 8 hours
- Meaning: More than one form exists for the invoice and they disagree on batch, amount or schedule.
- Fix: Ask the teacher which form is correct.
- Recommended action shown to the owner: Ask the teacher which of the conflicting forms is correct.

## ID_PAYER_MISMATCH

- Severity: notice
- Owner: NONE
- Stage: IDENTITY
- Channel: whatsapp (parent notice)
- SLA: FYI only
- Meaning: Name, mobile or email on the invoice differ from the registered parent. The payment link is bound to the student id, so this is not blocking.
- Fix: Approve, and notify the registered parent in case the payment is unexpected.
- Recommended action shown to the owner: Approve and notify the registered parent of the payment.

## ID_STUDENT_MISMATCH

- Severity: block
- Owner: DATA_DESK
- Stage: IDENTITY
- Channel: slack
- SLA: 4 hours
- Meaning: Invoice, form and student record do not agree on user id or student id, or there is no active student record.
- Fix: Data Desk checks which record is wrong before anything is scheduled.
- Recommended action shown to the owner: Do not schedule. Data Desk to verify student and user ids across the records.

## DATA_TEXT_NORMALIZED

- Severity: info
- Owner: NONE
- Stage: IDENTITY
- Channel: none
- SLA: FYI only
- Meaning: Some text contained look-alike characters (for example Cyrillic letters) that defeat plain string matching.
- Fix: Normalized automatically. Worth cleaning at source.
- Recommended action shown to the owner: No action. Text normalized before matching.

## BATCH_CHANGE_NO_MATCH

- Severity: warn
- Owner: SCHEDULING_DESK
- Stage: BATCH
- Channel: slack + whatsapp
- SLA: 24 hours
- Meaning: The parent wants a different batch but no batch of the same class has the requested days and time with a free seat.
- Fix: Scheduling Desk opens a batch or offers the closest alternatives to the parent.
- Recommended action shown to the owner: Find or open a matching batch, or offer the parent the closest alternatives.

## BATCH_CHANGE_PARENT_SELECTION

- Severity: notice
- Owner: PARENT
- Stage: BATCH
- Channel: whatsapp
- SLA: 24 hours
- Meaning: One or more batches match the requested days and time with seats free. The parent picks one.
- Fix: Send the options by WhatsApp. The parent's choice creates the schedule.
- Recommended action shown to the owner: Send the parent the matching batch options.

## BATCH_RECORD_MISMATCH

- Severity: warn
- Owner: SCHEDULING_DESK
- Stage: BATCH
- Channel: slack
- SLA: 8 hours
- Meaning: Batch, class or educator on the form do not match the student's active record.
- Fix: Check which is current before scheduling.
- Recommended action shown to the owner: Confirm the student's current batch, class and educator.

## BATCH_SLOT_MISMATCH

- Severity: warn
- Owner: SCHEDULING_DESK
- Stage: BATCH
- Channel: slack
- SLA: 8 hours
- Meaning: The form says same batch but the days or time differ from that batch.
- Fix: Ask whether the family wants a batch change.
- Recommended action shown to the owner: Clarify with the teacher or parent whether this is really a same-batch renewal.

## BATCH_FULL_FALSE_POSITIVE

- Severity: notice
- Owner: NONE
- Stage: BATCH
- Channel: slack (ops FYI)
- SLA: FYI only
- Meaning: A same-batch renewal was failed as 'batch full', but the student already holds a seat in that batch.
- Fix: Renewal is seat-neutral. Allocated automatically. Product fix: exclude the renewing student from the capacity count.
- Recommended action shown to the owner: Allocate in the same batch. No new seat is needed.

## BOOKING_STUCK_RESCUED

- Severity: notice
- Owner: NONE
- Stage: DOWNSTREAM
- Channel: slack (ops FYI)
- SLA: FYI only
- Meaning: A booking request sat unallocated beyond the threshold although the batch was valid and the case clean.
- Fix: Allocated and scheduled automatically.
- Recommended action shown to the owner: Allocate the batch and create the schedule rows.

## SCHEDULE_COVERAGE_LOW

- Severity: info
- Owner: NONE
- Stage: DOWNSTREAM
- Channel: none
- SLA: FYI only
- Meaning: A completed booking has fewer scheduled sessions than the number purchased.
- Fix: Check whether sessions are scheduled on a rolling basis or were missed.
- Recommended action shown to the owner: Verify the remaining sessions will be scheduled.

## REMARK_CONTRADICTION

- Severity: warn
- Owner: DATA_DESK
- Stage: REMARKS
- Channel: whatsapp (teacher)
- SLA: 8 hours
- Meaning: The free-text remark says one thing and the structured fields say another.
- Fix: Ask the teacher to confirm and correct the form.
- Recommended action shown to the owner: Ask the teacher which is correct: the remark or the form fields.
