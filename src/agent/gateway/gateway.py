import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ollama
from dotenv import load_dotenv
from openai import OpenAI

from ..tools import QuitRequested, execute_tool, to_schemas

config_path = Path(__file__).resolve().parent.parent / "config" / "config.json"
dotenv_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=dotenv_path)

SYSTEM_PROMPT = (
    "You are Zetelton, a concise and evidence-driven coding agent. You have access to these tools: "
    "listfiles lists the entries in a directory, readfile reads and returns the content "
    "of a file, where returns the current working directory, and quit ends the session. "
    "Use readfile when the user asks to read, display, show, or inspect a file. Use "
    "listfiles when the user asks to list a directory. When the user asks about the "
    "current project, its architecture, functions, or how its code works, you MUST "
    "inspect the project first: use listfiles, then readfile on the relevant files, "
    "before explaining anything. Never claim that there is no project when the tools "
    "can inspect the current directory. If the tools do not provide enough evidence, "
    "say what is missing instead of guessing. Greetings and general questions may be "
    "answered directly without tools."
    "if the user asks to quit the agent, use the quit tool to quit the agent. or if he say a word like goodbye"
    "if your have an error during a tools use or you can't use a tool or you don't have the right permissions to access to a file , you must answer the user directly and tell them about the error and not call any tool. "
    "if the user asks to know where the agent is running, you can use the 'where' tool to get the current working directory and return it to the user. "
    "Never invent source code, file contents, function names, tool results, or project "
    "structure. Use only evidence returned by tools. You may show illustrative code "
    "only when explicitly labeled as an example and not as code from the project."
)

TOOL_TRIGGER_KEYWORDS = (
    "list", "ls ", "dir", "directory", "folder", "show", "files", "file",
    "fichier", "dossier", "r\u00e9pertoire", "repertoire", "contenu", "arborescence",
    "read", "cat", "type", "open", "view", "inspect", "explore", "search",
    "find", "look", "display", "check", "analyze", "examine", "scan", "traverse",
    "where", "current working directory", "pwd", "present working directory", "quitter", "exit", "close", "stop", "end", "terminate"
)
FILE_REFERENCE_PATTERN = re.compile(r"(?:^|[\s/'\"])[^\s/'\"]+\.[a-zA-Z0-9]+(?:$|[\s'\"])")


def load_config():
    with open(config_path) as f:
        return json.load(f)


@dataclass
class ModelResponse:
    content: str
    thinking: str = ""


@dataclass
class StreamChunk:
    type: str
    text: str
    usage: dict[str, int] | None = None
    tool: str | None = None


class Gateway:
    def __init__(self, tools=None):
        config = load_config()
        self.default_provider = config["default_provider"]
        self.ollama_model = config["provider"]["local_ollama"]["model"]
        self.openai_model = config["provider"]["external_api_openai_compatible"].get("model")
        self.base_url = config["provider"]["external_api_openai_compatible"].get("base_url")
        self.tools = list[Any](tools or [])
        if self.openai_model and self.default_provider == "external_api_openai_compatible":
            api_key = os.getenv("EXTERNAL_API_KEY") or os.getenv("OPENAI_API_KEY")
            self.openai_client = OpenAI(base_url=self.base_url, api_key=api_key)

    def generate_text(self, prompt, history=None, tools=None, max_tool_iterations=10):
        messages = self._build_messages(prompt, history)
        active_tools, tool_schemas = self._resolve_tools(prompt, tools)

        for _ in range(max_tool_iterations):
            content, thinking, tool_calls = self._call_provider(messages, tool_schemas)

            if not tool_calls:
                return ModelResponse(content=content, thinking=thinking)

            messages.append(self._assistant_message(content, tool_calls))
            for call in tool_calls:
                try:
                    output = execute_tool(active_tools, call["name"], call["arguments"])
                except QuitRequested:
                    raise
                except Exception as e:  # noqa: BLE001 - tool failures are fed back to the model
                    output = f"Tool '{call['name']}' failed: {e}"
                messages.append(self._tool_result_message(call, output))

        return ModelResponse(content="Maximum tool iterations reached.", thinking="")

    def stream_text(self, prompt, history=None, tools=None, max_tool_iterations=10):
        messages = self._build_messages(prompt, history)
        active_tools, tool_schemas = self._resolve_tools(prompt, tools)

        for _ in range(max_tool_iterations):
            yield StreamChunk("status", "Thinking")
            try:
                if self.default_provider == "local_ollama":
                    content, _thinking, tool_calls = yield from self._stream_ollama(messages, tool_schemas)
                elif self.default_provider == "external_api_openai_compatible":
                    content, _thinking, tool_calls = yield from self._stream_openai(messages, tool_schemas)
                else:
                    raise ValueError(f"Unknown default provider: {self.default_provider}")
            except Exception as error:  # noqa: BLE001 - provider errors are shown in the CLI
                yield StreamChunk("error", self._provider_error_message(error))
                return

            if not tool_calls:
                return

            messages.append(self._assistant_message(content, tool_calls))
            for call in tool_calls:
                yield StreamChunk("tool_call", "", tool=call["name"])
                try:
                    output = execute_tool(active_tools, call["name"], call["arguments"])
                except QuitRequested:
                    raise
                except Exception as e:  # noqa: BLE001 - tool failures are fed back to the model
                    output = f"Tool '{call['name']}' failed: {e}"
                yield StreamChunk("tool_result", output, tool=call["name"])
                messages.append(self._tool_result_message(call, output))

        yield StreamChunk("error", "Maximum tool iterations reached.")

    @staticmethod
    def _provider_error_message(error):
        if getattr(error, "status_code", None) == 429:
            return "Le fournisseur IA est temporairement saturé (429). Réessayez dans quelques secondes."
        return f"Erreur du fournisseur IA : {error}"

    def _build_messages(self, prompt, history=None):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(list(history or []))
        messages.append({"role": "user", "content": prompt})
        return messages

    def _resolve_tools(self, prompt, tools=None):
        active_tools = self.tools if tools is None else list(tools)
        tool_schemas = to_schemas(active_tools) if active_tools else None
        return active_tools, tool_schemas

    def _prompt_requests_tools(self, prompt, tools=None):
        normalized = prompt.lower()
        if any(keyword in normalized for keyword in TOOL_TRIGGER_KEYWORDS):
            return True
        if FILE_REFERENCE_PATTERN.search(prompt):
            return True
        if tools:
            return any(tool["function"]["name"].lower() in normalized for tool in tools)
        return False

    def _call_provider(self, messages, tool_schemas):
        if self.default_provider == "local_ollama":
            return self._call_ollama(messages, tool_schemas)
        elif self.default_provider == "external_api_openai_compatible":
            return self._call_openai(messages, tool_schemas)
        else:
            raise ValueError(f"Unknown default provider: {self.default_provider}")

    def _call_ollama(self, messages, tool_schemas):
        kwargs = {"model": self.ollama_model, "messages": messages}
        if tool_schemas:
            kwargs["tools"] = tool_schemas
        response = ollama.chat(**kwargs)
        message = response["message"]
        if hasattr(message, "model_dump"):
            message = message.model_dump()

        content = message.get("content") or ""
        thinking = message.get("thinking") or message.get("reasoning_content") or ""

        tool_calls = []
        for call in message.get("tool_calls") or []:
            if hasattr(call, "model_dump"):
                call = call.model_dump()
            function = call.get("function", {})
            tool_calls.append({
                "id": call.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                "name": function.get("name"),
                "arguments": function.get("arguments") or {},
            })

        return content, thinking, tool_calls

    def _call_openai(self, messages, tool_schemas):
        kwargs = {"model": self.openai_model, "messages": messages}
        if tool_schemas:
            kwargs["tools"] = tool_schemas
        response = self.openai_client.chat.completions.create(**kwargs)
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
            tool_calls.append({
                "id": call.id or f"call_{uuid.uuid4().hex[:8]}",
                "name": call.function.name,
                "arguments": arguments or {},
            })

        return content, thinking, tool_calls

    def _stream_ollama(self, messages, tool_schemas):
        kwargs = {"model": self.ollama_model, "messages": messages, "stream": True}
        if tool_schemas:
            kwargs["tools"] = tool_schemas

        content_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        usage: dict[str, int] | None = None

        for response in ollama.chat(**kwargs):
            response_usage = self._extract_usage(response)
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

            for call in message.get("tool_calls") or []:
                if hasattr(call, "model_dump"):
                    call = call.model_dump()
                function = call.get("function", {})
                tool_calls.append({
                    "id": call.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                    "name": function.get("name"),
                    "arguments": function.get("arguments") or {},
                })

        if usage:
            yield StreamChunk("usage", "", usage=usage)
        return "".join(content_parts), "".join(thinking_parts), tool_calls

    def _stream_openai(self, messages, tool_schemas):
        kwargs = {"model": self.openai_model, "messages": messages, "stream": True}
        if tool_schemas:
            kwargs["tools"] = tool_schemas

        content_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_calls_by_index: dict[int, dict[str, Any]] = {}
        usage: dict[str, int] | None = None

        for chunk in self.openai_client.chat.completions.create(**kwargs):
            chunk_usage = self._extract_usage(chunk)
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
                    {"id": getattr(call, "id", None) or f"call_{uuid.uuid4().hex[:8]}", "name": "", "arguments": ""},
                )
                function = getattr(call, "function", None)
                name = getattr(function, "name", None) if function else None
                arguments = getattr(function, "arguments", None) if function else None
                if name:
                    entry["name"] += name
                if arguments:
                    entry["arguments"] += arguments

        tool_calls: list[dict[str, Any]] = []
        for entry in tool_calls_by_index.values():
            if not entry["name"]:
                continue
            try:
                arguments = json.loads(entry["arguments"]) if entry["arguments"] else {}
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append({"id": entry["id"], "name": entry["name"], "arguments": arguments})

        if usage:
            yield StreamChunk("usage", "", usage=usage)
        return "".join(content_parts), "".join(thinking_parts), tool_calls

    @staticmethod
    def _extract_usage(response) -> dict[str, int] | None:
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

    def _assistant_message(self, content, tool_calls):
        message = {"role": "assistant", "content": content or None}
        if tool_calls:
            if self.default_provider == "local_ollama":
                message["tool_calls"] = [
                    {
                        "function": {
                            "name": call["name"],
                            "arguments": call["arguments"],
                        }
                    }
                    for call in tool_calls
                ]
            else:
                message["tool_calls"] = [
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": json.dumps(call["arguments"]),
                        },
                    }
                    for call in tool_calls
                ]
        return message

    def _tool_result_message(self, call, output):
        if self.default_provider == "local_ollama":
            return {"role": "tool", "name": call["name"], "content": output}
        return {"role": "tool", "tool_call_id": call["id"], "content": output}
      
