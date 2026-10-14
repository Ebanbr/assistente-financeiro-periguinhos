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
    """Nota offline que a SEFAZ ainda não recebeu; `dados` traz o que o QR Code já informa."""

    def __init__(self, dados):
        super().__init__("Essa nota foi emitida com o caixa offline e a SEFAZ ainda não a recebeu "
                         "(o mercado tem até 24 horas para enviar).")
        self.dados = dados


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
    return {"chave": chave, "cnpj": chave[6:20], "data": data.strftime("%Y-%m-%d"), "total": total}


def ler_cupom(link):
    """Baixa e lê a nota. Nota offline ainda não recebida pela SEFAZ → NotaPendente."""
    link = validar_link(link)
    try:
        return ler_nfce(baixar_xml(link))
    except ValueError:
        dados = dados_do_qr_offline(link)
        if dados:
            raise NotaPendente(dados)
        raise


def marca_pendente(chave):
    return f"NFC-e {chave} · itens pendentes"


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
        })

    pagamentos = [(_txt(d, "n:tPag"), _num(d, "n:vPag")) for d in inf.findall("n:pag/n:detPag", NS)]
    tpag = max(pagamentos, key=lambda p: p[1])[0] if pagamentos else ""

    chave = (inf.get("Id") or "").removeprefix("NFe")
    return {
        "chave": chave,
        "data": data_hora[:10],
        "estabelecimento": " ".join(nome.split()),
        "cnpj": _txt(emit, "n:CNPJ"),
        "total": round(_num(inf, "n:total/n:ICMSTot/n:vNF"), 2),
        "forma_pagamento": _TPAG_FORMA.get(tpag),
        "itens": pd.DataFrame(itens, columns=["item", "descricao", "ncm", "quantidade", "unidade", "valor"]),
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
