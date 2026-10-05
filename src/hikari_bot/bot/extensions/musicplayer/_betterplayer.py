"""
The MIT License (MIT)

Copyright (c) 2025 Hoshino Yuki

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

import logging
import asyncio
from hikari_bot.bot.extensions.musicplayer._betterqueue import BetterQueue
from hikari_bot.bot.extensions.musicplayer._audiometadataextractor import *
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
    _is_rolling_back : bool
        A flag to indicate if a rollback operation is in progress, used to prevent auto-skipping
    controller : Message
        The message containing the playback controls (if any), used to update the controller message with current track information
    context : Context
        The `discord.py` command context, for sending messages later (e.g., embeds for now playing)

    Methods
    -------
    set_context(ctx)
        Store the command context on the player for later use (e.g., sending embeds).
    is_final_track()
        Check if the current track is the final track in the queue.
    now_playing_embed(track=None)
        Create an embed for the currently playing track, including metadata if available.
    previous_track(amount=1)
        Move backward in the queue by the specified amount, returning the track being played after moving backward
    next_track()
        Move forward in the queue by the next track, returning the track being played after moving forward
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue: BetterQueue = BetterQueue()    # The playback queue
        self._is_rolling_back: bool = False    # Flag to indicate if a rollback operation is in progress
        self.controller: Message = None   # The message containing the playback controls (if any)
        self.context: Context = None    # The command context, for sending messages later


    def set_context(self, ctx: Context) -> None:
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
    def is_final_track(self) -> bool:
        """
        Check if the current track is the final track in the queue.

        Returns
        -------
        bool
        """

        history = self.queue._playback_history
        _current_index = self.queue._current_index

        return (
            bool(history)
            and _current_index is not None
            and _current_index >= len(history) - 1
        )

    # Create an embed for the currently playing track
    async def now_playing_embed(self, track: Optional[Track] = None) -> tuple[Embed, object | None]:
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
        embed, custom_artwork_file = await player.now_playing_embed(player.current)
        
        if custom_artwork_file is not None:
            # Send both embed and custom artwork file if available
            await ctx.send(embed=embed, file=custom_artwork_file)

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

        custom_artwork_file = None    # If the track was from default sources this could be None

        if track is None:
            embed.add_field(name="", value="No tracks were playing in the voice channel.", inline=False)
            return embed, custom_artwork_file

        # We attempt to extract its metadata, if the track is not from default sources (i.e. YouTube, SoundCloud, Spotify, Apple Music) that provided metadata already
        if not track.track_type in {
            TrackType.YOUTUBE,
            TrackType.SOUNDCLOUD,
            TrackType.SPOTIFY,
            TrackType.APPLE_MUSIC
        }:
            audio_metadata = AudioMetadataExtractor(track.uri, stream=True)
            embed.description = f"[{audio_metadata.title or track.title}]({track.uri})"

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
            if audio_metadata and audio_metadata.artist:
                embed.add_field(name="Artist:", value=audio_metadata.artist, inline=False)

            if audio_metadata and audio_metadata.album:
                embed.add_field(name="Album:", value=audio_metadata.album, inline=False)

            if audio_metadata and audio_metadata.duration:
                embed.add_field(name="Duration:", value=audio_metadata.duration, inline=False)
            
            if audio_metadata and audio_metadata.genre:
                embed.add_field(name="Genre:", value=audio_metadata.genre, inline=False)

            if audio_metadata and audio_metadata.track_number:
                embed.add_field(name="Track Number:", value=audio_metadata.track_number, inline=False)

            if audio_metadata and audio_metadata.track_total:
                embed.add_field(name="Total Tracks:", value=audio_metadata.track_total, inline=False)

            if audio_metadata and audio_metadata.disc_number:
                embed.add_field(name="Disc Number:", value=audio_metadata.disc_number, inline=False)

            if audio_metadata.sampling_rate:
                embed.add_field(name="Sampling Rate:", value=f"{audio_metadata.sampling_rate} Hz", inline=False)

            if audio_metadata and audio_metadata.bit_depth:
                embed.add_field(name="Bit Depth:", value=f"{audio_metadata.bit_depth}-bit", inline=False)

            if audio_metadata and audio_metadata.bit_rate:
                # This is the streaming bitrate, not the original file bitrate
                embed.add_field(name="Streaming Bitrate:", value=f"{audio_metadata.bit_rate} kbps", inline=False)

            if audio_metadata and audio_metadata.channels:
                embed.add_field(name="Channels:", value=f"{audio_metadata.channels} ch.", inline=False)

            if audio_metadata and audio_metadata.year:
                embed.add_field(name="Year:", value=audio_metadata.year, inline=False)

            if audio_metadata and audio_metadata.release_date:
                embed.add_field(name="Release Date:", value=audio_metadata.release_date, inline=False)

            if audio_metadata and audio_metadata.label:
                embed.add_field(name="Label:", value=audio_metadata.label, inline=False)

            if audio_metadata and audio_metadata.publisher:
                embed.add_field(name="Publisher:", value=audio_metadata.publisher, inline=False)

            if audio_metadata and audio_metadata.copyright:
                embed.set_footer(text=f"{audio_metadata.copyright}")

            if audio_metadata and audio_metadata.cover_art:
                custom_artwork_file = to_discord_file(audio_metadata.cover_art)
                embed.set_image(url=f"attachment://{custom_artwork_file.filename}")

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
        return embed, custom_artwork_file


    # Lavalink client does not have a previous track function, so we implement our own.
    # This will go back to the previous track in the queue, if there is one.
    # Please note that fast trigger on commands might causing the player to have unintended behaviors, so use them gently :)
    # If the player is stopped (current is None), it will allow stepping "into" the last played track first.
    async def previous_track(self, amount: int = 1) -> Optional[Track] | None:
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
        if not getattr(self.queue, "_playback_history", None):
            return

        if self._is_rolling_back:
            return
        
        # Calculate the target index to move back to, ensure it clamps to 0
        target_index = max(self.queue.current_track_index - (amount - 1 if self.queue.is_at_history_end else amount), 0) 

        # Reset the end-of-queue flag to allow normal playback operations
        self.queue.is_at_history_end = False

        # Replace the current queue with the remaining tracks after the target index
        prev_track = self.queue._playback_history[target_index]
        self.queue._queue = self.queue._playback_history[target_index + 1:]

        # Set rollback flag to prevent on_track_end from auto-skipping
        self._is_rolling_back = True

        await self.play(prev_track)
        self.queue._current_index = target_index

        # Reset the pause flag to allow normal playback operations, just in case
        await self.set_pause(False)

        # Update controller message if applicable
        if not self.update_controller.is_running():
            self.update_controller.start()

        # Reset the rollback flag after a short delay to allow normal playback operations
        if not self.rollback_flag_initialize.is_running():
            self.rollback_flag_initialize.start()

        # Return the track being played
        return prev_track


    async def next_track(self) -> Optional[Track] | bool | None:
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Moves forward in the queue by the next track.

        If the end of the queue is reached, playback will be stopped, unlike the old logic which overflowed.

        `self._isEnded` will be `True` and `self.queue._current_index` will be the latest added track inside `self.queue._playback_history` in this case before returning.

        Returns
        -------
        Optional[lava_lyra.Track]
            The track being played after moving forward, if successful.
        bool: True
            Returns `True` to notify the caller if we already at the end of the queue.
        None
            Returns if the queue (both `self._queue` and `self.queue._playback_history`) was completely empty. This is a very rare scenario, probably due to some uncaught errors.
        """

        # Reset the end-of-queue flag to allow normal playback operations
        self.queue.is_at_history_end = False

        # Get the next track from the queue, if any

        try:
            next_track: Track = self.queue.get()
        except QueueEmpty:
            if len(self.queue._playback_history) == 0:
                # Queue is completely empty, nothing to play.
                # This is a very rare, nearly impossible scenario, probably due to some uncaught errors.
                return

            # Otherwise, this could generally mean that we are at the end of the queue
            # Stop playback and set the isEnded flag
            self.queue.is_at_history_end = True
        
            # Reset _current_index to the end of the queue to prevent overflow
            self.queue._current_index = len(self.queue._playback_history) - 1

            # Update controller message if applicable
            if not self.update_controller.is_running():
                self.update_controller.start()
            
            # Done
            # This is just a trick to notify the caller that the command was completed successfully
            return True

        # Play the target track
        await self.play(next_track, ignore_if_playing=False)

        # Reset the pause flag to allow normal playback operations, just in case
        await self.set_pause(False)

        # Update controller message if applicable
        if not self.update_controller.is_running():
            self.update_controller.start()

        # Return the track being played
        return next_track
 

    # Update the controller message with the current track information
    @tasks.loop(count=1)
    async def update_controller(self):
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
            embed, custom_artwork_file = await self.now_playing_embed(self.current)
            if custom_artwork_file is not None:
                self.controller = await self.context.send(embed=embed, silent=True, file=custom_artwork_file) if (self.context and not self.controller) else None
            else:
                self.controller = await self.context.send(embed=embed, silent=True) if (self.context and not self.controller) else None
            await asyncio.sleep(0.5)  # Small delay to ensure message is sent before next update

        finally:
            self.update_controller.cancel()


    # Reset the rollback and forward flags after a short delay
    # This is to prevent the previous track command from interfering with normal playback operations
    @tasks.loop(count=1)
    async def rollback_flag_initialize(self):
        """
        This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

        Resets the `_rollback` flags after a short delay to allow normal playback operations to resume.

        This is used to prevent the `on_track_end` event from automatically skipping to the next track when performing rollback or forward commands.

        Returns
        -------
        None
        """

        await asyncio.sleep(0.5)
        self._is_rolling_back = False
        self.rollback_flag_initialize.cancel()

