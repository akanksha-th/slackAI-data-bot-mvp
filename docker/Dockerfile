# Stage-1: Build
FROM python:3.14-slim as build
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

# Stage-2: Runtime
FROM python:3.14-slim
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY . .
ENV PATH="/app/.venv/bin:$PATH"
# pre-download models
# RUN /app/.venv/bin/python -c "\ "
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]