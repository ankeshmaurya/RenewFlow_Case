"""Teacher remark intent extraction. Gemini when available, deterministic keywords otherwise."""
from __future__ import annotations

import asyncio

from pydantic import BaseModel

from ..engine.remarks import INTENT_KEYS, keyword_intents
from . import client

SYSTEM = ("You read one short free-text remark written by a teacher about a student renewal at an online classes company. "
          "Return booleans only. mentions_same_batch means the remark says the student continues in the same batch. "
          "Do not infer anything that is not in the text.")


class RemarkIntents(BaseModel):
    mentions_discount: bool
    mentions_batch_change: bool
    mentions_third_party_payer: bool
    mentions_payment_issue: bool
    mentions_resubmission: bool
    mentions_same_batch: bool


async def _one(form):
    base = keyword_intents(form.remarks)
    if not form.remarks or not client.available():
        return form.id, base, "keyword"
    data = await client.generate_json(f"Remark: {form.remarks}", RemarkIntents, SYSTEM)
    if data and all(k in data and isinstance(data[k], bool) for k in INTENT_KEYS):
        return form.id, {k: data[k] for k in INTENT_KEYS}, "gemini"
    return form.id, base, "keyword"


async def extract_all(forms):
    """Returns (intents_by_form_id, sources_by_form_id)."""
    results = await asyncio.gather(*[_one(f) for f in forms])
    return {fid: i for fid, i, _ in results}, {fid: s for fid, _, s in results}
