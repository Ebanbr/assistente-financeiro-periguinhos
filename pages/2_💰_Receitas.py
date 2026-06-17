# ============================================================
#  2_💰_Receitas.py — Dashboard de Receitas
# ============================================================

import re
import streamlit as st

from auth import exigir_login
exigir_login()
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

from config import RECEITAS_FILE, MESES_PT
from utils import configurar_pagina, cabecalho_pagina, inicializar_dados, ler_csv, formatar_moeda

configurar_pagina("Receitas", icone="💰")
inicializar_dados()
cabecalho_pagina(titulo="Receitas", subtitulo="Acompanhe suas entradas de dinheiro", icone="💰")
st.markdown("---")

DARK = dict(paper_bgcolor="#161B22", plot_bgcolor="#161B22",
            font=dict(color="#8BAFC9", family="Inter", size=12),
            xaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
            yaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
            margin=dict(l=10, r=10, t=40, b=10))

df = ler_csv(RECEITAS_FILE)
if df.empty:
    st.info("📭 Sem receitas ainda")
    st.stop()

df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
if "data_dt" not in df.columns:
    df["data_dt"] = pd.to_datetime(df["data"], errors="coerce")

# ── Filtros ──────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    mes_f = st.selectbox("Mês:", [0]+list(range(1,13)), index=0,
                         format_func=lambda m: "Todos" if m==0 else MESES_PT[m-1])
with col_f2:
    anos = sorted(df["data_dt"].dt.year.dropna().astype(int).unique().tolist(), reverse=True)
    ano_f = st.selectbox("Ano:", ["Todos"]+anos)
with col_f3:
    categoria_f = st.selectbox("Categoria:", ["Todas"]+sorted(df["categoria"].dropna().unique().tolist()))

df_f = df.copy()
if mes_f > 0:       df_f = df_f[df_f["data_dt"].dt.month == mes_f]
if ano_f != "Todos": df_f = df_f[df_f["data_dt"].dt.year == int(ano_f)]
if categoria_f != "Todas": df_f = df_f[df_f["categoria"] == categoria_f]

# ── KPIs ─────────────────────────────────────────────────────
total = df_f["valor"].sum()
media = df_f["valor"].mean() if len(df_f) > 0 else 0
maior = df_f["valor"].max() if len(df_f) > 0 else 0

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"""<div class="card-receita">
        <div class="card-label">💰 Total Receitas</div>
        <div class="card-value-receita">{formatar_moeda(total)}</div>
        <div class="card-sub">{len(df_f)} lançamentos</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="card-neutro">
        <div class="card-label">📊 Média</div>
        <div class="card-value-neutro">{formatar_moeda(media)}</div>
        <div class="card-sub">por lançamento</div>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div class="card-neutro">
        <div class="card-label">📈 Maior Entrada</div>
        <div class="card-value-neutro">{formatar_moeda(maior)}</div>
        <div class="card-sub">&nbsp;</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
st.divider()

# ── Gráficos ─────────────────────────────────────────────────
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.markdown("### Por Categoria")
    if not df_f.empty:
        # Limpa categorias vazias ou só com emoji
        df_cat = df_f.copy()
        df_cat["_cat_limpa"] = df_cat["categoria"].astype(str).str.strip()
        df_cat = df_cat[df_cat["_cat_limpa"].str.len() > 1]  # remove vazios e "✅" sozinho
        if not df_cat.empty:
            por_cat = df_cat.groupby("_cat_limpa")["valor"].sum().sort_values(ascending=False).head(8)
            fig = px.pie(values=por_cat.values, names=por_cat.index, hole=0.5,
                         color_discrete_sequence=["#4A9EFF","#00C953","#FFB300","#FF4D6D","#9D4EDD","#00D4FF","#F72585","#FF6B35","#00FF87","#E040FB","#29B6F6","#FFEE58"])
            fig.update_traces(textposition="inside", textinfo="percent",
                              hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>")
            DARK_PIE = {k: v for k, v in DARK.items() if k not in ("xaxis", "yaxis", "margin")}
            fig.update_layout(height=350, **DARK_PIE,
                              legend=dict(bgcolor="#0D1B2A", bordercolor="#30363D",
                                          font=dict(color="#E6EDF3", size=11), x=1.02, y=0.5),
                              margin=dict(l=0, r=140, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

with col_g2:
    st.markdown("### Top 10 Origens de Receita")
    if not df_f.empty:
        top_desc = df_f.groupby("descricao")["valor"].sum().sort_values(ascending=True).tail(10)
        fig2 = go.Figure(go.Bar(
            x=top_desc.values, y=top_desc.index, orientation="h",
            marker=dict(color="#4A9EFF", opacity=0.85),
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
    fig3 = go.Figure(go.Scatter(
        x=evo["data_dt"], y=evo["valor"],
        name="Receitas", line=dict(color="#4A9EFF", width=2),
        fill="tozeroy", fillcolor="rgba(74,158,255,0.1)",
        hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>"
    ))
    fig3.update_layout(height=250, **DARK,
                       legend=dict(bgcolor="#0D1B2A", bordercolor="#30363D",
                                   font=dict(color="#E6EDF3")),
                       hovermode="x unified")
    st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ── Tabela completa ───────────────────────────────────────────
st.markdown("### Todas as Receitas")
if not df_f.empty:
    df_sorted = df_f.sort_values("data_dt", ascending=False).copy()
    df_sorted["data"]      = pd.to_datetime(df_sorted["data"]).dt.strftime("%d/%m/%Y")
    df_sorted["valor_fmt"] = df_sorted["valor"].apply(formatar_moeda)

    COLS_RESUMO = {
        "data":              "Data",
        "descricao":         "Descrição",
        "categoria":         "Categoria",
        "valor_fmt":         "Valor",
        "status":            "Status",
        "forma_recebimento": "Forma Recebimento",
    }
    COLS_EXTRA = {
        "fonte":      "Fonte",
        "observacao": "Observação",
        "criado_em":  "Criado em",
    }

    cols_res = [c for c in COLS_RESUMO if c in df_sorted.columns]
    cols_ext = [c for c in COLS_EXTRA  if c in df_sorted.columns]

    ver_tudo = st.toggle("🔍 Ver todas as colunas", value=False, key="toggle_receitas")

    if ver_tudo:
        cols_show = cols_res + cols_ext
        nomes = [COLS_RESUMO.get(c, COLS_EXTRA.get(c, c)) for c in cols_show]
        df_exib = df_sorted[cols_show].copy()
        df_exib.columns = nomes
    else:
        df_exib = df_sorted[cols_res].copy()
        df_exib.columns = [COLS_RESUMO[c] for c in cols_res]

    st.caption("💡 Clique no cabeçalho para ordenar" + (" · mostrando todas as colunas" if ver_tudo else ""))
    st.dataframe(df_exib, use_container_width=True, hide_index=True, height=400)

