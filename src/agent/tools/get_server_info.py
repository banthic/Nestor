"""Discord tool: get_server_info."""

from .discord_runtime import execute_discord_tool


def _get_server_info(**arguments):
    return execute_discord_tool("get_server_info", **arguments)


get_server_info = {
    "type": "function",
    "function": {
        "name": "get_server_info",
        "description": 'Get information about the current Discord server.',
        "parameters": {'type': 'object', 'properties': {}},
    },
    
    "call": _get_server_info,
}
