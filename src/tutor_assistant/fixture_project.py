import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from tutor_assistant.models import Lesson, Student
from tutor_assistant.source_models import (
    AiSafeStudentProfile,
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

KnownSourceEnvelope = (
    SourceEnvelope[DashboardStudentProfilePayload]
    | SourceEnvelope[DashboardTestPlanPayload]
    | SourceEnvelope[DashboardTestResultPayload]
    | SourceEnvelope[DashboardIntakeNotePayload]
    | SourceEnvelope[DashboardLessonRecordPayload]
    | SourceEnvelope[GranolaMeetingPayload]
    | SourceEnvelope[LessonSummaryDraftPayload]
    | SourceEnvelope[ReviewedLessonSummaryPayload]
)


class FixtureStudentEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    source_records: list[str]
    normalized_records: str
    ai_safe_profile: str
    expected_scores: str


class FixtureScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    student_slug: str
    application_lesson_id: str
    expected_outcome: Literal["matched", "ambiguous", "future_no_transcript"]
    dashboard_candidate_external_ids: list[str]
    granola_meeting_external_id: str | None = None
    selected_dashboard_external_id: str | None = None


class FixtureManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixture_schema_version: Literal[1]
    students: list[FixtureStudentEntry]
    scenarios: list[FixtureScenario]
    privacy_sentinels: list[str]


class ExpectedNormalizedRecords(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student: Student
    lessons: list[Lesson]


@dataclass(frozen=True)
class SyntheticProject:
    root: Path
    manifest: FixtureManifest
    source_records: tuple[KnownSourceEnvelope, ...]
    students: tuple[Student, ...]
    lessons: tuple[Lesson, ...]
    ai_safe_profiles: tuple[AiSafeStudentProfile, ...]
    transcripts: dict[str, str]


class FixtureValidationError(ValueError):
    """Raised when the representative project stops being internally coherent."""


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_source_envelope(path: Path) -> KnownSourceEnvelope:
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"source record must be a JSON object: {path}")

    record_type = data.get("source_record_type")
    if not isinstance(record_type, str):
        raise ValueError(f"source_record_type must be a string: {path}")
    expected_system = {
        "student_profile": "dashboard",
        "test_plan": "dashboard",
        "test_result": "dashboard",
        "intake_note": "dashboard",
        "dashboard_lesson": "dashboard",
        "granola_meeting": "granola",
        "lesson_summary_draft": "generated",
        "reviewed_lesson_summary": "generated",
    }.get(record_type)
    if expected_system is not None and data.get("source_system") != expected_system:
        raise ValueError(f"{record_type!r} must come from {expected_system!r}: {path}")
    if record_type == "student_profile":
        return SourceEnvelope[DashboardStudentProfilePayload].model_validate(data)
    if record_type == "test_plan":
        return SourceEnvelope[DashboardTestPlanPayload].model_validate(data)
    if record_type == "test_result":
        return SourceEnvelope[DashboardTestResultPayload].model_validate(data)
    if record_type == "intake_note":
        return SourceEnvelope[DashboardIntakeNotePayload].model_validate(data)
    if record_type == "dashboard_lesson":
        return SourceEnvelope[DashboardLessonRecordPayload].model_validate(data)
    if record_type == "granola_meeting":
        return SourceEnvelope[GranolaMeetingPayload].model_validate(data)
    if record_type == "lesson_summary_draft":
        return SourceEnvelope[LessonSummaryDraftPayload].model_validate(data)
    if record_type == "reviewed_lesson_summary":
        return SourceEnvelope[ReviewedLessonSummaryPayload].model_validate(data)
    raise ValueError(f"unsupported source_record_type {record_type!r}: {path}")


def load_synthetic_project(root: Path) -> SyntheticProject:
    """Load the static representative project through its public manifest."""

    manifest = FixtureManifest.model_validate(_read_json(root / "manifest.json"))
    source_records: list[KnownSourceEnvelope] = []
    students: list[Student] = []
    lessons: list[Lesson] = []
    ai_safe_profiles: list[AiSafeStudentProfile] = []
    transcripts: dict[str, str] = {}

    for fixture_student in manifest.students:
        student_root = root / "students" / fixture_student.slug
        normalized = ExpectedNormalizedRecords.model_validate(
            _read_json(student_root / fixture_student.normalized_records)
        )
        students.append(normalized.student)
        lessons.extend(normalized.lessons)
        ai_safe_profiles.append(
            AiSafeStudentProfile.model_validate(
                _read_json(student_root / fixture_student.ai_safe_profile)
            )
        )

        for relative_path in fixture_student.source_records:
            source_path = student_root / relative_path
            envelope = _load_source_envelope(source_path)
            source_records.append(envelope)
            if isinstance(envelope.payload, GranolaMeetingPayload):
                transcript_path = source_path.parent / envelope.payload.transcript_file
                transcripts[envelope.external_id] = transcript_path.read_text(
                    encoding="utf-8"
                )

    return SyntheticProject(
        root=root,
        manifest=manifest,
        source_records=tuple(source_records),
        students=tuple(students),
        lessons=tuple(lessons),
        ai_safe_profiles=tuple(ai_safe_profiles),
        transcripts=transcripts,
    )


def validate_synthetic_project(project: SyntheticProject) -> None:
    """Validate relationships and safety properties spanning the entire corpus."""

    errors: list[str] = []
    source_keys = [
        (record.source_system, record.external_id) for record in project.source_records
    ]
    if len(source_keys) != len(set(source_keys)):
        errors.append("source-system/external-id pairs must be unique")

    student_ids = [student.student_id for student in project.students]
    lesson_ids = [lesson.lesson_id for lesson in project.lessons]
    if len(student_ids) != len(set(student_ids)):
        errors.append("application student UUIDs must be unique")
    if len(lesson_ids) != len(set(lesson_ids)):
        errors.append("application lesson UUIDs must be unique")
    for lesson in project.lessons:
        if lesson.student_id not in set(student_ids):
            errors.append(f"lesson {lesson.lesson_id} refers to an unknown student")

    dashboard_lessons = {
        record.external_id: record
        for record in project.source_records
        if isinstance(record.payload, DashboardLessonRecordPayload)
    }
    granola_meetings = {
        record.external_id: record
        for record in project.source_records
        if isinstance(record.payload, GranolaMeetingPayload)
    }
    application_lesson_ids = {str(lesson.lesson_id) for lesson in project.lessons}
    application_lessons = {str(lesson.lesson_id): lesson for lesson in project.lessons}

    profiles = [
        record
        for record in project.source_records
        if isinstance(record.payload, DashboardStudentProfilePayload)
    ]
    plans = [
        record
        for record in project.source_records
        if isinstance(record.payload, DashboardTestPlanPayload)
    ]
    results = [
        record
        for record in project.source_records
        if isinstance(record.payload, DashboardTestResultPayload)
    ]
    intake_notes = [
        record
        for record in project.source_records
        if isinstance(record.payload, DashboardIntakeNotePayload)
    ]
    drafts = {
        record.external_id: record
        for record in project.source_records
        if isinstance(record.payload, LessonSummaryDraftPayload)
    }
    finals = [
        record
        for record in project.source_records
        if isinstance(record.payload, ReviewedLessonSummaryPayload)
    ]
    expected_type_counts = {
        "student profiles": (len(profiles), 3),
        "test plans": (len(plans), 2),
        "test results": (len(results), 7),
        "intake notes": (len(intake_notes), 4),
        "dashboard lessons": (len(dashboard_lessons), 8),
        "Granola meetings": (len(granola_meetings), 6),
        "summary drafts": (len(drafts), 5),
        "reviewed summaries": (len(finals), 5),
    }
    for label, (actual_count, expected_count) in expected_type_counts.items():
        if actual_count != expected_count:
            errors.append(f"expected {expected_count} {label}, found {actual_count}")

    profile_external_ids = {record.external_id for record in profiles}
    student_linked_payload_types = (
        DashboardTestPlanPayload,
        DashboardTestResultPayload,
        DashboardIntakeNotePayload,
        DashboardLessonRecordPayload,
    )
    for record in project.source_records:
        if isinstance(record.payload, student_linked_payload_types):
            if record.payload.student_external_id not in profile_external_ids:
                errors.append(
                    f"source record {record.external_id} refers to an unknown student"
                )

    notes_by_id = {record.external_id: record for record in intake_notes}
    for note in intake_notes:
        superseded_id = note.payload.supersedes_external_id
        if superseded_id is None:
            continue
        superseded = notes_by_id.get(superseded_id)
        if superseded is None:
            errors.append(f"intake note {note.external_id} supersedes an unknown note")
        elif (
            superseded.payload.student_external_id != note.payload.student_external_id
            or superseded.recorded_at >= note.recorded_at
        ):
            errors.append(
                f"intake note {note.external_id} has invalid supersession chronology"
            )

    for scenario in project.manifest.scenarios:
        if scenario.application_lesson_id not in application_lesson_ids:
            errors.append(
                f"scenario {scenario.scenario_id} refers to an unknown application lesson"
            )
        missing_candidates = set(scenario.dashboard_candidate_external_ids) - set(
            dashboard_lessons
        )
        if missing_candidates:
            errors.append(
                f"scenario {scenario.scenario_id} has unknown dashboard candidates: "
                f"{sorted(missing_candidates)}"
            )
        if (
            scenario.granola_meeting_external_id is not None
            and scenario.granola_meeting_external_id not in granola_meetings
        ):
            errors.append(
                f"scenario {scenario.scenario_id} refers to an unknown Granola meeting"
            )

        if scenario.expected_outcome == "matched":
            if len(scenario.dashboard_candidate_external_ids) != 1:
                errors.append(
                    f"matched scenario {scenario.scenario_id} must have one candidate"
                )
            if scenario.granola_meeting_external_id is None:
                errors.append(
                    f"matched scenario {scenario.scenario_id} must have a transcript"
                )
            if scenario.selected_dashboard_external_id not in (
                scenario.dashboard_candidate_external_ids
            ):
                errors.append(
                    f"matched scenario {scenario.scenario_id} must select its candidate"
                )
            for candidate_id in scenario.dashboard_candidate_external_ids:
                candidate = dashboard_lessons.get(candidate_id)
                if candidate is not None and candidate.payload.status != "complete":
                    errors.append(
                        f"matched scenario {scenario.scenario_id} must be complete"
                    )
            application_lesson = application_lessons.get(scenario.application_lesson_id)
            if (
                application_lesson is not None
                and application_lesson.dashboard_meeting_id
                != scenario.selected_dashboard_external_id
            ):
                errors.append(
                    f"matched scenario {scenario.scenario_id} disagrees with normalized lesson"
                )
        elif scenario.expected_outcome == "ambiguous":
            if len(scenario.dashboard_candidate_external_ids) < 2:
                errors.append(
                    f"ambiguous scenario {scenario.scenario_id} needs two candidates"
                )
            if scenario.selected_dashboard_external_id is not None:
                errors.append(
                    f"ambiguous scenario {scenario.scenario_id} must refuse selection"
                )
            if scenario.granola_meeting_external_id is None:
                errors.append(
                    f"ambiguous scenario {scenario.scenario_id} must have a transcript"
                )
            for candidate_id in scenario.dashboard_candidate_external_ids:
                candidate = dashboard_lessons.get(candidate_id)
                if candidate is not None and candidate.payload.status != "complete":
                    errors.append(
                        f"ambiguous scenario {scenario.scenario_id} candidates "
                        "must be complete"
                    )
            application_lesson = application_lessons.get(scenario.application_lesson_id)
            if (
                application_lesson is not None
                and application_lesson.dashboard_meeting_id is not None
            ):
                errors.append(
                    f"ambiguous scenario {scenario.scenario_id} must stay unmatched"
                )
        elif scenario.expected_outcome == "future_no_transcript":
            if scenario.granola_meeting_external_id is not None:
                errors.append(
                    f"future scenario {scenario.scenario_id} must not have a transcript"
                )
            if len(scenario.dashboard_candidate_external_ids) != 1:
                errors.append(
                    f"future scenario {scenario.scenario_id} must have one dashboard lesson"
                )
            if scenario.selected_dashboard_external_id not in (
                scenario.dashboard_candidate_external_ids
            ):
                errors.append(
                    f"future scenario {scenario.scenario_id} must select its dashboard lesson"
                )
            selected = dashboard_lessons.get(
                scenario.selected_dashboard_external_id or ""
            )
            if selected is not None and selected.payload.status != "scheduled":
                errors.append(
                    f"future scenario {scenario.scenario_id} must stay scheduled"
                )
            application_lesson = application_lessons.get(scenario.application_lesson_id)
            if (
                application_lesson is not None
                and application_lesson.dashboard_meeting_id
                != scenario.selected_dashboard_external_id
            ):
                errors.append(
                    f"future scenario {scenario.scenario_id} disagrees with normalized lesson"
                )

    for external_id, meeting in granola_meetings.items():
        transcript = project.transcripts.get(external_id)
        if transcript is None:
            errors.append(f"Granola meeting {external_id} has no transcript")
            continue
        actual_hash = sha256(transcript.encode("utf-8")).hexdigest()
        if actual_hash != meeting.payload.transcript_sha256:
            errors.append(f"transcript hash mismatch for {external_id}")
        if "Microphone:" not in transcript or "System audio:" not in transcript:
            errors.append(
                f"transcript {external_id} lacks Granola-style speaker labels"
            )

    word_counts = sorted(len(text.split()) for text in project.transcripts.values())
    if len(word_counts) != 6:
        errors.append("the corpus must contain six transcripts")
    elif not (
        1000 <= word_counts[0] <= 2000 and all(n >= 3400 for n in word_counts[1:])
    ):
        errors.append(
            "the corpus must contain one short transcript and five approximately "
            "3,500-word transcripts"
        )

    for final in finals:
        draft = drafts.get(final.payload.draft_external_id)
        if draft is None:
            errors.append(f"final summary {final.external_id} has no draft")
            continue
        if draft.recorded_at >= final.recorded_at:
            errors.append(f"draft must precede final summary {final.external_id}")
        dashboard_lesson = dashboard_lessons.get(
            final.payload.dashboard_lesson_external_id
        )
        if dashboard_lesson is None:
            errors.append(
                f"final summary {final.external_id} has no dashboard lesson source"
            )
        elif (
            dashboard_lesson.payload.noteworthy_information
            != final.payload.noteworthy_information
            or dashboard_lesson.payload.homework != final.payload.homework
        ):
            errors.append(
                f"final summary {final.external_id} must equal dashboard authority"
            )

    expected_score_fields = (
        "test_date",
        "score",
        "math_score",
        "reading_writing_score",
        "dashboard_reported_superscore",
    )
    actual_scores = {
        record.external_id: record.payload.model_dump(mode="json") for record in results
    }
    expected_score_ids: set[str] = set()
    for fixture_student in project.manifest.students:
        expected_path = (
            project.root
            / "students"
            / fixture_student.slug
            / fixture_student.expected_scores
        )
        expected_scores = _read_json(expected_path)
        if not isinstance(expected_scores, list):
            errors.append(f"expected scores must be a list: {expected_path}")
            continue
        for expected in expected_scores:
            if not isinstance(expected, dict) or not isinstance(
                expected.get("external_id"), str
            ):
                errors.append(f"malformed expected score in {expected_path}")
                continue
            external_id = expected["external_id"]
            expected_score_ids.add(external_id)
            actual = actual_scores.get(external_id)
            if actual is None:
                errors.append(f"expected score {external_id} has no dashboard source")
                continue
            expected_values = {
                field: expected.get(field) for field in expected_score_fields
            }
            actual_values = {
                field: actual.get(field) for field in expected_score_fields
            }
            if expected_values != actual_values:
                errors.append(
                    f"expected score {external_id} must copy dashboard-reported values"
                )
    if expected_score_ids != set(actual_scores):
        errors.append("expected score files must cover every dashboard test result")

    safe_values = [
        profile.model_dump_json() for profile in project.ai_safe_profiles
    ] + [student.model_dump_json() for student in project.students]
    safe_values.extend(lesson.model_dump_json() for lesson in project.lessons)
    safe_values.extend(project.transcripts.values())
    safe_values.extend(
        record.model_dump_json()
        for record in project.source_records
        if not isinstance(record.payload, DashboardStudentProfilePayload)
    )
    safe_text = "\n".join(safe_values)
    for sentinel in project.manifest.privacy_sentinels:
        if sentinel in safe_text:
            errors.append(f"restricted privacy sentinel leaked: {sentinel}")

    profile_sources = [
        record.payload
        for record in project.source_records
        if isinstance(record.payload, DashboardStudentProfilePayload)
    ]
    expected_safe_profiles = [
        build_ai_safe_student_profile(profile) for profile in profile_sources
    ]
    if expected_safe_profiles != list(project.ai_safe_profiles):
        errors.append("AI-safe profile drift from allowlisted source projection")

    if errors:
        raise FixtureValidationError("; ".join(errors))
