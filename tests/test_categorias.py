from categorias import com_emoji
from notion_import import linhas_do_notion


def test_poe_emoji_por_parte_e_preserva_o_resto():
    assert com_emoji("Padaria") == "🥖 Padaria"
    assert com_emoji("Pix Avulso, AABB") == "💸 Pix Avulso, 🏊 AABB"
    assert com_emoji("IPTU, Impostos - RF") == "🏠 IPTU, 🧾 Impostos - RF"
    assert com_emoji("🛒 Supermercado") == "🛒 Supermercado"
    assert com_emoji("💊 Saúde - Farmácia") == "💊 Saúde - Farmácia"   # só nome exato
    assert com_emoji("") == ""


def test_ja_com_emoji_nao_muda():
    for nome in ["🥖 Padaria", "💸 Pix Avulso, 🏊 AABB"]:
        assert com_emoji(nome) == nome


def test_sync_do_notion_ja_grava_com_emoji():
    d, r = linhas_do_notion([
        {"Nome": "Pão", "Vencimento": "2026-10-10", "Valor": -12.5, "Tipo": "Padaria"},
        {"Nome": "Salário", "Vencimento": "2026-10-05", "Valor": 1000, "Tipo": "Fricarne", "Rec/Des": "Receita"},
    ])
    assert d[0]["categoria"] == "🥖 Padaria"
    assert r[0]["categoria"] == "💼 Fricarne"
