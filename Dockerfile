# Servidor do ESTADO-MAIOR: Python 3.12 + FastAPI + Uvicorn + NumPy, servindo também o front-end (web/).
FROM python:3.12-slim

WORKDIR /app

# Dependências primeiro: esta camada só é refeita quando requirements.txt muda.
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

COPY server/ /app/server/
COPY web/ /app/web/

ENV DATA_DIR=/data \
    WEB_DIR=/app/web \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Usuário sem privilégios. O diretório /data pertence a ele; um volume nomeado
# herda essa posse na primeira criação.
RUN groupadd --gid 10001 estado \
    && useradd --uid 10001 --gid estado --home-dir /app --no-create-home --shell /usr/sbin/nologin estado \
    && mkdir -p /data \
    && chown -R estado:estado /data

# Estado da partida (state.json, turns/, secret.key) fica aqui e sobrevive a reinícios.
VOLUME /data
EXPOSE 8000

USER estado

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/server_time', timeout=4)"

WORKDIR /app/server

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
