> [← Previous: Key concepts](06-concepts.md) · [Index](README.md)

# 7. Extending the project

## Common tasks

### Adding a tool

1. Create a file in `src/agent/tools/`.
2. Describe it (name, explanation, parameters) and write the function that does the work.
3. Add it to the `TOOLS` list in `tools/__init__.py`.
4. Add a test in `tests/`.

**Why these steps?** Because a tool is always: a description + a function + a wiring + a check.

### Changing the model

Edit `src/agent/config/config.json`. Nothing else to touch.

### Adding an AI provider

Add its functions in `src/agent/gateway/providers.py`, then wire it up in `gateway.py`. **Do not touch the CLI or the tools**: that is the whole point of the split.

### Changing the terminal's appearance

Everything is in `src/agent/cli/`. The other layers don't move.

### Changing the AI's behavior (tone, rules)

Edit `src/agent/gateway/prompts.py` (the system prompt).

## Why these technical choices — recap

| Choice | Why |
|---|---|
| Splitting into layers (`cli`, `gateway`, `tools`) | modify one part without breaking the others |
| Config in a JSON | change model without touching the code |
| Secrets in `.env` | never put keys in Git |
| Two providers supported | privacy/local **or** power/online |
| Streamed responses | shorter wait, immediate visual feedback |
| Rich for display | readable Markdown and colors in the terminal |
| prompt-toolkit for input | free history and `@` auto-completion |
| Tools as dictionaries | standard format understood by all AIs |
| Tests without network | fast, free, reliable |
| A limit of 10 tool turns | avoid an infinite loop |

## In summary

- Nestor = **CLI** (talks) → **Gateway** (thinks and acts) → **Tools** (do) + **AI** (reasons).
- Each layer has **a single role**: that is what makes the project simple to extend.
- We go through **tools** so the AI relies on the real instead of making things up.
- Everything is **configurable** (model, provider, prompt, appearance) without rewriting the code.

---

> [← Previous: Key concepts](06-concepts.md) · [Index](README.md)
