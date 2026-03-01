from __future__ import annotations

import unittest

from src.agent.runtime import AgentRuntime, LkpdValidationError, MaterialValidationError
from src.agent.types import (
    EssayQuestion,
    EssayQuiz,
    LkpdActivity,
    LkpdContent,
    LkpdGeneratedPayload,
    LkpdRubricItem,
    MaterialGeneratedPayload,
    McqQuestion,
    McqQuiz,
    SummaryContent,
)


class RuntimeGenerationContractTests(unittest.TestCase):
    @staticmethod
    def _sample_payload() -> MaterialGeneratedPayload:
        return MaterialGeneratedPayload(
            mcq_quiz=McqQuiz(
                questions=[
                    McqQuestion(
                        question="Q1",
                        options=["A", "B", "C", "D"],
                        correct_answer="A",
                        explanation="E1",
                    )
                ]
            ),
            essay_quiz=EssayQuiz(
                questions=[EssayQuestion(question="E1", expected_points="P1")]
            ),
            summary=SummaryContent(
                title="S1",
                overview="ini ringkasan singkat",
                key_points=["k1"],
            ),
        )

    def test_only_requested_blocks_are_kept(self) -> None:
        payload = self._sample_payload()
        warnings: list[str] = []

        result = AgentRuntime._enforce_generation_contract(
            payload,
            generate_types=["mcq"],
            mcq_count=1,
            essay_count=1,
            summary_max_words=200,
            warnings=warnings,
        )

        self.assertIsNotNone(result.mcq_quiz)
        self.assertIsNone(result.essay_quiz)
        self.assertIsNone(result.summary)
        self.assertTrue(
            any("essay_quiz even though it was not requested" in item for item in warnings)
        )
        self.assertTrue(
            any("summary even though it was not requested" in item for item in warnings)
        )

    def test_missing_selected_block_raises(self) -> None:
        payload = MaterialGeneratedPayload(
            mcq_quiz=None,
            essay_quiz=None,
            summary=None,
        )

        with self.assertRaises(MaterialValidationError):
            AgentRuntime._enforce_generation_contract(
                payload,
                generate_types=["summary"],
                mcq_count=10,
                essay_count=3,
                summary_max_words=200,
                warnings=[],
            )

    def test_summary_trim_applies_when_selected(self) -> None:
        payload = MaterialGeneratedPayload(
            summary=SummaryContent(
                title="S1",
                overview="kata1 kata2 kata3 kata4 kata5 kata6",
                key_points=[],
            )
        )
        warnings: list[str] = []

        result = AgentRuntime._enforce_generation_contract(
            payload,
            generate_types=["summary"],
            mcq_count=10,
            essay_count=3,
            summary_max_words=3,
            warnings=warnings,
        )

        assert result.summary is not None
        self.assertEqual(result.summary.overview, "kata1 kata2 kata3")
        self.assertTrue(any("Summary overview trimmed" in item for item in warnings))


class RuntimeLkpdContractTests(unittest.TestCase):
    def test_lkpd_contract_trims_extra_activities(self) -> None:
        payload = LkpdGeneratedPayload(
            lkpd=LkpdContent(
                title="LKPD",
                learning_objectives=["Objektif"],
                instructions=["Instruksi"],
                activities=[
                    LkpdActivity(
                        activity_no=1,
                        task="A1",
                        expected_output="O1",
                        assessment_hint="H1",
                    ),
                    LkpdActivity(
                        activity_no=2,
                        task="A2",
                        expected_output="O2",
                        assessment_hint="H2",
                    ),
                ],
                worksheet_template="Template",
                assessment_rubric=[
                    LkpdRubricItem(
                        aspect="Aspek",
                        criteria="Kriteria",
                        score_range="1-4",
                    )
                ],
            )
        )
        warnings: list[str] = []

        result = AgentRuntime._enforce_lkpd_contract(
            payload,
            activity_count=1,
            warnings=warnings,
        )

        self.assertEqual(len(result.lkpd.activities), 1)
        self.assertEqual(result.lkpd.activities[0].activity_no, 1)
        self.assertTrue(any("LKPD activities trimmed" in item for item in warnings))

    def test_lkpd_contract_raises_on_too_few_activities(self) -> None:
        payload = LkpdGeneratedPayload(
            lkpd=LkpdContent(
                title="LKPD",
                learning_objectives=["Objektif"],
                instructions=["Instruksi"],
                activities=[
                    LkpdActivity(
                        activity_no=1,
                        task="A1",
                        expected_output="O1",
                        assessment_hint="H1",
                    )
                ],
                worksheet_template="Template",
                assessment_rubric=[
                    LkpdRubricItem(
                        aspect="Aspek",
                        criteria="Kriteria",
                        score_range="1-4",
                    )
                ],
            )
        )

        with self.assertRaises(LkpdValidationError):
            AgentRuntime._enforce_lkpd_contract(
                payload,
                activity_count=2,
                warnings=[],
            )


if __name__ == "__main__":
    unittest.main()
