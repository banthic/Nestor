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
- it runs the **tool loop**;
- it decides what to do according to the chosen provider;
- it turns technical errors into readable messages.

It exposes two public methods:

| Method | Mode | Returns |
|---|---|---|
| `generate_text` | response all at once | a `ModelResponse` |
| `stream_text` | response in pieces | a stream of `StreamChunk` |

**Keep in mind:** the CLI only uses `stream_text`.

## The tool loop, in detail

This is the heart of the Gateway. Here is the logic in plain language:

```
Repeat at most 10 times:
    ask the AI for a response
    if the AI requests NO tool:
        → this is the final answer, we stop
    otherwise:
        record what the AI requested
        for each requested tool:
            execute the tool
            add the result to the conversation
        (and we start the loop again)
```

- **Why a limit of 10?** To prevent a model from making a mistake and looping forever. After 10 turns, we stop for safety.
- **Why feed the result back in?** Because the AI needs to "see" what the tool found in order to write its final answer.
- **What if a tool fails?** The error is turned into text and sent back to the AI, which can react. The program does not crash.

## The thought signature (thought_signature)

Some models (Gemini 3) attach a **signature** to each tool call: a kind of stamp that proves the continuity of its reasoning. It must be **sent back as-is** on the next turn, otherwise it refuses to answer (error 400).

**Why do we care?** Because it is a Google peculiarity. We carry it faithfully through `providers.py` and `messages.py` so everything works, without bothering the other providers (which simply ignore it).

---

> [← Previous: The CLI](02-cli.md) · [Index](README.md) · [Next: Tools →](04-tools.md)
