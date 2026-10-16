"""Loads config.yaml and .env."""
import yaml
from dotenv import load_dotenv


def load_config(path: str = "config.yaml") -> dict:
    load_dotenv()
    with open(path) as f:
        return yaml.safe_load(f)
