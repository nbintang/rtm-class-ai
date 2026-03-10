from __future__ import annotations

import logging
from typing import Any

from src.agent.infra.mcp_registry import MCPToolRegistry
from src.agent.infra.memory_store import LongTermMemoryStore
from src.agent.material_extractor import extract_material_text
from src.agent.rag import MaterialRAGStore
from src.agent.runtime_helpers.agent_factory import create_generation_agent
from src.agent.runtime_helpers.contracts import (
    build_mcp_insert_plan,
    enforce_generation_contract,
    enforce_lkpd_contract,
)
from src.agent.runtime_helpers.errors import (
    LkpdValidationError,
    MaterialTooLargeError,
    MaterialValidationError,
)
from src.agent.runtime_helpers.internal_tools import build_internal_tools
from src.agent.runtime_helpers.mcp_insert import insert_material_payload_via_mcp
from src.agent.runtime_helpers.parsing import (
    dedupe_warnings,
    extract_json_candidate,
    extract_messages,
    extract_reply,
    extract_tool_calls,
    try_parse_generated_payload,
    try_parse_lkpd_payload,
)
from src.agent.runtime_helpers.rag_context import (
    build_lkpd_rag_context,
    build_lkpd_rag_queries,
    build_rag_context,
    build_rag_queries,
)
from src.agent.types import (
    GenerateType,
    LkpdGenerateRuntimeResult,
    LkpdGeneratedPayload,
    LkpdUploadRequest,
    MaterialGenerateResponse,
    MaterialGeneratedPayload,
    MaterialInfo,
    MaterialUploadRequest,
    SourceRef,
    ToolCallLog,
)
from src.agent.prompts import (
    build_lkpd_generation_prompt,
    build_material_generation_prompt,
)
from src.config import settings


logger = logging.getLogger(__name__)


class AgentRuntime:
    def __init__(self) -> None:
        self._memory_store = LongTermMemoryStore()
        self._mcp_registry = MCPToolRegistry()
        self._rag_store = MaterialRAGStore()
        self._startup_warnings: list[str] = []
        self._initialized = False

        if self._memory_store.init_warning:
            self._startup_warnings.append(self._memory_store.init_warning)
        if self._rag_store.init_warning:
            self._startup_warnings.append(self._rag_store.init_warning)

    async def initialize(self) -> None:
        if self._initialized:
            return

        await self._mcp_registry.load_tools()
        self._startup_warnings.extend(self._mcp_registry.warnings)
        self._initialized = True

    async def shutdown(self) -> None:
        await self._mcp_registry.close()
        self._initialized = False

    async def invoke_material_upload(
        self,
        *,
        request: MaterialUploadRequest,
        file_bytes: bytes,
        filename: str,
        content_type: str | None,
        document_id: str | None = None,
        job_id: str | None = None,
        requested_by_id: str | None = None,
    ) -> MaterialGenerateResponse:
        await self.initialize()

        max_bytes = settings.material_max_file_mb * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise MaterialTooLargeError(
                f"File exceeds maximum size of {settings.material_max_file_mb} MB."
            )

        warnings: list[str] = list(self._startup_warnings)

        extracted_text, file_type, extract_warnings = extract_material_text(
            filename=filename,
            content_type=content_type,
            payload=file_bytes,
        )
        warnings.extend(extract_warnings)

        doc_id = document_id or self._rag_store.new_document_id()
        rag_context, rag_sources, rag_warnings = self._build_rag_context(
            user_id=request.user_id,
            document_id=doc_id,
            filename=filename,
            file_type=file_type,
            extracted_text=extracted_text,
            generate_types=request.generate_types,
        )
        warnings.extend(rag_warnings)

        mcp_tools = await self._mcp_registry.load_tools()
        if request.mcp_enabled and self._mcp_registry.has_config and not mcp_tools:
            warnings.append("MCP is enabled, but no MCP tools are currently available.")
 
        # Use the actual Job ID for the prompt, fallback to doc_id if not provided
        actual_job_id = job_id or doc_id
 
        # Pass the IDs to the prompt so the LLM knows what to call the MCP tools with.
        ids_context = (
            f"ID Informasi Penting:\n"
            f"- job_id: {actual_job_id}\n"
            f"- user_id: {request.user_id}\n"
            f"- material_id: {doc_id}\n"
        )

        # Keep generation deterministic and prevent provider-side tool argument failures:
        # generation step is JSON-only; MCP tools are invoked programmatically afterward.
        agent = self._get_agent(tools=[])
        prompt = build_material_generation_prompt(
            material_text=rag_context,
            generate_types=request.generate_types,
            mcq_count=request.mcq_count,
            essay_count=request.essay_count,
            summary_max_words=request.summary_max_words,
            context=ids_context,
        )

        config = {
            "recursion_limit": max(2, settings.agent_max_iterations * 2),
        }
        payload = {"messages": [{"role": "user", "content": prompt}]}

        result = await agent.ainvoke(payload, config=config)
        reply = self._extract_reply(result)

        parsed = self._try_parse_generated_payload(reply)
        if parsed is None:
            logger.warning(
                "model_output_validation_failed stage=initial_parse user_id=%s reply_preview=%s",
                request.user_id,
                self._preview_text(reply),
            )
            warnings.append("model_output_validation_failed:initial_parse")
            retry_prompt = (
                f"{prompt}\n\n"
                "Your previous answer was invalid. Return only valid JSON that matches the required schema.\n\n"
                f"Invalid answer to repair:\n{reply}"
            )
            retry_result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": retry_prompt}]},
                config=config,
            )
            retry_reply = self._extract_reply(retry_result)
            parsed = self._try_parse_generated_payload(retry_reply)

        if parsed is None:
            logger.error(
                "model_output_validation_failed stage=repair_parse user_id=%s reply_preview=%s",
                request.user_id,
                self._preview_text(retry_reply if "retry_reply" in locals() else reply),
            )
            raise MaterialValidationError(
                "Model failed to produce valid JSON output after one retry."
            )

        payload_out = self._enforce_generation_contract(
            parsed,
            generate_types=request.generate_types,
            mcq_count=request.mcq_count,
            essay_count=request.essay_count,
            summary_max_words=request.summary_max_words,
            warnings=warnings,
        )
        tool_calls: list[ToolCallLog] = []

        if request.mcp_enabled:
            missing_identifiers: list[str] = []
            if not job_id:
                missing_identifiers.append("job_id")
            if not material_id:
                missing_identifiers.append("material_id")
            if not requested_by_id:
                missing_identifiers.append("requested_by_id")

            if missing_identifiers:
                warnings.append(
                    "mcp_insert_failed:missing_required_identifiers:"
                    + ",".join(missing_identifiers)
                )
            else:
                mcp_tool_calls, mcp_warnings = await self._insert_material_payload_via_mcp(
                    job_id=job_id,
                    material_id=material_id,
                    requested_by_id=requested_by_id,
                    payload=payload_out,
                    requested_types=request.generate_types,
                )
                tool_calls.extend(mcp_tool_calls)
                warnings.extend(mcp_warnings)

        if "summary" in request.generate_types and payload_out.summary is not None:
            self._memory_store.remember_fact(
                user_id=request.user_id,
                fact=payload_out.summary.overview,
                memory_type="material_summary",
                source="uploaded_material",
                extra_metadata={"filename": filename, "document_id": doc_id},
            )

        return MaterialGenerateResponse(
            user_id=request.user_id,
            document_id=doc_id,
            material=MaterialInfo(
                filename=filename,
                file_type=file_type,
                extracted_chars=len(extracted_text),
            ),
            mcq_quiz=payload_out.mcq_quiz,
            essay_quiz=payload_out.essay_quiz,
            summary=payload_out.summary,
            sources=rag_sources,
            tool_calls=tool_calls,
            warnings=self._dedupe_warnings(warnings),
        )

    async def invoke_lkpd_upload(
        self,
        *,
        request: LkpdUploadRequest,
        file_bytes: bytes,
        filename: str,
        content_type: str | None,
        document_id: str | None = None,
        job_id: str | None = None,
    ) -> LkpdGenerateRuntimeResult:
        await self.initialize()

        max_bytes = settings.material_max_file_mb * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise MaterialTooLargeError(
                f"File exceeds maximum size of {settings.material_max_file_mb} MB."
            )

        warnings: list[str] = list(self._startup_warnings)
        extracted_text, file_type, extract_warnings = extract_material_text(
            filename=filename,
            content_type=content_type,
            payload=file_bytes,
        )
        warnings.extend(extract_warnings)

        doc_id = document_id or self._rag_store.new_document_id()
        rag_context, rag_sources, rag_warnings = self._build_lkpd_rag_context(
            user_id=request.user_id,
            document_id=doc_id,
            filename=filename,
            file_type=file_type,
            extracted_text=extracted_text,
        )
        warnings.extend(rag_warnings)

        # LKPD upload flow is JSON generation-only; do not attach tool-calling tools.
        agent = self._get_agent(tools=[])
        prompt = build_lkpd_generation_prompt(
            material_text=rag_context,
            activity_count=request.activity_count,
            context="",
        )

        config = {
            "recursion_limit": max(2, settings.agent_max_iterations * 2),
        }
        payload = {"messages": [{"role": "user", "content": prompt}]}

        result = await agent.ainvoke(payload, config=config)
        reply = self._extract_reply(result)

        parsed = self._try_parse_lkpd_payload(reply)
        if parsed is None:
            retry_prompt = (
                f"{prompt}\n\n"
                "Your previous answer was invalid. Return only valid JSON that matches the required schema."
            )
            retry_result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": retry_prompt}]},
                config=config,
            )
            retry_reply = self._extract_reply(retry_result)
            parsed = self._try_parse_lkpd_payload(retry_reply)

        if parsed is None:
            raise LkpdValidationError(
                "Model failed to produce valid LKPD JSON output after one retry."
            )

        payload_out = self._enforce_lkpd_contract(
            parsed,
            activity_count=request.activity_count,
            warnings=warnings,
        )

        return LkpdGenerateRuntimeResult(
            document_id=doc_id,
            material=MaterialInfo(
                filename=filename,
                file_type=file_type,
                extracted_chars=len(extracted_text),
            ),
            lkpd=payload_out.lkpd,
            sources=rag_sources,
            warnings=self._dedupe_warnings(warnings),
        )

    def _build_rag_context(
        self,
        *,
        user_id: str,
        document_id: str,
        filename: str,
        file_type: str,
        extracted_text: str,
        generate_types: list[GenerateType],
    ) -> tuple[str, list[SourceRef], list[str]]:
        return build_rag_context(
            rag_store=self._rag_store,
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            file_type=file_type,
            extracted_text=extracted_text,
            generate_types=generate_types,
        )

    def _build_lkpd_rag_context(
        self,
        *,
        user_id: str,
        document_id: str,
        filename: str,
        file_type: str,
        extracted_text: str,
    ) -> tuple[str, list[SourceRef], list[str]]:
        return build_lkpd_rag_context(
            rag_store=self._rag_store,
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            file_type=file_type,
            extracted_text=extracted_text,
        )

    @staticmethod
    def _build_rag_queries(
        extracted_text: str,
        *,
        generate_types: list[GenerateType],
    ) -> list[str]:
        return build_rag_queries(extracted_text, generate_types=generate_types)

    @staticmethod
    def _build_lkpd_rag_queries(extracted_text: str) -> list[str]:
        return build_lkpd_rag_queries(extracted_text)

    def _get_agent(self, *, tools: list[Any]):
        return create_generation_agent(tools=tools)

    async def _insert_material_payload_via_mcp(
        self,
        *,
        job_id: str,
        material_id: str,
        requested_by_id: str,
        payload: MaterialGeneratedPayload,
        requested_types: list[GenerateType],
    ) -> tuple[list[ToolCallLog], list[str]]:
        return await insert_material_payload_via_mcp(
            registry=self._mcp_registry,
            logger=logger,
            job_id=job_id,
            material_id=material_id,
            requested_by_id=requested_by_id,
            payload=payload,
            requested_types=requested_types,
        )

    @staticmethod
    def _build_mcp_insert_plan(
        *,
        job_id: str,
        material_id: str,
        requested_by_id: str,
        payload: MaterialGeneratedPayload,
        requested_types: list[GenerateType],
    ) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        return build_mcp_insert_plan(
            job_id=job_id,
            material_id=material_id,
            requested_by_id=requested_by_id,
            payload=payload,
            requested_types=requested_types,
        )

    def _build_internal_tools(self, *, user_id: str) -> list[Any]:
        return build_internal_tools(memory_store=self._memory_store, user_id=user_id)

    @staticmethod
    def _try_parse_generated_payload(reply: str) -> MaterialGeneratedPayload | None:
        return try_parse_generated_payload(reply)

    @staticmethod
    def _try_parse_lkpd_payload(reply: str) -> LkpdGeneratedPayload | None:
        return try_parse_lkpd_payload(reply)

    @staticmethod
    def _extract_json_candidate(text: str) -> str:
        return extract_json_candidate(text)

    @staticmethod
    def _enforce_generation_contract(
        payload: MaterialGeneratedPayload,
        *,
        generate_types: list[GenerateType],
        mcq_count: int,
        essay_count: int,
        summary_max_words: int,
        warnings: list[str],
    ) -> MaterialGeneratedPayload:
        return enforce_generation_contract(
            payload,
            generate_types=generate_types,
            mcq_count=mcq_count,
            essay_count=essay_count,
            summary_max_words=summary_max_words,
            warnings=warnings,
            logger=logger,
        )

    @staticmethod
    def _enforce_lkpd_contract(
        payload: LkpdGeneratedPayload,
        *,
        activity_count: int,
        warnings: list[str],
    ) -> LkpdGeneratedPayload:
        return enforce_lkpd_contract(
            payload,
            activity_count=activity_count,
            warnings=warnings,
        )

    @staticmethod
    def _extract_reply(result: Any) -> str:
        return extract_reply(result)

    @staticmethod
    def _extract_tool_calls(result: Any) -> list[ToolCallLog]:
        return extract_tool_calls(result)

    @staticmethod
    def _extract_messages(result: Any) -> list[Any]:
        return extract_messages(result)

    @staticmethod
    def _dedupe_warnings(warnings: list[str]) -> list[str]:
        return dedupe_warnings(warnings)

    @staticmethod
    def _preview_text(text: str, *, limit: int = 320) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return f"{compact[: limit - 3]}..."


__all__ = [
    "AgentRuntime",
    "MaterialValidationError",
    "LkpdValidationError",
    "MaterialTooLargeError",
]

