FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DISCORDCODEX_CONFIG=/config/projects.json \
    DISCORDCODEX_DATA_DIR=/data \
    CODEX_BIN=codex

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        gpg \
        nodejs \
        npm \
    && mkdir -p -m 755 /etc/apt/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && printf 'deb [arch=%s signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main\n' "$(dpkg --print-architecture)" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && npm i -g @openai/codex \
    && gh --version \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 --shell /bin/bash discordcodex \
    && mkdir -p /config /data /projects \
    && chown -R discordcodex:discordcodex /app /config /data /projects

USER discordcodex

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["discordcodex", "--config", "/config/projects.json"]
