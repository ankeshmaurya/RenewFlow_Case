"""Pydantic models: the five source tables plus the engine's case types."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from .timeutil import parse_ist

ISTDateTime = Annotated[Optional[datetime], BeforeValidator(parse_ist)]


class Decision(str, Enum):
    AUTO_APPROVE = "AUTO_APPROVE"
    FAST_TRACK_PENDING_PARENT = "FAST_TRACK_PENDING_PARENT"
    FLAGGED = "FLAGGED"
    BLOCKED = "BLOCKED"
    ALREADY_COMPLETE = "ALREADY_COMPLETE"


class Owner(str, Enum):
    NONE = "NONE"
    PARENT = "PARENT"
    TEACHER = "TEACHER"
    OPS_LEAD = "OPS_LEAD"
    FINANCE_OPS = "FINANCE_OPS"
    SCHEDULING_DESK = "SCHEDULING_DESK"
    DATA_DESK = "DATA_DESK"


class Severity(str, Enum):
    info = "info"
    notice = "notice"
    warn = "warn"
    block = "block"


class Row(BaseModel):
    """Base for CSV rows: NULL and empty strings become None, extra columns are ignored."""

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _nullify(cls, data: Any):
        if isinstance(data, dict):
            out = {}
            for key, value in data.items():
                if isinstance(value, str):
                    value = value.strip()
                    if value in ("", "NULL", "null", "None"):
                        value = None
                out[key] = value
            return out
        return data


class Invoice(Row):
    id: int
    invoice_number: str
    user_id: int
    student_id: int
    class_id: Optional[int] = None
    educator_id: Optional[int] = None
    parent_name: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    currency: Optional[str] = None
    amount: float
    discount_amount: float = 0.0
    net_amount: float
    payment_type: Optional[str] = None
    payment_mode: Optional[str] = None
    payment_gateway: Optional[str] = None
    gateway_order_id: Optional[str] = None
    gateway_payment_id: Optional[str] = None
    invoice_link: Optional[str] = None
    payment_status: str
    is_renewal: str = "Yes"
    paid_at: ISTDateTime = None
    created_at: ISTDateTime = None
    updated_at: ISTDateTime = None
    deleted_at: ISTDateTime = None

    @field_validator("discount_amount", mode="before")
    @classmethod
    def _disc(cls, v):
        return 0.0 if v is None else v


class FacultyForm(Row):
    id: int
    educator_id: Optional[int] = None
    educator_name: Optional[str] = None
    user_id: Optional[int] = None
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    parent_mobile: Optional[str] = None
    class_id: Optional[int] = None
    current_classbatch_id: Optional[int] = None
    invoice_id: Optional[int] = None
    invoice_link: Optional[str] = None
    amount_paid: Optional[float] = None
    sessions_purchased: Optional[int] = None
    continue_same_batch: Optional[str] = None
    preferred_days: Optional[str] = None
    preferred_time_slot: Optional[str] = None
    remarks: Optional[str] = None
    approval_status: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: ISTDateTime = None
    created_at: ISTDateTime = None
    updated_at: ISTDateTime = None
    deleted_at: ISTDateTime = None
    source: str = "teacher"


class BookingRequest(Row):
    id: int
    faculty_form_id: Optional[int] = None
    invoice_id: Optional[int] = None
    user_id: Optional[int] = None
    student_id: Optional[int] = None
    class_id: Optional[int] = None
    educator_id: Optional[int] = None
    classbatch_id: Optional[int] = None
    sessions_count: Optional[int] = None
    is_renewal: Optional[str] = None
    continue_same_batch: Optional[str] = None
    preferred_days: Optional[str] = None
    preferred_time: Optional[str] = None
    request_status: Optional[str] = None
    batch_allocated: Optional[str] = None
    allocated_by: Optional[str] = None
    allocated_at: ISTDateTime = None
    created_at: ISTDateTime = None
    updated_at: ISTDateTime = None
    deleted_at: ISTDateTime = None


class ScheduleRow(Row):
    id: int
    bookingrequest_id: Optional[int] = None
    invoice_id: Optional[int] = None
    classschedule_id: Optional[int] = None
    classbatch_id: Optional[int] = None
    class_id: Optional[int] = None
    user_id: Optional[int] = None
    student_id: Optional[int] = None
    educator_id: Optional[int] = None
    class_date: Optional[date] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    booking_type: Optional[str] = None
    is_cancelled: Optional[str] = None
    attended_class: Optional[str] = None
    created_at: ISTDateTime = None
    updated_at: ISTDateTime = None
    deleted_at: ISTDateTime = None


class Reference(Row):
    student_id: int
    user_id: int
    student_name_masked: Optional[str] = None
    parent_name_masked: Optional[str] = None
    registered_mobile_masked: Optional[str] = None
    registered_email_masked: Optional[str] = None
    current_classbatch_id: Optional[int] = None
    classbatch_name: Optional[str] = None
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    educator_id: Optional[int] = None
    educator_name: Optional[str] = None
    standard_fee_24_sessions_inr: Optional[float] = None
    batch_days: Optional[str] = None
    batch_start_time: Optional[str] = None
    active_students_count: Optional[int] = None
    max_batch_size: Optional[int] = None
    deleted_at: ISTDateTime = None


@dataclass
class Tables:
    invoices: list = field(default_factory=list)
    forms: list = field(default_factory=list)
    bookings: list = field(default_factory=list)
    schedule: list = field(default_factory=list)
    reference: list = field(default_factory=list)


class CaseCheck(BaseModel):
    code: str
    name: str
    stage: str  # LINK, PAYMENT, IDENTITY, AMOUNT, BATCH, DOWNSTREAM, REMARKS
    severity: Severity
    passed: bool
    detail: str = ""


class InvoiceCase(BaseModel):
    invoice: Invoice
    reference: Optional[Reference] = None
    forms: list[FacultyForm] = Field(default_factory=list)
    primary_form_id: Optional[int] = None
    suppressed_form_ids: list[int] = Field(default_factory=list)
    healed_from_form_id: Optional[int] = None
    healed_typed_invoice_id: Optional[int] = None
    booking: Optional[BookingRequest] = None
    schedule_rows: list[ScheduleRow] = Field(default_factory=list)
    checks: list[CaseCheck] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    healed_actions: list[str] = Field(default_factory=list)
    decision: Optional[Decision] = None
    owner: Owner = Owner.NONE
    recommended_action: str = ""
    next_steps: list[str] = Field(default_factory=list)
    sla: dict = Field(default_factory=dict)
    steps: dict = Field(default_factory=dict)
    proposed_rows: list[dict] = Field(default_factory=list)
    proposed_booking_request: Optional[dict] = None
    alternatives: list[dict] = Field(default_factory=list)
    diffs: list[dict] = Field(default_factory=list)
    remark_intents: dict = Field(default_factory=dict)
    provisional: bool = False

    @property
    def primary_form(self) -> Optional[FacultyForm]:
        for f in self.forms:
            if f.id == self.primary_form_id:
                return f
        return None

    def add(self, check: CaseCheck):
        self.checks.append(check)
