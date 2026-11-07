"""Message generation: deterministic templates, optionally rewritten by Gemini with a facts guard."""
from __future__ import annotations

import asyncio
import re

from pydantic import BaseModel

from . import client
from .templates import template_messages

SYSTEM = ("You rewrite short operational messages for an online classes company. Keep every number, date, weekday, id, name, batch name and "
          "amount exactly as given, written with ASCII digits. Do not add facts, promises, links or dates. Parents: warm and clear. Teachers: short "
          "and respectful. Ops on Slack: factual and compact. WhatsApp messages must stay under 600 characters. Write in the requested language "
          "(English, Hindi, or Hinglish = Hindi written in Latin script).")
NUM = re.compile(r"\d[\d,.:]*\d|\d")


class Rewrite(BaseModel):
    body: str


def facts_preserved(base: str, new: str) -> bool:
    return all(tok in new for tok in set(NUM.findall(base)))


async def _rewrite(msg: dict, language: str) -> dict:
    prompt = f"Role: {msg['recipient_role']}\nChannel: {msg['channel']}\nLanguage: {language}\nMessage to rewrite:\n{msg['body']}"
    data = await client.generate_json(prompt, Rewrite, SYSTEM)
    if data and isinstance(data.get("body"), str):
        body = data["body"].strip()
        limit_ok = msg["channel"] != "whatsapp" or len(body) <= 600
        if body and limit_ok and facts_preserved(msg["body"], body):
            return {**msg, "body": body, "source": "ai", "language": language}
    return msg


def message_id(m: dict) -> str:
    return f"{m['invoice_id']}-{m['kind']}-{m['recipient_role'].lower()}"


async def build_messages(cases, language: str = "English", use_llm: bool = True) -> list[dict]:
    base = []
    seen = {}
    for case in cases:
        for m in template_messages(case):
            mid = message_id(m)
            seen[mid] = seen.get(mid, 0) + 1
            m["id"] = mid if seen[mid] == 1 else f"{mid}-{seen[mid]}"
            m["language_requested"] = language
            base.append(m)
    if use_llm and client.available():
        base = list(await asyncio.gather(*[_rewrite(m, language) for m in base]))
    elif language != "English":
        for m in base:
            m["fallback_note"] = "Gemini unavailable: showing the English template."
    return base
