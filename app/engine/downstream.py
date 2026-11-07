"""Downstream audit: stuck bookings and schedule coverage."""
from ..models import CaseCheck, Severity
from ..timeutil import hours_between

STUCK_STATUSES = {"Pending_Batch_Allocation", "Failed_Batch_Full", "Awaiting_Parent_Batch_Selection"}


def active_rows(case):
    return [r for r in case.schedule_rows if (r.is_cancelled or "No") != "Yes"]


def downstream_checks(case, settings, as_of):
    b = case.booking
    if b is None:
        return
    rows = active_rows(case)
    issues = [c for c in case.checks if not c.passed and c.severity in (Severity.warn, Severity.block)]
    if b.request_status == "Pending_Batch_Allocation" and not rows:
        age = hours_between(b.created_at, as_of) or 0
        stuck = age > settings.stuck_threshold_hours
        rescue = stuck and not issues and case.primary_form is not None and case.primary_form.continue_same_batch == "Yes"
        case.add(CaseCheck(code="BOOKING_STUCK_RESCUED", name="Booking request is not stuck unallocated", stage="DOWNSTREAM",
                           severity=Severity.notice, passed=not rescue,
                           detail=(f"Booking {b.id} has been Pending_Batch_Allocation for {age:.1f}h although batch "
                                   f"{b.classbatch_id} is valid and the case is clean.") if rescue else f"Pending for {age:.1f}h."))
        if rescue:
            case.healed_actions.append(f"Rescued booking {b.id}: stuck {age:.1f}h, allocating in batch {b.classbatch_id}.")
    if b.request_status == "Completed":
        want = b.sessions_count or settings.sessions_default
        low = len(rows) < want
        case.add(CaseCheck(code="SCHEDULE_COVERAGE_LOW", name="Scheduled sessions cover the sessions bought", stage="DOWNSTREAM",
                           severity=Severity.info, passed=not low,
                           detail=f"{len(rows)} of {want} sessions are scheduled." if low else f"{len(rows)} of {want} scheduled."))
