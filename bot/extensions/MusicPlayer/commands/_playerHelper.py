"""
The MIT License (MIT)

Copyright (c) 2026 Hoshino Yuki

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

from discord.ext.commands import Context
from bot.extensions.MusicPlayer._betterPlayer import BetterPlayer
from helpers.respondEmbed import respondEmbed


async def ensurePlayable(ctx: Context, player: BetterPlayer) -> bool:
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Helper function to ensure that the player is in a playable state.

    Parameters
    ----------
    ctx : `Context`
        The context of the command invocation.
    
    player : `BetterPlayer`
        The player instance to check.

    Returns
    -------
    bool
        True if the player is in a playable state, False otherwise.

    """

    if player is None:
        await respondEmbed(ctx, message=f"I'm not in a voice channel, either or the player is not connected to a node.", error=True)
        return False
    
    if player.queue.historyIsEmpty:
        # The player is not playing anything
        # We leave the color as user color or default because this is user friendly warning, not an actual error
        await respondEmbed(ctx, message=f"There is no track currently playing :thinking: ... Perhaps try to play something first, {ctx.author.mention}?")
        return False

    # If the player is in a playable state, return True
    return True
