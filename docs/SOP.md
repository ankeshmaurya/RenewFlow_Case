# Standard Operating Procedures

## 1. Exception Desk daily routine (15 minutes at 9:00)
1. Open the Dashboard. Read the morning brief and the "Needs action now" list.
2. Open Exceptions. For each owner queue take the oldest item first.
3. Read the recommended action, send or edit the drafted message, resolve, add a resolution note.
4. Re-run reconciliation. Resolved cases leave the queue.
5. Anything Breached at end of day is escalated to the Ops Lead.

## 2. Reason code playbook
See `REASON_CODES.md` for each code, its owner, the fix and the message to send.

## 3. Partial payment and discount policy (to be confirmed by the Head of Ops)
- Discounts: the Ops Lead approves or rejects in #ops-approvals and records an approval reference in the resolution note. Recommended product change: add `discount_approved_by` and `discount_reason` to invoices.
- Partial payments: default is hold and flag. If the Head of Ops enables provisional pro-rata scheduling, sessions equal to the paid share are scheduled and the parent is reminded about installment 2.

## 4. Weekend and after-hours rota
- A named on-call agent covers Blocked and Waiting-on-parent items on Saturdays, Sundays and holidays.
- The 15-minute sweeper handles everything else. Friday evening payments for Saturday batches are the highest-risk window.

## 5. Teacher guide
- You no longer need to fill a renewal form for a normal renewal. After the parent pays you will get a WhatsApp confirmation with the schedule.
- You still pitch the renewal and your attribution is unchanged (your educator id is on the invoice).
- If a batch change is needed the parent gets a one-tap message.
- Please do not submit forms for payments that are not confirmed.

## 6. Kill switch and rollback
- Set the mode back to manual: all renewals return to the old four-table path with no data loss.
- Auto-written schedule rows carry `booking_type = Regular_Renewal` and the engine's id in `allocated_by`, so they can be found and reversed in one query.
- Roll back if agreement with human decisions falls below 95% or any wrong schedule is found.
