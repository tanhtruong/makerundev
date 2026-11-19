FROM ghcr.io/astral-sh/uv:0.12-python3.13-trixie-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY packages/pacelab/pyproject.toml packages/pacelab/README.md packages/pacelab/
COPY apps/server/pyproject.toml apps/server/
RUN mkdir -p packages/pacelab/src/pacelab apps/server/src/pacelab_server \
    && uv sync --locked --no-dev --no-install-workspace --package pacelab-server

COPY packages/pacelab/src packages/pacelab/src
COPY apps/server/src apps/server/src
RUN uv sync --locked --no-dev --package pacelab-server

ENV PACELAB_DATA_DIR=/data PACELAB_HOST=0.0.0.0 PACELAB_PORT=8000
VOLUME /data
EXPOSE 8000
RUN useradd --create-home --uid 1000 pacelab && mkdir -p /data && chown pacelab /data
USER pacelab
CMD ["/app/.venv/bin/pacelab-server"]
