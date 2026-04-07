# Multi-stage build for SkillFlow: lightweight, production-ready image
# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /tmp
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# git is required when GITLAB_REPO_URL is set (clone / pull skills at startup)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY src/ src/
COPY dev-skills/ dev-skills/
COPY config/ config/
COPY web/ web/

# Health check: lightweight liveness (does not scan skills or call LLM)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=5).read()" || exit 1

# Expose web server port
EXPOSE 5000

# Default environment variables (can be overridden)
ENV LLM_API_URL=http://hzllmapi.dyn.nesc.nokia.net:8080/v1/chat/completions
ENV LLM_MODEL=qwen/qwen3-32b
ENV FLASK_ENV=production
# Optional: set to a GitLab HTTPS clone URL to pull skills at container start
# ENV GITLAB_REPO_URL=https://gitlabe2.ext.net.nokia.com/boam-fh-ai/dev-skills.git
# ENV GITLAB_BRANCH=main
# ENV GITLAB_TOKEN=<your-personal-access-token>

# Run Flask application
CMD ["python", "-m", "src.app"]
