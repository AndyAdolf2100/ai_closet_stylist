FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LANGSMITH_TRACING=false
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY stylist ./stylist
# Install the runtime from the checked-in lockfile.
RUN pip install --no-cache-dir uv==0.10.10 && uv sync --frozen --no-dev
RUN groupadd --gid 10001 stylist && useradd --uid 10001 --gid stylist --no-create-home stylist \
    && mkdir -p var && chown stylist:stylist var
USER 10001:10001
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "stylist.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-graceful-shutdown", "260", "--no-proxy-headers"]
