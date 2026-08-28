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

from numpy.ma import ceil
from discord import Button, ButtonStyle, Color, Embed, Interaction, Message, SelectOption, User
from discord.ext.commands import Context
from discord.ui import button, View, Select
from lava_lyra import LoopMode
from typing import List, Optional
from bot.extensions.MusicPlayer._betterPlayer import BetterPlayer
from helpers.respondEmbed import CROSS_RED, respondEmbed

# Fixed Interaction response for confirmations that are not for the interacting user.
NON_AUTHOR_CONFIRMATION_EMBED = Embed(
    description=f"{CROSS_RED} This confirmation isn't for you :thinking: ...",
    color=Color.red(),
)

# Ensure the player is in a playable state before proceeding with any queue-related operations.
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


# Build page options based on the upcoming items in the queue.
def buildPagination(player: BetterPlayer, pageSize: int) -> List[SelectOption]:
    """
    Build page options based on the upcoming items in the queue.

    Page descriptions show absolute queue indices (1-based).

    Parameters
    ----------
    player : BetterPlayer
        The music player instance containing the queue.
    
    pageSize : int
        Number of tracks per page.

    Returns
    -------
    List[SelectOption]
        A list of SelectOption for the dropdown menu.
    """

    total = player.queue.historySize
    if total <= 0:
        return []

    # Upcoming starts right after current position
    upcomingTrackStartIndex = min(max(player.queue.currentTrackIndex, 0) + 1, total)  # zero-based, guard -1
    upcomingTracksCount = max(total - upcomingTrackStartIndex, 0)
    if upcomingTracksCount <= 0:
        return []

    pages = ceil(upcomingTracksCount / pageSize)
    options: List[SelectOption] = []

    for i in range(pages):
        # Zero-based
        startIndexOfPage = upcomingTrackStartIndex + (i * pageSize)
        endingIndexOfPage = min(upcomingTrackStartIndex + (i + 1) * pageSize - 1, total - 1)

        # 1-based for display
        description = f"{1 + startIndexOfPage}" if startIndexOfPage == endingIndexOfPage else f"{1 + startIndexOfPage} - {1 + endingIndexOfPage}"
        options.append(SelectOption(label=str(i + 1), value=str(i + 1), description=description))

    return options


def createQueueEmbed(player: BetterPlayer, color: Color, page: int, pageSize: int) -> Embed:
    """
    Create an embed representing the current queue state.

    Parameters
    ----------
    player : BetterPlayer
        The music player instance containing the queue.

    color : discord.Color
        The color to use for the embed.
    
    page : int
        The page number to display (1-based).

    pageSize : int
        Number of tracks per page. Defaults to 10.

    Returns
    -------
    discord.Embed
        The constructed embed showing the queue.
    """

    embed = Embed(title="Queue:", color=color)

    # Using playbackHistory to avoid potential issues if the queue is modified during iteration
    total = player.queue.historySize

    # Now playing
    if player.current is None:
        embed.add_field(name="Now Playing :notes: :", value="There are no tracks playing now", inline=False)
        embed.add_field(name="Upcoming Tracks:", value="There are no upcoming tracks will be played", inline=False)
    
    else:
        currentTrackIndex = 0
        
        if total > 0:
            currentTrackIndex = min(max(player.queue.currentTrackIndex, 0), total - 1)
        embed.add_field(
            name=f"Now Playing :notes: ({currentTrackIndex + 1}/{max(total, 1)}) :",
            value=f"> **#{currentTrackIndex + 1}** - {player.current.title} {player.current.requester.mention if player.current.requester else ''}",
            inline=False,
        )

        # Upcoming section
        upcomingTrackStartIndex = min(max(player.queue.currentTrackIndex, 0) + 1, total)

        upcomingTracks = player.queue.playbackHistory[upcomingTrackStartIndex:]
        embed.add_field(
            name="Upcoming Tracks:",
            value="" if upcomingTracks else "There are no upcoming tracks will be played",
            inline=False,
        )

        # Upcoming list (paginated)
        if upcomingTracks:
            totalPages = ceil(len(upcomingTracks) / pageSize)
            page = max(1, min(page, totalPages))
            startIndexOfPage = (page - 1) * pageSize
            endingIndexOfPage = startIndexOfPage + pageSize
            
            for index, track in enumerate(upcomingTracks[startIndexOfPage:endingIndexOfPage]):
                absIndex = upcomingTrackStartIndex + startIndexOfPage + (1 + index)  # 1-based absolute index
                embed.add_field(
                    name="",
                    value=f"> **#{absIndex}** - {track.title} {track.requester.mention if track.requester else ''}",
                    inline=False,
                )
                
    if player.queue.is_looping:
        embed.add_field(name="", value="\u202a", inline=False)

    if player.queue.loop_mode == LoopMode.TRACK:
        embed.add_field(name="Repeat:", value="**Enabled** for the current track", inline=False)

    if player.queue.loop_mode == LoopMode.QUEUE:
        embed.add_field(name="Repeat:", value="**Enabled** for the entire queue", inline=False)

    return embed


# Dropdown menu for selecting queue pages.
class QueueSelect(Select):
    def __init__(self, *, player: BetterPlayer, pageSize: int) -> None:
        """
        Initialize the `QueueSelect` dropdown menu.

        Parameters
        ----------
        player : BetterPlayer
            The music player instance containing the queue.

        pageSize : int
            Number of tracks per page.

        Returns
        -------
        None
        """

        self.player = player
        self.pageSize = pageSize

        options = buildPagination(player, pageSize)
        placeholder = "Page" if options else "No pages"
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options,
            disabled=not bool(options),
        )


    async def callback(self, interaction: Interaction):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio/coroutine.html).

        Handles the selection of a page from the dropdown menu and updates the queue embed accordingly.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object representing the user's selection.

        Returns
        -------
        None
        """

        # Refresh options in case queue mutated
        self.options = buildPagination(self.player, self.pageSize)

        page = int(self.values[0]) if self.values else 1

        embed = createQueueEmbed(
            player=self.player,
            color=interaction.user.color,
            page=page,
            pageSize=self.pageSize,
        )

        # Check if there are any options available
        if len(self.options) == 0:
            return await interaction.response.edit_message(embed=embed, view=None)

        # Rebuild the whole view to ensure the latest options are reflected if there are options available
        new_view = QueueView(
            player=self.player,
            pageSize=self.pageSize
        )

        await interaction.response.edit_message(embed=embed, view=new_view)


class QueueView(View):
    def __init__(self, *, player: BetterPlayer, pageSize: int) -> None:
        """
        Initialize the `QueueView` containing the `QueueSelect` dropdown menu.

        Parameters
        ----------
        player : BetterPlayer
            The music player instance containing the queue.

        pageSize : int
            Number of tracks per page.

        Returns
        -------
        None
        """

        super().__init__(timeout=300)   # 5 minutes timeout
        self.add_item(
            QueueSelect(player=player, pageSize=pageSize)
        )


# Simple confirmation view with "Yes" and "Cancel" buttons.
class ConfirmView(View):
    def __init__(
        self,
        author: User,
        *,
        timeout: float = 30.0,
        confirmMessage: Optional[str] = None,
        cancelMessage: Optional[str] = None,
    ) -> None:
        """
        Initialize the `ConfirmView` containing the confirm/cancel buttons.

        The view is locked to the invoking user, so only they may respond.

        Parameters
        ----------
        author : discord.abc.User
            The user allowed to interact with this confirmation.

        timeout : float
            How long (in seconds) before the prompt expires. Defaults to 30.0.

        confirmMessage : str, optional
            If set, the prompt embed is edited in place to this text on confirm,
            and the buttons are removed. If None, only the buttons are disabled.

        cancelMessage : str, optional
            If set, the prompt embed is edited in place to this text on cancel
            (or timeout), and the buttons are removed. If None, only the buttons
            are disabled.

        Returns
        -------
        None
        """

        super().__init__(timeout=timeout)
        self.author = author
        self.value: Optional[bool] = None
        self.message: Optional[Message] = None
        self.confirmMessage = confirmMessage
        self.cancelMessage = cancelMessage


    async def interaction_check(self, interaction: Interaction) -> bool:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio/coroutine.html).

        Ensures that only the invoking user can interact with the confirmation.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object representing the user's click.

        Returns
        -------
        bool
            True if the interacting user is the invoker, False otherwise.
        """

        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                embed=NON_AUTHOR_CONFIRMATION_EMBED, ephemeral=True
            )
            return False
        return True


    def disableAll(self) -> None:
        """
        Disable every button in the view.

        Returns
        -------
        None
        """

        for child in self.children:
            if isinstance(child, Button):
                child.disabled = True


    async def _finish(self, interaction: Interaction, value: bool, resultMessage: Optional[str]) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio/coroutine.html).

        Records the result and edits the prompt in place: if a result message is
        given, the embed title is cleared and its description replaced; the view
        is removed either way.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object representing the user's click.

        value : bool
            The outcome to record (True for confirm, False for cancel).

        resultMessage : str, optional
            The text to show in place, or None to leave the embed untouched
            (only the buttons are removed).

        Returns
        -------
        None
        """

        self.value = value
        self.disableAll()

        if resultMessage is not None and interaction.message is not None and interaction.message.embeds:
            embed = interaction.message.embeds[0]
            embed.title = None
            embed.description = resultMessage
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.edit_message(view=None)

        self.stop()


    @button(label="Yes, proceed", style=ButtonStyle.danger)
    async def confirm(self, interaction: Interaction, _: Button) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio/coroutine.html).

        Handles the confirm action.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object representing the user's click.

        _ : discord.ui.Button
            The button that was clicked (unused).

        Returns
        -------
        None
        """

        await self._finish(interaction, True, self.confirmMessage)


    @button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, _: Button) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio/coroutine.html).

        Handles the cancel action.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object representing the user's click.

        _ : discord.ui.Button
            The button that was clicked (unused).

        Returns
        -------
        None
        """

        await self._finish(interaction, False, self.cancelMessage)


    async def on_timeout(self) -> None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio/coroutine.html).

        Treats an expired prompt as a cancellation, editing the prompt in place
        if the message reference and a cancel message are available.

        Returns
        -------
        None
        """

        self.value = False
        self.disableAll()

        if self.message is not None:
            try:
                if self.cancelMessage is not None and self.message.embeds:
                    embed = self.message.embeds[0]
                    if embed is not None:
                        embed.title = None
                        embed.description = self.cancelMessage
                        await self.message.edit(embed=embed, view=None)
                else:
                    await self.message.edit(view=self)
            except Exception:
                pass
