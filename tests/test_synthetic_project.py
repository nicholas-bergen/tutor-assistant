from dataclasses import replace
from pathlib import Path

import pytest

from tutor_assistant.fixture_project import (
    FixtureValidationError,
    load_synthetic_project,
    validate_synthetic_project,
)
from tutor_assistant.source_models import ReviewedLessonSummaryPayload

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "synthetic_project"


def test_representative_project_loads_the_complete_agreed_scenario_mix() -> None:
    project = load_synthetic_project(FIXTURE_ROOT)

    assert {student.slug for student in project.manifest.students} == {
        "lena-morales",
        "maya-patel",
        "theo-martin",
    }
    assert len(project.students) == 3
    assert len(project.lessons) == 7
    assert len(project.transcripts) == 6
    assert [scenario.expected_outcome for scenario in project.manifest.scenarios].count(
        "matched"
    ) == 5
    assert [scenario.expected_outcome for scenario in project.manifest.scenarios].count(
        "ambiguous"
    ) == 1
    assert [scenario.expected_outcome for scenario in project.manifest.scenarios].count(
        "future_no_transcript"
    ) == 1


def test_representative_project_satisfies_all_corpus_invariants() -> None:
    project = load_synthetic_project(FIXTURE_ROOT)

    validate_synthetic_project(project)


def test_project_validation_detects_transcript_content_drift() -> None:
    project = load_synthetic_project(FIXTURE_ROOT)
    changed_transcripts = dict(project.transcripts)
    changed_transcripts["granola-meeting-maya-01"] += "\nSystem audio: Changed.\n"

    with pytest.raises(FixtureValidationError, match="transcript hash mismatch"):
        validate_synthetic_project(replace(project, transcripts=changed_transcripts))


def test_project_validation_detects_restricted_data_in_ai_safe_records() -> None:
    project = load_synthetic_project(FIXTURE_ROOT)
    leaked_profile = project.ai_safe_profiles[0].model_copy(
        update={"general_goals": "privacy-sentinel-maya"}
    )

    with pytest.raises(FixtureValidationError, match="privacy sentinel leaked"):
        validate_synthetic_project(
            replace(
                project,
                ai_safe_profiles=(leaked_profile, *project.ai_safe_profiles[1:]),
            )
        )


def test_project_validation_detects_ai_safe_projection_drift() -> None:
    project = load_synthetic_project(FIXTURE_ROOT)
    changed_profile = project.ai_safe_profiles[0].model_copy(
        update={"general_goals": "A different but nonprivate goal."}
    )

    with pytest.raises(FixtureValidationError, match="AI-safe profile drift"):
        validate_synthetic_project(
            replace(
                project,
                ai_safe_profiles=(changed_profile, *project.ai_safe_profiles[1:]),
            )
        )


def test_project_validation_refuses_an_automatic_ambiguous_match() -> None:
    project = load_synthetic_project(FIXTURE_ROOT)
    scenarios = list(project.manifest.scenarios)
    ambiguous_index = next(
        index
        for index, scenario in enumerate(scenarios)
        if scenario.expected_outcome == "ambiguous"
    )
    scenarios[ambiguous_index] = scenarios[ambiguous_index].model_copy(
        update={
            "selected_dashboard_external_id": (
                scenarios[ambiguous_index].dashboard_candidate_external_ids[0]
            )
        }
    )
    changed_manifest = project.manifest.model_copy(update={"scenarios": scenarios})

    with pytest.raises(FixtureValidationError, match="must refuse selection"):
        validate_synthetic_project(replace(project, manifest=changed_manifest))


def test_project_validation_keeps_dashboard_reviewed_summary_authoritative() -> None:
    project = load_synthetic_project(FIXTURE_ROOT)
    changed_records = list(project.source_records)
    final_index = next(
        index
        for index, record in enumerate(changed_records)
        if isinstance(record.payload, ReviewedLessonSummaryPayload)
    )
    final = changed_records[final_index]
    changed_records[final_index] = final.model_copy(
        update={
            "payload": final.payload.model_copy(
                update={"noteworthy_information": "An unreviewed replacement."}
            )
        }
    )

    with pytest.raises(FixtureValidationError, match="dashboard authority"):
        validate_synthetic_project(
            replace(project, source_records=tuple(changed_records))
        )
