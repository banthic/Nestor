"""Discord tool: get_channel_info."""

from .discord_runtime import execute_discord_tool


def _get_channel_info(**arguments):
    return execute_discord_tool("get_channel_info", **arguments)


get_channel_info = {
    "type": "function",
    "function": {
        "name": "get_channel_info",
        "description": 'Get information about the current Discord channel.',
        "parameters": {'type': 'object', 'properties': {}},
    },
    
    "call": _get_channel_info,
}
