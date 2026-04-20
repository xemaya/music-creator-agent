FROM a2h/agent-base:python-3.12-http

WORKDIR /app

# Copy dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .
COPY suno_client.py .

# The base image already has uvicorn, fastapi, and the a2h SDK
# Expose the port (informational, actual port is in agent.yaml)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1
