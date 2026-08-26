import logging
import asyncio
from bot.extensions.MusicPlayer._betterQueue import BetterQueue
from bot.extensions.MusicPlayer._audioMetadataExtractor import *
from contextlib import suppress
from datetime import timedelta
from typing import Optional
from lava_lyra import LoopMode, Player, QueueEmpty, Track, TrackType
from discord import Color, Embed, Message, HTTPException
from discord.ext import tasks
from discord.ext.commands import Context

logger = logging.getLogger(__name__)

# Customized Player class to handle queue and history (i.e. with a modifiable queue system and previous track support)

class BetterPlayer(Player):
    """
    A custom player class that extends `lava_lyra.Player` to include advanced queue management and history tracking.

    Attributes
    ----------
    queue : BetterQueue
        The playback queue, i.e. an instance of `BetterQueue` that supports advanced queue operations
    _isRollingBack : bool
        A flag to indicate if a rollback operation is in progress, used to prevent auto-skipping
    controller : Message
        The message containing the playback controls (if any), used to update the controller message with current track information
    context : Context
        The `discord.py` command context, for sending messages later (e.g., embeds for now playing)

    Methods
    -------
    setContext(ctx)
        Store the command context on the player for later use (e.g., sending embeds).
    isFinalTrack()
        Check if the current track is the final track in the queue.
    nowPlayingEmbed(track=None)
        Create an embed for the currently playing track, including metadata if available.
    previousTrack(amount=1)
        Move backward in the queue by the specified amount, returning the track being played after moving backward
    nextTrack()
        Move forward in the queue by the next track, returning the track being played after moving forward
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue: BetterQueue = BetterQueue()    # The playback queue
        self._isRollingBack: bool = False    # Flag to indicate if a rollback operation is in progress
        self.controller: Message = None   # The message containing the playback controls (if any)
        self.context: Context = None    # The command context, for sending messages later


    def setContext(self, ctx: Context) -> None:
        """
        Store the command context on the player for later use (e.g., sending embeds).
        
        Parameters
        ----------
        ctx : Context
            The command context to store.
        
        Returns
        -------
        None
        """

        self.context = ctx        


    @property
    def isFinalTrack(self) -> bool:
        """
        Check if the current track is the final track in the queue.

        Returns
        -------
        bool
        """

        history = self.queue._playbackHistory
        _currentIndex = self.queue._currentIndex

        return (
            bool(history)
            and _currentIndex is not None
            and _currentIndex >= len(history) - 1
        )

    # Create an embed for the currently playing track
    async def nowPlayingEmbed(self, track: Optional[Track] = None) -> tuple[Embed, object | None]:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Create an embed for the currently playing track.

        Detailed metadata about the track would be provided if available.

        Parameters
        ----------
        track: Optional[lava_lyra.Track]
            The track that is currently playing. Leave it empty if no track is playing.

        Returns
        -------
        tuple[Embed, object | None]:
            A tuple containing a Discord embed with information about the currently playing track, and the custom artwork file (if any).

        Examples
        --------
        ```python
        # Example usage in a command, you should call this with unpacked values in order to avoid errors
        embed, customArtworkFile = await player.nowPlayingEmbed(player.current)
        
        if customArtworkFile is not None:
            # Send both embed and custom artwork file if available
            await ctx.send(embed=embed, file=customArtworkFile)

        else:
            # Otherwise just send the embed
            await ctx.send(embed=embed)
        ```

        Notes
        -----
        This function has been heavily modified since the second rewrite and it returns a tuple now, please be aware of that if you are calling it somewhere else to avoid potential issues.
        """

        embed = Embed(
            title="Now playing",
            color=self.context.author.color if self.context else Color.blurple()    # Defaults to user color. Use blurple in case self.context has not been set
        )
        
        # Display the track requester, if any
        if track and track.requester:
            embed.set_author(name=f"{track.requester.display_name}", icon_url=track.requester.display_avatar.url)

        customArtworkFile = None    # If the track was from default sources this could be None

        if track is None:
            embed.add_field(name="", value="No tracks were playing in the voice channel.", inline=False)
            return embed, customArtworkFile

        # We attempt to extract its metadata, if the track is not from default sources (i.e. YouTube, SoundCloud, Spotify, Apple Music) that provided metadata already
        if not track.track_type in {
            TrackType.YOUTUBE,
            TrackType.SOUNDCLOUD,
            TrackType.SPOTIFY,
            TrackType.APPLE_MUSIC
        }:
            audioMetadata = AudioMetadataExtractor(track.uri, stream=True)
            embed.description = f"[{audioMetadata.title or track.title}]({track.uri})"

            # Add a special source handling for some common links
            if "plex" in track.uri:
                # The track is from Plex Media Server
                embed.add_field(name="Source:", value="Plex Media Server", inline=False)
                embed.set_thumbnail(url="https://avatars.githubusercontent.com/u/324832")  # Plex logo

            elif "cdn.discordapp.com" in track.uri:
                # The track is from Discord CDN (i.e. uploaded file)
                embed.add_field(name="Source:", value="Discord Upload", inline=False)

            else:
                # Generic source handling
                embed.add_field(name="Source:", value=track.track_type.name.title(), inline=False)

            # Retrieves the metadata if available
            # We only display fields that are not None or empty to avoid exceeding Discord's embed field limits (25 fields)
            if audioMetadata and audioMetadata.artist:
                embed.add_field(name="Artist:", value=audioMetadata.artist, inline=False)

            if audioMetadata and audioMetadata.album:
                embed.add_field(name="Album:", value=audioMetadata.album, inline=False)

            if audioMetadata and audioMetadata.duration:
                embed.add_field(name="Duration:", value=audioMetadata.duration, inline=False)
            
            if audioMetadata and audioMetadata.genre:
                embed.add_field(name="Genre:", value=audioMetadata.genre, inline=False)

            if audioMetadata and audioMetadata.trackNumber:
                embed.add_field(name="Track Number:", value=audioMetadata.trackNumber, inline=False)

            if audioMetadata and audioMetadata.trackTotal:
                embed.add_field(name="Total Tracks:", value=audioMetadata.trackTotal, inline=False)

            if audioMetadata and audioMetadata.discNumber:
                embed.add_field(name="Disc Number:", value=audioMetadata.discNumber, inline=False)

            if audioMetadata.samplingRate:
                embed.add_field(name="Sampling Rate:", value=f"{audioMetadata.samplingRate} Hz", inline=False)

            if audioMetadata and audioMetadata.bitDepth:
                embed.add_field(name="Bit Depth:", value=f"{audioMetadata.bitDepth}-bit", inline=False)

            if audioMetadata and audioMetadata.bitRate:
                # This is the streaming bitrate, not the original file bitrate
                embed.add_field(name="Streaming Bitrate:", value=f"{audioMetadata.bitRate} kbps", inline=False)

            if audioMetadata and audioMetadata.channels:
                embed.add_field(name="Channels:", value=f"{audioMetadata.channels} ch.", inline=False)

            if audioMetadata and audioMetadata.year:
                embed.add_field(name="Year:", value=audioMetadata.year, inline=False)

            if audioMetadata and audioMetadata.releaseDate:
                embed.add_field(name="Release Date:", value=audioMetadata.releaseDate, inline=False)

            if audioMetadata and audioMetadata.label:
                embed.add_field(name="Label:", value=audioMetadata.label, inline=False)

            if audioMetadata and audioMetadata.publisher:
                embed.add_field(name="Publisher:", value=audioMetadata.publisher, inline=False)

            if audioMetadata and audioMetadata.copyright:
                embed.set_footer(text=f"{audioMetadata.copyright}")

            if audioMetadata and audioMetadata.coverArt:
                customArtworkFile = toDiscordFile(audioMetadata.coverArt)
                embed.set_image(url=f"attachment://{customArtworkFile.filename}")

        else:
            # Default sources, just let the player to handle it
            embed.description = f"{'**:red_circle: LIVE**' if track.is_stream else ''} [{track.title}]({track.uri})"
            
            if track.thumbnail:
                embed.set_image(url=track.thumbnail)

            if track.author:
                embed.add_field(name="Autor/Artist:", value=track.author, inline=False)

            if track.length and not track.is_stream:
                try:
                    embed.add_field(name="Duration:", value=f"{timedelta(milliseconds=track.length)}", inline=False)

                except OverflowError:
                    # Duration too long to represent
                    pass

        # Display loop status, if applicable
        # This will be displayed no matter if the track is from default sources or not
        # We add an empty field to create a visual separation if both loop modes are enabled
        if self.queue.is_looping:
            embed.add_field(name="", value="\u202a", inline=False)

        if self.queue.loop_mode == LoopMode.TRACK:
            # Single track loop
            embed.add_field(name="Repeat:", value="**Enabled** for the current track", inline=False)

        if self.queue.loop_mode == LoopMode.QUEUE:
            # Entire queue loop
            embed.add_field(name="Repeat:", value="**Enabled** for the entire queue", inline=False)

        embed.color = track.requester.color
        return embed, customArtworkFile


    # Lavalink client does not have a previous track function, so we implement our own.
    # This will go back to the previous track in the queue, if there is one.
    # Please note that fast trigger on commands might causing the player to have unintended behaviors, so use them gently :)
    # If the player is stopped (current is None), it will allow stepping "into" the last played track first.
    async def previousTrack(self, amount: int = 1) -> Optional[Track] | None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Moves backward in the queue by the specified amount.

        If the beginning of the queue is reached, playback is stopped.

        Parameters
        ----------
        amount : int
            The number of tracks to move backward in the queue. Default is 1.

        Returns
        ------- 
        None
            Returns if the function is called while a backward process is ongoing, or the history was not found.

        Optional[lava_lyra.Track]
            The track being played after moving backward, if successful.
        """

        # Quick guards
        if not getattr(self.queue, "_playbackHistory", None):
            return

        if self._isRollingBack:
            return
        
        # Calculate the target index to move back to, ensure it clamps to 0
        targetIndex = max(self.queue.currentTrackIndex - (amount - 1 if self.queue.isAtHistoryEnd else amount), 0) 

        # Reset the end-of-queue flag to allow normal playback operations
        self.queue.isAtHistoryEnd = False

        # Replace the current queue with the remaining tracks after the target index
        prevTrack = self.queue._playbackHistory[targetIndex]
        self.queue._queue = self.queue._playbackHistory[targetIndex + 1:]

        # Set rollback flag to prevent on_track_end from auto-skipping
        self._isRollingBack = True

        await self.play(prevTrack)
        self.queue._currentIndex = targetIndex

        # Reset the pause flag to allow normal playback operations, just in case
        await self.set_pause(False)

        # Update controller message if applicable
        if not self.updateController.is_running():
            self.updateController.start()

        # Reset the rollback flag after a short delay to allow normal playback operations
        if not self.rollbackFlagInitialize.is_running():
            self.rollbackFlagInitialize.start()

        # Return the track being played
        return prevTrack


    async def nextTrack(self) -> Optional[Track] | bool | None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Moves forward in the queue by the next track.

        If the end of the queue is reached, playback will be stopped, unlike the old logic which overflowed.

        `self._isEnded` will be `True` and `self.queue._currentIndex` will be the latest added track inside `self.queue._playbackHistory` in this case before returning.

        Returns
        -------
        Optional[lava_lyra.Track]
            The track being played after moving forward, if successful.
        bool: True
            Returns `True` to notify the caller if we already at the end of the queue.
        None
            Returns if the queue (both `self._queue` and `self.queue._playbackHistory`) was completely empty. This is a very rare scenario, probably due to some uncaught errors.
        """

        # Reset the end-of-queue flag to allow normal playback operations
        self.queue.isAtHistoryEnd = False

        # Get the next track from the queue, if any

        try:
            nextTrack: Track = self.queue.get()
        except QueueEmpty:
            if len(self.queue._playbackHistory) == 0:
                # Queue is completely empty, nothing to play.
                # This is a very rare, nearly impossible scenario, probably due to some uncaught errors.
                return

            # Otherwise, this could generally mean that we are at the end of the queue
            # Stop playback and set the isEnded flag
            self.queue.isAtHistoryEnd = True
        
            # Reset _currentIndex to the end of the queue to prevent overflow
            self.queue._currentIndex = len(self.queue._playbackHistory) - 1

            # Update controller message if applicable
            if not self.updateController.is_running():
                self.updateController.start()
            
            # Done
            # This is just a trick to notify the caller that the command was completed successfully
            return True

        # Play the target track
        await self.play(nextTrack, ignore_if_playing=False)

        # Reset the pause flag to allow normal playback operations, just in case
        await self.set_pause(False)

        # Update controller message if applicable
        if not self.updateController.is_running():
            self.updateController.start()

        # Return the track being played
        return nextTrack
 

    # Update the controller message with the current track information
    @tasks.loop(count=1)
    async def updateController(self):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Updates the playback controller message with the current track information.

        This generally solves the issue of multiple rapid command calls causing multiple controller messages to be sent.

        Returns
        -------
        None
        """

        try:
            with suppress(HTTPException):
                if self.controller:
                    await self.controller.delete()
                    self.controller = None
            embed, customArtworkFile = await self.nowPlayingEmbed(self.current)
            if customArtworkFile is not None:
                self.controller = await self.context.send(embed=embed, silent=True, file=customArtworkFile) if (self.context and not self.controller) else None
            else:
                self.controller = await self.context.send(embed=embed, silent=True) if (self.context and not self.controller) else None
            await asyncio.sleep(0.5)  # Small delay to ensure message is sent before next update

        finally:
            self.updateController.cancel()


    # Reset the rollback and forward flags after a short delay
    # This is to prevent the previous track command from interfering with normal playback operations
    @tasks.loop(count=1)
    async def rollbackFlagInitialize(self):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Resets the `_rollback` flags after a short delay to allow normal playback operations to resume.

        This is used to prevent the `on_track_end` event from automatically skipping to the next track when performing rollback or forward commands.

        Returns
        -------
        None
        """

        await asyncio.sleep(0.5)
        self._isRollingBack = False
        self.rollbackFlagInitialize.cancel()
