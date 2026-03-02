from __future__ import annotations

import logging
from typing import Any

from src.agent.runtime_helpers.errors import LkpdValidationError
from src.agent.types import (
    EssayInsertArgs,
    GenerateType,
    LkpdGeneratedPayload,
    MaterialGeneratedPayload,
    McqInsertArgs,
    SummaryInsertArgs,
)


def build_mcp_insert_plan(
    *,
    job_id: str,
    user_id: str,
    document_id: str,
    payload: MaterialGeneratedPayload,
    requested_types: list[GenerateType],
) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
    plans: list[tuple[str, dict[str, Any]]] = []
    warnings: list[str] = []
    selected = set(requested_types)

    if "mcq" in selected:
        if payload.mcq_quiz is None:
            warnings.append("mcp_insert_skipped:mcq_quiz_missing")
        else:
            mcq_args = McqInsertArgs(
                job_id=job_id,
                user_id=user_id,
                document_id=document_id,
                mcq_quiz=payload.mcq_quiz,
            )
            plans.append(
                (
                    "insert_mcq",
                    mcq_args.model_dump(mode="json"),
                )
            )
    if "essay" in selected:
        if payload.essay_quiz is None:
            warnings.append("mcp_insert_skipped:essay_quiz_missing")
        else:
            essay_args = EssayInsertArgs(
                job_id=job_id,
                user_id=user_id,
                document_id=document_id,
                essay_quiz=payload.essay_quiz,
            )
            plans.append(
                (
                    "insert_essay",
                    essay_args.model_dump(mode="json"),
                )
            )
    if "summary" in selected:
        if payload.summary is None:
            warnings.append("mcp_insert_skipped:summary_missing")
        else:
            summary_args = SummaryInsertArgs(
                job_id=job_id,
                user_id=user_id,
                document_id=document_id,
                summary=payload.summary,
            )
            plans.append(
                (
                    "insert_summary",
                    summary_args.model_dump(mode="json"),
                )
            )

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
        if payload.mcq_quiz is None:
            logger.warning("model_output_validation_failed type=mcq reason=missing")
            warnings.append("model_output_validation_failed:mcq_missing")
        else:
            mcq_questions = payload.mcq_quiz.questions
            if len(mcq_questions) < mcq_count:
                logger.warning(
                    "model_output_validation_failed type=mcq reason=too_few got=%s expected=%s",
                    len(mcq_questions),
                    mcq_count,
                )
                warnings.append(
                    f"model_output_validation_failed:mcq_count_lt_requested:{len(mcq_questions)}<{mcq_count}"
                )
            if len(mcq_questions) > mcq_count:
                warnings.append(
                    f"MCQ questions trimmed from {len(mcq_questions)} to {mcq_count}."
                )
                mcq_questions = mcq_questions[:mcq_count]
            payload.mcq_quiz.questions = mcq_questions
    elif payload.mcq_quiz is not None:
        warnings.append("Model returned mcq_quiz even though it was not requested.")
        payload.mcq_quiz = None

    if "essay" in selected:
        if payload.essay_quiz is None:
            logger.warning("model_output_validation_failed type=essay reason=missing")
            warnings.append("model_output_validation_failed:essay_missing")
        else:
            essay_questions = payload.essay_quiz.questions
            if len(essay_questions) < essay_count:
                logger.warning(
                    "model_output_validation_failed type=essay reason=too_few got=%s expected=%s",
                    len(essay_questions),
                    essay_count,
                )
                warnings.append(
                    f"model_output_validation_failed:essay_count_lt_requested:{len(essay_questions)}<{essay_count}"
                )
            if len(essay_questions) > essay_count:
                warnings.append(
                    f"Essay questions trimmed from {len(essay_questions)} to {essay_count}."
                )
                essay_questions = essay_questions[:essay_count]
            payload.essay_quiz.questions = essay_questions
    elif payload.essay_quiz is not None:
        warnings.append("Model returned essay_quiz even though it was not requested.")
        payload.essay_quiz = None

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
        warnings.append("Model returned summary even though it was not requested.")
        payload.summary = None

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

