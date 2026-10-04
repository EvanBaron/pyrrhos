import json
import re
from dataclasses import dataclass
from typing import Any
import aiohttp
import discord
from data.track import Track
from data.exceptions import DownloadError

SPOTIFY_URL_REGEX: re.Pattern[str] = re.compile(
    r"(?:https?://)?open\.spotify\.com/(?:intl-[\w-]+/)?(track|album|playlist)/([A-Za-z0-9]+)"
)
NEXT_DATA_REGEX: re.Pattern[str] = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-us,en;q=0.5",
}


@dataclass
class SpotifyTrack:
    """Metadata of a Spotify track, used to find it on YouTube."""

    title: str
    artists: str
    duration: int

    @property
    def search_query(self) -> str:
        """YouTube search query matching this track."""

        return f"ytsearch1:{self.artists} - {self.title}"

    def to_track(self, requester: discord.Member) -> Track:
        """Queueable track, resolved on YouTube when it is about to play."""

        return Track(
            title=self.title,
            source=self.search_query,
            duration=self.duration,
            uploader=self.artists,
            requester=requester,
        )


@dataclass
class SpotifyCollection:
    """A resolved Spotify link (a single track, an album or a playlist)."""

    kind: str
    name: str
    tracks: list[SpotifyTrack]


class SpotifyResolver:
    """
    Resolves Spotify links to track metadata through the public embed page,
    which does not require API credentials.
    """

    @staticmethod
    async def _resolve_short_link(session: aiohttp.ClientSession, url: str) -> str:
        """Follow spotify.link / spotify.app.link redirects to the open.spotify.com URL."""

        async with session.get(url, allow_redirects=True) as response:
            return str(response.url)

    @classmethod
    async def resolve(cls, url: str) -> SpotifyCollection:
        """
        Fetch the metadata of a Spotify track, album or playlist.

        Args:
            url: Spotify URL

        Returns:
            The resolved collection (a single-track collection for track links)

        Raises:
            DownloadError: If the link is invalid or the metadata cannot be fetched
        """

        timeout = aiohttp.ClientTimeout(total=15)

        try:
            async with aiohttp.ClientSession(
                headers=HEADERS, timeout=timeout
            ) as session:
                match = SPOTIFY_URL_REGEX.search(url)
                if not match:
                    match = SPOTIFY_URL_REGEX.search(
                        await cls._resolve_short_link(session, url)
                    )
                if not match:
                    raise DownloadError("Unsupported Spotify link")

                kind, spotify_id = match.groups()

                async with session.get(
                    f"https://open.spotify.com/embed/{kind}/{spotify_id}"
                ) as response:
                    if response.status != 200:
                        raise DownloadError(
                            f"Spotify returned HTTP {response.status} for this link"
                        )
                    html = await response.text()
        except aiohttp.ClientError as exception:
            raise DownloadError(f"Could not reach Spotify: {exception}") from exception

        data_match = NEXT_DATA_REGEX.search(html)
        if not data_match:
            raise DownloadError("Could not read Spotify metadata")

        try:
            entity: dict[str, Any] = json.loads(data_match.group(1))["props"][
                "pageProps"
            ]["state"]["data"]["entity"]
        except (KeyError, TypeError, json.JSONDecodeError) as exception:
            raise DownloadError("Could not read Spotify metadata") from exception

        name = entity.get("name") or entity.get("title") or "Unknown"

        if kind == "track":
            artists = ", ".join(artist["name"] for artist in entity.get("artists", []))
            tracks = [
                SpotifyTrack(
                    title=name,
                    artists=artists,
                    duration=int(entity.get("duration", 0)) // 1000,
                )
            ]
        else:
            tracks = [
                SpotifyTrack(
                    title=item.get("title", ""),
                    artists=item.get("subtitle", "").replace("\xa0", " "),
                    duration=int(item.get("duration", 0)) // 1000,
                )
                for item in entity.get("trackList", [])
                if item.get("title") and item.get("isPlayable", True)
            ]

        if not tracks:
            raise DownloadError(f"This Spotify {kind} has no playable tracks")

        return SpotifyCollection(kind=kind, name=name, tracks=tracks)
