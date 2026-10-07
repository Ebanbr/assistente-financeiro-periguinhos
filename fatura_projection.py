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


def faturas_encerradas(df_fechamentos, cartao):
    """{(ano, mes) da fatura encerrada: último dia que entrou nela}.

    O registro (ano, mes, dia) de ``fechamentos_fatura`` diz que a fatura do mês
    anterior fechou naquele dia (o ciclo (ano, mes) começa no dia seguinte).
    ``encerrada_em`` (ISO) é gravado pelo botão de encerrar; registros antigos só
    têm ``dia`` e valem como encerramento no mês anterior.
    """
    if df_fechamentos is None or df_fechamentos.empty:
        return {}
    d = df_fechamentos[
        df_fechamentos["cartao"].astype(str).str.strip().str.casefold().eq(str(cartao).strip().casefold())
    ]
    encerradas = {}
    for _, r in d.iterrows():
        ano, mes = pd.to_numeric(r.get("ano"), errors="coerce"), pd.to_numeric(r.get("mes"), errors="coerce")
        if pd.isna(ano) or pd.isna(mes):
            continue
        anterior = pd.Timestamp(year=int(ano), month=int(mes), day=1) - pd.DateOffset(months=1)
        enc = pd.to_datetime(str(r.get("encerrada_em", "")).strip(), format="%Y-%m-%d", errors="coerce")
        if pd.isna(enc):
            dia = pd.to_numeric(r.get("dia"), errors="coerce")
            if pd.isna(dia):
                continue
            try:
                enc = pd.Timestamp(year=int(anterior.year), month=int(anterior.month), day=int(dia))
            except ValueError:
                continue
        encerradas[(int(anterior.year), int(anterior.month))] = enc.date()
    return encerradas


def inicio_ciclo_aberto(encerradas):
    """Primeiro dia após o último encerramento; ``None`` se nunca encerrou."""
    return max(encerradas.values()) + timedelta(days=1) if encerradas else None


def lancamentos_semanais_fatura(df, cartao, inicio, fim, fonte="Semanal"):
    """Gastos lançados à mão no crédito do cartão dentro de [inicio, fim].

    Mesmo formato de ``semanas_fatura_importada``: serve para mostrar uma fatura
    já encerrada enquanto o arquivo dela ainda não foi importado.
    """
    if df is None or df.empty or "data" not in df.columns:
        return {"semanas": pd.DataFrame(), "fora": pd.DataFrame(), "total": 0.0}
    d = df[df.get("fonte", pd.Series("", index=df.index)).astype(str).eq(fonte)
           & mascara_credito_cartao(df, cartao)].copy()
    d["_compra"] = pd.to_datetime(d["data"], errors="coerce").dt.date
    d = d[d["_compra"].apply(lambda x: pd.notna(x) and inicio <= x <= fim)].copy()
    d["_valor"] = pd.to_numeric(d.get("valor"), errors="coerce").fillna(0)
    d["_inicio_semana"] = d["_compra"].apply(inicio_semana)
    return {"semanas": d.sort_values("_compra"), "fora": pd.DataFrame(), "total": float(d["_valor"].sum())}


def fatura_aberta(encerradas, hoje, dia_fechamento=4):
    """Fatura em andamento: a seguinte à última encerrada pelo usuário.

    Sem nenhum encerramento manual, cai na regra automática do dia de fechamento.
    """
    if not encerradas:
        return competencia_fatura(hoje, dia_fechamento)
    ano, mes = max(encerradas)
    prox = pd.Timestamp(year=ano, month=mes, day=1) + pd.DateOffset(months=1)
    return int(prox.year), int(prox.month)


def janela_semana(seg, dom, referencia, datas_encerramento):
    """Recorta a semana seg–dom no encerramento da fatura.

    O dia do encerramento pertence ao ciclo antigo; o seguinte já começa zerado.
    Retorna (inicio, fim) do trecho da semana que contém ``referencia``.
    """
    inicio, fim = seg, dom
    for enc in datas_encerramento:
        if not (seg <= enc < dom):
            continue
        if referencia > enc:
            inicio = max(inicio, enc + timedelta(days=1))
        else:
            fim = min(fim, enc)
    return inicio, fim


def data_compra_fatura(df):
    """Data real da compra de linhas importadas da fatura (dd/mm/aaaa).

    Importações novas gravam ``data_compra``; as antigas só têm "Compra em ..."
    na observação.
    """
    dc = df.get("data_compra", pd.Series("", index=df.index)).astype(str).str.strip()
    dc = dc.where(~dc.isin(["", "nan", "None"]), "")
    obs = df.get("observacao", pd.Series("", index=df.index)).astype(str)
    dc = dc.where(dc.ne(""), obs.str.extract(r"Compra em\s+(\S+)", expand=False).fillna(""))
    br = pd.to_datetime(dc, format="%d/%m/%Y", errors="coerce")
    iso = pd.to_datetime(dc, format="%Y-%m-%d", errors="coerce")
    return br.fillna(iso)


def meses_fatura_importados(df, cartao):
    """[(ano, mes)] das faturas do cartão importadas do C6, mais recente primeiro."""
    d = _linhas_fatura_importada(df, cartao)
    if d.empty:
        return []
    meses = pd.to_datetime(d["data"], errors="coerce").dropna()
    return sorted({(int(x.year), int(x.month)) for x in meses}, reverse=True)


def _linhas_fatura_importada(df, cartao):
    if df is None or df.empty or "data" not in df.columns:
        return pd.DataFrame()
    fonte = df.get("fonte", pd.Series("", index=df.index)).astype(str)
    banco = df.get("banco", pd.Series("", index=df.index)).astype(str).str.strip().str.casefold()
    return df[(fonte == "C6 Bank") & banco.eq(str(cartao).strip().casefold())]


def ciclo_fatura_importada(df, ano, mes, cartao):
    """(inicio, fim) reais do ciclo, lidos das próprias faturas importadas.

    O fechamento do C6 varia (dia 28 a 2), então o fim é a última compra da
    fatura e o início é o dia seguinte à última compra da fatura anterior.
    Sem a anterior importada, assume um mês antes do fim. ``None`` se não há
    datas de compra.
    """
    d = _linhas_fatura_importada(df, cartao)
    if d.empty:
        return None
    mes_fat = pd.to_datetime(d["data"], errors="coerce").dt.to_period("M")
    compra = data_compra_fatura(d)
    alvo = pd.Period(year=int(ano), month=int(mes), freq="M")
    fim = compra[mes_fat == alvo].max()
    if pd.isna(fim):
        return None
    fim_anterior = compra[mes_fat == alvo - 1].max()
    if pd.isna(fim_anterior):
        fim_anterior = fim - pd.DateOffset(months=1)
    return (fim_anterior + pd.Timedelta(days=1)).date(), fim.date()


def semanas_fatura_importada(df, ano, mes, cartao, inicio, fim):
    """Separa a fatura importada (ano, mes) em semanas pela data da compra.

    Compras dentro do ciclo [inicio, fim] ganham ``_inicio_semana`` (segunda);
    as demais (parcelas de compras antigas, compras lançadas com atraso) vão
    para ``fora``. ``semanas`` + ``fora`` somam a fatura inteira.
    """
    d = _linhas_fatura_importada(df, cartao).copy()
    if not d.empty:
        dt = pd.to_datetime(d["data"], errors="coerce")
        d = d[(dt.dt.year == int(ano)) & (dt.dt.month == int(mes))].copy()
    if d.empty:
        return {"semanas": pd.DataFrame(), "fora": pd.DataFrame(), "total": 0.0}
    d["_valor"] = pd.to_numeric(d.get("valor"), errors="coerce").fillna(0)
    d["_compra"] = data_compra_fatura(d).dt.date
    no_ciclo = d["_compra"].apply(lambda x: pd.notna(x) and inicio <= x <= fim)
    semanas = d[no_ciclo].copy()
    semanas["_inicio_semana"] = semanas["_compra"].apply(inicio_semana)
    return {
        "semanas": semanas.sort_values("_compra"),
        "fora": d[~no_ciclo].sort_values("_compra", na_position="first"),
        "total": float(d["_valor"].sum()),
    }


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
