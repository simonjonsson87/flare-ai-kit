# Dockerfile


# Stage 1: Build Backend
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS backend-builder
# Install core SDK
COPY /pyproject.toml /uv.lock /src /README.md /flare-ai-kit/
WORKDIR /flare-ai-kit
RUN uv sync --frozen
#RUN ls -l /flare-ai-kit/.venv/bin/ 

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Stage 2: Final Image
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

RUN apt-get update && apt-get install -y supervisor curl && \
    rm -rf /var/lib/apt/lists/*

#RUN ls
COPY examples/python-client .
COPY --from=backend-builder /flare-ai-kit /flare-ai-kit
RUN ls
RUN head pyproject.toml
RUN ls -ld /flare-ai-kit || echo "flare-ai-kit not found at /flare-ai-kit"
RUN uv sync --frozen
#RUN ls /app/.venv/bin

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Setup supervisor configuration
COPY examples/python-client/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Allow workload operator to override environment variables
LABEL "tee.launch_policy.allow_env_override"="GEMINI_API_KEY,GEMINI_MODEL,WEB3_PROVIDER_URL,WEB3_EXPLORER_URL,SIMULATE_ATTESTATION"
LABEL "tee.launch_policy.log_redirect"="always"

EXPOSE 8080

# Start supervisor (which will the backend)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]