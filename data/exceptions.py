class BotError(Exception):
    """Base exception for music bot errors."""

    pass


class AudioError(BotError):
    """Raised when audio playback fails."""

    pass


class DownloadError(AudioError):
    """Raised when downloading/extracting audio fails."""

    pass


class QueueError(BotError):
    """Raised when queue operations fail."""

    pass


class VoiceError(BotError):
    """Raised when voice connection operations fail."""

    pass
