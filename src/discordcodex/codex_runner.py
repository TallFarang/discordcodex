from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass

from .config import ProjectConfig

BLOCKED_ENV_PREFIXES = ("ALLOWED_", "DISCORD", "DISCORDCODEX_")
BLOCKED_ENV_NAMES = {"GITHUB_TOKEN"}
PRESERVED_ENV_NAMES = {
    "GIT_CONFIG_GLOBAL",
    "HOME",
    "LANG",
    "LC_ALL",
    "PATH",
    "SSL_CERT_FILE",
    "TMPDIR",
    "TZ",
}


@dataclass(frozen=True)
class CodexResult:
    exit_code: int | None
    output: str
    duration_seconds: float
    timed_out: bool
    cancelled: bool
    command: list[str]
    thread_id: str | None = None
    assistant_response: str | None = None


class CodexRunner:
    def __init__(self, codex_bin: str, cancel_grace_seconds: float = 5.0):
        self.codex_bin = codex_bin
        self.cancel_grace_seconds = cancel_grace_seconds

    async def run(
        self,
        project: ProjectConfig,
        prompt: str,
        timeout_seconds: int | None = None,
        extra_args: list[str] | None = None,
        session_id: str | None = None,
    ) -> CodexResult:
        started = time.monotonic()
        timeout = timeout_seconds or project.timeout_seconds
        args = self._build_args(project, session_id=session_id, extra_args=extra_args)
        args.append(prompt)

        env = _codex_child_env(os.environ)
        if project.codex_home:
            env["CODEX_HOME"] = str(project.codex_home)

        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(project.cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output = b""
        timed_out = False
        cancelled = False
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            timed_out = True
            output = await self._terminate(process)
        except asyncio.CancelledError:
            cancelled = True
            output = await self._terminate(process)
        duration = time.monotonic() - started
        return CodexResult(
            exit_code=process.returncode,
            output=output.decode("utf-8", errors="replace"),
            duration_seconds=duration,
            timed_out=timed_out,
            cancelled=cancelled,
            command=self._redacted_command(project, session_id=session_id),
            thread_id=_extract_thread_id(output.decode("utf-8", errors="replace")),
            assistant_response=_extract_agent_message(output.decode("utf-8", errors="replace")),
        )

    def _build_args(
        self,
        project: ProjectConfig,
        session_id: str | None,
        extra_args: list[str] | None = None,
    ) -> list[str]:
        args = [self.codex_bin]
        if extra_args:
            args.extend(extra_args)
        if session_id:
            args.extend(["exec", "resume", "--json", *project.codex_args, session_id])
        else:
            args.extend(["exec", "--json", *project.codex_args, "-C", str(project.cwd)])
        return args

    def _redacted_command(self, project: ProjectConfig, session_id: str | None) -> list[str]:
        if session_id:
            return [
                self.codex_bin,
                "exec",
                "resume",
                "--json",
                *project.codex_args,
                session_id,
                "<prompt redacted>",
            ]
        return [
            self.codex_bin,
            "exec",
            "--json",
            *project.codex_args,
            "-C",
            str(project.cwd),
            "<prompt redacted>",
        ]

    async def _terminate(self, process: asyncio.subprocess.Process) -> bytes:
        if process.returncode is not None:
            output, _ = await process.communicate()
            return output
        process.terminate()
        try:
            output, _ = await asyncio.wait_for(
                process.communicate(), timeout=self.cancel_grace_seconds
            )
            return output
        except asyncio.TimeoutError:
            process.kill()
            output, _ = await process.communicate()
            return output


def _codex_child_env(source: os._Environ[str] | dict[str, str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for key, value in source.items():
        if key in PRESERVED_ENV_NAMES or key.startswith("LC_"):
            env[key] = value
            continue
        if key in BLOCKED_ENV_NAMES or key.startswith(BLOCKED_ENV_PREFIXES):
            continue
    return env


def _extract_thread_id(output: str) -> str | None:
    for event in _json_events(output):
        if event.get("type") == "thread.started" and event.get("thread_id"):
            return str(event["thread_id"])
    return None


def _extract_agent_message(output: str) -> str | None:
    messages: list[str] = []
    for event in _json_events(output):
        item = event.get("item")
        if event.get("type") == "item.completed" and isinstance(item, dict):
            if item.get("type") == "agent_message" and item.get("text"):
                messages.append(str(item["text"]))
    if messages:
        return "\n".join(messages).strip()
    return None


def _json_events(output: str) -> list[dict]:
    events = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events
