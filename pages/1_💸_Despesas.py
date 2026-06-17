# ============================================================
#  1_💸_Despesas.py — Dashboard de Despesas
# ============================================================

import re
import streamlit as st

from auth import exigir_login
exigir_login()
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from config import DESPESAS_FILE, MESES_PT, CARTOES_FILE
from utils import configurar_pagina, cabecalho_pagina, inicializar_dados, ler_csv, formatar_moeda, ler_json

configurar_pagina("Despesas", icone="💸")
inicializar_dados()
cabecalho_pagina(titulo="Despesas", subtitulo="Analise todos os seus gastos", icone="💸")
st.markdown("---")

DARK = dict(paper_bgcolor="#161B22", plot_bgcolor="#161B22",
            font=dict(color="#8BAFC9", family="Inter", size=12),
            xaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
            yaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
            margin=dict(l=10, r=10, t=40, b=10))

df = ler_csv(DESPESAS_FILE)
if df.empty:
    st.info("📭 Sem despesas ainda")
    st.stop()

df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
if "data_dt" not in df.columns:
    df["data_dt"] = pd.to_datetime(df["data"], errors="coerce")

# ── Abas ─────────────────────────────────────────────────────
aba_dash, aba_fatura = st.tabs(["📊 Dashboard", "💳 Fatura do Cartão"])

# ════════════════════════════════════════════════════════════
# ABA 1 — DASHBOARD
# ════════════════════════════════════════════════════════════
with aba_dash:
    # ── Filtros ──────────────────────────────────────────────
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        mes_f = st.selectbox("Mês:", [0]+list(range(1,13)), index=0,
                             format_func=lambda m: "Todos" if m==0 else MESES_PT[m-1])
    with col_f2:
        anos = sorted(df["data_dt"].dt.year.dropna().astype(int).unique().tolist(), reverse=True)
        ano_f = st.selectbox("Ano:", ["Todos"]+anos)
    with col_f3:
        categoria_f = st.selectbox("Categoria:", ["Todas"]+sorted(df["categoria"].dropna().unique().tolist()))
    with col_f4:
        fontes = ["Todas"] + sorted(df["fonte"].dropna().unique().tolist()) if "fonte" in df.columns else ["Todas"]
        fonte_f = st.selectbox("Fonte:", fontes)

    df_f = df.copy()
    if mes_f > 0:           df_f = df_f[df_f["data_dt"].dt.month == mes_f]
    if ano_f != "Todos":    df_f = df_f[df_f["data_dt"].dt.year == int(ano_f)]
    if categoria_f != "Todas": df_f = df_f[df_f["categoria"] == categoria_f]
    if fonte_f != "Todas" and "fonte" in df_f.columns:
        df_f = df_f[df_f["fonte"] == fonte_f]

    # ── KPIs ─────────────────────────────────────────────────
    total = df_f["valor"].sum()
    media = df_f["valor"].mean() if len(df_f) > 0 else 0
    maior = df_f["valor"].max() if len(df_f) > 0 else 0
    desc_maior = df_f.loc[df_f["valor"].idxmax(), "descricao"] if len(df_f) > 0 and maior > 0 else "—"

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="card-despesa">
            <div class="card-label">💸 Total Despesas</div>
            <div class="card-value-despesa">{formatar_moeda(total)}</div>
            <div class="card-sub">{len(df_f)} lançamentos</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="card-neutro">
            <div class="card-label">📊 Ticket Médio</div>
            <div class="card-value-neutro">{formatar_moeda(media)}</div>
            <div class="card-sub">por lançamento</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="card-despesa">
            <div class="card-label">📈 Maior Gasto</div>
            <div class="card-value-despesa">{formatar_moeda(maior)}</div>
            <div class="card-sub">{str(desc_maior)[:22]}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        n_cats = df_f["categoria"].nunique() if not df_f.empty else 0
        st.markdown(f"""<div class="card-neutro">
            <div class="card-label">🏷️ Categorias</div>
            <div class="card-value-neutro">{n_cats}</div>
            <div class="card-sub">no período</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
    st.divider()

    # ── Gráficos ─────────────────────────────────────────────
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("### Por Categoria")
        if not df_f.empty:
            df_cat = df_f.copy()
            df_cat["_cat_limpa"] = df_cat["categoria"].astype(str).str.strip()
            df_cat = df_cat[df_cat["_cat_limpa"].str.len() > 1]
            if not df_cat.empty:
                por_cat = df_cat.groupby("_cat_limpa")["valor"].sum().sort_values(ascending=False).head(8)
                fig = px.pie(values=por_cat.values, names=por_cat.index, hole=0.5,
                             color_discrete_sequence=["#FF4D6D","#FFB300","#9D4EDD","#FF6B35","#4A9EFF","#00C953","#F72585","#00D4FF","#FFEE58","#E040FB","#29B6F6","#FF8FA3"])
                fig.update_traces(textposition="inside", textinfo="percent",
                                  hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>")
                fig.update_layout(height=350,
                                  paper_bgcolor="#161B22", plot_bgcolor="#161B22",
                                  font=dict(color="#8BAFC9", family="Inter", size=11),
                                  legend=dict(bgcolor="#0D1B2A", bordercolor="#30363D",
                                              font=dict(color="#E6EDF3", size=11), x=1.02, y=0.5),
                                  margin=dict(l=0, r=140, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)

    with col_g2:
        st.markdown("### Top Categorias")
        if not df_f.empty:
            top_cat = df_f.groupby("categoria")["valor"].sum().sort_values(ascending=True).tail(8)
            nomes_b = [re.sub(r'[^\x00-\x7FÀ-ɏ\s]', '', str(n)).strip() for n in top_cat.index]
            fig2 = go.Figure(go.Bar(
                x=top_cat.values, y=nomes_b, orientation="h",
                marker=dict(color="#FF4D6D", opacity=0.85),
                hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>"
            ))
            fig2.update_layout(height=350, **DARK)
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ── Evolução mensal ───────────────────────────────────────
    st.markdown("### Evolução Mensal")
    if not df_f.empty:
        evo = df_f.groupby(df_f["data_dt"].dt.to_period("M"))["valor"].sum().reset_index()
        evo["data_dt"] = evo["data_dt"].astype(str)
        fig3 = go.Figure(go.Bar(
            x=evo["data_dt"], y=evo["valor"],
            marker_color="#FF4D6D", opacity=0.85,
            hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>"
        ))
        fig3.update_layout(height=250, **DARK, hovermode="x unified")
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()

    # ── Tabela completa ───────────────────────────────────────
    st.markdown("### Todos os Lançamentos")

    if not df_f.empty:
        df_sorted = df_f.sort_values("data_dt", ascending=False).copy()
        df_sorted["data"] = pd.to_datetime(df_sorted["data"]).dt.strftime("%d/%m/%Y")
        df_sorted["valor_fmt"] = df_sorted["valor"].apply(formatar_moeda)

        # Colunas resumidas (padrão)
        COLS_RESUMO = {
            "data":       "Data",
            "descricao":  "Descrição",
            "categoria":  "Categoria",
            "valor_fmt":  "Valor",
            "status":     "Status",
            "banco":      "Banco",
        }
        # Colunas extras (expandido)
        COLS_EXTRA = {
            "forma_pagamento": "Forma Pagamento",
            "fonte":           "Fonte",
            "observacao":      "Observação",
            "criado_em":       "Criado em",
        }

        cols_res = [c for c in COLS_RESUMO if c in df_sorted.columns]
        cols_ext = [c for c in COLS_EXTRA  if c in df_sorted.columns]

        ver_tudo = st.toggle("🔍 Ver todas as colunas", value=False)

        if ver_tudo:
            cols_show = cols_res + cols_ext
            nomes = [COLS_RESUMO.get(c, COLS_EXTRA.get(c, c)) for c in cols_show]
            df_exib = df_sorted[cols_show].copy()
            df_exib.columns = nomes
        else:
            df_exib = df_sorted[cols_res].copy()
            df_exib.columns = [COLS_RESUMO[c] for c in cols_res]

        st.caption("💡 Clique no cabeçalho para ordenar" + (" · mostrando todas as colunas" if ver_tudo else " · ative o toggle para ver mais"))
        st.dataframe(df_exib, use_container_width=True, hide_index=True, height=450)


# ════════════════════════════════════════════════════════════
# ABA 2 — FATURA DO CARTÃO
# ════════════════════════════════════════════════════════════
with aba_fatura:
    st.markdown("### 💳 Fatura do Cartão")
    st.caption("Visualize a fatura atual e futura de cada cartão, com base nos lançamentos já registrados.")

    # Carrega cartões cadastrados
    df_cartoes = ler_csv(CARTOES_FILE)
    cartoes_disponiveis = []
    if not df_cartoes.empty and "nome" in df_cartoes.columns:
        ativos = df_cartoes[df_cartoes.get("ativo", pd.Series(["sim"]*len(df_cartoes))).astype(str).str.lower().isin(["sim","true","1","s"])] if "ativo" in df_cartoes.columns else df_cartoes
        cartoes_disponiveis = ativos["nome"].tolist()

    # Fallback: detecta cartões a partir dos lançamentos
    if not cartoes_disponiveis and "cartao" in df.columns:
        cartoes_disponiveis = sorted(df["cartao"].dropna().unique().tolist())
        cartoes_disponiveis = [c for c in cartoes_disponiveis if str(c).strip() and str(c).strip() != "nan"]

    if not cartoes_disponiveis:
        st.info("Nenhum cartão cadastrado. Adicione em ✏️ Editar Dados → Cartões.")
        st.stop()

    cartao_sel = st.selectbox("Selecione o cartão:", cartoes_disponiveis, key="fatura_cartao_sel")

    # Dia de fechamento do cartão
    dia_fechamento = 10  # padrão
    if not df_cartoes.empty and "nome" in df_cartoes.columns:
        linha_cartao = df_cartoes[df_cartoes["nome"] == cartao_sel]
        if not linha_cartao.empty:
            for col_fech in ["dia_fechamento", "dia_vencimento"]:
                if col_fech in linha_cartao.columns:
                    try:
                        dia_fechamento = int(linha_cartao.iloc[0][col_fech])
                        break
                    except:
                        pass

    # Carrega config para pegar fechamentos manuais
    try:
        cfg = ler_json("configuracoes")
        fechamentos_cfg = cfg.get("fechamentos_cartoes", {})
        if cartao_sel in fechamentos_cfg:
            dia_fechamento = int(fechamentos_cfg[cartao_sel])
    except:
        pass

    st.caption(f"📅 Dia de fechamento: **{dia_fechamento}** (altere em ✏️ Editar Dados → Cartões)")

    # ── Filtra despesas do cartão selecionado ─────────────────
    mask_cartao = pd.Series([False] * len(df))
    if "cartao" in df.columns:
        mask_cartao = df["banco"].astype(str).str.strip().str.lower().eq(cartao_sel.strip().lower()) if "banco" in df.columns else pd.Series([False]*len(df))
    if "forma_pagamento" in df.columns:
        mask_cartao = mask_cartao | df["forma_pagamento"].astype(str).str.strip().str.lower().eq(cartao_sel.strip().lower())

    df_cartao = df[mask_cartao].copy()

    if df_cartao.empty:
        st.info(f"Nenhum lançamento encontrado para o cartão **{cartao_sel}**.")
        st.stop()

    df_cartao["_dt"] = pd.to_datetime(df_cartao["data"], errors="coerce")

    # ── Calcula mês de fatura de cada lançamento ──────────────
    def mes_fatura_de(dt, dia_fech):
        """Retorna (ano, mes) da fatura à qual a data pertence."""
        if pd.isna(dt):
            return (dt.year if not pd.isna(dt) else 0, 0)
        if dt.day > dia_fech:
            # Compra após fechamento → vai para fatura do próximo mês
            prox = dt + relativedelta(months=1)
            return (prox.year, prox.month)
        return (dt.year, dt.month)

    df_cartao["_fatura_ano"]  = df_cartao["_dt"].apply(lambda d: mes_fatura_de(d, dia_fechamento)[0])
    df_cartao["_fatura_mes"]  = df_cartao["_dt"].apply(lambda d: mes_fatura_de(d, dia_fechamento)[1])
    df_cartao["_fatura_label"] = df_cartao.apply(
        lambda r: f"{MESES_PT[int(r['_fatura_mes'])-1][:3]}/{int(r['_fatura_ano'])}"
        if r["_fatura_mes"] > 0 else "?", axis=1
    )

    # ── Agrupa por fatura ─────────────────────────────────────
    hoje = date.today()
    faturas = df_cartao.groupby(["_fatura_ano","_fatura_mes"]).agg(
        total=("valor","sum"),
        qtd=("valor","count"),
    ).reset_index().sort_values(["_fatura_ano","_fatura_mes"])

    # Separa passado/atual/futuro
    fatura_atual_ano = hoje.year if hoje.day <= dia_fechamento else (hoje + relativedelta(months=1)).year
    fatura_atual_mes = hoje.month if hoje.day <= dia_fechamento else (hoje + relativedelta(months=1)).month

    faturas["_label"]  = faturas.apply(
        lambda r: f"{MESES_PT[int(r['_fatura_mes'])-1]}/{int(r['_fatura_ano'])}", axis=1
    )
    faturas["_status"] = faturas.apply(
        lambda r: "atual" if (r["_fatura_ano"]==fatura_atual_ano and r["_fatura_mes"]==fatura_atual_mes)
        else ("futura" if (r["_fatura_ano"] > fatura_atual_ano or
              (r["_fatura_ano"]==fatura_atual_ano and r["_fatura_mes"] > fatura_atual_mes))
        else "fechada"),
        axis=1
    )

    # ── KPIs de fatura ────────────────────────────────────────
    fat_atual = faturas[faturas["_status"]=="atual"]
    fat_fut   = faturas[faturas["_status"]=="futura"]
    total_atual  = fat_atual["total"].sum() if not fat_atual.empty else 0
    total_futuro = fat_fut["total"].sum()   if not fat_fut.empty  else 0

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""<div class="card-despesa">
            <div class="card-label">💳 Fatura Atual</div>
            <div class="card-value-despesa">{formatar_moeda(total_atual)}</div>
            <div class="card-sub">{MESES_PT[fatura_atual_mes-1]}/{fatura_atual_ano}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="card-neutro">
            <div class="card-label">📅 Faturas Futuras</div>
            <div class="card-value-neutro">{formatar_moeda(total_futuro)}</div>
            <div class="card-sub">{len(fat_fut)} meses à frente</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        n_parcelas = int(fat_fut["qtd"].sum()) if not fat_fut.empty else 0
        st.markdown(f"""<div class="card-neutro">
            <div class="card-label">🔄 Parcelas Futuras</div>
            <div class="card-value-neutro">{n_parcelas}</div>
            <div class="card-sub">lançamentos programados</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Timeline de faturas ───────────────────────────────────
    st.markdown("#### 📆 Faturas por Mês")
    for _, fat in faturas.iterrows():
        ano_f  = int(fat["_fatura_ano"])
        mes_f  = int(fat["_fatura_mes"])
        label  = fat["_label"]
        status = fat["_status"]
        total_f = fat["total"]
        qtd_f   = int(fat["qtd"])

        # Detecta se esse mês foi importado via C6 Bank
        df_mes = df_cartao[(df_cartao["_fatura_ano"]==ano_f) & (df_cartao["_fatura_mes"]==mes_f)]
        tem_c6 = "fonte" in df_mes.columns and df_mes["fonte"].astype(str).str.contains("C6", case=False).any()
        tem_manual = "fonte" in df_mes.columns and df_mes["fonte"].astype(str).str.contains("Manual", case=False).any()

        # Ícone e cor por status
        if status == "atual":
            icone = "🟡"
            badge = "ABERTA"
            cor   = "#FFB300"
        elif status == "futura":
            icone = "🔵"
            badge = "FUTURA"
            cor   = "#4A9EFF"
        else:
            icone = "✅"
            badge = "FECHADA"
            cor   = "#00C953"

        fonte_badge = ""
        if tem_c6:
            fonte_badge = " · <span style='color:#00C953;font-size:0.8rem'>✅ Importada do C6</span>"
        elif tem_manual:
            fonte_badge = " · <span style='color:#FFB300;font-size:0.8rem'>✏️ Lançada manualmente</span>"

        with st.expander(
            f"{icone} {label} — {formatar_moeda(total_f)} ({qtd_f} itens) [{badge}]",
            expanded=(status == "atual")
        ):
            st.markdown(fonte_badge, unsafe_allow_html=True)

            cols_exib = ["data","descricao","categoria","valor","status"]
            if "fonte" in df_mes.columns: cols_exib.append("fonte")
            df_exib = df_mes.sort_values("_dt", ascending=True)[cols_exib].copy()
            df_exib["data"]  = pd.to_datetime(df_exib["data"]).dt.strftime("%d/%m/%Y")
            df_exib["valor"] = df_exib["valor"].apply(formatar_moeda)
            nomes = ["Data","Descrição","Categoria","Valor","Status"]
            if "fonte" in cols_exib: nomes.append("Fonte")
            df_exib.columns = nomes
            st.dataframe(df_exib, use_container_width=True, hide_index=True)

            st.markdown(f"**Total: {formatar_moeda(total_f)}**")
            if not tem_c6 and status == "fechada":
                st.warning("⚠️ Esta fatura não foi importada do C6. Os valores são baseados em lançamentos manuais.")
