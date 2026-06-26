# ============================================================
#  4_📋_Dados.py — Central de Dados
#  Lançamentos · Editar · Importar · Categorias
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st

from auth import exigir_login
exigir_login()

import pandas as pd
import re
import unicodedata
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from io import StringIO

from rapidfuzz import process, fuzz

from config import (
    DESPESAS_FILE, RECEITAS_FILE, CARTOES_FILE,
    MAPEAMENTOS_FILE, MESES_PT, MAPEAMENTOS_PADRAO,
    COLUNAS_DESPESAS, COLUNAS_RECEITAS,
)
from utils import (
    configurar_pagina, cabecalho_pagina, inicializar_dados,
    ler_csv, salvar_parquet, mensagem_sucesso, mensagem_erro, mensagem_aviso,
    formatar_moeda, gerar_id, agora,
    salvar_despesas_novas, salvar_receitas_novas,
    listar_cartoes_ativos, listar_categorias,
    aplicar_mapeamentos, remover_por_fonte,
)
from activity_log import registrar as log_atividade

configurar_pagina("Dados", icone="📋")
inicializar_dados()
cabecalho_pagina(
    titulo="Central de Dados",
    subtitulo="Lançamentos · Editar · Categorias · Importar",
    icone="📋",
)

# ══════════════════════════════════════════════════════════════
# HELPERS GERAIS
# ══════════════════════════════════════════════════════════════

_CHAVES_FORM = ["desc_desp", "desc_rec", "sug_desp", "sug_rec"]

def _limpar_form():
    for k in _CHAVES_FORM:
        st.session_state.pop(k, None)

def _sugerir(texto, historico_df, limite=5, score_min=55):
    if not texto or len(texto) < 2 or historico_df.empty:
        return []
    descs = historico_df["descricao"].dropna().unique().tolist()
    matches = process.extract(texto, descs, scorer=fuzz.partial_ratio, limit=limite, score_cutoff=score_min)
    resultado = []
    for desc, score, _ in matches:
        cats = historico_df[historico_df["descricao"] == desc]["categoria"].dropna()
        cat  = cats.mode().iloc[0] if not cats.empty else ""
        resultado.append((desc, cat, score))
    return resultado

# ── Helpers importação ──────────────────────────────────────

def limpar_link_notion(texto):
    if pd.isna(texto): return ""
    return re.sub(r'\s*\(https?://[^\)]*\)', '', str(texto)).strip()

def limpar_valor(texto):
    if pd.isna(texto): return 0.0
    s = re.sub(r'[R$\s"\'"""]', '', str(texto)).replace('-', '')
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try: return abs(float(s))
    except: return 0.0

def to_iso(texto):
    if pd.isna(texto): return ""
    s = str(texto).strip()
    for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"]:
        try: return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except: continue
    return s

def to_br(texto):
    iso = to_iso(texto)
    if not iso: return ""
    try: return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return iso

def limpar_categoria(prop, fallback="📦 Outros"):
    if not prop or pd.isna(prop): return fallback
    s = str(prop).strip()
    alfa = [c for c in s if unicodedata.category(c).startswith(("L", "N"))]
    if len(alfa) < 2: return fallback
    return s

# ══════════════════════════════════════════════════════════════
# ABAS PRINCIPAIS
# ══════════════════════════════════════════════════════════════

tab_lanc, tab_cats, tab_import = st.tabs([
    "📋 Lançamentos",
    "🏷️ Categorias & Regras",
    "📥 Importar",
])

# ══════════════════════════════════════════════════════════════
# TAB 1 — LANÇAMENTOS
# ══════════════════════════════════════════════════════════════
with tab_lanc:

    # ── Formulário rápido ─────────────────────────────────────
    with st.expander("➕ Novo Lançamento", expanded=False):
        col_tipo, col_data = st.columns([1, 1])
        with col_tipo:
            tipo_form = st.radio("Tipo:", ["💸 Despesa", "💰 Receita"], horizontal=True, key="tipo_form")
        with col_data:
            data_form = st.date_input("Data:", value=date.today(), format="DD/MM/YYYY", key="data_form")

        _hist_desp = ler_csv(DESPESAS_FILE)
        _hist_rec  = ler_csv(RECEITAS_FILE)

        if "💸" in tipo_form:
            col1, col2 = st.columns(2)
            with col1:
                desc_input = st.text_input("Descrição:", key="desc_desp")
                valor_form = st.number_input("Valor (R$):", min_value=0.0, step=0.01, key="valor_desp")

            sugestoes_d = _sugerir(desc_input, _hist_desp) if desc_input else []
            cat_sug_d   = ""
            desc_form   = desc_input

            if sugestoes_d:
                opts = ["✏️ Usar como digitado"] + [f"{d}  ({s}%)" for d, _, s in sugestoes_d]
                with col1:
                    esc = st.selectbox("💡 Sugestões:", opts, key="sug_desp")
                if esc != "✏️ Usar como digitado":
                    idx = opts.index(esc) - 1
                    desc_form, cat_sug_d, _ = sugestoes_d[idx]
                    st.caption(f"✅ **{desc_form}** · Categoria: **{cat_sug_d}**")

            with col2:
                cats_d  = listar_categorias("despesa")
                idx_cat = (cats_d.index(cat_sug_d) + 1) if cat_sug_d in cats_d else 0
                cat_sel = st.selectbox("Categoria:", ["➕ Nova categoria..."] + cats_d, index=idx_cat, key="cat_desp")
                cat_form = st.text_input("Nome:", placeholder="Ex: 🎮 Games", key="nova_cat_desp") if cat_sel == "➕ Nova categoria..." else cat_sel

            col3, col4 = st.columns(2)
            cartoes = listar_cartoes_ativos()
            opts_pag = ["💵 Dinheiro", "📱 PIX", "💳 Débito", "🏦 Transferência"] + (cartoes or [])
            with col3:
                forma_form = st.selectbox("Forma de pagamento:", opts_pag, key="forma_desp")
            with col4:
                if forma_form in cartoes:
                    banco_form = forma_form
                    st.caption("✅ Banco pelo cartão.")
                else:
                    _df_bancos = ler_csv("bancos")
                    _bancos = _df_bancos["nome"].tolist() if not _df_bancos.empty and "nome" in _df_bancos.columns else ["C6 BRU","C6 PRI","Nubank","Itaú"]
                    banco_form = st.selectbox("Banco:", _bancos, key="banco_desp")

            if forma_form in cartoes:
                status_form = "Pago"
                st.caption("✅ Status: Pago (cartão).")
            else:
                status_form = st.selectbox("Status:", ["A Pagar", "Agendado", "Pendente", "Pago"], key="status_desp")
            obs_form = st.text_area("Obs:", height=50, key="obs_desp")

            recorrente = st.checkbox("🔁 Recorrente?", key="rec_desp")
            meses_rep  = 1
            if recorrente:
                meses_rep = st.number_input("Meses (incluindo este):", min_value=2, max_value=60, value=3, key="meses_desp")
                st.caption(f"{meses_rep} lançamentos · {data_form.strftime('%m/%Y')} → {(data_form + relativedelta(months=meses_rep-1)).strftime('%m/%Y')}")

            if st.button("✅ Salvar Despesa", type="primary", use_container_width=True, key="btn_salvar_desp"):
                if not desc_form or valor_form == 0:
                    mensagem_erro("Preencha descrição e valor!")
                elif not cat_form or not cat_form.strip():
                    mensagem_erro("Preencha a categoria!")
                else:
                    linhas = []
                    for i in range(int(meses_rep)):
                        data_i = data_form + relativedelta(months=i)
                        obs_i  = obs_form + (f" ({i+1}/{meses_rep})" if recorrente else "")
                        linhas.append({
                            "id": gerar_id(), "data": data_i.strftime("%Y-%m-%d"),
                            "descricao": desc_form, "categoria": cat_form.strip(),
                            "valor": round(valor_form, 2), "forma_pagamento": forma_form,
                            "banco": banco_form, "status": status_form,
                            "observacao": obs_i, "fonte": "Manual", "criado_em": agora(),
                        })
                    salvos = salvar_despesas_novas(pd.DataFrame(linhas))
                    if salvos > 0:
                        st.cache_data.clear()
                        _limpar_form()
                        log_atividade("lançou despesa", f"{desc_form} · {formatar_moeda(valor_form)}" + (f" · {salvos}x" if recorrente else ""))
                        mensagem_sucesso(f"{'Despesa' if not recorrente else f'{salvos} despesas'} registrada(s)!")
                        st.rerun()
                    elif salvos == 0:
                        mensagem_erro("Já existe um registro com mesma data, descrição e valor.")
                    elif salvos == -1:
                        mensagem_erro("Erro de conexão. Tente novamente.")

        else:  # Receita
            col1, col2 = st.columns(2)
            with col1:
                desc_input = st.text_input("Descrição:", key="desc_rec")
                valor_form = st.number_input("Valor (R$):", min_value=0.0, step=0.01, key="valor_rec")

            sugestoes_r = _sugerir(desc_input, _hist_rec) if desc_input else []
            cat_sug_r   = ""
            desc_form   = desc_input

            if sugestoes_r:
                opts = ["✏️ Usar como digitado"] + [f"{d}  ({s}%)" for d, _, s in sugestoes_r]
                with col1:
                    esc = st.selectbox("💡 Sugestões:", opts, key="sug_rec")
                if esc != "✏️ Usar como digitado":
                    idx = opts.index(esc) - 1
                    desc_form, cat_sug_r, _ = sugestoes_r[idx]
                    st.caption(f"✅ **{desc_form}** · Categoria: **{cat_sug_r}**")

            with col2:
                cats_r  = listar_categorias("receita")
                idx_cat = (cats_r.index(cat_sug_r) + 1) if cat_sug_r in cats_r else 0
                cat_sel = st.selectbox("Categoria:", ["➕ Nova categoria..."] + cats_r, index=idx_cat, key="cat_rec")
                cat_form = st.text_input("Nome:", placeholder="Ex: 💡 Consultoria", key="nova_cat_rec") if cat_sel == "➕ Nova categoria..." else cat_sel

            forma_rec_form = st.selectbox("Forma:", ["🏦 Transferência", "📱 PIX", "💵 Dinheiro", "💳 Crédito"], key="forma_rec")
            status_form    = st.selectbox("Status:", ["A Receber", "Agendado", "Pendente", "Recebida"], key="status_rec")
            obs_form       = st.text_area("Obs:", height=50, key="obs_rec")

            recorrente = st.checkbox("🔁 Recorrente?", key="rec_rec")
            meses_rep  = 1
            if recorrente:
                meses_rep = st.number_input("Meses:", min_value=2, max_value=60, value=3, key="meses_rec")

            if st.button("✅ Salvar Receita", type="primary", use_container_width=True, key="btn_salvar_rec"):
                if not desc_form or valor_form == 0:
                    mensagem_erro("Preencha descrição e valor!")
                elif not cat_form or not cat_form.strip():
                    mensagem_erro("Preencha a categoria!")
                else:
                    linhas = []
                    for i in range(int(meses_rep)):
                        data_i = data_form + relativedelta(months=i)
                        obs_i  = obs_form + (f" ({i+1}/{meses_rep})" if recorrente else "")
                        linhas.append({
                            "id": gerar_id(), "data": data_i.strftime("%Y-%m-%d"),
                            "descricao": desc_form, "categoria": cat_form.strip(),
                            "valor": round(valor_form, 2), "forma_recebimento": forma_rec_form,
                            "status": status_form, "observacao": obs_i,
                            "fonte": "Manual", "criado_em": agora(),
                        })
                    salvos = salvar_receitas_novas(pd.DataFrame(linhas))
                    if salvos > 0:
                        st.cache_data.clear()
                        _limpar_form()
                        log_atividade("lançou receita", f"{desc_form} · {formatar_moeda(valor_form)}")
                        mensagem_sucesso(f"{'Receita' if not recorrente else f'{salvos} receitas'} registrada(s)!")
                        st.rerun()
                    elif salvos == 0:
                        mensagem_erro("Já existe um registro com mesma data, descrição e valor.")
                    elif salvos == -1:
                        mensagem_erro("Erro de conexão. Tente novamente.")

    # ── Tabela interativa ─────────────────────────────────────
    st.markdown("---")

    # Filtros
    col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns([2, 2, 2, 2, 3])
    with col_f1:
        tipo_f = st.selectbox("Tipo:", ["Todos", "💸 Despesas", "💰 Receitas"], key="tf_tipo")
    with col_f2:
        mes_f = st.selectbox("Mês:", [0] + list(range(1, 13)),
                             format_func=lambda m: "Todos" if m == 0 else MESES_PT[m-1], key="tf_mes")
    with col_f3:
        ano_f = st.selectbox("Ano:", ["Todos"] + list(range(2023, date.today().year + 2)), key="tf_ano")
    with col_f4:
        status_f = st.selectbox("Status:", ["Todos", "Pago", "Recebida", "A Pagar", "A Receber", "Agendado", "Pendente"], key="tf_status")
    with col_f5:
        busca_f = st.text_input("🔍 Busca:", placeholder="Digite para filtrar...", key="tf_busca")

    # Carrega dados
    df_d_full = ler_csv(DESPESAS_FILE)
    df_r_full = ler_csv(RECEITAS_FILE)

    if not df_d_full.empty:
        df_d_full["_tabela"] = "despesas"
        df_d_full["_tipo"]   = "💸"
    if not df_r_full.empty:
        df_r_full["_tabela"] = "receitas"
        df_r_full["_tipo"]   = "💰"

    df_all = pd.concat([df_d_full, df_r_full], ignore_index=True)

    if not df_all.empty:
        df_all["data_dt"] = pd.to_datetime(df_all["data"], dayfirst=True, errors="coerce")
        df_all["valor"]   = pd.to_numeric(df_all["valor"], errors="coerce").fillna(0)

    def _filtrar(df):
        if df.empty: return df
        d = df.copy()
        if tipo_f == "💸 Despesas": d = d[d["_tabela"] == "despesas"]
        elif tipo_f == "💰 Receitas": d = d[d["_tabela"] == "receitas"]
        if mes_f > 0 and "data_dt" in d.columns:
            d = d[d["data_dt"].dt.month == mes_f]
        if ano_f != "Todos" and "data_dt" in d.columns:
            d = d[d["data_dt"].dt.year == int(ano_f)]
        if status_f != "Todos" and "status" in d.columns:
            d = d[d["status"] == status_f]
        if busca_f and "descricao" in d.columns:
            d = d[d["descricao"].astype(str).str.contains(busca_f, case=False, na=False)]
        return d

    df_view = _filtrar(df_all)
    if not df_view.empty and "data_dt" in df_view.columns:
        df_view = df_view.sort_values("data_dt", ascending=False)

    # Métricas
    total_d = df_view[df_view["_tabela"] == "despesas"]["valor"].sum() if not df_view.empty and "_tabela" in df_view.columns else 0
    total_r = df_view[df_view["_tabela"] == "receitas"]["valor"].sum() if not df_view.empty and "_tabela" in df_view.columns else 0
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("📊 Registros", len(df_view) if not df_view.empty else 0)
    col_m2.metric("💸 Despesas",  formatar_moeda(total_d))
    col_m3.metric("💰 Receitas",  formatar_moeda(total_r))
    col_m4.metric("💵 Saldo",     formatar_moeda(total_r - total_d))

    st.caption("✏️ Clique em qualquer célula para editar · Use o ícone 🗑️ (hover na linha) para deletar · Clique em **Salvar** para confirmar.")

    # Prepara df para o data_editor
    ALL_CATS    = sorted(set(listar_categorias("despesa") + listar_categorias("receita")))
    STATUS_OPTS = ["Pago", "Recebida", "A Pagar", "A Receber", "Agendado", "Pendente"]

    if not df_view.empty:
        cols_edit = ["_tipo", "data", "descricao", "categoria", "valor", "status", "fonte", "id", "_tabela"]
        df_edit = df_view.reindex(columns=cols_edit).copy()
        df_edit["data"]     = pd.to_datetime(df_edit["data"], errors="coerce").dt.date
        df_edit["id"]       = df_edit["id"].astype(str)
        df_edit["_deletar"] = False  # checkbox de exclusão

        orig_ids_set = set(df_edit["id"].tolist())

        edited_df = st.data_editor(
            df_edit,
            column_config={
                "_deletar":   st.column_config.CheckboxColumn("🗑️",       width="small"),
                "_tipo":      st.column_config.TextColumn("Tipo",          disabled=True, width="small"),
                "data":       st.column_config.DateColumn("Data",          format="DD/MM/YYYY", width="small"),
                "descricao":  st.column_config.TextColumn("Descrição",     width="large"),
                "categoria":  st.column_config.SelectboxColumn("Categoria", options=ALL_CATS, width="medium"),
                "valor":      st.column_config.NumberColumn("Valor",       format="R$ %.2f", min_value=0),
                "status":     st.column_config.SelectboxColumn("Status",   options=STATUS_OPTS, width="small"),
                "fonte":      st.column_config.TextColumn("Fonte",         disabled=True, width="small"),
                "id":         st.column_config.TextColumn("ID",            disabled=True, width="small"),
                "_tabela":    st.column_config.TextColumn("Tabela",        disabled=True, width="small"),
            },
            column_order=["_deletar", "_tipo", "data", "descricao", "categoria", "valor", "status", "fonte", "id", "_tabela"],
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            key="data_editor_main",
        )

        n_marcados = int(edited_df["_deletar"].sum()) if not edited_df.empty else 0
        col_salvar, col_deletar = st.columns([3, 1])

        with col_salvar:
            btn_salvar = st.button("💾 Salvar Alterações", type="primary", use_container_width=True, key="btn_salvar_edicoes")
        with col_deletar:
            btn_deletar = st.button(
                f"🗑️ Excluir {n_marcados} selecionado(s)" if n_marcados > 0 else "🗑️ Excluir",
                type="secondary", use_container_width=True, key="btn_excluir_sel",
                disabled=(n_marcados == 0),
            )

        if btn_deletar and n_marcados > 0:
            ids_del = set(edited_df[edited_df["_deletar"] == True]["id"].astype(str).tolist())
            df_d_s = ler_csv(DESPESAS_FILE)
            df_r_s = ler_csv(RECEITAS_FILE)
            df_d_s = df_d_s[~df_d_s["id"].astype(str).isin(ids_del)]
            df_r_s = df_r_s[~df_r_s["id"].astype(str).isin(ids_del)]
            salvar_parquet("despesas", df_d_s)
            salvar_parquet("receitas", df_r_s)
            st.cache_data.clear()
            log_atividade("deletou lançamentos", f"{len(ids_del)} via tabela")
            mensagem_sucesso(f"✅ {len(ids_del)} lançamento(s) excluído(s)!")
            st.rerun()

        if btn_salvar:
            df_d_save = ler_csv(DESPESAS_FILE)
            df_r_save = ler_csv(RECEITAS_FILE)

            if df_d_save.empty: df_d_save = pd.DataFrame(columns=list(COLUNAS_DESPESAS.keys()))
            if df_r_save.empty: df_r_save = pd.DataFrame(columns=list(COLUNAS_RECEITAS.keys()))

            for _, row in edited_df.iterrows():
                if row.get("_deletar"): continue  # ignorar marcados para exclusão no save
                row_id = str(row.get("id", ""))
                if not row_id or row_id not in orig_ids_set:
                    continue

                nova_data = row.get("data")
                if isinstance(nova_data, date):
                    nova_data = nova_data.strftime("%Y-%m-%d")
                elif nova_data is not None:
                    nova_data = str(nova_data)

                updates = {
                    "data":      nova_data,
                    "descricao": str(row.get("descricao", "")),
                    "categoria": str(row.get("categoria", "")),
                    "valor":     round(float(row.get("valor", 0) or 0), 2),
                    "status":    str(row.get("status", "")),
                }

                tabela_row = str(row.get("_tabela", ""))
                if tabela_row == "despesas":
                    mask = df_d_save["id"].astype(str) == row_id
                    if mask.any():
                        for k, v in updates.items():
                            df_d_save.loc[mask, k] = v
                elif tabela_row == "receitas":
                    mask = df_r_save["id"].astype(str) == row_id
                    if mask.any():
                        for k, v in updates.items():
                            df_r_save.loc[mask, k] = v

            salvar_parquet("despesas", df_d_save)
            salvar_parquet("receitas", df_r_save)
            st.cache_data.clear()

            msg = []
            if deleted_ids: msg.append(f"{len(deleted_ids)} deletado(s)")
            st.rerun() if not msg else None
            mensagem_sucesso("✅ " + (" · ".join(msg) if msg else "Alterações salvas!"))
            log_atividade("editou lançamentos", f"{len(deleted_ids)} deletados via tabela" if deleted_ids else "edições salvas")
            st.rerun()

    else:
        st.info("Nenhum lançamento encontrado com esses filtros.")


# ══════════════════════════════════════════════════════════════
# TAB 2 — CATEGORIAS & REGRAS
# ══════════════════════════════════════════════════════════════
with tab_cats:
    sub_cats, sub_regras, sub_recateg = st.tabs([
        "🏷️ Categorias",
        "📋 Regras",
        "⚡ Recategorizar",
    ])

    # ── Sub: Categorias ───────────────────────────────────────
    with sub_cats:
        st.markdown("### 🏷️ Gerenciar Categorias")

        df_d_cat = ler_csv(DESPESAS_FILE)
        df_r_cat = ler_csv(RECEITAS_FILE)

        col_c1, col_c2 = st.columns(2)

        for col_side, tipo_cat, df_cat, arquivo_cat, cor in [
            (col_c1, "despesa",  df_d_cat, "despesas", "#FF4D6D"),
            (col_c2, "receita",  df_r_cat, "receitas", "#4A9EFF"),
        ]:
            label = "💸 Despesas" if tipo_cat == "despesa" else "💰 Receitas"
            with col_side:
                st.markdown(f"#### {label}")
                cats = listar_categorias(tipo_cat)

                for cat in cats:
                    qtd = total = 0
                    df_lanc_cat = pd.DataFrame()
                    if not df_cat.empty and "categoria" in df_cat.columns:
                        mask        = df_cat["categoria"] == cat
                        qtd         = int(mask.sum())
                        total       = pd.to_numeric(df_cat.loc[mask, "valor"], errors="coerce").sum()
                        df_lanc_cat = df_cat[mask].copy()

                    key_d    = f"del_cat_{tipo_cat}_{cat}"
                    exp_label = f"{cat}  ·  {qtd} lançamentos  ·  {formatar_moeda(total)}"

                    with st.expander(exp_label, expanded=False):
                        # Lançamentos da categoria
                        if not df_lanc_cat.empty:
                            cols_show = ["data", "descricao", "valor", "status"]
                            df_show = df_lanc_cat[cols_show].copy()
                            df_show["data"]  = pd.to_datetime(df_show["data"], dayfirst=True, errors="coerce").dt.strftime("%d/%m/%Y")
                            df_show["valor"] = pd.to_numeric(df_show["valor"], errors="coerce").apply(formatar_moeda)
                            df_show = df_show.sort_values("data", ascending=False)
                            df_show.columns = ["Data", "Descrição", "Valor", "Status"]
                            st.dataframe(df_show, use_container_width=True, hide_index=True, height=min(200, 40 + qtd * 36))

                            # ── Recategorizar ──────────────────────────────
                            st.divider()
                            st.markdown("**🔀 Recategorizar itens desta categoria**")
                            descs_unicas = sorted(df_lanc_cat["descricao"].dropna().unique().tolist())
                            col_rc1, col_rc2 = st.columns(2)
                            with col_rc1:
                                descs_sel = st.multiselect(
                                    "Descrições a mover:",
                                    options=descs_unicas,
                                    placeholder="Selecione uma ou mais...",
                                    key=f"rc_descs_{tipo_cat}_{cat}",
                                )
                            with col_rc2:
                                outras_cats = [c for c in cats if c != cat] + ["📦 Outros"]
                                nova_cat_rc = st.selectbox(
                                    "Nova categoria:",
                                    options=outras_cats,
                                    key=f"rc_nova_{tipo_cat}_{cat}",
                                )
                            if descs_sel:
                                n_af = int(df_lanc_cat["descricao"].isin(descs_sel).sum())
                                st.caption(f"ℹ️ {n_af} lançamento(s) serão movidos para **{nova_cat_rc}**")
                                if st.button(f"✅ Mover para \"{nova_cat_rc}\"", key=f"rc_btn_{tipo_cat}_{cat}", type="primary", use_container_width=True):
                                    df_full = ler_csv(arquivo_cat)
                                    mask_rc = df_full["descricao"].isin(descs_sel) & (df_full["categoria"] == cat)
                                    df_full.loc[mask_rc, "categoria"] = nova_cat_rc
                                    salvar_parquet(arquivo_cat, df_full)
                                    st.cache_data.clear()
                                    mensagem_sucesso(f"✅ {int(mask_rc.sum())} lançamentos → \"{nova_cat_rc}\"")
                                    st.rerun()
                        else:
                            st.caption("Nenhum lançamento nesta categoria.")

                        st.divider()
                        # Ação de exclusão
                        if st.button(f"🗑️ Excluir categoria \"{cat}\"", key=key_d, use_container_width=True):
                            st.session_state[f"conf_{key_d}"] = True

                    if st.session_state.get(f"conf_{key_d}"):
                        if qtd > 0:
                            subs = st.selectbox(
                                f"Mover {qtd} lançamento(s) de \"{cat}\" para:",
                                [c for c in cats if c != cat] + ["📦 Outros"],
                                key=f"subs_{key_d}"
                            )
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("✅ Confirmar", key=f"ok_{key_d}", type="primary", use_container_width=True):
                                    df_full = ler_csv(arquivo_cat)
                                    df_full.loc[df_full["categoria"] == cat, "categoria"] = subs
                                    salvar_parquet(arquivo_cat, df_full)
                                    st.session_state.pop(f"conf_{key_d}", None)
                                    mensagem_sucesso(f"\"{cat}\" → \"{subs}\" ({qtd} lançamentos)")
                                    st.rerun()
                            with c2:
                                if st.button("❌ Cancelar", key=f"can_{key_d}", use_container_width=True):
                                    st.session_state.pop(f"conf_{key_d}", None)
                                    st.rerun()
                        else:
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("✅ Excluir", key=f"ok_{key_d}", type="primary", use_container_width=True):
                                    st.session_state.pop(f"conf_{key_d}", None)
                                    mensagem_sucesso(f"Categoria \"{cat}\" excluída.")
                                    st.rerun()
                            with c2:
                                if st.button("❌ Cancelar", key=f"can_{key_d}", use_container_width=True):
                                    st.session_state.pop(f"conf_{key_d}", None)
                                    st.rerun()

        st.info("💡 Categorias são criadas ao usar em lançamentos. Excluir reclassifica os lançamentos existentes.")

    # ── Sub: Regras ───────────────────────────────────────────
    with sub_regras:
        st.markdown("### 📋 Regras de Categorização Automática")
        st.info("Palavras-chave que identificam a categoria automaticamente. Ex: 'Netflix' → 🎬 Streaming")

        if st.button("🔄 Gerar regras do histórico", use_container_width=True):
            df_dh = ler_csv(DESPESAS_FILE); df_rh = ler_csv(RECEITAS_FILE)
            df_ra = ler_csv(MAPEAMENTOS_FILE)
            padroes_ok = set(df_ra["padrao"].astype(str).str.strip().tolist()) if not df_ra.empty and "padrao" in df_ra.columns else set()
            novas = []
            for df_h, tipo_r in [(df_dh, "despesa"), (df_rh, "receita")]:
                if df_h.empty or "descricao" not in df_h.columns: continue
                df_v = df_h[~df_h["categoria"].astype(str).str.contains("Outros", na=False) & df_h["descricao"].astype(str).str.strip().ne("")]
                if df_v.empty: continue
                cat_desc = df_v.groupby("descricao")["categoria"].agg(lambda x: x.value_counts().index[0]).to_dict()
                for desc, cat in cat_desc.items():
                    desc = str(desc).strip()
                    if desc and desc not in padroes_ok:
                        novas.append({"id": gerar_id(), "padrao": desc, "categoria": str(cat).strip(), "tipo": tipo_r, "criado_em": agora()})
                        padroes_ok.add(desc)
            if novas:
                df_final = pd.concat([df_ra, pd.DataFrame(novas)], ignore_index=True) if not df_ra.empty else pd.DataFrame(novas)
                salvar_parquet("mapeamentos", df_final)
                mensagem_sucesso(f"✅ {len(novas)} regras criadas!")
            else:
                st.info("Nenhuma regra nova — tudo já mapeado.")

        st.divider()
        df_reg = ler_csv(MAPEAMENTOS_FILE)

        if df_reg.empty:
            if st.button("🚀 Carregar Regras Padrão", type="primary", use_container_width=True):
                linhas = [{"id": gerar_id(), "padrao": p, "categoria": c, "tipo": t, "criado_em": agora()} for p, c, t in MAPEAMENTOS_PADRAO]
                salvar_parquet("mapeamentos", pd.DataFrame(linhas))
                mensagem_sucesso(f"{len(linhas)} regras padrão!")
                st.rerun()
            st.info("Nenhuma regra ainda.")
        else:
            st.success(f"✅ {len(df_reg)} regras ativas")
            st.dataframe(df_reg[["padrao","categoria","tipo"]].rename(columns={"padrao":"Palavra-chave","categoria":"Categoria","tipo":"Tipo"}), use_container_width=True, hide_index=True, height=260)

        st.divider()
        st.markdown("#### ➕ Nova Regra")
        col1, col2, col3 = st.columns(3)
        with col1: novo_pad = st.text_input("Palavra-chave:", placeholder="Netflix...", key="reg_pad")
        with col2:
            cats_ex = listar_categorias("despesa")
            cat_sel_r = st.selectbox("Categoria:", ["➕ Nova..."] + cats_ex, key="reg_cat_sel")
            nova_cat_reg = st.text_input("Nome:", key="reg_nova_cat") if cat_sel_r == "➕ Nova..." else cat_sel_r
        with col3:
            novo_tipo_reg = st.selectbox("Aplicar em:", ["ambos", "despesa", "receita"], key="reg_tipo")
        if st.button("✅ Adicionar Regra", type="primary", use_container_width=True, key="btn_add_reg"):
            if not novo_pad or not nova_cat_reg:
                mensagem_erro("Preencha palavra-chave e categoria!")
            else:
                df_reg2 = ler_csv(MAPEAMENTOS_FILE)
                nova = pd.DataFrame([{"id": gerar_id(), "padrao": novo_pad.strip(), "categoria": nova_cat_reg.strip(), "tipo": novo_tipo_reg, "criado_em": agora()}])
                salvar_parquet("mapeamentos", pd.concat([df_reg2, nova], ignore_index=True) if not df_reg2.empty else nova)
                mensagem_sucesso(f"Regra: '{novo_pad}' → '{nova_cat_reg}'")
                st.rerun()

        if not df_reg.empty:
            st.divider()
            st.markdown("#### 🗑️ Remover Regra")
            opts_reg = [f"{r['padrao']} → {r['categoria']}" for _, r in df_reg.iterrows()]
            idx_del  = st.selectbox("Selecione:", range(len(opts_reg)), format_func=lambda i: opts_reg[i], key="del_reg_sel")
            if st.button("🗑️ Remover", use_container_width=True, key="btn_del_reg"):
                salvar_parquet("mapeamentos", df_reg[df_reg["id"] != df_reg.iloc[idx_del]["id"]])
                mensagem_sucesso("Regra removida!")
                st.rerun()

    # ── Sub: Recategorizar ────────────────────────────────────
    with sub_recateg:
        st.markdown("### ⚡ Recategorizar em Massa")
        st.info("Aplica todas as regras cadastradas sobre os dados existentes.")

        df_reg3 = ler_csv(MAPEAMENTOS_FILE)
        if df_reg3.empty:
            st.warning("Cadastre regras na aba **Regras** primeiro.")
        else:
            col_p1, col_p2 = st.columns(2)
            with col_p1: ap_d = st.checkbox("Despesas", value=True, key="apd")
            with col_p2: ap_r = st.checkbox("Receitas",  value=True, key="apr")
            if st.button("⚡ Aplicar Regras Agora", type="primary", use_container_width=True, key="btn_aplicar"):
                total_alt = 0
                for flag, arquivo_at in [(ap_d, "despesas"), (ap_r, "receitas")]:
                    if not flag: continue
                    df_at = ler_csv(arquivo_at)
                    if df_at.empty: continue
                    antes = df_at["categoria"].copy()
                    df_at = aplicar_mapeamentos(df_at)
                    alt   = int((df_at["categoria"] != antes).sum())
                    salvar_parquet(arquivo_at, df_at)
                    total_alt += alt
                    st.caption(f"{'💸' if arquivo_at == 'despesas' else '💰'} {alt} recategorizados")
                mensagem_sucesso(f"✅ {total_alt} lançamentos recategorizados!")
                st.rerun()

        st.divider()
        st.markdown("### 🔀 Migrar Categoria")
        st.info("Move todos os lançamentos de uma categoria para outra.")
        tipo_mig = st.radio("Tipo:", ["💸 Despesas", "💰 Receitas"], horizontal=True, key="tipo_mig")
        df_mig   = ler_csv("despesas" if "💸" in tipo_mig else "receitas")
        tab_mig  = "despesas" if "💸" in tipo_mig else "receitas"

        if not df_mig.empty and "categoria" in df_mig.columns:
            cats_mig = sorted(df_mig["categoria"].dropna().unique().tolist())
            col_de, col_para = st.columns(2)
            with col_de:   cat_orig = st.selectbox("De:", cats_mig, key="cat_orig")
            with col_para: cat_dest = st.selectbox("Para:", [c for c in cats_mig if c != cat_orig], key="cat_dest")
            n_af = int((df_mig["categoria"] == cat_orig).sum())
            if n_af:
                st.caption(f"ℹ️ {n_af} lançamentos migrados")
            if st.button("🔀 Migrar", type="primary", use_container_width=True, key="btn_migrar"):
                df_mig.loc[df_mig["categoria"] == cat_orig, "categoria"] = cat_dest
                salvar_parquet(tab_mig, df_mig)
                mensagem_sucesso(f"✅ {n_af} lançamentos: \"{cat_orig}\" → \"{cat_dest}\"")
                st.rerun()

        st.divider()
        st.markdown("### 🔍 Sem Categoria Definida")
        df_sc = ler_csv(DESPESAS_FILE)
        if not df_sc.empty and "categoria" in df_sc.columns:
            sem_cat = df_sc[df_sc["categoria"].astype(str).str.contains("Outros|outros", na=False)]
            if not sem_cat.empty:
                st.warning(f"⚠️ {len(sem_cat)} despesas em 'Outros'")
                df_sc2 = sem_cat[["data","descricao","valor","categoria"]].head(20).copy()
                df_sc2["valor"] = pd.to_numeric(df_sc2["valor"], errors="coerce").apply(formatar_moeda)
                st.dataframe(df_sc2.rename(columns={"data":"Data","descricao":"Descrição","valor":"Valor","categoria":"Categoria"}), use_container_width=True, hide_index=True)
            else:
                st.success("✅ Nenhuma despesa sem categoria!")


# ══════════════════════════════════════════════════════════════
# TAB 3 — IMPORTAR
# ══════════════════════════════════════════════════════════════
with tab_import:
    sub_notion, sub_c6, sub_tmpl, sub_diag = st.tabs([
        "📓 Notion",
        "💳 C6 Bank",
        "📥 Template",
        "🔍 Diagnóstico",
    ])

    # ── Sub: Notion ───────────────────────────────────────────
    with sub_notion:
        st.markdown("### 📓 Notion — Banco de Dados")
        st.info(
            "Importa histórico completo do Notion.\n\n"
            "- **Pago + Valor Pago** → *Pago/Recebida*\n"
            "- **Não pago** → *A Pagar/A Receber* (aparece na Agenda)\n\n"
            "Re-importar **substitui apenas dados do Notion** — C6 e Manuais preservados."
        )

        df_n_atual = ler_csv(DESPESAS_FILE)
        df_n_rec   = ler_csv(RECEITAS_FILE)
        n_nd = int((df_n_atual["fonte"] == "Notion").sum()) if not df_n_atual.empty and "fonte" in df_n_atual.columns else 0
        n_nr = int((df_n_rec["fonte"]   == "Notion").sum()) if not df_n_rec.empty   and "fonte" in df_n_rec.columns   else 0
        if n_nd or n_nr:
            st.caption(f"📊 Atualmente {n_nd} despesas e {n_nr} receitas do Notion.")

        arq_notion = st.file_uploader("CSV exportado do Notion", type=["csv"], key="notion_up")
        if arq_notion:
            try:
                df_raw = pd.read_csv(StringIO(arq_notion.read().decode("utf-8-sig")))
                st.markdown("**Colunas:**"); st.code(", ".join(df_raw.columns.tolist()))
                st.dataframe(df_raw.head(3), use_container_width=True, hide_index=True)

                if "Vencimento" not in df_raw.columns or "Nome" not in df_raw.columns:
                    mensagem_erro("Colunas obrigatórias não encontradas: Vencimento, Nome")
                else:
                    df_raw["_nome"]       = df_raw["Nome"].apply(limpar_link_notion)
                    df_raw["_banco"]      = df_raw["Banco"].apply(limpar_link_notion) if "Banco" in df_raw.columns else "Outros"
                    df_raw["_prop"]       = df_raw["Propriedade"].apply(limpar_link_notion) if "Propriedade" in df_raw.columns else "📦 Outros"
                    df_raw["_vencimento"] = df_raw["Vencimento"].apply(to_iso)

                    def data_efetiva(row):
                        dpg = row.get("Data de PG", "")
                        iso = to_iso(dpg)
                        return iso if iso and len(iso) == 10 else row["_vencimento"]
                    df_raw["_data"] = df_raw.apply(data_efetiva, axis=1)

                    def detectar_pago(row):
                        campo = str(row.get("Pago", "")).lower().strip()
                        val   = limpar_valor(row.get("Valor Pago", "0"))
                        return campo in ["yes", "sim", "true", "✅", "1"] and val > 0
                    df_raw["_foi_pago"] = df_raw.apply(detectar_pago, axis=1)

                    def parse_valor_sinal(texto):
                        if pd.isna(texto): return 0.0
                        s = str(texto).strip()
                        neg = "-" in s
                        v = limpar_valor(s)
                        return -v if neg else v
                    if "Valor" in df_raw.columns:
                        df_raw["_valor_bruto"] = df_raw["Valor"].apply(parse_valor_sinal)
                    else:
                        df_raw["_valor_bruto"] = 0.0

                    df_raw["_val_rec"]  = df_raw["_valor_bruto"].apply(lambda x: x  if x > 0 else 0.0)
                    df_raw["_val_desp"] = df_raw["_valor_bruto"].apply(lambda x: abs(x) if x < 0 else 0.0)
                    mask_rec  = df_raw["_val_rec"] > 0
                    mask_desp = (df_raw["_val_desp"] > 0) & (~mask_rec)
                    df_desp_n = df_raw[mask_desp].copy()
                    df_rec_n  = df_raw[mask_rec].copy()

                    n_pd = int(df_desp_n["_foi_pago"].sum()) if not df_desp_n.empty else 0
                    n_pr = int(df_rec_n["_foi_pago"].sum())  if not df_rec_n.empty  else 0
                    st.markdown(f"📊 **{len(df_desp_n)} despesas** ({n_pd} pagas · {len(df_desp_n)-n_pd} a pagar) | **{len(df_rec_n)} receitas** ({n_pr} recebidas · {len(df_rec_n)-n_pr} a receber)")

                    bancos_csv = sorted(df_raw["_banco"].dropna().unique().tolist())
                    cartoes_cad = listar_cartoes_ativos()
                    bancos_exc = st.multiselect("🚫 Excluir bancos/cartões (virão da fatura):", options=bancos_csv, default=[b for b in bancos_csv if b in cartoes_cad])

                    DATA_CORTE_C6 = pd.Timestamp("2025-12-01")
                    CORTE_BANCO   = {"C6 BRU": DATA_CORTE_C6}
                    if bancos_exc:
                        df_desp_n["_data_ts"] = pd.to_datetime(df_desp_n["_data"], errors="coerce")
                        def deve_manter(row):
                            banco = row["_banco"]
                            if banco not in bancos_exc: return True
                            corte = CORTE_BANCO.get(banco)
                            return bool(corte and pd.notna(row["_data_ts"]) and row["_data_ts"] < corte)
                        n_antes = len(df_desp_n)
                        df_desp_n = df_desp_n[df_desp_n.apply(deve_manter, axis=1)].drop(columns=["_data_ts"])
                        exc = n_antes - len(df_desp_n)
                        if exc: st.caption(f"ℹ️ {exc} despesas excluídas (histórico C6 BRU preservado até nov/2025).")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**💸 {len(df_desp_n)} despesas**")
                        if not df_desp_n.empty:
                            pv = df_desp_n[["_data","_nome","_prop","_val_desp","_banco","_foi_pago"]].copy()
                            pv["_data"]     = pv["_data"].apply(to_br)
                            pv["_val_desp"] = pv["_val_desp"].apply(formatar_moeda)
                            pv["_foi_pago"] = pv["_foi_pago"].apply(lambda x: "✅" if x else "⏳")
                            pv.columns = ["Data","Descrição","Categoria","Valor","Banco","Status"]
                            st.dataframe(pv, use_container_width=True, hide_index=True, height=260)
                    with col2:
                        st.markdown(f"**💰 {len(df_rec_n)} receitas**")
                        if not df_rec_n.empty:
                            pv = df_rec_n[["_data","_nome","_val_rec","_banco","_foi_pago"]].copy()
                            pv["_data"]    = pv["_data"].apply(to_br)
                            pv["_val_rec"] = pv["_val_rec"].apply(formatar_moeda)
                            pv["_foi_pago"]= pv["_foi_pago"].apply(lambda x: "✅" if x else "⏳")
                            pv.columns = ["Data","Descrição","Valor","Banco","Status"]
                            st.dataframe(pv, use_container_width=True, hide_index=True, height=260)

                    st.divider()
                    if n_nd or n_nr:
                        st.warning(f"⚠️ Re-importar substituirá {n_nd} despesas e {n_nr} receitas do Notion.")

                    if st.button("✅ Confirmar Importação Notion", type="primary", use_container_width=True, key="btn_notion"):
                        remover_por_fonte("despesas", ["Notion"])
                        remover_por_fonte("receitas",  ["Notion"])
                        total_d = total_r = 0

                        if not df_desp_n.empty:
                            linhas = []
                            for _, r in df_desp_n.iterrows():
                                if not r["_data"] or not r["_nome"]: continue
                                linhas.append({
                                    "id": gerar_id(), "data": r["_data"],
                                    "descricao": r["_nome"], "categoria": limpar_categoria(r["_prop"]),
                                    "valor": round(float(r["_val_desp"]), 2),
                                    "forma_pagamento": r["_banco"] or "Outros", "banco": "",
                                    "status": "Pago" if r["_foi_pago"] else "A Pagar",
                                    "observacao": "", "fonte": "Notion", "criado_em": agora(),
                                })
                            if linhas:
                                df_nd = aplicar_mapeamentos(pd.DataFrame(linhas))
                                df_ex = ler_csv(DESPESAS_FILE)
                                salvar_parquet("despesas", pd.concat([df_ex, df_nd], ignore_index=True) if not df_ex.empty else df_nd)
                                total_d = len(linhas)

                        if not df_rec_n.empty:
                            linhas = []
                            for _, r in df_rec_n.iterrows():
                                if not r["_data"] or not r["_nome"]: continue
                                linhas.append({
                                    "id": gerar_id(), "data": r["_data"],
                                    "descricao": r["_nome"], "categoria": limpar_categoria(r["_prop"], "📦 Outros"),
                                    "valor": round(float(r["_val_rec"]), 2),
                                    "forma_recebimento": r["_banco"] or "📱 PIX",
                                    "status": "Recebida" if r["_foi_pago"] else "A Receber",
                                    "observacao": "", "fonte": "Notion", "criado_em": agora(),
                                })
                            if linhas:
                                df_nr = aplicar_mapeamentos(pd.DataFrame(linhas))
                                df_ex = ler_csv(RECEITAS_FILE)
                                salvar_parquet("receitas", pd.concat([df_ex, df_nr], ignore_index=True) if not df_ex.empty else df_nr)
                                total_r = len(linhas)

                        log_atividade("importou Notion", f"{total_d} despesas e {total_r} receitas")
                        mensagem_sucesso(f"Notion atualizado! {total_d} despesas e {total_r} receitas.")
                        st.balloons()

            except Exception as e:
                mensagem_erro(f"Erro: {e}"); st.exception(e)

    # ── Sub: C6 Bank ─────────────────────────────────────────
    with sub_c6:
        st.markdown("### 💳 C6 Bank — Fatura Mensal")

        MAPA_CAT_C6 = {
            "Especialidade varejo": "🛒 Compras Online", "Vestuário / Roupas": "👗 Vestuário",
            "Marketing Direto": "🛒 Compras Online", "Empresa para empresa": "📦 Outros",
            "Departamento / Desconto": "🛒 Compras Online", "Alimentação": "🍽️ Alimentação",
            "Restaurantes": "🍽️ Alimentação", "Saúde": "💊 Saúde", "Educação": "📚 Educação",
            "Transporte": "🚗 Transporte", "Entretenimento": "🎮 Lazer", "Viagens": "✈️ Viagens",
            "Farmácias": "💊 Saúde", "Supermercados": "🍽️ Alimentação", "Postos de Combustível": "🚗 Transporte",
        }
        MESES_NOME = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

        cartoes_df    = ler_csv(CARTOES_FILE)
        nomes_cartoes = cartoes_df["nome"].tolist() if not cartoes_df.empty and "nome" in cartoes_df.columns else []
        cartao_sel    = st.selectbox("Cartão desta fatura:", nomes_cartoes, key="c6_cartao") if nomes_cartoes else st.text_input("Nome do cartão:", value="C6 BRU", key="c6_cartao_txt")

        modo = st.radio("Modo:", ["📄 Fatura única (1 mês)", "📦 CSV unificado (múltiplos meses)"], horizontal=True, key="modo_c6")

        if modo == "📄 Fatura única (1 mês)":
            st.info("Envie um ou mais CSVs — cada um é uma fatura de um mês.")
            arquivos_c6 = st.file_uploader("CSVs de fatura C6 (sep por ;)", type=["csv"], key="c6_up", accept_multiple_files=True)

            if arquivos_c6:
                configs_fat = []
                for idx_a, arq in enumerate(arquivos_c6):
                    with st.expander(f"📄 `{arq.name}`", expanded=True):
                        col_m, col_a = st.columns(2)
                        with col_m: mes_a = st.selectbox("Mês:", range(1,13), index=datetime.now().month-1, format_func=lambda m: MESES_NOME[m-1], key=f"mes_fat_{idx_a}")
                        with col_a: ano_a = st.selectbox("Ano:", range(2024,2029), index=1, key=f"ano_fat_{idx_a}")
                    configs_fat.append((arq, mes_a, ano_a))

                df_hist_c6 = ler_csv(DESPESAS_FILE)
                cat_hist_c6 = {}
                if not df_hist_c6.empty and "descricao" in df_hist_c6.columns:
                    df_hist_c6["categoria"] = df_hist_c6["categoria"].astype(str)
                    cat_hist_c6 = df_hist_c6[~df_hist_c6["categoria"].str.contains("Outros", na=False)].groupby("descricao")["categoria"].agg(lambda x: x.value_counts().index[0]).to_dict()

                def _proc_csv(arq, mes_f, ano_f):
                    arq.seek(0)
                    df = pd.read_csv(StringIO(arq.read().decode("utf-8-sig")), sep=";")
                    req = ["Data de Compra","Descrição","Categoria","Valor (em R$)"]
                    falt = [c for c in req if c not in df.columns]
                    if falt: return None, None, f"Colunas faltando: {falt}"
                    ignorar = ["Inclusao","Inclusão","Estorno","Anuidade","Taxa","Juros"]
                    df = df[~df["Descrição"].str.contains("|".join(ignorar), case=False, na=False)].copy()
                    df["_val"] = pd.to_numeric(df["Valor (em R$)"], errors="coerce")
                    df["_data_orig"] = df["Data de Compra"].apply(to_br)
                    df["_desc"] = df["Descrição"].str.strip()
                    df["_cat"]  = df["Categoria"].apply(lambda x: MAPA_CAT_C6.get(str(x).strip(), "📦 Outros"))
                    desp  = df[df["_val"] > 0].copy()
                    devol = df[df["_val"] < 0].copy()
                    if not desp.empty:
                        desp["_valor"] = desp["_val"].abs()
                        desp["_cat"]   = desp.apply(lambda r: r["_cat"] if r["_cat"] != "📦 Outros" else cat_hist_c6.get(r["_desc"], "📦 Outros"), axis=1)
                    if not devol.empty:
                        devol["_valor"] = devol["_val"].abs()
                        devol["_desc"]  = devol["Descrição"].apply(lambda x: f"Reembolso - {str(x).strip()}")
                    return desp, devol, None

                resumo_geral = []
                faturas_dados = {}
                for arq, mes_f, ano_f in configs_fat:
                    desp, devol, erro = _proc_csv(arq, mes_f, ano_f)
                    if erro: st.error(f"`{arq.name}`: {erro}"); continue
                    faturas_dados[(mes_f, ano_f)] = (desp, devol, arq.name)
                    resumo_geral.append({
                        "Fatura": f"{MESES_NOME[mes_f-1]}/{ano_f}", "Arquivo": arq.name,
                        "Despesas": formatar_moeda(desp["_valor"].sum() if not desp.empty else 0),
                        "Reembolsos": formatar_moeda(devol["_valor"].sum() if not devol.empty else 0),
                        "Itens": len(desp) + len(devol),
                    })

                if resumo_geral:
                    prov_por_fat = {}
                    for (mes_f, ano_f) in faturas_dados:
                        if not df_hist_c6.empty and "fonte" in df_hist_c6.columns:
                            mask_p = (
                                (df_hist_c6["fonte"].astype(str) == "Manual") &
                                (~df_hist_c6.get("forma_pagamento", pd.Series(dtype=str)).astype(str).str.contains("PIX|Pix|pix", na=False)) &
                                (df_hist_c6.get("banco", pd.Series(dtype=str)).astype(str).str.strip().str.lower() == cartao_sel.strip().lower()) &
                                (pd.to_datetime(df_hist_c6["data"], dayfirst=True, errors="coerce").dt.month == mes_f) &
                                (pd.to_datetime(df_hist_c6["data"], dayfirst=True, errors="coerce").dt.year  == ano_f)
                            )
                            prov_por_fat[(mes_f, ano_f)] = df_hist_c6[mask_p]
                        else:
                            prov_por_fat[(mes_f, ano_f)] = pd.DataFrame()

                    for r in resumo_geral:
                        mn = MESES_NOME.index(r["Fatura"].split("/")[0]) + 1
                        an = int(r["Fatura"].split("/")[1])
                        n  = len(prov_por_fat.get((mn, an), pd.DataFrame()))
                        r["Provisórios"] = f"🗑️ {n}" if n > 0 else "—"

                    st.markdown("#### 📋 Resumo")
                    st.dataframe(pd.DataFrame(resumo_geral), use_container_width=True, hide_index=True)

                    total_prov = sum(len(v) for v in prov_por_fat.values())
                    if total_prov:
                        st.warning(f"🗑️ **{total_prov} lançamento(s) manual(is) provisório(s)** de **{cartao_sel}** serão substituídos.")

                    if st.button("✅ Confirmar e Importar", type="primary", use_container_width=True, key="btn_c6_multi"):
                        total_d = total_r = total_rem = 0
                        df_desp_full = ler_csv(DESPESAS_FILE)

                        for (mes_fat, ano_fat), (df_desp, df_devol, _) in faturas_dados.items():
                            data_fmt = f"{ano_fat:04d}-{mes_fat:02d}-01"
                            df_prov  = prov_por_fat.get((mes_fat, ano_fat), pd.DataFrame())
                            if not df_prov.empty and not df_desp_full.empty:
                                ids_rem = set(df_prov["id"].astype(str))
                                df_desp_full = df_desp_full[~df_desp_full["id"].astype(str).isin(ids_rem)]
                                total_rem += len(ids_rem)

                            if not df_desp.empty:
                                linhas = [{"id": gerar_id(), "data": data_fmt, "descricao": r["_desc"],
                                           "categoria": r["_cat"], "valor": round(float(r["_valor"]), 2),
                                           "forma_pagamento": "💳 Crédito", "banco": cartao_sel,
                                           "status": "Pago", "observacao": f"Compra em {r['_data_orig']}",
                                           "fonte": "C6 Bank", "criado_em": agora()}
                                          for _, r in df_desp.iterrows()]
                                df_nov = aplicar_mapeamentos(pd.DataFrame(linhas))
                                df_desp_full = pd.concat([df_desp_full, df_nov], ignore_index=True)
                                total_d += len(df_nov)

                            if not df_devol.empty:
                                linhas_r = [{"id": gerar_id(), "data": data_fmt, "descricao": r["_desc"],
                                             "categoria": "🔄 Reembolso", "valor": round(float(r["_valor"]), 2),
                                             "forma_recebimento": "💳 Crédito no Cartão", "status": "Pago",
                                             "observacao": f"Reembolso {r['_data_orig']}", "fonte": "C6 Bank", "criado_em": agora()}
                                            for _, r in df_devol.iterrows()]
                                total_r += salvar_receitas_novas(pd.DataFrame(linhas_r))

                        if not df_desp_full.empty:
                            salvar_parquet("despesas", df_desp_full)
                            st.cache_data.clear()

                        log_atividade("importou faturas C6", f"{len(faturas_dados)} meses · {total_d} despesas · {total_rem} provisórios removidos")
                        mensagem_sucesso(f"✅ {total_d} despesas · {total_rem} provisórios substituídos!")
                        st.balloons()

        else:  # CSV unificado
            st.info("CSV com faturas de vários meses juntos.")
            arq_multi = st.file_uploader("CSV unificado C6 (sep por ;)", type=["csv"], key="c6_multi_up")
            if arq_multi:
                try:
                    df_c6 = pd.read_csv(StringIO(arq_multi.read().decode("utf-8-sig")), sep=";")
                    req = ["Data de Compra","Descrição","Categoria","Valor (em R$)"]
                    falt = [c for c in req if c not in df_c6.columns]
                    if falt:
                        mensagem_erro(f"Colunas não encontradas: {falt}")
                    else:
                        ignorar = ["Inclusao","Inclusão","Estorno","Anuidade","Taxa","Juros"]
                        df_c6 = df_c6[~df_c6["Descrição"].str.contains("|".join(ignorar), case=False, na=False)].copy()
                        df_c6["_val"]      = pd.to_numeric(df_c6["Valor (em R$)"], errors="coerce")
                        df_c6["_data_ts"]  = pd.to_datetime(df_c6["Data de Compra"], dayfirst=True, errors="coerce")
                        df_c6["_data_orig"]= df_c6["Data de Compra"].apply(to_br)
                        df_c6["_desc"]     = df_c6["Descrição"].str.strip()
                        df_c6["_cat"]      = df_c6["Categoria"].apply(lambda x: MAPA_CAT_C6.get(str(x).strip(), "📦 Outros"))
                        df_c6["_ano"] = df_c6["_data_ts"].dt.year
                        df_c6["_mes"] = df_c6["_data_ts"].dt.month

                        meses_pres = [(int(a), int(m)) for a, m in df_c6[["_ano","_mes"]].dropna().drop_duplicates().sort_values(["_ano","_mes"]).values.tolist()]
                        st.markdown(f"**📅 {len(meses_pres)} faturas:** " + ", ".join(f"{MESES_NOME[m-1]}/{a}" for a, m in meses_pres))

                        resumo = [{"Mês": f"{MESES_NOME[m-1]}/{a}", "Despesas": formatar_moeda(df_c6[(df_c6["_ano"]==a)&(df_c6["_mes"]==m)&(df_c6["_val"]>0)]["_val"].sum()), "Reembolsos": formatar_moeda(df_c6[(df_c6["_ano"]==a)&(df_c6["_mes"]==m)&(df_c6["_val"]<0)]["_val"].abs().sum()), "Itens": len(df_c6[(df_c6["_ano"]==a)&(df_c6["_mes"]==m)])} for a, m in meses_pres]
                        st.dataframe(pd.DataFrame(resumo), use_container_width=True, hide_index=True)

                        if st.button("✅ Confirmar Importação", type="primary", use_container_width=True, key="btn_c6_unif"):
                            total_d = total_r = total_rem2 = 0
                            for ano_f, mes_f in meses_pres:
                                data_fmt = f"{ano_f:04d}-{mes_f:02d}-01"
                                sub = df_c6[(df_c6["_ano"] == ano_f) & (df_c6["_mes"] == mes_f)]
                                n_rem = remover_por_fonte("despesas", fontes=["Notion","Manual"], mes=mes_f, ano=ano_f, cartao=cartao_sel)
                                total_rem2 += n_rem
                                df_dd = sub[sub["_val"] > 0].copy()
                                df_dv = sub[sub["_val"] < 0].copy()
                                if not df_dd.empty:
                                    linhas = [{"id": gerar_id(), "data": data_fmt, "descricao": r["_desc"], "categoria": r["_cat"],
                                               "valor": round(float(r["_val"]), 2), "forma_pagamento": "💳 Crédito",
                                               "banco": cartao_sel, "status": "Pago", "observacao": f"Compra em {r['_data_orig']}", "fonte": "C6 Bank", "criado_em": agora()} for _, r in df_dd.iterrows()]
                                    total_d += salvar_despesas_novas(aplicar_mapeamentos(pd.DataFrame(linhas)))
                                if not df_dv.empty:
                                    linhas = [{"id": gerar_id(), "data": data_fmt, "descricao": f"Reembolso - {r['_desc']}", "categoria": "🔄 Reembolso",
                                               "valor": round(abs(float(r["_val"])), 2), "forma_recebimento": "💳 Crédito no Cartão",
                                               "status": "Pago", "observacao": f"Reembolso {r['_data_orig']}", "fonte": "C6 Bank", "criado_em": agora()} for _, r in df_dv.iterrows()]
                                    total_r += salvar_receitas_novas(pd.DataFrame(linhas))
                            log_atividade("importou C6 unificado", f"{total_d} despesas em {len(meses_pres)} meses")
                            mensagem_sucesso(f"✅ {total_d} despesas e {total_r} reembolsos em {len(meses_pres)} meses!")
                            st.balloons()
                except Exception as e:
                    mensagem_erro(f"Erro: {e}"); st.exception(e)

    # ── Sub: Template ─────────────────────────────────────────
    with sub_tmpl:
        st.markdown("### 📥 Template Manual")
        st.info("Importação em massa via CSV. Para lançamentos individuais use a aba **Lançamentos**.")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Despesas**")
            ex_d = pd.DataFrame([{"data":"2025-05-15","descricao":"Supermercado","categoria":"🍽️ Alimentação","valor":250.00,"forma_pagamento":"💳 Débito","banco":"","status":"Pago","observacao":""}])
            st.download_button("⬇️ Baixar template", data=ex_d.to_csv(index=False).encode("utf-8-sig"), file_name="template_despesas.csv", mime="text/csv", use_container_width=True)
        with col2:
            st.markdown("**Receitas**")
            ex_r = pd.DataFrame([{"data":"2025-05-01","descricao":"Salário","categoria":"💼 Salário","valor":5000.00,"forma_recebimento":"🏦 Transferência","status":"Pago","observacao":""}])
            st.download_button("⬇️ Baixar template", data=ex_r.to_csv(index=False).encode("utf-8-sig"), file_name="template_receitas.csv", mime="text/csv", use_container_width=True)

        st.caption("Data: yyyy-mm-dd (ex: 2025-05-15)")
        st.divider()
        tipo_tmpl = st.radio("Tipo:", ["Despesas", "Receitas"], horizontal=True, key="tipo_tmpl")
        arq_tmpl  = st.file_uploader("CSV preenchido", type=["csv"], key="tmpl_up")
        if arq_tmpl:
            try:
                df_t = pd.read_csv(StringIO(arq_tmpl.read().decode("utf-8-sig")))
                st.dataframe(df_t.head(10), use_container_width=True, hide_index=True)
                if st.button("✅ Importar", type="primary", use_container_width=True, key="btn_tmpl"):
                    df_t["id"]        = [gerar_id() for _ in range(len(df_t))]
                    df_t["criado_em"] = agora()
                    df_t["fonte"]     = "Manual"
                    df_t["valor"]     = pd.to_numeric(df_t["valor"], errors="coerce").fillna(0)
                    df_t["data"]      = df_t["data"].apply(to_iso)
                    fn = salvar_despesas_novas if tipo_tmpl == "Despesas" else salvar_receitas_novas
                    salvos = fn(df_t)
                    mensagem_sucesso(f"✅ {salvos} {tipo_tmpl.lower()} importadas!")
            except Exception as e:
                mensagem_erro(f"Erro: {e}")

    # ── Sub: Diagnóstico ──────────────────────────────────────
    with sub_diag:
        st.markdown("### 🔍 Diagnóstico")
        df_diag_d = ler_csv(DESPESAS_FILE)
        df_diag_r = ler_csv(RECEITAS_FILE)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 💸 Despesas por fonte")
            if df_diag_d.empty:
                st.warning("Sem despesas.")
            else:
                st.success(f"✅ {len(df_diag_d)} registros")
                if "fonte" in df_diag_d.columns:
                    st.dataframe(df_diag_d.groupby("fonte").size().reset_index(name="Qtd"), use_container_width=True, hide_index=True)
        with col2:
            st.markdown("#### 💰 Receitas por fonte")
            if df_diag_r.empty:
                st.warning("Sem receitas.")
            else:
                st.success(f"✅ {len(df_diag_r)} registros")
                if "fonte" in df_diag_r.columns:
                    st.dataframe(df_diag_r.groupby("fonte").size().reset_index(name="Qtd"), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("#### 🗑️ Limpar por fonte")
        st.error("⚠️ Irreversível!")
        for fonte_nome in ["Notion", "C6 Bank", "Manual"]:
            key_btn  = f"btn_diag_{fonte_nome}"
            key_conf = f"conf_diag_{fonte_nome}"
            if st.button(f"🗑️ Limpar {fonte_nome}", use_container_width=True, key=key_btn):
                st.session_state[key_conf] = True
            if st.session_state.get(key_conf):
                st.warning(f"Confirma exclusão de todos os dados de fonte **{fonte_nome}**?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Sim, limpar", type="primary", key=f"ok_{key_conf}", use_container_width=True):
                        n_d = remover_por_fonte("despesas", [fonte_nome])
                        n_r = remover_por_fonte("receitas",  [fonte_nome])
                        st.session_state[key_conf] = False
                        st.cache_data.clear()
                        mensagem_sucesso(f"✅ {n_d} despesas e {n_r} receitas de {fonte_nome} removidas!")
                        st.rerun()
                with c2:
                    if st.button("❌ Cancelar", key=f"can_{key_conf}", use_container_width=True):
                        st.session_state[key_conf] = False
                        st.rerun()
