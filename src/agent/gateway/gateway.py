"""Gateway: orchestrates provider calls and the agent tool-use loop.

This module owns the wiring only. Provider communication lives in
:mod:`agent.gateway.providers`, and message normalization in
:mod:`agent.gateway.messages`.
"""

import os
from time import perf_counter

from openai import OpenAI

from ..observability import log_event, log_exception
from ..tools import QuitRequested, execute_tool, to_schemas
from . import providers
from .config import load_config
from .loop import DEFAULT_MAX_ITERATIONS, DEFAULT_MAX_TOOL_CALLS, AgentLoop
from .messages import assistant_message, build_messages, tool_result_message
from .models import ModelResponse, StreamChunk
from .prompts import SYSTEM_PROMPT

LOCAL_PROVIDER = "local_ollama"
EXTERNAL_PROVIDER = "external_api_openai_compatible"


class Gateway:
    def __init__(self, tools=None, system_prompt=None, system_prompt_suffix=None):
        config = load_config()
        self.default_provider = config["default_provider"]
        self.ollama_model = config["provider"][LOCAL_PROVIDER]["model"]
        self.openai_model = config["provider"][EXTERNAL_PROVIDER].get("model")
        self.base_url = config["provider"][EXTERNAL_PROVIDER].get("base_url")
        self.system_prompt = system_prompt or SYSTEM_PROMPT
        self.system_prompt_suffix = system_prompt_suffix
        self.tools = list(tools or [])
        if self.openai_model and self.default_provider == EXTERNAL_PROVIDER:
            api_key = os.getenv("EXTERNAL_API_KEY") or os.getenv("OPENAI_API_KEY")
            self.openai_client = OpenAI(base_url=self.base_url, api_key=api_key)

    def _build_messages(self, prompt, history):
        return build_messages(
            prompt,
            history,
            system_prompt=self.system_prompt,
            system_prompt_suffix=self.system_prompt_suffix,
        )

    def generate_text(
        self,
        prompt,
        history=None,
        tools=None,
        max_tool_iterations=DEFAULT_MAX_ITERATIONS,
        max_tool_calls=DEFAULT_MAX_TOOL_CALLS,
    ):
        messages = self._build_messages(prompt, history)
        active_tools, tool_schemas = self._resolve_tools(tools)
        loop = AgentLoop(max_iterations=max_tool_iterations, max_tool_calls=max_tool_calls)
        failed_tools: list[tuple[str, str]] = []

        while loop.start_iteration():
            round_started = perf_counter()
            log_event(
                "agent.model_round.started",
                round=loop.iterations,
                provider=self.default_provider,
                model=self.ollama_model if self.default_provider == LOCAL_PROVIDER else self.openai_model,
                message_count=len(messages),
            )
            try:
                content, thinking, tool_calls = self._call_provider(messages, tool_schemas)
            except Exception as error:
                log_exception("agent.model_round.failed", error, round=loop.iterations)
                raise
            log_event(
                "agent.model_round.completed",
                round=loop.iterations,
                duration_ms=round((perf_counter() - round_started) * 1000),
                requested_tools=[call["name"] for call in tool_calls],
                response_chars=len(content),
                response=content,
            )

            if not tool_calls:
                log_event("agent.request.completed", rounds=loop.iterations, tool_calls=loop.tool_calls)
                return ModelResponse(
                    content=self._append_tool_failure_notice(content, failed_tools),
                    thinking=thinking,
                )

            messages.append(assistant_message(content, tool_calls, self.default_provider))
            for call in tool_calls:
                if not loop.reserve_tool_call():
                    log_event("agent.tool_budget.exhausted", tool=call["name"], level=40)
                    return ModelResponse(content=loop.tool_limit_message(), thinking=thinking)
                tool_started = perf_counter()
                log_event("agent.tool.started", tool=call["name"], arguments=call.get("arguments", {}))
                output = self._run_tool(active_tools, call)
                log_event(
                    "agent.tool.completed",
                    tool=call["name"],
                    duration_ms=round((perf_counter() - tool_started) * 1000),
                    failed=self._is_tool_failure(call["name"], output),
                    result=output,
                )
                if self._is_tool_failure(call["name"], output):
                    failed_tools.append((call["name"], output))
                messages.append(tool_result_message(call, output, self.default_provider))
                if call["name"] == "finish_task":
                    log_event("agent.request.completed", rounds=loop.iterations, tool_calls=loop.tool_calls, finish_tool=True)
                    return ModelResponse(
                        content=self._append_tool_failure_notice(output, failed_tools),
                        thinking=thinking,
                    )

        log_event("agent.iteration_budget.exhausted", rounds=loop.iterations, level=40)
        log_event("agent.finalization.started", rounds=loop.iterations)
        try:
            content, thinking, tool_calls = self._call_provider(messages, None)
        except Exception as error:
            log_exception("agent.finalization.failed", error, rounds=loop.iterations)
            raise
        if tool_calls:
            log_event(
                "agent.finalization.requested_tools_without_budget",
                requested_tools=[call["name"] for call in tool_calls],
                level=40,
            )
            failed_tools.extend(
                (call["name"], "Action not run because the reasoning-round budget was exhausted.")
                for call in tool_calls
            )
        if not content.strip():
            content = loop.iteration_limit_message()
        content = self._append_tool_failure_notice(content, failed_tools)
        log_event(
            "agent.finalization.completed",
            rounds=loop.iterations,
            response_chars=len(content),
            requested_tools=[call["name"] for call in tool_calls],
        )
        return ModelResponse(content=content, thinking=thinking)

    def stream_text(
        self,
        prompt,
        history=None,
        tools=None,
        max_tool_iterations=DEFAULT_MAX_ITERATIONS,
        max_tool_calls=DEFAULT_MAX_TOOL_CALLS,
    ):
        messages = self._build_messages(prompt, history)
        active_tools, tool_schemas = self._resolve_tools(tools)
        loop = AgentLoop(max_iterations=max_tool_iterations, max_tool_calls=max_tool_calls)
        failed_tools: list[tuple[str, str]] = []

        while loop.start_iteration():
            round_started = perf_counter()
            log_event(
                "agent.model_round.started",
                round=loop.iterations,
                provider=self.default_provider,
                model=self.ollama_model if self.default_provider == LOCAL_PROVIDER else self.openai_model,
                message_count=len(messages),
            )
            yield StreamChunk(
                "status",
                "Thinking"
                if loop.iterations == 1
                else f"Agent loop · reasoning round {loop.iterations}/{loop.max_iterations}",
            )
            provider_chunks = []
            try:
                stream = self._stream_provider(messages, tool_schemas)
                while True:
                    try:
                        provider_chunks.append(next(stream))
                    except StopIteration as completed:
                        content, _thinking, tool_calls = completed.value
                        break
            except Exception as error:  # noqa: BLE001 - provider errors are shown in the CLI
                log_exception("agent.model_round.failed", error, round=loop.iterations)
                yield StreamChunk("error", self._provider_error_message(error))
                return

            log_event(
                "agent.model_round.completed",
                round=loop.iterations,
                duration_ms=round((perf_counter() - round_started) * 1000),
                requested_tools=[call["name"] for call in tool_calls],
                response_chars=len(content),
                response=content,
            )

            if not tool_calls:
                if failed_tools:
                    log_event(
                        "agent.request.completed",
                        rounds=loop.iterations,
                        tool_calls=loop.tool_calls,
                        failed=True,
                    )
                    yield StreamChunk("error", self._tool_failure_notice(failed_tools))
                    return
                log_event("agent.request.completed", rounds=loop.iterations, tool_calls=loop.tool_calls)
                yield from provider_chunks
                return

            # Do not show speculative narration from a provider response that is
            # still asking to execute tools. The completed, post-tool response is
            # streamed on a later iteration instead.
            for chunk in provider_chunks:
                if chunk.type == "usage":
                    yield chunk

            messages.append(assistant_message(content, tool_calls, self.default_provider))
            for call in tool_calls:
                if not loop.reserve_tool_call():
                    log_event("agent.tool_budget.exhausted", tool=call["name"], level=40)
                    yield StreamChunk("error", loop.tool_limit_message())
                    return
                yield StreamChunk("tool_call", "", tool=call["name"])
                tool_started = perf_counter()
                log_event("agent.tool.started", tool=call["name"], arguments=call.get("arguments", {}))
                output = self._run_tool(active_tools, call)
                log_event(
                    "agent.tool.completed",
                    tool=call["name"],
                    duration_ms=round((perf_counter() - tool_started) * 1000),
                    failed=self._is_tool_failure(call["name"], output),
                    result=output,
                )
                if self._is_tool_failure(call["name"], output):
                    failed_tools.append((call["name"], output))
                yield StreamChunk("tool_result", output, tool=call["name"])
                messages.append(tool_result_message(call, output, self.default_provider))
                if call["name"] == "finish_task":
                    log_event(
                        "agent.request.completed",
                        rounds=loop.iterations,
                        tool_calls=loop.tool_calls,
                        finish_tool=True,
                        failed=bool(failed_tools),
                    )
                    if failed_tools:
                        yield StreamChunk("error", self._tool_failure_notice(failed_tools))
                    else:
                        yield StreamChunk("content", output)
                    return

        log_event("agent.iteration_budget.exhausted", rounds=loop.iterations, level=40)
        log_event("agent.finalization.started", rounds=loop.iterations)
        yield StreamChunk("status", "Finalizing the result")
        try:
            final_stream = self._stream_provider(messages, None)
            final_usage = None
            while True:
                try:
                    chunk = next(final_stream)
                    if chunk.type == "usage":
                        final_usage = chunk.usage
                except StopIteration as completed:
                    content, final_thinking, tool_calls = completed.value
                    break
        except Exception as error:  # noqa: BLE001 - report finalization errors to Discord
            log_exception("agent.finalization.failed", error, rounds=loop.iterations)
            yield StreamChunk("error", self._provider_error_message(error))
            if failed_tools:
                yield StreamChunk("error", self._tool_failure_notice(failed_tools))
            return
        if not content.strip():
            content = loop.iteration_limit_message()
        if tool_calls:
            log_event(
                "agent.finalization.requested_tools_without_budget",
                requested_tools=[call["name"] for call in tool_calls],
                level=40,
            )
            failed_tools.extend(
                (call["name"], "Action not run because the reasoning-round budget was exhausted.")
                for call in tool_calls
            )
        log_event(
            "agent.finalization.completed",
            rounds=loop.iterations,
            response_chars=len(content),
            requested_tools=[call["name"] for call in tool_calls],
        )
        if final_usage:
            yield StreamChunk("usage", "", usage=final_usage)
        if final_thinking:
            yield StreamChunk("thinking", final_thinking)
        if failed_tools:
            yield StreamChunk("error", self._tool_failure_notice(failed_tools))
        else:
            yield StreamChunk("content", content)

    @staticmethod
    def _is_tool_failure(name, output):
        return output.startswith(
            (f"Tool '{name}' failed:", "Discord action failed:")
        )

    @staticmethod
    def _tool_failure_notice(failed_tools):
        details = "\n".join(
            f"- `{name}` : {result[:500]}" for name, result in failed_tools
        )
        return (
            "⚠️ **Résultat incomplet — une ou plusieurs actions ont échoué.** "
            "La tâche ne doit pas être considérée comme entièrement réussie.\n"
            f"{details}"
        )

    @classmethod
    def _append_tool_failure_notice(cls, content, failed_tools):
        if not failed_tools:
            return content
        # A model may claim success despite seeing an error in its tool context.
        # Do not display that unverified claim as the final answer.
        return cls._tool_failure_notice(failed_tools)

    @staticmethod
    def _run_tool(active_tools, call):
        """Execute a tool call, turning recoverable failures into feedback text."""
        try:
            return execute_tool(active_tools, call["name"], call["arguments"])
        except QuitRequested:
            raise
        except Exception as error:  # noqa: BLE001 - tool failures are fed back to the model
            log_exception("agent.tool.exception", error, tool=call["name"])
            return f"Tool '{call['name']}' failed: {error}"

    @staticmethod
    def _provider_error_message(error):
        if getattr(error, "status_code", None) == 429:
            return "Le fournisseur IA est temporairement saturé (429). Réessayez dans quelques secondes."
        return f"Erreur du fournisseur IA : {error}"

    def _resolve_tools(self, tools=None):
        active_tools = self.tools if tools is None else list(tools)
        tool_schemas = to_schemas(active_tools) if active_tools else None
        return active_tools, tool_schemas

    def _call_provider(self, messages, tool_schemas):
        if self.default_provider == LOCAL_PROVIDER:
            return providers.call_ollama(self.ollama_model, messages, tool_schemas)
        if self.default_provider == EXTERNAL_PROVIDER:
            return providers.call_openai(self.openai_client, self.openai_model, messages, tool_schemas)
        raise ValueError(f"Unknown default provider: {self.default_provider}")

    def _stream_provider(self, messages, tool_schemas):
        if self.default_provider == LOCAL_PROVIDER:
            return providers.stream_ollama(self.ollama_model, messages, tool_schemas)
        if self.default_provider == EXTERNAL_PROVIDER:
            return providers.stream_openai(self.openai_client, self.openai_model, messages, tool_schemas)
        raise ValueError(f"Unknown default provider: {self.default_provider}")
