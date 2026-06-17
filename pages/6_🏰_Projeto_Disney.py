# ============================================================
#  6_🏰_Projeto_Disney.py — Sonho da Família
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st

from auth import exigir_login
exigir_login()
import pandas as pd
import plotly.graph_objects as go
from datetime import date
from dateutil.relativedelta import relativedelta

from config import CONFIG_FILE, CORES
from utils import (
    configurar_pagina, cabecalho_pagina, inicializar_dados,
    ler_json, salvar_json, formatar_moeda, mensagem_sucesso,
)

configurar_pagina("Projeto Disney", icone="🏰")
inicializar_dados()

st.markdown(f"""
<div style="
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    padding: 2rem;
    border-radius: 16px;
    margin-bottom: 1.5rem;
    text-align: center;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    border: 1px solid rgba(255,215,0,0.3);
">
    <div style="font-size:3rem;">🏰✨</div>
    <h1 style="color:#FFD700; margin:0.5rem 0; font-size:2rem; text-shadow: 0 0 20px rgba(255,215,0,0.5);">
        Projeto Disney
    </h1>
    <p style="color:rgba(255,255,255,0.7); margin:0;">
        O sonho da Família Periguinhos — guardando cada centavo para realizar! 🐧
    </p>
</div>
""", unsafe_allow_html=True)

hoje = date.today()
config = ler_json(CONFIG_FILE)
meta_valor      = float(config.get("disney_meta_valor", 25000.0))
eco_mensal      = float(config.get("disney_economia_mensal", 500.0))
valor_atual     = float(config.get("disney_valor_atual", 0.0))

with st.expander("⚙️ Configurar Meta Disney", expanded=(meta_valor == 25000.0)):
    with st.form("form_disney_config"):
        col1, col2, col3 = st.columns(3)
        with col1:
            nova_meta    = st.number_input("🎯 Valor Total da Meta (R$)", value=meta_valor,
                                           min_value=1000.0, step=500.0, format="%.2f")
        with col2:
            nova_eco     = st.number_input("💰 Economia Mensal Planejada (R$)", value=eco_mensal,
                                           min_value=50.0, step=50.0, format="%.2f")
        with col3:
            novo_atual   = st.number_input("🐷 Já Guardado (R$)", value=valor_atual,
                                           min_value=0.0, step=100.0, format="%.2f")

        if st.form_submit_button("💾 Salvar Configurações", type="primary", use_container_width=True):
            config["disney_meta_valor"]       = nova_meta
            config["disney_economia_mensal"]  = nova_eco
            config["disney_valor_atual"]      = novo_atual
            salvar_json(CONFIG_FILE, config)
            mensagem_sucesso("Configurações salvas!")
            st.rerun()

config      = ler_json(CONFIG_FILE)
meta_valor  = float(config.get("disney_meta_valor", 25000.0))
eco_mensal  = float(config.get("disney_economia_mensal", 500.0))
valor_atual = float(config.get("disney_valor_atual", 0.0))

faltando    = max(meta_valor - valor_atual, 0)
percentual  = min((valor_atual / meta_valor * 100) if meta_valor > 0 else 0, 100)
meses_faltando = int(faltando / eco_mensal) + 1 if eco_mensal > 0 else 999
data_projetada = hoje + relativedelta(months=meses_faltando)

st.divider()
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#FFD700,#FFA500); border-radius:12px; padding:1.2rem; text-align:center; color:#1a1a2e;">
        <div style="font-size:1.8rem;">🎯</div>
        <div style="font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:1px;">Meta Total</div>
        <div style="font-size:1.4rem; font-weight:800;">{formatar_moeda(meta_valor)}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#06D6A0,#028a63); border-radius:12px; padding:1.2rem; text-align:center; color:white;">
        <div style="font-size:1.8rem;">🐷</div>
        <div style="font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:1px;">Já Guardado</div>
        <div style="font-size:1.4rem; font-weight:800;">{formatar_moeda(valor_atual)}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#FF6B6B,#c0392b); border-radius:12px; padding:1.2rem; text-align:center; color:white;">
        <div style="font-size:1.8rem;">💸</div>
        <div style="font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:1px;">Faltam</div>
        <div style="font-size:1.4rem; font-weight:800;">{formatar_moeda(faltando)}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1E3A5F,#2a5298); border-radius:12px; padding:1.2rem; text-align:center; color:white;">
        <div style="font-size:1.8rem;">✈️</div>
        <div style="font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:1px;">Previsão</div>
        <div style="font-size:1.2rem; font-weight:800;">{data_projetada.strftime('%b/%Y')}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

cor_barra = "#06D6A0" if percentual >= 75 else "#FFD166" if percentual >= 40 else "#2EC4B6"
st.markdown(f"""
<div style="margin: 0.5rem 0 1.5rem;">
    <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
        <span style="font-weight:700; color:#1E3A5F;">🏰 Progresso até a Disney</span>
        <span style="font-weight:800; color:{cor_barra}; font-size:1.1rem;">{percentual:.1f}%</span>
    </div>
    <div style="background:#e0e0e0; border-radius:50px; height:24px; overflow:hidden; box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);">
        <div style="
            background: linear-gradient(90deg, {cor_barra}, {cor_barra}99);
            width:{percentual:.1f}%;
            height:24px;
            border-radius:50px;
            transition: width 1s ease;
            display:flex; align-items:center; justify-content:flex-end; padding-right:8px;
        ">
            {'✨' if percentual > 5 else ''}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("### 📈 Projeção de Crescimento")

meses_proj = min(meses_faltando + 3, 60)
datas_proj  = [hoje + relativedelta(months=i) for i in range(meses_proj + 1)]
valores_proj = [min(valor_atual + eco_mensal * i, meta_valor) for i in range(meses_proj + 1)]
labels_proj  = [d.strftime("%b/%Y") for d in datas_proj]

fig_proj = go.Figure()
fig_proj.add_trace(go.Scatter(
    x=labels_proj, y=valores_proj,
    mode="lines",
    fill="tozeroy",
    fillcolor="rgba(255,215,0,0.15)",
    line=dict(color="#FFD700", width=3),
    name="Projeção de Economia"
))

fig_proj.add_hline(
    y=meta_valor,
    line_dash="dash",
    line_color="#FF6B6B",
    line_width=2,
    annotation_text=f"🎯 Meta: {formatar_moeda(meta_valor)}",
    annotation_position="top right"
)

fig_proj.add_trace(go.Scatter(
    x=[labels_proj[0]],
    y=[valor_atual],
    mode="markers",
    marker=dict(size=14, color="#06D6A0", symbol="star"),
    name=f"Atual: {formatar_moeda(valor_atual)}"
))

fig_proj.update_layout(
    paper_bgcolor="white",
    plot_bgcolor="white",
    margin=dict(t=20, b=20, l=10, r=10),
    height=350,
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    yaxis=dict(tickprefix="R$ ", gridcolor="#f0f0f0"),
    xaxis=dict(gridcolor="#f0f0f0", tickangle=-45),
)
st.plotly_chart(fig_proj, use_container_width=True)

st.divider()
st.markdown("### 🧮 Simulador — E se eu guardar mais?")

col_s1, col_s2 = st.columns(2)
with col_s1:
    eco_sim = st.slider("Economia mensal simulada (R$):",
                        min_value=100, max_value=5000,
                        value=int(eco_mensal), step=50)

meses_sim = int(faltando / eco_sim) + 1 if eco_sim > 0 else 999
data_sim  = hoje + relativedelta(months=meses_sim)

with col_s2:
    diff = meses_faltando - meses_sim
    st.markdown(f"""
    <div style="background:#f8f9fa; border-radius:12px; padding:1.2rem; margin-top:0.5rem;">
        <div style="font-size:0.85rem; color:#8D99AE;">Com <b>R$ {eco_sim:,.0f}/mês</b> você chegará em:</div>
        <div style="font-size:1.5rem; font-weight:800; color:#1E3A5F;">{data_sim.strftime('%B de %Y')}</div>
        <div style="font-size:0.85rem; color:{'#06D6A0' if diff > 0 else '#FF6B6B'};">
            {'🚀 ' + str(abs(diff)) + ' meses mais rápido!' if diff > 0 else ('⚠️ ' + str(abs(diff)) + ' meses mais devagar.' if diff < 0 else '✅ Mesmo prazo.')}
        </div>
    </div>
    """, unsafe_allow_html=True)

st.divider()
st.markdown("### 💡 Dicas para chegar mais rápido à Disney")
st.markdown("""
- ☕ **Café fora**: Fazer café em casa pode economizar R$ 150/mês
- 🍕 **Delivery**: Reduzir 2 pedidos por mês = R$ 80-120 a mais
- 🎬 **Streamings**: Cancelar 2 serviços = ~R$ 60/mês
- 💳 **Cartão**: Quite sempre inteira para não pagar juros!
""")

st.markdown("""
<div style="text-align:center; padding:1rem; color:#8D99AE; font-size:0.85rem;">
    🌟 Cada real guardado é um passo mais perto da magia! 🏰✨
</div>
""", unsafe_allow_html=True)
