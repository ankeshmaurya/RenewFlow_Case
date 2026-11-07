import pytest

from app.loader import LoadError, load_texts, read_csv_text
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "sample"


def texts():
    return {"invoices": (DATA / "1_invoices.csv").read_text(), "forms": (DATA / "2_faculty_form_unapproved.csv").read_text(),
            "bookings": (DATA / "3_booking_requests.csv").read_text(), "schedule": (DATA / "4_class_schedule_bookings.csv").read_text(),
            "reference": (DATA / "reference_active_batches_and_students.csv").read_text()}


def test_load_sample_counts():
    tables, report = load_texts(texts())
    assert (len(tables.invoices), len(tables.forms), len(tables.bookings), len(tables.schedule), len(tables.reference)) == (13, 12, 4, 2, 13)
    assert report["tables"]["invoices"]["rows"] == 13


def test_null_strings_become_none():
    tables, _ = load_texts(texts())
    failed = next(i for i in tables.invoices if i.id == 84911)
    assert failed.paid_at is None and failed.gateway_payment_id is None


def test_missing_columns_named():
    t = texts()
    t["invoices"] = "id,invoice_number\n1,X\n"
    with pytest.raises(LoadError) as e:
        load_texts(t)
    assert "user_id" in e.value.report["tables"]["invoices"]["missing_columns"]


def test_empty_file_and_missing_table():
    t = texts()
    t["forms"] = ""
    with pytest.raises(LoadError):
        load_texts(t)
    del t["forms"]
    with pytest.raises(LoadError) as e:
        load_texts(t)
    assert "forms" in e.value.report["missing_tables"]


def test_extra_columns_and_bom_tolerated():
    t = texts()
    lines = t["invoices"].splitlines()
    t["invoices"] = "\ufeff" + "\n".join([lines[0] + ",extra_col"] + [ln + ",x" for ln in lines[1:]])
    tables, report = load_texts(t)
    assert len(tables.invoices) == 13 and report["tables"]["invoices"]["extra_columns"] == ["extra_col"]


def test_bad_row_skipped_not_crashing():
    t = texts()
    lines = t["invoices"].splitlines()
    lines.append(lines[1].replace("84901", "notanumber", 1))
    t["invoices"] = "\n".join(lines)
    tables, report = load_texts(t)
    assert report["tables"]["invoices"]["skipped"] == 1 and len(tables.invoices) == 13


def test_read_csv_text_header():
    header, rows = read_csv_text("a,b\n1,2\n")
    assert header == ["a", "b"] and rows == [{"a": "1", "b": "2"}]
