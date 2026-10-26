"""Discord tool: create_announcement_draft."""

from .discord_runtime import execute_discord_tool


def _create_announcement_draft(**arguments):
    return execute_discord_tool("create_announcement_draft", **arguments)


create_announcement_draft = {
    "type": "function",
    "function": {
        "name": "create_announcement_draft",
        "description": 'Format an announcement draft without publishing it.',
        "parameters": {'type': 'object', 'properties': {'title': {'type': 'string'}, 'content': {'type': 'string'}}, 'required': ['title', 'content']},
    },
    
    "call": _create_announcement_draft,
}
