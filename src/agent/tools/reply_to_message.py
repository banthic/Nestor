"""Discord tool: reply_to_message."""

from .discord_runtime import execute_discord_tool


def _reply_to_message(**arguments):
    return execute_discord_tool("reply_to_message", **arguments)


reply_to_message = {
    "type": "function",
    "function": {
        "name": "reply_to_message",
        "description": 'Reply to the message that triggered this response.',
        "parameters": {'type': 'object', 'properties': {'content': {'type': 'string'}}, 'required': ['content']},
    },
    
    "call": _reply_to_message,
}
