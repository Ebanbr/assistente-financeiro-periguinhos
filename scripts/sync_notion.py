# ============================================================
#  scripts/sync_notion.py — Sincronização automática Notion → Sheets
#  Roda toda madrugada pelo GitHub Actions (.github/workflows/sync-notion.yml).
#  Só LÊ o Notion; no Sheets troca apenas as linhas de fonte "Notion".
#
#  Uso local:  python scripts/sync_notion.py --dry-run
#
#  ATENÇÃO: o repositório é público e os logs do Actions também. Este script
#  imprime só contagens — nunca descrições, valores ou categorias.
# ============================================================

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import notion_sync  # noqa: E402
import utils  # noqa: E402
from config import DESPESAS_FILE, RECEITAS_FILE  # noqa: E402
from notion_import import linhas_do_notion, mesclar_notion, MAPA_PADRAO  # noqa: E402

# Uma busca que volta com menos da metade do que já existe é tratada como falha
# (Notion fora do ar, paginação cortada) — melhor manter a cópia de ontem.
QUEDA_MAXIMA = 0.5


def _qtd_notion(df):
    if df.empty or "fonte" not in df.columns:
        return 0
    return int((df["fonte"].astype(str) == "Notion").sum())


def main(dry_run=False):
    if not utils._usar_gsheets():
        print("ERRO: credenciais do Google Sheets ausentes.")
        return 1
    if not notion_sync.token_configurado():
        print("ERRO: token do Notion ausente.")
        return 1
    db = notion_sync._secrets_notion().get("database_id", "")
    if not db:
        print("ERRO: database_id do Notion ausente.")
        return 1

    regs, erro = notion_sync.buscar_registros(db, so_relacoes={MAPA_PADRAO["categoria"]})
    if erro:
        print(f"ERRO ao ler o Notion: {erro}")
        return 1
    print(f"Notion: {len(regs)} registros lidos.")

    # Leitura que falha levanta exceção: nunca grava em cima de uma base vazia.
    df_d = utils._ler_gsheet(utils._resolve_tabela(DESPESAS_FILE))
    df_r = utils._ler_gsheet(utils._resolve_tabela(RECEITAS_FILE))
    antes = _qtd_notion(df_d) + _qtd_notion(df_r)

    linhas_d, linhas_r = linhas_do_notion(regs)
    df_d_final, df_r_final, td, tr, pulados = mesclar_notion(df_d, df_r, linhas_d, linhas_r)
    depois = td + tr
    print(f"Sheets antes: {antes} linhas do Notion · depois: {td} despesas + {tr} receitas "
          f"({pulados} resumo(s) de cartão pulado(s)).")

    if depois == 0:
        print("ERRO: o Notion não retornou lançamentos — nada foi alterado.")
        return 1
    if antes and depois < antes * QUEDA_MAXIMA:
        print(f"ERRO: queda suspeita ({antes} → {depois}) — nada foi alterado.")
        return 1
    if len(df_d_final) < len(df_d) - _qtd_notion(df_d) or len(df_r_final) < len(df_r) - _qtd_notion(df_r):
        print("ERRO: linhas que não são do Notion sumiriam — nada foi alterado.")
        return 1

    if dry_run:
        print("Simulação (--dry-run): nada foi gravado.")
        return 0

    if not utils.salvar_parquet("despesas", df_d_final):
        print("ERRO ao gravar despesas — nada foi alterado.")
        return 1
    if not utils.salvar_parquet("receitas", df_r_final):
        print("ERRO ao gravar receitas (despesas já atualizadas).")
        return 1
    print("Sincronização concluída.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Sincroniza o Notion com o Google Sheets.")
    ap.add_argument("--dry-run", action="store_true", help="calcula tudo, mas não grava")
    sys.exit(main(ap.parse_args().dry_run))
