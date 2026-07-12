"""Director role extraction target: appointment/cessation/interest notices.

The purpose is name→role resolution (was this seller an executive?), so the
schema is deliberately small: one RoleEvent per person mentioned with a
stated role. Verification target for the LLM-knowledge role enrichment of
2026-07-10 — extraction from primary documents outranks model memory.
"""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class RoleAction(StrEnum):
    APPOINTED = "appointed"
    CEASED = "ceased"
    SERVING = "serving"  # document states the role without a change event


class RoleEvent(BaseModel):
    person_name: str = Field(min_length=1)
    # Verbatim title: "Managing Director", "Non-Executive Director", "CFO"...
    role: str = Field(min_length=1)
    action: RoleAction
    effective_date: date | None = None


class RolesResult(BaseModel):
    events: list[RoleEvent]
