import discord
from discord import app_commands
from discord.ext import commands
from data.constants import BOT_NAME, BOT_VERSION, BOT_DESCRIPTION


class General(commands.GroupCog, name="general"):
    """General bot commands."""

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

    @app_commands.command(name="help", description="Show help information")
    async def help(self, interaction: discord.Interaction):
        """Display help information."""

        embed = discord.Embed(
            title=f"🎵 {BOT_NAME} - Help",
            description=BOT_DESCRIPTION,
            color=discord.Color.blue(),
        )

        music_commands = [
            ("**`/play <query>`**", "Play a song or add it to queue"),
            ("**`/pause`**", "Pause the current song"),
            ("**`/resume`**", "Resume playback"),
            ("**`/skip`**", "Skip the current song"),
            ("**`/stop`**", "Stop playback and clear queue"),
            ("**`/queue [page]`**", "Show the current queue"),
            ("**`/nowplaying`**", "Show current song info"),
            ("**`/volume <0-100>`**", "Set playback volume"),
            ("**`/loop`**", "Toggle loop for current song"),
            ("**`/loopqueue`**", "Toggle loop for entire queue"),
            ("**`/shuffle`**", "Shuffle the queue"),
            ("**`/clear`**", "Clear the queue"),
            ("**`/remove <position>`**", "Remove a song from queue"),
            ("**`/disconnect`**", "Disconnect from voice"),
        ]

        music_text = "\n".join([f"{cmd} - {desc}" for cmd, desc in music_commands])
        embed.add_field(name="🎵 Music Commands", value=music_text, inline=False)

        general_commands = [
            ("**`/help`**", "Show this help message"),
            ("**`/info`**", "Show bot information"),
            ("**`/invite`**", "Get bot invite link"),
        ]

        general_text = "\n".join([f"{cmd} - {desc}" for cmd, desc in general_commands])
        embed.add_field(name="ℹ️ General Commands", value=general_text, inline=False)

        debug_commands = [
            ("**`/ping`**", "Check bot latency"),
            ("**`/uptime`**", "Show bot uptime"),
            ("**`/stats`**", "Show bot statistics"),
        ]

        debug_text = "\n".join([f"{cmd} - {desc}" for cmd, desc in debug_commands])
        embed.add_field(name="🔧 Debug Commands", value=debug_text, inline=False)

        embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="info", description="Show bot information")
    async def info(self, interaction: discord.Interaction):
        """Display bot information."""

        embed = discord.Embed(
            title=f"ℹ️ About {BOT_NAME}",
            description=BOT_DESCRIPTION,
            color=discord.Color.orange(),
        )

        embed.add_field(name="Version", value=f"`{BOT_VERSION}`", inline=True)

        embed.add_field(name="Servers", value=f"`{len(self.bot.guilds)}`", inline=True)

        embed.add_field(name="Python", value="`discord.py 2.x`", inline=True)

        features = [
            "🎵 YouTube & URL support",
            "📜 Queue management",
            "🔁 Loop modes",
            "🔀 Shuffle",
            "🔊 Volume control",
            "⏯️ Playback controls",
        ]

        embed.add_field(name="Features", value="\n".join(features), inline=False)

        embed.add_field(
            name="Support", value="Use `/help` for command list", inline=False
        )

        if self.bot.user and self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="invite", description="Get the bot invite link")
    async def invite(self, interaction: discord.Interaction):
        """Generate and send bot invite link."""

        if not self.bot.user:
            await interaction.response.send_message(
                "Bot is not ready yet.", ephemeral=True
            )

            return

        # Generate OAuth2 URL with required permissions
        permissions = discord.Permissions(
            connect=True,
            speak=True,
            use_voice_activation=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
        )

        invite_url = discord.utils.oauth_url(
            self.bot.user.id,
            permissions=permissions,
            scopes=["bot", "applications.commands"],
        )

        embed = discord.Embed(
            title="📨 Invite Me!",
            description=f"Click [here]({invite_url}) to add me to your server!",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="Required Permissions",
            value=(
                "• Connect to voice channels\n"
                "• Speak in voice channels\n"
                "• Send messages\n"
                "• Embed links\n"
                "• Use slash commands"
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function to add cog to bot."""

    await bot.add_cog(General(bot))
