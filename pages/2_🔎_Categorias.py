# ============================================================
#  2_🔎_Categorias.py — Explorador de Categorias
#  Entra em cada categoria e destrincha o gasto de verdade.
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st

from auth import exigir_login
exigir_login()

import re
import pandas as pd
import plotly.graph_objects as go

from config import DESPESAS_FILE, RECEITAS_FILE, MESES_PT
from utils import esc, configurar_pagina, cabecalho_pagina, inicializar_dados, ler_csv, formatar_moeda

configurar_pagina("Categorias", icone="🔎")
inicializar_dados()

ICE, AURORA, RECEITA, DESPESA = "#4FE3FF", "#39E0A6", "#4AA8FF", "#FF5C7A"
ARCTIC = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#93A2C4", family="Inter", size=12),
    xaxis=dict(gridcolor="#16223a", linecolor="#1E2942", zeroline=False),
    yaxis=dict(gridcolor="#16223a", linecolor="#1E2942", zeroline=False),
    margin=dict(l=6, r=6, t=10, b=6),
)

st.markdown("""
<div class="thesis">
  <div class="eyebrow">Explorador</div>
  <div class="big" style="font-size:clamp(26px,4vw,40px)">O que tem <em class="pos">dentro</em> de cada categoria</div>
  <div class="trow"><span class="pill mut">Escolha uma categoria e destrinche o gasto real</span></div>
</div>
""", unsafe_allow_html=True)
st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

# ── Dados ────────────────────────────────────────────────────
df_d = ler_csv(DESPESAS_FILE)
df_r = ler_csv(RECEITAS_FILE)
# Macro: exclui os gastos semanais (ferramenta à parte)
if not df_d.empty and "fonte" in df_d.columns:
    df_d = df_d[df_d["fonte"].astype(str) != "Semanal"].copy()

# ── Filtros ──────────────────────────────────────────────────
f1, f2, f3 = st.columns([1.2, 1, 1])
with f1:
    tipo = st.radio("Tipo:", ["💸 Despesas", "💰 Receitas"], horizontal=True, key="cat_tipo")
base = df_d if "💸" in tipo else df_r
cor  = DESPESA if "💸" in tipo else RECEITA
if base.empty:
    st.info("Sem dados.")
    st.stop()
base = base.copy()
base["valor"]   = pd.to_numeric(base["valor"], errors="coerce").fillna(0)
base["data_dt"] = pd.to_datetime(base["data"], errors="coerce") if "data_dt" not in base.columns else base["data_dt"]
with f2:
    anos = sorted(base["data_dt"].dt.year.dropna().astype(int).unique().tolist(), reverse=True)
    ano = st.selectbox("Ano:", ["Todos"] + anos, key="cat_ano")
with f3:
    mes = st.selectbox("Mês:", [0] + list(range(1, 13)),
                       format_func=lambda m: "Todos" if m == 0 else MESES_PT[m-1], key="cat_mes")

d = base.copy()
if ano != "Todos": d = d[d["data_dt"].dt.year == int(ano)]
if mes > 0:        d = d[d["data_dt"].dt.month == mes]
if d.empty:
    st.info("Nenhum lançamento nesse período.")
    st.stop()

# ── Overview: todas as categorias ranqueadas ─────────────────
por_cat = d.groupby("categoria")["valor"].sum().sort_values(ascending=False)
total_geral = por_cat.sum()

st.markdown('<div class="p-title"><span class="tbar"></span> Todas as categorias</div>', unsafe_allow_html=True)
maxv = por_cat.max() or 1
linhas = ""
for c, v in por_cat.head(20).items():
    pct = v / total_geral * 100 if total_geral else 0
    linhas += (f'<div><div class="c-top"><span class="c-name">{esc(c)}</span>'
               f'<span class="c-val num">{formatar_moeda(v)} · {pct:.0f}%</span></div>'
               f'<div class="track"><div class="fill" style="width:{v/maxv*100:.0f}%;'
               f'background:linear-gradient(90deg,{cor},{cor}bb)"></div></div></div>')
st.markdown(f'<div class="cat">{linhas}</div>', unsafe_allow_html=True)

st.divider()

# ── Detalhe de uma categoria ─────────────────────────────────
opcoes = [f"{c}  ·  {formatar_moeda(v)}" for c, v in por_cat.items()]
mapa_op = {f"{c}  ·  {formatar_moeda(v)}": c for c, v in por_cat.items()}
escolha = st.selectbox("🔎 Destrinchar categoria:", opcoes, key="cat_sel")
cat_sel = mapa_op[escolha]
dc = d[d["categoria"].astype(str) == cat_sel].copy()

# KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total", formatar_moeda(dc["valor"].sum()), f"{len(dc)} lançamentos")
k2.metric("Ticket médio", formatar_moeda(dc["valor"].mean() if len(dc) else 0))
k3.metric("Maior", formatar_moeda(dc["valor"].max() if len(dc) else 0))
k4.metric("% do total", f"{dc['valor'].sum()/total_geral*100:.1f}%" if total_geral else "—")

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
col_a, col_b = st.columns([1, 1])

# Evolução mensal da categoria
with col_a:
    st.markdown('<div class="p-title"><span class="tbar"></span> Evolução mensal</div>', unsafe_allow_html=True)
    evo = dc.groupby(dc["data_dt"].dt.to_period("M"))["valor"].sum()
    if not evo.empty:
        labels = [f"{MESES_PT[p.month-1][:3]}/{str(p.year)[2:]}" for p in evo.index]
        fig = go.Figure(go.Bar(x=labels, y=evo.values, marker_color=cor, opacity=0.9,
                               hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>"))
        fig.update_layout(**ARCTIC, height=280, showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key="cat_evo")

# Top estabelecimentos (o gasto real)
with col_b:
    st.markdown('<div class="p-title"><span class="tbar"></span> Estabelecimentos</div>', unsafe_allow_html=True)
    est = dc.groupby("descricao")["valor"].agg(total="sum", n="count").sort_values("total", ascending=False).head(10)
    if not est.empty:
        mx = est["total"].max() or 1
        li = ""
        for nome, r in est.iterrows():
            li += (f'<div><div class="c-top"><span class="c-name">{esc(str(nome)[:34])}</span>'
                   f'<span class="c-val num">{formatar_moeda(r["total"])} ({int(r["n"])}x)</span></div>'
                   f'<div class="track"><div class="fill" style="width:{r["total"]/mx*100:.0f}%;'
                   f'background:linear-gradient(90deg,{cor},{cor}bb)"></div></div></div>')
        st.markdown(f'<div class="cat">{li}</div>', unsafe_allow_html=True)

# Por fonte
if "fonte" in dc.columns:
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    fontes = dc.groupby("fonte")["valor"].sum().sort_values(ascending=False)
    chips = " · ".join(f"**{f}**: {formatar_moeda(v)}" for f, v in fontes.items())
    st.caption(f"Por fonte → {chips}")

# Tabela completa
st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
st.markdown(f'<div class="p-title"><span class="tbar"></span> Todos os {len(dc)} lançamentos de "{cat_sel}"</div>',
            unsafe_allow_html=True)
cols = [c for c in ["data", "descricao", "valor", "status", "fonte", "banco", "forma_pagamento"] if c in dc.columns]
tab = dc.sort_values("data_dt", ascending=False)[cols].copy()
tab["data"] = dc.sort_values("data_dt", ascending=False)["data_dt"].dt.strftime("%d/%m/%Y").values
tab["valor"] = tab["valor"].apply(formatar_moeda)
_ren = {"data": "Data", "descricao": "Descrição", "valor": "Valor", "status": "Status",
        "fonte": "Fonte", "banco": "Banco", "forma_pagamento": "Forma"}
tab.columns = [_ren.get(c, c) for c in cols]
st.dataframe(tab, use_container_width=True, hide_index=True, height=420)
