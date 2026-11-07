"""Linking: forms to invoices (exact, link number, healed), duplicate suppression, booking and schedule attachment."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime

from ..models import CaseCheck, FacultyForm, InvoiceCase, Severity
from .normalize import damerau_levenshtein

LINK_RE = re.compile(r"(BMB-INV-\d{4}-\d+)", re.I)
HEAL_THRESHOLD = 0.9
CONFIRMED = {"Paid", "Partially_Paid"}


def number_from_link(link):
    m = LINK_RE.search(link or "")
    return m.group(1).upper() if m else None


def _ts(f: FacultyForm) -> float:
    return f.created_at.timestamp() if f.created_at else float("inf")


def _form_key(f: FacultyForm):
    return (f.user_id, f.student_id, f.class_id, f.current_classbatch_id, f.amount_paid,
            f.sessions_purchased, f.continue_same_batch, f.preferred_days, f.preferred_time_slot)


def score_candidate(form: FacultyForm, inv) -> tuple[float, list[str]]:
    score, ev = 0.0, []
    if form.user_id == inv.user_id:
        score += 0.30
        ev.append(f"same user_id {inv.user_id}")
    if form.student_id == inv.student_id:
        score += 0.30
        ev.append(f"same student_id {inv.student_id}")
    if form.educator_id is not None and form.educator_id == inv.educator_id:
        score += 0.10
        ev.append(f"same educator {inv.educator_id}")
    if form.amount_paid is not None and abs(form.amount_paid - inv.net_amount) < 0.01:
        score += 0.15
        ev.append(f"same amount {inv.net_amount:.0f}")
    dist = damerau_levenshtein(str(form.invoice_id), str(inv.id))
    if dist <= 2:
        score += 0.15
        ev.append(f"invoice id {form.invoice_id} vs {inv.id} differs by {dist} edit{'s' if dist != 1 else ''}")
    return round(score, 2), ev


def resolve_forms(invoices, forms):
    """Return (forms_by_invoice, healed, orphan_forms, conflicts)."""
    inv_by_id = {i.id: i for i in invoices}
    inv_by_num = {i.invoice_number.upper(): i for i in invoices}
    by_student, by_user = defaultdict(list), defaultdict(list)
    for i in invoices:
        by_student[i.student_id].append(i)
        by_user[i.user_id].append(i)
    by_invoice = defaultdict(list)
    healed: dict[int, dict] = {}
    conflicts = defaultdict(list)
    unresolved = []
    for f in forms:
        inv = inv_by_id.get(f.invoice_id)
        link_inv = inv_by_num.get(number_from_link(f.invoice_link) or "")
        if inv and link_inv and inv.id != link_inv.id:
            conflicts[inv.id].append(f"Form {f.id}: invoice_id {inv.id} but invoice_link points at {link_inv.invoice_number}")
        if inv:
            by_invoice[inv.id].append(f)
        elif link_inv:
            by_invoice[link_inv.id].append(f)
            healed[f.id] = dict(typed=f.invoice_id, invoice_id=link_inv.id, score=1.0,
                                evidence=[f"invoice number {link_inv.invoice_number} found in the form's link"])
        else:
            unresolved.append(f)
    orphan_forms = []
    taken = set(by_invoice.keys())
    for f in unresolved:
        scored = []
        pool = {i.id: i for i in by_student.get(f.student_id, []) + by_user.get(f.user_id, [])}
        for inv in pool.values():
            if inv.id in taken:
                continue
            s, ev = score_candidate(f, inv)
            if s >= HEAL_THRESHOLD:
                scored.append((s, inv, ev))
        if len(scored) == 1:
            s, inv, ev = scored[0]
            by_invoice[inv.id].append(f)
            taken.add(inv.id)
            healed[f.id] = dict(typed=f.invoice_id, invoice_id=inv.id, score=s, evidence=ev)
        else:
            orphan_forms.append(dict(form_id=f.id, typed_invoice_id=f.invoice_id,
                                     candidates=[dict(invoice_id=i.id, score=s) for s, i, _ in scored],
                                     detail="No single invoice matches well enough to heal this form."))
    return by_invoice, healed, orphan_forms, conflicts


def build_case(inv, ref, forms, healed, conflicts, bk_by_invoice, bk_by_form, sched_by_invoice, sched_by_booking, as_of) -> InvoiceCase:
    case = InvoiceCase(invoice=inv, reference=ref)
    case.forms = sorted(forms, key=_ts)
    approved = [f for f in case.forms if f.approval_status == "Approved"]
    primary = approved[0] if approved else (case.forms[0] if case.forms else None)
    suppressed, conflict_forms = [], []
    if primary:
        case.primary_form_id = primary.id
        for f in case.forms:
            if f.id == primary.id:
                continue
            same = _form_key(f) == _form_key(primary)
            within = abs(_ts(f) - _ts(primary)) <= 24 * 3600
            (suppressed if same and within else conflict_forms).append(f.id)
    case.suppressed_form_ids = suppressed
    for fid, h in healed.items():
        if h["invoice_id"] == inv.id:
            case.healed_from_form_id = fid
            case.healed_typed_invoice_id = h["typed"]

    form_ids = {f.id for f in case.forms}
    cand = {b.id: b for b in bk_by_invoice.get(inv.id, [])}
    for fid in form_ids:
        for b in bk_by_form.get(fid, []):
            cand[b.id] = b
    cand = list(cand.values())
    cand.sort(key=lambda b: b.created_at.timestamp() if b.created_at else 0, reverse=True)
    case.booking = cand[0] if cand else None
    bid = case.booking.id if case.booking else None
    rows = {s.id: s for s in sched_by_invoice.get(inv.id, [])}
    if bid:
        for s in sched_by_booking.get(bid, []):
            rows[s.id] = s
    case.schedule_rows = list(rows.values())

    confirmed = inv.payment_status in CONFIRMED
    case.add(CaseCheck(code="LINK_ORPHAN_INVOICE", name="Teacher form received for this payment", stage="LINK",
                       severity=Severity.warn, passed=bool(case.forms) or not confirmed,
                       detail=("No teacher form exists for this paid invoice." if confirmed and not case.forms
                               else f"{len(case.forms)} form(s) linked." if case.forms else "Payment not confirmed, so no form is expected yet.")))
    h = healed.get(case.healed_from_form_id) if case.healed_from_form_id else None
    case.add(CaseCheck(code="LINK_ID_TYPO_HEALED", name="Form points at the correct invoice id", stage="LINK",
                       severity=Severity.notice, passed=h is None,
                       detail=(f"Form {case.healed_from_form_id} typed invoice {h['typed']}; matched to {inv.id} (score {h['score']:.2f}: "
                               + "; ".join(h["evidence"]) + ").") if h else "Form invoice id matches."))
    if h:
        case.healed_actions.append(f"Healed link: form {case.healed_from_form_id} typed invoice {h['typed']}, matched to invoice {inv.id} "
                                   f"(score {h['score']:.2f}).")
    case.add(CaseCheck(code="LINK_DUPLICATE_FORM", name="Only one form per invoice", stage="LINK", severity=Severity.notice,
                       passed=not suppressed,
                       detail=(f"Form(s) {suppressed} are identical to form {case.primary_form_id}; suppressed." if suppressed else "No duplicates.")))
    if suppressed:
        case.healed_actions.append(f"Suppressed duplicate form(s) {suppressed} (identical to form {case.primary_form_id}).")
    cdetail = conflicts.get(inv.id, [])[:]
    if conflict_forms:
        cdetail.append(f"Form(s) {conflict_forms} differ from form {case.primary_form_id}.")
    case.add(CaseCheck(code="FORM_CONFLICT", name="Forms for this invoice agree", stage="LINK", severity=Severity.warn,
                       passed=not cdetail, detail=" ".join(cdetail) or "No conflicting forms."))
    return case
