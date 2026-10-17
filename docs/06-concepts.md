> [← Previous: Configuration & tests](05-configuration-and-tests.md) · [Index](README.md) · [Next: Extending →](07-extending.md)

# 6. Key concepts

This page gathers, explained simply, the words you come across in the code.

## Provider

The service that runs the AI model. Two options in Nestor:

| Provider | Where it runs | Advantages |
|---|---|---|
| **Ollama** | on your machine | free, private, but slower |
| **Online API** (Gemini, OpenRouter…) | remote server | fast, but requires a key |

**Why support both?** To leave the choice: privacy and free use locally, or power and speed online.

## Streaming

Instead of waiting for the AI to write everything, we receive and display **word by word**. That is why the answer "pushes" progressively onto the screen.

**Why?** The wait feels much shorter, and you can see the program is working.

## Tool call

Rather than guessing, the AI can **request**: *"run `readfiles` on `main.py`"*. Our code executes, then sends back the result.

**Why?** This is what keeps the AI from making things up. It relies on the real. See the [tool loop](03-gateway.md#the-tool-loop-in-detail).

## Thinking

Recent models think before answering. We can display this reasoning (`/thinking full`), shorten it (`short`) or hide it (`off`).

**Why display it?** To understand the reasoning and spot possible mistakes.

## History

The list of previous exchanges, sent back to the AI on each new question so it keeps the context.

**Why?** Without it, each question would be asked to an amnesiac model.

## Token

A unit for measuring text (about one short word). Providers often charge and limit by tokens.

**Why count them?** To display consumption and estimate the cost on the online API side.

## System prompt

The text of instructions given to the AI at the start of each conversation: who it is, how to behave, what it must not do.

**Why?** This is where Nestor's personality and rules are defined. It lives in `gateway/prompts.py`.

## Thought signature (thought_signature)

For some models (Gemini 3), a stamp attached to each tool call, to be sent back as-is on the next turn.

**Why?** Without it, Gemini refuses to answer. See the [dedicated note](03-gateway.md#the-thought-signature-thought_signature).

---

> [← Previous: Configuration & tests](05-configuration-and-tests.md) · [Index](README.md) · [Next: Extending →](07-extending.md)
