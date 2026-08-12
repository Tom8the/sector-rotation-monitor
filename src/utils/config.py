from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_local_env(path: str | Path | None = None) -> Path | None:
    """Load simple KEY=VALUE entries from the project-local .env file.

    Existing process environment variables always win. This keeps credentials
    out of source/config files while making scheduled and manual runs behave
    consistently without requiring an additional dotenv dependency.
    """
    env_path = Path(path) if path else PROJECT_ROOT / ".env"
    if not env_path.exists():
        return None

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value
    return env_path


def load_settings(path: str | Path | None = None) -> dict[str, Any]:
    settings_path = Path(path) if path else PROJECT_ROOT / "config" / "settings.yaml"
    with settings_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def save_settings(settings: dict[str, Any], path: str | Path | None = None) -> Path:
    settings_path = Path(path) if path else PROJECT_ROOT / "config" / "settings.yaml"
    with settings_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(settings, file, allow_unicode=True, sort_keys=False)
    return settings_path


def project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
