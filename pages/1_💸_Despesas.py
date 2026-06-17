# ============================================================
#  1_💸_Despesas.py — Dashboard de Despesas
# ============================================================

import re
import streamlit as st

from auth import exigir_login
exigir_login()
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

from config import DESPESAS_FILE, MESES_PT
from utils import configurar_pagina, cabecalho_pagina, inicializar_dados, ler_csv, formatar_moeda

configurar_pagina("Despesas", icone="💸")
inicializar_dados()
cabecalho_pagina(titulo="Despesas", subtitulo="Analise todos os seus gastos", icone="💸")
st.markdown("---")

DARK = dict(paper_bgcolor="#161B22", plot_bgcolor="#161B22",
            font=dict(color="#8BAFC9", family="Inter", size=12),
            xaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
            yaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
            margin=dict(l=10, r=10, t=40, b=10))

df = ler_csv(DESPESAS_FILE)
if df.empty:
    st.info("📭 Sem despesas ainda")
    st.stop()

df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
if "data_dt" not in df.columns:
    df["data_dt"] = pd.to_datetime(df["data"], errors="coerce")

# ── Filtros ──────────────────────────────────────────────────
col_f1, col_f2, col_f3, col_f4 = st.columns(4)
with col_f1:
    mes_f = st.selectbox("Mês:", [0]+list(range(1,13)), index=0,
                         format_func=lambda m: "Todos" if m==0 else MESES_PT[m-1])
with col_f2:
    anos = sorted(df["data_dt"].dt.year.dropna().astype(int).unique().tolist(), reverse=True)
    ano_f = st.selectbox("Ano:", ["Todos"]+anos)
with col_f3:
    categoria_f = st.selectbox("Categoria:", ["Todas"]+sorted(df["categoria"].dropna().unique().tolist()))
with col_f4:
    fontes = ["Todas"] + sorted(df["fonte"].dropna().unique().tolist()) if "fonte" in df.columns else ["Todas"]
    fonte_f = st.selectbox("Fonte:", fontes)

df_f = df.copy()
if mes_f > 0:           df_f = df_f[df_f["data_dt"].dt.month == mes_f]
if ano_f != "Todos":    df_f = df_f[df_f["data_dt"].dt.year == int(ano_f)]
if categoria_f != "Todas": df_f = df_f[df_f["categoria"] == categoria_f]
if fonte_f != "Todas" and "fonte" in df_f.columns:
    df_f = df_f[df_f["fonte"] == fonte_f]

# ── KPIs ─────────────────────────────────────────────────────
total = df_f["valor"].sum()
media = df_f["valor"].mean() if len(df_f) > 0 else 0
maior = df_f["valor"].max() if len(df_f) > 0 else 0
desc_maior = df_f.loc[df_f["valor"].idxmax(), "descricao"] if len(df_f) > 0 and maior > 0 else "—"

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""<div class="card-despesa">
        <div class="card-label">💸 Total Despesas</div>
        <div class="card-value-despesa">{formatar_moeda(total)}</div>
        <div class="card-sub">{len(df_f)} lançamentos</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="card-neutro">
        <div class="card-label">📊 Ticket Médio</div>
        <div class="card-value-neutro">{formatar_moeda(media)}</div>
        <div class="card-sub">por lançamento</div>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div class="card-despesa">
        <div class="card-label">📈 Maior Gasto</div>
        <div class="card-value-despesa">{formatar_moeda(maior)}</div>
        <div class="card-sub">{str(desc_maior)[:22]}</div>
    </div>""", unsafe_allow_html=True)
with c4:
    n_cats = df_f["categoria"].nunique() if not df_f.empty else 0
    st.markdown(f"""<div class="card-neutro">
        <div class="card-label">🏷️ Categorias</div>
        <div class="card-value-neutro">{n_cats}</div>
        <div class="card-sub">no período</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
st.divider()

# ── Gráficos ─────────────────────────────────────────────────
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.markdown("### Por Categoria")
    if not df_f.empty:
        df_cat = df_f.copy()
        df_cat["_cat_limpa"] = df_cat["categoria"].astype(str).str.strip()
        df_cat = df_cat[df_cat["_cat_limpa"].str.len() > 1]
        if not df_cat.empty:
            por_cat = df_cat.groupby("_cat_limpa")["valor"].sum().sort_values(ascending=False).head(8)
            fig = px.pie(values=por_cat.values, names=por_cat.index, hole=0.5,
                         color_discrete_sequence=["#FF4D6D","#FFB300","#9D4EDD","#FF6B35","#4A9EFF","#00C953","#F72585","#00D4FF","#FFEE58","#E040FB","#29B6F6","#FF8FA3"])
            fig.update_traces(textposition="inside", textinfo="percent",
                              hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>")
            fig.update_layout(height=350,
                              paper_bgcolor="#161B22", plot_bgcolor="#161B22",
                              font=dict(color="#8BAFC9", family="Inter", size=11),
                              legend=dict(bgcolor="#0D1B2A", bordercolor="#30363D",
                                          font=dict(color="#E6EDF3", size=11), x=1.02, y=0.5),
                              margin=dict(l=0, r=140, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

with col_g2:
    st.markdown("### Top Categorias")
    if not df_f.empty:
        top_cat = df_f.groupby("categoria")["valor"].sum().sort_values(ascending=True).tail(8)
        nomes_b = [re.sub(r'[^\x00-\x7FÀ-ɏ\s]', '', str(n)).strip() for n in top_cat.index]
        fig2 = go.Figure(go.Bar(
            x=top_cat.values, y=nomes_b, orientation="h",
            marker=dict(color="#FF4D6D", opacity=0.85),
            hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>"
        ))
        fig2.update_layout(height=350, **DARK)
        st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── Evolução mensal ───────────────────────────────────────────
st.markdown("### Evolução Mensal")
if not df_f.empty:
    evo = df_f.groupby(df_f["data_dt"].dt.to_period("M"))["valor"].sum().reset_index()
    evo["data_dt"] = evo["data_dt"].astype(str)
    fig3 = go.Figure(go.Bar(
        x=evo["data_dt"], y=evo["valor"],
        marker_color="#FF4D6D", opacity=0.85,
        hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>"
    ))
    fig3.update_layout(height=250, **DARK, hovermode="x unified")
    st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ── Tabela completa com ordenação ────────────────────────────
st.markdown("### Todos os Lançamentos")
st.caption("💡 Clique no cabeçalho da coluna para ordenar")
if not df_f.empty:
    cols = ["data","descricao","categoria","valor","status"]
    if "fonte" in df_f.columns: cols.append("fonte")
    if "cartao" in df_f.columns: cols.append("cartao")
    df_exib = df_f.sort_values("data_dt", ascending=False)[cols].copy()
    df_exib["data"]  = pd.to_datetime(df_exib["data"]).dt.strftime("%d/%m/%Y")
    df_exib["valor"] = df_exib["valor"].apply(formatar_moeda)
    nomes_col = ["Data","Descrição","Categoria","Valor","Status"]
    if "fonte" in cols:  nomes_col.append("Fonte")
    if "cartao" in cols: nomes_col.append("Cartão")
    df_exib.columns = nomes_col
    st.dataframe(df_exib, use_container_width=True, hide_index=True, height=450)

