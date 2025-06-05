# Dockerfile
FROM python:3.12-slim
WORKDIR /app
# Install system dependencies
RUN apt-get update && apt-get install -y gcc \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Update the project's environment
RUN uv sync

COPY app/* .

CMD ["uv", "run", "kopf", "run", "operator.py", "--verbose"]