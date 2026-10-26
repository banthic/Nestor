# Internal runtime logs

Nestor writes structured JSON Lines events to `logs/nestor.jsonl`. The log rotates at 10 MB and keeps five archived files. The `logs/` files are local runtime data and are ignored by Git.

## What is recorded

Each event has a UTC timestamp, severity, event name, and—during an agent request—a `request_id` that links the Discord message, model rounds, tool calls/results, and final reply. Events include provider/model names, timings, message and channel IDs, tool names, outcome/error status, and response sizes. Modal submissions, slash-command failures, bot startup, and reply delivery are also recorded.

By default, message bodies, prompts, model responses, tool results, and free-text tool arguments are redacted while their lengths remain visible. Set `NESTOR_LOG_CONTENT=1` in the environment to include those text values when investigating a behavior. API keys, tokens, passwords, and authorization fields remain redacted either way. Treat opt-in content logs as sensitive and remove them when the investigation is complete.

## Inspecting a request

Copy the `request_id` from `discord.agent.request_received` and search for it:

```sh
rg '"request_id":"THE_REQUEST_ID"' logs/nestor.jsonl
```

The event sequence shows each model round, requested tool, actual tool result or error, and final response. Provider and Discord HTTP exceptions include stack traces. If an interaction has already expired, Nestor records the failed acknowledgement or follow-up rather than silently swallowing it.
