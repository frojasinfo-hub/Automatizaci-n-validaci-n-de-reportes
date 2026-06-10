"""Singleton para cargar y exponer la configuración centralizada."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


class ConfigManager:
    _instance: Optional[ConfigManager] = None
    _config: dict[str, Any] = {}

    def __new__(cls) -> ConfigManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, config_path: Path) -> None:
        if not config_path.exists():
            raise FileNotFoundError(f"Archivo de configuración no encontrado: {config_path}")
        with config_path.open(encoding="utf-8") as fh:
            self._config = json.load(fh)

    # --- accesores tipados ---

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    @property
    def input_folder(self) -> Path:
        return Path(self._config["input_folder"])

    @property
    def download_folder(self) -> Path:
        return Path(self._config["download_folder"])

    @property
    def output_folder(self) -> Path:
        return Path(self._config["output_folder"])

    @property
    def logs_folder(self) -> Path:
        return Path(self._config["logs_folder"])

    @property
    def reports_folder(self) -> Path:
        return Path(self._config["reports_folder"])

    @property
    def retry_attempts(self) -> int:
        return int(self._config.get("retry_attempts", 5))

    @property
    def retry_wait_sec(self) -> int:
        return int(self._config.get("retry_wait_sec", 30))

    @property
    def timeout_sec(self) -> int:
        return int(self._config.get("timeout_sec", 60))

    @property
    def headless(self) -> bool:
        return bool(self._config.get("headless", False))

    @property
    def notify_email(self) -> bool:
        return bool(self._config.get("notify_email", False))

    @property
    def notify_teams(self) -> bool:
        return bool(self._config.get("notify_teams", False))

    @property
    def email_config(self) -> dict[str, Any]:
        return self._config.get("email", {})

    @property
    def teams_config(self) -> dict[str, Any]:
        return self._config.get("teams", {})
