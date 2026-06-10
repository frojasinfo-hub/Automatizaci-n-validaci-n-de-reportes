"""Consultor para Contraloría General — Responsabilidad Fiscal."""

from __future__ import annotations

from pathlib import Path

from src.core.base_consultor import BaseConsultor
from src.infrastructure.logger_manager import LoggerManager
from src.models.tercero import EstadoFuente, ResultadoFuente, TerceroData
from src.services.notificador import Notificador

logger = LoggerManager()
notificador = Notificador()

_URL_NATURAL = (
    "https://cfiscal.contraloria.gov.co/Certificados/CertificadoPersonaNatural.aspx"
)
_URL_JURIDICA = (
    "https://cfiscal.contraloria.gov.co/Certificados/CertificadoPersonaJuridica.aspx"
)

_SEL_BTN_BUSCAR = "input[value='Buscar'], button:has-text('Buscar')"

# Textos que indican NIT inválido o sin registros en Contraloría Fiscal
_TEXTOS_ERROR_FISCAL = [
    "BOLETIN_RESPONSABLES_FISCALES",   # email específico del error de NIT
    "NIT DE EXACTAMENTE 10",            # validación de formato de 10 dígitos
    "SOLICÍTELO AL CORREO",             # parte del mensaje de error NIT
]


class _FiscalNoEncontradoError(Exception):
    """El NIT ingresado no es válido o no tiene registros en Contraloría Fiscal."""


class ConsultorFiscal(BaseConsultor):
    _tipo_doc: str = "CC"

    def consultar(self, tercero: TerceroData):
        self._tipo_doc = tercero.tipo_documento
        try:
            return super().consultar(tercero)
        except _FiscalNoEncontradoError as exc:
            # Resultado definitivo — no se reintenta, continúa con otras fuentes
            resultado = ResultadoFuente(fuente=self.nombre_fuente)
            resultado.estado = EstadoFuente.NO_ENCONTRADO
            resultado.error_mensaje = str(exc)
            logger.warning(f"[Fiscal] {tercero} — {exc}")
            return resultado

    @property
    def nombre_fuente(self) -> str:
        return "Fiscal"

    def _navegar(self) -> None:
        url = _URL_JURIDICA if self._tipo_doc == "NIT" else _URL_NATURAL
        logger.info(f"[Fiscal] Navegando directamente a: {url}")
        self._page.goto(url, wait_until="networkidle")
        self._page.wait_for_load_state("domcontentloaded")
        self._page.wait_for_timeout(3000)

        # Cerrar modal informativo de NIT si aparece (solo Persona Jurídica)
        if self._tipo_doc == "NIT":
            try:
                btn_entendido = self._page.locator("button:has-text('Entendido')")
                btn_entendido.wait_for(state="visible", timeout=5000)
                btn_entendido.click()
                logger.info("[Fiscal] Modal NIT cerrado.")
                self._page.wait_for_timeout(1000)
            except Exception:
                logger.info("[Fiscal] No apareció modal NIT — continuando.")

        self._page.screenshot(path="debug_fiscal.png")
        logger.info(f"[Fiscal] URL actual: {self._page.url}")

    def _ingresar_datos(self, tercero: TerceroData) -> None:
        logger.info(
            f"[Fiscal] Ingresando datos: {tercero.tipo_documento} {tercero.numero_documento}"
        )
        if self._tipo_doc != "NIT":
            try:
                self._page.locator("select#ddlTipoDocumento").select_option(
                    value=tercero.tipo_documento
                )
            except Exception:
                logger.warning("[Fiscal] Select tipo doc no encontrado — omitiendo.")

        self._page.locator("input#txtNumeroDocumento").fill(tercero.numero_documento)

    def _resolver_captcha(self, tercero: TerceroData) -> None:
        notificador.notificar_captcha_manual(self.nombre_fuente, str(tercero))
        print(
            f"\n{'='*60}\n"
            f"  [FISCAL] Resuelva el reCAPTCHA en el navegador\n"
            f"  Tercero: {tercero}\n"
            f"  Luego presione ENTER para continuar...\n"
            f"{'='*60}"
        )
        input()
        logger.info("[Fiscal] Operador confirmó resolución de reCAPTCHA.")

    def _verificar_no_encontrado(self, tercero: TerceroData) -> None:
        """Lanza _FiscalNoEncontradoError si la página muestra error de NIT inválido."""
        try:
            contenido = self._page.content().upper()
            for texto in _TEXTOS_ERROR_FISCAL:
                if texto in contenido:
                    raise _FiscalNoEncontradoError(
                        f"NIT {tercero.numero_documento} no válido o sin registros "
                        f"en Contraloría Fiscal (indicador: '{texto}')"
                    )
        except _FiscalNoEncontradoError:
            raise
        except Exception:
            pass

    def _descargar_certificado(self, tercero: TerceroData) -> Path:
        logger.info("[Fiscal] Haciendo clic en Buscar y esperando descarga...")
        try:
            archivo = self._esperar_descarga(
                lambda: self._page.locator(_SEL_BTN_BUSCAR).click()
            )
        except Exception:
            # Verificar DESPUÉS del intento fallido — la página muestra el error
            # de NIT inválido solo tras ejecutar la búsqueda, no en la carga inicial.
            self._verificar_no_encontrado(tercero)
            raise  # Error real → re-raise para que el retry handler lo maneje

        logger.info(f"[Fiscal] Certificado descargado: {archivo.name}")
        return archivo
