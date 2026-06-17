# ============================================================
#  0_📅_Agenda_Financeira.py
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st

from auth import exigir_login
exigir_login()
import pandas as pd
from datetime import date, timedelta

from config import DESPESAS_FILE, RECEITAS_FILE, MESES_PT, CONFIG_FILE
from utils import (
    configurar_pagina, cabecalho_pagina, inicializar_dados,
    ler_csv, salvar_parquet, formatar_moeda,
    mensagem_sucesso, mensagem_erro, ler_json, salvar_json,
)

configurar_pagina("Agenda Financeira", icone="📅")
inicializar_dados()
cabecalho_pagina(
    titulo="Agenda Financeira",
    subtitulo="Vencimentos, gastos semanais e saúde financeira",
    icone="📅"
)

HOJE          = date.today()
JANELA_ALERTA = 7

if st.button("🔄 Atualizar dados", help="Limpa o cache e recarrega do Google Sheets"):
    st.cache_data.clear()
    st.rerun()
STATUS_PENDENTES = {"A Pagar", "A Receber", "Agendado", "Pendente"}
BANCOS_PADRAO = [
    "Nubank", "Itaú", "Bradesco", "Santander",
    "Caixa", "Banco do Brasil", "Inter", "Sicoob", "C6 PRI", "C6 BRU",
]

# Carrega bancos cadastrados (se houver), senão usa o padrão
_df_bancos = ler_csv("bancos")
if not _df_bancos.empty and "nome" in _df_bancos.columns:
    BANCOS_PADRAO = _df_bancos["nome"].tolist()

# ── Semana atual (seg → dom) ──────────────────────────────────
SEG = HOJE - timedelta(days=HOJE.weekday())      # segunda-feira
DOM = SEG + timedelta(days=6)                    # domingo

# ── Carregar dados ────────────────────────────────────────────
df_d = ler_csv(DESPESAS_FILE)
df_r = ler_csv(RECEITAS_FILE)
cfg  = ler_json(str(CONFIG_FILE))

def pendentes(df, tipo):
    if df.empty or "status" not in df.columns:
        return pd.DataFrame()
    sub = df[df["status"].astype(str).isin(STATUS_PENDENTES)].copy()
    if sub.empty:
        return pd.DataFrame()
    sub["_tipo"]    = tipo
    sub["_data_dt"] = pd.to_datetime(sub["data"], errors="coerce")
    sub["valor"]    = pd.to_numeric(sub["valor"], errors="coerce").fillna(0)
    return sub

df_pend = pd.concat([
    pendentes(df_d, "💸 Despesa"),
    pendentes(df_r, "💰 Receita"),
], ignore_index=True)
if not df_pend.empty:
    df_pend = df_pend.sort_values("_data_dt")

# ════════════════════════════════════════════════════════════
# ALERTAS GLOBAIS (acima das abas)
# ════════════════════════════════════════════════════════════
if not df_pend.empty:
    vence_hoje  = df_pend[df_pend["_data_dt"].dt.date == HOJE]
    vence_breve = df_pend[
        (df_pend["_data_dt"].dt.date > HOJE) &
        (df_pend["_data_dt"].dt.date <= HOJE + timedelta(days=JANELA_ALERTA))
    ]
    if not vence_hoje.empty:
        nomes = ", ".join(vence_hoje["descricao"].astype(str).tolist())
        st.error(f"🚨 **VENCE HOJE:** {nomes} — {formatar_moeda(vence_hoje['valor'].sum())} — Já efetuou o pagamento?")
    if not vence_breve.empty:
        nomes = ", ".join(vence_breve["descricao"].astype(str).tolist())
        st.warning(f"🔔 **Vence nos próximos 7 dias:** {nomes} — {formatar_moeda(vence_breve['valor'].sum())}")
    if vence_hoje.empty and vence_breve.empty:
        st.success("✅ Nenhum vencimento nos próximos 7 dias!")

st.divider()

aba_agenda, aba_semana, aba_saude = st.tabs([
    "📋 Agenda de Vencimentos",
    "📆 Gastos Semanais",
    "🧠 Saúde Financeira",
])


# ════════════════════════════════════════════════════════════
# ABA 1 — AGENDA DE VENCIMENTOS
# ════════════════════════════════════════════════════════════
with aba_agenda:
    st.markdown(f"### 📊 Previsão — {MESES_PT[HOJE.month - 1]} {HOJE.year}")

    if not df_pend.empty:
        mes_atual  = df_pend[
            (df_pend["_data_dt"].dt.month == HOJE.month) &
            (df_pend["_data_dt"].dt.year  == HOJE.year)
        ]
        prev_desp  = mes_atual[mes_atual["_tipo"] == "💸 Despesa"]["valor"].sum()
        prev_rec   = mes_atual[mes_atual["_tipo"] == "💰 Receita"]["valor"].sum()
        saldo_prev = prev_rec - prev_desp
        cor_saldo  = "#00C953" if saldo_prev >= 0 else "#FF4D6D"

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""<div style='background:#1a0a0e;border-left:4px solid #FF4D6D;
                border-radius:8px;padding:14px 18px;'>
                <div style='color:#8BAFC9;font-size:0.8rem'>💸 Despesas Previstas</div>
                <div style='color:#FF4D6D;font-size:1.4rem;font-weight:700'>{formatar_moeda(prev_desp)}</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<div style='background:#0a1a10;border-left:4px solid #00C953;
                border-radius:8px;padding:14px 18px;'>
                <div style='color:#8BAFC9;font-size:0.8rem'>💰 Receitas Previstas</div>
                <div style='color:#00C953;font-size:1.4rem;font-weight:700'>{formatar_moeda(prev_rec)}</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""<div style='background:#0d1117;border-left:4px solid {cor_saldo};
                border-radius:8px;padding:14px 18px;'>
                <div style='color:#8BAFC9;font-size:0.8rem'>💵 Saldo Previsto</div>
                <div style='color:{cor_saldo};font-size:1.4rem;font-weight:700'>{formatar_moeda(saldo_prev)}</div>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("Nenhum lançamento pendente. Use **Lançamentos** para agendar.")

    st.divider()
    st.markdown("### 📋 Todos os Pendentes por Mês")

    if df_pend.empty:
        st.info("Nenhum lançamento pendente ou agendado.")
    else:
        df_pend["_mes_ano"] = df_pend["_data_dt"].dt.to_period("M")
        for periodo in sorted(df_pend["_mes_ano"].dropna().unique()):
            sub     = df_pend[df_pend["_mes_ano"] == periodo].copy()
            label   = f"{MESES_PT[periodo.month - 1]} {periodo.year}"
            total_d = sub[sub["_tipo"] == "💸 Despesa"]["valor"].sum()
            total_r = sub[sub["_tipo"] == "💰 Receita"]["valor"].sum()
            destaque = "🔵 " if (periodo.month == HOJE.month and periodo.year == HOJE.year) else ""

            with st.expander(
                f"{destaque}📅 **{label}** — 💸 {formatar_moeda(total_d)}  |  💰 {formatar_moeda(total_r)}",
                expanded=(periodo.month == HOJE.month and periodo.year == HOJE.year)
            ):
                for _, row in sub.iterrows():
                    data_fmt  = row["_data_dt"].strftime("%d/%m/%Y") if pd.notna(row["_data_dt"]) else "—"
                    dias_para = (row["_data_dt"].date() - HOJE).days if pd.notna(row["_data_dt"]) else None

                    if dias_para is not None and dias_para <= 0:
                        cor_b    = "#FF4D6D"
                        tag_dias = "🚨 HOJE" if dias_para == 0 else f"🚨 Vencido há {abs(dias_para)}d"
                    elif dias_para is not None and dias_para <= JANELA_ALERTA:
                        cor_b    = "#FFB300"
                        tag_dias = f"⏰ {dias_para}d"
                    else:
                        cor_b    = "#30363D"
                        tag_dias = f"{dias_para}d" if dias_para is not None else ""

                    col_info, col_btn = st.columns([5, 1])
                    with col_info:
                        st.markdown(
                            f"<div style='border-left:3px solid {cor_b};padding:8px 14px;"
                            f"background:#161B22;border-radius:6px;margin:4px 0'>"
                            f"<span style='color:#E6EDF3;font-weight:600'>{row['_tipo']} {row['descricao']}</span>"
                            f"<span style='color:#556878;font-size:0.8rem'> · {data_fmt} "
                            f"<span style='color:{cor_b}'>{tag_dias}</span>"
                            f" · {formatar_moeda(row['valor'])} · <i>{row.get('status','')}</i></span>"
                            f"</div>", unsafe_allow_html=True
                        )
                    with col_btn:
                        if st.button("✅ Baixa", key=f"baixa_{row['id']}", use_container_width=True):
                            st.session_state[f"form_baixa_{row['id']}"] = True

                    if st.session_state.get(f"form_baixa_{row['id']}"):
                        with st.form(key=f"form_{row['id']}"):
                            st.markdown(f"**Dar baixa: {row['descricao']}** ({formatar_moeda(row['valor'])})")
                            data_pgto = st.date_input("Data do pagamento:", value=HOJE)
                            banco_sel = st.selectbox("Banco:", BANCOS_PADRAO + ["➕ Outro banco..."])
                            banco_txt = st.text_input("Nome do banco:", key=f"btxt_{row['id']}") if banco_sel == "➕ Outro banco..." else ""
                            banco_final = banco_txt if banco_sel == "➕ Outro banco..." else banco_sel

                            ok, cancel = st.columns(2)
                            if ok.form_submit_button("✅ Confirmar", type="primary", use_container_width=True):
                                if not banco_final.strip():
                                    st.error("Informe o banco!")
                                else:
                                    is_desp = row["_tipo"] == "💸 Despesa"
                                    arq     = DESPESAS_FILE if is_desp else RECEITAS_FILE
                                    df_full = ler_csv(arq)
                                    idx     = df_full[df_full["id"] == row["id"]].index
                                    if len(idx) > 0:
                                        obs_ant = str(df_full.loc[idx[0], "observacao"] or "")
                                        df_full.loc[idx[0], "status"]     = "Pago" if is_desp else "Recebida"
                                        df_full.loc[idx[0], "data"]        = data_pgto.strftime("%Y-%m-%d")
                                        df_full.loc[idx[0], "observacao"]  = f"{obs_ant} | Pago em {data_pgto.strftime('%d/%m/%Y')} via {banco_final}".strip(" |")
                                        salvar_parquet("despesas" if is_desp else "receitas", df_full)
                                        st.session_state.pop(f"form_baixa_{row['id']}", None)
                                        mensagem_sucesso(f"Baixa registrada!")
                                        st.rerun()
                            if cancel.form_submit_button("❌ Cancelar", use_container_width=True):
                                st.session_state.pop(f"form_baixa_{row['id']}", None)
                                st.rerun()


# ════════════════════════════════════════════════════════════
# ABA 2 — GASTOS SEMANAIS
# ════════════════════════════════════════════════════════════
with aba_semana:
    st.markdown(f"### 📆 Semana atual: {SEG.strftime('%d/%m')} a {DOM.strftime('%d/%m/%Y')}")
    st.caption("Exibe automaticamente os gastos lançados de segunda a domingo. Zera toda semana à meia-noite de domingo.")

    # ── Limite semanal ────────────────────────────────────────
    limite_atual = float(cfg.get("limite_semanal", 0.0))
    col_lim, col_btn_lim = st.columns([3, 1])
    with col_lim:
        novo_limite = st.number_input(
            "💰 Limite de gastos da semana (R$):",
            min_value=0.0, step=50.0, value=limite_atual,
            help="Defina quanto quer gastar no máximo nesta semana."
        )
    with col_btn_lim:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("💾 Salvar limite", use_container_width=True):
            cfg["limite_semanal"] = novo_limite
            salvar_json(str(CONFIG_FILE), cfg)
            mensagem_sucesso("Limite salvo!")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # ── Filtrar despesas da semana atual ──────────────────────
    # Apenas gastos realizados (Pago) e NÃO agendados/fixos
    STATUS_REALIZADOS = {"Pago", "Pendente"}
    df_semana = pd.DataFrame()
    if not df_d.empty and "data" in df_d.columns:
        df_d["valor"]    = pd.to_numeric(df_d["valor"], errors="coerce").fillna(0)
        df_d["_data_dt"] = pd.to_datetime(df_d["data"], errors="coerce")
        mask_semana  = (df_d["_data_dt"].dt.date >= SEG) & (df_d["_data_dt"].dt.date <= DOM)
        mask_status  = df_d["status"].astype(str).isin(STATUS_REALIZADOS) if "status" in df_d.columns else True
        mask_fixos   = ~df_d["status"].astype(str).isin({"Agendado", "A Pagar"}) if "status" in df_d.columns else True
        # Exclui Notion — são despesas fixas/programadas, não gastos do dia a dia
        mask_fonte   = ~df_d["fonte"].astype(str).isin({"Notion"}) if "fonte" in df_d.columns else True
        df_semana    = df_d[mask_semana & mask_status & mask_fixos & mask_fonte].copy()

    total_semana = df_semana["valor"].sum() if not df_semana.empty else 0.0
    limite       = float(cfg.get("limite_semanal", 0.0))

    # ── KPIs ─────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""<div style='background:#1a0a0e;border-left:4px solid #FF4D6D;
            border-radius:8px;padding:14px 18px;'>
            <div style='color:#8BAFC9;font-size:0.8rem'>💸 Gasto na semana</div>
            <div style='color:#FF4D6D;font-size:1.4rem;font-weight:700'>{formatar_moeda(total_semana)}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        restante = max(limite - total_semana, 0) if limite > 0 else 0
        cor_rest = "#00C953" if restante > limite * 0.3 else "#FFB300" if restante > 0 else "#FF4D6D"
        label_rest = formatar_moeda(restante) if limite > 0 else "Sem limite definido"
        st.markdown(f"""<div style='background:#0d1117;border-left:4px solid {cor_rest};
            border-radius:8px;padding:14px 18px;'>
            <div style='color:#8BAFC9;font-size:0.8rem'>💵 Saldo do limite</div>
            <div style='color:{cor_rest};font-size:1.4rem;font-weight:700'>{label_rest}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        qtd = len(df_semana) if not df_semana.empty else 0
        st.markdown(f"""<div style='background:#0d1117;border-left:4px solid #4A9EFF;
            border-radius:8px;padding:14px 18px;'>
            <div style='color:#8BAFC9;font-size:0.8rem'>📊 Lançamentos</div>
            <div style='color:#4A9EFF;font-size:1.4rem;font-weight:700'>{qtd} gastos</div>
        </div>""", unsafe_allow_html=True)

    # ── Barra de progresso ────────────────────────────────────
    if limite > 0:
        st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
        pct = min(total_semana / limite, 1.0)
        cor_barra = "#00C953" if pct < 0.7 else "#FFB300" if pct < 1.0 else "#FF4D6D"

        if pct >= 1.0:
            st.error(f"🚨 **Limite estourado!** Você gastou {formatar_moeda(total_semana)} de {formatar_moeda(limite)} ({pct*100:.0f}%)")
        elif pct >= 0.8:
            st.warning(f"⚠️ **Atenção!** Você já usou {pct*100:.0f}% do limite semanal.")
        elif pct >= 0.5:
            st.info(f"📊 Você usou {pct*100:.0f}% do limite semanal.")
        else:
            st.success(f"✅ Dentro do limite — {pct*100:.0f}% utilizado.")

        st.progress(pct)

    st.divider()

    # ── Lista de gastos da semana ─────────────────────────────
    if df_semana.empty:
        st.info("Nenhum gasto lançado nesta semana ainda. Use a página **✍️ Lançamentos** para registrar.")
    else:
        # Agrupa por dia
        df_semana["_dia"] = df_semana["_data_dt"].dt.date
        dias_semana = sorted(df_semana["_dia"].unique())
        DIAS_NOME   = ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"]

        for dia in dias_semana:
            sub_dia   = df_semana[df_semana["_dia"] == dia]
            nome_dia  = DIAS_NOME[dia.weekday()]
            total_dia = sub_dia["valor"].sum()

            with st.expander(f"**{nome_dia}, {dia.strftime('%d/%m')}** — {formatar_moeda(total_dia)}", expanded=True):
                for _, row in sub_dia.iterrows():
                    cat = str(row.get("categoria", ""))
                    st.markdown(
                        f"<div style='border-left:3px solid #FF4D6D;padding:7px 14px;"
                        f"background:#161B22;border-radius:6px;margin:3px 0;"
                        f"display:flex;justify-content:space-between;align-items:center'>"
                        f"<span style='color:#E6EDF3'>{row['descricao']}"
                        f"<span style='color:#556878;font-size:0.78rem'> · {cat}</span></span>"
                        f"<span style='color:#FF4D6D;font-weight:700'>{formatar_moeda(row['valor'])}</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

        st.divider()
        # ── Ranking por categoria ──────────────────────────────
        st.markdown("**🏆 Ranking por categoria na semana**")
        por_cat = df_semana.groupby("categoria")["valor"].sum().sort_values(ascending=False).reset_index()
        por_cat["valor_fmt"] = por_cat["valor"].apply(formatar_moeda)
        por_cat.columns = ["Categoria", "Valor", "Total"]
        st.dataframe(por_cat[["Categoria", "Total"]], use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════
# ABA 3 — SAÚDE FINANCEIRA
# ════════════════════════════════════════════════════════════
with aba_saude:
    st.markdown("### 🧠 Análise de Saúde Financeira")
    st.caption("Análise gerada com base nos seus dados reais — atualiza a cada visita.")

    # ── Coletar dados para análise ────────────────────────────
    hoje = HOJE
    mes  = hoje.month
    ano  = hoje.year

    df_d_full = ler_csv(DESPESAS_FILE)
    df_r_full = ler_csv(RECEITAS_FILE)

    def soma_mes(df, m, a):
        if df.empty or "data" not in df.columns:
            return 0.0
        dt = pd.to_datetime(df["data"], errors="coerce")
        sub = df[(dt.dt.month == m) & (dt.dt.year == a)]
        return pd.to_numeric(sub["valor"], errors="coerce").sum()

    def soma_ultimos_meses(df, n=3):
        if df.empty:
            return 0.0
        vals = []
        for i in range(n):
            d = hoje.replace(day=1) - pd.DateOffset(months=i)
            vals.append(soma_mes(df, d.month, d.year))
        return sum(vals) / n if vals else 0.0

    desp_mes    = soma_mes(df_d_full, mes, ano)
    rec_mes     = soma_mes(df_r_full, mes, ano)
    saldo_mes   = rec_mes - desp_mes
    media_desp  = soma_ultimos_meses(df_d_full, 3)
    media_rec   = soma_ultimos_meses(df_r_full, 3)

    # Top categorias de gasto
    top_cats = pd.DataFrame()
    if not df_d_full.empty and "categoria" in df_d_full.columns:
        df_d_full["valor"] = pd.to_numeric(df_d_full["valor"], errors="coerce").fillna(0)
        dt = pd.to_datetime(df_d_full["data"], errors="coerce")
        df_3m = df_d_full[(dt >= pd.Timestamp(hoje.replace(day=1)) - pd.DateOffset(months=3))]
        if not df_3m.empty:
            top_cats = df_3m.groupby("categoria")["valor"].sum().sort_values(ascending=False).head(5)

    # Metas do config
    disney_meta    = float(cfg.get("disney_meta_valor", 50000))
    disney_atual   = float(cfg.get("disney_valor_atual", 0))
    disney_mensal  = float(cfg.get("disney_economia_mensal", 0))
    apos_meta      = float(cfg.get("aposentadoria_meta", 1000000))
    apos_atual     = float(cfg.get("apos_patrimonio_atual", 0))
    apos_aporte    = float(cfg.get("apos_aporte_mensal", 0))

    disney_falta   = max(disney_meta - disney_atual, 0)
    apos_falta     = max(apos_meta - apos_atual, 0)

    # ── Score de saúde (0-100) ────────────────────────────────
    score = 50
    insights = []
    alertas  = []
    dicas    = []

    # Saldo do mês
    if rec_mes > 0:
        tx_poupanca = saldo_mes / rec_mes
        if tx_poupanca >= 0.20:
            score += 20
            insights.append(f"✅ Você está poupando **{tx_poupanca*100:.0f}%** da sua renda este mês — excelente!")
        elif tx_poupanca >= 0.10:
            score += 10
            insights.append(f"👍 Você está poupando **{tx_poupanca*100:.0f}%** da renda. O ideal é chegar a 20%.")
        elif tx_poupanca >= 0:
            insights.append(f"⚠️ Poupança baixa este mês: **{tx_poupanca*100:.0f}%**. Tente reduzir gastos variáveis.")
            alertas.append("Poupança abaixo de 10% da renda.")
        else:
            score -= 20
            alertas.append(f"🚨 Saldo negativo de {formatar_moeda(abs(saldo_mes))} este mês!")

    # Tendência de gastos
    if media_desp > 0 and desp_mes > 0:
        if desp_mes > media_desp * 1.2:
            score -= 10
            alertas.append(f"📈 Gastos de {MESES_PT[mes-1]} ({formatar_moeda(desp_mes)}) estão **20% acima** da média dos últimos 3 meses ({formatar_moeda(media_desp)}).")
        elif desp_mes < media_desp * 0.9:
            score += 10
            insights.append(f"📉 Ótimo! Gastos deste mês abaixo da média dos últimos 3 meses.")

    # Meta Disney
    if disney_meta > 0:
        pct_disney = disney_atual / disney_meta * 100 if disney_meta > 0 else 0
        if disney_atual >= disney_meta:
            score += 15
            insights.append(f"🏰 **Meta Disney concluída!** Parabéns, família Periguinhos! 🎉")
        elif disney_mensal > 0:
            meses_disney = int(disney_falta / disney_mensal) if disney_mensal > 0 else 999
            insights.append(f"🏰 Projeto Disney: **{pct_disney:.0f}%** concluído. Faltam {formatar_moeda(disney_falta)} — em ~{meses_disney} meses no ritmo atual.")
            if disney_mensal < saldo_mes * 0.3 and saldo_mes > 0:
                dicas.append(f"💡 Você poderia aumentar o aporte do projeto Disney para {formatar_moeda(saldo_mes * 0.3)}/mês e chegar lá mais rápido.")
        else:
            alertas.append(f"🏰 Projeto Disney parado — configure um aporte mensal em **Projeto Disney**.")

    # Aposentadoria
    if apos_meta > 0:
        pct_apos = apos_atual / apos_meta * 100 if apos_meta > 0 else 0
        if apos_aporte > 0:
            insights.append(f"👴 Aposentadoria: **{pct_apos:.1f}%** da meta atingida ({formatar_moeda(apos_atual)} de {formatar_moeda(apos_meta)}).")
            if apos_aporte < media_rec * 0.10 and media_rec > 0:
                dicas.append(f"💡 Considere aumentar o aporte de aposentadoria. O recomendado é 10-15% da renda ({formatar_moeda(media_rec * 0.12)}/mês).")
        else:
            score -= 10
            alertas.append("👴 Nenhum aporte de aposentadoria configurado — quanto antes começar, melhor!")

    # Top gastos
    if not top_cats.empty:
        top1 = top_cats.index[0]
        val1 = top_cats.iloc[0]
        if media_rec > 0 and val1 / (media_rec * 3) > 0.25:
            dicas.append(f"💡 **{top1}** representa mais de 25% dos seus gastos nos últimos 3 meses ({formatar_moeda(val1)}). Vale revisar.")

    # Gastos semanais vs limite
    limite_sem = float(cfg.get("limite_semanal", 0))
    if limite_sem > 0 and total_semana > limite_sem:
        score -= 5
        alertas.append(f"📆 Limite semanal estourado: {formatar_moeda(total_semana)} vs {formatar_moeda(limite_sem)} definido.")

    score = max(0, min(100, score))

    # ── Exibir score ──────────────────────────────────────────
    if score >= 75:
        cor_score = "#00C953"
        label_score = "Ótima 🌟"
    elif score >= 50:
        cor_score = "#4A9EFF"
        label_score = "Boa 👍"
    elif score >= 30:
        cor_score = "#FFB300"
        label_score = "Atenção ⚠️"
    else:
        cor_score = "#FF4D6D"
        label_score = "Crítica 🚨"

    st.markdown(f"""
    <div style='background:#161B22;border-radius:12px;padding:24px;text-align:center;
    border:2px solid {cor_score};margin-bottom:1rem'>
        <div style='color:#8BAFC9;font-size:0.9rem;margin-bottom:4px'>Score de Saúde Financeira</div>
        <div style='color:{cor_score};font-size:3rem;font-weight:800'>{score}<span style='font-size:1.5rem'>/100</span></div>
        <div style='color:{cor_score};font-size:1.1rem;font-weight:600'>{label_score}</div>
    </div>
    """, unsafe_allow_html=True)

    st.progress(score / 100)

    # ── Painel de dados ───────────────────────────────────────
    st.divider()
    st.markdown("#### 📊 Resumo do Mês Atual")
    c1, c2, c3 = st.columns(3)
    c1.metric("💸 Despesas", formatar_moeda(desp_mes))
    c2.metric("💰 Receitas", formatar_moeda(rec_mes))
    c3.metric("💵 Saldo", formatar_moeda(saldo_mes), delta=f"Média 3m: {formatar_moeda(media_rec - media_desp)}")

    # ── Alertas ───────────────────────────────────────────────
    if alertas:
        st.divider()
        st.markdown("#### 🚨 Pontos de Atenção")
        for a in alertas:
            st.error(a)

    # ── Insights ─────────────────────────────────────────────
    if insights:
        st.divider()
        st.markdown("#### ✅ Pontos Positivos")
        for i in insights:
            st.success(i)

    # ── Dicas ─────────────────────────────────────────────────
    if dicas:
        st.divider()
        st.markdown("#### 💡 Recomendações")
        for d in dicas:
            st.info(d)

    # ── Top categorias ────────────────────────────────────────
    if not top_cats.empty:
        st.divider()
        st.markdown("#### 🏆 Maiores categorias de gasto (últimos 3 meses)")
        for cat, val in top_cats.items():
            pct = val / top_cats.sum() * 100
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;padding:6px 12px;"
                f"background:#161B22;border-radius:6px;margin:3px 0;border-left:3px solid #FF4D6D'>"
                f"<span style='color:#E6EDF3'>{cat}</span>"
                f"<span style='color:#FF4D6D;font-weight:600'>{formatar_moeda(val)} "
                f"<span style='color:#556878;font-size:0.8rem'>({pct:.0f}%)</span></span>"
                f"</div>", unsafe_allow_html=True
            )

    if not alertas and not dicas:
        st.balloons()
        st.success("🎉 Parabéns! Sua saúde financeira está em dia. Continue assim, família Periguinhos!")

