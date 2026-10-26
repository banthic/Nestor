"""Discord tool: edit_own_message."""

from .discord_runtime import execute_discord_tool


def _edit_own_message(**arguments):
    return execute_discord_tool("edit_own_message", **arguments)


edit_own_message = {
    "type": "function",
    "function": {
        "name": "edit_own_message",
        "description": 'Edit a message previously sent by this bot. Requires its message ID.',
        "parameters": {'type': 'object', 'properties': {'message_id': {'type': 'string'}, 'content': {'type': 'string'}}, 'required': ['message_id', 'content']},
    },
    
    "call": _edit_own_message,
}
