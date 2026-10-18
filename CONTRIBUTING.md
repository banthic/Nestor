# Contributing to Nestor

Thank you for contributing to Nestor, Banthic Labs' AI-powered community assistant built on Zetelton. The project is in pre-alpha, so focused changes, regression tests, provider compatibility reports, and documentation improvements are especially useful.

## Development setup

Requirements:

- Python `3.11` or newer;
- `uv`;
- Ollama for local-provider work, or an OpenAI-compatible API key for external-provider work.

```bash
git clone https://github.com/banthic/Nestor.git
cd Nestor
uv sync
```

Create a local `.env` only when you need an external provider:

```dotenv
EXTERNAL_API_KEY=replace_with_your_api_key
```

Never commit `.env`, API keys, tokens, or generated credentials. The repository ignores `.env`, but check `git status` before committing.

## Running the project

```bash
uv run nestor
```

Provider selection and model names are stored in `src/agent/config/config.json`. Keep provider-specific behavior in the gateway; tools should not depend on Ollama, OpenRouter, or another provider.

## Validation

Run the complete test suite and lint before opening a pull request:

```bash
uv run python -m unittest discover -s tests
uv run ruff check .
```

The tests cover the gateway, provider streaming normalization, tool dispatch, CLI rendering, Markdown output, and `@` file completion. Tests must not make real network requests. Mock provider responses and force a deterministic provider in gateway tests when needed.

## Project boundaries

- `src/agent/gateway/`: provider communication, message construction, streaming, tool-call normalization, provider errors, and usage extraction.
- `src/agent/tools/`: small provider-independent actions exposed to the model.
- `src/agent/cli/`: terminal presentation, Markdown rendering, prompt completion, thinking display, and usage display.
- `tests/`: focused regression and integration tests.

When adding a provider, normalize its response in the gateway rather than adding provider logic to the CLI or tools. When adding a tool, define its schema, implementation, registry entry, and focused tests together.

## Code style

- Keep new code and code comments in English.
- Follow the existing Python typing and `unittest` style.
- Prefer small, focused changes over unrelated refactors.
- Use existing dependencies and project patterns before adding abstractions.
- Add a regression test for bug fixes.

## Pull requests

Pull requests should explain:

- what behavior changed;
- why the change is needed;
- how it was tested;
- any provider-specific limitation or configuration requirement.

Keep commits focused and do not include secrets, local configuration, virtual environments, build artifacts, or generated files.
