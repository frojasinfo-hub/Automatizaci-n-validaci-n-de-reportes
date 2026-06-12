"""Consultor para la Policía Nacional — antecedentes judiciales."""

from __future__ import annotations

import time
from pathlib import Path

from src.core.base_consultor import BaseConsultor
from src.infrastructure.logger_manager import LoggerManager
from src.models.tercero import EstadoFuente, ResultadoFuente, TerceroData
from src.services.notificador import Notificador

logger = LoggerManager()
notificador = Notificador()

_SIGNAL_FILE = Path(__file__).parent.parent.parent / "captcha_signal.txt"


def _esperar_confirmacion_captcha(timeout: int = 300) -> None:
    _SIGNAL_FILE.write_text("")
    start = time.time()
    while time.time() - start < timeout:
        if _SIGNAL_FILE.read_text().strip() == "CONFIRMED":
            _SIGNAL_FILE.write_text("")
            return
        time.sleep(0.5)
    raise TimeoutError("CAPTCHA no confirmado en 5 minutos")

_URL_TERMINOS = "https://antecedentes.policia.gov.co:7005/WebJudicial/index.xhtml"
_URL_RESULTADO = "formAntecedentes.xhtml"

_HALL_POL_LIMPIO = "NO TIENE ASUNTOS PENDIENTES CON LAS AUTORIDADES JUDICIALES"
_HALL_POL_LIBRE  = "ACTUALMENTE NO ES REQUERIDO POR AUTORIDAD JUDICIAL"


def _extraer_hallazgo_policia(pdf_path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            texto = " ".join(p.extract_text() or "" for p in pdf.pages).upper()
        if "NO TIENE ASUNTOS PENDIENTES" in texto:
            return _HALL_POL_LIMPIO
        if "NO ES REQUERIDO" in texto:
            return _HALL_POL_LIBRE
    except Exception:
        pass
    return ""

_SEL_TIPO_DOC   = "select#formAntecedentes\\:selTipoDocumento, select[id*='TipoDocumento'], select[id*='tipoDocumento']"
_SEL_NUM_DOC    = "input#formAntecedentes\\:txtNroDocumento, input[id*='NroDocumento'], input[id*='cedula']"
_SEL_BTN_CONSULTAR = "button#formAntecedentes\\:btnConsultar, button:has-text('Consultar'), input[value*='Consultar' i]"
_SEL_RECAPTCHA  = "iframe[src*='recaptcha']"
_VAL_CC         = "CC"


class ConsultorPolicia(BaseConsultor):
    """
    Flujo Policía Nacional:
      1. Navegar → aceptar términos (radio Acepto + botón Enviar)
      2. Esperar formulario antecedentes.xhtml
      3. Seleccionar tipo CC, ingresar número
      4. Operador resuelve reCAPTCHA → ENTER
      5. Clic Consultar → esperar formAntecedentes.xhtml con resultado
      6. Generar PDF via page.pdf()
    """

    @property
    def nombre_fuente(self) -> str:
        return "Policia"

    def consultar(self, tercero: TerceroData) -> ResultadoFuente:
        resultado = super().consultar(tercero)
        if resultado.archivo_descargado:
            resultado.hallazgo = _extraer_hallazgo_policia(
                Path(resultado.archivo_descargado)
            )
        return resultado

    def _navegar(self) -> None:
        logger.info(f"[Policia] Navegando a términos: {_URL_TERMINOS}")
        self._page.goto(_URL_TERMINOS, wait_until="networkidle")
        self._page.screenshot(path="debug_policia.png")
        self._aceptar_terminos()
        # Esperar que cargue el formulario de datos
        self._page.wait_for_load_state("networkidle")
        self._page.wait_for_timeout(2000)
        logger.info(f"[Policia] URL tras términos: {self._page.url}")
        # Esperar cualquier select visible en la página de formulario
        self._page.wait_for_selector("select", timeout=60000)
        logger.info("[Policia] Formulario de datos cargado.")

    def _aceptar_terminos(self) -> None:
        logger.info("[Policia] Aceptando términos...")
        # El radio "Acepto" tiene name="aceptaOption" y es el primero
        self._page.locator("input[name='aceptaOption']").first.click()
        self._page.wait_for_timeout(500)
        # Botón Enviar
        self._page.locator("#continuarBtn").click()
        logger.info("[Policia] Términos aceptados — esperando formulario.")
        self._page.wait_for_load_state("networkidle")

    def _ingresar_datos(self, tercero: TerceroData) -> None:
        logger.info(f"[Policia] Ingresando CC {tercero.numero_documento}")
        # Loguear todos los selects disponibles para debug
        selects = self._page.eval_on_selector_all(
            "select", "els => els.map(e => e.id + '|' + e.name)"
        )
        logger.info(f"[Policia] Selects en página: {selects}")
        inputs = self._page.eval_on_selector_all(
            "input[type='text']", "els => els.map(e => e.id + '|' + e.name)"
        )
        logger.info(f"[Policia] Inputs texto en página: {inputs}")

        self._page.locator("select#cedulaTipo").select_option(value="cc")
        self._page.locator("input#cedulaInput").fill(tercero.numero_documento)

    def _resolver_captcha(self, tercero: TerceroData) -> None:
        try:
            self._page.wait_for_selector(_SEL_RECAPTCHA, timeout=5000)
            captcha_presente = True
        except Exception:
            captcha_presente = False

        if captcha_presente:
            notificador.notificar_captcha_manual(self.nombre_fuente, str(tercero))
            print(
                f"\n{'='*60}\n"
                f"  [POLICIA] Resuelva el reCAPTCHA en el navegador\n"
                f"  Tercero: {tercero}\n"
                f"\n"
                f"  IMPORTANTE: Resuelva el CAPTCHA Y espere que aparezca\n"
                f"  el botón CONSULTAR activo antes de presionar ENTER\n"
                f"{'='*60}"
            )
            _esperar_confirmacion_captcha()
            logger.info("[Policia] Operador confirmó reCAPTCHA.")

        # Clic en Consultar
        self._page.locator(_SEL_BTN_CONSULTAR).click()
        logger.info("[Policia] Clic en Consultar — esperando resultado...")
        self._page.wait_for_load_state("networkidle", timeout=self._timeout_ms)
        logger.info(f"[Policia] URL tras consultar: {self._page.url}")

    def _descargar_certificado(self, tercero: TerceroData) -> Path:
        self._page.wait_for_load_state("networkidle", timeout=self._timeout_ms)
        self._page.wait_for_timeout(3000)

        url_actual = self._page.url
        logger.info(f"[Policia] URL al generar PDF: {url_actual}")

        # Verificar que estamos en la página de resultado
        if _URL_RESULTADO not in url_actual:
            self._page.screenshot(path="debug_policia_resultado.png")
            raise RuntimeError(
                f"[Policia] Se esperaba {_URL_RESULTADO} pero URL es: {url_actual}"
            )

        self._page.screenshot(path="debug_policia_resultado.png")
        nombre_archivo = f"POL_temp_{tercero.numero_documento}.pdf"
        destino = self._download_folder / nombre_archivo
        self._page.pdf(path=str(destino), format="A4", print_background=True)

        if not destino.exists():
            raise RuntimeError("[Policia] El PDF no fue generado correctamente.")

        logger.info(f"[Policia] PDF generado: {destino.name}")
        return destino
