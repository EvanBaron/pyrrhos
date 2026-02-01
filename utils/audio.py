import asyncio
from typing import Any, Callable, cast
import discord
import yt_dlp
from data.track import Track
from data.exceptions import AudioError, DownloadError
from utils.config import YTDL_FORMAT_OPTIONS, YTDL_HEADERS, FFMPEG_OPTIONS


class YTDLSource:
    """Handles YouTube-DL operations for downloading and extracting audio info."""

    ytdl_options: dict[str, Any] = YTDL_FORMAT_OPTIONS.copy()
    ytdl_options["http_headers"] = YTDL_HEADERS
    ytdl: yt_dlp.YoutubeDL = yt_dlp.YoutubeDL(cast(Any, ytdl_options))

    @classmethod
    async def extract_info(cls, url: str, download: bool = False) -> dict[str, Any]:
        """
        Extract information from a URL asynchronously.

        Args:
            url: The URL or search query
            download: Whether to download the audio

        Returns:
            Dictionary containing track information

        Raises:
            DownloadError: If extraction fails
        """
        loop = asyncio.get_event_loop()

        try:
            # Run in executor to avoid blocking
            data = await loop.run_in_executor(
                None, lambda: cls.ytdl.extract_info(url, download=download)
            )

            if not data:
                raise DownloadError(f"Could not extract info from {url}")

            # Handle playlists
            if "entries" in data:
                if len(data["entries"]) == 0:
                    raise DownloadError("Playlist is empty")
                data = data["entries"][0]

            return dict(data)

        except Exception as exception:
            raise DownloadError(
                f"Unexpected error during extraction: {str(exception)}"
            ) from exception

    @classmethod
    async def from_url(cls, url: str, requester: discord.Member) -> Track:
        """
        Create a Track object from a URL or search query.

        Args:
            url: YouTube URL or search query
            requester: Discord member who requested the track

        Returns:
            Track object ready to play

        Raises:
            DownloadError: If track creation fails
        """

        data = await cls.extract_info(url, download=False)

        # Extract the streaming URL
        if "url" not in data:
            raise DownloadError("Could not find streaming URL")

        track = Track(
            title=data.get("title", "Unknown Title"),
            url=data["url"],
            webpage_url=data.get("webpage_url", url),
            duration=data.get("duration", 0),
            thumbnail=data.get("thumbnail"),
            uploader=data.get("uploader", "Unknown"),
            requester=requester,
        )

        return track

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

        source = discord.FFmpegPCMAudio(
            track.url,
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

        if self.voice_client.is_playing():
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
