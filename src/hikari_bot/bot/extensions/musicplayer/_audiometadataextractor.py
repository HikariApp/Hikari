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

import io
import os
import tempfile
import discord
from math import floor
from datetime import timedelta
from urllib3 import PoolManager
from PIL import Image
from io import BytesIO
from tinytag import TinyTag


class AudioMetadataExtractor:
    """
    Lightweight audio metadata extractor based on TinyTag.

    Supports MP3, FLAC, M4A, OGG, and a few others.  
    Can handle both local files and HTTP(S) URLs (via partial range requests).

    All properties return `None` if the tag is missing.

    Attributes
    ----------
    title : str | None
        The title of the audio track.
    artist : str | None
        The artist of the audio track.
    album : str | None
        The album of the audio track.
    album_artist : str | None
        The album artist of the audio track.
    duration : str | None
        The duration of the audio track in HH:MM:SS format.
    genre : str | None
        The genre of the audio track.
    release_date : str | None
        The release date of the audio track.
    year : int | None
        The release year of the audio track.
    sampling_rate : int | None
        The sampling rate of the audio track in Hz.
    bit_rate : float | None
        The bit rate of the audio track in kbps.
    bit_depth : int | None
        The bit depth of the audio track.
    channels : int | None
        The number of channels in the audio track.
    track_number : int | None
        The track number of the audio track.
    track_total : int | None
        The total number of tracks in the audio album.
    disc_number : int | None
        The disc number of the audio track.
    disc_total : int | None
        The total number of discs for the audio track.
    label : str | None
        The record label of the audio track.
    copyright : str | None
        The copyright information of the audio track.
    lyrics : str | None
        The lyrics of the audio track.
    comment : str | None
        The comment of the audio track.
    composer : str | None
        The composer of the audio track.
    publisher : str | None
        The publisher of the audio track.
    cover_art : dict | None
        The embedded cover art of the audio track, if available. Returns a dictionary with keys:
        - mime: MIME type of the image (e.g., "image/jpeg").
        - width: Width of the image in pixels.
        - height: Height of the image in pixels.
        - desc: Description of the image (e.g., "front cover").
        - data: Raw bytes of the image.
    others(tag: str) : str | None
        Return other metadata fields by tag name. Returns the value of the specified tag, or None if not available.
    

    Parameters
    ----------
    source : str | bytes | io.BytesIO
        Local file path, remote URL, or in-memory audio bytes.
    stream : bool, optional
        If True, performs a partial HTTP Range request for URL sources.
    bytes_range : int, optional
        Number of bytes to fetch if streaming. Defaults to 20 MB.  
        WARNING: Failure to do so may lead to missing metadata fields.

    Examples
    --------
    ```python
    # For local file source (please ensure the filename without any spaces)
    extractor = AudioMetadataExtractor("path/to/audio.mp3")
    print(extractor.title)
    print(extractor.duration)

    # For URL source with streaming
    url_extractor = AudioMetadataExtractor("https://example.com/audio.flac", stream=True)
    print(url_extractor.artist)
    ```
    """

    def __init__(self, source: str | bytes | io.BytesIO, stream: bool = False, bytes_range: int = 20 * 1048576):
        self._tag = self._load_audio(source, stream, bytes_range)

    
    def _load_audio(self, source: str | bytes | io.BytesIO, stream: bool, bytes_range: int) -> TinyTag:
        """Load from file, URL, or byte source via temporary file."""
        if isinstance(source, (bytes, io.BytesIO)):
            data = source.getvalue() if isinstance(source, io.BytesIO) else source
        elif isinstance(source, str):
            if source.startswith(("http://", "https://")):
                http = PoolManager()
                headers = {"Range": f"bytes=0-{bytes_range - 1}"} if stream else {}
                resp = http.request("GET", source, headers=headers)
                data = resp.data
                resp.release_conn()
            else:
                # Local file path
                return TinyTag.get(source, image=True)
        else:
            raise ValueError(f"Unsupported source type: {type(source)}")

        # TinyTag requires file path — use safely via mkstemp
        fd, tmp_path = tempfile.mkstemp(suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as tmp:
                tmp.write(data)
            tag = TinyTag.get(tmp_path, image=True)
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return tag

    
    def get_metadata(self) -> dict:
        """
        Return structured metadata dictionary.
        
        Combines basic TinyTag fields with any additional tags found.

        Returns
        -------
        dict
            Dictionary of metadata fields.
        """

        t = self._tag
        if not t:
            return {}

        basic_info = t.__dict__.copy()
        basic_info.update(t.other)
        return basic_info

    
    def get_cover_art(self) -> dict | None:
        """
        Returns embedded artwork info, if available.

        Returns
        -------
        dict | None
            Dictionary with keys: mime, width, height, desc, data. Returns None if no artwork is found.
        """

        if not self._tag:
            return

        if not self._tag.images.any:
            return

        image_data = self._tag.images.any.data
        if not image_data:
            return

        try:
            img = Image.open(BytesIO(image_data))
            mime = Image.MIME[img.format]
            width, height = img.size
            desc = "front cover"
        except Exception:
            return

        return {
            "mime": mime,
            "width": width,
            "height": height,
            "desc": desc,
            "data": image_data,
        }

    
    @property
    def title(self) -> str | None:
        """
        Return the title of the audio track.
        
        Returns
        -------
        str | None
            Title of the track, or None if not available.
        """

        return self.get_metadata().get("title")

    
    @property
    def artist(self) -> str | None:
        """
        Return the artist of the audio track.

        Returns
        -------
        str | None
            Artist of the track, or None if not available.
        """

        return self.get_metadata().get("artist")

    
    @property
    def album(self) -> str | None:
        """
        Return the album of the audio track.

        Returns
        -------
        str | None
            Album of the track, or None if not available.
        """

        return self.get_metadata().get("album")

    
    @property
    def album_artist(self) -> str | None:
        """
        Return the album artist of the audio track.
        
        Returns
        -------
        str | None
            Album artist of the track, or None if not available.
        """

        return self.get_metadata().get("albumartist")

    
    @property
    def duration(self) -> str | None:
        """
        Return the duration of the audio track in HH:MM:SS format.
        Returns
        -------
        str | None
            Duration of the track as a string, or None if not available.
        """

        return str(timedelta(seconds=floor(self.get_metadata().get("duration")))) if self.get_metadata().get("duration") else None

    
    @property
    def genre(self) -> str | None:
        """
        Return the genre of the audio track.

        Returns
        -------
        str | None
            Genre of the track, or None if not available.
        """

        return self.get_metadata().get("genre")

    
    @property
    def release_date(self) -> str | None:
        """
        Return the release date of the audio track.

        Returns
        -------
        str | None
            Release date of the track, or None if not available.
        """

        return (self.get_metadata().get("releasetime")[0] if self.get_metadata().get("releasetime") else None) or self.get_metadata().get("year")

    
    @property
    def year(self) -> int | None:
        """
        Return the release year of the audio track.

        Returns
        -------
        int | None
            Release year of the track, or None if not available.
        """

        return (self.get_metadata().get("_year")[0] if self.get_metadata().get("_year") else None) or (str(self.get_metadata().get("year")).split('-')[0] if self.get_metadata().get("year") else None)

    
    @property
    def sampling_rate(self) -> int | None:
        """
        Return the sampling rate of the audio track in Hz.

        Returns
        -------
        int | None
            Sampling rate in Hz, or None if not available.
        """

        return self.get_metadata().get("samplerate")

    
    @property
    def bit_rate(self) -> float | None:
        """
        Return the bit rate of the audio track in kbps.

        Returns
        -------
        float | None
            Bit rate in kbps, or None if not available.
        """

        return round(float(self.get_metadata().get("bitrate")), 3) if self.get_metadata().get("bitrate") else None

    
    @property
    def bit_depth(self) -> int | None:
        """
        Return the bit depth of the audio track.
        
        Returns
        -------
        int | None
            Bit depth, or None if not available.
        """

        return self.get_metadata().get("bitdepth")

    
    @property
    def channels(self) -> int | None:
        """
        Return the number of channels in the audio track.

        Returns
        -------
        int | None
            Number of channels, or None if not available.
        """

        return self.get_metadata().get("channels")

    
    @property
    def track_number(self) -> int | None:
        """
        Return the track number of the audio track.

        Returns
        -------
        int | None
            Track number, or None if not available.
        """

        return self.get_metadata().get("track")

    
    @property
    def track_total(self) -> int | None:
        """
        Return the total number of tracks in the audio album.

        Returns
        -------
        int | None
            Total number of tracks, or None if not available.
        """

        return self.get_metadata().get("track_total")

    
    @property
    def disc_number(self) -> int | None:
        """
        Return the disc number of the audio track.

        Returns
        -------
        int | None
            Disc number, or None if not available.
        """

        return self.get_metadata().get("disc")

    
    @property
    def disc_total(self) -> int | None:
        """
        Return the total number of discs for the audio track.

        Returns
        -------
        int | None
            Total number of discs, or None if not available.
        """

        return self.get_metadata().get("discs")

    
    @property
    def label(self) -> str | None:
        """
        Return the record label of the audio track.

        Returns
        -------
        str | None
            Record label, or None if not available.
        """

        return self.get_metadata().get("label")[0] if self.get_metadata().get("label") else None

    
    @property
    def copyright(self) -> str | None:
        """
        Return the copyright information of the audio track.

        Returns
        -------
        str | None
            Copyright information, or None if not available.
        """

        return (self.get_metadata().get("copyright")[0] if self.get_metadata().get("copyright") else None) or self.get_metadata().get("license")

    
    @property
    def lyrics(self) -> str | None:
        """
        Return the lyrics of the audio track.
        
        Returns
        -------
        str | None
            Lyrics of the track, or None if not available.
        """

        return (self.get_metadata().get("lyrics")[0] if self.get_metadata().get("lyrics") else None)

    
    @property
    def comment(self) -> str | None:
        """
        Return the comment of the audio track.

        Returns
        -------
        str | None
            Comment of the track, or None if not available.
        """

        return (self.get_metadata().get("comment")[0] if self.get_metadata().get("comment") else None)

    
    @property
    def composer(self) -> str | None:
        """
        Return the composer of the audio track.

        Returns
        -------
        str | None
            Composer of the track, or None if not available.
        """

        return (self.get_metadata().get("composer")[0] if self.get_metadata().get("composer") else None)

    
    @property
    def publisher(self) -> str | None:
        """
        Return the publisher of the audio track.

        Returns
        -------
        str | None
            Publisher of the track, or None if not available.
        """
        
        return (self.get_metadata().get("publisher")[0] if self.get_metadata().get("publisher") else None)

    
    @property
    def cover_art(self) -> dict | None:
        """
        Return the embedded cover art of the audio track.
        
        Returns
        -------
        dict | None
            Dictionary with keys: mime, width, height, desc, data. Returns None if no artwork is found.
        """

        return self.get_cover_art()

    
    @property
    def others(self, tag: str) -> str | None:
        """
        Return other metadata fields by tag name.

        Parameters
        ----------
        tag : str
            The metadata tag name to retrieve.
        
        Returns
        -------
        str | None
            Value of the specified tag, or None if not available.
        """

        return (self.get_metadata().get(tag)[0] if self.get_metadata().get(tag) else None) or self.get_metadata().get(tag)


# Utility
# Convert artwork dict to a Discord File

def to_discord_file(artwork: dict, filename: str = "artwork.png") -> "discord.File | None":
    """
    Convert embedded artwork to a Discord attachment.

    Parameters
    ----------
    artwork : dict
        The artwork dictionary from `CustomAudioMetadata.coverImage`.
    
    Returns
    -------
    discord.File | None
        A discord.File object if artwork is present, otherwise None.
    """
    
    if not artwork or not artwork.get("data"):
        return

    try:
        artwork_data: bytes = artwork["data"]
        img = Image.open(BytesIO(artwork_data))

        # Resize, and convert to PNG for Discord preview friendliness
        # Same logic as before
        max_size = (500, 500)
        if any(s > m for s, m in zip(img.size, max_size)):
            img.thumbnail(max_size)

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        img.close()

        return discord.File(buffer, filename=filename)
    
    except Exception as e:
        print(f"Error occurred while converting artwork to Discord file: {e}")
        return

