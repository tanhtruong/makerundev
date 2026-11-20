import os
from pathlib import Path

PREFIXES = ("MAKERUNDEV_", "PACELAB_")
DATABASE = "makerundev.db"
LEGACY_DATABASE = "pacelab.db"


def env(name: str, default: str) -> str:
    for prefix in PREFIXES:
        value = os.environ.get(prefix + name)
        if value is not None:
            return value
    return default


def data_dir() -> Path:
    return Path(env("DATA_DIR", "data"))


def database_path(data_dir: Path) -> Path:
    current = data_dir / DATABASE
    legacy = data_dir / LEGACY_DATABASE
    if legacy.exists() and not current.exists():
        return legacy
    return current
