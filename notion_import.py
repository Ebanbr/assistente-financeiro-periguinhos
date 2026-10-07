# ============================================================
#  notion_import.py — Converte o banco do Notion em despesas/receitas
#  Regra única usada pelo botão em Configurações e pela sincronização
#  automática (scripts/sync_notion.py). Funções puras, sem gravação.
#  Assistente Financeiro da Família Periguinhos 🐧
# ============================================================

import re
import unicodedata
from datetime import datetime

import pandas as pd

from utils import aplicar_mapeamentos, gerar_id, agora

# Propriedades do banco da família (os palpites padrão da tela de Configurações).
MAPA_PADRAO = {
    "nome": "Nome", "data": "Vencimento", "valor": "Valor", "categoria": "Tipo",
    "banco": "Banco", "pago": "Pago", "rec_des": "Rec/Des",
}
SEM_PAGO = "(nenhum)"
SEM_REC_DES = "(usar sinal do valor)"


def limpar_link_notion(texto):
    if pd.isna(texto): return ""
    return re.sub(r'\s*\(https?://[^\)]*\)', '', str(texto)).strip()

def limpar_valor(texto):
    if pd.isna(texto): return 0.0
    s = re.sub(r'[R$\s"\'"""]', '', str(texto)).replace('-', '')
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try: return abs(float(s))
    except: return 0.0

def to_iso(texto):
    if pd.isna(texto): return ""
    s = str(texto).strip()
    # Remove horário se vier junto (ex: "2026-01-05 00:00:00")
    s = s.split(" ")[0].split("T")[0]
    for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y",
                "%B %d, %Y", "%b %d, %Y",   # "January 5, 2026" / "Jan 5, 2026"
                "%Y/%m/%d"]:
        try: return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except: continue
    return s

def to_br(texto):
    iso = to_iso(texto)
    if not iso: return ""
    try: return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return iso

def limpar_categoria(prop, fallback="📦 Outros"):
    if not prop or pd.isna(prop): return fallback
    s = str(prop).strip()
    alfa = [c for c in s if unicodedata.category(c).startswith(("L", "N"))]
    if len(alfa) < 2: return fallback
    return s


def linhas_do_notion(registros, mapa=None):
    """Converte registros crus do Notion em (linhas_despesa, linhas_receita)."""
    m = {**MAPA_PADRAO, **(mapa or {})}
    linhas_d, linhas_r = [], []
    for r in registros:
        desc = str(r.get(m["nome"], "")).strip()
        data_iso = to_iso(str(r.get(m["data"], "")))
        if not desc or not data_iso:
            continue
        bruto = r.get(m["valor"], 0)
        # valor pode vir float (API number) ou string formatada
        if isinstance(bruto, (int, float)):
            sinal_neg = bruto < 0
            val = abs(float(bruto))
        else:
            sinal_neg = "-" in str(bruto)
            val = limpar_valor(bruto)
        cat = limpar_categoria(limpar_link_notion(r.get(m["categoria"], "")))
        banco = str(r.get(m["banco"], "")).strip()
        if m["pago"] != SEM_PAGO:
            pago = str(r.get(m["pago"], "")).lower() in ("true", "yes", "sim", "1", "✅")
        else:
            pago = True
        if m["rec_des"] != SEM_REC_DES:
            td = str(r.get(m["rec_des"], "")).lower()
            eh_receita = "rece" in td or "income" in td or "entrada" in td
        else:
            eh_receita = not sinal_neg
        if val <= 0:
            continue
        if eh_receita:
            linhas_r.append({"id": gerar_id(), "data": data_iso, "descricao": desc,
                             "categoria": limpar_categoria(cat, "📦 Outros"),
                             "valor": round(val, 2), "forma_recebimento": banco or "📱 PIX",
                             "status": "Recebida" if pago else "A Receber",
                             "observacao": "", "fonte": "Notion", "criado_em": agora()})
        else:
            linhas_d.append({"id": gerar_id(), "data": data_iso, "descricao": desc,
                             "categoria": cat, "valor": round(val, 2),
                             "forma_pagamento": banco or "Outros", "banco": "",
                             "status": "Pago" if pago else "A Pagar",
                             "observacao": "", "fonte": "Notion", "criado_em": agora()})
    return linhas_d, linhas_r


def mesclar_notion(df_d_atual, df_r_atual, linhas_d, linhas_r, aplicar_regras=False):
    """Troca só as linhas de fonte Notion; C6 Bank, Manual e Semanal ficam intactas.

    A categoria vem do "Tipo" do Notion, como a Pri cadastrou. As regras de
    categorização do app (``aplicar_regras``) ficam desligadas por padrão: ligá-las
    recategorizaria ~840 lançamentos de uma vez, e categoria é decisão do Bruno.

    Monta o conjunto final inteiro em memória (atômico). Retorna
    (df_d_final, df_r_final, n_despesas, n_receitas, resumos_pulados).
    """
    # base = tudo que NÃO é Notion (preserva C6 Bank, Manual, Semanal)
    df_d_base = (df_d_atual[df_d_atual["fonte"].astype(str) != "Notion"]
                 if not df_d_atual.empty and "fonte" in df_d_atual.columns else df_d_atual)
    df_r_base = (df_r_atual[df_r_atual["fonte"].astype(str) != "Notion"]
                 if not df_r_atual.empty and "fonte" in df_r_atual.columns else df_r_atual)

    # não re-adicionar o resumo de cartão de meses já detalhados por fatura
    detalhados = set()
    if not df_d_base.empty and "fonte" in df_d_base.columns:
        _c6 = df_d_base[df_d_base["fonte"].astype(str) == "C6 Bank"]
        for _, rr in _c6.iterrows():
            card = str(rr.get("banco", "")).strip().lower() or str(rr.get("forma_pagamento", "")).strip().lower()
            mes = str(rr.get("data", ""))[:7]
            if card and mes:
                detalhados.add((card, mes))
    linhas_d_final, pulados = [], 0
    for ln in linhas_d:
        eh_resumo = "cart" in str(ln.get("categoria", "")).lower()
        card = str(ln.get("forma_pagamento", "")).strip().lower()
        mes = str(ln.get("data", ""))[:7]
        if eh_resumo and (card, mes) in detalhados:
            pulados += 1
            continue
        linhas_d_final.append(ln)

    df_d_novo = pd.DataFrame(linhas_d_final)
    df_r_novo = pd.DataFrame(linhas_r)
    if aplicar_regras:
        df_d_novo = aplicar_mapeamentos(df_d_novo, tipo="despesa") if not df_d_novo.empty else df_d_novo
        df_r_novo = aplicar_mapeamentos(df_r_novo, tipo="receita") if not df_r_novo.empty else df_r_novo
    df_d_final = pd.concat([df_d_base, df_d_novo], ignore_index=True) if not df_d_novo.empty else df_d_base
    df_r_final = pd.concat([df_r_base, df_r_novo], ignore_index=True) if not df_r_novo.empty else df_r_base
    return df_d_final, df_r_final, len(linhas_d_final), len(linhas_r), pulados
