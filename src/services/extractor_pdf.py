"""Extrae nombre completo y número de documento de PDFs generados por Inspektor."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pdfplumber

from src.infrastructure.logger_manager import LoggerManager
from src.models.tercero import TerceroData

logger = LoggerManager()


class ExtractorPDF:
    """Lee un PDF de Inspektor y retorna el TerceroData extraído."""

    def extraer(self, pdf_path: Path) -> TerceroData:
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

        texto = self._extraer_texto(pdf_path)
        nombre = self._extraer_nombre(texto)
        cedula = self._extraer_cedula(texto)

        if not nombre or not cedula:
            raise ValueError(
                f"No se pudo extraer nombre o cédula de '{pdf_path.name}'. "
                f"nombre='{nombre}', cedula='{cedula}'"
            )

        cedula_limpia = cedula.strip()
        nombre_limpio = nombre.strip().upper()
        tipo_doc = self._inferir_tipo_doc(nombre_limpio)
        logger.info(f"PDF extraído: {nombre_limpio} {tipo_doc} {cedula_limpia} — {pdf_path.name}")
        return TerceroData(
            nombre_completo=nombre_limpio,
            numero_documento=cedula_limpia,
            tipo_documento=tipo_doc,
        )

    def _extraer_texto(self, pdf_path: Path) -> str:
        texto_total = ""
        with pdfplumber.open(pdf_path) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if texto:
                    texto_total += texto + "\n"
        logger.info(f"[ExtractorPDF] Texto raw (primeros 500 chars):\n{texto_total[:500]!r}")
        return texto_total

    def _extraer_nombre(self, texto: str) -> Optional[str]:
        m = re.search(r"Nombre\s+([A-ZÁÉÍÓÚÑ][^\n\r]+)", texto)
        if m:
            return m.group(1).strip()
        return None

    # Términos jurídicos colombianos — lookbehind/lookahead evitan \b
    # para manejar correctamente acrónimos con puntos finales (S.A.S., LTDA.)
    _PALABRAS_JURIDICO = re.compile(
        r"(?<!\w)(?:"
        r"S\.?A\.?S?\.?"          # S.A., SA, SAS, S.A.S.
        r"|LTDA\.?"               # LTDA, LTDA.
        r"|E\.?U\.?"              # E.U., EU
        r"|E\.?S\.?P\.?"          # E.S.P., ESP
        r"|S\.?C\.?A\.?"          # S.C.A.
        r"|S\.?C\.?S\.?"          # S.C.S.
        r"|E\.?I\.?C\.?E\.?"      # E.I.C.E.
        r"|I\.?P\.?S\.?"          # I.P.S.
        r"|E\.?P\.?S\.?"          # E.P.S.
        r"|E\.?S\.?E\.?"          # E.S.E.
        r"|O\.?N\.?G\.?"          # O.N.G.
        r"|CORP\.?"               # CORP
        r"|INC\.?"                # INC
        r"|CIA\.?"                # CIA.
        r"|FUNDACI[OÓ]N"          # FUNDACION / FUNDACIÓN
        r"|COOPERATIVA"
        r"|CONSORCIO"
        r"|EMPRESA"
        r"|UNION\s+TEMPORAL"      # UNION TEMPORAL (frase compuesta)
        r")(?!\w)",
        re.IGNORECASE,
    )

    def _inferir_tipo_doc(self, nombre: str) -> str:
        return "NIT" if self._PALABRAS_JURIDICO.search(nombre) else "CC"

    def _extraer_cedula(self, texto: str) -> Optional[str]:
        # Patrón primario: "identificación: 900943048" (dígitos continuos)
        m = re.search(r"identificaci[oó]n\s*[:\s]+(\d{6,12})", texto, re.IGNORECASE)
        if m:
            return m.group(1).strip()

        # Patrón NIT con formato colombiano: "NIT: 900.943.048-4" o "NIT 900943048"
        m = re.search(
            r"\bNIT\s*[:\s]+(\d{3}[\.\s]?\d{3}[\.\s]?\d{3}(?:[\-\s]?\d)?)",
            texto,
            re.IGNORECASE,
        )
        if m:
            return re.sub(r"[^\d]", "", m.group(1)).strip()

        # Fallback: primer número de 7-11 dígitos continuos en el texto
        m = re.search(r"\b(\d{7,11})\b", texto)
        if m:
            return m.group(1).strip()

        return None
