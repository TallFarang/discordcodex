# DiscordCodex

DiscordCodex is a self-hosted Discord bot for running Codex CLI from Discord. Map Discord channels to local project directories, then send a normal message in a mapped channel to start a `codex exec` run for that project.

The bot is intended for private servers and trusted users. It is a remote code execution bridge.

## Features

- Map one Discord channel to one project directory.
- Run Codex headlessly with `codex exec`.
- Keep one persistent Codex session per Discord channel.
- Keep raw Codex transcripts and prompts in local logs.
- Send concise Codex replies back to Discord.
- Use `!status`, `!cancel`, `!tail`, `!session`, `!new`, `!projects`, and `!help`.
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
DISCORDCODEX_GIT_USERNAME=
DISCORDCODEX_GIT_CREDENTIAL_TOKEN=
DISCORDCODEX_GIT_CREDENTIAL_TOKEN_FILE=
DISCORDCODEX_GITHUB_API_TOKEN=
DISCORDCODEX_GITHUB_API_TOKEN_FILE=
```

`DISCORDCODEX_GIT_CREDENTIAL_TOKEN` is used only at container startup to write a Git credential store under `/data` and configure Git with `GIT_CONFIG_GLOBAL`. This is useful for private GitHub repos mounted into the container. The raw token is unset before DiscordCodex starts. `DISCORDCODEX_GIT_USERNAME` defaults to `x-access-token` when omitted.

`DISCORDCODEX_GITHUB_API_TOKEN` is exported internally as `GH_TOKEN` so the GitHub CLI can read GitHub API data such as issues and pull requests. This token is intentionally available to Codex subprocesses. Use a fine-grained read-only token scoped only to the repositories Codex should inspect.

For Docker, prefer the `_FILE` variants and mount token files read-only. This keeps token values out of Docker's configured environment while still letting the entrypoint read them at startup. Each file should contain only the token value on the first line.

For compatibility, `GITHUB_USERNAME`, `GITHUB_TOKEN`, and `GH_TOKEN` are also accepted, but the `DISCORDCODEX_*` names are clearer for new installs.

Map Discord channels to projects in `config/projects.json`:

```json
{
  "channels": {
    "<DISCORD_CHANNEL_ID>": {
      "name": "webapp",
      "cwd": "/projects/webapp",
      "codex_home": "/data/codex-home/webapp",
      "persistent_session": true
    }
  }
}
```

`codex_home` should point to a writable directory that contains Codex auth/config for that project.

By default, each channel keeps one Codex conversation session. The first message starts a new session and later messages resume it with `codex exec resume`. Set `persistent_session` to `false` on a project to keep stateless per-message runs.

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
environment:
  DISCORDCODEX_GIT_CREDENTIAL_TOKEN_FILE: /run/secrets/discordcodex_git_token
  DISCORDCODEX_GITHUB_API_TOKEN_FILE: /run/secrets/discordcodex_github_api_token
volumes:
  - ./config:/config:ro
  - ./data:/data
  - ./secrets:/run/secrets:ro
  - /path/to/projects:/projects
```

Only add the `_FILE` environment entries for token files that exist.

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
- `!session`: show the current channel's stored Codex session.
- `!new`: clear the current channel's stored Codex session.
- `!projects`: list configured project names.
- `!help`: show the usage guide.

Any non-command message in a configured channel starts a Codex run.

## Logs

For each run, DiscordCodex stores:

- The prompt sent to Codex.
- The raw Codex transcript.
- Redacted metadata about the run.
- Persistent session metadata under the local data directory.

Use `!tail` when Discord output is too short and you need the raw transcript.

## Safety

- Use private Discord channels.
- Allow only trusted Discord user IDs.
- Mount only project directories the bot should edit.
- Keep `.env`, Codex auth files, and generated Git credentials out of Git.
- DiscordCodex strips bot/runtime secrets from the environment before launching `codex exec`. If Git credentials are configured through the Docker entrypoint, Codex receives `GIT_CONFIG_GLOBAL` so Git can use the generated credential helper without inheriting the raw Git credential token.
- If `DISCORDCODEX_GITHUB_API_TOKEN` is configured, the entrypoint exposes it to Codex as `GH_TOKEN` for GitHub CLI/API reads. Prefer fine-grained read-only repository tokens.
- In Docker, prefer `DISCORDCODEX_GIT_CREDENTIAL_TOKEN_FILE` and `DISCORDCODEX_GITHUB_API_TOKEN_FILE` so Docker inspect and exec sessions do not receive token values through the configured container environment.
- Rotate Discord and GitHub tokens if they are pasted into chat, logs, or terminals.
