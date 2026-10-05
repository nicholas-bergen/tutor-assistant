import pytest
from pydantic import BaseModel, ValidationError

from tutor_assistant.source_models import (
    DashboardIntakeNotePayload,
    DashboardLessonRecordPayload,
    DashboardStudentProfilePayload,
    DashboardTestPlanPayload,
    DashboardTestResultPayload,
    GranolaMeetingPayload,
    LessonSummaryDraftPayload,
    ReviewedLessonSummaryPayload,
    SourceEnvelope,
    build_ai_safe_student_profile,
)


def test_source_envelope_is_strict_while_dashboard_payload_preserves_unknown_fields() -> (
    None
):
    envelope = SourceEnvelope[DashboardStudentProfilePayload].model_validate(
        {
            "source_system": "dashboard",
            "source_record_type": "student_profile",
            "external_id": "dashboard-student-maya-patel",
            "event_at": "2026-08-01T09:00:00-04:00",
            "recorded_at": "2026-08-01T09:02:00-04:00",
            "captured_at": "2026-09-20T12:00:00-04:00",
            "fixture_schema_version": 1,
            "payload": {
                "display_name": "Maya Patel",
                "graduation_year": 2027,
                "contact": {"email": "maya.patel@example.test"},
                "upstream_field_not_yet_supported": "preserved",
            },
        }
    )

    assert envelope.payload.display_name == "Maya Patel"
    assert envelope.payload.model_extra == {
        "upstream_field_not_yet_supported": "preserved"
    }


def test_ai_safe_student_profile_uses_an_allowlist_that_excludes_contact_data() -> None:
    source = DashboardStudentProfilePayload.model_validate(
        {
            "display_name": "Maya Patel",
            "graduation_year": 2027,
            "student_personality": "Thoughtful and persistent.",
            "general_goals": "Build reliable pacing before the October SAT.",
            "current_academics": ["AP Calculus AB", "AP English Language"],
            "contact": {
                "email": "privacy-sentinel-maya@example.test",
                "phone_numbers": ["+1-202-555-0101"],
                "address": "100 Example Way, Exampleville, NY 10001",
                "time_zone": "America/New_York",
            },
            "new_private_upstream_field": "privacy-sentinel-unknown",
        }
    )

    safe_profile = build_ai_safe_student_profile(source)
    serialized = safe_profile.model_dump_json()

    assert safe_profile.display_name == "Maya Patel"
    assert safe_profile.current_academics == [
        "AP Calculus AB",
        "AP English Language",
    ]
    assert "privacy-sentinel" not in serialized
    assert "contact" not in type(safe_profile).model_fields


def test_source_envelope_rejects_capture_before_the_source_record_was_written() -> None:
    with pytest.raises(
        ValidationError, match="recorded_at must not be after captured_at"
    ):
        SourceEnvelope[DashboardStudentProfilePayload].model_validate(
            {
                "source_system": "dashboard",
                "source_record_type": "student_profile",
                "external_id": "dashboard-student-maya-patel",
                "event_at": "2026-10-06T18:30:00-04:00",
                "recorded_at": "2026-10-02T09:02:00-04:00",
                "captured_at": "2026-10-01T12:00:00-04:00",
                "fixture_schema_version": 1,
                "payload": {
                    "display_name": "Maya Patel",
                    "graduation_year": 2027,
                },
            }
        )


def test_source_envelope_rejects_unknown_provenance_fields() -> None:
    with pytest.raises(ValidationError) as exception_info:
        SourceEnvelope[DashboardStudentProfilePayload].model_validate(
            {
                "source_system": "dashboard",
                "source_record_type": "student_profile",
                "external_id": "dashboard-student-maya-patel",
                "event_at": "2026-08-01T09:00:00-04:00",
                "recorded_at": "2026-08-01T09:02:00-04:00",
                "captured_at": "2026-09-20T12:00:00-04:00",
                "fixture_schema_version": 1,
                "unexpected_provenance": "not allowed",
                "payload": {
                    "display_name": "Maya Patel",
                    "graduation_year": 2027,
                },
            }
        )

    assert exception_info.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize(
    ("payload_type", "data"),
    [
        (
            DashboardTestPlanPayload,
            {
                "student_external_id": "dashboard-student-maya-patel",
                "test_type": "SAT",
                "target_tests": ["2026-10-03"],
                "default_accommodation": "standard_time",
            },
        ),
        (
            DashboardTestResultPayload,
            {
                "student_external_id": "dashboard-student-maya-patel",
                "test_date": "2026-08-22",
                "test_name": "Fictional Practice Test C",
                "accommodation": "standard_time",
                "is_official": False,
                "score": 1480,
                "math_score": 750,
                "reading_writing_score": 730,
            },
        ),
        (
            DashboardIntakeNotePayload,
            {
                "student_external_id": "dashboard-student-maya-patel",
                "posted_to": "Maya Patel",
                "author_display_name": "Jordan Lee",
                "body": "Initial goal: 1450. Student wants help with pacing.",
            },
        ),
        (
            DashboardLessonRecordPayload,
            {
                "student_external_id": "dashboard-student-maya-patel",
                "scheduled_start_at": "2026-08-27T17:00:00-04:00",
                "duration_minutes": 90,
                "status": "complete",
                "subjects": ["SAT Math"],
                "coach_display_name": "Jordan Lee",
                "content_and_concepts": ["Math: Algebra - Linear equations"],
                "noteworthy_information": "Maya improved her equation setup.",
                "homework": ["Complete Mixed Practice Set 3."],
            },
        ),
        (
            GranolaMeetingPayload,
            {
                "title": "Maya Patel - SAT tutoring",
                "participant_display_names": ["Maya Patel", "Jordan Lee"],
                "started_at": "2026-08-27T17:00:00-04:00",
                "ended_at": "2026-08-27T18:30:00-04:00",
                "transcript_file": "transcript.txt",
                "transcript_sha256": "a" * 64,
            },
        ),
        (
            LessonSummaryDraftPayload,
            {
                "dashboard_lesson_external_id": "dashboard-lesson-maya-01",
                "granola_meeting_external_id": "granola-meeting-maya-01",
                "model_name": "fictional-summary-model",
                "noteworthy_information": "Draft summary.",
                "homework": ["Draft homework."],
            },
        ),
        (
            ReviewedLessonSummaryPayload,
            {
                "dashboard_lesson_external_id": "dashboard-lesson-maya-01",
                "draft_external_id": "generated-draft-maya-01",
                "reviewer_display_name": "Jordan Lee",
                "noteworthy_information": "Reviewed summary.",
                "homework": ["Reviewed homework."],
            },
        ),
    ],
)
def test_supported_source_payloads_validate_known_fields(
    payload_type: type[BaseModel], data: dict[str, object]
) -> None:
    payload = payload_type.model_validate(data)

    assert payload.model_dump(mode="json", exclude_none=True) == data


def test_dashboard_test_result_rejects_out_of_range_scores() -> None:
    with pytest.raises(ValidationError):
        DashboardTestResultPayload.model_validate(
            {
                "student_external_id": "dashboard-student-maya-patel",
                "test_date": "2026-08-22",
                "test_name": "Fictional Practice Test C",
                "accommodation": "standard_time",
                "is_official": False,
                "score": 1700,
                "math_score": 750,
                "reading_writing_score": 730,
            }
        )


def test_granola_meeting_rejects_an_end_before_its_start() -> None:
    with pytest.raises(ValidationError, match="ended_at must be after started_at"):
        GranolaMeetingPayload.model_validate(
            {
                "title": "Maya Patel - SAT tutoring",
                "participant_display_names": ["Maya Patel", "Jordan Lee"],
                "started_at": "2026-08-27T17:00:00-04:00",
                "ended_at": "2026-08-27T16:59:00-04:00",
                "transcript_file": "transcript.txt",
                "transcript_sha256": "a" * 64,
            }
        )
