import json
from pathlib import Path

from dotenv import load_dotenv

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.json"
DOTENV_PATH = Path(__file__).resolve().parents[3] / ".env"

load_dotenv(dotenv_path=DOTENV_PATH)


def load_config() -> dict:
    """Read the provider and model configuration file."""
    with CONFIG_PATH.open() as config_file:
        return json.load(config_file)
