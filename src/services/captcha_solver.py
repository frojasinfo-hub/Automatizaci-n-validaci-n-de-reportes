"""Resuelve CAPTCHAs de texto matemáticos y geográficos de la Procuraduría."""

from __future__ import annotations

import re
from typing import Optional

from src.infrastructure.logger_manager import LoggerManager

logger = LoggerManager()

# Capitales de departamentos colombianos para preguntas geográficas
_CAPITALES_COLOMBIA: dict[str, str] = {
    "amazonas": "leticia",
    "antioquia": "medellín",
    "arauca": "arauca",
    "atlántico": "barranquilla",
    "atlantico": "barranquilla",
    "bolívar": "cartagena",
    "bolivar": "cartagena",
    "boyacá": "tunja",
    "boyaca": "tunja",
    "caldas": "manizales",
    "caquetá": "florencia",
    "caqueta": "florencia",
    "casanare": "yopal",
    "cauca": "popayán",
    "cesar": "valledupar",
    "chocó": "quibdó",
    "choco": "quibdó",
    "córdoba": "montería",
    "cordoba": "montería",
    "cundinamarca": "bogotá",
    "guainía": "inírida",
    "guaviare": "san josé del guaviare",
    "huila": "neiva",
    "guajira": "riohacha",
    "la guajira": "riohacha",
    "magdalena": "santa marta",
    "meta": "villavicencio",
    "nariño": "pasto",
    "narino": "pasto",
    "norte de santander": "cúcuta",
    "putumayo": "mocoa",
    "quindío": "armenia",
    "quindio": "armenia",
    "risaralda": "pereira",
    "san andrés": "san andrés",
    "san andres": "san andrés",
    "santander": "bucaramanga",
    "sucre": "sincelejo",
    "tolima": "ibagué",
    "tolima": "ibagué",
    "valle del cauca": "cali",
    "vaupés": "mitú",
    "vaupes": "mitú",
    "vichada": "puerto carreño",
    "colombia": "bogotá",
}


class CaptchaSolver:
    """
    Resuelve preguntas CAPTCHA de texto que aparecen en la Procuraduría.
    Soporta: operaciones matemáticas y preguntas geográficas de Colombia.
    """

    def resolver(self, pregunta: str) -> Optional[str]:
        pregunta_limpia = pregunta.strip().lower()
        logger.debug(f"Resolviendo CAPTCHA: '{pregunta}'")

        respuesta = self._resolver_matematica(pregunta_limpia)
        if respuesta is not None:
            logger.debug(f"CAPTCHA matemático resuelto: {respuesta}")
            return str(respuesta)

        respuesta = self._resolver_geografica(pregunta_limpia)
        if respuesta is not None:
            logger.debug(f"CAPTCHA geográfico resuelto: {respuesta}")
            return respuesta

        logger.warning(f"No se pudo resolver el CAPTCHA automáticamente: '{pregunta}'")
        return None

    def _resolver_matematica(self, texto: str) -> Optional[int]:
        """Evalúa expresiones del tipo '¿Cuánto es 5 - 2?' o '¿Cuánto es 3 + 4?'."""
        patron = re.search(r"(\d+)\s*([\+\-\*x×])\s*(\d+)", texto)
        if not patron:
            return None
        a = int(patron.group(1))
        operador = patron.group(2)
        b = int(patron.group(3))

        operaciones = {
            "+": a + b,
            "-": a - b,
            "*": a * b,
            "x": a * b,
            "×": a * b,
        }
        return operaciones.get(operador)

    def _resolver_geografica(self, texto: str) -> Optional[str]:
        """Responde '¿Cuál es la capital de X?' usando el mapa de capitales."""
        for departamento, capital in _CAPITALES_COLOMBIA.items():
            if departamento in texto:
                return capital
        return None
