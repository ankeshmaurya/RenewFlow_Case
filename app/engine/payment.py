"""Payment gate: is the money really in?"""
from ..models import CaseCheck, Severity


def payment_checks(case):
    inv = case.invoice
    status = inv.payment_status
    has_gateway = bool(inv.gateway_payment_id) and inv.paid_at is not None
    full = status == "Paid" and has_gateway and inv.deleted_at is None
    partial = status == "Partially_Paid" and has_gateway
    not_conf = not (full or partial)
    detail = f"Status {status}, gateway payment id {'present' if inv.gateway_payment_id else 'missing'}."
    if not_conf and case.forms:
        detail += f" Teacher form {case.forms[0].id} was already filed on this invoice."
    case.add(CaseCheck(code="PAY_NOT_CONFIRMED", name="Payment confirmed by gateway", stage="PAYMENT",
                       severity=Severity.block, passed=not not_conf, detail=detail if not_conf else f"Status {status} with gateway id."))
    case.add(CaseCheck(code="PAY_PARTIAL", name="Payment is complete, not an installment", stage="PAYMENT",
                       severity=Severity.warn, passed=not partial,
                       detail=(f"{inv.payment_type}: collected {inv.net_amount:.0f} of {inv.amount:.0f}." if partial else "Full payment.")))
