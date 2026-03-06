from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast

from src.agent.runtime_helpers.errors import LkpdValidationError
from src.agent.types import (
    EssayInsertArgs,
    GenerateType,
    LkpdGeneratedPayload,
    MaterialGeneratedPayload,
    McqInsertArgs,
    SummaryInsertArgs,
)


@dataclass(frozen=True)
class _InsertSpec:
    requested_type: GenerateType
    payload_field: str
    missing_warning: str
    tool_name: str
    args_model: type[Any]


_INSERT_SPECS: tuple[_InsertSpec, ...] = (
    _InsertSpec(
        requested_type="mcq",
        payload_field="mcq_quiz",
        missing_warning="mcp_insert_skipped:mcq_quiz_missing",
        tool_name="insert_mcq",
        args_model=McqInsertArgs,
    ),
    _InsertSpec(
        requested_type="essay",
        payload_field="essay_quiz",
        missing_warning="mcp_insert_skipped:essay_quiz_missing",
        tool_name="insert_essay",
        args_model=EssayInsertArgs,
    ),
    _InsertSpec(
        requested_type="summary",
        payload_field="summary",
        missing_warning="mcp_insert_skipped:summary_missing",
        tool_name="insert_summary",
        args_model=SummaryInsertArgs,
    ),
)


def build_mcp_insert_plan(
    *,
    job_id: str,
    material_id: str,
    requested_by_id: str,
    payload: MaterialGeneratedPayload,
    requested_types: list[GenerateType],
) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
    plans: list[tuple[str, dict[str, Any]]] = []
    warnings: list[str] = []
    selected = set(requested_types)

    for spec in _INSERT_SPECS:
        if spec.requested_type not in selected:
            continue

        content = getattr(payload, spec.payload_field)
        if content is None:
            warnings.append(spec.missing_warning)
            continue

        args = spec.args_model(
            job_id=job_id,
            material_id=material_id,
            requested_by_id=requested_by_id,
            **{spec.payload_field: content},
        )
        plans.append((spec.tool_name, cast(dict[str, Any], args.model_dump(mode="json"))))

    return plans, warnings


def enforce_generation_contract(
    payload: MaterialGeneratedPayload,
    *,
    generate_types: list[GenerateType],
    mcq_count: int,
    essay_count: int,
    summary_max_words: int,
    warnings: list[str],
    logger: logging.Logger,
) -> MaterialGeneratedPayload:
    selected = set(generate_types)

    if "mcq" in selected:
        payload.mcq_quiz = _enforce_quiz_contract(
            quiz=payload.mcq_quiz,
            quiz_type="mcq",
            requested_count=mcq_count,
            trim_label="MCQ",
            warnings=warnings,
            logger=logger,
        )
    elif payload.mcq_quiz is not None:
        payload.mcq_quiz = _drop_unrequested_payload(
            payload_name="mcq_quiz",
            warnings=warnings,
        )

    if "essay" in selected:
        payload.essay_quiz = _enforce_quiz_contract(
            quiz=payload.essay_quiz,
            quiz_type="essay",
            requested_count=essay_count,
            trim_label="Essay",
            warnings=warnings,
            logger=logger,
        )
    elif payload.essay_quiz is not None:
        payload.essay_quiz = _drop_unrequested_payload(
            payload_name="essay_quiz",
            warnings=warnings,
        )

    if "summary" in selected:
        if payload.summary is None:
            logger.warning("model_output_validation_failed type=summary reason=missing")
            warnings.append("model_output_validation_failed:summary_missing")
        else:
            overview_words = payload.summary.overview.split()
            if len(overview_words) > summary_max_words:
                warnings.append(
                    f"Summary overview trimmed from {len(overview_words)} to {summary_max_words} words."
                )
                payload.summary.overview = " ".join(
                    overview_words[:summary_max_words]
                )
    elif payload.summary is not None:
        payload.summary = _drop_unrequested_payload(
            payload_name="summary",
            warnings=warnings,
        )

    return payload


def enforce_lkpd_contract(
    payload: LkpdGeneratedPayload,
    *,
    activity_count: int,
    warnings: list[str],
) -> LkpdGeneratedPayload:
    lkpd = payload.lkpd

    if not lkpd.learning_objectives:
        raise LkpdValidationError("LKPD must contain learning objectives.")
    if not lkpd.instructions:
        raise LkpdValidationError("LKPD must contain instructions.")
    if not lkpd.assessment_rubric:
        raise LkpdValidationError("LKPD must contain assessment rubric.")

    activities = lkpd.activities
    if len(activities) < activity_count:
        raise LkpdValidationError(
            f"Model generated too few LKPD activities ({len(activities)} < {activity_count})."
        )
    if len(activities) > activity_count:
        warnings.append(
            f"LKPD activities trimmed from {len(activities)} to {activity_count}."
        )
        activities = activities[:activity_count]

    for idx, activity in enumerate(activities, start=1):
        activity.activity_no = idx
    lkpd.activities = activities

    return payload


def _enforce_quiz_contract(
    *,
    quiz: Any,
    quiz_type: str,
    requested_count: int,
    trim_label: str,
    warnings: list[str],
    logger: logging.Logger,
) -> Any:
    if quiz is None:
        logger.warning("model_output_validation_failed type=%s reason=missing", quiz_type)
        warnings.append(f"model_output_validation_failed:{quiz_type}_missing")
        return None

    questions = quiz.questions
    question_count = len(questions)
    if question_count < requested_count:
        logger.warning(
            "model_output_validation_failed type=%s reason=too_few got=%s expected=%s",
            quiz_type,
            question_count,
            requested_count,
        )
        warnings.append(
            f"model_output_validation_failed:{quiz_type}_count_lt_requested:{question_count}<{requested_count}"
        )
    if question_count > requested_count:
        warnings.append(
            f"{trim_label} questions trimmed from {question_count} to {requested_count}."
        )
        questions = questions[:requested_count]
    quiz.questions = questions
    return quiz


def _drop_unrequested_payload(*, payload_name: str, warnings: list[str]) -> None:
    warnings.append(f"Model returned {payload_name} even though it was not requested.")
    return None

