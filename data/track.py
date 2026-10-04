from dataclasses import dataclass
import time
import discord

# YouTube stream URLs expire after ~6 hours, re-resolve them well before that
STREAM_URL_TTL = 3600


@dataclass
class Track:
    """
    Represents a music track.

    `source` is what yt-dlp resolves when the track is about to play: a video
    URL, or a search query for tracks found by metadata.
    The stream URL is resolved lazily, so queued tracks never hold expired URLs.
    """

    title: str
    source: str
    duration: int  # in seconds, 0 when unknown
    thumbnail: str | None = None
    uploader: str | None = None
    requester: discord.Member | None = None
    stream_url: str | None = None
    resolved_at: float = 0.0

    @property
    def needs_resolving(self) -> bool:
        """Whether the stream URL is missing or may have expired."""

        return (
            self.stream_url is None
            or time.monotonic() - self.resolved_at > STREAM_URL_TTL
        )

    @property
    def link(self) -> str:
        """Markdown link to the track, or its bare title if it has no URL yet."""

        if self.source.startswith("http"):
            return f"[{self.title}]({self.source})"

        return self.title

    @property
    def duration_formatted(self) -> str:
        """Returns formatted duration (MM:SS or HH:MM:SS)."""

        if self.duration <= 0:
            return "Unknown"

        hours, remainder = divmod(self.duration, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"

        return f"{minutes}:{seconds:02d}"
