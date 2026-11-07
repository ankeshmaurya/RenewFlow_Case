"""CSV loading and validation using only the standard csv module."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from pydantic import ValidationError

from .models import BookingRequest, FacultyForm, Invoice, Reference, ScheduleRow, Tables

TABLE_SPECS = {
    "invoices": (Invoice, ["1_invoices.csv", "invoices.csv"],
                 {"id", "invoice_number", "user_id", "student_id", "amount", "net_amount", "payment_status"}),
    "forms": (FacultyForm, ["2_faculty_form_unapproved.csv", "faculty_form_unapproved.csv"],
              {"id", "invoice_id", "user_id", "student_id", "amount_paid", "continue_same_batch", "approval_status"}),
    "bookings": (BookingRequest, ["3_booking_requests.csv", "booking_requests.csv"],
                 {"id", "invoice_id", "request_status"}),
    "schedule": (ScheduleRow, ["4_class_schedule_bookings.csv", "class_schedule_bookings.csv"],
                 {"id", "invoice_id", "class_date"}),
    "reference": (Reference, ["reference_active_batches_and_students.csv"],
                  {"student_id", "user_id", "current_classbatch_id", "batch_days", "batch_start_time",
                   "standard_fee_24_sessions_inr"}),
}


class LoadError(Exception):
    def __init__(self, report: dict):
        super().__init__("Data could not be loaded")
        self.report = report


def read_csv_text(text: str) -> tuple[list[str], list[dict]]:
    text = text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(text))
    rows = [dict(r) for r in reader]
    return list(reader.fieldnames or []), rows


def parse_table(name: str, text: str) -> tuple[list, dict]:
    model, _files, required = TABLE_SPECS[name]
    info = {"rows": 0, "skipped": 0, "missing_columns": [], "extra_columns": [], "null_counts": {}, "errors": []}
    if not text or not text.strip():
        info["errors"].append("File is empty")
        return [], info
    header, raw_rows = read_csv_text(text)
    known = set(model.model_fields.keys())
    info["missing_columns"] = sorted(required - set(header))
    info["extra_columns"] = sorted(set(header) - known)
    if info["missing_columns"]:
        info["errors"].append("Missing required columns: " + ", ".join(info["missing_columns"]))
        return [], info
    nulls = {c: 0 for c in header}
    parsed = []
    for i, raw in enumerate(raw_rows, start=2):
        for col in header:
            v = raw.get(col)
            if v is None or v.strip() in ("", "NULL"):
                nulls[col] += 1
        try:
            parsed.append(model(**raw))
        except (ValidationError, ValueError, TypeError) as exc:
            info["skipped"] += 1
            info["errors"].append(f"Row {i}: {str(exc).splitlines()[0][:140]}")
    info["rows"] = len(parsed)
    info["null_counts"] = {c: n for c, n in nulls.items() if n}
    return parsed, info


def load_texts(texts: dict) -> tuple[Tables, dict]:
    """texts: {table_name: csv_text}. Raises LoadError when anything is unusable."""
    missing_tables = [n for n in TABLE_SPECS if n not in texts]
    report = {"tables": {}, "missing_tables": missing_tables}
    if missing_tables:
        raise LoadError({**report, "message": "Missing tables: " + ", ".join(missing_tables)})
    tables = Tables()
    problems = []
    for name in TABLE_SPECS:
        rows, info = parse_table(name, texts[name])
        report["tables"][name] = info
        setattr(tables, name, rows)
        if info["missing_columns"] or (not rows and info["errors"]):
            problems.append(f"{name}: " + "; ".join(info["errors"][:2]))
    if problems:
        raise LoadError({**report, "message": " | ".join(problems)})
    return tables, report


def load_folder(folder) -> tuple[Tables, dict]:
    folder = Path(folder)
    texts = {}
    for name, (_m, files, _r) in TABLE_SPECS.items():
        for fname in files:
            p = folder / fname
            if p.exists():
                texts[name] = p.read_text(encoding="utf-8")
                break
    return load_texts(texts)


def summarize(tables: Tables, report: dict) -> dict:
    stamps = []
    for rows in (tables.invoices, tables.forms, tables.bookings, tables.schedule):
        stamps += [r.created_at for r in rows if getattr(r, "created_at", None)]
    return {
        "loaded": True,
        "counts": {n: len(getattr(tables, n)) for n in TABLE_SPECS},
        "date_range": {"from": min(stamps).isoformat() if stamps else None,
                       "to": max(stamps).isoformat() if stamps else None},
        "tables": report.get("tables", {}),
    }
