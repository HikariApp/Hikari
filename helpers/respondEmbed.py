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

from discord import Embed, Color
from discord.ext import commands
from typing import Optional

CROSS_RED = "<a:crossred:1356353067024515266>"


async def respondEmbed(
    ctx: commands.Context,
    message: str,
    *,
    error: bool = False,
    title: str = "",
    isPrivate: bool = False,
    isReply: bool = False,
    deleteAfter: Optional[float] = None,
) -> None:
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Creates an embed message and sends it as response to a command invocation.

    Parameters
    ----------
    ctx : discord.ext.commands.Context
        The context of the command invocation.
    message : str
        The message to be included in the embed.
    error : bool, optional
        Whether the embed should be displayed in red (for errors).
    title : str, optional
        The title of the embed.
    isPrivate : bool, optional
        Whether the embed should be sent as a private message.
    isReply : bool, optional
        Whether the embed should be sent as a reply to the original message.
    deleteAfter : Optional[float], optional
        The time in seconds after which the message should be deleted.
        If it is None, the message will not be deleted.

    Returns
    -------
    None

    Raises
    ------
    ValueError
        If both `isPrivate` and `isReply` are set to `True`, as a message cannot be both private and a reply.
    """
    
    if error:
        message = f"{CROSS_RED} {message}"

    embed = Embed(
        title=title,
        description=message,
        color=Color.red() if error else ctx.author.color,
    )

    if isPrivate and isReply:
        raise ValueError("Cannot send a private reply. Choose either isPrivate or isReply.")

    # Determine the correct send method
    send_method = ctx.author.send if isPrivate else (ctx.reply if isReply else ctx.send)

    # Pass delete_after only if it is provided
    kwargs = {"delete_after": deleteAfter} if deleteAfter else {}

    return await send_method(embed=embed, **kwargs)
