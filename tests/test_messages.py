import asyncio
import os
import re

from app.engine.pipeline import run_pipeline
from app.llm import client
from app.llm.messages import build_messages, facts_preserved
from app.llm.brief import build_brief
from app.llm.remarks import extract_all


def _run(coro):
    return asyncio.run(coro)


def test_templates_work_without_key(tables, settings, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert not client.available()
    run = run_pipeline(tables, settings)
    msgs = _run(build_messages(run["cases"], "English", True))
    assert msgs and all(m["source"] == "template" for m in msgs)
    assert {m["invoice_id"] for m in msgs} >= {c.invoice.id for c in run["cases"] if c.decision.value != "ALREADY_COMPLETE"}
    assert len({m["id"] for m in msgs}) == len(msgs)


def test_failed_payment_never_tells_parent_to_pay_again(tables, settings):
    run = run_pipeline(tables, settings)
    case = next(c for c in run["cases"] if c.invoice.id == 84911)
    msgs = _run(build_messages([case], "English", False))
    parent = next(m for m in msgs if m["recipient_role"] == "PARENT")
    body = parent["body"].lower()
    assert "do not pay again" in body
    assert not re.search(r"(please|kindly|you can|you should)\s+(pay|retry|try)", body)


def test_whatsapp_length_and_facts(tables, settings):
    run = run_pipeline(tables, settings)
    for m in _run(build_messages(run["cases"], "English", False)):
        if m["channel"] == "whatsapp":
            assert len(m["body"]) <= 600, (m["id"], len(m["body"]))


def test_typo_message_mentions_healed_id(tables, settings):
    run = run_pipeline(tables, settings)
    case = next(c for c in run["cases"] if c.invoice.id == 84913)
    msgs = _run(build_messages([case], "English", False))
    teacher = [m for m in msgs if m["kind"] == "teacher_data_fix"][0]
    assert "84931" in teacher["body"] and "84913" in teacher["body"]


def test_facts_guard():
    base = "Payment of Rs 12,000 for invoice 84901, first class Mon 9 Nov"
    assert facts_preserved(base, "Hum ne Rs 12,000 ka payment invoice 84901 ke liye liya, class Mon 9 Nov")
    assert not facts_preserved(base, "Payment of Rs 15,000 for invoice 84901, first class Mon 9 Nov")


def test_remarks_and_brief_fallback(tables, settings, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    forms = [f for f in tables.forms]
    intents, sources = _run(extract_all(forms))
    assert set(sources.values()) == {"keyword"}
    assert intents[3307]["mentions_discount"] and intents[3312]["mentions_batch_change"] and intents[3304]["mentions_third_party_payer"]
    run = run_pipeline(tables, settings)
    b = _run(build_brief(run["metrics"], run["cases"], True))
    assert b["source"] == "template" and len(b["lines"]) == 5 and "126,850" in b["lines"][0]


def test_remark_contradiction_flags_a_case(tables, settings):
    from app.engine.remarks import contradictions
    inv = next(i for i in tables.invoices if i.id == 84903)
    form = next(f for f in tables.forms if f.id == 3303)
    assert contradictions(form, inv, False, {"mentions_batch_change": True})
    assert not contradictions(form, inv, False, {"mentions_batch_change": False})
