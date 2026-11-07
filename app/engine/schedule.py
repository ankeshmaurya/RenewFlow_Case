"""Build proposed class_schedule_bookings rows for AUTO_APPROVE cases."""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from ..models import Decision
from .downstream import active_rows
from .normalize import days_set

_WD = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


def _add_minutes(hhmmss: str, minutes: int) -> str:
    h, m, *rest = (hhmmss + ":00").split(":")[:3]
    base = datetime(2000, 1, 1, int(h), int(m), int(rest[0]) if rest and rest[0] else 0) + timedelta(minutes=minutes)
    return base.strftime("%H:%M:%S")


def _norm_time(t: str) -> str:
    parts = (t or "00:00:00").split(":")
    while len(parts) < 3:
        parts.append("00")
    return ":".join(p.zfill(2) for p in parts[:3])


def propose_rows(case, settings, as_of):
    case.proposed_rows, case.proposed_booking_request = [], None
    if case.decision != Decision.AUTO_APPROVE or case.reference is None:
        return
    ref, form, inv = case.reference, case.primary_form, case.invoice
    wd = sorted(_WD[d] for d in days_set(ref.batch_days) if d in _WD)
    if not wd:
        return
    n = (form.sessions_purchased if form and form.sessions_purchased else None) or \
        (case.booking.sessions_count if case.booking and case.booking.sessions_count else None) or settings.sessions_default
    if case.provisional and inv.amount:
        n = max(1, math.floor(n * inv.net_amount / inv.amount))
    start_after = as_of.date()
    existing = [r.class_date for r in active_rows(case) if r.class_date]
    if existing:
        start_after = max(start_after, max(existing))
    start = _norm_time(ref.batch_start_time)
    end = _add_minutes(start, settings.session_minutes)
    d, rows = start_after + timedelta(days=1), []
    while len(rows) < n:
        if d.weekday() in wd:
            rows.append(dict(
                id=None,
                bookingrequest_id=case.booking.id if case.booking else None,
                new_booking_request=case.booking is None,
                invoice_id=inv.id,
                classschedule_id=None,
                classschedule_lookup=dict(classbatch_id=ref.current_classbatch_id, class_date=d.isoformat(), start_time=start),
                classbatch_id=ref.current_classbatch_id, class_id=ref.class_id, user_id=inv.user_id, student_id=inv.student_id,
                educator_id=ref.educator_id, class_date=d.isoformat(), start_time=start, end_time=end,
                booking_type="Regular_Renewal", is_cancelled="No", attended_class="No",
                created_at=as_of.isoformat(), updated_at=as_of.isoformat(), deleted_at=None))
        d += timedelta(days=1)
    case.proposed_rows = rows
    if case.booking is None:
        case.proposed_booking_request = dict(
            faculty_form_id=form.id if form and form.source == "teacher" else None, invoice_id=inv.id, user_id=inv.user_id,
            student_id=inv.student_id, class_id=ref.class_id, educator_id=ref.educator_id, classbatch_id=ref.current_classbatch_id,
            sessions_count=n, is_renewal="Yes", continue_same_batch="Yes", preferred_days=ref.batch_days, preferred_time=start,
            request_status="Completed", batch_allocated="Yes", allocated_by="renewflow_engine", allocated_at=as_of.isoformat())
