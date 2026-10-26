"""Signal that the current agent run is complete and return its final result."""


def _finish_task(**arguments):
    return str(arguments["result"])


finish_task = {
    "type": "function",
    "function": {
        "name": "finish_task",
        "description": (
            "Finish the current agent run after all requested steps have been completed "
            "and verified. Provide a concise final result. Calling this ends the loop."
        ),
        "parameters": {'type': 'object', 'properties': {'result': {'type': 'string'}}, 'required': ['result']},
    },
    
    "call": _finish_task,
}
