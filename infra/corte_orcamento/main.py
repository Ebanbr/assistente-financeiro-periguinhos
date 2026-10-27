"""Corte automático: quando o gasto do mês no Google Cloud passa do orçamento, tira o acesso
público da API do app (o Google passa a recusar tudo antes de chegar no servidor = nada cobrado).

Recebe os avisos do orçamento (Pub/Sub, várias vezes por dia). Para religar:
  gcloud run services add-iam-policy-binding periguinhos-api --region=southamerica-east1 \
      --member=allUsers --role=roles/run.invoker
"""
import base64
import json

import functions_framework
import google.auth
from google.auth.transport.requests import AuthorizedSession

SERVICO = "https://run.googleapis.com/v2/projects/dashchaves/locations/southamerica-east1/services/periguinhos-api"


def deve_cortar(aviso):
    gasto, limite = float(aviso.get("costAmount", 0)), float(aviso.get("budgetAmount", 0))
    return limite > 0 and gasto >= limite


def sem_acesso_publico(politica):
    for b in politica.get("bindings", []):
        if b.get("role") == "roles/run.invoker":
            b["members"] = [m for m in b.get("members", []) if m != "allUsers"]
    politica["bindings"] = [b for b in politica.get("bindings", []) if b.get("members")]
    return politica


@functions_framework.cloud_event
def cortar(evento):
    aviso = json.loads(base64.b64decode(evento.data["message"]["data"]))
    print(f"orçamento: gasto {aviso.get('costAmount')} de {aviso.get('budgetAmount')} {aviso.get('currencyCode')}")
    if not deve_cortar(aviso):
        return
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    sessao = AuthorizedSession(creds)
    politica = sessao.get(SERVICO + ":getIamPolicy").json()
    resposta = sessao.post(SERVICO + ":setIamPolicy", json={"policy": sem_acesso_publico(politica)})
    resposta.raise_for_status()
    print("ORÇAMENTO ESTOURADO: acesso público da API removido.")
