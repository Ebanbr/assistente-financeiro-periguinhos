# ============================================================
#  7_👴👵_Aposentadoria.py — Planejamento de Aposentadoria
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st

from auth import exigir_login
exigir_login()
import pandas as pd
import plotly.graph_objects as go
from datetime import date

from config import CONFIG_FILE
from utils import (
    configurar_pagina, cabecalho_pagina, inicializar_dados,
    ler_json, salvar_json, formatar_moeda, mensagem_sucesso,
)

configurar_pagina("Aposentadoria", icone="👴")
inicializar_dados()
cabecalho_pagina(
    titulo="Planejamento de Aposentadoria",
    subtitulo="Construa o futuro financeiro da Família Periguinhos",
    icone="👴👵"
)

config = ler_json(CONFIG_FILE)

DARK = dict(
    paper_bgcolor="#161B22", plot_bgcolor="#161B22",
    font=dict(color="#8BAFC9", family="Inter", size=12),
    xaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
    yaxis=dict(gridcolor="#21262D", linecolor="#30363D", tickprefix="R$ "),
    margin=dict(t=40, b=20, l=10, r=10),
    legend=dict(bgcolor="#0D1B2A", bordercolor="#30363D", orientation="h", y=1.1,
                font=dict(color="#E6EDF3"))
)

def card(icone, label, valor, cor):
    return f"""<div style="background:#161B22;border:1px solid {cor}44;border-left:4px solid {cor};
    border-radius:12px;padding:1rem 1.2rem;transition:all 0.2s">
    <div style="font-size:0.72rem;color:#8BAFC9;text-transform:uppercase;letter-spacing:0.8px">{icone} {label}</div>
    <div style="font-size:1.4rem;font-weight:800;color:{cor};margin:4px 0">{valor}</div>
    </div>"""

def calcular(patrimonio_atual, aporte_mensal, rentabilidade, anos_acumulacao):
    taxa_mensal = (1 + rentabilidade / 100) ** (1 / 12) - 1
    meses = anos_acumulacao * 12
    patrimonios = []
    saldo = patrimonio_atual
    for _ in range(meses + 1):
        patrimonios.append(saldo)
        saldo = saldo * (1 + taxa_mensal) + aporte_mensal
    return patrimonios, taxa_mensal

def render_pessoa(prefixo, nome, emoji, cor_primaria, cor_secundaria):
    st.markdown(f"### {emoji} {nome}")

    with st.form(f"form_{prefixo}"):
        col1, col2, col3 = st.columns(3)
        with col1:
            idade_atual     = st.number_input("Idade atual", min_value=18, max_value=80,
                                              value=int(config.get(f"{prefixo}_idade_atual", 35)))
            idade_apos      = st.number_input("Idade de aposentadoria", min_value=40, max_value=80,
                                              value=int(config.get(f"{prefixo}_idade_meta", 60)))
            patrimonio_atual= st.number_input("Patrimônio atual investido (R$)", min_value=0.0,
                                              step=1000.0, format="%.2f",
                                              value=float(config.get(f"{prefixo}_patrimonio_atual", 0.0)))
        with col2:
            aporte_mensal   = st.number_input("Aporte mensal (R$)", min_value=0.0,
                                              step=100.0, format="%.2f",
                                              value=float(config.get(f"{prefixo}_aporte_mensal", 1000.0)))
            renda_desejada  = st.number_input("Renda mensal desejada na aposen. (R$)",
                                              min_value=500.0, step=500.0, format="%.2f",
                                              value=float(config.get(f"{prefixo}_renda_desejada", 5000.0)))
            taxa_saque      = st.number_input("Taxa de saque anual segura (%)", min_value=1.0,
                                              max_value=10.0, step=0.5, format="%.1f",
                                              value=float(config.get(f"{prefixo}_taxa_saque", 4.0)))
        with col3:
            rentabilidade   = st.number_input("Rentabilidade anual esperada (%)", min_value=1.0,
                                              max_value=30.0, step=0.5, format="%.1f",
                                              value=float(config.get(f"{prefixo}_rentabilidade", 10.0)))
            inflacao        = st.number_input("Inflação anual estimada (%)", min_value=0.0,
                                              max_value=20.0, step=0.5, format="%.1f",
                                              value=float(config.get(f"{prefixo}_inflacao", 5.0)))

        if st.form_submit_button("🔄 Calcular / Salvar", type="primary", use_container_width=True):
            config.update({
                f"{prefixo}_idade_atual": idade_atual, f"{prefixo}_idade_meta": idade_apos,
                f"{prefixo}_patrimonio_atual": patrimonio_atual, f"{prefixo}_aporte_mensal": aporte_mensal,
                f"{prefixo}_renda_desejada": renda_desejada, f"{prefixo}_taxa_saque": taxa_saque,
                f"{prefixo}_rentabilidade": rentabilidade, f"{prefixo}_inflacao": inflacao,
            })
            salvar_json(CONFIG_FILE, config)
            mensagem_sucesso(f"Dados de {nome} salvos!")
            st.rerun()

    # Recalcula com dados salvos
    cfg = ler_json(CONFIG_FILE)
    idade_atual      = int(cfg.get(f"{prefixo}_idade_atual", 35))
    idade_apos       = int(cfg.get(f"{prefixo}_idade_meta", 60))
    patrimonio_atual = float(cfg.get(f"{prefixo}_patrimonio_atual", 0.0))
    aporte_mensal    = float(cfg.get(f"{prefixo}_aporte_mensal", 1000.0))
    renda_desejada   = float(cfg.get(f"{prefixo}_renda_desejada", 5000.0))
    taxa_saque       = float(cfg.get(f"{prefixo}_taxa_saque", 4.0))
    rentabilidade    = float(cfg.get(f"{prefixo}_rentabilidade", 10.0))

    anos_acumulacao      = max(idade_apos - idade_atual, 1)
    meses_acumulacao     = anos_acumulacao * 12
    patrimonio_necessario= (renda_desejada * 12) / (taxa_saque / 100)
    patrimonios, taxa_m  = calcular(patrimonio_atual, aporte_mensal, rentabilidade, anos_acumulacao)
    patrimonio_projetado = patrimonios[-1]
    renda_gerada         = patrimonio_projetado * (taxa_saque / 100) / 12
    juros_compostos      = patrimonio_projetado - (patrimonio_atual + aporte_mensal * meses_acumulacao)
    perc_meta            = min(patrimonio_projetado / patrimonio_necessario * 100, 100) if patrimonio_necessario > 0 else 0

    st.divider()

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    cor_renda = "#00C953" if renda_gerada >= renda_desejada else "#FF4D6D"
    with c1: st.markdown(card("🏦", "Patrimônio Projetado", formatar_moeda(patrimonio_projetado), cor_primaria), unsafe_allow_html=True)
    with c2: st.markdown(card("🎯", "Meta Necessária", formatar_moeda(patrimonio_necessario), "#FFB300"), unsafe_allow_html=True)
    with c3: st.markdown(card("💰", "Renda Gerada/mês", formatar_moeda(renda_gerada), cor_renda), unsafe_allow_html=True)
    with c4: st.markdown(card("📈", "Juros Compostos", formatar_moeda(juros_compostos), cor_secundaria), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)

    # Barra de progresso
    cor_barra = "#00C953" if perc_meta >= 100 else "#FFB300" if perc_meta >= 60 else "#FF4D6D"
    st.markdown(f"""
    <div style="margin-bottom:1.5rem">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px">
            <span style="color:#8BAFC9;font-weight:600">Projeção vs Meta</span>
            <span style="font-weight:800;color:{cor_barra}">{perc_meta:.1f}%</span>
        </div>
        <div style="background:#21262D;border-radius:50px;height:16px">
            <div style="background:{cor_barra};width:{min(perc_meta,100):.1f}%;height:16px;border-radius:50px;
            box-shadow:0 0 8px {cor_barra}66;transition:width 0.5s"></div>
        </div>
        <div style="display:flex;justify-content:space-between;margin-top:4px">
            <span style="color:#556878;font-size:0.75rem">Hoje: {formatar_moeda(patrimonio_atual)}</span>
            <span style="color:#556878;font-size:0.75rem">Aos {idade_apos} anos — {anos_acumulacao} anos restantes</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Gráfico de crescimento
    st.markdown("#### 📈 Curva de Crescimento")
    anos_labels  = [str(idade_atual + i) for i in range(anos_acumulacao + 1)]
    aportes_acum = [patrimonio_atual + aporte_mensal * 12 * i for i in range(anos_acumulacao + 1)]
    patrim_anual = patrimonios[::12][:anos_acumulacao + 1]
    tam = min(len(anos_labels), len(aportes_acum), len(patrim_anual))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=anos_labels[:tam], y=aportes_acum[:tam],
        name="Total Investido", fill="tozeroy",
        fillcolor="rgba(74,158,255,0.08)" if cor_primaria == "#4A9EFF" else "rgba(255,77,109,0.08)",
        line=dict(color=cor_primaria, width=2, dash="dash"),
        hovertemplate="Idade %{x}<br>Investido: R$ %{y:,.0f}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=anos_labels[:tam], y=patrim_anual[:tam],
        name="Patrimônio com Juros", fill="tonexty",
        fillcolor="rgba(0,212,255,0.12)" if cor_secundaria == "#00D4FF" else "rgba(255,143,163,0.12)",
        line=dict(color=cor_secundaria, width=3),
        hovertemplate="Idade %{x}<br>Patrimônio: R$ %{y:,.0f}<extra></extra>"
    ))
    fig.add_hline(y=patrimonio_necessario, line_dash="dot", line_color="#FFB300", line_width=2,
                  annotation_text=f"Meta: {formatar_moeda(patrimonio_necessario)}",
                  annotation_font_color="#FFB300", annotation_position="top left")
    DARK_APOS = {**DARK, "xaxis": dict(title="Idade (anos)", gridcolor="#21262D", linecolor="#30363D")}
    fig.update_layout(height=350, **DARK_APOS)
    st.plotly_chart(fig, use_container_width=True)

    # Simulador
    st.markdown("#### 🔬 Simulador de Aportes")
    aportes_sim = [500, 1000, 1500, 2000, 3000, 5000]
    rows = []
    for ap in aportes_sim:
        pats, _ = calcular(patrimonio_atual, ap, rentabilidade, anos_acumulacao)
        pat_f = pats[-1]
        renda_f = pat_f * (taxa_saque / 100) / 12
        rows.append({
            "Aporte/mês": formatar_moeda(ap),
            "Patrimônio Final": formatar_moeda(pat_f),
            "Renda Mensal": formatar_moeda(renda_f),
            "Meta?": "✅" if pat_f >= patrimonio_necessario else "❌",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    return {
        "nome": nome, "emoji": emoji,
        "patrimonio_projetado": patrimonio_projetado,
        "patrimonio_necessario": patrimonio_necessario,
        "renda_gerada": renda_gerada,
        "renda_desejada": renda_desejada,
        "idade_apos": idade_apos,
        "patrim_anual": patrim_anual,
        "anos_labels": anos_labels[:tam],
        "cor": cor_primaria,
    }


# ── Abas ─────────────────────────────────────────────────────
aba_boo, aba_pri, aba_casal = st.tabs(["🧔 Boo", "👩 Pixilinha", "💑 Visão do Casal"])

with aba_boo:
    dados_boo = render_pessoa("boo", "Boo", "🧔", "#4A9EFF", "#00D4FF")

with aba_pri:
    dados_pri = render_pessoa("pri", "Pixilinha", "👩", "#FF4D6D", "#FF8FA3")

with aba_casal:
    st.markdown("### 💑 Visão Consolidada do Casal")

    cfg = ler_json(CONFIG_FILE)
    # Recalcula ambos para a visão consolidada
    def get_dados(prefixo):
        idade_atual  = int(cfg.get(f"{prefixo}_idade_atual", 35))
        idade_apos   = int(cfg.get(f"{prefixo}_idade_meta", 60))
        pat_atual    = float(cfg.get(f"{prefixo}_patrimonio_atual", 0.0))
        aporte       = float(cfg.get(f"{prefixo}_aporte_mensal", 1000.0))
        renda_des    = float(cfg.get(f"{prefixo}_renda_desejada", 5000.0))
        taxa_s       = float(cfg.get(f"{prefixo}_taxa_saque", 4.0))
        rent         = float(cfg.get(f"{prefixo}_rentabilidade", 10.0))
        anos         = max(idade_apos - idade_atual, 1)
        pats, _      = calcular(pat_atual, aporte, rent, anos)
        pat_proj     = pats[-1]
        pat_nec      = (renda_des * 12) / (taxa_s / 100)
        renda_g      = pat_proj * (taxa_s / 100) / 12
        return {"pat_proj": pat_proj, "pat_nec": pat_nec, "renda_g": renda_g,
                "renda_des": renda_des, "aporte": aporte, "anos": anos,
                "idade_apos": idade_apos, "pat_anual": pats[::12][:anos+1],
                "idades": [str(idade_atual+i) for i in range(anos+1)]}

    b = get_dados("boo")
    p = get_dados("pri")

    # KPIs casal
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(card("🏦", "Patrimônio Casal", formatar_moeda(b["pat_proj"]+p["pat_proj"]), "#00D4FF"), unsafe_allow_html=True)
    with c2: st.markdown(card("🎯", "Meta Casal", formatar_moeda(b["pat_nec"]+p["pat_nec"]), "#FFB300"), unsafe_allow_html=True)
    with c3: st.markdown(card("💰", "Renda Casal/mês", formatar_moeda(b["renda_g"]+p["renda_g"]), "#00C953"), unsafe_allow_html=True)
    with c4: st.markdown(card("💸", "Aporte Casal/mês", formatar_moeda(b["aporte"]+p["aporte"]), "#9D4EDD"), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
    st.divider()

    # Gráfico comparativo
    st.markdown("#### 📊 Crescimento Comparativo — Boo vs Pixilinha")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=b["idades"], y=b["pat_anual"],
        name="🧔 Boo", line=dict(color="#4A9EFF", width=3),
        fill="tozeroy", fillcolor="rgba(74,158,255,0.1)",
        hovertemplate="Boo — Idade %{x}<br>R$ %{y:,.0f}<extra></extra>"
    ))
    fig2.add_trace(go.Scatter(
        x=p["idades"], y=p["pat_anual"],
        name="👩 Pixilinha", line=dict(color="#FF4D6D", width=3),
        fill="tozeroy", fillcolor="rgba(255,77,109,0.1)",
        hovertemplate="Pixilinha — Idade %{x}<br>R$ %{y:,.0f}<extra></extra>"
    ))
    DARK_CASAL = {**DARK, "xaxis": dict(title="Idade (anos)", gridcolor="#21262D", linecolor="#30363D")}
    fig2.update_layout(height=380, **DARK_CASAL)
    st.plotly_chart(fig2, use_container_width=True)

    # Resumo lado a lado
    st.markdown("#### 📋 Resumo Comparativo")
    col_b, col_p = st.columns(2)
    with col_b:
        st.markdown(f"""
        <div style="background:#161B22;border:1px solid #4A9EFF33;border-radius:12px;padding:1.2rem">
            <div style="color:#4A9EFF;font-weight:800;font-size:1.1rem;margin-bottom:12px">🧔 Boo</div>
            <div style="color:#8BAFC9;font-size:0.85rem">Aposenta aos <strong style="color:#E6EDF3">{b['idade_apos']} anos</strong> ({b['anos']} anos restantes)</div>
            <div style="color:#8BAFC9;font-size:0.85rem;margin-top:6px">Patrimônio: <strong style="color:#4A9EFF">{formatar_moeda(b['pat_proj'])}</strong></div>
            <div style="color:#8BAFC9;font-size:0.85rem;margin-top:6px">Renda: <strong style="color:#{'00C953' if b['renda_g']>=b['renda_des'] else 'FF4D6D'}">{formatar_moeda(b['renda_g'])}/mês</strong></div>
            <div style="color:#8BAFC9;font-size:0.85rem;margin-top:6px">Meta: <strong style="color:#FFB300">{formatar_moeda(b['pat_nec'])}</strong></div>
        </div>
        """, unsafe_allow_html=True)
    with col_p:
        st.markdown(f"""
        <div style="background:#161B22;border:1px solid #FF4D6D33;border-radius:12px;padding:1.2rem">
            <div style="color:#FF4D6D;font-weight:800;font-size:1.1rem;margin-bottom:12px">👩 Pixilinha</div>
            <div style="color:#8BAFC9;font-size:0.85rem">Aposenta aos <strong style="color:#E6EDF3">{p['idade_apos']} anos</strong> ({p['anos']} anos restantes)</div>
            <div style="color:#8BAFC9;font-size:0.85rem;margin-top:6px">Patrimônio: <strong style="color:#FF4D6D">{formatar_moeda(p['pat_proj'])}</strong></div>
            <div style="color:#8BAFC9;font-size:0.85rem;margin-top:6px">Renda: <strong style="color:#{'00C953' if p['renda_g']>=p['renda_des'] else 'FF4D6D'}">{formatar_moeda(p['renda_g'])}/mês</strong></div>
            <div style="color:#8BAFC9;font-size:0.85rem;margin-top:6px">Meta: <strong style="color:#FFB300">{formatar_moeda(p['pat_nec'])}</strong></div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <br><div style="text-align:center;color:#30363D;font-size:0.75rem">
    ⚠️ Simulação educacional. Rentabilidades passadas não garantem resultados futuros.
    </div>""", unsafe_allow_html=True)

