# ============================================================
#  1_📆_Gastos_Semanais.py — Controle de Gastos da Semana
#  Ferramenta independente do Notion. Aqui você lança e corta gastos.
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st

from auth import exigir_login
exigir_login()

import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from ui_theme import paleta_graficos, tema_atual
from expense_defaults import categoria_do_local

from config import DESPESAS_FILE, CONFIG_FILE
from utils import (esc, 
    configurar_pagina, cabecalho_pagina, inicializar_dados,
    ler_csv, salvar_parquet, formatar_moeda, mensagem_sucesso, mensagem_erro, mensagem_aviso,
    ler_json, salvar_json, invalidar_cache, gerar_id, agora,
    salvar_despesas_novas, listar_categorias,
)
from fatura_projection import (
    projetar_parcelas, mascara_credito_cartao, inicio_semana,
    intervalo_fatura, aplicar_edicoes_semanais,
    faturas_encerradas, fatura_aberta, janela_semana, inicio_ciclo_aberto, lancamentos_semanais_fatura,
    meses_fatura_importados, semanas_fatura_importada, ciclo_fatura_importada,
)

configurar_pagina("Gastos Semanais", icone="📆")
inicializar_dados()

FONTE_SEMANAL = "Semanal"   # tag que mantém esses gastos separados do macro do Notion
ICE, AURORA, DESPESA, WARN = "#4FE3FF", "#39E0A6", "#FF5C7A", "#FFC24B"

HOJE = date.today()
DIAS_NOME = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

cfg = ler_json(str(CONFIG_FILE))
CATEGORIAS_DESPESA = listar_categorias("despesa")

# ── Header ───────────────────────────────────────────────────
st.markdown(f"""
<div class="thesis">
  <div class="eyebrow">Controle semanal · histórico por data</div>
  <div class="big" style="font-size:clamp(26px,4vw,40px)">Onde o dinheiro <em class="pos">está indo</em> esta semana</div>
  <div class="trow"><span class="pill mut">Independente do Notion · zera todo domingo e ao encerrar a fatura</span></div>
</div>
""", unsafe_allow_html=True)
st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
tab_atual, tab_fechadas = st.tabs(["📆 Semana atual", "🧾 Faturas fechadas"])

with tab_atual:

    # ── Semana consultada + limite padrão/exceção ─────────────────
    semana_ref = st.date_input("📅 Semana para acompanhar:", value=HOJE, format="DD/MM/YYYY",
                                help="Escolha qualquer dia; exibiremos a segunda a domingo correspondente.")
    SEG, DOM = inicio_semana(semana_ref), inicio_semana(semana_ref) + timedelta(days=6)

    df_limites = ler_csv("limites_semanais")
    if df_limites.empty:
        df_limites = pd.DataFrame(columns=["id", "chave", "inicio_semana", "valor", "criado_em"])
    _valor_padrao = pd.to_numeric(
        df_limites.loc[df_limites.get("chave", pd.Series(dtype=str)).astype(str) == "padrao", "valor"],
        errors="coerce",
    )
    limite_padrao = float(_valor_padrao.iloc[-1]) if not _valor_padrao.empty else float(cfg.get("limite_semanal", 0) or 0)
    chave_semana = SEG.isoformat()
    _valor_excecao = pd.to_numeric(
        df_limites.loc[df_limites.get("chave", pd.Series(dtype=str)).astype(str) == chave_semana, "valor"],
        errors="coerce",
    )
    tem_excecao = not _valor_excecao.empty
    limite = float(_valor_excecao.iloc[-1]) if tem_excecao else limite_padrao

    with st.expander("💰 Configurar limites semanais"):
        cl1, cl2 = st.columns(2)
        with cl1:
            novo_padrao = st.number_input("Limite padrão de toda semana (R$):", min_value=0.0,
                                          value=limite_padrao, step=50.0, format="%.2f")
            if st.button("💾 Salvar limite padrão", use_container_width=True):
                base = df_limites[df_limites["chave"].astype(str) != "padrao"].copy()
                linha = pd.DataFrame([{"id": gerar_id(), "chave": "padrao", "inicio_semana": "",
                                       "valor": round(float(novo_padrao), 2), "criado_em": agora()}])
                if salvar_parquet("limites_semanais", pd.concat([base, linha], ignore_index=True)):
                    invalidar_cache("limites_semanais"); mensagem_sucesso("Limite padrão salvo!"); st.rerun()
        with cl2:
            valor_semana = st.number_input(
                f"Exceção para {SEG.strftime('%d/%m')}–{DOM.strftime('%d/%m')} (R$):",
                min_value=0.0, value=limite if tem_excecao else limite_padrao, step=50.0, format="%.2f",
            )
            if st.button("💾 Salvar exceção desta semana", use_container_width=True):
                base = df_limites[df_limites["chave"].astype(str) != chave_semana].copy()
                linha = pd.DataFrame([{"id": gerar_id(), "chave": chave_semana, "inicio_semana": chave_semana,
                                       "valor": round(float(valor_semana), 2), "criado_em": agora()}])
                if salvar_parquet("limites_semanais", pd.concat([base, linha], ignore_index=True)):
                    invalidar_cache("limites_semanais"); mensagem_sucesso("Exceção semanal salva!"); st.rerun()
            if tem_excecao and st.button("↩️ Voltar ao limite padrão nesta semana", use_container_width=True):
                base = df_limites[df_limites["chave"].astype(str) != chave_semana].copy()
                if salvar_parquet("limites_semanais", base, permitir_vazio=True):
                    invalidar_cache("limites_semanais"); st.rerun()

    # ── Lançar gasto ─────────────────────────────────────────────
    if st.session_state.pop("_limpar_novo_gasto", False):
        st.session_state.pop("novo_gasto_descricao", None)
        st.session_state.pop("novo_gasto_categoria", None)

    def _sugerir_categoria_local():
        categoria = categoria_do_local(
            st.session_state.get("novo_gasto_descricao", ""),
            ler_csv(DESPESAS_FILE), CATEGORIAS_DESPESA,
        )
        if categoria:
            st.session_state["novo_gasto_categoria"] = categoria
        st.session_state["_categoria_local_sugerida"] = categoria

    with st.expander("➕ Lançar gasto da semana", expanded=False):
        g_desc = st.text_input("Descrição:", placeholder="ex: Cidade Jardim, Recibom, Deskontão",
                               key="novo_gasto_descricao", on_change=_sugerir_categoria_local)
        if st.session_state.get("_categoria_local_sugerida"):
            st.caption(f"Categoria lembrada: {st.session_state['_categoria_local_sugerida']}. Você pode alterar abaixo.")
        with st.form("form_gasto_semana", clear_on_submit=True):
            cg1, cg2, cg3 = st.columns([2, 2, 1])
            with cg1:
                g_data = st.date_input("Data:", value=semana_ref, max_value=HOJE,
                                       format="DD/MM/YYYY", help="Aceita lançamentos retroativos e os envia à semana correta.")
            with cg2:
                g_cat = st.selectbox("Categoria:", CATEGORIAS_DESPESA, key="novo_gasto_categoria")
                g_pag = st.selectbox("Forma de pagamento:", ["💳 Crédito", "💳 Débito", "📱 PIX", "💵 Dinheiro"])
                g_cartao = st.selectbox("Cartão (somente para crédito):", ["C6 BRU", "C6 PRI", "Nubank", "Não se aplica"])
            with cg3:
                g_valor = st.number_input("Valor (R$):", min_value=0.0, value=None,
                                          step=None, placeholder="0,00", format="%.2f")

            if st.form_submit_button("💾 Lançar gasto", type="primary", use_container_width=True):
                if not g_desc.strip():
                    mensagem_erro("Informe a descrição.")
                elif not g_valor or g_valor <= 0:
                    mensagem_erro("Informe um valor maior que zero.")
                else:
                    nova = pd.DataFrame([{
                        "id": gerar_id(), "data": g_data.strftime("%Y-%m-%d"),
                        "descricao": g_desc.strip(), "categoria": g_cat,
                        "valor": round(float(g_valor), 2), "forma_pagamento": g_pag,
                        "banco": g_cartao if g_pag == "💳 Crédito" else "", "status": "Pago", "observacao": "",
                        "fonte": FONTE_SEMANAL, "criado_em": agora(),
                    }])
                    n = salvar_despesas_novas(nova)
                    if n > 0:
                        st.session_state["_limpar_novo_gasto"] = True
                        st.session_state.pop("_categoria_local_sugerida", None)
                        invalidar_cache("despesas")
                        mensagem_sucesso(f"Gasto lançado: {g_desc.strip()} · {formatar_moeda(g_valor)}")
                        st.rerun()
                    elif n == 0:
                        mensagem_aviso("Esse gasto já parece estar lançado (mesma data, descrição e valor).")

    st.divider()

    df_d = ler_csv(DESPESAS_FILE)
    if not df_d.empty and "data" in df_d.columns:
        df_d["valor"]    = pd.to_numeric(df_d["valor"], errors="coerce").fillna(0)
        df_d["_dt"]      = pd.to_datetime(df_d["data"], errors="coerce")

    # ── Estimativa da fatura do cartão ────────────────────────────
    st.markdown('<div class="p-title"><span class="tbar"></span> Fatura estimada do mês</div>',
                unsafe_allow_html=True)

    df_bases = ler_csv("faturas_base")
    if df_bases.empty:
        df_bases = pd.DataFrame(columns=["id", "ano", "mes", "cartao", "valor", "criado_em"])
    for _col in ["ano", "mes", "valor"]:
        if _col in df_bases.columns:
            df_bases[_col] = pd.to_numeric(df_bases[_col], errors="coerce")

    df_fechamentos = ler_csv("fechamentos_fatura")
    if df_fechamentos.empty:
        df_fechamentos = pd.DataFrame(columns=["id", "ano", "mes", "cartao", "dia", "encerrada_em", "criado_em"])
    else:
        for _col in ["id", "ano", "mes", "cartao", "dia", "encerrada_em", "criado_em"]:
            if _col not in df_fechamentos.columns:
                df_fechamentos[_col] = ""
    for _col in ["ano", "mes", "dia"]:
        if _col in df_fechamentos.columns:
            df_fechamentos[_col] = pd.to_numeric(df_fechamentos[_col], errors="coerce")

    col_card, col_ref = st.columns([2, 1])
    with col_card:
        cartao_proj = st.selectbox("Cartão:", ["C6 BRU", "C6 PRI", "Nubank"], key="cartao_projecao")

    def _dia_fechamento(cartao, ano, mes):
        if df_fechamentos.empty:
            return 4
        mask = (
            df_fechamentos["ano"].eq(int(ano)) & df_fechamentos["mes"].eq(int(mes))
            & df_fechamentos["cartao"].astype(str).str.strip().str.casefold().eq(str(cartao).casefold())
        )
        encontrados = df_fechamentos[mask]
        return int(encontrados.iloc[-1]["dia"]) if not encontrados.empty else 4

    # A fatura em andamento é a seguinte à última que você encerrou manualmente;
    # sem encerramento manual, vale o padrão contratual (fecha dia 4).
    encerradas = faturas_encerradas(df_fechamentos, cartao_proj)
    ano_atual_fat, mes_atual_fat = fatura_aberta(encerradas, HOJE, 4)
    # Tudo até o último encerramento é passado (aba Faturas fechadas).
    INICIO_ABERTO = inicio_ciclo_aberto(encerradas)
    _ref_atual = pd.Timestamp(year=ano_atual_fat, month=mes_atual_fat, day=1)
    _refs = {_ref_atual + pd.DateOffset(months=n) for n in range(-1, 13)}
    if not df_bases.empty:
        for _, _rb in df_bases.dropna(subset=["ano", "mes"]).iterrows():
            _refs.add(pd.Timestamp(year=int(_rb["ano"]), month=int(_rb["mes"]), day=1))
    _refs = sorted(_refs)
    _labels_ref = [r.strftime("%m/%Y") for r in _refs]
    _default_ref = _labels_ref.index(_ref_atual.strftime("%m/%Y"))

    with col_ref:
        ref_label = st.selectbox("Fatura de referência:", _labels_ref, index=_default_ref,
                                 key=f"ref_fatura_{cartao_proj}_{_labels_ref[_default_ref]}",
                                 help="C6 fecha dia 4: compras do dia 5 em diante entram na fatura seguinte.")
    ref_ts = _refs[_labels_ref.index(ref_label)]
    ano_fatura, mes_fatura = int(ref_ts.year), int(ref_ts.month)
    dia_fechamento_anterior = _dia_fechamento(cartao_proj, ano_fatura, mes_fatura)
    _ref_seguinte = ref_ts + pd.DateOffset(months=1)
    dia_fechamento = _dia_fechamento(cartao_proj, int(_ref_seguinte.year), int(_ref_seguinte.month))
    inicio_ciclo, fim_ciclo = intervalo_fatura(
        ano_fatura, mes_fatura, dia_fechamento, dia_fechamento_anterior,
    )
    fatura_em_aberto = (ano_fatura, mes_fatura) == (ano_atual_fat, mes_atual_fat)
    encerrada_em = encerradas.get((ano_fatura, mes_fatura))
    if fatura_em_aberto:
        # Só termina quando você encerra: compras após o dia previsto seguem nela.
        fim_ciclo = max(fim_ciclo, HOJE)
        st.caption(f"Ciclo considerado: **{inicio_ciclo.strftime('%d/%m/%Y')} até hoje** · em aberto até você encerrar")
    else:
        _status = f" · encerrada em {encerrada_em.strftime('%d/%m/%Y')}" if encerrada_em else ""
        st.caption(f"Ciclo considerado: **{inicio_ciclo.strftime('%d/%m/%Y')} a {fim_ciclo.strftime('%d/%m/%Y')}**{_status}")

    _mask_prox = (
        df_fechamentos["ano"].eq(int(_ref_seguinte.year)) & df_fechamentos["mes"].eq(int(_ref_seguinte.month))
        & df_fechamentos["cartao"].astype(str).str.strip().str.casefold().eq(cartao_proj.casefold())
    ) if not df_fechamentos.empty else pd.Series(dtype=bool)
    _base_sem_prox = df_fechamentos[~_mask_prox].copy() if len(_mask_prox) else df_fechamentos.copy()

    if fatura_em_aberto:
        _ini_mes = date(ano_fatura, mes_fatura, 1)
        _fim_mes = (pd.Timestamp(_ini_mes) + pd.offsets.MonthEnd(0)).date()
        _min_enc = max(_ini_mes, inicio_ciclo)
        _max_enc = min(_fim_mes, HOJE)
        if _min_enc > _max_enc:
            st.caption(f"🔒 A fatura {ref_label} poderá ser encerrada a partir de {_min_enc.strftime('%d/%m/%Y')}.")
        else:
            with st.expander(f"🔒 Encerrar fatura {ref_label}"):
                st.caption("Ao encerrar, o acompanhamento semanal zera e os próximos lançamentos no crédito "
                           "passam a contar na fatura seguinte.")
                data_encerramento = st.date_input(
                    "Último dia que entra nesta fatura:", format="DD/MM/YYYY",
                    value=min(max(date(ano_fatura, mes_fatura, dia_fechamento), _min_enc), _max_enc),
                    min_value=_min_enc, max_value=_max_enc,
                    key=f"data_encerrar_{cartao_proj}_{ano_fatura}_{mes_fatura}",
                    help="Normalmente o dia do fechamento (4). Compras do dia seguinte em diante vão para a próxima fatura.",
                )
                if st.button(f"🔒 Encerrar fatura {ref_label}", type="primary", use_container_width=True,
                             key=f"encerrar_{cartao_proj}_{ano_fatura}_{mes_fatura}"):
                    _novo_fech = pd.DataFrame([{
                        "id": gerar_id(), "ano": int(_ref_seguinte.year), "mes": int(_ref_seguinte.month),
                        "cartao": cartao_proj, "dia": int(data_encerramento.day),
                        "encerrada_em": data_encerramento.isoformat(), "criado_em": agora(),
                    }])
                    if salvar_parquet("fechamentos_fatura", pd.concat([_base_sem_prox, _novo_fech], ignore_index=True)):
                        invalidar_cache("fechamentos_fatura")
                        mensagem_sucesso(f"Fatura {ref_label} encerrada em {data_encerramento.strftime('%d/%m/%Y')}. "
                                         f"Semana zerada para os novos lançamentos.")
                        st.rerun()
                    else:
                        mensagem_erro("Não foi possível encerrar a fatura.")
    elif encerrada_em and max(encerradas) == (ano_fatura, mes_fatura):
        with st.expander(f"↩️ Reabrir fatura {ref_label}"):
            st.caption("Desfaz o encerramento: esta volta a ser a fatura em andamento.")
            if st.button(f"↩️ Reabrir fatura {ref_label}", use_container_width=True,
                         key=f"reabrir_{cartao_proj}_{ano_fatura}_{mes_fatura}"):
                if salvar_parquet("fechamentos_fatura", _base_sem_prox, permitir_vazio=True):
                    invalidar_cache("fechamentos_fatura")
                    mensagem_sucesso(f"Fatura {ref_label} reaberta.")
                    st.rerun()
                else:
                    mensagem_erro("Não foi possível reabrir a fatura.")

    proj = projetar_parcelas(df_d, ano_fatura, mes_fatura, cartao_proj)

    # O valor informado pelo usuário é a fonte principal da estimativa. É salvo em
    # uma aba própria do Sheets para sobreviver aos reinícios do Streamlit Cloud.
    _mask_base = (
        (df_bases.get("ano", pd.Series(dtype=float)) == ano_fatura)
        & (df_bases.get("mes", pd.Series(dtype=float)) == mes_fatura)
        & (df_bases.get("cartao", pd.Series(dtype=str)).astype(str).str.strip().str.casefold() == cartao_proj.casefold())
    ) if not df_bases.empty else pd.Series(dtype=bool)
    _registro_base = df_bases[_mask_base] if len(_mask_base) else pd.DataFrame()
    base_manual = float(_registro_base.iloc[-1]["valor"]) if not _registro_base.empty else None
    valor_atual_banco = None
    if not _registro_base.empty and "valor_atual" in _registro_base.columns:
        _vab = pd.to_numeric(pd.Series([_registro_base.iloc[-1].get("valor_atual")]), errors="coerce").iloc[0]
        valor_atual_banco = float(_vab) if pd.notna(_vab) else None

    with st.expander("✍️ Definir valores informados pelo banco", expanded=base_manual is None):
        st.caption(f"Este valor ficará vinculado a **{cartao_proj} · {ref_label}**.")
        novo_base = st.number_input(
            "Valor inicial da fatura (R$):", min_value=0.0,
            value=base_manual, step=None, placeholder="0,00", format="%.2f",
            key=f"base_fatura_{cartao_proj}_{ano_fatura}_{mes_fatura}",
        )
        novo_valor_atual = st.number_input(
            "Valor atual mostrado no banco (opcional):", min_value=0.0,
            value=valor_atual_banco, step=None, placeholder="0,00", format="%.2f",
            key=f"atual_fatura_{cartao_proj}_{ano_fatura}_{mes_fatura}",
            help="Serve para conferir a soma do dashboard; não altera os lançamentos.",
        )
        if st.button("💾 Salvar valor inicial", type="primary", use_container_width=True,
                     key=f"salvar_base_{cartao_proj}_{ano_fatura}_{mes_fatura}"):
            if novo_base is None:
                mensagem_erro("Informe o valor inicial da fatura.")
            else:
                df_bases = df_bases[~_mask_base].copy() if len(_mask_base) else df_bases.copy()
                nova_base = pd.DataFrame([{
                    "id": gerar_id(), "ano": ano_fatura, "mes": mes_fatura,
                    "cartao": cartao_proj, "valor": round(float(novo_base), 2),
                    "valor_atual": round(float(novo_valor_atual), 2) if novo_valor_atual is not None else "",
                    "criado_em": agora(),
                }])
                ok_base = salvar_parquet("faturas_base", pd.concat([df_bases, nova_base], ignore_index=True))
                if ok_base:
                    invalidar_cache("faturas_base")
                    mensagem_sucesso(f"Valor inicial de {formatar_moeda(novo_base)} salvo para {ref_label}.")
                    st.rerun()
                else:
                    mensagem_erro("Não foi possível salvar o valor inicial.")

    base_parcelada = base_manual if base_manual is not None else proj["total"]

    if not df_d.empty:
        _fon = df_d.get("fonte", pd.Series("", index=df_d.index)).astype(str)
        _dt = pd.to_datetime(df_d.get("data"), errors="coerce")
        _no_ciclo = (_dt.dt.date >= inicio_ciclo) & (_dt.dt.date <= fim_ciclo)
        _credito_cartao = mascara_credito_cartao(df_d, cartao_proj)
        _gastos_ciclo = df_d[(_fon == FONTE_SEMANAL) & _no_ciclo].copy()
        sem_credito = df_d[(_fon == FONTE_SEMANAL) & _credito_cartao & _no_ciclo].copy()
    else:
        _gastos_ciclo = pd.DataFrame()
        sem_credito = pd.DataFrame()

    gastos_credito = float(sem_credito["valor"].sum()) if not sem_credito.empty else 0.0
    estimada = base_parcelada + gastos_credito
    f1, f2, f3, f4 = st.columns(4)
    _origem_base = "valor fixado por você" if base_manual is not None else "parcelas identificadas"
    f1.metric("Fatura começa em", formatar_moeda(base_parcelada), help=_origem_base)
    f2.metric("Novos gastos no crédito", formatar_moeda(gastos_credito))
    f3.metric("Fatura estimada", formatar_moeda(estimada))
    f4.metric("Valor no banco", formatar_moeda(valor_atual_banco) if valor_atual_banco is not None else "não informado")

    _total_ciclo = float(_gastos_ciclo["valor"].sum()) if not _gastos_ciclo.empty else 0.0
    _fora_cartao = round(_total_ciclo - gastos_credito, 2)
    st.caption(
        f"Conciliação de {inicio_ciclo:%d/%m/%Y} a {fim_ciclo:%d/%m/%Y}: "
        f"gastos semanais lançados {formatar_moeda(_total_ciclo)} "
        f"− outras formas/cartões {formatar_moeda(_fora_cartao)} "
        f"= crédito no {cartao_proj} {formatar_moeda(gastos_credito)}. "
        f"Base {formatar_moeda(base_parcelada)} + crédito = {formatar_moeda(estimada)}."
    )

    if valor_atual_banco is not None:
        _diferenca_banco = round(estimada - valor_atual_banco, 2)
        if abs(_diferenca_banco) <= 0.01:
            st.success("✅ Dashboard e banco estão conciliados nos centavos.")
        else:
            _sentido = "a mais" if _diferenca_banco > 0 else "a menos"
            st.warning(f"⚠️ O dashboard está {formatar_moeda(abs(_diferenca_banco))} {_sentido} que o banco.")

    if cartao_proj == "C6 BRU" and not sem_credito.empty:
        _sem_banco = sem_credito.get("banco", pd.Series("", index=sem_credito.index)).astype(str).str.strip().eq("").sum()
        if _sem_banco:
            st.caption(f"ℹ️ {_sem_banco} compra(s) antiga(s) no crédito sem cartão informado foram consideradas como C6 BRU.")

    if base_manual is not None:
        st.caption(f"🔒 Base mensal fixada manualmente: **{formatar_moeda(base_manual)}**. A projeção por parcelas não altera este valor.")
    elif proj["candidatos"] and not proj["com_parcela"]:
        st.warning("⚠️ As faturas antigas não guardaram a coluna Parcela. A base inicial aparece zerada até que uma fatura "
                   "seja reimportada pelo importador atualizado; não estimarei valores sem comprovação.")
    elif proj["candidatos"] > proj["com_parcela"]:
        st.caption(f"Cobertura das parcelas: {proj['com_parcela']} de {proj['candidatos']} lançamentos anteriores possuem metadados.")

    with st.expander("🔎 Ver parcelas que formam o valor inicial"):
        if proj["itens"].empty:
            st.caption("Nenhuma parcela comprovada para este mês.")
        else:
            _pi = proj["itens"][["descricao", "_valor", "parcela_projetada", "_pt"]].copy()
            _pi.columns = ["Descrição", "Valor", "Parcela atual", "Total de parcelas"]
            st.dataframe(_pi, hide_index=True, use_container_width=True,
                         column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")})

    _linhas_futuras, _detalhes_futuros = [], []
    for _n_mes in range(1, 13):
        _ref_fut = ref_ts + pd.DateOffset(months=_n_mes)
        _af, _mf = int(_ref_fut.year), int(_ref_fut.month)
        _proj_fut = projetar_parcelas(df_d, _af, _mf, cartao_proj)
        _mask_bf = (
            df_bases["ano"].eq(_af) & df_bases["mes"].eq(_mf)
            & df_bases["cartao"].astype(str).str.strip().str.casefold().eq(cartao_proj.casefold())
        ) if not df_bases.empty else pd.Series(dtype=bool)
        _bf = df_bases[_mask_bf] if len(_mask_bf) else pd.DataFrame()
        _fixo_fut = float(_bf.iloc[-1]["valor"]) if not _bf.empty else None
        _valor_fut = _fixo_fut if _fixo_fut is not None else float(_proj_fut["total"])
        _linhas_futuras.append({
            "Fatura": _ref_fut.strftime("%m/%Y"), "Parcelas identificadas": len(_proj_fut["itens"]),
            "Comprometido": _valor_fut, "Origem": "Valor fixado" if _fixo_fut is not None else "Parcelas importadas",
        })
        if not _proj_fut["itens"].empty:
            for _, _pf in _proj_fut["itens"].iterrows():
                _detalhes_futuros.append({
                    "Fatura": _ref_fut.strftime("%m/%Y"), "Descrição": _pf.get("descricao", ""),
                    "Parcela": f"{int(_pf['parcela_projetada'])}/{int(_pf['_pt'])}", "Valor": float(_pf["_valor"]),
                })
    _linhas_futuras_visiveis = [
        linha for linha in _linhas_futuras
        if float(linha["Comprometido"]) > 0 or linha["Origem"] == "Valor fixado"
    ]
    if _linhas_futuras_visiveis:
        st.markdown("#### 📅 Parcelas comprometidas nos próximos meses")
        st.dataframe(
            pd.DataFrame(_linhas_futuras_visiveis), hide_index=True, use_container_width=True,
            column_config={"Comprometido": st.column_config.NumberColumn(format="R$ %.2f")},
        )
        if _detalhes_futuros:
            with st.expander("🔎 Ver detalhamento das parcelas futuras"):
                st.dataframe(
                    pd.DataFrame(_detalhes_futuros), hide_index=True, use_container_width=True,
                    column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")},
                )

    st.divider()

    # ── Gastos semanais da semana, zerados no encerramento da fatura ──
    INI_SEM, FIM_SEM = janela_semana(SEG, DOM, semana_ref, list(encerradas.values()))
    df_sem = pd.DataFrame()
    if not df_d.empty and "_dt" in df_d.columns:
        eh_semanal = df_d.get("fonte", pd.Series("", index=df_d.index)).astype(str) == FONTE_SEMANAL
        na_semana  = (df_d["_dt"].dt.date >= INI_SEM) & (df_d["_dt"].dt.date <= FIM_SEM)
        df_sem = df_d[eh_semanal & na_semana].copy()
    semana_encerrada = INICIO_ABERTO is not None and FIM_SEM < INICIO_ABERTO
    if semana_encerrada:
        df_sem = pd.DataFrame()
    _nota_corte = " · recortada no encerramento da fatura" if (INI_SEM, FIM_SEM) != (SEG, DOM) else ""
    st.caption(f"Semana exibida: **{INI_SEM.strftime('%d/%m/%Y')} a {FIM_SEM.strftime('%d/%m/%Y')}**{_nota_corte}")

    total = df_sem["valor"].sum() if not df_sem.empty else 0.0
    restante = max(limite - total, 0) if limite > 0 else 0
    pct = min(total / limite, 1.0) if limite > 0 else 0

    # ── KPIs ─────────────────────────────────────────────────────
    cor_saldo = AURORA if (limite > 0 and pct < 0.7) else (WARN if pct < 1.0 else DESPESA)
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f"""<div class="kpi despesa"><div class="k-top"><span class="k-lab">Gasto na semana</span>
        <span class="k-ico">💸</span></div><div class="k-val num">{formatar_moeda(total)}</div>
        <div class="k-sub">{len(df_sem)} lançamentos</div></div>""", unsafe_allow_html=True)
    with k2:
        val_saldo = formatar_moeda(restante) if limite > 0 else "sem limite"
        st.markdown(f"""<div class="kpi saldo"><div class="k-top"><span class="k-lab">Saldo do limite</span>
        <span class="k-ico">💵</span></div><div class="k-val num" style="color:{cor_saldo}">{val_saldo}</div>
        <div class="k-sub">{'de ' + formatar_moeda(limite) if limite > 0 else 'defina um limite acima'}</div></div>""",
            unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi poup"><div class="k-top"><span class="k-lab">Uso do limite</span>
        <span class="k-ico">📊</span></div><div class="k-val num">{pct*100:.0f}%</div>
        <div class="k-sub">{'restam ' + formatar_moeda(restante) if limite > 0 else '—'}</div></div>""",
            unsafe_allow_html=True)

    # ── Barra de progresso ───────────────────────────────────────
    if limite > 0:
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        st.markdown(f"""<div class="bar-outer"><div class="bar-inner" style="width:{pct*100:.0f}%;
        background:linear-gradient(90deg,{cor_saldo},{cor_saldo}bb);box-shadow:0 0 16px {cor_saldo}55"></div></div>""",
            unsafe_allow_html=True)
        if pct >= 1.0:
            st.error(f"🚨 Limite estourado! Você gastou {formatar_moeda(total)} de {formatar_moeda(limite)}.")
        elif pct >= 0.8:
            st.warning(f"⚠️ Já usou {pct*100:.0f}% do limite semanal.")

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── Gastos por dia ───────────────────────────────────────────
    if semana_encerrada:
        st.info("Esta semana pertence a uma fatura já encerrada. Veja os gastos dela na aba **🧾 Faturas fechadas**.")
    elif df_sem.empty:
        st.info("Nenhum gasto lançado nesta semana ainda. Use **➕ Lançar gasto da semana** acima.")
    else:
        df_sem["_dia"] = df_sem["_dt"].dt.date
        for dia in sorted(df_sem["_dia"].dropna().unique()):
            sub = df_sem[df_sem["_dia"] == dia]
            nome = DIAS_NOME[dia.weekday()]
            with st.expander(f"**{nome}, {dia.strftime('%d/%m')}** — {formatar_moeda(sub['valor'].sum())}", expanded=True):
                for _, r in sub.iterrows():
                    st.markdown(
                        f"<div class='weekly-entry'>"
                        f"<span class='weekly-entry-name'>{esc(r['descricao'])}"
                        f"<span class='weekly-entry-meta'> · {esc(r.get('categoria',''))} · {esc(r.get('forma_pagamento',''))}</span></span>"
                        f"<span class='weekly-entry-value num'>{formatar_moeda(r['valor'])}</span></div>",
                        unsafe_allow_html=True)

        # ── Editar / excluir ─────────────────────────────────────
        with st.expander("✏️ Editar ou excluir gastos"):
            st.caption("Altere qualquer célula ou marque 🗑️ para excluir. Depois clique em **Salvar**.")
            df_ed = df_sem[["data", "descricao", "categoria", "valor", "forma_pagamento", "banco", "id"]].copy()
            df_ed["data"] = pd.to_datetime(df_ed["data"], errors="coerce").dt.date
            df_ed["id"]   = df_ed["id"].astype(str)
            df_ed.insert(0, "🗑️", False)
            editado = st.data_editor(
                df_ed,
                column_config={
                    "🗑️":              st.column_config.CheckboxColumn("🗑️", width="small"),
                    "data":            st.column_config.DateColumn("Data", format="DD/MM/YYYY", width="small"),
                    "descricao":       st.column_config.TextColumn("Descrição", width="large"),
                    "categoria":       st.column_config.SelectboxColumn("Categoria", options=CATEGORIAS_DESPESA),
                    "valor":           st.column_config.NumberColumn("Valor", format="R$ %.2f", min_value=0.0),
                    "forma_pagamento": st.column_config.SelectboxColumn("Forma", options=["💳 Débito", "📱 PIX", "💵 Dinheiro", "💳 Crédito"]),
                    "banco":           st.column_config.SelectboxColumn("Cartão", options=["", "C6 BRU", "C6 PRI", "Nubank"]),
                    "id":              st.column_config.TextColumn("ID", disabled=True, width="small"),
                },
                column_order=["🗑️", "data", "descricao", "categoria", "valor", "forma_pagamento", "banco"],
                hide_index=True, use_container_width=True, num_rows="fixed", key="editor_semana",
            )
            if st.button("💾 Salvar alterações", type="primary", use_container_width=True, key="btn_salvar_sem"):
                full = ler_csv(DESPESAS_FILE)
                if not full.empty:
                    ids_del = set(editado[editado["🗑️"] == True]["id"].astype(str))
                    for _, row in editado.iterrows():
                        rid = str(row["id"])
                        if rid in ids_del:
                            continue
                        m = full["id"].astype(str) == rid
                        if m.any():
                            nd = row["data"]
                            full.loc[m, "data"] = nd.strftime("%Y-%m-%d") if hasattr(nd, "strftime") else str(nd)
                            full.loc[m, "descricao"]       = str(row["descricao"])
                            full.loc[m, "categoria"]       = str(row["categoria"])
                            full.loc[m, "valor"]           = round(float(row["valor"] or 0), 2)
                            full.loc[m, "forma_pagamento"] = str(row["forma_pagamento"])
                            full.loc[m, "banco"]           = str(row["banco"]) if "crédito" in str(row["forma_pagamento"]).casefold() else ""
                    if ids_del:
                        full = full[~full["id"].astype(str).isin(ids_del)]
                    # checa o retorno: se a trava de segurança bloquear, não finge sucesso
                    if salvar_parquet("despesas", full):
                        invalidar_cache("despesas")
                        n_del = len(ids_del)
                        mensagem_sucesso("Alterações salvas!" + (f" {n_del} excluído(s)." if n_del else ""))
                        st.rerun()
                    else:
                        mensagem_erro("Gravação bloqueada por segurança — nada foi alterado. Recarregue e tente de novo.")

        st.divider()
        st.markdown('<div class="p-title"><span class="tbar"></span> Ranking da semana por categoria</div>',
                    unsafe_allow_html=True)
        rank = df_sem.groupby("categoria")["valor"].sum().sort_values(ascending=False)
        maxv = rank.max() or 1
        linhas = ""
        for cat, val in rank.items():
            linhas += (f'<div><div class="c-top"><span class="c-name">{esc(cat)}</span>'
                       f'<span class="c-val num">{formatar_moeda(val)}</span></div>'
                       f'<div class="track"><div class="fill" style="width:{val/maxv*100:.0f}%;'
                       f'background:linear-gradient(90deg,#FF5C7A,#FF8AA0)"></div></div></div>')
        st.markdown(f'<div class="cat">{linhas}</div>', unsafe_allow_html=True)

    # ── Histórico completo organizado por semana ─────────────────
    st.divider()
    st.markdown('<div class="p-title"><span class="tbar"></span> Histórico de semanas</div>',
                unsafe_allow_html=True)
    st.caption("Semanas de segunda a domingo, com todos os meios de pagamento e cartões. A fatura estimada considera apenas o crédito do cartão selecionado no ciclo informado acima.")
    if df_d.empty:
        st.caption("Ainda não há lançamentos semanais.")
    else:
        _hist = df_d[df_d.get("fonte", pd.Series("", index=df_d.index)).astype(str) == FONTE_SEMANAL].copy()
        _hist["_dt_hist"] = pd.to_datetime(_hist.get("data"), errors="coerce")
        _hist = _hist[_hist["_dt_hist"].notna()].copy()
        if INICIO_ABERTO is not None:
            _hist = _hist[_hist["_dt_hist"].dt.date >= INICIO_ABERTO].copy()
            st.caption(f"Desde {INICIO_ABERTO.strftime('%d/%m/%Y')} (fatura em aberto). "
                       f"O que veio antes está na aba **🧾 Faturas fechadas**.")
        _hist["_inicio_semana"] = _hist["_dt_hist"].apply(inicio_semana)
        _totais_sem = _hist.groupby("_inicio_semana")["valor"].sum().sort_index().tail(8)
        _semana_grafico = None
        if not _totais_sem.empty:
            _pal = paleta_graficos(tema_atual())
            _rotulos_sem = [max(d, INICIO_ABERTO or d).strftime("%d/%m") for d in _totais_sem.index]
            _fig_sem = go.Figure(go.Bar(
                x=_rotulos_sem, y=_totais_sem.values, marker_color=_pal["destaque"],
                hovertemplate="Semana de %{x}<br>R$ %{y:,.2f}<extra></extra>",
            ))
            _fig_sem.update_layout(
                paper_bgcolor=_pal["fundo"], plot_bgcolor=_pal["fundo"],
                font=dict(color=_pal["texto"]), margin=dict(l=4, r=4, t=8, b=6),
                height=220, showlegend=False,
                xaxis=dict(showgrid=False, tickfont=dict(color=_pal["texto"])),
                yaxis=dict(gridcolor=_pal["grade"], tickprefix="R$ ",
                           tickfont=dict(color=_pal["texto"])),
            )
            _sel_sem = st.plotly_chart(
                _fig_sem, use_container_width=True, key="historico_semanal_grafico", theme=None,
                on_select="rerun", selection_mode="points",
            )
            _pontos_sem = _sel_sem.selection.points if _sel_sem else []
            if _pontos_sem:
                _pos_sem = _pontos_sem[0].get("point_index", _pontos_sem[0].get("pointNumber", -1))
                if isinstance(_pos_sem, int) and 0 <= _pos_sem < len(_totais_sem):
                    _semana_grafico = _totais_sem.index[_pos_sem]
            st.caption("Clique numa barra para abrir os lançamentos daquela semana.")
        for _ini in sorted(_hist["_inicio_semana"].unique(), reverse=True):
            _fim = _ini + timedelta(days=6)
            _hs = _hist[_hist["_inicio_semana"] == _ini].sort_values("_dt_hist")
            _chave = _ini.isoformat()
            _lim_exc = pd.to_numeric(
                df_limites.loc[df_limites.get("chave", pd.Series(dtype=str)).astype(str) == _chave, "valor"],
                errors="coerce",
            )
            _lim_h = float(_lim_exc.iloc[-1]) if not _lim_exc.empty else limite_padrao
            _tot_h = float(_hs["valor"].sum())
            _tag_lim = f" · limite {formatar_moeda(_lim_h)}" if _lim_h > 0 else ""
            with st.expander(
                f"{max(_ini, INICIO_ABERTO or _ini).strftime('%d/%m/%Y')}–{_fim.strftime('%d/%m/%Y')} · "
                f"{formatar_moeda(_tot_h)} · {len(_hs)} lançamento(s){_tag_lim}",
                expanded=(_ini == SEG or _ini == _semana_grafico),
            ):
                _edit_hist = _hs[["data", "descricao", "categoria", "forma_pagamento", "banco", "valor", "id"]].copy()
                _edit_hist["data"] = _hs["_dt_hist"].dt.date
                _edit_hist.insert(0, "Excluir", False)
                _editado_hist = st.data_editor(
                    _edit_hist, hide_index=True, use_container_width=True, num_rows="fixed",
                    key=f"editor_hist_{_chave}",
                    column_config={
                        "Excluir":         st.column_config.CheckboxColumn("🗑️", width="small"),
                        "data":            st.column_config.DateColumn("Data", format="DD/MM/YYYY", max_value=HOJE),
                        "descricao":       st.column_config.TextColumn("Descrição", width="large"),
                        "categoria":       st.column_config.SelectboxColumn("Categoria", options=CATEGORIAS_DESPESA),
                        "forma_pagamento": st.column_config.SelectboxColumn("Forma", options=["💳 Débito", "📱 PIX", "💵 Dinheiro", "💳 Crédito"]),
                        "banco":           st.column_config.SelectboxColumn("Cartão", options=["", "C6 BRU", "C6 PRI", "Nubank"]),
                        "valor":           st.column_config.NumberColumn("Valor", format="R$ %.2f", min_value=0.01),
                        "id":              st.column_config.TextColumn("ID", disabled=True),
                    },
                    column_order=["Excluir", "data", "descricao", "categoria", "forma_pagamento", "banco", "valor"],
                )
                if st.button("💾 Salvar alterações desta semana", type="primary", use_container_width=True,
                             key=f"salvar_hist_{_chave}"):
                    _ativos_hist = _editado_hist[_editado_hist["Excluir"] != True]
                    if _ativos_hist["descricao"].astype(str).str.strip().eq("").any():
                        mensagem_erro("A descrição não pode ficar vazia.")
                    elif pd.to_numeric(_ativos_hist["valor"], errors="coerce").fillna(0).le(0).any():
                        mensagem_erro("O valor precisa ser maior que zero.")
                    elif _ativos_hist["data"].isna().any():
                        mensagem_erro("A data não pode ficar vazia.")
                    else:
                        _full_hist = ler_csv(DESPESAS_FILE)
                        _full_hist, _n_del_hist = aplicar_edicoes_semanais(_full_hist, _editado_hist)
                        if salvar_parquet("despesas", _full_hist, permitir_vazio=True):
                            invalidar_cache("despesas")
                            _msg_del = f" · {_n_del_hist} excluído(s)" if _n_del_hist else ""
                            mensagem_sucesso(f"Alterações salvas{_msg_del}!")
                            st.rerun()
                        else:
                            mensagem_erro("Não foi possível salvar as alterações.")

# ── Faturas fechadas: semanas reconstruídas a partir da fatura importada ──
with tab_fechadas:
    st.caption("Semanas montadas pela **data da compra** de cada linha da fatura importada do C6 "
               "(Configurações → Importar). Fatura encerrada e ainda não importada aparece com os "
               "gastos no crédito que você lançou à mão até o encerramento.")
    cf1, cf2 = st.columns([2, 1])
    with cf1:
        cartao_fech = st.selectbox("Cartão:", ["C6 BRU", "C6 PRI", "Nubank"], key="cartao_faturas_fechadas")
    _importadas_f = set(meses_fatura_importados(df_d, cartao_fech))
    _encerradas_f = faturas_encerradas(df_fechamentos, cartao_fech)
    _meses_imp = sorted(_importadas_f | set(_encerradas_f), reverse=True)
    if not _meses_imp:
        st.info(f"Nenhuma fatura do {cartao_fech} importada ou encerrada ainda.")
    else:
        _labels_imp = [f"{m:02d}/{a}" + ("" if (a, m) in _importadas_f else " · não importada")
                       for a, m in _meses_imp]
        with cf2:
            _fat_label = st.selectbox("Fatura:", _labels_imp, key=f"fatura_fechada_{cartao_fech}")
        _af, _mf = _meses_imp[_labels_imp.index(_fat_label)]
        if (_af, _mf) in _importadas_f:
            _ciclo_f = ciclo_fatura_importada(df_d, _af, _mf, cartao_fech)
            if _ciclo_f is None:
                _ciclo_f = intervalo_fatura(_af, _mf, _dia_fechamento(cartao_fech, _af, _mf))
            _ini_f, _fim_f = _ciclo_f
            _fat = semanas_fatura_importada(df_d, _af, _mf, cartao_fech, _ini_f, _fim_f)
            _origem_ciclo = "lido da própria fatura: da compra seguinte ao fechamento anterior até a última compra"
        else:
            _ant_f = pd.Timestamp(year=_af, month=_mf, day=1) - pd.DateOffset(months=1)
            _fim_f = _encerradas_f[(_af, _mf)]
            _enc_ant = _encerradas_f.get((int(_ant_f.year), int(_ant_f.month)))
            _ini_f = _enc_ant + timedelta(days=1) if _enc_ant else intervalo_fatura(_af, _mf)[0]
            _fat = lancamentos_semanais_fatura(df_d, cartao_fech, _ini_f, _fim_f, FONTE_SEMANAL)
            _origem_ciclo = "até o encerramento que você informou"
            st.warning("Fatura ainda não importada: mostrando só os gastos no crédito lançados à mão. "
                       "Importe o arquivo do C6 em Configurações para ver a fatura completa.")
        _sem_f, _fora_f = _fat["semanas"], _fat["fora"]
        _tot_sem_f = float(_sem_f["_valor"].sum()) if not _sem_f.empty else 0.0
        _tot_fora_f = float(_fora_f["_valor"].sum()) if not _fora_f.empty else 0.0
        st.caption(f"Ciclo: **{_ini_f.strftime('%d/%m/%Y')} a {_fim_f.strftime('%d/%m/%Y')}** ({_origem_ciclo})")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total da fatura", formatar_moeda(_fat["total"]))
        m2.metric("Compras do ciclo (semanas)", formatar_moeda(_tot_sem_f), help=f"{len(_sem_f)} lançamento(s)")
        m3.metric("Parcelas e compras anteriores", formatar_moeda(_tot_fora_f), help=f"{len(_fora_f)} lançamento(s)")

        def _tabela_fatura(linhas):
            _t = pd.DataFrame({
                "Data da compra": linhas["_compra"],
                "Descrição": linhas.get("descricao", ""),
                "Categoria": linhas.get("categoria", ""),
                "Valor": linhas["_valor"],
            })
            st.dataframe(_t, hide_index=True, use_container_width=True, column_config={
                "Data da compra": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Valor": st.column_config.NumberColumn(format="R$ %.2f"),
            })

        if not _sem_f.empty:
            _por_sem = _sem_f.groupby("_inicio_semana")["_valor"].sum().sort_index()
            _rot_f = [
                f"{max(d, _ini_f).strftime('%d/%m')}–{min(d + timedelta(days=6), _fim_f).strftime('%d/%m')}"
                for d in _por_sem.index
            ]
            _pal_f = paleta_graficos(tema_atual())
            _fig_f = go.Figure(go.Bar(
                x=_rot_f, y=_por_sem.values, marker_color=_pal_f["destaque"],
                hovertemplate="Semana %{x}<br>R$ %{y:,.2f}<extra></extra>",
            ))
            _fig_f.update_layout(
                paper_bgcolor=_pal_f["fundo"], plot_bgcolor=_pal_f["fundo"],
                font=dict(color=_pal_f["texto"]), margin=dict(l=4, r=4, t=8, b=6),
                height=220, showlegend=False,
                xaxis=dict(showgrid=False, tickfont=dict(color=_pal_f["texto"])),
                yaxis=dict(gridcolor=_pal_f["grade"], tickprefix="R$ ",
                           tickfont=dict(color=_pal_f["texto"])),
            )
            st.plotly_chart(_fig_f, use_container_width=True, key="faturas_fechadas_grafico", theme=None)
            for _ini_s, _rot in zip(_por_sem.index, _rot_f):
                _ls = _sem_f[_sem_f["_inicio_semana"] == _ini_s]
                with st.expander(f"Semana {_rot} · {formatar_moeda(_ls['_valor'].sum())} · {len(_ls)} compra(s)"):
                    _tabela_fatura(_ls)
        if not _fora_f.empty:
            with st.expander(f"Parcelas e compras anteriores ao ciclo · {formatar_moeda(_tot_fora_f)} · "
                             f"{len(_fora_f)} lançamento(s)"):
                st.caption("Parcelas de compras antigas e compras que o banco lançou com atraso.")
                _tabela_fatura(_fora_f)
