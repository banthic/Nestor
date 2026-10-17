# Nestor Documentation

Welcome. This documentation explains **how Nestor works** and **why** each part is built the way it is. The goal is to be understandable even if you are not an expert: technical words are explained as they come up.

## Where to start

If you are discovering the project, read the files **in order**. If you want the big picture first, start with the [Architecture](architecture.md) map. If you are looking for specific information, jump straight to the right file.

| # | File | Content |
|---|---|---|
| — | [Architecture](architecture.md) | Mermaid map of the layers and how they connect |
| 1 | [Overview](01-overview.md) | What Nestor is, the idea of layers, the path of a question |
| 2 | [The CLI](02-cli.md) | The layer that talks with you (display, input, history) |
| 3 | [The Gateway](03-gateway.md) | The brain: talking with the AI + the tool loop |
| 4 | [Tools](04-tools.md) | The concrete actions (list, read, locate, quit) |
| 5 | [Configuration & tests](05-configuration-and-tests.md) | Settings, the secret file, and the checks |
| 6 | [Key concepts](06-concepts.md) | Provider, streaming, tool call, thinking, history |
| 7 | [Extending the project](07-extending.md) | How to add/modify, and recap |

## 30-second summary

Nestor is an **assistant that runs in the terminal**. You write it a question; it can **go look at your files** to inform itself, then answer you.

The code is split into **layers**, each with a single role:

```
CLI (talks)  →  GATEWAY (thinks and acts)  →  TOOLS (do)  +  AI (reasons)
```

**Why?** So you can modify one part without breaking the others.

## See also

- The [main README](../README.md): installation, getting started, examples.
- The [CONTRIBUTING.md](../CONTRIBUTING.md) file: contribution rules and tests.
