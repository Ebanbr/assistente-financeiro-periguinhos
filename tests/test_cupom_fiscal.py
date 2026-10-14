import pandas as pd
import pytest

from cupom_fiscal import (
    CATEGORIA_PADRAO_CUPOM, agrupar_por_categoria, categoria_por_ncm, chave_do_link,
    ja_lancado, ler_nfce, nome_lembrado, sugerir_categorias, validar_link,
)

CHAVE = "2" * 44
LINK = f"http://nfce.sefaz.pe.gov.br/nfce/consulta?p={CHAVE}|2|1|2|ABCDEF"


def _det(n, nome, ncm, qtd, valor, desconto=None):
    desc = f"<vDesc>{desconto}</vDesc>" if desconto else ""
    return (f'<det nItem="{n}"><prod><cProd>{n}</cProd><xProd>{nome}</xProd><NCM>{ncm}</NCM>'
            f"<uCom>UN</uCom><qCom>{qtd}</qCom><vProd>{valor}</vProd>{desc}</prod></det>")


# XML fictício no formato que a SEFAZ-PE devolve (nfeProc v4.00)
XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><erro></erro><proc><nfeProc><NFe>
<infNFe Id="NFe{CHAVE}" versao="4.00">
<ide><dhEmi>2026-10-10T10:59:33-03:00</dhEmi></ide>
<emit><CNPJ>00000000000191</CNPJ><xNome>MERCADO  EXEMPLO LTDA</xNome><xFant>Mercado Exemplo</xFant></emit>
{_det(1, "BANANA PRATA KG", "08039000", "1.250", "8.74")}
{_det(2, "TOMATE  KG", "07020000", "0.800", "6.40")}
{_det(3, "DETERGENTE YPE 500ML", "34022000", "2", "5.98", desconto="0.50")}
<total><ICMSTot><vProd>21.12</vProd><vDesc>0.50</vDesc><vNF>20.62</vNF></ICMSTot></total>
<pag><detPag><tPag>17</tPag><vPag>20.62</vPag></detPag></pag>
</infNFe></NFe></nfeProc></proc></nfeProc>"""


def test_le_cabecalho_e_itens_da_nota():
    nota = ler_nfce(XML)
    assert nota["chave"] == CHAVE
    assert nota["data"] == "2026-10-10"
    assert nota["estabelecimento"] == "Mercado Exemplo"
    assert nota["total"] == 20.62
    assert nota["forma_pagamento"] == "📱 PIX"
    itens = nota["itens"]
    assert list(itens["descricao"]) == ["BANANA PRATA KG", "TOMATE KG", "DETERGENTE YPE 500ML"]
    assert itens.loc[2, "valor"] == 5.48            # desconto do item já abatido
    assert round(itens["valor"].sum(), 2) == nota["total"]


def test_resposta_sem_nota_vira_erro_legivel():
    with pytest.raises(ValueError, match="não devolveu"):
        ler_nfce('<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><erro>Chave inválida</erro></nfeProc>')
    with pytest.raises(ValueError):
        ler_nfce("<html>fora do ar")


def test_so_aceita_link_de_qr_code_da_sefaz_pe():
    assert validar_link(LINK) == LINK
    assert validar_link(LINK.removeprefix("http://")).startswith("http://nfce.sefaz.pe.gov.br")
    assert chave_do_link(LINK) == CHAVE
    for ruim in ["", "http://exemplo.com/consulta?p=" + CHAVE + "|2", "http://nfce.sefaz.pe.gov.br/nfce/consulta"]:
        with pytest.raises(ValueError):
            validar_link(ruim)


def test_ncm_sugere_categoria_e_prefixo_mais_longo_vence():
    assert categoria_por_ncm("08039000") == "🥬 Hortifruti"
    assert categoria_por_ncm("22071090") == "⛽Combustível"   # etanol não é bebida
    assert categoria_por_ncm("22030000") == "🥤 Bebidas"
    assert categoria_por_ncm("04070000") == "🥫 Mercearia"
    assert categoria_por_ncm("99999999") is None


def test_categoria_ja_dada_ao_produto_vence_o_ncm():
    itens = ler_nfce(XML)["itens"]
    historico = pd.DataFrame([{"descricao": "Banana Prata Kg", "categoria": "🥫 Mercearia",
                               "criado_em": "2026-10-01"}])
    cats = ["🥬 Hortifruti", "🥫 Mercearia", "🧽 Limpeza", CATEGORIA_PADRAO_CUPOM]
    assert sugerir_categorias(itens, historico, cats) == ["🥫 Mercearia", "🥬 Hortifruti", "🧽 Limpeza"]
    assert sugerir_categorias(itens, pd.DataFrame(), [CATEGORIA_PADRAO_CUPOM]) == [CATEGORIA_PADRAO_CUPOM] * 3


def test_agrupa_por_categoria_fechando_com_o_total():
    itens = pd.DataFrame({"valor": [8.74, 6.40, 5.48], "categoria": ["H", "H", "L"]})
    soma = agrupar_por_categoria(itens, 20.62)
    assert soma.to_dict() == {"H": 15.14, "L": 5.48}
    assert agrupar_por_categoria(itens, 20.63)["H"] == 15.15   # centavo de arredondamento vai na maior


def test_detecta_cupom_ja_lancado():
    assert ja_lancado(CHAVE, pd.DataFrame({"chave": [CHAVE]}))
    assert not ja_lancado(CHAVE, pd.DataFrame())


def test_lembra_o_nome_dado_ao_cnpj():
    hist = pd.DataFrame([
        {"cnpj": "1", "estabelecimento": "Posto Velho", "criado_em": "2026-01-01"},
        {"cnpj": "1", "estabelecimento": "Posto Arraial", "criado_em": "2026-10-01"},
    ])
    assert nome_lembrado("1", hist) == "Posto Arraial"
    assert nome_lembrado("2", hist) is None
    assert nome_lembrado("1", pd.DataFrame()) is None
