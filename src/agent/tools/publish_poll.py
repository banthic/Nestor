"""Discord tool: publish_poll."""

from .discord_runtime import execute_discord_tool


def _publish_poll(**arguments):
    return execute_discord_tool("publish_poll", **arguments)


publish_poll = {
    "type": "function",
    "function": {
        "name": "publish_poll",
        "description": 'Publish a native Discord poll in the current channel.',
        "parameters": {'type': 'object', 'properties': {'question': {'type': 'string'}, 'options': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 2, 'maxItems': 10}, 'duration_hours': {'type': 'integer', 'enum': [1, 4, 8, 24, 72, 168], 'description': 'Poll duration in hours; defaults to 24.'}, 'multiple': {'type': 'boolean', 'description': 'Allow voters to select multiple answers.'}}, 'required': ['question', 'options']},
    },
    
    "call": _publish_poll,
}
