from typing import override, Any
import discord
from discord.ext import commands
import traceback
from cogs.music import Music


class MusicBot(commands.Bot):
    """Custom bot class for the music bot."""

    def __init__(
        self,
        command_prefix: str,
        intents: discord.Intents,
        test_guild_id: int | None = None,
        **kwargs: Any,
    ):
        super().__init__(
            command_prefix=command_prefix, intents=intents, help_command=None, **kwargs
        )

        self.test_guild_id: int | None = test_guild_id
        self.initial_extensions: list[str] = [
            "cogs.debug",
            "cogs.general",
            "cogs.music",
        ]

    @override
    async def setup_hook(self) -> None:
        """Setup hook called when bot is starting up."""

        print("-" * 50)
        print("Starting Music Bot...")
        print("-" * 50)

        # Load all cogs
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                print(f"✓ Loaded extension: {extension}")
            except Exception:
                print(f"✗ Failed to load extension {extension}")
                traceback.print_exc()

        # Sync commands
        try:
            print("\nSyncing command tree...")

            if self.test_guild_id:
                # Sync to test guild
                guild = discord.Object(id=self.test_guild_id)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                print(
                    f"✓ Synced {len(synced)} command(s) to test guild (ID: {self.test_guild_id})"
                )
                print("  Commands will be available instantly in the test guild!")
            else:
                # Sync globally
                synced = await self.tree.sync()
                print(f"✓ Synced {len(synced)} command(s) globally")
                print("  ⚠️ Global commands may take up to 1 hour to appear")
        except Exception as exception:
            print(f"✗ Failed to sync commands: {exception}")
            traceback.print_exc()

        print("-" * 50)

    async def on_ready(self) -> None:
        """Called when bot is ready."""

        print(f"\n{'-' * 50}")
        print("Bot is ready!")
        if self.user:
            print(f"Logged in as: {self.user.name} (ID: {self.user.id})")

        print(f"Connected to {len(self.guilds)} guild(s)")

        if self.test_guild_id:
            print(f"Development Mode: Commands synced to guild {self.test_guild_id}")
        else:
            print("Production Mode: Commands synced globally")

        print(f"{'-' * 50}\n")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening, name="/play"
            ),
            status=discord.Status.online,
        )

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Called when bot joins a guild."""

        print(f"Joined new guild: {guild.name} (ID: {guild.id})")
        if self.test_guild_id and guild.id == self.test_guild_id:
            try:
                guild_obj = discord.Object(id=self.test_guild_id)
                self.tree.copy_global_to(guild=guild_obj)
                await self.tree.sync(guild=guild_obj)
                print("✓ Synced commands to test guild")
            except Exception as exception:
                print(f"✗ Failed to sync commands to test guild: {exception}")

        # Try to send a welcome message
        if (
            guild.system_channel
            and guild.system_channel.permissions_for(guild.me).send_messages
        ):
            embed = discord.Embed(
                title="🎵 Thanks for adding me!",
                description=(
                    "I'm a music bot that can play music from YouTube and other sources.\n\n"
                    "**Getting Started:**\n"
                    "• Use `/play <song>` to play music\n"
                    "• Use `/queue` to see what's playing\n"
                    "• Use `/help` to see all commands\n\n"
                    "Enjoy the music! 🎶"
                ),
                color=discord.Color.orange(),
            )

            try:
                await guild.system_channel.send(embed=embed)
            except Exception:
                pass

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Called when bot is removed from a guild."""

        print(f"Removed from guild: {guild.name} (ID: {guild.id})")

    @override
    async def on_command_error(
        self, context: commands.Context[Any], error: commands.CommandError
    ) -> None:
        """Global error handler for prefix commands."""

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await context.send(f"❌ Missing required argument: `{error.param.name}`")
        elif isinstance(error, commands.BadArgument):
            await context.send("❌ Invalid argument provided.")
        elif isinstance(error, commands.MissingPermissions):
            await context.send("❌ You don't have permission to use this command.")
        elif isinstance(error, commands.BotMissingPermissions):
            await context.send(
                "❌ I don't have the necessary permissions to execute this command."
            )
        else:
            print(f"Error in command {context.command}: {error}")
            traceback.print_exc()
            await context.send("❌ An error occurred while executing the command.")

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        """Global error handler for slash commands."""

        if isinstance(error, discord.app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"⏱️ This command is on cooldown. Try again in {error.retry_after:.1f}s.",
                ephemeral=True,
            )
        elif isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.", ephemeral=True
            )
        elif isinstance(error, discord.app_commands.BotMissingPermissions):
            await interaction.response.send_message(
                "❌ I don't have the necessary permissions to execute this command.",
                ephemeral=True,
            )
        elif isinstance(error, discord.app_commands.CheckFailure):
            await interaction.response.send_message(
                "❌ You cannot use this command.", ephemeral=True
            )
        else:
            print(f"Error in slash command: {error}")
            traceback.print_exc()

            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ An error occurred while executing the command.",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        "❌ An error occurred while executing the command.",
                        ephemeral=True,
                    )
            except Exception:
                pass

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Handle voice state updates."""

        if self.user and member.id == self.user.id:
            if before.channel and not after.channel:
                music_cog = self.get_cog("music")
                if isinstance(music_cog, Music):
                    await music_cog.state_manager.cleanup_state(member.guild.id)
                    print(f"Cleaned up state for guild: {member.guild.name}")


def create_bot(command_prefix: str, test_guild_id: int | None = None) -> MusicBot:
    """
    Create and configure the bot instance.

    Args:
        command_prefix: Prefix for text commands
        test_guild_id: Optional guild ID for instant command syncing (development)

    Returns:
        Configured MusicBot instance
    """

    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    intents.guilds = True

    bot = MusicBot(
        command_prefix=command_prefix,
        intents=intents,
        test_guild_id=test_guild_id,
        case_insensitive=True,
    )

    return bot
