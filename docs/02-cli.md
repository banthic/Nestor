> [← Previous: Overview](01-overview.md) · [Index](README.md) · [Next: The Gateway →](03-gateway.md)

# 2. The CLI — the layer that talks with you

Folder: `src/agent/cli/`

**Why this layer exists:** it is the only place where display and input are handled. It knows nothing about the AI or the files. If one day you want a web interface instead of the terminal, you only replace this layer.

## The files, one by one

### `cli.py` — the main loop

This is the `run_cli()` function launched at startup. It:

- displays the startup banner;
- **waits for your input in a loop**;
- handles special commands, such as `/thinking short|full|off`;
- receives the response pieces from the Gateway **as they arrive** and displays them live;
- files each exchange into the **history**.

**Why a loop?** So you can chain several questions without relaunching the program.

At the end of each turn, it also computes the **tokens** used (a unit for measuring text): the real number if the AI provides it, otherwise an estimate.

### `cli/interface/panel.py` — the chrome

Displays the top banner (name, model, current folder) and the footer (keyboard shortcuts, tokens). It reads the displayed model straight from the config.

**Why separate?** Because it is pure presentation, with no logic.

### `cli/interface/prompt.py` — text input

Handles the line where you type your question. It uses the **prompt-toolkit** library.

**Why prompt-toolkit instead of `input()`?** Because it gives you for free:
- the **history** of commands (up/down arrows);
- **auto-completion**: when you type `@`, it suggests the files and folders of the current directory.

### `cli/interface/messages.py` — the history

Keeps the list of past exchanges, as dictionaries `{"role": "...", "content": "..."}`.

**Why this format?** Because it is exactly what the AIs expect. So there is nothing to convert before sending it back to them.

### `cli/interface/thinking.py` — the AI's reasoning

Recent models "think" before answering. This file displays that reasoning in three modes:

- `short`: truncated (default);
- `full`: complete;
- `off`: hidden.

**Why display it?** To understand the reasoning and spot possible mistakes.

### `markdown_engine.py` — formatting

Turns the AI's answer into formatted text: headings, lists, colored code. It uses the **Rich** library.

**Why Rich?** Because it makes Markdown readable in a terminal and handles colors and code blocks.

## In summary

| File | Role | Library used |
|---|---|---|
| `cli.py` | the conversational loop | — |
| `interface/panel.py` | banner and footer | Rich |
| `interface/prompt.py` | input + `@` auto-completion | prompt-toolkit |
| `interface/messages.py` | history | — |
| `interface/thinking.py` | display of the reasoning | Rich |
| `markdown_engine.py` | Markdown rendering | Rich |

---

> [← Previous: Overview](01-overview.md) · [Index](README.md) · [Next: The Gateway →](03-gateway.md)
