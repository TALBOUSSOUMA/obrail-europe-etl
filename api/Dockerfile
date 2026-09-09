# ObRail Europe API image (FastAPI).
#
# Built from the REPO ROOT (context: . in docker-compose.yml), not from
# api/, because the API imports ml/predict.py directly to serve /predict
# (see main.py): it therefore needs the ml/ folder next to it in the
# image, exactly as it does locally.
#
#   docker build -f api/Dockerfile -t obrail-api .

FROM python:3.12-slim

# No .pyc written to disk, logs shown immediately (useful for
# `docker compose logs -f api` during development).
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies installed before copying the source code: Docker caches
# this step as long as the requirements files don't change, which
# greatly speeds up rebuilds during development.
COPY api/requirements.txt ./api/requirements.txt
COPY ml/requirements-predict.txt ./ml/requirements-predict.txt
RUN pip install --no-cache-dir \
    -r ./api/requirements.txt \
    -r ./ml/requirements-predict.txt

# API code
COPY api/ ./api/
# Only what /predict needs: the inference script and the already-trained
# model (not the training notebooks/scripts).
COPY ml/predict.py ./ml/predict.py
COPY ml/models/ ./ml/models/

WORKDIR /app/api

EXPOSE 8000

# Checks that the API responds AND that the database is reachable
# (the /health endpoint runs a SELECT 1) - this is what docker-compose
# uses to know when the other services can start.
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
