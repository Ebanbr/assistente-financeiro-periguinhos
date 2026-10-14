from datetime import date

import pandas as pd

from custo_vida import (CORTAVEL, ESSENCIAL, FIXA, FORA, SEM_TIPO, classificar, custo_minimo,
                        gasto_mensal_por_tipo, media_por_categoria, meses_da_janela, tipo_padrao)


def test_classificacao_aprovada_e_casos_por_fora():
    assert tipo_padrao("🏢 Condomínio") == FIXA
    assert tipo_padrao("🛒 Supermercado") == ESSENCIAL
    assert tipo_padrao("🎮 Lazer") == CORTAVEL
    for fora in ["💳 Cartões", "💸 Pix Avulso", "🐷 Poupança Kids", "👩 Mãe"]:
        assert tipo_padrao(fora) == FORA
    assert tipo_padrao("📦 Outros") == SEM_TIPO
    assert tipo_padrao("🏠 IPTU, 🧾 Impostos - RF") == FIXA          # partes concordam
    assert tipo_padrao("💸 Pix Avulso, 🏊 AABB") == SEM_TIPO          # partes discordam


def test_o_que_foi_salvo_vence_a_sugestao():
    salvos = pd.DataFrame({"categoria": ["🎬 Streaming", "📦 Outros"], "tipo": [CORTAVEL, "lixo"]})
    mapa = classificar(["🎬 Streaming", "📦 Outros", "🏢 Condomínio"], salvos)
    assert mapa == {"🎬 Streaming": CORTAVEL, "📦 Outros": SEM_TIPO, "🏢 Condomínio": FIXA}


def test_janela_so_meses_completos_e_a_partir_do_c6():
    meses = meses_da_janela(date(2026, 10, 14), 3)
    assert [str(m) for m in meses] == ["2026-07", "2026-08", "2026-09"]
    assert [str(m) for m in meses_da_janela(date(2026, 10, 14), 12, "2026-08-20")] == ["2026-08", "2026-09"]


def test_custo_minimo_e_media_com_mes_zerado():
    desp = pd.DataFrame([
        {"data": "2026-08-05", "categoria": "🏢 Condomínio", "valor": "1000"},
        {"data": "2026-08-10", "categoria": "🛒 Supermercado", "valor": "600"},
        {"data": "2026-08-12", "categoria": "🎮 Lazer", "valor": "300"},
        {"data": "2026-09-05", "categoria": "🏢 Condomínio", "valor": "1000"},
        {"data": "2026-09-30", "categoria": "💸 Pix Avulso", "valor": "999"},
        {"data": "2026-10-01", "categoria": "🏢 Condomínio", "valor": "5000"},   # fora da janela
    ])
    meses = [pd.Period("2026-08", "M"), pd.Period("2026-09", "M")]
    mapa = classificar(desp["categoria"].unique(), pd.DataFrame())
    mensal = gasto_mensal_por_tipo(desp, mapa, meses)
    assert mensal.loc[pd.Period("2026-09", "M"), ESSENCIAL] == 0
    assert custo_minimo(mensal) == 1300.0                 # (1600 + 1000) / 2
    assert mensal[FORA].sum() == 999
    cat = media_por_categoria(desp, mapa, meses)
    assert cat.iloc[0].to_dict() == {"categoria": "🏢 Condomínio", "tipo": FIXA, "media_mes": 1000.0}
