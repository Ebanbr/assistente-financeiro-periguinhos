"""Sugestões conservadoras a partir dos lançamentos já categorizados."""
import unicodedata
import re


def normalizar_local(valor):
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", texto.casefold()))


def categoria_do_local(descricao, historico, categorias):
    """Nome normalizado exato; a classificação mais recente prevalece."""
    nome = normalizar_local(descricao)
    if not nome or historico.empty or not {"descricao", "categoria"}.issubset(historico.columns):
        return None
    candidatos = historico[
        historico["descricao"].map(normalizar_local).eq(nome)
        & historico["categoria"].isin(categorias)
    ].copy()
    if candidatos.empty:
        return None
    if "criado_em" in candidatos.columns:
        candidatos = candidatos.sort_values("criado_em", kind="stable", na_position="first")
    return candidatos.iloc[-1]["categoria"]
