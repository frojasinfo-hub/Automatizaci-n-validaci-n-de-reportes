"""Orquestador principal — punto de entrada del sistema."""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.consultores.fiscal import ConsultorFiscal
from src.consultores.policia import ConsultorPolicia
from src.consultores.procuraduria import ConsultorProcuraduria
from src.core.retry_handler import RetryHandler
from src.infrastructure.config_manager import ConfigManager
from src.infrastructure.logger_manager import LoggerManager
from src.models.tercero import EstadoFuente, ResultadoFuente, ResultadoTercero, TerceroData
from src.services.buscador_rues import BuscadorRUES
from src.services.extractor_pdf import ExtractorPDF
from src.services.organizador import Organizador
from src.services.renombrador import Renombrador
from src.services.reporte_excel import ReporteExcel
from src.services.validador_nit import limpiar_nit

config = ConfigManager()
logger = LoggerManager()

# Estados que se consideran "descarga exitosa"
_ESTADOS_OK = {EstadoFuente.EXITOSO, EstadoFuente.AUTOMATICO}
_ESTADOS_OK_STR = {"EXITOSO", "AUTOMATICO"}

# Estados terminales: exitosos + "no encontrado" (no tiene sentido reintentar)
_ESTADOS_TERMINADOS = {
    EstadoFuente.EXITOSO,
    EstadoFuente.AUTOMATICO,
    EstadoFuente.NO_ENCONTRADO,
}

# Reintentos adicionales al finalizar el loop principal (punto 5)
_MAX_PASADAS_EXTRA = 4


def _inicializar() -> None:
    config_path = ROOT / "config" / "config.json"
    config.load(config_path)
    config.logs_folder.mkdir(parents=True, exist_ok=True)
    config.download_folder.mkdir(parents=True, exist_ok=True)
    config.output_folder.mkdir(parents=True, exist_ok=True)
    config.reports_folder.mkdir(parents=True, exist_ok=True)
    logger.setup(config.logs_folder)


def _cargar_pdfs() -> list[Path]:
    pdfs = sorted(config.input_folder.glob("*.pdf"))
    if not pdfs:
        logger.warning(f"No se encontraron PDFs en: {config.input_folder}")
    return pdfs


def _es_completo(resultado: ResultadoTercero) -> bool:
    """True si todas las fuentes requeridas terminaron exitosamente.

    Para CC: NO_ENCONTRADO cuenta como terminal (sin antecedentes = OK).
    Para NIT: solo EXITOSO/AUTOMATICO cuenta — se exige descarga real del certificado.
    """
    es_nit = resultado.tercero.tipo_documento == "NIT"
    if es_nit:
        # Para NIT: solo cuenta si se descargó el PDF
        pro_ok = resultado.procuraduria.estado in _ESTADOS_TERMINADOS
        fis_ok = resultado.fiscal.estado in _ESTADOS_OK
        return pro_ok and fis_ok
    # Para CC: NO_ENCONTRADO es terminal válido
    pro_ok = resultado.procuraduria.estado in _ESTADOS_TERMINADOS
    fis_ok = resultado.fiscal.estado in _ESTADOS_TERMINADOS
    pol_ok = resultado.policia.estado in _ESTADOS_TERMINADOS
    return pro_ok and fis_ok and pol_ok


def _estado_str_a_fuente(estado_str: str) -> EstadoFuente:
    """Convierte el texto del Excel al enum EstadoFuente."""
    if estado_str in _ESTADOS_OK_STR:
        return EstadoFuente.EXITOSO
    if estado_str == "NO_ENCONTRADO":
        return EstadoFuente.NO_ENCONTRADO
    if estado_str in ("NO APLICA", "PENDIENTE"):
        return EstadoFuente.PENDIENTE
    return EstadoFuente.FALLIDO


def _reconstruir_resultado_previo(
    tercero: TerceroData, previo: dict
) -> ResultadoTercero:
    """Crea un ResultadoTercero con los estados guardados en el Excel previo."""
    resultado = ResultadoTercero(tercero=tercero)
    resultado.procuraduria = ResultadoFuente(
        fuente="Procuraduria",
        estado=_estado_str_a_fuente(previo.get("procuraduria", "PENDIENTE")),
    )
    resultado.policia = ResultadoFuente(
        fuente="Policia",
        estado=_estado_str_a_fuente(previo.get("policia", "PENDIENTE")),
    )
    resultado.fiscal = ResultadoFuente(
        fuente="Fiscal",
        estado=_estado_str_a_fuente(previo.get("fiscal", "PENDIENTE")),
    )
    return resultado


def _enriquecer_nit_si_aplica(tercero: TerceroData, browser) -> TerceroData:
    """Para NIT sin dígito de verificación, obtiene el NIT completo vía RUES (o fórmula DIAN).

    Retorna un nuevo TerceroData con el numero_documento completo (10 dígitos).
    Para CC o NIT ya completo, retorna el mismo objeto sin cambios.
    """
    if tercero.tipo_documento != "NIT":
        return tercero

    nit_limpio = limpiar_nit(tercero.numero_documento)
    if len(nit_limpio) >= 10:
        # Ya tiene dígito de verificación — solo normalizar
        if nit_limpio != tercero.numero_documento:
            return TerceroData(
                nombre_completo=tercero.nombre_completo,
                numero_documento=nit_limpio[:10],
                tipo_documento=tercero.tipo_documento,
            )
        return tercero

    timeout_ms = config.timeout_sec * 1000
    buscador = BuscadorRUES(browser, timeout_ms=timeout_ms)
    nit_completo = buscador.obtener_nit_completo(nit_limpio)

    if nit_completo == tercero.numero_documento:
        return tercero

    logger.info(
        f"[NIT] Enriquecido: {tercero.numero_documento} → {nit_completo}"
        f" ({tercero.nombre_completo})"
    )
    return TerceroData(
        nombre_completo=tercero.nombre_completo,
        numero_documento=nit_completo,
        tipo_documento=tercero.tipo_documento,
    )


def _mover_a_procesados(pdf_path: Path) -> None:
    """Mueve el PDF de Inspektor a input/pdfs/procesados/ tras completarse exitosamente."""
    procesados = pdf_path.parent / "procesados"
    procesados.mkdir(exist_ok=True)
    destino = procesados / pdf_path.name
    try:
        if destino.exists():
            # Ya existe en procesados — eliminar el origen para limpiar input/pdfs/
            pdf_path.unlink()
            logger.info(f"[PDF] Origen eliminado (ya estaba en procesados): {pdf_path.name}")
        else:
            pdf_path.rename(destino)
            logger.info(f"[PDF] Movido a procesados: {pdf_path.name}")
    except Exception as exc:
        logger.warning(f"[PDF] No se pudo mover {pdf_path.name}: {exc}")


def _reintentar_tercero(
    resultado_anterior: ResultadoTercero,
    browser,
    retry: RetryHandler,
    renombrador: Renombrador,
    organizador: Organizador,
) -> ResultadoTercero:
    """Reintenta solo las fuentes que fallaron, conservando las exitosas."""
    tercero = resultado_anterior.tercero
    timeout_ms = config.timeout_sec * 1000
    es_nit = tercero.tipo_documento == "NIT"

    fuentes_pendientes = []
    if resultado_anterior.procuraduria.estado not in _ESTADOS_TERMINADOS:
        fuentes_pendientes.append(
            ("procuraduria", ConsultorProcuraduria(browser, config.download_folder, timeout_ms))
        )
    if not es_nit and resultado_anterior.policia.estado not in _ESTADOS_TERMINADOS:
        fuentes_pendientes.append(
            ("policia", ConsultorPolicia(browser, config.download_folder, timeout_ms))
        )
    if resultado_anterior.fiscal.estado not in _ESTADOS_TERMINADOS:
        fuentes_pendientes.append(
            ("fiscal", ConsultorFiscal(browser, config.download_folder, timeout_ms))
        )

    for fuente_key, consultor in fuentes_pendientes:
        resultado_fuente = ResultadoFuente(fuente=consultor.nombre_fuente)
        resultado_fuente = retry.ejecutar(
            operacion=lambda c=consultor: c.consultar(tercero),
            resultado=resultado_fuente,
        )
        if resultado_fuente.archivo_descargado:
            archivo_temp = Path(resultado_fuente.archivo_descargado)
            archivo_renombrado = renombrador.renombrar(archivo_temp, fuente_key, tercero)
            resultado_fuente.archivo_descargado = str(
                organizador.mover_archivo(archivo_renombrado, tercero)
            )
        setattr(resultado_anterior, fuente_key, resultado_fuente)
        logger.registrar_resumen(
            cedula=tercero.numero_documento,
            nombre=tercero.nombre_completo,
            fuente=consultor.nombre_fuente,
            estado=resultado_fuente.estado.value,
            intentos=resultado_fuente.intentos,
            error=resultado_fuente.error_mensaje or "",
        )
        logger.info(
            f"[Reintento][{consultor.nombre_fuente}] {tercero} → {resultado_fuente.estado.value}"
        )

    resultado_anterior.cerrar()
    return resultado_anterior


def _procesar_tercero(
    tercero: TerceroData,
    browser,
    retry: RetryHandler,
    renombrador: Renombrador,
    organizador: Organizador,
) -> ResultadoTercero:
    timeout_ms = config.timeout_sec * 1000
    resultado = ResultadoTercero(tercero=tercero)
    es_nit = tercero.tipo_documento == "NIT"

    fuentes_config = [
        ("procuraduria", ConsultorProcuraduria(browser, config.download_folder, timeout_ms)),
    ]

    if es_nit:
        logger.info(
            f"[Info] {tercero.nombre_completo} es Persona Jurídica (NIT) "
            "— Policía no aplica, se consulta Fiscal"
        )
        resultado.policia = ResultadoFuente(
            fuente="Policia",
            estado=EstadoFuente.PENDIENTE,
            error_mensaje="No aplica para Persona Jurídica (NIT)",
        )
        fuentes_config += [
            ("fiscal", ConsultorFiscal(browser, config.download_folder, timeout_ms)),
        ]
    else:
        fuentes_config += [
            ("policia", ConsultorPolicia(browser, config.download_folder, timeout_ms)),
            ("fiscal", ConsultorFiscal(browser, config.download_folder, timeout_ms)),
        ]

    for fuente_key, consultor in fuentes_config:
        resultado_fuente = ResultadoFuente(fuente=consultor.nombre_fuente)
        resultado_fuente = retry.ejecutar(
            operacion=lambda c=consultor: c.consultar(tercero),
            resultado=resultado_fuente,
        )
        if resultado_fuente.archivo_descargado:
            archivo_temp = Path(resultado_fuente.archivo_descargado)
            archivo_renombrado = renombrador.renombrar(archivo_temp, fuente_key, tercero)
            resultado_fuente.archivo_descargado = str(
                organizador.mover_archivo(archivo_renombrado, tercero)
            )
        setattr(resultado, fuente_key, resultado_fuente)
        logger.registrar_resumen(
            cedula=tercero.numero_documento,
            nombre=tercero.nombre_completo,
            fuente=consultor.nombre_fuente,
            estado=resultado_fuente.estado.value,
            intentos=resultado_fuente.intentos,
            error=resultado_fuente.error_mensaje or "",
        )
        logger.info(
            f"[{consultor.nombre_fuente}] {tercero} → {resultado_fuente.estado.value}"
        )

    resultado.cerrar()
    return resultado


def main() -> None:
    _inicializar()
    logger.info("=" * 60)
    logger.info("INICIO — AutomatizacionV1.0")
    logger.info("=" * 60)

    pdfs = _cargar_pdfs()
    if not pdfs:
        logger.error(
            "Sin PDFs para procesar. Coloque archivos en input/pdfs/ y vuelva a ejecutar."
        )
        sys.exit(1)

    extractor = ExtractorPDF()
    renombrador = Renombrador()
    organizador = Organizador(config.output_folder)
    retry = RetryHandler(
        max_attempts=config.retry_attempts,
        wait_sec=config.retry_wait_sec,
    )
    reporte = ReporteExcel()
    reporte_path = config.reports_folder / "resultado_consultas.xlsx"

    # Cargar estados de ejecuciones anteriores (punto 7 y 8)
    estados_previos = reporte.cargar_estados(reporte_path)
    if estados_previos:
        n_ok = sum(1 for v in estados_previos.values() if v.get("estado") in _ESTADOS_OK_STR)
        n_inc = len(estados_previos) - n_ok
        logger.info(
            f"[Excel] Historial cargado: {n_ok} exitoso(s) (se omitirán), "
            f"{n_inc} incompleto(s) (se reintentarán)."
        )

    resultados: list[ResultadoTercero] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            channel="chrome",
            headless=config.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-popup-blocking",
                "--disable-features=IsolateOrigins,site-per-process",
                "--lang=es-CO",
            ],
        )
        logger.info(f"Navegador iniciado (headless={config.headless})")

        for idx, pdf_path in enumerate(pdfs, start=1):
            logger.info(f"\n--- PDF {idx}/{len(pdfs)}: {pdf_path.name} ---")

            # Extraer datos del PDF
            try:
                tercero = extractor.extraer(pdf_path)
            except Exception as exc:
                logger.error(f"ERROR_PDF: {pdf_path.name} — {exc}")
                tercero_error = TerceroData(
                    nombre_completo=pdf_path.stem,
                    numero_documento="DESCONOCIDO",
                )
                resultado = ResultadoTercero(tercero=tercero_error)
                resultado.procuraduria.estado = EstadoFuente.FALLIDO
                resultado.procuraduria.error_mensaje = str(exc)
                resultado.policia.estado = EstadoFuente.FALLIDO
                resultado.fiscal.estado = EstadoFuente.FALLIDO
                resultado.cerrar()
                resultados.append(resultado)
                reporte.actualizar_o_crear([resultado], reporte_path, incrementar_consulta=True)
                continue

            # Para NIT: completar con dígito de verificación antes de todo lo demás
            tercero = _enriquecer_nit_si_aplica(tercero, browser)

            cedula = tercero.numero_documento
            previo = estados_previos.get(cedula, {})
            estado_previo = previo.get("estado", "")

            # Punto 7: ya exitoso → no volver a consultar
            if estado_previo in _ESTADOS_OK_STR:
                logger.info(
                    f"[Skip] {tercero} ya procesado exitosamente "
                    f"(consultas previas: {previo.get('consultas', '?')}). Omitiendo."
                )
                _mover_a_procesados(pdf_path)
                continue

            # Punto 5 & 6: PARCIAL de ejecución anterior → reintenta solo fuentes fallidas
            if estado_previo == "PARCIAL" and previo:
                logger.info(
                    f"[Reanudar] {tercero} → estado previo PARCIAL. "
                    "Reintentando fuentes fallidas."
                )
                resultado_previo = _reconstruir_resultado_previo(tercero, previo)
                resultado = _reintentar_tercero(
                    resultado_previo, browser, retry, renombrador, organizador
                )
            else:
                # Nuevo tercero o FALLIDO_TOTAL → procesar todas las fuentes
                logger.info(f"--- Tercero {idx}/{len(pdfs)}: {tercero} ---")
                resultado = _procesar_tercero(
                    tercero, browser, retry, renombrador, organizador
                )

            resultados.append(resultado)
            logger.info(f"Resultado: {resultado.estado_general.value}")

            # Guardar Excel inmediatamente tras cada tercero (crash safety)
            reporte.actualizar_o_crear([resultado], reporte_path, incrementar_consulta=True)

            # Actualizar estados en memoria para próximas iteraciones del mismo run.
            # Para NIT: si no está completo, siempre es PARCIAL (nunca FALLIDO_TOTAL),
            # coherente con lo que escribe _calcular_estado en el Excel.
            _es_nit = tercero.tipo_documento == "NIT"
            if _es_completo(resultado):
                _estado_mem = "EXITOSO"
            elif _es_nit:
                _estado_mem = "PARCIAL"
            else:
                _estado_mem = resultado.estado_general.value
            estados_previos[cedula] = {
                "estado": _estado_mem,
                "procuraduria": resultado.procuraduria.estado.value,
                "policia": (
                    "NO APLICA" if tercero.tipo_documento == "NIT"
                    else resultado.policia.estado.value
                ),
                "fiscal": resultado.fiscal.estado.value,
                "consultas": previo.get("consultas", 0) + 1,
            }

            # Punto 4: mover a procesados si el tercero está completo
            if _es_completo(resultado):
                _mover_a_procesados(pdf_path)

        # Pasadas de reintento para terceros incompletos de este run (punto 5)
        for pasada in range(1, _MAX_PASADAS_EXTRA + 1):
            incompletos = [
                (i, r) for i, r in enumerate(resultados)
                if not _es_completo(r) and r.tercero.numero_documento != "DESCONOCIDO"
            ]
            if not incompletos:
                break
            logger.info(
                f"\n{'='*60}\n"
                f"  Pasada reintento {pasada}/{_MAX_PASADAS_EXTRA} — "
                f"{len(incompletos)} tercero(s) incompleto(s)\n"
                f"{'='*60}"
            )
            for i, resultado_anterior in incompletos:
                logger.info(f"  Reintentando: {resultado_anterior.tercero}")
                resultados[i] = _reintentar_tercero(
                    resultado_anterior, browser, retry, renombrador, organizador
                )
                # Sin incrementar consultas — ya se contó en el loop principal
                reporte.actualizar_o_crear(
                    [resultados[i]], reporte_path, incrementar_consulta=False
                )

        browser.close()

    exitosos = sum(1 for r in resultados if _es_completo(r))
    logger.info("=" * 60)
    logger.info(f"FIN — {exitosos}/{len(resultados)} terceros completados exitosamente.")
    logger.info(f"Reporte: {reporte_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
