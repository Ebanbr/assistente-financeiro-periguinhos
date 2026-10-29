"""Cupom fiscal (NFC-e) lido pelo link do QR Code — hoje só SEFAZ-PE.

O link do QR (`http://nfce.sefaz.pe.gov.br/nfce/consulta?p=...`) devolve o XML
completo da nota, sem CAPTCHA. Tudo aqui é função pura, exceto `baixar_xml`.
"""
import re
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlsplit

import pandas as pd

from expense_defaults import categoria_do_local

NS = {"n": "http://www.portalfiscal.inf.br/nfe"}
HOSTS_PERMITIDOS = ("nfce.sefaz.pe.gov.br",)

CATEGORIA_PADRAO_CUPOM = "🛒 Supermercado"

# Categorias de item propostas para o cupom (o Bruno pode trocar à vontade).
CATEGORIAS_CUPOM = [
    "🥬 Hortifruti",
    "🥩 Carnes e Peixes",
    "🧀 Frios e Laticínios",
    "🥖 Padaria",
    "🥫 Mercearia",
    "🥤 Bebidas",
    "🧽 Limpeza",
    "🧴 Higiene e Beleza",
    "🐾 Pets",
    "💊 Saúde - Farmácia",
    "⛽Combustível",
    CATEGORIA_PADRAO_CUPOM,
]

# Prefixo do NCM → categoria. O prefixo mais longo vence.
_NCM_CATEGORIA = {
    "07": "🥬 Hortifruti", "08": "🥬 Hortifruti",
    "02": "🥩 Carnes e Peixes", "03": "🥩 Carnes e Peixes",
    "1601": "🥩 Carnes e Peixes", "1602": "🥩 Carnes e Peixes", "1604": "🥩 Carnes e Peixes",
    "04": "🧀 Frios e Laticínios", "0407": "🥫 Mercearia", "0409": "🥫 Mercearia",
    "1905": "🥖 Padaria",
    "09": "🥫 Mercearia", "10": "🥫 Mercearia", "11": "🥫 Mercearia", "12": "🥫 Mercearia",
    "15": "🥫 Mercearia", "17": "🥫 Mercearia", "18": "🥫 Mercearia", "19": "🥫 Mercearia",
    "20": "🥫 Mercearia", "21": "🥫 Mercearia",
    "22": "🥤 Bebidas", "2009": "🥤 Bebidas", "2207": "⛽Combustível", "2710": "⛽Combustível",
    "2309": "🐾 Pets",
    "3003": "💊 Saúde - Farmácia", "3004": "💊 Saúde - Farmácia", "3005": "💊 Saúde - Farmácia",
    "33": "🧴 Higiene e Beleza", "3401": "🧴 Higiene e Beleza", "4818": "🧴 Higiene e Beleza",
    "9603": "🧴 Higiene e Beleza", "9619": "🧴 Higiene e Beleza",
    "3402": "🧽 Limpeza", "3405": "🧽 Limpeza", "3808": "🧽 Limpeza",
}

# tPag da NFC-e → forma de pagamento do app (sem correspondência = o usuário escolhe)
_TPAG_FORMA = {"01": "💵 Dinheiro", "03": "💳 Crédito", "04": "💳 Débito", "17": "📱 PIX"}


def validar_link(link):
    """Devolve o link normalizado se for um QR Code de NFC-e conhecido; senão levanta ValueError."""
    # celular costuma copiar o link com o "|" codificado (%7C) e às vezes com espaço/quebra de linha
    link = re.sub(r"\s+", "", unquote(link or ""))
    # alguns caixas/leitores entregam ".../consultarNFCe<chave>|..." sem o "?p="
    link = re.sub(r"(consultar?NFCe|consulta)/?(\d{44}\|)", r"\1?p=\2", link, flags=re.I)
    if not link:
        raise ValueError("Cole o link do QR Code do cupom.")
    if not re.match(r"^https?://", link, re.I):
        link = "http://" + link
    partes = urlsplit(link)
    if (partes.hostname or "").lower() not in HOSTS_PERMITIDOS:
        raise ValueError("Por enquanto só leio cupons da SEFAZ-PE (nfce.sefaz.pe.gov.br).")
    if not re.search(r"[?&]p=\d{44}\|", link):
        raise ValueError("Esse link não parece ser de um QR Code de NFC-e (falta a chave de 44 dígitos).")
    return link


def chave_do_link(link):
    m = re.search(r"[?&]p=(\d{44})\|", unquote(link or ""))
    return m.group(1) if m else None


def link_do_qr(imagem):
    """Lê o QR Code de uma foto (bytes ou arquivo) e devolve o texto, ou None se não achar."""
    import zxingcpp
    from PIL import Image, ImageOps

    foto = ImageOps.exif_transpose(Image.open(imagem)).convert("L")
    # foto de celular é grande e o QR do cupom é pequeno: tenta inteira e reduzida
    tentativas = [foto]
    if max(foto.size) > 1600:
        escala = 1600 / max(foto.size)
        tentativas.append(foto.resize((int(foto.width * escala), int(foto.height * escala))))
    for img in tentativas:
        achados = zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.QRCode)
        textos = [a.text for a in achados if a.text]
        if textos:
            return next((t for t in textos if "sefaz" in t.lower()), textos[0])
    return None


def emitida_offline(link):
    """Chave com tipo de emissão 9 = contingência offline (o caixa estava sem SEFAZ)."""
    chave = chave_do_link(validar_link(link))
    return bool(chave) and chave[34] == "9"


class NotaPendente(ValueError):
    """Nota que a SEFAZ ainda não tem (236); `dados` traz o que o QR Code já informa.

    Nota offline: o QR traz data e total. Nota normal: só chave e CNPJ (`data`/`total` = None),
    e quem lança informa o total.
    """

    def __init__(self, dados):
        if dados.get("total") is None:
            texto = ("A SEFAZ ainda não liberou essa nota para consulta (às vezes leva algumas horas "
                     "depois da compra).")
        else:
            texto = ("Essa nota foi emitida com o caixa offline e a SEFAZ ainda não a recebeu "
                     "(o mercado tem até 24 horas para enviar).")
        super().__init__(texto)
        self.dados = dados


class NotaSemItens(ValueError):
    """A SEFAZ já tem a nota, mas responde erro 100 = "QR Code Inválido" (XSL da SEFAZ-PE) e não devolve os itens.

    (236 = "Nota não se encontra na base": ainda não chegou.)
    """

    def __init__(self, dados):
        super().__init__("A nota já chegou na SEFAZ, mas ela diz que o QR Code desse cupom é inválido "
                         "e não devolve os itens.")
        self.dados = dados


def _codigo_erro(xml_texto):
    m = re.search(r"<erro>\s*(\d+)\s*</erro>", xml_texto or "")
    return m.group(1) if m else None


def dados_do_qr_offline(link):
    """QR de contingência: chave|versão|ambiente|dia|valor|... → {chave, cnpj, data, total} ou None."""
    link = validar_link(link)
    chave = chave_do_link(link)
    campos = link.split("p=", 1)[1].split("|")
    if not chave or chave[34] != "9" or len(campos) < 5:
        return None
    try:
        dia, total = int(campos[3]), round(float(campos[4].replace(",", ".")), 2)
        data = pd.Timestamp(year=2000 + int(chave[2:4]), month=int(chave[4:6]), day=dia)
    except (ValueError, TypeError):
        return None
    return {"chave": chave, "cnpj": chave[6:20], "data": data.strftime("%Y-%m-%d"), "total": total,
            "link": link}


def dados_do_qr(link):
    """O que dá para lançar antes da SEFAZ ter a nota: offline → chave, CNPJ, data e total;
    normal → só chave e CNPJ (`data`/`total` = None)."""
    dados = dados_do_qr_offline(link)
    if dados:
        return dados
    link = validar_link(link)
    chave = chave_do_link(link)
    return {"chave": chave, "cnpj": chave[6:20], "data": None, "total": None, "link": link}


def ler_cupom(link):
    """Baixa e lê a nota. Nota que a SEFAZ ainda não tem (236, ou offline ainda não enviada)
    → NotaPendente; offline já autorizada mas sem itens pelo link (erro 100) → NotaSemItens."""
    link = validar_link(link)
    xml_texto = baixar_xml(link)
    try:
        return {**ler_nfce(xml_texto), "link": link}
    except ValueError:
        dados = dados_do_qr_offline(link)
        if dados and _codigo_erro(xml_texto) == "100":
            raise NotaSemItens(dados)
        if dados:
            raise NotaPendente(dados)
        if _codigo_erro(xml_texto) == "236":
            raise NotaPendente(dados_do_qr(link))
        raise


def chave_da_observacao(observacao):
    m = re.search(r"NFC-e (\d{44})", str(observacao or ""))
    return m.group(1) if m else None


def agrupar_compras(gastos):
    """Junta as linhas de um mesmo cupom numa compra só (na ordem em que aparecem).

    Devolve [{chave, nome, total, linhas}]; gasto avulso vira uma compra de uma linha (chave None).
    """
    compras, por_chave = [], {}
    for idx, linha in gastos.iterrows():
        chave = chave_da_observacao(linha.get("observacao"))
        if chave and chave in por_chave:
            por_chave[chave]["_idx"].append(idx)
            continue
        compra = {"chave": chave, "nome": str(linha.get("descricao", "")).split(" · ")[0].strip(), "_idx": [idx]}
        compras.append(compra)
        if chave:
            por_chave[chave] = compra
    for compra in compras:
        compra["linhas"] = gastos.loc[compra.pop("_idx")]
        compra["total"] = round(float(pd.to_numeric(compra["linhas"]["valor"], errors="coerce").fillna(0).sum()), 2)
    return compras


def concluir_pendente(chave, despesas):
    """Fica só com o total: a linha deixa de esperar os itens, mas continua marcada como do cupom."""
    despesas = despesas.copy()
    despesas.loc[linhas_pendentes(chave, despesas), "observacao"] = f"NFC-e {chave}"
    return despesas


def marca_pendente(chave):
    return f"NFC-e {chave} · itens pendentes"


def cupons_aguardando(pendentes, despesas):
    """Cupons lançados só com o total cuja linha ainda está na semana (esperando os itens da SEFAZ)."""
    if pendentes.empty or not {"chave", "link"}.issubset(pendentes.columns):
        return pendentes.iloc[0:0]
    marcas = set(despesas["observacao"].astype(str).str.strip()) if "observacao" in despesas.columns else set()
    ativos = pendentes[pendentes["chave"].astype(str).map(lambda c: marca_pendente(c) in marcas)]
    return ativos.drop_duplicates("chave", keep="last").reset_index(drop=True)


def linhas_pendentes(chave, despesas):
    """Máscara das linhas lançadas só com o total, à espera dos itens."""
    if not chave or despesas.empty or "observacao" not in despesas.columns:
        return pd.Series(False, index=despesas.index)
    return despesas["observacao"].astype(str).str.strip().eq(marca_pendente(chave))


def baixar_xml(link, timeout=30):
    import requests
    resposta = requests.get(validar_link(link), timeout=timeout)
    resposta.raise_for_status()
    return resposta.text


def _txt(no, caminho, padrao=""):
    achado = no.find(caminho, NS) if no is not None else None
    return (achado.text or "").strip() if achado is not None and achado.text else padrao


def _num(no, caminho):
    try:
        return float(_txt(no, caminho, "0").replace(",", "."))
    except ValueError:
        return 0.0


_COLUNAS_ITENS = ["item", "descricao", "ncm", "quantidade", "unidade", "valor", "desconto"]


def ratear_ao_total(itens, total, limite=0.5):
    """Acerta os itens ao total da nota quando a soma não bate.

    O desconto do item (ex.: "preço com CPF") já vem abatido em ``valor``. Se ainda sobrar diferença
    (desconto dado no fim da compra e não distribuído pelo caixa, acréscimo…), ela é rateada entre os
    itens proporcionalmente ao valor e somada à coluna ``desconto`` (desconto positivo = abatimento).
    Diferença maior que ``limite`` (50% da soma) não é rateada: aí a nota está estranha e o aviso de
    "soma não bate" continua aparecendo.
    """
    itens = itens.copy()
    if "desconto" not in itens.columns:
        itens["desconto"] = 0.0
    itens["desconto"] = pd.to_numeric(itens["desconto"], errors="coerce").fillna(0.0)
    soma = round(float(itens["valor"].sum()), 2)
    diferenca = round(float(total) - soma, 2)
    if itens.empty or not diferenca or soma <= 0 or abs(diferenca) > soma * limite:
        return itens
    centavos = round(diferenca * 100)
    partes = [int(centavos * v / soma) for v in itens["valor"]]          # trunca em direção a zero
    sobra = centavos - sum(partes)
    maior = int(itens["valor"].to_numpy().argmax())
    partes[maior] += sobra                                               # o arredondamento fica no maior item
    ajuste = pd.Series(partes, index=itens.index) / 100
    itens["valor"] = (itens["valor"] + ajuste).round(2)
    itens["desconto"] = (itens["desconto"] - ajuste).round(2)
    return itens


def ler_nfce(xml_texto):
    """XML da NFC-e → {chave, data, estabelecimento, cnpj, total, forma_pagamento, itens(DataFrame)}."""
    try:
        raiz = ET.fromstring(xml_texto.encode("utf-8") if isinstance(xml_texto, str) else xml_texto)
    except ET.ParseError:
        raise ValueError("A SEFAZ não devolveu a nota (resposta inválida). Tente de novo em instantes.")
    inf = raiz.find(".//n:infNFe", NS)
    if inf is None:
        erro = _txt(raiz, "n:erro") or "nota não encontrada"
        raise ValueError(f"A SEFAZ não devolveu a nota: {erro}.")

    emit = inf.find("n:emit", NS)
    nome = _txt(emit, "n:xFant") or _txt(emit, "n:xNome")
    data_hora = _txt(inf, "n:ide/n:dhEmi")

    itens = []
    for det in inf.findall("n:det", NS):
        prod = det.find("n:prod", NS)
        bruto = _num(prod, "n:vProd")
        liquido = bruto - _num(prod, "n:vDesc") + _num(prod, "n:vOutro") + _num(prod, "n:vFrete") + _num(prod, "n:vSeg")
        itens.append({
            "item": int(det.get("nItem", len(itens) + 1)),
            "descricao": " ".join(_txt(prod, "n:xProd").split()),
            "ncm": _txt(prod, "n:NCM"),
            "quantidade": _num(prod, "n:qCom"),
            "unidade": _txt(prod, "n:uCom"),
            "valor": round(liquido, 2),
            "desconto": round(_num(prod, "n:vDesc"), 2),
        })

    pagamentos = [(_txt(d, "n:tPag"), _num(d, "n:vPag")) for d in inf.findall("n:pag/n:detPag", NS)]
    tpag = max(pagamentos, key=lambda p: p[1])[0] if pagamentos else ""

    chave = (inf.get("Id") or "").removeprefix("NFe")
    total = round(_num(inf, "n:total/n:ICMSTot/n:vNF"), 2)
    itens = ratear_ao_total(pd.DataFrame(itens, columns=_COLUNAS_ITENS), total)
    return {
        "chave": chave,
        "data": data_hora[:10],
        "estabelecimento": " ".join(nome.split()),
        "cnpj": _txt(emit, "n:CNPJ"),
        "total": total,
        "desconto": round(float(itens["desconto"].sum()), 2),
        "forma_pagamento": _TPAG_FORMA.get(tpag),
        "itens": itens,
    }


# ── Página da consulta pela chave (quem consulta resolve o reCAPTCHA no site da SEFAZ) ──
# Nota de contingência já autorizada: o link do QR responde erro 100 e não traz os itens, mas a
# consulta completa pela chave (com o "Não sou um robô" feito pela pessoa) mostra a nota inteira
# numa página HTML. Aqui só lemos essa página; nada é enviado à SEFAZ.

URL_CONSULTA_CHAVE = "https://nfce.sefaz.pe.gov.br:444/nfce-web/entradaConsNfce?tp=C"


class _No:
    def __init__(self, tag, attrs):
        self.tag, self.attrs, self.filhos, self.texto = tag, dict(attrs), [], []

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def todos(self):
        for f in self.filhos:
            yield f
            yield from f.todos()

    def texto_todo(self):
        partes = list(self.texto) + [f.texto_todo() for f in self.filhos]
        return " ".join(" ".join(partes).replace("\xa0", " ").split())


def _arvore(html):
    from html.parser import HTMLParser

    vazias = {"meta", "link", "br", "img", "input", "hr", "base", "col", "source", "wbr"}
    raiz = _No("raiz", [])
    pilha = [raiz]

    class Leitor(HTMLParser):
        def handle_starttag(self, tag, attrs):
            no = _No(tag, attrs)
            pilha[-1].filhos.append(no)
            if tag not in vazias:
                pilha.append(no)

        def handle_endtag(self, tag):
            for i in range(len(pilha) - 1, 0, -1):   # fecha até a tag (HTML mal fechado não quebra)
                if pilha[i].tag == tag:
                    del pilha[i:]
                    break

        def handle_data(self, data):
            pilha[-1].texto.append(data)

    Leitor(convert_charrefs=True).feed(html)
    return raiz


def _pares(no):
    """[(rótulo, valor)] dos blocos "form-group": <label>rótulo</label><label|textarea>valor</…>."""
    pares = []
    for g in [no] + list(no.todos()):
        if "form-group" in g.classes():
            campos = [f for f in g.filhos if f.tag in ("label", "textarea")]
            if len(campos) >= 2:
                pares.append((campos[0].texto_todo(), campos[1].texto_todo()))
    return pares


def _valor(pares, rotulo):
    return next((v for r, v in pares if r == rotulo), "")


def _num_br(texto):
    texto = (texto or "").strip().replace(".", "").replace(",", ".")
    try:
        return float(texto) if texto else 0.0
    except ValueError:
        return 0.0


def ler_pagina_consulta(html):
    """Página do resultado da consulta completa pela chave → mesmo formato de `ler_nfce`."""
    raiz = _arvore(html or "")
    por_id = {n.attrs["id"]: n for n in raiz.todos() if n.attrs.get("id")}
    if "produtos" not in por_id or "nfce" not in por_id:
        raise ValueError("Essa página não é o resultado da consulta da nota na SEFAZ-PE.")
    situacao = " ".join(n.texto_todo() for n in raiz.todos() if "Situação Atual" in "".join(n.texto))
    if "CANCELADA" in situacao.upper():
        raise ValueError("A SEFAZ diz que essa nota foi cancelada.")

    chave = re.sub(r"\D", "", _valor(_pares(raiz), "Chave de Acesso"))
    nfce = _pares(por_id["nfce"])
    emit = _pares(por_id.get("emitente-conteudo", por_id["nfce"]))
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", _valor(nfce, "Data de Emissão"))
    if len(chave) != 44 or not m:
        raise ValueError("Não achei a chave e a data da nota nessa página.")

    itens = []
    for linha in por_id["produtos"].todos():
        if "row-custom" not in linha.classes():
            continue
        celulas = [n for n in linha.todos() if "form-control" in n.classes()]
        if len(celulas) < 6:
            continue
        num, descricao, qtd, unidade, _, valor = (c.texto_todo() for c in celulas[:6])
        detalhe = _pares(por_id.get((linha.attrs.get("data-target") or "").lstrip("#"), _No("x", [])))
        liquido = (_num_br(valor) - _num_br(_valor(detalhe, "Valor do Desconto"))
                   + _num_br(_valor(detalhe, "Outras Despesas Acessórias"))
                   + _num_br(_valor(detalhe, "Valor Total do Frete")) + _num_br(_valor(detalhe, "Valor do Seguro")))
        itens.append({
            "item": int(num) if num.isdigit() else len(itens) + 1,
            "descricao": descricao,
            "ncm": re.sub(r"\D", "", _valor(detalhe, "Código NCM")),
            "quantidade": _num_br(qtd),
            "unidade": unidade,
            "valor": round(liquido, 2),
            "desconto": round(_num_br(_valor(detalhe, "Valor do Desconto")), 2),
        })
    if not itens:
        raise ValueError("Não achei os produtos nessa página.")

    nome = _valor(emit, "Nome Fantasia") or _valor(emit, "Nome / Razão Social")
    total = round(_num_br(_valor(nfce, "Valor Total da Nota Fiscal")), 2)
    itens = ratear_ao_total(pd.DataFrame(itens, columns=_COLUNAS_ITENS), total)
    return {
        "chave": chave,
        "data": f"{m.group(3)}-{m.group(2)}-{m.group(1)}",
        "estabelecimento": nome,
        "cnpj": re.sub(r"\D", "", _valor(emit, "CNPJ / CPF")),
        "total": total,
        "desconto": round(float(itens["desconto"].sum()), 2),
        "forma_pagamento": None,
        "itens": itens,
    }


def categoria_por_ncm(ncm):
    ncm = re.sub(r"\D", "", str(ncm or ""))
    for tamanho in (4, 2):
        categoria = _NCM_CATEGORIA.get(ncm[:tamanho])
        if categoria:
            return categoria
    return None


def sugerir_categorias(itens, historico_itens, categorias):
    """Categoria de cada item: a que vocês já deram ao mesmo produto > NCM > padrão."""
    sugestoes = []
    for _, item in itens.iterrows():
        categoria = categoria_do_local(item["descricao"], historico_itens, categorias)
        if not categoria:
            categoria = categoria_por_ncm(item["ncm"])
        sugestoes.append(categoria if categoria in categorias else CATEGORIA_PADRAO_CUPOM)
    return sugestoes


def agrupar_por_categoria(itens, total):
    """Soma por categoria; a diferença de arredondamento para o total da nota vai na maior."""
    soma = itens.groupby("categoria", sort=False)["valor"].sum().round(2).sort_values(ascending=False)
    if soma.empty:
        return soma
    diferenca = round(float(total) - float(soma.sum()), 2)
    if diferenca and abs(diferenca) < 1:
        soma.iloc[0] = round(soma.iloc[0] + diferenca, 2)
    return soma


def nome_lembrado(cnpj, historico_itens):
    """Último nome que vocês deram a esse CNPJ (o nome fantasia da nota às vezes é o bairro)."""
    if not cnpj or historico_itens.empty or not {"cnpj", "estabelecimento"}.issubset(historico_itens.columns):
        return None
    nomes = historico_itens[historico_itens["cnpj"].astype(str).eq(str(cnpj))]
    if "criado_em" in nomes.columns:
        nomes = nomes.sort_values("criado_em", kind="stable")
    nomes = nomes["estabelecimento"].astype(str).str.strip()
    nomes = nomes[nomes.ne("")]
    return nomes.iloc[-1] if not nomes.empty else None


def ja_lancado(chave, despesas):
    """O cupom conta como lançado enquanto alguma linha dele existir nas despesas.

    Se as linhas forem excluídas na semana, o mesmo cupom pode ser lançado de novo.
    """
    if not chave or despesas.empty or "observacao" not in despesas.columns:
        return False
    return despesas["observacao"].astype(str).str.strip().eq(f"NFC-e {chave}").any()
