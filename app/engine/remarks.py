"""Deterministic remark intent extraction and cross-checks. The Gemini layer may supply intents instead."""
from __future__ import annotations

import re

INTENT_KEYS = ["mentions_discount", "mentions_batch_change", "mentions_third_party_payer",
               "mentions_payment_issue", "mentions_resubmission", "mentions_same_batch"]

_PATTERNS = {
    "mentions_discount": r"discount|scholarship|% ?off|waiver|concession",
    "mentions_batch_change": r"instead of|change (the )?batch|different batch|new batch|switch|shift to",
    "mentions_third_party_payer": r"(mother|father|mom|dad|grand\w*|uncle|aunt|sister|brother|relative|friend|employer|someone)\s+(has\s+)?paid",
    "mentions_payment_issue": r"processing|screenshot|failed|not deducted|debited|deducted|stuck|pending payment",
    "mentions_resubmission": r"resubmit|re-submit|submitted again|froze|duplicate",
    "mentions_same_batch": r"same batch|continue\b.*\bbatch|continue same",
}


def keyword_intents(text) -> dict:
    t = (text or "").lower()
    return {k: bool(re.search(p, t)) for k, p in _PATTERNS.items()}


def contradictions(form, invoice, payer_mismatch: bool, intents: dict) -> list[str]:
    """Return human-readable contradictions between remark intent and structured fields."""
    out = []
    if intents.get("mentions_discount") and (invoice.discount_amount or 0) == 0:
        out.append("Remark mentions a discount but the invoice has no discount.")
    if intents.get("mentions_batch_change") and form.continue_same_batch == "Yes":
        out.append("Remark asks for a batch change but the form says continue_same_batch = Yes.")
    if intents.get("mentions_same_batch") and form.continue_same_batch == "No":
        out.append("Remark says same batch but the form says continue_same_batch = No.")
    if intents.get("mentions_third_party_payer") and not payer_mismatch:
        out.append("Remark says someone else paid but the payer details match the registered parent.")
    return out
