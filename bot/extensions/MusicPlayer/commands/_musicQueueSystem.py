from discord import Color
from discord.ext import commands
from discord.ext.commands import Cog, Context, Range
from typing import Optional
from startup import MyBot
from bot.extensions.MusicPlayer._betterPlayer import BetterPlayer
from bot.extensions.MusicPlayer.commands._playerHelper import ensurePlayable, createQueueEmbed, buildPagination, QueueView
from helpers.respondEmbed import respondEmbed


PAGE_SIZE = 10


class MusicQueueSystem(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.getLogger()


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
            self.logger.error(f"Error while removing track at index {index} from queue: {e}")
            return await respondEmbed(ctx, message=f"An error occurred while trying to remove the track at index **#{1 + index}** from the queue. This could be due to an invalid index or an issue with the queue itself.", error=True)

        except Exception as e:
            # Catch-all for any other exceptions
            self.logger.error(f"Unexpected error while removing track at index {index} from queue: {e}")
            return await respondEmbed(ctx, message=f"An unexpected error occurred while trying to remove the track at index **#{1 + index}** from the queue. Please try again later.", error=True)

        await respondEmbed(ctx, message=f"Removed track **#{1 + index}** from the queue.")
