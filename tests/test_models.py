import json
from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from tutor_assistant.models import Lesson, Student


def test_student_parses_and_normalizes_valid_input() -> None:
    student_id = "dd4d7409-ade0-455b-a66a-885c567bf29d"

    student = Student.model_validate(
        {
            "student_id": student_id,
            "display_name": "  Avery Chen  ",
        }
    )

    assert student.student_id == UUID(student_id)
    assert student.display_name == "Avery Chen"


def test_student_rejects_blank_display_name() -> None:
    with pytest.raises(ValidationError) as exception_info:
        Student.model_validate(
            {
                "student_id": "dd4d7409-ade0-455b-a66a-885c567bf29d",
                "display_name": "   ",
            }
        )

    error = exception_info.value.errors()[0]

    assert error["loc"] == ("display_name",)
    assert error["type"] == "string_too_short"


def test_lesson_parses_valid_unmatched_input() -> None:
    lesson_id = "f11df24a-563a-4ded-8cbb-668e4f75ec04"
    student_id = "dd4d7409-ade0-455b-a66a-885c567bf29d"

    lesson = Lesson.model_validate(
        {
            "lesson_id": lesson_id,
            "student_id": student_id,
            "scheduled_start_at": "2026-09-17T16:30:00-04:00",
        }
    )

    assert lesson.lesson_id == UUID(lesson_id)
    assert lesson.student_id == UUID(student_id)
    assert lesson.dashboard_meeting_id is None
    assert isinstance(lesson.scheduled_start_at, datetime)
    assert lesson.scheduled_start_at.isoformat() == "2026-09-17T16:30:00-04:00"


def test_lesson_rejects_timezone_naive_scheduled_start() -> None:
    with pytest.raises(ValidationError) as exception_info:
        Lesson.model_validate(
            {
                "lesson_id": "f11df24a-563a-4ded-8cbb-668e4f75ec04",
                "student_id": "dd4d7409-ade0-455b-a66a-885c567bf29d",
                "scheduled_start_at": "2026-09-17T16:30:00",
            }
        )

    error = exception_info.value.errors()[0]

    assert error["loc"] == ("scheduled_start_at",)
    assert error["type"] == "timezone_aware"


def test_lesson_serializes_full_unmatched_snapshot() -> None:
    lesson = Lesson.model_validate(
        {
            "lesson_id": "f11df24a-563a-4ded-8cbb-668e4f75ec04",
            "student_id": "dd4d7409-ade0-455b-a66a-885c567bf29d",
            "scheduled_start_at": "2026-09-17T16:30:00-04:00",
        }
    )

    expected = {
        "lesson_id": "f11df24a-563a-4ded-8cbb-668e4f75ec04",
        "student_id": "dd4d7409-ade0-455b-a66a-885c567bf29d",
        "dashboard_meeting_id": None,
        "scheduled_start_at": "2026-09-17T16:30:00-04:00",
    }

    assert lesson.model_dump(mode="json") == expected
    assert json.loads(lesson.model_dump_json()) == expected


def test_student_rejects_undeclared_fields() -> None:
    with pytest.raises(ValidationError) as exception_info:
        Student.model_validate(
            {
                "student_id": "dd4d7409-ade0-455b-a66a-885c567bf29d",
                "display_name": "Avery Chen",
                "display_naem": "Typo",
            }
        )

    error = exception_info.value.errors()[0]

    assert error["loc"] == ("display_naem",)
    assert error["type"] == "extra_forbidden"


def test_student_validates_assignment() -> None:
    student = Student.model_validate(
        {
            "student_id": "dd4d7409-ade0-455b-a66a-885c567bf29d",
            "display_name": "Avery Chen",
        }
    )

    with pytest.raises(ValidationError) as exception_info:
        student.display_name = "   "

    error = exception_info.value.errors()[0]

    assert error["loc"] == ("display_name",)
    assert error["type"] == "string_too_short"
    assert student.display_name == "Avery Chen"


def test_lesson_normalizes_dashboard_meeting_id() -> None:
    lesson = Lesson.model_validate(
        {
            "lesson_id": "f11df24a-563a-4ded-8cbb-668e4f75ec04",
            "student_id": "dd4d7409-ade0-455b-a66a-885c567bf29d",
            "dashboard_meeting_id": "  dashboard-meeting-4815  ",
            "scheduled_start_at": "2026-09-17T16:30:00-04:00",
        }
    )

    assert lesson.dashboard_meeting_id == "dashboard-meeting-4815"


def test_lesson_rejects_non_string_dashboard_meeting_id() -> None:
    with pytest.raises(ValidationError) as exception_info:
        Lesson.model_validate(
            {
                "lesson_id": "f11df24a-563a-4ded-8cbb-668e4f75ec04",
                "student_id": "dd4d7409-ade0-455b-a66a-885c567bf29d",
                "dashboard_meeting_id": 4815,
                "scheduled_start_at": "2026-09-17T16:30:00-04:00",
            }
        )

    error = exception_info.value.errors()[0]

    assert error["loc"] == ("dashboard_meeting_id",)
    assert error["type"] == "string_type"
