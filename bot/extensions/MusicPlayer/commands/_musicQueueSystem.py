import math
from discord import Color, Embed, Interaction, SelectOption
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context, Range
from discord.ui import View, Select
from lava_lyra import LoopMode
from typing import Optional, List
from bot.extensions.MusicPlayer._betterPlayer import BetterPlayer
from bot.extensions.MusicPlayer.commands._playerHelper import ensurePlayable
from helpers.respondEmbed import respondEmbed


PAGE_SIZE = 10


# Build page options based on the upcoming items in the queue.
def buildPagination(player: BetterPlayer, pageSize: int) -> List[SelectOption]:
    """
    Build page options based on the upcoming items in the queue.

    Page descriptions show absolute queue indices (1-based).

    Parameters
    ----------
    player : `BetterPlayer`
        The music player instance containing the queue.
    
    pageSize : int
        Number of tracks per page.
    
    Returns
    -------
    List`[SelectOption]`
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

    pages = math.ceil(upcomingTracksCount / pageSize)
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
    player : `BetterPlayer`
        The music player instance containing the queue.

    color : `discord.Color`
        The color to use for the embed.
    
    page : int
        The page number to display (1-based).

    pageSize : int
        Number of tracks per page. Defaults to 10.
    
    Returns
    -------
    `discord.Embed`
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
            totalPages = math.ceil(len(upcomingTracks) / pageSize)
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
        player : `BetterPlayer`
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
        interaction : `discord.Interaction`
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

        player : `BetterPlayer`
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


class MusicQueueSystem(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot


    @commands.hybrid_command(aliases=["qu"])
    async def queue(self, ctx: Context) -> None:
        """
        Show the music queue with pagination in the current guild.
        """

        player: BetterPlayer = ctx.voice_client

        if not await ensurePlayable(ctx, player):  # Ensure the player is in a playable state
            return

        # Build embed
        embed = createQueueEmbed(player=player, color=getattr(ctx.author, "color", Color.default()), page=1, pageSize=PAGE_SIZE)

        # Build view only if we have upcoming tracks in the queue
        options = buildPagination(player, PAGE_SIZE)
        if not options:
            return await ctx.send(embed=embed)

        view = QueueView(player=player, pageSize=PAGE_SIZE)
        
        await ctx.send(embed=embed, view=view or None)


    @commands.hybrid_command(aliases=["rm", "pop"])
    async def remove(self, ctx: Context, index: Optional[Range[int, 0]] = 0) -> None:
        """
        Remove a track from the queue by its index.

        Parameters
        ----------
        index : Optional[int]
            The index of the track to remove. Leave this blank or pass 0 to remove the last track in the queue.

        Returns
        -------
        None
        """

        player: BetterPlayer = ctx.voice_client

        if not await ensurePlayable(ctx, player):  # Ensure the player is in a playable state
            return

        if index is not None and (index < 0 or index > player.queue.historySize):
            return await respondEmbed(ctx, message=f"Please enter a valid index of the track you want to remove from the queue.", error=True)

        # Disable loop mode when removing tracks
        if player.queue.is_looping:
            player.queue.disable_loop()

        # Calculate the zero-based index, default to the last track if index is None
        index = (index - 1) % player.queue.historySize

        if index == player.queue.currentTrackIndex:
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, You cannot remove the **currently playing track**. Use the `skip` command instead to skip to the next track.")
        
        try:
            newCurrentIndex = player.queue.currentTrackIndex
            if newCurrentIndex is None:
                return await respondEmbed(ctx, message=f"I couldn't determine the current playback position. Please try again.", error=True)

            # Remove from history first.
            player.queue.playbackHistory.pop(index)

            # If we removed a track before the current one, shift current left once.
            if index < newCurrentIndex:
                newCurrentIndex -= 1

            player.queue.currentTrackIndex = newCurrentIndex

            # Rebuild upcoming queue from the track after the current index.
            # We don't need to worry if the current track is the final one, thanks to the way slicing works in Python :)
            player.queue._queue = player.queue.playbackHistory[newCurrentIndex + 1:]

        except (ValueError, IndexError) as e:
            self.bot.logger.error(f"Error while removing track at index {index} from queue: {e}")
            return await respondEmbed(ctx, message=f"An error occurred while trying to remove the track at index **#{1 + index}** from the queue. This could be due to an invalid index or an issue with the queue itself.", error=True)
        
        except Exception as e:
            # Catch-all for any other exceptions
            self.bot.logger.error(f"Unexpected error while removing track at index {index} from queue: {e}")
            return await respondEmbed(ctx, message=f"An unexpected error occurred while trying to remove the track at index **#{1 + index}** from the queue. Please try again later.", error=True)

        await respondEmbed(ctx, message=f"Removed track **#{1 + index}** from the queue.")

