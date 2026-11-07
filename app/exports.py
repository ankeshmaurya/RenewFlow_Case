"""CSV exports shared by the API and the command line tool."""
from __future__ import annotations

import csv
import io

from .models import Decision

SCHEDULE_COLUMNS = ["id", "bookingrequest_id", "invoice_id", "classschedule_id", "classbatch_id", "class_id", "user_id", "student_id",
                    "educator_id", "class_date", "start_time", "end_time", "booking_type", "is_cancelled", "attended_class",
                    "created_at", "updated_at", "deleted_at"]
OPEN = (Decision.FLAGGED, Decision.BLOCKED, Decision.FAST_TRACK_PENDING_PARENT)


def auto_approved_csv(cases) -> str:
    """The class_schedule_bookings columns in order, plus one helper column with the lookup key for classschedule_id."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(SCHEDULE_COLUMNS + ["classschedule_lookup_key"])
    for c in cases:
        if c.decision != Decision.AUTO_APPROVE:
            continue
        for r in c.proposed_rows:
            lk = r["classschedule_lookup"]
            w.writerow([("" if r.get(k) is None else r.get(k)) for k in SCHEDULE_COLUMNS]
                       + [f"{lk['classbatch_id']}|{lk['class_date']}|{lk['start_time']}"])
    return out.getvalue()


def exceptions_csv(cases, reassign: dict | None = None) -> str:
    reassign = reassign or {}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["invoice_id", "decision", "reason_codes", "owner", "hours_open", "sla_state", "recommended_action"])
    for c in cases:
        if c.decision in OPEN:
            w.writerow([c.invoice.id, c.decision.value, "|".join(c.reason_codes), reassign.get(c.invoice.id) or c.owner.value,
                        c.sla.get("hours_open"), c.sla.get("state"), c.recommended_action])
    return out.getvalue()
