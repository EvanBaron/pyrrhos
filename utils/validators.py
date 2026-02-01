import re
from data.constants import MAX_TRACK_DURATION, MAX_QUEUE_SIZE


class Validators:
    """Validation utilities for music bot."""

    # URL patterns
    YOUTUBE_REGEX: re.Pattern[str] = re.compile(
        r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
    )
    SPOTIFY_REGEX: re.Pattern[str] = re.compile(
        r"(https?://)?(open\.)?spotify\.com/(track|playlist|album)/.+"
    )
    SOUNDCLOUD_REGEX: re.Pattern[str] = re.compile(
        r"(https?://)?(www\.)?soundcloud\.com/.+"
    )

    @staticmethod
    def is_url(text: str) -> bool:
        """Check if text is a URL."""
        url_pattern = re.compile(
            r"^https?://" +
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|" +
            r"localhost|" +
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})" +
            r"(?::\d+)?" +
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

        return url_pattern.match(text) is not None

    @staticmethod
    def is_youtube_url(text: str) -> bool:
        """Check if URL is a YouTube link."""

        return Validators.YOUTUBE_REGEX.match(text) is not None

    @staticmethod
    def is_spotify_url(text: str) -> bool:
        """Check if URL is a Spotify link."""

        return Validators.SPOTIFY_REGEX.match(text) is not None

    @staticmethod
    def is_soundcloud_url(text: str) -> bool:
        """Check if URL is a SoundCloud link."""

        return Validators.SOUNDCLOUD_REGEX.match(text) is not None

    @staticmethod
    def validate_duration(duration: int) -> bool:
        """
        Validate track duration.

        Args:
            duration: Duration in seconds

        Returns:
            True if duration is valid
        """

        return 0 < duration <= MAX_TRACK_DURATION

    @staticmethod
    def validate_queue_size(queue_size: int) -> bool:
        """
        Validate queue size.

        Args:
            queue_size: Current queue size

        Returns:
            True if queue can accept more tracks
        """

        return queue_size < MAX_QUEUE_SIZE

    @staticmethod
    def validate_volume(volume: int) -> bool:
        """
        Validate volume level.

        Args:
            volume: Volume level (0-100)

        Returns:
            True if volume is valid
        """

        return 0 <= volume <= 100

    @staticmethod
    def sanitize_search_query(query: str) -> str:
        """
        Sanitize search query.

        Args:
            query: Search query

        Returns:
            Sanitized query
        """

        query = " ".join(query.split())

        return query[:200]
