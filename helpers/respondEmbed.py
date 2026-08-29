"""
The MIT License (MIT)

Copyright (c) 2026 Hoshino Yuki, Hikari

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

# SPDX-License-Identifier: MIT

import logging
from enum import Enum, auto
from discord import Color, Embed, Forbidden, Message
from discord.ui import View
from discord.ext.commands import Context
from typing import Optional

logger = logging.getLogger(__name__)

CROSS_RED = "<a:crossred:1356353067024515266>"
DEFAULT_COLOR = Color.blurple()   # brand fallback when the author has no role color

# Neutral system acknowledgement — neither error nor content, so intentionally uncolored.
DM_SENT_EMBED = Embed(description="I've sent you a DM.")

# Fixed DM-failure notices. Errors, so red + CROSS_RED, matching the inline error path.
DM_FORBIDDEN_EMBED = Embed(
    description=f"{CROSS_RED} I couldn't DM you — please enable DMs.",
    color=Color.red(),
)
DM_ERROR_EMBED = Embed(
    description=f"{CROSS_RED} I couldn't DM you due to an unexpected error. Please try again later.",
    color=Color.red(),
)

DM_FALLBACK_DELETE = 10.0   # one home for the magic number, used by both fallbacks


class ResponseTarget(Enum):
    """
    Represents the target for sending a response message.
    """

    CHANNEL = auto()
    """
    Sends the response message to the channel where the command was invoked.
    This is the default behavior.
    """

    REPLY = auto()
    """
    Reply to the invoking message in the channel where the command was invoked.
    This is a public response that references the original message.
    """

    DM = auto()
    """
    Sends the response message as a direct message (DM)
    to the user who invoked the command.
    """

    EPHEMERAL = auto()
    """
    Sends the response message as an ephemeral message if the command was invoked
    through an interaction that has not yet responded.
    For other cases, sends it as a public message.
    """


async def _dm_fallback(ctx: Context, embed: Embed) -> Optional[Message]:
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Last-resort delivery when a channel/reply send is rejected.
    
    This could happen on sometimes (e.g. the bot was locked out of the channel
    it's trying to post in), and we need to DM the invoking author with
    the original embed.
    
    If the DM also fails, it's logged and None is returned,
    so callers never see an uncaught Forbidden bubble up
    into the command error handler.
    """

    try:
        return await ctx.author.send(embed=embed)

    except Forbidden:
        logger.warning(
            "respondEmbed: channel send forbidden and author has DMs closed "
            "(command=%s user=%s)",
            getattr(ctx, "command", None), ctx.author,
        )
        return

    except Exception:
        logger.exception(
            "respondEmbed: channel send forbidden and DM fallback errored "
            "(command=%s user=%s)",
            getattr(ctx, "command", None), ctx.author,
        )
        return


async def respondEmbed(
    ctx: Context,
    message: str,
    *,
    target: ResponseTarget = ResponseTarget.CHANNEL,
    error: bool = False,
    title: Optional[str] = None,
    isSilent: bool = False,
    deleteAfter: Optional[float] = None,
    view: Optional[View] = None
) -> Optional[Message]:
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Creates an embed message and sends it as response to a command invocation.

    Parameters
    ----------
    ctx : discord.ext.commands.Context
        The context of the command invocation.
    message : str
        The message to be included in the embed.
    target : ResponseTarget, optional
        The target for sending the response message.
    error : bool, optional
        Whether the embed should be displayed in red (for errors).
    title : str, optional
        The title of the embed.
    isSilent : bool, optional
        Whether the embed should be sent silently (without a notification).
    deleteAfter : float, optional
        The time in seconds after which the message should be deleted.
        If it is None, the message will not be deleted.
    view : discord.ui.View, optional
        The view to be attached to the message. If None, no view will be attached.

    Returns
    -------
    Optional[Message]
        The sent message, or None if the message was not sent.
    """

    # If error is True, the message will be displayed in red, with a cross emoji prefix;
    # otherwise the author's role color, falling back to brand when they have none
    # (Color.default() is 0x000000, i.e. no colored role)

    if error:
        message = f"{CROSS_RED} {message}"
        color = Color.red()
    else:
        author_color = ctx.author.color
        color = author_color if author_color.value else DEFAULT_COLOR

    embed = Embed(
        title=title,
        description=message,
        color=color,
    )

    # common kwargs for the classic (Messageable) sends
    kwargs = {"embed": embed}

    if isSilent:
        kwargs["silent"] = True

    if deleteAfter is not None:
        kwargs["delete_after"] = deleteAfter

    if view is not None:
        kwargs["view"] = view

    # dispatch on the single delivery axis
    if target is ResponseTarget.EPHEMERAL:
        interaction = ctx.interaction

        if interaction is not None and not interaction.response.is_done():
            # We own the first response, ephemeral is honored here
            ephemeralKwargs = {"embed": embed, "view": view, "ephemeral": True}
            await interaction.response.send_message(**ephemeralKwargs)
            return await interaction.original_response()

        # For deferred/already-responded OR not an interaction, they can't be ephemeral.
        logger.info(
            "respondEmbed: EPHEMERAL requested but interaction already responded/"
            "deferred (or non-interaction); sending publicly. command=%s user=%s",
            getattr(ctx, "command", None), ctx.author,
        )

        try:
            return await ctx.send(**kwargs)

        except Forbidden:
            logger.warning(
                "respondEmbed: public fallback of EPHEMERAL forbidden; DMing author "
                "(command=%s user=%s)",
                getattr(ctx, "command", None), ctx.author,
            )
            return await _dm_fallback(ctx, embed)

    if target is ResponseTarget.DM:
        interaction = ctx.interaction
        try:
            dmMessage = await ctx.author.send(**kwargs)

        except Forbidden:
            # DM is closed, so we try to reply in-channel with a notice that the DM failed.
            logger.exception(
                "respondEmbed: DM requested but failed to send (command=%s user=%s) due to Forbidden (likely DMs closed)",
                getattr(ctx, "command", None), ctx.author,
            )
            try:
                return await ctx.reply(embed=DM_FORBIDDEN_EMBED, delete_after=DM_FALLBACK_DELETE)

            except Forbidden:
                # can't reply in-channel either (locked out); nothing left to try
                logger.warning(
                    "respondEmbed: DM forbidden and in-channel notice also forbidden "
                    "(command=%s user=%s)",
                    getattr(ctx, "command", None), ctx.author,
                )
                return

        except Exception:
            # DM errored, so we try to reply in-channel with a notice that the DM failed.
            logger.exception(
                "respondEmbed: DM requested but failed to send (command=%s user=%s)",
                getattr(ctx, "command", None), ctx.author,
            )
            try:
                return await ctx.reply(embed=DM_ERROR_EMBED, delete_after=DM_FALLBACK_DELETE)

            except Forbidden:
                # can't reply in-channel either (locked out); nothing left to try
                logger.warning(
                    "respondEmbed: DM errored and in-channel notice also forbidden "
                    "(command=%s user=%s)",
                    getattr(ctx, "command", None), ctx.author,
                )
                return

        # DM landed — acknowledge the interaction if there is one, so slash callers
        # don't see "application did not respond". Ephemeral: it's noise, not content.
        if interaction is not None and not interaction.response.is_done():
            try:
                await interaction.response.send_message(embed=DM_SENT_EMBED, ephemeral=True)

            except Exception:
                logger.exception(
                    "respondEmbed: DM sent but failed to acknowledge interaction "
                    "(command=%s user=%s)",
                    getattr(ctx, "command", None), ctx.author,
                )

        return dmMessage

    if target is ResponseTarget.REPLY:
        try:
            return await ctx.reply(**kwargs)

        except Forbidden:
            # reply is forbidden (likely locked out); DM the author instead
            logger.warning(
                "respondEmbed: REPLY forbidden (likely locked out); DMing author "
                "(command=%s user=%s)",
                getattr(ctx, "command", None), ctx.author,
            )
            return await _dm_fallback(ctx, embed)

    # ResponseTarget.CHANNEL (default)
    try:
        return await ctx.send(**kwargs)

    except Forbidden:
        # channel send is forbidden (likely locked out); DM the author instead
        logger.warning(
            "respondEmbed: CHANNEL send forbidden (likely locked out); DMing author "
            "(command=%s user=%s)",
            getattr(ctx, "command", None), ctx.author,
        )
        return await _dm_fallback(ctx, embed)
