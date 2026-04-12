# DiscordCodex

DiscordCodex is a self-hosted Discord bot for running Codex CLI from Discord. Map Discord channels to local project directories, then send a normal message in a mapped channel to start a `codex exec` run for that project.

The bot is intended for private servers and trusted users. It is a remote code execution bridge.

## Features

- Map one Discord channel to one project directory.
- Run Codex headlessly with `codex exec`.
- Keep raw Codex transcripts and prompts in local logs.
- Send concise Codex replies back to Discord.
- Use `!status`, `!cancel`, `!tail`, `!projects`, and `!help`.
- Run locally with Python or in Docker.
- Optionally configure GitHub credentials from environment variables for private repo access.

## Discord Setup

Create a Discord application and bot in the Discord Developer Portal.

Required bot settings:

- Enable `Message Content Intent`.
- Keep the bot in a private server.
- Invite it with permissions to view channels, send messages, and read message history.

You also need these IDs from Discord developer mode:

- Guild/server ID.
- Allowed user ID or comma-separated user IDs.
- Channel IDs for each project channel.

## Configuration

Copy the example files:

```bash
cp .env.example .env
cp config/projects.example.json config/projects.json
```

Set Discord credentials in `.env`:

```bash
DISCORD_TOKEN=
ALLOWED_GUILD_ID=
ALLOWED_USER_IDS=
DISCORDCODEX_LOG_LEVEL=INFO
```

Optional GitHub credentials:

```bash
GITHUB_USERNAME=
GITHUB_TOKEN=
```

When `GITHUB_TOKEN` is set, the Docker entrypoint writes a Git credential store under `/data` and configures Git with `GIT_CONFIG_GLOBAL`. This is useful for private GitHub repos mounted into the container.

Map Discord channels to projects in `config/projects.json`:

```json
{
  "channels": {
    "<DISCORD_CHANNEL_ID>": {
      "name": "webapp",
      "cwd": "/projects/webapp",
      "codex_home": "/data/codex-home/webapp"
    }
  }
}
```

`codex_home` should point to a writable directory that contains Codex auth/config for that project.

## Codex Auth

DiscordCodex does not require an OpenAI API key. It runs the Codex CLI, so authentication is whatever Codex CLI supports in its `CODEX_HOME`.

For headless Docker use:

1. Authenticate Codex locally.
2. Configure Codex for file credential storage.
3. Copy the Codex auth/config files into the mounted `codex_home`.
4. Treat `auth.json` like a password.

## Run Locally

Install the package:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

Run the bot:

```bash
discordcodex --config config/projects.json
```

The host must also have Codex CLI installed and authenticated. Set `CODEX_BIN` if `codex` is not on `PATH`.

## Run With Docker

Copy the Docker Compose example:

```bash
cp docker-compose.example.yml docker-compose.yml
```

Edit the project mount in `docker-compose.yml`:

```yaml
volumes:
  - ./config:/config:ro
  - ./data:/data
  - /path/to/projects:/projects
```

Build and start:

```bash
docker compose up -d --build
docker compose logs -f discordcodex
```

The container expects:

- `/config/projects.json` for channel mappings.
- `/data` for logs, Codex homes, and generated Git credentials.
- `/projects` for project workspaces.

## Discord Commands

- `!status`: show whether Codex is running in the current channel.
- `!cancel`: request cancellation for the current channel's active run.
- `!tail`: show the tail of the latest raw log for the current channel.
- `!projects`: list configured project names.
- `!help`: show the usage guide.

Any non-command message in a configured channel starts a Codex run.

## Logs

For each run, DiscordCodex stores:

- The prompt sent to Codex.
- The raw Codex transcript.
- Redacted metadata about the run.

Use `!tail` when Discord output is too short and you need the raw transcript.

## Safety

- Use private Discord channels.
- Allow only trusted Discord user IDs.
- Mount only project directories the bot should edit.
- Keep `.env`, Codex auth files, and generated Git credentials out of Git.
- DiscordCodex strips bot/runtime secrets from the environment before launching `codex exec`. If Git credentials are configured through the Docker entrypoint, Codex receives `GIT_CONFIG_GLOBAL` so Git can use the generated credential helper without inheriting the raw `GITHUB_TOKEN` environment variable.
- Rotate Discord and GitHub tokens if they are pasted into chat, logs, or terminals.
