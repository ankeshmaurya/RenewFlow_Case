"""Five-line morning brief for the Head of Ops."""
from __future__ import annotations

import re

from pydantic import BaseModel

from . import client
from .messages import NUM
from .templates import inr


class BriefOut(BaseModel):
    lines: list[str]


def deterministic_brief(metrics: dict, cases) -> list[str]:
    m, dc = metrics, metrics["decision_counts"]
    total = m["total_invoices"]
    human = [c for c in cases if c.decision.value in ("FLAGGED", "BLOCKED")]
    human_txt = "; ".join(f"{c.invoice.id} {c.reason_codes[0] if c.reason_codes else ''} ({c.owner.value})" for c in human) or "none"
    top = m["needs_action"][0] if m["needs_action"] else None
    return [
        f"{inr(m['paid_unscheduled_value_inr'])} is collected on renewals that are not scheduled; only {m['fully_completed_end_to_end']} of {total} renewals is complete.",
        f"{m['forms_pending_over_threshold']} teacher forms have waited over the threshold (oldest {m['oldest_pending_form_hours']}h) and "
        f"{m['bookings_unscheduled_over_threshold']} bookings sit unscheduled (oldest {m['oldest_unscheduled_booking_hours']}h).",
        f"The engine can approve {dc['AUTO_APPROVE']} of {total} with no human touch ({m['touchless_rate_percent']}%), and {dc['FAST_TRACK_PENDING_PARENT']} more need only a parent tap.",
        f"Needs a person: {human_txt}.",
        (f"Start with invoice {top['invoice_id']}: {inr(top['collected'])} waiting {top['hours']}h, owner {top['owner']}." if top else "No urgent case."),
    ]


async def build_brief(metrics: dict, cases, use_llm: bool) -> dict:
    base = deterministic_brief(metrics, cases)
    if use_llm and client.available():
        data = await client.generate_json(
            "Rewrite these five lines as a crisp morning brief for a Head of Operations. Keep every number and id exactly. "
            "Return exactly five lines.\n" + "\n".join(base), BriefOut,
            "You write short operational briefs. Never change or add numbers, ids or names.")
        if data and isinstance(data.get("lines"), list) and len(data["lines"]) == 5:
            joined, src = " ".join(base), " ".join(data["lines"])
            if all(tok in src for tok in set(NUM.findall(joined))):
                return dict(lines=data["lines"], source="ai")
    return dict(lines=base, source="template")
