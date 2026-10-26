"""Discord tool: get_message_context."""

from .discord_runtime import execute_discord_tool


def _get_message_context(**arguments):
    return execute_discord_tool("get_message_context", **arguments)


get_message_context = {
    "type": "function",
    "function": {
        "name": "get_message_context",
        "description": 'Read the message that triggered this response.',
        "parameters": {'type': 'object', 'properties': {}},
    },
    
    "call": _get_message_context,
}
