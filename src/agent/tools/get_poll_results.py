"""Discord tool: get_poll_results."""

from .discord_runtime import execute_discord_tool


def _get_poll_results(**arguments):
    return execute_discord_tool("get_poll_results", **arguments)


get_poll_results = {
    "type": "function",
    "function": {
        "name": "get_poll_results",
        "description": 'Read vote totals for a native Discord poll message in this channel.',
        "parameters": {'type': 'object', 'properties': {'message_id': {'type': 'string'}}, 'required': ['message_id']},
    },
    
    "call": _get_poll_results,
}
