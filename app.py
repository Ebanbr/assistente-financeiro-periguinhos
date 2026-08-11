# ============================================================
#  app.py — Dashboard Principal (tema Ártico ❄️)
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from pathlib import Path

from config import APP_NOME, APP_EMOJI, DESPESAS_FILE, RECEITAS_FILE, MESES_PT, CONFIG_FILE
from utils import ler_csv, formatar_moeda, ler_json
from auth import login_page, usuario_logado, logout

# ── Login ─────────────────────────────────────────────────────
if not st.session_state.get("logado"):
    login_page()
    st.stop()

st.set_page_config(page_title=f"{APP_EMOJI} {APP_NOME}", page_icon=APP_EMOJI,
                   layout="wide", initial_sidebar_state="expanded")

css_path = Path(__file__).parent / "style.css"
if css_path.exists():
    with open(css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Paleta Ártico p/ gráficos
ICE, AURORA, RECEITA, DESPESA, WARN = "#4FE3FF", "#39E0A6", "#4AA8FF", "#FF5C7A", "#FFC24B"
ARCTIC = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#93A2C4", family="Inter", size=12),
    xaxis=dict(gridcolor="#16223a", linecolor="#1E2942", zeroline=False),
    yaxis=dict(gridcolor="#16223a", linecolor="#1E2942", zeroline=False),
    margin=dict(l=6, r=6, t=10, b=6),
)

# ── Sidebar ──────────────────────────────────────────────────
st.sidebar.markdown(f"## {APP_EMOJI} {APP_NOME}")
st.sidebar.markdown("<small style='color:#5B6889'>Painel financeiro da família</small>", unsafe_allow_html=True)
_u = usuario_logado()
_emoji_u = "🧔" if _u == "BOo" else "👩"
st.sidebar.markdown(f"<small style='color:#4AA8FF'>{_emoji_u} Olá, <b>{_u}</b>!</small>", unsafe_allow_html=True)
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

# ── Séries mensais (p/ sparklines e fluxo) ───────────────────
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

def _spark(vals, color):
    vals = [float(v) for v in vals]
    if len(vals) < 2:
        return "<div style='height:30px'></div>"
    lo, hi = min(vals), max(vals); rng = (hi - lo) or 1; n = len(vals)
    pts = [f"{i/(n-1)*120:.1f},{30-((v-lo)/rng)*24-3:.1f}" for i, v in enumerate(vals)]
    lx, ly = pts[-1].split(",")
    return (f'<svg class="spark" viewBox="0 0 120 30" preserveAspectRatio="none" aria-hidden="true">'
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<circle cx="{lx}" cy="{ly}" r="2.4" fill="{color}"/></svg>')

spk_r = _spark(fluxo["receitas"].tail(8).tolist(), RECEITA) if idx else "<div style='height:30px'></div>"
spk_d = _spark(fluxo["despesas"].tail(8).tolist(), DESPESA) if idx else "<div style='height:30px'></div>"
spk_s = _spark(fluxo["saldo"].tail(8).tolist(), AURORA) if idx else "<div style='height:30px'></div>"
spk_p = _spark([(fluxo["saldo"].iloc[i]/fluxo["receitas"].iloc[i]) if fluxo["receitas"].iloc[i] > 0 else 0
                for i in range(len(idx))][-8:], ICE) if idx else "<div style='height:30px'></div>"

# ══════════════════════════════════════════════════════════════
# HERO / TESE
# ══════════════════════════════════════════════════════════════
if saldo >= 0:
    verbo, classe, valor_tese = "Sobrou", "pos", saldo
    pill1 = f'<span class="pill up">▲ {poup*100:.0f}% da renda poupada</span>'
else:
    verbo, classe, valor_tese = "Faltaram", "neg", abs(saldo)
    pill1 = f'<span class="pill down">▼ gastou mais do que ganhou</span>'
pill2 = f'<span class="pill mut">{len(df_df)} despesas · {len(df_rf)} receitas no período</span>'

st.markdown(f"""
<div class="thesis">
  <div class="eyebrow">Resultado · {periodo_label}</div>
  <div class="big num">{verbo} <em class="{classe}">{formatar_moeda(valor_tese)}</em></div>
  <div class="trow">{pill1}{pill2}</div>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# KPIs (clicáveis → detalhe)
# ══════════════════════════════════════════════════════════════
def _tabela_detalhe(df, cols=("data", "descricao", "categoria", "valor")):
    if df.empty:
        st.caption("Sem lançamentos.")
        return
    t = df.sort_values("valor", ascending=False)[list(cols)].head(60).copy()
    t["data"] = pd.to_datetime(t["data"], errors="coerce").dt.strftime("%d/%m/%Y")
    t["valor"] = t["valor"].apply(formatar_moeda)
    t.columns = ["Data", "Descrição", "Categoria", "Valor"]
    st.dataframe(t, use_container_width=True, hide_index=True, height=300)

k1, k2, k3, k4 = st.columns(4)
kpis = [
    (k1, "receita", "Receitas", "💰", formatar_moeda(total_rec), f"{len(df_rf)} lançamentos", spk_r, df_rf),
    (k2, "despesa", "Despesas", "💸", formatar_moeda(total_desp), f"{len(df_df)} lançamentos", spk_d, df_df),
    (k3, "saldo",   "Saldo",    "💵", ("+" if saldo >= 0 else "") + formatar_moeda(saldo), "receitas − despesas", spk_s, None),
    (k4, "poup",    "Poupança", "📈", f"{poup*100:.0f}%", "meta ideal: 20%", spk_p, None),
]
for col, cls, lab, ico, val, sub, spk, detalhe in kpis:
    with col:
        st.markdown(f"""
        <div class="kpi {cls}">
          <div class="k-top"><span class="k-lab">{lab}</span><span class="k-ico">{ico}</span></div>
          <div class="k-val num">{val}</div>
          <div class="k-sub">{sub}</div>
          {spk}
        </div>""", unsafe_allow_html=True)
        with st.popover("🔎 detalhar", use_container_width=True):
            if cls == "receita":
                st.markdown("**Receitas do período**"); _tabela_detalhe(df_rf)
            elif cls == "despesa":
                st.markdown("**Despesas do período**"); _tabela_detalhe(df_df)
            elif cls == "saldo":
                st.markdown("**Composição do saldo**")
                st.metric("Receitas", formatar_moeda(total_rec))
                st.metric("Despesas", formatar_moeda(total_desp))
                st.metric("Saldo", ("+" if saldo >= 0 else "") + formatar_moeda(saldo))
            else:
                st.markdown("**Taxa de poupança**")
                st.caption("Quanto da sua renda sobrou no período. O ideal é guardar ao menos 20%.")
                st.progress(min(max(poup, 0), 1.0))
                st.caption(f"Poupança atual: **{poup*100:.1f}%** — {formatar_moeda(saldo)} de {formatar_moeda(total_rec)}.")

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
            line=dict(color=RECEITA, width=2.4), fill="tozeroy", fillcolor="rgba(74,168,255,0.14)",
            hovertemplate="<b>%{x}</b><br>Receitas: R$ %{y:,.2f}<extra></extra>"))
        fig.add_trace(go.Scatter(
            x=labels_fluxo, y=fluxo["despesas"], name="Despesas",
            line=dict(color=DESPESA, width=2.4), fill="tozeroy", fillcolor="rgba(255,92,122,0.12)",
            hovertemplate="<b>%{x}</b><br>Despesas: R$ %{y:,.2f}<extra></extra>"))
        fig.update_layout(**ARCTIC, height=300, hovermode="x unified",
                          legend=dict(orientation="h", x=0, y=1.14, bgcolor="rgba(0,0,0,0)",
                                      font=dict(color="#EAF1FF", size=12)))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados para o período.")

with col_b:
    st.markdown('<div class="p-title"><span class="tbar"></span> Onde foi o dinheiro</div>', unsafe_allow_html=True)
    if not df_df.empty and "categoria" in df_df.columns:
        por_cat = df_df.groupby("categoria")["valor"].sum().sort_values(ascending=False)
        top = por_cat.head(6)
        maxv = top.max() or 1
        grads = ["#FF5C7A,#FF8AA0", "#4AA8FF,#7CC4FF", "#4FE3FF,#8CEBFF",
                 "#39E0A6,#7CF0C8", "#B98CFF,#D3B8FF", "#FFC24B,#FFD87E"]
        linhas = ""
        for i, (cat, val) in enumerate(top.items()):
            g = grads[i % len(grads)]
            linhas += (f'<div><div class="c-top"><span class="c-name">{cat}</span>'
                       f'<span class="c-val num">{formatar_moeda(val)}</span></div>'
                       f'<div class="track"><div class="fill" style="width:{val/maxv*100:.0f}%;'
                       f'background:linear-gradient(90deg,{g})"></div></div></div>')
        st.markdown(f'<div class="cat">{linhas}</div>', unsafe_allow_html=True)
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

# Fatura C6 Bru — mês corrente
def _is_c6bru(df):
    fp = df.get("forma_pagamento", pd.Series("", index=df.index)).astype(str).str.upper().str.strip()
    bk = df.get("banco", pd.Series("", index=df.index)).astype(str).str.upper().str.strip()
    return (fp == "C6 BRU") | (bk == "C6 BRU")
fat_c6 = pd.DataFrame()
if not df_d.empty and "data_dt" in df_d.columns:
    fat_c6 = df_d[_is_c6bru(df_d) & (df_d["data_dt"].dt.month == hoje.month) & (df_d["data_dt"].dt.year == hoje.year)]
total_fat = fat_c6["valor"].sum() if not fat_c6.empty else 0

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

st.markdown(
    "<p style='text-align:center;color:#2A3A58;font-size:0.75rem;margin-top:14px'>"
    f"🐧 {APP_NOME} · tema Ártico ❄️"
    "</p>", unsafe_allow_html=True
)
