"""Settings with defaults. All thresholds are editable from the UI."""
from typing import Literal

from pydantic import BaseModel, Field

from .timeutil import parse_ist


class Assumptions(BaseModel):
    renewals_per_week: int = 400
    manual_minutes: float = 18.0
    teacher_form_minutes: float = 4.0
    mix_auto: float = 0.60
    mix_parent: float = 0.25
    mix_exception: float = 0.15
    minutes_auto: float = 0.5
    minutes_parent: float = 2.0
    minutes_exception: float = 15.0


class Settings(BaseModel):
    as_of: str = "2026-11-04T09:00:00+05:30"
    stuck_threshold_hours: float = 12.0
    form_target_hours: float = 2.0
    approval_target_hours: float = 1.0
    allocation_target_hours: float = 0.5
    schedule_target_hours: float = 4.0
    session_minutes: int = 50
    sessions_default: int = 24
    partial_payment_policy: Literal["HOLD", "PROVISIONAL_PRO_RATA"] = "HOLD"
    use_llm: bool = True
    assumptions: Assumptions = Field(default_factory=Assumptions)

    @property
    def as_of_dt(self):
        return parse_ist(self.as_of)
