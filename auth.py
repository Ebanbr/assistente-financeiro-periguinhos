# ============================================================
#  auth.py — Sistema de Login
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st
from pathlib import Path


def _get_usuarios() -> dict:
    try:
        if "usuarios" in st.secrets:
            return dict(st.secrets["usuarios"])
    except:
        pass
    try:
        import toml
        secrets = toml.load(Path(__file__).parent / ".streamlit" / "secrets.toml")
        return secrets.get("usuarios", {})
    except:
        pass
    return {}


def login_page():
    st.set_page_config(
        page_title="🐧 Periguinhos — Login",
        page_icon="🐧",
        layout="centered",
    )

    css_path = Path(__file__).parent / "style.css"
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    st.markdown("""
        <div style='text-align:center; padding: 2rem 0 1rem 0'>
            <div style='font-size:4rem'>🐧</div>
            <h2 style='margin:0; color:#E6EDF3'>Família Periguinhos</h2>
            <p style='color:#556878; margin-top:4px'>Assistente Financeiro Familiar</p>
        </div>
    """, unsafe_allow_html=True)

    with st.form("form_login"):
        usuario = st.selectbox("Quem é você?", ["BOo", "Pixi"])
        senha   = st.text_input("Senha:", type="password", placeholder="••••••••••")
        entrar  = st.form_submit_button("Entrar 🚀", use_container_width=True, type="primary")

    if entrar:
        usuarios = _get_usuarios()
        if usuarios.get(usuario) == senha:
            st.session_state["logado"]  = True
            st.session_state["usuario"] = usuario
            st.rerun()
        else:
            st.error("Senha incorreta. Tente novamente.")


def exigir_login():
    """Chama no início de cada página para proteger acesso."""
    if not st.session_state.get("logado"):
        st.stop()


def usuario_logado() -> str:
    return st.session_state.get("usuario", "Desconhecido")


def logout():
    for k in ["logado", "usuario"]:
        st.session_state.pop(k, None)
    st.rerun()
