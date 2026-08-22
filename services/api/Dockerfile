# One image, two entrypoints: `gridlab.web.app` (api) and `gridlab.agent.app` (agent).
#
# Build context is the REPOSITORY ROOT, not services/api, because the image needs
# docs/electricity-maps-api.md: it is the contract that tests/test_signals.py asserts the
# capability matrix against. Keeping one copy of that document, rather than a second one
# next to the code, is worth a wider build context.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Dependencies first, so source edits do not bust the layer cache.
COPY services/api/pyproject.toml services/api/README.md ./
RUN mkdir -p src/gridlab && touch src/gridlab/__init__.py \
    && uv pip install --system -e ".[dev,tracing]"

COPY services/api/src ./src
COPY services/api/tests ./tests
COPY docs/electricity-maps-api.md ./docs/electricity-maps-api.md

# Non-root. The agent container additionally runs read-only with no volumes.
RUN useradd --create-home --uid 10001 gridlab \
    && mkdir -p /data /app/fixtures /app/scenarios \
    && chown -R gridlab:gridlab /data /app
USER gridlab

EXPOSE 8000 8001
CMD ["uvicorn", "gridlab.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
