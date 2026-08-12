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

    import time
    MAX_TENTATIVAS = 5          # (#9) trava após 5 erros
    BLOQUEIO_SEG   = 300        # 5 min de cooldown

    _bloq_ate = st.session_state.get("_login_bloqueado_ate", 0)
    _agora = time.time()
    if _agora < _bloq_ate:
        st.error(f"🔒 Muitas tentativas. Tente de novo em {int(_bloq_ate - _agora)}s.")
        return

    with st.form("form_login"):
        usuario = st.selectbox("Quem é você?", ["BOo", "Pixi"])
        senha   = st.text_input("Senha:", type="password", placeholder="••••••••••")
        entrar  = st.form_submit_button("Entrar 🚀", use_container_width=True, type="primary")

    if entrar:
        usuarios = _get_usuarios()
        # comparação em tempo (quase) constante, evita duas senhas iguais entre usuários
        import hmac
        esperado = str(usuarios.get(usuario, ""))
        if esperado and hmac.compare_digest(esperado, str(senha)):
            st.session_state["logado"]  = True
            st.session_state["usuario"] = usuario
            st.session_state["_login_ts"] = _agora
            st.session_state["_login_tentativas"] = 0
            st.rerun()
        else:
            n = st.session_state.get("_login_tentativas", 0) + 1
            st.session_state["_login_tentativas"] = n
            if n >= MAX_TENTATIVAS:
                st.session_state["_login_bloqueado_ate"] = _agora + BLOQUEIO_SEG
                st.error(f"🔒 {n} tentativas erradas — bloqueado por {BLOQUEIO_SEG//60} min.")
            else:
                st.error(f"Senha incorreta ({n}/{MAX_TENTATIVAS} tentativas).")


SESSAO_MAX_SEG = 12 * 3600   # (#9) sessão expira em 12h

def exigir_login():
    """Chama no início de cada página para proteger acesso."""
    import time
    if not st.session_state.get("logado"):
        st.stop()
    # expiração de sessão
    ts = st.session_state.get("_login_ts", 0)
    if ts and (time.time() - ts) > SESSAO_MAX_SEG:
        for k in ["logado", "usuario", "_login_ts"]:
            st.session_state.pop(k, None)
        st.warning("Sua sessão expirou. Faça login novamente.")
        st.stop()


def usuario_logado() -> str:
    return st.session_state.get("usuario", "Desconhecido")


def logout():
    for k in ["logado", "usuario"]:
        st.session_state.pop(k, None)
    st.rerun()
