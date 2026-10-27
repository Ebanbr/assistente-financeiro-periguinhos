"""Regras de dados sem Streamlit: datas, esquema das abas, id e carimbo de hora.

Usadas pelo app Streamlit (via utils) e pela API do app do celular.
"""
import uuid
from datetime import datetime

import pandas as pd


def _parse_data_robusta(serie) -> pd.Series:
    """Parser ÚNICO e canônico de datas — fonte de verdade do app inteiro.

    Aceita:
      • ISO  'YYYY-MM-DD' (opcional com hora) → tratado como NÃO ambíguo
      • BR   'DD/MM/YYYY' / 'DD-MM-YYYY'      → dayfirst (padrão brasileiro)

    Retorna pd.Series datetime64. Nunca usa MM/DD silenciosamente.
    """
    s = serie.astype(str).str.strip()
    # descarta hora se vier ("2026-06-05 00:00:00" / "2026-06-05T...")
    s_data = s.str.split(" ").str[0].str.split("T").str[0]
    # ISO = começa com ano de 4 dígitos (aceita '-' ou '/'); pandas trata year-first
    # sempre como AAAA-MM-DD, então não há ambiguidade de dayfirst aqui.
    # Ausências não são ISO: a máscara precisa ser booleana para usar ~.
    iso_mask = s_data.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", na=False)
    iso_parsed = pd.to_datetime(s_data.where(iso_mask).str.replace("/", "-", regex=False),
                                format="%Y-%m-%d", errors="coerce")
    # Resto: formato brasileiro, dia primeiro
    br_parsed  = pd.to_datetime(s.where(~iso_mask), dayfirst=True, errors="coerce")
    return iso_parsed.fillna(br_parsed)


def _normalizar_coluna_data(df: pd.DataFrame) -> pd.DataFrame:
    """Garante df['data_dt'] correto E df['data'] em ISO 'YYYY-MM-DD'.

    Normalizar 'data' para ISO faz com que QUALQUER pd.to_datetime() posterior
    (com ou sem dayfirst) leia a data corretamente — ISO é não ambíguo.
    """
    if "data" in df.columns:
        dt = _parse_data_robusta(df["data"])
        df["data_dt"] = dt
        df["data"] = dt.dt.strftime("%Y-%m-%d").where(dt.notna(), df["data"])
    return df


def _normalizar_schema_tabela(df: pd.DataFrame, tabela: str) -> pd.DataFrame:
    """Aplica migrações apenas nas tabelas às quais pertencem.

    `cartao -> banco` é legado exclusivo de despesas/receitas. As tabelas de
    configuração de fatura usam `cartao` de propósito.
    """
    df = df.copy()
    if tabela in ("despesas", "receitas"):
        if "cartao" in df.columns and "banco" not in df.columns:
            df = df.rename(columns={"cartao": "banco"})
    elif tabela in ("faturas_base", "fechamentos_fatura") and "banco" in df.columns:
        if "cartao" not in df.columns:
            df = df.rename(columns={"banco": "cartao"})
        else:
            vazio = df["cartao"].astype(str).str.strip().isin(["", "nan", "None"])
            df.loc[vazio, "cartao"] = df.loc[vazio, "banco"]
            df = df.drop(columns=["banco"])
    return df


def gerar_id() -> str:
    # UUID completo — risco de colisão nulo (o encurtado de 8 chars tinha risco desnecessário)
    return str(uuid.uuid4())


def agora() -> str:
    return datetime.now().isoformat()
