from __future__ import annotations

import json
from typing import Any

from src.agent.material_extractor import extract_material_text
from src.agent.mcp import MCPToolRegistry
from src.agent.memory import LongTermMemoryStore
from src.agent.model import get_groq_chat_model
from src.agent.prompts import (
    build_lkpd_generation_prompt,
    build_material_generation_prompt,
)
from src.agent.rag import MaterialRAGStore
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
from src.config import settings


class MaterialValidationError(ValueError):
    pass


class LkpdValidationError(ValueError):
    pass


class MaterialTooLargeError(MaterialValidationError):
    pass


class AgentRuntime:
    def __init__(self) -> None:
        self._memory_store = LongTermMemoryStore()
        self._mcp_registry = MCPToolRegistry()
        self._rag_store = MaterialRAGStore()
        self._mcp_tools: list[Any] = []
        self._startup_warnings: list[str] = []
        self._initialized = False

        if self._memory_store.init_warning:
            self._startup_warnings.append(self._memory_store.init_warning)
        if self._rag_store.init_warning:
            self._startup_warnings.append(self._rag_store.init_warning)

    async def initialize(self) -> None:
        if self._initialized:
            return

        self._mcp_tools = await self._mcp_registry.load_tools()
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

        document_id = self._rag_store.new_document_id()
        rag_context, rag_sources, rag_warnings = self._build_rag_context(
            user_id=request.user_id,
            document_id=document_id,
            filename=filename,
            file_type=file_type,
            extracted_text=extracted_text,
            generate_types=request.generate_types,
        )
        warnings.extend(rag_warnings)

        if request.mcp_enabled and self._mcp_registry.has_config and not self._mcp_tools:
            warnings.append("MCP is enabled, but no MCP tools are currently available.")

        # Keep generation deterministic: disable internal memory tools for upload flows
        # so the model returns JSON directly instead of tool-calling loops.
        tools: list[Any] = []
        if request.mcp_enabled:
            tools.extend(self._mcp_tools)

        agent = self._get_agent(tools=tools)
        prompt = build_material_generation_prompt(
            material_text=rag_context,
            generate_types=request.generate_types,
            mcq_count=request.mcq_count,
            essay_count=request.essay_count,
            summary_max_words=request.summary_max_words,
            context="",
        )

        config = {
            "recursion_limit": max(2, settings.agent_max_iterations * 2),
        }
        payload = {"messages": [{"role": "user", "content": prompt}]}

        result = await agent.ainvoke(payload, config=config)
        tool_calls = self._extract_tool_calls(result)
        reply = self._extract_reply(result)

        parsed = self._try_parse_generated_payload(reply)
        if parsed is None:
            retry_prompt = (
                f"{prompt}\n\n"
                "Your previous answer was invalid. Return only valid JSON that matches the required schema."
            )
            retry_result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": retry_prompt}]},
                config=config,
            )
            tool_calls.extend(self._extract_tool_calls(retry_result))
            retry_reply = self._extract_reply(retry_result)
            parsed = self._try_parse_generated_payload(retry_reply)

        if parsed is None:
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

        if "summary" in request.generate_types and payload_out.summary is not None:
            self._memory_store.remember_fact(
                user_id=request.user_id,
                fact=payload_out.summary.overview,
                memory_type="material_summary",
                source="uploaded_material",
                extra_metadata={"filename": filename, "document_id": document_id},
            )

        return MaterialGenerateResponse(
            user_id=request.user_id,
            document_id=document_id,
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

        document_id = self._rag_store.new_document_id()
        rag_context, rag_sources, rag_warnings = self._build_lkpd_rag_context(
            user_id=request.user_id,
            document_id=document_id,
            filename=filename,
            file_type=file_type,
            extracted_text=extracted_text,
        )
        warnings.extend(rag_warnings)

        # LKPD upload flow is JSON generation-only; do not attach tool-calling tools.
        tools: list[Any] = []
        agent = self._get_agent(tools=tools)
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
            document_id=document_id,
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
        warnings: list[str] = []

        try:
            chunk_count, index_warnings = self._rag_store.index_material(
                user_id=user_id,
                document_id=document_id,
                filename=filename,
                file_type=file_type,
                text=extracted_text,
            )
            warnings.extend(index_warnings)
            if chunk_count <= 0:
                warnings.append(
                    "RAG indexing produced no chunks; using extracted text fallback."
                )
                return extracted_text, [], warnings
        except Exception as exc:
            warnings.append(f"RAG indexing failed; using extracted text fallback: {exc}")
            return extracted_text, [], warnings

        queries = self._build_rag_queries(
            extracted_text,
            generate_types=generate_types,
        )
        docs, retrieval_warnings = self._rag_store.retrieve_for_generation(
            user_id=user_id,
            document_id=document_id,
            queries=queries,
        )
        warnings.extend(retrieval_warnings)

        if not docs:
            warnings.append("RAG retrieval returned no chunks; using extracted text fallback.")
            return extracted_text, [], warnings

        context = "\n\n".join(doc.page_content for doc in docs)
        sources: list[SourceRef] = []
        for doc in docs:
            metadata = doc.metadata or {}
            sources.append(
                SourceRef(
                    chunk_id=metadata.get("chunk_id"),
                    source_id=metadata.get("document_id"),
                    excerpt=doc.page_content[:200],
                )
            )

        return context, sources, warnings

    def _build_lkpd_rag_context(
        self,
        *,
        user_id: str,
        document_id: str,
        filename: str,
        file_type: str,
        extracted_text: str,
    ) -> tuple[str, list[SourceRef], list[str]]:
        warnings: list[str] = []

        try:
            chunk_count, index_warnings = self._rag_store.index_material(
                user_id=user_id,
                document_id=document_id,
                filename=filename,
                file_type=file_type,
                text=extracted_text,
            )
            warnings.extend(index_warnings)
            if chunk_count <= 0:
                warnings.append(
                    "RAG indexing produced no chunks; using extracted text fallback."
                )
                return extracted_text, [], warnings
        except Exception as exc:
            warnings.append(f"RAG indexing failed; using extracted text fallback: {exc}")
            return extracted_text, [], warnings

        queries = self._build_lkpd_rag_queries(extracted_text)
        docs, retrieval_warnings = self._rag_store.retrieve_for_generation(
            user_id=user_id,
            document_id=document_id,
            queries=queries,
        )
        warnings.extend(retrieval_warnings)

        if not docs:
            warnings.append("RAG retrieval returned no chunks; using extracted text fallback.")
            return extracted_text, [], warnings

        context = "\n\n".join(doc.page_content for doc in docs)
        sources: list[SourceRef] = []
        for doc in docs:
            metadata = doc.metadata or {}
            sources.append(
                SourceRef(
                    chunk_id=metadata.get("chunk_id"),
                    source_id=metadata.get("document_id"),
                    excerpt=doc.page_content[:200],
                )
            )

        return context, sources, warnings

    @staticmethod
    def _build_rag_queries(
        extracted_text: str,
        *,
        generate_types: list[GenerateType],
    ) -> list[str]:
        topic_hint = " ".join(extracted_text.split()[:40])
        queries = [f"konsep utama materi {topic_hint}"]
        if "summary" in generate_types:
            queries.append(f"ringkasan konsep utama materi {topic_hint}")
        if "mcq" in generate_types:
            queries.append(
                f"fakta penting dan konsep untuk kuis pilihan ganda {topic_hint}"
            )
        if "essay" in generate_types:
            queries.append(f"pemahaman mendalam untuk soal essay {topic_hint}")
        return queries

    @staticmethod
    def _build_lkpd_rag_queries(extracted_text: str) -> list[str]:
        topic_hint = " ".join(extracted_text.split()[:40])
        return [
            f"konsep utama dan tujuan pembelajaran materi {topic_hint}",
            f"langkah kegiatan praktikum atau aktivitas pembelajaran {topic_hint}",
            f"indikator penilaian dan rubrik tugas untuk materi {topic_hint}",
        ]

    def _get_agent(self, *, tools: list[Any]):
        try:
            from langchain.agents import create_agent
        except ImportError as exc:
            raise RuntimeError(
                "langchain is not installed. Install dependencies before using /api/material."
            ) from exc

        return create_agent(
            model=get_groq_chat_model(),
            tools=tools,
        )

    def _build_internal_tools(self, *, user_id: str) -> list[Any]:
        try:
            from langchain_core.tools import tool
        except ImportError as exc:
            raise RuntimeError(
                "langchain-core is not installed. Install dependencies before using /api/material."
            ) from exc

        memory_store = self._memory_store

        @tool
        def remember_user_fact(fact: str, memory_type: str = "general") -> str:
            """Save a durable user fact into long-term memory."""
            memory_id = memory_store.remember_fact(
                user_id=user_id,
                fact=fact,
                memory_type=memory_type,
            )
            if not memory_id:
                return "No memory saved because the fact was empty."
            return f"Saved memory with id {memory_id}."

        @tool
        def recall_user_facts(query: str = "", limit: int = 5) -> str:
            """Recall previously saved user facts for personalization."""
            docs = memory_store.recall_user_facts(
                user_id=user_id,
                query=query,
                limit=limit,
            )
            if not docs:
                return "No memories found for this user."

            lines: list[str] = []
            for idx, doc in enumerate(docs, start=1):
                metadata = doc.metadata or {}
                memory_type = metadata.get("memory_type", "general")
                created_at = metadata.get("created_at", "unknown")
                lines.append(
                    f"{idx}. [{memory_type}] ({created_at}) {doc.page_content}"
                )
            return "\n".join(lines)

        return [remember_user_fact, recall_user_facts]

    @staticmethod
    def _try_parse_generated_payload(reply: str) -> MaterialGeneratedPayload | None:
        candidate = AgentRuntime._extract_json_candidate(reply)
        if not candidate:
            return None

        try:
            raw = json.loads(candidate)
        except json.JSONDecodeError:
            return None

        try:
            return MaterialGeneratedPayload.model_validate(raw)
        except Exception:
            return None

    @staticmethod
    def _try_parse_lkpd_payload(reply: str) -> LkpdGeneratedPayload | None:
        candidate = AgentRuntime._extract_json_candidate(reply)
        if not candidate:
            return None

        try:
            raw = json.loads(candidate)
        except json.JSONDecodeError:
            return None

        try:
            return LkpdGeneratedPayload.model_validate(raw)
        except Exception:
            return None

    @staticmethod
    def _extract_json_candidate(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                stripped = "\n".join(lines[1:-1]).strip()

        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return ""
        return stripped[start : end + 1]

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
        selected = set(generate_types)

        if "mcq" in selected:
            if payload.mcq_quiz is None:
                raise MaterialValidationError("Model did not return mcq_quiz.")

            mcq_questions = payload.mcq_quiz.questions
            if len(mcq_questions) < mcq_count:
                raise MaterialValidationError(
                    f"Model generated too few multiple-choice questions ({len(mcq_questions)} < {mcq_count})."
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
                raise MaterialValidationError("Model did not return essay_quiz.")

            essay_questions = payload.essay_quiz.questions
            if len(essay_questions) < essay_count:
                raise MaterialValidationError(
                    f"Model generated too few essay questions ({len(essay_questions)} < {essay_count})."
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
                raise MaterialValidationError("Model did not return summary.")

            overview_words = payload.summary.overview.split()
            if len(overview_words) > summary_max_words:
                warnings.append(
                    f"Summary overview trimmed from {len(overview_words)} to {summary_max_words} words."
                )
                payload.summary.overview = " ".join(overview_words[:summary_max_words])
        elif payload.summary is not None:
            warnings.append("Model returned summary even though it was not requested.")
            payload.summary = None

        return payload

    @staticmethod
    def _enforce_lkpd_contract(
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

    @staticmethod
    def _extract_reply(result: Any) -> str:
        messages = AgentRuntime._extract_messages(result)
        for message in reversed(messages):
            message_type = getattr(message, "type", "")
            if message_type != "ai":
                continue

            content = getattr(message, "content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()

            if isinstance(content, list):
                chunks: list[str] = []
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text")
                        if isinstance(text, str) and text.strip():
                            chunks.append(text.strip())
                if chunks:
                    return "\n".join(chunks)

        if isinstance(result, dict):
            output = result.get("output")
            if isinstance(output, str) and output.strip():
                return output.strip()

        return ""

    @staticmethod
    def _extract_tool_calls(result: Any) -> list[ToolCallLog]:
        logs: list[ToolCallLog] = []
        for message in AgentRuntime._extract_messages(result):
            raw_calls = getattr(message, "tool_calls", None)
            if not raw_calls:
                continue

            for call in raw_calls:
                if not isinstance(call, dict):
                    continue

                arguments = call.get("args", {})
                if isinstance(arguments, str):
                    try:
                        parsed = json.loads(arguments)
                        arguments = parsed if isinstance(parsed, dict) else {"raw": arguments}
                    except json.JSONDecodeError:
                        arguments = {"raw": arguments}
                elif not isinstance(arguments, dict):
                    arguments = {"value": arguments}

                logs.append(
                    ToolCallLog(
                        name=str(call.get("name", "")),
                        arguments=arguments,
                        call_id=call.get("id"),
                    )
                )

        return logs

    @staticmethod
    def _extract_messages(result: Any) -> list[Any]:
        if isinstance(result, dict):
            messages = result.get("messages")
            if isinstance(messages, list):
                return messages
        return []

    @staticmethod
    def _dedupe_warnings(warnings: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for warning in warnings:
            clean = warning.strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            deduped.append(clean)
        return deduped
