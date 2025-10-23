import logging
import asyncio
from copy import copy
from extensions.MusicPlayer._audioMetadataExtractor import *
from contextlib import suppress
from datetime import timedelta
from typing import List, Optional, Iterable
from pomice import LoopMode, Player, Queue, QueueEmpty, Track, TrackType
from discord import Color, Embed, Message, HTTPException
from discord.ext import tasks
from discord.ext.commands import Context

logger = logging.getLogger("music_v2")

# Queue class that combines list operations with pomice.Queue functionality
# A good demonstration of multiple inheritance usage in python
# This allows us to use list operations (like indexing, slicing, etc.) while still having the queue behavior of pomice.Queue

class BetterQueue(Queue):
    """
    A custom queue class that extends `pomice.Queue` to include advanced queue management and history tracking.

    This allows us to maintain a full history of tracks played, indexing and slicing.

    Attributes
    ----------
    doubleEndedQueue : `List[pomice.Track]`
        A double-ended queue that maintains the full history of tracks played.
    
    currentIndex : `Optional[int]`
        The index of the current track in `doubleEndedQueue`. None means not initialized (before-first).

    Methods
    -------

    get() -> `pomice.Track`
        Retrieves the next track from the queue and updates `currentIndex` accordingly.

    copy() -> `BetterQueue`
        Creates a copy of the current queue including all its members.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doubleEndedQueue: List[Track] = []    # Full list of tracks including played ones (history-like; we never remove from this)
        self.currentIndex: Optional[int] = None    # Position in the queue, None means before-first
        self._qEnd: bool = False    # To track if the queue has reached the end



    def __getitem__(self, key):  # type: ignore[override]
        if isinstance(key, slice):
            return self._queue[key]  # returns List[pomice.Track]
        return super().__getitem__(key)


    # Record successful enqueues into doubleEndedQueue
    def put(self, item: Track) -> None:  # type: ignore[override]
        super().put(item)
        self.doubleEndedQueue.append(item)


    def extend(self, iterable: Iterable[Track], *, atomic: bool = True) -> None:  # type: ignore[override]
        # super().extend will call self.put per item, which already appends to doubleEndedQueue
        super().extend(iterable, atomic=atomic)


    def put_at_index(self, index: int, item: Track) -> None:  # type: ignore[override]
        super().put_at_index(index, item)
        # Keep history with positional intent: insert at that index
        self.doubleEndedQueue.insert(index, item)
        # If inserted before or at the current item, bump the pointer to keep pointing at the same item
        if self.currentIndex >= 0 and index <= self.currentIndex:
            self.currentIndex += 1


    def put_at_front(self, item: Track) -> None:  # type: ignore[override]
        super().put_at_front(item)
        self.doubleEndedQueue.insert(0, item)
        if self.currentIndex >= 0:
            self.currentIndex += 1


    def get(self) -> Track:  # type: ignore[override]
        """
        Return next immediately available item in queue if any.

        This also updates `currentIndex` to point to the returned item in `doubleEndedQueue`.

        If there exists any duplicated tracks in the queue, `currentIndex` will point to the first occurrence after the previous `currentIndex`.

        `doubleEndedQueue` will not be modified after `Queue.pop()`, so the full history will be preserved.

        However, if the queue is empty, this will raise `pomice.QueueEmpty` as usual.

        Returns
        ----------
        pomice.Track
            The next track in the queue.

        Raises 
        ----------
        pomice.QueueEmpty
            Raised if no items in queue.

        """

        item = super().get()

        #
        # Overrides the default behavior of pomice.Queue.get() to update currentIndex
        #
        
        originalIndex = self.currentIndex if self.currentIndex is not None else 0

        try:
            self.currentIndex = self.doubleEndedQueue.index(item, originalIndex)

        except ValueError as e:
            # This should never happen, but just in case
            raise e

        # If the item was found before originalIndex
        if originalIndex > self.currentIndex:
            try:
                # Checking if any duplicates exist after originalIndex
                self.currentIndex = self.doubleEndedQueue.index(item, originalIndex + 1)

            except ValueError:
                # Don't worry, this just means no duplicates found after originalIndex, not an error
                pass

        return item


    def copy(self) -> "BetterQueue":  # type: ignore[override]
        """
        Create a copy of the current queue including all it's members.

        Same as `pomice.Queue.copy()` but also maintains the state of `doubleEndedQueue` and `currentIndex`.
        
        Returns
        -------
        BetterQueue
            A new instance of `BetterQueue` with the same contents and state as the original.

        """

        # Preserve constructor options (max_size, overflow)
        newQueue: BetterQueue = self.__class__(max_size=self.max_size, overflow=self._overflow)  # type: ignore[arg-type]

        # Copy runtime queue contents (shallow)
        newQueue._queue = copy(self._queue)

        # Copy BetterQueue extras
        newQueue.doubleEndedQueue = copy(self.doubleEndedQueue)
        newQueue.currentIndex = copy(self.currentIndex)

        return newQueue


    def remove(self, item):
        """
        Remove the first occurrence of item.
        
        This also removes the item from `doubleEndedQueue`.

        Parameters
        ----------
        item : pomice.Track
            The track to remove from the queue.
        
        Returns
        -------
        None

        """
    
        super().remove(item)
        self.doubleEndedQueue.remove(item)


    def clear(self) -> None:
        """
        Remove all items from the queue.

        This also resets our `doubleEndedQueue` and resets `currentIndex` to None (before-first).

        Returns
        -------
        None

        """

        super().clear()
        self.doubleEndedQueue.clear()
        self.currentIndex = None  # Reset to before-first


    @property
    def getCurrentTrackIndex(self) -> int | None:
        """
        Returns current track index.

        Similar to `Queue.find_position()` but works with our `doubleEndedQueue` and `currentIndex`.

        It is highly recommended to use this property instead of `Queue.find_position()` as the latter
        
        does not account for tracks that have already been played and removed from the queue.

        Returns
        -------
        int
            Returns if `currentIndex` is a valid non-negative integer.

        None
            The `currentIndex` has not been initialized (before-first).

        """

        return self.currentIndex if self.currentIndex is not None and self.currentIndex >= 0 else None
    

    @property
    def hasReachedTheEnd(self) -> bool:
        """
        Check if the queue has reached the end.

        This is useful for determining if playback has finished all tracks in the queue.

        Returns
        -------
        bool
            `True` if the queue has reached the end, `False` otherwise.

        """

        return bool(self._qEnd)
    
    @hasReachedTheEnd.setter
    def hasReachedTheEnd(self, value: bool) -> None:
        """
        Set the end-of-queue status.

        This can be used to manually set the end-of-queue status, which might be useful in certain scenarios.

        Parameters
        ----------
        value : bool
            The new end-of-queue status.

        Returns
        -------
        None

        """

        self._qEnd = value

    @property
    def hasReachedTheBeginning(self) -> bool:
        """
        Check if the queue has reached the beginning.

        Examaining only `currentIndex` is not sufficient, as sometimes the player has a single track only, and `currentIndex` will still be 0 even after the track has been played.
        
        This will be `True` if `currentIndex` is 0 and the queue has not reached the end.

        Returns
        -------
        bool
            `True` if the queue has reached the beginning, `False` otherwise.

        """

        return (self.currentIndex == 0 and self._qEnd is False)

# Customized Player class to handle queue and history (i.e. with a modifiable queue system and previous track support)
# Huge thanks to GPT-5 for the original implementation idea lol
# and to cloudwithax for pomice and help with the API


class BetterPlayer(Player):
    """
    A custom player class that extends `pomice.Player` to include advanced queue management and history tracking.
    
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

        return self.queue.currentIndex == (len(self.queue.doubleEndedQueue) - 1) if self.queue.currentIndex is not None else False


    # Create an embed for the currently playing track
    # UPDATE 17-10-2025: This function has been heavily modified and it returns a tuple now, see the Notes section below
    async def nowPlayingEmbed(self, track: Optional[Track] = None) -> tuple[Embed, object | None]:
        """
        Create an embed for the currently playing track.

        Updates the embed with detailed information about the track, including metadata if available.

        Parameters
        ----------
        track: Optional`[pomice.Track]`
            The track that is currently playing. Leave it empty if no track is playing.

        Returns
        ----------
        tuple[Embed, object | None]:
            A tuple containing a Discord embed with information about the currently playing track, and the custom artwork file (if any).

        Examples
        ----------
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
        ----------
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

        # We attempt to extract its metadata, if the track is not from YouTube, SoundCloud, or Spotify etc.
        if not track.track_type in {TrackType.YOUTUBE, TrackType.SOUNDCLOUD, TrackType.SPOTIFY}:
            audioMetadata = AudioMetadataExtractor(track.uri, stream=True)
            embed.description = f"[{audioMetadata.title or track.title}]({track.uri})"

            # Add a special source handling for some common links
            if "plex.direct" in track.uri or "plex.tv" in track.uri:
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
    # Please note that fast trigger on commands might causing the player to have unintended behavior, so use them gently :)
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
            Returns if the function is called while a backward process is ongoing.

        Optional`[pomice.Track]`
            The track being played after moving backward, if successful.

        """

        # Quick guards
        if not getattr(self.queue, "doubleEndedQueue", None):
            return None

        if self._isRollingBack:
            return None
        
        # Calculate the target index to move back to, ensure it clamps to 0
        targetIndex = max(self.queue.getCurrentTrackIndex - (amount - 1 if self.queue.hasReachedTheEnd else amount), 0) 

        # Reset the end-of-queue flag to allow normal playback operations
        self.queue.hasReachedTheEnd = False

        # Replace the current queue with the remaining tracks after the target index
        prevTrack = self.queue.doubleEndedQueue[targetIndex]
        self.queue._queue = self.queue.doubleEndedQueue[targetIndex + 1:]

        # Set rollback flag to prevent on_track_end from auto-skipping
        self._isRollingBack = True

        if self.is_playing:
            # Forcefully reset current playing status to allow playback of another track without triggering on_track_end
            await self.set_pause(True)
            self._current = None
            await self.set_pause(False)

        await self.play(prevTrack)
        self.queue.currentIndex = targetIndex

        # Update controller message if applicable
        if not self.updateController.is_running():
            self.updateController.start()

        # Reset the rollback flag after a short delay to allow normal playback operations
        if not self.rollbackFlagInitialize.is_running():
            self.rollbackFlagInitialize.start()

        # Return the track being played
        return prevTrack


    async def nextTrack(self) -> Optional[Track] | None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Moves forward in the queue by the next track.

        If the end of the queue is reached, playback will be stopped, unlike the old logic which overflowed.

        `self._isEnded` will be `True` and `self.queue.currentIndex` will be the latest added track inside `self.queue.doubleEndedQueue` in this case before returning.

        Returns
        -------
        Optional`[pomice.Track]`
            The track being played after moving forward, if successful.

        bool: True
            Returns `True` to notify the caller if we already at the end of the queue.

        None
            Returns if the queue (both `self._queue` and `self.queue.doubleEndedQueue`) was completely empty. This is a very rare scenario, probably due to some uncaught errors.

        """

        # Reset the end-of-queue flag to allow normal playback operations
        self.queue.hasReachedTheEnd = False

        # Get the next track from the queue, if any
        try:
            nextTrack: Track = self.queue.get()
        except QueueEmpty:
            if len(self.queue.doubleEndedQueue) == 0:
                # Queue is completely empty, nothing to play.
                # This is a very rare, nearly impossible scenario, probably due to some uncaught errors.
                return
            
            # Otherwise, this could generally mean that we are at the end of the queue
            # Stop playback and set the isEnded flag
            self.queue.hasReachedTheEnd = True

            # Reset currentIndex to the end of the queue to prevent overflow
            self.queue.currentIndex = len(self.queue.doubleEndedQueue) - 1

            # Update controller message if applicable
            if not self.updateController.is_running():
                self.updateController.start()
            
            # Done
            # This is just a trick to notify the caller that the command was completed successfully
            return True

        # Play the target track
        await self.play(nextTrack, ignore_if_playing=False)

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

