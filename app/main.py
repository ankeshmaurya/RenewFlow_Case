"""RenewFlow API (FastAPI). Run with: uvicorn app.main:app --reload"""
from __future__ import annotations

import io
import json
import os
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import exports
from .engine.codes import CATALOG
from .engine.pipeline import run_pipeline, run_stage1
from .engine.selftest import run_selftest, shadow_report
from .llm import client as llm_client
from .llm.brief import build_brief
from .llm.messages import build_messages
from .llm.remarks import extract_all
from .loader import LoadError, load_folder, load_texts, summarize
from .models import Decision
from .settings import Settings
from .store import STORE, now_iso

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "sample"
STATIC_DIR = ROOT / "static"

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Optional: set RENEWFLOW_AUTOLOAD=1 to load the sample data at startup."""
    if os.getenv("RENEWFLOW_AUTOLOAD") == "1":
        try:
            tables, report = load_folder(DATA_DIR)
            _install(tables, report)
        except LoadError:
            pass
    yield


app = FastAPI(title="RenewFlow", version="1.0.0", lifespan=lifespan,
              description="Reconciliation and auto-approval engine for the student renewal to class scheduling pipeline.")


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": f"{type(exc).__name__}: {exc}"})


# ----------------------------------------------------------------------------- helpers
def need_tables():
    if STORE.tables is None:
        raise HTTPException(status_code=409, detail="No data loaded. Load the sample data or upload the 5 CSV files first.")
    return STORE.tables


def need_run():
    need_tables()
    if STORE.last_run is None:
        compute_run()
    return STORE.last_run


def compute_run(intents=None):
    run = run_pipeline(STORE.tables, STORE.settings, STORE.parent_replies, intents if intents is not None else STORE.remark_intents)
    STORE.last_run = run
    return run


def case_dict(case) -> dict:
    d = case.model_dump(mode="json")
    iid = case.invoice.id
    ap = STORE.approvals.get(iid)
    d["approved"] = ap if (ap and case.decision == Decision.AUTO_APPROVE) else None
    d["owner_override"] = STORE.reassign.get(iid)
    d["display_owner"] = STORE.reassign.get(iid) or case.owner.value
    d["notes"] = STORE.notes.get(iid, [])
    d["parent_replied"] = iid in STORE.parent_replies
    return d


def find_case(invoice_id: int):
    run = need_run()
    for c in run["cases"]:
        if c.invoice.id == invoice_id:
            return c
    raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")


def results_payload() -> dict:
    run = need_run()
    return dict(as_of=run["as_of"], generated_at=run["generated_at"], settings=run["settings"], metrics=run["metrics"],
                orphan_forms=run["orphan_forms"], cases=[case_dict(c) for c in run["cases"]],
                llm=dict(enabled=STORE.settings.use_llm, key_present=llm_client.available(), model=llm_client.model_name(),
                         remark_source=STORE.remark_source))


# ----------------------------------------------------------------------------- health and data
@app.get("/api/health")
def health():
    return dict(status="ok", data_loaded=STORE.tables is not None, gemini_key_present=llm_client.available(),
                model=llm_client.model_name())


def _install(tables, report):
    STORE.tables, STORE.report = tables, report
    STORE.reset_workflow()
    compute_run()
    STORE.log("data_loaded", detail=", ".join(f"{k}={len(getattr(tables, k))}" for k in report["tables"]))


@app.post("/api/data/load-sample")
def load_sample():
    try:
        tables, report = load_folder(DATA_DIR)
    except LoadError as e:
        raise HTTPException(status_code=422, detail=e.report)
    _install(tables, report)
    return summarize(tables, report)


class UploadBody(BaseModel):
    invoices: str
    forms: str
    bookings: str
    schedule: str
    reference: str


@app.post("/api/data/upload")
def upload(body: UploadBody):
    try:
        tables, report = load_texts(body.model_dump())
    except LoadError as e:
        raise HTTPException(status_code=422, detail=e.report)
    _install(tables, report)
    return summarize(tables, report)


@app.get("/api/data/summary")
def data_summary():
    if STORE.tables is None:
        return dict(loaded=False)
    return summarize(STORE.tables, STORE.report)


@app.get("/api/data/preview/{table}")
def data_preview(table: str, limit: int = 10):
    tables = need_tables()
    if table not in ("invoices", "forms", "bookings", "schedule", "reference"):
        raise HTTPException(status_code=404, detail="Unknown table")
    rows = getattr(tables, table)[:max(1, min(limit, 50))]
    return dict(table=table, rows=[r.model_dump(mode="json") for r in rows])


@app.get("/api/settings")
def get_settings():
    return STORE.settings.model_dump()


@app.put("/api/settings")
def put_settings(body: dict):
    merged = STORE.settings.model_dump()
    for k, v in body.items():
        if k == "assumptions" and isinstance(v, dict):
            merged["assumptions"].update(v)
        else:
            merged[k] = v
    try:
        STORE.settings = Settings(**merged)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid settings: {e}")
    return STORE.settings.model_dump()


@app.post("/api/settings/reset")
def reset_settings():
    STORE.settings = Settings()
    return STORE.settings.model_dump()


@app.get("/api/codes")
def codes():
    return CATALOG


# ----------------------------------------------------------------------------- engine
@app.get("/api/debug/stage1")
def debug_stage1():
    tables = need_tables()
    cases, orphan_forms = run_stage1(tables, STORE.settings, STORE.parent_replies)
    return dict(orphan_forms=orphan_forms, cases=[dict(
        invoice_id=c.invoice.id, forms=[f.id for f in c.forms], primary_form=c.primary_form_id, suppressed=c.suppressed_form_ids,
        healed_from_form=c.healed_from_form_id, booking=c.booking.id if c.booking else None,
        failed_checks=[dict(code=k.code, severity=k.severity.value, detail=k.detail) for k in c.checks if not k.passed])
        for c in cases])


class ReconcileBody(BaseModel):
    use_llm: Optional[bool] = None


@app.post("/api/reconcile")
async def reconcile(body: Optional[ReconcileBody] = None):
    tables = need_tables()
    use = STORE.settings.use_llm if (body is None or body.use_llm is None) else body.use_llm
    intents, source = None, "keyword"
    if use and llm_client.available():
        forms = [f for f in tables.forms if f.deleted_at is None]
        intents, sources = await extract_all(forms)
        source = "gemini" if "gemini" in sources.values() else "keyword"
    STORE.remark_intents, STORE.remark_source = intents, source
    run = compute_run(intents)
    STORE.log("reconcile", detail=f"remarks via {source}; {len(run['cases'])} invoices")
    return dict(ok=True, remark_source=source, decision_counts=run["metrics"]["decision_counts"], generated_at=run["generated_at"])


@app.get("/api/results")
def results():
    return results_payload()


@app.get("/api/results/{invoice_id}")
def result_one(invoice_id: int):
    c = find_case(invoice_id)
    d = case_dict(c)
    d["messages"] = [m for m in STORE.messages.values() if m["invoice_id"] == invoice_id]
    return d


@app.get("/api/metrics")
def metrics():
    return need_run()["metrics"]


@app.get("/api/selftest")
def selftest():
    return run_selftest(need_tables())


@app.get("/api/shadow")
def shadow():
    need_run()
    return shadow_report(STORE.last_run, STORE.tables, STORE.settings)


# ----------------------------------------------------------------------------- case actions
@app.post("/api/cases/{invoice_id}/approve")
def approve_case(invoice_id: int):
    c = find_case(invoice_id)
    if c.decision != Decision.AUTO_APPROVE:
        raise HTTPException(status_code=409, detail="Only AUTO_APPROVE cases can be approved here.")
    STORE.approvals[invoice_id] = dict(by="ops_demo", at=now_iso())
    STORE.log("approve", invoice_id, f"{len(c.proposed_rows)} proposed rows approved (simulated)")
    return case_dict(c)


@app.post("/api/approve-all")
def approve_all():
    run = need_run()
    n = 0
    for c in run["cases"]:
        if c.decision == Decision.AUTO_APPROVE and c.invoice.id not in STORE.approvals:
            STORE.approvals[c.invoice.id] = dict(by="ops_demo", at=now_iso())
            n += 1
    STORE.log("approve_all", detail=f"{n} cases approved (simulated)")
    return dict(approved=n)


@app.post("/api/cases/{invoice_id}/parent-reply")
def parent_reply(invoice_id: int):
    c = find_case(invoice_id)
    if c.decision != Decision.FAST_TRACK_PENDING_PARENT:
        raise HTTPException(status_code=409, detail="This case is not waiting on a parent reply.")
    STORE.parent_replies[invoice_id] = "continue_same"
    run = compute_run()
    STORE.log("parent_reply", invoice_id, "Parent replied 'continue same batch' (simulated); case re-run")
    for m in [k for k, v in STORE.messages.items() if v["invoice_id"] == invoice_id and v["status"] == "draft"]:
        del STORE.messages[m]
    return case_dict(next(x for x in run["cases"] if x.invoice.id == invoice_id))


class OwnerBody(BaseModel):
    owner: str


class NoteBody(BaseModel):
    text: str


@app.post("/api/cases/{invoice_id}/reassign")
def reassign(invoice_id: int, body: OwnerBody):
    c = find_case(invoice_id)
    STORE.reassign[invoice_id] = body.owner
    STORE.log("reassign", invoice_id, f"{c.owner.value} to {body.owner}")
    return case_dict(c)


@app.post("/api/cases/{invoice_id}/note")
def add_note(invoice_id: int, body: NoteBody):
    c = find_case(invoice_id)
    STORE.notes.setdefault(invoice_id, []).insert(0, dict(text=body.text, by="ops_demo", at=now_iso()))
    STORE.log("note", invoice_id, body.text[:140])
    return case_dict(c)


@app.get("/api/audit")
def audit():
    return STORE.audit


# ----------------------------------------------------------------------------- messages and brief
class GenBody(BaseModel):
    invoice_id: Optional[int] = None
    language: str = "English"
    use_llm: Optional[bool] = None


@app.post("/api/messages/generate")
async def generate_messages(body: Optional[GenBody] = None):
    body = body or GenBody()
    run = need_run()
    use = STORE.settings.use_llm if body.use_llm is None else body.use_llm
    cases = [c for c in run["cases"] if body.invoice_id is None or c.invoice.id == body.invoice_id]
    new = await build_messages(cases, body.language, use)
    keep = {k: v for k, v in STORE.messages.items()
            if (v["status"] != "draft" or v.get("edited")) or (body.invoice_id is not None and v["invoice_id"] != body.invoice_id)}
    STORE.messages = dict(keep)
    for m in new:
        if m["id"] in keep and (keep[m["id"]]["status"] != "draft" or keep[m["id"]].get("edited")):
            continue
        STORE.messages[m["id"]] = m
    STORE.log("messages_generated", body.invoice_id, f"{len(new)} messages, language {body.language}")
    return list(STORE.messages.values())


@app.get("/api/messages")
def list_messages():
    return list(STORE.messages.values())


class StatusBody(BaseModel):
    status: str


class EditBody(BaseModel):
    body: str


@app.post("/api/messages/{message_id}/status")
def message_status(message_id: str, body: StatusBody):
    m = STORE.messages.get(message_id)
    if not m:
        raise HTTPException(status_code=404, detail="Message not found")
    if body.status not in ("draft", "approved", "sent-simulated"):
        raise HTTPException(status_code=422, detail="Invalid status")
    m["status"] = body.status
    STORE.log("message_" + body.status, m["invoice_id"], message_id)
    return m


@app.put("/api/messages/{message_id}")
def message_edit(message_id: str, body: EditBody):
    m = STORE.messages.get(message_id)
    if not m:
        raise HTTPException(status_code=404, detail="Message not found")
    m["body"], m["edited"] = body.body, True
    return m


@app.post("/api/messages/{message_id}/regenerate")
async def message_regenerate(message_id: str, body: Optional[GenBody] = None):
    body = body or GenBody()
    m = STORE.messages.get(message_id)
    if not m:
        raise HTTPException(status_code=404, detail="Message not found")
    run = need_run()
    case = next(c for c in run["cases"] if c.invoice.id == m["invoice_id"])
    use = STORE.settings.use_llm if body.use_llm is None else body.use_llm
    fresh = next((x for x in await build_messages([case], body.language, use) if x["id"] == message_id), None)
    if fresh:
        fresh["status"] = "draft"
        STORE.messages[message_id] = fresh
    return STORE.messages[message_id]


@app.post("/api/brief")
async def brief(body: Optional[ReconcileBody] = None):
    run = need_run()
    use = STORE.settings.use_llm if (body is None or body.use_llm is None) else body.use_llm
    return await build_brief(run["metrics"], run["cases"], use)


# ----------------------------------------------------------------------------- exports
def auto_approved_csv() -> str:
    return exports.auto_approved_csv(need_run()["cases"])


def exceptions_csv() -> str:
    return exports.exceptions_csv(need_run()["cases"], STORE.reassign)


def _download(content: str, name: str, media: str) -> Response:
    return Response(content=content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/export/auto-approved.csv")
def export_auto():
    return _download(auto_approved_csv(), "auto-approved.csv", "text/csv")


@app.get("/api/export/exceptions.csv")
def export_exceptions():
    return _download(exceptions_csv(), "exceptions.csv", "text/csv")


@app.get("/api/export/messages.json")
def export_messages():
    return _download(json.dumps(list(STORE.messages.values()), indent=2), "messages.json", "application/json")


@app.get("/api/export/full-results.json")
def export_full():
    return _download(json.dumps(results_payload(), indent=2, default=str), "full-results.json", "application/json")


@app.get("/api/export/bundle.zip")
def export_bundle():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("full-results.json", json.dumps(results_payload(), indent=2, default=str))
        z.writestr("auto-approved.csv", auto_approved_csv())
        z.writestr("exceptions.csv", exceptions_csv())
        z.writestr("messages.json", json.dumps(list(STORE.messages.values()), indent=2))
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="renewflow-results-bundle.zip"'})


# ----------------------------------------------------------------------------- static frontend
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")
