<div align="right">
   <img src="./Clarity.png" alt="Logo Zetelton" width="72" style="border-radius: 10px;">
</div>

# Zetelton

![banner](%5Bt%C3%976s%5D_%5B75caebef-f2f2-4a20-8a92-d7d1c80db737%5D_2026-10-05_00-37-29.svg)

> **A simple, customizable base for building your own terminal agent.**

[![Version](https://img.shields.io/badge/version-pre--alpha_v0.0.1-yellow.svg)](https://github.com/vznd3v/Zetelton-agent)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Zetelton** is a minimal Python agent base designed to be customized. It connects an LLM provider to a set of tools and presents the result through a Rich-based interactive CLI. Each layer is small and separated, so you can replace the provider, add tools, or restyle the interface without touching the rest. Out of the box, it ships as a codebase exploration assistant with filesystem tools.

## Features

- **Customizable agent base**: separated layers (CLI, gateway, tools, config) you can extend or replace independently.
- **Codebase exploration**: list directories and read file contents through the built-in example tools.
- **Multi-provider gateway**: use local Ollama models or OpenAI-compatible APIs such as OpenRouter.
- **Streaming responses**: stream text, reasoning, tool results, and provider errors through one gateway interface.
- **Tool calling**: execute `listfiles`, `readfile`, and `quit` from model-generated tool calls.
- **Terminal Markdown**: render agent responses with Rich, including syntax-highlighted code blocks.
- **Token statistics**: show provider usage when available and a clearly marked estimate otherwise.
- **File references**: autocomplete files and directories after typing `@` in the prompt.
- **Tested core**: unit tests cover the gateway, tools, streaming, Markdown rendering, and completion.

## Architecture

The project follows a simple, layered architecture. Each directory has a single responsibility, and dependencies flow in one direction only:

```text
Zetelton-agent/
├── src/agent/
│   ├── cli/                # Terminal interface, Markdown renderer, prompt completion
│   ├── config/             # Provider and model configuration (config.json)
│   ├── gateway/            # Provider calls, streaming, tool-call normalization
│   ├── tools/              # Agent tools: small, provider-independent actions
│   └── main.py             # CLI entry point
├── tests/                  # Unit and integration tests
├── pyproject.toml          # Python project and command configuration
└── README.md
```

The boundaries are:

```text
CLI ──> Gateway ──> LLM provider
   │          └───> Tools
   └── presentation only
```

- **CLI** owns presentation: prompt, Markdown rendering, completion, and usage display. It contains no provider or tool logic.
- **Gateway** owns provider communication: message construction, streaming, tool-call normalization, errors, and token usage. It is the only layer that knows about Ollama or OpenAI-compatible APIs.
- **Tools** are small provider-independent functions exposed to the model. They know nothing about the CLI or the gateway.
- **Config** is a plain JSON file selecting the provider and model.

Because each layer is isolated, you can fork this base and customize one layer at a time without breaking the others.

## Customization

Zetelton is meant to be a starting point for your own agent. The common customization points are:

### Add a tool

1. Create a module in `src/agent/tools/` implementing the action.
2. Define its JSON schema and register it so the gateway can expose it to the model.
3. Add focused tests in `tests/`.

Tools stay provider-independent: they receive plain arguments and return plain results.

### Change the provider or model

Edit `src/agent/config/config.json` to select the default provider and model. External providers use an OpenAI-compatible API with a key from `.env`; Ollama runs fully locally.

### Add a provider

Normalize the provider's responses and tool-call format inside `src/agent/gateway/`. Never add provider logic to the CLI or tools.

### Restyle the interface

All presentation code lives in `src/agent/cli/` (Markdown rendering, prompt completion, usage display). Changing the look and feel never affects the gateway or tools.

## Getting Started

### Requirements

- Python `3.11` or newer;
- `uv`, recommended for dependency management;
- Ollama, only when using the local provider;
- an OpenRouter or other OpenAI-compatible API key, only when using an external provider.

### Installation

```bash
git clone https://github.com/vznd3v/Zetelton-agent.git
cd Zetelton-agent
uv sync
```

`uv sync` installs the pure-Python package, so no Rust toolchain is required.

### Scaffold a new agent

`zetelton-init` (a separate project) generates a ready-to-run project from this
base: it copies the bare Python package, writes the provider configuration, and
keeps only the tools you select (`listfiles`, `readfile`, `where`; `quit` is
always included). No RAG, no web tool, and no persistent memory are added.

Run it once, without cloning:

```bash
uvx zetelton-init
```

It asks a few basic questions (project name, package, provider, model, tools).
For scripts and CI, skip the prompts with `-y` and pass answers as flags:

```bash
uvx zetelton-init ./my-agent \
  --name my-agent \
  --provider local \
  --model qwen3:4b \
  --tools listfiles,where \
  -y
```

Flags:

- `--name`: project and distribution name.
- `--package`: Python import package name (default: derived from `--name`).
- `--provider`: `local` (Ollama) or `external` (OpenAI-compatible API).
- `--model`: model name for the selected provider.
- `--base-url`: base URL for the external provider.
- `--api-key`: API key written to `.env` for the external provider.
- `--tools` (alias `--features`): comma-separated tools to include.
- `--force`: write into a non-empty directory.

The generated project is a standalone, pure-Python package: `cd` into it, run
`uv sync`, then `uv run <name>`.

### Provider configuration

The default provider and model are configured in `src/agent/config/config.json`.

For an external OpenAI-compatible provider, create a local `.env` file:

```dotenv
EXTERNAL_API_KEY=replace_with_your_api_key
```

`OPENAI_API_KEY` is also supported. `.env` is ignored by Git and must never be committed.

For Ollama, install the selected model and start the service:

```bash
ollama pull qwen3:4b
ollama serve
```

Start the CLI with:

```bash
uv run zetelton
```

### Examples

```text
Zetelton > list the files in /path/to/project
Zetelton > read src/agent/main.py
Zetelton > what is inside @src/agent/gateway/gateway.py
```

Type `@` followed by a path fragment to autocomplete files and directories from the current working directory.

## Built-in tools

- `listfiles`: list entries in a directory.
- `readfile`: read and return the complete content of a file.
- `quit`: stop the interactive session.

Tool calls are exposed when the request concerns files or directories. The gateway normalizes streamed tool-call fragments from OpenAI-compatible providers before executing them.

## Roadmap

- [ ] Add architecture and dependency graph tools.
- [ ] Add flowchart generation and a graphical flowchart view.
- [ ] Add a CLI splash screen.
- [ ] Add a `/provider` command for changing providers during a session.

## Contributing

The project is in active **pre-alpha (`v0.0.1`)**. Bug reports, provider compatibility notes, tests, and focused improvements are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.

## License

Distributed under the MIT License. See `LICENSE` for more information.

---

<sub>dev by Zetelton Labs by Niceware</sub>
