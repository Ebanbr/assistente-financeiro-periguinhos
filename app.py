# ============================================================
#  app.py — Dashboard Principal (tema Ártico ❄️)
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta

from config import APP_NOME, APP_EMOJI, DESPESAS_FILE, RECEITAS_FILE, MESES_PT, CONFIG_FILE, MAPEAMENTOS_FILE
from utils import (esc, ler_csv, salvar_parquet, formatar_moeda, ler_json, gerar_id,
                   listar_categorias, invalidar_cache, mensagem_sucesso, mensagem_erro)
from auth import login_page, usuario_logado, logout
from ui_theme import aplicar_tema, paleta_graficos, tema_atual

# ── Login ─────────────────────────────────────────────────────
if not st.session_state.get("logado"):
    login_page()
    st.stop()

st.set_page_config(page_title=f"{APP_EMOJI} {APP_NOME}", page_icon=APP_EMOJI,
                   layout="wide", initial_sidebar_state="collapsed")

aplicar_tema()

# Paleta Ártico p/ gráficos
_cores = paleta_graficos(tema_atual())
ICE, AURORA, RECEITA, DESPESA, WARN = (
    _cores["destaque"], _cores["saldo"], _cores["receita"], _cores["despesa"], "#FFC24B"
)
ARCTIC = dict(
    paper_bgcolor=_cores["fundo"], plot_bgcolor=_cores["fundo"],
    font=dict(color=_cores["texto"], family="Inter", size=12),
    xaxis=dict(gridcolor=_cores["grade"], linecolor=_cores["grade"], zeroline=False,
               tickfont=dict(color=_cores["texto"])),
    yaxis=dict(gridcolor=_cores["grade"], linecolor=_cores["grade"], zeroline=False,
               tickfont=dict(color=_cores["texto"])),
    margin=dict(l=6, r=6, t=10, b=6),
)

# ── Sidebar ──────────────────────────────────────────────────
st.sidebar.markdown(f"## {APP_EMOJI} {APP_NOME}")
st.sidebar.markdown("<small style='color:var(--txt-dim)'>Painel financeiro da família</small>", unsafe_allow_html=True)
_u = usuario_logado()
_emoji_u = "🧔" if _u == "BOo" else "👩"
st.sidebar.markdown(f"<small style='color:var(--ice)'>{_emoji_u} Olá, <b>{esc(_u)}</b>!</small>", unsafe_allow_html=True)
if st.sidebar.button("🚪 Sair", use_container_width=True):
    logout()
st.sidebar.divider()

# ── Dados ────────────────────────────────────────────────────
df_d_all = ler_csv(DESPESAS_FILE)
df_r = ler_csv(RECEITAS_FILE)
for _df in (df_d_all, df_r):
    if not _df.empty and "valor" in _df.columns:
        _df["valor"] = pd.to_numeric(_df["valor"], errors="coerce").fillna(0)

# Gastos semanais (fonte "Semanal") são uma ferramenta à parte — NÃO entram no
# macro do dashboard (que reflete o Notion + faturas), só no tile "Esta semana".
if not df_d_all.empty and "fonte" in df_d_all.columns:
    _mask_sem = df_d_all["fonte"].astype(str) == "Semanal"
    df_semanal = df_d_all[_mask_sem].copy()
    df_d = df_d_all[~_mask_sem].copy()
else:
    df_semanal = pd.DataFrame()
    df_d = df_d_all

# ── Filtro de período ────────────────────────────────────────
st.sidebar.markdown("### 🎛️ Período")
anos = []
if not df_d.empty and "data_dt" in df_d.columns:
    anos += df_d["data_dt"].dt.year.dropna().astype(int).tolist()
if not df_r.empty and "data_dt" in df_r.columns:
    anos += df_r["data_dt"].dt.year.dropna().astype(int).tolist()
anos = sorted(set(anos), reverse=True) or [date.today().year]
ano_sel = st.sidebar.selectbox("Ano:", ["Todos"] + anos)
mes_sel = st.sidebar.selectbox("Mês:", [0] + list(range(1, 13)),
                               format_func=lambda m: "Todos" if m == 0 else MESES_PT[m-1])

def filtrar(df):
    if df.empty or "data_dt" not in df.columns:
        return df
    d = df.copy()
    if ano_sel != "Todos": d = d[d["data_dt"].dt.year == int(ano_sel)]
    if mes_sel > 0:        d = d[d["data_dt"].dt.month == mes_sel]
    return d

df_df, df_rf = filtrar(df_d), filtrar(df_r)
total_desp = df_df["valor"].sum() if not df_df.empty else 0
total_rec  = df_rf["valor"].sum() if not df_rf.empty else 0
saldo = total_rec - total_desp
poup = (saldo / total_rec) if total_rec > 0 else 0

periodo_label = (f"{MESES_PT[mes_sel-1]} {ano_sel}" if mes_sel > 0 and ano_sel != "Todos"
                 else (str(ano_sel) if ano_sel != "Todos" else "todo o período"))

# ── Séries mensais para o fluxo ───────────────────────────────
def serie_mensal(df):
    if df.empty or "data_dt" not in df.columns:
        return pd.Series(dtype=float)
    d = df.copy()
    if ano_sel != "Todos": d = d[d["data_dt"].dt.year == int(ano_sel)]
    return d.groupby(d["data_dt"].dt.to_period("M"))["valor"].sum().sort_index()

sr, sd = serie_mensal(df_r), serie_mensal(df_d)
idx = sorted(set(sr.index).union(sd.index))
fluxo = pd.DataFrame(index=idx)
fluxo["receitas"] = sr.reindex(idx).fillna(0) if idx else []
fluxo["despesas"] = sd.reindex(idx).fillna(0) if idx else []
fluxo["saldo"] = (fluxo["receitas"] - fluxo["despesas"]) if idx else []
labels_fluxo = [f"{MESES_PT[p.month-1][:3]}/{str(p.year)[2:]}" for p in idx]

# ══════════════════════════════════════════════════════════════
# RESUMO — mesma informação, linguagem Pulse/Caderno conforme o tema
# ══════════════════════════════════════════════════════════════
_resultado_label = "Disponível após as despesas" if saldo >= 0 else "Déficit no período"
_resultado_classe = "positivo" if saldo >= 0 else "negativo"
st.markdown(f"""
<div class="dashboard-intro">
  <div class="dashboard-brand">🐧 PERIGUINHOS <span>· {esc(periodo_label)}</span></div>
  <h1>O essencial, de primeira.</h1>
  <p>O mês inteiro à vista. Período e aparência ficam no menu lateral.</p>
</div>
<section class="dashboard-summary" aria-label="Resumo financeiro do período">
  <div class="dashboard-balance {_resultado_classe}">
    <div class="dashboard-eyebrow">{_resultado_label}</div>
    <div class="dashboard-big num">{formatar_moeda(abs(saldo))}</div>
    <div class="dashboard-context">Receitas menos despesas · {poup*100:.1f}% da renda</div>
  </div>
  <div class="dashboard-figures">
    <div><span>Receitas</span><strong class="num receita">{formatar_moeda(total_rec)}</strong></div>
    <div><span>Despesas</span><strong class="num despesa">{formatar_moeda(total_desp)}</strong></div>
  </div>
</section>
""", unsafe_allow_html=True)

# Todos os números acima conservam um caminho para os lançamentos de origem.
def _tabela_detalhe(df, cols=("data", "descricao", "categoria", "valor")):
    if df.empty:
        st.caption("Sem lançamentos.")
        return
    t = df.sort_values("valor", ascending=False)[list(cols)].head(60).copy()
    t["data"] = pd.to_datetime(t["data"], errors="coerce").dt.strftime("%d/%m/%Y")
    t["valor"] = t["valor"].apply(formatar_moeda)
    t.columns = ["Data", "Descrição", "Categoria", "Valor"]
    st.dataframe(t, use_container_width=True, hide_index=True, height=300)
    if len(df) > len(t):
        st.caption(f"Exibindo {len(t)} dos {len(df)} lançamentos. Use as páginas de detalhamento para consultar todos.")

col_rec, col_desp, col_saldo = st.columns(3)
with col_rec, st.popover(f"Ver {len(df_rf)} receitas", use_container_width=True):
    _tabela_detalhe(df_rf)
with col_desp, st.popover(f"Ver {len(df_df)} despesas", use_container_width=True):
    _tabela_detalhe(df_df)
with col_saldo, st.popover("Entender o saldo", use_container_width=True):
    st.caption(f"{formatar_moeda(total_rec)} em receitas − {formatar_moeda(total_desp)} em despesas = {formatar_moeda(saldo)}.")
    st.caption("Gastos semanais provisórios não entram neste resultado macro.")

st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# FLUXO MENSAL  |  ONDE FOI O DINHEIRO
# ══════════════════════════════════════════════════════════════
col_a, col_b = st.columns([1.55, 1])

with col_a:
    st.markdown('<div class="p-title"><span class="tbar"></span> Fluxo mensal</div>', unsafe_allow_html=True)
    if idx:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=labels_fluxo, y=fluxo["receitas"], name="Receitas",
            mode="lines+markers", marker=dict(size=8),
            line=dict(color=RECEITA, width=2.4), fill="tozeroy", fillcolor=_cores["receita_fill"],
            hovertemplate="<b>%{x}</b><br>Receitas: R$ %{y:,.2f}<extra></extra>"))
        fig.add_trace(go.Scatter(
            x=labels_fluxo, y=fluxo["despesas"], name="Despesas",
            mode="lines+markers", marker=dict(size=8),
            line=dict(color=DESPESA, width=2.4), fill="tozeroy", fillcolor=_cores["despesa_fill"],
            hovertemplate="<b>%{x}</b><br>Despesas: R$ %{y:,.2f}<extra></extra>"))
        fig.update_layout(**ARCTIC, height=300, hovermode="x unified",
                          legend=dict(orientation="h", x=0, y=1.14, bgcolor="rgba(0,0,0,0)",
                                      font=dict(color=_cores["texto"], size=12)))
        escolha_fluxo = st.plotly_chart(
            fig, use_container_width=True, key="fluxo_mensal_interativo", theme=None,
            on_select="rerun", selection_mode="points",
        )
        pontos_fluxo = escolha_fluxo.selection.points if escolha_fluxo else []
        if pontos_fluxo:
            ponto = pontos_fluxo[0]
            pos = ponto.get("point_index", ponto.get("pointNumber", -1))
            curva = ponto.get("curve_number", ponto.get("curveNumber", 0))
            if isinstance(pos, int) and 0 <= pos < len(idx):
                origem = df_r if curva == 0 else df_d
                detalhe_mes = origem[origem["data_dt"].dt.to_period("M") == idx[pos]]
                with st.expander(f"Lançamentos de {labels_fluxo[pos]} · {'receitas' if curva == 0 else 'despesas'}", expanded=True):
                    _tabela_detalhe(detalhe_mes)
        else:
            st.caption("Clique em um ponto para abrir os lançamentos daquele mês.")
    else:
        st.info("Sem dados para o período.")

with col_b:
    st.markdown('<div class="p-title"><span class="tbar"></span> Onde foi o dinheiro</div>', unsafe_allow_html=True)
    if not df_df.empty and "categoria" in df_df.columns:
        por_cat = df_df.groupby("categoria")["valor"].sum().sort_values(ascending=False)
        top = por_cat.head(6)
        graf_cat = go.Figure(go.Bar(
            x=top.values[::-1], y=top.index.astype(str)[::-1], orientation="h",
            marker_color=DESPESA, customdata=top.index.astype(str)[::-1],
            hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>",
        ))
        graf_cat.update_layout(**ARCTIC, height=300, showlegend=False)
        graf_cat.update_xaxes(visible=False)
        graf_cat.update_yaxes(showgrid=False)
        escolha_cat = st.plotly_chart(
            graf_cat, use_container_width=True, key="categorias_interativas", theme=None,
            on_select="rerun", selection_mode="points",
        )
        pontos_cat = escolha_cat.selection.points if escolha_cat else []
        if pontos_cat:
            ponto_cat = pontos_cat[0]
            categoria_escolhida = ponto_cat.get("y")
            if categoria_escolhida is None:
                pos_cat = ponto_cat.get("point_index", ponto_cat.get("pointNumber", -1))
                if isinstance(pos_cat, int) and 0 <= pos_cat < len(top):
                    categoria_escolhida = str(top.index[::-1][pos_cat])
            detalhe_cat = df_df[df_df["categoria"].astype(str) == str(categoria_escolhida)]
            with st.expander(f"{categoria_escolhida} · {len(detalhe_cat)} lançamentos", expanded=True):
                _tabela_detalhe(detalhe_cat)
        else:
            st.caption("Clique numa barra para ver os lançamentos da categoria.")
        with st.expander("🔍 Ver todas as categorias"):
            tbl = por_cat.reset_index()
            tbl.columns = ["Categoria", "Total"]
            tbl["Total"] = tbl["Total"].apply(formatar_moeda)
            st.dataframe(tbl, use_container_width=True, hide_index=True, height=280)
    else:
        st.info("Sem despesas no período.")

st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# SAÚDE  |  SEMANA  |  FATURA C6 BRU
# ══════════════════════════════════════════════════════════════
# Score simples e honesto (baseado na poupança do período)
score = 50
if total_rec > 0:
    if   poup >= 0.20: score += 27
    elif poup >= 0.10: score += 13
    elif poup >= 0:    score += 0
    else:              score -= 27
score = max(0, min(100, score))
if   score >= 75: s_lab, s_col, s_bg, s_bd = "Ótima", AURORA, "#39E0A614", "#39E0A63a"
elif score >= 50: s_lab, s_col, s_bg, s_bd = "Boa", RECEITA, "#4AA8FF14", "#4AA8FF3a"
elif score >= 30: s_lab, s_col, s_bg, s_bd = "Atenção", WARN, "#FFC24b14", "#FFC24b3a"
else:             s_lab, s_col, s_bg, s_bd = "Crítica", DESPESA, "#FF5C7a14", "#FF5C7a3a"
CIRC = 257.6
dash_off = CIRC * (1 - score / 100)

# Semana atual — lê os gastos semanais (fonte "Semanal"), independentes do macro
hoje = date.today()
seg = hoje - timedelta(days=hoje.weekday()); dom = seg + timedelta(days=6)
gasto_sem = 0.0
if not df_semanal.empty and "data_dt" in df_semanal.columns:
    wk = df_semanal[(df_semanal["data_dt"].dt.date >= seg) & (df_semanal["data_dt"].dt.date <= dom)]
    gasto_sem = wk["valor"].sum()
cfg = ler_json(str(CONFIG_FILE)); limite_sem = float(cfg.get("limite_semanal", 0) or 0)
_limites_salvos = ler_csv("limites_semanais")
if not _limites_salvos.empty and {"chave", "valor"}.issubset(_limites_salvos.columns):
    _chaves_limite = _limites_salvos["chave"].astype(str)
    for _chave in ("padrao", seg.isoformat()):
        _v = pd.to_numeric(_limites_salvos.loc[_chaves_limite == _chave, "valor"], errors="coerce").dropna()
        if not _v.empty:
            limite_sem = float(_v.iloc[-1])

# Fatura C6 Bru — mês corrente.
# A fatura = detalhe importado (fonte C6 Bank) OU o resumo do Notion (categoria "Cartões").
# NÃO inclui despesas do Notion apenas marcadas como C6 BRU (Madre de Deus, Unimed…),
# que não fazem parte da fatura do cartão.
def _fatura_c6bru(df):
    fp = df.get("forma_pagamento", pd.Series("", index=df.index)).astype(str).str.upper().str.strip()
    bk = df.get("banco", pd.Series("", index=df.index)).astype(str).str.upper().str.strip()
    fon = df.get("fonte", pd.Series("", index=df.index)).astype(str)
    cat = df.get("categoria", pd.Series("", index=df.index)).astype(str)
    c6 = (fp == "C6 BRU") | (bk == "C6 BRU")
    return c6 & ((fon == "C6 Bank") | ((fon == "Notion") & cat.str.contains("Cart", case=False, na=False)))
fat_c6 = pd.DataFrame()
if not df_d.empty and "data_dt" in df_d.columns:
    fat_c6 = df_d[_fatura_c6bru(df_d) & (df_d["data_dt"].dt.month == hoje.month) & (df_d["data_dt"].dt.year == hoje.year)]
# Reembolsos do C6 no mês (receitas fonte C6 Bank) abatem a fatura
_reemb_c6 = 0.0
if not df_r.empty and "data_dt" in df_r.columns and "fonte" in df_r.columns:
    _rc = df_r[(df_r["fonte"].astype(str) == "C6 Bank") &
               (df_r["data_dt"].dt.month == hoje.month) & (df_r["data_dt"].dt.year == hoje.year)]
    _reemb_c6 = _rc["valor"].sum()
total_fat = (fat_c6["valor"].sum() if not fat_c6.empty else 0) - _reemb_c6

s1, s2, s3 = st.columns(3)

with s1:
    st.markdown('<div class="p-title"><span class="tbar"></span> Saúde Financeira</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="panel gauge">
      <div class="ring">
        <svg width="96" height="96" viewBox="0 0 96 96" style="transform:rotate(-90deg)">
          <circle cx="48" cy="48" r="41" fill="none" stroke="#152034" stroke-width="8"/>
          <circle cx="48" cy="48" r="41" fill="none" stroke="{s_col}" stroke-width="8" stroke-linecap="round"
                  stroke-dasharray="{CIRC}" stroke-dashoffset="{dash_off:.1f}"
                  style="filter:drop-shadow(0 0 6px {s_col}88)"/>
        </svg>
        <div class="score"><b class="num">{score}</b><span>/100</span></div>
      </div>
      <div>
        <div class="status" style="color:{s_col};background:{s_bg};border:1px solid {s_bd}">● {s_lab}</div>
        <div class="muted">Baseado na taxa de poupança do período. Guardar 20%+ da renda mantém a saúde no verde.</div>
      </div>
    </div>""", unsafe_allow_html=True)

with s2:
    st.markdown('<div class="p-title"><span class="tbar"></span> Esta semana</div>', unsafe_allow_html=True)
    if limite_sem > 0:
        pct = min(gasto_sem / limite_sem, 1.0); restam = max(limite_sem - gasto_sem, 0)
        cor = AURORA if pct < 0.7 else (WARN if pct < 1.0 else DESPESA)
        st.markdown(f"""
        <div class="panel">
          <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px">
            <span class="num" style="color:var(--txt-hi);font-weight:800;font-size:20px">{formatar_moeda(gasto_sem)}</span>
            <span class="num" style="color:var(--txt-dim);font-size:12.5px">de {formatar_moeda(limite_sem)}</span>
          </div>
          <div class="bar-outer"><div class="bar-inner" style="width:{pct*100:.0f}%;
               background:linear-gradient(90deg,{cor},{cor}bb);box-shadow:0 0 16px {cor}55"></div></div>
          <div style="margin-top:9px;font-size:12.5px;color:{cor};font-weight:600">
            {'Restam ' + formatar_moeda(restam) + f' · {pct*100:.0f}% usado' if pct < 1 else '🚨 Limite estourado!'}
          </div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class="panel">
          <div class="num" style="color:var(--txt-hi);font-weight:800;font-size:20px">{formatar_moeda(gasto_sem)}</div>
          <div class="muted">Gasto de {seg.strftime('%d/%m')} a {dom.strftime('%d/%m')}. Defina um limite na página
          <b>📆 Gastos Semanais</b>.</div>
        </div>""", unsafe_allow_html=True)

with s3:
    st.markdown('<div class="p-title"><span class="tbar"></span> Fatura C6 Bru</div>', unsafe_allow_html=True)
    st.markdown(f"""<div class="panel">
      <div style="color:var(--txt-dim);font-size:12px">{MESES_PT[hoje.month-1]}/{hoje.year}</div>
      <div class="num" style="color:var(--despesa);font-weight:800;font-size:24px;margin-top:2px">{formatar_moeda(total_fat)}</div>
    </div>""", unsafe_allow_html=True)
    with st.popover("🔎 ver fatura", use_container_width=True):
        if fat_c6.empty:
            st.caption("Sem lançamentos do C6 Bru neste mês. Importe a fatura em **Configurações → Importar → C6 Bank**.")
        else:
            _tabela_detalhe(fat_c6)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
st.divider()

# ══════════════════════════════════════════════════════════════
# DETALHE (oculto por padrão, clicável)
# ══════════════════════════════════════════════════════════════
with st.expander("📑 Top lançamentos do período"):
    t1, t2 = st.columns(2)
    with t1:
        st.markdown("**🔴 Maiores despesas**")
        _tabela_detalhe(df_df) if not df_df.empty else st.caption("Sem despesas.")
    with t2:
        st.markdown("**🔵 Maiores receitas**")
        _tabela_detalhe(df_rf) if not df_rf.empty else st.caption("Sem receitas.")

# ══════════════════════════════════════════════════════════════
# CATEGORIZAR "OUTROS" (recategoriza + cria regra p/ o futuro)
# ══════════════════════════════════════════════════════════════
_out = df_d[df_d["categoria"].astype(str).str.contains("Outros", case=False, na=False)] if not df_d.empty else pd.DataFrame()
if not _out.empty:
    _tot_out = _out["valor"].sum()
    with st.expander(f"🏷️ Categorizar gastos em 'Outros'  ·  {len(_out)} lançamentos · {formatar_moeda(_tot_out)}"):
        st.caption("Escolha a categoria de cada estabelecimento. Ao salvar, recategoriza **todos** os lançamentos "
                   "daquele nome **e cria uma regra** pra categorizar sozinho nas próximas importações.")
        _g = (_out.groupby("descricao")["valor"].agg(Total="sum", Lancs="count")
              .reset_index().sort_values("Total", ascending=False).head(50))
        _g["Nova categoria"] = ""
        _g = _g.rename(columns={"descricao": "Estabelecimento"})
        _g["Total"] = _g["Total"].round(2)

        _cats = [""] + sorted(set(listar_categorias("despesa")))
        _ed = st.data_editor(
            _g[["Estabelecimento", "Lancs", "Total", "Nova categoria"]],
            column_config={
                "Estabelecimento": st.column_config.TextColumn("Estabelecimento", disabled=True, width="large"),
                "Lancs": st.column_config.NumberColumn("Qtd", disabled=True, width="small"),
                "Total": st.column_config.NumberColumn("Total", format="R$ %.2f", disabled=True),
                "Nova categoria": st.column_config.SelectboxColumn("→ Categoria", options=_cats, width="medium"),
            },
            hide_index=True, use_container_width=True, num_rows="fixed", key="cat_outros_editor", height=400,
        )
        _criar_regra = st.checkbox("Criar regra pra categorizar isso automaticamente no futuro", value=True, key="cat_criar_regra")

        # Prévia do impacto real (recategoriza TODOS os lançamentos com esses nomes)
        _sel = _ed[_ed["Nova categoria"].astype(str).str.strip() != ""]
        if not _sel.empty:
            _nomes = set(_sel["Estabelecimento"].astype(str))
            _afeta = int(df_d["descricao"].astype(str).isin(_nomes).sum()) if not df_d.empty else 0
            st.info(f"🔎 **Prévia:** {len(_sel)} categoria(s) escolhida(s) vão recategorizar "
                    f"**{_afeta} lançamento(s)** com esses nomes — de **todas as fontes e períodos**, "
                    f"não só o que está em Outros.")

        if st.button("💾 Salvar categorização", type="primary", use_container_width=True, key="btn_cat_outros"):
            if _sel.empty:
                st.warning("Escolha ao menos uma categoria.")
            else:
                _dfull = ler_csv(DESPESAS_FILE)
                _n = 0
                for _, _r in _sel.iterrows():
                    _est = str(_r["Estabelecimento"]); _cat = str(_r["Nova categoria"])
                    _m = _dfull["descricao"].astype(str) == _est
                    _n += int(_m.sum())
                    _dfull.loc[_m, "categoria"] = _cat
                _ok = salvar_parquet("despesas", _dfull)
                # cria regras — SEM duplicar (mesma descrição não vira 2 regras)
                _nr = 0
                if _ok and _criar_regra:
                    _reg = ler_csv(MAPEAMENTOS_FILE)
                    _existentes = set(_reg["padrao"].astype(str).str.strip().str.lower()) if not _reg.empty and "padrao" in _reg.columns else set()
                    _novas = [{"id": gerar_id(), "padrao": str(_r["Estabelecimento"]),
                               "categoria": str(_r["Nova categoria"]), "tipo": "despesa"}
                              for _, _r in _sel.iterrows()
                              if str(_r["Estabelecimento"]).strip().lower() not in _existentes]
                    if _novas:
                        _reg2 = pd.concat([_reg, pd.DataFrame(_novas)], ignore_index=True) if not _reg.empty else pd.DataFrame(_novas)
                        salvar_parquet("mapeamentos", _reg2)
                        _nr = len(_novas)
                if _ok:
                    invalidar_cache("despesas"); invalidar_cache("mapeamentos")
                    mensagem_sucesso(f"✅ {_n} lançamento(s) recategorizados" + (f" · {_nr} regra(s) nova(s)!" if _nr else "!"))
                    st.rerun()
                else:
                    mensagem_erro("Gravação bloqueada por segurança — nada foi alterado.")

st.divider()
st.markdown(
    "<p style='text-align:center;color:var(--txt-dim);font-size:0.75rem;margin-top:14px'>"
    f"🐧 {APP_NOME} · {tema_atual()}"
    "</p>", unsafe_allow_html=True
)
