"""Slash commands registry: one module per command, listed in ``COMMANDS``."""

from discord import app_commands

from .config import config_command
from .config_review import config_review_command, disable_review_monitor_command

COMMANDS = [
    config_command,
    config_review_command,
    disable_review_monitor_command,
]


def register_commands(tree: app_commands.CommandTree) -> None:
    """Register every command of the registry on the application command tree."""
    for command in COMMANDS:
        tree.add_command(command)


__all__ = ["COMMANDS", "register_commands"]
