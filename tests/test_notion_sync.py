import pandas as pd

import notion_sync
import notion_import
from notion_import import linhas_do_notion, mesclar_notion


def _reg(nome, venc, valor, tipo="Mercado", rec_des="Despesa", banco="BB", pago=True):
    return {"Nome": nome, "Vencimento": venc, "Valor": valor, "Tipo": tipo,
            "Rec/Des": rec_des, "Banco": banco, "Pago": pago}


def test_linhas_do_notion_separa_receita_despesa_e_descarta_invalidos():
    regs = [
        _reg("Escola", "2026-10-13", -130.0, tipo="Madre de Deus"),
        _reg("Salário", "2026-10-05", 5000.0, tipo="Trabalho", rec_des="Receita", pago=False),
        _reg("", "2026-10-01", -10.0),            # sem nome
        _reg("Sem data", "", -10.0),              # sem data
        _reg("Zerado", "2026-10-01", 0),          # sem valor
        _reg("Vazio", "2026-10-01", None),        # número vazio no Notion
    ]
    d, r = linhas_do_notion(regs)
    assert [(x["descricao"], x["valor"], x["categoria"], x["forma_pagamento"]) for x in d] == [
        ("Escola", 130.0, "Madre de Deus", "BB")]
    assert [(x["descricao"], x["status"]) for x in r] == [("Salário", "A Receber")]
    assert all(x["fonte"] == "Notion" for x in d + r)


def test_mesclar_troca_so_notion_e_mantem_categoria_do_notion(monkeypatch):
    # Regras do app NÃO são aplicadas por padrão: categoria é a do Notion.
    monkeypatch.setattr(notion_import, "aplicar_mapeamentos",
                        lambda df, tipo=None: df.assign(categoria="RECATEGORIZADO"))
    d_atual = pd.DataFrame([
        {"id": "1", "data": "2026-09-01", "descricao": "Velho", "valor": 1.0, "categoria": "X", "fonte": "Notion"},
        {"id": "2", "data": "2026-09-01", "descricao": "Fatura", "valor": 2.0, "categoria": "Y", "fonte": "C6 Bank", "banco": "C6 BRU"},
        {"id": "3", "data": "2026-09-08", "descricao": "Mercado", "valor": 3.0, "categoria": "Z", "fonte": "Semanal"},
    ])
    r_atual = pd.DataFrame([{"id": "4", "data": "2026-09-01", "descricao": "R", "valor": 9.0, "fonte": "Manual"}])
    d, r = linhas_do_notion([
        _reg("Escola", "2026-10-13", -130.0, tipo="Madre de Deus"),
        _reg("Resumo C6", "2026-09-10", -500.0, tipo="Cartões", banco="C6 BRU"),   # mês já detalhado
        _reg("Resumo C6 out", "2026-10-10", -400.0, tipo="Cartões", banco="C6 BRU"),
    ])
    df_d, df_r, td, tr, pulados = mesclar_notion(d_atual, r_atual, d, r)
    assert df_d["fonte"].tolist().count("Notion") == 2 and "Velho" not in df_d["descricao"].tolist()
    assert set(df_d.loc[df_d["fonte"] != "Notion", "id"]) == {"2", "3"}
    assert df_d.loc[df_d["descricao"] == "Escola", "categoria"].item() == "Madre de Deus"
    assert (td, tr, pulados) == (2, 0, 1)
    assert df_r["id"].tolist() == ["4"]
    df_d2, *_ = mesclar_notion(d_atual, r_atual, d, r, aplicar_regras=True)
    assert df_d2.loc[df_d2["descricao"] == "Escola", "categoria"].item() == "RECATEGORIZADO"


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code, self._p, self.headers, self.text = status, payload or {}, {}, ""
    def json(self):
        return self._p


def _pagina(tipo_id):
    return {"properties": {
        "Nome": {"type": "title", "title": [{"plain_text": "Escola"}]},
        "Tipo": {"type": "relation", "relation": [{"id": tipo_id}]},
        "Ano": {"type": "relation", "relation": [{"id": "ano-2026"}]},
    }}


def test_busca_resolve_so_relacoes_pedidas_e_acusa_falha(monkeypatch):
    chamadas = []
    monkeypatch.setattr(notion_sync, "_post", lambda path, body: _Resp(200, {
        "results": [_pagina("tipo-ok"), _pagina("tipo-ruim")], "has_more": False}))
    def fake_get(path):
        chamadas.append(path)
        if path.endswith("tipo-ruim"):
            return _Resp(404)
        return _Resp(200, {"properties": {"t": {"type": "title", "title": [{"plain_text": "Madre de Deus"}]}}})
    monkeypatch.setattr(notion_sync, "_get", fake_get)
    regs, erro = notion_sync.buscar_registros("x" * 32, so_relacoes={"Tipo"})
    assert regs[0]["Tipo"] == "Madre de Deus" and regs[0]["Ano"] == "ano-2026"
    assert "pages/ano-2026" not in chamadas          # relação não pedida não custa chamada
    assert erro and "1 página" in erro                # falha não vira categoria vazia em silêncio


def test_retry_em_limite_de_taxa(monkeypatch):
    respostas = iter([_Resp(429), _Resp(502), _Resp(200)])
    monkeypatch.setattr(notion_sync.time, "sleep", lambda s: None)
    assert notion_sync._com_retry(lambda: next(respostas)).status_code == 200
