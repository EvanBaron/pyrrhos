import asyncio
import discord
from data.constants import VOICE_TIMEOUT
from data.track import Track
from data.queue import MusicQueue
from data.exceptions import VoiceError
from utils.audio import AudioPlayer


class GuildState:
    """Manages music playback state for a single guild."""

    def __init__(self, guild: discord.Guild):
        self.guild: discord.Guild = guild
        self.queue: MusicQueue = MusicQueue()
        self.voice_client: discord.VoiceClient | None = None
        self.player: AudioPlayer | None = None
        self.current_track: Track | None = None
        self.text_channel: discord.TextChannel | None = None

        # Playback control
        self._is_playing: bool = False
        self._skip_votes: set[int] = set()

        # Auto-disconnect timer
        self._disconnect_timer: asyncio.Task[None] | None = None
        self._timeout: int = VOICE_TIMEOUT

    @property
    def is_connected(self) -> bool:
        """Check if bot is connected to voice."""

        return self.voice_client is not None and self.voice_client.is_connected()

    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""

        return self.player is not None and self.player.is_playing()

    @property
    def is_paused(self) -> bool:
        """Check if audio is paused."""

        return self.player is not None and self.player.is_paused()

    async def connect(self, channel: discord.VoiceChannel) -> discord.VoiceClient:
        """
        Connect to a voice channel.

        Args:
            channel: Voice channel to connect to

        Returns:
            Voice client

        Raises:
            VoiceError: If connection fails
        """

        if self.is_connected and self.voice_client:
            if self.voice_client.channel.id == channel.id:
                return self.voice_client
            await self.voice_client.move_to(channel)
        else:
            try:
                self.voice_client = await channel.connect()
                self.player = AudioPlayer(self.voice_client)
            except asyncio.TimeoutError as exc:
                raise VoiceError(f"Could not connect to {channel.name}") from exc
            except discord.ClientException as exception:
                raise VoiceError(f"Failed to connect: {str(exception)}") from exception

        # Cancel disconnect timer if exists
        if self._disconnect_timer and not self._disconnect_timer.done():
            self._disconnect_timer.cancel()

        return self.voice_client

    async def disconnect(self) -> None:
        """Disconnect from voice channel and cleanup."""

        if self._disconnect_timer and not self._disconnect_timer.done():
            self._disconnect_timer.cancel()

        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None
            self.player = None

        self.current_track = None
        self._is_playing = False
        self._skip_votes.clear()

    async def play_next(self) -> None:
        """Play the next track in queue."""

        if self.queue.loop and self.current_track:
            next_track = self.current_track
        else:
            next_track = self.queue.get_next()

        if next_track is None:
            self._is_playing = False
            await self._start_disconnect_timer()
            return

        self.current_track = next_track
        self._skip_votes.clear()

        try:
            # Play track with callback to play next when done
            if self.player:
                await self.player.play(
                    next_track, after=lambda error: self._after_track(error)
                )
                self._is_playing = True

            if self.text_channel:
                await self._send_now_playing()

        except Exception as exception:
            # If playback fails, try next track
            if self.text_channel:
                await self.text_channel.send(
                    f"❌ Error playing `{next_track.title}`: {str(exception)}"
                )
            await self.play_next()

    def _after_track(self, error: Exception | None) -> None:
        """Callback after track finishes playing."""

        if error:
            print(f"Player error: {error}")

        # Schedule next track in event loop
        if self.voice_client:
            asyncio.run_coroutine_threadsafe(self.play_next(), self.voice_client.loop)

    async def _send_now_playing(self) -> None:
        """Send now playing embed to text channel."""

        if not self.current_track or not self.text_channel:
            return

        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"[{self.current_track.title}]({self.current_track.webpage_url})",
            color=discord.Color.blue(),
        )

        if self.current_track.thumbnail:
            embed.set_thumbnail(url=self.current_track.thumbnail)

        embed.add_field(
            name="Duration", value=self.current_track.duration_formatted, inline=True
        )

        if self.current_track.requester:
            embed.add_field(
                name="Requested by",
                value=self.current_track.requester.name,
                inline=True,
            )

        if self.current_track.uploader:
            embed.add_field(
                name="Uploader", value=self.current_track.uploader, inline=True
            )

        if len(self.queue) > 0:
            embed.add_field(
                name="Up Next",
                value=f"{len(self.queue)} track(s) in queue",
                inline=False,
            )

        await self.text_channel.send(embed=embed)

    async def _start_disconnect_timer(self) -> None:
        """Start auto-disconnect timer."""

        if self._disconnect_timer and not self._disconnect_timer.done():
            self._disconnect_timer.cancel()

        self._disconnect_timer = asyncio.create_task(self._auto_disconnect())

    async def _auto_disconnect(self) -> None:
        """Auto-disconnect after timeout of inactivity."""

        await asyncio.sleep(self._timeout)

        if not self.is_playing and self.is_connected:
            if self.text_channel:
                await self.text_channel.send(
                    f"⏸️ Disconnecting due to {self._timeout // 60} minutes of inactivity."
                )
            await self.disconnect()

    def add_skip_vote(self, user_id: int) -> tuple[int, int]:
        """
        Add a skip vote.

        Args:
            user_id: ID of user voting to skip

        Returns:
            Tuple of (current votes, required votes)
        """

        self._skip_votes.add(user_id)

        # Calculate required votes (50% of listeners)
        if self.voice_client and self.voice_client.channel:
            # Don't count bots
            listeners = [
                member for member in self.voice_client.channel.members if not member.bot
            ]
            required = len(listeners) // 2
        else:
            required = 1

        return len(self._skip_votes), required

    def clear_skip_votes(self) -> None:
        """Clear all skip votes."""

        self._skip_votes.clear()


class StateManager:
    """Manages guild states across the bot."""

    def __init__(self):
        self._states: dict[int, GuildState] = {}

    def get_state(self, guild: discord.Guild) -> GuildState:
        """
        Get or create a guild state.

        Args:
            guild: Discord guild

        Returns:
            GuildState for the guild
        """

        if guild.id not in self._states:
            self._states[guild.id] = GuildState(guild)

        return self._states[guild.id]

    async def cleanup_state(self, guild_id: int) -> None:
        """
        Cleanup and remove a guild state.

        Args:
            guild_id: ID of guild to cleanup
        """

        if guild_id in self._states:
            state = self._states[guild_id]
            await state.disconnect()
            del self._states[guild_id]

    async def cleanup_all(self) -> None:
        """Cleanup all guild states."""

        for guild_id in list(self._states.keys()):
            await self.cleanup_state(guild_id)
