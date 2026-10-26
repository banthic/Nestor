"""Discord tool: send_dm."""

from .discord_runtime import execute_discord_tool


def _send_dm(**arguments):
    return execute_discord_tool("send_dm", **arguments)


send_dm = {
    "type": "function",
    "function": {
        "name": "send_dm",
        "description": 'Send a direct message to a server member.',
        "parameters": {'type': 'object', 'properties': {'member': {'type': 'string'}, 'content': {'type': 'string'}}, 'required': ['member', 'content']},
    },
    
    "call": _send_dm,
}
