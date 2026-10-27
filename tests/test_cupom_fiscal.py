import pandas as pd
import pytest

from cupom_fiscal import (
    CATEGORIA_PADRAO_CUPOM, agrupar_por_categoria, categoria_por_ncm, chave_do_link,
    emitida_offline, ja_lancado, ler_nfce, link_do_qr, nome_lembrado, sugerir_categorias, validar_link,
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


def test_cupom_so_conta_como_lancado_enquanto_as_linhas_existem():
    despesas = pd.DataFrame({"observacao": [f"NFC-e {CHAVE}", ""]})
    assert ja_lancado(CHAVE, despesas)
    assert not ja_lancado(CHAVE, despesas.iloc[[1]])      # linhas excluídas → pode relançar
    assert not ja_lancado(CHAVE, pd.DataFrame())


def test_lembra_o_nome_dado_ao_cnpj():
    hist = pd.DataFrame([
        {"cnpj": "1", "estabelecimento": "Posto Velho", "criado_em": "2026-01-01"},
        {"cnpj": "1", "estabelecimento": "Posto Arraial", "criado_em": "2026-10-01"},
    ])
    assert nome_lembrado("1", hist) == "Posto Arraial"
    assert nome_lembrado("2", hist) is None
    assert nome_lembrado("1", pd.DataFrame()) is None


def test_aceita_link_sem_p_e_com_barra_codificada():
    chave = "2" * 44
    sem_p = f"http://nfce.sefaz.pe.gov.br/nfce-web/consultarNFCe{chave}|2|1|14|56.61|ABC"
    assert chave_do_link(validar_link(sem_p)) == chave
    assert chave_do_link(validar_link(LINK.replace("|", "%7C"))) == CHAVE


def test_reconhece_nota_emitida_offline():
    offline = "2" * 34 + "9" + "2" * 9          # 35º dígito = tipo de emissão
    assert emitida_offline(f"http://nfce.sefaz.pe.gov.br/nfce/consulta?p={offline}|2|1|14|5|AB")
    assert not emitida_offline(LINK)


def test_le_o_link_de_uma_foto_do_qr_code():
    import io
    import zxingcpp
    from PIL import Image
    gerar = getattr(zxingcpp, "create_barcode", None)
    if gerar:
        img = Image.fromarray(gerar(LINK, zxingcpp.BarcodeFormat.QRCode).to_image(scale=4))
    else:
        img = Image.fromarray(zxingcpp.write_barcode(zxingcpp.BarcodeFormat.QRCode, LINK, 400, 400))
    foto = Image.new("L", (1200, 1600), 255)
    foto.paste(img.convert("L"), (300, 500))
    arquivo = io.BytesIO()
    foto.save(arquivo, format="JPEG")
    arquivo.seek(0)
    assert link_do_qr(arquivo) == LINK
    vazio = io.BytesIO()
    Image.new("L", (300, 300), 255).save(vazio, format="PNG")
    vazio.seek(0)
    assert link_do_qr(vazio) is None


OFFLINE = "2" * 2 + "2610" + "0" * 14 + "65" + "0" * 12 + "9" + "1" * 9   # AAMM=2610, tpEmis=9


def test_qr_offline_ja_traz_data_total_e_cnpj():
    from cupom_fiscal import dados_do_qr_offline
    link = f"http://nfce.sefaz.pe.gov.br/nfce-web/consultarNFCe{OFFLINE}|2|1|14|56.61|BC41"
    dados = dados_do_qr_offline(link)
    assert {k: dados[k] for k in ("chave", "cnpj", "data", "total")} == {
        "chave": OFFLINE, "cnpj": "0" * 14, "data": "2026-10-14", "total": 56.61}
    assert chave_do_link(dados["link"]) == OFFLINE           # link guardado para buscar os itens depois
    assert dados_do_qr_offline(LINK) is None                     # nota normal (online)


def test_nota_offline_nao_recebida_vira_pendente(monkeypatch):
    import cupom_fiscal
    from cupom_fiscal import NotaPendente, ler_cupom
    monkeypatch.setattr(cupom_fiscal, "baixar_xml",
                        lambda link: '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><erro>236</erro></nfeProc>')
    with pytest.raises(NotaPendente) as erro:
        ler_cupom(f"http://nfce.sefaz.pe.gov.br/nfce/consulta?p={OFFLINE}|2|1|14|56.61|BC41")
    assert erro.value.dados["total"] == 56.61
    with pytest.raises(ValueError) as erro:                          # nota online não encontrada: erro comum
        ler_cupom(LINK)
    assert not isinstance(erro.value, NotaPendente)


def test_nota_offline_ja_autorizada_sem_itens_nao_fica_esperando(monkeypatch):
    import cupom_fiscal
    from cupom_fiscal import NotaPendente, NotaSemItens, ler_cupom
    monkeypatch.setattr(cupom_fiscal, "baixar_xml",
                        lambda link: '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><erro>100</erro>'
                                     '<consulta>0</consulta></nfeProc>')
    with pytest.raises(NotaSemItens) as erro:
        ler_cupom(f"http://nfce.sefaz.pe.gov.br/nfce/consulta?p={OFFLINE}|2|1|14|56.61|BC41")
    assert not isinstance(erro.value, NotaPendente) and erro.value.dados["total"] == 56.61


def test_ficar_so_com_o_total_tira_da_espera_mas_continua_lancado():
    from cupom_fiscal import concluir_pendente, cupons_aguardando, marca_pendente
    despesas = pd.DataFrame({"observacao": [marca_pendente(OFFLINE), "outra"], "valor": [56.61, 10.0]})
    novo = concluir_pendente(OFFLINE, despesas)
    assert novo["observacao"].tolist() == [f"NFC-e {OFFLINE}", "outra"]
    assert novo["valor"].tolist() == [56.61, 10.0]
    assert cupons_aguardando(pd.DataFrame({"chave": [OFFLINE], "link": ["a"]}), novo).empty
    assert ja_lancado(OFFLINE, novo)                 # não deixa lançar o mesmo cupom de novo


def test_linhas_do_mesmo_cupom_viram_uma_compra_com_total():
    from cupom_fiscal import agrupar_compras, marca_pendente
    outro = CHAVE[:-1] + ("0" if CHAVE[-1] != "0" else "1")
    gastos = pd.DataFrame({
        "descricao": ["Mercado X · 🥤 Bebidas", "Padaria", "Mercado X · 🥬 Hortifruti", "Mercado X · 🥤 Bebidas",
                      "Recibom"],
        "observacao": [f"NFC-e {CHAVE}", "", f"NFC-e {CHAVE}", f"NFC-e {outro}", marca_pendente(OFFLINE)],
        "valor": [10.0, 5.5, 2.25, 3.0, 56.61],
    })
    compras = agrupar_compras(gastos)
    assert [(c["nome"], c["total"], len(c["linhas"])) for c in compras] == [
        ("Mercado X", 12.25, 2), ("Padaria", 5.5, 1), ("Mercado X", 3.0, 1), ("Recibom", 56.61, 1)]
    assert compras[0]["chave"] == CHAVE and compras[1]["chave"] is None and compras[3]["chave"] == OFFLINE
    assert agrupar_compras(gastos.iloc[0:0]) == []


def test_linha_so_com_total_e_reconhecida_e_nao_conta_como_lancado():
    from cupom_fiscal import linhas_pendentes, marca_pendente
    despesas = pd.DataFrame({"observacao": [marca_pendente(OFFLINE), f"NFC-e {CHAVE}", ""]})
    assert linhas_pendentes(OFFLINE, despesas).tolist() == [True, False, False]
    assert not ja_lancado(OFFLINE, despesas)        # deixa lançar com os itens, trocando a linha do total


def test_lista_so_cupons_cuja_linha_do_total_ainda_existe():
    from cupom_fiscal import cupons_aguardando, marca_pendente
    outro = OFFLINE[:-1] + "2"
    pend = pd.DataFrame({"chave": [OFFLINE, outro, OFFLINE], "link": ["a", "b", "c"]})
    despesas = pd.DataFrame({"observacao": [marca_pendente(OFFLINE), f"NFC-e {outro}"]})
    lista = cupons_aguardando(pend, despesas)
    assert lista["chave"].tolist() == [OFFLINE] and lista["link"].tolist() == ["c"]
    assert cupons_aguardando(pd.DataFrame(), despesas).empty
