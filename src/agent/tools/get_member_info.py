"""Discord tool: get_member_info."""

from .discord_runtime import execute_discord_tool


def _get_member_info(**arguments):
    return execute_discord_tool("get_member_info", **arguments)


get_member_info = {
    "type": "function",
    "function": {
        "name": "get_member_info",
        "description": 'Get public profile information about a server member.',
        "parameters": {'type': 'object', 'properties': {'member': {'type': 'string'}}, 'required': ['member']},
    },
    
    "call": _get_member_info,
}
