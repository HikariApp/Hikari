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
from discord.ext.voice_recv import VoiceRecvClient
from discord.ui import button, View, Select
from lava_lyra import LoopMode
from typing import List, Optional
from hikari_bot.bot.extensions.musicplayer._betterplayer import BetterPlayer
from hikari_bot.helpers.respondembed import CROSS_RED, ResponseTarget, respond_embed

# Fixed Interaction response for confirmations that are not for the interacting user.
NON_AUTHOR_CONFIRMATION_EMBED = Embed(
    description=f"{CROSS_RED} This confirmation isn't for you :thinking: ...",
    color=Color.red(),
)

# Ensure the player is in a playable state before proceeding with any queue-related operations.
async def ensure_playable(ctx: Context, player: BetterPlayer | VoiceRecvClient) -> bool:
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Helper function to ensure that the player is in a playable state.

    Parameters
    ----------
    ctx : commands.Context
        The context of the command invocation.
    
    player : BetterPlayer | discord.ext.voice_recv.VoiceRecvClient
        The player instance to check.

    Returns
    -------
    bool
        True if the player is in a playable state, False otherwise.
    """

    if player is None:
        await respond_embed(ctx, message=f"I'm not in a voice channel, either or the player is not connected to a node.", error=True)
        return False
    
    if isinstance(player, VoiceRecvClient):
        await respond_embed(ctx, message=f"The voice client is now being occupied by the voice recorder. Please terminate the recorder and try again.", target=ResponseTarget.EPHEMERAL, error=True)
        return False
    
    if player.queue.history_is_empty:
        # The player is not playing anything
        # We leave the color as user color or default because this is user friendly warning, not an actual error
        await respond_embed(ctx, message=f"There is no track currently playing :thinking: ... Perhaps try to play something first, {ctx.author.mention}?")
        return False

    # If the player is in a playable state, return True
    return True


# Build page options based on the upcoming items in the queue.
def build_pagination(player: BetterPlayer, page_size: int) -> List[SelectOption]:
    """
    Build page options based on the upcoming items in the queue.

    Page descriptions show absolute queue indices (1-based).

    Parameters
    ----------
    player : BetterPlayer
        The music player instance containing the queue.
    
    page_size : int
        Number of tracks per page.

    Returns
    -------
    list of SelectOption
        A list of SelectOption for the dropdown menu.
    """

    total = player.queue.history_size
    if total <= 0:
        return []

    # Upcoming starts right after current position
    upcoming_track_start_index = min(max(player.queue.current_track_index, 0) + 1, total)  # zero-based, guard -1
    upcoming_tracks_count = max(total - upcoming_track_start_index, 0)
    if upcoming_tracks_count <= 0:
        return []

    pages = ceil(upcoming_tracks_count / page_size)
    options: List[SelectOption] = []

    for i in range(pages):
        # Zero-based
        start_index_of_page = upcoming_track_start_index + (i * page_size)
        ending_index_of_page = min(upcoming_track_start_index + (i + 1) * page_size - 1, total - 1)

        # 1-based for display
        description = f"{1 + start_index_of_page}" if start_index_of_page == ending_index_of_page else f"{1 + start_index_of_page} - {1 + ending_index_of_page}"
        options.append(SelectOption(label=str(i + 1), value=str(i + 1), description=description))

    return options


def create_queue_embed(player: BetterPlayer, color: Color, page: int, page_size: int) -> Embed:
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

    page_size : int
        Number of tracks per page. Defaults to 10.

    Returns
    -------
    discord.Embed
        The constructed embed showing the queue.
    """

    embed = Embed(title="Queue:", color=color)

    # Using playback_history to avoid potential issues if the queue is modified during iteration
    total = player.queue.history_size

    # Now playing
    if player.current is None:
        embed.add_field(name="Now Playing :notes: :", value="There are no tracks playing now", inline=False)
        embed.add_field(name="Upcoming Tracks:", value="There are no upcoming tracks will be played", inline=False)
    
    else:
        current_track_index = 0
        
        if total > 0:
            current_track_index = min(max(player.queue.current_track_index, 0), total - 1)
        embed.add_field(
            name=f"Now Playing :notes: ({current_track_index + 1}/{max(total, 1)}) :",
            value=f"> **#{current_track_index + 1}** - {player.current.title} {player.current.requester.mention if player.current.requester else ''}",
            inline=False,
        )

        # Upcoming section
        upcoming_track_start_index = min(max(player.queue.current_track_index, 0) + 1, total)

        upcoming_tracks = player.queue.playback_history[upcoming_track_start_index:]
        embed.add_field(
            name="Upcoming Tracks:",
            value="" if upcoming_tracks else "There are no upcoming tracks will be played",
            inline=False,
        )

        # Upcoming list (paginated)
        if upcoming_tracks:
            total_pages = ceil(len(upcoming_tracks) / page_size)
            page = max(1, min(page, total_pages))
            start_index_of_page = (page - 1) * page_size
            ending_index_of_page = start_index_of_page + page_size
            
            for index, track in enumerate(upcoming_tracks[start_index_of_page:ending_index_of_page]):
                abs_index = upcoming_track_start_index + start_index_of_page + (1 + index)  # 1-based absolute index
                embed.add_field(
                    name="",
                    value=f"> **#{abs_index}** - {track.title} {track.requester.mention if track.requester else ''}",
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
    def __init__(self, *, player: BetterPlayer, page_size: int) -> None:
        """
        Initialize the `QueueSelect` dropdown menu.

        Parameters
        ----------
        player : BetterPlayer
            The music player instance containing the queue.

        page_size : int
            Number of tracks per page.

        Returns
        -------
        None
        """

        self.player = player
        self.page_size = page_size

        options = build_pagination(player, page_size)
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
        self.options = build_pagination(self.player, self.page_size)

        page = int(self.values[0]) if self.values else 1

        embed = create_queue_embed(
            player=self.player,
            color=interaction.user.color,
            page=page,
            page_size=self.page_size,
        )

        # Check if there are any options available
        if len(self.options) == 0:
            return await interaction.response.edit_message(embed=embed, view=None)

        # Rebuild the whole view to ensure the latest options are reflected if there are options available
        new_view = QueueView(
            player=self.player,
            page_size=self.page_size
        )

        await interaction.response.edit_message(embed=embed, view=new_view)


class QueueView(View):
    def __init__(self, *, player: BetterPlayer, page_size: int) -> None:
        """
        Initialize the `QueueView` containing the `QueueSelect` dropdown menu.

        Parameters
        ----------
        player : BetterPlayer
            The music player instance containing the queue.

        page_size : int
            Number of tracks per page.

        Returns
        -------
        None
        """

        super().__init__(timeout=300)   # 5 minutes timeout
        self.add_item(
            QueueSelect(player=player, page_size=page_size)
        )


# Simple confirmation view with "Yes" and "Cancel" buttons.
class ConfirmView(View):
    def __init__(
        self,
        author: User,
        *,
        timeout: float = 30.0,
        confirm_message: Optional[str] = None,
        cancel_message: Optional[str] = None,
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

        confirm_message : str, optional
            If set, the prompt embed is edited in place to this text on confirm,
            and the buttons are removed. If None, only the buttons are disabled.

        cancel_message : str, optional
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
        self.confirm_message = confirm_message
        self.cancel_message = cancel_message


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


    def disable_all(self) -> None:
        """
        Disable every button in the view.

        Returns
        -------
        None
        """

        for child in self.children:
            if isinstance(child, Button):
                child.disabled = True


    async def _finish(self, interaction: Interaction, value: bool, result_message: Optional[str]) -> None:
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

        result_message : str, optional
            The text to show in place, or None to leave the embed untouched
            (only the buttons are removed).

        Returns
        -------
        None
        """

        self.value = value
        self.disable_all()

        if result_message is not None and interaction.message is not None and interaction.message.embeds:
            embed = interaction.message.embeds[0]
            embed.title = None
            embed.description = result_message
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

        await self._finish(interaction, True, self.confirm_message)


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

        await self._finish(interaction, False, self.cancel_message)


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
        self.disable_all()

        if self.message is not None:
            try:
                if self.cancel_message is not None and self.message.embeds:
                    embed = self.message.embeds[0]
                    if embed is not None:
                        embed.title = None
                        embed.description = self.cancel_message
                        await self.message.edit(embed=embed, view=None)
                else:
                    await self.message.edit(view=self)
            except Exception:
                pass
