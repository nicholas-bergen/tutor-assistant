from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints

DisplayName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        strict=True,
    ),
]

DashboardMeetingId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=255,
        strict=True,
    ),
]


class Student(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    student_id: UUID
    display_name: DisplayName


class Lesson(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    lesson_id: UUID
    student_id: UUID
    dashboard_meeting_id: DashboardMeetingId | None = None
    scheduled_start_at: AwareDatetime
