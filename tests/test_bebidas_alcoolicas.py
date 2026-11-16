import pandas as pd

from bebidas_alcoolicas import CATEGORIA_ALCOOLICAS, eh_alcoolica
from cupom_fiscal import CATEGORIAS_CUPOM, sugerir_categorias


def test_cerveja_pela_marca_ou_pelo_tipo():
    assert eh_alcoolica("CERV DEVASSA LAGER LT 473ML TROPICAL")
    assert eh_alcoolica("Devassa lata")                       # só a marca
    assert eh_alcoolica("cerveja qualquer artesanal")          # só o tipo
    assert eh_alcoolica("STELLA ARTOIS LN 330ML")             # marca de duas palavras
    assert eh_alcoolica("VINHO TINTO SECO 750ML")
    assert eh_alcoolica("Produto sem nome", ncm="22030000")     # NCM de cerveja


def test_o_resto_continua_bebida():
    assert not eh_alcoolica("REFRIG GUARANA ANTARC 2L")
    assert not eh_alcoolica("GUARANA ANTARCTICA 2L", ncm="22021000")
    assert not eh_alcoolica("SUCO DE UVA INTEGRAL OQ 1,5L", ncm="20096100")
    assert not eh_alcoolica("AGUA MINERAL COM GAS 500", ncm="22011000")
    assert not eh_alcoolica("VINAGRE DE VINHO TINTO")
    assert not eh_alcoolica("CERV HEINEKEN 0.0 LT 350ML", ncm="22030000")   # sem álcool
    assert not eh_alcoolica("GINGER ALE")                      # "gin" só como palavra inteira


def test_sugestao_do_cupom_separa_as_alcoolicas():
    itens = pd.DataFrame({
        "descricao": ["CERV SPATEN LT 473ML", "REFRIG GUARANA ANTARC 2L", "CERV PETRA LT"],
        "ncm": ["22030000", "22021000", "22030000"],
    })
    historico = pd.DataFrame({"descricao": ["CERV PETRA LT"], "categoria": ["🥤 Bebidas"]})
    assert sugerir_categorias(itens, pd.DataFrame(), CATEGORIAS_CUPOM) == [
        CATEGORIA_ALCOOLICAS, "🥤 Bebidas", CATEGORIA_ALCOOLICAS]
    # o que vocês já deram ao mesmo produto continua valendo
    assert sugerir_categorias(itens, historico, CATEGORIAS_CUPOM)[2] == "🥤 Bebidas"
