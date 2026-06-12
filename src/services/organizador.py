"""Repository para operaciones de filesystem: carpetas y movimiento de archivos."""

from __future__ import annotations

import shutil
from pathlib import Path

from src.infrastructure.logger_manager import LoggerManager
from src.models.tercero import TerceroData

logger = LoggerManager()

class Organizador:
    """Crea la carpeta del tercero y mueve los PDFs renombrados a su destino final."""

    def __init__(self, output_folder: Path) -> None:
        self._output_folder = output_folder

    def carpeta_tercero(self, tercero: TerceroData) -> Path:
        return self._output_folder / tercero.carpeta_nombre

    def crear_carpeta(self, tercero: TerceroData) -> Path:
        carpeta = self.carpeta_tercero(tercero)
        carpeta.mkdir(parents=True, exist_ok=True)
        logger.info(f"Carpeta lista: {carpeta}")
        return carpeta

    def mover_archivo(self, origen: Path, tercero: TerceroData) -> Path:
        carpeta = self.crear_carpeta(tercero)
        destino = carpeta / origen.name
        shutil.move(str(origen), str(destino))
        logger.info(f"Archivo movido: {origen.name} -> {carpeta.name}/")
        return destino

    def mover_todos(self, archivos: list[Path], tercero: TerceroData) -> list[Path]:
        return [self.mover_archivo(archivo, tercero) for archivo in archivos]
