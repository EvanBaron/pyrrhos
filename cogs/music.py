from typing import override
import discord
from discord import app_commands
from discord.ext import commands
from utils.state import StateManager
from utils.audio import YTDLSource
from utils.validators import Validators
from data.exceptions import DownloadError, VoiceError, QueueError
from data.constants import (
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    EMOJI_PLAY,
    EMOJI_PAUSE,
    EMOJI_STOP,
    EMOJI_SKIP,
    EMOJI_SHUFFLE,
    EMOJI_LOOP,
    EMOJI_LOOP_ONE,
    EMOJI_MUSIC,
    EMOJI_QUEUE,
    MSG_NOT_IN_VOICE,
    MSG_BOT_NOT_IN_VOICE,
    MSG_DIFFERENT_VOICE,
    MSG_QUEUE_EMPTY,
    MSG_NOTHING_PLAYING,
    MSG_ALREADY_PAUSED,
    MSG_NOT_PAUSED,
    MAX_TRACK_DURATION,
    MAX_QUEUE_SIZE,
)


class Music(commands.Cog, name="music"):
    """Music playback commands."""

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.state_manager: StateManager = StateManager()

    @override
    async def cog_unload(self) -> None:
        """Cleanup when cog is unloaded."""

        await self.state_manager.cleanup_all()

    def _check_voice_state(self, interaction: discord.Interaction) -> str | None:
        """
        Check if user and bot are in valid voice states.

        Returns:
            Error message if invalid, None if valid
        """

        if not isinstance(interaction.user, discord.Member):
            return MSG_NOT_IN_VOICE

        if not interaction.user.voice:
            return MSG_NOT_IN_VOICE

        if not interaction.guild:
            return "❌ This command can only be used in a server."

        state = self.state_manager.get_state(interaction.guild)

        if state.is_connected and state.voice_client:
            if (
                interaction.user.voice.channel
                and interaction.user.voice.channel.id != state.voice_client.channel.id
            ):
                return MSG_DIFFERENT_VOICE

        return None

    @app_commands.command(name="play", description="Play a song or add it to the queue")
    @app_commands.describe(query="Song name or URL to play")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        """Play a song from YouTube or other sources."""

        await interaction.response.defer(thinking=True)

        if not isinstance(interaction.user, discord.Member):
            await interaction.followup.send(MSG_NOT_IN_VOICE, ephemeral=True)
            return

        if not interaction.guild:
            await interaction.followup.send(
                "❌ This command can only be used in a server.", ephemeral=True
            )
            return

        error = self._check_voice_state(interaction)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        state = self.state_manager.get_state(interaction.guild)

        if isinstance(interaction.channel, discord.TextChannel):
            state.text_channel = interaction.channel

        try:
            if not state.is_connected:
                if not interaction.user.voice or not interaction.user.voice.channel:
                    await interaction.followup.send(MSG_NOT_IN_VOICE, ephemeral=True)
                    return

                if not isinstance(interaction.user.voice.channel, discord.VoiceChannel):
                    await interaction.followup.send(
                        "❌ I can only join voice channels, not stage channels.",
                        ephemeral=True,
                    )
                    return

                await state.connect(interaction.user.voice.channel)

            if not Validators.validate_queue_size(len(state.queue)):
                await interaction.followup.send(
                    f"❌ Queue is full! Maximum size is {MAX_QUEUE_SIZE} tracks.",
                    ephemeral=True,
                )
                return

            if not Validators.is_url(query):
                query = f"ytsearch:{Validators.sanitize_search_query(query)}"

            track = await YTDLSource.from_url(query, interaction.user)

            if not Validators.validate_duration(track.duration):
                await interaction.followup.send(
                    f"❌ Track is too long! Maximum duration is {MAX_TRACK_DURATION // 60} minutes.",
                    ephemeral=True,
                )

                return

            position = state.queue.add(track)

            embed = discord.Embed(
                title=f"{EMOJI_MUSIC} Added to Queue",
                description=f"[{track.title}]({track.webpage_url})",
                color=COLOR_SUCCESS,
            )

            if track.thumbnail:
                embed.set_thumbnail(url=track.thumbnail)

            embed.add_field(
                name="Duration", value=track.duration_formatted, inline=True
            )

            embed.add_field(
                name="Position in Queue", value=f"#{position + 1}", inline=True
            )

            if track.uploader:
                embed.add_field(name="Uploader", value=track.uploader, inline=True)

            await interaction.followup.send(embed=embed)

            if not state.is_playing:
                await state.play_next()

        except DownloadError as error:
            await interaction.followup.send(
                f"❌ Download error: {str(error)}", ephemeral=True
            )
        except VoiceError as error:
            await interaction.followup.send(
                f"❌ Voice error: {str(error)}", ephemeral=True
            )
        except Exception as exception:
            await interaction.followup.send(
                f"❌ An unexpected error occurred: {str(exception)}", ephemeral=True
            )

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction) -> None:
        """Pause current playback."""

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )

            return

        error = self._check_voice_state(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        state = self.state_manager.get_state(interaction.guild)

        if not state.is_playing:
            await interaction.response.send_message(MSG_NOTHING_PLAYING, ephemeral=True)
            return

        if state.is_paused:
            await interaction.response.send_message(MSG_ALREADY_PAUSED, ephemeral=True)
            return

        if state.player:
            state.player.pause()
        await interaction.response.send_message(f"{EMOJI_PAUSE} Paused playback.")

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction) -> None:
        """Resume paused playback."""

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )

            return

        error = self._check_voice_state(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        state = self.state_manager.get_state(interaction.guild)

        if not state.is_paused:
            await interaction.response.send_message(MSG_NOT_PAUSED, ephemeral=True)
            return

        if state.player:
            state.player.resume()
        await interaction.response.send_message(f"{EMOJI_PLAY} Resumed playback.")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction) -> None:
        """Skip current track."""

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )

            return

        error = self._check_voice_state(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        state = self.state_manager.get_state(interaction.guild)

        if not state.is_playing:
            await interaction.response.send_message(MSG_NOTHING_PLAYING, ephemeral=True)
            return

        current_votes, required_votes = state.add_skip_vote(interaction.user.id)

        if current_votes >= required_votes and state.player and state.current_track:
            state.player.stop()
            await interaction.response.send_message(
                f"{EMOJI_SKIP} Skipped **{state.current_track.title}**"
            )
        else:
            await interaction.response.send_message(
                f"🗳️ Skip vote added. ({current_votes}/{required_votes} votes needed)"
            )

    @app_commands.command(name="stop", description="Stop playback and clear the queue")
    async def stop(self, interaction: discord.Interaction) -> None:
        """Stop playback and clear queue."""

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )

            return

        error = self._check_voice_state(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        state = self.state_manager.get_state(interaction.guild)

        if not state.is_connected:
            await interaction.response.send_message(
                MSG_BOT_NOT_IN_VOICE, ephemeral=True
            )
            return

        state.queue.clear()
        if state.player:
            state.player.stop()
        await interaction.response.send_message(
            f"{EMOJI_STOP} Stopped playback and cleared the queue."
        )

    @app_commands.command(name="queue", description="Show the current queue")
    @app_commands.describe(page="Page number to display")
    async def queue(self, interaction: discord.Interaction, page: int = 1) -> None:
        """Display the current queue."""

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )

            return

        state = self.state_manager.get_state(interaction.guild)

        if state.queue.is_empty and not state.current_track:
            await interaction.response.send_message(MSG_QUEUE_EMPTY, ephemeral=True)
            return

        items_per_page = 10
        total_pages = max(1, (len(state.queue) + items_per_page - 1) // items_per_page)
        page = max(1, min(page, total_pages))

        embed = discord.Embed(
            title=f"{EMOJI_QUEUE} Queue for {interaction.guild.name}",
            color=COLOR_PRIMARY,
        )

        if state.current_track:
            current = state.current_track
            requester_name = current.requester.name if current.requester else "Unknown"
            embed.add_field(
                name="🎵 Now Playing",
                value=(
                    f"[{current.title}]({current.webpage_url})\n"
                    f"`{current.duration_formatted}` | Requested by {requester_name}"
                ),
                inline=False,
            )

        if not state.queue.is_empty:
            start_idx = (page - 1) * items_per_page
            end_idx = min(start_idx + items_per_page, len(state.queue))

            queue_text = ""
            for i in range(start_idx, end_idx):
                track = state.queue[i]
                requester_name = track.requester.name if track.requester else "Unknown"
                queue_text += f"`{i + 1}.` [{track.title}]({track.webpage_url})\n"
                queue_text += f"     `{track.duration_formatted}` | {requester_name}\n"

            embed.add_field(
                name=f"📜 Up Next ({len(state.queue)} tracks)",
                value=queue_text or "No tracks in queue",
                inline=False,
            )

            total_duration = state.queue.get_total_duration()
            hours, remainder = divmod(total_duration, 3600)
            minutes, seconds = divmod(remainder, 60)

            stats = "**Total Duration:** "
            if hours > 0:
                stats += f"{hours}h {minutes}m {seconds}s"
            else:
                stats += f"{minutes}m {seconds}s"

            if total_pages > 1:
                stats += f"\n**Page:** {page}/{total_pages}"

            embed.add_field(name="ℹ️ Stats", value=stats, inline=False)

        loop_status: list[str] = []
        if state.queue.loop:
            loop_status.append("🔂 Loop: ON")
        if state.queue.loop_queue:
            loop_status.append("🔁 Loop Queue: ON")

        if loop_status:
            embed.set_footer(text=" | ".join(loop_status))

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="nowplaying", description="Show the currently playing song"
    )
    async def nowplaying(self, interaction: discord.Interaction) -> None:
        """Show currently playing track."""

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )

            return

        state = self.state_manager.get_state(interaction.guild)

        if not state.current_track:
            await interaction.response.send_message(MSG_NOTHING_PLAYING, ephemeral=True)
            return

        track = state.current_track

        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"[{track.title}]({track.webpage_url})",
            color=COLOR_PRIMARY,
        )

        if track.thumbnail:
            embed.set_image(url=track.thumbnail)

        embed.add_field(name="Duration", value=track.duration_formatted, inline=True)

        requester_name = track.requester.name if track.requester else "Unknown"
        embed.add_field(name="Requested by", value=requester_name, inline=True)

        if track.uploader:
            embed.add_field(name="Uploader", value=track.uploader, inline=True)

        if state.player:
            embed.add_field(name="Volume", value=f"{state.player.volume}%", inline=True)

        loop_status: list[str] = []
        if state.queue.loop:
            loop_status.append("🔂 Loop")
        if state.queue.loop_queue:
            loop_status.append("🔁 Loop Queue")

        if loop_status:
            embed.set_footer(text=" | ".join(loop_status))

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="Set the playback volume")
    @app_commands.describe(volume="Volume level (0-100)")
    async def volume(self, interaction: discord.Interaction, volume: int) -> None:
        """Set playback volume."""

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )

            return

        error = self._check_voice_state(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        state = self.state_manager.get_state(interaction.guild)

        if not state.is_playing:
            await interaction.response.send_message(MSG_NOTHING_PLAYING, ephemeral=True)
            return

        if not Validators.validate_volume(volume):
            await interaction.response.send_message(
                "❌ Volume must be between 0 and 100.", ephemeral=True
            )
            return

        if state.player:
            state.player.volume = volume

        # Choose emoji based on volume
        if volume == 0:
            emoji = "🔇"
        elif volume < 33:
            emoji = "🔉"
        elif volume < 66:
            emoji = "🔊"
        else:
            emoji = "📢"

        await interaction.response.send_message(f"{emoji} Volume set to **{volume}%**")

    @app_commands.command(
        name="loop", description="Toggle loop mode for the current song"
    )
    async def loop(self, interaction: discord.Interaction) -> None:
        """Toggle loop mode."""

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )

            return

        state = self.state_manager.get_state(interaction.guild)

        state.queue.loop = not state.queue.loop

        if state.queue.loop:
            state.queue.loop_queue = False
            await interaction.response.send_message(
                f"{EMOJI_LOOP_ONE} Loop mode **enabled** for current track."
            )
        else:
            await interaction.response.send_message(
                f"{EMOJI_LOOP_ONE} Loop mode **disabled**."
            )

    @app_commands.command(
        name="loopqueue", description="Toggle loop mode for the entire queue"
    )
    async def loopqueue(self, interaction: discord.Interaction) -> None:
        """Toggle queue loop mode."""

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )

            return

        state = self.state_manager.get_state(interaction.guild)

        state.queue.loop_queue = not state.queue.loop_queue

        if state.queue.loop_queue:
            state.queue.loop = False
            await interaction.response.send_message(
                f"{EMOJI_LOOP} Queue loop mode **enabled**."
            )
        else:
            await interaction.response.send_message(
                f"{EMOJI_LOOP} Queue loop mode **disabled**."
            )

    @app_commands.command(name="shuffle", description="Shuffle the queue")
    async def shuffle(self, interaction: discord.Interaction) -> None:
        """Shuffle the queue."""

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )

            return

        error = self._check_voice_state(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        state = self.state_manager.get_state(interaction.guild)

        if state.queue.is_empty:
            await interaction.response.send_message(MSG_QUEUE_EMPTY, ephemeral=True)
            return

        state.queue.shuffle()
        await interaction.response.send_message(
            f"{EMOJI_SHUFFLE} Shuffled **{len(state.queue)}** tracks in the queue."
        )

    @app_commands.command(name="clear", description="Clear all songs from the queue")
    async def clear(self, interaction: discord.Interaction) -> None:
        """Clear the queue."""

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )

            return

        error = self._check_voice_state(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        state = self.state_manager.get_state(interaction.guild)

        if state.queue.is_empty:
            await interaction.response.send_message(MSG_QUEUE_EMPTY, ephemeral=True)
            return

        count = len(state.queue)
        state.queue.clear()
        await interaction.response.send_message(
            f"🗑️ Cleared **{count}** tracks from the queue."
        )

    @app_commands.command(
        name="remove", description="Remove a specific song from the queue"
    )
    @app_commands.describe(position="Position of the song in the queue")
    async def remove(self, interaction: discord.Interaction, position: int) -> None:
        """Remove a track from queue."""

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )
            return

        error = self._check_voice_state(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        state = self.state_manager.get_state(interaction.guild)

        if state.queue.is_empty:
            await interaction.response.send_message(MSG_QUEUE_EMPTY, ephemeral=True)
            return

        try:
            index = position - 1
            track = state.queue.remove(index)
            await interaction.response.send_message(
                f"🗑️ Removed **{track.title}** from the queue."
            )
        except QueueError:
            await interaction.response.send_message(
                f"❌ Invalid position. Queue has {len(state.queue)} tracks.",
                ephemeral=True,
            )

    @app_commands.command(
        name="disconnect", description="Disconnect the bot from voice channel"
    )
    async def disconnect(self, interaction: discord.Interaction) -> None:
        """Disconnect from voice."""

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )

            return

        error = self._check_voice_state(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        state = self.state_manager.get_state(interaction.guild)

        if not state.is_connected:
            await interaction.response.send_message(
                MSG_BOT_NOT_IN_VOICE, ephemeral=True
            )

            return

        await state.disconnect()
        await interaction.response.send_message("👋 Disconnected from voice channel.")


async def setup(bot: commands.Bot) -> None:
    """Setup function to add cog to bot."""

    await bot.add_cog(Music(bot))
