FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libvirt-dev \
    qemu-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment
ENV PYTHONPATH=/app
ENV API_HOST=0.0.0.0
ENV API_PORT=8000
ENV API_DEBUG=false

# Data directory for DB and converted images
RUN mkdir -p /app/data /app/logs

EXPOSE 8000

CMD ["python", "src/main.py", "api"]
