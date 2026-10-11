# Reprise du projet Zetelton — à reprendre demain

## Contexte

Zetelton est une base d'agent terminal en Python, avec une architecture séparée en couches :

- `src/agent/cli/` : interface terminale (Rich), markdown, autocomplétion `@`
- `src/agent/gateway/` : communication provider (Ollama local ou API OpenAI-compatible)
- `src/agent/tools/` : tools exposés au modèle (`listfiles`, `readfile`, `where`, `quit`)
- `src/agent/config/config.json` : provider + modèle par défaut

Le but du projet : une base facile à forker/customiser.

## Ce qui a été commencé aujourd'hui

Ajout d'un **CLI scaffolder** `zetelton-init` (le projet est généré avec `uvx`, façon `npx init` en Python).

- Nouveau package : `src/agent/scaffold/`
  - `features.py` : catalogue des tools sélectionnables = **uniquement les tools réels** (`listfiles`, `readfiles`, `where` ; `quit` toujours inclus). Pas de RAG, pas de web, pas de mémoire permanente.
  - `templates.py` : génération de `pyproject.toml`, `README.md`, `.gitignore`, `.env`, `.env.example`, `.python-version`, `tests/`, et de `tools/__init__.py`.
  - `generator.py` : copie la base `agent/` (en excluant `tools/`, `config/`, `scaffold/`, les `.so`), puis écrit la config + les tools choisis.
  - `wizard.py` : wizard interactif (prompt_toolkit) — nom, package, dossier, provider local/external, modèle, clé API, sélection des tools.
  - `main.py` : entrée `zetelton-init` (argparse + mode `-y/--no-input`).
- `pyproject.toml` : ajout du script console `zetelton-init = "agent.scaffold.main:main"`.
- Tests manuels OK : génération dans `/tmp`, `tools/__init__.py` correct, imports OK (`['listfiles', 'readfile', 'where', 'quit']`).

Commande testée (fonctionne) :

```bash
uv run zetelton-init /tmp/demo-agent --name demo-agent --provider local --model qwen3:4b \
  --tools listfiles,readfiles,where -y
```

## Nettoyage fait : suppression du Rust/maturin

Le module Rust `_core` n'était importé nulle part. Supprimé pour repasser en Python pur :

- `git rm` de `Cargo.toml`, `Cargo.lock`, `src/rust/lib.rs`
- rm de `target/` et `src/agent/_core.cpython-*.so`
- `[tool.maturin]` → build backend **hatchling** (`[tool.hatch.build.targets.wheel] packages = ["src/agent"]`)
- `.gitignore` nettoyé (plus de `target/`, `*.so`, `*.pyd`)
- README mis à jour (plus de toolchain Rust requise)

Vérifié : `uv lock` OK, `uv build --wheel` OK et le wheel **contient bien `agent/scaffold/`** (le doute
maturin est réglé). `uv run zetelton` et `uv run zetelton-init --help` fonctionnent.

## ⚠️ À savoir sur l'état git

Le working tree contenait **déjà** des modifs non commitées avant cette session
(`CONTRIBUTING.md`, `README.md`, `project.md`, `src/agent/cli/...`, `tests/...`,
`uv.lock`). Mes changements à moi :

- `pyproject.toml` (script `zetelton-init` + backend hatchling)
- `.gitignore`
- suppression `Cargo.toml`, `Cargo.lock`, `src/rust/lib.rs`
- `src/agent/scaffold/` (nouveau, non tracké)
- `RESUME.md`

Ne pas tout mélanger dans un commit : vérifier `git status` / `git diff` avant.

## Reste à faire

- [ ] Écrire `tests/test_scaffold.py` (génération non-interactive dans un `TemporaryDirectory`, vérifier les fichiers et le registre de tools).
- [ ] Documenter `zetelton-init` dans `README.md` et `project.md` (section "Getting Started" / usage `uvx`).
- [ ] Vérifier le packaging `uvx` : `uvx --from git+https://github.com/vznd3v/Zetelton-agent zetelton-init`. Documenter la commande exacte.
- [ ] Lancer `uv run ruff check .` et `uv run python -m unittest discover -s tests`.
- [ ] Tester le wizard interactif pour de vrai (prompt_toolkit dialogs) dans un vrai terminal.
- [ ] Décider du nom du flag : `--tools` (alias `--features` conservé) — valider.

## Prompt à coller demain

```text
On reprend le projet Zetelton (/Users/vzn/Desktop/Zetelton).

Contexte : j'ai ajouté hier un CLI scaffolder `zetelton-init` dans src/agent/scaffold/
(features.py, templates.py, generator.py, wizard.py, main.py), enregistré dans
pyproject.toml. Il génère un projet agent Zetelton prêt à l'emploi (copie de la base
agent/ + config provider + tools choisis). Les features sélectionnables sont
UNIQUEMENT les tools existants (listfiles, readfiles, where ; quit toujours inclus).
PAS de RAG, PAS de web, PAS de mémoire permanente.

Lis d'abord RESUME.md à la racine, puis git status et git diff pour voir l'état.

À faire aujourd'hui, dans cet ordre :
1. Ajouter tests/test_scaffold.py (unittest, style du repo) qui génère dans un
   TemporaryDirectory en mode non-interactif et vérifie les fichiers + le registre.
2. Documenter zetelton-init dans README.md + project.md (usage uvx + uv run).
3. Vérifier la commande uvx : `uvx --from git+https://github.com/vznd3v/Zetelton-agent zetelton-init`.
4. Lancer `uv run ruff check .` et `uv run python -m unittest discover -s tests`,
   corriger ce qui casse.

Note : le build maturin/Rust a été supprimé (backend hatchling, Python pur) — le clone
n'a plus besoin de toolchain Rust. Le wheel embarque bien agent/scaffold.

Contraintes : code/commentaires en anglais, style unittest, ne pas toucher aux modifs
non liées déjà présentes dans le working tree, ne pas commit sans que je le demande.
```
