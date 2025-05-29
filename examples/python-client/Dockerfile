# Stage 1: Build flare-ai-kit
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS flare-ai-kit-builder
COPY /pyproject.toml /uv.lock /src /README.md /flare-ai-kit/
WORKDIR /flare-ai-kit
RUN uv sync --frozen

# Stage 2: Final Image
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install supervisor and git
RUN apt-get update && apt-get install -y supervisor curl git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the built flare-ai-kit
COPY --from=flare-ai-kit-builder /flare-ai-kit /flare-ai-kit

# Copy and install dependencies to python-client
COPY examples/python-client .
RUN uv sync --frozen
RUN uv pip install /flare-ai-kit

# Set virtual environment
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Setup supervisor configuration
COPY examples/python-client/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Allow workload operator to override environment variables
LABEL "tee.launch_policy.allow_env_override"="GEMINI_API_KEY,GEMINI_MODEL,WEB3_PROVIDER_URL,WEB3_EXPLORER_URL,SIMULATE_ATTESTATION"
LABEL "tee.launch_policy.log_redirect"="always"

# Expose the port used by the server script
EXPOSE 4433

# Start supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]