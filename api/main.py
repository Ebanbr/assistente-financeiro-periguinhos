"""API do app do celular (Gastos da semana).

Rodar no PC, da pasta do projeto:  uvicorn api.main:app --reload --port 8080
"""
import sys
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # módulos da raiz (config, cupom_fiscal…)

from api import acesso, servico  # noqa: E402
from api.planilha import Planilha  # noqa: E402

app = FastAPI(title="Periguinhos — app da semana")
planilha = Planilha()


def usuario_atual(authorization: str = Header(default="")):
    usuario = acesso.usuario_do_token(authorization.removeprefix("Bearer ").strip())
    if not usuario:
        raise HTTPException(401, "Entre de novo.")
    return usuario


def _executar(fn, *args):
    try:
        return fn(*args)
    except servico.Duplicado as e:
        raise HTTPException(409, str(e))
    except servico.ErroDeUso as e:
        raise HTTPException(400, str(e))


class Login(BaseModel):
    usuario: str
    senha: str


class Gasto(BaseModel):
    data: str | None = None
    descricao: str | None = None
    categoria: str | None = None
    valor: float | None = None
    forma_pagamento: str | None = None
    banco: str | None = None


class LinkQR(BaseModel):
    link: str


class LancarCupom(BaseModel):
    chave: str
    link: str | None = None
    estabelecimento: str
    forma_pagamento: str
    banco: str | None = None
    categorias: dict[str, str] = {}     # nº do item → categoria escolhida (o resto fica a sugerida)


class CupomSoTotal(BaseModel):
    link: str
    estabelecimento: str
    categoria: str | None = None
    forma_pagamento: str
    banco: str | None = None
    total: float | None = None          # nota normal: o QR não traz o total
    data: str | None = None


@app.get("/saude")
def saude():
    return {"ok": True}


@app.post("/login")
def login(dados: Login):
    try:
        return {"token": acesso.entrar(dados.usuario, dados.senha), "usuario": dados.usuario}
    except PermissionError as e:
        raise HTTPException(401, str(e))


@app.get("/opcoes")
def opcoes(usuario: str = Depends(usuario_atual)):
    return {**servico.opcoes(planilha), "usuario": usuario}


@app.get("/sugestao")
def sugestao(descricao: str, usuario: str = Depends(usuario_atual)):
    return {"categoria": servico.sugestao(planilha, descricao)}


@app.get("/semana")
def semana(dia: date | None = None, usuario: str = Depends(usuario_atual)):
    return servico.semana(planilha, dia)


@app.post("/gastos")
def lancar(gasto: Gasto, usuario: str = Depends(usuario_atual)):
    return _executar(servico.lancar_gasto, planilha, gasto.model_dump(), usuario)


@app.patch("/gastos/{id_gasto}")
@app.post("/gastos/{id_gasto}")   # o HttpURLConnection do Android não faz PATCH
def editar(id_gasto: str, gasto: Gasto, usuario: str = Depends(usuario_atual)):
    return _executar(servico.editar_gasto, planilha, id_gasto, gasto.model_dump())


@app.delete("/gastos/{id_gasto}")
def excluir(id_gasto: str, usuario: str = Depends(usuario_atual)):
    return {"excluidos": _executar(servico.excluir_gasto, planilha, id_gasto)}


@app.post("/cupom/ler")
def ler_cupom(pedido: LinkQR, usuario: str = Depends(usuario_atual)):
    return _executar(servico.ler_cupom_qr, planilha, pedido.link)


@app.post("/cupom/lancar")
def lancar_cupom(pedido: LancarCupom, usuario: str = Depends(usuario_atual)):
    return _executar(servico.lancar_cupom, planilha, pedido.model_dump(), usuario)


@app.post("/cupom/so-total")
def cupom_so_total(pedido: CupomSoTotal, usuario: str = Depends(usuario_atual)):
    return _executar(servico.lancar_cupom_so_total, planilha, pedido.model_dump(), usuario)


@app.get("/cupom/esperando")
def cupons_esperando(usuario: str = Depends(usuario_atual)):
    return servico.cupons_esperando(planilha)


@app.post("/cupom/{chave}/ficar-so-com-total")
def ficar_so_com_total(chave: str, usuario: str = Depends(usuario_atual)):
    return {"linhas": _executar(servico.ficar_so_com_total, planilha, chave)}
