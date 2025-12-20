# Codoc Dockerfile
# Generate documentation from codebases using an agentic workflow

FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for outputs and setup
RUN mkdir -p /app/outputs /app/setup_dirs

# Default environment variables (override at runtime)
ENV GROQ_API_KEY="" \
    OPENAI_API_KEY=""

# Expose volume mount points
VOLUME ["/app/outputs", "/app/setup_dirs"]

# Default command - show help
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
