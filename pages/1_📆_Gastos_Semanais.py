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

configurar_pagina("Gastos Semanais", icone="📆")
inicializar_dados()

FONTE_SEMANAL = "Semanal"   # tag que mantém esses gastos separados do macro do Notion
ICE, AURORA, DESPESA, WARN = "#4FE3FF", "#39E0A6", "#FF5C7A", "#FFC24B"

HOJE = date.today()
SEG  = HOJE - timedelta(days=HOJE.weekday())     # segunda
DOM  = SEG + timedelta(days=6)                    # domingo
DIAS_NOME = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

cfg = ler_json(str(CONFIG_FILE))

# ── Header ───────────────────────────────────────────────────
st.markdown(f"""
<div class="thesis">
  <div class="eyebrow">Controle da semana · {SEG.strftime('%d/%m')} a {DOM.strftime('%d/%m')}</div>
  <div class="big" style="font-size:clamp(26px,4vw,40px)">Onde o dinheiro <em class="pos">está indo</em> esta semana</div>
  <div class="trow"><span class="pill mut">Independente do Notion · zera todo domingo</span></div>
</div>
""", unsafe_allow_html=True)
st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# ── Limite da semana ─────────────────────────────────────────
limite = float(cfg.get("limite_semanal", 0.0) or 0.0)
col_lim, col_btn = st.columns([3, 1])
with col_lim:
    novo_limite = st.number_input("💰 Limite de gastos da semana (R$):", min_value=0.0, step=50.0,
                                  value=limite, help="Quanto você quer gastar no máximo nesta semana.")
with col_btn:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    if st.button("💾 Salvar limite", use_container_width=True):
        cfg["limite_semanal"] = novo_limite
        salvar_json(str(CONFIG_FILE), cfg)
        mensagem_sucesso("Limite salvo!")
        st.rerun()

# ── Lançar gasto ─────────────────────────────────────────────
with st.expander("➕ Lançar gasto da semana", expanded=False):
    with st.form("form_gasto_semana", clear_on_submit=True):
        cg1, cg2, cg3 = st.columns([2, 2, 1])
        with cg1:
            g_desc = st.text_input("Descrição:", placeholder="ex: Padaria")
            g_data = st.date_input("Data:", value=HOJE, min_value=SEG, max_value=DOM,
                                   format="DD/MM/YYYY", help="Só aceita datas desta semana.")
        with cg2:
            g_cat = st.selectbox("Categoria:", listar_categorias("despesa"))
            g_pag = st.selectbox("Forma de pagamento:", ["💳 Débito", "📱 PIX", "💵 Dinheiro", "💳 Crédito"])
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
                    "banco": "", "status": "Pago", "observacao": "",
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
        df_ed = df_sem[["data", "descricao", "categoria", "valor", "forma_pagamento", "id"]].copy()
        df_ed["data"] = pd.to_datetime(df_ed["data"], errors="coerce").dt.date
        df_ed["id"]   = df_ed["id"].astype(str)
        df_ed.insert(0, "🗑️", False)
        editado = st.data_editor(
            df_ed,
            column_config={
                "🗑️":              st.column_config.CheckboxColumn("🗑️", width="small"),
                "data":            st.column_config.DateColumn("Data", format="DD/MM/YYYY", width="small"),
                "descricao":       st.column_config.TextColumn("Descrição", width="large"),
                "categoria":       st.column_config.SelectboxColumn("Categoria", options=listar_categorias("despesa")),
                "valor":           st.column_config.NumberColumn("Valor", format="R$ %.2f", min_value=0.0),
                "forma_pagamento": st.column_config.SelectboxColumn("Forma", options=["💳 Débito", "📱 PIX", "💵 Dinheiro", "💳 Crédito"]),
                "id":              st.column_config.TextColumn("ID", disabled=True, width="small"),
            },
            column_order=["🗑️", "data", "descricao", "categoria", "valor", "forma_pagamento"],
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
