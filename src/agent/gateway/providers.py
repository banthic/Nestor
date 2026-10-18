"""Provider adapters for the local Ollama runtime and OpenAI-compatible APIs.

Every adapter speaks the same normalized language: a triple
``(content, thinking, tool_calls)`` where ``tool_calls`` is a list of
``{"id", "name", "arguments", "extra_content"?}`` dicts. The streaming variants
also yield :class:`StreamChunk` objects as content, thinking and usage arrive.
"""

import json
import uuid
from typing import Any

import ollama

from .models import StreamChunk


def extract_usage(response) -> dict[str, int] | None:
    """Return prompt/completion/total tokens when the response carries usage."""
    usage = response.get("usage") if isinstance(response, dict) else getattr(response, "usage", None)
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump()
    if not isinstance(usage, dict):
        return None
    values = {
        key: usage[key]
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if isinstance(usage.get(key), int)
    }
    return values or None


def extract_extra_content(call) -> dict[str, Any] | None:
    """Return provider-specific extra_content (e.g. Gemini thought_signature)."""
    extra_content = getattr(call, "extra_content", None)
    if extra_content is None:
        model_extra = getattr(call, "model_extra", None) or {}
        extra_content = model_extra.get("extra_content")
    return extra_content or None


def _normalize_ollama_tool_calls(raw_calls) -> list[dict[str, Any]]:
    tool_calls: list[dict[str, Any]] = []
    for call in raw_calls or []:
        if hasattr(call, "model_dump"):
            call = call.model_dump()
        function = call.get("function", {})
        tool_calls.append({
            "id": call.get("id") or f"call_{uuid.uuid4().hex[:8]}",
            "name": function.get("name"),
            "arguments": function.get("arguments") or {},
        })
    return tool_calls


def call_ollama(model, messages, tool_schemas):
    kwargs = {"model": model, "messages": messages}
    if tool_schemas:
        kwargs["tools"] = tool_schemas
    response = ollama.chat(**kwargs)
    message = response["message"]
    if hasattr(message, "model_dump"):
        message = message.model_dump()

    content = message.get("content") or ""
    thinking = message.get("thinking") or message.get("reasoning_content") or ""
    tool_calls = _normalize_ollama_tool_calls(message.get("tool_calls"))

    return content, thinking, tool_calls


def stream_ollama(model, messages, tool_schemas):
    kwargs = {"model": model, "messages": messages, "stream": True}
    if tool_schemas:
        kwargs["tools"] = tool_schemas

    content_parts: list[str] = []
    thinking_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    usage: dict[str, int] | None = None

    for response in ollama.chat(**kwargs):
        response_usage = extract_usage(response)
        if response_usage:
            usage = response_usage
        message = response["message"]
        if hasattr(message, "model_dump"):
            message = message.model_dump()

        content = message.get("content") or ""
        if content:
            content_parts.append(content)
            yield StreamChunk("content", content)

        thinking = message.get("thinking") or message.get("reasoning_content") or ""
        if thinking:
            thinking_parts.append(thinking)
            yield StreamChunk("thinking", thinking)

        tool_calls.extend(_normalize_ollama_tool_calls(message.get("tool_calls")))

    if usage:
        yield StreamChunk("usage", "", usage=usage)
    return "".join(content_parts), "".join(thinking_parts), tool_calls


def call_openai(client, model, messages, tool_schemas):
    kwargs = {"model": model, "messages": messages}
    if tool_schemas:
        kwargs["tools"] = tool_schemas
    response = client.chat.completions.create(**kwargs)
    message = response.choices[0].message

    content = message.content or ""
    thinking = (
        getattr(message, "thinking", None)
        or getattr(message, "reasoning_content", None)
        or ""
    )

    tool_calls = []
    for call in getattr(message, "tool_calls", None) or []:
        arguments = call.function.arguments
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        tool_call = {
            "id": call.id or f"call_{uuid.uuid4().hex[:8]}",
            "name": call.function.name,
            "arguments": arguments or {},
        }
        extra_content = extract_extra_content(call)
        if extra_content:
            tool_call["extra_content"] = extra_content
        tool_calls.append(tool_call)

    return content, thinking, tool_calls


def stream_openai(client, model, messages, tool_schemas):
    kwargs = {"model": model, "messages": messages, "stream": True}
    if tool_schemas:
        kwargs["tools"] = tool_schemas

    content_parts: list[str] = []
    thinking_parts: list[str] = []
    tool_calls_by_index: dict[int, dict[str, Any]] = {}
    usage: dict[str, int] | None = None

    for chunk in client.chat.completions.create(**kwargs):
        chunk_usage = extract_usage(chunk)
        if chunk_usage:
            usage = chunk_usage
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta

        content = getattr(delta, "content", None)
        if content:
            content_parts.append(content)
            yield StreamChunk("content", content)

        thinking = getattr(delta, "thinking", None) or getattr(delta, "reasoning_content", None)
        if thinking:
            thinking_parts.append(thinking)
            yield StreamChunk("thinking", thinking)

        for call in getattr(delta, "tool_calls", None) or []:
            call_index = getattr(call, "index", None)
            if call_index is None:
                call_index = len(tool_calls_by_index)
            entry = tool_calls_by_index.setdefault(
                call_index,
                {"id": getattr(call, "id", None) or f"call_{uuid.uuid4().hex[:8]}", "name": "", "arguments": "", "extra_content": None},
            )
            function = getattr(call, "function", None)
            name = getattr(function, "name", None) if function else None
            arguments = getattr(function, "arguments", None) if function else None
            if name:
                entry["name"] += name
            if arguments:
                entry["arguments"] += arguments
            extra_content = extract_extra_content(call)
            if extra_content:
                entry["extra_content"] = extra_content

    tool_calls: list[dict[str, Any]] = []
    for entry in tool_calls_by_index.values():
        if not entry["name"]:
            continue
        try:
            arguments = json.loads(entry["arguments"]) if entry["arguments"] else {}
        except json.JSONDecodeError:
            arguments = {}
        tool_call = {"id": entry["id"], "name": entry["name"], "arguments": arguments}
        if entry.get("extra_content"):
            tool_call["extra_content"] = entry["extra_content"]
        tool_calls.append(tool_call)

    if usage:
        yield StreamChunk("usage", "", usage=usage)
    return "".join(content_parts), "".join(thinking_parts), tool_calls
