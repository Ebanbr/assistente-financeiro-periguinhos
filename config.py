# ============================================================
#  config.py — Configurações Globais
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import os
from pathlib import Path

# ── Identidade ───────────────────────────────────────────────
APP_NOME        = "Família Periguinhos"
APP_EMOJI       = "🐧"
APP_SUBTITULO   = "Assistente Financeiro"

# ── Caminhos de dados ────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DATA_DIR   = BASE_DIR / "data"

# Arquivos CSV
DESPESAS_FILE      = DATA_DIR / "despesas.parquet"
RECEITAS_FILE      = DATA_DIR / "receitas.parquet"
CARTOES_FILE       = DATA_DIR / "cartoes.parquet"
LANCAMENTOS_FILE   = DATA_DIR / "lancamentos.parquet"
METAS_FILE         = DATA_DIR / "metas.parquet"
CONFIG_FILE        = DATA_DIR / "configuracoes.json"

# ── Locale / Moeda ───────────────────────────────────────────
MOEDA_SIMBOLO  = "R$"
LOCALE         = "pt_BR"
DATE_FORMAT    = "%d/%m/%Y"

# ── Meses em Português ───────────────────────────────────────
MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

# ── Categorias padrão ────────────────────────────────────────
CATEGORIAS_DESPESA = [
    "🏠 Moradia",
    "🍽️ Alimentação",
    "🚗 Transporte",
    "💊 Saúde",
    "📚 Educação",
    "👗 Vestuário",
    "🎮 Lazer",
    "🐧 Filhos",
    "💳 Cartão de Crédito",
    "💡 Contas (água/luz/internet)",
    "🐾 Pets",
    "🎁 Presentes",
    "✈️ Viagens",
    "📦 Outros",
]

CATEGORIAS_RECEITA = [
    "💼 Salário",
    "💰 Freelance / Extra",
    "📈 Investimentos",
    "🏠 Aluguel recebido",
    "🎁 Presente / Doação",
    "📦 Outros",
]

FORMAS_PAGAMENTO = [
    "💵 Dinheiro",
    "💳 Débito",
    "💳 Crédito",
    "📱 PIX",
    "🏦 Transferência",
    "📄 Boleto",
]

MEMBROS_FAMILIA = ["Família", "Pai", "Mãe", "Filho(a) 1", "Filho(a) 2"]

STATUS_OPCOES = ["Pago", "Pendente", "Agendado"]

# ── Paleta de cores (para gráficos Plotly) ───────────────────
CORES = {
    "primaria":    "#1E3A5F",   # azul marinho
    "secundaria":  "#2EC4B6",   # verde-água
    "destaque":    "#FF6B6B",   # vermelho suave
    "aviso":       "#FFD166",   # amarelo
    "sucesso":     "#06D6A0",   # verde
    "neutro":      "#8D99AE",   # cinza
    "fundo":       "#F8F9FA",
}

CORES_GRAFICOS = [
    "#2EC4B6", "#1E3A5F", "#FF6B6B", "#FFD166",
    "#06D6A0", "#8D99AE", "#A8DADC", "#E63946",
]

# ── Colunas dos CSVs ─────────────────────────────────────────
COLUNAS_DESPESAS = [
    "id", "data", "descricao", "categoria", "valor",
    "forma_pagamento", "cartao", "status", "observacao", "fonte", "criado_em"
]

COLUNAS_RECEITAS = [
    "id", "data", "descricao", "categoria", "valor",
    "forma_recebimento", "status", "observacao", "fonte", "criado_em"
]

# Fontes possíveis
FONTES = ["Manual", "Notion", "C6 Bank"]

COLUNAS_CARTOES = [
    "id", "nome", "bandeira", "limite", "dia_fechamento",
    "dia_vencimento", "cor", "ativo"
]

COLUNAS_LANCAMENTOS = [
    "id", "data", "tipo", "descricao", "categoria",
    "valor", "forma_pagamento", "cartao", "status", "observacao"
]

COLUNAS_METAS = [
    "id", "nome", "descricao", "valor_total", "valor_atual",
    "data_inicio", "data_meta", "categoria", "ativa"
]

COLUNAS_MAPEAMENTOS = [
    "id", "padrao", "categoria", "tipo", "criado_em"
]

MAPEAMENTOS_FILE = DATA_DIR / "mapeamentos.parquet"

# Mapeamentos padrão iniciais
MAPEAMENTOS_PADRAO = [
    # ── RECEITAS — Salários e Rendimentos ────────────────────
    ("Fricarne", "💼 Salário - Fricarne", "receita"),
    ("Associados", "💼 Salário - Associados", "receita"),
    ("Stand Lab", "💼 Salário - Stand Lab", "receita"),
    ("StandLab", "💼 Salário - Stand Lab", "receita"),
    ("Pró-labore", "💼 Salário - Stand Lab", "receita"),
    ("Pro-labore", "💼 Salário - Stand Lab", "receita"),

    # ── RECEITAS — Família ────────────────────────────────────
    ("Pai -", "👨 Família", "receita"),
    ("Débitos Amanda", "👨 Família", "receita"),
    ("Empréstimo Rafa", "💰 Empréstimos Recebidos", "receita"),
    ("Emprestimo Rafa", "💰 Empréstimos Recebidos", "receita"),

    # ── DESPESAS — Casa ───────────────────────────────────────
    ("Diarista", "🏠 Casa - Diarista", "despesa"),
    ("Condomínio", "🏠 Casa - Condomínio", "despesa"),
    ("Condominio", "🏠 Casa - Condomínio", "despesa"),
    ("Marceneiro", "🏠 Casa - Reforma", "despesa"),
    ("Ar Condicionado", "🏠 Casa - Reforma", "despesa"),
    ("Cortinas", "🏠 Casa - Reforma", "despesa"),
    ("Cloud Park", "🚗 Estacionamento", "despesa"),

    # ── DESPESAS — Energia e Contas ───────────────────────────
    ("Neo Energia", "💡 Energia Elétrica", "despesa"),
    ("BV Energia", "💡 Energia Elétrica", "despesa"),
    ("Atel", "🌐 Internet", "despesa"),
    ("Tim Casa", "🌐 Internet", "despesa"),
    ("Claro", "📱 Celular", "despesa"),
    ("Vivo", "📱 Celular", "despesa"),
    ("AABB", "🎾 Clube - AABB", "despesa"),

    # ── DESPESAS — Saúde ──────────────────────────────────────
    ("Unimed", "💊 Saúde - Unimed", "despesa"),
    ("Farmacia", "💊 Saúde - Farmácia", "despesa"),
    ("Drogaria", "💊 Saúde - Farmácia", "despesa"),
    ("Remedio", "💊 Saúde - Farmácia", "despesa"),
    ("Manipulado", "💊 Saúde - Farmácia", "despesa"),
    ("Resilienza", "💊 Saúde - Clínica", "despesa"),
    ("RESILIENZA", "💊 Saúde - Clínica", "despesa"),
    ("Hospital", "💊 Saúde - Hospital", "despesa"),

    # ── DESPESAS — Escola Madre de Deus ───────────────────────
    ("MD -", "🎓 Escola - Madre de Deus", "despesa"),
    ("Taciana MD", "🎓 Escola - Madre de Deus", "despesa"),
    ("Nicole MD", "🎓 Escola - Madre de Deus", "despesa"),
    ("Camila Sathler", "🎓 Escola - Madre de Deus", "despesa"),
    ("Zuleide MD", "🎓 Escola - Madre de Deus", "despesa"),
    ("Madre de Deus", "🎓 Escola - Madre de Deus", "despesa"),
    ("Santillana", "📚 Material Escolar", "despesa"),
    ("MULTISELO", "📚 Material Escolar", "despesa"),

    # ── DESPESAS — Impostos ───────────────────────────────────
    ("IPTU", "🏛️ Impostos - IPTU", "despesa"),
    ("Bombeiros", "🏛️ Impostos - Bombeiros", "despesa"),
    ("MEI", "🏢 MEI", "despesa"),

    # ── DESPESAS — Família / Empréstimos ──────────────────────
    ("Empréstimo Sandra", "👨 Família - Sandra", "despesa"),
    ("Sandra", "👨 Família - Sandra", "despesa"),
    ("Poup. Raul", "🐣 Poupança Kids", "despesa"),
    ("Poup. Aurora", "🐣 Poupança Kids", "despesa"),
    ("Poupança", "🐣 Poupança Kids", "despesa"),
    ("Empréstimo Rafa", "💸 Empréstimos Pagos", "despesa"),

    # ── DESPESAS — Alimentação ────────────────────────────────
    ("Pizza", "🍽️ Alimentação", "despesa"),
    ("Cerveja", "🍺 Lazer - Bar", "despesa"),
    ("Restaurante", "🍽️ Alimentação", "despesa"),
    ("iFood", "🍽️ Alimentação", "despesa"),
    ("Rappi", "🍽️ Alimentação", "despesa"),
    ("McDonald", "🍽️ Alimentação", "despesa"),
    ("Burger", "🍽️ Alimentação", "despesa"),
    ("Lanche", "🍽️ Alimentação", "despesa"),
    ("Padaria", "🍽️ Alimentação", "despesa"),
    ("Supermercado", "🛒 Supermercado", "despesa"),
    ("Recibom", "🛒 Supermercado", "despesa"),
    ("Carrefour", "🛒 Supermercado", "despesa"),
    ("Atacadao", "🛒 Supermercado", "despesa"),

    # ── DESPESAS — Lazer ──────────────────────────────────────
    ("Pelada", "⚽ Esporte", "despesa"),
    ("Tauwan", "⚽ Esporte", "despesa"),
    ("Igor - Jantar Sport", "🎾 Lazer - Sport", "despesa"),
    ("Concurso", "🎲 Apostas", "despesa"),
    ("Bolão", "🎲 Apostas", "despesa"),
    ("Mega Sena", "🎲 Apostas", "despesa"),

    # ── DESPESAS — Streaming ──────────────────────────────────
    ("Netflix", "🎬 Streaming", "despesa"),
    ("Spotify", "🎬 Streaming", "despesa"),
    ("HBO", "🎬 Streaming", "despesa"),
    ("Disney", "🎬 Streaming", "despesa"),
    ("ESPN", "🎬 Streaming", "despesa"),
    ("Amazon Prime", "🎬 Streaming", "despesa"),
    ("AMAZON PRIME", "🎬 Streaming", "despesa"),
    ("Globoplay", "🎬 Streaming", "despesa"),
    ("IPTV", "🎬 Streaming", "despesa"),
    ("LIVELO", "🎬 Streaming", "despesa"),

    # ── DESPESAS — Compras Online ─────────────────────────────
    ("Shopee", "🛍️ Compras Online", "despesa"),
    ("SHOPEE", "🛍️ Compras Online", "despesa"),
    ("Amazon", "🛍️ Compras Online", "despesa"),
    ("AMAZON", "🛍️ Compras Online", "despesa"),
    ("Mercado Livre", "🛍️ Compras Online", "despesa"),
    ("Aliexpress", "🛍️ Compras Online", "despesa"),

    # ── DESPESAS — Vestuário ──────────────────────────────────
    ("Roupa", "👗 Vestuário", "despesa"),
    ("LALELILO", "👗 Vestuário", "despesa"),

    # ── DESPESAS — Transporte ─────────────────────────────────
    ("Uber", "🚗 Transporte", "despesa"),
    ("99 ", "🚗 Transporte", "despesa"),
    ("Combustivel", "🚗 Transporte", "despesa"),
    ("Combustível", "🚗 Transporte", "despesa"),
    ("GOL LINHA", "✈️ Viagens", "despesa"),
    ("Passagem", "✈️ Viagens", "despesa"),
    ("Hotel", "✈️ Viagens", "despesa"),

    # ── DESPESAS — Trabalho ───────────────────────────────────
    ("PAYGO", "💼 Trabalho - Design", "despesa"),
    ("Berg Design", "💼 Trabalho - Design", "despesa"),
    ("Armorial", "🏢 Imóveis", "despesa"),
    ("Remax", "🏢 Imóveis", "despesa"),

    # ── DESPESAS — Doações ────────────────────────────────────
    ("Doação", "❤️ Doações", "despesa"),
    ("Doacao", "❤️ Doações", "despesa"),
    ("Anjo da Guarda", "❤️ Doações", "despesa"),
    ("Caixinha Natal", "🎁 Presentes", "despesa"),

    # ── DESPESAS — Academia ───────────────────────────────────
    ("Academia", "🏋️ Academia", "despesa"),
    ("C COND FIS", "🏋️ Academia", "despesa"),
    ("Fitness", "🏋️ Academia", "despesa"),

    # ── DESPESAS — Taxas Bancárias ────────────────────────────
    ("Juros", "🏦 Taxas Bancárias", "despesa"),
    ("Juros-Taxas", "🏦 Taxas Bancárias", "despesa"),
    ("Taxa", "🏦 Taxas Bancárias", "despesa"),

    # ── DESPESAS — C6 Bank (descrições da fatura) ─────────────
    ("SHOPEE", "🛍️ Compras Online", "despesa"),
    ("AMAZON", "🛍️ Compras Online", "despesa"),
    ("MERCADO LIVRE", "🛍️ Compras Online", "despesa"),
    ("ALIEXPRESS", "🛍️ Compras Online", "despesa"),
    ("KOCHILO", "🛍️ Compras Online", "despesa"),
    ("MAGALU", "🛍️ Compras Online", "despesa"),
    ("AMERICANAS", "🛍️ Compras Online", "despesa"),
    ("GOL LINHA", "✈️ Viagens", "despesa"),
    ("LATAM", "✈️ Viagens", "despesa"),
    ("AZUL", "✈️ Viagens", "despesa"),
    ("RESILIENZA", "💊 Saúde - Clínica", "despesa"),
    ("FERREIRA COS", "💊 Saúde", "despesa"),
    ("DROGASIL", "💊 Saúde - Farmácia", "despesa"),
    ("DROGA", "💊 Saúde - Farmácia", "despesa"),
    ("PACHECO", "💊 Saúde - Farmácia", "despesa"),
    ("LALELILO", "👗 Vestuário", "despesa"),
    ("ZARA", "👗 Vestuário", "despesa"),
    ("RIACHUELO", "👗 Vestuário", "despesa"),
    ("RENNER", "👗 Vestuário", "despesa"),
    ("C COND FIS", "🏋️ Academia", "despesa"),
    ("SMARTFIT", "🏋️ Academia", "despesa"),
    ("PAYGO", "💼 Trabalho - Design", "despesa"),
    ("LIVELO", "🎁 Benefícios - Pontos", "despesa"),
    ("SANTILLANA", "📚 Material Escolar", "despesa"),
    ("MULTISELO", "📚 Material Escolar", "despesa"),
    ("IFOOD", "🍽️ Alimentação", "despesa"),
    ("RAPPI", "🍽️ Alimentação", "despesa"),
    ("UBER EATS", "🍽️ Alimentação", "despesa"),
    ("UBER", "🚗 Transporte", "despesa"),
    ("99APP", "🚗 Transporte", "despesa"),
    ("POSTO", "🚗 Combustível", "despesa"),
    ("PETROBRAS", "🚗 Combustível", "despesa"),
    ("SHELL", "🚗 Combustível", "despesa"),
    ("NETFLIX", "🎬 Streaming", "despesa"),
    ("SPOTIFY", "🎬 Streaming", "despesa"),
    ("DISNEY", "🎬 Streaming", "despesa"),
    ("HBO MAX", "🎬 Streaming", "despesa"),
    ("PRIME VIDEO", "🎬 Streaming", "despesa"),
    ("OPENAI", "💻 Tecnologia", "despesa"),
    ("GOOGLE", "💻 Tecnologia", "despesa"),
    ("APPLE", "💻 Tecnologia", "despesa"),
    ("MICROSOFT", "💻 Tecnologia", "despesa"),
]
