import time

from app.engine.pipeline import run_pipeline
from app.models import Tables
from app.settings import Settings


def replicate(tables, k):
    out = Tables()
    for n in range(k):
        o = n * 1_000_000
        for i in tables.invoices:
            out.invoices.append(i.model_copy(update=dict(id=i.id + o, invoice_number=f"{i.invoice_number}-{n}", user_id=i.user_id + o,
                                                          student_id=i.student_id + o)))
        for f in tables.forms:
            out.forms.append(f.model_copy(update=dict(id=f.id + o, invoice_id=(f.invoice_id + o) if f.invoice_id else None,
                                                      user_id=f.user_id + o, student_id=f.student_id + o,
                                                      current_classbatch_id=(f.current_classbatch_id + o) if f.current_classbatch_id else None)))
        for b in tables.bookings:
            out.bookings.append(b.model_copy(update=dict(id=b.id + o, invoice_id=b.invoice_id + o, faculty_form_id=b.faculty_form_id + o,
                                                         user_id=b.user_id + o, student_id=b.student_id + o,
                                                         classbatch_id=(b.classbatch_id + o) if b.classbatch_id else None)))
        for s in tables.schedule:
            out.schedule.append(s.model_copy(update=dict(id=s.id + o, invoice_id=s.invoice_id + o, bookingrequest_id=s.bookingrequest_id + o)))
        for r in tables.reference:
            out.reference.append(r.model_copy(update=dict(student_id=r.student_id + o, user_id=r.user_id + o,
                                                          current_classbatch_id=r.current_classbatch_id + o)))
    return out


def test_5000_rows_stay_linear(tables):
    big = replicate(tables, 385)  # 5,005 invoices
    assert len(big.invoices) == 5005
    t0 = time.time()
    run = run_pipeline(big, Settings())
    elapsed = time.time() - t0
    assert elapsed < 15, f"took {elapsed:.1f}s"
    dc = run["metrics"]["decision_counts"]
    assert dc["AUTO_APPROVE"] == 6 * 385 and dc["FLAGGED"] == 3 * 385 and dc["BLOCKED"] == 385
