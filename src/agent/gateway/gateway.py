"""Gateway: orchestrates provider calls and the agent tool-use loop.

This module owns the wiring only. Provider communication lives in
:mod:`agent.gateway.providers`, and message normalization in
:mod:`agent.gateway.messages`.
"""

import os

from openai import OpenAI

from ..tools import QuitRequested, execute_tool, to_schemas
from . import providers
from .config import load_config
from .messages import assistant_message, build_messages, tool_result_message
from .models import ModelResponse, StreamChunk

LOCAL_PROVIDER = "local_ollama"
EXTERNAL_PROVIDER = "external_api_openai_compatible"


class Gateway:
    def __init__(self, tools=None):
        config = load_config()
        self.default_provider = config["default_provider"]
        self.ollama_model = config["provider"][LOCAL_PROVIDER]["model"]
        self.openai_model = config["provider"][EXTERNAL_PROVIDER].get("model")
        self.base_url = config["provider"][EXTERNAL_PROVIDER].get("base_url")
        self.tools = list(tools or [])
        if self.openai_model and self.default_provider == EXTERNAL_PROVIDER:
            api_key = os.getenv("EXTERNAL_API_KEY") or os.getenv("OPENAI_API_KEY")
            self.openai_client = OpenAI(base_url=self.base_url, api_key=api_key)

    def generate_text(self, prompt, history=None, tools=None, max_tool_iterations=10):
        messages = build_messages(prompt, history)
        active_tools, tool_schemas = self._resolve_tools(tools)

        for _ in range(max_tool_iterations):
            content, thinking, tool_calls = self._call_provider(messages, tool_schemas)

            if not tool_calls:
                return ModelResponse(content=content, thinking=thinking)

            messages.append(assistant_message(content, tool_calls, self.default_provider))
            for call in tool_calls:
                output = self._run_tool(active_tools, call)
                messages.append(tool_result_message(call, output, self.default_provider))

        return ModelResponse(content="Maximum tool iterations reached.", thinking="")

    def stream_text(self, prompt, history=None, tools=None, max_tool_iterations=10):
        messages = build_messages(prompt, history)
        active_tools, tool_schemas = self._resolve_tools(tools)

        for _ in range(max_tool_iterations):
            yield StreamChunk("status", "Thinking")
            try:
                content, _thinking, tool_calls = yield from self._stream_provider(messages, tool_schemas)
            except Exception as error:  # noqa: BLE001 - provider errors are shown in the CLI
                yield StreamChunk("error", self._provider_error_message(error))
                return

            if not tool_calls:
                return

            messages.append(assistant_message(content, tool_calls, self.default_provider))
            for call in tool_calls:
                yield StreamChunk("tool_call", "", tool=call["name"])
                output = self._run_tool(active_tools, call)
                yield StreamChunk("tool_result", output, tool=call["name"])
                messages.append(tool_result_message(call, output, self.default_provider))

        yield StreamChunk("error", "Maximum tool iterations reached.")

    @staticmethod
    def _run_tool(active_tools, call):
        """Execute a tool call, turning recoverable failures into feedback text."""
        try:
            return execute_tool(active_tools, call["name"], call["arguments"])
        except QuitRequested:
            raise
        except Exception as error:  # noqa: BLE001 - tool failures are fed back to the model
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
