import asyncio
import time
from typing import Any, Callable, cast
import discord
import yt_dlp
from data.track import Track
from data.exceptions import AudioError, DownloadError
from utils.config import YTDL_FORMAT_OPTIONS, YTDL_HEADERS, FFMPEG_OPTIONS
from data.constants import MAX_PLAYLIST_SIZE
import logging

logger = logging.getLogger(__name__)


class YTDLSource:
    """Handles YouTube-DL operations for extracting track info and streams."""

    ytdl_options: dict[str, Any] = YTDL_FORMAT_OPTIONS.copy()
    ytdl_options["http_headers"] = YTDL_HEADERS
    ytdl: yt_dlp.YoutubeDL = yt_dlp.YoutubeDL(cast(Any, ytdl_options))
    flat_ytdl: yt_dlp.YoutubeDL = yt_dlp.YoutubeDL(
        cast(
            Any,
            {
                **ytdl_options,
                "extract_flat": "in_playlist",
                "playlistend": MAX_PLAYLIST_SIZE,
            },
        )
    )

    @staticmethod
    async def _extract(ytdl: yt_dlp.YoutubeDL, query: str) -> dict[str, Any]:
        """Run a yt-dlp extraction in an executor to avoid blocking the event loop."""

        loop = asyncio.get_running_loop()

        try:
            data = await loop.run_in_executor(
                None, lambda: ytdl.extract_info(query, download=False)
            )
        except Exception as exception:
            raise DownloadError(f"Extraction failed: {str(exception)}") from exception

        if not data:
            raise DownloadError(f"Could not extract info from {query}")

        return dict(data)

    @staticmethod
    def _track_from_info(
        data: dict[str, Any], requester: discord.Member | None
    ) -> Track:
        """Build a Track from a (possibly flat) yt-dlp info dict."""

        thumbnail = data.get("thumbnail")
        if not thumbnail and data.get("thumbnails"):
            thumbnail = data["thumbnails"][-1].get("url")

        return Track(
            title=data.get("title") or "Unknown Title",
            source=data.get("webpage_url") or data.get("url") or "",
            duration=int(data.get("duration") or 0),
            thumbnail=thumbnail,
            uploader=data.get("uploader") or data.get("channel"),
            requester=requester,
        )

    @classmethod
    async def search(
        cls, query: str, requester: discord.Member
    ) -> tuple[list[Track], str | None]:
        """
        Find the tracks matching a URL or search query.

        Playlists are listed without resolving their streams, which happens
        when each track is about to play.

        Args:
            query: URL or yt-dlp search query
            requester: Discord member who requested the tracks

        Returns:
            The tracks found, and the playlist title if the query was a playlist

        Raises:
            DownloadError: If nothing could be extracted
        """

        data = await cls._extract(cls.flat_ytdl, query)

        if data.get("_type") != "playlist":
            track = cls._track_from_info(data, requester)

            if data.get("formats") and data.get("url"):
                track.stream_url = data["url"]
                track.resolved_at = time.monotonic()

            return [track], None

        tracks = [
            cls._track_from_info(entry, requester)
            for entry in data.get("entries") or []
            if entry
            and entry.get("title") not in (None, "[Deleted video]", "[Private video]")
        ]

        if not tracks:
            raise DownloadError("No playable tracks found")

        is_search = query.startswith(("ytsearch", "scsearch"))

        return tracks, None if is_search else data.get("title")

    @classmethod
    async def resolve(cls, track: Track) -> None:
        """
        Resolve the stream URL of a track, refreshing its metadata.

        Raises:
            DownloadError: If the stream cannot be found
        """

        data = await cls._extract(cls.ytdl, track.source)

        if "entries" in data:
            entries = [entry for entry in data["entries"] if entry]
            if not entries:
                raise DownloadError(f"No results for {track.title}")
            data = entries[0]

        if "url" not in data:
            raise DownloadError("Could not find streaming URL")

        resolved = cls._track_from_info(data, track.requester)

        track.title = resolved.title
        track.source = resolved.source or track.source
        track.duration = resolved.duration or track.duration
        track.thumbnail = resolved.thumbnail or track.thumbnail
        track.uploader = resolved.uploader or track.uploader
        track.stream_url = data["url"]
        track.resolved_at = time.monotonic()

    @classmethod
    def get_audio_source(
        cls, track: Track, volume: float = 0.5
    ) -> discord.PCMVolumeTransformer[discord.FFmpegPCMAudio]:
        """
        Create an audio source from a Track object.

        Args:
            track: Track object to create source from
            volume: Initial volume (0.0 to 1.0)

        Returns:
            Discord audio source ready to play
        """

        if not track.stream_url:
            raise AudioError(f"Track {track.title} has no stream URL")

        source = discord.FFmpegPCMAudio(
            track.stream_url,
            before_options=FFMPEG_OPTIONS.get("before_options"),
            options=FFMPEG_OPTIONS.get("options"),
        )

        return discord.PCMVolumeTransformer(source, volume=volume)


class AudioPlayer:
    """Manages audio playback for a guild."""

    def __init__(self, voice_client: discord.VoiceClient):
        self.voice_client: discord.VoiceClient = voice_client
        self._volume: float = 0.5
        self.current_track: Track | None = None

    @property
    def volume(self) -> int:
        """Get current volume (0-100)."""

        return int(self._volume * 100)

    @volume.setter
    def volume(self, value: int) -> None:
        """Set volume (0-100)."""

        self._volume = max(0, min(100, value)) / 100

        # Update current playing audio if exists
        if self.voice_client.source and isinstance(
            self.voice_client.source, discord.PCMVolumeTransformer
        ):
            source = cast(discord.PCMVolumeTransformer[Any], self.voice_client.source)
            source.volume = self._volume

    def is_playing(self) -> bool:
        """Check if audio is currently playing."""

        return self.voice_client.is_playing()

    def is_paused(self) -> bool:
        """Check if audio is paused."""

        return self.voice_client.is_paused()

    async def play(
        self, track: Track, after: Callable[[Exception | None], Any] | None = None
    ) -> None:
        """
        Play a track.

        Args:
            track: Track to play
            after: Callback function to call when track finishes
        """

        # A paused source also has to be stopped before playing another one
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()

        self.current_track = track

        try:
            source = YTDLSource.get_audio_source(track, volume=self._volume)
            self.voice_client.play(source, after=after)
        except Exception as exception:
            raise AudioError(f"Failed to play track: {str(exception)}") from exception

    def pause(self) -> None:
        """Pause current playback."""

        if self.voice_client.is_playing():
            self.voice_client.pause()

    def resume(self) -> None:
        """Resume paused playback."""

        if self.voice_client.is_paused():
            self.voice_client.resume()

    def stop(self) -> None:
        """Stop current playback."""

        self.voice_client.stop()
        self.current_track = None
