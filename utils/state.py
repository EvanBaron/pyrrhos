import asyncio
import discord
from data.constants import VOICE_TIMEOUT
from data.track import Track
from data.queue import MusicQueue
from data.exceptions import VoiceError
from utils.audio import AudioPlayer, YTDLSource


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
        self._skip_votes: set[int] = set()
        self._skip_requested: bool = False
        self._playback_id: int = 0
        self._play_lock: asyncio.Lock = asyncio.Lock()

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

    @property
    def is_active(self) -> bool:
        """Check if a track is current (playing, paused or loading)."""

        return self.current_track is not None

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

        self._cancel_disconnect_timer()

        if self.is_connected and self.voice_client:
            if self.voice_client.channel.id != channel.id:
                await self.voice_client.move_to(channel)
            return self.voice_client

        stale_client = self.guild.voice_client
        if stale_client:
            await stale_client.disconnect(force=True)

        try:
            self.voice_client = await channel.connect()
            self.player = AudioPlayer(self.voice_client)
        except asyncio.TimeoutError as exc:
            raise VoiceError(f"Could not connect to {channel.name}") from exc
        except discord.ClientException as exception:
            raise VoiceError(f"Failed to connect: {str(exception)}") from exception

        return self.voice_client

    async def disconnect(self) -> None:
        """Disconnect from voice channel and reset playback."""

        self._cancel_disconnect_timer()
        self._playback_id += 1

        voice_client = self.voice_client
        self.voice_client = None
        self.player = None

        if voice_client:
            await voice_client.disconnect(force=True)

        self.queue.clear()
        self.queue.loop = False
        self.queue.loop_queue = False
        self.current_track = None
        self._skip_requested = False
        self._skip_votes.clear()

    def stop(self) -> None:
        """Stop playback and clear the queue, staying connected."""

        self._playback_id += 1
        self.queue.clear()
        self.current_track = None
        self._skip_votes.clear()

        if self.player:
            self.player.stop()

        self._start_disconnect_timer()

    def skip(self) -> None:
        """Skip the current track, even when it is looping."""

        self._skip_requested = True

        if self.player and (self.player.is_playing() or self.player.is_paused()):
            # The source's after callback plays the next track
            self.player.stop()

    async def ensure_playing(self) -> None:
        """Start playing the queue if no track is current."""

        async with self._play_lock:
            if self.current_track is None:
                await self._play_next()

    async def _advance(self, playback_id: int) -> None:
        """Play the next track once the source `playback_id` has finished."""

        async with self._play_lock:
            # The track was replaced or stopped meanwhile
            if playback_id == self._playback_id:
                await self._play_next()

    async def _play_next(self) -> None:
        finished = self.current_track
        replay = False

        if finished is not None:
            if self.queue.loop and not self._skip_requested:
                replay = True
                self.queue.add_next(finished)
            elif self.queue.loop_queue:
                self.queue.add(finished)

        self._skip_requested = False
        self._skip_votes.clear()

        for _ in range(len(self.queue)):
            next_track = self.queue.get_next()
            if next_track is None or not self.player:
                break

            self.current_track = next_track
            self._cancel_disconnect_timer()

            try:
                if next_track.needs_resolving:
                    await YTDLSource.resolve(next_track)

                # Stopped or disconnected while resolving the stream
                if self.current_track is not next_track or not self.player:
                    return

                self._playback_id += 1
                playback_id = self._playback_id
                loop = asyncio.get_running_loop()

                await self.player.play(
                    next_track,
                    after=lambda error: self._after_track(error, playback_id, loop),
                )
            except Exception as exception:
                self.current_track = None
                if self.text_channel:
                    await self.text_channel.send(
                        f"❌ Error playing `{next_track.title}`: {str(exception)}"
                    )
                continue

            # Do not announce the same track every time it loops
            if self.text_channel and not replay:
                await self._send_now_playing()

            return

        self.current_track = None
        self._start_disconnect_timer()

    def _after_track(
        self,
        error: Exception | None,
        playback_id: int,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Callback after track finishes playing (called from the audio thread)."""

        if error:
            print(f"Player error: {error}")

        asyncio.run_coroutine_threadsafe(self._advance(playback_id), loop)

    async def _send_now_playing(self) -> None:
        """Send now playing embed to text channel."""

        if not self.current_track or not self.text_channel:
            return

        embed = discord.Embed(
            title="🎵 Now Playing",
            description=self.current_track.link,
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

    def _cancel_disconnect_timer(self) -> None:
        """Cancel the auto-disconnect timer, if running."""

        if self._disconnect_timer and not self._disconnect_timer.done():
            self._disconnect_timer.cancel()

    def _start_disconnect_timer(self) -> None:
        """Start auto-disconnect timer."""

        self._cancel_disconnect_timer()
        self._disconnect_timer = asyncio.create_task(self._auto_disconnect())

    async def _auto_disconnect(self) -> None:
        """Auto-disconnect after timeout of inactivity."""

        await asyncio.sleep(self._timeout)

        if not self.is_active and self.is_connected:
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
            required = max(1, (len(listeners) + 1) // 2)
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
