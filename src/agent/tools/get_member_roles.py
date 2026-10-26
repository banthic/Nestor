"""Discord tool: get_member_roles."""

from .discord_runtime import execute_discord_tool


def _get_member_roles(**arguments):
    return execute_discord_tool("get_member_roles", **arguments)


get_member_roles = {
    "type": "function",
    "function": {
        "name": "get_member_roles",
        "description": "List a server member's roles.",
        "parameters": {'type': 'object', 'properties': {'member': {'type': 'string'}}, 'required': ['member']},
    },
    
    "call": _get_member_roles,
}
