"""Verifica que os dois temas mostram o painel sem acessar dados reais."""

from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

import ui_theme
import utils


def test_paletas_separam_receita_e_despesa():
    for nome in ui_theme.OPCOES_TEMA:
        cores = ui_theme.paleta_graficos(nome)
        assert cores["receita"] != cores["despesa"]
        assert cores["texto"] != cores["fundo"]


def test_dashboard_renderiza_nos_dois_temas_sem_dados_reais(monkeypatch):
    despesas = pd.DataFrame([
        {"id": "d1", "data": "2026-09-05", "data_dt": pd.Timestamp("2026-09-05"),
         "descricao": "Despesa demonstrativa", "categoria": "Mercado", "valor": 20.0,
         "fonte": "Notion", "banco": "BB", "forma_pagamento": "Pix"},
        {"id": "d2", "data": "2026-09-10", "data_dt": pd.Timestamp("2026-09-10"),
         "descricao": "Compra demonstrativa", "categoria": "Mercado", "valor": 30.0,
         "fonte": "Semanal", "banco": "C6 BRU", "forma_pagamento": "Crédito"},
    ])
    receitas = pd.DataFrame([
        {"id": "r1", "data": "2026-09-01", "data_dt": pd.Timestamp("2026-09-01"),
         "descricao": "Receita demonstrativa", "categoria": "Trabalho", "valor": 100.0,
         "fonte": "Notion"},
    ])

    def dados_falsos(tabela):
        nome = str(tabela).lower()
        if "despesa" in nome:
            return despesas.copy()
        if "receita" in nome:
            return receitas.copy()
        return pd.DataFrame()

    monkeypatch.setattr(utils, "ler_csv", dados_falsos)
    monkeypatch.setattr(utils, "ler_json", lambda _: {"limite_semanal": 2000})
    monkeypatch.setattr(utils, "listar_categorias", lambda _: ["Mercado"])

    app = Path(__file__).resolve().parents[1] / "app.py"
    for tema in ui_theme.OPCOES_TEMA:
        at = AppTest.from_file(str(app), default_timeout=20)
        at.session_state["logado"] = True
        at.session_state["usuario"] = "BOo"
        at.session_state["aparencia"] = tema
        at.run()
        assert not at.exception, [e.message for e in at.exception]

    paginas = Path(__file__).resolve().parents[1] / "pages"
    # AppTest abre cada página isoladamente e não registra a navegação multipage.
    monkeypatch.setattr(st, "page_link", lambda *args, **kwargs: None)
    for arquivo in ("1_📆_Gastos_Semanais.py", "2_🔎_Categorias.py"):
        at = AppTest.from_file(str(paginas / arquivo), default_timeout=20)
        at.session_state["logado"] = True
        at.session_state["usuario"] = "BOo"
        at.session_state["aparencia"] = "Claro"
        at.run()
        assert not at.exception, [e.message for e in at.exception]
