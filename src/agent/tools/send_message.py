"""Discord tool: send_message."""

from .discord_runtime import execute_discord_tool


def _send_message(**arguments):
    return execute_discord_tool("send_message", **arguments)


send_message = {
    "type": "function",
    "function": {
        "name": "send_message",
        "description": 'Send a message to the current channel.',
        "parameters": {'type': 'object', 'properties': {'content': {'type': 'string'}}, 'required': ['content']},
    },
    
    "call": _send_message,
}
