# ============================================================
#  1_📆_Gastos_Semanais.py — Controle de Gastos da Semana
#  Ferramenta independente do Notion. Aqui você lança e corta gastos.
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st

from auth import exigir_login
exigir_login()

import pandas as pd
from datetime import date, timedelta

from config import DESPESAS_FILE, CONFIG_FILE
from utils import (esc, 
    configurar_pagina, cabecalho_pagina, inicializar_dados,
    ler_csv, salvar_parquet, formatar_moeda, mensagem_sucesso, mensagem_erro, mensagem_aviso,
    ler_json, salvar_json, invalidar_cache, gerar_id, agora,
    salvar_despesas_novas, listar_categorias,
)
from fatura_projection import (
    projetar_parcelas, mascara_credito_cartao, inicio_semana,
    competencia_fatura, intervalo_fatura, semana_no_ciclo_fatura,
    aplicar_edicoes_semanais,
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
  <div class="trow"><span class="pill mut">Independente do Notion · zera todo domingo</span></div>
</div>
""", unsafe_allow_html=True)
st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# ── Semana consultada + limite padrão/exceção ─────────────────
semana_ref = st.date_input("📅 Semana para acompanhar:", value=HOJE, format="DD/MM/YYYY",
                            help="Escolha qualquer dia; exibiremos a segunda a domingo correspondente.")
SEG, DOM = inicio_semana(semana_ref), inicio_semana(semana_ref) + timedelta(days=6)
st.caption(f"Exibindo **{SEG.strftime('%d/%m/%Y')} a {DOM.strftime('%d/%m/%Y')}**")

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
with st.expander("➕ Lançar gasto da semana", expanded=False):
    with st.form("form_gasto_semana", clear_on_submit=True):
        cg1, cg2, cg3 = st.columns([2, 2, 1])
        with cg1:
            g_desc = st.text_input("Descrição:", placeholder="ex: Padaria")
            g_data = st.date_input("Data:", value=semana_ref, max_value=HOJE,
                                   format="DD/MM/YYYY", help="Aceita lançamentos retroativos e os envia à semana correta.")
        with cg2:
            g_cat = st.selectbox("Categoria:", CATEGORIAS_DESPESA)
            g_pag = st.selectbox("Forma de pagamento:", ["💳 Débito", "📱 PIX", "💵 Dinheiro", "💳 Crédito"])
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
                    invalidar_cache("despesas")
                    mensagem_sucesso(f"Gasto lançado: {g_desc.strip()} · {formatar_moeda(g_valor)}")
                    st.rerun()
                elif n == 0:
                    mensagem_aviso("Esse gasto já parece estar lançado (mesma data, descrição e valor).")

st.divider()

# ── Carrega SÓ os gastos semanais desta semana ───────────────
df_d = ler_csv(DESPESAS_FILE)
df_sem = pd.DataFrame()
if not df_d.empty and "data" in df_d.columns:
    df_d["valor"]    = pd.to_numeric(df_d["valor"], errors="coerce").fillna(0)
    df_d["_dt"]      = pd.to_datetime(df_d["data"], errors="coerce")
    eh_semanal = df_d.get("fonte", pd.Series("", index=df_d.index)).astype(str) == FONTE_SEMANAL
    na_semana  = (df_d["_dt"].dt.date >= SEG) & (df_d["_dt"].dt.date <= DOM)
    df_sem = df_d[eh_semanal & na_semana].copy()

# ── Estimativa da fatura do cartão ────────────────────────────
st.markdown('<div class="p-title"><span class="tbar"></span> Fatura estimada do mês</div>',
            unsafe_allow_html=True)

df_bases = ler_csv("faturas_base")
if df_bases.empty:
    df_bases = pd.DataFrame(columns=["id", "ano", "mes", "cartao", "valor", "criado_em"])
for _col in ["ano", "mes", "valor"]:
    if _col in df_bases.columns:
        df_bases[_col] = pd.to_numeric(df_bases[_col], errors="coerce")

ano_atual_fat, mes_atual_fat = competencia_fatura(HOJE, 4)
_ref_atual = pd.Timestamp(year=ano_atual_fat, month=mes_atual_fat, day=1)
_refs = {_ref_atual + pd.DateOffset(months=n) for n in (-1, 0, 1)}
if not df_bases.empty:
    for _, _rb in df_bases.dropna(subset=["ano", "mes"]).iterrows():
        _refs.add(pd.Timestamp(year=int(_rb["ano"]), month=int(_rb["mes"]), day=1))
_refs = sorted(_refs)
_labels_ref = [r.strftime("%m/%Y") for r in _refs]
_default_ref = _labels_ref.index(_ref_atual.strftime("%m/%Y"))

col_card, col_ref = st.columns([2, 1])
with col_card:
    cartao_proj = st.selectbox("Cartão:", ["C6 BRU", "C6 PRI", "Nubank"], key="cartao_projecao")
with col_ref:
    ref_label = st.selectbox("Fatura de referência:", _labels_ref, index=_default_ref,
                             help="C6 fecha dia 4: compras do dia 5 em diante entram na fatura seguinte.")
ref_ts = _refs[_labels_ref.index(ref_label)]
ano_fatura, mes_fatura = int(ref_ts.year), int(ref_ts.month)
inicio_ciclo, fim_ciclo = intervalo_fatura(ano_fatura, mes_fatura, 4)
st.caption(f"Ciclo considerado: **{inicio_ciclo.strftime('%d/%m/%Y')} a {fim_ciclo.strftime('%d/%m/%Y')}**")

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

with st.expander("✍️ Definir valor inicial fixo", expanded=base_manual is None):
    st.caption(f"Este valor ficará vinculado a **{cartao_proj} · {ref_label}**.")
    novo_base = st.number_input(
        "Valor inicial da fatura (R$):", min_value=0.0,
        value=base_manual, step=None, placeholder="0,00", format="%.2f",
        key=f"base_fatura_{cartao_proj}_{ano_fatura}_{mes_fatura}",
    )
    if st.button("💾 Salvar valor inicial", type="primary", use_container_width=True,
                 key=f"salvar_base_{cartao_proj}_{ano_fatura}_{mes_fatura}"):
        if novo_base is None:
            mensagem_erro("Informe o valor inicial da fatura.")
        else:
            df_bases = df_bases[~_mask_base].copy() if len(_mask_base) else df_bases.copy()
            nova_base = pd.DataFrame([{
                "id": gerar_id(), "ano": ano_fatura, "mes": mes_fatura,
                "cartao": cartao_proj, "valor": round(float(novo_base), 2), "criado_em": agora(),
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
    sem_credito = df_d[(_fon == FONTE_SEMANAL) & _credito_cartao & _no_ciclo].copy()
else:
    sem_credito = pd.DataFrame()

if not sem_credito.empty:
    sem_credito["_semana_ciclo"] = semana_no_ciclo_fatura(sem_credito["data"], ano_fatura, mes_fatura, 4)
    por_semana = sem_credito.groupby("_semana_ciclo")["valor"].sum().to_dict()
else:
    por_semana = {}

gastos_credito = float(sum(por_semana.values()))
estimada = base_parcelada + gastos_credito
f1, f2, f3 = st.columns(3)
_origem_base = "valor fixado por você" if base_manual is not None else "parcelas identificadas"
f1.metric("Fatura começa em", formatar_moeda(base_parcelada), help=_origem_base)
f2.metric("Novos gastos no crédito", formatar_moeda(gastos_credito))
f3.metric("Fatura estimada", formatar_moeda(estimada))

if cartao_proj == "C6 BRU" and not sem_credito.empty:
    _sem_banco = sem_credito.get("banco", pd.Series("", index=sem_credito.index)).astype(str).str.strip().eq("").sum()
    if _sem_banco:
        st.caption(f"ℹ️ {_sem_banco} compra(s) antiga(s) no crédito sem cartão informado foram consideradas como C6 BRU.")

acumulado = base_parcelada
linhas_proj = []
_n_semanas_ciclo = ((fim_ciclo - inicio_ciclo).days // 7) + 1
for n_sem in range(1, _n_semanas_ciclo + 1):
    valor_sem = float(por_semana.get(n_sem, 0))
    acumulado += valor_sem
    ini_sem_fat = inicio_ciclo + timedelta(days=(n_sem - 1) * 7)
    fim_sem_fat = min(ini_sem_fat + timedelta(days=6), fim_ciclo)
    linhas_proj.append({"Semana": f"Semana {n_sem} · {ini_sem_fat.strftime('%d/%m')}–{fim_sem_fat.strftime('%d/%m')}",
                        "Novos gastos": valor_sem, "Fatura acumulada": acumulado})
st.dataframe(
    pd.DataFrame(linhas_proj), hide_index=True, use_container_width=True,
    column_config={
        "Novos gastos": st.column_config.NumberColumn(format="R$ %.2f"),
        "Fatura acumulada": st.column_config.NumberColumn(format="R$ %.2f"),
    },
)

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

st.divider()

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
if df_sem.empty:
    st.info("Nenhum gasto lançado nesta semana ainda. Use **➕ Lançar gasto da semana** acima.")
else:
    df_sem["_dia"] = df_sem["_dt"].dt.date
    for dia in sorted(df_sem["_dia"].dropna().unique()):
        sub = df_sem[df_sem["_dia"] == dia]
        nome = DIAS_NOME[dia.weekday()]
        with st.expander(f"**{nome}, {dia.strftime('%d/%m')}** — {formatar_moeda(sub['valor'].sum())}", expanded=True):
            for _, r in sub.iterrows():
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;align-items:center;"
                    f"padding:9px 14px;background:#0E1626;border:1px solid #1E2942;border-radius:10px;margin:4px 0'>"
                    f"<span style='color:#EAF1FF'>{esc(r['descricao'])}"
                    f"<span style='color:#5B6889;font-size:.8rem'> · {esc(r.get('categoria',''))} · {esc(r.get('forma_pagamento',''))}</span></span>"
                    f"<span style='color:#FF5C7A;font-weight:700' class='num'>{formatar_moeda(r['valor'])}</span></div>",
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
                salvar_parquet("despesas", full)
                invalidar_cache("despesas")
                n_del = len(ids_del)
                mensagem_sucesso(f"Alterações salvas!" + (f" {n_del} excluído(s)." if n_del else ""))
                st.rerun()

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
st.caption("Todos os gastos semanais, agrupados automaticamente pela data do lançamento.")
if df_d.empty:
    st.caption("Ainda não há lançamentos semanais.")
else:
    _hist = df_d[df_d.get("fonte", pd.Series("", index=df_d.index)).astype(str) == FONTE_SEMANAL].copy()
    _hist["_dt_hist"] = pd.to_datetime(_hist.get("data"), errors="coerce")
    _hist = _hist[_hist["_dt_hist"].notna()].copy()
    _hist["_inicio_semana"] = _hist["_dt_hist"].apply(inicio_semana)
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
            f"{_ini.strftime('%d/%m/%Y')}–{_fim.strftime('%d/%m/%Y')} · "
            f"{formatar_moeda(_tot_h)} · {len(_hs)} lançamento(s){_tag_lim}",
            expanded=(_ini == SEG),
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
