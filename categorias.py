"""Nome com emoji para as categorias que vieram sem (a maioria vem crua do Notion).

O sync do Notion regrava os lançamentos com o "Tipo" de lá todo dia; por isso o
nome com emoji é aplicado na entrada (`notion_import`) e não só na planilha.
"""

# Nome cru → nome com emoji. Vale por parte: "Pix Avulso, AABB" → "💸 Pix Avulso, 🏊 AABB".
# Internet, Streaming e Saúde juntam-se de propósito com as que já tinham emoji.
NOMES_COM_EMOJI = {
    # despesas
    "AABB": "🏊 AABB",
    "Atividade Física": "🏃 Atividade Física",
    "Bombeiros": "🚒 Bombeiros",
    "CAU": "📐 CAU",
    "Cartões": "💳 Cartões",
    "Celulares": "📱 Celulares",
    "Condomínio": "🏢 Condomínio",
    "DETRAN": "🚦 DETRAN",
    "Diarista": "🧹 Diarista",
    "Energia": "💡 Energia",
    "Fin. CAIXA": "🏦 Fin. CAIXA",
    "Impostos - RF": "🧾 Impostos - RF",
    "Internet": "🌐 Internet",
    "IPTU": "🏠 IPTU",
    "Loterias": "🍀 Loterias",
    "Madre de Deus": "🏫 Madre de Deus",
    "Padaria": "🥖 Padaria",
    "Pix Avulso": "💸 Pix Avulso",
    "Pix Pelada": "⚽ Pix Pelada",
    "Poupança Kids": "🐷 Poupança Kids",
    "Remax": "🏘️ Remax",
    "Saúde": "💊 Saúde",
    "Sport Recife": "🦁 Sport Recife",
    "Streaming": "🎬 Streaming",
    "Taxas": "🪙 Taxas",
    # despesas e receitas
    "Mãe": "👩 Mãe",
    "Pai": "👨 Pai",
    "Sandra": "👤 Sandra",
    "StandLab": "💼 StandLab",
    # receitas
    "Amanda": "👤 Amanda",
    "Associados": "💼 Associados",
    "Fricarne": "💼 Fricarne",
    "Paula": "👤 Paula",
    "Rafa Gomes": "👤 Rafa Gomes",
}


def com_emoji(categoria):
    """Troca cada parte conhecida pelo nome com emoji; o resto fica igual."""
    if not isinstance(categoria, str) or not categoria.strip():
        return categoria
    partes = [p.strip() for p in categoria.split(",")]
    return ", ".join(NOMES_COM_EMOJI.get(p, p) for p in partes)
