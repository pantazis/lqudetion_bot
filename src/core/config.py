"""Configuration loading with ${ENV_VAR} substitution."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _substitute_env(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return os.getenv(var_name, "")

    return ENV_VAR_PATTERN.sub(replace, value)


def _walk_and_substitute(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _walk_and_substitute(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_and_substitute(v) for v in obj]
    if isinstance(obj, str):
        return _substitute_env(obj)
    return obj


def load_config(path: str | Path) -> dict[str, Any]:
    raw_text = Path(path).read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw_text) or {}
    return _walk_and_substitute(parsed)
