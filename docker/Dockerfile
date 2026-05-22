# Standalone runtime image for WhiteSnout.
#
# Serves /srv as static content over HTTP on port 8000. Mount your assets:
#
#   docker run --rm -p 8000:8000 -v ./public:/srv ghcr.io/rrobles-qdq/whitesnout:latest
#
# For framework integration (FastAPI / Django / Starlette), use the wheels from
# PyPI in your own image — this Dockerfile is the standalone-server case only.

FROM python:3.13-slim

ARG WHITESNOUT_VERSION=

LABEL org.opencontainers.image.title="whitesnout" \
      org.opencontainers.image.description="ASGI-native static file server" \
      org.opencontainers.image.source="https://github.com/rrobles-qdq/whitesnout" \
      org.opencontainers.image.licenses="MIT"

RUN useradd --create-home --uid 10001 whitesnout

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install "uvicorn[standard]>=0.30" && \
    if [ -n "$WHITESNOUT_VERSION" ]; then \
        pip install "whitesnout==${WHITESNOUT_VERSION}"; \
    else \
        pip install whitesnout; \
    fi

COPY docker/serve.py /opt/whitesnout/serve.py

USER whitesnout
WORKDIR /srv
EXPOSE 8000

ENV WHITESNOUT_DIRECTORY=/srv \
    WHITESNOUT_SECURITY_HEADERS=true \
    WHITESNOUT_HEALTH_CHECK_PATH=/healthz

CMD ["uvicorn", "--host", "0.0.0.0", "--port", "8000", \
     "--app-dir", "/opt/whitesnout", "serve:app"]
