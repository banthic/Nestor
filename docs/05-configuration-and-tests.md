> [← Previous: Tools](04-tools.md) · [Index](README.md) · [Next: Key concepts →](06-concepts.md)

# 5. Configuration & tests

## Configuration: `src/agent/config/config.json`

```json
{
  "default_provider": "external_api_openai_compatible",
  "provider": {
    "external_api_openai_compatible": { "base_url": "...", "model": "..." },
    "local_ollama": { "model": "qwen3:4b" }
  }
}
```

- `default_provider`: which provider to use by default.
- `model`: the name of the model.
- `base_url`: the address of the online API.

**Why a JSON file rather than code?** So you can change model without touching the code. A setting should stay a setting.

## The secret: `.env`

The `.env` file (at the root) contains the **secrets**, such as your API key:

```dotenv
EXTERNAL_API_KEY=replace_with_your_api_key
```

**Why separate?** To never put a password in the Git repository. This file is ignored by Git (`.gitignore`). For Ollama locally, no key is needed.

## The tests: `tests/`

The tests run the code with **fake AI responses** and check that it reacts well.

**Why is this important?** When you modify something, the tests immediately tell you if you broke something else. They **make no network calls**: everything is simulated, so they are fast, free and reliable.

| File | What it checks |
|---|---|
| `test_tools.py` | the tools list and read correctly |
| `test_gateway.py` | the tool loop, the streaming, the Gemini signature |
| `test_interface.py` | the display of the banner, the thinking, the history |
| `test_cli.py` | the terminal loop |

### Running the tests and the style check

```bash
uv run python -m unittest discover -s tests
uv run ruff check .
```

- The first command runs **all the tests**.
- The second runs **ruff**, a tool that checks the code follows the formatting rules. **Why?** To keep a consistent style without arguing over the details.

---

> [← Previous: Tools](04-tools.md) · [Index](README.md) · [Next: Key concepts →](06-concepts.md)
