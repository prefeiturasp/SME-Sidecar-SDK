ARG PYTHON_VERSION=3.12

# ---------- Stage 1: builder ----------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --upgrade pip build \
    && python -m build --wheel --outdir /build/dist

# ---------- Stage 2: runtime ----------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SME_SDK_ENABLED=true \
    SME_LOG_FORMAT=json

RUN groupadd --system sme && useradd --system --gid sme --create-home sme

WORKDIR /app

COPY --from=builder /build/dist/*.whl /tmp/

RUN pip install --upgrade pip \
    && pip install /tmp/*.whl \
    && rm -rf /tmp/*.whl

USER sme

CMD ["python", "-c", "from sme_sidecar_sdk import runtime; runtime.configure(); print('SME Sidecar SDK ready')"]
