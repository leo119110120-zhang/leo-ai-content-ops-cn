from pathlib import Path

import yaml


class ConfigError(ValueError):
    """Raised when a content-operations config is missing or malformed."""


def load_yaml(path: Path, required: set[str] | None = None) -> dict:
    if not path.exists():
        raise ConfigError(f"config does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"config must be a mapping: {path}")
    missing = sorted((required or set()) - data.keys())
    if missing:
        raise ConfigError(f"missing required keys: {', '.join(missing)}")
    return data


def save_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
