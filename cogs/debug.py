import discord
from discord import app_commands
from discord.ext import commands
import time
import psutil
import os


class Debug(commands.GroupCog, name="debug"):
    """Debug and utility commands."""

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.start_time: float = time.time()

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        """Show bot latency."""

        # Measure API latency
        start = time.perf_counter()
        await interaction.response.defer()
        end = time.perf_counter()

        api_latency = (end - start) * 1000
        ws_latency = self.bot.latency * 1000

        embed = discord.Embed(title="🏓 Pong!", color=discord.Color.green())

        embed.add_field(
            name="WebSocket Latency", value=f"`{ws_latency:.2f}ms`", inline=True
        )

        embed.add_field(name="API Latency", value=f"`{api_latency:.2f}ms`", inline=True)

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="uptime", description="Show how long the bot has been running"
    )
    async def uptime(self, interaction: discord.Interaction):
        """Show bot uptime."""

        uptime_seconds = int(time.time() - self.start_time)

        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        uptime_str = ""
        if days > 0:
            uptime_str += f"{days}d "
        if hours > 0:
            uptime_str += f"{hours}h "
        if minutes > 0:
            uptime_str += f"{minutes}m "
        uptime_str += f"{seconds}s"

        embed = discord.Embed(
            title="⏱️ Uptime",
            description=f"Bot has been running for: **{uptime_str}**",
            color=discord.Color.blue(),
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="stats", description="Show bot statistics")
    async def stats(self, interaction: discord.Interaction):
        """Show detailed bot statistics."""

        # System stats
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / 1024 / 1024  # MB
        cpu_usage = process.cpu_percent(interval=0.1)

        # Bot stats
        total_members = sum(guild.member_count or 0 for guild in self.bot.guilds)

        # Voice stats
        voice_clients = len(self.bot.voice_clients)

        embed = discord.Embed(title="📊 Bot Statistics", color=discord.Color.blue())

        embed.add_field(
            name="🌐 Guilds", value=f"`{len(self.bot.guilds)}`", inline=True
        )

        embed.add_field(name="👥 Users", value=f"`{total_members}`", inline=True)

        embed.add_field(
            name="🔊 Voice Connections", value=f"`{voice_clients}`", inline=True
        )

        embed.add_field(name="💾 Memory", value=f"`{memory_usage:.2f} MB`", inline=True)

        embed.add_field(name="⚙️ CPU", value=f"`{cpu_usage:.1f}%`", inline=True)

        embed.add_field(
            name="🏓 Latency", value=f"`{self.bot.latency * 1000:.2f}ms`", inline=True
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function to add cog to bot."""

    await bot.add_cog(Debug(bot))
