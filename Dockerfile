FROM isheji-registry-vpc.cn-beijing.cr.aliyuncs.com/devops_dev/python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LANGSMITH_TRACING=false
WORKDIR /app
RUN pip install --no-cache-dir uv==0.10.10
COPY pyproject.toml uv.lock README.md ./
# Keep dependency installation cached when only application code changes.
RUN uv sync --frozen --no-dev --no-install-project
COPY stylist ./stylist
COPY deploy/docker/start.sh /usr/local/bin/stylist-start
RUN uv sync --frozen --no-dev
RUN /app/.venv/bin/python -m stylist.image_assets
RUN groupadd --gid 10001 stylist && useradd --uid 10001 --gid stylist --no-create-home stylist \
    && mkdir -p var && chown stylist:stylist var
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["/bin/sh", "/usr/local/bin/stylist-start"]
CMD ["/app/.venv/bin/uvicorn", "stylist.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-graceful-shutdown", "260", "--no-proxy-headers"]
