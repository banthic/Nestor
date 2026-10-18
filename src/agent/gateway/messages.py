"""Message construction and provider-specific tool-call normalization."""

import json

from .prompts import SYSTEM_PROMPT


def build_messages(prompt, history=None, system_prompt=SYSTEM_PROMPT):
    """Assemble the request: system prompt, prior turns, then the new prompt."""
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(list(history or []))
    messages.append({"role": "user", "content": prompt})
    return messages


def assistant_message(content, tool_calls, provider):
    """Build the assistant turn that carries the model's tool calls."""
    message = {"role": "assistant", "content": content or None}
    if not tool_calls:
        return message

    if provider == "local_ollama":
        message["tool_calls"] = [
            {
                "function": {
                    "name": call["name"],
                    "arguments": call["arguments"],
                }
            }
            for call in tool_calls
        ]
        return message

    external_calls = []
    for call in tool_calls:
        tool_call = {
            "id": call["id"],
            "type": "function",
            "function": {
                "name": call["name"],
                "arguments": json.dumps(call["arguments"]),
            },
        }
        if call.get("extra_content"):
            tool_call["extra_content"] = call["extra_content"]
        external_calls.append(tool_call)
    message["tool_calls"] = external_calls
    return message


def tool_result_message(call, output, provider):
    """Build the tool turn that feeds an executed tool's output back to the model."""
    if provider == "local_ollama":
        return {"role": "tool", "name": call["name"], "content": output}
    return {"role": "tool", "tool_call_id": call["id"], "content": output}
