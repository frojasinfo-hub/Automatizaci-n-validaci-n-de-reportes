"""Chain of Responsibility para reintentos con backoff exponencial acotado."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

from src.infrastructure.logger_manager import LoggerManager
from src.models.tercero import EstadoFuente, ResultadoFuente

T = TypeVar("T")

logger = LoggerManager()


class RetryHandler:
    """
    Ejecuta una función hasta max_attempts veces.
    Espera wait_sec entre intentos (sin crecer exponencialmente en V1.0,
    el documento especifica tiempo variable ajustado en pruebas).
    """

    def __init__(self, max_attempts: int = 5, wait_sec: int = 30) -> None:
        self._max_attempts = max_attempts
        self._wait_sec = wait_sec

    def ejecutar(
        self,
        operacion: Callable[[], ResultadoFuente],
        resultado: ResultadoFuente,
    ) -> ResultadoFuente:
        for intento in range(1, self._max_attempts + 1):
            resultado.intentos = intento
            try:
                logger.info(f"[{resultado.fuente}] Intento {intento}/{self._max_attempts}")
                resultado = operacion()
                resultado.intentos = intento
                return resultado
            except Exception as exc:
                resultado.error_mensaje = str(exc)
                logger.warning(
                    f"[{resultado.fuente}] Intento {intento} fallido: {exc}"
                )
                if intento < self._max_attempts:
                    resultado.estado = EstadoFuente.REINTENTANDO
                    logger.info(
                        f"[{resultado.fuente}] Esperando {self._wait_sec}s antes del siguiente intento..."
                    )
                    time.sleep(self._wait_sec)

        resultado.estado = EstadoFuente.FALLIDO
        logger.error(
            f"[{resultado.fuente}] Agotados {self._max_attempts} intentos. Marcada como FALLIDA."
        )
        return resultado
