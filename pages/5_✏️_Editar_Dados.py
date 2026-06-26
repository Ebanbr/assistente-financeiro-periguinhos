# ============================================================
#  5_✏️_Editar_Dados.py — Editar, Deletar e Categorias
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st

from auth import exigir_login
exigir_login()
import pandas as pd
from datetime import date

from config import (
    DESPESAS_FILE, RECEITAS_FILE, MAPEAMENTOS_FILE, CARTOES_FILE,
    MESES_PT, MAPEAMENTOS_PADRAO, COLUNAS_MAPEAMENTOS,
)
from utils import (
    configurar_pagina, cabecalho_pagina, inicializar_dados,
    ler_csv, salvar_parquet, mensagem_sucesso, mensagem_erro,
    formatar_moeda, editar_linha, deletar_linha,
    listar_categorias, aplicar_mapeamentos, gerar_id, agora,
)

configurar_pagina("Editar", icone="✏️")
inicializar_dados()
cabecalho_pagina(titulo="Editar Dados", subtitulo="Modifique, delete lançamentos e gerencie categorias", icone="✏️")
st.markdown("---")

aba_editar, aba_cats, aba_regras, aba_recategorizar, aba_cartoes, aba_bancos, aba_formas = st.tabs([
    "✏️ Editar Lançamentos",
    "🏷️ Categorias",
    "📋 Regras de Categorização",
    "⚡ Recategorizar em Massa",
    "💳 Cartões",
    "🏦 Bancos",
    "💸 Formas de Pagamento",
])

# ════════════════════════════════════════════════════════════
# ABA 1 — EDITAR LANÇAMENTOS
# ════════════════════════════════════════════════════════════
with aba_editar:
    tipo = st.radio("O que deseja editar?", ["💸 Despesas", "💰 Receitas"], horizontal=True)

    if "💸" in tipo:
        df = ler_csv(DESPESAS_FILE)
        tabela   = "despesas"
        tipo_cat = "despesa"
    else:
        df = ler_csv(RECEITAS_FILE)
        tabela   = "receitas"
        tipo_cat = "receita"

    if df.empty:
        st.info(f"Nenhum registro em {tipo}")
        st.stop()

    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
    if "data_dt" not in df.columns:
        df["data_dt"] = pd.to_datetime(df["data"], errors="coerce")

    # ── Filtros ───────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        mes_f = st.selectbox("Mês:", [0]+list(range(1,13)), index=0,
                             format_func=lambda m: "Todos" if m==0 else MESES_PT[m-1])
    with col_f2:
        anos = sorted(df["data_dt"].dt.year.dropna().astype(int).unique().tolist(), reverse=True)
        ano_f = st.selectbox("Ano:", ["Todos"]+anos)
    with col_f3:
        busca = st.text_input("🔍 Buscar descrição:", placeholder="Digite para filtrar...")

    col_f4, col_f5 = st.columns(2)
    with col_f4:
        cats_disponiveis = ["Todas"] + sorted(df["categoria"].dropna().unique().tolist()) if "categoria" in df.columns else ["Todas"]
        cat_filtro = st.selectbox("🏷️ Categoria:", cats_disponiveis, index=0)
    with col_f5:
        status_opts_filt = ["Todos"] + sorted(df["status"].dropna().unique().tolist()) if "status" in df.columns else ["Todos"]
        status_filtro = st.selectbox("📌 Status:", status_opts_filt, index=0)

    df_filt = df.copy()
    if mes_f > 0:                    df_filt = df_filt[df_filt["data_dt"].dt.month == mes_f]
    if ano_f != "Todos":             df_filt = df_filt[df_filt["data_dt"].dt.year == int(ano_f)]
    if busca:                        df_filt = df_filt[df_filt["descricao"].astype(str).str.contains(busca, case=False, na=False)]
    if cat_filtro != "Todas":        df_filt = df_filt[df_filt["categoria"].astype(str) == cat_filtro]
    if status_filtro != "Todos":     df_filt = df_filt[df_filt["status"].astype(str) == status_filtro]

    if cat_filtro == "📦 Outros":
        st.warning(f"⚠️ {len(df_filt)} lançamentos sem categoria específica.")

    if df_filt.empty:
        st.info("Nenhum registro com esses filtros")
        st.stop()

    df_filt = df_filt.sort_values("data_dt", ascending=False)

    # ── Selecionar lançamento ─────────────────────────────────
    st.markdown("### Selecione o lançamento:")
    def _fmt_data(v):
        try:
            return pd.to_datetime(v, dayfirst=True, errors="coerce").strftime("%d/%m/%Y")
        except Exception:
            return str(v)

    opcoes = [
        f"{_fmt_data(row['data'])} | {row['descricao'][:40]} | {formatar_moeda(row['valor'])}"
        for _, row in df_filt.iterrows()
    ]
    selecionado_idx = st.selectbox("Lançamento:", range(len(opcoes)), format_func=lambda i: opcoes[i])
    linha = df_filt.iloc[selecionado_idx]

    st.divider()
    st.markdown("### ✏️ Editar")

    col1, col2 = st.columns(2)

    with col1:
        nova_desc  = st.text_input("Descrição:", value=str(linha["descricao"]))
        novo_valor = st.number_input("Valor (R$):", value=float(linha["valor"]), min_value=0.0, step=0.01)
        novo_data  = st.date_input("Data:", value=pd.to_datetime(linha["data"], dayfirst=True, errors="coerce").date(), format="DD/MM/YYYY")

    with col2:
        cats = listar_categorias(tipo_cat)
        cat_atual = str(linha.get("categoria", ""))
        opcoes_cat = ["➕ Nova categoria..."] + cats
        idx_cat = cats.index(cat_atual)+1 if cat_atual in cats else 0
        cat_sel = st.selectbox("Categoria:", opcoes_cat, index=idx_cat)
        if cat_sel == "➕ Nova categoria...":
            nova_cat = st.text_input("Nome da nova categoria:", placeholder="Ex: 🎮 Games")
        else:
            nova_cat = cat_sel

        status_opts = ["Pago", "Pendente", "Recebida", "Agendado", "A Pagar", "A Receber"]
        status_atual = str(linha.get("status", "Pago"))
        idx_status = status_opts.index(status_atual) if status_atual in status_opts else 0
        novo_status = st.selectbox("Status:", status_opts, index=idx_status)

    novo_obs = st.text_area("Observação:", value=str(linha.get("observacao", "")), height=80)

    # ── Ações ─────────────────────────────────────────────────
    col_save, col_del = st.columns(2)

    with col_save:
        if st.button("💾 Salvar Mudanças", type="primary", use_container_width=True):
            if not nova_cat or not nova_cat.strip():
                mensagem_erro("Preencha a categoria!")
            else:
                dados_novos = {
                    "descricao":  nova_desc,
                    "valor":      round(novo_valor, 2),
                    "data":       novo_data.strftime("%Y-%m-%d"),
                    "categoria":  nova_cat.strip(),
                    "status":     novo_status,
                    "observacao": novo_obs,
                }
                if editar_linha(tabela, linha["id"], dados_novos):
                    # ── Cria regra de mapeamento automática se categoria mudou ──
                    cat_anterior = str(linha.get("categoria", "")).strip()
                    if nova_cat.strip() != cat_anterior:
                        df_reg = ler_csv(MAPEAMENTOS_FILE)
                        desc_strip = str(linha["descricao"]).strip()
                        # Só cria se não existir regra igual
                        ja_existe = False
                        if not df_reg.empty and "padrao" in df_reg.columns:
                            ja_existe = df_reg["padrao"].astype(str).str.strip().eq(desc_strip).any()
                        if not ja_existe:
                            tipo_reg = "despesa" if tabela == "despesas" else "receita"
                            nova_regra = pd.DataFrame([{
                                "id": gerar_id(), "padrao": desc_strip,
                                "categoria": nova_cat.strip(), "tipo": tipo_reg,
                                "criado_em": agora()
                            }])
                            df_final_reg = pd.concat([df_reg, nova_regra], ignore_index=True) if not df_reg.empty else nova_regra
                            salvar_parquet("mapeamentos", df_final_reg)
                            st.toast(f"✅ Regra criada: '{desc_strip}' → '{nova_cat.strip()}'", icon="🏷️")

                    iguais = df[
                        (df["descricao"].astype(str).str.strip() == str(linha["descricao"]).strip()) &
                        (df["id"] != linha["id"])
                    ]
                    if not iguais.empty:
                        st.session_state["_aplicar_todos_desc"]   = str(linha["descricao"]).strip()
                        st.session_state["_aplicar_todos_cat"]    = nova_cat.strip()
                        st.session_state["_aplicar_todos_n"]      = len(iguais)
                        st.session_state["_aplicar_todos_tabela"] = tabela
                    else:
                        mensagem_sucesso("Alterações salvas!")
                        st.rerun()
                else:
                    mensagem_erro("Não foi possível salvar.")

    with col_del:
        if st.button("🗑️ Deletar Lançamento", type="secondary", use_container_width=True):
            st.session_state["confirmar_delete"] = True

    # ── Aplicar para todos com mesma descrição ────────────────
    if st.session_state.get("_aplicar_todos_desc"):
        desc_alvo = st.session_state["_aplicar_todos_desc"]
        cat_alvo  = st.session_state["_aplicar_todos_cat"]
        n_alvo    = st.session_state["_aplicar_todos_n"]
        tab_alvo  = st.session_state["_aplicar_todos_tabela"]

        st.divider()
        st.info(
            f"✅ Salvo! Encontrei **{n_alvo} outro(s) lançamento(s)** com a descrição "
            f"**\"{desc_alvo}\"**.\n\nDeseja classificar todos como **\"{cat_alvo}\"**?"
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button(f"✅ Sim, aplicar para todos os {n_alvo+1}", type="primary", use_container_width=True):
                arquivo  = DESPESAS_FILE if tab_alvo == "despesas" else RECEITAS_FILE
                df_full  = ler_csv(arquivo)
                mask     = df_full["descricao"].astype(str).str.strip() == desc_alvo
                df_full.loc[mask, "categoria"] = cat_alvo
                salvar_parquet(tab_alvo, df_full)
                for k in ["_aplicar_todos_desc","_aplicar_todos_cat","_aplicar_todos_n","_aplicar_todos_tabela"]:
                    st.session_state.pop(k, None)
                mensagem_sucesso(f"✅ {mask.sum()} lançamentos → \"{cat_alvo}\"")
                st.rerun()
        with c2:
            if st.button("❌ Não, só este", use_container_width=True):
                for k in ["_aplicar_todos_desc","_aplicar_todos_cat","_aplicar_todos_n","_aplicar_todos_tabela"]:
                    st.session_state.pop(k, None)
                mensagem_sucesso("Alteração salva só neste lançamento.")
                st.rerun()

    if st.session_state.get("confirmar_delete"):
        st.warning(f"⚠️ Confirma exclusão de **{linha['descricao']}** ({formatar_moeda(linha['valor'])})?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Sim, deletar", type="primary", use_container_width=True):
                if deletar_linha(tabela, linha["id"]):
                    st.session_state["confirmar_delete"] = False
                    mensagem_sucesso("Lançamento deletado!")
                    st.rerun()
        with c2:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state["confirmar_delete"] = False
                st.rerun()


# ════════════════════════════════════════════════════════════
# ABA 2 — CATEGORIAS
# ════════════════════════════════════════════════════════════
with aba_cats:
    st.markdown("### 🏷️ Gerenciar Categorias")

    col_c1, col_c2 = st.columns(2)
    df_d_cat = ler_csv(DESPESAS_FILE)
    df_r_cat = ler_csv(RECEITAS_FILE)

    # ── Despesas ──────────────────────────────────────────────
    with col_c1:
        st.markdown("#### 💸 Categorias de Despesa")
        cats_d = listar_categorias("despesa")

        for cat in cats_d:
            qtd = total = 0
            if not df_d_cat.empty and "categoria" in df_d_cat.columns:
                mask  = df_d_cat["categoria"] == cat
                qtd   = int(mask.sum())
                total = pd.to_numeric(df_d_cat.loc[mask, "valor"], errors="coerce").sum()

            col_nome, col_excluir = st.columns([4, 1])
            with col_nome:
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;padding:6px 10px;"
                    f"background:#161B22;border-radius:6px;margin:3px 0;border-left:3px solid #FF4D6D'>"
                    f"<span style='color:#E6EDF3'>{cat}</span>"
                    f"<span style='color:#556878;font-size:0.8rem'>{qtd} lanç · {formatar_moeda(total)}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with col_excluir:
                if st.button("🗑️", key=f"del_cat_d_{cat}", help=f"Excluir categoria {cat}"):
                    st.session_state[f"confirm_del_cat_d_{cat}"] = True

            if st.session_state.get(f"confirm_del_cat_d_{cat}"):
                if qtd > 0:
                    nova_cat_subs = st.selectbox(
                        f"Reclassificar os {qtd} lançamentos de \"{cat}\" para:",
                        [c for c in cats_d if c != cat] + ["📦 Outros"],
                        key=f"subs_cat_d_{cat}"
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Confirmar", key=f"ok_del_d_{cat}", type="primary", use_container_width=True):
                            df_full = ler_csv(DESPESAS_FILE)
                            df_full.loc[df_full["categoria"] == cat, "categoria"] = nova_cat_subs
                            salvar_parquet("despesas", df_full)
                            st.session_state.pop(f"confirm_del_cat_d_{cat}", None)
                            mensagem_sucesso(f"Categoria \"{cat}\" removida. {qtd} lançamentos → \"{nova_cat_subs}\"")
                            st.rerun()
                    with c2:
                        if st.button("❌ Cancelar", key=f"cancel_del_d_{cat}", use_container_width=True):
                            st.session_state.pop(f"confirm_del_cat_d_{cat}", None)
                            st.rerun()
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Excluir", key=f"ok_del_d_{cat}", type="primary", use_container_width=True):
                            st.session_state.pop(f"confirm_del_cat_d_{cat}", None)
                            mensagem_sucesso(f"Categoria \"{cat}\" removida (sem lançamentos).")
                            st.rerun()
                    with c2:
                        if st.button("❌ Cancelar", key=f"cancel_del_d_{cat}", use_container_width=True):
                            st.session_state.pop(f"confirm_del_cat_d_{cat}", None)
                            st.rerun()

        st.divider()
        st.markdown("**➕ Nova categoria de despesa**")
        nova_cat_d = st.text_input("Nome:", placeholder="Ex: 🎾 Esporte", key="nova_cat_d_input")
        if st.button("✅ Adicionar", key="btn_add_cat_d", use_container_width=True):
            if nova_cat_d.strip():
                # Salva um lançamento fictício com a categoria para ela aparecer na lista
                # Não — apenas orienta o usuário a usar ao criar um lançamento.
                # A categoria será criada ao primeiro uso. Aqui só confirmamos.
                mensagem_sucesso(f"Categoria \"{nova_cat_d.strip()}\" disponível! Use-a ao criar um lançamento.")
            else:
                mensagem_erro("Digite um nome para a categoria.")

    # ── Receitas ──────────────────────────────────────────────
    with col_c2:
        st.markdown("#### 💰 Categorias de Receita")
        cats_r = listar_categorias("receita")

        for cat in cats_r:
            qtd = total = 0
            if not df_r_cat.empty and "categoria" in df_r_cat.columns:
                mask  = df_r_cat["categoria"] == cat
                qtd   = int(mask.sum())
                total = pd.to_numeric(df_r_cat.loc[mask, "valor"], errors="coerce").sum()

            col_nome, col_excluir = st.columns([4, 1])
            with col_nome:
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;padding:6px 10px;"
                    f"background:#161B22;border-radius:6px;margin:3px 0;border-left:3px solid #4A9EFF'>"
                    f"<span style='color:#E6EDF3'>{cat}</span>"
                    f"<span style='color:#556878;font-size:0.8rem'>{qtd} lanç · {formatar_moeda(total)}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with col_excluir:
                if st.button("🗑️", key=f"del_cat_r_{cat}", help=f"Excluir categoria {cat}"):
                    st.session_state[f"confirm_del_cat_r_{cat}"] = True

            if st.session_state.get(f"confirm_del_cat_r_{cat}"):
                if qtd > 0:
                    nova_cat_subs = st.selectbox(
                        f"Reclassificar os {qtd} lançamentos de \"{cat}\" para:",
                        [c for c in cats_r if c != cat] + ["📦 Outros"],
                        key=f"subs_cat_r_{cat}"
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Confirmar", key=f"ok_del_r_{cat}", type="primary", use_container_width=True):
                            df_full = ler_csv(RECEITAS_FILE)
                            df_full.loc[df_full["categoria"] == cat, "categoria"] = nova_cat_subs
                            salvar_parquet("receitas", df_full)
                            st.session_state.pop(f"confirm_del_cat_r_{cat}", None)
                            mensagem_sucesso(f"Categoria \"{cat}\" removida. {qtd} lançamentos → \"{nova_cat_subs}\"")
                            st.rerun()
                    with c2:
                        if st.button("❌ Cancelar", key=f"cancel_del_r_{cat}", use_container_width=True):
                            st.session_state.pop(f"confirm_del_cat_r_{cat}", None)
                            st.rerun()
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Excluir", key=f"ok_del_r_{cat}", type="primary", use_container_width=True):
                            st.session_state.pop(f"confirm_del_cat_r_{cat}", None)
                            mensagem_sucesso(f"Categoria \"{cat}\" removida (sem lançamentos).")
                            st.rerun()
                    with c2:
                        if st.button("❌ Cancelar", key=f"cancel_del_r_{cat}", use_container_width=True):
                            st.session_state.pop(f"confirm_del_cat_r_{cat}", None)
                            st.rerun()

        st.divider()
        st.markdown("**➕ Nova categoria de receita**")
        nova_cat_r = st.text_input("Nome:", placeholder="Ex: 💡 Consultoria", key="nova_cat_r_input")
        if st.button("✅ Adicionar", key="btn_add_cat_r", use_container_width=True):
            if nova_cat_r.strip():
                mensagem_sucesso(f"Categoria \"{nova_cat_r.strip()}\" disponível! Use-a ao criar um lançamento.")
            else:
                mensagem_erro("Digite um nome para a categoria.")

    st.info(
        "💡 **Como funciona:** as categorias são criadas automaticamente ao serem usadas em lançamentos. "
        "Excluir uma categoria reclassifica os lançamentos existentes para outra de sua escolha."
    )


# ════════════════════════════════════════════════════════════
# ABA 3 — REGRAS DE CATEGORIZAÇÃO
# ════════════════════════════════════════════════════════════
with aba_regras:
    st.markdown("### 📋 Regras de Categorização Automática")
    st.info(
        "Defina palavras-chave que identificam automaticamente a categoria de um lançamento.\n\n"
        "Ex: qualquer despesa com **'Netflix'** na descrição → **🎬 Streaming**"
    )

    # ── Gerar regras a partir do histórico ───────────────────────
    if st.button("🔄 Gerar regras a partir do histórico", use_container_width=True, help="Varre todos os lançamentos existentes e cria regras para os que já foram categorizados manualmente."):
        with st.spinner("Analisando histórico de lançamentos..."):
            df_d_hist = ler_csv(DESPESAS_FILE)
            df_r_hist = ler_csv(RECEITAS_FILE)
            df_reg_at = ler_csv(MAPEAMENTOS_FILE)

            # Regras já existentes
            padroes_existentes = set()
            if not df_reg_at.empty and "padrao" in df_reg_at.columns:
                padroes_existentes = set(df_reg_at["padrao"].astype(str).str.strip().tolist())

            novas = []

            for df_hist, tipo_r in [(df_d_hist, "despesa"), (df_r_hist, "receita")]:
                if df_hist.empty or "descricao" not in df_hist.columns or "categoria" not in df_hist.columns:
                    continue
                # Pega a categoria mais frequente por descrição, ignorando "Outros"
                df_validos = df_hist[
                    ~df_hist["categoria"].astype(str).str.contains("Outros|outros", na=False) &
                    df_hist["descricao"].astype(str).str.strip().ne("")
                ]
                if df_validos.empty:
                    continue
                cat_por_desc = (
                    df_validos.groupby("descricao")["categoria"]
                    .agg(lambda x: x.value_counts().index[0])
                    .to_dict()
                )
                for desc, cat in cat_por_desc.items():
                    desc = str(desc).strip()
                    if desc and desc not in padroes_existentes:
                        novas.append({
                            "id": gerar_id(), "padrao": desc,
                            "categoria": str(cat).strip(),
                            "tipo": tipo_r, "criado_em": agora()
                        })
                        padroes_existentes.add(desc)

            if novas:
                df_novas = pd.DataFrame(novas)
                df_reg_at = ler_csv(MAPEAMENTOS_FILE)
                df_final  = pd.concat([df_reg_at, df_novas], ignore_index=True) if not df_reg_at.empty else df_novas
                salvar_parquet("mapeamentos", df_final)
                mensagem_sucesso(f"✅ {len(novas)} regras criadas a partir do histórico!")
            else:
                st.info("Nenhuma regra nova encontrada — tudo já está mapeado.")

    st.divider()

    df_reg = ler_csv(MAPEAMENTOS_FILE)

    if df_reg.empty:
        if st.button("🚀 Carregar Regras Padrão", type="primary", use_container_width=True):
            linhas = []
            for padrao, categoria, tipo_r in MAPEAMENTOS_PADRAO:
                linhas.append({
                    "id": gerar_id(), "padrao": padrao,
                    "categoria": categoria, "tipo": tipo_r, "criado_em": agora()
                })
            salvar_parquet("mapeamentos", pd.DataFrame(linhas))
            mensagem_sucesso(f"{len(linhas)} regras padrão carregadas!")
            st.rerun()
        st.info("Nenhuma regra cadastrada ainda.")
    else:
        st.success(f"✅ {len(df_reg)} regras ativas")
        df_exib = df_reg[["padrao","categoria","tipo"]].copy()
        df_exib.columns = ["Palavra-chave","Categoria","Tipo"]
        st.dataframe(df_exib, use_container_width=True, hide_index=True, height=300)

    st.divider()
    st.markdown("### ➕ Nova Regra")

    col1, col2, col3 = st.columns(3)
    with col1:
        novo_padrao = st.text_input("Palavra-chave:", placeholder="Ex: Netflix, Shopee...")
    with col2:
        cats_existentes = listar_categorias("despesa")
        nova_cat_sel = st.selectbox("Categoria:", ["➕ Nova categoria..."] + cats_existentes, key="reg_cat_sel")
        if nova_cat_sel == "➕ Nova categoria...":
            nova_cat_reg = st.text_input("Nome da nova categoria:", placeholder="Ex: 🎬 Streaming", key="reg_nova_cat")
        else:
            nova_cat_reg = nova_cat_sel
    with col3:
        novo_tipo = st.selectbox("Aplicar em:", ["ambos", "despesa", "receita"])

    if st.button("✅ Adicionar Regra", type="primary", use_container_width=True):
        if not novo_padrao or not nova_cat_reg:
            mensagem_erro("Preencha a palavra-chave e a categoria!")
        else:
            df_reg = ler_csv(MAPEAMENTOS_FILE)
            nova_linha = pd.DataFrame([{
                "id": gerar_id(), "padrao": novo_padrao.strip(),
                "categoria": nova_cat_reg.strip(), "tipo": novo_tipo, "criado_em": agora()
            }])
            df_final = pd.concat([df_reg, nova_linha], ignore_index=True) if not df_reg.empty else nova_linha
            salvar_parquet("mapeamentos", df_final)
            mensagem_sucesso(f"Regra adicionada: '{novo_padrao}' → '{nova_cat_reg}'")
            st.rerun()

    st.divider()
    if not df_reg.empty:
        st.markdown("### 🗑️ Remover Regra")
        opcoes_reg = [f"{r['padrao']} → {r['categoria']}" for _, r in df_reg.iterrows()]
        idx_del = st.selectbox("Selecione:", range(len(opcoes_reg)), format_func=lambda i: opcoes_reg[i])
        if st.button("🗑️ Remover Regra", use_container_width=True):
            id_del = df_reg.iloc[idx_del]["id"]
            salvar_parquet("mapeamentos", df_reg[df_reg["id"] != id_del])
            mensagem_sucesso("Regra removida!")
            st.rerun()


# ════════════════════════════════════════════════════════════
# ABA 4 — RECATEGORIZAR EM MASSA
# ════════════════════════════════════════════════════════════
with aba_recategorizar:
    st.markdown("### ⚡ Aplicar Regras em Massa")
    st.info(
        "Aplica todas as regras cadastradas sobre os dados existentes.\n\n"
        "Útil após adicionar novas regras ou importar dados novos."
    )

    df_reg = ler_csv(MAPEAMENTOS_FILE)
    if df_reg.empty:
        st.warning("Cadastre regras na aba **Regras de Categorização** primeiro.")
    else:
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            aplicar_desp = st.checkbox("Aplicar em Despesas", value=True)
        with col_p2:
            aplicar_rec = st.checkbox("Aplicar em Receitas", value=True)

        if st.button("⚡ Aplicar Regras Agora", type="primary", use_container_width=True):
            total_alt = 0
            if aplicar_desp:
                df_d2 = ler_csv(DESPESAS_FILE)
                if not df_d2.empty:
                    antes = df_d2["categoria"].copy()
                    df_d2 = aplicar_mapeamentos(df_d2)
                    alt   = int((df_d2["categoria"] != antes).sum())
                    salvar_parquet("despesas", df_d2)
                    total_alt += alt
                    st.caption(f"💸 Despesas: {alt} lançamentos recategorizados")

            if aplicar_rec:
                df_r2 = ler_csv(RECEITAS_FILE)
                if not df_r2.empty:
                    antes = df_r2["categoria"].copy()
                    df_r2 = aplicar_mapeamentos(df_r2)
                    alt   = int((df_r2["categoria"] != antes).sum())
                    salvar_parquet("receitas", df_r2)
                    total_alt += alt
                    st.caption(f"💰 Receitas: {alt} lançamentos recategorizados")

            mensagem_sucesso(f"✅ {total_alt} lançamentos recategorizados!")
            st.rerun()

    st.divider()
    st.markdown("### 🗑️ Excluir Categorias em Massa")
    st.info("Selecione várias categorias para excluir de uma vez. Os lançamentos de todas elas serão reclassificados para uma única categoria destino.")

    df_d_exc = ler_csv(DESPESAS_FILE)
    df_r_exc = ler_csv(RECEITAS_FILE)

    tipo_exc = st.radio("Tipo:", ["💸 Despesas", "💰 Receitas"], horizontal=True, key="tipo_exc")
    df_exc   = df_d_exc if "💸" in tipo_exc else df_r_exc
    tab_exc  = "despesas" if "💸" in tipo_exc else "receitas"

    if not df_exc.empty and "categoria" in df_exc.columns:
        cats_exc = sorted(df_exc["categoria"].dropna().unique().tolist())

        cats_remover = st.multiselect(
            "Categorias a excluir:",
            options=cats_exc,
            placeholder="Selecione uma ou mais categorias..."
        )

        if cats_remover:
            cats_destino = [c for c in cats_exc if c not in cats_remover]
            cat_destino_exc = st.selectbox("Reclassificar todos para:", cats_destino, key="cat_destino_exc")
            total_afetados = int(df_exc["categoria"].isin(cats_remover).sum())
            st.caption(f"ℹ️ {total_afetados} lançamento(s) serão reclassificados para **{cat_destino_exc}**")

            if st.button("🗑️ Excluir Categorias Selecionadas", type="primary", use_container_width=True, key="btn_excluir_massa"):
                df_exc.loc[df_exc["categoria"].isin(cats_remover), "categoria"] = cat_destino_exc
                salvar_parquet(tab_exc, df_exc)
                mensagem_sucesso(f"✅ {len(cats_remover)} categoria(s) removida(s). {total_afetados} lançamentos → \"{cat_destino_exc}\"")
                st.rerun()
    else:
        st.info("Sem dados.")

    st.divider()
    st.markdown("### 🔀 Migrar Categoria")
    st.info("Mova todos os lançamentos de uma categoria para outra. Útil para unificar ou renomear categorias.")

    df_d_mig = ler_csv(DESPESAS_FILE)
    df_r_mig = ler_csv(RECEITAS_FILE)

    tipo_mig = st.radio("Tipo:", ["💸 Despesas", "💰 Receitas"], horizontal=True, key="tipo_mig")
    df_mig   = df_d_mig if "💸" in tipo_mig else df_r_mig
    tab_mig  = "despesas" if "💸" in tipo_mig else "receitas"

    if not df_mig.empty and "categoria" in df_mig.columns:
        cats_mig = sorted(df_mig["categoria"].dropna().unique().tolist())

        col_de, col_para = st.columns(2)
        with col_de:
            cat_origem = st.selectbox("De (categoria atual):", cats_mig, key="cat_origem")
        with col_para:
            opcoes_destino = [c for c in cats_mig if c != cat_origem]
            cat_destino = st.selectbox("Para (nova categoria):", opcoes_destino, key="cat_destino")

        qtd_afetados = int((df_mig["categoria"] == cat_origem).sum())
        if qtd_afetados:
            st.caption(f"ℹ️ {qtd_afetados} lançamento(s) serão migrados de **{cat_origem}** → **{cat_destino}**")

        if st.button("🔀 Migrar Agora", type="primary", use_container_width=True, key="btn_migrar"):
            df_mig.loc[df_mig["categoria"] == cat_origem, "categoria"] = cat_destino
            salvar_parquet(tab_mig, df_mig)
            mensagem_sucesso(f"✅ {qtd_afetados} lançamentos migrados de \"{cat_origem}\" → \"{cat_destino}\"")
            st.rerun()
    else:
        st.info("Sem dados para migrar.")

    st.divider()
    st.markdown("### 🔍 Lançamentos sem Categoria Definida")
    df_d2 = ler_csv(DESPESAS_FILE)
    if not df_d2.empty and "categoria" in df_d2.columns:
        sem_cat = df_d2[df_d2["categoria"].astype(str).str.contains("Outros|outros", na=False)]
        if not sem_cat.empty:
            st.warning(f"⚠️ {len(sem_cat)} despesas classificadas como 'Outros'")
            df_exib2 = sem_cat[["data","descricao","valor","categoria"]].head(20).copy()
            df_exib2["valor"] = pd.to_numeric(df_exib2["valor"], errors="coerce").apply(formatar_moeda)
            df_exib2.columns  = ["Data","Descrição","Valor","Categoria"]
            st.dataframe(df_exib2, use_container_width=True, hide_index=True)
        else:
            st.success("✅ Nenhuma despesa sem categoria específica!")


# ════════════════════════════════════════════════════════════
# ABA 5 — CARTÕES
# ════════════════════════════════════════════════════════════
with aba_cartoes:
    st.markdown("### 💳 Gerenciar Cartões de Crédito")

    df_cartoes = ler_csv(CARTOES_FILE)

    # ── Lista atual ───────────────────────────────────────────
    if not df_cartoes.empty:
        for _, c in df_cartoes.iterrows():
            col_info, col_del = st.columns([5, 1])
            with col_info:
                st.markdown(
                    f"<div style='border-left:3px solid #4A9EFF;padding:8px 14px;"
                    f"background:#161B22;border-radius:6px;margin:4px 0'>"
                    f"<span style='color:#E6EDF3;font-weight:600'>💳 {c.get('nome','?')}</span>"
                    f"<span style='color:#556878;font-size:0.8rem'> · {c.get('bandeira','?')}"
                    f" · Limite: {formatar_moeda(float(c.get('limite',0)))}"
                    f" · Vence dia {c.get('dia_vencimento','?')}</span>"
                    f"</div>", unsafe_allow_html=True
                )
            with col_del:
                if st.button("🗑️", key=f"del_cart_{c['id']}", help="Excluir cartão"):
                    st.session_state[f"confirm_cart_{c['id']}"] = True

            if st.session_state.get(f"confirm_cart_{c['id']}"):
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Confirmar exclusão", key=f"ok_cart_{c['id']}", type="primary", use_container_width=True):
                        df_novo = df_cartoes[df_cartoes["id"] != c["id"]]
                        salvar_parquet("cartoes", df_novo)
                        st.session_state.pop(f"confirm_cart_{c['id']}", None)
                        mensagem_sucesso(f"Cartão '{c['nome']}' removido!")
                        st.rerun()
                with c2:
                    if st.button("❌ Cancelar", key=f"cancel_cart_{c['id']}", use_container_width=True):
                        st.session_state.pop(f"confirm_cart_{c['id']}", None)
                        st.rerun()
    else:
        st.info("Nenhum cartão cadastrado.")

    st.divider()
    st.markdown("### ➕ Novo Cartão")

    col1, col2 = st.columns(2)
    with col1:
        nome_c     = st.text_input("Nome:", placeholder="Ex: C6 BRU", key="cart_nome")
        bandeira_c = st.selectbox("Bandeira:", ["Mastercard","Visa","Elo","Amex","Hipercard"], key="cart_band")
    with col2:
        limite_c = st.number_input("Limite (R$):", value=5000.0, step=500.0, key="cart_lim")
        venc_c   = st.number_input("Dia de vencimento:", min_value=1, max_value=31, value=10, key="cart_venc")

    if st.button("✅ Adicionar Cartão", type="primary", use_container_width=True, key="btn_add_cart"):
        if nome_c.strip():
            novo = {
                "id": gerar_id(), "nome": nome_c.strip(), "bandeira": bandeira_c,
                "limite": round(limite_c, 2), "dia_vencimento": int(venc_c),
                "ativo": True, "criado_em": agora(),
            }
            df_ex = ler_csv(CARTOES_FILE)
            df_novo = pd.concat([df_ex, pd.DataFrame([novo])], ignore_index=True) if not df_ex.empty else pd.DataFrame([novo])
            salvar_parquet("cartoes", df_novo)
            mensagem_sucesso(f"Cartão '{nome_c}' adicionado!")
            st.rerun()
        else:
            mensagem_erro("Digite o nome do cartão.")


# ════════════════════════════════════════════════════════════
# ABA 6 — BANCOS
# ════════════════════════════════════════════════════════════
with aba_bancos:
    st.markdown("### 🏦 Gerenciar Bancos")
    st.info("Bancos cadastrados aqui aparecem na opção **Dar Baixa** da Agenda Financeira.")

    df_bancos = ler_csv("bancos")

    # ── Lista atual ───────────────────────────────────────────
    if not df_bancos.empty and "nome" in df_bancos.columns:
        for _, b in df_bancos.iterrows():
            col_info, col_del = st.columns([5, 1])
            with col_info:
                st.markdown(
                    f"<div style='border-left:3px solid #00C953;padding:8px 14px;"
                    f"background:#161B22;border-radius:6px;margin:4px 0'>"
                    f"<span style='color:#E6EDF3;font-weight:600'>🏦 {b.get('nome','?')}</span>"
                    f"</div>", unsafe_allow_html=True
                )
            with col_del:
                if st.button("🗑️", key=f"del_banco_{b['id']}", help="Excluir banco"):
                    st.session_state[f"confirm_banco_{b['id']}"] = True

            if st.session_state.get(f"confirm_banco_{b['id']}"):
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Confirmar", key=f"ok_banco_{b['id']}", type="primary", use_container_width=True):
                        df_novo = df_bancos[df_bancos["id"] != b["id"]]
                        salvar_parquet("bancos", df_novo)
                        st.session_state.pop(f"confirm_banco_{b['id']}", None)
                        mensagem_sucesso(f"Banco '{b['nome']}' removido!")
                        st.rerun()
                with c2:
                    if st.button("❌ Cancelar", key=f"cancel_banco_{b['id']}", use_container_width=True):
                        st.session_state.pop(f"confirm_banco_{b['id']}", None)
                        st.rerun()
    else:
        st.info("Nenhum banco cadastrado ainda.")

    st.divider()
    st.markdown("### ➕ Novo Banco")
    nome_b = st.text_input("Nome do banco:", placeholder="Ex: Itaú, Nubank, BB...", key="banco_nome")
    if st.button("✅ Adicionar Banco", type="primary", use_container_width=True, key="btn_add_banco"):
        if nome_b.strip():
            df_ex = ler_csv("bancos")
            novo  = pd.DataFrame([{"id": gerar_id(), "nome": nome_b.strip(), "criado_em": agora()}])
            df_novo = pd.concat([df_ex, novo], ignore_index=True) if not df_ex.empty else novo
            salvar_parquet("bancos", df_novo)
            mensagem_sucesso(f"Banco '{nome_b}' adicionado!")
            st.rerun()
        else:
            mensagem_erro("Digite o nome do banco.")


# ════════════════════════════════════════════════════════════
# ABA 7 — FORMAS DE PAGAMENTO
# ════════════════════════════════════════════════════════════
with aba_formas:
    st.markdown("### 💸 Formas de Pagamento e Recebimento")
    st.info("Formas cadastradas aqui ficam disponíveis nos campos de lançamento.")

    df_formas = ler_csv("formas_pagamento")

    col_fp, col_fr = st.columns(2)

    # ── Pagamento ─────────────────────────────────────────────
    with col_fp:
        st.markdown("#### 💸 Formas de Pagamento")
        formas_pag = df_formas[df_formas["tipo"] == "pagamento"] if not df_formas.empty and "tipo" in df_formas.columns else pd.DataFrame()

        if not formas_pag.empty:
            for _, f in formas_pag.iterrows():
                col_n, col_d = st.columns([4, 1])
                with col_n:
                    st.markdown(
                        f"<div style='border-left:3px solid #FF4D6D;padding:6px 12px;"
                        f"background:#161B22;border-radius:6px;margin:3px 0'>"
                        f"<span style='color:#E6EDF3'>{f['nome']}</span></div>",
                        unsafe_allow_html=True
                    )
                with col_d:
                    if st.button("🗑️", key=f"del_fp_{f['id']}"):
                        df_novo = df_formas[df_formas["id"] != f["id"]]
                        salvar_parquet("formas_pagamento", df_novo)
                        mensagem_sucesso("Removido!")
                        st.rerun()
        else:
            st.caption("Nenhuma forma cadastrada.")

        st.markdown("**➕ Nova forma de pagamento**")
        nova_fp = st.text_input("Nome:", placeholder="Ex: 📄 Boleto", key="nova_fp")
        if st.button("✅ Adicionar", key="btn_add_fp", use_container_width=True):
            if nova_fp.strip():
                df_ex = ler_csv("formas_pagamento")
                novo  = pd.DataFrame([{"id": gerar_id(), "nome": nova_fp.strip(), "tipo": "pagamento", "criado_em": agora()}])
                df_novo = pd.concat([df_ex, novo], ignore_index=True) if not df_ex.empty else novo
                salvar_parquet("formas_pagamento", df_novo)
                mensagem_sucesso(f"'{nova_fp}' adicionado!")
                st.rerun()

    # ── Recebimento ───────────────────────────────────────────
    with col_fr:
        st.markdown("#### 💰 Formas de Recebimento")
        formas_rec = df_formas[df_formas["tipo"] == "recebimento"] if not df_formas.empty and "tipo" in df_formas.columns else pd.DataFrame()

        if not formas_rec.empty:
            for _, f in formas_rec.iterrows():
                col_n, col_d = st.columns([4, 1])
                with col_n:
                    st.markdown(
                        f"<div style='border-left:3px solid #00C953;padding:6px 12px;"
                        f"background:#161B22;border-radius:6px;margin:3px 0'>"
                        f"<span style='color:#E6EDF3'>{f['nome']}</span></div>",
                        unsafe_allow_html=True
                    )
                with col_d:
                    if st.button("🗑️", key=f"del_fr_{f['id']}"):
                        df_novo = df_formas[df_formas["id"] != f["id"]]
                        salvar_parquet("formas_pagamento", df_novo)
                        mensagem_sucesso("Removido!")
                        st.rerun()
        else:
            st.caption("Nenhuma forma cadastrada.")

        st.markdown("**➕ Nova forma de recebimento**")
        nova_fr = st.text_input("Nome:", placeholder="Ex: 📱 PIX", key="nova_fr")
        if st.button("✅ Adicionar", key="btn_add_fr", use_container_width=True):
            if nova_fr.strip():
                df_ex = ler_csv("formas_pagamento")
                novo  = pd.DataFrame([{"id": gerar_id(), "nome": nova_fr.strip(), "tipo": "recebimento", "criado_em": agora()}])
                df_novo = pd.concat([df_ex, novo], ignore_index=True) if not df_ex.empty else novo
                salvar_parquet("formas_pagamento", df_novo)
                mensagem_sucesso(f"'{nova_fr}' adicionado!")
                st.rerun()

