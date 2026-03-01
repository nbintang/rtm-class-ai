from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pydantic import ValidationError

from src.agent.types import (
    CallbackErrorInfo,
    LkpdAsyncSubmitRequest,
    LkpdGenerateResult,
    LkpdGenerateRuntimeResult,
    LkpdSubmitAcceptedResponse,
    MaterialAsyncSubmitRequest,
    MaterialGenerateResponse,
    MaterialInfo,
    MaterialWebhookResultPayload,
    LkpdWebhookResultPayload,
    MaterialUploadRequest,
    MaterialSubmitAcceptedResponse,
    McqQuestion,
    LkpdContent,
    LkpdActivity,
    LkpdRubricItem,
)


class MaterialUploadRequestTests(unittest.TestCase):
    def test_valid_payload(self) -> None:
        payload = MaterialUploadRequest(
            user_id="user-1",
            generate_types=["mcq", "summary"],
            mcq_count=10,
            essay_count=3,
            summary_max_words=200,
            mcp_enabled=True,
        )
        self.assertEqual(payload.user_id, "user-1")
        self.assertEqual(payload.mcq_count, 10)
        self.assertEqual(payload.generate_types, ["mcq", "summary"])

    def test_rejects_empty_user_id(self) -> None:
        with self.assertRaises(ValidationError):
            MaterialUploadRequest(
                user_id="",
                generate_types=["mcq"],
            )

    def test_rejects_out_of_range_counts(self) -> None:
        with self.assertRaises(ValidationError):
            MaterialUploadRequest(
                user_id="user-1",
                generate_types=["mcq"],
                mcq_count=0,
            )

    def test_rejects_missing_generate_types(self) -> None:
        with self.assertRaises(ValidationError):
            MaterialUploadRequest(
                user_id="user-1",
            )

    def test_rejects_empty_generate_types(self) -> None:
        with self.assertRaises(ValidationError):
            MaterialUploadRequest(
                user_id="user-1",
                generate_types=[],
            )

    def test_rejects_invalid_generate_type(self) -> None:
        with self.assertRaises(ValidationError):
            MaterialUploadRequest(
                user_id="user-1",
                generate_types=["lkpd"],
            )

    def test_rejects_duplicate_generate_types(self) -> None:
        with self.assertRaises(ValidationError):
            MaterialUploadRequest(
                user_id="user-1",
                generate_types=["mcq", "mcq"],
            )

    def test_rejects_legacy_thread_id_field(self) -> None:
        with self.assertRaises(ValidationError):
            MaterialUploadRequest.model_validate(
                {
                    "user_id": "user-1",
                    "generate_types": ["mcq"],
                    "thread_id": "legacy",
                }
            )


class McqQuestionTests(unittest.TestCase):
    def test_accepts_four_unique_options(self) -> None:
        question = McqQuestion(
            question="Apa ibu kota Indonesia?",
            options=["Bandung", "Medan", "Jakarta", "Surabaya"],
            correct_answer="Jakarta",
            explanation="Ibu kota Indonesia adalah Jakarta.",
        )
        self.assertEqual(len(question.options), 4)

    def test_rejects_when_correct_answer_not_in_options(self) -> None:
        with self.assertRaises(ValidationError):
            McqQuestion(
                question="Contoh soal",
                options=["A", "B", "C", "D"],
                correct_answer="E",
                explanation="Penjelasan",
            )


class MaterialAsyncSubmitRequestTests(unittest.TestCase):
    def test_accepts_valid_callback_url(self) -> None:
        payload = MaterialAsyncSubmitRequest(
            user_id="user-1",
            callback_url="https://example.com/webhook",
            generate_types=["summary"],
        )
        self.assertEqual(str(payload.callback_url), "https://example.com/webhook")
        material_request = payload.to_material_upload_request()
        self.assertIsInstance(material_request, MaterialUploadRequest)
        self.assertEqual(material_request.generate_types, ["summary"])

    def test_rejects_invalid_callback_url(self) -> None:
        with self.assertRaises(ValidationError):
            MaterialAsyncSubmitRequest(
                user_id="user-1",
                callback_url="not-a-url",
                generate_types=["summary"],
            )


class AsyncCallbackPayloadTests(unittest.TestCase):
    def test_accepted_response_defaults(self) -> None:
        response = MaterialSubmitAcceptedResponse(job_id="job-1")
        self.assertEqual(response.status, "accepted")
        self.assertEqual(response.message, "Material queued for async processing.")

    def test_webhook_success_payload_requires_result(self) -> None:
        payload = MaterialWebhookResultPayload(
            job_id="job-1",
            status="succeeded",
            user_id="user-1",
            result=MaterialGenerateResponse(
                user_id="user-1",
                document_id="doc-1",
                material=MaterialInfo(
                    filename="materi.txt",
                    file_type="txt",
                    extracted_chars=10,
                ),
            ),
            attempt=1,
            finished_at=datetime.now(UTC),
        )
        self.assertEqual(payload.status, "succeeded")

    def test_webhook_failed_payload_requires_error(self) -> None:
        payload = MaterialWebhookResultPayload(
            job_id="job-1",
            status="failed_processing",
            user_id="user-1",
            error=CallbackErrorInfo(
                code="material_validation_error",
                message="Unsupported file type",
            ),
            attempt=1,
            finished_at=datetime.now(UTC),
        )
        self.assertEqual(payload.status, "failed_processing")


class LkpdRequestAndPayloadTests(unittest.TestCase):
    def test_lkpd_submit_request_accepts_valid_callback(self) -> None:
        payload = LkpdAsyncSubmitRequest(
            user_id="user-1",
            callback_url="https://example.com/lkpd-callback",
            activity_count=7,
        )
        self.assertEqual(str(payload.callback_url), "https://example.com/lkpd-callback")
        request = payload.to_lkpd_upload_request()
        self.assertEqual(request.activity_count, 7)

    def test_lkpd_submit_request_rejects_out_of_range_activity_count(self) -> None:
        with self.assertRaises(ValidationError):
            LkpdAsyncSubmitRequest(
                user_id="user-1",
                callback_url="https://example.com/lkpd-callback",
                activity_count=0,
            )

    def test_lkpd_accepted_response_defaults(self) -> None:
        response = LkpdSubmitAcceptedResponse(job_id="job-lkpd")
        self.assertEqual(response.status, "accepted")
        self.assertEqual(response.message, "LKPD queued for async processing.")

    def test_lkpd_webhook_success_payload_requires_result(self) -> None:
        runtime_result = LkpdGenerateRuntimeResult(
            document_id="doc-1",
            material=MaterialInfo(
                filename="materi.txt",
                file_type="txt",
                extracted_chars=120,
            ),
            lkpd=LkpdContent(
                title="LKPD Ekosistem",
                learning_objectives=["Memahami rantai makanan"],
                instructions=["Baca materi", "Kerjakan aktivitas"],
                activities=[
                    LkpdActivity(
                        activity_no=1,
                        task="Jelaskan rantai makanan sederhana",
                        expected_output="Diagram rantai makanan",
                        assessment_hint="Ketepatan komponen produsen-konsumen",
                    )
                ],
                worksheet_template="Nama: ...\nKelas: ...\nJawaban: ...",
                assessment_rubric=[
                    LkpdRubricItem(
                        aspect="Konsep",
                        criteria="Kelengkapan",
                        score_range="1-4",
                    )
                ],
            ),
        )
        payload = LkpdWebhookResultPayload(
            job_id="job-1",
            status="succeeded",
            user_id="user-1",
            result=LkpdGenerateResult(
                **runtime_result.model_dump(),
                pdf_url="http://localhost:8000/api/lkpd/files/lkpd-1",
                pdf_expires_at=datetime.now(UTC),
            ),
            attempt=1,
            finished_at=datetime.now(UTC),
        )
        self.assertEqual(payload.status, "succeeded")

    def test_lkpd_webhook_failed_payload_requires_error(self) -> None:
        payload = LkpdWebhookResultPayload(
            job_id="job-1",
            status="failed_processing",
            user_id="user-1",
            error=CallbackErrorInfo(
                code="lkpd_validation_error",
                message="LKPD JSON invalid",
            ),
            attempt=1,
            finished_at=datetime.now(UTC),
        )
        self.assertEqual(payload.status, "failed_processing")


if __name__ == "__main__":
    unittest.main()
