# ============================================================
#  activity_log.py — Log de Atividades
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path

LOG_PATH = Path("data") / "log_atividades.parquet"
LOG_PATH.parent.mkdir(exist_ok=True)


def _ler_log() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(LOG_PATH)
    except:
        return pd.DataFrame()


def _salvar_log(df: pd.DataFrame):
    try:
        df.to_parquet(LOG_PATH, engine="pyarrow", index=False)
    except:
        pass


def registrar(acao: str, detalhes: str = ""):
    """Registra uma ação no log (sempre local, nunca GSheets)."""
    usuario = st.session_state.get("usuario", "Sistema")
    nova = pd.DataFrame([{
        "data_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usuario":   usuario,
        "acao":      acao,
        "detalhes":  detalhes,
    }])
    df = _ler_log()
    df = pd.concat([nova, df], ignore_index=True) if not df.empty else nova
    _salvar_log(df)


def exibir_log(limite: int = 50):
    """Exibe o log de atividades formatado."""
    df = _ler_log()
    if df.empty:
        st.info("Nenhuma atividade registrada ainda.")
        return

    EMOJI = {
        "BOo":  "🧔",
        "Pixi": "👩",
        "Sistema": "🤖",
    }

    for _, row in df.head(limite).iterrows():
        usuario  = str(row.get("usuario", "?"))
        acao     = str(row.get("acao", ""))
        detalhes = str(row.get("detalhes", ""))
        data_hora = str(row.get("data_hora", ""))

        # Formata data
        try:
            dt = datetime.strptime(data_hora, "%Y-%m-%d %H:%M:%S")
            data_fmt = dt.strftime("%d/%m/%Y às %H:%M")
        except:
            data_fmt = data_hora

        emoji = EMOJI.get(usuario, "👤")
        detalhe_html = f"<span style='color:#556878;font-size:0.85rem'> — {detalhes}</span>" if detalhes else ""

        st.markdown(
            f"<div style='padding:6px 0; border-bottom:1px solid #21262D'>"
            f"{emoji} <b style='color:#E6EDF3'>{usuario}</b> "
            f"<span style='color:#8BAFC9'>{acao}</span>{detalhe_html} "
            f"<span style='color:#30363D;font-size:0.8rem;float:right'>{data_fmt}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
