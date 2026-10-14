# ============================================================
#  6_💰_Custo_de_Vida.py — Fixas × Variáveis: quanto custa viver
#  Custo mínimo = média mensal de Fixas + Variáveis essenciais.
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st

from auth import exigir_login
exigir_login()

from datetime import date

import pandas as pd
import plotly.graph_objects as go

from config import DESPESAS_FILE, RECEITAS_FILE, TIPOS_CATEGORIA_FILE, COLUNAS_TIPOS_CATEGORIA
from utils import (esc, configurar_pagina, inicializar_dados, ler_csv, salvar_parquet, invalidar_cache,
                   formatar_moeda, mensagem_sucesso, mensagem_erro, gerar_id, agora)
from ui_theme import paleta_graficos, tema_atual, estilizar_figura, eixo_reais, valor_curto
from custo_vida import (FIXA, ESSENCIAL, CORTAVEL, FORA, SEM_TIPO, TIPOS, classificar, meses_da_janela,
                        gasto_mensal_por_tipo, media_por_categoria, custo_minimo)

configurar_pagina("Custo de vida", icone="💰")
inicializar_dados()

_cores = paleta_graficos(tema_atual())
COR_TIPO = {FIXA: _cores["receita"], ESSENCIAL: _cores["saldo"], CORTAVEL: "#c98500" if tema_atual() != "Claro" else "#eda100"}

st.markdown("""
<div class="thesis">
  <div class="eyebrow">Fixas × variáveis</div>
  <div class="big" style="font-size:clamp(26px,4vw,40px)">Quanto custa <em class="pos">viver</em> por mês</div>
  <div class="trow"><span class="pill mut">Custo mínimo = despesas fixas + variáveis essenciais (média dos meses completos)</span></div>
</div>
""", unsafe_allow_html=True)
st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

# ── Dados ────────────────────────────────────────────────────
df_d = ler_csv(DESPESAS_FILE)
df_r = ler_csv(RECEITAS_FILE)
df_tipos = ler_csv(TIPOS_CATEGORIA_FILE)
if df_d.empty:
    st.info("Sem despesas lançadas ainda.")
    st.stop()

# Mesmo critério do dashboard: os gastos semanais são ferramenta à parte (o crédito
# reaparece na fatura importada do C6) e reembolsos do C6 não são renda.
if "fonte" in df_d.columns:
    df_d = df_d[df_d["fonte"].astype(str) != "Semanal"].copy()
if not df_r.empty and "fonte" in df_r.columns:
    df_r = df_r[df_r["fonte"].astype(str) != "C6 Bank"].copy()

# Janela começa na 1ª fatura do C6 importada: antes disso o cartão só existe como resumo.
_c6 = df_d.loc[df_d.get("fonte", pd.Series(dtype=str)).astype(str) == "C6 Bank", "data"]
primeiro_c6 = pd.to_datetime(_c6, errors="coerce").min()
n_meses = st.radio("Média dos últimos:", [3, 6, 12, 24], index=2, horizontal=True,
                   format_func=lambda n: f"{n} meses", key="custo_janela")
meses = meses_da_janela(date.today(), n_meses, primeiro_c6 if pd.notna(primeiro_c6) else None)
if not meses:
    st.info("Ainda não há um mês completo desde a primeira fatura importada.")
    st.stop()
if len(meses) < n_meses:
    st.caption(f"Só {len(meses)} mês(es) desde a primeira fatura do C6 importada — a média usa esses.")

categorias = sorted(df_d["categoria"].dropna().astype(str).unique())
mapa = classificar(categorias, df_tipos)
mensal = gasto_mensal_por_tipo(df_d, mapa, meses)
por_cat = media_por_categoria(df_d, mapa, meses)

receita_media = 0.0
if not df_r.empty:
    _r = df_r.copy()
    _r["_mes"] = pd.to_datetime(_r["data"], errors="coerce").dt.to_period("M")
    _r = _r[_r["_mes"].isin(meses)]
    receita_media = float(pd.to_numeric(_r["valor"], errors="coerce").fillna(0).sum()) / len(meses)

minimo = custo_minimo(mensal)
media = mensal.mean()
cortavel = float(media[CORTAVEL])
sem_tipo = float(media[SEM_TIPO])
folga = receita_media - minimo - cortavel - sem_tipo

# ── KPIs ─────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("💰 Custo mínimo para viver", formatar_moeda(minimo),
          help="Média mensal de despesas fixas + variáveis essenciais.")
k2.metric("✂️ Variáveis cortáveis", formatar_moeda(cortavel), help="Média mensal do que dá para cortar.")
k3.metric("📥 Receita média", formatar_moeda(receita_media), help="Receitas no mesmo período (sem reembolsos do C6).")
k4.metric("🧮 Sobra depois de tudo", formatar_moeda(folga),
          help="Receita média − (fixas + essenciais + cortáveis + sem tipo). 'Fora da conta' não entra.")
st.caption(f"Fixas {formatar_moeda(media[FIXA])} · Essenciais {formatar_moeda(media[ESSENCIAL])} · "
           f"Fora da conta {formatar_moeda(media[FORA])} · Média de {len(meses)} mês(es): "
           f"{meses[0].strftime('%m/%Y')} a {meses[-1].strftime('%m/%Y')}")
if sem_tipo > 0:
    n_sem = int((por_cat["tipo"] == SEM_TIPO).sum())
    st.warning(f"{n_sem} categoria(s) ainda sem tipo somam {formatar_moeda(sem_tipo)}/mês e entram só na sobra. "
               "Classifique em **🏷️ Tipo de cada categoria**, no fim da página.")

# ── Gráfico mês a mês ────────────────────────────────────────
st.markdown('<div class="p-title"><span class="tbar"></span> Mês a mês</div>', unsafe_allow_html=True)
rotulos = [m.strftime("%m/%Y") for m in mensal.index]
fig = go.Figure()
for tipo in (FIXA, ESSENCIAL, CORTAVEL):
    fig.add_bar(x=rotulos, y=mensal[tipo], name=tipo, marker_color=COR_TIPO[tipo],
                hovertemplate=f"{tipo}<br>%{{x}}: R$ %{{y:,.2f}}<extra></extra>")
if receita_media > 0:
    fig.add_hline(y=receita_media, line_dash="dot", line_color=_cores["texto"],
                  annotation_text=f"Receita média {valor_curto(receita_media)}", annotation_position="top left")
fig.add_hline(y=minimo, line_dash="dash", line_color=_cores["despesa"],
              annotation_text=f"Mínimo {valor_curto(minimo)}", annotation_position="bottom left")
_vmax = max(float(mensal[[FIXA, ESSENCIAL, CORTAVEL]].sum(axis=1).max()), receita_media, minimo)
_tv, _tt = eixo_reais(_vmax * 1.08)
fig.update_layout(barmode="stack", height=360, margin=dict(l=6, r=6, t=10, b=6),
                  legend=dict(orientation="h", y=-0.15), yaxis=dict(tickvals=_tv, ticktext=_tt, automargin=True),
                  xaxis=dict(automargin=True))
estilizar_figura(fig)
st.plotly_chart(fig, use_container_width=True)

# ── Detalhe por tipo ─────────────────────────────────────────
st.markdown('<div class="p-title"><span class="tbar"></span> O que tem em cada tipo</div>', unsafe_allow_html=True)
for tipo in TIPOS + [SEM_TIPO]:
    linhas = por_cat[por_cat["tipo"] == tipo]
    if linhas.empty:
        continue
    titulo = f"{tipo} · {formatar_moeda(linhas['media_mes'].sum())}/mês · {len(linhas)} categoria(s)"
    if tipo == FORA:
        titulo += " — não entra no custo nem na sobra"
    with st.expander(titulo, expanded=(tipo == FORA)):
        st.dataframe(
            linhas[["categoria", "media_mes"]], hide_index=True, use_container_width=True,
            column_config={"categoria": "Categoria",
                           "media_mes": st.column_config.NumberColumn("Média/mês", format="R$ %.2f")})

# ── Classificação (editável) ─────────────────────────────────
with st.expander("🏷️ Tipo de cada categoria", expanded=False):
    st.caption("Escolha o tipo de cada categoria e clique em Salvar. Categoria nova aparece como "
               f"**{SEM_TIPO}** até você classificar.")
    tabela = pd.DataFrame({"categoria": categorias, "tipo": [mapa[c] for c in categorias]})
    tabela = tabela.merge(por_cat[["categoria", "media_mes"]], on="categoria", how="left").fillna({"media_mes": 0.0})
    tabela = tabela.sort_values(["tipo", "media_mes"], ascending=[True, False], ignore_index=True)
    editada = st.data_editor(
        tabela, hide_index=True, use_container_width=True, num_rows="fixed", key="editor_tipos_categoria",
        column_config={
            "categoria": st.column_config.TextColumn("Categoria", disabled=True),
            "tipo": st.column_config.SelectboxColumn("Tipo", options=TIPOS + [SEM_TIPO], required=True),
            "media_mes": st.column_config.NumberColumn("Média/mês", format="R$ %.2f", disabled=True),
        },
    )
    if st.button("💾 Salvar tipos", type="primary", use_container_width=True):
        salvar = editada[editada["tipo"].isin(TIPOS)]
        novo = pd.DataFrame({"id": [gerar_id() for _ in range(len(salvar))],
                             "categoria": salvar["categoria"].values, "tipo": salvar["tipo"].values,
                             "atualizado_em": agora()})[COLUNAS_TIPOS_CATEGORIA]
        # mantém o tipo de categorias que hoje não têm lançamento (não some nada salvo)
        if not df_tipos.empty and "categoria" in df_tipos.columns:
            antigos = df_tipos[~df_tipos["categoria"].astype(str).isin(categorias)]
            novo = pd.concat([antigos.reindex(columns=COLUNAS_TIPOS_CATEGORIA), novo], ignore_index=True)
        if salvar_parquet("tipos_categoria", novo, permitir_vazio=True):
            invalidar_cache("tipos_categoria")
            mensagem_sucesso("Tipos salvos!")
            st.rerun()
        else:
            mensagem_erro("Não foi possível salvar os tipos.")
