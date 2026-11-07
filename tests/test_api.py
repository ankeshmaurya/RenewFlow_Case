import json

from fastapi.testclient import TestClient

from app.main import app
from app.store import STORE
from app.settings import Settings

client = TestClient(app)


def fresh():
    STORE.tables = None
    STORE.reset_workflow()
    STORE.settings = Settings()


def load():
    r = client.post("/api/data/load-sample")
    assert r.status_code == 200
    return r.json()


def test_no_data_gives_clear_409():
    fresh()
    r = client.get("/api/results")
    assert r.status_code == 409 and "Load the sample" in r.json()["detail"]
    assert client.get("/api/data/summary").json() == {"loaded": False}


def test_load_results_selftest():
    fresh()
    assert load()["counts"]["invoices"] == 13
    res = client.get("/api/results").json()
    assert len(res["cases"]) == 13 and res["metrics"]["paid_unscheduled_value_inr"] == 126850
    assert client.get("/api/selftest").json()["passed"] is True
    one = client.get("/api/results/84913").json()
    assert one["healed_from_form_id"] == 3313 and one["decision"] == "AUTO_APPROVE"
    assert client.get("/api/results/1").status_code == 404


def test_approve_all_and_parent_reply_flow():
    fresh(); load()
    assert client.post("/api/approve-all").json()["approved"] == 6
    assert client.post("/api/approve-all").json()["approved"] == 0
    assert client.post("/api/cases/84903/parent-reply").status_code == 409
    r = client.post("/api/cases/84906/parent-reply")
    assert r.status_code == 200 and r.json()["decision"] == "AUTO_APPROVE" and len(r.json()["proposed_rows"]) == 24
    lines = client.get("/api/export/auto-approved.csv").text.strip().splitlines()
    assert len(lines) == 1 + 7 * 24
    assert lines[0].startswith("id,bookingrequest_id,invoice_id,classschedule_id") and lines[0].endswith("classschedule_lookup_key")


def test_exports_and_bundle():
    fresh(); load()
    exc = client.get("/api/export/exceptions.csv")
    assert exc.headers["content-disposition"].startswith("attachment") and exc.text.splitlines()[0].startswith("invoice_id,decision")
    assert len(exc.text.strip().splitlines()) == 1 + 6  # 3 flagged, 1 blocked, 2 waiting on parent
    z = client.get("/api/export/bundle.zip")
    assert z.status_code == 200 and z.content[:2] == b"PK"
    assert isinstance(json.loads(client.get("/api/export/full-results.json").text)["cases"], list)


def test_settings_validation_and_reconcile_policy():
    fresh(); load()
    assert client.put("/api/settings", json={"stuck_threshold_hours": "abc"}).status_code == 422
    client.put("/api/settings", json={"partial_payment_policy": "PROVISIONAL_PRO_RATA"})
    assert client.post("/api/reconcile", json={"use_llm": False}).json()["ok"]
    c = client.get("/api/results/84909").json()
    assert c["decision"] == "AUTO_APPROVE" and c["provisional"]
    client.post("/api/settings/reset")


def test_messages_flow():
    fresh(); load()
    msgs = client.post("/api/messages/generate", json={"use_llm": False}).json()
    assert len(msgs) >= 20
    mid = msgs[0]["id"]
    assert client.put(f"/api/messages/{mid}", json={"body": "edited"}).json()["edited"]
    assert client.post(f"/api/messages/{mid}/status", json={"status": "sent-simulated"}).json()["status"] == "sent-simulated"
    assert client.post(f"/api/messages/{mid}/status", json={"status": "nonsense"}).status_code == 422
    again = client.post("/api/messages/generate", json={"use_llm": False}).json()
    assert next(m for m in again if m["id"] == mid)["status"] == "sent-simulated"
    r = client.post(f"/api/messages/{mid}/regenerate", json={"use_llm": False, "language": "Hindi"})
    assert r.status_code == 200
    assert client.get("/api/results/84911").json()["messages"]


def test_upload_missing_columns_is_422_with_names():
    fresh()
    body = {k: "id\n1\n" for k in ("invoices", "forms", "bookings", "schedule", "reference")}
    r = client.post("/api/data/upload", json=body)
    assert r.status_code == 422
    assert "invoice_number" in json.dumps(r.json())


def test_shadow_brief_audit_and_static():
    fresh(); load()
    assert client.get("/api/shadow").json()["agreed"] == 3
    assert len(client.post("/api/brief", json={}).json()["lines"]) == 5
    client.post("/api/cases/84907/note", json={"text": "approved by ops lead"})
    client.post("/api/cases/84907/reassign", json={"owner": "FINANCE_OPS"})
    assert client.get("/api/results/84907").json()["display_owner"] == "FINANCE_OPS"
    assert any(a["action"] == "note" for a in client.get("/api/audit").json())
    assert client.get("/").status_code == 200 and "RenewFlow" in client.get("/").text
    assert client.get("/static/js/app.js").status_code == 200
    assert client.get("/docs").status_code == 200
