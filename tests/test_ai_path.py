"""The Gemini path is exercised with a stubbed client: no network, no key needed."""
import asyncio

from app.engine.pipeline import run_pipeline
from app.llm import client, messages as msgmod
from app.llm.brief import build_brief
from app.llm.remarks import extract_all


def _run(c):
    return asyncio.run(c)


def test_ai_rewrite_accepted_when_facts_preserved(tables, settings, monkeypatch):
    monkeypatch.setattr(client, "available", lambda: True)

    async def fake(prompt, schema, system=None):
        base = prompt.split("Message to rewrite:\n", 1)[1]
        return {"body": "Namaste! " + base}

    monkeypatch.setattr(client, "generate_json", fake)
    run = run_pipeline(tables, settings)
    case = next(c for c in run["cases"] if c.invoice.id == 84903)
    out = _run(msgmod.build_messages([case], "Hinglish", True))
    assert out and all(m["source"] == "ai" and m["language"] == "Hinglish" for m in out)


def test_ai_rewrite_rejected_when_it_changes_a_number(tables, settings, monkeypatch):
    monkeypatch.setattr(client, "available", lambda: True)

    async def fake(prompt, schema, system=None):
        return {"body": "Your payment of Rs 99,999 was received."}

    monkeypatch.setattr(client, "generate_json", fake)
    run = run_pipeline(tables, settings)
    case = next(c for c in run["cases"] if c.invoice.id == 84903)
    out = _run(msgmod.build_messages([case], "English", True))
    assert out and all(m["source"] == "template" for m in out)


def test_ai_failure_falls_back(tables, settings, monkeypatch):
    monkeypatch.setattr(client, "available", lambda: True)

    async def boom(prompt, schema, system=None):
        return None

    monkeypatch.setattr(client, "generate_json", boom)
    run = run_pipeline(tables, settings)
    out = _run(msgmod.build_messages(run["cases"], "English", True))
    assert out and all(m["source"] == "template" for m in out)
    b = _run(build_brief(run["metrics"], run["cases"], True))
    assert b["source"] == "template"
    intents, sources = _run(extract_all(list(tables.forms)))
    assert set(sources.values()) == {"keyword"}


def test_ai_remark_intents_used(tables, monkeypatch):
    monkeypatch.setattr(client, "available", lambda: True)

    async def fake(prompt, schema, system=None):
        return dict(mentions_discount=True, mentions_batch_change=False, mentions_third_party_payer=False,
                    mentions_payment_issue=False, mentions_resubmission=False, mentions_same_batch=False)

    monkeypatch.setattr(client, "generate_json", fake)
    forms = [f for f in tables.forms if f.remarks][:2]
    intents, sources = _run(extract_all(forms))
    assert set(sources.values()) == {"gemini"} and all(i["mentions_discount"] for i in intents.values())
