from dataclasses import dataclass
import discord


@dataclass
class Track:
    """Represents a music track."""

    title: str
    url: str
    webpage_url: str
    duration: int  # in seconds
    thumbnail: str | None = None
    uploader: str | None = None
    requester: discord.Member | None = None

    @property
    def duration_formatted(self) -> str:
        """Returns formatted duration (MM:SS or HH:MM:SS)."""

        hours, remainder = divmod(self.duration, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"

        return f"{minutes}:{seconds:02d}"
