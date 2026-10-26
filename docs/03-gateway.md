> [← Previous: The CLI](02-cli.md) · [Index](README.md) · [Next: Tools →](04-tools.md)

# 3. The Gateway — the brain

Folder: `src/agent/gateway/`

This is the most important part. It is **the only layer that talks to the AI providers**. It does no display (that's the CLI) and does not know the content of the tools (that's `tools/`).

It is itself split into small files to stay clear.

## The files, one by one

### `config.py` — reading the settings

Reads the `config/config.json` file (which model, which provider) and loads the secret `.env` file (which contains your API key).

**Why separate?** So that "where are the settings" has a single answer. Configuration is not mixed with logic.

### `prompts.py` — the AI's instruction manual

Contains the **system prompt**: the text of instructions given to the AI at the start of each conversation, for example *"You are Nestor, before talking about a project you must first look at the files, never make things up…"*.

**Why keep it apart?** Because it is content (text), not logic. You can improve it without risking breaking the code.

### `models.py` — the data structures

Two small objects:

- `ModelResponse`: the full final response (`content` + `thinking`);
- `StreamChunk`: **one piece** of a response when it arrives as a stream.

**Why objects instead of raw text?** For readability: `chunk.type == "tool_call"` is clearer than manipulating strings.

### `providers.py` — the adapters to each AI

A "provider" = a service that hosts the model (Ollama locally, or an online API such as Gemini/OpenRouter).

**Why this file?** Each provider speaks a slightly different dialect. Everything is translated here, so the rest of the code only has to know **one single format**. Adding a new provider = adding functions here.

Four main functions:

| Function | What it does |
|---|---|
| `call_ollama` | asks Ollama for a response all at once |
| `stream_ollama` | asks Ollama for a response in pieces |
| `call_openai` | asks an OpenAI-compatible API for a response, all at once |
| `stream_openai` | same, in pieces |

Two small utilities also live there: `extract_usage` (get the number of tokens) and `extract_extra_content` (get the thought signature, see below).

### `messages.py` — building the messages

- `build_messages`: assembles `[system instructions] + [history] + [your question]`.
- `assistant_message` / `tool_result_message`: format the tool exchanges **according to the provider**.

**Why here and not in `gateway.py`?** Because "how a message is written" is a translation detail, not logic.

### `gateway.py` — the conductor

This is the shortest file, almost only coordination:

- it creates the provider's client;
- it runs the **agent loop**;
- it decides what to do according to the chosen provider;
- it turns technical errors into readable messages.

It exposes two public methods:

| Method | Mode | Returns |
|---|---|---|
| `generate_text` | response all at once | a `ModelResponse` |
| `stream_text` | response in pieces | a stream of `StreamChunk` |

### `loop.py` — per-request limits

Tracks model rounds and tool calls, and creates clear stop messages when either budget is exhausted.

**Keep in mind:** the CLI and Discord both use `stream_text`.

## The tool loop, in detail

This is the heart of the Gateway. Here is the logic in plain language:

```
Repeat at most 12 action rounds and 40 tool calls for one user request:
    ask the AI for a response
    if the AI requests NO tool:
        → this is the final answer, we stop
    otherwise:
        record what the AI requested
        for each requested tool:
            stop if finish_task was called
            execute the tool
            add the result to the conversation
        (and we start the loop again)
After the action-round budget, make one final model call with tools disabled
so it can summarize the results without starting more actions.
```

- **Why two limits?** The round limit stops an endless model/tool cycle; the action limit also caps batches where a model requests many tools at once. Reaching the action-round limit reserves one final model call with tools disabled, so Nestor can still summarize what happened.
- **Why feed the result back in?** Because the AI needs to "see" what the tool found in order to write its final answer.
- **What does `finish_task` do?** It is a terminal tool: its result becomes the final answer and no more provider call is made.
- **What if an action failed?** The tool error is fed back to the model. The Gateway also replaces any claimed success with a deterministic incomplete-result notice, so a final answer cannot report the run as successful after a detected tool failure.
- **What if a tool fails?** The error is turned into text and sent back to the AI, which can react. The program does not crash.

See [the agent loop guide](08-agent-loop.md) for the step-by-step behavior, budgets, finish rules, and current limitations.

## The thought signature (thought_signature)

Some models (Gemini 3) attach a **signature** to each tool call: a kind of stamp that proves the continuity of its reasoning. It must be **sent back as-is** on the next turn, otherwise it refuses to answer (error 400).

**Why do we care?** Because it is a Google peculiarity. We carry it faithfully through `providers.py` and `messages.py` so everything works, without bothering the other providers (which simply ignore it).

---

> [← Previous: The CLI](02-cli.md) · [Index](README.md) · [Next: Tools →](04-tools.md)
