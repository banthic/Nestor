# Project notes

**Vision**: Nestor is Banthic Labs' AI-powered community assistant, built on Zetelton. Designed to support Discord helpers and moderators, it combines intelligent assistance, contextual knowledge retrieval, and agent-powered tools to make community management simpler, smarter, and more efficient. It keeps a simple, separated architecture (CLI / Gateway / Tools / Config).

## completed

- [x] coding the base of the cli interface and test the history and the call to ollama
- [x] create a good files structure for the projects
- [x] create the first tools of the agent that lets him to read the files in the directory where he is

- [x] make a gateway for using ollama or open ai with an other base url if the user want an non-local model
- [x] test the first tool call with the model llama3.2:1b and a external api

- [x] add the readfiles tools

- [x] best cli  for chatting (adding a markdown engine and a stats panel, and a completer for @ a file or folder)

- [x] add a `zetelton-init` scaffolder that generates a ready-to-run agent project
- [x] drop the experimental Rust module and build as a pure-Python wheel (hatchling)

## zetelton-init

`zetelton-init` lives in its own project (separate repo) and creates a
ready-to-run Zetelton agent: it copies the base `agent/` package, writes the
provider config, and keeps only the selected tools (`listfiles`, `readfile`,
`where`; `quit` always included). No RAG, no web, no persistent memory.

Run it without cloning:

```bash
uvx zetelton-init
```

`-y` / `--no-input` skips the prompts and uses the flags (or defaults).

## what next

- [ ] new tools like generate_flowchart and more
- [ ] graphic ui for show the flowchart 
- [ ] a splash for the cli
- [ ] a command /provider for choose the default provider in the config json
