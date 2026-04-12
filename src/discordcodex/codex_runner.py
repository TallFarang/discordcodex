from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass

from .config import ProjectConfig


@dataclass(frozen=True)
class CodexResult:
    exit_code: int | None
    output: str
    duration_seconds: float
    timed_out: bool
    cancelled: bool
    command: list[str]


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
    ) -> CodexResult:
        started = time.monotonic()
        timeout = timeout_seconds or project.timeout_seconds
        args = [self.codex_bin]
        if extra_args is None:
            args.extend(["exec", *project.codex_args, "-C", str(project.cwd)])
        else:
            args.extend(extra_args)
        args.append(prompt)

        env = os.environ.copy()
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
            command=[self.codex_bin, "exec", *project.codex_args, "-C", str(project.cwd), "<prompt redacted>"],
        )

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
