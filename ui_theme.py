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
            "despesa_fill": "rgba(179,79,70,0.10)", "marcador_borda": "#ffffff",
        }
    return {
        "receita": "#4AA8FF", "despesa": "#FF5C7A", "saldo": "#39E0A6",
        "destaque": "#4FE3FF", "texto": "#93A2C4", "grade": "#1E2942",
        "fundo": "rgba(0,0,0,0)", "receita_fill": "rgba(74,168,255,0.14)",
        "despesa_fill": "rgba(255,92,122,0.12)", "marcador_borda": "#0B1020",
    }


# Paleta categórica (identidade, não ranking), validada para daltonismo nos
# dois temas: cada slot é uma categoria fixa. Ordem importa — não reordenar.
CATEGORICAS = {
    "Claro":  ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
    "Escuro": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
}
COR_OUTRAS = {"Claro": "#a8a294", "Escuro": "#4a5675"}


def cores_por_categoria(ordem_global, tema: str) -> dict:
    """{categoria: cor}. A cor segue a categoria (pela posição no ranking de
    todo o histórico), então não muda quando o filtro de período muda."""
    pal = CATEGORICAS["Claro" if tema == "Claro" else "Escuro"]
    return {str(c): pal[i] for i, c in enumerate(list(ordem_global)[:len(pal)])}


def cor_outras(tema: str) -> str:
    return COR_OUTRAS["Claro" if tema == "Claro" else "Escuro"]


def valor_curto(v: float) -> str:
    """R$ em formato curto para eixos: 'R$ 15 mil', 'R$ 1,2 mi', 'R$ 800'."""
    v = float(v)
    if abs(v) >= 1_000_000:
        n, suf = v / 1_000_000, " mi"
    elif abs(v) >= 1_000:
        n, suf = v / 1_000, " mil"
    else:
        n, suf = v, ""
    txt = f"{n:,.1f}".rstrip("0").rstrip(".") if n % 1 else f"{n:,.0f}"
    return "R$ " + txt.replace(",", "X").replace(".", ",").replace("X", ".") + suf


def eixo_reais(vmax: float, divisoes: int = 4):
    """Ticks 'redondos' de 0 até cobrir vmax: (tickvals, ticktext)."""
    vmax = float(vmax or 0)
    if vmax <= 0:
        return [0], [valor_curto(0)]
    bruto = vmax / divisoes
    ordem = 10 ** (len(str(int(bruto))) - 1)
    passo = next(m * ordem for m in (1, 2, 2.5, 5, 10) if m * ordem >= bruto)
    vals = [i * passo for i in range(int(-(-vmax // passo)) + 1)]
    return vals, [valor_curto(v) for v in vals]


def estilizar_figura(fig) -> None:
    """Aplica contraste do tema a um gráfico Plotly sem alterar seus dados."""
    cores = paleta_graficos(tema_atual())
    fig.update_layout(
        paper_bgcolor=cores["fundo"], plot_bgcolor=cores["fundo"],
        font_color=cores["texto"], legend_bgcolor=cores["fundo"],
        legend_font_color=cores["texto"],
        xaxis_gridcolor=cores["grade"], yaxis_gridcolor=cores["grade"],
        xaxis_tickfont_color=cores["texto"], yaxis_tickfont_color=cores["texto"],
    )
