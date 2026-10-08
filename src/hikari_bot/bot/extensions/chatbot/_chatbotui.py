import re
from datetime import datetime, timezone
from typing import Awaitable, Callable, List

import anthropic
import discord
from discord import AllowedMentions, Embed, Interaction
from discord.ui import Modal, TextInput


DISCORD_MESSAGE_LIMIT = 2000
CROSS = "<a:crossred:1356353067024515266>"
CUT_OFF_NOTE = "-# My reply was cut off because it got too long."

# Claude's replies must never ping anyone except the person being replied to.
REPLY_MENTIONS = AllowedMentions(everyone=False, users=False, roles=False, replied_user=True)


class ChatBotModal(Modal):
    """Modal that collects the first message of a ChatBot conversation"""

    content = TextInput(
        label="Content",
        style=discord.TextStyle.paragraph,
        placeholder="Your content here...",
        required=True,
        max_length=4000
    )

    def __init__(self, on_content: Callable[[Interaction, str], Awaitable[None]]):
        self.on_content = on_content
        super().__init__(title="Talk to our AI assistant")


    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)
        await self.on_content(interaction, self.content.value)


def _wrap_line(line: str, width: int) -> List[str]:
    pieces = []
    while len(line) > width:
        cut = line.rfind(" ", 0, width)
        if cut <= 0:
            cut = width
        pieces.append(line[:cut])
        line = line[cut:].lstrip(" ")
    pieces.append(line)
    return pieces


def split_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> List[str]:
    """
    Split a reply into chunks that fit Discord's message length limit.

    Splits between lines where possible, falls back to spaces and then to hard cuts for very long
    lines, and closes and reopens code blocks that span two chunks so each chunk renders correctly.
    Discord only renders headings up to `###`, so deeper headings are flattened to `###`.
    """

    text = re.sub(r"^(\s*)#{4,}(?=\s)", r"\1###", text, flags=re.MULTILINE).strip()

    chunks = []
    current = ""
    fence = None    # The opening line of the code block `current` ends inside, if any.

    for raw_line in text.split("\n"):
        for line in _wrap_line(raw_line, limit - 100):
            is_fence = line.lstrip().startswith("```")
            candidate = f"{current}\n{line}" if current else line

            # Leave room to close an open code block, unless this line is what closes it.
            reserve = 0 if fence and is_fence else 8
            if current and len(candidate) + reserve > limit:
                chunks.append(f"{current}\n```" if fence else current)
                current = f"{fence}\n{line}" if fence else line
            else:
                current = candidate

            if is_fence:
                fence = None if fence else line.strip()

    if current:
        chunks.append(current)

    return [chunk for chunk in chunks if chunk.strip()]


def error_embed(message: str) -> Embed:
    embed = Embed(title="", color=discord.Colour.red())
    embed.add_field(name="", value=f"{CROSS} {message}")
    return embed


def api_error_embed(error: anthropic.APIError) -> Embed:
    """Build an embed describing a failed Claude API request."""

    if isinstance(error, anthropic.AuthenticationError):
        summary = "The bot's Claude API key is missing or invalid. Please let the bot owner know."
    elif isinstance(error, anthropic.PermissionDeniedError):
        summary = "The bot's Claude API key isn't allowed to do this. Please let the bot owner know."
    elif isinstance(error, anthropic.RateLimitError):
        summary = "I'm getting too many requests right now. Please try again in a moment."
    elif isinstance(error, (anthropic.OverloadedError, anthropic.InternalServerError)):
        summary = "Claude is having trouble right now. Please try again in a moment."
    elif isinstance(error, anthropic.APIConnectionError):
        summary = "I couldn't reach Claude. Please try again in a moment."
    else:
        summary = "Something went wrong while talking to Claude."

    embed = Embed(
        title=f"{CROSS} An error occurred while processing your request",
        description=summary,
        timestamp=datetime.now(timezone.utc),
        color=discord.Colour.red()
    )

    details = []
    if isinstance(error, anthropic.APIStatusError):
        details.append(f"Status code: {error.status_code}")
    details.append(f"Type: {type(error).__name__}")
    request_id = getattr(error, "request_id", None)
    if request_id:
        details.append(f"Request ID: {request_id}")

    embed.add_field(name="Error details:", value="\n".join(details)[:1024], inline=False)
    return embed
