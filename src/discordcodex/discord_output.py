from __future__ import annotations


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
        headline = f"Codex finished for `{project_name}`."
    duration = f"{duration_seconds:.0f}s"
    return "\n".join(
        [
            headline,
            f"Exit code: {exit_code if exit_code is not None else 'unknown'}",
            f"Duration: {duration}",
            f"Log: {log_path}",
        ]
    )
