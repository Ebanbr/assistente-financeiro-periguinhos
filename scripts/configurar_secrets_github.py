# ============================================================
#  scripts/configurar_secrets_github.py — Cadastra no GitHub os secrets da
#  sincronização automática do Notion, lendo do .streamlit/secrets.toml local.
#
#  Uso (uma vez, com o gh logado):  python scripts/configurar_secrets_github.py
#
#  Os valores vão direto do arquivo para o `gh secret set` via stdin:
#  nunca são impressos nem passam pela linha de comando.
# ============================================================

import json
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = "Ebanbr/assistente-financeiro-periguinhos"
ARQUIVO = Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml"


def main():
    s = tomllib.loads(ARQUIVO.read_text(encoding="utf-8"))
    secrets = {
        "SPREADSHEET_ID": s["SPREADSHEET_ID"],
        "GCP_SERVICE_ACCOUNT": json.dumps(dict(s["gcp_service_account"])),
        "NOTION_TOKEN": s["notion"]["token"],
        "NOTION_DATABASE_ID": s["notion"]["database_id"],
    }
    for nome, valor in secrets.items():
        r = subprocess.run(["gh", "secret", "set", nome, "-R", REPO],
                           input=valor, text=True, capture_output=True)
        print(f"{'✅' if r.returncode == 0 else '❌'} {nome}" + ("" if r.returncode == 0 else f": {r.stderr.strip()}"))
        if r.returncode != 0:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
