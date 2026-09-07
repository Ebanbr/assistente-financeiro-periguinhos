# ============================================================
#  tests/test_core.py — testes das partes mais críticas
#  Rode com:  pip install pytest  &&  pytest
# ============================================================
import re
from datetime import date
import pandas as pd
import pytest

import utils
from fatura_projection import (
    parse_parcela, projetar_parcelas, semana_do_mes, mascara_credito_cartao,
    inicio_semana, competencia_fatura, intervalo_fatura, semana_no_ciclo_fatura,
)


# ── Datas: a área que mais deu bug (mês trocado) ────────────
@pytest.mark.parametrize("entrada, esperado", [
    ("2026-06-05", "2026-06-05"),          # ISO
    ("05/06/2026", "2026-06-05"),          # BR: 5 de junho (dayfirst)
    ("05/05/2025", "2025-05-05"),          # BR
    ("10/01/2026", "2026-01-10"),          # BR: 10 de janeiro (NÃO 1 de out)
    ("2026-06-05 00:00:00", "2026-06-05"), # ISO com hora
    ("2026/06/05", "2026-06-05"),          # ISO com barra
])
def test_parse_data_iso_e_br(entrada, esperado):
    got = utils._parse_data_robusta(pd.Series([entrada]))
    assert got.iloc[0].strftime("%Y-%m-%d") == esperado

def test_parse_data_invalida_vira_nat():
    got = utils._parse_data_robusta(pd.Series(["", "lixo", None]))
    assert got.isna().all()

@pytest.mark.parametrize("ausente", [None, float("nan"), pd.NA, pd.NaT, "", "   "])
def test_parse_data_ausente_nao_altera_datas_validas(ausente):
    serie = pd.Series(["05/06/2026", ausente, "2026-07-05"], index=[10, 20, 30])
    got = utils._parse_data_robusta(serie)
    assert got.index.equals(serie.index)
    assert got.loc[10] == pd.Timestamp("2026-06-05")
    assert pd.isna(got.loc[20])
    assert got.loc[30] == pd.Timestamp("2026-07-05")

def test_normalizar_coluna_data_padroniza_iso():
    df = pd.DataFrame({"data": ["05/06/2026", "2025-01-10"]})
    out = utils._normalizar_coluna_data(df.copy())
    assert list(out["data"]) == ["2026-06-05", "2025-01-10"]
    assert out["data_dt"].dt.month.tolist() == [6, 1]


# ── Detecção do mês da fatura C6 pelo nome (não pela compra) ─
def _detect_mes_ano(nome):
    s = str(nome).lower()
    m = re.search(r'(20\d{2})[-_./]?(0[1-9]|1[0-2])(?!\d)', s)
    if m: return int(m.group(2)), int(m.group(1))
    m = re.search(r'(?<!\d)(0[1-9]|1[0-2])[-_./](20\d{2})', s)
    if m: return int(m.group(1)), int(m.group(2))
    return None, None

@pytest.mark.parametrize("nome, mes, ano", [
    ("Fatura_2024-12-10.csv", 12, 2024),
    ("Fatura_2025-01-10.csv", 1, 2025),
    ("extrato_05-2024.csv",   5, 2024),
    ("fatura c6.zip",         None, None),
])
def test_deteccao_mes_fatura(nome, mes, ano):
    assert _detect_mes_ano(nome) == (mes, ano)


# ── esc(): não deixa HTML injetado quebrar o layout ─────────
def test_esc_escapa_html():
    assert utils.esc("<script>x</script>") == "&lt;script&gt;x&lt;/script&gt;"
    assert utils.esc("A & B") == "A &amp; B"
    assert utils.esc(None) == ""


# ── IDs: UUID completo (sem colisão) ────────────────────────
def test_gerar_id_completo_e_unico():
    ids = {utils.gerar_id() for _ in range(5000)}
    assert len(ids) == 5000
    assert all(len(i) == 36 for i in ids)


# ── Moeda ───────────────────────────────────────────────────
def test_formatar_moeda():
    assert utils.formatar_moeda(1234.5) == "R$ 1.234,50"
    assert utils.formatar_moeda(0) == "R$ 0,00"


def test_projecao_parcelas_respeita_mes_e_cartao():
    df = pd.DataFrame([
        {"data": "2026-08-01", "valor": 100, "descricao": "Compra A", "fonte": "C6 Bank", "banco": "C6 BRU", "parcela_atual": 3, "parcelas_total": 5},
        {"data": "2026-08-01", "valor": 80, "descricao": "Finalizada", "fonte": "C6 Bank", "banco": "C6 BRU", "parcela_atual": 5, "parcelas_total": 5},
        {"data": "2026-08-01", "valor": 50, "descricao": "Outro cartao", "fonte": "C6 Bank", "banco": "C6 PRI", "parcela_atual": 1, "parcelas_total": 4},
    ])
    out = projetar_parcelas(df, 2026, 9, "C6 BRU")
    assert out["total"] == 100
    assert out["itens"].iloc[0]["parcela_projetada"] == 4


def test_parse_parcela_e_semana_do_mes():
    assert parse_parcela("3/10") == (3, 10)
    assert parse_parcela("0/10") is None
    assert semana_do_mes(pd.Series(["2026-09-01", "2026-09-08", "2026-09-29"])).tolist() == [1, 2, 5]


def test_projecao_nao_duplica_mesmas_parcelas_de_faturas_anteriores():
    df = pd.DataFrame([
        {"data": "2026-07-01", "data_compra": "10/05/2026", "descricao": "Loja", "valor": 100,
         "fonte": "C6 Bank", "banco": "C6 BRU", "parcela_atual": 3, "parcelas_total": 10},
        {"data": "2026-08-01", "data_compra": "10/05/2026", "descricao": "Loja", "valor": 100,
         "fonte": "C6 Bank", "banco": "C6 BRU", "parcela_atual": 4, "parcelas_total": 10},
    ])
    out = projetar_parcelas(df, 2026, 9, "C6 BRU")
    assert out["total"] == 100
    assert len(out["itens"]) == 1
    assert out["itens"].iloc[0]["parcela_projetada"] == 5


def test_resolve_tabela_faturas_base():
    assert utils._resolve_tabela("faturas_base") == "faturas_base"


def test_credito_legado_sem_cartao_so_entra_no_c6_bru():
    df = pd.DataFrame([
        {"forma_pagamento": "💳 Crédito", "banco": ""},
        {"forma_pagamento": "💳 Crédito", "banco": "C6 PRI"},
        {"forma_pagamento": "📱 PIX", "banco": ""},
    ])
    assert mascara_credito_cartao(df, "C6 BRU").tolist() == [True, False, False]
    assert mascara_credito_cartao(df, "C6 PRI").tolist() == [False, True, False]


def test_semana_calendario_e_ciclo_fatura_dia_4():
    assert inicio_semana("2026-09-06").isoformat() == "2026-08-31"
    assert competencia_fatura("2026-09-04", 4) == (2026, 9)
    assert competencia_fatura("2026-09-05", 4) == (2026, 10)
    assert intervalo_fatura(2026, 10, 4) == (date(2026, 9, 5), date(2026, 10, 4))
    semanas = semana_no_ciclo_fatura(pd.Series(["2026-09-05", "2026-09-11", "2026-09-12", "2026-10-04"]), 2026, 10, 4)
    assert semanas.tolist() == [1, 1, 2, 5]
