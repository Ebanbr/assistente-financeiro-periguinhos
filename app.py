# ============================================================
#  app.py — Dashboard Principal
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
from pathlib import Path

from config import APP_NOME, APP_EMOJI, DESPESAS_FILE, RECEITAS_FILE, MESES_PT
from utils import ler_csv, formatar_moeda
from auth import login_page, usuario_logado, logout

# ── Login ─────────────────────────────────────────────────────
if not st.session_state.get("logado"):
    login_page()
    st.stop()

# ── Config da página ─────────────────────────────────────────
st.set_page_config(
    page_title=f"{APP_EMOJI} {APP_NOME}",
    page_icon=APP_EMOJI,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ──────────────────────────────────────────────────────
css_path = Path(__file__).parent / "style.css"
if css_path.exists():
    with open(css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────
st.sidebar.markdown(f"## {APP_EMOJI} {APP_NOME}")
st.sidebar.markdown("<small style='color:#556878'>Assistente Financeiro Familiar</small>", unsafe_allow_html=True)

_u = usuario_logado()
_emoji_u = "🧔" if _u == "BOo" else "👩"
st.sidebar.markdown(f"<small style='color:#4A9EFF'>{_emoji_u} Olá, <b>{_u}</b>!</small>", unsafe_allow_html=True)
if st.sidebar.button("🚪 Sair", use_container_width=True):
    logout()

st.sidebar.divider()

# ── Carregar dados ───────────────────────────────────────────
df_d = ler_csv(DESPESAS_FILE)
df_r = ler_csv(RECEITAS_FILE)

if not df_d.empty and "valor" in df_d.columns:
    df_d["valor"] = pd.to_numeric(df_d["valor"], errors="coerce").fillna(0)
if not df_r.empty and "valor" in df_r.columns:
    df_r["valor"] = pd.to_numeric(df_r["valor"], errors="coerce").fillna(0)

# ── Filtro de período no sidebar ─────────────────────────────
st.sidebar.markdown("### 🎛️ Filtro de Período")

anos_disponiveis = []
if not df_d.empty and "data_dt" in df_d.columns:
    anos_d = df_d["data_dt"].dt.year.dropna().astype(int).unique().tolist()
    anos_disponiveis += anos_d
if not df_r.empty and "data_dt" in df_r.columns:
    anos_r = df_r["data_dt"].dt.year.dropna().astype(int).unique().tolist()
    anos_disponiveis += anos_r

anos_disponiveis = sorted(set(anos_disponiveis), reverse=True) if anos_disponiveis else [date.today().year]

ano_sel = st.sidebar.selectbox("Ano:", ["Todos"] + anos_disponiveis)
mes_sel = st.sidebar.selectbox(
    "Mês:",
    [0] + list(range(1, 13)),
    format_func=lambda m: "Todos" if m == 0 else MESES_PT[m - 1]
)

def filtrar(df):
    if df.empty or "data_dt" not in df.columns:
        return df
    d = df.copy()
    if ano_sel != "Todos":
        d = d[d["data_dt"].dt.year == int(ano_sel)]
    if mes_sel > 0:
        d = d[d["data_dt"].dt.month == mes_sel]
    return d

df_df = filtrar(df_d)
df_rf = filtrar(df_r)

total_desp = df_df["valor"].sum() if not df_df.empty and "valor" in df_df.columns else 0
total_rec  = df_rf["valor"].sum() if not df_rf.empty and "valor" in df_rf.columns else 0
saldo      = total_rec - total_desp
saldo_cor  = "#00C953" if saldo >= 0 else "#FF4D6D"
saldo_card = "card-saldo-pos" if saldo >= 0 else "card-saldo-neg"
saldo_val  = "card-value-positivo" if saldo >= 0 else "card-value-negativo"

# ── Header ───────────────────────────────────────────────────
periodo_label = f"{MESES_PT[mes_sel-1]} {ano_sel}" if mes_sel > 0 and ano_sel != "Todos" else (
    str(ano_sel) if ano_sel != "Todos" else "Todo o período"
)

st.markdown(f"# {APP_EMOJI} Dashboard")
st.markdown(f"<p style='color:#556878;margin-top:-12px'>📅 {periodo_label}</p>", unsafe_allow_html=True)

# ── KPIs principais ──────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
    <div class="card-despesa">
        <div class="card-label">💸 Despesas</div>
        <div class="card-value-despesa">{formatar_moeda(total_desp)}</div>
        <div class="card-sub">{len(df_df)} lançamentos</div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="card-receita">
        <div class="card-label">💰 Receitas</div>
        <div class="card-value-receita">{formatar_moeda(total_rec)}</div>
        <div class="card-sub">{len(df_rf)} lançamentos</div>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="{saldo_card}">
        <div class="card-label">💵 Saldo</div>
        <div class="{saldo_val}">{formatar_moeda(saldo)}</div>
        <div class="card-sub">{'✅ Positivo' if saldo >= 0 else '⚠️ Negativo'}</div>
    </div>""", unsafe_allow_html=True)

with c4:
    maior = df_df["valor"].max() if not df_df.empty and "valor" in df_df.columns else 0
    desc_maior = df_df.loc[df_df["valor"].idxmax(), "descricao"] if not df_df.empty and "valor" in df_df.columns and maior > 0 else "—"
    st.markdown(f"""
    <div class="card-neutro">
        <div class="card-label">📈 Maior Gasto</div>
        <div class="card-value-neutro">{formatar_moeda(maior)}</div>
        <div class="card-sub">{str(desc_maior)[:25]}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
st.divider()

# ── Gráficos ─────────────────────────────────────────────────
col_g1, col_g2 = st.columns([3, 2])

with col_g1:
    st.markdown("### 📊 Despesas vs Receitas por Mês")

    df_mensal_d = pd.DataFrame()
    df_mensal_r = pd.DataFrame()

    if not df_d.empty and "data_dt" in df_d.columns:
        d_temp = df_d.copy()
        if ano_sel != "Todos":
            d_temp = d_temp[d_temp["data_dt"].dt.year == int(ano_sel)]
        df_mensal_d = d_temp.groupby(d_temp["data_dt"].dt.month)["valor"].sum().reset_index()
        df_mensal_d.columns = ["mes", "despesas"]

    if not df_r.empty and "data_dt" in df_r.columns:
        r_temp = df_r.copy()
        if ano_sel != "Todos":
            r_temp = r_temp[r_temp["data_dt"].dt.year == int(ano_sel)]
        df_mensal_r = r_temp.groupby(r_temp["data_dt"].dt.month)["valor"].sum().reset_index()
        df_mensal_r.columns = ["mes", "receitas"]

    if not df_mensal_d.empty or not df_mensal_r.empty:
        df_mensal = pd.DataFrame({"mes": range(1, 13)})
        if not df_mensal_d.empty:
            df_mensal = df_mensal.merge(df_mensal_d, on="mes", how="left")
        else:
            df_mensal["despesas"] = 0
        if not df_mensal_r.empty:
            df_mensal = df_mensal.merge(df_mensal_r, on="mes", how="left")
        else:
            df_mensal["receitas"] = 0
        df_mensal = df_mensal.fillna(0)
        df_mensal["mes_nome"] = df_mensal["mes"].apply(lambda m: MESES_PT[m-1][:3])

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Despesas", x=df_mensal["mes_nome"], y=df_mensal["despesas"],
            marker_color="#FF4D6D", opacity=0.85,
            hovertemplate="<b>%{x}</b><br>Despesas: R$ %{y:,.2f}<extra></extra>"
        ))
        fig.add_trace(go.Bar(
            name="Receitas", x=df_mensal["mes_nome"], y=df_mensal["receitas"],
            marker_color="#4A9EFF", opacity=0.85,
            hovertemplate="<b>%{x}</b><br>Receitas: R$ %{y:,.2f}<extra></extra>"
        ))
        fig.update_layout(
            barmode="group", height=320,
            paper_bgcolor="#161B22", plot_bgcolor="#161B22",
            font=dict(color="#8BAFC9", family="Inter", size=12),
            legend=dict(
                bgcolor="#0D1B2A", bordercolor="#30363D", borderwidth=1,
                orientation="h", x=0, y=1.12,
                font=dict(color="#E6EDF3", size=12)
            ),
            xaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
            yaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados para o período selecionado.")

with col_g2:
    st.markdown("### 🍕 Despesas por Categoria")

    if not df_df.empty and "categoria" in df_df.columns:
        por_cat = df_df.groupby("categoria")["valor"].sum().sort_values(ascending=False).head(8)
        # Remove emojis dos nomes para a legenda não quebrar
        import re
        nomes_limpos = [re.sub(r'[^\x00-\x7FÀ-ɏ\s]', '', str(n)).strip() for n in por_cat.index]

        fig2 = px.pie(
            values=por_cat.values,
            names=nomes_limpos,
            hole=0.5,
            color_discrete_sequence=["#FF4D6D","#FFB300","#9D4EDD","#FF6B35","#4A9EFF","#00C953","#F72585","#00D4FF","#FFEE58","#E040FB","#29B6F6","#FF8FA3"]
        )
        fig2.update_traces(
            textposition="inside",
            textinfo="percent",
            hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>"
        )
        fig2.update_layout(
            height=320,
            paper_bgcolor="#161B22",
            font=dict(color="#E6EDF3", family="Inter", size=11),
            legend=dict(
                bgcolor="#0D1B2A", bordercolor="#30363D",
                font=dict(color="#E6EDF3", size=11),
                orientation="v", x=1.02, y=0.5
            ),
            margin=dict(l=0, r=120, t=10, b=10),
            showlegend=True,
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Sem despesas no período.")

st.divider()

# ── Linha temporal ───────────────────────────────────────────
st.markdown("### 📈 Evolução do Saldo ao Longo do Tempo")

if not df_d.empty and not df_r.empty and "data_dt" in df_d.columns and "data_dt" in df_r.columns:
    d_temp = df_d if ano_sel == "Todos" else df_d[df_d["data_dt"].dt.year == int(ano_sel)]
    r_temp = df_r if ano_sel == "Todos" else df_r[df_r["data_dt"].dt.year == int(ano_sel)]

    desp_mes = d_temp.groupby(d_temp["data_dt"].dt.to_period("M"))["valor"].sum()
    rec_mes  = r_temp.groupby(r_temp["data_dt"].dt.to_period("M"))["valor"].sum()

    df_evolucao = pd.DataFrame({"despesas": desp_mes, "receitas": rec_mes}).fillna(0)
    df_evolucao["saldo"] = df_evolucao["receitas"] - df_evolucao["despesas"]
    df_evolucao.index = df_evolucao.index.astype(str)

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=df_evolucao.index, y=df_evolucao["receitas"],
        name="Receitas", line=dict(color="#4A9EFF", width=2),
        fill="tozeroy", fillcolor="rgba(74,158,255,0.08)",
        hovertemplate="<b>%{x}</b><br>Receitas: R$ %{y:,.2f}<extra></extra>"
    ))
    fig3.add_trace(go.Scatter(
        x=df_evolucao.index, y=df_evolucao["despesas"],
        name="Despesas", line=dict(color="#FF4D6D", width=2),
        fill="tozeroy", fillcolor="rgba(255,77,109,0.08)",
        hovertemplate="<b>%{x}</b><br>Despesas: R$ %{y:,.2f}<extra></extra>"
    ))
    fig3.add_trace(go.Scatter(
        x=df_evolucao.index, y=df_evolucao["saldo"],
        name="Saldo", line=dict(color="#00C953", width=2, dash="dot"),
        hovertemplate="<b>%{x}</b><br>Saldo: R$ %{y:,.2f}<extra></extra>"
    ))
    fig3.update_layout(
        height=280,
        paper_bgcolor="#161B22", plot_bgcolor="#161B22",
        font=dict(color="#8BAFC9", family="Inter", size=12),
        legend=dict(
            bgcolor="#0D1B2A", bordercolor="#30363D", borderwidth=1,
            orientation="h", x=0, y=1.15,
            font=dict(color="#E6EDF3", size=12)
        ),
        xaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
        yaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
    )
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("Importe dados para ver a evolução temporal.")

st.divider()

# ── Top 5 maiores gastos ──────────────────────────────────────
col_t1, col_t2 = st.columns(2)

with col_t1:
    st.markdown("### 🔴 Top 10 Maiores Despesas")
    if not df_df.empty:
        top_d = df_df.nlargest(10, "valor")[["data","descricao","categoria","valor"]].copy()
        top_d["data"]  = pd.to_datetime(top_d["data"]).dt.strftime("%d/%m/%Y")
        top_d["valor"] = top_d["valor"].apply(formatar_moeda)
        top_d.columns  = ["Data","Descrição","Categoria","Valor"]
        st.dataframe(top_d, use_container_width=True, hide_index=True, height=320)
    else:
        st.info("Sem despesas no período.")

with col_t2:
    st.markdown("### 🔵 Top 10 Maiores Receitas")
    if not df_rf.empty:
        top_r = df_rf.nlargest(10, "valor")[["data","descricao","categoria","valor"]].copy()
        top_r["data"]  = pd.to_datetime(top_r["data"]).dt.strftime("%d/%m/%Y")
        top_r["valor"] = top_r["valor"].apply(formatar_moeda)
        top_r.columns  = ["Data","Descrição","Categoria","Valor"]
        st.dataframe(top_r, use_container_width=True, hide_index=True, height=320)
    else:
        st.info("Sem receitas no período.")

# ── Footer ───────────────────────────────────────────────────
st.divider()
st.markdown(
    "<p style='text-align:center;color:#30363D;font-size:0.75rem'>"
    f"🐧 {APP_NOME} · Versão 3.0 · Desenvolvido com ❤️"
    "</p>",
    unsafe_allow_html=True
)
