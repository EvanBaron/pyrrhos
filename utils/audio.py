import asyncio
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable, cast
import discord
import yt_dlp
from data.track import Track
from data.exceptions import AudioError, DownloadError
from utils.config import (
    COOKIES_PATH,
    FFMPEG_OPTIONS,
    POT_PROVIDER_URL,
    YTDL_FORMAT_OPTIONS,
    YTDL_HEADERS,
)
from data.constants import MAX_PLAYLIST_SIZE
import logging

logger = logging.getLogger(__name__)


# Fresh extractions to try when downloading a stream fails before any audio
DOWNLOAD_RETRIES = 2


class YTDLDownloadStream:
    """
    Output of a yt-dlp process downloading a stream, read by ffmpeg's pipe writer.

    YouTube rejects ffmpeg's own requests to stream URLs with 403 Forbidden,
    and sometimes rejects yt-dlp's first request too, so a download failing
    before any audio is retried with a fresh extraction.
    """

    def __init__(self, stream_info: dict[str, Any]):
        self._source: str = stream_info.get("webpage_url") or stream_info["url"]
        self._retries: int = DOWNLOAD_RETRIES
        self._received: bool = False
        self._stopped: bool = False
        self._lock: threading.Lock = threading.Lock()

        with tempfile.NamedTemporaryFile(
            "w", suffix=".info.json", delete=False
        ) as info_file:
            json.dump(stream_info, info_file)
            self._info_path: str = info_file.name

        try:
            self._process: subprocess.Popen[bytes] = self._spawn(
                ["--load-info-json", self._info_path]
            )
        except OSError:
            self._remove_info_file()
            raise

    @staticmethod
    def _spawn(input_args: list[str]) -> subprocess.Popen[bytes]:
        command = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--quiet",
            "--no-warnings",
            "--no-progress",
            "--no-playlist",
            "--format",
            str(YTDL_FORMAT_OPTIONS["format"]),
            "--http-chunk-size",
            str(YTDL_FORMAT_OPTIONS["http_chunk_size"]),
            "--extractor-args",
            f"youtubepot-bgutilhttp:base_url={POT_PROVIDER_URL}",
            "--output",
            "-",
        ]
        if os.path.exists(COOKIES_PATH):
            command += ["--cookies", COOKIES_PATH]

        # stderr is inherited so download errors show up in the bot's logs
        return subprocess.Popen(
            [*command, *input_args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
        )

    def read(self, size: int) -> bytes:
        while True:
            process = self._process
            assert process.stdout is not None
            data = process.stdout.read(size)

            if data:
                self._received = True
                return data

            returncode = process.wait()

            with self._lock:
                if (
                    returncode == 0
                    or self._received
                    or self._stopped
                    or self._retries <= 0
                ):
                    return b""

                self._retries -= 1
                logger.warning(
                    "Downloading %s failed (exit code %s), retrying",
                    self._source,
                    returncode,
                )
                self._process = self._spawn(["--", self._source])

    def stop(self) -> None:
        """Kill the download, which ends the stream for ffmpeg."""

        with self._lock:
            self._stopped = True
            process = self._process

        if process.poll() is None:
            process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("yt-dlp process %s did not exit", process.pid)

        self._remove_info_file()

    def _remove_info_file(self) -> None:
        try:
            os.unlink(self._info_path)
        except FileNotFoundError:
            pass


class YTDLPipeAudio(discord.FFmpegPCMAudio):
    """FFmpeg audio fed by yt-dlp downloading the stream."""

    def __init__(self, stream_info: dict[str, Any]):
        self._download: YTDLDownloadStream = YTDLDownloadStream(stream_info)

        try:
            super().__init__(
                cast(Any, self._download),
                pipe=True,
                before_options=FFMPEG_OPTIONS.get("before_options"),
                options=FFMPEG_OPTIONS.get("options"),
            )
        except Exception:
            self._download.stop()
            raise

    def cleanup(self) -> None:
        # Ending the download first lets ffmpeg's pipe writer thread exit cleanly
        download = getattr(self, "_download", None)
        if download is not None:
            download.stop()

        super().cleanup()


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

    @classmethod
    def _sanitize(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Make an info dict JSON-serializable, to pass it to a yt-dlp process."""

        return cast(dict[str, Any], cls.ytdl.sanitize_info(cast(Any, data)))

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
                track.stream_info = cls._sanitize(data)
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
        track.stream_info = cls._sanitize(data)
        track.resolved_at = time.monotonic()

    @classmethod
    def get_audio_source(
        cls, track: Track, volume: float = 0.5
    ) -> discord.PCMVolumeTransformer[YTDLPipeAudio]:
        """
        Create an audio source from a Track object.

        Args:
            track: Track object to create source from
            volume: Initial volume (0.0 to 1.0)

        Returns:
            Discord audio source ready to play
        """

        if not track.stream_info:
            raise AudioError(f"Track {track.title} has no stream info")

        source = YTDLPipeAudio(track.stream_info)

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
