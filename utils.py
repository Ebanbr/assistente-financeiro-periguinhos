# ============================================================
#  utils.py — Funções Utilitárias
#  Backend: Google Sheets (produção) | Parquet (local sem secrets)
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import streamlit as st
import pandas as pd
from datetime import datetime, date
import uuid
from pathlib import Path

# ── DIRETÓRIO LOCAL (fallback sem GSheets) ───────────────────
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# ── GOOGLE SHEETS ────────────────────────────────────────────

def _get_secrets() -> dict:
    """Lê secrets do Streamlit ou do arquivo toml diretamente."""
    try:
        # Contexto Streamlit (produção e local via st.secrets)
        if "gcp_service_account" in st.secrets:
            return {
                "gcp_service_account": dict(st.secrets["gcp_service_account"]),
                "SPREADSHEET_ID": st.secrets["SPREADSHEET_ID"],
            }
    except:
        pass
    try:
        # Fallback: lê o arquivo toml diretamente
        import toml
        secrets = toml.load(Path(__file__).parent / ".streamlit" / "secrets.toml")
        if "gcp_service_account" in secrets and "SPREADSHEET_ID" in secrets:
            return secrets
    except:
        pass
    return {}

def _usar_gsheets() -> bool:
    s = _get_secrets()
    return bool(s.get("gcp_service_account") and s.get("SPREADSHEET_ID"))

def _get_worksheet(tabela: str):
    from google.oauth2.service_account import Credentials
    import gspread

    s = _get_secrets()
    creds = Credentials.from_service_account_info(
        s["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    client = gspread.authorize(creds)
    sh = client.open_by_key(s["SPREADSHEET_ID"])
    try:
        return sh.worksheet(tabela)
    except Exception:
        return sh.add_worksheet(title=tabela, rows=5000, cols=25)

def _gsheet_com_retry(fn, *args, tentativas=5, **kwargs):
    """Chama fn(*args, **kwargs) com retry exponencial em caso de 429."""
    import time
    for i in range(tentativas):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) and i < tentativas - 1:
                espera = 2 ** i  # 1s, 2s, 4s, 8s...
                time.sleep(espera)
            else:
                raise

@st.cache_data(ttl=300, show_spinner=False)
def _ler_gsheet(tabela: str, _v: int = 0) -> pd.DataFrame:
    try:
        ws = _get_worksheet(tabela)
        all_values = _gsheet_com_retry(ws.get_all_values)
        if not all_values or len(all_values) < 2:
            return pd.DataFrame()
        header = all_values[0]
        rows = all_values[1:]
        # Remove colunas com cabeçalho vazio ou duplicado
        seen = set()
        cols_validas = []
        for i, h in enumerate(header):
            h = str(h).strip()
            if h and h not in seen:
                cols_validas.append((i, h))
                seen.add(h)
        indices = [i for i, _ in cols_validas]
        nomes   = [h for _, h in cols_validas]
        dados = [[row[i] if i < len(row) else "" for i in indices] for row in rows]
        df = pd.DataFrame(dados, columns=nomes)
        df = df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)].reset_index(drop=True)
        if df.empty:
            return pd.DataFrame()
        # Migração: renomeia coluna legada 'cartao' → 'banco'
        if "cartao" in df.columns and "banco" not in df.columns:
            df = df.rename(columns={"cartao": "banco"})

        # Migração: popula 'banco' a partir da descrição para registros Notion
        if "banco" in df.columns and "descricao" in df.columns:
            _BANCO_DE_DESC = {
                "cartão c6 bru": "C6 BRU", "cartao c6 bru": "C6 BRU",
                "cartão c6 pri": "C6 PRI", "cartao c6 pri": "C6 PRI",
                "cartão nu pri":  "Nubank",  "cartao nu pri":  "Nubank",
                "cartão nu bru":  "Nubank",  "cartao nu bru":  "Nubank",
                "cartão nubank":  "Nubank",  "cartao nubank":  "Nubank",
            }
            mask_vazio = df["banco"].astype(str).str.strip().isin(["", "nan", "None"])
            if mask_vazio.any():
                def _inferir_banco(desc):
                    d = str(desc).strip().lower()
                    for k, v in _BANCO_DE_DESC.items():
                        if k in d:
                            return v
                    return ""
                df.loc[mask_vazio, "banco"] = df.loc[mask_vazio, "descricao"].apply(_inferir_banco)

        if "data" in df.columns:
            df["data_dt"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
        if "valor" in df.columns:
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)

        # ── Validação de colunas esperadas ────────────────────
        COLUNAS_ESPERADAS = {
            "despesas":    ["id","data","descricao","categoria","valor","forma_pagamento","status","fonte"],
            "receitas":    ["id","data","descricao","categoria","valor","forma_recebimento","status","fonte"],
            "cartoes":     ["id","nome","bandeira","limite","dia_vencimento"],
            "mapeamentos": ["id","padrao","categoria","tipo"],
        }
        if tabela in COLUNAS_ESPERADAS:
            faltando = [c for c in COLUNAS_ESPERADAS[tabela] if c not in df.columns]
            if faltando:
                st.warning(
                    f"⚠️ A aba **{tabela}** no Google Sheets está com colunas faltando: "
                    f"`{', '.join(faltando)}`. Verifique se o cabeçalho foi alterado."
                )

        return df
    except Exception as e:
        st.error(f"❌ Erro ao ler Google Sheets ({tabela}): {e}")
        return pd.DataFrame()

def _salvar_gsheet(tabela: str, df: pd.DataFrame):
    try:
        ws = _get_worksheet(tabela)
        _ler_gsheet.clear()  # invalida cache após escrita

        if df.empty:
            ws.clear()
            return

        df_export = df.copy()
        # Migração: garante que coluna legada 'cartao' sai como 'banco' ao salvar
        if "cartao" in df_export.columns and "banco" not in df_export.columns:
            df_export = df_export.rename(columns={"cartao": "banco"})
        if "data_dt" in df_export.columns:
            df_export = df_export.drop(columns=["data_dt"])

        for col_num in ["valor", "limite"]:
            if col_num in df_export.columns:
                df_export[col_num] = df_export[col_num].apply(
                    lambda x: f"{float(x):.2f}" if str(x).strip() not in ("", "nan") else "0.00"
                )

        df_export = df_export.fillna("").astype(str)
        header = df_export.columns.tolist()
        rows   = df_export.values.tolist()
        # update com resize=True sobrescreve tudo sem precisar de clear() separado
        _gsheet_com_retry(ws.update, [header] + rows, value_input_option="USER_ENTERED")
        # Limpa linhas extras que sobraram de versões anteriores maiores
        total_linhas = len(rows) + 1
        _gsheet_com_retry(ws.resize, rows=max(total_linhas, 1))
    except Exception as e:
        st.error(f"❌ Erro ao salvar Google Sheets ({tabela}): {e}")

# ── FUNÇÕES PÚBLICAS ─────────────────────────────────────────

def configurar_pagina(titulo: str, icone: str = "🐧"):
    st.set_page_config(
        page_title=f"{icone} {titulo}",
        page_icon=icone,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    # Carrega CSS global
    css_path = Path(__file__).parent / "style.css"
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def cabecalho_pagina(titulo: str, subtitulo: str, icone: str):
    st.markdown(f"# {icone} {titulo}")
    st.markdown(f"*{subtitulo}*")

def inicializar_dados():
    DATA_DIR.mkdir(exist_ok=True)

def formatar_moeda(valor: float) -> str:
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    except:
        return "R$ 0,00"

def formatar_data(d: date) -> str:
    if isinstance(d, str):
        return d
    return d.strftime("%d/%m/%Y")

def formatar_data_br(valor: str) -> str:
    if not valor or pd.isna(valor):
        return ""
    try:
        for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"]:
            try:
                return pd.to_datetime(valor, format=fmt).strftime("%d/%m/%Y")
            except:
                continue
        return str(valor)
    except:
        return str(valor)

def data_hoje() -> date:
    return date.today()

def mensagem_sucesso(msg: str):
    st.success(f"✅ {msg}")

def mensagem_erro(msg: str):
    st.error(f"❌ {msg}")

def mensagem_aviso(msg: str):
    st.warning(f"⚠️ {msg}")

def gerar_id() -> str:
    return str(uuid.uuid4())[:8].upper()

def agora() -> str:
    return datetime.now().isoformat()

# ── LEITURA ──────────────────────────────────────────────────

def _resolve_tabela(arquivo) -> str:
    s = str(arquivo).lower()
    if "despesas"        in s: return "despesas"
    if "receitas"        in s: return "receitas"
    if "cartoes"         in s: return "cartoes"
    if "lancamentos"     in s: return "lancamentos"
    if "mapeamentos"     in s: return "mapeamentos"
    if "metas"           in s: return "metas"
    if "bancos"           in s: return "bancos"
    if "formas_pagamento" in s: return "formas_pagamento"
    if "log_atividades"   in s: return "log_atividades"
    return ""

def aplicar_mapeamentos(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica regras de categorização automática baseadas na descrição."""
    if df.empty or "descricao" not in df.columns:
        return df
    from config import MAPEAMENTOS_FILE
    regras = ler_csv(MAPEAMENTOS_FILE)
    if regras.empty:
        return df
    df = df.copy()
    for _, regra in regras.iterrows():
        padrao   = str(regra.get("padrao", "")).strip()
        categoria = str(regra.get("categoria", "")).strip()
        tipo     = str(regra.get("tipo", "ambos")).strip().lower()
        if not padrao or not categoria:
            continue
        mask = df["descricao"].astype(str).str.contains(padrao, case=False, na=False, regex=False)
        if tipo == "despesa" and "tipo" in df.columns:
            mask = mask & (df["tipo"] == "despesa")
        elif tipo == "receita" and "tipo" in df.columns:
            mask = mask & (df["tipo"] == "receita")
        df.loc[mask, "categoria"] = categoria
    return df

def invalidar_cache(tabela: str):
    """Invalida o cache só da tabela modificada, sem derrubar as demais."""
    from config import DESPESAS_FILE, RECEITAS_FILE, MAPEAMENTOS_FILE, CARTOES_FILE
    _ALIAS = {
        DESPESAS_FILE:    "despesas",
        RECEITAS_FILE:    "receitas",
        MAPEAMENTOS_FILE: "mapeamentos",
        CARTOES_FILE:     "cartoes",
        "despesas": "despesas", "receitas": "receitas",
        "mapeamentos": "mapeamentos", "cartoes": "cartoes",
    }
    chave = _ALIAS.get(tabela, str(tabela))
    if "_data_versions" not in st.session_state:
        st.session_state["_data_versions"] = {}
    st.session_state["_data_versions"][chave] = st.session_state["_data_versions"].get(chave, 0) + 1


def adicionar_categoria(tipo: str, nome: str):
    """Persiste uma nova categoria no config JSON."""
    from config import CONFIG_FILE
    cfg = ler_json(str(CONFIG_FILE))
    chave = f"categorias_extras_{tipo}"
    extras = cfg.get(chave, [])
    nome = nome.strip()
    if nome and nome not in extras:
        extras.append(nome)
        cfg[chave] = extras
        salvar_json(str(CONFIG_FILE), cfg)


def listar_categorias(tipo: str = "despesa") -> list:
    """Retorna todas as categorias únicas usadas + as dos mapeamentos + extras do config."""
    from config import DESPESAS_FILE, RECEITAS_FILE, MAPEAMENTOS_FILE, CATEGORIAS_DESPESA, CATEGORIAS_RECEITA, CONFIG_FILE
    cats = set(CATEGORIAS_DESPESA if tipo == "despesa" else CATEGORIAS_RECEITA)
    # Categorias extras criadas pelo usuário
    cfg = ler_json(str(CONFIG_FILE))
    cats.update(cfg.get(f"categorias_extras_{tipo}", []))
    arquivo = DESPESAS_FILE if tipo == "despesa" else RECEITAS_FILE
    df = ler_csv(arquivo)
    if not df.empty and "categoria" in df.columns:
        cats.update(df["categoria"].dropna().unique().tolist())
    regras = ler_csv(MAPEAMENTOS_FILE)
    if not regras.empty and "categoria" in regras.columns:
        cats.update(regras["categoria"].dropna().unique().tolist())
    return sorted([c for c in cats if c and str(c).strip()])

def ler_csv(arquivo) -> pd.DataFrame:
    tabela = _resolve_tabela(arquivo)
    if not tabela:
        return pd.DataFrame()

    if _usar_gsheets():
        versoes = st.session_state.get("_data_versions", {})
        return _ler_gsheet(tabela, _v=versoes.get(tabela, 0))

    # ── Fallback local (Parquet) ──────────────────────────────
    arquivo_parquet = DATA_DIR / f"{tabela}.parquet"
    if not arquivo_parquet.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(arquivo_parquet)
        # Migração: renomeia coluna legada 'cartao' → 'banco'
        if "cartao" in df.columns and "banco" not in df.columns:
            df = df.rename(columns={"cartao": "banco"})
        # Migração: popula 'banco' a partir da descrição para registros Notion
        if "banco" in df.columns and "descricao" in df.columns:
            _BANCO_DE_DESC = {
                "cartão c6 bru": "C6 BRU", "cartao c6 bru": "C6 BRU",
                "cartão c6 pri": "C6 PRI", "cartao c6 pri": "C6 PRI",
                "cartão nu pri":  "Nubank",  "cartao nu pri":  "Nubank",
                "cartão nu bru":  "Nubank",  "cartao nu bru":  "Nubank",
                "cartão nubank":  "Nubank",  "cartao nubank":  "Nubank",
            }
            mask_vazio = df["banco"].astype(str).str.strip().isin(["", "nan", "None"])
            if mask_vazio.any():
                def _inferir_banco_p(desc):
                    d = str(desc).strip().lower()
                    for k, v in _BANCO_DE_DESC.items():
                        if k in d:
                            return v
                    return ""
                df.loc[mask_vazio, "banco"] = df.loc[mask_vazio, "descricao"].apply(_inferir_banco_p)
        if not df.empty and "data" in df.columns:
            df["data_dt"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
        return df
    except Exception as e:
        mensagem_erro(f"Erro ao ler {arquivo_parquet}: {e}")
        return pd.DataFrame()

# ── ESCRITA ──────────────────────────────────────────────────

def salvar_parquet(tabela: str, df: pd.DataFrame):
    """Salva no GSheets (produção) ou Parquet (local)."""
    if _usar_gsheets():
        _salvar_gsheet(tabela, df)
        return

    arquivo = DATA_DIR / f"{tabela}.parquet"
    if df.empty:
        if arquivo.exists():
            arquivo.unlink()
        return
    try:
        df_save = df.copy()
        if "data_dt" in df_save.columns:
            df_save = df_save.drop(columns=["data_dt"])
        df_save.to_parquet(arquivo, engine="pyarrow", index=False)
    except Exception as e:
        mensagem_erro(f"Erro ao salvar {tabela}: {e}")

def _salvar_novas(tabela: str, df: pd.DataFrame) -> int:
    """Adiciona linhas novas sem sobrescrever existentes. Retorna -1 se a leitura falhar."""
    if df.empty:
        return 0
    # Tenta ler dados existentes com retry embutido em _ler_gsheet
    df_existente = ler_csv(tabela)
    # Guarda em session_state se leu com sucesso, para detectar falha silenciosa
    if _usar_gsheets():
        chave_cache = f"_ultima_leitura_{tabela}"
        if not df_existente.empty:
            st.session_state[chave_cache] = len(df_existente)
        elif st.session_state.get(chave_cache, 0) > 0:
            # Leitura retornou vazio mas tínhamos dados antes → provável falha 429
            st.error(f"⚠️ Leitura de '{tabela}' falhou — salvamento cancelado para não perder dados. Tente novamente.")
            return -1

    if not df_existente.empty:
        chaves = set(zip(
            df_existente["data"].astype(str),
            df_existente["descricao"].astype(str),
            df_existente["valor"].astype(float).round(2).astype(str),
        ))
        df_novo = df[~df.apply(
            lambda r: (str(r["data"]), str(r["descricao"]), str(round(float(r["valor"]), 2))) in chaves, axis=1
        )]
        if df_novo.empty:
            return 0
        df_final = pd.concat([df_existente, df_novo], ignore_index=True)
    else:
        df_final = df.copy()
        df_novo  = df
    salvar_parquet(tabela, df_final)
    return len(df_novo)

def salvar_despesas_novas(df: pd.DataFrame) -> int:
    return _salvar_novas("despesas", df)

def salvar_receitas_novas(df: pd.DataFrame) -> int:
    return _salvar_novas("receitas", df)

def remover_por_fonte(tabela: str, fontes: list, mes: int = None, ano: int = None, cartao: str = None) -> int:
    """
    Remove linhas de 'tabela' filtrando por fonte(s) e opcionalmente por mês/ano e cartão.
    Retorna quantas linhas foram removidas.
    """
    df = ler_csv(tabela)
    if df.empty:
        return 0

    mask = df["fonte"].astype(str).isin(fontes) if "fonte" in df.columns else pd.Series([False] * len(df))

    if mes and ano and "data" in df.columns:
        dt = pd.to_datetime(df["data"], format="%Y-%m-%d", errors="coerce")
        mask = mask & (dt.dt.month == mes) & (dt.dt.year == ano)

    if cartao:
        cartao_lower = cartao.strip().lower()
        col_fp = df["forma_pagamento"].astype(str).str.strip().str.lower() if "forma_pagamento" in df.columns else pd.Series([""] * len(df))
        col_c  = df["banco"].astype(str).str.strip().str.lower() if "banco" in df.columns else pd.Series([""] * len(df))
        mask = mask & (col_fp.eq(cartao_lower) | col_c.eq(cartao_lower))

    n = int(mask.sum())
    if n > 0:
        salvar_parquet(tabela, df[~mask].copy())
    return n

def listar_cartoes_ativos() -> list:
    df = ler_csv("cartoes")
    if df.empty:
        return []
    return df["nome"].tolist() if "nome" in df.columns else []

# ── FUZZY MATCHING ───────────────────────────────────────────

def fuzzy_match_fatura(df_fatura: pd.DataFrame, df_existente: pd.DataFrame,
                        similaridade_min: int = 75, janela_dias: int = 3) -> dict:
    """
    Compara itens da fatura com lançamentos já existentes.
    Retorna dict com três listas:
      - 'duplicatas': itens da fatura que já existem (mesmo valor ±0, data próxima, desc similar)
      - 'novos': itens da fatura sem correspondência (devem ser inseridos)
      - 'matches': lista de (idx_fatura, idx_existente, score) para log
    """
    try:
        from rapidfuzz import fuzz
    except ImportError:
        return {"duplicatas": [], "novos": list(range(len(df_fatura))), "matches": []}

    duplicatas = []
    novos      = []
    matches    = []

    if df_existente.empty or "descricao" not in df_existente.columns:
        return {"duplicatas": [], "novos": list(range(len(df_fatura))), "matches": []}

    df_ex = df_existente.copy()
    df_ex["_dt"] = pd.to_datetime(df_ex.get("data", pd.Series(dtype=str)), errors="coerce")
    df_ex["_valor_num"] = pd.to_numeric(df_ex.get("valor", pd.Series(dtype=float)), errors="coerce").fillna(0)

    for i, row in df_fatura.iterrows():
        val_fat  = float(row.get("_valor", row.get("valor", 0)))
        desc_fat = str(row.get("_desc", row.get("descricao", ""))).strip().lower()
        try:
            data_fat = pd.to_datetime(str(row.get("_data_orig", row.get("data", ""))), dayfirst=True, errors="coerce")
        except:
            data_fat = pd.NaT

        melhor_score = 0
        melhor_idx   = None

        for j, ex in df_ex.iterrows():
            # Filtro por valor (exato)
            if abs(ex["_valor_num"] - val_fat) > 0.01:
                continue
            # Filtro por data (janela)
            if pd.notna(data_fat) and pd.notna(ex["_dt"]):
                delta = abs((data_fat - ex["_dt"]).days)
                if delta > janela_dias:
                    continue
            # Similaridade da descrição
            score = fuzz.partial_ratio(desc_fat, str(ex["descricao"]).strip().lower())
            if score > melhor_score:
                melhor_score = score
                melhor_idx   = j

        if melhor_score >= similaridade_min and melhor_idx is not None:
            duplicatas.append(i)
            matches.append((i, melhor_idx, melhor_score))
        else:
            novos.append(i)

    return {"duplicatas": duplicatas, "novos": novos, "matches": matches}


# ── EDITAR / DELETAR ─────────────────────────────────────────

def editar_linha(arquivo: str, id_registro: str, novos_dados: dict) -> bool:
    tabela = _resolve_tabela(arquivo)
    if tabela not in ("despesas", "receitas"):
        return False
    df = ler_csv(tabela)
    if df.empty:
        return False
    try:
        idx = df[df["id"] == id_registro].index
        if len(idx) == 0:
            return False
        for col, val in novos_dados.items():
            df.loc[idx[0], col] = val
        salvar_parquet(tabela, df)
        return True
    except:
        return False

def deletar_linha(arquivo: str, id_registro: str) -> bool:
    tabela = _resolve_tabela(arquivo)
    if tabela not in ("despesas", "receitas"):
        return False
    df = ler_csv(tabela)
    if df.empty:
        return False
    try:
        salvar_parquet(tabela, df[df["id"] != id_registro].copy())
        return True
    except:
        return False

# ── JSON ─────────────────────────────────────────────────────

def ler_json(arquivo: str) -> dict:
    import json
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def salvar_json(arquivo: str, dados: dict):
    import json
    try:
        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except:
        pass

def salvar_csv(arquivo: str, df: pd.DataFrame):
    """Stub de compatibilidade — não faz nada."""
    pass
