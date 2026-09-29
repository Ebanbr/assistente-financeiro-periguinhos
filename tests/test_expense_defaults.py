import pandas as pd
from expense_defaults import categoria_do_local


def test_local_lembra_categoria_sem_diferenciar_acento_e_caixa():
    df = pd.DataFrame([{"descricao": "Deskontão", "categoria": "Supermercado"}])
    assert categoria_do_local("  DESKONTAO ", df, ["Supermercado"]) == "Supermercado"


def test_classificacao_mais_recente_prevalece():
    df = pd.DataFrame([
        {"descricao": "Recibom", "categoria": "Bar", "criado_em": "2026-01-01"},
        {"descricao": "Recibom", "categoria": "Supermercado", "criado_em": "2026-09-01"},
    ])
    assert categoria_do_local("Recibom", df, ["Bar", "Supermercado"]) == "Supermercado"


def test_nao_inventa_categoria_nem_usa_categoria_excluida():
    df = pd.DataFrame([{"descricao": "Cidade Jardim", "categoria": "Padaria"}])
    assert categoria_do_local("Cidade Jardim", df, ["Bar"]) is None
    assert categoria_do_local("Outro local", df, ["Padaria"]) is None
