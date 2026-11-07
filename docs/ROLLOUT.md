# Rollout: 30-60-90 Days

## Gates
- Shadow to Assist: at least 95% agreement with human decisions and zero wrong schedules in the previous 2 weeks.
- Assist to Autopilot: same gate, plus 10% audit sample of auto-approvals clean for 2 weeks.

## Days 1 to 30: See and stabilise
- Run the engine in shadow mode on every renewal, read-only. Compare with human decisions daily.
- Publish baseline SLAs and the morning dashboard.
- Cheap fixes: invoice picker instead of a pasted link on the form, duplicate-submit guard, same-batch seat rule fix, nightly orphan sweep to Slack.
- Pilot with 10 volunteer teachers and 2 Ops agents.

## Days 31 to 60: Assist
- Payment webhook creates the renewal case. Teacher form pre-filled and optional.
- Engine proposes, Ops bulk-approves the green list in one click.
- WhatsApp confirmation to parents. Expand to 50 teachers.
- Exception Desk with named owners and timers.
- Target: touchless 40%, nothing paid and unscheduled for more than 24 hours.

## Days 61 to 90: Autopilot
- Green-path renewals write to booking and schedule tables automatically (same batch, clean only).
- Parent one-tap flow for batch change and for orphan invoices.
- Remove the teacher form for renewals, keep an optional note.
- All 200+ teachers. Target: touchless 65% or more, P90 payment-to-schedule under 4 hours.

## Change management
Cohort by subject and region, never a big bang. Kill switch. Freeze around term ends and festival peaks. Teachers get a 90-second WhatsApp video, a one-page guide and status pings. Ops moves from checking to owning exceptions. Parents only see faster confirmations.
