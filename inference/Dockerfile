# Serves the MLflow model imported from fashion-seg-train (models/fashion-maskrcnn).
# Build context: repository root.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2 \
    MLFLOW_DISABLE_AGENT_HINT=1

# The model pins its own runtime requirements; install them first for layer caching.
COPY models/fashion-maskrcnn/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY models/fashion-maskrcnn /opt/model

EXPOSE 5000
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/ping')"]

# One worker: each worker loads its own copy of the ~1 GB TensorFlow model.
CMD ["mlflow", "models", "serve", "-m", "/opt/model", "--env-manager", "local", \
     "--host", "0.0.0.0", "--port", "5000", "--workers", "1"]
