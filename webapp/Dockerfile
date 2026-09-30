# Two stages: uv builds the app's virtual environment, then only that environment is copied into
# a clean image. The final image has no uv, pip or build cache: just Python and the app.
# Both stages use the same base, so the environment's interpreter paths stay valid.
ARG PYTHON_IMAGE=python:3.12-slim

FROM ${PYTHON_IMAGE} AS build
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src
# Dependencies first (cached), then the app itself, installed as a regular package.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable

FROM ${PYTHON_IMAGE}
# No package manager at run time, and an unprivileged user.
RUN rm -rf /usr/local/lib/python3.12/site-packages/pip* /usr/local/bin/pip* \
    && useradd --system --uid 1000 --no-create-home app \
    && mkdir -p /data/uploads && chown app /data/uploads
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UPLOAD_DIR=/data/uploads
USER 1000
EXPOSE 8000
CMD ["uvicorn", "--factory", "fashion_webapp.app:create_app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
