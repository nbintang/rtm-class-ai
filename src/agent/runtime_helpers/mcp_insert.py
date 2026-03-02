from __future__ import annotations

import logging
from typing import Any

from src.agent.infra.mcp_registry import MCPToolRegistry
from src.agent.runtime_helpers.contracts import build_mcp_insert_plan
from src.agent.types import GenerateType, MaterialGeneratedPayload, ToolCallLog


async def insert_material_payload_via_mcp(
    *,
    registry: MCPToolRegistry,
    logger: logging.Logger,
    job_id: str,
    user_id: str,
    document_id: str,
    payload: MaterialGeneratedPayload,
    requested_types: list[GenerateType],
) -> tuple[list[ToolCallLog], list[str]]:
    warnings: list[str] = []
    calls: list[ToolCallLog] = []

    plans, plan_warnings = build_mcp_insert_plan(
        job_id=job_id,
        user_id=user_id,
        document_id=document_id,
        payload=payload,
        requested_types=requested_types,
    )
    warnings.extend(plan_warnings)

    for tool_name, args in plans:
        try:
            result = await registry.call_mcp_tool(
                tool_name=tool_name,
                args=args,
            )
            call_id = _extract_call_id(result)
            calls.append(
                ToolCallLog(
                    name=tool_name,
                    arguments=args,
                    call_id=call_id,
                )
            )
        except Exception as exc:
            logger.exception(
                "mcp_insert_failed tool=%s job_id=%s document_id=%s",
                tool_name,
                job_id,
                document_id,
            )
            warnings.append(f"mcp_insert_failed:{tool_name}:{exc}")

    return calls, warnings


def _extract_call_id(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None

    maybe_call_id = result.get("call_id") or result.get("id")
    if maybe_call_id is None:
        return None
    return str(maybe_call_id)

