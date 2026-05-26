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
DISCORDCODEX_GITHUB_TOKEN=
DISCORDCODEX_GITHUB_TOKEN_FILE=
```

`DISCORDCODEX_GITHUB_TOKEN` is used at container startup to write a Git credential store under `/data`, configure Git with `GIT_CONFIG_GLOBAL`, and export `GH_TOKEN` for GitHub CLI/API access. This is useful for private GitHub repos and GitHub data such as issues and pull requests. `DISCORDCODEX_GIT_USERNAME` defaults to `x-access-token` when omitted.

Use a fine-grained token scoped only to the repositories Codex should inspect or modify. Grant only the permissions you need, such as contents, issues, and pull requests. Avoid administration, secrets, workflow/actions, packages, and organization-wide permissions.

Use exactly one GitHub token source per container. For new installs, choose either `DISCORDCODEX_GITHUB_TOKEN` or `DISCORDCODEX_GITHUB_TOKEN_FILE`, and remove unused legacy variables such as `GITHUB_TOKEN`, `GH_TOKEN`, `DISCORDCODEX_GIT_CREDENTIAL_TOKEN`, `DISCORDCODEX_GIT_CREDENTIAL_TOKEN_FILE`, `DISCORDCODEX_GITHUB_API_TOKEN`, and `DISCORDCODEX_GITHUB_API_TOKEN_FILE` from the container environment.

For Docker, prefer `DISCORDCODEX_GITHUB_TOKEN_FILE` and mount the token file read-only. This keeps the token value out of Docker's configured environment while still letting the entrypoint read it at startup. The file should contain only the token value on the first line.

For compatibility, `DISCORDCODEX_GIT_CREDENTIAL_TOKEN`, `DISCORDCODEX_GIT_CREDENTIAL_TOKEN_FILE`, `DISCORDCODEX_GITHUB_API_TOKEN`, `DISCORDCODEX_GITHUB_API_TOKEN_FILE`, `GITHUB_USERNAME`, `GITHUB_TOKEN`, and `GH_TOKEN` are also accepted. Prefer `DISCORDCODEX_GITHUB_TOKEN_FILE` for new Docker installs.

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

Set `DISCORDCODEX_CODEX_MODEL=latest` to have the Docker entrypoint resolve OpenAI's current latest model at container startup and write it to `DISCORDCODEX_CODEX_CONFIG`, which defaults to `/data/codex-home/shared/config.toml`. If the lookup fails, the existing Codex config is left unchanged.

By default, each channel keeps one Codex conversation session. The first message starts a new session and later messages resume it with `codex exec resume`. Set `persistent_session` to `false` on a project to keep stateless per-message runs.

### GitHub Project Provisioning

DiscordCodex can poll GitHub and provision missing repositories as projects. GitHub is treated as the source of truth for new repos only; if a repo is deleted or hidden from the token later, DiscordCodex leaves existing channels, folders, and config entries alone.

Example:

```json
{
  "github_provisioning": {
    "enabled": true,
    "owner": "TallFarang",
    "poll_interval_seconds": 3600,
    "run_on_startup": true,
    "project_root": "/projects",
    "codex_home_root": "/data/codex-home",
    "codex_home_template": "/data/codex-home-template",
    "admin_channel_name": "neo",
    "include_archived": true
  }
}
```

The poller runs once at startup and then every `poll_interval_seconds`; the recommended default is `3600` seconds, or once per hour. Use `!pollgh` in Discord to run the same provisioning process on demand.

For each missing repository, DiscordCodex:

- creates or reuses a Discord text channel named after the repo, such as `discordcodex`;
- creates or reuses `/projects/<repo-name>` and clones the repo when the folder is missing or empty;
- creates `/data/codex-home/<repo-name>` from `codex_home_template`, or as an empty directory when no template is configured;
- appends the new channel mapping to `config/projects.json`;
- posts the provisioning report to the admin channel, normally `#neo`.

If GitHub provisioning is enabled, `config/projects.json` must be writable by the bot because new channel mappings are appended automatically. Docker deployments that use provisioning should not mount `/config` read-only.

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
  DISCORDCODEX_GITHUB_TOKEN_FILE: /run/secrets/discordcodex_github_token
volumes:
  - ./config:/config:ro
  - ./data:/data
  - ./secrets:/run/secrets:ro
  - /path/to/projects:/projects
```

Only add the `_FILE` environment entry when the token file exists.

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

On the first normal text message in each configured channel, DiscordCodex sends the usage guide once, then continues running Codex for that same message. The guide is not sent on container restart. Use `!help` to show it again at any time.

- `!status`: show whether Codex is running in the current channel.
- `!cancel`: request cancellation for the current channel's active run.
- `!tail`: show the tail of the latest raw log for the current channel.
- `!session`: show the current channel's stored Codex session.
- `!new`: clear the current channel's stored Codex session.
- `!projects`: list configured project names.
- `!pollgh`: run GitHub project provisioning immediately when enabled.
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
- DiscordCodex strips bot/runtime secrets from the environment before launching `codex exec`. If GitHub credentials are configured through the Docker entrypoint, Codex receives `GIT_CONFIG_GLOBAL` for Git access and `GH_TOKEN` for GitHub CLI/API access.
- In Docker, prefer `DISCORDCODEX_GITHUB_TOKEN_FILE` so Docker inspect and exec sessions do not receive the token value through the configured container environment.
- Keep only one GitHub token source configured for the container. Remove unused token variables instead of leaving old values in place.
- If the GitHub token can write to repositories, keep it limited to the mapped repositories and require confirmation before GitHub write actions.
- Rotate Discord and GitHub tokens if they are pasted into chat, logs, or terminals.
