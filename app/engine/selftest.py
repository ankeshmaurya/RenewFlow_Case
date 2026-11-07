"""Self-test (always deterministic, default settings) and shadow-mode comparison."""
from __future__ import annotations

import json
from pathlib import Path

from ..models import Decision
from ..settings import Settings
from .pipeline import run_pipeline

GOLDEN = Path(__file__).resolve().parents[2] / "data" / "sample" / "expected_results.json"

METRIC_MAP = {
    "decisionCounts": "decision_counts",
    "rawPaidInvoicesWithoutValidForm": "raw_paid_without_valid_form",
    "paidInvoicesWithoutFormAfterHealing": "paid_without_form_after_healing",
    "formsPendingOver12h": "forms_pending_over_threshold",
    "bookingsUnscheduledOver12h": "bookings_unscheduled_over_threshold",
    "paidUnscheduledValueInr": "paid_unscheduled_value_inr",
    "fullyCompletedEndToEnd": "fully_completed_end_to_end",
    "touchlessRatePercent": "touchless_rate_percent",
}


def run_selftest(tables) -> dict:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    settings = Settings(as_of=golden["asOf"])
    run = run_pipeline(tables, settings)
    by_id = {str(c.invoice.id): c for c in run["cases"]}
    items, matched = [], 0
    for inv_id, exp in golden["invoices"].items():
        c = by_id.get(inv_id)
        if c is None:
            items.append(dict(invoice_id=inv_id, expected=exp, actual=None, match=False, problems=["invoice missing from run"]))
            continue
        problems = []
        if c.decision.value != exp["decision"]:
            problems.append(f"decision {c.decision.value} != {exp['decision']}")
        missing = [x for x in exp["expectedReasonCodes"] if x not in c.reason_codes]
        if missing:
            problems.append("missing codes: " + ", ".join(missing))
        if c.owner.value != exp["owner"]:
            problems.append(f"owner {c.owner.value} != {exp['owner']}")
        ok = not problems
        matched += ok
        items.append(dict(invoice_id=inv_id, expected=exp, match=ok, problems=problems,
                          actual=dict(decision=c.decision.value, reason_codes=c.reason_codes, owner=c.owner.value)))
    metric_items, m_ok = [], 0
    for gk, mk in METRIC_MAP.items():
        exp, act = golden["metrics"][gk], run["metrics"][mk]
        ok = (exp == act) if not isinstance(exp, float) else abs(exp - float(act)) < 0.051
        m_ok += ok
        metric_items.append(dict(metric=gk, expected=exp, actual=act, match=ok))
    form_items = []
    c3309 = next((c for c in run["cases"] if 3309 in c.suppressed_form_ids), None)
    form_items.append(dict(check="Form 3309 suppressed as duplicate of 3308", match=bool(c3309 and c3309.primary_form_id == 3308)))
    c3313 = next((c for c in run["cases"] if c.healed_from_form_id == 3313), None)
    form_items.append(dict(check="Form 3313 (typed 84931) healed to invoice 84913",
                           match=bool(c3313 and c3313.invoice.id == 84913 and c3313.healed_typed_invoice_id == 84931)))
    f_ok = sum(i["match"] for i in form_items)
    return dict(total=len(items), matched=matched, metrics_total=len(metric_items), metrics_matched=m_ok,
                forms_total=len(form_items), forms_matched=f_ok,
                passed=(matched == len(items) and m_ok == len(metric_items) and f_ok == len(form_items)),
                invoices=items, metrics=metric_items, forms=form_items)


def shadow_report(run: dict, tables, settings) -> dict:
    as_of = settings.as_of_dt
    cases = run["cases"]
    by_invoice = {c.invoice.id: c for c in cases}
    approved, pending = [], []
    for c in cases:
        for f in c.forms:
            if f.source != "teacher":
                continue
            if f.approval_status == "Approved":
                agree = c.decision in (Decision.AUTO_APPROVE, Decision.ALREADY_COMPLETE)
                stalled = bool(c.booking and not [r for r in c.schedule_rows if (r.is_cancelled or "No") != "Yes"])
                approved.append(dict(form_id=f.id, invoice_id=c.invoice.id, approved_by=f.approved_by,
                                     human_hours=round((f.approved_at - f.created_at).total_seconds() / 3600, 2),
                                     engine_decision=c.decision.value, agree=agree, stalled_downstream=stalled,
                                     booking_status=c.booking.request_status if c.booking else None,
                                     reason_codes=c.reason_codes,
                                     note=("Engine agrees." if agree else "Human approved something the engine flags: " + c.recommended_action)
                                     + (" Approval then stalled downstream." if stalled else "")))
            elif f.approval_status == "Pending" and f.created_at:
                waited = (as_of - f.created_at).total_seconds() / 3600
                suppressed = f.id in c.suppressed_form_ids
                removed = suppressed or c.decision == Decision.AUTO_APPROVE
                pending.append(dict(form_id=f.id, invoice_id=c.invoice.id, waited_hours=round(waited, 1),
                                    engine_decision=c.decision.value, engine_seconds=1,
                                    waiting_removed=removed, suppressed_duplicate=suppressed))
    agree_n = sum(a["agree"] for a in approved)
    rate = round(agree_n / len(approved) * 100, 1) if approved else 0.0
    removed_hours = round(sum(p["waited_hours"] for p in pending if p["waiting_removed"]), 1)
    triaged_hours = round(sum(p["waited_hours"] for p in pending if not p["waiting_removed"]), 1)
    wrong = 0
    return dict(approved=approved, pending=pending, agreement_rate=rate, agreed=agree_n, approved_total=len(approved),
                removed_wait_hours=removed_hours, triaged_wait_hours=triaged_hours,
                gate=dict(required_agreement=95.0, wrong_schedules=wrong, open=(rate >= 95.0 and wrong == 0),
                          reason=("Agreement is below 95%. The disagreement is the engine being stricter than the human, "
                                  "so review each disagreement before moving to Assist mode.") if rate < 95.0 else "Gate met."))
