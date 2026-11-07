"""SLA clocks and 4-step tracker states for each case."""
from __future__ import annotations

from ..models import Decision
from ..timeutil import hours_between
from .downstream import STUCK_STATUSES, active_rows


def _fmt(h):
    return f"{h:.0f}h" if h is not None else ""


def compute_sla(case, settings, as_of):
    inv = case.invoice
    anchor = inv.paid_at or inv.created_at
    since = hours_between(anchor, as_of)
    real = [f for f in case.forms if f.source == "teacher"]
    first = real[0] if real else None
    primary = case.primary_form
    p2f = ((first.created_at - inv.paid_at).total_seconds() / 60) if first and inv.paid_at and first.created_at else None
    f2a = hours_between(primary.created_at, primary.approved_at) if primary and primary.approved_at else None
    pending_h = hours_between(primary.created_at, as_of) if primary and primary.source == "teacher" and primary.approval_status == "Pending" else None
    rows = active_rows(case)
    booking_age = hours_between(case.booking.created_at, as_of) if case.booking and not rows else None
    p2s = None
    if rows and inv.paid_at:
        stamps = [r.created_at for r in rows if r.created_at]
        p2s = hours_between(inv.paid_at, min(stamps)) if stamps else None
    open_h = None if case.decision == Decision.ALREADY_COMPLETE else since
    state = "Complete"
    if open_h is not None:
        state = "Breached" if open_h > settings.stuck_threshold_hours else \
            "Due soon" if open_h > settings.stuck_threshold_hours / 2 else "On track"
    escalation = None
    if case.decision == Decision.FAST_TRACK_PENDING_PARENT and open_h is not None and open_h > 4:
        escalation = "Escalate to an Ops agent: no parent response within 4 hours."
    case.sla = dict(anchor="paid_at" if inv.paid_at else "created_at", hours_since_payment=round(since, 2) if since is not None else None,
                    payment_to_form_minutes=round(p2f, 1) if p2f is not None else None,
                    form_to_approval_hours=round(f2a, 2) if f2a is not None else None,
                    form_pending_hours=round(pending_h, 2) if pending_h is not None else None,
                    booking_age_hours=round(booking_age, 2) if booking_age is not None else None,
                    payment_to_schedule_hours=round(p2s, 2) if p2s is not None else None,
                    hours_open=round(open_h, 2) if open_h is not None else None, state=state, escalation=escalation,
                    form_breach=bool(pending_h and pending_h > settings.stuck_threshold_hours),
                    booking_breach=bool(booking_age and booking_age > settings.stuck_threshold_hours))


def compute_steps(case, settings, as_of):
    inv, thr = case.invoice, settings.stuck_threshold_hours
    s = {}
    st = inv.payment_status
    s["invoice"] = dict(state="done" if st == "Paid" else "failed" if st not in ("Paid", "Partially_Paid") else "pending",
                        label={"Paid": "Paid"}.get(st, "Partial" if st == "Partially_Paid" else "Failed"))
    real = [f for f in case.forms if f.source == "teacher"]
    sla = case.sla
    if not real:
        if case.primary_form is not None:
            s["form"] = dict(state="done", label="Parent reply")
        else:
            h = sla.get("hours_since_payment") or 0
            s["form"] = dict(state="stuck" if (inv.payment_status in ("Paid", "Partially_Paid") and h > thr) else "missing",
                             label="Missing" + (f" {_fmt(h)}" if inv.payment_status in ("Paid", "Partially_Paid") else ""))
    elif case.healed_from_form_id:
        s["form"] = dict(state="healed", label="Healed link")
    elif case.primary_form and case.primary_form.approval_status == "Approved":
        s["form"] = dict(state="done", label="Approved")
    else:
        h = sla.get("form_pending_hours") or 0
        s["form"] = dict(state="stuck" if h > thr else "pending", label=f"Pending {_fmt(h)}")
    b = case.booking
    rows = active_rows(case)
    if b is None:
        s["booking"] = dict(state="missing", label="Missing")
    elif b.request_status == "Completed":
        s["booking"] = dict(state="done", label="Completed")
    else:
        age = sla.get("booking_age_hours") or 0
        s["booking"] = dict(state="stuck" if (b.request_status in STUCK_STATUSES and age > thr) else "pending",
                            label=f"{b.request_status.replace('_', ' ')} {_fmt(age)}")
    s["schedule"] = dict(state="done" if rows else "missing", label=f"{len(rows)} rows" if rows else "None")
    case.steps = s
