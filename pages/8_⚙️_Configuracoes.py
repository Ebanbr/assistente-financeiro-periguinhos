# ============================================================
#  8_⚙️_Configuracoes.py — Configurações do App
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st

from auth import exigir_login
exigir_login()
import pandas as pd
import json
from datetime import date
from io import StringIO

from config import (
    CONFIG_FILE, DESPESAS_FILE, RECEITAS_FILE,
    CARTOES_FILE, METAS_FILE, LANCAMENTOS_FILE,
    CATEGORIAS_DESPESA, CATEGORIAS_RECEITA,
    COLUNAS_DESPESAS, COLUNAS_RECEITAS,
)
from utils import (
    configurar_pagina, cabecalho_pagina, inicializar_dados,
    ler_json, salvar_json, ler_csv, salvar_parquet,
    formatar_moeda, mensagem_sucesso, mensagem_erro, mensagem_aviso,
)

configurar_pagina("Configurações", icone="⚙️")
inicializar_dados()

cabecalho_pagina(
    titulo="Configurações",
    subtitulo="Personalize o Assistente Financeiro",
    icone="⚙️"
)

config = ler_json(CONFIG_FILE)

aba1, aba2, aba3, aba4 = st.tabs([
    "👨‍👩‍👧‍👦 Família",
    "🏷️ Categorias",
    "💾 Backup",
    "🗑️ Limpar Dados"
])

# ════════════════════════════════════════════════════════════
# ABA 1 — FAMÍLIA
# ════════════════════════════════════════════════════════════
with aba1:
    st.markdown("### 👨‍👩‍👧‍👦 Dados da Família")

    with st.form("form_familia"):
        nome_familia = st.text_input("Nome da Família", value=config.get("nome_familia", "Família Periguinhos"))
        st.markdown("**Membros da Família**")
        col1, col2 = st.columns(2)
        with col1:
            membro1 = st.text_input("Membro 1 (Pai/Mãe)", value=config.get("membro1", "Bruno"))
            membro2 = st.text_input("Membro 2 (Pai/Mãe)", value=config.get("membro2", "Pri"))
        with col2:
            membro3 = st.text_input("Filho(a) 1", value=config.get("membro3", ""))
            membro4 = st.text_input("Filho(a) 2", value=config.get("membro4", ""))

        if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
            config.update({"nome_familia": nome_familia, "membro1": membro1, "membro2": membro2,
                           "membro3": membro3, "membro4": membro4})
            salvar_json(CONFIG_FILE, config)
            mensagem_sucesso("Dados salvos!")

    st.divider()
    st.markdown("### 📊 Resumo dos Dados")

    df_d = ler_csv(DESPESAS_FILE)
    df_r = ler_csv(RECEITAS_FILE)
    df_c = ler_csv(CARTOES_FILE)

    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("💸 Despesas cadastradas", len(df_d) if not df_d.empty else 0)
    col_r2.metric("💰 Receitas cadastradas", len(df_r) if not df_r.empty else 0)
    col_r3.metric("💳 Cartões cadastrados", len(df_c) if not df_c.empty else 0)

# ════════════════════════════════════════════════════════════
# ABA 2 — CATEGORIAS
# ════════════════════════════════════════════════════════════
with aba2:
    st.markdown("### 🏷️ Categorias Cadastradas")

    col_c1, col_c2 = st.columns(2)

    with col_c1:
        st.markdown("**💸 Categorias de Despesa**")
        for cat in CATEGORIAS_DESPESA:
            st.markdown(f"- {cat}")

    with col_c2:
        st.markdown("**💰 Categorias de Receita**")
        for cat in CATEGORIAS_RECEITA:
            st.markdown(f"- {cat}")

    st.divider()
    st.markdown("### 📊 Categorias mais usadas")

    df_desp_cat = ler_csv(DESPESAS_FILE)
    if not df_desp_cat.empty and "categoria" in df_desp_cat.columns:
        df_desp_cat["valor"] = pd.to_numeric(df_desp_cat["valor"], errors="coerce").fillna(0)
        uso = df_desp_cat.groupby("categoria").agg(
            Lançamentos=("valor", "count"), Total=("valor", "sum")
        ).reset_index().sort_values("Total", ascending=False)
        uso["Total"] = uso["Total"].apply(formatar_moeda)
        uso.columns = ["Categoria", "Lançamentos", "Total Gasto"]
        st.dataframe(uso, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma despesa cadastrada ainda.")

# ════════════════════════════════════════════════════════════
# ABA 3 — BACKUP
# ════════════════════════════════════════════════════════════
with aba3:
    st.markdown("### 💾 Backup dos Dados")

    col_b1, col_b2 = st.columns(2)

    with col_b1:
        st.markdown("**📤 Exportar Dados**")
        df_exp_d = ler_csv(DESPESAS_FILE)
        df_exp_r = ler_csv(RECEITAS_FILE)
        df_exp_c = ler_csv(CARTOES_FILE)

        if not df_exp_d.empty:
            st.download_button("⬇️ Despesas (CSV)",
                               data=df_exp_d.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                               file_name=f"despesas_backup_{date.today().strftime('%Y%m%d')}.csv",
                               mime="text/csv", use_container_width=True)

        if not df_exp_r.empty:
            st.download_button("⬇️ Receitas (CSV)",
                               data=df_exp_r.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                               file_name=f"receitas_backup_{date.today().strftime('%Y%m%d')}.csv",
                               mime="text/csv", use_container_width=True)

        if not df_exp_c.empty:
            st.download_button("⬇️ Cartões (CSV)",
                               data=df_exp_c.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                               file_name=f"cartoes_backup_{date.today().strftime('%Y%m%d')}.csv",
                               mime="text/csv", use_container_width=True)

        config_str = json.dumps(config, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button("⬇️ Configurações (JSON)",
                           data=config_str,
                           file_name=f"configuracoes_backup_{date.today().strftime('%Y%m%d')}.json",
                           mime="application/json", use_container_width=True)

    with col_b2:
        st.markdown("**📥 Restaurar Backup**")
        tipo_restore = st.selectbox("Tipo de arquivo:", ["Despesas", "Receitas", "Cartões"])
        arquivo_restore = st.file_uploader("Selecione o arquivo CSV:", type=["csv"], key="restore_up")

        if arquivo_restore and st.button("📥 Restaurar", type="primary", use_container_width=True):
            try:
                conteudo = arquivo_restore.read().decode("utf-8-sig")
                df_rest = pd.read_csv(StringIO(conteudo))
                mapa_tabela = {"Despesas": "despesas", "Receitas": "receitas", "Cartões": "cartoes"}
                salvar_parquet(mapa_tabela[tipo_restore], df_rest)
                mensagem_sucesso(f"{tipo_restore} restauradas! ({len(df_rest)} registros)")
            except Exception as e:
                mensagem_erro(f"Erro ao restaurar: {e}")

# ════════════════════════════════════════════════════════════
# ABA 4 — LIMPAR DADOS
# ════════════════════════════════════════════════════════════
with aba4:
    st.markdown("### 🗑️ Limpar Dados")
    st.error("⚠️ ATENÇÃO: Esta ação é irreversível!")

    col_l1, col_l2 = st.columns(2)

    with col_l1:
        if st.button("🗑️ Apagar TODAS as Despesas", use_container_width=True):
            st.session_state["confirm_del_desp"] = True

        if st.session_state.get("confirm_del_desp"):
            st.warning("Tem certeza? Isso apagará TODAS as despesas!")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                if st.button("✅ Sim, apagar", key="confirm_d_yes"):
                    salvar_parquet("despesas", pd.DataFrame())
                    st.session_state["confirm_del_desp"] = False
                    mensagem_sucesso("Despesas apagadas.")
                    st.rerun()
            with col_c2:
                if st.button("❌ Cancelar", key="confirm_d_no"):
                    st.session_state["confirm_del_desp"] = False
                    st.rerun()

    with col_l2:
        if st.button("🗑️ Apagar TODAS as Receitas", use_container_width=True):
            st.session_state["confirm_del_rec"] = True

        if st.session_state.get("confirm_del_rec"):
            st.warning("Tem certeza?")
            col_c3, col_c4 = st.columns(2)
            with col_c3:
                if st.button("✅ Sim, apagar", key="confirm_r_yes"):
                    salvar_parquet("receitas", pd.DataFrame())
                    st.session_state["confirm_del_rec"] = False
                    mensagem_sucesso("Receitas apagadas.")
                    st.rerun()
            with col_c4:
                if st.button("❌ Cancelar", key="confirm_r_no"):
                    st.session_state["confirm_del_rec"] = False
                    st.rerun()

