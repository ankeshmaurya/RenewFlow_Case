from app.engine.pipeline import run_pipeline
from app.engine.selftest import run_selftest, shadow_report
from app.settings import Settings


def test_selftest_passes(tables):
    res = run_selftest(tables)
    assert res["matched"] == res["total"] == 13
    assert res["metrics_matched"] == res["metrics_total"]
    assert res["forms_matched"] == res["forms_total"]
    assert res["passed"]


def test_decisions_and_proposed_rows(tables, settings):
    run = run_pipeline(tables, settings)
    d = {c.invoice.id: c for c in run["cases"]}
    for iid in (84902, 84903, 84904, 84905, 84908, 84913):
        assert d[iid].decision.value == "AUTO_APPROVE" and len(d[iid].proposed_rows) == 24
    assert d[84902].proposed_rows[0]["bookingrequest_id"] == 5502
    assert d[84903].proposed_rows[0]["bookingrequest_id"] is None
    assert d[84905].proposed_rows[0]["class_date"] == "2026-11-07"  # first Saturday after the as-of date
    assert d[84902].proposed_rows[0]["end_time"] == "18:50:00"
    for iid in (84901,):
        assert d[iid].proposed_rows == []


def test_alternatives_for_batch_change(tables, settings):
    run = run_pipeline(tables, settings)
    c = next(x for x in run["cases"] if x.invoice.id == 84912)
    assert c.alternatives and c.alternatives[0]["caveat"]


def test_partial_payment_policy_pro_rata(tables):
    run = run_pipeline(tables, Settings(partial_payment_policy="PROVISIONAL_PRO_RATA"))
    c = next(x for x in run["cases"] if x.invoice.id == 84909)
    assert c.decision.value == "AUTO_APPROVE" and c.provisional and len(c.proposed_rows) == 12


def test_parent_reply_moves_orphan_to_auto_approve(tables, settings):
    run = run_pipeline(tables, settings, parent_replies={84906: "continue_same"})
    c = next(x for x in run["cases"] if x.invoice.id == 84906)
    assert c.decision.value == "AUTO_APPROVE" and len(c.proposed_rows) == 24 and c.proposed_booking_request


def test_shadow_report(tables, settings):
    run = run_pipeline(tables, settings)
    sh = shadow_report(run, tables, settings)
    assert sh["approved_total"] == 4 and sh["agreed"] == 3
    bad = [a for a in sh["approved"] if not a["agree"]]
    assert [a["form_id"] for a in bad] == [3312]
    assert sh["gate"]["open"] is False
    assert sh["removed_wait_hours"] > 0


def test_threshold_changes_counts(tables):
    run = run_pipeline(tables, Settings(stuck_threshold_hours=40))
    assert run["metrics"]["forms_pending_over_threshold"] == 2  # only the 47.5h and 45h forms exceed 40h
