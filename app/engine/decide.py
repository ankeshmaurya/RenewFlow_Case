"""Decision, owner and recommended action. Precedence: BLOCKED > FLAGGED > FAST_TRACK > ALREADY_COMPLETE > AUTO_APPROVE."""
from __future__ import annotations

from ..models import Decision, Owner, Severity
from .codes import CATALOG, PRIORITY, action_of, owner_of
from .downstream import active_rows

PARTIAL_CODES = {"PAY_PARTIAL", "PAY_AMOUNT_MISMATCH"}


def decide(case, settings):
    fails = [c for c in case.checks if not c.passed]
    case.reason_codes = [c.code for c in fails]
    codes = set(case.reason_codes)
    blocks = [c for c in fails if c.severity == Severity.block]
    warns = [c for c in fails if c.severity == Severity.warn]
    rows = active_rows(case)
    completed = bool(case.booking and case.booking.request_status == "Completed" and rows)
    non_orphan = [w for w in warns if w.code != "LINK_ORPHAN_INVOICE"]
    case.provisional = False

    if blocks:
        case.decision = Decision.BLOCKED
    elif warns:
        if "LINK_ORPHAN_INVOICE" in codes and not non_orphan and case.reference is not None \
                and case.invoice.payment_status == "Paid" and (case.invoice.discount_amount or 0) == 0:
            case.decision = Decision.FAST_TRACK_PENDING_PARENT
        elif (settings.partial_payment_policy == "PROVISIONAL_PRO_RATA" and warns
              and all(w.code in PARTIAL_CODES for w in warns) and case.primary_form is not None
              and case.primary_form.continue_same_batch == "Yes"):
            case.decision = Decision.AUTO_APPROVE
            case.provisional = True
        else:
            case.decision = Decision.FLAGGED
    elif completed:
        case.decision = Decision.ALREADY_COMPLETE
    elif "BATCH_CHANGE_PARENT_SELECTION" in codes:
        case.decision = Decision.FAST_TRACK_PENDING_PARENT
    else:
        case.decision = Decision.AUTO_APPROVE

    case.owner = Owner.NONE
    if case.decision == Decision.FAST_TRACK_PENDING_PARENT:
        case.owner = Owner.PARENT
    elif case.decision in (Decision.FLAGGED, Decision.BLOCKED):
        for code in PRIORITY:
            if code in codes and CATALOG[code]["severity"] in ("warn", "block"):
                case.owner = owner_of(code)
                break

    steps = []
    for code in PRIORITY:
        if code in codes and CATALOG[code]["severity"] in ("warn", "block") or (code == "BATCH_CHANGE_PARENT_SELECTION" and code in codes):
            if case.decision == Decision.AUTO_APPROVE and case.provisional is False and code in PARTIAL_CODES:
                continue
            steps.append(action_of(code))
    if case.decision == Decision.AUTO_APPROVE:
        lead = "Approve and write the proposed schedule rows, then confirm with the parent."
        if case.provisional:
            lead = "Provisional approval: schedule only the paid share of sessions and remind the parent about installment 2."
        notes = [action_of(c) for c in case.reason_codes if CATALOG[c]["severity"] == "notice"]
        steps = [lead] + notes
    elif case.decision == Decision.ALREADY_COMPLETE:
        steps = ["Nothing to do." + (" " + action_of("SCHEDULE_COVERAGE_LOW") if "SCHEDULE_COVERAGE_LOW" in codes else "")]
    case.next_steps = steps
    case.recommended_action = steps[0] if steps else ""
    return case
