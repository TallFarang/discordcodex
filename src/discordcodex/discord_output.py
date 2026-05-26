from __future__ import annotations


def help_message() -> str:
    return "\n".join(
        [
            "DiscordCodex is ready.",
            "",
            "Send a normal message here to ask Codex to work in this channel's project.",
            "",
            "Commands:",
            "`!status` - check if Codex is running",
            "`!cancel` - stop the current run",
            "`!tail` - show the latest raw log",
            "`!session` - show this channel's Codex session",
            "`!new` - clear this channel's Codex session",
            "`!projects` - list configured projects",
            "`!pollgh` - run GitHub project provisioning",
            "`!help` - show this guide",
        ]
    )


def extract_assistant_response(text: str) -> str | None:
    lines = text.splitlines()
    codex_indices = [index for index, line in enumerate(lines) if line.strip() == "codex"]
    for index in reversed(codex_indices):
        answer_lines: list[str] = []
        for line in lines[index + 1 :]:
            if line.strip() == "tokens used":
                break
            answer_lines.append(line)
        answer = "\n".join(answer_lines).strip()
        if answer:
            return answer
    return None


def chunk_output(text: str, max_chars: int = 1800, max_chunks: int = 4) -> tuple[list[str], bool]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if max_chunks <= 0:
        raise ValueError("max_chunks must be positive")
    chunks: list[str] = []
    remaining = text
    while remaining and len(chunks) < max_chunks:
        chunks.append(remaining[:max_chars])
        remaining = remaining[max_chars:]
    return chunks, bool(remaining)


def summarize_result(
    project_name: str,
    exit_code: int | None,
    duration_seconds: float,
    log_path: str,
    cancelled: bool = False,
    timed_out: bool = False,
) -> str:
    if cancelled:
        headline = f"Codex cancelled for `{project_name}`."
    elif timed_out:
        headline = f"Codex timed out for `{project_name}`."
    else:
        headline = f"Codex failed for `{project_name}`."
    return f"{headline} Use `!tail` for details."
