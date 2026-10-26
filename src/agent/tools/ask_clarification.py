"""Discord tool: ask_clarification."""

from .discord_runtime import execute_discord_tool


def _ask_clarification(**arguments):
    return execute_discord_tool("ask_clarification", **arguments)


ask_clarification = {
    "type": "function",
    "function": {
        "name": "ask_clarification",
        "description": 'Ask the user a question when required information is missing.',
        "parameters": {'type': 'object', 'properties': {'question': {'type': 'string'}}, 'required': ['question']},
    },
    
    "call": _ask_clarification,
}
