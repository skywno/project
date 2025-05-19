# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory
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

# Copy source code
COPY src/ /app/src/

# Expose port 8000
EXPOSE 8000

# Command to run the application with hot-reload
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
