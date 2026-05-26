from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from .config import ProjectConfig

BLOCKED_ENV_PREFIXES = ("ALLOWED_", "DISCORD", "DISCORDCODEX_")
BLOCKED_ENV_NAMES = {"GITHUB_TOKEN"}
PRESERVED_ENV_NAMES = {
    "GH_TOKEN",
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
class CodexProgress:
    message: str
    kind: str
    detail: str | None = None


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
        progress_callback: Callable[[CodexProgress], Awaitable[None]] | None = None,
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
        output_parts: list[bytes] = []
        timed_out = False
        cancelled = False
        reader_task = asyncio.create_task(
            self._read_output(process, output_parts, progress_callback)
        )
        try:
            await asyncio.wait_for(asyncio.shield(reader_task), timeout=timeout)
            await process.wait()
        except asyncio.TimeoutError:
            timed_out = True
            await self._terminate_streaming(process, reader_task)
        except asyncio.CancelledError:
            cancelled = True
            await self._terminate_streaming(process, reader_task)
        duration = time.monotonic() - started
        output = b"".join(output_parts)
        decoded_output = output.decode("utf-8", errors="replace")
        return CodexResult(
            exit_code=process.returncode,
            output=decoded_output,
            duration_seconds=duration,
            timed_out=timed_out,
            cancelled=cancelled,
            command=self._redacted_command(project, session_id=session_id),
            thread_id=_extract_thread_id(decoded_output),
            assistant_response=_extract_agent_message(decoded_output),
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

    async def _read_output(
        self,
        process: asyncio.subprocess.Process,
        output_parts: list[bytes],
        progress_callback: Callable[[CodexProgress], Awaitable[None]] | None,
    ) -> None:
        if process.stdout is None:
            return
        last_progress: CodexProgress | None = None
        while True:
            line = await process.stdout.readline()
            if not line:
                return
            output_parts.append(line)
            if progress_callback is None:
                continue
            progress = _progress_from_line(line.decode("utf-8", errors="replace"))
            if progress is None or progress == last_progress:
                continue
            last_progress = progress
            try:
                await progress_callback(progress)
            except Exception:
                continue

    async def _terminate_streaming(
        self,
        process: asyncio.subprocess.Process,
        reader_task: asyncio.Task[None],
    ) -> None:
        if process.returncode is None:
            process.terminate()
        try:
            await asyncio.wait_for(asyncio.shield(reader_task), timeout=self.cancel_grace_seconds)
        except asyncio.TimeoutError:
            if process.returncode is None:
                process.kill()
            await reader_task
        await process.wait()


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


def _progress_from_line(line: str) -> CodexProgress | None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict):
        return None
    return _progress_from_event(event)


def _progress_from_event(event: dict) -> CodexProgress | None:
    item = event.get("item")
    item = item if isinstance(item, dict) else {}
    event_type = event.get("type")
    item_type = item.get("type")

    if event_type == "item.completed" and item_type == "agent_message":
        return CodexProgress(message="Codex is preparing a response...", kind="response")

    if event_type not in {"item.started", "item.completed"}:
        return None

    searchable = " ".join(
        str(value)
        for value in (
            item_type,
            item.get("name"),
            item.get("title"),
            item.get("command"),
            item.get("status"),
        )
        if value
    ).lower()
    if not searchable:
        return None
    if any(token in searchable for token in ("edit", "patch", "write", "apply_patch")):
        return CodexProgress(message="Codex is editing files...", kind="edit")
    if any(token in searchable for token in ("read", "grep", "search", "find", "list", "ls", "cat", "sed", "rg")):
        return CodexProgress(message="Codex is inspecting files...", kind="inspect")
    if any(token in searchable for token in ("command", "shell", "exec", "tool_call")):
        return CodexProgress(message="Codex is running a command...", kind="command")
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
