"""Aparência do painel. Preferência apenas da sessão, sem gravar dados financeiros."""

from pathlib import Path

import streamlit as st


ROOT = Path(__file__).parent
OPCOES_TEMA = ("Escuro", "Claro")


def tema_atual() -> str:
    return st.session_state.get("aparencia", "Escuro")


def _guardar_tema() -> None:
    st.session_state["aparencia"] = st.session_state["_aparencia_widget"]


def aplicar_tema() -> None:
    # O estado de widgets pode ser limpo ao navegar entre páginas; a chave sem
    # widget preserva a escolha durante toda a sessão de Bruno ou Pri.
    if "_aparencia_widget" not in st.session_state:
        st.session_state["_aparencia_widget"] = tema_atual()
    st.sidebar.radio("Aparência", OPCOES_TEMA, key="_aparencia_widget",
                     horizontal=True, on_change=_guardar_tema)
    for nome in ("style.css", "style-light.css"):
        if nome == "style-light.css" and tema_atual() != "Claro":
            continue
        caminho = ROOT / nome
        if caminho.exists():
            st.markdown(f"<style>{caminho.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    with st.container(key="periguinhos_nav"):
        destinos = (
            ("app.py", "Visão geral", "🏠"),
            ("pages/1_📆_Gastos_Semanais.py", "Semana", "📆"),
            ("pages/2_🔎_Categorias.py", "Categorias", "🔎"),
            ("pages/3_🌴_Projeto_Ferias.py", "Férias", "🌴"),
            ("pages/4_👴👵_Aposentadoria.py", "Futuro", "👴"),
            ("pages/5_⚙️_Configuracoes.py", "Ajustes", "⚙️"),
        )
        for coluna, (caminho, rotulo, icone) in zip(st.columns(len(destinos)), destinos):
            with coluna:
                st.page_link(caminho, label=rotulo, icon=icone)


def paleta_graficos(tema: str) -> dict:
    """Cores de séries e eixos compartilhadas entre as páginas."""
    if tema == "Claro":
        return {
            "receita": "#176b57", "despesa": "#b34f46", "saldo": "#176b57",
            "destaque": "#176b57", "texto": "#586960", "grade": "#d6ddd2",
            "fundo": "rgba(0,0,0,0)", "receita_fill": "rgba(23,107,87,0.10)",
            "despesa_fill": "rgba(179,79,70,0.10)",
        }
    return {
        "receita": "#4AA8FF", "despesa": "#FF5C7A", "saldo": "#39E0A6",
        "destaque": "#4FE3FF", "texto": "#93A2C4", "grade": "#1E2942",
        "fundo": "rgba(0,0,0,0)", "receita_fill": "rgba(74,168,255,0.14)",
        "despesa_fill": "rgba(255,92,122,0.12)",
    }


def estilizar_figura(fig) -> None:
    """Aplica contraste do tema a um gráfico Plotly sem alterar seus dados."""
    cores = paleta_graficos(tema_atual())
    fig.update_layout(
        paper_bgcolor=cores["fundo"], plot_bgcolor=cores["fundo"],
        font_color=cores["texto"], legend_bgcolor=cores["fundo"],
        legend_font_color=cores["texto"],
        xaxis_gridcolor=cores["grade"], yaxis_gridcolor=cores["grade"],
    )
