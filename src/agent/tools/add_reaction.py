"""Discord tool: add_reaction."""

from .discord_runtime import execute_discord_tool


def _add_reaction(**arguments):
    return execute_discord_tool("add_reaction", **arguments)


add_reaction = {
    "type": "function",
    "function": {
        "name": "add_reaction",
        "description": 'Add an emoji reaction to the triggering message.',
        "parameters": {'type': 'object', 'properties': {'emoji': {'type': 'string'}}, 'required': ['emoji']},
    },
    
    "call": _add_reaction,
}
