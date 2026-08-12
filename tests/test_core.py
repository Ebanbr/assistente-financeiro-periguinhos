# ============================================================
#  tests/test_core.py — testes das partes mais críticas
#  Rode com:  pip install pytest  &&  pytest
# ============================================================
import re
import pandas as pd
import pytest

import utils


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
