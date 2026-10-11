import json
from pathlib import Path

from rich.console import Console
from rich.text import Text

"""Terminal layout components for the Zetelton CLI."""

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.json"
SEPARATOR = "─"


def get_provider_metadata() -> tuple[str, str]:
    """Return the configured provider label and model name."""
    try:
        with CONFIG_PATH.open() as config_file:
            config = json.load(config_file)
    except (OSError, json.JSONDecodeError):
        return "Provider", "Unknown model"

    provider_name = config.get("default_provider", "Provider")
    provider_config = config.get("provider", {}).get(provider_name, {})
    model = provider_config.get("model", "Unknown model")
    if provider_name == "external_api_openai_compatible":
        provider_name = "OpenAI-compatible API"
    elif provider_name == "local_ollama":
        provider_name = "Ollama"
    return provider_name, model


def get_panel(provider: str | None = None, model: str | None = None) -> Text:
    """Build the startup metadata block for the terminal."""
    configured_provider, configured_model = get_provider_metadata()
    provider = provider or configured_provider
    model = model or configured_model

    content = Text()
    content.append("Zetelton\n", style="bold bright_cyan")
    content.append(f"{provider} · {model}\n", style="bold bright_magenta")
    content.append(f"{Path.cwd()}", style="bright_green")
    return content


def get_separator(width: int = 80) -> Text:
    """Build a full-width terminal separator."""
    return Text(SEPARATOR * max(width, 1), style="dim bright_cyan")


def get_footer(
    provider: str | None = None,
    model: str | None = None,
    usage: dict[str, int] | None = None,
) -> Text:
    """Build the shortcuts and model status line below the prompt."""
    configured_provider, configured_model = get_provider_metadata()
    provider = provider or configured_provider
    model = model or configured_model
    usage_text = ""
    if usage:
        usage_text = (
            f"   Tokens {usage.get('total_tokens', '?')}"
            f" (in {usage.get('prompt_tokens', '?')}, out {usage.get('completion_tokens', '?')})"
        )

    footer = Text()
    footer.append("? for shortcuts", style="dim white")
    footer.append(" " * 8, style="dim white")
    footer.append(f"{provider} · {model}", style="dim bright_cyan")
    footer.append(usage_text, style="dim bright_magenta")
    footer.append("   dev by Zetelton Labs by Niceware", style="dim")
    return footer


def render_panel(console: Console | None = None) -> None:
    """Render the startup metadata block once."""
    active_console = console or Console()
    active_console.print(get_panel())


def render_prompt_frame(console: Console, usage: dict[str, int] | None = None) -> None:
    """Render the separator and footer before the next prompt."""
    console.print(get_separator(console.width))
    console.print(get_footer(usage=usage))
