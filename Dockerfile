# ============================================================
# "Claro que Eu vendo!" v2 — imagem endurecida (AUS-06)
# ============================================================
FROM python:3.11-slim

# Não escrever .pyc / buffer de stdout desligado.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências primeiro (melhor cache de camadas).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código. .dockerignore exclui .env, data/*.db, .git, etc.
COPY . .

# Cria usuário sem privilégios e transfere a posse do diretório de dados.
RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Healthcheck consulta o endpoint de saúde da API.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').status==200 else 1)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
