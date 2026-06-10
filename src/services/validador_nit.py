"""Utilidades para NITs colombianos: dígito de verificación por fórmula DIAN."""

from __future__ import annotations

import re

# Pesos oficiales DIAN para cálculo del dígito de verificación (posición 1 a 10)
_PESOS = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43]


def limpiar_nit(nit_raw: str) -> str:
    """Elimina puntos, guiones, espacios y cualquier no-dígito.

    '900.943.048-4' → '9009430484'
    '900943048'     → '900943048'
    """
    return re.sub(r"[^\d]", "", str(nit_raw))


def digito_verificacion(nit_base: str) -> str:
    """Calcula el dígito de verificación de un NIT colombiano (algoritmo DIAN).

    Fórmula: suma(dígito_i × peso_i para i desde la derecha) % 11
    Si residuo ≤ 1 → DV = residuo; si residuo ≥ 2 → DV = 11 - residuo
    """
    digits = limpiar_nit(nit_base)
    if not digits:
        return "0"
    total = sum(int(d) * _PESOS[i] for i, d in enumerate(reversed(digits)))
    residuo = total % 11
    return str(residuo if residuo <= 1 else 11 - residuo)


def completar_nit(nit_raw: str) -> str:
    """Retorna el NIT completo con dígito de verificación (10 dígitos puros).

    Si ya tiene 10+ dígitos, lo retorna truncado a 10.
    Si tiene 9 dígitos, calcula y agrega el DV.
    """
    digits = limpiar_nit(nit_raw)
    if len(digits) >= 10:
        return digits[:10]
    if len(digits) == 9:
        return digits + digito_verificacion(digits)
    return digits
