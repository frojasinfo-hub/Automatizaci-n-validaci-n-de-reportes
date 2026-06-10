"""Singleton para logging centralizado con canales separados por tipo."""

from __future__ import annotations

import csv
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class LoggerManager:
    _instance: Optional[LoggerManager] = None

    def __new__(cls) -> LoggerManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._ejecucion = cls._instance._build_fallback_logger()
            cls._instance._errores = cls._instance._ejecucion
            cls._instance._resumen_path = None
        return cls._instance

    @staticmethod
    def _build_fallback_logger() -> logging.Logger:
        """Logger de consola usado antes de que setup() sea invocado."""
        fallback = logging.getLogger("automatizacion")
        if not fallback.handlers:
            fallback.setLevel(logging.DEBUG)
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(
                logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
            )
            fallback.addHandler(handler)
        return fallback

    def setup(self, logs_folder: Path) -> None:
        if self._initialized:
            return
        logs_folder.mkdir(parents=True, exist_ok=True)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        self._ejecucion = self._build_logger(
            "ejecucion",
            logs_folder / "ejecucion.log",
            formatter,
        )
        self._errores = self._build_logger(
            "errores",
            logs_folder / "errores.log",
            formatter,
            level=logging.ERROR,
        )
        self._resumen_path = logs_folder / "resumen.csv"
        self._ensure_csv_header()
        self._initialized = True

    @staticmethod
    def _build_logger(
        name: str,
        file_path: Path,
        formatter: logging.Formatter,
        level: int = logging.DEBUG,
    ) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(level)

        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        return logger

    def _ensure_csv_header(self) -> None:
        if not self._resumen_path.exists():
            with self._resumen_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(
                    ["timestamp", "cedula", "nombre", "fuente", "estado", "intentos", "error"]
                )

    def info(self, message: str) -> None:
        self._ejecucion.info(message)

    def warning(self, message: str) -> None:
        self._ejecucion.warning(message)

    def error(self, message: str) -> None:
        self._ejecucion.error(message)
        self._errores.error(message)

    def debug(self, message: str) -> None:
        self._ejecucion.debug(message)

    def registrar_resumen(
        self,
        cedula: str,
        nombre: str,
        fuente: str,
        estado: str,
        intentos: int,
        error: str = "",
    ) -> None:
        if self._resumen_path is None:
            return
        with self._resumen_path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cedula, nombre, fuente, estado, intentos, error]
            )
