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
    faturas_encerradas, fatura_aberta, janela_semana, inicio_ciclo_aberto, lancamentos_semanais_fatura,
    meses_fatura_importados, semanas_fatura_importada, ciclo_fatura_importada,
    aplicar_edicoes_semanais,
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
    assert intervalo_fatura(2026, 10, 4, 3) == (date(2026, 9, 4), date(2026, 10, 4))


def test_encerramento_manual_da_fatura_define_fatura_aberta():
    fech = pd.DataFrame([
        {"ano": 2026, "mes": 10, "cartao": "C6 BRU", "dia": 3, "encerrada_em": ""},       # legado: só início
        {"ano": 2026, "mes": 11, "cartao": "C6 BRU", "dia": 4, "encerrada_em": "2026-10-04"},
        {"ano": 2026, "mes": 12, "cartao": "C6 PRI", "dia": 4, "encerrada_em": "2026-11-04"},
    ])
    enc = faturas_encerradas(fech, "c6 bru")
    # O registro antigo (só "dia") também vale: a 09/2026 fechou no dia 3 de setembro.
    assert enc == {(2026, 9): date(2026, 9, 3), (2026, 10): date(2026, 10, 4)}
    assert inicio_ciclo_aberto(enc) == date(2026, 10, 5)
    assert inicio_ciclo_aberto({}) is None
    # Sem encerrar a 11/2026, ela segue aberta mesmo depois do dia 4 de novembro.
    assert fatura_aberta(enc, date(2026, 11, 20)) == (2026, 11)
    assert fatura_aberta({}, date(2026, 10, 6)) == (2026, 11)
    assert faturas_encerradas(fech.drop(columns=["encerrada_em"]), "C6 BRU") == {
        (2026, 9): date(2026, 9, 3), (2026, 10): date(2026, 10, 4)}


def test_fatura_encerrada_sem_importacao_usa_lancamentos_manuais():
    df = pd.DataFrame([
        {"data": "2026-09-30", "fonte": "Semanal", "forma_pagamento": "💳 Crédito", "banco": "C6 BRU", "valor": 10.0},
        {"data": "2026-10-01", "fonte": "Semanal", "forma_pagamento": "💳 Crédito", "banco": "", "valor": 5.0},  # legado = C6 BRU
        {"data": "2026-10-02", "fonte": "Semanal", "forma_pagamento": "💳 Crédito", "banco": "C6 BRU", "valor": 99.0},  # ciclo novo
        {"data": "2026-09-30", "fonte": "Semanal", "forma_pagamento": "📱 PIX", "banco": "", "valor": 99.0},
        {"data": "2026-09-30", "fonte": "C6 Bank", "forma_pagamento": "💳 Crédito", "banco": "C6 BRU", "valor": 99.0},
    ])
    r = lancamentos_semanais_fatura(df, "C6 BRU", date(2026, 9, 4), date(2026, 10, 1))
    assert r["total"] == 15.0
    assert r["semanas"]["_inicio_semana"].tolist() == [date(2026, 9, 28), date(2026, 9, 28)]


def test_semana_zera_no_encerramento_da_fatura():
    seg, dom = date(2026, 9, 29), date(2026, 10, 5)
    enc = [date(2026, 10, 2)]
    assert janela_semana(seg, dom, date(2026, 10, 4), enc) == (date(2026, 10, 3), dom)
    assert janela_semana(seg, dom, date(2026, 10, 2), enc) == (seg, date(2026, 10, 2))
    assert janela_semana(seg, dom, date(2026, 10, 1), []) == (seg, dom)
    # Encerrar no domingo não corta nada: a semana seguinte já começa zerada.
    assert janela_semana(seg, dom, date(2026, 10, 1), [dom]) == (seg, dom)


def test_fatura_importada_separada_em_semanas_pela_data_da_compra():
    df = pd.DataFrame([
        {"data": "2026-09-01", "fonte": "C6 Bank", "banco": "C6 BRU", "valor": 10.0, "observacao": "Compra em 06/08/2026"},
        {"data": "2026-09-01", "fonte": "C6 Bank", "banco": "C6 BRU", "valor": 20.0, "observacao": "Compra em 11/08/2026"},
        {"data": "2026-09-01", "fonte": "C6 Bank", "banco": "C6 BRU", "valor": 5.0, "observacao": "Compra em 10/03/2026"},  # parcela antiga
        {"data": "2026-09-01", "fonte": "C6 Bank", "banco": "C6 BRU", "valor": 7.0, "observacao": "", "data_compra": "03/09/2026"},
        {"data": "2026-09-01", "fonte": "C6 Bank", "banco": "C6 PRI", "valor": 99.0, "observacao": "Compra em 06/08/2026"},
        {"data": "2026-08-01", "fonte": "C6 Bank", "banco": "C6 BRU", "valor": 99.0, "observacao": "Compra em 06/08/2026"},
        {"data": "2026-08-10", "fonte": "Semanal", "banco": "C6 BRU", "valor": 99.0, "observacao": ""},
    ])
    assert meses_fatura_importados(df, "C6 BRU") == [(2026, 9), (2026, 8)]
    r = semanas_fatura_importada(df, 2026, 9, "C6 BRU", date(2026, 8, 5), date(2026, 9, 4))
    assert r["total"] == 42.0
    assert r["semanas"]["_valor"].tolist() == [10.0, 20.0, 7.0]
    assert r["semanas"]["_inicio_semana"].tolist() == [date(2026, 8, 3), date(2026, 8, 10), date(2026, 8, 31)]
    assert r["fora"]["_valor"].tolist() == [5.0]
    assert semanas_fatura_importada(df, 2026, 10, "C6 BRU", date(2026, 9, 5), date(2026, 10, 4))["total"] == 0.0
    # Fechamento real lido dos dados: fim = última compra; início = dia após o fim da anterior.
    assert ciclo_fatura_importada(df, 2026, 9, "C6 BRU") == (date(2026, 8, 7), date(2026, 9, 3))
    assert ciclo_fatura_importada(df, 2026, 8, "C6 BRU") == (date(2026, 7, 7), date(2026, 8, 6))
    assert ciclo_fatura_importada(df, 2026, 10, "C6 BRU") is None


def test_editar_e_excluir_diretamente_no_historico_semanal():
    full = pd.DataFrame([
        {"id": "a", "data": "2026-09-01", "descricao": "Antigo", "categoria": "Outros", "valor": 10., "forma_pagamento": "💳 Crédito", "banco": "C6 BRU"},
        {"id": "b", "data": "2026-09-02", "descricao": "Excluir", "categoria": "Outros", "valor": 20, "forma_pagamento": "📱 PIX", "banco": ""},
    ])
    editado = pd.DataFrame([
        {"Excluir": False, "id": "a", "data": date(2026, 9, 8), "descricao": "Corrigido", "categoria": "Mercado", "valor": 15.5, "forma_pagamento": "📱 PIX", "banco": "C6 BRU"},
        {"Excluir": True, "id": "b", "data": date(2026, 9, 2), "descricao": "Excluir", "categoria": "Outros", "valor": 20, "forma_pagamento": "📱 PIX", "banco": ""},
    ])
    out, removidos = aplicar_edicoes_semanais(full, editado)
    assert removidos == 1
    assert out["id"].tolist() == ["a"]
    assert out.iloc[0]["data"] == "2026-09-08"
    assert out.iloc[0]["descricao"] == "Corrigido"
    assert out.iloc[0]["valor"] == 15.5
    assert out.iloc[0]["banco"] == ""


def test_migracao_cartao_banco_respeita_tipo_da_tabela():
    desp = utils._normalizar_schema_tabela(pd.DataFrame({"cartao": ["C6 BRU"]}), "despesas")
    assert list(desp.columns) == ["banco"]
    fech = utils._normalizar_schema_tabela(pd.DataFrame({"banco": ["C6 BRU"]}), "fechamentos_fatura")
    assert list(fech.columns) == ["cartao"]
    base = utils._normalizar_schema_tabela(
        pd.DataFrame({"banco": ["C6 BRU", ""], "cartao": ["", "C6 PRI"]}), "faturas_base"
    )
    assert list(base.columns) == ["cartao"]
    assert base["cartao"].tolist() == ["C6 BRU", "C6 PRI"]
