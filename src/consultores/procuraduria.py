"""Consultor para la Procuraduría General de la Nación."""

from __future__ import annotations

import time
from pathlib import Path

from src.core.base_consultor import BaseConsultor
from src.infrastructure.config_manager import ConfigManager
from src.infrastructure.logger_manager import LoggerManager
from src.models.tercero import EstadoFuente, ResultadoFuente, TerceroData

logger = LoggerManager()

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

_URL = "https://apps.procuraduria.gov.co/webcert/inicio.aspx?tpo=2"
_TIPO_DOC_VALUE = {"CC": "1", "NIT": "2"}
_TEXTO_NO_ENCONTRADO = "NO SE ENCUENTRA REGISTRADO"
_SELECTORES_DESCARGA = (
    "#btnDescargar, input[name='btnDescargar'], "
    "input[id='btnDescargar'], input[type='image'][name*='Descargar']"
)

_HALL_PRO_LIMPIO = "NO REGISTRA SANCIONES NI INHABILIDADES VIGENTES"
_HALL_PRO_CON    = "REGISTRA SANCIONES O INHABILIDADES VIGENTES"
_HALL_PRO_NO_REG = "NO SE ENCUENTRA REGISTRADO EN EL SISTEMA"


def _extraer_hallazgo_procuraduria(pdf_path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            texto = " ".join(p.extract_text() or "" for p in pdf.pages).upper()
        if "NO REGISTRA SANCIONES" in texto:
            return _HALL_PRO_LIMPIO
        if "REGISTRA SANCIONES" in texto:
            return _HALL_PRO_CON
    except Exception:
        pass
    return _HALL_PRO_NO_REG

class _RegistroNoEncontradoError(Exception):
    """El número de identificación no figura en la base de datos de Procuraduría."""


class ConsultorProcuraduria(BaseConsultor):
    """
    Flujo Procuraduría:
      1. Navegar a WEBCERT/Certificado.aspx
      2. select#ddlTipoID + input#txtNumID
      3. Operador resuelve CAPTCHA en el navegador y presiona ENTER
      4. Clic input[value='Generar']
      5. Clic botón Descargar en el iframe de webcert → expect_download
    """

    @property
    def nombre_fuente(self) -> str:
        return "Procuraduria"

    @property
    def _estado_exitoso(self) -> EstadoFuente:
        return EstadoFuente.AUTOMATICO

    def consultar(self, tercero: TerceroData) -> ResultadoFuente:
        config = ConfigManager()
        carpeta = config.output_folder / tercero.carpeta_nombre
        existentes = list(carpeta.glob(f"PRO *{tercero.numero_documento}*.pdf"))
        if existentes:
            resultado = ResultadoFuente(fuente=self.nombre_fuente)
            resultado.estado = self._estado_exitoso
            resultado.archivo_descargado = str(existentes[0])
            resultado.error_mensaje = "Archivo ya existente"
            resultado.hallazgo = _extraer_hallazgo_procuraduria(existentes[0])
            logger.info(f"[Procuraduria] {tercero} — archivo ya existe, omitiendo consulta.")
            return resultado

        try:
            resultado = super().consultar(tercero)
            if resultado.archivo_descargado:
                resultado.hallazgo = _extraer_hallazgo_procuraduria(
                    Path(resultado.archivo_descargado)
                )
            return resultado
        except _RegistroNoEncontradoError as exc:
            resultado = ResultadoFuente(fuente=self.nombre_fuente)
            resultado.estado = EstadoFuente.NO_ENCONTRADO
            resultado.error_mensaje = str(exc)
            resultado.hallazgo = _HALL_PRO_NO_REG
            logger.warning(f"[Procuraduria] {tercero} — {exc}")
            return resultado

    def _navegar(self) -> None:
        logger.info(f"[Procuraduria] Navegando a: {_URL}")
        self._page.goto(_URL, wait_until="networkidle")
        self._page.wait_for_timeout(3000)
        url_actual = self._page.url
        logger.info(f"[Procuraduria] URL tras navegar: {url_actual}")

    def _ingresar_datos(self, tercero: TerceroData) -> None:
        logger.info(
            f"[Procuraduria] Ingresando datos: "
            f"{tercero.tipo_documento} {tercero.numero_documento}"
        )
        valor = _TIPO_DOC_VALUE.get(tercero.tipo_documento, "1")
        self._page.locator("select#ddlTipoID").select_option(value=valor)
        self._page.wait_for_timeout(500)
        self._page.locator("input#txtNumID").fill(tercero.numero_documento)

    def _resolver_captcha(self, tercero: TerceroData) -> None:
        sep = "=" * 60
        print(
            f"\n{sep}\n"
            f"[PROCURADURIA] Resuelva el CAPTCHA en el navegador\n"
            f"Tercero: {tercero.nombre_completo} "
            f"{tercero.tipo_documento} {tercero.numero_documento}\n"
            f"\n"
            f"IMPORTANTE: Escriba la respuesta del CAPTCHA en el campo\n"
            f"del navegador y presione ENTER aquí cuando esté listo\n"
            f"{sep}"
        )
        _esperar_confirmacion_captcha()
        logger.info("[Procuraduria] Operador confirmó resolución de CAPTCHA.")

    def _webcert_frame(self):
        """Retorna el frame del iframe de webcert, o None si no se encuentra."""
        for frame in self._page.frames:
            if "webcert" in frame.url.lower() or "apps.procuraduria" in frame.url.lower():
                return frame
        return None

    def _verificar_no_encontrado(self, tercero: TerceroData) -> None:
        frame = self._webcert_frame()
        targets = [frame, self._page] if frame else [self._page]
        for target in targets:
            try:
                texto = target.locator("body").inner_text(timeout=3000)
                if _TEXTO_NO_ENCONTRADO in texto.upper():
                    raise _RegistroNoEncontradoError(
                        f"Número {tercero.numero_documento} no encontrado en Procuraduría"
                    )
            except _RegistroNoEncontradoError:
                raise
            except Exception:
                pass

    def _descargar_certificado(self, tercero: TerceroData) -> Path:
        nombre = f"PROC_temp_{tercero.numero_documento}.pdf"
        destino = self._download_folder / nombre

        self._page.locator(
            "input[value='Generar'], button:has-text('Generar')"
        ).click()
        logger.info("[Procuraduria] Clic en Generar — esperando resultado...")

        self._verificar_no_encontrado(tercero)
        try:
            self._page.wait_for_url("**/verpdf.aspx**", timeout=30000)
        except Exception:
            self._page.screenshot(path="debug_procuraduria_resultado.png")
            self._verificar_no_encontrado(tercero)
            raise RuntimeError(
                "[Procuraduria] No navegó a verpdf.aspx en 30s. "
                "Revise debug_procuraduria_resultado.png"
            )

        self._verificar_no_encontrado(tercero)
        logger.info("[Procuraduria] En verpdf.aspx — buscando botón Descargar...")
        frame = self._webcert_frame()
        target = frame if frame else self._page
        boton = target.locator(_SELECTORES_DESCARGA)
        boton.first.wait_for(state="visible", timeout=15000)
        logger.info("[Procuraduria] Botón Descargar visible — descargando...")
        with self._page.expect_download(timeout=30000) as dl_info:
            boton.first.click()
        download = dl_info.value
        download.save_as(destino)
        logger.info(f"[Procuraduria] Archivo descargado: {destino.name}")

        if not destino.exists() or destino.stat().st_size < 1000:
            raise RuntimeError("[Procuraduria] PDF no generado o vacío.")
        return destino
