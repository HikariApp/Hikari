import io
import math
import discord
from urllib3 import PoolManager
from PIL import Image
from io import BytesIO
from mutagen import File
from datetime import timedelta


class AudioMetadataExtractor:
    """
    Extracts and provides structured access to common metadata fields from a wide range
    of audio formats (FLAC, MP3, MP4, OGG, etc.).

    The class uses Mutagen to auto-detect the correct file type and parse its tags.
    It supports both local files and HTTP(S) URLs (via partial range requests).

    All properties return `None` if the tag is missing.

    Parameters
    ----------
    source : str | bytes | io.BytesIO
        Local file path, remote URL, or in-memory audio bytes.

    stream : bool, optional
        If True, performs a partial HTTP Range request for URL sources.

    bytesRange : int, optional
        Number of bytes to fetch if streaming. Default is 4 MB.

        WARNING: Setting this too low may result in incomplete metadata.

    Attributes
    ----------
    samplingRate : int | None
        Audio sampling rate in Hz.

    bitrate : int | None
        Audio bitrate in kbps.

    channels : int | None
        Number of audio channels (1=mono, 2=stereo, etc.).

    length : float | None
        Length of the audio track in seconds.

    duration : timedelta | None
        Length of the audio track as a timedelta object.

    lyrics : str | None
        Lyrics of the track.

    isrc : str | None
        International Standard Recording Code.

    iTunesPlaylistID : str | None
        iTunes playlist identifier.

    copyright : str | None
        Copyright statement or rights holder.

    albumSortOrder : str | None
        Sorting key for the album title used by some players.

    iTunesAlbumTitleID : str | None
        iTunes-specific album title identifier.

    date : str | None
        Original release date or year.

    discNumber : str | None
        Current disc number (e.g., 1 for disc 1 of 2).

    artist : str | None
        Name of the performing artist or main performer.

    upc : str | None
        Universal Product Code (barcode) associated with the release.

    performer : str | None
        Contributing performer or musician.

    releaseTime : str | None
        Exact release timestamp when available.

    titleSortOrder : str | None
        Sorting key for the track title used by some media libraries.

    label : str | None
        Record label or publishing entity.

    trackNumber : str | None
        Track number within the album or disc.

    albumArtistSortOrder : str | None
        Sorting key for the album artist.

    genre : str | None
        Musical genre or style.

    title : str | None
        Track title.

    albumArtist : str | None
        Primary album artist (may differ from the performing artist).

    artistSortOrder : str | None
        Sorting key for the artist name.

    discTotal : str | None
        Total number of discs in the release.

    album : str | None
        Title of the album or release the track belongs to.

    trackTotal : str | None
        Total number of tracks in this album or disc.

    coverImage : dict | None
        Embedded album artwork with keys: mime (str), width (int),
        height (int), desc (str), data (bytes).

    Methods
    -------
    getMetadata() : dict | None
        Return all parsed metadata as a dictionary.

    getCoverArt() : dict | None
        Return embedded cover image info, if available.

    """

    def __init__(self, source: str | bytes | io.BytesIO, stream: bool = False, bytesRange: int = 4 * 1048576):
        self._audio = self._loadAudio(source, stream, bytesRange)


    def _loadAudio(self, source: str | bytes | io.BytesIO, stream: bool, bytesRange: int) -> File:
        """Load file or fetch from a URL into a Mutagen File object."""

        if isinstance(source, (bytes, io.BytesIO)):
            bio = source if isinstance(source, io.BytesIO) else io.BytesIO(source)
            return File(bio)

        if isinstance(source, str):
            if source.startswith(("http://", "https://")) and stream:
                http = PoolManager()
                headers = {"Range": f"bytes=0-{bytesRange - 1}"}
                resp = http.request("GET", source, headers=headers, preload_content=False)
                data = resp.read()
                resp.release_conn()
                return File(io.BytesIO(data))
            
            return File(source)

        raise ValueError(f"Unsupported source type for {source}")


    def getMetadata(self):
        """
        Extract and return all metadata as a dictionary.

        Note: This does NOT include embedded cover image data. Use `getCoverArt` for that.

        Returns
        -------
        dict | None
            Dictionary of metadata fields and values.

        """
        
        output = {}

        # Technical info
        info = getattr(self._audio, "info", None)
        if info:
            output.update({
                "sample_rate": getattr(info, "sample_rate", None),
                "bitrate": getattr(info, "bitrate", None),
                "channels": getattr(info, "channels", None),
                "length": getattr(info, "length", None),
            })

        # Tags / metadata
        tags = getattr(self._audio, "tags", None)
        if tags:
            for k, v in tags.items():
                if isinstance(v, (list, tuple)):
                    output[k] = v[0] if v else None
                else:
                    output[k] = v

        return output if output else None


    def getCoverArt(self):
        """
        Returns the embedded cover image, if available.

        Returns
        -------
        dict | None
            Dictionary with keys: mime (str), width (int), height (int), desc (str), data (bytes), or `None` if no cover image is found.

        """

        a = self._audio
        if not a:
            return None

        # FLAC / MP4 pictures
        if hasattr(a, "pictures") and a.pictures:
            pic = a.pictures[0]
            return {
                "mime": getattr(pic, "mime", None),
                "desc": getattr(pic, "desc", ""),
                "width": getattr(pic, "width", None),
                "height": getattr(pic, "height", None),
                "data": pic.data,
            }

        # MP3 / ID3 artwork
        if hasattr(a, "tags") and a.tags:
            for key in a.tags.keys():
                if key.startswith("APIC:") or key == "APIC":
                    apic = a.tags[key]
                    return {
                        "mime": getattr(apic, "mime", None),
                        "desc": getattr(apic, "desc", ""),
                        "width": None,
                        "height": None,
                        "data": apic.data,
                    }

        # If no cover image found
        return None
    

    @property
    def samplingRate(self) -> int | None:
        """
        Returns the audio sampling rate in Hz.

        Returns
        -------
        int | None
            Sampling rate in Hertz (Hz), or `None` if unavailable.

        """

        value = self.getMetadata().get("sample_rate") if self.getMetadata() else None
        return int(value) if value else None


    @property
    def bitrate(self) -> float | None:
        """
        Returns the audio bitrate, in kbps.

        Returns
        -------
        int | None
            Bitrate in kilobits per second (kbps), or `None` if unavailable.

        """

        value = self.getMetadata().get("bitrate") if self.getMetadata() else None
        return float(value / 1000) if value else None
    

    @property
    def channels(self) -> int | None:
        """
        Returns the number of audio channels.

        Returns
        -------
        int | None
            Number of audio channels (e.g., 1 for mono, 2 for stereo), or `None` if unavailable.

        """

        value = self.getMetadata().get("channels") if self.getMetadata() else None
        return int(value) if value else None


    @property
    def length(self) -> float | None:
        """
        Returns the audio length, in seconds.

        Returns
        -------
        float | None
            Length of the audio track in seconds, or `None` if unavailable.

        """

        value = self.getMetadata().get("length") if self.getMetadata() else None
        return float(value) if value else None


    @property
    def duration(self) -> str | None:
        """
        Returns the audio length, in timestamp.

        Returns
        -------
        `timedelta` | None
            Length of the audio track in timestamp, or `None` if unavailable.

        """

        value = self.getMetadata().get("length") if self.getMetadata() else None
        return str(timedelta(seconds=math.floor(value))) if value else None


    @property
    def lyrics(self) -> str | None:
        """
        Retrieves the lyrics of the track.

        Returns
        -------
        str | None
            The song’s lyrics if embedded in the file, or `None` if not present.

        """

        return self.getMetadata().get("lyrics") if self.getMetadata() else None
    

    @property
    def isrc(self) -> str | None:
        """
        Retrieves the International Standard Recording Code of the track.

        Returns
        -------
        str | None
            The official ISRC identifier for the recording, if available.

        """

        return self.getMetadata().get("isrc") if self.getMetadata() else None


    @property
    def iTunesPlaylistID(self) -> int | None:
        """
        Retrieves the iTunes playlist identifier.

        Returns
        -------
        str | None
            The Apple iTunes playlist or collection ID, or `None` if missing.

        """

        value = self.getMetadata().get("itunesplaylistid") if self.getMetadata() else None
        return int(value) if value else None


    @property
    def copyright(self) -> str | None:
        """
        Retrieves the copyright statement or rights holder.

        Returns
        -------
        str | None
            Copyright or rights notice associated with the track, or `None`.

        """

        return self.getMetadata().get("copyright") if self.getMetadata() else None


    @property
    def albumSortOrder(self) -> str | None:
        """
        Retrieves the album sort order field.

        Returns
        -------
        str | None
            Sort key used by media libraries when ordering albums, or `None`.

        """

        return self.getMetadata().get("albumsortorder") if self.getMetadata() else None


    @property
    def iTunesAlbumTitleID(self) -> int | None:
        """
        Retrieves the iTunes album title identifier.

        Returns
        -------
        str | None
            The internal iTunes ID for the album title, if defined.

        """

        value = self.getMetadata().get("itunesalbumtitleid") if self.getMetadata() else None
        return int(value) if value else None


    @property
    def date(self) -> str | None:
        """
        Retrieves the album's original release date.

        Returns
        -------
        str | None
            The date or year when the track was originally released, or `None`.

        """

        return self.getMetadata().get("date") if self.getMetadata() else None


    @property
    def discNumber(self) -> int | None:
        """
        Retrieves the disc number within a multi-disc set.

        Returns
        -------
        str | None
            Current disc number (e.g., '1' for disc 1 of 2), or `None`.

        """

        value = self.getMetadata().get("discnumber") if self.getMetadata() else None
        return int(value) if value else None


    @property
    def artist(self) -> str | None:
        """
        Retrieves the artist of the track.

        Returns
        -------
        str | None
            The performing artist name, or `None` if missing.

        """

        return self.getMetadata().get("artist") if self.getMetadata() else None


    @property
    def upc(self) -> str | None:
        """
        Retrieves the Universal Product Code.

        Returns
        -------
        str | None
            UPC (barcode) linked to this release, or `None` if unavailable.

        """

        return self.getMetadata().get("upc") if self.getMetadata() else None


    @property
    def performer(self) -> str | None:
        """
        Retrieves the performer information.

        Returns
        -------
        str | None
            The credited performer or musician, or `None` if not encoded.

        """

        return self.getMetadata().get("performer") if self.getMetadata() else None


    @property
    def releaseTime(self) -> str | None:
        """
        Returns the release timestamp.

        Returns
        -------
        str | None
            Full release timestamp or date-time string, or `None`.

        """

        return self.getMetadata().get("releasetime") if self.getMetadata() else None


    @property
    def titleSortOrder(self) -> str | None:
        """
        Retrieves the title sort order.

        Returns
        -------
        str | None
            Sort key used for title ordering in libraries, or `None`.

        """

        return self.getMetadata().get("titlesortorder") if self.getMetadata() else None


    @property
    def label(self) -> str | None:
        """
        Retrieves the record label or publisher.

        Returns
        -------
        str | None
            Publishing or record label name, or `None` if absent.

        """

        return self.getMetadata().get("label") if self.getMetadata() else None


    @property
    def trackNumber(self) -> int | None:
        """
        Returns the track number on the disc or album.

        Returns
        -------
        int | None
            The track number (e.g., 3 for track 3), or `None` if unavailable.

        """

        value = self.getMetadata().get("tracknumber") if self.getMetadata() else None
        return int(value) if value else None


    @property
    def albumArtistSortOrder(self) -> str | None:
        """
        Retrieves the album artist sort order key.

        Returns
        -------
        str | None
            Sort key used for the album artist field, or `None`.

        """

        return self.getMetadata().get("albumartistsortorder") if self.getMetadata() else None


    @property
    def genre(self) -> str | None:
        """
        Retrieves the musical genre.

        Returns
        -------
        str | None
            The genre or style of the track (e.g., 'Rock', 'Jazz'), or `None`.

        """

        return self.getMetadata().get("genre") if self.getMetadata() else None


    @property
    def title(self) -> str | None:
        """
        Returns the track title.

        Returns
        -------
        str | None
            The name of the track, or `None` if the tag is missing.

        """

        return self.getMetadata().get("title") if self.getMetadata() else None


    @property
    def albumartist(self) -> str | None:
        """
        Retrieves the primary album artist.

        Returns
        -------
        str | None
            The main artist credited for the album, or `None` if missing.

        """

        return self.getMetadata().get("albumartist") if self.getMetadata() else None


    @property
    def artistSortOrder(self) -> str | None:
        """
        Retrieves the artist sort order key.

        Returns
        -------
        str | None
            Sorting key for the artist name, or `None`.

        """

        return self.getMetadata().get("artistsortorder") if self.getMetadata() else None


    @property
    def discTotal(self) -> int | None:
        """
        Returns the total number of discs.

        Returns
        -------
        str | None
            The total number of discs in a multi-disc release, or `None`.

        """

        value = self.getMetadata().get("disctotal") if self.getMetadata() else None
        return int(value) if value else None


    @property
    def album(self) -> str | None:
        """
        Retrieves the album title.

        Returns
        -------
        str | None
            The name of the album this track belongs to, or `None`.

        """

        return self.getMetadata().get("album") if self.getMetadata() else None


    @property
    def trackTotal(self) -> int | None:
        """
        Returns the total number of tracks.

        Returns
        -------
        str | None
            Total track count for the album or disc, or `None`.

        """

        value = self.getMetadata().get("tracktotal") if self.getMetadata() else None
        return int(value) if value else None
    

    @property
    def coverArt(self) -> dict | None:
        """
        Returns the embedded cover image, if available.

        Returns
        -------
        dict | None
            Dictionary with keys: mime (str), width (int), height (int), desc (str), data (bytes), or `None` if no cover image is found.

        """


        return self.getCoverArt()
    

# Utility function converting artwork to a discord.File()
def toDiscordFile(artwork: dict, filename: str = "artwork.png") -> 'discord.File | None':
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

    if not artwork:
        return None
    
    if artwork.get("data") is None:
        return None
    
    # Raw data
    artworkData: bytes = artwork.get("data")

    try:
        artworkFile = Image.open(BytesIO(artworkData))
        
        # Resize artwork if dimensions are too large
        max_dimensions = (500, 500) 
        if artworkFile.size[0] > max_dimensions[0] or artworkFile.size[1] > max_dimensions[1]:
            artworkFile.thumbnail(max_dimensions)

        # Same logic as before
        artworkBuffer = BytesIO()
        artworkFile.save(artworkBuffer, format="PNG")
        artworkFile.close()
        artworkBuffer.seek(0)
        return discord.File(artworkBuffer, filename=filename)

    except Exception as e:
        print(f"An unexpected error occurred while processing artwork: {e}")
        return None
