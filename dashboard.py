"""Dashboard principal — AutomatizaciónV1."""
from __future__ import annotations

import html
import time
from typing import Any

import httpx
import pandas as pd
import streamlit as st
from urllib.parse import urlencode

from login import _USERS, show_login

API = "http://localhost:8000"

_ROLE_LABEL = {
    "admin": "Administrador",
    "supervisor": "Supervisor",
    "consultor": "Consultor",
}

_STATUS_BG: dict[str, str] = {
    "EXITOSO":       "#C6EFCE",
    "AUTOMATICO":    "#C6EFCE",
    "PARCIAL":       "#FFEB9C",
    "EN_ESPERA":     "#FFEB9C",
    "REINTENTANDO":  "#FFEB9C",
    "NO_ENCONTRADO": "#FCE4D6",
    "FALLIDO":       "#FFC7CE",
    "FALLIDO_TOTAL": "#FFC7CE",
    "ERROR_PDF":     "#FFC7CE",
    "PENDIENTE":     "#E9ECEF",
}

_STATUS_COLS = {"Procuraduría", "Policía", "Fiscal", "Estado"}

_PAGE_GUARD: dict[str, tuple[str, ...]] = {
    "historial": ("supervisor", "admin"),
    "sistema":   ("admin",),
}

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AutomatizaciónV1",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Auth guard ─────────────────────────────────────────────────────────────────
if not st.session_state.get("authenticated"):
    show_login()
    st.stop()

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown(
    """<style>
[data-testid="stSidebar"]{display:none}
.block-container{padding-top:8px!important;padding-bottom:40px!important}
.stApp{background:#FFFFFF!important}
#MainMenu,footer,header{visibility:hidden}

.topbar{
    background:#1B2A4A;padding:12px 20px;border-radius:8px;
    display:flex;align-items:center;justify-content:space-between;
    margin-bottom:4px;
}
.topbar-left{display:flex;align-items:center;gap:12px}
.topbar-title{color:#FFFFFF;font-size:16px;font-weight:700;margin:0}
.topbar-sub{
    color:#8898AA;font-size:10px;text-transform:uppercase;letter-spacing:1px
}
.topbar-right{display:flex;align-items:center;gap:14px}
.topbar-user{color:#FFFFFF;font-size:13px}
.topbar-badge{
    background:#C8A951;color:#1B2A4A;font-size:10px;font-weight:700;
    padding:2px 8px;border-radius:10px;text-transform:uppercase;letter-spacing:.5px;
}
.api-ok{color:#2ecc71;font-size:11px}
.api-err{color:#e74c3c;font-size:11px}

button[kind="primary"],[data-testid="stBaseButton-primary"]{
    background:#1B2A4A!important;color:#FFFFFF!important;
    border:none!important;border-radius:6px!important;font-weight:600!important;
}
button[kind="primary"]:hover,[data-testid="stBaseButton-primary"]:hover{
    background:#2c4070!important;
}
button[kind="secondary"],[data-testid="stBaseButton-secondary"]{
    background:#FFFFFF!important;color:#1B2A4A!important;
    border:1.5px solid #1B2A4A!important;border-radius:6px!important;
}
button[kind="secondary"]:hover,[data-testid="stBaseButton-secondary"]:hover{
    background:#EEF2FF!important;
}

.mcard{
    background:#FFFFFF;border-radius:10px;padding:18px 22px;
    box-shadow:0 1px 6px rgba(0,0,0,.08);border-top:4px solid #C8A951;
}
.mcard-val{font-size:32px;font-weight:700;color:#1A1A1A;margin:8px 0 4px}
.mcard-lbl{font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.5px}

.scard{
    background:#FFFFFF;border-radius:8px;padding:14px 18px;
    box-shadow:0 1px 4px rgba(0,0,0,.06);margin-bottom:12px;
}

.chip{
    display:inline-block;padding:3px 10px;border-radius:4px;
    font-size:12px;color:#1A1A1A;margin-right:6px;margin-top:4px;
}

.page-title{
    font-size:20px;font-weight:700;color:#1A1A1A;
    border-left:4px solid #1B2A4A;padding-left:12px;margin:16px 0 4px;
}
.page-sub{font-size:13px;color:#666;margin:0 0 16px 16px}
.sec-title{font-size:15px;font-weight:600;color:#1A1A1A;margin:16px 0 8px}

[data-testid="stExpander"]{
    background:#FFFFFF!important;
    border:1px solid #E0E0E0!important;
    border-radius:8px!important;
}
[data-testid="stExpander"] *{color:#1A1A1A!important}
[data-testid="stExpanderToggleIcon"]{color:#1B2A4A!important}
details summary{
    background:#F8F9FA!important;
    color:#1A1A1A!important;
    border-radius:8px!important;
}
details[open] summary{border-radius:8px 8px 0 0!important}
</style>""",
    unsafe_allow_html=True,
)

# ── Session defaults ───────────────────────────────────────────────────────────
role: str = st.session_state.get("user_role", "consultor")
user_name: str = st.session_state.get("user_name", "Usuario")
role_label: str = _ROLE_LABEL.get(role, role.title())

if "current_page" not in st.session_state:
    st.session_state.current_page = "home"


# ── API helpers ────────────────────────────────────────────────────────────────
def _api(path: str, timeout: float = 5.0, **kwargs: Any) -> Any:
    return httpx.get(f"{API}{path}", timeout=timeout, **kwargs).json()


@st.cache_data(ttl=10)
def _fetch_api_status() -> dict[str, Any]:
    return _api("/api/automation/status", timeout=2)


@st.cache_data(ttl=30)
def _fetch_reports() -> list[dict[str, Any]]:
    return _api("/api/reports/data", timeout=5)


@st.cache_data(ttl=30)
def _fetch_files() -> list[dict[str, Any]]:
    return _api("/api/files/list", timeout=5)


# ── HTML table (white bg, color only in status cells) ─────────────────────────
def _html_table(
    rows: list[dict[str, Any]], max_rows: int | None = None
) -> str:
    if not rows:
        return ""
    if max_rows:
        rows = rows[-max_rows:]
    headers = list(rows[0].keys())

    ths = "".join(
        f'<th style="padding:9px 14px;background:#F8F9FA;color:#1A1A1A;'
        f'font-size:12px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.4px;border:1px solid #E0E0E0;white-space:nowrap">'
        f"{html.escape(str(h))}</th>"
        for h in headers
    )

    trs = ""
    for i, r in enumerate(rows):
        row_bg = "#FAFAFA" if i % 2 else "#FFFFFF"
        tds = ""
        for h in headers:
            val = str(r.get(h, ""))
            escaped = html.escape(val)
            if h in _STATUS_COLS and val in _STATUS_BG:
                bg = _STATUS_BG[val]
                tds += (
                    f'<td style="padding:8px 14px;border:1px solid #E0E0E0;'
                    f"background:{bg};color:#1A1A1A;font-size:13px;"
                    f'font-weight:600;white-space:nowrap">{escaped}</td>'
                )
            else:
                tds += (
                    f'<td style="padding:8px 14px;border:1px solid #E0E0E0;'
                    f"background:{row_bg};color:#1A1A1A;"
                    f'font-size:13px">{escaped}</td>'
                )
        trs += f"<tr>{tds}</tr>"

    return (
        '<div style="overflow-x:auto;border-radius:8px;'
        'border:1px solid #E0E0E0;margin-bottom:8px">'
        '<table style="border-collapse:collapse;width:100%;background:#FFFFFF">'
        f"<thead><tr>{ths}</tr></thead>"
        f"<tbody>{trs}</tbody>"
        "</table></div>"
    )


# ── Shared UI components ───────────────────────────────────────────────────────
def _page_heading(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="page-title">{title}</div>', unsafe_allow_html=True
    )
    if subtitle:
        st.markdown(
            f'<div class="page-sub">{subtitle}</div>', unsafe_allow_html=True
        )


def _legend_chips() -> None:
    st.markdown(
        """<div style="margin:8px 0 4px">
        <span class="chip" style="background:#C6EFCE">■ Exitoso / Automático</span>
        <span class="chip" style="background:#FFEB9C">■ Parcial / En espera</span>
        <span class="chip" style="background:#FFC7CE">■ Fallido / Error</span>
        <span class="chip" style="background:#FCE4D6">■ No encontrado</span>
        <span class="chip" style="background:#E9ECEF">■ Pendiente</span>
        </div>""",
        unsafe_allow_html=True,
    )


def _excel_download_btn(key: str = "dl_excel") -> None:
    try:
        resp = httpx.get(f"{API}/api/reports/download", timeout=5)
        if resp.status_code == 200:
            st.download_button(
                "⬇️  Descargar Excel",
                data=resp.content,
                file_name="resultado_consultas.xlsx",
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet"
                ),
                key=key,
                type="primary",
            )
    except Exception:
        pass


def _docs_por_tercero(rows: list[dict[str, Any]]) -> None:
    st.markdown(
        '<hr style="border:none;border-top:1px solid #E0E0E0;margin:20px 0 12px">',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="page-title" style="font-size:17px">📁 Documentos por Tercero</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color:#666;font-size:13px;margin:4px 0 12px 16px">'
        "Certificados en <code>output/CONSULTAS_AUTOMATIZADAS/</code></p>",
        unsafe_allow_html=True,
    )

    for r in rows:
        nombre   = r.get("Nombre", "")
        tipo_doc = r.get("Tipo Doc", "CC")
        cedula   = r.get("Cédula", "")
        folder   = f"{nombre} {tipo_doc} {cedula}".strip()
        if not folder:
            continue

        try:
            pdfs: list[dict[str, Any]] = httpx.get(
                f"{API}/api/tercero/pdfs",
                params={"folder": folder},
                timeout=5,
            ).json()
        except Exception:
            pdfs = []

        n = len(pdfs)
        badge = "✅" if n >= 3 else ("⚠️" if n > 0 else "❌")

        with st.expander(f"{badge}  {folder}  —  {n} PDF(s)"):
            if not pdfs:
                st.markdown(
                    '<p style="color:#666;font-size:13px;margin:4px 0">'
                    "Sin certificados en esta carpeta.</p>",
                    unsafe_allow_html=True,
                )
                continue

            st.markdown(
                f'<p style="color:#666;font-size:12px;margin-bottom:10px">'
                f"📂 <code>output/CONSULTAS_AUTOMATIZADAS/"
                f"{html.escape(folder)}/</code></p>",
                unsafe_allow_html=True,
            )
            for pdf in pdfs:
                nm   = pdf["name"]
                sz   = pdf["size_kb"]
                icon = (
                    "🔵" if nm.upper().startswith("PRO")  else
                    "🟢" if nm.upper().startswith("POL")  else
                    "🟡" if nm.upper().startswith("RFIS") else
                    "📄"
                )
                url = f"{API}/api/tercero/pdf?" + urlencode(
                    {"folder": folder, "filename": nm}
                )
                st.markdown(
                    f'<div style="padding:7px 0;'
                    f'border-bottom:1px solid #F0F0F0;color:#1A1A1A">'
                    f"{icon} <strong style=\"color:#1A1A1A\">"
                    f"{html.escape(nm)}</strong>"
                    f' <span style="color:#888;font-size:12px">{sz} KB</span>'
                    f' &emsp; <a href="{url}" target="_blank"'
                    f' style="color:#1B2A4A;font-weight:600;'
                    f'text-decoration:none">⬇️ Descargar</a></div>',
                    unsafe_allow_html=True,
                )


# ── Nav builder ────────────────────────────────────────────────────────────────
def _build_nav() -> list[tuple[str, str, str]]:
    items: list[tuple[str, str, str]] = [
        ("🏠", "Inicio",        "home"),
        ("📤", "Nueva Consulta","nueva_consulta"),
        ("📋", "Resultados",    "resultados"),
    ]
    if role in ("supervisor", "admin"):
        items.append(("📚", "Historial", "historial"))
    if role == "admin":
        items.append(("🖥️", "Sistema", "sistema"))
    return items


# ── Header ─────────────────────────────────────────────────────────────────────
def _render_header() -> None:
    try:
        _fetch_api_status()
        api_dot = '<span class="api-ok">⬤ en línea</span>'
    except Exception:
        api_dot = '<span class="api-err">⬤ no disponible</span>'

    st.markdown(
        f"""<div class="topbar">
          <div class="topbar-left">
            <span style="font-size:28px;line-height:1">🛡️</span>
            <div>
              <div class="topbar-title">AutomatizaciónV1</div>
              <div class="topbar-sub">Consulta de Antecedentes &nbsp;·&nbsp; {api_dot}</div>
            </div>
          </div>
          <div class="topbar-right">
            <span class="topbar-user">👤 {html.escape(user_name)}</span>
            <span class="topbar-badge">{html.escape(role_label)}</span>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )

    nav_items = _build_nav()
    cols = st.columns(len(nav_items) + 1)
    for col, (icon, label, key) in zip(cols, nav_items):
        with col:
            active = st.session_state.current_page == key
            if st.button(
                f"{icon}  {label}",
                key=f"nav_{key}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                if not active:
                    st.session_state.current_page = key
                    st.rerun()
    with cols[-1]:
        if st.button("🚪 Salir", use_container_width=True, key="logout"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    st.markdown(
        '<hr style="border:none;border-top:1px solid #E0E0E0;margin:6px 0 8px">',
        unsafe_allow_html=True,
    )


_render_header()


# ── Pages ──────────────────────────────────────────────────────────────────────

def _page_home() -> None:
    _page_heading("🏠 Inicio", f"Bienvenido, {user_name} — {role_label}")

    try:
        pdf_count = len(_fetch_files())
    except Exception:
        pdf_count = 0

    exitosos = pendientes = fallidos = total = 0
    rows: list[dict[str, Any]] = []
    try:
        rows = _fetch_reports()
        total = len(rows)
        for r in rows:
            estado = r.get("Estado", "")
            if estado in ("EXITOSO", "AUTOMATICO"):
                exitosos += 1
            elif estado in ("EN_ESPERA", "PARCIAL", "REINTENTANDO"):
                pendientes += 1
            elif "FALLIDO" in estado or estado == "ERROR_PDF":
                fallidos += 1
    except Exception:
        pass

    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl, color in [
        (c1, pdf_count, "PDFs en cola", "#C8A951"),
        (c2, exitosos,  "Exitosos",      "#27ae60"),
        (c3, pendientes,"Pendientes",    "#f39c12"),
        (c4, fallidos,  "Fallidos",      "#e74c3c"),
    ]:
        with col:
            st.markdown(
                f'<div class="mcard" style="border-top-color:{color}">'
                f'<div class="mcard-lbl">{lbl}</div>'
                f'<div class="mcard-val" style="color:{color}">{val}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    try:
        proc_status = _fetch_api_status().get("status", "idle")
        _pmap = {
            "idle":    ("#95a5a6", "⏸", "Sin proceso activo"),
            "running": ("#3498db", "🔄", "Proceso en ejecución"),
            "done":    ("#27ae60", "✅", "Proceso completado"),
            "error":   ("#e74c3c", "❌", "Proceso con error"),
        }
        color, icon, lbl = _pmap.get(proc_status, ("#95a5a6", "⏸", proc_status))
        st.markdown(
            f'<div class="scard" style="border-left:4px solid {color}">'
            f'<strong style="color:{color}">{icon} Motor: {lbl}</strong>'
            f'<span style="color:#999;font-size:12px;margin-left:16px">'
            f"AutomatizaciónV1</span></div>",
            unsafe_allow_html=True,
        )
    except Exception:
        pass

    st.markdown(
        '<div class="sec-title">Últimas 10 consultas</div>',
        unsafe_allow_html=True,
    )
    if rows:
        st.markdown(_html_table(rows, max_rows=10), unsafe_allow_html=True)
        _legend_chips()
    else:
        st.info(
            "Sin resultados aún. Vaya a **Nueva Consulta** para iniciar el proceso."
        )


def _page_nueva_consulta() -> None:
    _page_heading(
        "📤 Nueva Consulta",
        "Cargue los PDFs de Inspektor e inicie el proceso de automatización",
    )
    col_up, col_run = st.columns([3, 2])

    with col_up:
        st.markdown('<div class="sec-title">1. Cargar PDFs</div>', unsafe_allow_html=True)
        archivos = st.file_uploader(
            "Seleccione uno o más PDFs de Inspektor",
            type="pdf",
            accept_multiple_files=True,
            key="uploader",
        )
        if archivos and st.button("⬆️  Subir archivos", type="primary"):
            ok = err = 0
            bar = st.progress(0)
            for i, archivo in enumerate(archivos):
                try:
                    resp = httpx.post(
                        f"{API}/api/files/upload",
                        files={
                            "file": (
                                archivo.name,
                                archivo.getvalue(),
                                "application/pdf",
                            )
                        },
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        ok += 1
                    else:
                        err += 1
                        st.warning(f"✗ {archivo.name}: {resp.text}")
                except Exception as exc:
                    err += 1
                    st.error(str(exc))
                bar.progress((i + 1) / len(archivos))
            if ok:
                st.success(f"✓ {ok} archivo(s) subido(s) correctamente")
            if err:
                st.error(f"✗ {err} archivo(s) con error")
            _fetch_files.clear()
            st.rerun()

        st.markdown(
            '<hr style="border:none;border-top:1px solid #E0E0E0;margin:12px 0">'
            '<div class="sec-title" style="margin-top:0">Archivos en cola</div>',
            unsafe_allow_html=True,
        )
        try:
            files: list[dict[str, Any]] = _fetch_files()
            if files:
                for f in files:
                    st.markdown(
                        f'<div style="color:#1A1A1A;font-size:13px;padding:4px 0">'
                        f"📄 {html.escape(f['name'])} "
                        f'<span style="color:#888">{f["size_kb"]} KB</span></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No hay PDFs en la carpeta de entrada.")
        except Exception:
            st.warning("No se pudo cargar la lista.")

    with col_run:
        st.markdown('<div class="sec-title">2. Iniciar proceso</div>', unsafe_allow_html=True)
        st.info(
            "Se abrirá una ventana de terminal separada donde el operador "
            "resuelve los CAPTCHAs manualmente."
        )
        if st.button(
            "▶  Iniciar Automatización",
            type="primary",
            use_container_width=True,
        ):
            try:
                resp = httpx.post(f"{API}/api/automation/run", timeout=10)
                data = resp.json()
                s = data.get("status")
                if s == "started":
                    st.success(f"✅ Proceso iniciado — PID {data.get('pid')}")
                elif s == "already_running":
                    st.warning(f"⚠️ Proceso en ejecución (PID {data.get('pid')})")
            except Exception as exc:
                st.error(f"No se pudo conectar a la API: {exc}")

        st.markdown(
            '<hr style="border:none;border-top:1px solid #E0E0E0;margin:12px 0">'
            '<div class="sec-title" style="margin-top:0">Estado actual</div>',
            unsafe_allow_html=True,
        )
        try:
            data = _api("/api/automation/status")
            status = data.get("status", "idle")
            _lmap = {
                "idle":    ("⏸", "Inactivo"),
                "running": ("🔄", "En ejecución..."),
                "done":    ("✅", "Completado"),
                "error":   ("❌", "Error"),
            }
            icon, lbl = _lmap.get(status, ("⏸", status))
            st.markdown(
                f'<div style="color:#1A1A1A;font-size:14px;font-weight:600">'
                f"{icon} {lbl}</div>",
                unsafe_allow_html=True,
            )
            log = data.get("log", [])
            if log:
                st.code("\n".join(log[-10:]), language="text")
            if status == "running":
                c_ref, c_aut = st.columns(2)
                with c_ref:
                    if st.button("🔄 Actualizar"):
                        st.rerun()
                with c_aut:
                    if st.checkbox("Auto 3s"):
                        time.sleep(3)
                        st.rerun()
        except Exception as exc:
            st.error(f"No se puede conectar: {exc}")


def _page_resultados() -> None:
    _page_heading(
        "📋 Resultados",
        "Tabla de resultados con semáforo de estados por fuente",
    )

    c_ref, c_dl, _ = st.columns([1, 1, 5])
    with c_ref:
        if st.button("🔄 Actualizar"):
            _fetch_reports.clear()
            st.rerun()

    try:
        rows = _fetch_reports()
    except Exception as exc:
        st.error(f"Error al cargar resultados: {exc}")
        return

    if not rows:
        st.info("Sin resultados. Inicie el proceso desde **Nueva Consulta**.")
        return

    with c_dl:
        _excel_download_btn(key="dl_excel_res")

    st.caption(f"Total: {len(rows)} tercero(s)")
    st.markdown(_html_table(rows), unsafe_allow_html=True)
    _legend_chips()
    _docs_por_tercero(rows)


def _page_historial() -> None:
    _page_heading("📚 Historial", "Registro completo con filtros y descarga de PDFs")

    c_ref, _ = st.columns([1, 7])
    with c_ref:
        if st.button("🔄 Actualizar"):
            _fetch_reports.clear()
            st.rerun()

    try:
        all_rows: list[dict[str, Any]] = _fetch_reports()
    except Exception as exc:
        st.error(f"Error cargando historial: {exc}")
        return

    if not all_rows:
        st.info("Sin historial aún. Ejecute el proceso desde **Nueva Consulta**.")
        return

    df_hist = pd.DataFrame(all_rows)

    st.markdown('<div class="sec-title">Filtros</div>', unsafe_allow_html=True)
    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
    with fcol1:
        f_nombre = st.text_input("Buscar nombre", key="h_nombre")
    with fcol2:
        tipos = (
            sorted(df_hist["Tipo Doc"].dropna().unique().tolist())
            if "Tipo Doc" in df_hist.columns else []
        )
        f_tipo = st.selectbox("Tipo documento", ["Todos"] + tipos, key="h_tipo")
    with fcol3:
        estados = (
            sorted(df_hist["Estado"].dropna().unique().tolist())
            if "Estado" in df_hist.columns else []
        )
        f_estado = st.selectbox("Estado", ["Todos"] + estados, key="h_estado")
    with fcol4:
        f_fecha = st.text_input("Fecha contiene (ej: 06/26)", key="h_fecha")

    mask = pd.Series([True] * len(df_hist), index=df_hist.index)
    if f_nombre and "Nombre" in df_hist.columns:
        mask &= df_hist["Nombre"].str.contains(f_nombre, case=False, na=False)
    if f_tipo != "Todos" and "Tipo Doc" in df_hist.columns:
        mask &= df_hist["Tipo Doc"] == f_tipo
    if f_estado != "Todos" and "Estado" in df_hist.columns:
        mask &= df_hist["Estado"] == f_estado
    if f_fecha and "Fecha" in df_hist.columns:
        mask &= df_hist["Fecha"].str.contains(f_fecha, na=False)

    filtered = df_hist[mask].reset_index(drop=True).to_dict("records")
    st.caption(f"Mostrando **{len(filtered)}** de **{len(all_rows)}** registros")
    st.markdown(_html_table(filtered), unsafe_allow_html=True)
    _legend_chips()

    _excel_download_btn(key="dl_excel_hist")

    st.markdown(
        '<hr style="border:none;border-top:1px solid #E0E0E0;margin:20px 0 12px">'
        '<div class="sec-title" style="margin-top:0">'
        "Descargar PDFs por tercero</div>",
        unsafe_allow_html=True,
    )
    if not filtered:
        st.info("Sin registros que coincidan con los filtros.")
        return

    opciones = [
        f"{r.get('Nombre','')} {r.get('Tipo Doc','')} {r.get('Cédula','')}".strip()
        for r in filtered
    ]
    seleccionado = st.selectbox("Seleccione un tercero", opciones, key="h_tercero")
    if seleccionado:
        try:
            pdfs: list[dict[str, Any]] = httpx.get(
                f"{API}/api/tercero/pdfs",
                params={"folder": seleccionado},
                timeout=5,
            ).json()
            if pdfs:
                st.caption(
                    f"📂 `output/CONSULTAS_AUTOMATIZADAS/{seleccionado}/`"
                )
                for pdf in pdfs:
                    try:
                        resp_pdf = httpx.get(
                            f"{API}/api/tercero/pdf",
                            params={
                                "folder": seleccionado,
                                "filename": pdf["name"],
                            },
                            timeout=10,
                        )
                        if resp_pdf.status_code == 200:
                            st.download_button(
                                f"⬇️  {pdf['name']}  ({pdf['size_kb']} KB)",
                                data=resp_pdf.content,
                                file_name=pdf["name"],
                                mime="application/pdf",
                                key=f"pdf_{seleccionado}_{pdf['name']}",
                            )
                    except Exception:
                        st.warning(f"No se pudo cargar {pdf['name']}")
            else:
                st.warning("No se encontraron PDFs para este tercero.")
        except Exception as exc2:
            st.error(f"Error cargando PDFs: {exc2}")


def _page_sistema() -> None:
    _page_heading("🖥️ Sistema", "Estado del motor y logs del servidor")

    c1, c2, _ = st.columns([1, 1, 5])
    with c1:
        if st.button("🔄 Actualizar"):
            st.rerun()
    with c2:
        auto = st.checkbox("Auto 3s")

    try:
        data: dict[str, Any] = _api("/api/automation/status")
        status = data.get("status", "idle")
        _smap: dict[str, tuple[Any, str]] = {
            "idle":    (st.info,    "⏸ Inactivo"),
            "running": (st.info,    "🔄 En ejecución..."),
            "done":    (st.success, "✅ Proceso completado"),
            "error":   (st.error,   "❌ Proceso con error"),
        }
        fn, lbl = _smap.get(status, (st.info, status))
        fn(lbl)
        log_lines: list[str] = data.get("log", [])
        if log_lines:
            st.markdown(
                '<div class="sec-title">Log reciente (últimas 25 líneas)</div>',
                unsafe_allow_html=True,
            )
            st.code("\n".join(log_lines), language="text")
        else:
            st.caption("Sin entradas en el log aún.")
        if auto and status == "running":
            time.sleep(3)
            st.rerun()
    except Exception as exc:
        st.error(f"No se puede conectar a la API: {exc}")

    st.markdown(
        '<hr style="border:none;border-top:1px solid #E0E0E0;margin:24px 0 12px">'
        '<div class="sec-title" style="margin-top:0">👥 Usuarios del sistema</div>',
        unsafe_allow_html=True,
    )
    _role_color = {
        "admin":      "#C8A951",
        "supervisor": "#5B8DB8",
        "consultor":  "#4CAF50",
    }
    for usuario, info in _USERS.items():
        c1, c2, c3 = st.columns([3, 2, 1])
        with c1:
            st.markdown(
                f'<div style="color:#1A1A1A"><strong>{html.escape(info["nombre"])}'
                f"</strong><br>"
                f'<code style="font-size:12px">{html.escape(usuario)}</code></div>',
                unsafe_allow_html=True,
            )
        with c2:
            rl = info["rol"]
            color = _role_color.get(rl, "#999")
            st.markdown(
                f'<span style="color:{color};font-weight:600">'
                f"{_ROLE_LABEL.get(rl, rl)}</span>",
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                '<span style="color:#27ae60;font-weight:600">✓ Activo</span>',
                unsafe_allow_html=True,
            )
        st.divider()

    st.info(
        "Gestión completa de usuarios (agregar / desactivar) disponible "
        "en V1.1 con base de datos integrada."
    )


# ── Router ─────────────────────────────────────────────────────────────────────
_PAGE_MAP: dict[str, Any] = {
    "home":          _page_home,
    "nueva_consulta": _page_nueva_consulta,
    "resultados":    _page_resultados,
    "historial":     _page_historial,
    "sistema":       _page_sistema,
}

_current = st.session_state.get("current_page", "home")
if _current in _PAGE_GUARD and role not in _PAGE_GUARD[_current]:
    st.error("⛔ No tiene permisos para acceder a esta página.")
else:
    _fn = _PAGE_MAP.get(_current)
    if _fn:
        _fn()
    else:
        st.error("Página no encontrada.")
