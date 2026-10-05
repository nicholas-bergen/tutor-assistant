from datetime import date
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]


class SourcePayload(BaseModel):
    """Known source fields with lossless preservation of new upstream fields."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)


class RestrictedContactInformation(SourcePayload):
    email: NonBlankText | None = None
    phone_numbers: list[NonBlankText] = Field(default_factory=list)
    address: NonBlankText | None = None
    time_zone: NonBlankText | None = None


class DashboardStudentProfilePayload(SourcePayload):
    display_name: NonBlankText
    graduation_year: int
    student_personality: NonBlankText | None = None
    general_goals: NonBlankText | None = None
    family_life: NonBlankText | None = None
    learning_style: NonBlankText | None = None
    extracurriculars: list[NonBlankText] = Field(default_factory=list)
    current_academics: list[NonBlankText] = Field(default_factory=list)
    prior_test_preparation: NonBlankText | None = None
    colleges_of_interest: list[NonBlankText] = Field(default_factory=list)
    additional_interests: list[NonBlankText] = Field(default_factory=list)
    contact: RestrictedContactInformation | None = None


AccommodationStatus = Literal["standard_time", "extended_time_50", "not_recorded"]


class DashboardTestPlanPayload(SourcePayload):
    student_external_id: NonBlankText
    test_type: Literal["SAT", "ACT"]
    target_tests: list[date]
    default_accommodation: AccommodationStatus
    proctor_notes: NonBlankText | None = None
    online_testing: bool | None = None


class DashboardTestResultPayload(SourcePayload):
    student_external_id: NonBlankText
    test_date: date
    test_name: NonBlankText
    accommodation: AccommodationStatus
    is_official: bool
    score: int = Field(ge=400, le=1600)
    math_score: int = Field(ge=200, le=800)
    reading_writing_score: int = Field(ge=200, le=800)
    dashboard_reported_percentile: float | None = Field(default=None, ge=0, le=100)
    dashboard_reported_superscore: int | None = Field(default=None, ge=400, le=1600)


class DashboardIntakeNotePayload(SourcePayload):
    student_external_id: NonBlankText
    posted_to: NonBlankText
    author_display_name: NonBlankText
    body: NonBlankText
    supersedes_external_id: NonBlankText | None = None


class DashboardLessonRecordPayload(SourcePayload):
    student_external_id: NonBlankText
    scheduled_start_at: AwareDatetime
    duration_minutes: int = Field(gt=0, le=480)
    status: Literal["scheduled", "complete", "cancelled"]
    subjects: list[NonBlankText]
    coach_display_name: NonBlankText
    content_and_concepts: list[NonBlankText] = Field(default_factory=list)
    noteworthy_information: NonBlankText | None = None
    homework: list[NonBlankText] = Field(default_factory=list)


class GranolaMeetingPayload(SourcePayload):
    title: NonBlankText
    participant_display_names: list[NonBlankText]
    started_at: AwareDatetime
    ended_at: AwareDatetime
    transcript_file: NonBlankText
    transcript_sha256: Annotated[
        str,
        StringConstraints(pattern=r"^[0-9a-f]{64}$", strict=True),
    ]

    @model_validator(mode="after")
    def validate_meeting_times(self) -> "GranolaMeetingPayload":
        if self.ended_at <= self.started_at:
            raise ValueError("ended_at must be after started_at")
        return self


class LessonSummaryDraftPayload(SourcePayload):
    dashboard_lesson_external_id: NonBlankText
    granola_meeting_external_id: NonBlankText
    model_name: NonBlankText
    noteworthy_information: NonBlankText
    homework: list[NonBlankText]


class ReviewedLessonSummaryPayload(SourcePayload):
    dashboard_lesson_external_id: NonBlankText
    draft_external_id: NonBlankText
    reviewer_display_name: NonBlankText
    noteworthy_information: NonBlankText
    homework: list[NonBlankText]


class AiSafeStudentProfile(BaseModel):
    """Academic profile fields approved for AI and retrieval workflows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: NonBlankText
    graduation_year: int
    student_personality: NonBlankText | None = None
    general_goals: NonBlankText | None = None
    learning_style: NonBlankText | None = None
    extracurriculars: list[NonBlankText] = Field(default_factory=list)
    current_academics: list[NonBlankText] = Field(default_factory=list)
    prior_test_preparation: NonBlankText | None = None
    colleges_of_interest: list[NonBlankText] = Field(default_factory=list)
    additional_interests: list[NonBlankText] = Field(default_factory=list)


def build_ai_safe_student_profile(
    source: DashboardStudentProfilePayload,
) -> AiSafeStudentProfile:
    """Project an untrusted profile through an explicit academic-field allowlist."""

    return AiSafeStudentProfile.model_validate(
        {
            "display_name": source.display_name,
            "graduation_year": source.graduation_year,
            "student_personality": source.student_personality,
            "general_goals": source.general_goals,
            "learning_style": source.learning_style,
            "extracurriculars": source.extracurriculars,
            "current_academics": source.current_academics,
            "prior_test_preparation": source.prior_test_preparation,
            "colleges_of_interest": source.colleges_of_interest,
            "additional_interests": source.additional_interests,
        }
    )


class SourceEnvelope[PayloadT: SourcePayload](BaseModel):
    """Strict provenance shared by every captured external source record."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    source_system: Literal["dashboard", "granola", "generated"]
    source_record_type: NonBlankText
    external_id: NonBlankText
    event_at: AwareDatetime
    recorded_at: AwareDatetime
    captured_at: AwareDatetime
    fixture_schema_version: Literal[1]
    payload: PayloadT

    @model_validator(mode="after")
    def validate_provenance_chronology(self) -> "SourceEnvelope[PayloadT]":
        if self.recorded_at > self.captured_at:
            raise ValueError("recorded_at must not be after captured_at")
        return self
