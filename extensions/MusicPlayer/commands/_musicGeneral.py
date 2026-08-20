from discord import app_commands, Color, Embed
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context
from discord.app_commands import Choice, Range
from lava_lyra import LoopMode, Playlist, QueueException, Timescale
from lava_lyra.pool import NodePool
from typing import cast, Optional, List
from extensions.MusicPlayer._player import BetterPlayer
from errorhandling._errorHandling import *


# Helper function to get the color of the user who invoked the command
def userColor(ctx: Context) -> Color:
    """
    Get the color of the user who invoked the command.

    Parameters
    ----------
    ctx : `Context`
        The context of the command invocation.

    Returns
    -------
    Color
        The color of the user who invoked the command.

    """
    return ctx.interaction.user.color if ctx.interaction else ctx.author.color


class MusicGeneral(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

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
        
        try:
            await player.nextTrack()

        except Exception as e:
            if player.context:
                return player.context.send(embed=Embed(title="", description=f"<a:crossred:1356353067024515266> An unexpected error occurred while trying play the upcoming track. The player may be stuck on the current track until the next track ends or errors again. \n\n {e}", color=Color.red()))
            
            # If there was an error and the context is not available, we just simply ignore this action.
            return


    @commands.Cog.listener()
    async def on_lyra_track_stuck(self, player: BetterPlayer, track, _):
        try:
            await player.nextTrack()

        except Exception as e:
            if player.context:
                return player.context.send(embed=Embed(title="", description=f"<a:crossred:1356353067024515266> An unexpected error occurred while trying play the upcoming track. The player may be stuck on the current track until the next track ends or errors again. \n\n {e}", color=Color.red()))
            
            # If there was an error and the context is not available, we just simply ignore this action.
            return


    @commands.Cog.listener()
    async def on_lyra_track_exception(self, player: BetterPlayer, track, _):
        try:
            await player.nextTrack()

        except Exception as e:
            if player.context:
                return player.context.send(embed=Embed(title="", description=f"<a:crossred:1356353067024515266> An unexpected error occurred while trying play the upcoming track. The player may be stuck on the current track until the next track ends or errors again. \n\n {e}", color=Color.red()))
            
            # If there was an error and the context is not available, we just simply ignore this action.
            return


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
        ctx: `Context`
            The context of the command invocation.

        search: str
            Link or keywords of the track you want to play.

        Returns
        -------
        Context | None

        """

        await ctx.interaction.response.defer() if ctx.interaction else None
        embed = Embed(title="")
        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)

        if player is None:
            try:
                await ctx.author.voice.channel.connect(cls=BetterPlayer)
                player = ctx.voice_client  # type: ignore
                # Set the context, for later use in the message sending
                player.setContext(ctx)

            except AttributeError:
                # The author is not in a voice channel
                embed.add_field(name="", value=f"{ctx.author.mention} Join a voice channel plz :pleading_face:  I don't think I can stay there without you :pensive: ...", inline=False)
                embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
                return await ctx.send(embed=embed)
            
            except Exception as e:
                embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I was unable to join {ctx.author.voice.channel} due to an unexpected error. Please try again later. \n\n {e}", inline=False)
                embed.color = Color.red()
                return await ctx.send(embed=embed)
            
        if not search:
            embed.add_field(name="", value=f"Looks like you've been specified searching online for the audio source, but haven't specified the track you would like to play :thinking: ...\nJust curious to know, what should I play right now, {ctx.author.mention}?", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)

        try:
            results = await player.get_tracks(search, ctx=ctx)

        except Exception as e:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> An unexpected error occurred while trying to search for the track. \n\n {e}", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)

        if results is None or (isinstance(results, list) and len(results) == 0):
            embed.add_field(name="No results", value=f"I couldn't find any tracks with that query you entered :thinking: ... Perhaps try to search something else and gave me a chance to play it, {ctx.author.mention}?", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)

        if isinstance(results, Playlist):
            player.queue.put(results)
            embed.add_field(name="", value=f"Added the playlist **{results.name}** (**{len(results.tracks)}** songs) to the queue.", inline=False)
            embed.color = userColor(ctx)
            await ctx.send(embed=embed)

        else:
            track = results[0]  # Get the first track from the search results, this is why we specify the autocomplete to be uri
            #for i in range(102):
            player.queue.put(track)
            embed.add_field(name="", value=f"Added the track **{track.title}** to the queue.", inline=False)
            embed.color = userColor(ctx)
            await ctx.send(embed=embed)

        if player.current is None:
            await player.nextTrack()   # Start playing if nothing is currently playing


    @commands.hybrid_command(aliases=["sk", "n", "next"])
    async def skip(self, ctx: Context, *, amount: Optional[Range[int, 1]] = 1) -> None:
        """
        Skips the current track being played in voice channel

        Parameters
        ----------
        ctx: `Context`
            The context of the command invocation.

        amount: Optional`[int]` = 1
            Number of track to skip. Leave this blank if you want to skip the current track only.

        Returns
        -------
        None


        """

        await ctx.interaction.response.defer() if ctx.interaction else None
        embed = Embed(title="")
        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)

        if player is None:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I'm not in a voice channel, either or the player is not connected to a node.", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)

        if len(player.queue.doubleEndedQueue) == 0:  # The player is not playing anything before
            embed.add_field(name="", value=f"There are no tracks being played in history :thinking: ... Perhaps try to play something first, {ctx.author.mention}?", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)
        
        if amount < 1:  # Invalid amount
            embed.add_field(name="", value=f"The amount of tracks to skip must be at least 1 :thinking: ...", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        if player.queue.hasReachedTheEnd:  # The author has already skipped all tracks in the queue
            embed.add_field(name="", value=f"{ctx.author.mention}, you are already **gone through all tracks** in the queue.", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)

        if player.current and player.isFinalTrack:  # The author just skipped the final track
            embed.add_field(name="", value=f"Skipped the **final track**. There are **no upcoming tracks** to be played unless you **add more tracks to the queue** or **looping** is enabled.", inline=False)
            amount = 1  # Set amount to 1 since they are at the final track

        elif amount == player.queue.size:  # The author just skipped to the last track
            embed.add_field(name="", value=f"Skipping to the **final track** in the queue...", inline=False)
        
        elif amount > player.queue.size:  # The author tried to skip more tracks than available in the queue
            amount = player.queue.size  # Set amount to the size of the queue
            embed.add_field(name="", value=f"The amount of tracks you tried to skip **exceeded** the **total number of available tracks** in the queue. Automatically **skipping to the last track** in the queue...", inline=False)

        else:   # Normal skip
            embed.add_field(name="", value=f"Skipping **{amount}** track(s)...", inline=False)

        # We keep the skipping logic here minimal, and let the player API handle the rest
        # This is the most resource efficient way to skip multiple tracks at once, without having to call nextTrack multiple times
        # And also avoids potential exploits or state inconsistencies (e.g. recurrsion errors)

        # Disable the loop mode if it's set to TRACK as the API breaks with this condition
        if player.queue.loop_mode == LoopMode.TRACK:
            player.queue.disable_loop()
            embed.add_field(name="", value=f"Note: Repeat-One will be **disabled** to skip the track(s), please **re-enable it afterwards** if you need it.", inline=False)

        if not (player.queue.loop_mode == LoopMode.QUEUE and player.isFinalTrack):
            # Replace the current queue with the remaining tracks after skipping          
            originalIndex = player.queue.currentIndex
            player.queue.currentIndex = originalIndex + amount - 1
            player.queue._queue = player.queue.doubleEndedQueue[originalIndex + amount:]


        await player.stop()
    
        embed.color = userColor(ctx)
        await ctx.send(embed=embed)


    @commands.hybrid_command(aliases=["prev", "back"])
    async def previous(self, ctx: Context, *, amount: Optional[Range[int, 1]] = 1) -> None:
        """
        Rollback to a previous track in the queue.

        Parameters
        ----------
        ctx: `Context`
            The context of the command invocation.

        amount: Optional`[int]` = 1
            Number of tracks to rollback. Leave this blank if you want to rollback to the previous track only.
        
        Returns
        -------
        None

        """

        await ctx.interaction.response.defer() if ctx.interaction else None
        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)
        embed = Embed(title="")

        if player is None:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I'm not in a voice channel, either or the player is not connected to a node.", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)

        
        if len(player.queue.doubleEndedQueue) == 0:  # The player is not playing anything
            embed.add_field(name="", value=f"There is no track currently playing :thinking: ... Perhaps try to play something first, {ctx.author.mention}?", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)
        
        if amount < 1:  # Invalid amount
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> The amount of tracks to rollback must be at least 1 :thinking: ...", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)

        if player.queue.hasReachedTheBeginning:  # The author is already at the first track
            embed.add_field(name="", value=f"{ctx.author.mention}, you are already at the **first track** in the history.", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)

        if amount == max(player.queue.getCurrentTrackIndex, player.queue.getCurrentTrackIndex + int(player.queue.hasReachedTheEnd)):    # The author just rolled back to the first track
            embed.add_field(name="", value=f"Rolling back to the **first track**...", inline=False)

        elif amount > player.queue.getCurrentTrackIndex:  # The author tried to rollback more tracks than available in history
            embed.add_field(name="", value=f"The amount of tracks you tried to rollback **exceeded** the **total number of previous tracks** in the history. Automatically **rolling back to the first track** in the history...", inline=False)
            amount = 1 + player.queue.getCurrentTrackIndex  # Set amount to the current position

        else:  # The author is rolling back to a previous track
            embed.add_field(name="", value=f"Rolling back **{amount}** track(s)...", inline=False)

        # Rollback the track(s)
        prev_track = await player.previousTrack(amount)

        # Post check if the previous track is valid
        if not prev_track:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> An unexpected error occurred while trying to rollback the track(s).", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        embed.color = userColor(ctx)
        await ctx.send(embed=embed)


    @commands.hybrid_command(aliases=["pau", "break"])
    async def pause(self, ctx: Context):
        """
        Pauses the current track being played in voice channel

        Parameters
        ----------
        ctx: `Context`
            The context of the command invocation.
        
        Returns
        -------
        None

        """

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)
        embed = Embed(title="")

        if player is None:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I'm not in a voice channel, either or the player is not connected to a node.", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        if len(player.queue.doubleEndedQueue) == 0:  # The player is not playing anything
            embed.add_field(name="", value=f"There is no track currently playing :thinking: ... Perhaps try to play something first, {ctx.author.mention}?", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)
        
        if player.is_paused:
            embed.add_field(name="", value=f"{ctx.author.mention}, the track has been already paused!", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)

        try:
            await player.set_pause(pause=True)

        except Exception as e:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> An unexpected error occurred while trying to pause the track. \n\n {e}", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)
            
        embed.add_field(name="", value="The track has been paused.", inline=False)
        embed.color = userColor(ctx)
        await ctx.send(embed=embed)


    @commands.hybrid_command(aliases=["resu", "continue"])
    async def resume(self, ctx: Context):
        """
        Resumes the current track which is paused in voice channel

        Parameters
        ----------
        ctx: `Context`24 
            The context of the command invocation.
        
        Returns
        -------
        None

        """

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)
        embed = Embed(title="")

        if player is None:
            embed.add_field(name="", value=f"I'm not in a voice channel, either or the player is not connected to a node.", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        if len(player.queue.doubleEndedQueue) == 0:  # The player is not playing anything
            embed.add_field(name="", value=f"There is no track currently playing :thinking: ... Perhaps try to play something first, {ctx.author.mention}?", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)
        
        if not player.is_paused:
            embed.add_field(name="", value=f"{ctx.author.mention}, the track has not been paused.", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)

        try:
            await player.set_pause(pause=False)

        except Exception as e:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> An unexpected error occurred while trying to resume the track. \n\n {e}", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)

        embed.add_field(name="", value="The track has been resumed.", inline=False)
        embed.color = userColor(ctx)
        await ctx.send(embed=embed)

    @commands.hybrid_command(aliases=["now"])
    async def nowplaying(self, ctx: Context) -> None:
        """
        Display the current track being played in voice channel

        Parameters
        ----------
        ctx: `Context`
            The context of the command invocation.


        Returns
        -------
        None


        """

        if ctx.interaction:
            await ctx.interaction.response.defer()

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)
        embed = Embed(title="")

        if player is None:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I'm not in a voice channel, either or the player is not connected to a node.", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        if len(player.queue.doubleEndedQueue) == 0:  # The player is not playing anything
            embed.add_field(name="", value=f"There is no track currently playing :thinking: ... Perhaps try to play something first, {ctx.author.mention}?", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)

        embed, customArtworkFile = await player.nowPlayingEmbed(player.current)  # Get the now playing embed from the player from _player.py
        embed.color = userColor(ctx)

        if customArtworkFile is None:
            return await ctx.send(embed=embed)
        await ctx.send(embed=embed, file=customArtworkFile)


    @commands.hybrid_command(aliases=["rep", "r"])
    async def replay(self, ctx: Context):
        """
        Replay the current track.

        Parameters
        ----------
        ctx: `Context`
            The context of the command invocation.

        Returns
        -------
        None

        """

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)
        embed = Embed(title="")

        if player is None:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I'm not in a voice channel, either or the player is not connected to a node.", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        if len(player.queue.doubleEndedQueue) == 0:  # The player is not playing anything
            embed.add_field(name="", value=f"There is no track currently playing :thinking: ... Perhaps try to play something first, {ctx.author.mention}?", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)
        
        # Replay the track
        try:
            await player.seek(0)

        except Exception as e:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> An error occurred while trying to replay the track. \n\n {e}", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        embed.add_field(name="", value=f"Replaying the current track...", inline=False)
        embed.color = userColor(ctx)
        await ctx.send(embed=embed)


    @commands.hybrid_group(name="repeat", help="Toggle repeat for the current track or the entire queue.")
    async def repeat(self, ctx: Context):
        # This is the main command group for repeat
        # We won't implement any logic here, as the subcommands will handle the functionality
        # If no subcommand is invoked, return an error message
        embed = Embed(title="")
        embed.add_field(name="", value=f"{ctx.author.mention}, you need to specify a subcommand: `one` or `all`.", inline=False)
        embed.color = Color.red()
        await ctx.send(embed=embed)
    

    @repeat.command()
    async def one(self, ctx: Context):
        """
        Toggle repeat for the current track.

        Parameters
        ----------
        ctx: `Context`
            The context of the command invocation.

        Returns
        -------
        None

        """
        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)
        embed = Embed(title="")

        if player is None:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I'm not in a voice channel, either or the player is not connected to a node.", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        if len(player.queue.doubleEndedQueue) == 0:  # The player is not playing anything
            embed.add_field(name="", value=f"There is no track currently playing :thinking: ... Perhaps try to play something first, {ctx.author.mention}?", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)
                
        if player.queue.loop_mode == LoopMode.TRACK:
            embed.add_field(name="", value=f"Disabling repeat for the current track...", inline=False)

            try:
                player.queue.disable_loop()

            except QueueException as e:
                embed.add_field(name="", value=f"The repeat mode is **already disabled** for the current track. \n\n {e}", inline=False)
                embed.color = userColor(ctx)    # Friendly reminder, so the color won't be red
                return await ctx.send(embed=embed)
            
            except Exception as e:
                embed.add_field(name="", value=f"<a:crossred:1356353067024515266> An error occurred while trying to disable repeat for the current track. \n\n {e}", inline=False)
                embed.color = Color.red()
                return await ctx.send(embed=embed)
            
        else:
            embed.add_field(name="", value=f"Repeating the current track...", inline=False)
            player.queue.set_loop_mode(LoopMode.TRACK)

        embed.color = userColor(ctx)
        await ctx.send(embed=embed)


    @repeat.command()
    async def all(self, ctx: Context):
        """
        Toggle repeat for the entire queue.

        Parameters
        ----------
        ctx: `Context`
            The context of the command invocation.

        Returns
        -------
        None

        """

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)
        embed = Embed(title="")

        if player is None:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I'm not in a voice channel, either or the player is not connected to a node.", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        if len(player.queue.doubleEndedQueue) == 0:  # The player is not playing anything
            embed.add_field(name="", value=f"There is no track currently playing :thinking: ... Perhaps try to play something first, {ctx.author.mention}?", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)
        
        if player.queue.loop_mode == LoopMode.QUEUE:
            embed.add_field(name="", value=f"Disabling repeat for the entire queue...", inline=False)

            try:
                player.queue.disable_loop()

            except QueueException as e:
                embed.add_field(name="", value=f"The repeat mode is **already disabled** for the entire queue. \n\n {e}", inline=False)
                embed.color = userColor(ctx)    # Friendly reminder, so the color won't be red
                return await ctx.send(embed=embed)
            
            except Exception as e:
                embed.add_field(name="", value=f"<a:crossred:1356353067024515266> An error occurred while trying to disable repeat for the entire queue. \n\n {e}", inline=False)
                embed.color = Color.red()
                return await ctx.send(embed=embed)

        else:
            embed.add_field(name="", value=f"Repeating the entire queue...", inline=False)
            player.queue.set_loop_mode(LoopMode.QUEUE)

        embed.color = userColor(ctx)
        await ctx.send(embed=embed)


    @commands.hybrid_command(aliases=["halt", "st"])
    async def stop(self, ctx: Context):
        """
        Stops the current track being played in voice channel and clears the queue.

        Parameters
        ----------
        ctx: `Context`
            The context of the command invocation.

        Returns
        -------
        None

        """

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)
        embed = Embed(title="")

        if player is None:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I'm not in a voice channel, either or the player is not connected to a node.", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)

        if len(player.queue.doubleEndedQueue) == 0:  # The player is not playing anything
            embed.add_field(name="", value=f"There is no track currently playing :thinking: ... Perhaps try to play something first, {ctx.author.mention}?", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)

        try:
            if player.queue.is_looping:
                player.queue.disable_loop()  # Disable looping if it's enabled
            player.queue.clear()  # Clear the queue
            await player.stop()   # Stop the current track
            
            # The controller will not be updated automatically after stopping the track, so we do it manually
            player.updateController.start()

        except Exception as e:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> An error occurred while trying to stop the track. \n\n {e}", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)
        
        embed.add_field(name="", value="Stopped the current track and cleared the queue.", inline=False)
        embed.color = userColor(ctx)
        await ctx.send(embed=embed)


    @commands.hybrid_command(aliases=["vol", "v"])
    async def volume(self, ctx: Context, *, value: Optional[app_commands.Range[int, 0, 500]] = 60) -> None:
        """
        Change the volume of the music player

        Parameters
        ----------
        ctx: `Context`
            The context of the command invocation.

        value: Optional`[int]` = 30
            The new volume to set. Leave this blank if you want to set it as default.
        
        Returns
        -------
        None

        """

        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)
        embed = Embed(title="")

        if player is None:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I'm not in a voice channel, either or the player is not connected to a node.", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)

        if len(player.queue.doubleEndedQueue) == 0:  # The player is not playing anything
            embed.add_field(name="", value=f"There is no track currently playing :thinking: ... Perhaps try to play something first, {ctx.author.mention}?", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)

        if value < 0 or value > 500:  # Invalid volume
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> The volume must be between **0** and **500** :thinking: ...\n Generally, **60** is already good enough, **100** is considered as very loud, and **200** will blow your eardrums out lol.", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)

        # Set the volume
        try:
            await player.set_volume(value)

        except Exception as e:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> An error occurred while trying to change the volume. \n\n {e}", inline=False)
            return await ctx.send(embed=embed)
        
        embed.add_field(name="", value=f"Changed volume to **{value}%**", inline=False)
        embed.color = userColor(ctx)
        await ctx.send(embed=embed)


    @commands.hybrid_command(aliases=["nig"])
    async def nightcore(self, ctx: Context):
        """
        Toggle nightcore mode on the player.

        Parameters
        ----------
        ctx: `Context`
            The context of the command invocation.

        Returns
        -------
        None

        """

        # Set the filter to a nightcore style. We have to use pomice.Timescale to adjust the pitch and speed.
        player: BetterPlayer = cast(BetterPlayer, ctx.voice_client)
        embed = Embed(title="")
        
        if player is None:
            embed.add_field(name="", value=f"<a:crossred:1356353067024515266> I'm not in a voice channel, either or the player is not connected to a node.", inline=False)
            embed.color = Color.red()
            return await ctx.send(embed=embed)

        if len(player.queue.doubleEndedQueue) == 0:  # The player is not playing anything
            embed.add_field(name="", value=f"There is no track currently playing :thinking: ... Perhaps try to play something first, {ctx.author.mention}?", inline=False)
            embed.color = userColor(ctx)   # Friendly reminder, so the color won't be red
            return await ctx.send(embed=embed)

        if player.filters.empty:
            await player.add_filter(Timescale.nightcore(), fast_apply=True)
            embed.add_field(name="", value=f"**Activating** nightcore mode...", inline=False)
        
        else:
            await player.reset_filters(fast_apply=True)
            embed.add_field(name="", value=f"**Deactivating** nightcore mode... The track may be briefly interrupted.", inline=False)
        
        embed.color = userColor(ctx)
        await ctx.send(embed=embed)

