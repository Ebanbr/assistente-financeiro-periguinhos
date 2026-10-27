# API do app do celular para o Google Cloud Run. Construir da raiz do projeto:
#   docker build -f api/Dockerfile .
FROM python:3.13-slim
WORKDIR /app
COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
COPY config.py dados.py categorias.py cupom_fiscal.py expense_defaults.py fatura_projection.py ./
COPY api/ api/
ENV PORT=8080
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT}
