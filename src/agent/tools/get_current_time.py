"""Discord tool: get_current_time."""

from datetime import UTC, datetime


def _get_current_time(**arguments):
    return datetime.now(UTC).isoformat()


get_current_time = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": 'Get the current UTC time.',
        "parameters": {'type': 'object', 'properties': {}},
    },
    
    "call": _get_current_time,
}
