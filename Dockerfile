# Drive-Saver Copilot API.
#
# The model is trained during the build, not at startup, so the image is
# self contained and a cold start serves traffic immediately. The AI4I sample
# ships in the repo rather than being fetched from UCI at build time, which
# keeps builds hermetic: a deploy does not fail because an upstream host is down.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

# libgomp1 is the OpenMP runtime XGBoost links against. curl is for HEALTHCHECK.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so code edits do not invalidate the install layer.
#
# xgboost is swapped for xgboost-cpu here. On Linux the default wheel drags in
# 291 MB of NVIDIA CUDA libraries for GPU training that this service never does.
# xgboost-cpu ships the same `xgboost` module without them. The swap is Linux
# only: the macOS wheel used for local development has no such dependency.
COPY requirements.txt ./
RUN sed -i 's/^xgboost==/xgboost-cpu==/' requirements.txt \
    && pip install --no-cache-dir -r requirements.txt \
    && python -c "import xgboost; print('xgboost', xgboost.__version__)"

COPY backend/ ./backend/
COPY data/raw/ai4i2020.csv ./data/raw/ai4i2020.csv

# Bake the trained model into the image. Fails the build if training fails,
# which is what you want: a broken model should never reach a deploy.
RUN python -m backend.ml.train && test -f models/drive_saver_model.joblib

RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

# One worker by design. The telemetry store is in process, so a second worker
# would not see the first one's uploads. Scale with replicas only after that
# store moves to a database.
CMD ["sh", "-c", "exec uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
