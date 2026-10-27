"""Acesso ao Google Sheets para a API do app do celular — sem Streamlit.

Diferente do Streamlit (que regrava a aba inteira), aqui cada operação mexe só nas linhas
dela: lançamento novo é ``append_rows``; edição e exclusão acham a linha pelo ``id`` numa
leitura fresca. Assim um lançamento pelo celular nunca apaga o que o PC gravou.
"""
import json
import os
import threading
import time
from pathlib import Path

import pandas as pd

from dados import _normalizar_coluna_data, _normalizar_schema_tabela

RAIZ = Path(__file__).resolve().parent.parent
_CACHE_SEGUNDOS = 20


_ESCOPO = ["https://www.googleapis.com/auth/spreadsheets"]


def _credenciais():
    """(credenciais, id da planilha).

    No Cloud Run basta SPREADSHEET_ID: o serviço roda como a própria conta de serviço que já
    tem acesso à planilha (sem chave JSON guardada). GCP_SERVICE_ACCOUNT (JSON) também vale;
    no PC, vem do secrets.toml.
    """
    from google.oauth2.service_account import Credentials
    conta, planilha = os.environ.get("GCP_SERVICE_ACCOUNT"), os.environ.get("SPREADSHEET_ID")
    if planilha and conta:
        return Credentials.from_service_account_info(json.loads(conta), scopes=_ESCOPO), planilha
    if planilha:
        import google.auth
        return google.auth.default(scopes=_ESCOPO)[0], planilha
    import toml
    s = toml.load(RAIZ / ".streamlit" / "secrets.toml")
    return Credentials.from_service_account_info(dict(s["gcp_service_account"]), scopes=_ESCOPO), s["SPREADSHEET_ID"]


def _com_retry(fn, *args, tentativas=5, **kwargs):
    for i in range(tentativas):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if ("429" in str(e) or "503" in str(e)) and i < tentativas - 1:
                time.sleep(2 ** i)
            else:
                raise


class Planilha:
    def __init__(self):
        self._lock = threading.Lock()
        self._abas = {}
        self._cache = {}
        self._planilha = None

    def _doc(self):
        if self._planilha is None:
            import gspread
            creds, planilha_id = _credenciais()
            self._planilha = gspread.authorize(creds).open_by_key(planilha_id)
        return self._planilha

    def _aba(self, tabela):
        if tabela not in self._abas:
            from gspread.exceptions import WorksheetNotFound
            try:
                self._abas[tabela] = self._doc().worksheet(tabela)
            except WorksheetNotFound:
                self._abas[tabela] = self._doc().add_worksheet(title=tabela, rows=1000, cols=25)
        return self._abas[tabela]

    def _valores(self, tabela):
        return _com_retry(self._aba(tabela).get_all_values)

    def ler(self, tabela, fresca=False):
        """Aba → DataFrame (datas em ISO, valor numérico). Falha de leitura levanta, nunca vira vazio."""
        agora = time.monotonic()
        em_cache = self._cache.get(tabela)
        if not fresca and em_cache and agora - em_cache[0] < _CACHE_SEGUNDOS:
            return em_cache[1].copy()
        df = _para_df(self._valores(tabela), tabela)
        self._cache[tabela] = (agora, df)
        return df.copy()

    def invalidar(self, tabela):
        self._cache.pop(tabela, None)

    def _cabecalho(self, tabela, colunas):
        """Cabeçalho da aba; acrescenta no fim as colunas que faltarem (ex.: lancado_por)."""
        ws = self._aba(tabela)
        cab = [str(c).strip() for c in _com_retry(ws.row_values, 1)]
        faltam = [c for c in colunas if c not in cab]
        if faltam:
            if len(cab) + len(faltam) > ws.col_count:
                _com_retry(ws.add_cols, len(cab) + len(faltam) - ws.col_count)
            _com_retry(ws.update, [cab + faltam], f"A1", value_input_option="RAW")
            cab = cab + faltam
        return cab

    def anexar(self, tabela, linhas):
        """Acrescenta linhas no fim da aba, na ordem do cabeçalho."""
        if not linhas:
            return 0
        with self._lock:
            colunas = list(dict.fromkeys(c for linha in linhas for c in linha))
            cab = self._cabecalho(tabela, colunas)
            valores = [[_celula(linha.get(c, "")) for c in cab] for linha in linhas]
            _com_retry(self._aba(tabela).append_rows, valores, value_input_option="RAW",
                       insert_data_option="INSERT_ROWS", table_range="A1")
            self.invalidar(tabela)
        return len(linhas)

    def _linhas_por(self, tabela, coluna, valores_alvo):
        """(cabeçalho, [(nº da linha na planilha, linha)]) das linhas cuja ``coluna`` está em ``valores_alvo``."""
        todos = self._valores(tabela)
        if not todos:
            return [], []
        cab = [str(c).strip() for c in todos[0]]
        if coluna not in cab:
            return cab, []
        i = cab.index(coluna)
        alvo = {str(v) for v in valores_alvo}
        achadas = [(n, linha) for n, linha in enumerate(todos[1:], start=2)
                   if i < len(linha) and str(linha[i]).strip() in alvo]
        return cab, achadas

    def atualizar(self, tabela, coluna, valor_chave, campos):
        """Troca ``campos`` nas linhas em que ``coluna`` == ``valor_chave``. Devolve quantas mudou."""
        with self._lock:
            cab = self._cabecalho(tabela, list(campos))
            _, achadas = self._linhas_por(tabela, coluna, [valor_chave])
            ws = self._aba(tabela)
            for n, linha in achadas:
                nova = list(linha) + [""] * (len(cab) - len(linha))
                for c, v in campos.items():
                    nova[cab.index(c)] = _celula(v)
                _com_retry(ws.update, [nova], f"A{n}", value_input_option="RAW")
            self.invalidar(tabela)
            return len(achadas)

    def excluir(self, tabela, coluna, valores_chave):
        """Apaga as linhas em que ``coluna`` está em ``valores_chave`` (de baixo para cima)."""
        with self._lock:
            _, achadas = self._linhas_por(tabela, coluna, valores_chave)
            ws = self._aba(tabela)
            for n, _ in sorted(achadas, reverse=True):
                _com_retry(ws.delete_rows, n)
            self.invalidar(tabela)
            return len(achadas)


def _celula(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def _para_df(valores, tabela):
    if not valores or len(valores) < 2:
        return pd.DataFrame()
    cab, vistos, idx = valores[0], set(), []
    for i, h in enumerate(cab):
        h = str(h).strip()
        if h and h not in vistos:
            idx.append((i, h))
            vistos.add(h)
    dados = [[linha[i] if i < len(linha) else "" for i, _ in idx] for linha in valores[1:]]
    df = pd.DataFrame(dados, columns=[h for _, h in idx])
    df = df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)].reset_index(drop=True)
    if df.empty:
        return df
    df = _normalizar_coluna_data(_normalizar_schema_tabela(df, tabela))
    if "valor" in df.columns:
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
    return df
