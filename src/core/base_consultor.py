"""Strategy base abstracta para todos los consultores gubernamentales."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page

from src.models.tercero import ResultadoFuente, TerceroData

try:
    from playwright_stealth import stealth_sync as _stealth_sync
    _STEALTH_DISPONIBLE = True
except ImportError:
    _STEALTH_DISPONIBLE = False


class BaseConsultor(ABC):
    """
    Contrato común para Procuraduría, Policía y Contraloría.

    Subclases implementan _navegar(), _ingresar_datos(), _resolver_captcha()
    y _descargar_certificado(). El flujo orquestado está en consultar().
    """

    def __init__(self, browser: Browser, download_folder: Path, timeout_ms: int) -> None:
        self._browser = browser
        self._download_folder = download_folder
        self._timeout_ms = timeout_ms
        self._page: Page | None = None
        self._context: BrowserContext | None = None

    # --- Template Method principal ---

    def consultar(self, tercero: TerceroData) -> ResultadoFuente:
        resultado = ResultadoFuente(fuente=self.nombre_fuente)
        try:
            self._abrir_contexto()
            self._navegar()
            self._ingresar_datos(tercero)
            self._resolver_captcha(tercero)
            archivo = self._descargar_certificado(tercero)
            resultado.archivo_descargado = str(archivo)
            resultado.estado = self._estado_exitoso
        except Exception as exc:
            resultado.error_mensaje = str(exc)
            raise
        finally:
            self._cerrar_contexto()
        return resultado

    # --- Hooks abstractos que cada fuente implementa ---

    @property
    @abstractmethod
    def nombre_fuente(self) -> str:
        """Nombre legible de la fuente (p.ej. 'Procuraduria')."""

    @property
    def _estado_exitoso(self):
        from src.models.tercero import EstadoFuente
        return EstadoFuente.EXITOSO

    @abstractmethod
    def _navegar(self) -> None:
        """Abrir URL y esperar carga inicial."""

    @abstractmethod
    def _ingresar_datos(self, tercero: TerceroData) -> None:
        """Completar campos de tipo y número de documento."""

    @abstractmethod
    def _resolver_captcha(self, tercero: TerceroData) -> None:
        """Resolver o esperar resolución del CAPTCHA."""

    @abstractmethod
    def _descargar_certificado(self, tercero: TerceroData) -> Path:
        """Generar/descargar el PDF y retornar su ruta temporal."""

    # --- Utilidades compartidas ---

    def _abrir_contexto(self) -> None:
        self._context = self._browser.new_context(
            accept_downloads=True,
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
        self._page = self._context.new_page()

        # Scripts de stealth — ocultan señales de automatización
        self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['es-CO', 'es', 'en-US', 'en']});
            Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
            window.chrome = {runtime: {}};
            const origQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (p) =>
                p.name === 'notifications'
                    ? Promise.resolve({state: Notification.permission})
                    : origQuery(p);
        """)

        # playwright-stealth aplica ~20 parches adicionales si está instalado
        if _STEALTH_DISPONIBLE:
            _stealth_sync(self._page)

        self._page.set_default_timeout(self._timeout_ms)

    def _cerrar_contexto(self) -> None:
        if self._page:
            self._page.close()
        if self._context:
            self._context.close()
        self._page = None
        self._context = None

    def _esperar_descarga(self, accion_descarga) -> Path:
        """Ejecuta accion_descarga y espera que Playwright capture el archivo."""
        with self._page.expect_download() as download_info:
            accion_descarga()
        download = download_info.value
        destino = self._download_folder / download.suggested_filename
        download.save_as(destino)
        return destino
