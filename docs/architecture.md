> [← Index](README.md) · [Next: Overview →](01-overview.md)

# Architecture

A single map of the layers, the files, and how a request travels through them. For a gentler walkthrough, read the [Overview](01-overview.md) first.

## Layer map

```mermaid
flowchart TD
    User(["You"]) -->|"question"| run_cli

    subgraph cli["cli/ — talks with you"]
        direction TB
        run_cli["run_cli()<br/>main loop"]
        prompt["prompt.py<br/>input + @ completion"]
        panel["panel.py<br/>banner + footer"]
        thinking["thinking.py<br/>reasoning display"]
        md["markdown_engine.py<br/>Markdown rendering"]
        history["messages.py<br/>MessageHistory"]
        run_cli --- prompt
        run_cli --- panel
        run_cli --- thinking
        run_cli --- md
        run_cli --- history
    end

    run_cli -->|"stream_text()"| gateway

    subgraph gw["gateway/ — the brain"]
        direction TB
        gateway["Gateway<br/>orchestration + tool loop"]
        msgs["messages.py<br/>build / format messages"]
        prov["providers.py<br/>provider adapters"]
        cfg["config.py<br/>settings + .env"]
        sysp["prompts.py<br/>system prompt"]
        models["models.py<br/>ModelResponse / StreamChunk"]
        gateway --- msgs
        gateway --- prov
        gateway --- models
        cfg --- gateway
        sysp --- msgs
    end

    gateway -->|"tool call"| registry
    registry -->|"output"| gateway
    prov <-->|"API calls"| ai

    subgraph tools["tools/ — the hands"]
        direction TB
        registry["__init__.py<br/>TOOLS / to_schemas / execute_tool"]
        listfiles["listfiles"]
        readfiles["readfile"]
        where["where"]
        quit["quit"]
        registry --- listfiles
        registry --- readfiles
        registry --- where
        registry --- quit
    end

    subgraph ai["AI providers"]
        direction TB
        ollama["Ollama (local)"]
        api["OpenAI-compatible API"]
    end
```

## Role of each part

| Layer / file | Role | Knows about |
|---|---|---|
| `cli/cli.py` | `run_cli()`: reads your input, consumes the `StreamChunk` stream, renders, updates token counters | `Gateway`, `StreamChunk` |
| `cli/interface/prompt.py` | Text input with history and `@` file completion | prompt-toolkit |
| `cli/interface/panel.py` | Banner and footer, reads the displayed model from config | `config.json` |
| `cli/interface/thinking.py` | Renders the model's reasoning (`short` / `full` / `off`) | — |
| `cli/interface/messages.py` | `MessageHistory`: stores `{role, content}` turns | — |
| `cli/markdown_engine.py` | Renders the final answer as Markdown | Rich |
| `gateway/gateway.py` | `Gateway`: provider dispatch, the tool loop, error translation | all gateway modules + `tools` |
| `gateway/messages.py` | `build_messages`, `assistant_message`, `tool_result_message` | `prompts`, provider dialect |
| `gateway/providers.py` | Adapters: `call_/stream_ollama`, `call_/stream_openai`, usage + signature helpers | Ollama, OpenAI SDK |
| `gateway/config.py` | Loads `config.json` and `.env` | filesystem |
| `gateway/prompts.py` | The system prompt (AI personality and rules) | — |
| `gateway/models.py` | `ModelResponse` and `StreamChunk` data types | — |
| `tools/__init__.py` | `TOOLS` registry, `to_schemas`, `execute_tool`, `get_tools` | each tool module |
| `tools/*.py` | The concrete actions: list, read, locate, quit | filesystem |

## One request, step by step

```mermaid
sequenceDiagram
    actor U as You
    participant C as CLI (run_cli)
    participant G as Gateway
    participant P as Provider
    participant T as Tool

    U->>C: question
    C->>G: stream_text(prompt, history)
    loop up to 10 turns
        G->>P: messages + tool schemas
        P-->>G: content / thinking / tool_calls
        alt no tool call
            G-->>C: StreamChunk(content) — final answer
        else tool call requested
            G-->>C: StreamChunk(tool_call)
            G->>T: execute_tool(name, args)
            T-->>G: output
            G-->>C: StreamChunk(tool_result)
        end
    end
    C-->>U: rendered Markdown + token count
```

## Rule of thumb

Each layer only knows the layer directly below it (CLI → Gateway → Tools). The one exception is the provider call, which the Gateway owns end to end. This is what lets you change a layer without touching the others — details in [Extending the project](07-extending.md).

---

> [← Index](README.md) · [Next: Overview →](01-overview.md)
