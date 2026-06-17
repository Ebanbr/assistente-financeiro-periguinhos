# ============================================================
#  9_📥_Importacoes.py — Importação de Dados
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import re
import streamlit as st

from auth import exigir_login
exigir_login()
import pandas as pd
from datetime import datetime
from io import StringIO
from dateutil.relativedelta import relativedelta

from config import (
    DESPESAS_FILE, RECEITAS_FILE, CARTOES_FILE,
    COLUNAS_DESPESAS, COLUNAS_RECEITAS,
)
from utils import (
    configurar_pagina, cabecalho_pagina, inicializar_dados,
    ler_csv, mensagem_sucesso, mensagem_erro, mensagem_aviso,
    formatar_moeda, gerar_id, agora,
    salvar_despesas_novas, salvar_receitas_novas,
    salvar_parquet, remover_por_fonte, listar_cartoes_ativos,
    aplicar_mapeamentos, fuzzy_match_fatura,
)
from activity_log import registrar as log_atividade, exibir_log

configurar_pagina("Importações", icone="📥")
inicializar_dados()

cabecalho_pagina(
    titulo="Importações",
    subtitulo="Notion (BD histórico) · C6 Bank (fatura) · Template manual",
    icone="📥"
)

# ── Helpers ──────────────────────────────────────────────────

def limpar_link_notion(texto) -> str:
    if pd.isna(texto):
        return ""
    return re.sub(r'\s*\(https?://[^\)]*\)', '', str(texto)).strip()

def limpar_valor(texto) -> float:
    if pd.isna(texto):
        return 0.0
    s = re.sub(r'[R$\s"\'"""]', '', str(texto)).replace('-', '')
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return abs(float(s))
    except:
        return 0.0

def to_iso(texto) -> str:
    if pd.isna(texto):
        return ""
    s = str(texto).strip()
    for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"]:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except:
            continue
    return s

def to_br(texto) -> str:
    iso = to_iso(texto)
    if not iso:
        return ""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return iso

def limpar_categoria(prop, fallback: str = "📦 Outros") -> str:
    """Descarta valores inúteis do Notion (só emoji, só checkmark, vazio)."""
    if not prop or pd.isna(prop):
        return fallback
    s = str(prop).strip()
    import unicodedata
    # Verifica se tem pelo menos 2 caracteres alfanuméricos reais
    alfa = [c for c in s if unicodedata.category(c).startswith(("L", "N"))]
    if len(alfa) < 2:
        return fallback
    return s


# ── Abas ─────────────────────────────────────────────────────
aba1, aba2, aba3, aba4, aba5 = st.tabs([
    "📓 Notion (BD)",
    "💳 C6 Bank (Fatura)",
    "📥 Template Manual",
    "🔍 Diagnóstico",
    "📋 Log de Atividades",
])


# ════════════════════════════════════════════════════════════
# ABA 1 — NOTION (Banco de Dados histórico/fixo)
# ════════════════════════════════════════════════════════════
with aba1:
    st.markdown("### 📓 Notion — Banco de Dados")
    st.info(
        "Importa passado, presente e futuro do Notion.\n\n"
        "- **Pago = Sim + Valor Pago preenchido** → status *Pago/Recebida*\n"
        "- **Não pago / sem Data de PG** → status *A Pagar/A Receber* → aparece na **Agenda Financeira**\n\n"
        "**Re-importar substitui todos os dados do Notion** — C6 Bank e Manuais são preservados."
    )

    df_notion_atual = ler_csv(DESPESAS_FILE)
    df_notion_rec   = ler_csv(RECEITAS_FILE)
    n_notion_d = int((df_notion_atual["fonte"] == "Notion").sum()) if not df_notion_atual.empty and "fonte" in df_notion_atual.columns else 0
    n_notion_r = int((df_notion_rec["fonte"] == "Notion").sum())   if not df_notion_rec.empty   and "fonte" in df_notion_rec.columns   else 0
    if n_notion_d or n_notion_r:
        st.caption(f"📊 Atualmente {n_notion_d} despesas e {n_notion_r} receitas do Notion no banco.")

    arquivo_notion = st.file_uploader("CSV exportado do Notion", type=["csv"], key="notion_upload")

    if arquivo_notion:
        try:
            df_raw = pd.read_csv(StringIO(arquivo_notion.read().decode("utf-8-sig")))

            st.markdown("**Colunas encontradas:**")
            st.code(", ".join(df_raw.columns.tolist()))
            st.dataframe(df_raw.head(3), use_container_width=True, hide_index=True)

            if "Vencimento" not in df_raw.columns or "Nome" not in df_raw.columns:
                mensagem_erro("Colunas obrigatórias não encontradas: Vencimento, Nome")
            else:
                # ── Campos base ───────────────────────────────────────
                df_raw["_nome"]      = df_raw["Nome"].apply(limpar_link_notion)
                df_raw["_banco"]     = df_raw["Banco"].apply(limpar_link_notion)     if "Banco"      in df_raw.columns else "Outros"
                df_raw["_prop"]      = df_raw["Propriedade"].apply(limpar_link_notion) if "Propriedade" in df_raw.columns else "📦 Outros"
                df_raw["_vencimento"]= df_raw["Vencimento"].apply(to_iso)

                # ── Data efetiva: usa Data de PG se preenchida, senão Vencimento ──
                def data_efetiva(row):
                    dpg = row.get("Data de PG", "")
                    iso = to_iso(dpg)
                    return iso if iso and iso != str(dpg) or (iso and len(iso) == 10) else row["_vencimento"]

                df_raw["_data"] = df_raw.apply(data_efetiva, axis=1)

                # ── Status: pago se Pago=Yes E Valor Pago > 0 ────────
                def detectar_pago(row):
                    campo_pago = str(row.get("Pago", "")).lower().strip()
                    val_pago   = limpar_valor(row.get("Valor Pago", "0"))
                    data_pg    = str(row.get("Data de PG", "")).strip()
                    foi_pago   = campo_pago in ["yes", "sim", "true", "✅", "1"] and val_pago > 0
                    return foi_pago

                df_raw["_foi_pago"] = df_raw.apply(detectar_pago, axis=1)

                # ── Valores ───────────────────────────────────────────
                # Usa coluna Valor: positivo = receita, negativo = despesa
                # Receitas/Despesas no Notion = valor pago (ficam R$0 se não pago — não usar)
                def parse_valor_com_sinal(texto) -> float:
                    if pd.isna(texto):
                        return 0.0
                    s = str(texto).strip()
                    negativo = "-" in s
                    v = limpar_valor(s)  # limpar_valor já retorna abs
                    return -v if negativo else v

                if "Valor" in df_raw.columns:
                    df_raw["_valor_bruto"] = df_raw["Valor"].apply(parse_valor_com_sinal)
                else:
                    df_raw["_valor_bruto"] = 0.0

                df_raw["_val_rec"]  = df_raw["_valor_bruto"].apply(lambda x: x  if x > 0 else 0.0)
                df_raw["_val_desp"] = df_raw["_valor_bruto"].apply(lambda x: abs(x) if x < 0 else 0.0)

                mask_rec  = df_raw["_val_rec"] > 0
                mask_desp = (df_raw["_val_desp"] > 0) & (~mask_rec)
                df_desp_n = df_raw[mask_desp].copy()
                df_rec_n  = df_raw[mask_rec].copy()

                # ── Resumo de status ──────────────────────────────────
                n_pagos_d   = int(df_desp_n["_foi_pago"].sum())   if not df_desp_n.empty else 0
                n_pagos_r   = int(df_rec_n["_foi_pago"].sum())    if not df_rec_n.empty  else 0
                n_futuros_d = len(df_desp_n) - n_pagos_d
                n_futuros_r = len(df_rec_n)  - n_pagos_r

                st.markdown(
                    f"📊 **{len(df_desp_n)} despesas** ({n_pagos_d} pagas · {n_futuros_d} a pagar)  |  "
                    f"**{len(df_rec_n)} receitas** ({n_pagos_r} recebidas · {n_futuros_r} a receber)"
                )

                # ── Filtro de bancos a excluir (virão da fatura) ──────
                st.divider()
                bancos_no_csv      = sorted(df_raw["_banco"].dropna().unique().tolist())
                cartoes_cadastrados = listar_cartoes_ativos()
                default_excluir    = [b for b in bancos_no_csv if b in cartoes_cadastrados]

                bancos_excluir = st.multiselect(
                    "🚫 Excluir bancos/cartões do Notion (virão da fatura separadamente):",
                    options=bancos_no_csv,
                    default=default_excluir,
                    help="C6 BRU mantém histórico até nov/2025 automaticamente."
                )

                DATA_CORTE_C6  = pd.Timestamp("2025-12-01")
                CORTE_POR_BANCO = {"C6 BRU": DATA_CORTE_C6}

                if bancos_excluir:
                    df_desp_n["_data_ts"] = pd.to_datetime(df_desp_n["_data"], errors="coerce")

                    def deve_manter(row):
                        banco = row["_banco"]
                        if banco not in bancos_excluir:
                            return True
                        corte = CORTE_POR_BANCO.get(banco)
                        if corte and pd.notna(row["_data_ts"]) and row["_data_ts"] < corte:
                            return True
                        return False

                    n_antes = len(df_desp_n)
                    df_desp_n = df_desp_n[df_desp_n.apply(deve_manter, axis=1)].copy()
                    df_desp_n = df_desp_n.drop(columns=["_data_ts"])
                    excluidos = n_antes - len(df_desp_n)
                    if excluidos:
                        st.caption(f"ℹ️ {excluidos} despesa(s) excluída(s) (mantido histórico C6 BRU até nov/2025).")

                # ── Preview ───────────────────────────────────────────
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**💸 {len(df_desp_n)} despesas**")
                    if not df_desp_n.empty:
                        prev = df_desp_n[["_data","_nome","_prop","_val_desp","_banco","_foi_pago"]].copy()
                        prev["_data"]     = prev["_data"].apply(to_br)
                        prev["_val_desp"] = prev["_val_desp"].apply(formatar_moeda)
                        prev["_foi_pago"] = prev["_foi_pago"].apply(lambda x: "✅ Pago" if x else "⏳ A Pagar")
                        prev.columns = ["Data","Descrição","Categoria","Valor","Banco","Status"]
                        st.dataframe(prev, use_container_width=True, hide_index=True, height=280)
                        st.markdown(f"**Total: {formatar_moeda(df_desp_n['_val_desp'].sum())}**")

                with col2:
                    st.markdown(f"**💰 {len(df_rec_n)} receitas**")
                    if not df_rec_n.empty:
                        prev = df_rec_n[["_data","_nome","_val_rec","_banco","_foi_pago"]].copy()
                        prev["_data"]    = prev["_data"].apply(to_br)
                        prev["_val_rec"] = prev["_val_rec"].apply(formatar_moeda)
                        prev["_foi_pago"]= prev["_foi_pago"].apply(lambda x: "✅ Recebida" if x else "⏳ A Receber")
                        prev.columns = ["Data","Descrição","Valor","Banco","Status"]
                        st.dataframe(prev, use_container_width=True, hide_index=True, height=280)
                        st.markdown(f"**Total: {formatar_moeda(df_rec_n['_val_rec'].sum())}**")

                st.divider()

                if n_notion_d or n_notion_r:
                    st.warning(f"⚠️ Re-importar vai substituir {n_notion_d} despesas e {n_notion_r} receitas do Notion. C6 Bank e Manuais não serão afetados.")

                if st.button("✅ Confirmar Importação Notion", type="primary", use_container_width=True):
                    remover_por_fonte("despesas", ["Notion"])
                    remover_por_fonte("receitas",  ["Notion"])

                    total_d = total_r = 0

                    # ── Despesas ─────────────────────────────────────
                    if not df_desp_n.empty:
                        linhas = []
                        for _, r in df_desp_n.iterrows():
                            if not r["_data"] or not r["_nome"]:
                                continue
                            linhas.append({
                                "id":              gerar_id(),
                                "data":            r["_data"],
                                "descricao":       r["_nome"],
                                "categoria":       limpar_categoria(r["_prop"]),
                                "valor":           round(float(r["_val_desp"]), 2),
                                "forma_pagamento": r["_banco"] or "Outros",
                                "banco":           "",
                                "status":          "Pago" if r["_foi_pago"] else "A Pagar",
                                "observacao":      "",
                                "fonte":           "Notion",
                                "criado_em":       agora(),
                            })
                        if linhas:
                            df_notion_d  = aplicar_mapeamentos(pd.DataFrame(linhas))
                            df_existente = ler_csv(DESPESAS_FILE)
                            df_final = pd.concat([df_existente, df_notion_d], ignore_index=True) if not df_existente.empty else df_notion_d
                            salvar_parquet("despesas", df_final)
                            total_d = len(linhas)

                    # ── Receitas ─────────────────────────────────────
                    if not df_rec_n.empty:
                        linhas = []
                        for _, r in df_rec_n.iterrows():
                            if not r["_data"] or not r["_nome"]:
                                continue
                            linhas.append({
                                "id":               gerar_id(),
                                "data":             r["_data"],
                                "descricao":        r["_nome"],
                                "categoria":        limpar_categoria(r["_prop"], fallback="📦 Outros"),
                                "valor":            round(float(r["_val_rec"]), 2),
                                "forma_recebimento": r["_banco"] or "📱 PIX",
                                "status":           "Recebida" if r["_foi_pago"] else "A Receber",
                                "observacao":       "",
                                "fonte":            "Notion",
                                "criado_em":        agora(),
                            })
                        if linhas:
                            df_notion_r  = aplicar_mapeamentos(pd.DataFrame(linhas))
                            df_existente = ler_csv(RECEITAS_FILE)
                            df_final = pd.concat([df_existente, df_notion_r], ignore_index=True) if not df_existente.empty else df_notion_r
                            salvar_parquet("receitas", df_final)
                            total_r = len(linhas)

                    log_atividade("importou Notion", f"{total_d} despesas e {total_r} receitas")
                    mensagem_sucesso(f"Notion atualizado! {total_d} despesas e {total_r} receitas importadas.")
                    st.balloons()

        except Exception as e:
            mensagem_erro(f"Erro: {e}")
            st.exception(e)


# ════════════════════════════════════════════════════════════
# ABA 2 — C6 BANK (Fatura mensal)
# ════════════════════════════════════════════════════════════
with aba2:
    st.markdown("### 💳 C6 Bank — Fatura Mensal")

    MAPA_CAT_C6 = {
        "Especialidade varejo":    "🛒 Compras Online",
        "Vestuário / Roupas":      "👗 Vestuário",
        "Marketing Direto":        "🛒 Compras Online",
        "Empresa para empresa":    "📦 Outros",
        "Departamento / Desconto": "🛒 Compras Online",
        "Alimentação":             "🍽️ Alimentação",
        "Restaurantes":            "🍽️ Alimentação",
        "Saúde":                   "💊 Saúde",
        "Educação":                "📚 Educação",
        "Transporte":              "🚗 Transporte",
        "Entretenimento":          "🎮 Lazer",
        "Viagens":                 "✈️ Viagens",
        "Farmácias":               "💊 Saúde",
        "Supermercados":           "🍽️ Alimentação",
        "Postos de Combustível":   "🚗 Transporte",
    }
    MESES_NOME = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

    cartoes_df    = ler_csv(CARTOES_FILE)
    nomes_cartoes = cartoes_df["nome"].tolist() if not cartoes_df.empty and "nome" in cartoes_df.columns else []

    if nomes_cartoes:
        cartao_sel = st.selectbox("Cartão desta fatura:", nomes_cartoes)
    else:
        cartao_sel = st.text_input("Nome do cartão:", value="C6 BRU")

    modo = st.radio(
        "Modo de importação:",
        ["📄 Fatura única (1 mês)", "📦 CSV unificado (múltiplos meses)"],
        horizontal=True,
        key="modo_c6"
    )

    # ── Modo fatura única ─────────────────────────────────────
    if modo == "📄 Fatura única (1 mês)":
        st.info(
            "Importe a fatura fechada do mês. O app vai:\n"
            "- Remover os lançamentos do **Notion** desse cartão/mês\n"
            "- Remover lançamentos **Manuais** desse cartão/mês\n"
            "- Inserir os itens **oficiais da fatura** no lugar"
        )

        col_mes, col_ano = st.columns(2)
        with col_mes:
            mes_fatura = st.selectbox(
                "Mês da Fatura:",
                range(1, 13),
                index=datetime.now().month - 1,
                format_func=lambda m: MESES_NOME[m-1],
                key="mes_fat_c6"
            )
        with col_ano:
            ano_fatura = st.selectbox(
                "Ano da Fatura:",
                range(2024, 2028),
                index=1,
                key="ano_fat_c6"
            )

        data_fat_fmt = f"{ano_fatura:04d}-{mes_fatura:02d}-01"

        df_atual = ler_csv(DESPESAS_FILE)
        if not df_atual.empty and "fonte" in df_atual.columns and "data" in df_atual.columns:
            dt_col = pd.to_datetime(df_atual["data"], format="%Y-%m-%d", errors="coerce")
            mesmo_mes = (dt_col.dt.month == mes_fatura) & (dt_col.dt.year == ano_fatura)
            cartao_lower = cartao_sel.strip().lower()
            bate_cartao = (
                df_atual["forma_pagamento"].astype(str).str.strip().str.lower().eq(cartao_lower) |
                df_atual["banco"].astype(str).str.strip().str.lower().eq(cartao_lower) if "banco" in df_atual.columns else pd.Series([False]*len(df_atual))
            )
            serao_removidos = df_atual[mesmo_mes & bate_cartao & df_atual["fonte"].isin(["Notion","Manual"])]
            if not serao_removidos.empty:
                st.warning(
                    f"⚠️ {len(serao_removidos)} lançamento(s) de **{cartao_sel}** em "
                    f"{mes_fatura:02d}/{ano_fatura} serão substituídos pela fatura oficial."
                )
                with st.expander("Ver o que será substituído"):
                    st.dataframe(
                        serao_removidos[["data","descricao","valor","fonte"]].assign(
                            data=serao_removidos["data"].apply(to_br)
                        ),
                        use_container_width=True, hide_index=True
                    )

        arquivo_c6 = st.file_uploader("CSV da fatura C6 (separado por ;)", type=["csv"], key="c6_upload")

        if arquivo_c6:
            try:
                df_c6 = pd.read_csv(StringIO(arquivo_c6.read().decode("utf-8-sig")), sep=";")
                st.dataframe(df_c6.head(5), use_container_width=True, hide_index=True)

                colunas_req = ["Data de Compra", "Descrição", "Categoria", "Valor (em R$)"]
                faltando = [c for c in colunas_req if c not in df_c6.columns]
                if faltando:
                    mensagem_erro(f"Colunas não encontradas: {faltando}")
                else:
                    ignorar = ["Inclusao","Inclusão","Estorno","Anuidade","Taxa","Juros"]
                    df_c6 = df_c6[~df_c6["Descrição"].str.contains("|".join(ignorar), case=False, na=False)].copy()
                    df_c6["_val"] = pd.to_numeric(df_c6["Valor (em R$)"], errors="coerce")

                    df_desp  = df_c6[df_c6["_val"] > 0].copy()
                    df_devol = df_c6[df_c6["_val"] < 0].copy()

                    df_desp["_data_orig"] = df_desp["Data de Compra"].apply(to_br)
                    df_desp["_valor"]     = df_desp["_val"].abs()
                    df_desp["_desc"]      = df_desp["Descrição"].str.strip()
                    df_desp["_cat"]       = df_desp["Categoria"].apply(lambda x: MAPA_CAT_C6.get(str(x).strip(), "📦 Outros"))

                    # ── Herdar categorias de lançamentos anteriores ───
                    # Se o mesmo estabelecimento já foi categorizado antes, usa essa categoria
                    df_historico = ler_csv(DESPESAS_FILE)
                    if not df_historico.empty and "descricao" in df_historico.columns and "categoria" in df_historico.columns:
                        df_historico["categoria"] = df_historico["categoria"].astype(str)
                        # Mapeia descrição → categoria mais usada no histórico
                        cat_historico = (
                            df_historico[~df_historico["categoria"].str.contains("Outros", na=False)]
                            .groupby("descricao")["categoria"]
                            .agg(lambda x: x.value_counts().index[0])
                            .to_dict()
                        )
                        def herdar_categoria(row):
                            if row["_cat"] != "📦 Outros":
                                return row["_cat"]  # já tem categoria boa pelo MAPA_CAT_C6
                            return cat_historico.get(row["_desc"], "📦 Outros")
                        df_desp["_cat"] = df_desp.apply(herdar_categoria, axis=1)

                    df_devol["_data_orig"] = df_devol["Data de Compra"].apply(to_br)
                    df_devol["_valor"]     = df_devol["_val"].abs()
                    df_devol["_desc"]      = df_devol["Descrição"].apply(lambda x: f"Reembolso - {str(x).strip()}")

                    st.markdown(f"**✅ {len(df_desp)} despesas · {len(df_devol)} reembolsos — Fatura {MESES_NOME[mes_fatura-1]}/{ano_fatura}**")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**💸 Despesas ({len(df_desp)})**")
                        if not df_desp.empty:
                            prev = df_desp[["_data_orig","_desc","_valor"]].copy()
                            prev.columns = ["Compra","Descrição","Valor"]
                            prev["Valor"] = prev["Valor"].apply(formatar_moeda)
                            st.dataframe(prev, use_container_width=True, hide_index=True, height=280)
                            st.markdown(f"**Total: {formatar_moeda(df_desp['_valor'].sum())}**")
                    with col2:
                        st.markdown(f"**💰 Reembolsos ({len(df_devol)})**")
                        if not df_devol.empty:
                            prev = df_devol[["_data_orig","_desc","_valor"]].copy()
                            prev.columns = ["Compra","Descrição","Valor"]
                            prev["Valor"] = prev["Valor"].apply(formatar_moeda)
                            st.dataframe(prev, use_container_width=True, hide_index=True, height=280)
                            st.markdown(f"**Total: {formatar_moeda(df_devol['_valor'].sum())}**")

                    st.divider()

                    # ── Fuzzy matching: compara fatura com lançamentos existentes ──
                    df_existente_cartao = pd.DataFrame()
                    if not df_historico.empty and "data" in df_historico.columns:
                        dt_col = pd.to_datetime(df_historico["data"], errors="coerce")
                        mask_cartao = (
                            df_historico.get("forma_pagamento", pd.Series(dtype=str)).astype(str).str.strip().str.lower().eq(cartao_sel.strip().lower()) |
                            df_historico.get("banco", pd.Series(dtype=str)).astype(str).str.strip().str.lower().eq(cartao_sel.strip().lower())
                        )
                        df_existente_cartao = df_historico[mask_cartao].copy()

                    resultado_fuzzy = fuzzy_match_fatura(df_desp, df_existente_cartao, similaridade_min=75, janela_dias=5)
                    idxs_dup  = set(resultado_fuzzy["duplicatas"])
                    idxs_novo = set(resultado_fuzzy["novos"])
                    matches   = resultado_fuzzy["matches"]

                    df_ja_existe = df_desp.loc[list(idxs_dup)] if idxs_dup else pd.DataFrame()
                    df_a_inserir = df_desp.loc[list(idxs_novo)] if idxs_novo else pd.DataFrame()

                    # Preview inteligente
                    if not df_ja_existe.empty:
                        with st.expander(f"✅ {len(df_ja_existe)} item(ns) já lançados — não serão duplicados", expanded=False):
                            for i, m in enumerate(matches):
                                idx_fat, idx_ex, score = m
                                row_fat = df_desp.loc[idx_fat]
                                row_ex  = df_existente_cartao.loc[idx_ex] if idx_ex in df_existente_cartao.index else None
                                desc_ex = row_ex["descricao"] if row_ex is not None else "?"
                                cat_ex  = row_ex["categoria"] if row_ex is not None else "?"
                                st.markdown(
                                    f"🔗 **{row_fat['_desc']}** → já existe como *\"{desc_ex}\"* "
                                    f"(similaridade {score}%) · categoria mantida: **{cat_ex}**"
                                )

                    if not df_a_inserir.empty:
                        with st.expander(f"🆕 {len(df_a_inserir)} item(ns) novos — serão inseridos", expanded=True):
                            prev = df_a_inserir[["_data_orig","_desc","_valor","_cat"]].copy()
                            prev.columns = ["Compra","Descrição","Valor","Categoria"]
                            prev["Valor"] = prev["Valor"].apply(formatar_moeda)
                            st.dataframe(prev, use_container_width=True, hide_index=True)
                    else:
                        st.success("🎉 Todos os itens da fatura já estão lançados! Nenhuma ação necessária.")

                    if not df_a_inserir.empty:
                        if st.button("✅ Confirmar Importação C6", type="primary", use_container_width=True, key="btn_c6_unico"):
                            total_d = total_r = 0
                            linhas = []
                            for _, r in df_a_inserir.iterrows():
                                linhas.append({
                                    "id": gerar_id(), "data": data_fat_fmt,
                                    "descricao": r["_desc"], "categoria": r["_cat"],
                                    "valor": round(float(r["_valor"]), 2),
                                    "forma_pagamento": "💳 Crédito", "banco": cartao_sel,
                                    "status": "Pago", "observacao": f"Compra em {r['_data_orig']}",
                                    "fonte": "C6 Bank", "criado_em": agora(),
                                })
                            if linhas:
                                total_d = salvar_despesas_novas(aplicar_mapeamentos(pd.DataFrame(linhas)))

                            if not df_devol.empty:
                                linhas_r = []
                                for _, r in df_devol.iterrows():
                                    linhas_r.append({
                                        "id": gerar_id(), "data": data_fat_fmt,
                                        "descricao": r["_desc"], "categoria": "🔄 Reembolso",
                                        "valor": round(float(r["_valor"]), 2),
                                        "forma_recebimento": "💳 Crédito no Cartão", "status": "Pago",
                                        "observacao": f"Reembolso de {r['_data_orig']}",
                                        "fonte": "C6 Bank", "criado_em": agora(),
                                    })
                                if linhas_r:
                                    total_r = salvar_receitas_novas(pd.DataFrame(linhas_r))

                            log_atividade("importou fatura C6 (único mês)", f"{total_d} novos + {len(df_ja_existe)} já existiam")
                            mensagem_sucesso(f"✅ {total_d} novos lançamentos importados! ({len(df_ja_existe)} duplicatas ignoradas)")
                            st.balloons()

            except Exception as e:
                mensagem_erro(f"Erro: {e}")
                st.exception(e)

    # ── Modo CSV unificado (múltiplos meses) ──────────────────
    else:
        st.info(
            "Envie um CSV com faturas de **vários meses juntos**. O app detecta os meses automaticamente, "
            "exibe um resumo por mês e importa tudo de uma vez."
        )

        arquivo_c6_multi = st.file_uploader("CSV unificado C6 (separado por ;)", type=["csv"], key="c6_multi_upload")

        if arquivo_c6_multi:
            try:
                df_c6 = pd.read_csv(StringIO(arquivo_c6_multi.read().decode("utf-8-sig")), sep=";")

                colunas_req = ["Data de Compra", "Descrição", "Categoria", "Valor (em R$)"]
                faltando = [c for c in colunas_req if c not in df_c6.columns]
                if faltando:
                    mensagem_erro(f"Colunas não encontradas: {faltando}")
                else:
                    ignorar = ["Inclusao","Inclusão","Estorno","Anuidade","Taxa","Juros"]
                    df_c6 = df_c6[~df_c6["Descrição"].str.contains("|".join(ignorar), case=False, na=False)].copy()
                    df_c6["_val"]      = pd.to_numeric(df_c6["Valor (em R$)"], errors="coerce")
                    df_c6["_data_ts"]  = pd.to_datetime(df_c6["Data de Compra"], dayfirst=True, errors="coerce")
                    df_c6["_data_orig"]= df_c6["Data de Compra"].apply(to_br)
                    df_c6["_desc"]     = df_c6["Descrição"].str.strip()
                    df_c6["_cat"]      = df_c6["Categoria"].apply(lambda x: MAPA_CAT_C6.get(str(x).strip(), "📦 Outros"))

                    # Dia de fechamento para calcular mês correto da fatura
                    dia_fech_multi = st.number_input(
                        "Dia de fechamento do cartão:", min_value=1, max_value=28, value=10,
                        key="dia_fech_multi",
                        help="Compras APÓS esse dia vão para a fatura do mês seguinte"
                    )

                    # Calcula mês de fatura real (compra após fechamento → próximo mês)
                    def _mes_fat(dt, dia_fech):
                        if pd.isna(dt): return (0, 0)
                        if dt.day > dia_fech:
                            prox = dt + relativedelta(months=1)
                            return (prox.year, prox.month)
                        return (dt.year, dt.month)

                    df_c6["_fat_ano"] = df_c6["_data_ts"].apply(lambda d: _mes_fat(d, dia_fech_multi)[0])
                    df_c6["_fat_mes"] = df_c6["_data_ts"].apply(lambda d: _mes_fat(d, dia_fech_multi)[1])
                    # Aliases para compatibilidade com código abaixo
                    df_c6["_ano"] = df_c6["_fat_ano"]
                    df_c6["_mes"] = df_c6["_fat_mes"]

                    # Detecta meses de fatura presentes
                    meses_presentes = (
                        df_c6[["_fat_ano","_fat_mes"]].dropna()
                        .drop_duplicates()
                        .sort_values(["_fat_ano","_fat_mes"])
                        .values.tolist()
                    )
                    meses_presentes = [(int(a), int(m)) for a, m in meses_presentes if a > 0]

                    st.markdown(f"**📅 {len(meses_presentes)} faturas detectadas:** " +
                                ", ".join(f"{MESES_NOME[m-1]}/{a}" for a, m in meses_presentes))

                    # Resumo por mês
                    resumo = []
                    for ano_f, mes_f in meses_presentes:
                        sub = df_c6[(df_c6["_ano"] == ano_f) & (df_c6["_mes"] == mes_f)]
                        desp  = sub[sub["_val"] > 0]["_val"].sum()
                        devol = sub[sub["_val"] < 0]["_val"].abs().sum()
                        resumo.append({
                            "Mês": f"{MESES_NOME[mes_f-1]}/{ano_f}",
                            "Despesas": formatar_moeda(desp),
                            "Reembolsos": formatar_moeda(devol),
                            "Itens": len(sub),
                        })
                    st.dataframe(pd.DataFrame(resumo), use_container_width=True, hide_index=True)

                    with st.expander("👁️ Ver todos os lançamentos"):
                        prev = df_c6[["_data_orig","_desc","_cat","_val"]].copy()
                        prev.columns = ["Compra","Descrição","Categoria","Valor"]
                        prev["Valor"] = prev["Valor"].apply(formatar_moeda)
                        st.dataframe(prev, use_container_width=True, hide_index=True, height=350)

                    st.divider()

                    df_atual = ler_csv(DESPESAS_FILE)
                    total_serao_removidos = 0
                    if not df_atual.empty and "fonte" in df_atual.columns:
                        cartao_lower = cartao_sel.strip().lower()
                        for ano_f, mes_f in meses_presentes:
                            dt_col = pd.to_datetime(df_atual["data"], format="%Y-%m-%d", errors="coerce")
                            mesmo_mes = (dt_col.dt.month == mes_f) & (dt_col.dt.year == ano_f)
                            bate_cartao = (
                                df_atual["forma_pagamento"].astype(str).str.strip().str.lower().eq(cartao_lower) |
                                df_atual["banco"].astype(str).str.strip().str.lower().eq(cartao_lower) if "banco" in df_atual.columns else pd.Series([False]*len(df_atual))
                            )
                            total_serao_removidos += int((mesmo_mes & bate_cartao & df_atual["fonte"].isin(["Notion","Manual"])).sum())

                    if total_serao_removidos:
                        st.warning(f"⚠️ {total_serao_removidos} lançamento(s) existentes de **{cartao_sel}** serão substituídos nos meses importados.")

                    if st.button("✅ Confirmar Importação C6 (todos os meses)", type="primary", use_container_width=True, key="btn_c6_multi"):
                        total_d = total_r = total_rem = 0

                        for ano_f, mes_f in meses_presentes:
                            data_fat_fmt = f"{ano_f:04d}-{mes_f:02d}-01"
                            sub = df_c6[(df_c6["_ano"] == ano_f) & (df_c6["_mes"] == mes_f)]

                            n_rem = remover_por_fonte("despesas", fontes=["Notion","Manual"],
                                                      mes=mes_f, ano=ano_f, cartao=cartao_sel)
                            total_rem += n_rem

                            df_desp  = sub[sub["_val"] > 0].copy()
                            df_devol = sub[sub["_val"] < 0].copy()

                            if not df_desp.empty:
                                linhas = []
                                for _, r in df_desp.iterrows():
                                    linhas.append({
                                        "id": gerar_id(), "data": data_fat_fmt,
                                        "descricao": r["_desc"], "categoria": r["_cat"],
                                        "valor": round(float(r["_val"]), 2),
                                        "forma_pagamento": "💳 Crédito", "banco": cartao_sel,
                                        "status": "Pago", "observacao": f"Compra em {r['_data_orig']}",
                                        "fonte": "C6 Bank", "criado_em": agora(),
                                    })
                                if linhas:
                                    total_d += salvar_despesas_novas(aplicar_mapeamentos(pd.DataFrame(linhas)))

                            if not df_devol.empty:
                                linhas = []
                                for _, r in df_devol.iterrows():
                                    linhas.append({
                                        "id": gerar_id(), "data": data_fat_fmt,
                                        "descricao": f"Reembolso - {r['_desc']}",
                                        "categoria": "🔄 Reembolso",
                                        "valor": round(abs(float(r["_val"])), 2),
                                        "forma_recebimento": "💳 Crédito no Cartão", "status": "Pago",
                                        "observacao": f"Reembolso de {r['_data_orig']}",
                                        "fonte": "C6 Bank", "criado_em": agora(),
                                    })
                                if linhas:
                                    total_r += salvar_receitas_novas(pd.DataFrame(linhas))

                        if total_rem:
                            st.info(f"🔄 {total_rem} lançamento(s) substituídos.")
                        log_atividade("importou fatura C6 (múltiplos meses)", f"{total_d} despesas em {len(meses_presentes)} meses")
                        mensagem_sucesso(f"✅ {total_d} despesas e {total_r} reembolsos importados em {len(meses_presentes)} meses!")
                        st.balloons()

            except Exception as e:
                mensagem_erro(f"Erro: {e}")
                st.exception(e)


# ════════════════════════════════════════════════════════════
# ABA 3 — TEMPLATE MANUAL
# ════════════════════════════════════════════════════════════
with aba3:
    st.markdown("### 📥 Template Manual")
    st.info("Use para importar lançamentos em massa via CSV. Lançamentos individuais use a página **Lançamentos**.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Template Despesas**")
        ex_d = pd.DataFrame([{
            "data": "2025-05-15", "descricao": "Supermercado",
            "categoria": "🍽️ Alimentação", "valor": 250.00,
            "forma_pagamento": "💳 Débito", "banco": "", "status": "Pago", "observacao": ""
        }])
        st.download_button("⬇️ Baixar", data=ex_d.to_csv(index=False).encode("utf-8-sig"),
                           file_name="template_despesas.csv", mime="text/csv", use_container_width=True)

    with col2:
        st.markdown("**Template Receitas**")
        ex_r = pd.DataFrame([{
            "data": "2025-05-01", "descricao": "Salário",
            "categoria": "💼 Salário", "valor": 5000.00,
            "forma_recebimento": "🏦 Transferência", "status": "Pago", "observacao": ""
        }])
        st.download_button("⬇️ Baixar", data=ex_r.to_csv(index=False).encode("utf-8-sig"),
                           file_name="template_receitas.csv", mime="text/csv", use_container_width=True)

    st.caption("Data no formato yyyy-mm-dd (ex: 2025-05-15)")
    st.divider()

    tipo = st.radio("Tipo:", ["Despesas", "Receitas"], horizontal=True)
    arq  = st.file_uploader("Selecione o CSV preenchido", type=["csv"], key="tmpl_up")

    if arq:
        try:
            df_t = pd.read_csv(StringIO(arq.read().decode("utf-8-sig")))
            st.dataframe(df_t.head(10), use_container_width=True, hide_index=True)
            if st.button("✅ Importar", type="primary", use_container_width=True):
                df_t["id"]        = [gerar_id() for _ in range(len(df_t))]
                df_t["criado_em"] = agora()
                df_t["fonte"]     = "Manual"
                df_t["valor"]     = pd.to_numeric(df_t["valor"], errors="coerce").fillna(0)
                df_t["data"]      = df_t["data"].apply(to_iso)
                fn = salvar_despesas_novas if tipo == "Despesas" else salvar_receitas_novas
                mensagem_sucesso(f"{fn(df_t)} {tipo.lower()} importadas!")
        except Exception as e:
            mensagem_erro(f"Erro: {e}")


# ════════════════════════════════════════════════════════════
# ABA 4 — DIAGNÓSTICO
# ════════════════════════════════════════════════════════════
with aba4:
    st.markdown("### 🔍 Diagnóstico")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 💸 Despesas por fonte")
        df_d = ler_csv(DESPESAS_FILE)
        if df_d.empty:
            st.warning("Sem despesas.")
        else:
            st.success(f"✅ {len(df_d)} registros totais")
            if "fonte" in df_d.columns:
                resumo = df_d.groupby("fonte").size().reset_index(name="Qtd")
                st.dataframe(resumo, use_container_width=True, hide_index=True)
            if "data" in df_d.columns:
                df_d["valor"] = pd.to_numeric(df_d["valor"], errors="coerce").fillna(0)
                df_d["_dt"]   = pd.to_datetime(df_d["data"], format="%Y-%m-%d", errors="coerce")
                por_ano = df_d.groupby(df_d["_dt"].dt.year)["valor"].agg(["count","sum"])
                por_ano.columns = ["Qtd","Total"]
                por_ano["Total"] = por_ano["Total"].apply(formatar_moeda)
                st.dataframe(por_ano, use_container_width=True)

    with col2:
        st.markdown("#### 💰 Receitas por fonte")
        df_r = ler_csv(RECEITAS_FILE)
        if df_r.empty:
            st.warning("Sem receitas.")
        else:
            st.success(f"✅ {len(df_r)} registros totais")
            if "fonte" in df_r.columns:
                resumo = df_r.groupby("fonte").size().reset_index(name="Qtd")
                st.dataframe(resumo, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### 🗑️ Limpar por fonte")
    st.error("⚠️ Irreversível!")

    col_l1, col_l2, col_l3 = st.columns(3)

    for col_btn, fonte_nome in zip([col_l1, col_l2, col_l3], ["Notion", "C6 Bank", "Manual"]):
        with col_btn:
            key_btn  = f"btn_del_{fonte_nome}"
            key_conf = f"conf_del_{fonte_nome}"
            if st.button(f"🗑️ Limpar {fonte_nome}", use_container_width=True, key=key_btn):
                st.session_state[key_conf] = True
            if st.session_state.get(key_conf):
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Sim", key=f"ok_{fonte_nome}"):
                        remover_por_fonte("despesas", [fonte_nome])
                        remover_por_fonte("receitas", [fonte_nome])
                        st.session_state[key_conf] = False
                        mensagem_sucesso(f"{fonte_nome} removido!")
                        st.rerun()
                with c2:
                    if st.button("❌ Não", key=f"no_{fonte_nome}"):
                        st.session_state[key_conf] = False
                        st.rerun()


# ════════════════════════════════════════════════════════════
# ABA 5 — LOG DE ATIVIDADES
# ════════════════════════════════════════════════════════════
with aba5:
    st.markdown("### 📋 Log de Atividades")
    st.caption("Registro de importações e lançamentos feitos pela família.")
    st.divider()
    exibir_log(limite=100)
