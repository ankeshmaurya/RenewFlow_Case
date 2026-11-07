"""Pipeline orchestration: stage 1 (link, payment, identity) then stage 2 (amount, batch, remarks, downstream, decide)."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from ..models import CaseCheck, FacultyForm, Severity, Tables
from ..settings import Settings
from ..timeutil import IST
from .amount import amount_checks
from .batch import batch_checks, build_batches
from .decide import decide
from .downstream import downstream_checks
from .identity import identity_checks
from .link import build_case, resolve_forms
from .metrics import compute_metrics
from .payment import payment_checks
from .remarks import contradictions, keyword_intents
from .schedule import propose_rows
from .sla import compute_sla, compute_steps

PARENT_FORM_BASE = 9_000_000


def _virtual_form(inv, ref, as_of):
    return FacultyForm(
        id=PARENT_FORM_BASE + inv.id, educator_id=ref.educator_id, educator_name=ref.educator_name, user_id=inv.user_id,
        student_id=inv.student_id, student_name=ref.student_name_masked, parent_mobile=ref.registered_mobile_masked,
        class_id=ref.class_id, current_classbatch_id=ref.current_classbatch_id, invoice_id=inv.id, invoice_link=inv.invoice_link,
        amount_paid=inv.net_amount, sessions_purchased=24, continue_same_batch="Yes", preferred_days=ref.batch_days,
        preferred_time_slot=ref.batch_start_time, remarks="Parent confirmed continue-same-batch by WhatsApp reply (simulated).",
        approval_status="Pending", created_at=as_of, updated_at=as_of, source="parent_reply")


def run_stage1(tables: Tables, settings: Settings, parent_replies: dict | None = None):
    as_of = settings.as_of_dt
    invoices = [i for i in tables.invoices if i.deleted_at is None and (i.is_renewal or "Yes") == "Yes"]
    forms = [f for f in tables.forms if f.deleted_at is None]
    ref_by_student = {r.student_id: r for r in tables.reference if r.deleted_at is None}
    inv_by_id_early = {i.id: i for i in invoices}
    by_invoice, healed, orphan_forms, conflicts = resolve_forms(invoices, forms)
    for inv_id in (parent_replies or {}):
        inv = inv_by_id_early.get(inv_id)
        ref = ref_by_student.get(inv.student_id) if inv else None
        if inv and ref and not by_invoice.get(inv.id):
            by_invoice[inv.id] = [_virtual_form(inv, ref, as_of)]
    bk_by_invoice, bk_by_form = defaultdict(list), defaultdict(list)
    for b in tables.bookings:
        if b.deleted_at is None:
            bk_by_invoice[b.invoice_id].append(b)
            if b.faculty_form_id is not None:
                bk_by_form[b.faculty_form_id].append(b)
    sched_by_invoice, sched_by_booking = defaultdict(list), defaultdict(list)
    for r in tables.schedule:
        if r.deleted_at is None:
            sched_by_invoice[r.invoice_id].append(r)
            if r.bookingrequest_id is not None:
                sched_by_booking[r.bookingrequest_id].append(r)
    inv_by_id = {i.id: i for i in invoices}
    cases = []
    for inv in invoices:
        case = build_case(inv, ref_by_student.get(inv.student_id), by_invoice.get(inv.id, []), healed, conflicts,
                          bk_by_invoice, bk_by_form, sched_by_invoice, sched_by_booking, as_of)
        payment_checks(case)
        identity_checks(case)
        cases.append(case)
    return cases, orphan_forms


def run_pipeline(tables: Tables, settings: Settings, parent_replies: dict | None = None, remark_intents: dict | None = None) -> dict:
    as_of = settings.as_of_dt
    cases, orphan_forms = run_stage1(tables, settings, parent_replies)
    batches = build_batches(tables.reference)
    for case in cases:
        amount_checks(case, settings)
        batch_checks(case, batches)
        form = case.primary_form
        if form is not None and form.source == "teacher":
            intents = (remark_intents or {}).get(form.id) or keyword_intents(form.remarks)
            case.remark_intents = intents
            payer_mismatch = "ID_PAYER_MISMATCH" in [c.code for c in case.checks if not c.passed]
            found = contradictions(form, case.invoice, payer_mismatch, intents)
            case.add(CaseCheck(code="REMARK_CONTRADICTION", name="Teacher remark agrees with form fields", stage="REMARKS",
                               severity=Severity.warn, passed=not found, detail=" ".join(found) if found else "Consistent."))
        downstream_checks(case, settings, as_of)
        decide(case, settings)
        propose_rows(case, settings, as_of)
        compute_sla(case, settings, as_of)
        compute_steps(case, settings, as_of)
    metrics = compute_metrics(cases, orphan_forms, tables, settings, as_of)
    return dict(as_of=as_of.isoformat(), generated_at=datetime.now(IST).isoformat(), settings=settings.model_dump(),
                cases=cases, orphan_forms=orphan_forms, metrics=metrics)
