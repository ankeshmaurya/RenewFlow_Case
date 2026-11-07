"""Deterministic message templates. These always work, with or without Gemini."""
from __future__ import annotations

from datetime import date

from ..models import Decision

SLACK_CHANNEL = {"FINANCE_OPS": "#ops-finance", "OPS_LEAD": "#ops-approvals", "SCHEDULING_DESK": "#ops-scheduling",
                 "DATA_DESK": "#ops-data", "NONE": "#ops-renewals", "PARENT": "#ops-renewals", "TEACHER": "#ops-renewals"}


def inr(n) -> str:
    return "Rs " + f"{float(n):,.0f}"


def fmt_date(iso) -> str:
    d = date.fromisoformat(iso) if isinstance(iso, str) else iso
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}"


def fmt_time(hhmm: str) -> str:
    h, m = int(hhmm[:2]), int(hhmm[3:5])
    suffix = "AM" if h < 12 else "PM"
    return f"{(h % 12) or 12}:{m:02d} {suffix}"


def ctx(case) -> dict:
    inv, ref = case.invoice, case.reference
    dates = [fmt_date(r["class_date"]) for r in case.proposed_rows[:4]]
    return dict(
        student=(ref.student_name_masked if ref else f"student {inv.student_id}"),
        parent=(ref.parent_name_masked if ref else (inv.parent_name or "Parent")),
        parent_mobile=(ref.registered_mobile_masked if ref else inv.mobile),
        class_name=(ref.class_name if ref else ""), batch=(ref.classbatch_name if ref else ""),
        days=(ref.batch_days if ref else ""), time=(fmt_time(ref.batch_start_time) if ref and ref.batch_start_time else ""),
        educator=(ref.educator_name if ref else "Teacher"), net=inr(inv.net_amount), amount=inr(inv.amount),
        inv=inv.invoice_number, inv_id=inv.id, dates=dates, n_sessions=len(case.proposed_rows))


def _m(case, kind, channel, role, label, body, cta=""):
    return dict(invoice_id=case.invoice.id, kind=kind, channel=channel, recipient_role=role, recipient_label=label,
                language="English", body=body, cta=cta, source="template", status="draft")


def template_messages(case) -> list[dict]:
    c, codes, form = ctx(case), set(case.reason_codes), case.primary_form
    out = []
    d = case.decision
    teacher = f"{c['educator']} (teacher)"
    parent = f"{c['parent']} ({c['parent_mobile']})"

    if d == Decision.AUTO_APPROVE:
        dates = ", ".join(c["dates"])
        extra = ""
        if case.provisional:
            extra = f" Because this is installment 1, {c['n_sessions']} sessions are scheduled now; we will share the remaining installment details."
        out.append(_m(case, "parent_confirmation", "whatsapp", "PARENT", parent,
                      f"Hello {c['parent']}, we have received your payment of {c['net']} for {c['student']}'s {c['class_name']}. "
                      f"Classes continue in {c['batch']} ({c['days']} at {c['time']}). First classes: {dates}.{extra} "
                      f"No form or action is needed. - Bambinos.live", "None needed"))
        out.append(_m(case, "teacher_fyi", "whatsapp", "TEACHER", teacher,
                      f"Hi {c['educator']}, the renewal for {c['student']} (invoice {c['inv_id']}) is confirmed and scheduled in {c['batch']}. "
                      f"First class {c['dates'][0] if c['dates'] else ''}. You do not need to fill a renewal form.", "None needed"))
        if "ID_PAYER_MISMATCH" in codes:
            fields = ", ".join(x["field"] for x in case.diffs)
            out.append(_m(case, "parent_payer_notice", "whatsapp", "PARENT", parent,
                          f"Hello {c['parent']}, we received a payment of {c['net']} for {c['student']}'s renewal from a different "
                          f"{fields} than the one registered with us. If you or a family member paid, no action is needed. "
                          f"If you do not recognise this payment, please reply NO or call us.", "Reply NO if unrecognised"))
        if "LINK_ID_TYPO_HEALED" in codes:
            out.append(_m(case, "teacher_data_fix", "whatsapp", "TEACHER", teacher,
                          f"Hi {c['educator']}, your renewal form {case.healed_from_form_id} listed invoice {case.healed_typed_invoice_id}, "
                          f"which does not exist. We matched it automatically to invoice {c['inv_id']}. Nothing to do now; please double-check "
                          f"the invoice number next time.", "Check invoice number"))
        if "LINK_DUPLICATE_FORM" in codes:
            out.append(_m(case, "teacher_data_fix", "whatsapp", "TEACHER", teacher,
                          f"Hi {c['educator']}, we received form {case.primary_form_id} and a duplicate ({', '.join(map(str, case.suppressed_form_ids))}) "
                          f"for invoice {c['inv_id']}. We kept the first one. No action needed.", "None needed"))
        if "BATCH_FULL_FALSE_POSITIVE" in codes or "BOOKING_STUCK_RESCUED" in codes:
            what = ("booking was wrongly failed as batch full; a renewing student already holds a seat" if "BATCH_FULL_FALSE_POSITIVE" in codes
                    else "booking was stuck unallocated although the batch was valid")
            out.append(_m(case, "ops_autofix_fyi", "slack", "OPS_AGENT", SLACK_CHANNEL["NONE"] + " (Ops agents)",
                          f"Auto-fixed: invoice {c['inv_id']} - {what}. Allocated in {c['batch']} and {c['n_sessions']} schedule rows proposed. FYI only.",
                          "None needed"))

    elif d == Decision.FAST_TRACK_PENDING_PARENT:
        if "BATCH_CHANGE_PARENT_SELECTION" in codes:
            opts = "; ".join(f"{i + 1}) {a['name']} {a['days']} {fmt_time(a['time'])}" for i, a in enumerate(case.alternatives[:3]))
            out.append(_m(case, "parent_batch_options", "whatsapp", "PARENT", parent,
                          f"Hello {c['parent']}, thank you for renewing {c['student']}'s {c['class_name']}. These batches match your request: {opts}. "
                          f"Reply with the number you prefer.", "Reply with a number"))
        else:
            out.append(_m(case, "parent_choice", "whatsapp", "PARENT", parent,
                          f"Hello {c['parent']}, we have received your payment of {c['net']} for {c['student']}'s {c['class_name']}. "
                          f"Reply 1 to continue in the same batch ({c['batch']}, {c['days']} at {c['time']}) or 2 to change batch.",
                          "Reply 1 or 2"))
        out.append(_m(case, "teacher_fyi_no_form", "whatsapp", "TEACHER", teacher,
                      f"Hi {c['educator']}, {c['student']}'s renewal payment ({c['net']}, invoice {c['inv_id']}) is in. We have asked the parent to "
                      f"confirm the batch, so you do not need to fill a renewal form.", "None needed"))

    elif d == Decision.BLOCKED:
        if "PAY_NOT_CONFIRMED" in codes:
            out.append(_m(case, "parent_payment_check", "whatsapp", "PARENT", parent,
                          f"Hello {c['parent']}, we could not yet confirm your payment of {c['amount']} for {c['student']}'s renewal. "
                          f"If the amount was debited from your account, please do not pay again: banks usually confirm or reverse such payments within a "
                          f"few hours, and we are checking with the payment provider. We will message you within 2 hours.", "Wait for our update"))
            out.append(_m(case, "teacher_unpaid_form", "whatsapp", "TEACHER", teacher,
                          f"Hi {c['educator']}, form {form.id if form else ''} was filed for invoice {c['inv_id']}, but its payment is not confirmed. "
                          f"Please file renewal forms only after payment is confirmed.", "None needed"))
        out.append(_m(case, "ops_exception", "slack", "FINANCE_OPS" if case.owner.value == "FINANCE_OPS" else case.owner.value,
                      f"{SLACK_CHANNEL.get(case.owner.value, '#ops-renewals')} ({case.owner.value})",
                      _ops_body(case, c), "Resolve and re-run"))

    elif d == Decision.FLAGGED:
        out.append(_m(case, "ops_exception", "slack", case.owner.value,
                      f"{SLACK_CHANNEL.get(case.owner.value, '#ops-renewals')} ({case.owner.value})", _ops_body(case, c),
                      "Resolve and re-run"))
        if "PAY_AMOUNT_MISMATCH" in codes and form:
            out.append(_m(case, "teacher_correction", "whatsapp", "TEACHER", teacher,
                          f"Hi {c['educator']}, form {form.id} shows {inr(form.amount_paid)} paid for invoice {c['inv_id']}, but the invoice shows "
                          f"{c['net']} collected ({case.invoice.payment_type}). Please correct the form. We will use the invoice amount.",
                          "Correct the form"))
        if "PAY_PARTIAL" in codes:
            rest = case.invoice.amount - case.invoice.net_amount
            out.append(_m(case, "parent_installment", "whatsapp", "PARENT", parent,
                          f"Hello {c['parent']}, we received {c['net']} (installment 1 of 2) for {c['student']}'s renewal. The remaining "
                          f"{inr(rest)} completes the 24 sessions. Our team will share the next payment link.", "Wait for payment link"))
        if "REMARK_CONTRADICTION" in codes and form:
            out.append(_m(case, "teacher_correction", "whatsapp", "TEACHER", teacher,
                          f"Hi {c['educator']}, on form {form.id} the remark and the form fields disagree: "
                          f"{next((x.detail for x in case.checks if x.code == 'REMARK_CONTRADICTION'), '')} Please confirm which is correct.",
                          "Confirm which is correct"))
        if "BATCH_CHANGE_NO_MATCH" in codes:
            want = f"{form.preferred_days} at {fmt_time(form.preferred_time_slot[:5])}" if form else "your requested slot"
            alt = "; ".join(f"{a['name']} {a['days']} {fmt_time(a['time'])} ({a['seats_left']} seat left)" for a in case.alternatives[:2]) \
                or "no close alternative yet"
            out.append(_m(case, "parent_batch_options", "whatsapp", "PARENT", parent,
                          f"Hello {c['parent']}, thank you for renewing {c['student']}'s {c['class_name']}. We do not have a batch on {want} yet; "
                          f"we are working on it. Closest options: {alt}. Reply 1 to keep your current batch for now, or 2 to wait for a "
                          f"{want} batch.", "Reply 1 or 2"))
    return out


def _ops_body(case, c) -> str:
    facts = "; ".join(x.detail for x in case.checks if not x.passed and x.severity.value in ("warn", "block"))
    return (f"[{', '.join(k for k in case.reason_codes if k)}] Invoice {c['inv_id']} ({c['net']}, {c['student']}, {c['class_name']}). "
            f"{facts} Recommended: {case.recommended_action}")
