"""Login UI module — AutomatizaciónV1."""
from __future__ import annotations

import streamlit as st

_USERS: dict[str, dict[str, str]] = {
    "franklin.rojas": {
        "password": "Risk2026*",
        "rol": "admin",
        "nombre": "Franklin Alexander Rojas Moreno",
    },
    "edward.paniagua": {
        "password": "Risk2026*",
        "rol": "supervisor",
        "nombre": "Edward Enrique Paniagua Serna",
    },
    "consultor": {
        "password": "Consul2026*",
        "rol": "consultor",
        "nombre": "Consultor RiskGC",
    },
}

_CSS = """<style>
.stApp{background-color:#1B2A4A!important}
[data-testid="stHeader"]{background:transparent!important}
#MainMenu,footer,header{visibility:hidden}
.lg-top{
    background:white;border-radius:12px 12px 0 0;
    padding:36px 36px 16px;text-align:center;
}
.lg-mid{
    background:white;padding:4px 20px;
}
.lg-err{
    background:white;padding:0 20px 4px;
}
.lg-bot{
    background:white;border-radius:0 0 12px 12px;
    padding:8px 36px 28px;text-align:center;
    color:#aaa;font-size:12px;
}
[data-testid="stForm"]{
    background:white!important;padding:4px 20px!important;
    border:none!important;box-shadow:none!important;border-radius:0!important;
}
[data-testid="stTextInput"] input{
    border-radius:8px!important;border:1.5px solid #e0e0e0!important;
    font-size:14px!important;
}
[data-testid="stTextInput"] input:focus{
    border-color:#1B2A4A!important;
    box-shadow:0 0 0 2px rgba(27,42,74,.12)!important;
}
[data-testid="stFormSubmitButton"]>button,
button[kind="primaryFormSubmit"]{
    background:#C8A951!important;color:#1B2A4A!important;
    font-weight:700!important;font-size:15px!important;
    height:50px!important;border:none!important;
    border-radius:8px!important;letter-spacing:.3px;
    margin-top:6px;
}
[data-testid="stFormSubmitButton"]>button:hover{
    background:#b8952e!important;
}
</style>"""

_TOP_HTML = """<div class="lg-top">
<div style="font-size:52px;line-height:1.2">🛡️</div>
<h2 style="color:#1B2A4A;margin:12px 0 6px;font-size:22px">AutomatizaciónV1</h2>
<p style="color:#888;font-size:13px;margin:0">
    Sistema de Consulta de Antecedentes Colombianos
</p>
<div style="height:3px;background:linear-gradient(90deg,#C8A951,#e8c96e,#C8A951);
    border-radius:2px;margin:18px 0 0"></div>
</div>"""

_BOT_HTML = """<div class="lg-bot">
AutomatizaciónV1 &copy; 2025 &mdash; Uso exclusivo corporativo
</div>"""

_ERR_HTML = """<div class="lg-err">
<div style="background:#fce4e4;color:#c0392b;padding:10px 14px;
    border-radius:8px;font-size:13px">
⚠️ Credenciales incorrectas. Verifique su usuario y contraseña.
</div>
</div>"""


def show_login() -> None:
    """Render full-page login screen and handle authentication."""
    st.markdown(_CSS, unsafe_allow_html=True)
    _, col, _ = st.columns([1.3, 2, 1.3])

    with col:
        st.markdown(_TOP_HTML, unsafe_allow_html=True)

        if st.session_state.get("_login_err"):
            st.markdown(_ERR_HTML, unsafe_allow_html=True)

        with st.form("login_form"):
            email = st.text_input(
                "Usuario", placeholder="usuario"
            )
            password = st.text_input(
                "Contraseña", type="password", placeholder="••••••••"
            )
            submitted = st.form_submit_button(
                "▶  Ingresar al Sistema",
                use_container_width=True,
                type="primary",
            )

        if submitted:
            user = _USERS.get(email.lower().strip())
            if user and user["password"] == password:
                st.session_state.pop("_login_err", None)
                st.session_state.update(
                    {
                        "authenticated": True,
                        "user_email": email.lower().strip(),
                        "user_name": user["nombre"],
                        "user_role": user["rol"],
                        "current_page": "home",
                    }
                )
                st.rerun()
            else:
                st.session_state["_login_err"] = True
                st.rerun()

        st.markdown(_BOT_HTML, unsafe_allow_html=True)
