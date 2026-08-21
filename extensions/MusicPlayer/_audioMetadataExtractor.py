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

    Parameters
    ----------
    source : str | bytes | io.BytesIO
        Local file path, remote URL, or in-memory audio bytes.

    stream : bool, optional
        If True, performs a partial HTTP Range request for URL sources.

    bytesRange : int, optional
        Number of bytes to fetch if streaming. Defaults to 20 MB.

        WARNING: Failure to do so may lead to missing metadata fields.

    Examples
    --------
    >>> # For local file source (please ensure the filename without any spaces)
    >>> extractor = AudioMetadataExtractor("path/to/audio.mp3")
    >>> print(extractor.title)
    >>> print(extractor.duration)

    >>> # For URL source with streaming
    >>> url_extractor = AudioMetadataExtractor("https://example.com/audio.flac", stream=True)
    >>> print(url_extractor.artist)

    """

    def __init__(self, source: str | bytes | io.BytesIO, stream: bool = False, bytesRange: int = 20 * 1048576):
        self._tag = self._loadAudio(source, stream, bytesRange)


    def _loadAudio(self, source: str | bytes | io.BytesIO, stream: bool, bytesRange: int) -> TinyTag:
        """Load from file, URL, or byte source via temporary file."""
        if isinstance(source, (bytes, io.BytesIO)):
            data = source.getvalue() if isinstance(source, io.BytesIO) else source
        elif isinstance(source, str):
            if source.startswith(("http://", "https://")):
                http = PoolManager()
                headers = {"Range": f"bytes=0-{bytesRange - 1}"} if stream else {}
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

    # -------------------------------------------------------
    # Metadata Extraction
    # -------------------------------------------------------

    def getMetadata(self) -> dict:
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

        basicInfo = t.__dict__.copy()
        basicInfo.update(t.other)
        return basicInfo
    

    def getCoverArt(self) -> dict | None:
        """
        Returns embedded artwork info, if available.

        Returns
        -------
        dict | None
            Dictionary with keys: mime, width, height, desc, data.
            Returns None if no artwork is found.

        """

        if not self._tag:
            return None

        if not self._tag.images.any:
            return None

        image_data = self._tag.images.any.data
        if not image_data:
            return None

        try:
            img = Image.open(BytesIO(image_data))
            mime = Image.MIME[img.format]
            width, height = img.size
            desc = "front cover"
        except Exception:
            return None

        return {
            "mime": mime,
            "width": width,
            "height": height,
            "desc": desc,
            "data": image_data,
        }

    # -------------------------------------------------------
    # Convenience Properties
    # -------------------------------------------------------


    @property
    def title(self) -> str | None:
        """
        Return the title of the audio track.
        
        Returns
        -------
        str | None
            Title of the track, or None if not available.

        """

        return self.getMetadata().get("title")

    @property
    def artist(self) -> str | None:
        """
        Return the artist of the audio track.

        Returns
        -------
        str | None
            Artist of the track, or None if not available.

        """

        return self.getMetadata().get("artist")

    @property
    def album(self) -> str | None:
        """
        Return the album of the audio track.

        Returns
        -------
        str | None
            Album of the track, or None if not available.

        """

        return self.getMetadata().get("album")

    @property
    def albumArtist(self) -> str | None:
        """
        Return the album artist of the audio track.
        
        Returns
        -------
        str | None
            Album artist of the track, or None if not available.

        """

        return self.getMetadata().get("albumartist")

    @property
    def duration(self) -> str | None:
        """
        Return the duration of the audio track in HH:MM:SS format.
        Returns
        -------
        str | None
            Duration of the track as a string, or None if not available.

        """

        return str(timedelta(seconds=floor(self.getMetadata().get("duration")))) if self.getMetadata().get("duration") else None

    @property
    def genre(self) -> str | None:
        """
        Return the genre of the audio track.

        Returns
        -------
        str | None
            Genre of the track, or None if not available.

        """

        return self.getMetadata().get("genre")

    @property
    def releaseDate(self) -> str | None:
        """
        Return the release date of the audio track.

        Returns
        -------
        str | None
            Release date of the track, or None if not available.

        """

        return (self.getMetadata().get("releasetime")[0] if self.getMetadata().get("releasetime") else None) or self.getMetadata().get("year")

    @property
    def year(self) -> int | None:
        """
        Return the release year of the audio track.

        Returns
        -------
        int | None
            Release year of the track, or None if not available.

        """

        return (self.getMetadata().get("_year")[0] if self.getMetadata().get("_year") else None) or (str(self.getMetadata().get("year")).split('-')[0] if self.getMetadata().get("year") else None)

    @property
    def samplingRate(self) -> int | None:
        """
        Return the sampling rate of the audio track in Hz.

        Returns
        -------
        int | None
            Sampling rate in Hz, or None if not available.

        """

        return self.getMetadata().get("samplerate")

    @property
    def bitRate(self) -> float | None:
        """
        Return the bit rate of the audio track in kbps.

        Returns
        -------
        float | None
            Bit rate in kbps, or None if not available.

        """

        return round(float(self.getMetadata().get("bitrate")), 3) if self.getMetadata().get("bitrate") else None
    
    @property
    def bitDepth(self) -> int | None:
        """
        Return the bit depth of the audio track.
        
        Returns
        -------
        int | None
            Bit depth, or None if not available.

        """

        return self.getMetadata().get("bitdepth")

    @property
    def channels(self) -> int | None:
        """
        Return the number of channels in the audio track.

        Returns
        -------
        int | None
            Number of channels, or None if not available.

        """

        return self.getMetadata().get("channels")
    
    @property
    def trackNumber(self) -> int | None:
        """
        Return the track number of the audio track.

        Returns
        -------
        int | None
            Track number, or None if not available.

        """

        return self.getMetadata().get("track")
    
    @property
    def trackTotal(self) -> int | None:
        """
        Return the total number of tracks in the audio album.

        Returns
        -------
        int | None
            Total number of tracks, or None if not available.

        """

        return self.getMetadata().get("track_total")
    
    @property
    def discNumber(self) -> int | None:
        """
        Return the disc number of the audio track.

        Returns
        -------
        int | None
            Disc number, or None if not available.

        """

        return self.getMetadata().get("disc")

    @property
    def discTotal(self) -> int | None:
        """
        Return the total number of discs for the audio track.

        Returns
        -------
        int | None
            Total number of discs, or None if not available.

        """

        return self.getMetadata().get("discs")

    @property
    def label(self) -> str | None:
        """
        Return the record label of the audio track.

        Returns
        -------
        str | None
            Record label, or None if not available.

        """

        return self.getMetadata().get("label")[0] if self.getMetadata().get("label") else None
    
    @property
    def copyright(self) -> str | None:
        """
        Return the copyright information of the audio track.

        Returns
        -------
        str | None
            Copyright information, or None if not available.

        """

        return (self.getMetadata().get("copyright")[0] if self.getMetadata().get("copyright") else None) or self.getMetadata().get("license")
    
    @property
    def lyrics(self) -> str | None:
        """
        Return the lyrics of the audio track.
        
        Returns
        -------
        str | None
            Lyrics of the track, or None if not available.

        """

        return (self.getMetadata().get("lyrics")[0] if self.getMetadata().get("lyrics") else None)

    @property
    def comment(self) -> str | None:
        """
        Return the comment of the audio track.

        Returns
        -------
        str | None
            Comment of the track, or None if not available.

        """

        return (self.getMetadata().get("comment")[0] if self.getMetadata().get("comment") else None)

    @property
    def composer(self) -> str | None:
        """
        Return the composer of the audio track.

        Returns
        -------
        str | None
            Composer of the track, or None if not available.

        """

        return (self.getMetadata().get("composer")[0] if self.getMetadata().get("composer") else None)

    @property
    def publisher(self) -> str | None:
        """
        Return the publisher of the audio track.

        Returns
        -------
        str | None
            Publisher of the track, or None if not available.

        """
        
        return (self.getMetadata().get("publisher")[0] if self.getMetadata().get("publisher") else None)
    
    @property
    def coverArt(self) -> dict | None:
        """
        Return the embedded cover art of the audio track.
        
        Returns
        -------
        dict | None
            Dictionary with keys: mime, width, height, desc, data.
            Returns None if no artwork is found.

        """

        return self.getCoverArt()

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

        return (self.getMetadata().get(tag)[0] if self.getMetadata().get(tag) else None) or self.getMetadata().get(tag)


# Utility
# Convert artwork dict to a Discord File

def toDiscordFile(artwork: dict, filename: str = "artwork.png") -> "discord.File | None":
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
        return None

    try:
        artworkData: bytes = artwork["data"]
        img = Image.open(BytesIO(artworkData))

        # Resize, and convert to PNG for Discord preview friendliness
        # Same logic as before
        maxSize = (500, 500)
        if any(s > m for s, m in zip(img.size, maxSize)):
            img.thumbnail(maxSize)

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        img.close()

        return discord.File(buffer, filename=filename)
    
    except Exception as e:
        print(f"Error converting artwork to Discord file: {e}")
        return None
