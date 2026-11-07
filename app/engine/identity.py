"""Identity: hard keys must agree, payer contact differences are soft."""
from ..models import CaseCheck, Severity
from .normalize import email_match, name_match, phone_match, was_folded


def identity_checks(case):
    inv, ref, form = case.invoice, case.reference, case.primary_form
    problems = []
    if ref is None:
        problems.append(f"No active student record for student_id {inv.student_id}.")
    else:
        if ref.user_id != inv.user_id:
            problems.append(f"invoice user_id {inv.user_id} vs student record {ref.user_id}")
    if form is not None:
        if form.user_id != inv.user_id:
            problems.append(f"invoice user_id {inv.user_id} vs form {form.user_id}")
        if form.student_id != inv.student_id:
            problems.append(f"invoice student_id {inv.student_id} vs form {form.student_id}")
    case.add(CaseCheck(code="ID_STUDENT_MISMATCH", name="User and student ids agree across records", stage="IDENTITY",
                       severity=Severity.block, passed=not problems,
                       detail="; ".join(problems) if problems else "Invoice, form and student record agree."))

    diffs = []
    if ref is not None:
        if not phone_match(inv.mobile, ref.registered_mobile_masked):
            diffs.append(("mobile", inv.mobile, ref.registered_mobile_masked))
        if not email_match(inv.email, ref.registered_email_masked):
            diffs.append(("email", inv.email, ref.registered_email_masked))
        if not name_match(inv.parent_name, ref.parent_name_masked):
            diffs.append(("parent name", inv.parent_name, ref.parent_name_masked))
    for label, a, b in diffs:
        case.diffs.append(dict(field=label, invoice=a, registered=b))
    case.add(CaseCheck(code="ID_PAYER_MISMATCH", name="Payer matches the registered parent", stage="IDENTITY",
                       severity=Severity.notice, passed=not diffs,
                       detail=("Differs from registered: " + ", ".join(d[0] for d in diffs) + ". Payment link is bound to the student, so not blocking.")
                       if diffs else "Mobile, email and name match."))

    texts = [("invoice parent name", inv.parent_name), ("invoice mobile", inv.mobile), ("invoice email", inv.email)]
    if form is not None:
        texts += [("form student name", form.student_name), ("form parent mobile", form.parent_mobile)]
    folded = [label for label, t in texts if was_folded(t)]
    case.add(CaseCheck(code="DATA_TEXT_NORMALIZED", name="Text free of look-alike characters", stage="IDENTITY",
                       severity=Severity.info, passed=not folded,
                       detail=("Look-alike (non-Latin) characters found and normalized in: " + ", ".join(folded)) if folded else "Clean."))
    if folded:
        case.healed_actions.append("Normalized look-alike characters in: " + ", ".join(folded) + ".")
