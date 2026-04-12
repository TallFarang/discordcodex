# DiscordCodex V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a portable Python Discord bot that routes every allowed project-channel message into a stateless `codex exec` run.

**Architecture:** Keep Discord handling thin and put testable behavior in focused modules for config validation, prompt construction, output chunking, log storage, process execution, and concurrency. The runtime uses `discord.py` when installed and standard-library `asyncio` subprocesses for Codex.

**Tech Stack:** Python 3.11+, `discord.py` runtime dependency, standard-library `unittest` tests.

---

### Task 1: Package and Core Behavior

**Files:**
- Create: `pyproject.toml`
- Create: `src/discordcodex/__init__.py`
- Create: `src/discordcodex/__main__.py`
- Create: `src/discordcodex/cli.py`
- Create: `src/discordcodex/config.py`
- Create: `src/discordcodex/prompt.py`
- Create: `src/discordcodex/discord_output.py`
- Create: `src/discordcodex/logging_store.py`
- Create: `src/discordcodex/locks.py`
- Create: `src/discordcodex/codex_runner.py`
- Create: `src/discordcodex/bot.py`
- Create: `tests/test_config.py`
- Create: `tests/test_prompt.py`
- Create: `tests/test_discord_output.py`
- Create: `tests/test_logging_store.py`
- Create: `tests/test_codex_runner.py`

- [ ] Write failing tests for config parsing, prompt construction, chunking, log metadata, and fake Codex execution.
- [ ] Run `python -m unittest discover -s tests -v` and confirm failures are from missing package code.
- [ ] Implement the package modules with minimal behavior required by the spec.
- [ ] Run `python -m unittest discover -s tests -v` and fix failures.
- [ ] Run `python -m compileall src tests` to verify syntax across the package.
