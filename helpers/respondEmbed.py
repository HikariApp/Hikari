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
from datetime import datetime
from discord import Color, Embed, Forbidden, Interaction, Message
from discord.abc import User as AbcUser
from discord.ui import View
from discord.ext.commands import Context
from discord.utils import MISSING
from typing import Optional, Union

logger = logging.getLogger(__name__)

CROSS_RED = "<a:crossred:1356353067024515266>"
DEFAULT_COLOR = Color.blurple()   # brand fallback when the author has no role color
DEFAULT_DELETE_AFTER = 5.0

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

    When the source is a raw Interaction (no message to reference, e.g. a modal
    submit), this transparently downgrades to CHANNEL.
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


def _commandLabel(source: Union[Context, Interaction]):
    """Best-effort command name for log lines, tolerant of either source type."""
    return getattr(source, "command", None)


async def _dmFallback(author: AbcUser, embed: Embed, label) -> Optional[Message]:
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Last-resort delivery when a channel/reply send is rejected.

    This can happen (e.g. the bot was locked out of the channel it's trying to
    post in), so we DM the invoking author with the original embed.

    If the DM also fails, it's logged and None is returned, so callers never see
    an uncaught Forbidden bubble up into the command error handler.

    Parameters
    ----------
    author : discord.abc.User
        The user to DM.
    embed : discord.Embed
        The embed to send in the DM.
    label : str
        The command label, for logging.

    Returns
    -------
    discord.Message, optional
        The sent message, or None if the message was not sent.
    """

    try:
        return await author.send(embed=embed)

    except Forbidden:
        logger.warning(
            "respondEmbed: channel send forbidden and author has DMs closed "
            "(command=%s user=%s)",
            label, author,
        )
        return

    except Exception:
        logger.exception(
            "respondEmbed: channel send forbidden and DM fallback errored "
            "(command=%s user=%s)",
            label, author,
        )
        return


async def _sendViaInteraction(
    interaction: Interaction,
    *,
    embed: Embed,
    view: Optional[View],
    ephemeral: bool,
    isSilent: bool,
    deleteAfter: Optional[float],
) -> Optional[Message]:
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Sends an embed through an interaction.

    This handles the complexity of sending an embed through an interaction,
    transparently picking the correct surface.

    It would take the initial response if it hasn't been used yet,
    otherwise a followup.

    `wait=True` is passed on the followup path so the WebhookMessage is returned,
    keeping respondEmbed's "returns the Message" contract intact.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction to send the embed through.
    embed : discord.Embed
        The embed to send.
    view : discord.ui.View, optional
        The view to attach to the message. If None, no view will be attached.
    ephemeral : bool
        Whether the message should be ephemeral (only visible to the user).
    isSilent : bool
        Whether the message should be sent silently (without a notification).
    deleteAfter : float, optional
        The time in seconds after which the message should be deleted.
        If it is None, the message will not be deleted.

    Returns
    -------
    discord.Message, optional
        The sent message, or None if the message was not sent.

    Notes
    -----
    `delete_after` skipped entirely for ephemerals, since they're transient
    by nature (and deleting an ephemeral WebhookMessage can error anyway).
    
    For non-ephemerals, `InteractionResponse.send_message` supports `delete_after`
    natively so we hand it straight through, while `Webhook.send` (followup) does
    not, so on that branch we self-schedule via non-blocking `Message.delete(delay=...)`.
    """

    resolvedView = view if view is not None else MISSING
    effectiveDeleteAfter = deleteAfter if not ephemeral else None

    if not interaction.response.is_done():
        logger.info("The interaction response is not done, sending the embed as the initial response.")
        await interaction.response.send_message(
            embed=embed,
            view=resolvedView,
            ephemeral=ephemeral,
            silent=isSilent,
            delete_after=effectiveDeleteAfter,
        )
        return await interaction.original_response()

    logger.info("The interaction response is already done, sending the embed as a followup.")
    sentMessage = await interaction.followup.send(
        embed=embed,
        view=resolvedView,
        ephemeral=ephemeral,
        silent=isSilent,
        wait=True
        )

    # Webhook/followup sends don't accept delete_after, so we schedule it ourselves.
    if not ephemeral and (effectiveDeleteAfter is not None and sentMessage is not None):
        await sentMessage.delete(delay=effectiveDeleteAfter)

    return sentMessage



async def _noticeViaInteraction(interaction: Interaction, embed: Embed, label: str) -> None:
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Delivers a fixed DM-failure notice back throughthe interaction,
    with an ephemeral message.

    Used when the source is a raw Interaction
    and there's no channel to reply in.
    
    If the notice fails to send, the error is logged and swallowed.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction to send the notice through.
    embed : discord.Embed
        The embed to send as the notice.
    label : str
        The command label, for logging.
    """

    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception:
        logger.exception(
            "respondEmbed: failed to deliver DM-failure notice via interaction "
            "(command=%s)",
            label,
        )


def _withDeleteNotice(footerText: Optional[str], deleteAfter: float) -> str:
    """
    Returns a footer text with a notice about the message being deleted after a certain time.
    
    Parameters
    ----------
    footerText : str, optional
        The original footer text. If None, only the delete notice will be returned.
    deleteAfter : float
        The time in seconds after which the message will be deleted.
    """

    notice = f"This message will be deleted in {deleteAfter:.0f} seconds."
    return f"{footerText} • {notice}" if footerText else notice


async def respondEmbed(
    source: Union[Context, Interaction],
    *,
    title: Optional[str] = None,
    message: str,
    authorName: Optional[str] = None,
    authorUrl: Optional[str] = None,
    authorIconUrl: Optional[str] = None,
    imageUrl: Optional[str] = None,
    thumbnailUrl: Optional[str] = None,
    footerText: Optional[str] = None,
    footerIconUrl: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    target: Optional[ResponseTarget] = ResponseTarget.CHANNEL,
    error: bool = False,
    isSilent: bool = False,
    deleteAfter: Optional[float] = None,
    view: Optional[View] = None
) -> Optional[Message]:
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Creates an embed message and sends it as response to a command invocation.

    Supports most common embed fields, including `author`, `image`, `thumbnail`, `footer` and `timestamp`.

    Parameters
    ----------
    source : Union[discord.ext.commands.Context, discord.Interaction]
        The context of the command invocation, or a raw interaction (e.g. from a
        modal submit or component callback, which have no associated Context).
    title : str, optional
        The title of the embed.
    message : str
        The message to be included in the embed. Treated as `description` text.
    authorName : str, optional
        The name of the author to be displayed in the embed, if provided.
    authorUrl : str, optional
        The URL of the author to be displayed in the embed, if provided.
    authorIconUrl : str, optional
        The URL of the author's icon to be displayed in the embed, if provided.
    imageUrl : str, optional
        The URL of the image to be displayed in the embed, if provided.
    thumbnailUrl : str, optional
        The URL of the thumbnail to be displayed in the embed, if provided.
    footerText : str, optional
        The text of the footer to be displayed in the embed, if provided.
    footerIconUrl : str, optional
        The URL of the footer's icon to be displayed in the embed, if provided.
    timestamp : datetime, optional
        The timestamp to be displayed in the embed, if provided.
    target : ResponseTarget, optional
        The target for sending the response message. Defaults to `ResponseTarget.CHANNEL` if not provided.
    error : bool, optional
        Whether the embed should be displayed in red (for errors).
    isSilent : bool, optional
        Whether the embed should be sent silently (without a notification).
    deleteAfter : float, optional
        The time in seconds after which the message should be deleted.
        If it is None, the message will not be deleted.
    view : discord.ui.View, optional
        The view to be attached to the message. If None, no view will be attached.

    Returns
    -------
    Message, optional
        The sent message, or None if the message was not sent.

    Raises
    ------
    ValueError
        If `authorUrl` or `authorIconUrl` is provided without `authorName`,
        or if `footerIconUrl` is provided without `footerText`.
    """

    # --- Normalize the source into the three things this function actually uses:
    #     the invoking author, the interaction (if any), and — for the classic
    #     Messageable paths — the Context itself. A raw Interaction has no Context.
    if isinstance(source, Interaction):
        ctx: Optional[Context] = None
        interaction: Optional[Interaction] = source
        author = source.user
    else:
        ctx = source
        interaction = source.interaction
        author = source.author

    label = _commandLabel(source)

    # If error is True, the message will be displayed in red, with a cross emoji prefix;
    # otherwise the author's role color, falling back to brand when they have none
    # (Color.default() is 0x000000, i.e. no colored role). getattr guards against a
    # plain User (DM interactions) that lacks a role color.
    if error:
        message = f"{CROSS_RED} {message}"
        color = Color.red()
    else:
        author_color = getattr(author, "color", None)
        color = author_color if (author_color and author_color.value) else DEFAULT_COLOR

    # author sub-values are meaningless without a name; fail loudly instead of
    # silently dropping them.
    if authorName is None and (authorUrl is not None or authorIconUrl is not None):
        raise ValueError(
            "authorUrl/authorIconUrl require authorName to be set."
        )

    # footer icon won't render without footer text.
    if footerText is None and footerIconUrl is not None:
        raise ValueError(
            "footerIconUrl requires footerText to be set."
        )

    embed = Embed(
        title=title,
        description=message,
        color=color,
    )

    if authorName is not None:
        embed.set_author(name=authorName, url=authorUrl, icon_url=authorIconUrl)

    if imageUrl is not None:
        embed.set_image(url=imageUrl)

    if thumbnailUrl is not None:
        embed.set_thumbnail(url=thumbnailUrl)

    if (isinstance(source, Context) and target is ResponseTarget.EPHEMERAL) and deleteAfter is None:
        deleteAfter = DEFAULT_DELETE_AFTER

    if deleteAfter is not None and not (
        isinstance(source, Interaction) and target is ResponseTarget.EPHEMERAL
    ):
        footerText = _withDeleteNotice(footerText, deleteAfter)

    if footerText is not None:
        embed.set_footer(text=footerText, icon_url=footerIconUrl)

    if timestamp is not None:
        embed.timestamp = timestamp

    # common kwargs for the classic (Messageable) sends
    kwargs = {"embed": embed}

    if isSilent:
        kwargs["silent"] = True

    if deleteAfter is not None:
        kwargs["delete_after"] = deleteAfter

    if view is not None:
        kwargs["view"] = view

    # =====================================================================
    # dispatch on the single delivery axis
    # =====================================================================
    if target is ResponseTarget.EPHEMERAL:
        if interaction is not None:
            # Ephemeral is only meaningful for interactions. Works whether or not
            # the interaction was already deferred/responded (followup handles it).
            return await _sendViaInteraction(
                interaction,
                embed=embed,
                view=view,
                ephemeral=True,
                isSilent=isSilent,
                deleteAfter=deleteAfter,
            )

        # Pure prefix (no interaction) can't be ephemeral; send publicly.
        logger.info(
            "respondEmbed: EPHEMERAL requested on a non-interaction source; "
            "sending publicly. command=%s user=%s",
            label, author,
        )
        try:
            return await ctx.send(**kwargs)

        except Forbidden:
            logger.warning(
                "respondEmbed: public fallback of EPHEMERAL forbidden; DMing author "
                "(command=%s user=%s)",
                label, author,
            )
            return await _dmFallback(author, embed, label)

    if target is ResponseTarget.DM:
        try:
            dmMessage = await author.send(**kwargs)

        except Forbidden:
            # DM is closed, so notify in-channel that the DM failed.
            logger.exception(
                "respondEmbed: DM requested but failed (command=%s user=%s) due to "
                "Forbidden (likely DMs closed)",
                label, author,
            )
            if ctx is not None:
                try:
                    return await ctx.reply(embed=DM_FORBIDDEN_EMBED, delete_after=DM_FALLBACK_DELETE)
                except Forbidden:
                    logger.warning(
                        "respondEmbed: DM forbidden and in-channel notice also "
                        "forbidden (command=%s user=%s)",
                        label, author,
                    )
                    return
            else:
                await _noticeViaInteraction(interaction, DM_FORBIDDEN_EMBED, label)
                return

        except Exception:
            # DM errored, so notify in-channel that the DM failed.
            logger.exception(
                "respondEmbed: DM requested but failed to send (command=%s user=%s)",
                label, author,
            )
            if ctx is not None:
                try:
                    return await ctx.reply(embed=DM_ERROR_EMBED, delete_after=DM_FALLBACK_DELETE)
                except Forbidden:
                    logger.warning(
                        "respondEmbed: DM errored and in-channel notice also forbidden "
                        "(command=%s user=%s)",
                        label, author,
                    )
                    return
            else:
                await _noticeViaInteraction(interaction, DM_ERROR_EMBED, label)
                return

        # DM landed — acknowledge the interaction if one exists and hasn't been used,
        # so slash callers don't see "application did not respond".
        if interaction is not None and not interaction.response.is_done():
            try:
                await interaction.response.send_message(embed=DM_SENT_EMBED, ephemeral=True)
            except Exception:
                logger.exception(
                    "respondEmbed: DM sent but failed to acknowledge interaction "
                    "(command=%s user=%s)",
                    label, author,
                )

        return dmMessage

    if target is ResponseTarget.REPLY:
        if ctx is not None:
            try:
                return await ctx.reply(**kwargs)
            except Forbidden:
                logger.warning(
                    "respondEmbed: REPLY forbidden (likely locked out); DMing author "
                    "(command=%s user=%s)",
                    label, author,
                )
                return await _dmFallback(author, embed, label)

        # Raw interaction has no message to reply to; downgrade to a channel-style send.
        logger.info(
            "respondEmbed: REPLY requested on a raw interaction; sending as a normal "
            "response. command=%s user=%s",
            label, author,
        )
        return await _sendViaInteraction(
            interaction,
            embed=embed,
            view=view,
            ephemeral=False,
            isSilent=isSilent,
            deleteAfter=deleteAfter,
        )

    # ResponseTarget.CHANNEL (default)
    if ctx is not None:
        try:
            return await ctx.send(**kwargs)
        except Forbidden:
            logger.warning(
                "respondEmbed: CHANNEL send forbidden (likely locked out); DMing author "
                "(command=%s user=%s)",
                label, author,
            )
            return await _dmFallback(author, embed, label)

    # Raw interaction, public channel send.
    try:
        return await _sendViaInteraction(
            interaction,
            embed=embed,
            view=view,
            ephemeral=False,
            isSilent=isSilent,
            deleteAfter=deleteAfter,
        )
    except Forbidden:
        logger.warning(
            "respondEmbed: interaction CHANNEL send forbidden; DMing author "
            "(command=%s user=%s)",
            label, author,
        )
        return await _dmFallback(author, embed, label)

