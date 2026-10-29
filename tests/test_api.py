"""API do app do celular: regras com uma planilha em memória (nada vai ao Google Sheets)."""
import json
from datetime import date, timedelta

import pandas as pd
import pytest

from api import acesso, servico
from api.planilha import _para_df
from cupom_fiscal import NotaPendente, NotaSemItens, ler_nfce

from test_cupom_fiscal import CHAVE, LINK, PAGINA_CONSULTA, XML
from test_cupom_fiscal import OFFLINE as CHAVE_PAGINA

PAGINA = PAGINA_CONSULTA.replace("28/10/2026", "26/10/2026")   # antes do "hoje" fixo dos testes

OFFLINE = "26261000943155000242651070005674329182615687"
LINK_OFFLINE = f"http://nfce.sefaz.pe.gov.br/nfce-web/consultarNFCe{OFFLINE}|2|1|26|56.61|BC41"


class PlanilhaFalsa:
    """Mesmas operações da Planilha de verdade, guardando listas de dicionários."""

    def __init__(self, **abas):
        self.abas = {k: [dict(l) for l in v] for k, v in abas.items()}

    def ler(self, tabela, fresca=False):
        linhas = self.abas.get(tabela, [])
        if not linhas:
            return pd.DataFrame()
        cab = list(dict.fromkeys(c for l in linhas for c in l))
        return _para_df([cab] + [[str(l.get(c, "")) for c in cab] for l in linhas], tabela)

    def anexar(self, tabela, linhas):
        self.abas.setdefault(tabela, []).extend(dict(l) for l in linhas)
        return len(linhas)

    def atualizar(self, tabela, coluna, valor, campos):
        alvo = [l for l in self.abas.get(tabela, []) if str(l.get(coluna)) == str(valor)]
        for l in alvo:
            l.update(campos)
        return len(alvo)

    def excluir(self, tabela, coluna, valores):
        antes = self.abas.get(tabela, [])
        self.abas[tabela] = [l for l in antes if str(l.get(coluna)) not in {str(v) for v in valores}]
        return len(antes) - len(self.abas[tabela])


HOJE = date(2026, 10, 27)   # terça


@pytest.fixture(autouse=True)
def _hoje_fixo(monkeypatch):
    monkeypatch.setattr(servico, "hoje", lambda: HOJE)
    servico._LIDOS.clear()


def _gasto(**kw):
    base = {"id": "g1", "data": "2026-10-27", "descricao": "Padaria", "categoria": "🥖 Padaria",
            "valor": "10.24", "forma_pagamento": "💳 Crédito", "banco": "C6 BRU", "status": "Pago",
            "observacao": "", "fonte": "Semanal", "criado_em": "2026-10-27T08:00:00"}
    return {**base, **kw}


def test_lancar_gasto_grava_quem_lancou_e_aparece_na_semana():
    p = PlanilhaFalsa(despesas=[_gasto()])
    linha = servico.lancar_gasto(p, {"data": "2026-10-26", "descricao": "Abastece Aí", "categoria": "🚗 Transporte",
                                     "valor": 150, "forma_pagamento": "📱 PIX", "banco": "C6 BRU"}, "Pixi")
    assert linha["lancado_por"] == "Pixi" and linha["fonte"] == "Semanal"
    assert linha["banco"] == ""            # banco só vale no crédito
    sem = servico.semana(p, HOJE)
    assert (sem["inicio"], sem["fim"], sem["total"]) == ("2026-10-26", "2026-11-01", 160.24)
    assert [d["data"] for d in sem["dias"]] == ["2026-10-27", "2026-10-26"]   # mais recente primeiro
    assert sem["dias"][1]["compras"][0]["lancado_por"] == "Pixi"


def test_lancar_gasto_recusa_duplicado_futuro_e_sem_categoria():
    p = PlanilhaFalsa(despesas=[_gasto()])
    dup = {"data": "2026-10-27", "descricao": "Padaria", "categoria": "🥖 Padaria", "valor": 10.24,
           "forma_pagamento": "💳 Crédito", "banco": "C6 BRU"}
    with pytest.raises(servico.Duplicado):
        servico.lancar_gasto(p, dup, "BOo")
    with pytest.raises(servico.ErroDeUso, match="futuro"):
        servico.lancar_gasto(p, {**dup, "data": "2026-10-28"}, "BOo")
    with pytest.raises(servico.ErroDeUso, match="categoria"):
        servico.lancar_gasto(p, {**dup, "categoria": "Inventada", "valor": 5}, "BOo")
    with pytest.raises(servico.ErroDeUso, match="cartão"):
        servico.lancar_gasto(p, {**dup, "banco": "", "valor": 5}, "BOo")


def test_estorno_negativo_entra():
    p = PlanilhaFalsa(despesas=[_gasto()])
    linha = servico.lancar_gasto(p, {"descricao": "Amazon estorno", "categoria": "🥖 Padaria", "valor": -34.9,
                                     "forma_pagamento": "💳 Crédito", "banco": "C6 BRU"}, "BOo")
    assert linha["valor"] == -34.9 and linha["data"] == "2026-10-27"


def test_semana_usa_limite_da_excecao_e_recorta_no_encerramento():
    p = PlanilhaFalsa(
        despesas=[_gasto(id="a", data="2026-09-29"), _gasto(id="b", data="2026-10-02", valor="20")],
        limites_semanais=[{"chave": "padrao", "valor": "500"}, {"chave": "2026-09-28", "valor": "300"}],
        fechamentos_fatura=[{"ano": "2026", "mes": "11", "cartao": "C6 BRU", "dia": "1", "encerrada_em": "2026-10-01"}],
    )
    sem = servico.semana(p, date(2026, 10, 2))
    assert (sem["inicio"], sem["fim"], sem["recortada"]) == ("2026-10-02", "2026-10-04", True)
    assert (sem["limite"], sem["total"], sem["restante"]) == (300.0, 20.0, 280.0)


def test_editar_e_excluir_so_mexem_no_que_foi_lancado_a_mao():
    p = PlanilhaFalsa(despesas=[_gasto(), _gasto(id="c6", fonte="C6 Bank", categoria="🛒 Supermercado")])
    servico.editar_gasto(p, "g1", {"valor": 12.5, "categoria": "🛒 Supermercado"})
    assert p.abas["despesas"][0]["valor"] == 12.5 and p.abas["despesas"][0]["categoria"] == "🛒 Supermercado"
    with pytest.raises(servico.ErroDeUso):
        servico.excluir_gasto(p, "c6")
    assert servico.excluir_gasto(p, "g1") == 1
    assert [l["id"] for l in p.abas["despesas"]] == ["c6"]


def test_cupom_lido_e_lancado_por_categoria_com_itens():
    p = PlanilhaFalsa(despesas=[_gasto()])
    lido = servico.ler_cupom_qr(p, LINK, leitor=lambda link: ler_nfce(XML))
    json.dumps(lido)   # a resposta precisa virar JSON (nada de tipos do numpy)
    assert lido["status"] == "ok" and lido["total"] == 20.62 and len(lido["itens"]) == 3
    assert {i["categoria"] for i in lido["itens"]} == {"🥬 Hortifruti", "🧽 Limpeza"}
    r = servico.lancar_cupom(p, {"chave": CHAVE, "estabelecimento": "Mercado Exemplo",
                                 "forma_pagamento": "📱 PIX", "categorias": {"2": "🛒 Supermercado"}}, "BOo")
    assert r["total"] == 20.62 and r["linhas"] == 3
    linhas = [l for l in p.abas["despesas"] if l["observacao"] == f"NFC-e {CHAVE}"]
    assert sorted(l["categoria"] for l in linhas) == ["🛒 Supermercado", "🥬 Hortifruti", "🧽 Limpeza"]
    assert len(p.abas["itens_cupom"]) == 3
    sem = servico.semana(p, date(2026, 10, 10))
    json.dumps(sem)
    compra = sem["dias"][0]["compras"][0]
    assert compra["cupom"] and compra["total"] == 20.62 and sum(len(c["itens"]) for c in compra["categorias"]) == 3
    with pytest.raises(servico.Duplicado):
        servico.lancar_cupom(p, {"chave": CHAVE, "link": LINK, "estabelecimento": "X", "forma_pagamento": "📱 PIX"},
                             "BOo", leitor=lambda link: ler_nfce(XML))


def test_nota_offline_lanca_total_e_depois_troca_pela_divisao():
    p = PlanilhaFalsa(despesas=[_gasto(categoria="🛒 Supermercado")])

    def pendente(link):
        raise NotaPendente({"chave": CHAVE, "cnpj": "00000000000191", "data": "2026-10-10", "total": 20.62,
                            "link": link})
    lido = servico.ler_cupom_qr(p, LINK, leitor=pendente)
    json.dumps(lido)
    assert lido["status"] == "pendente" and not lido["ja_lancado"]
    servico.lancar_cupom_so_total(
        p, {"link": LINK, "estabelecimento": "Recibom", "forma_pagamento": "💳 Crédito", "banco": "C6 BRU"}, "Pixi",
        leitor_offline=lambda link: {"chave": CHAVE, "cnpj": "1", "data": "2026-10-10", "total": 20.62, "link": link})
    assert [c["chave"] for c in servico.cupons_esperando(p)] == [CHAVE]
    lido = servico.ler_cupom_qr(p, LINK, leitor=lambda link: ler_nfce(XML))
    assert lido["substitui_total"] and lido["forma_pagamento"] == "💳 Crédito" and lido["banco"] == "C6 BRU"
    servico.lancar_cupom(p, {"chave": CHAVE, "estabelecimento": "Recibom", "forma_pagamento": "💳 Crédito",
                             "banco": "C6 BRU"}, "Pixi")
    do_cupom = [l for l in p.abas["despesas"] if CHAVE in str(l["observacao"])]
    assert all("pendentes" not in l["observacao"] for l in do_cupom)
    assert round(sum(float(l["valor"]) for l in do_cupom), 2) == 20.62
    assert servico.cupons_esperando(p) == []


def test_nota_normal_que_a_sefaz_nao_liberou_lanca_com_total_digitado():
    p = PlanilhaFalsa(despesas=[_gasto(categoria="🛒 Supermercado")])

    def nao_liberada(link):
        raise NotaPendente({"chave": CHAVE, "cnpj": "1", "data": None, "total": None, "link": link})
    lido = servico.ler_cupom_qr(p, LINK, leitor=nao_liberada)
    json.dumps(lido)
    assert lido["status"] == "pendente" and lido["total"] is None and "ainda não liberou" in lido["mensagem"]
    pedido = {"link": LINK, "estabelecimento": "Bio Farma", "categoria": "🛒 Supermercado",
              "forma_pagamento": "📱 PIX"}
    with pytest.raises(servico.ErroDeUso, match="total"):
        servico.lancar_cupom_so_total(p, pedido, "Bruno")
    with pytest.raises(servico.ErroDeUso, match="Data"):
        servico.lancar_cupom_so_total(p, {**pedido, "total": 8.9, "data": "2026-10-28"}, "Bruno")
    servico.lancar_cupom_so_total(p, {**pedido, "total": 8.9}, "Bruno")      # sem data = hoje
    linha = [l for l in p.abas["despesas"] if CHAVE in str(l["observacao"])][0]
    assert (linha["valor"], linha["data"], linha["observacao"]) == (8.9, "2026-10-27", f"NFC-e {CHAVE} · itens pendentes")
    assert [c["chave"] for c in servico.cupons_esperando(p)] == [CHAVE]
    lido = servico.ler_cupom_qr(p, LINK, leitor=lambda link: ler_nfce(XML))   # chegou: troca pelos itens
    assert lido["substitui_total"]


def test_qr_sem_itens_fica_so_com_o_total():
    p = PlanilhaFalsa(despesas=[_gasto(observacao=f"NFC-e {OFFLINE} · itens pendentes")])

    def sem_itens(link):
        raise NotaSemItens({"chave": OFFLINE, "cnpj": "1", "data": "2026-10-14", "total": 56.61, "link": link})
    lido = servico.ler_cupom_qr(p, LINK_OFFLINE, leitor=sem_itens)
    json.dumps(lido)
    assert lido["status"] == "sem_itens"
    assert servico.ficar_so_com_total(p, OFFLINE) == 1
    assert p.abas["despesas"][0]["observacao"] == f"NFC-e {OFFLINE}"


def test_login_token_e_bloqueio(monkeypatch):
    monkeypatch.setattr(acesso, "usuarios", lambda: {"BOo": "senha-de-teste"})
    monkeypatch.setattr(acesso, "_tentativas", {})
    token = acesso.entrar("BOo", "senha-de-teste", agora=1000)
    assert acesso.usuario_do_token(token, agora=2000) == "BOo"
    assert acesso.usuario_do_token(token, agora=1000 + acesso.VALIDADE_SEGUNDOS + 1) is None
    assert acesso.usuario_do_token(token[:-1] + ("0" if token[-1] != "0" else "1"), agora=2000) is None
    for _ in range(5):
        with pytest.raises(PermissionError, match="incorretos"):
            acesso.entrar("BOo", "errada", agora=3000)
    with pytest.raises(PermissionError, match="Espere"):
        acesso.entrar("BOo", "senha-de-teste", agora=3010)
    assert acesso.entrar("BOo", "senha-de-teste", agora=3000 + 301)


def test_contingencia_sem_itens_pela_pagina_da_consulta_troca_o_total():
    p = PlanilhaFalsa(despesas=[_gasto(id="t1", data="2026-10-27", descricao="Super Exemplo", categoria="🛒 Supermercado",
                                       valor="1020.5", observacao=f"NFC-e {CHAVE_PAGINA} · itens pendentes")])
    with pytest.raises(servico.ErroDeUso, match="outra nota"):
        servico.ler_cupom_pagina(p, OFFLINE, PAGINA)
    with pytest.raises(servico.ErroDeUso, match="não é o resultado"):
        servico.ler_cupom_pagina(p, CHAVE_PAGINA, "<html><body>Consulta NFC-e</body></html>")
    lido = servico.ler_cupom_pagina(p, CHAVE_PAGINA, PAGINA)
    json.dumps(lido)
    assert lido["status"] == "ok" and lido["substitui_total"] and len(lido["itens"]) == 3
    assert lido["estabelecimento"] == "Super Exemplo" and lido["total"] == 1020.5
    servico._LIDOS.clear()                     # servidor reiniciou entre ler e lançar: usa a página enviada
    servico.lancar_cupom(p, {"chave": CHAVE_PAGINA, "html": PAGINA, "estabelecimento": "Super Exemplo",
                             "forma_pagamento": "📱 PIX"}, "Bruno")
    do_cupom = [l for l in p.abas["despesas"] if CHAVE_PAGINA in str(l["observacao"])]
    assert all("pendentes" not in l["observacao"] for l in do_cupom) and len(do_cupom) >= 2
    assert round(sum(float(l["valor"]) for l in do_cupom), 2) == 1020.5
    assert len(p.abas["itens_cupom"]) == 3
