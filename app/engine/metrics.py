"""Global metrics for the dashboard, SLA panel and self-test."""
from __future__ import annotations

import statistics
from collections import Counter

from ..models import Decision
from ..timeutil import hours_between
from .downstream import active_rows

CONFIRMED = {"Paid", "Partially_Paid"}
BUCKETS = [("0-4h", 0, 4), ("4-12h", 4, 12), ("12-24h", 12, 24), ("24-48h", 24, 48), ("48h+", 48, 1e9)]
OPEN_DECISIONS = {Decision.FLAGGED, Decision.BLOCKED, Decision.FAST_TRACK_PENDING_PARENT}


def _bucketize(values):
    out = [0] * len(BUCKETS)
    for v in values:
        for i, (_l, lo, hi) in enumerate(BUCKETS):
            if lo <= v < hi:
                out[i] += 1
                break
    return out


def _median(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 2) if xs else None


def hours_saved(a):
    n = a.renewals_per_week
    base_ops = n * a.manual_minutes / 60.0
    avg_min = a.mix_auto * a.minutes_auto + a.mix_parent * a.minutes_parent + a.mix_exception * a.minutes_exception
    target_ops = n * avg_min / 60.0
    return dict(baseline_ops_hours=round(base_ops, 1), target_ops_hours=round(target_ops, 1),
                ops_hours_saved=round(base_ops - target_ops, 1), avg_minutes_per_renewal=round(avg_min, 2),
                teacher_hours_saved=round(n * a.teacher_form_minutes / 60.0, 1))


def compute_metrics(cases, orphan_forms, tables, settings, as_of):
    thr = settings.stuck_threshold_hours
    total = len(cases)
    inv_ids = {c.invoice.id for c in cases}
    real_forms = [f for f in tables.forms if f.deleted_at is None]
    decision_counts = {d.value: 0 for d in Decision}
    for c in cases:
        decision_counts[c.decision.value] += 1

    confirmed = [c for c in cases if c.invoice.payment_status in CONFIRMED]
    exact_form_invoices = {f.invoice_id for f in real_forms if f.invoice_id in inv_ids}
    raw_orphans = [c for c in confirmed if c.invoice.id not in exact_form_invoices]
    healed_orphans = [c for c in confirmed if not [f for f in c.forms if f.source == "teacher"]]

    pending = [f for f in real_forms if f.approval_status == "Pending" and f.created_at]
    pending_ages = [hours_between(f.created_at, as_of) for f in pending]
    forms_pending_over = [a for a in pending_ages if a > thr]

    unsched_bookings = [c for c in cases if c.booking and not active_rows(c)]
    unsched_ages = [hours_between(c.booking.created_at, as_of) for c in unsched_bookings]
    unsched_over = [a for a in unsched_ages if a > thr]

    unscheduled_paid = [c for c in confirmed if not active_rows(c)]
    paid_unscheduled_value = sum(c.invoice.net_amount for c in unscheduled_paid)

    completed = [c for c in cases if c.decision == Decision.ALREADY_COMPLETE]
    approved_forms = [f for f in real_forms if f.approval_status == "Approved"]
    approved_cases = [c for c in cases if any(f.approval_status == "Approved" for f in c.forms if f.source == "teacher")]
    stalled = [c for c in approved_cases if c.booking and not active_rows(c)]

    code_counts = Counter(code for c in cases for code in c.reason_codes)
    pareto = [dict(code=k, count=v) for k, v in code_counts.most_common()]

    workload = {}
    for c in cases:
        if c.decision in OPEN_DECISIONS:
            w = workload.setdefault(c.owner.value, dict(owner=c.owner.value, open=0, oldest_hours=0.0, invoice_ids=[]))
            w["open"] += 1
            w["oldest_hours"] = max(w["oldest_hours"], c.sla.get("hours_open") or 0)
            w["invoice_ids"].append(c.invoice.id)
    workload = sorted(workload.values(), key=lambda w: -w["oldest_hours"])

    needs = []
    for c in cases:
        if c.decision == Decision.ALREADY_COMPLETE:
            continue
        collected = c.invoice.net_amount if c.invoice.payment_status in CONFIRMED else 0.0
        h = c.sla.get("hours_open") or 0
        needs.append(dict(invoice_id=c.invoice.id, invoice_number=c.invoice.invoice_number, decision=c.decision.value,
                          owner=c.owner.value, collected=collected, hours=round(h, 1), risk=round(collected * h, 0),
                          reason_codes=c.reason_codes, action=c.recommended_action))
    needs.sort(key=lambda n: (-n["risk"], -n["hours"]))

    funnel_raw = [total, len(exact_form_invoices & inv_ids), len({c.invoice.id for c in approved_cases}),
                  len([c for c in cases if c.booking]), len([c for c in cases if active_rows(c)])]
    engine_ok = decision_counts["AUTO_APPROVE"] + decision_counts["ALREADY_COMPLETE"]
    funnel_engine = [total, len([c for c in cases if [f for f in c.forms if f.source == "teacher"]]), engine_ok, engine_ok, engine_ok]

    p2f = [c.sla.get("payment_to_form_minutes") for c in cases]
    f2a = [c.sla.get("form_to_approval_hours") for c in cases]
    p2s = [c.sla.get("payment_to_schedule_hours") for c in cases]
    alloc = [hours_between(c.booking.created_at, c.booking.allocated_at) for c in cases if c.booking and c.booking.allocated_at]
    stuck_unsched_conf = [c for c in unscheduled_paid if (c.sla.get("hours_since_payment") or 0) > settings.schedule_target_hours]
    approved_over_target = [c for c in approved_cases if (c.sla.get("form_to_approval_hours") or 0) > settings.approval_target_hours]
    pending_over_target = [a for a in pending_ages if a > settings.approval_target_hours]
    orphan_over_form_target = [c for c in raw_orphans if (c.sla.get("hours_since_payment") or 0) > settings.form_target_hours]

    sla_panel = [
        dict(stage="Payment to teacher form", target=f"{settings.form_target_hours:g}h", median=_median(p2f), unit="min",
             breaches=len(orphan_over_form_target), note="Paid invoices with no form past target"),
        dict(stage="Form to Ops approval", target=f"{settings.approval_target_hours:g}h", median=_median(f2a), unit="h",
             breaches=len(pending_over_target) + len(approved_over_target), note="Pending forms plus approvals slower than target"),
        dict(stage="Approval to batch allocation", target=f"{settings.allocation_target_hours:g}h", median=_median(alloc), unit="h",
             breaches=len(unsched_over), note="Bookings unscheduled past the stuck threshold"),
        dict(stage="Payment to schedule (headline)", target=f"{settings.schedule_target_hours:g}h", median=_median(p2s), unit="h",
             breaches=len(stuck_unsched_conf), note="Confirmed payments still unscheduled past target"),
    ]

    ageing = dict(buckets=[b[0] for b in BUCKETS],
                  no_form=_bucketize([c.sla.get("hours_since_payment") or 0 for c in raw_orphans]),
                  form_pending=_bucketize(pending_ages), booking_unscheduled=_bucketize(unsched_ages))

    touchless = round(decision_counts["AUTO_APPROVE"] / total * 100, 1) if total else 0.0
    return dict(
        as_of=as_of.isoformat(), total_invoices=total, payment_confirmed=len(confirmed),
        forms_total=len(real_forms), orphan_forms=len(orphan_forms), decision_counts=decision_counts,
        raw_paid_without_valid_form=len(raw_orphans), paid_without_form_after_healing=len(healed_orphans),
        forms_pending_over_threshold=len(forms_pending_over), bookings_unscheduled_over_threshold=len(unsched_over),
        paid_unscheduled_value_inr=round(paid_unscheduled_value, 2), fully_completed_end_to_end=len(completed),
        touchless_rate_percent=touchless,
        parent_tap_rate_percent=round(decision_counts["FAST_TRACK_PENDING_PARENT"] / total * 100, 1) if total else 0.0,
        false_batch_full_count=sum("BATCH_FULL_FALSE_POSITIVE" in c.reason_codes for c in cases),
        duplicate_form_count=sum("LINK_DUPLICATE_FORM" in c.reason_codes for c in cases),
        typo_count=sum("LINK_ID_TYPO_HEALED" in c.reason_codes for c in cases),
        payer_mismatch_count=sum("ID_PAYER_MISMATCH" in c.reason_codes for c in cases),
        discount_unapproved_count=sum("DISCOUNT_UNAPPROVED" in c.reason_codes for c in cases),
        median_payment_to_form_minutes=_median(p2f), median_form_to_approval_hours=_median(f2a),
        median_payment_to_schedule_hours=_median(p2s),
        oldest_pending_form_hours=round(max(pending_ages), 1) if pending_ages else 0,
        oldest_unscheduled_booking_hours=round(max(unsched_ages), 1) if unsched_ages else 0,
        approval_throughput=dict(approved=len(approved_forms), total=len(real_forms)),
        approved_but_stalled=dict(stalled=len(stalled), approved=len(approved_cases), invoice_ids=[c.invoice.id for c in stalled]),
        funnel=dict(labels=["Invoices", "Valid forms", "Approved", "Booking requests", "Scheduled"], raw=funnel_raw, engine=funnel_engine),
        ageing=ageing, pareto=pareto, owner_workload=workload, needs_action=needs[:5], sla_panel=sla_panel,
        hours_saved=hours_saved(settings.assumptions),
    )
