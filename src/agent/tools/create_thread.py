"""Discord tool: create_thread."""

from .discord_runtime import execute_discord_tool


def _create_thread(**arguments):
    return execute_discord_tool("create_thread", **arguments)


create_thread = {
    "type": "function",
    "function": {
        "name": "create_thread",
        "description": 'Create a thread from the triggering message.',
        "parameters": {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']},
    },
    
    "call": _create_thread,
}
