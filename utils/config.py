import os
from dotenv import load_dotenv

ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
if ENVIRONMENT == "prod":
    dotenv_path = ".env.production"
else:
    dotenv_path = ".env.development"

load_dotenv(dotenv_path)

# Bot Configuration
TOKEN = os.getenv("DISCORD_TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

# Test Guild Configuration
test_guild_id = os.getenv("TEST_GUILD_ID")
if test_guild_id:
    try:
        test_guild_id = int(test_guild_id)
    except ValueError:
        test_guild_id = None

# FFmpeg Configuration
FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -b:a 128k",
}

# yt-dlp Configuration
COOKIES_FILE = os.getenv("COOKIES_FILE", "cookies.txt")

YTDL_FORMAT_OPTIONS = {
    "format": "bestaudio/best",
    "extractaudio": True,
    "audioformat": "mp3",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
    "force-ipv4": True,
    "prefer_ffmpeg": True,
    "keepvideo": False,
    "extract_flat": False,
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "cookiefile": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
    "age_limit": None,
    "http_chunk_size": 10485760,
}

# Additional headers to avoid blocks
YTDL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-us,en;q=0.5",
    "Sec-Fetch-Mode": "navigate",
}

# Audio Configuration
MAX_VOLUME = 100
DEFAULT_VOLUME = 50
AUDIO_TIMEOUT = 300
