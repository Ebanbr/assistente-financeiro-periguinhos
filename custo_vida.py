"""Custo de vida: cada categoria é Fixa, Variável essencial, Variável cortável ou Fora da conta.

Custo mínimo para viver = média mensal de Fixas + Variáveis essenciais.
Funções puras; a página só lê, classifica e desenha.
"""
import pandas as pd

FIXA, ESSENCIAL, CORTAVEL, FORA = "Fixa", "Variável essencial", "Variável cortável", "Fora da conta"
SEM_TIPO = "Sem tipo"
TIPOS = [FIXA, ESSENCIAL, CORTAVEL, FORA]

# Classificação aprovada pelo Bruno em 2026-10-14. O que não está aqui fica "Sem tipo"
# até ele classificar na página.
CLASSIFICACAO_PADRAO = {
    **dict.fromkeys([
        "🏢 Condomínio", "💡 Energia", "🌐 Internet", "📱 Celulares", "🧹 Diarista",
        "🏫 Madre de Deus", "🎓 Escola - Madre de Deus", "🏦 Fin. CAIXA", "🏋️ Academia",
        "🏊 AABB", "🏠 IPTU", "🧾 Impostos - RF", "🎬 Streaming",
    ], FIXA),
    **dict.fromkeys([
        "🛒 Supermercado", "🥖 Padaria", "💊 Saúde", "💊 Saúde - Farmácia", "💊 Saúde - Clínica",
        "⛽Combustível", "🚗 Transporte", "🚗 Estacionamento",
        "🥬 Hortifruti", "🥩 Carnes e Peixes", "🧀 Frios e Laticínios", "🥫 Mercearia",
        "🥤 Bebidas", "🧽 Limpeza", "🧴 Higiene e Beleza",
    ], ESSENCIAL),
    **dict.fromkeys([
        "🎮 Lazer", "🛍️ Compras Online", "👗 Vestuário", "🎁 Presentes", "✈️ Viagens",
        "🍀 Loterias", "💇🏻Beleza", "🦁 Sport Recife",
    ], CORTAVEL),
    # Cartões: o resumo do Notion é só um norte, a fatura importada do C6 é que vale.
    # Pix Avulso: por fora, para o Bruno analisar. Poupança e ajuda à família: fora.
    **dict.fromkeys([
        "💳 Cartões", "💸 Pix Avulso", "🐷 Poupança Kids", "👩 Mãe", "👨 Pai", "👤 Sandra",
    ], FORA),
}


def tipo_padrao(categoria):
    """Tipo sugerido; categoria combinada ("A, B") só herda se todas as partes concordam."""
    categoria = str(categoria).strip()
    if categoria in CLASSIFICACAO_PADRAO:
        return CLASSIFICACAO_PADRAO[categoria]
    partes = {CLASSIFICACAO_PADRAO.get(p.strip()) for p in categoria.split(",")}
    return partes.pop() if len(partes) == 1 and None not in partes else SEM_TIPO


def classificar(categorias, salvos):
    """{categoria: tipo} — o que o Bruno salvou vence a sugestão."""
    escolhidos = {}
    if not salvos.empty and {"categoria", "tipo"}.issubset(salvos.columns):
        validos = salvos[salvos["tipo"].isin(TIPOS)]
        escolhidos = dict(zip(validos["categoria"].astype(str), validos["tipo"]))
    return {c: escolhidos.get(c, tipo_padrao(c)) for c in categorias}


def meses_da_janela(hoje, n_meses, primeiro_mes=None):
    """Últimos `n_meses` meses completos (o mês atual fica de fora), sem passar de `primeiro_mes`."""
    fim = pd.Period(hoje, freq="M") - 1
    meses = pd.period_range(end=fim, periods=n_meses, freq="M")
    if primeiro_mes is not None:
        meses = meses[meses >= pd.Period(primeiro_mes, freq="M")]
    return list(meses)


def gasto_mensal_por_tipo(despesas, mapa, meses):
    """Tabela mês × tipo (inclui Sem tipo e meses zerados)."""
    colunas = TIPOS + [SEM_TIPO]
    vazio = pd.DataFrame(0.0, index=pd.PeriodIndex(meses, freq="M"), columns=colunas)
    if despesas.empty or not meses:
        return vazio
    d = despesas.copy()
    d["_mes"] = pd.to_datetime(d["data"], errors="coerce").dt.to_period("M")
    d = d[d["_mes"].isin(meses)]
    d["_tipo"] = d["categoria"].astype(str).map(mapa).fillna(SEM_TIPO)
    d["valor"] = pd.to_numeric(d["valor"], errors="coerce").fillna(0)
    tabela = d.pivot_table(index="_mes", columns="_tipo", values="valor", aggfunc="sum", fill_value=0.0)
    return tabela.reindex(index=vazio.index, columns=colunas, fill_value=0.0).astype(float)


def media_por_categoria(despesas, mapa, meses):
    """Média mensal de cada categoria na janela, com o tipo."""
    if despesas.empty or not meses:
        return pd.DataFrame(columns=["categoria", "tipo", "media_mes"])
    d = despesas.copy()
    d["_mes"] = pd.to_datetime(d["data"], errors="coerce").dt.to_period("M")
    d = d[d["_mes"].isin(meses)]
    d["valor"] = pd.to_numeric(d["valor"], errors="coerce").fillna(0)
    soma = d.groupby(d["categoria"].astype(str))["valor"].sum() / len(meses)
    out = soma.round(2).rename("media_mes").reset_index().rename(columns={"index": "categoria"})
    out["tipo"] = out["categoria"].map(mapa).fillna(SEM_TIPO)
    return out.sort_values("media_mes", ascending=False, ignore_index=True)[["categoria", "tipo", "media_mes"]]


def custo_minimo(mensal):
    """Média mensal de Fixas + Variáveis essenciais."""
    if mensal.empty:
        return 0.0
    return round(float(mensal[[FIXA, ESSENCIAL]].sum(axis=1).mean()), 2)
