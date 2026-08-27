from discord import app_commands, Color
from discord.ext import commands
from discord.ext.commands import Cog, Context, Range
from discord.app_commands import Choice
from lava_lyra import LoopMode, Playlist, QueueException, Timescale
from lava_lyra.pool import NodePool
from typing import cast, Optional, List
from startup import MyBot
from bot.extensions.MusicPlayer._betterPlayer import BetterPlayer
from bot.extensions.MusicPlayer.commands._playerHelper import ensurePlayable
from helpers.errorHandling import *
from helpers.respondEmbed import respondEmbed


class MusicGeneral(Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.logger = self.bot.getLogger()


    async def _advanceOrReport(self, player: BetterPlayer):
        try:
            await player.nextTrack()

        except Exception as e:
            if player.context:
                self.logger.error(f"An unexpected error occurred while trying to play the upcoming track: {e}")
                return await respondEmbed(player.context, message=f"An unexpected error occurred while trying play the upcoming track. The player may be stuck on the current track until the next track ends or errors again.", error=True)
            
            # If there was an error and the context is not available, we just simply ignore this action.
            return


    # The following are events from lava_lyra.events
    # We are using these so that if the track either stops or errors,
    # we can just skip to the next track

    # Of course, you can modify this to do whatever you like

    # General event listener for when a track ends or stops
    @commands.Cog.listener()
    async def on_lyra_track_end(self, player: BetterPlayer, track, _):
        if player._isRollingBack:
            # 
            # Prevent auto-skipping when a rollback operation is in progress
            #
            # We have to do this unfortunately because lyra does not provide a way to differentiate 
            # between a normal track end and a manual stop, and there are current no ways to workaround this.
            #
            # DO NOT REMOVE THIS CHECK or else the rollback WILL NOT WORK
            #
            return
        
        await self._advanceOrReport(player)


    @commands.Cog.listener()
    async def on_lyra_track_stuck(self, player: BetterPlayer, track, _):
        await self._advanceOrReport(player)


    @commands.Cog.listener()
    async def on_lyra_track_exception(self, player: BetterPlayer, track, _):
        await self._advanceOrReport(player)


    # Discord Autocomplete for Web search, rewrited for discord.py, and now for lava_lyra
    async def web_serach_autocomplete(self, ctx: Optional[Context], search: str) -> List[Choice[str]]:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Provides autocomplete suggestions for track search queries.

        Parameters
        ----------
        ctx : Optional`[Context]`
            The context of the command invocation. Optional.
        
        search : str
            The current input string to search for.

        Returns
        -------
        List`[app_commands.Choice[str]]`
            A list of autocomplete choices based on the search query. Limited to 25 choices.
        """

        node = NodePool.get_node()

        if not (search.startswith("http://") or search.startswith("https://")):   # Search from keywords
            try:
                tracks = await node.get_tracks(search)
                return [
                    Choice(name=result.title, value=result.uri)
                    for result in tracks[:25]   # Limit to 25 choices due to the limitation from Discord
                ]
            
            except TypeError:
                # The author did not entered anything yet
                return []
            
            except Exception:
                # An unexpected error occurred while trying to search for the track
                return []
        
        # Return a blank list because web URL's does not require to be searched, or the player object is None.
        return []
    

    @commands.hybrid_command(aliases=["p", "pla"])
    @app_commands.autocomplete(search=web_serach_autocomplete)
    async def play(self, ctx: Context, *, search: Optional[str] = None) -> Context | None:
        """
        Adds a selected track to the queue from web link or keywords.

        Parameters
        ----------
        search: str
            Link or keywords of the track you want to play.

        Returns
        -------
        commands.Context
            The context of the command invocation, if the command was successful.
        
        None
            If the command failed due to an error or invalid state.
        """

        await ctx.interaction.response.defer() if ctx.interaction else None
        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)

        if player is None:
            try:
                await ctx.author.voice.channel.connect(cls=BetterPlayer)
                player = ctx.voice_client  # type: ignore
                # Set the context, for later use in the message sending
                player.setContext(ctx)

            except AttributeError:
                # The author is not in a voice channel
                return await respondEmbed(ctx, message=f"{ctx.author.mention} Join a voice channel plz :pleading_face:  I don't think I can stay there without you :pensive: ...")
            
            except Exception as e:
                self.logger.error(f"An unexpected error occurred while trying to join the voice channel: {e}")
                return await respondEmbed(ctx, message=f"I was unable to join {ctx.author.voice.channel} due to an unexpected error. Please try again later.", error=True)

        if not search:
            return await respondEmbed(ctx, message=f"Looks like you've been specified searching online for the audio source, but haven't specified the track you would like to play :thinking: ...\nJust curious to know, what should I play right now, {ctx.author.mention}?")

        try:
            results = await player.get_tracks(search, ctx=ctx)

        except Exception as e:
            self.logger.error(f"An unexpected error occurred while trying to search for the track: {e}")
            return await respondEmbed(ctx, message=f"An unexpected error occurred while trying to search for the track.", error=True)

        if results is None or (isinstance(results, list) and len(results) == 0):
            return await respondEmbed(ctx, message=f"I couldn't find any tracks with that query you entered :thinking: ... Perhaps try to search something else and gave me a chance to play it, {ctx.author.mention}?")
        
        if isinstance(results, Playlist):
            player.queue.put(results)
            await respondEmbed(ctx, message=f"Added the playlist **{results.name}** (**{len(results.tracks)}** songs) to the queue.")

        else:
            track = results[0]  # Get the first track from the search results, this is why we specify the autocomplete to be uri
            player.queue.put(track)
            await respondEmbed(ctx, message=f"Added the track **{track.title}** to the queue.")

        if player.current is None:
            await player.nextTrack()   # Start playing if nothing is currently playing


    @commands.hybrid_command(aliases=["sk", "n", "next"])
    async def skip(self, ctx: Context, *, amount: Optional[Range[int, 1]] = 1) -> None:
        """
        Skips the current track being played in voice channel

        Parameters
        ----------
        amount: Optional`[int]` = 1
            Number of track to skip. Leave this blank if you want to skip the current track only.
        """

        await ctx.interaction.response.defer() if ctx.interaction else None
        messageLines: List[str] = []
        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)

        if not await ensurePlayable(ctx, player):  # Ensure the player is in a playable state
            return

        if amount < 1:  # Invalid amount
            return await respondEmbed(ctx, message=f"The amount of tracks to skip must be at least 1 :thinking: ...", error=True)
        
        if player.queue.isAtHistoryEnd:  # The author has already skipped all tracks in the queue
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, you are already **gone through all tracks** in the queue.", error=True)

        if player.isFinalTrack:  # The author just skipped the final track
            messageLines.append(f"Skipped the **final track**. There are **no upcoming tracks** to be played unless you **add more tracks to the queue** or **looping** is enabled.")
            amount = 1  # Set amount to 1 since they are at the final track

        elif amount == player.queue.size:  # The author just skipped to the last track
            messageLines.append(f"Skipping to the **final track** in the queue...")
        
        elif amount > player.queue.size:  # The author tried to skip more tracks than available in the queue
            amount = player.queue.size  # Set amount to the size of the queue
            messageLines.append(f"The amount of tracks you tried to skip **exceeded** the **total number of available tracks** in the queue. Automatically **skipping to the last track** in the queue...")

        else:   # Normal skip
            messageLines.append(f"Skipping **{amount}** track(s)...")

        # We keep the skipping logic here minimal, and let the player API handle the rest
        # This is the most resource efficient way to skip multiple tracks at once, without having to call nextTrack multiple times
        # And also avoids potential exploits or state inconsistencies (e.g. recurrsion errors)

        # Disable the loop mode if it's set to TRACK as the API breaks with this condition
        if player.queue.loop_mode == LoopMode.TRACK:
            player.queue.disable_loop()
            messageLines.append(f"Note: Repeat-One will be **disabled** to skip the track(s), please **re-enable it afterwards** if you need it.")

        if not (player.queue.loop_mode == LoopMode.QUEUE and player.isFinalTrack):
            # Replace the current queue with the remaining tracks after skipping          
            originalIndex = player.queue.currentTrackIndex
            player.queue.currentTrackIndex = originalIndex + amount - 1
            player.queue._queue = player.queue.playbackHistory[originalIndex + amount:]


        await player.stop()

        # Respond with the message lines
        await respondEmbed(ctx, message="\n".join(messageLines))


    @commands.hybrid_command(aliases=["prev", "back"])
    async def previous(self, ctx: Context, *, amount: Optional[Range[int, 1]] = 1) -> None:
        """
        Rollback to a previous track in the queue.

        Parameters
        ----------
        amount: Optional`[int]` = 1
            Number of tracks to rollback. Leave this blank if you want to rollback to the previous track only.
        """

        await ctx.interaction.response.defer() if ctx.interaction else None
        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)
        messageLines = []

        if not await ensurePlayable(ctx, player):  # Ensure the player is in a playable state
            return

        if amount < 1:  # Invalid amount
            return await respondEmbed(ctx, message=f"The amount of tracks to rollback must be at least 1 :thinking: ...", error=True)

        if player.queue.isAtHistoryStart:  # The author is already at the first track
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, you are already at the **first track** in the history.")

        if amount == max(player.queue.currentTrackIndex, player.queue.currentTrackIndex + int(player.queue.isAtHistoryEnd)):    # The author just rolled back to the first track
            messageLines.append("Rolling back to the **first track**...")

        elif amount > player.queue.currentTrackIndex:  # The author tried to rollback more tracks than available in history
            messageLines.append(f"The amount of tracks you tried to rollback **exceeded** the **total number of previous tracks** in the history. Automatically **rolling back to the first track** in the history...")
            amount = 1 + player.queue.currentTrackIndex  # Set amount to the current position

        else:  # The author is rolling back to a previous track
            messageLines.append(f"Rolling back **{amount}** track(s)...")

        # Rollback the track(s)
        prev_track = await player.previousTrack(amount)

        # Post check if the previous track is valid
        if not prev_track:
            self.logger.error(f"An unexpected error occurred while trying to rollback the track(s). The previous track is None.")
            messageLines.append(f"An unexpected error occurred while trying to rollback the track(s).")
            return await respondEmbed(ctx, message="\n".join(messageLines), error=True)
        
        await respondEmbed(ctx, message="\n".join(messageLines))


    @commands.hybrid_command(aliases=["pau", "break"])
    async def pause(self, ctx: Context):
        """
        Pauses the current track being played in voice channel
        """

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)

        if not await ensurePlayable(ctx, player):  # Ensure the player is in a playable state
            return

        if player.is_paused:
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, the track has been already paused!")

        try:
            await player.set_pause(pause=True)

        except Exception as e:
            self.logger.error(f"An unexpected error occurred while trying to pause the track: {e}")
            return await respondEmbed(ctx, message=f"An unexpected error occurred while trying to pause the track.", error=True)
            
        await respondEmbed(ctx, message="The track has been paused.")


    @commands.hybrid_command(aliases=["resu", "continue"])
    async def resume(self, ctx: Context):
        """
        Resumes the current track which is paused in voice channel
        """

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)

        if not await ensurePlayable(ctx, player):  # Ensure the player is in a playable state
            return

        if not player.is_paused:
            return await respondEmbed(ctx, message=f"{ctx.author.mention}, the track has not been paused.")

        try:
            await player.set_pause(pause=False)

        except Exception as e:
            self.logger.error(f"An unexpected error occurred while trying to resume the track: {e}")
            return await respondEmbed(ctx, message=f"An unexpected error occurred while trying to resume the track.", error=True)

        await respondEmbed(ctx, message="The track has been resumed.")


    @commands.hybrid_command(aliases=["now"])
    async def nowplaying(self, ctx: Context) -> None:
        """
        Display the current track being played in voice channel
        """

        if ctx.interaction:
            await ctx.interaction.response.defer()

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)

        if not await ensurePlayable(ctx, player):  # Ensure the player is in a playable state
            return

        nowPlayingEmbed, customArtworkFile = await player.nowPlayingEmbed(player.current)  # Get the now playing embed from the player from _player.py
        nowPlayingEmbed.color = getattr(ctx.author, "color", Color.default())

        if customArtworkFile is None:
            return await ctx.send(embed=nowPlayingEmbed)
        
        await ctx.send(embed=nowPlayingEmbed, file=customArtworkFile)


    @commands.hybrid_command(aliases=["rep", "r"])
    async def replay(self, ctx: Context):
        """
        Replay the current track.
        """

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)

        if not await ensurePlayable(ctx, player):  # Ensure the player is in a playable state
            return

        # Replay the track
        try:
            await player.seek(0)

        except Exception as e:
            self.logger.error(f"An error occurred while trying to replay the track: {e}")
            return await respondEmbed(ctx, message=f"An error occurred while trying to replay the track.", error=True)

        await respondEmbed(ctx, message=f"Replaying the current track...")


    @commands.hybrid_group(name="repeat", help="Toggle repeat for the current track or the entire queue.")
    async def repeat(self, ctx: Context):
        # This is the main command group for repeat
        # We won't implement any logic here, as the subcommands will handle the functionality
        # If no subcommand is invoked, return an error message
        await respondEmbed(ctx, message=f"{ctx.author.mention}, you need to specify a subcommand: `one` or `all`.", error=True)
    

    @repeat.command()
    async def one(self, ctx: Context):
        """
        Toggle repeat for the current track.
        """

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)
        messageLines: List[str] = []

        if not await ensurePlayable(ctx, player):  # Ensure the player is in a playable state
            return

        if player.queue.loop_mode == LoopMode.TRACK:
            messageLines.append(f"Disabling repeat for the current track...")

            try:
                player.queue.disable_loop()

            except QueueException as e:
                messageLines.append(f"The repeat mode is **already disabled** for the current track. \n\n {e}")
                return await respondEmbed(ctx, message="\n".join(messageLines), error=True)
            
            except Exception as e:
                self.logger.error(f"An error occurred while trying to disable repeat for the current track: {e}")
                messageLines.append(f"An error occurred while trying to disable repeat for the current track.")
                return await respondEmbed(ctx, message="\n".join(messageLines), error=True)

            await respondEmbed(ctx, message="\n".join(messageLines))

        else:
            await respondEmbed(ctx, message=f"Repeating the current track...")
            player.queue.set_loop_mode(LoopMode.TRACK)


    @repeat.command()
    async def all(self, ctx: Context):
        """
        Toggle repeat for the entire queue.
        """

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)
        messageLines: List[str] = []

        if not await ensurePlayable(ctx, player):  # Ensure the player is in a playable state
            return

        if player.queue.loop_mode == LoopMode.QUEUE:
            messageLines.append(f"Disabling repeat for the entire queue...")

            try:
                player.queue.disable_loop()

            except QueueException as e:
                messageLines.append(f"The repeat mode is **already disabled** for the entire queue. \n\n {e}")
                return await respondEmbed(ctx, message="\n".join(messageLines), error=True)
            
            except Exception as e:
                self.logger.error(f"An error occurred while trying to disable repeat for the entire queue: {e}")
                messageLines.append(f"An error occurred while trying to disable repeat for the entire queue.")
                return await respondEmbed(ctx, message="\n".join(messageLines), error=True)

            await respondEmbed(ctx, message="\n".join(messageLines))

        else:
            await respondEmbed(ctx, message=f"Repeating the entire queue...")
            player.queue.set_loop_mode(LoopMode.QUEUE)


    @commands.hybrid_command(aliases=["halt", "st"])
    async def stop(self, ctx: Context):
        """
        Stops the current track being played in voice channel and clears the queue.
        """

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)

        if not await ensurePlayable(ctx, player):  # Ensure the player is in a playable state
            return

        try:
            if player.queue.is_looping:
                player.queue.disable_loop()  # Disable looping if it's enabled
            
            player.queue.clear()  # Clear the queue
            await player.stop()   # Stop the current track
            
            # The controller will not be updated automatically after stopping the track, so we do it manually
            player.updateController.start()

        except Exception as e:
            self.logger.error(f"An error occurred while trying to stop the track: {e}")
            return await respondEmbed(ctx, message=f"An error occurred while trying to stop the track.", error=True)
        
        await respondEmbed(ctx, message=f"Stopped the current track and cleared the queue.")


    @commands.hybrid_command(aliases=["vol", "v"])
    async def volume(self, ctx: Context, *, value: Optional[Range[int, 0, 500]] = 60) -> None:
        """
        Change the volume of the music player

        Parameters
        ----------
        value: Optional`[int]` = 30
            The new volume to set. Leave this blank if you want to set it as default.
        """

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)

        if not await ensurePlayable(ctx, player):  # Ensure the player is in a playable state
            return

        if value < 0 or value > 500:  # Invalid volume
            return await respondEmbed(ctx, message=f"The volume must be between **0** and **500** :thinking: ...\n Generally, **60** is already good enough, **100** is considered as very loud, and **200** will blow your eardrums out lol.", error=True)

        # Set the volume
        try:
            await player.set_volume(value)

        except Exception as e:
            self.logger.error(f"An error occurred while trying to change the volume: {e}")
            return await respondEmbed(ctx, message=f"An error occurred while trying to change the volume.", error=True)
        
        await respondEmbed(ctx, message=f"Changed volume to **{value}%**")


    @commands.hybrid_command(aliases=["nig"])
    async def nightcore(self, ctx: Context):
        """
        Toggle nightcore mode on the player.
        """

        # Set the filter to a nightcore style. We have to use pomice.Timescale to adjust the pitch and speed.
        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)
        
        if not await ensurePlayable(ctx, player):  # Ensure the player is in a playable state
            return

        if player.filters.empty:
            await player.add_filter(Timescale.nightcore(), fast_apply=True)
            await respondEmbed(ctx, message=f"**Activating** nightcore mode... The track may be briefly interrupted.")
        
        else:
            await player.reset_filters(fast_apply=True)
            await respondEmbed(ctx, message=f"**Deactivating** nightcore mode... The track may be briefly interrupted.")


