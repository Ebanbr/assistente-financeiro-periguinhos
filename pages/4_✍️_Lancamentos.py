# ============================================================
#  4_✍️_Lancamentos.py — Centro de Lançamentos
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st

from auth import exigir_login
exigir_login()
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

from config import DESPESAS_FILE, RECEITAS_FILE, MESES_PT
from utils import (
    configurar_pagina, cabecalho_pagina, inicializar_dados,
    ler_csv, mensagem_sucesso, mensagem_erro,
    formatar_moeda, gerar_id, agora,
    salvar_despesas_novas, salvar_receitas_novas,
    listar_cartoes_ativos, listar_categorias,
)
from activity_log import registrar as log_atividade

configurar_pagina("Lançamentos", icone="✍️")
inicializar_dados()

cabecalho_pagina(
    titulo="Lançamentos",
    subtitulo="Registre despesas e receitas aqui",
    icone="✍️"
)

st.markdown("---")

# ── FORMULÁRIO ───────────────────────────────────────────────
st.markdown("## ➕ Novo Lançamento")

col_tipo, col_data = st.columns([1, 1])

with col_tipo:
    tipo = st.radio("Tipo:", ["💸 Despesa", "💰 Receita"], horizontal=True)

with col_data:
    data = st.date_input("Data:", value=date.today())

st.markdown("---")

# ── DESPESA ──────────────────────────────────────────────────
if "💸" in tipo:
    st.markdown("### 💸 Nova Despesa")

    col1, col2 = st.columns(2)

    with col1:
        desc  = st.text_input("Descrição:")
        valor = st.number_input("Valor (R$):", min_value=0.0, step=0.01)

    with col2:
        cats_d = listar_categorias("despesa")
        cat_sel = st.selectbox("Categoria:", ["➕ Nova categoria..."] + cats_d)
        if cat_sel == "➕ Nova categoria...":
            cat = st.text_input("Nome da nova categoria:", placeholder="Ex: 🎮 Games")
        else:
            cat = cat_sel

    col3, col4 = st.columns(2)

    cartoes = listar_cartoes_ativos()
    opcoes_pagamento = ["💵 Dinheiro", "📱 PIX", "💳 Débito", "🏦 Transferência"] + (cartoes if cartoes else [])

    with col3:
        forma = st.selectbox("Forma de pagamento:", opcoes_pagamento)

    with col4:
        if forma in cartoes:
            cartao = forma
            st.info("💳 Compra no cartão — registrada como **Pago** (gasto realizado).")
        else:
            cartao = ""

    # Cartão de crédito = gasto já realizado → Pago automaticamente
    # Boleto/outros → padrão A Pagar
    if forma in cartoes:
        status = "Pago"
        st.caption("✅ Status definido automaticamente como **Pago** por ser compra no cartão.")
    else:
        status = st.selectbox("Status:", ["A Pagar", "Agendado", "Pendente", "Pago"])
    obs    = st.text_area("Obs (opcional):", height=50)

    # ── Recorrência ───────────────────────────────────────────
    st.markdown("---")
    recorrente = st.checkbox("🔁 Lançamento recorrente?")
    meses_rep  = 1
    if recorrente:
        meses_rep = st.number_input(
            "Repetir por quantos meses (incluindo este)?",
            min_value=2, max_value=60, value=3, step=1
        )
        st.caption(f"Serão criados {meses_rep} lançamentos — de {data.strftime('%m/%Y')} até "
                   f"{(data + relativedelta(months=meses_rep-1)).strftime('%m/%Y')}")

    if st.button("✅ Salvar Despesa", type="primary", use_container_width=True):
        if not desc or valor == 0:
            mensagem_erro("Preencha descrição e valor!")
        elif not cat or not cat.strip():
            mensagem_erro("Preencha a categoria!")
        else:
            linhas = []
            for i in range(meses_rep):
                data_i = data + relativedelta(months=i)
                parcela_obs = f" ({i+1}/{meses_rep})" if recorrente else ""
                linhas.append({
                    "id":              gerar_id(),
                    "data":            data_i.strftime("%Y-%m-%d"),
                    "descricao":       desc,
                    "categoria":       cat.strip(),
                    "valor":           round(valor, 2),
                    "forma_pagamento": forma,
                    "cartao":          cartao,
                    "status":          status,
                    "observacao":      obs + parcela_obs,
                    "fonte":           "Manual",
                    "criado_em":       agora(),
                })
            salvos = salvar_despesas_novas(pd.DataFrame(linhas))
            if salvos > 0:
                if recorrente:
                    log_atividade("lançou despesa recorrente", f"{desc} · {formatar_moeda(valor)} · {salvos}x")
                    mensagem_sucesso(f"{salvos} despesa(s) recorrente(s) de {formatar_moeda(valor)} registradas!")
                else:
                    log_atividade("lançou despesa", f"{desc} · {formatar_moeda(valor)}")
                    mensagem_sucesso(f"Despesa de {formatar_moeda(valor)} registrada!")
                st.rerun()

# ── RECEITA ──────────────────────────────────────────────────
else:
    st.markdown("### 💰 Nova Receita")

    col1, col2 = st.columns(2)

    with col1:
        desc  = st.text_input("Descrição:")
        valor = st.number_input("Valor (R$):", min_value=0.0, step=0.01)

    with col2:
        cats_r = listar_categorias("receita")
        cat_sel = st.selectbox("Categoria:", ["➕ Nova categoria..."] + cats_r)
        if cat_sel == "➕ Nova categoria...":
            cat = st.text_input("Nome da nova categoria:", placeholder="Ex: 💡 Consultoria")
        else:
            cat = cat_sel

    forma_rec = st.selectbox("Forma de recebimento:", ["🏦 Transferência", "📱 PIX", "💵 Dinheiro", "💳 Crédito"])
    status    = st.selectbox("Status:", ["A Receber", "Agendado", "Pendente", "Recebida"])
    obs       = st.text_area("Obs (opcional):", height=50)

    # ── Recorrência ───────────────────────────────────────────
    st.markdown("---")
    recorrente = st.checkbox("🔁 Lançamento recorrente?")
    meses_rep  = 1
    if recorrente:
        meses_rep = st.number_input(
            "Repetir por quantos meses (incluindo este)?",
            min_value=2, max_value=60, value=3, step=1
        )
        st.caption(f"Serão criados {meses_rep} lançamentos — de {data.strftime('%m/%Y')} até "
                   f"{(data + relativedelta(months=meses_rep-1)).strftime('%m/%Y')}")

    if st.button("✅ Salvar Receita", type="primary", use_container_width=True):
        if not desc or valor == 0:
            mensagem_erro("Preencha descrição e valor!")
        elif not cat or not cat.strip():
            mensagem_erro("Preencha a categoria!")
        else:
            linhas = []
            for i in range(meses_rep):
                data_i = data + relativedelta(months=i)
                parcela_obs = f" ({i+1}/{meses_rep})" if recorrente else ""
                linhas.append({
                    "id":               gerar_id(),
                    "data":             data_i.strftime("%Y-%m-%d"),
                    "descricao":        desc,
                    "categoria":        cat.strip(),
                    "valor":            round(valor, 2),
                    "forma_recebimento": forma_rec,
                    "status":           status,
                    "observacao":       obs + parcela_obs,
                    "fonte":            "Manual",
                    "criado_em":        agora(),
                })
            salvos = salvar_receitas_novas(pd.DataFrame(linhas))
            if salvos > 0:
                if recorrente:
                    log_atividade("lançou receita recorrente", f"{desc} · {formatar_moeda(valor)} · {salvos}x")
                    mensagem_sucesso(f"{salvos} receita(s) recorrente(s) de {formatar_moeda(valor)} registradas!")
                else:
                    log_atividade("lançou receita", f"{desc} · {formatar_moeda(valor)}")
                    mensagem_sucesso(f"Receita de {formatar_moeda(valor)} registrada!")
                st.rerun()

st.markdown("---")

# ── LISTA CONSOLIDADA ────────────────────────────────────────
st.markdown("## 📋 Todos os Lançamentos")

df_d = ler_csv(DESPESAS_FILE)
df_r = ler_csv(RECEITAS_FILE)

col_f1, col_f2, col_f3, col_f4 = st.columns(4)

with col_f1:
    mes_f = st.selectbox("Mês:", [0] + list(range(1, 13)), index=0,
                         format_func=lambda m: "Todos" if m == 0 else MESES_PT[m-1])
with col_f2:
    ano_f = st.selectbox("Ano:", ["Todos"] + list(range(2023, date.today().year + 2)))
with col_f3:
    tipo_f = st.selectbox("Tipo:", ["Todos", "💸 Despesas", "💰 Receitas"])
with col_f4:
    status_f = st.selectbox("Status:", ["Todos", "Pago", "Recebida", "A Pagar", "A Receber", "Agendado", "Pendente"])

def filtrar(df):
    if df.empty or "data_dt" not in df.columns:
        return df
    df_f = df.copy()
    if mes_f > 0:        df_f = df_f[df_f["data_dt"].dt.month == mes_f]
    if ano_f != "Todos": df_f = df_f[df_f["data_dt"].dt.year == int(ano_f)]
    if status_f != "Todos" and "status" in df_f.columns:
        df_f = df_f[df_f["status"] == status_f]
    return df_f

if tipo_f == "Todos":
    df_final = pd.concat([filtrar(df_d), filtrar(df_r)], ignore_index=True)
elif tipo_f == "💸 Despesas":
    df_final = filtrar(df_d)
else:
    df_final = filtrar(df_r)

if not df_final.empty:
    df_final = df_final.sort_values("data_dt", ascending=False)

total_d = filtrar(df_d)["valor"].sum() if not filtrar(df_d).empty and "valor" in filtrar(df_d).columns else 0
total_r = filtrar(df_r)["valor"].sum() if not filtrar(df_r).empty and "valor" in filtrar(df_r).columns else 0

col_r1, col_r2, col_r3, col_r4 = st.columns(4)
with col_r1: st.metric("📊 Registros", len(df_final))
with col_r2: st.metric("💸 Despesas",  formatar_moeda(total_d))
with col_r3: st.metric("💰 Receitas",  formatar_moeda(total_r))
with col_r4: st.metric("💵 Saldo",     formatar_moeda(total_r - total_d))

st.divider()

if not df_final.empty:
    cols = ["data", "descricao", "categoria", "valor", "status"]
    if "fonte" in df_final.columns:
        cols.append("fonte")
    df_exib = df_final[cols].copy()
    df_exib["data"]  = pd.to_datetime(df_exib["data"]).dt.strftime("%d/%m/%Y")
    df_exib["valor"] = df_exib["valor"].apply(formatar_moeda)
    nomes = ["Data", "Descrição", "Categoria", "Valor", "Status"]
    if "fonte" in cols:
        nomes.append("Fonte")
    df_exib.columns = nomes
    st.dataframe(df_exib, use_container_width=True, hide_index=True)
else:
    st.info("Nenhum lançamento encontrado")

