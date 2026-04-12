# DiscordCodex Specification

## Summary

DiscordCodex is a self-hosted Discord bot that connects Discord project channels to local Codex CLI executions. Each configured Discord channel maps to a project workspace. Messages in that channel are treated as coding instructions for that project, and the bot runs Codex in the mapped working directory.

The tool is intended to be open source and portable across macOS, Linux, and containerized environments. It must not assume QNAP, NAS-specific paths, or Docker-only deployment.

## Goals

- Let a developer use Discord channels as project-specific Codex workspaces.
- Run Codex CLI against local project directories.
- Support automatic execution for all messages in configured project channels.
- Keep project configuration explicit and auditable.
- Work on macOS, Linux, and Docker hosts.
- Provide safe defaults while allowing advanced users to opt into broader permissions.
- Persist logs for every Codex run.
- Support cancellation and basic status reporting.

## Non-Goals

- DiscordCodex is not a general chatbot framework.
- DiscordCodex is not a hosted SaaS product.
- DiscordCodex will not implement its own coding agent. Codex CLI remains the agent.
- DiscordCodex will not require Docker, though Docker deployment should be supported.
- DiscordCodex will not assume access to the host Docker socket.
- DiscordCodex will not provide multi-user collaboration controls in v1 beyond allowlists.

## Target Users

- Developers who want to control local Codex coding sessions from Discord.
- Developers who organize work by Discord channel.
- Users running Codex on a home server, workstation, NAS, or development VM.
- Users who want one bot connected to multiple local projects.

## Core Concept

Each Discord channel maps to one project:

```text
#codex-webapp       -> /projects/webapp
#codex-homebridge   -> /projects/homebridge-tools
#codex-discord-bot  -> /projects/discordcodex
```

When an allowed user posts in a configured channel, DiscordCodex runs Codex in that channel's project directory.

```text
Discord message
  -> validate guild, channel, and user
  -> load channel project config
  -> build prompt with message and optional recent channel context
  -> run codex exec in project cwd
  -> stream or summarize output back to Discord
  -> write full run log to disk
```

## Execution Model

### Default Mode

The default execution model is stateless per message:

```bash
codex exec -C <project.cwd> <prompt>
```

Each Discord message starts a new Codex CLI run. The bot may include recent Discord channel history in the prompt to provide conversational continuity.

This is preferred for v1 because it is easier to supervise, cancel, log, and recover from failure than a long-lived interactive Codex process.

### Permissions Mode

The recommended default is full autonomy inside a constrained workspace:

```bash
codex exec \
  --full-auto \
  -C <project.cwd> \
  <prompt>
```

If the installed Codex CLI version supports explicit approval and sandbox flags, DiscordCodex should support equivalent configuration:

```bash
codex exec \
  --ask-for-approval never \
  --sandbox workspace-write \
  -C <project.cwd> \
  <prompt>
```

The dangerous bypass mode should be available only as an explicit project-level setting:

```bash
codex exec \
  --dangerously-bypass-approvals-and-sandbox \
  -C <project.cwd> \
  <prompt>
```

This mode gives Codex whatever access the bot process or container has. It is not the default.

## Discord Behavior

### Message Handling

The bot ignores:

- Messages from bots.
- Direct messages, unless explicitly enabled.
- Messages outside the configured Discord guild.
- Messages from users not in the allowlist.
- Messages in channels not listed in the project config.
- Empty messages.

In a configured project channel, every normal message from an allowed user triggers Codex.
Attachments are ignored in v1. If a triggering message includes attachments, the bot should reply that attachments are not supported yet and continue using only the text content when present. If the message has attachments but no text content, it should not trigger Codex.

### Control Commands

Control commands do not trigger Codex. They are handled by the bot.

Required v1 commands:

```text
!status
!cancel
!tail
!projects
!help
```

Command behavior:

- `!status`: show whether the current channel has a running Codex job.
- `!cancel`: terminate the current channel's running Codex job.
- `!tail`: show the last part of the current channel's latest log.
- `!projects`: list configured projects visible to the current user.
- `!help`: show usage and control commands.

Slash commands may be added later, but text commands are simpler for v1 and easier to use in project channels.

### Output Handling

DiscordCodex should send short progress updates during long runs:

```text
Codex started for project `webapp`.
```

For output:

- Short output is posted directly to the channel.
- Long output is chunked.
- Very long output is saved as a log file and uploaded as an attachment if supported.
- The full log is always written to local disk.
- Discord messages should respect a conservative per-message limit from config, defaulting to 1800 characters.
- The bot should send only a bounded number of output chunks to Discord. After that, it should stop posting chunks and point users to the local log or uploaded log attachment.
- Discord API failures must be logged but must not kill the running Codex process.
- Progress updates should be throttled so long-running commands do not spam the channel.

Final message format:

```text
Codex finished for `webapp`.
Exit code: 0
Duration: 3m 42s
Log: data/logs/webapp/2026-04-11T14-22-09Z.log
```

## Concurrency

V1 uses one active Codex job per Discord channel.

If a job is already running in a channel and another normal message arrives, the bot should reject it with:

```text
Codex is already running for this channel. Use `!status` or `!cancel`.
```

Different channels may run jobs concurrently, subject to a global maximum.

Configurable limits:

- `max_concurrent_jobs_global`
- `max_output_chars_per_message`
- `default_timeout_seconds`
- `per_project_timeout_seconds`

## Configuration

DiscordCodex uses environment variables for secrets and a JSON or TOML file for project mappings.

### Environment Variables

Required:

```text
DISCORD_TOKEN
ALLOWED_GUILD_ID
ALLOWED_USER_IDS
```

Usually required:

```text
OPENAI_API_KEY
```

Optional:

```text
DISCORDCODEX_CONFIG
DISCORDCODEX_DATA_DIR
DISCORDCODEX_LOG_LEVEL
CODEX_BIN
```

### Discord Intents

The Discord bot requires the message content intent because v1 reads normal channel messages and sends them to Codex. Setup documentation should instruct users to enable the Message Content Intent in the Discord Developer Portal for the bot application.

### Project Config

Example `config/projects.json`:

```json
{
  "defaults": {
    "timeout_seconds": 1800,
    "include_recent_messages": 10,
    "codex_args": ["--full-auto"],
    "max_output_chars_per_message": 1800
  },
  "channels": {
    "111111111111111111": {
      "name": "webapp",
      "cwd": "/projects/webapp",
      "codex_home": "/data/codex-home/webapp"
    },
    "222222222222222222": {
      "name": "discordcodex",
      "cwd": "/projects/discordcodex",
      "codex_home": "/data/codex-home/discordcodex",
      "timeout_seconds": 2400
    }
  }
}
```

### Path Rules

- `cwd` must exist.
- `cwd` must be a directory.
- `codex_home` is optional.
- If `codex_home` is set, the bot creates it when missing and sets `CODEX_HOME` for that run.
- If `codex_home` cannot be created or is not writable, the project config is invalid.
- Sharing one `codex_home` across multiple projects is allowed only when explicitly configured by using the same path in those projects.
- Relative paths are resolved relative to the config file directory.
- The project config must not contain secrets.

### Startup Validation

DiscordCodex should fail fast at startup when required configuration is invalid.

Required validation:

- `DISCORD_TOKEN`, `ALLOWED_GUILD_ID`, and `ALLOWED_USER_IDS` are present.
- `ALLOWED_GUILD_ID`, `ALLOWED_USER_IDS`, and configured channel IDs parse as Discord snowflake IDs.
- `CODEX_BIN`, or `codex` from `PATH`, exists and is executable.
- Every configured `cwd` exists and is a directory.
- Every configured `codex_home`, when provided, exists or can be created and is writable.
- The data/log directory exists or can be created and is writable.
- Project names are unique after filesystem-safe normalization.
- Channel IDs are not duplicated in the project config.
- Numeric limits such as timeouts, output limits, and concurrency limits are positive.

## Prompt Construction

For each run, DiscordCodex builds a prompt with:

- The current user message.
- The project name.
- The channel name.
- Optional recent channel messages.
- Optional project-specific instructions from config.

The bot should clearly separate metadata from the user's instruction.

Prompt template:

```text
You are running inside DiscordCodex.

Project: <project.name>
Working directory: <project.cwd>
Discord channel: <channel.name>

Recent channel context:
<recent messages, newest last>

User request:
<message content>
```

Recent context must exclude bot output unless configured otherwise, to avoid feeding long logs back into Codex repeatedly.

## Logging

Every Codex run writes a structured metadata file and a text log.

Suggested layout:

```text
data/
  logs/
    <project-name>/
      2026-04-11T14-22-09Z.meta.json
      2026-04-11T14-22-09Z.log
```

Metadata fields:

```json
{
  "project": "webapp",
  "channel_id": "111111111111111111",
  "user_id": "333333333333333333",
  "started_at": "2026-04-11T14:22:09Z",
  "finished_at": "2026-04-11T14:25:51Z",
  "duration_seconds": 222,
  "cwd": "/projects/webapp",
  "command": ["codex", "exec", "--full-auto", "-C", "/projects/webapp", "<prompt redacted>"],
  "prompt_log": "data/logs/webapp/2026-04-11T14-22-09Z.prompt.txt",
  "exit_code": 0,
  "timed_out": false,
  "cancelled": false
}
```

The metadata file should not store Discord tokens, OpenAI API keys, or the full prompt text. The prompt may contain private Discord content or pasted secrets, so it should be written to a separate prompt log file when prompt logging is enabled. The full Codex stdout/stderr log remains separate from metadata.

## Security Model

DiscordCodex is a remote code execution bridge. The security model must be explicit.

Required protections:

- Allowlist a single Discord guild by ID.
- Allowlist user IDs.
- Ignore DMs by default.
- Only run in configured channels.
- One job per channel.
- Timeouts for every Codex process.
- Audit log for every run.
- No secrets in project config.

Recommended protections:

- Run under a dedicated OS user.
- Mount only required project directories in Docker.
- Avoid mounting the Docker socket unless the project needs it.
- Prefer Codex full-auto with workspace sandbox over dangerous bypass.
- Use private Discord channels.
- Rotate Discord and OpenAI tokens if leaked.

## Process Lifecycle

Each Codex run is started as a subprocess in the configured project `cwd`.

Cancellation behavior:

- `!cancel` sends a graceful termination signal to the running Codex process.
- If the process has not exited after a short configurable grace period, the bot force-kills it.
- Cancelled jobs are marked with `cancelled: true` in metadata.
- If a cancelled process exits with a non-zero code, the final Discord message should still identify the job as cancelled rather than a normal failure.

Timeout behavior:

- Every run has a timeout.
- On timeout, the bot uses the same graceful-then-forceful termination flow.
- Timed-out jobs are marked with `timed_out: true` in metadata.
- The final Discord message should include the timeout duration.

## Docker Support

Docker deployment is supported but not required.

The container image should include:

- Python runtime.
- DiscordCodex package.
- Codex CLI.
- Git.
- Common shell utilities.

Example compose:

```yaml
services:
  discordcodex:
    image: discordcodex:latest
    container_name: discordcodex
    restart: unless-stopped
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ALLOWED_GUILD_ID=${ALLOWED_GUILD_ID}
      - ALLOWED_USER_IDS=${ALLOWED_USER_IDS}
      - DISCORDCODEX_CONFIG=/app/config/projects.json
      - DISCORDCODEX_DATA_DIR=/data
    volumes:
      - ./config:/app/config:ro
      - ./data:/data
      - /path/to/projects:/projects
```

Docker socket access is intentionally not included in the default example.

## Local Development Support

DiscordCodex should also run directly on macOS or Linux:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
discordcodex --config config/projects.json
```

Local requirements:

- Python 3.11 or newer.
- Codex CLI installed and available on `PATH`, or configured through `CODEX_BIN`.
- Valid Discord bot token.
- Valid OpenAI credentials for Codex CLI.

## Python Package Shape

Suggested package layout:

```text
discordcodex/
  pyproject.toml
  README.md
  LICENSE
  src/
    discordcodex/
      __init__.py
      __main__.py
      bot.py
      config.py
      codex_runner.py
      discord_output.py
      logging_store.py
      locks.py
  config/
    projects.example.json
  tests/
    test_config.py
    test_prompt_builder.py
    test_codex_runner.py
```

Module responsibilities:

- `bot.py`: Discord client setup and message handling.
- `config.py`: environment and project config loading.
- `codex_runner.py`: subprocess execution, timeouts, cancellation, output streaming.
- `discord_output.py`: message chunking and Discord output formatting.
- `logging_store.py`: run metadata and log persistence.
- `locks.py`: per-channel and global concurrency controls.

## Testing Strategy

Unit tests:

- Config parsing.
- Channel lookup.
- User and guild allowlist checks.
- Prompt construction.
- Discord output chunking.
- Codex command construction.
- Timeout and cancellation behavior with fake subprocesses.

Integration tests:

- Run a fake Codex binary that emits known output.
- Verify logs and metadata are written.
- Verify concurrent jobs are blocked per channel.

Manual tests:

- Connect to a private Discord test server.
- Configure one scratch project.
- Send a simple message.
- Verify Codex runs in the expected cwd.
- Verify `!status`, `!cancel`, and `!tail`.

## V1 Acceptance Criteria

- The bot connects to Discord and ignores all unapproved users, guilds, and channels.
- A configured channel maps to a project cwd.
- A normal message in that channel triggers one Codex CLI run.
- Codex runs in the configured cwd.
- The bot posts start and finish messages.
- The bot returns short output to Discord.
- Full logs are persisted locally.
- `!status`, `!cancel`, `!tail`, `!projects`, and `!help` work.
- One active job per channel is enforced.
- The tool runs locally on macOS/Linux and in Docker.
- The default Docker example does not rely on QNAP-specific paths.

## Future Features

- Slash command support.
- Persistent interactive Codex sessions per channel.
- Web dashboard for logs and project status.
- Git branch/worktree management helpers.
- Per-project default prompt files.
- Attachment handling for screenshots, patches, and logs.
- GitHub issue or PR integration.
- Role-based access control.
- Multiple Discord guild support.
- Optional Docker socket profile for container-management projects.
