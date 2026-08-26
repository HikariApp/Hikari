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

CROSS_RED = "<a:crossred:1356353067024515266>"


async def respondEmbed(
    ctx: commands.Context,
    message: str,
    *,
    error: bool = False,
    title: str = "",
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

    Returns
    -------
    None
    """
    
    if error:
        message = f"{CROSS_RED} {message}"
    embed = Embed(
        title=title,
        description=message,
        color=Color.red() if error else ctx.author.color,
    )
    return await ctx.send(embed=embed)

