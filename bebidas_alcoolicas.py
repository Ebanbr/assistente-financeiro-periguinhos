"""Separa as bebidas alcoólicas das demais bebidas nos produtos do cupom fiscal.

Para acrescentar uma marca ou um filtro, é só pôr o nome numa das listas abaixo, do jeito que se fala
("Devassa", "cerveja Devassa", "Stella Artois"). Maiúsculas, acentos e pontuação não importam; o termo
precisa aparecer como palavra inteira no nome do produto ("GIN" não pega "GINGER").
"""
import re

from expense_defaults import normalizar_local

CATEGORIA_ALCOOLICAS = "🍻 Bebidas Alcoólicas"
CATEGORIA_BEBIDAS = "🥤 Bebidas"

# Marcas de cerveja (e de bebidas "ice") que aparecem nos cupons.
# Fora de propósito: "Sol", "Original", "Crystal", "Colorado", "Polar"… (também são palavras comuns,
# marca de água ou de outro produto);
# esses nomes só contam junto de "cerveja"/"cerv", que já está nos tipos de bebida.
MARCAS = [
    # cervejas tradicionais
    "Skol", "Brahma", "Antarctica", "Bohemia", "Budweiser", "Stella Artois", "Corona", "Coronita",
    "Heineken", "Amstel", "Devassa", "Itaipava", "Petra", "Spaten", "Eisenbahn", "Baden Baden",
    "Kaiser", "Bavaria", "Schin", "Nova Schin", "Proibida", "Caracu",
    "Serramalte", "Patagonia", "Becks", "Beck's", "Michelob", "Black Princess",
    "Therezopolis", "Praya", "Goose Island", "Hoegaarden", "Leffe", "Guinness", "Erdinger",
    "Paulaner", "Weihenstephaner", "Estrella Galicia", "Birra Moretti", "Peroni", "Sapporo",
    "Blue Moon", "Lokal", "Cintra", "Wals", "Dado Bier", "Bierland",
    # bebidas ice e destilados mais comuns
    "Smirnoff", "Skol Beats", "Absolut", "Johnnie Walker", "Red Label", "Black Label",
    "Jack Daniels", "Jack Daniel's", "Chivas", "Ballantines", "Old Parr", "White Horse",
    "Jagermeister", "Tanqueray", "Bombay Sapphire", "Beefeater", "Bacardi", "Montilla",
    "Pitu", "Ypioca", "Velho Barreiro", "Sagatiba", "Campari", "Aperol", "Martini", "Cinzano",
    "Baileys", "Jose Cuervo", "Orloff", "Askov",
]

# Tipos de bebida, inclusive as abreviações dos cupons ("CERV", "VH").
TIPOS = [
    "cerveja", "cerv", "chopp", "chope", "vinho", "vh", "espumante", "prosecco", "champagne",
    "vodka", "whisky", "whiskey", "cachaca", "aguardente", "gin", "rum", "tequila", "licor", "sake",
    "conhaque", "vermute", "sidra", "caipirinha", "drink pronto",
]

# Se aparecer qualquer um destes, NÃO é alcoólica (fica em 🥤 Bebidas ou na categoria do NCM):
# "Guaraná Antarctica", "suco de uva", "vinagre de vinho", "cerveja sem álcool", "Heineken 0.0"…
NAO_ALCOOLICAS = [
    "sem alcool", "s alcool", "zero alcool", "0 0", "00", "zero",
    "guarana", "refrig", "refrigerante", "suco", "agua", "tonica", "energetico", "refresco",
    "vinagre", "molho", "tempero",
]


def _tem(texto, termos):
    """Algum termo aparece como palavra(s) inteira(s) no texto (os dois já normalizados)."""
    return any(f" {t} " in f" {texto} " for t in termos if t)


_MARCAS = [normalizar_local(m) for m in MARCAS]
_TIPOS = [normalizar_local(t) for t in TIPOS]
_NAO = [normalizar_local(t) for t in NAO_ALCOOLICAS]
# NCM: 2203 cerveja, 2204 vinho, 2205 vermute, 2206 sidra/fermentados, 2208 destilados.
NCM_ALCOOLICAS = ("2203", "2204", "2205", "2206", "2208")


def nao_alcoolica(descricao):
    return _tem(normalizar_local(descricao), _NAO)


def eh_alcoolica(descricao, ncm=None):
    """Produto é bebida alcoólica pelo nome (marca ou tipo) ou pelo NCM, salvo os termos de NAO_ALCOOLICAS."""
    texto = normalizar_local(descricao)
    if _tem(texto, _NAO):
        return False
    if _tem(texto, _MARCAS) or _tem(texto, _TIPOS):
        return True
    return re.sub(r"\D", "", str(ncm or ""))[:4] in NCM_ALCOOLICAS
