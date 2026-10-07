# ============================================================
#  notion_sync.py — Integração com a API oficial do Notion
#  Assistente Financeiro da Família Periguinhos 🐧
#
#  Padrão idêntico ao acesso ao Google Sheets: o token é lido
#  de st.secrets["notion"]["token"] e NUNCA fica no código.
# ============================================================

import re
import time
import requests
import streamlit as st

API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"          # versão estável do endpoint /databases/{id}/query
TIMEOUT = 30


# ── Config / credenciais ────────────────────────────────────

def _secrets_notion() -> dict:
    try:
        return dict(st.secrets["notion"])
    except Exception:
        return {}

def token_configurado() -> bool:
    return bool(_secrets_notion().get("token"))

def _headers() -> dict:
    tok = _secrets_notion().get("token", "")
    return {
        "Authorization": f"Bearer {tok}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

def normalizar_id(valor: str) -> str:
    """Aceita URL, ID com hífens ou ID cru e devolve o ID de 32 hex."""
    if not valor:
        return ""
    s = str(valor).strip()
    # Se for URL, pega o último bloco de 32 hex
    achados = re.findall(r"[0-9a-fA-F]{32}", s.replace("-", ""))
    return achados[-1].lower() if achados else s.replace("-", "").lower()


# ── Chamadas HTTP com tratamento de erro ────────────────────

def _com_retry(fn, tentativas=5):
    """Repete em limite de taxa (429) e instabilidade (5xx) do Notion."""
    for i in range(tentativas):
        r = fn()
        if r.status_code != 429 and r.status_code < 500:
            return r
        espera = float(r.headers.get("Retry-After", 0) or 0) or 2 ** i
        time.sleep(min(espera, 30))
    return r

def _get(path: str):
    return _com_retry(lambda: requests.get(f"{API}/{path}", headers=_headers(), timeout=TIMEOUT))

def _post(path: str, body: dict):
    return _com_retry(lambda: requests.post(f"{API}/{path}", headers=_headers(), json=body, timeout=TIMEOUT))


# ── Extração genérica de propriedades ───────────────────────

def _texto(rich):
    return "".join(x.get("plain_text", "") for x in (rich or []))

def extrair_valor(prop: dict, cache_titulos: dict | None = None):
    """Converte uma propriedade do Notion em valor Python simples.

    Datas voltam em ISO 'YYYY-MM-DD' — sem ambiguidade DD/MM.
    Relações são resolvidas para os títulos das páginas (se cache fornecido).
    """
    if not isinstance(prop, dict):
        return ""
    t = prop.get("type")
    v = prop.get(t)

    if t in ("title", "rich_text"):
        return _texto(v)
    if t == "number":
        return v
    if t in ("select", "status"):
        return v.get("name", "") if v else ""
    if t == "multi_select":
        return ", ".join(x.get("name", "") for x in (v or []))
    if t == "date":
        return (v or {}).get("start", "") if v else ""
    if t == "checkbox":
        return bool(v)
    if t in ("email", "phone_number", "url", "created_time", "last_edited_time"):
        return v or ""
    if t == "people":
        return ", ".join(p.get("name", "") for p in (v or []))
    if t == "formula":
        ft = (v or {}).get("type")
        return (v or {}).get(ft, "")
    if t == "rollup":
        rt = (v or {}).get("type")
        if rt == "array":
            return ", ".join(str(extrair_valor(it, cache_titulos)) for it in v.get("array", []))
        return (v or {}).get(rt, "")
    if t == "relation":
        ids = [r.get("id") for r in (v or [])]
        if cache_titulos is not None:
            return ", ".join(titulo_pagina(i, cache_titulos) for i in ids if i)
        return ", ".join(ids)
    # Fallback
    return str(v) if v is not None else ""

_FALHAS = "__falhas__"


def titulo_pagina(page_id: str, cache: dict) -> str:
    """Busca o título de uma página (com cache) — usado p/ resolver relações."""
    if page_id in cache:
        return cache[page_id]
    nome = ""
    try:
        r = _get(f"pages/{page_id}")
        ok = r.status_code == 200
        if ok:
            props = r.json().get("properties", {})
            for p in props.values():
                if p.get("type") == "title":
                    nome = _texto(p.get("title"))
                    break
    except Exception:
        ok = False
    if ok:
        cache[page_id] = nome
        return nome
    # Falha não entra no cache: fica registrada para quem chamou decidir.
    cache.setdefault(_FALHAS, set()).add(page_id)
    return nome


# ── Inspeção do banco (descobre o esquema real) ─────────────

def inspecionar(database_id: str):
    """Retorna (info, erro): info = {'titulo','props':[(nome,tipo)], 'amostra':[dict]}"""
    dbid = normalizar_id(database_id)
    r = _get(f"databases/{dbid}")
    if r.status_code == 401:
        return None, "Token inválido ou não autorizado (401). Confira o token no secrets."
    if r.status_code == 404:
        return None, ("Banco não encontrado (404). Verifique se você **conectou a integração "
                      "ao banco** (menu ••• → Connections) e se o ID está correto.")
    if r.status_code != 200:
        return None, f"Erro {r.status_code}: {r.text[:300]}"

    meta = r.json()
    titulo = _texto(meta.get("title"))
    props_schema = meta.get("properties", {})
    props = [(nome, p.get("type", "?")) for nome, p in props_schema.items()]

    # Amostra: 3 primeiras páginas
    amostra = []
    rq = _post(f"databases/{dbid}/query", {"page_size": 3})
    if rq.status_code == 200:
        cache = {}
        for pg in rq.json().get("results", []):
            linha = {nome: extrair_valor(p, cache) for nome, p in pg.get("properties", {}).items()}
            amostra.append(linha)
    return {"titulo": titulo, "props": props, "amostra": amostra}, None


# ── Busca completa (todas as páginas, paginado) ─────────────

def buscar_registros(database_id: str, resolver_relacoes: bool = True, limite_paginas: int = 200,
                     so_relacoes=None):
    """Retorna (lista_de_dicts, erro). Cada dict = {nome_propriedade: valor}.

    ``so_relacoes`` (ex.: {"Tipo"}) resolve o título só dessas relações; as
    demais voltam como IDs. Cada relação resolvida custa uma chamada por página
    relacionada, então limitar ao que é usado deixa a busca bem mais rápida.
    Se algum título não puder ser lido, devolve erro em vez de categorias vazias.
    """
    dbid = normalizar_id(database_id)
    registros = []
    cache_titulos = {} if resolver_relacoes else None
    cursor = None
    paginas = 0

    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = _post(f"databases/{dbid}/query", body)
        if r.status_code != 200:
            return registros, f"Erro {r.status_code}: {r.text[:300]}"
        data = r.json()
        for pg in data.get("results", []):
            linha = {nome: extrair_valor(p, cache_titulos if so_relacoes is None or nome in so_relacoes else None)
                     for nome, p in pg.get("properties", {}).items()}
            registros.append(linha)
        paginas += 1
        if not data.get("has_more") or paginas >= limite_paginas:
            break
        cursor = data.get("next_cursor")

    falhas = (cache_titulos or {}).get(_FALHAS)
    if falhas:
        return registros, (f"Não foi possível ler o título de {len(falhas)} página(s) relacionada(s) "
                           f"(categoria). Tente de novo em alguns minutos.")
    return registros, None
