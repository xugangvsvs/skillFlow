# Multi-stage build for SkillFlow: lightweight, production-ready image
# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /tmp
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY src/ src/
COPY dev-skills/ dev-skills/
COPY config/ config/
COPY web/ web/

# Health check: verify Flask endpoint is responsive
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/api/skills')" || exit 1

# Expose web server port
EXPOSE 5000

# Default environment variables (can be overridden)
ENV LLM_API_URL=http://hzllmapi.dyn.nesc.nokia.net:8080/v1/chat/completions
ENV LLM_MODEL=qwen/qwen3-32b
ENV FLASK_ENV=production

# Run Flask application
CMD ["python", "-m", "src.app"]
