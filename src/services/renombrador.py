"""Aplica la convención estándar de nombres de archivo definida en el documento funcional."""

from __future__ import annotations

import re
from pathlib import Path

from src.models.tercero import TerceroData

# Prefijos oficiales por fuente
_PREFIJOS: dict[str, str] = {
    "procuraduria": "PRO",
    "policia": "POL",
    "fiscal": "RFIS",
}


class Renombrador:
    """
    Convención:
      PRO  [Nombre completo] CC [Cédula].pdf
      POL  [Nombre completo] CC [Cédula].pdf
      RFIS [Nombre completo] CC [Cédula].pdf
    """

    def nombre_archivo(self, fuente: str, tercero: TerceroData) -> str:
        prefijo = _PREFIJOS.get(fuente.lower())
        if not prefijo:
            raise ValueError(f"Fuente desconocida: '{fuente}'. Válidas: {list(_PREFIJOS)}")
        nombre_sanitizado = self._sanitizar(tercero.nombre_completo)
        return (
            f"{prefijo} {nombre_sanitizado} {tercero.tipo_documento} "
            f"{tercero.numero_documento}.pdf"
        )

    def renombrar(self, archivo_actual: Path, fuente: str, tercero: TerceroData) -> Path:
        nuevo_nombre = self.nombre_archivo(fuente, tercero)
        destino = archivo_actual.parent / nuevo_nombre
        archivo_actual.rename(destino)
        return destino

    @staticmethod
    def _sanitizar(texto: str) -> str:
        """Elimina caracteres no permitidos en nombres de archivo Windows."""
        caracteres_invalidos = r'[<>:"/\\|?*]'
        return re.sub(caracteres_invalidos, "", texto).strip()
