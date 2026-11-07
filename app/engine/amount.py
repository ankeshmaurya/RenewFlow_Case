"""Amount, fee and discount checks."""
from ..models import CaseCheck, Severity


def expected_price(case, settings):
    ref = case.reference
    if ref is None or ref.standard_fee_24_sessions_inr is None:
        return None
    form = case.primary_form
    sessions = (form.sessions_purchased if form and form.sessions_purchased else None) or \
               (case.booking.sessions_count if case.booking and case.booking.sessions_count else None) or settings.sessions_default
    return ref.standard_fee_24_sessions_inr * sessions / 24.0


def amount_checks(case, settings):
    inv, form = case.invoice, case.primary_form
    if inv.payment_status not in ("Paid", "Partially_Paid"):
        return
    if form is not None and form.amount_paid is not None:
        bad = abs(form.amount_paid - inv.net_amount) > 0.01
        case.add(CaseCheck(code="PAY_AMOUNT_MISMATCH", name="Form amount equals invoice net amount", stage="AMOUNT",
                           severity=Severity.warn, passed=not bad,
                           detail=(f"Form {form.id} says {form.amount_paid:.0f} paid; invoice net amount is {inv.net_amount:.0f}.") if bad
                           else f"Both {inv.net_amount:.0f}."))
    exp = expected_price(case, settings)
    if exp is not None:
        bad = abs(inv.amount - exp) > 0.01
        case.add(CaseCheck(code="FEE_MISMATCH", name="Invoice amount equals standard fee", stage="AMOUNT", severity=Severity.warn,
                           passed=not bad, detail=(f"Invoice amount {inv.amount:.0f}, standard fee for these sessions {exp:.0f}.") if bad
                           else f"Standard fee {exp:.0f}."))
    disc = inv.discount_amount or 0
    case.add(CaseCheck(code="DISCOUNT_UNAPPROVED", name="No discount, or discount has an approval", stage="AMOUNT", severity=Severity.warn,
                       passed=disc <= 0,
                       detail=(f"Discount {disc:.0f} ({disc / inv.amount * 100:.0f}% of {inv.amount:.0f}); there is no approver field in the schema.")
                       if disc > 0 else "No discount."))
