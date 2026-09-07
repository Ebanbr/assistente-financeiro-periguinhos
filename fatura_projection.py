"""Calculos puros para estimar a fatura corrente sem misturar datas de compra."""

import re
import pandas as pd
from datetime import date, timedelta


def parse_parcela(valor):
    """Converte '3/10' em (3, 10); compras a vista/invalidas retornam None."""
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", str(valor or ""))
    if not m:
        return None
    atual, total = int(m.group(1)), int(m.group(2))
    return (atual, total) if 1 <= atual <= total else None


def meses_entre(origem, destino):
    return (destino.year - origem.year) * 12 + destino.month - origem.month


def projetar_parcelas(df, ano, mes, cartao):
    """Projeta parcelas de faturas anteriores ainda devidas no mes-alvo.

    Cada linha representa a parcela cobrada no mes salvo em ``data``. Para um
    registro 3/10 de agosto, por exemplo, setembro recebe a 4/10 pelo mesmo valor.
    """
    vazio = {"total": 0.0, "itens": pd.DataFrame(), "com_parcela": 0, "candidatos": 0}
    if df.empty:
        return vazio

    d = df.copy()
    fonte = d.get("fonte", pd.Series("", index=d.index)).astype(str)
    banco = d.get("banco", pd.Series("", index=d.index)).astype(str).str.strip().str.casefold()
    d = d[(fonte == "C6 Bank") & (banco == str(cartao).strip().casefold())].copy()
    if d.empty:
        return vazio

    d["_data"] = pd.to_datetime(d.get("data"), errors="coerce")
    d["_valor"] = pd.to_numeric(d.get("valor"), errors="coerce").fillna(0)
    alvo = pd.Timestamp(year=int(ano), month=int(mes), day=1)
    d = d[d["_data"].notna() & (d["_data"] < alvo)].copy()
    candidatos = len(d)

    if "parcela_atual" in d.columns and "parcelas_total" in d.columns:
        d["_pa"] = pd.to_numeric(d["parcela_atual"], errors="coerce")
        d["_pt"] = pd.to_numeric(d["parcelas_total"], errors="coerce")
    else:
        parcela = d.get("parcela", pd.Series("", index=d.index)).apply(parse_parcela)
        d["_pa"] = parcela.apply(lambda x: x[0] if x else pd.NA)
        d["_pt"] = parcela.apply(lambda x: x[1] if x else pd.NA)

    com_parcela = int(d["_pa"].notna().sum())
    # A mesma compra parcelada aparece em diversas faturas (3/10, 4/10, ...).
    # Para projetar, use somente a ocorrencia mais recente de cada compra; somar
    # todas as ocorrencias inflaria a fatura.
    data_compra = d.get("data_compra", pd.Series("", index=d.index)).astype(str).str.strip()
    if not data_compra.ne("").any():
        obs = d.get("observacao", pd.Series("", index=d.index)).astype(str)
        data_compra = obs.str.extract(r"Compra em\s+(.+)$", expand=False).fillna("")
    d["_chave_compra"] = (
        d.get("descricao", pd.Series("", index=d.index)).astype(str).str.strip().str.casefold()
        + "|" + data_compra
        + "|" + d["_valor"].round(2).astype(str)
        + "|" + d["_pt"].astype(str)
    )
    d = d.sort_values("_data").drop_duplicates("_chave_compra", keep="last")
    d["_offset"] = d["_data"].apply(lambda x: meses_entre(x, alvo))
    d["parcela_projetada"] = d["_pa"] + d["_offset"]
    itens = d[(d["_offset"] > 0) & (d["parcela_projetada"] <= d["_pt"])].copy()
    return {
        "total": float(itens["_valor"].sum()),
        "itens": itens,
        "com_parcela": com_parcela,
        "candidatos": candidatos,
    }


def semana_do_mes(datas):
    """Semana 1= dias 1-7, Semana 2=8-14, ... Semana 5=29-fim."""
    dt = pd.to_datetime(datas, errors="coerce")
    return ((dt.dt.day - 1) // 7 + 1).astype("Int64")


def inicio_semana(valor):
    d = pd.Timestamp(valor).date()
    return d - timedelta(days=d.weekday())


def competencia_fatura(valor, dia_fechamento=4):
    """Retorna (ano, mes) da fatura: compras apos o fechamento vao ao mes seguinte."""
    d = pd.Timestamp(valor).date()
    if d.day <= dia_fechamento:
        return d.year, d.month
    prox = pd.Timestamp(d) + pd.offsets.MonthBegin(1)
    return int(prox.year), int(prox.month)


def intervalo_fatura(ano, mes, dia_fechamento=4, dia_fechamento_anterior=None):
    fim = date(int(ano), int(mes), dia_fechamento)
    mes_anterior = pd.Timestamp(year=int(ano), month=int(mes), day=1) - pd.DateOffset(months=1)
    fechamento_anterior = dia_fechamento if dia_fechamento_anterior is None else int(dia_fechamento_anterior)
    inicio = date(int(mes_anterior.year), int(mes_anterior.month), fechamento_anterior + 1)
    return inicio, fim


def semana_no_ciclo_fatura(datas, ano, mes, dia_fechamento=4, dia_fechamento_anterior=None):
    """Numera blocos de 7 dias dentro do ciclo, começando no dia 5."""
    inicio, fim = intervalo_fatura(ano, mes, dia_fechamento, dia_fechamento_anterior)
    dt = pd.to_datetime(datas, errors="coerce")
    dias = (dt - pd.Timestamp(inicio)).dt.days
    semanas = (dias // 7 + 1).astype("Int64")
    return semanas.where((dt.dt.date >= inicio) & (dt.dt.date <= fim))


def mascara_credito_cartao(df, cartao, cartao_legado="C6 BRU"):
    """Seleciona compras no credito do cartao.

    Antes de o campo ``banco`` existir nos gastos semanais, as compras no
    credito eram salvas em branco. Apenas nesse legado, branco pertence ao
    cartao padrao C6 BRU; novos registros sempre gravam o cartao explicitamente.
    """
    fp = df.get("forma_pagamento", pd.Series("", index=df.index)).astype(str).str.casefold()
    banco = df.get("banco", pd.Series("", index=df.index)).astype(str).str.strip().str.casefold()
    alvo = str(cartao).strip().casefold()
    eh_credito = fp.str.contains("crédito|credito", regex=True, na=False)
    eh_cartao = banco.eq(alvo)
    if alvo == str(cartao_legado).strip().casefold():
        eh_cartao = eh_cartao | banco.eq("")
    return eh_credito & eh_cartao


def aplicar_edicoes_semanais(df_completo, editado):
    """Aplica edição/exclusão de uma tabela semanal usando o ID estável."""
    full = df_completo.copy()
    ids_excluir = set(
        editado.loc[editado.get("Excluir", False) == True, "id"].astype(str)
    ) if "Excluir" in editado.columns else set()
    campos = ["data", "descricao", "categoria", "valor", "forma_pagamento", "banco"]
    for _, row in editado.iterrows():
        rid = str(row.get("id", ""))
        if not rid or rid in ids_excluir:
            continue
        mask = full["id"].astype(str).eq(rid)
        if not mask.any():
            continue
        for campo in campos:
            if campo not in row.index:
                continue
            valor = row[campo]
            if campo == "data":
                valor = pd.Timestamp(valor).strftime("%Y-%m-%d") if pd.notna(valor) else ""
            elif campo == "valor":
                valor = round(float(valor), 2)
            else:
                valor = str(valor)
            full.loc[mask, campo] = valor
        if "forma_pagamento" in row.index and "crédito" not in str(row["forma_pagamento"]).casefold():
            full.loc[mask, "banco"] = ""
    if ids_excluir:
        full = full[~full["id"].astype(str).isin(ids_excluir)].copy()
    return full, len(ids_excluir)
