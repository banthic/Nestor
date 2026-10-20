# Interface Discord (Nestor)

Ce document décrit l'ajout de l'**interface Discord** au projet Nestor : remplacement
du point d'entrée CLI par un **bot Discord** (via la librairie officielle `discord.py`)
exposant des **slash commands** et une **UI Discord** (modale Components V2 + embed).

> Objectif de cette itération : fournir la base du bot et une commande `/config`
> permettant de choisir, via une **modale**, le **salon qui sert de chatbot**.
> Le bot et son UI sont en **anglais**. Le câblage du moteur Nestor (`Gateway`) sur
> les messages du salon viendra ensuite.

## 1. Ce qui a été ajouté

| Fichier / dossier | Rôle |
|---|---|
| `src/agent/discord_app/` | Nouvelle couche interface Discord (sœur de `cli/`) |
| `src/agent/discord_app/__init__.py` | Exports publics : `NestorBot`, `run_bot`, `build_intents` |
| `src/agent/discord_app/bot.py` | Client Discord (`NestorBot`), intents, chargement token, `run_bot()` |
| `src/agent/discord_app/commands/` | Dossier des slash commands (un fichier par commande) |
| `src/agent/discord_app/commands/__init__.py` | Registre `COMMANDS` + `register_commands()` |
| `src/agent/discord_app/commands/checks.py` | Checks partagés (`can_configure`) |
| `src/agent/discord_app/commands/config.py` | Slash command `/config` |
| `src/agent/discord_app/settings.py` | Persistance des réglages Discord (`config/discord.json`) |
| `src/agent/discord_app/ui/__init__.py` | Exports UI |
| `src/agent/discord_app/ui/config_modal.py` | Modale Components V2 (Label + ChannelSelect) |
| `src/agent/discord_app/ui/banner.py` | Bandeau (Container V2) posté dans le salon chatbot |
| `src/agent/config/discord.json` | Fichier de réglages Discord (créé, vide au départ) |
| `tests/test_discord_settings.py` | Tests settings + modale |
| `pyproject.toml` | Ajout de `discord-py>=2.7.1` + script `nestor-cli` |
| `.env` | Ajout de la clé `DISCORD_TOKEN` (à remplir par toi) |

## 2. Structure et séparation des couches

L'architecture en couches du projet est respectée : la nouvelle interface `discord_app/`
est l'équivalent exact de `cli/`. Elle ne fait que de la **présentation / interaction**
et ne contient pas de logique LLM.

```
src/agent/
├── discord_app/        <-- NOUVEAU : interface Discord (présentation)
│   ├── bot.py          #   client Discord, intents, lifecycle
│   ├── commands/       #   une commande par fichier + registre
│   │   ├── __init__.py #     COMMANDS + register_commands()
│   │   ├── checks.py   #     checks partagés
│   │   └── config.py   #     /config
│   ├── settings.py     #   persistance des réglages Discord
│   ├── agent_bridge.py #   pont Discord <-> Gateway (outils Discord)
│   └── ui/
│       ├── config_modal.py   # modale Components V2
│       └── banner.py         # bandeau posté dans le salon
├── cli/                # interface terminal (conservée, accessible via `nestor-cli`)
├── gateway/            # moteur / boucle agent + providers (system prompt paramétrable)
├── tools/              # outils exposés au modèle : rename_server uniquement
└── config/             # config.json + discord.json
```

- `discord_app/` ne dépend **pas** de `cli/`.
- `settings.py` lit le prompt Discord par défaut depuis `gateway/prompts.py`.
- Le registre `tools/` ne contient plus qu'un seul outil, `rename_server` (voir §3 ter).
  paramétrable (aucun changement de comportement par défaut).

## 3. Détail des modules

### `settings.py` — persistance

Gère un fichier `src/agent/config/discord.json` de la forme :

```json
{
    "system_prompt": "",
    "guilds": {
        "123456789012345678": { "chatbot_channel_id": 987654321098765432 }
    }
}
```

API publique :

- `get_chatbot_channel_id(guild_id: int) -> int | None`
- `set_chatbot_channel_id(guild_id: int, channel_id: int) -> None`
- `get_system_prompt() -> str` / `set_system_prompt(prompt: str) -> None`

La lecture est défensive : fichier absent ou JSON corrompu ⇒ valeurs par défaut (le bot
ne crashe pas). La clé `guilds` est indexée par **serveur** (guild), donc chaque serveur a
son propre salon.

`system_prompt` est le **mod Discord** ajouté au system prompt du gateway (voir §3 bis).
Vide ou absent ⇒ le mod par défaut `DISCORD_SYSTEM_PROMPT` est utilisé.

### `bot.py` — client Discord

- `build_intents()` : `Intents.default()` + `message_content = True`
  (`guilds` est déjà actif par défaut). Les intents correspondent à ce que tu as demandé :
  - `guilds` (+ `members` si tu l'actives dans le portail développeur)
  - `message_content`
- `NestorBot(discord.Client)` :
  - crée son `app_commands.CommandTree` dans `__init__` ;
  - `setup_hook()` enregistre les slash commands puis synchronise l'arbre ;
  - `on_ready()` logge la connexion via `rich` ;
  - `on_message()` : déclenche l'agent (voir `agent_bridge.py`) uniquement dans le salon
    chatbot du serveur, ignore les bots et les messages commençant par `/`.
- `run_bot()` : charge `.env`, vérifie `DISCORD_TOKEN`, valide `DISCORD_GUILD_ID`
  si présent, puis démarre le bot.

**Sync des commandes** : si `DISCORD_GUILD_ID` est défini dans `.env`, les commandes
sont copiées + synchronisées sur ce serveur uniquement (propagation instantanée, idéal en dev).
Sinon elles sont synchronisées globalement (propagation jusqu'à 1 h côté Discord).

### `agent_bridge.py` — pont Discord <-> Gateway (outils Discord)

C'est le module qui **branche l'agent** sur les messages Discord :

- `AgentBridge` garde un historique de conversation **par salon** (mémoire, 20 derniers
  messages via `MAX_HISTORY_MESSAGES`).
- `reply(channel_id, prompt, guild=None)` construit
  `Gateway(tools=DISCORD_TOOLS, system_prompt_suffix=get_system_prompt())` et consomme
  `stream_text()` dans un thread (`asyncio.to_thread`) pour ne pas bloquer la boucle Discord.
- **Seuls les outils Discord** (`DISCORD_TOOLS = [rename_server]`) sont exposés au modèle :
  aucun outil filesystem/host n'est passé, donc un message Discord ne peut pas toucher à la
  machine qui fait tourner le bot.
- Au début de `reply`, si une `guild` est fournie, le bridge enregistre un *handler* de
  renommage (`set_rename_handler`). Ce handler programme la coroutine `guild.edit(name=...)`
  sur la boucle du bot via `asyncio.run_coroutine_threadsafe` (le tool s'exécute dans le
  thread du flux) et est **nettoyé** après la réponse (`set_rename_handler(None)`).
  `discord.Forbidden` / `discord.HTTPException` sont convertis en texte renvoyé au modèle.
- `split_message()` découpe les réponses > 2000 caractères pour respecter la limite Discord.

### `commands/` — slash commands (un fichier par commande)

- `config.py` : la commande `/config` (`guild_only`, réservée aux membres ayant la
  permission **Manage Server**). Elle ouvre une **modale** Components V2.
- `checks.py` : checks réutilisables (`can_configure`).
- `__init__.py` : registre `COMMANDS` (liste des commandes) et `register_commands(tree)`,
  point unique d'enregistrement sur l'arbre.

**Ajouter une commande** : créer un fichier `commands/ma_commande.py` exposant une
commande décorée `@app_commands.command(...)`, puis l'ajouter à `COMMANDS` dans
`commands/__init__.py`. Elle sera enregistrée automatiquement par `register_commands()`.

### `ui/config_modal.py` — modale Components V2

Modale basée sur `discord.ui.Modal` composée d'un `Label` (Components V2) contenant un
`ChannelSelect` (types texte uniquement) :

- **Chatbot channel** — libellé du champ, avec description ;
- sélection d'un salon → à la soumission (`on_submit`), le salon est écrit via
  `settings.set_chatbot_channel_id` ;
- confirmation → réponse ephemeral en **embed** vert (« Configuration saved — Nestor will
  now act as a chatbot in #channel »).

La modale est ouverte par `/config` via `interaction.response.send_modal(...)`.

### `ui/banner.py` — bandeau du salon

Un **bandeau** (inspiré du panel du CLI) est posté automatiquement dans le salon chatbot
dès que `/config` est confirmé. C'est un `Container` (Components V2, type 17) avec accent
couleur, contenant :

- un titre + sous-titre (« Nestor — Your community assistant ») ;
- des séparateurs ;
- un bloc d'infos avec des **placeholders** (`Status`, `Provider`, `Model`, `Commands`) —
  volontairement non reliés à l'agent pour l'instant ;
- une signature discrète « Powered by Banthic Labs ».

`post_banner(channel)` envoie le bandeau et retourne le `discord.Message`. Si le bot n'a
pas accès au salon (permissions), la confirmation ephemeral l'indique.

## 3 bis. System prompt Discord (mod ajouté au gateway)

Pour limiter les actions au strict nécessaire, le bot Discord n'expose que l'outil Discord
`rename_server` à l'agent et ajoute un **mod de system prompt** à celui du gateway.

- Le gateway accepte désormais `Gateway(tools=..., system_prompt=..., system_prompt_suffix=...)`.
  `build_messages()` concatène : `SYSTEM_PROMPT` du gateway + `"\n\n"` + le suffixe Discord.
- Le mod par défaut est `DISCORD_SYSTEM_PROMPT` (`gateway/prompts.py`) : il précise que
  l'agent tourne dans Discord, que les outils filesystem sont **désactivés**, que le seul
  outil disponible est `rename_server`, et qu'il ne faut l'utiliser **que** si l'utilisateur
  demande explicitement de renommer le serveur.
- Ce mod est **surchargeable** par serveur via la clé `system_prompt` de `discord.json`
  (`settings.get_system_prompt()` / `set_system_prompt()`). Vide ⇒ mod par défaut.

## 3 ter. Outil `rename_server`

Le registre `src/agent/tools/` ne contient plus qu'un seul outil : `rename_server`.

- `tools/rename_server.py` décrit l'outil (`name`, `description`, paramètre requis `name`)
  et délègue l'exécution à un *handler* enregistré par la couche Discord via
  `set_rename_handler` / `clear_rename_handler`.
- Sans handler (CLI, tests, contexte hors Discord), le tool renvoie simplement
  « Renaming the server is not available in this context. » — il ne touche à rien.
- `tools/quit.py` ne conserve que l'exception `QuitRequested` (contrôle de session du CLI) ;
  les anciens outils `listfiles`, `readfile`, `where` et le tool `quit` ont été supprimés.
- Le prompt de base `SYSTEM_PROMPT` a été réécrit pour ne décrire que `rename_server`.

## 4. Configuration

### `.env` (racine, non versionné)

```dotenv
DISCORD_TOKEN=ton_token_ici
# Optionnel : force la sync des slash commands sur un serveur (dev)
DISCORD_GUILD_ID=123456789012345678
```

- `DISCORD_TOKEN` est requis : sans lui, `run_bot()` s'arrête avec un message clair.
- `DISCORD_GUILD_ID` est optionnel et numérique.

### `config/discord.json`

Fichier de réglages géré par l'application (ne pas éditer à la main en général) :
il enregistre le salon chatbot **par serveur**. Créé automatiquement au premier
`/config` confirmé s'il n'existe pas.

## 5. Dépendances et scripts

`pyproject.toml` :

```toml
dependencies = [
    "discord-py>=2.7.1",
    ...
]

[project.scripts]
nestor = "agent.main:main"      # démarre le BOT Discord
nestor-cli = "agent.cli:run_cli" # conserve l'ancienne interface terminal
```

Installation / lancement :

```bash
uv sync
uv run nestor        # lance le bot Discord
uv run nestor-cli    # lance l'ancien REPL terminal
```

## 6. Intents requis dans le portail développeur Discord

Sur <https://discord.com/developers> → ton application → **Bot** → *Privileged Gateway Intents* :

- ✅ **MESSAGE CONTENT INTENT** (nécessaire : le chatbot lit désormais le contenu des messages) ;
- ✅ **SERVER MEMBERS INTENT** si tu veux cibler/mentionner les membres (optionnel pour l'instant).

Sans `message_content`, le bot ne verra pas le contenu des messages.

## 7. Tests et lint

```bash
uv run ruff check .
uv run python -m unittest discover -s tests
```

`tests/test_discord_settings.py` couvre :

- lecture/écriture des réglages (round-trip, isolation par serveur, JSON valide) ;
- fichier absent ou corrompu ⇒ valeurs par défaut ;
- modale : présence du `ChannelSelect` (type 18 → Label contenant type 8) ;
- titre de la modale en anglais (`Nestor configuration`) ;
- bandeau : rendu `Container` (type 17) avec TextDisplay/Separator et placeholders ;
- system prompt Discord : défaut, round-trip, repli si vide.

`tests/test_discord_bridge.py` couvre :

- `AgentBridge` : réponse, historique par salon, reset ;
- gateway limité aux **outils Discord** (`rename_server`) + mod Discord comme suffixe ;
- enregistrement puis nettoyage du handler de renommage autour de `reply` ;
- concaténation du system prompt (`build_messages`) ;
- découpage des messages > 2000 caractères.

`tests/test_tools.py` couvre :

- registre réduit à `rename_server` ;
- exécution sûre sans handler (message d'indisponibilité) ;
- exécution avec handler (délégation) ;
- `QuitRequested` toujours exporté pour le CLI.

## 8. Comment ça a été fait (résumé des étapes)

1. Ajout de la dépendance : `uv add discord.py` (version installée : 2.7.1),
   vérification que `discord.ui.LayoutView`, `Modal`, `Label`, `TextDisplay`, `Separator`,
   `ChannelSelect`, `ActionRow` et les décorateurs sont bien disponibles pour les
   **Components V2**.
2. Création du package `discord_app/` en respectant la séparation des couches
   (interface = présentation, pas de logique métier).
3. `settings.py` : persistance JSON isolée, robuste aux fichiers absents/corrompus.
4. `ui/config_modal.py` : modale `Modal` avec un `Label` + `ChannelSelect` ;
   `on_submit` enregistre le salon et répond avec un **embed** de confirmation.
5. `ui/banner.py` : `Container` Components V2 (bandeau) posté dans le salon configuré,
   avec placeholders d'infos.
6. `commands/` : dossier avec un fichier par commande (`config.py`), les checks partagés
   (`checks.py`) et un registre (`__init__.py`).
7. `bot.py` : `discord.Client` avec `CommandTree`, intents, sync dev/prod, `on_ready`.
8. Rebranchement de `main.py` sur `run_bot()` et ajout du script `nestor-cli`
   pour ne pas perdre l'interface terminal.
9. `.env` : ajout de `DISCORD_TOKEN` (+ `DISCORD_GUILD_ID` commenté).
10. Passage de tous les textes du bot en **anglais** (description de commande, messages,
    modale, embed, logs).
11. **Branchement de l'agent** : `agent_bridge.py` (historique par salon, `stream_text`
    via `asyncio.to_thread`) + `on_message` dans `bot.py` (répond dans le salon configuré).
12. **Sécurité** : `Gateway` accepte un `system_prompt_suffix` ; ajout de
    `DISCORD_SYSTEM_PROMPT` ; le bridge n'expose que les outils Discord. Mod surchargeable
    via `discord.json`.
13. **Remplacement des outils** : suppression de `listfiles` / `readfile` / `where` / `quit`,
    ajout de `rename_server` (handler branché sur la guild) et réécriture du `SYSTEM_PROMPT`.
14. Tests + lint.

## 9. Étapes suivantes (non incluses ici)

- Afficher dans le bandeau les vraies infos (provider, modèle, statut) au lieu des placeholders.
- Limiter le débit / le coût (rate-limit par utilisateur, longueur max).
- Persister l'historique des conversations (aujourd'hui en mémoire, perdu au redémarrage).
- Relier la config Discord à `config.json` (provider/modèle) si nécessaire.
