from __future__ import annotations

from dataclasses import dataclass

from .config import ProjectConfig


@dataclass(frozen=True)
class ChannelMessage:
    author: str
    content: str
    is_bot: bool = False


def build_prompt(
    project: ProjectConfig,
    channel_name: str,
    recent_messages: list[ChannelMessage],
    user_request: str,
    include_bot_messages: bool = False,
    resumed_session: bool = False,
) -> str:
    if resumed_session:
        return "\n".join(
            [
                "You are running inside DiscordCodex.",
                "Resuming existing Codex conversation.",
                "",
                f"Project: {project.name}",
                f"Working directory: {project.cwd}",
                f"Discord channel: {channel_name}",
                "",
                "User request:",
                user_request,
            ]
        )

    filtered = [
        message
        for message in recent_messages
        if message.content.strip() and (include_bot_messages or not message.is_bot)
    ]
    if project.include_recent_messages:
        filtered = filtered[-project.include_recent_messages :]
    else:
        filtered = []

    recent = "\n".join(f"{message.author}: {message.content}" for message in filtered)
    if not recent:
        recent = "(none)"

    return "\n".join(
        [
            "You are running inside DiscordCodex.",
            "",
            f"Project: {project.name}",
            f"Working directory: {project.cwd}",
            f"Discord channel: {channel_name}",
            "",
            "Recent channel context:",
            recent,
            "",
            "User request:",
            user_request,
        ]
    )
