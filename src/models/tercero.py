"""Modelos de datos del dominio."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EstadoFuente(str, Enum):
    EXITOSO = "EXITOSO"
    AUTOMATICO = "AUTOMATICO"
    EN_ESPERA = "EN_ESPERA"
    REINTENTANDO = "REINTENTANDO"
    FALLIDO = "FALLIDO"
    PENDIENTE = "PENDIENTE"
    NO_ENCONTRADO = "NO_ENCONTRADO"  # Número no registrado en la fuente


class EstadoEjecucion(str, Enum):
    EXITOSO = "EXITOSO"
    PARCIAL = "PARCIAL"
    FALLIDO = "FALLIDO"
    FALLIDO_TOTAL = "FALLIDO_TOTAL"
    ERROR_PDF = "ERROR_PDF"


@dataclass(frozen=True)
class TerceroData:
    """Value Object inmutable que representa a un tercero extraído del PDF."""

    nombre_completo: str
    numero_documento: str
    tipo_documento: str = "CC"

    @property
    def carpeta_nombre(self) -> str:
        return f"{self.nombre_completo} {self.tipo_documento} {self.numero_documento}"

    def __str__(self) -> str:
        return self.carpeta_nombre


@dataclass
class ResultadoFuente:
    """Resultado de la consulta en una fuente gubernamental."""

    fuente: str
    estado: EstadoFuente = EstadoFuente.PENDIENTE
    archivo_descargado: Optional[str] = None
    error_mensaje: Optional[str] = None
    intentos: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ResultadoTercero:
    """Resultado completo del procesamiento de un tercero (3 fuentes)."""

    tercero: TerceroData
    procuraduria: ResultadoFuente = field(
        default_factory=lambda: ResultadoFuente(fuente="Procuraduria")
    )
    policia: ResultadoFuente = field(
        default_factory=lambda: ResultadoFuente(fuente="Policia")
    )
    fiscal: ResultadoFuente = field(
        default_factory=lambda: ResultadoFuente(fuente="Fiscal")
    )
    timestamp_inicio: datetime = field(default_factory=datetime.now)
    timestamp_fin: Optional[datetime] = None

    @property
    def estado_general(self) -> EstadoEjecucion:
        fuentes = [self.procuraduria, self.policia, self.fiscal]
        exitosas = sum(
            1 for f in fuentes if f.estado in (EstadoFuente.EXITOSO, EstadoFuente.AUTOMATICO)
        )
        if exitosas == 3:
            return EstadoEjecucion.EXITOSO
        if exitosas == 0:
            return EstadoEjecucion.FALLIDO_TOTAL
        return EstadoEjecucion.PARCIAL

    def cerrar(self) -> None:
        self.timestamp_fin = datetime.now()
