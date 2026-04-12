# DiscordCodex

DiscordCodex is a self-hosted Discord bot that maps Discord project channels to local Codex CLI runs. Every normal message from an allowed user in a configured channel starts a stateless `codex exec` process in that channel's project directory.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

The host also needs the Codex CLI installed and authenticated. Set `CODEX_BIN` if `codex` is not on `PATH`.

## Discord Setup

Create a Discord bot application, add it to your private server, and enable the Message Content Intent in the Discord Developer Portal. The bot needs permission to read messages, send messages, read message history, and attach files if you want log uploads later.

## Configure

Copy `config/projects.example.json` to `config/projects.json` and update channel IDs and paths.

Required environment variables:

```bash
export DISCORD_TOKEN="..."
export ALLOWED_GUILD_ID="123456789012345678"
export ALLOWED_USER_IDS="123456789012345678,234567890123456789"
export OPENAI_API_KEY="..."
```

Optional environment variables:

```bash
export DISCORDCODEX_CONFIG="config/projects.json"
export DISCORDCODEX_DATA_DIR="data"
export CODEX_BIN="codex"
```

## Run

```bash
discordcodex --config config/projects.json
```

Or without installing the console script:

```bash
PYTHONPATH=src python3 -m discordcodex --config config/projects.json
```

## Docker

The Docker image includes DiscordCodex and the Codex CLI. Copy the example files and edit them for your host:

```bash
cp .env.example .env
cp config/projects.example.json config/projects.json
cp docker-compose.example.yml docker-compose.yml
```

Edit `.env`, `config/projects.json`, and the project mount in `docker-compose.yml`.

Build and run:

```bash
docker compose up -d --build
docker compose logs -f discordcodex
```

The container expects:

- `/config/projects.json` for project/channel mappings.
- `/data` for DiscordCodex logs and per-project Codex homes.
- `/projects` or another host-mounted directory containing the workspaces Codex may edit.

If `GITHUB_TOKEN` is set, the container writes a Git credential store under `/data` at startup and points Git at it with `GIT_CONFIG_GLOBAL`. Set `GITHUB_USERNAME` to your GitHub username, or omit it to use `x-access-token`.

For headless account auth, configure Codex to use file credential storage and mount the relevant `CODEX_HOME` under `/data`. The Codex auth cache contains access tokens; treat it like a password and never commit it.

## Commands

- `!status`: show whether the current channel has a running Codex job.
- `!cancel`: request cancellation for the current channel's running job.
- `!tail`: show the tail of the current channel's latest log.
- `!projects`: list configured projects.
- `!help`: show commands.

## Safety

This is a remote code execution bridge. Use private Discord channels, allowlist only trusted users, run the bot under a dedicated OS user, and mount only the project directories the bot needs.
