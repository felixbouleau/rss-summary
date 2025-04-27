FROM python:3.13-slim AS base
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.6.17 /uv /uvx /bin/
RUN groupadd -r appuser && useradd -m -d /home/appuser -r -g appuser appuser

FROM base AS builder
ENV UV_LINK_MODE=copy
COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM base AS final
COPY --from=builder /app /app
RUN chown -R appuser:appuser /app
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=info
# Add the virtual environment's bin directory to the PATH
ENV PATH="/app/.venv/bin:$PATH"
# Set VIRTUAL_ENV so tools like uv run work correctly without activation
ENV VIRTUAL_ENV=/app/.venv
ENV UV_CACHE_DIR=/app/uv-cache/
COPY prompt.j2 .
USER appuser

CMD ["uv", "run", "rss_summarizer.py"]
