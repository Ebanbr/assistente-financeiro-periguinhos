# ============================================================
#  6_🌴_Projeto_Ferias.py — Projeto Férias da Família
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st

from auth import exigir_login
exigir_login()
import plotly.graph_objects as go
from datetime import date
from dateutil.relativedelta import relativedelta

from config import CONFIG_FILE
from utils import (
    configurar_pagina, cabecalho_pagina, inicializar_dados,
    ler_json, salvar_json, formatar_moeda, mensagem_sucesso,
)

configurar_pagina("Projeto Férias", icone="🌴")
inicializar_dados()

hoje   = date.today()
config = ler_json(CONFIG_FILE)

# ── Lê config salva ──────────────────────────────────────────
destino      = config.get("ferias_destino", "")
eco_mensal   = float(config.get("ferias_economia_mensal", 500.0))
valor_atual  = float(config.get("ferias_valor_atual", 0.0))

orcamento = {
    "translado":    float(config.get("ferias_translado",    0.0)),
    "hospedagem":   float(config.get("ferias_hospedagem",   0.0)),
    "passeios":     float(config.get("ferias_passeios",     0.0)),
    "carro":        float(config.get("ferias_carro",        0.0)),
    "alimentacao":  float(config.get("ferias_alimentacao",  0.0)),
    "extras":       float(config.get("ferias_extras",       0.0)),
}
meta_valor = sum(orcamento.values())

# ── Cabeçalho ─────────────────────────────────────────────────
nome_destino = destino if destino else "???"
st.markdown(f"""
<div style="background:linear-gradient(135deg,#0d2137 0%,#1a3a5c 50%,#0d5c45 100%);
    padding:2rem; border-radius:16px; margin-bottom:1.5rem; text-align:center;
    box-shadow:0 8px 32px rgba(0,0,0,0.3); border:1px solid rgba(100,220,150,0.3);">
    <div style="font-size:3rem;">🌴✈️</div>
    <h1 style="color:#7FFFD4; margin:0.5rem 0; font-size:2rem;">Projeto Férias</h1>
    <p style="color:rgba(255,255,255,0.8); margin:0; font-size:1.2rem; font-weight:600;">
        🗺️ Destino: <b style="color:#FFD700">{nome_destino}</b>
    </p>
    <p style="color:rgba(255,255,255,0.5); margin:0.3rem 0 0;">
        Guardando cada centavo para realizar o sonho! 🐧
    </p>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ════════════════════════════════════════════════════════════
with st.expander("⚙️ Configurar Destino e Orçamento", expanded=(not destino)):
    with st.form("form_ferias_config"):
        st.markdown("#### 🗺️ Destino e Poupança")
        col_d, col_e, col_a = st.columns(3)
        with col_d:
            novo_destino = st.text_input("Destino da viagem:", value=destino,
                                         placeholder="Ex: Maceió, Portugal, EUA...")
        with col_e:
            nova_eco = st.number_input("💰 Economia mensal planejada (R$):",
                                       value=eco_mensal, min_value=50.0, step=50.0, format="%.2f")
        with col_a:
            novo_atual = st.number_input("🐷 Já guardado (R$):",
                                         value=valor_atual, min_value=0.0, step=100.0, format="%.2f")

        st.markdown("#### 💸 Orçamento estimado por categoria")
        col1, col2, col3 = st.columns(3)
        with col1:
            novo_translado   = st.number_input("✈️ Translado (passagens, uber):",
                                               value=orcamento["translado"], min_value=0.0, step=100.0, format="%.2f")
            novo_hospedagem  = st.number_input("🏨 Hospedagem:",
                                               value=orcamento["hospedagem"], min_value=0.0, step=100.0, format="%.2f")
        with col2:
            novo_passeios    = st.number_input("🎡 Passeios e lazer:",
                                               value=orcamento["passeios"], min_value=0.0, step=100.0, format="%.2f")
            novo_carro       = st.number_input("🚗 Aluguel de carro:",
                                               value=orcamento["carro"], min_value=0.0, step=100.0, format="%.2f")
        with col3:
            novo_alimentacao = st.number_input("🍽️ Alimentação:",
                                               value=orcamento["alimentacao"], min_value=0.0, step=100.0, format="%.2f")
            novo_extras      = st.number_input("🎁 Gastos extras (compras, imprevistos):",
                                               value=orcamento["extras"], min_value=0.0, step=100.0, format="%.2f")

        if st.form_submit_button("💾 Salvar Configurações", type="primary", use_container_width=True):
            config.update({
                "ferias_destino":          novo_destino,
                "ferias_economia_mensal":  nova_eco,
                "ferias_valor_atual":      novo_atual,
                "ferias_translado":        novo_translado,
                "ferias_hospedagem":       novo_hospedagem,
                "ferias_passeios":         novo_passeios,
                "ferias_carro":            novo_carro,
                "ferias_alimentacao":      novo_alimentacao,
                "ferias_extras":           novo_extras,
            })
            salvar_json(CONFIG_FILE, config)
            mensagem_sucesso("Configurações salvas!")
            st.rerun()

# Recarrega após salvar
config       = ler_json(CONFIG_FILE)
destino      = config.get("ferias_destino", "")
eco_mensal   = float(config.get("ferias_economia_mensal", 500.0))
valor_atual  = float(config.get("ferias_valor_atual", 0.0))
orcamento    = {
    "translado":   float(config.get("ferias_translado",   0.0)),
    "hospedagem":  float(config.get("ferias_hospedagem",  0.0)),
    "passeios":    float(config.get("ferias_passeios",    0.0)),
    "carro":       float(config.get("ferias_carro",       0.0)),
    "alimentacao": float(config.get("ferias_alimentacao", 0.0)),
    "extras":      float(config.get("ferias_extras",      0.0)),
}
meta_valor     = sum(orcamento.values())
faltando       = max(meta_valor - valor_atual, 0)
percentual     = min((valor_atual / meta_valor * 100) if meta_valor > 0 else 0, 100)
meses_faltando = int(faltando / eco_mensal) + 1 if eco_mensal > 0 and faltando > 0 else 0
data_projetada = hoje + relativedelta(months=meses_faltando)

# ════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════
st.divider()
st.markdown("### 📊 Resumo da Meta")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""<div style="background:linear-gradient(135deg,#FFD700,#FFA500);border-radius:12px;padding:1.2rem;text-align:center;color:#1a1a2e;">
        <div style="font-size:1.8rem;">🎯</div>
        <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Orçamento Total</div>
        <div style="font-size:1.3rem;font-weight:800;">{formatar_moeda(meta_valor)}</div>
    </div>""", unsafe_allow_html=True)
with col2:
    st.markdown(f"""<div style="background:linear-gradient(135deg,#06D6A0,#028a63);border-radius:12px;padding:1.2rem;text-align:center;color:white;">
        <div style="font-size:1.8rem;">🐷</div>
        <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Já Guardado</div>
        <div style="font-size:1.3rem;font-weight:800;">{formatar_moeda(valor_atual)}</div>
    </div>""", unsafe_allow_html=True)
with col3:
    st.markdown(f"""<div style="background:linear-gradient(135deg,#FF6B6B,#c0392b);border-radius:12px;padding:1.2rem;text-align:center;color:white;">
        <div style="font-size:1.8rem;">💸</div>
        <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Faltam</div>
        <div style="font-size:1.3rem;font-weight:800;">{formatar_moeda(faltando)}</div>
    </div>""", unsafe_allow_html=True)
with col4:
    st.markdown(f"""<div style="background:linear-gradient(135deg,#1E3A5F,#2a5298);border-radius:12px;padding:1.2rem;text-align:center;color:white;">
        <div style="font-size:1.8rem;">✈️</div>
        <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Previsão</div>
        <div style="font-size:1.1rem;font-weight:800;">{"Meta atingida! 🎉" if faltando == 0 else data_projetada.strftime('%b/%Y')}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Barra de progresso
cor_barra = "#06D6A0" if percentual >= 75 else "#FFD166" if percentual >= 40 else "#2EC4B6"
st.markdown(f"""
<div style="margin:0.5rem 0 1.5rem;">
    <div style="display:flex;justify-content:space-between;margin-bottom:0.5rem;">
        <span style="font-weight:700;color:#7FFFD4;">🌴 Progresso da poupança</span>
        <span style="font-weight:800;color:{cor_barra};font-size:1.1rem;">{percentual:.1f}%</span>
    </div>
    <div style="background:#21262D;border-radius:50px;height:28px;overflow:hidden;">
        <div style="background:linear-gradient(90deg,{cor_barra},{cor_barra}99);
            width:{percentual:.1f}%;height:28px;border-radius:50px;
            display:flex;align-items:center;justify-content:flex-end;padding-right:10px;">
            {'✨' if percentual > 5 else ''}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Orçamento por categoria ───────────────────────────────────
if meta_valor > 0:
    st.divider()
    st.markdown("### 🗂️ Orçamento por Categoria")

    CATS = {
        "✈️ Translado":     ("translado",   "#4A9EFF"),
        "🏨 Hospedagem":    ("hospedagem",  "#9D4EDD"),
        "🎡 Passeios":      ("passeios",    "#FFB300"),
        "🚗 Aluguel Carro": ("carro",       "#00D4FF"),
        "🍽️ Alimentação":  ("alimentacao", "#00C953"),
        "🎁 Extras":        ("extras",      "#FF4D6D"),
    }

    cols = st.columns(3)
    for i, (label, (key, cor)) in enumerate(CATS.items()):
        val = orcamento[key]
        pct = (val / meta_valor * 100) if meta_valor > 0 else 0
        guardado_cat = min(valor_atual * (val / meta_valor), val) if meta_valor > 0 else 0
        with cols[i % 3]:
            st.markdown(f"""
            <div style="background:#161B22;border:1px solid #30363D;border-radius:10px;padding:1rem;margin-bottom:0.8rem;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
                    <span style="font-weight:600;color:#E6EDF3;">{label}</span>
                    <span style="font-size:0.8rem;color:{cor};font-weight:700;">{pct:.0f}%</span>
                </div>
                <div style="font-size:1.2rem;font-weight:800;color:{cor};">{formatar_moeda(val)}</div>
                <div style="background:#21262D;border-radius:20px;height:6px;margin-top:0.5rem;">
                    <div style="background:{cor};width:{min(guardado_cat/val*100 if val>0 else 0,100):.0f}%;height:6px;border-radius:20px;"></div>
                </div>
                <div style="font-size:0.75rem;color:#8BAFC9;margin-top:0.3rem;">
                    Guardado proporcional: {formatar_moeda(guardado_cat)}
                </div>
            </div>""", unsafe_allow_html=True)

    # Gráfico pizza do orçamento
    st.markdown("#### 🥧 Distribuição do orçamento")
    labels_pizza = [l for l, (k, _) in CATS.items() if orcamento[k] > 0]
    values_pizza = [orcamento[k] for _, (k, _) in CATS.items() if orcamento[k] > 0]
    cores_pizza  = [c for _, (k, c) in CATS.items() if orcamento[k] > 0]

    if values_pizza:
        fig_pizza = go.Figure(go.Pie(
            labels=labels_pizza, values=values_pizza,
            hole=0.5,
            marker=dict(colors=cores_pizza),
            textinfo="percent",
            hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>"
        ))
        fig_pizza.update_layout(
            paper_bgcolor="#0D1117", plot_bgcolor="#0D1117",
            font=dict(color="#E6EDF3"),
            height=320, margin=dict(l=0, r=160, t=10, b=10),
            legend=dict(bgcolor="#161B22", bordercolor="#30363D",
                        font=dict(color="#E6EDF3", size=11), x=1.02, y=0.5),
        )
        st.plotly_chart(fig_pizza, use_container_width=True)

# ── Projeção de crescimento ───────────────────────────────────
st.divider()
st.markdown("### 📈 Projeção de Crescimento")

meses_proj   = min(meses_faltando + 3, 60) if meses_faltando > 0 else 12
datas_proj   = [hoje + relativedelta(months=i) for i in range(meses_proj + 1)]
valores_proj = [min(valor_atual + eco_mensal * i, meta_valor) for i in range(meses_proj + 1)]
labels_proj  = [d.strftime("%b/%Y") for d in datas_proj]

fig_proj = go.Figure()
fig_proj.add_trace(go.Scatter(
    x=labels_proj, y=valores_proj,
    mode="lines", fill="tozeroy",
    fillcolor="rgba(127,255,212,0.1)",
    line=dict(color="#7FFFD4", width=3),
    name="Projeção de poupança"
))
if meta_valor > 0:
    fig_proj.add_hline(y=meta_valor, line_dash="dash", line_color="#FFD700", line_width=2,
                       annotation_text=f"🎯 Meta: {formatar_moeda(meta_valor)}", annotation_position="top right")
fig_proj.add_trace(go.Scatter(
    x=[labels_proj[0]], y=[valor_atual],
    mode="markers", marker=dict(size=14, color="#06D6A0", symbol="star"),
    name=f"Atual: {formatar_moeda(valor_atual)}"
))
fig_proj.update_layout(
    paper_bgcolor="#0D1117", plot_bgcolor="#0D1117",
    font=dict(color="#E6EDF3"),
    margin=dict(t=20, b=20, l=10, r=10), height=320,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, bgcolor="#0D1117"),
    yaxis=dict(tickprefix="R$ ", gridcolor="#21262D"),
    xaxis=dict(gridcolor="#21262D", tickangle=-45),
)
st.plotly_chart(fig_proj, use_container_width=True)

# ── Simulador ─────────────────────────────────────────────────
st.divider()
st.markdown("### 🧮 Simulador — E se eu guardar mais?")
col_s1, col_s2 = st.columns(2)
with col_s1:
    eco_sim = st.slider("Economia mensal simulada (R$):",
                        min_value=100, max_value=5000, value=int(eco_mensal), step=50)
meses_sim = int(faltando / eco_sim) + 1 if eco_sim > 0 and faltando > 0 else 0
data_sim  = hoje + relativedelta(months=meses_sim)
diff      = meses_faltando - meses_sim
with col_s2:
    st.markdown(f"""
    <div style="background:#161B22;border:1px solid #30363D;border-radius:12px;padding:1.2rem;margin-top:0.5rem;">
        <div style="font-size:0.85rem;color:#8BAFC9;">Com <b>R$ {eco_sim:,.0f}/mês</b> você chegará em:</div>
        <div style="font-size:1.5rem;font-weight:800;color:#7FFFD4;">{"Meta já atingida! 🎉" if faltando == 0 else data_sim.strftime('%B de %Y')}</div>
        <div style="font-size:0.85rem;color:{'#06D6A0' if diff > 0 else '#FF6B6B'};">
            {'🚀 ' + str(abs(diff)) + ' meses mais rápido!' if diff > 0 else ('⚠️ ' + str(abs(diff)) + ' meses mais devagar.' if diff < 0 else '✅ Mesmo prazo.')}
        </div>
    </div>""", unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center;padding:1.5rem;color:#8BAFC9;font-size:0.85rem;margin-top:1rem;">
    🌟 Cada real guardado é um passo mais perto da viagem dos sonhos! 🌴✈️
</div>""", unsafe_allow_html=True)
