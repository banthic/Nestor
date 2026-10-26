> [← Previous: The Gateway](03-gateway.md) · [Index](README.md) · [Next: Configuration & tests →](05-configuration-and-tests.md)

# 4. Tools

Folder: `src/agent/tools/`

## What the tools are for

Without them, the AI would **make up** the content of your files. With them, it can **request** a real action: *"run `readfiles` on `main.py`"*. Our code executes, then sends back the result. This is what happens at steps 4 to 6 of [the path of a question](01-overview.md#the-path-of-a-question-end-to-end).

## The structure of a tool

Each tool lives in its own file and contains **two things**:

1. a **description** (name, explanation, parameters) that we show to the AI;
2. a **Python function** that does the real work.

Simplified example (`listfiles.py`):

```python
def _listfiles(path: str) -> str:
    ...  # the real code that lists the folder

listfiles = {
    "type": "function",
    "function": {
        "name": "listfiles",
        "description": "List files and directories in a given path.",
        "parameters": { ... },
    },
    "call": _listfiles,   # the "call" key wires up the Python code
}
```

## The available tools

| File | Tool | What it does | Why |
|---|---|---|---|
| `listfiles.py` | `listfiles` | lists the files in a folder | to "see" the tree |
| `readfiles.py` | `readfile` | reads the content of a file | to "read" a document |
| `where.py` | `where` | gives the current folder | to know where we are |
| `quit.py` | `quit` | stops the session | to exit cleanly |

## The registry (`tools/__init__.py`)

All the tools are stored in a **list** called `TOOLS`. This allows two operations:

- **`to_schemas`**: presents the tools to the AI. Note that it **removes the `"call"` key**: the AI does not need to see the Python code, only the description.
- **`execute_tool`**: looks up the tool by its name and calls the right Python function.

**Why dictionaries?** Because the description is a standard format understood by all AIs. We only add a `"call"` key to wire up the code.

**Why a central list?** So that adding a tool is a single line to change, and so the AI discovers them automatically.

## Special case: `quit`

The `quit` tool does not return text: it **raises an exception** (`QuitRequested`). The Gateway lets it bubble up to the CLI, which closes the session cleanly.

**Why an exception rather than a simple message?** Because it is a stop order, not an answer. An exception is the right tool to "interrupt the normal flow".

## Discord behavior review

The conversational agent has no tools for moderation or enforcement: it cannot delete messages, time out members, or apply sanctions. A separate background behavior monitor can classify visible guild messages and send likely concerns to a staff-only channel for human review. It never acts on a member or message automatically.

Use `/config_review` to select the staff review channel. This enables continuous AI review of text messages in channels the bot can see; the selected channel must be private to staff and grant Nestor View Channel, Send Messages, and Embed Links. Alerts contain a short explanation, the message excerpt, and a link to the original. The classifier keeps at most six recent messages per active channel in memory; entries older than ten minutes are excluded from classification, and the buffer is cleared when entries are evicted or the bot shuts down. Use `/disable_review_monitor` to stop the review service for a guild. If no review channel is configured, no messages are sent to the classifier.

The monitor uses the configured AI provider for every non-bot text message it can see while enabled. It is intentionally conservative and only asks for human review; it does not make a finding or take an enforcement action.

## When Nestor replies

Nestor answers every message in the configured chatbot channel. In other guild text channels, it answers when a member directly mentions the bot or writes `Nestor` (or the bot's exact Discord username) as a whole word. Those replies are sent as Discord replies to the addressed message.

---

> [← Previous: The Gateway](03-gateway.md) · [Index](README.md) · [Next: Configuration & tests →](05-configuration-and-tests.md)
