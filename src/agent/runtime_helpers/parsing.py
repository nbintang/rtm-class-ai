from __future__ import annotations

import ast
import json
import re
from typing import Any

from src.agent.types import LkpdGeneratedPayload, MaterialGeneratedPayload, ToolCallLog


def try_parse_generated_payload(reply: str) -> MaterialGeneratedPayload | None:
    candidate = extract_json_candidate(reply)
    if not candidate:
        return None

    raw = _load_json_lenient(candidate)
    if raw is None:
        return None

    try:
        return MaterialGeneratedPayload.model_validate(raw)
    except Exception:
        return None


def try_parse_lkpd_payload(reply: str) -> LkpdGeneratedPayload | None:
    candidate = extract_json_candidate(reply)
    if not candidate:
        return None

    raw = _load_json_lenient(candidate)
    if raw is None:
        return None

    try:
        return LkpdGeneratedPayload.model_validate(raw)
    except Exception:
        return None


def extract_json_candidate(text: str) -> str:
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


def extract_reply(result: Any) -> str:
    messages = extract_messages(result)
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


def extract_tool_calls(result: Any) -> list[ToolCallLog]:
    logs: list[ToolCallLog] = []
    for message in extract_messages(result):
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


def extract_messages(result: Any) -> list[Any]:
    if isinstance(result, dict):
        messages = result.get("messages")
        if isinstance(messages, list):
            return messages
    return []


def dedupe_warnings(warnings: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for warning in warnings:
        clean = warning.strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        deduped.append(clean)
    return deduped


def _load_json_lenient(candidate: str) -> dict[str, Any] | None:
    normalized = _normalize_json_candidate(candidate)
    for attempt in _json_parse_attempts(normalized):
        try:
            raw = json.loads(attempt)
            if isinstance(raw, dict):
                return raw
        except json.JSONDecodeError:
            continue

    python_like = _js_literal_to_python(normalized)
    for attempt in _json_parse_attempts(python_like):
        try:
            raw = ast.literal_eval(attempt)
            if isinstance(raw, dict):
                return raw
        except (SyntaxError, ValueError):
            continue

    return None


def _normalize_json_candidate(text: str) -> str:
    cleaned = text.strip().lstrip("\ufeff")
    replacements = {
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    return cleaned


def _json_parse_attempts(text: str) -> tuple[str, ...]:
    no_trailing_commas = re.sub(r",(\s*[}\]])", r"\1", text)
    return (text, no_trailing_commas)


def _js_literal_to_python(text: str) -> str:
    out = re.sub(r"\btrue\b", "True", text)
    out = re.sub(r"\bfalse\b", "False", out)
    out = re.sub(r"\bnull\b", "None", out)
    return out

