import sys

import pytest

if sys.version_info < (3, 11):
    pytest.skip("Runtime tests require Python 3.11+.", allow_module_level=True)

from src.agent.runtime import AgentRuntime
from src.agent.types import (
    McqQuestion,
    McqQuiz,
    MaterialGeneratedPayload,
    SummaryContent,
)


def test_build_mcp_insert_plan_injects_required_metadata() -> None:
    payload = MaterialGeneratedPayload(
        mcq_quiz=McqQuiz(
            questions=[
                McqQuestion(
                    question="Apa itu AI?",
                    options=["A", "B", "C", "D"],
                    correct_answer="A",
                    explanation="AI adalah kemampuan mesin untuk meniru kecerdasan.",
                )
            ]
        ),
        summary=SummaryContent(
            title="Ringkasan AI",
            overview="AI membantu otomatisasi proses dan analitik.",
            key_points=["otomatisasi", "analitik"],
        ),
    )

    plans, warnings = AgentRuntime._build_mcp_insert_plan(
        job_id="job-1",
        user_id="user-1",
        document_id="doc-1",
        payload=payload,
        requested_types=["mcq", "summary"],
    )

    assert warnings == []
    assert [name for name, _ in plans] == ["insert_mcq", "insert_summary"]
    for _, args in plans:
        assert args["job_id"] == "job-1"
        assert args["user_id"] == "user-1"
        assert args["document_id"] == "doc-1"


def test_generation_contract_does_not_fail_on_missing_requested_type() -> None:
    warnings: list[str] = []
    payload = MaterialGeneratedPayload(
        summary=SummaryContent(
            title="Ringkasan",
            overview="Satu dua tiga empat lima",
            key_points=["poin 1"],
        )
    )

    result = AgentRuntime._enforce_generation_contract(
        payload,
        generate_types=["mcq", "summary"],
        mcq_count=5,
        essay_count=3,
        summary_max_words=5,
        warnings=warnings,
    )

    assert result.mcq_quiz is None
    assert result.summary is not None
    assert "model_output_validation_failed:mcq_missing" in warnings
