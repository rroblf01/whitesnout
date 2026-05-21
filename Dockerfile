FROM rust:1.95.0-slim-trixie

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV PATH="/root/.cargo/bin:/root/.local/bin:$PATH"

RUN cargo install maturin

WORKDIR /app

CMD ["bash"]
