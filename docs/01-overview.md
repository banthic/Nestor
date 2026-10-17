> [← Index](README.md) · [Next: The CLI →](02-cli.md)

# 1. Overview

## What Nestor is, in one sentence

Nestor is an **assistant that runs in the terminal**. You write it a question, it thinks, it can **go look at files on your computer** to inform itself, then it answers you.

It is built on a base called **Zetelton**. Nestor is the "assistant for communities" version (helping Discord moderators and helpers).

## The main idea: separating responsibilities

Imagine a small company. You don't ask the same person to answer the phone, think about the problem, and go fetch the documents. Each person has a precise role.

Nestor works the same way. The code is split into **layers**, and each layer has a single role:

| Layer | Its role | Analogy |
|---|---|---|
| `cli/` | Talk with you (display, type) | The front desk / reception |
| `gateway/` | Talk with the AI and execute actions | The brain / the team lead |
| `tools/` | The concrete actions (list, read…) | The hands |
| `config/` | The settings (which model to use) | The configuration panel |

**Why do this?** Because if you want to change the terminal's appearance, you only touch `cli/`. If you want to change the AI provider, you only touch `gateway/`. The other pieces don't move. It's easier to modify and to debug.

The golden rule: **information flows in a single direction**.

```
        You type a question
                │
                ▼
        ┌───────────────┐
        │      CLI      │   displays, listens to your keyboard
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │    GATEWAY    │   talks to the AI, decides to use a tool
        └───────┬───────┘
                │
      ┌─────────┴─────────┐
      ▼                   ▼
  ┌────────┐        ┌───────────┐
  │   AI   │        │   TOOLS   │   list, read a file…
  └────────┘        └───────────┘
```

## The path of a question, end to end

Here is what happens when you type *"list the files in the src folder"*:

1. **The CLI** captures your sentence (`cli.py`).
2. It sends it to the **Gateway** along with the conversation history.
3. The Gateway adds the **system prompt** (the behavior instructions) then sends everything to the **AI**.
4. The AI replies: *"call `listfiles` on `src`"* instead of answering directly.
5. The Gateway **executes the tool** `listfiles`, which really reads the disk.
6. The Gateway **sends the result back** to the AI.
7. The AI, now informed, writes a **real answer**.
8. The Gateway passes this answer to the CLI, which **displays it nicely** (Markdown, colors).
9. The sentence is added to the **history** so the next turn remembers it.

Remember points 4-6: **the AI does nothing itself**. It *requests* an action, and it is our code that executes it. That is safer and more controllable.

---

> [← Index](README.md) · [Next: The CLI →](02-cli.md)
