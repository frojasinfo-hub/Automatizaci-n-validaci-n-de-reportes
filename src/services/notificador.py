"""Envía alertas al operador por correo SMTP y/o webhook de Teams."""

from __future__ import annotations

import smtplib
import urllib.request
import json
from email.mime.text import MIMEText
from typing import Any

from src.infrastructure.config_manager import ConfigManager
from src.infrastructure.logger_manager import LoggerManager

logger = LoggerManager()
config = ConfigManager()


class Notificador:
    """
    Notifica al operador cuando se requiere intervención manual (CAPTCHA)
    o cuando una fuente falla definitivamente.
    Solo activo si notify_email / notify_teams están en true en config.json.
    """

    def notificar_captcha_manual(self, fuente: str, nombre_tercero: str) -> None:
        asunto = f"[CAPTCHA] Intervención requerida — {fuente}"
        cuerpo = (
            f"El sistema requiere resolución manual del reCAPTCHA en {fuente}\n"
            f"Tercero: {nombre_tercero}\n\n"
            "Por favor resuelva el CAPTCHA en el navegador y presione Enter en la consola."
        )
        self._enviar(asunto, cuerpo)

    def notificar_fuente_fallida(self, fuente: str, nombre_tercero: str, error: str) -> None:
        asunto = f"[FALLIDO] {fuente} — {nombre_tercero}"
        cuerpo = (
            f"La fuente {fuente} falló después de 5 intentos.\n"
            f"Tercero: {nombre_tercero}\n"
            f"Error: {error}"
        )
        self._enviar(asunto, cuerpo)

    def _enviar(self, asunto: str, cuerpo: str) -> None:
        if config.notify_email:
            self._enviar_email(asunto, cuerpo)
        if config.notify_teams:
            self._enviar_teams(cuerpo)

    def _enviar_email(self, asunto: str, cuerpo: str) -> None:
        cfg = config.email_config
        if not cfg.get("smtp_host") or not cfg.get("sender"):
            logger.warning("Notificación email omitida: configuración incompleta.")
            return
        try:
            mensaje = MIMEText(cuerpo, "plain", "utf-8")
            mensaje["Subject"] = asunto
            mensaje["From"] = cfg["sender"]
            mensaje["To"] = ", ".join(cfg.get("recipients", []))

            with smtplib.SMTP(cfg["smtp_host"], cfg.get("smtp_port", 587)) as server:
                server.starttls()
                server.login(cfg["sender"], cfg.get("password", ""))
                server.sendmail(cfg["sender"], cfg.get("recipients", []), mensaje.as_string())
            logger.info(f"Email enviado: {asunto}")
        except Exception as exc:
            logger.error(f"Error enviando email: {exc}")

    def _enviar_teams(self, cuerpo: str) -> None:
        cfg = config.teams_config
        webhook_url = cfg.get("webhook_url", "")
        if not webhook_url:
            logger.warning("Notificación Teams omitida: webhook_url no configurado.")
            return
        try:
            payload = json.dumps({"text": cuerpo}).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            logger.info("Notificación Teams enviada.")
        except Exception as exc:
            logger.error(f"Error enviando notificación Teams: {exc}")
