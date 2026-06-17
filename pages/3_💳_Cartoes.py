# ============================================================
#  3_💳_Cartoes.py — Gerenciar Cartões
# ============================================================

import streamlit as st

from auth import exigir_login
exigir_login()
import pandas as pd
from datetime import date

from config import CARTOES_FILE, DESPESAS_FILE, MESES_PT
from utils import (
    configurar_pagina, cabecalho_pagina, inicializar_dados,
    ler_csv, mensagem_sucesso, formatar_moeda, gerar_id, agora, salvar_parquet,
)

configurar_pagina("Cartões", icone="💳")
inicializar_dados()
cabecalho_pagina(titulo="Cartões", subtitulo="Gerencie seus cartões de crédito", icone="💳")
st.markdown("---")

tab1, tab2 = st.tabs(["💳 Meus Cartões", "📈 Despesas por Cartão"])

# ── ABA 1: MEUS CARTÕES ────────────────────────────────────
with tab1:
    df_cartoes = ler_csv(CARTOES_FILE)

    if not df_cartoes.empty:
        cols = st.columns(3)
        for idx, (_, c) in enumerate(df_cartoes.iterrows()):
            with cols[idx % 3]:
                limite_val = float(c.get("limite", 0))
                venc = c.get("dia_vencimento", "?")
                st.markdown(f"""
                <div class="card-neutro" style="margin-bottom:12px">
                    <div style="font-size:1.1rem;font-weight:800;color:#E6EDF3;margin-bottom:8px">
                        💳 {c.get('nome','?')}
                    </div>
                    <div style="color:#8BAFC9;font-size:0.85rem">🏦 {c.get('bandeira','N/A')}</div>
                    <div style="color:#00D4FF;font-size:1rem;font-weight:700;margin:4px 0">
                        {formatar_moeda(limite_val)}
                    </div>
                    <div style="color:#556878;font-size:0.8rem">📅 Vence dia {venc}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Nenhum cartão cadastrado")

    st.info("💡 Para adicionar ou remover cartões, acesse **✏️ Editar Dados → 💳 Cartões**.")

# ── ABA 2: DESPESAS POR CARTÃO ─────────────────────────────
with tab2:
    df_desp = ler_csv(DESPESAS_FILE)

    if df_desp.empty:
        st.info("Sem despesas de cartão ainda.")
    else:
        df_desp["valor"] = pd.to_numeric(df_desp["valor"], errors="coerce").fillna(0)
        if "data_dt" not in df_desp.columns:
            df_desp["data_dt"] = pd.to_datetime(df_desp["data"], errors="coerce")

        df_desp = df_desp[df_desp["cartao"].astype(str).str.strip().ne("")].copy()

        if df_desp.empty:
            st.info("Nenhuma despesa de cartão. Importe uma fatura na página Importações.")
        else:
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                cartao_f = st.selectbox("Cartão:", ["Todos"] + sorted(df_desp["cartao"].dropna().unique().tolist()), key="cart_f")
            with col_f2:
                mes_f = st.selectbox("Mês:", [0]+list(range(1,13)), index=0,
                                     format_func=lambda m: "Todos" if m==0 else MESES_PT[m-1], key="mes_fc")
            with col_f3:
                ano_f = st.selectbox("Ano:", ["Todos"]+list(range(2023, date.today().year+2)), key="ano_fc")

            df_f = df_desp.copy()
            if cartao_f != "Todos": df_f = df_f[df_f["cartao"] == cartao_f]
            if mes_f > 0:           df_f = df_f[df_f["data_dt"].dt.month == mes_f]
            if ano_f != "Todos":    df_f = df_f[df_f["data_dt"].dt.year == int(ano_f)]

            c1, c2, c3 = st.columns(3)
            with c1: st.markdown(f'<div class="card-despesa"><div class="card-label">💸 Total</div><div class="card-value-despesa">{formatar_moeda(df_f["valor"].sum())}</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="card-neutro"><div class="card-label">📊 Lançamentos</div><div class="card-value-neutro">{len(df_f)}</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="card-neutro"><div class="card-label">📈 Média</div><div class="card-value-neutro">{formatar_moeda(df_f["valor"].mean() if len(df_f)>0 else 0)}</div></div>', unsafe_allow_html=True)

            st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
            st.divider()

            if not df_f.empty:
                df_exib = df_f[["data","descricao","categoria","valor","cartao"]].copy()
                df_exib["data"]  = pd.to_datetime(df_exib["data"]).dt.strftime("%d/%m/%Y")
                df_exib["valor"] = df_exib["valor"].apply(formatar_moeda)
                df_exib.columns  = ["Data","Descrição","Categoria","Valor","Cartão"]
                st.dataframe(df_exib, use_container_width=True, hide_index=True, height=450)

