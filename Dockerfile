FROM node:24.19.0-slim AS web

WORKDIR /src/apps/web
RUN corepack enable
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN COREPACK_ENABLE_DOWNLOAD_PROMPT=0 pnpm install --frozen-lockfile
COPY apps/web ./
COPY apps/server/openapi.json /src/apps/server/openapi.json
RUN pnpm build

FROM ghcr.io/astral-sh/uv:0.13-python3.13-trixie-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock LICENSE ./
COPY packages/makerundev/pyproject.toml packages/makerundev/README.md packages/makerundev/LICENSE packages/makerundev/
COPY apps/server/pyproject.toml apps/server/README.md apps/server/LICENSE apps/server/
RUN mkdir -p packages/makerundev/src/makerundev apps/server/src/makerundev_server \
    && uv sync --locked --no-dev --no-install-workspace --package makerundev-server

COPY packages/makerundev/src packages/makerundev/src
COPY apps/server/src apps/server/src
COPY --from=web /src/apps/server/src/makerundev_server/web apps/server/src/makerundev_server/web
RUN uv sync --locked --no-dev --package makerundev-server

ENV MAKERUNDEV_DATA_DIR=/data MAKERUNDEV_HOST=0.0.0.0 MAKERUNDEV_PORT=8000
VOLUME /data
EXPOSE 8000
RUN useradd --create-home --uid 1000 makerundev && mkdir -p /data && chown makerundev /data
USER makerundev
CMD ["/app/.venv/bin/makerundev-server"]
