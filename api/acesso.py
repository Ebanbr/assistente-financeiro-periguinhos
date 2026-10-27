"""Login do app do celular: as mesmas senhas do Streamlit ([usuarios] do secrets.toml).

O login devolve um token assinado (HMAC) que vale 90 dias; 5 senhas erradas bloqueiam o
usuário por 5 minutos, como no Streamlit.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from api.planilha import RAIZ

VALIDADE_SEGUNDOS = 90 * 24 * 3600
_MAX_TENTATIVAS, _BLOQUEIO_SEGUNDOS = 5, 300
_tentativas = {}


def _toml():
    try:
        import toml
        return toml.load(RAIZ / ".streamlit" / "secrets.toml")
    except Exception:
        return {}


def usuarios():
    """APP_USUARIOS (JSON {usuario: senha}) no servidor; no PC, a seção [usuarios] do secrets.toml."""
    bruto = os.environ.get("APP_USUARIOS")
    if bruto:
        return json.loads(bruto)
    return dict(_toml().get("usuarios", {}))


def _segredo():
    s = os.environ.get("API_SEGREDO") or _toml().get("api", {}).get("segredo")
    if not s:
        # sem segredo configurado (teste no PC): vale até a API reiniciar
        s = _segredo.temporario = getattr(_segredo, "temporario", None) or secrets.token_hex(32)
    return s.encode()


def _assinar(corpo):
    return hmac.new(_segredo(), corpo, hashlib.sha256).hexdigest()


def entrar(usuario, senha, agora=None):
    """Confere a senha e devolve o token; levanta PermissionError com a mensagem para a tela."""
    agora = agora or time.time()
    falhas, desde = _tentativas.get(usuario, (0, 0))
    if falhas >= _MAX_TENTATIVAS and agora - desde < _BLOQUEIO_SEGUNDOS:
        raise PermissionError("Muitas tentativas. Espere 5 minutos.")
    esperado = str(usuarios().get(usuario, ""))
    if not esperado or not hmac.compare_digest(str(senha).encode(), esperado.encode()):
        falhas = 0 if agora - desde >= _BLOQUEIO_SEGUNDOS else falhas
        _tentativas[usuario] = (falhas + 1, agora)
        raise PermissionError("Usuário ou senha incorretos.")
    _tentativas.pop(usuario, None)
    corpo = base64.urlsafe_b64encode(json.dumps({"u": usuario, "exp": int(agora + VALIDADE_SEGUNDOS)}).encode())
    return f"{corpo.decode()}.{_assinar(corpo)}"


def usuario_do_token(token, agora=None):
    """Usuário dono do token, ou None se inválido/vencido."""
    try:
        corpo, assinatura = str(token).rsplit(".", 1)
        if not hmac.compare_digest(assinatura, _assinar(corpo.encode())):
            return None
        dados = json.loads(base64.urlsafe_b64decode(corpo.encode()))
    except (ValueError, TypeError):
        return None
    if dados.get("exp", 0) < (agora or time.time()) or dados.get("u") not in usuarios():
        return None
    return dados["u"]
