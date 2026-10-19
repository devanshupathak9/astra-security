"""Loads config.yaml, filling ${VAR} placeholders from the environment / .env.

  ${NAME}            value of NAME (empty if not set)
  ${NAME:-default}   value of NAME, or `default` if not set

Placeholders are replaced in the text before YAML parsing, so numbers stay numbers
and an empty value becomes null.
"""
import os
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv

PLACEHOLDER = re.compile(r"\$\{(\w+)(?::-([^}]*))?\}")


def load_config(path: str = "config.yaml") -> dict:
    load_dotenv(Path.cwd() / ".env")
    text = Path(path).read_text()
    text = PLACEHOLDER.sub(lambda m: os.environ.get(m.group(1)) or (m.group(2) or ""), text)
    return yaml.safe_load(text)
