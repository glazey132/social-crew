"""Load KEY=value pairs from a .env file into os.environ (for local runs without export)."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path | None = None) -> bool:
    """
    Parse .env and set os.environ. Values support ${VAR} expansion via os.path.expandvars.

    Returns True if a file was read, False if missing.
    """
    if path is None:
        path = Path.cwd() / ".env"
    path = path.resolve()
    if not path.is_file():
        return False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        value = os.path.expandvars(value)
        os.environ[key] = value
    return True
