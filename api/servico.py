"""Regras da API do app do celular: semana, lançamentos e cupom fiscal.

Mesmas regras da página 📆 Gastos Semanais — reaproveita fatura_projection, cupom_fiscal e
expense_defaults. ``planilha`` é qualquer objeto com ler/anexar/atualizar/excluir (nos testes,
uma planilha em memória).
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from config import CATEGORIAS_DESPESA, COLUNAS_CUPONS_PENDENTES, COLUNAS_ITENS_CUPOM
from cupom_fiscal import (CATEGORIAS_CUPOM, NotaPendente, NotaSemItens, agrupar_compras,
                          agrupar_por_categoria, cupons_aguardando, ja_lancado, ler_cupom,
                          linhas_pendentes, marca_pendente, nome_lembrado, sugerir_categorias)
from dados import gerar_id
from expense_defaults import categoria_do_local
from fatura_projection import (faturas_encerradas, inicio_ciclo_aberto, inicio_semana, janela_semana,
                               resumo_categorias)

FONTE_SEMANAL = "Semanal"
CARTAO_FATURA = "C6 BRU"          # cartão cujo encerramento recorta a semana (como na página)
FORMAS = ["💳 Crédito", "💳 Débito", "📱 PIX", "💵 Dinheiro"]
CARTOES = ["C6 BRU", "C6 PRI", "Nubank"]
DIAS_NOME = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
_FUSO = ZoneInfo("America/Recife")


class ErroDeUso(ValueError):
    """Pedido inválido: a mensagem vai direto para a tela do app."""


class Duplicado(ErroDeUso):
    pass


def hoje():
    return datetime.now(_FUSO).date()


def agora():
    return datetime.now(_FUSO).replace(tzinfo=None).isoformat()


def _texto(v):
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)


def _semanais(despesas):
    if despesas.empty or "fonte" not in despesas.columns:
        return despesas.iloc[0:0]
    return despesas[despesas["fonte"].astype(str).eq(FONTE_SEMANAL)]


# ── Opções ───────────────────────────────────────────────────────

def categorias(planilha):
    cats = set(CATEGORIAS_DESPESA)
    for tabela in ("despesas", "mapeamentos"):
        df = planilha.ler(tabela)
        if "categoria" in df.columns:
            cats.update(c for c in df["categoria"].dropna().astype(str).str.strip() if c)
    return sorted(cats)


def opcoes(planilha):
    cats = categorias(planilha)
    return {
        "categorias": cats,
        "categorias_cupom": list(dict.fromkeys(CATEGORIAS_CUPOM + cats)),
        "formas": FORMAS,
        "cartoes": CARTOES,
    }


def sugestao(planilha, descricao):
    return categoria_do_local(descricao, planilha.ler("despesas"), categorias(planilha))


# ── Semana ───────────────────────────────────────────────────────

def _limite(planilha, seg):
    df = planilha.ler("limites_semanais")
    if df.empty or "chave" not in df.columns:
        return 0.0
    chave = df["chave"].astype(str)
    valor = pd.to_numeric(df.get("valor"), errors="coerce")
    for alvo in (seg.isoformat(), "padrao"):
        achado = valor[chave.eq(alvo)].dropna()
        if not achado.empty:
            return float(achado.iloc[-1])
    return 0.0


def _encerradas(planilha):
    df = planilha.ler("fechamentos_fatura")
    if df.empty:
        return {}
    for col in ("ano", "mes", "dia"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "cartao" not in df.columns:
        return {}
    return faturas_encerradas(df, CARTAO_FATURA)


def _linha_json(r):
    return {
        "id": _texto(r.get("id")), "data": _texto(r.get("data")), "descricao": _texto(r.get("descricao")),
        "categoria": _texto(r.get("categoria")), "valor": round(float(r.get("valor") or 0), 2),
        "forma_pagamento": _texto(r.get("forma_pagamento")), "banco": _texto(r.get("banco")),
        "observacao": _texto(r.get("observacao")), "lancado_por": _texto(r.get("lancado_por")),
    }


def _compras_json(gastos, itens):
    compras = []
    for compra in agrupar_compras(gastos):
        linhas = compra["linhas"]
        itens_c = (itens[itens["despesa_id"].astype(str).isin(linhas["id"].astype(str))]
                   if compra["chave"] and not itens.empty else itens.iloc[0:0])
        cats = []
        for _, r in linhas.sort_values("valor", ascending=False).iterrows():
            prods = itens_c[itens_c["despesa_id"].astype(str) == str(r["id"])] if not itens_c.empty else itens_c
            cats.append({
                "id": _texto(r.get("id")), "categoria": _texto(r.get("categoria")),
                "valor": round(float(r["valor"]), 2),
                "itens": [{
                    "descricao": _texto(it.get("descricao")),
                    "quantidade": float(pd.to_numeric(it.get("quantidade"), errors="coerce") or 0),
                    "unidade": _texto(it.get("unidade")),
                    "valor": round(float(pd.to_numeric(it.get("valor"), errors="coerce") or 0), 2),
                } for _, it in prods.iterrows()],
            })
        compras.append({
            "chave": compra["chave"], "nome": compra["nome"], "total": compra["total"],
            "cupom": bool(compra["chave"]),
            "itens_pendentes": any("itens pendentes" in _texto(o) for o in linhas.get("observacao", [])),
            "forma_pagamento": " / ".join(dict.fromkeys(linhas["forma_pagamento"].astype(str))),
            "lancado_por": " / ".join(dict.fromkeys(x for x in linhas.get("lancado_por", pd.Series(dtype=str))
                                                    .fillna("").astype(str) if x)),
            "linhas": [_linha_json(r) for _, r in linhas.iterrows()],
            "categorias": cats,
        })
    return compras


def semana(planilha, referencia=None):
    """Semana seg–dom de ``referencia`` (recortada no encerramento da fatura), dia a dia."""
    ref = referencia or hoje()
    seg = inicio_semana(ref)
    dom = seg + timedelta(days=6)
    encerradas = _encerradas(planilha)
    ini, fim = janela_semana(seg, dom, ref, list(encerradas.values()))
    inicio_aberto = inicio_ciclo_aberto(encerradas)
    encerrada = inicio_aberto is not None and fim < inicio_aberto

    gastos = _semanais(planilha.ler("despesas"))
    if not gastos.empty:
        dias = pd.to_datetime(gastos["data"], errors="coerce").dt.date
        gastos = gastos[dias.apply(lambda d: pd.notna(d) and ini <= d <= fim)].copy()
        gastos["_dia"] = pd.to_datetime(gastos["data"], errors="coerce").dt.date
    if encerrada:
        gastos = gastos.iloc[0:0]
    itens = planilha.ler("itens_cupom")
    if "despesa_id" not in itens.columns:
        itens = pd.DataFrame(columns=COLUNAS_ITENS_CUPOM)

    total = round(float(gastos["valor"].sum()), 2) if not gastos.empty else 0.0
    limite = _limite(planilha, seg)
    dias_json = []
    if not gastos.empty:
        for dia in sorted(gastos["_dia"].dropna().unique(), reverse=True):
            sub = gastos[gastos["_dia"] == dia]
            dias_json.append({
                "data": dia.isoformat(), "nome": DIAS_NOME[dia.weekday()],
                "total": round(float(sub["valor"].sum()), 2),
                "compras": _compras_json(sub, itens),
            })
    resumo = resumo_categorias(gastos) if not gastos.empty else resumo_categorias(pd.DataFrame())
    return {
        "inicio": ini.isoformat(), "fim": fim.isoformat(), "recortada": (ini, fim) != (seg, dom),
        "encerrada": encerrada, "limite": limite, "total": total,
        "restante": round(max(limite - total, 0), 2) if limite > 0 else None,
        "dias": dias_json,
        "resumo": [{"categoria": r.categoria, "valor": float(r.valor), "pct": float(r.pct)}
                   for r in resumo.itertuples()],
    }


# ── Lançar / editar / excluir gasto ──────────────────────────────

def _validar_gasto(dados, cats):
    descricao = _texto(dados.get("descricao")).strip()
    categoria = _texto(dados.get("categoria")).strip()
    forma = _texto(dados.get("forma_pagamento")).strip()
    try:
        valor = round(float(dados.get("valor")), 2)
    except (TypeError, ValueError):
        raise ErroDeUso("Informe o valor.")
    try:
        dia = date.fromisoformat(_texto(dados.get("data")) or hoje().isoformat())
    except ValueError:
        raise ErroDeUso("Data inválida.")
    if not descricao:
        raise ErroDeUso("Informe a descrição.")
    if categoria not in cats:
        raise ErroDeUso("Escolha a categoria.")
    if forma not in FORMAS:
        raise ErroDeUso("Escolha a forma de pagamento.")
    if valor == 0:
        raise ErroDeUso("O valor não pode ser zero (estorno entra negativo).")
    if dia > hoje():
        raise ErroDeUso("A data não pode ser no futuro.")
    banco = _texto(dados.get("banco")).strip() if forma == "💳 Crédito" else ""
    if forma == "💳 Crédito" and banco not in CARTOES:
        raise ErroDeUso("Escolha o cartão.")
    return {"data": dia.isoformat(), "descricao": descricao, "categoria": categoria, "valor": valor,
            "forma_pagamento": forma, "banco": banco}


def _ja_existe(despesas, data, descricao, valor):
    if despesas.empty:
        return False
    return bool((despesas["data"].astype(str).eq(data)
                 & despesas["descricao"].astype(str).eq(descricao)
                 & despesas["valor"].astype(float).round(2).eq(round(valor, 2))).any())


def lancar_gasto(planilha, dados, usuario):
    campos = _validar_gasto(dados, categorias(planilha))
    if _ja_existe(planilha.ler("despesas", fresca=True), campos["data"], campos["descricao"], campos["valor"]):
        raise Duplicado("Esse gasto já parece estar lançado (mesma data, descrição e valor).")
    linha = {"id": gerar_id(), **campos, "status": "Pago", "observacao": "", "fonte": FONTE_SEMANAL,
             "criado_em": agora(), "lancado_por": usuario}
    planilha.anexar("despesas", [linha])
    return linha


def _gasto_semanal(planilha, id_gasto):
    despesas = planilha.ler("despesas", fresca=True)
    achado = despesas[despesas["id"].astype(str).eq(str(id_gasto))] if not despesas.empty else despesas
    if achado.empty:
        raise ErroDeUso("Gasto não encontrado (pode ter sido excluído no PC).")
    if _texto(achado.iloc[0].get("fonte")) != FONTE_SEMANAL:
        raise ErroDeUso("Só dá para mexer pelo app nos gastos lançados à mão.")
    return achado.iloc[0]


def editar_gasto(planilha, id_gasto, dados):
    atual = _gasto_semanal(planilha, id_gasto)
    base = {k: atual.get(k) for k in ("data", "descricao", "categoria", "valor", "forma_pagamento", "banco")}
    base.update({k: v for k, v in dados.items() if v is not None})
    campos = _validar_gasto(base, categorias(planilha))
    planilha.atualizar("despesas", "id", str(id_gasto), campos)
    return {**_linha_json(atual), **campos}


def excluir_gasto(planilha, id_gasto):
    _gasto_semanal(planilha, id_gasto)
    return planilha.excluir("despesas", "id", [str(id_gasto)])


# ── Cupom fiscal ─────────────────────────────────────────────────

_LIDOS = {}   # chave → (instante, cupom lido): o lançamento usa o que foi lido, sem baixar de novo


def _itens_hist(planilha):
    itens = planilha.ler("itens_cupom")
    return itens if "despesa_id" in itens.columns else pd.DataFrame(columns=COLUNAS_ITENS_CUPOM)


def _linha_pendente(chave, despesas):
    pend = despesas[linhas_pendentes(chave, despesas)] if not despesas.empty else despesas
    return None if pend.empty else pend.iloc[0]


def ler_cupom_qr(planilha, link, leitor=ler_cupom):
    """Lê o QR. Devolve status ``ok`` (itens com categoria sugerida), ``pendente`` (nota offline
    que a SEFAZ ainda não recebeu) ou ``sem_itens`` (SEFAZ não devolve os itens desse QR)."""
    despesas = planilha.ler("despesas", fresca=True)
    hist = _itens_hist(planilha)
    try:
        cupom = leitor(link)
    except NotaPendente as e:
        d = e.dados
        return {"status": "pendente", "mensagem": str(e), "chave": d["chave"], "data": d["data"],
                "total": d["total"], "cnpj": d["cnpj"], "link": d["link"],
                "estabelecimento": nome_lembrado(d["cnpj"], hist) or "",
                "ja_lancado": bool(linhas_pendentes(d["chave"], despesas).any() or ja_lancado(d["chave"], despesas))}
    except NotaSemItens as e:
        d = e.dados
        return {"status": "sem_itens", "mensagem": str(e), "chave": d["chave"], "data": d["data"],
                "total": d["total"], "ja_lancado": bool(ja_lancado(d["chave"], despesas))}
    except ValueError as e:
        raise ErroDeUso(str(e))

    cats = opcoes(planilha)["categorias_cupom"]
    itens = cupom["itens"].copy()
    itens["categoria"] = sugerir_categorias(itens, hist, cats)
    _LIDOS[cupom["chave"]] = cupom
    pend = _linha_pendente(cupom["chave"], despesas)
    return {
        "status": "ok", "chave": cupom["chave"], "data": cupom["data"], "total": cupom["total"],
        "cnpj": cupom["cnpj"],
        "estabelecimento": nome_lembrado(cupom["cnpj"], hist) or cupom["estabelecimento"].title(),
        "forma_pagamento": (_texto(pend["forma_pagamento"]) if pend is not None else cupom["forma_pagamento"]),
        "banco": _texto(pend["banco"]) if pend is not None else "",
        "ja_lancado": bool(ja_lancado(cupom["chave"], despesas)),
        "substitui_total": pend is not None,
        "itens": [{"item": int(r.item), "descricao": r.descricao, "quantidade": float(r.quantidade),
                   "unidade": r.unidade, "valor": float(r.valor), "categoria": r.categoria}
                  for r in itens.itertuples()],
    }


def lancar_cupom(planilha, pedido, usuario, leitor=ler_cupom):
    """Grava o cupom lido: uma linha por categoria + item a item. Se o cupom já estava lançado
    só com o total (nota offline), troca essa linha pela divisão."""
    chave = _texto(pedido.get("chave"))
    cupom = _LIDOS.get(chave)
    if cupom is None:
        if not pedido.get("link"):
            raise ErroDeUso("Leia o QR Code de novo.")
        cupom = leitor(pedido["link"])
        _LIDOS[cupom["chave"]] = cupom
        chave = cupom["chave"]
    estab = _texto(pedido.get("estabelecimento")).strip()
    forma = _texto(pedido.get("forma_pagamento")).strip()
    banco = _texto(pedido.get("banco")).strip() if forma == "💳 Crédito" else ""
    cats_validas = opcoes(planilha)["categorias_cupom"]
    por_item = {int(k): v for k, v in (pedido.get("categorias") or {}).items()}
    if not estab:
        raise ErroDeUso("Informe o estabelecimento.")
    if forma not in FORMAS:
        raise ErroDeUso("Escolha a forma de pagamento.")
    if forma == "💳 Crédito" and banco not in CARTOES:
        raise ErroDeUso("Escolha o cartão.")
    data = pd.to_datetime(cupom["data"], errors="coerce")
    if pd.isna(data) or data.date() > hoje():
        raise ErroDeUso("A data do cupom é inválida.")

    itens = cupom["itens"].copy()
    hist = _itens_hist(planilha)
    itens["categoria"] = sugerir_categorias(itens, hist, cats_validas)
    for i, cat in por_item.items():
        if cat not in cats_validas:
            raise ErroDeUso(f"Categoria inválida: {cat}")
        itens.loc[itens["item"] == i, "categoria"] = cat

    despesas = planilha.ler("despesas", fresca=True)
    if ja_lancado(chave, despesas):
        raise Duplicado("Esse cupom já foi lançado.")
    pend = _linha_pendente(chave, despesas)

    criado, dia = agora(), data.strftime("%Y-%m-%d")
    por_cat = agrupar_por_categoria(itens, cupom["total"])
    ids_cat = {cat: gerar_id() for cat in por_cat.index}
    linhas = [{
        "id": ids_cat[cat], "data": dia, "descricao": f"{estab} · {cat}", "categoria": cat,
        "valor": round(float(valor), 2), "forma_pagamento": forma, "banco": banco, "status": "Pago",
        "observacao": f"NFC-e {chave}", "fonte": FONTE_SEMANAL, "criado_em": criado, "lancado_por": usuario,
    } for cat, valor in por_cat.items()]
    planilha.anexar("despesas", linhas)
    if pend is not None:
        planilha.excluir("despesas", "id", [_texto(pend["id"])])

    novos = itens.assign(
        id=[gerar_id() for _ in range(len(itens))], chave=chave, data=dia, estabelecimento=estab,
        cnpj=cupom["cnpj"], despesa_id=itens["categoria"].map(ids_cat), criado_em=criado,
    )[COLUNAS_ITENS_CUPOM]
    planilha.excluir("itens_cupom", "chave", [chave])   # relançamento troca os itens antigos
    planilha.anexar("itens_cupom", novos.to_dict("records"))
    _LIDOS.pop(chave, None)
    return {"linhas": len(linhas), "total": round(float(por_cat.sum()), 2), "estabelecimento": estab}


def lancar_cupom_so_total(planilha, pedido, usuario, leitor_offline=None):
    """Nota offline: lança já só com o total e guarda o link para buscar os itens depois."""
    from cupom_fiscal import dados_do_qr_offline
    dados = (leitor_offline or dados_do_qr_offline)(_texto(pedido.get("link")))
    if not dados:
        raise ErroDeUso("Esse QR Code não é de nota offline.")
    estab = _texto(pedido.get("estabelecimento")).strip()
    categoria = _texto(pedido.get("categoria")).strip() or "🛒 Supermercado"
    forma = _texto(pedido.get("forma_pagamento")).strip()
    banco = _texto(pedido.get("banco")).strip() if forma == "💳 Crédito" else ""
    if not estab:
        raise ErroDeUso("Informe o estabelecimento.")
    if categoria not in categorias(planilha):
        raise ErroDeUso("Escolha a categoria.")
    if forma not in FORMAS:
        raise ErroDeUso("Escolha a forma de pagamento.")
    if forma == "💳 Crédito" and banco not in CARTOES:
        raise ErroDeUso("Escolha o cartão.")
    despesas = planilha.ler("despesas", fresca=True)
    if linhas_pendentes(dados["chave"], despesas).any() or ja_lancado(dados["chave"], despesas):
        raise Duplicado("Esse cupom já está lançado.")
    criado = agora()
    planilha.anexar("despesas", [{
        "id": gerar_id(), "data": dados["data"], "descricao": estab, "categoria": categoria,
        "valor": dados["total"], "forma_pagamento": forma, "banco": banco, "status": "Pago",
        "observacao": marca_pendente(dados["chave"]), "fonte": FONTE_SEMANAL, "criado_em": criado,
        "lancado_por": usuario,
    }])
    planilha.anexar("cupons_pendentes", [dict(zip(COLUNAS_CUPONS_PENDENTES, [
        gerar_id(), dados["chave"], dados["link"], dados["data"], estab, dados["total"], criado]))])
    return {"total": dados["total"], "estabelecimento": estab}


def cupons_esperando(planilha):
    pend = planilha.ler("cupons_pendentes")
    aguardando = cupons_aguardando(pend, planilha.ler("despesas"))
    return [{"chave": _texto(r.get("chave")), "link": _texto(r.get("link")), "data": _texto(r.get("data")),
             "estabelecimento": _texto(r.get("estabelecimento")),
             "valor": round(float(pd.to_numeric(r.get("valor"), errors="coerce") or 0), 2)}
            for _, r in aguardando.iterrows()]


def ficar_so_com_total(planilha, chave):
    """A SEFAZ não devolve os itens desse QR: a linha deixa de esperar e fica só com o total."""
    n = planilha.atualizar("despesas", "observacao", marca_pendente(chave), {"observacao": f"NFC-e {chave}"})
    if not n:
        raise ErroDeUso("Esse cupom não está esperando a SEFAZ.")
    return n
