"""In-memory application state. Data lives per process; restart to clear."""
from __future__ import annotations

from datetime import datetime

from .settings import Settings
from .timeutil import IST


class Store:
    def __init__(self):
        self.tables = None
        self.report = {}
        self.settings = Settings()
        self.last_run = None
        self.messages: dict[str, dict] = {}
        self.audit: list[dict] = []
        self.approvals: dict[int, dict] = {}
        self.parent_replies: dict[int, str] = {}
        self.reassign: dict[int, str] = {}
        self.notes: dict[int, list] = {}
        self.remark_intents = None
        self.remark_source = "keyword"

    def reset_workflow(self):
        self.last_run = None
        self.messages, self.approvals, self.parent_replies = {}, {}, {}
        self.reassign, self.notes, self.audit = {}, {}, []
        self.remark_intents, self.remark_source = None, "keyword"

    def log(self, action: str, invoice_id=None, detail: str = "", actor: str = "ops_demo"):
        self.audit.insert(0, dict(at=datetime.now(IST).isoformat(timespec="seconds"), actor=actor, action=action,
                                  invoice_id=invoice_id, detail=detail))


def now_iso() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


STORE = Store()
