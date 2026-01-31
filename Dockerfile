# Plan-Z Docker Image
# Multi-platform support for running Plan-Z in containers

FROM python:3.11-slim

LABEL maintainer="Plan-Z Contributors"
LABEL org.opencontainers.image.description="Cross-platform distributed job scheduler"

# Install system dependencies including Docker CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    openssh-client \
    curl \
    ca-certificates \
    gnupg \
    gosu \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and docker group
# The docker group GID will be matched at runtime via entrypoint
RUN groupadd docker 2>/dev/null || true \
    && useradd -m -s /bin/bash planz \
    && usermod -aG docker planz 2>/dev/null || true

# Set working directory
WORKDIR /app

# Copy application
COPY pyproject.toml .
COPY src/ ./src/

# Install Plan-Z
RUN pip install --no-cache-dir -e .

# Create directories for config and logs
RUN mkdir -p /home/planz/.planz/jobs /home/planz/.planz/logs \
    && chown -R planz:planz /home/planz/.planz

# Copy entrypoint script (before switching user)
COPY --chmod=755 docker-entrypoint.sh /usr/local/bin/

# Set environment variables
ENV HOME=/home/planz
ENV PLANZ_CONFIG_DIR=/home/planz/.planz

# Default entrypoint (runs as root initially to fix docker socket perms, then drops to planz)
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["planz", "--help"]
