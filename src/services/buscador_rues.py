"""Busca el NIT completo (con dígito de verificación) en el portal RUES."""

from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Browser

from src.infrastructure.logger_manager import LoggerManager
from src.services.validador_nit import completar_nit, limpiar_nit

logger = LoggerManager()

_URL_RUES = "https://app-antiguoprd.rues.org.co/"
_DEBUG_DIR = Path(".")


class BuscadorRUES:
    """
    Consulta RUES para obtener el NIT completo con dígito de verificación.
    Si la búsqueda en RUES falla, retorna el NIT completado por fórmula DIAN.
    """

    def __init__(self, browser: Browser, timeout_ms: int = 30000) -> None:
        self._browser = browser
        self._timeout_ms = timeout_ms

    def obtener_nit_completo(self, nit_base: str) -> str:
        """Retorna el NIT completo (10 dígitos) para el NIT base dado.

        Intenta RUES primero; si falla, usa la fórmula DIAN como fallback.
        """
        nit_limpio = limpiar_nit(nit_base)

        # Si ya tiene 10 dígitos, no necesita búsqueda
        if len(nit_limpio) >= 10:
            logger.info(f"[RUES] NIT ya tiene dígito de verificación: {nit_limpio[:10]}")
            return nit_limpio[:10]

        # Intentar RUES
        nit_rues = self._buscar_en_rues(nit_limpio)
        if nit_rues and len(limpiar_nit(nit_rues)) == 10:
            resultado = limpiar_nit(nit_rues)
            logger.info(f"[RUES] NIT completo obtenido de RUES: {nit_limpio} → {resultado}")
            return resultado

        # Fallback: fórmula DIAN
        resultado = completar_nit(nit_limpio)
        logger.info(f"[RUES] NIT completado por fórmula DIAN: {nit_limpio} → {resultado}")
        return resultado

    def _buscar_en_rues(self, nit_base: str) -> str | None:
        """Navega a RUES y extrae el NIT completo. Retorna None si falla."""
        context = None
        page = None
        try:
            context = self._browser.new_context(
                accept_downloads=False,
                ignore_https_errors=True,
                viewport={"width": 1280, "height": 900},
                locale="es-CO",
                timezone_id="America/Bogota",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.set_default_timeout(self._timeout_ms)
            return self._ejecutar_busqueda(page, nit_base)
        except Exception as exc:
            logger.warning(f"[RUES] Error durante búsqueda de NIT {nit_base}: {exc}")
            return None
        finally:
            if page:
                try:
                    page.screenshot(path=str(_DEBUG_DIR / "debug_rues_final.png"))
                except Exception:
                    pass
                page.close()
            if context:
                context.close()

    def _cerrar_aviso_inicial(self, page) -> None:
        """Cierra el modal 'Aviso Importante' que aparece al entrar a RUES."""
        botones_cierre = [
            "button:has-text('Cerrar')",
            "button:has-text('cerrar')",
            "button:has-text('Aceptar')",
            "button:has-text('Continuar')",
            "button:has-text('Entendido')",
            "button:has-text('OK')",
            "[aria-label='Close']",
            "[aria-label='Cerrar']",
            "button.close",
            "button.btn-close",
            ".modal-footer button",
            ".modal button",
        ]
        for sel in botones_cierre:
            try:
                btn = page.locator(sel).first
                # Timeout corto: si el modal no está, saltar rápido al siguiente selector
                if btn.is_visible(timeout=500):
                    btn.click()
                    logger.info(f"[RUES] Aviso inicial cerrado ('{sel}')")
                    page.wait_for_timeout(800)
                    return
            except Exception:
                continue
        logger.info("[RUES] No se detectó aviso inicial o ya estaba cerrado.")

    def _ejecutar_busqueda(self, page, nit_base: str) -> str | None:
        logger.info(f"[RUES] Navegando a {_URL_RUES} para NIT {nit_base}...")
        page.goto(_URL_RUES, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        # Cerrar modal de aviso importante antes de interactuar
        self._cerrar_aviso_inicial(page)
        page.screenshot(path=str(_DEBUG_DIR / "debug_rues_inicio.png"))
        logger.info(f"[RUES] URL inicial: {page.url}")

        # --- Intento 1: buscar campo por NIT directamente ---
        ingresado = self._intentar_llenar_campo(
            page,
            selectores=[
                "input[placeholder*='NIT' i]",
                "input[name*='nit' i]",
                "input[id*='nit' i]",
                "input[placeholder*='número' i]",
                "input[placeholder*='identificacion' i]",
                "input[placeholder*='identificación' i]",
            ],
            valor=nit_base,
        )

        # --- Intento 2: si no encontró campo específico, usar el primer input de texto ---
        if not ingresado:
            ingresado = self._intentar_llenar_campo(
                page,
                selectores=["input[type='text']:visible", "input:not([type]):visible"],
                valor=nit_base,
            )

        if not ingresado:
            logger.warning("[RUES] No se encontró campo de búsqueda.")
            return None

        page.screenshot(path=str(_DEBUG_DIR / "debug_rues_campo_llenado.png"))

        # --- Clic en botón de búsqueda ---
        clicado = self._intentar_clic(
            page,
            selectores=[
                "button:has-text('Consultar')",
                "button:has-text('Buscar')",
                "input[value='Consultar']",
                "input[value='Buscar']",
                "button[type='submit']",
                "input[type='submit']",
            ],
        )
        if not clicado:
            # Intentar Enter en el campo
            try:
                page.keyboard.press("Enter")
            except Exception:
                pass

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(2000)
        page.screenshot(path=str(_DEBUG_DIR / "debug_rues_resultado.png"))
        logger.info(f"[RUES] URL tras búsqueda: {page.url}")

        return self._extraer_nit_de_pagina(page, nit_base)

    def _intentar_llenar_campo(
        self, page, selectores: list[str], valor: str
    ) -> bool:
        for sel in selectores:
            try:
                campo = page.locator(sel).first
                if campo.is_visible():
                    campo.clear()
                    campo.fill(valor)
                    logger.info(f"[RUES] Campo encontrado con selector '{sel}'")
                    return True
            except Exception:
                continue
        return False

    def _intentar_clic(self, page, selectores: list[str]) -> bool:
        for sel in selectores:
            try:
                btn = page.locator(sel).first
                if btn.is_visible():
                    btn.click()
                    logger.info(f"[RUES] Botón encontrado con selector '{sel}'")
                    return True
            except Exception:
                continue
        return False

    def _extraer_nit_de_pagina(self, page, nit_base: str) -> str | None:
        """Busca en el HTML de resultados un NIT que empiece por nit_base."""
        contenido = page.content()

        # Patrón 1: NIT con formato "XXX.XXX.XXX-D" o "XXXXXXXXX-D"
        # Buscar la secuencia base de dígitos seguida de guión y un dígito
        base_sin_puntos = limpiar_nit(nit_base)

        # Patrón flexible: los dígitos del base pueden aparecer con puntos entre ellos
        segmentos = [base_sin_puntos[:3], base_sin_puntos[3:6], base_sin_puntos[6:]]
        patron_puntos = (
            rf"{re.escape(segmentos[0])}"
            rf"[\.\s]?"
            rf"{re.escape(segmentos[1])}"
            rf"[\.\s]?"
            rf"{re.escape(segmentos[2])}"
            rf"[\s\-–](\d)"
        )
        m = re.search(patron_puntos, contenido)
        if m:
            dv = m.group(1)
            logger.info(f"[RUES] NIT con DV encontrado (patrón con puntos): DV={dv}")
            return base_sin_puntos + dv

        # Patrón 2: los 9 dígitos del base seguidos inmediatamente por otro dígito
        patron_directo = re.search(
            rf"(?<!\d){re.escape(base_sin_puntos)}(\d)(?!\d)",
            re.sub(r"[^\d\n]", "\n", contenido),
        )
        if patron_directo:
            dv = patron_directo.group(1)
            logger.info(f"[RUES] NIT con DV encontrado (patrón directo): DV={dv}")
            return base_sin_puntos + dv

        logger.warning(
            f"[RUES] No se encontró NIT {nit_base} en resultados. "
            f"Revise debug_rues_resultado.png"
        )
        return None
