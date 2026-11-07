from app.engine.pipeline import run_stage1


def by_inv(cases):
    return {c.invoice.id: c for c in cases}


def test_typo_healed_and_text_normalized(tables, settings):
    cases, orphan_forms = run_stage1(tables, settings)
    c = by_inv(cases)[84913]
    assert c.healed_from_form_id == 3313 and c.healed_typed_invoice_id == 84931
    assert "LINK_ID_TYPO_HEALED" in [k.code for k in c.checks if not k.passed]
    assert "DATA_TEXT_NORMALIZED" in [k.code for k in c.checks if not k.passed]
    assert orphan_forms == []


def test_duplicate_suppressed(tables, settings):
    cases, _ = run_stage1(tables, settings)
    c = by_inv(cases)[84908]
    assert c.primary_form_id == 3308 and c.suppressed_form_ids == [3309]


def test_orphan_invoices_and_payment_gate(tables, settings):
    cases, _ = run_stage1(tables, settings)
    d = by_inv(cases)
    failed = lambda c: [k.code for k in c.checks if not k.passed]  # noqa: E731
    assert "LINK_ORPHAN_INVOICE" in failed(d[84906]) and "LINK_ORPHAN_INVOICE" in failed(d[84910])
    assert "PAY_NOT_CONFIRMED" in failed(d[84911])
    assert "PAY_PARTIAL" in failed(d[84909])
    assert "ID_PAYER_MISMATCH" in failed(d[84904])


def test_stage1_flags_nothing_else(tables, settings):
    cases, _ = run_stage1(tables, settings)
    clean = [84901, 84902, 84903, 84905, 84907, 84912]
    for iid in clean:
        assert [k.code for k in by_inv(cases)[iid].checks if not k.passed] == [], iid


def test_unrelated_form_is_not_healed(tables, settings):
    from app.models import FacultyForm
    from app.engine.link import resolve_forms
    invoices = [i for i in tables.invoices]
    bad = FacultyForm(id=1, user_id=1, student_id=2, invoice_id=99999, amount_paid=5, approval_status="Pending")
    _, healed, orphans, _ = resolve_forms(invoices, [bad])
    assert not healed and len(orphans) == 1
