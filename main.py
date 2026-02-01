import sys
import asyncio
import signal
from client import MusicBot, create_bot
from utils.config import TOKEN, ENVIRONMENT, COMMAND_PREFIX, test_guild_id


def setup_environment():
    """Validate environment variables."""

    if not TOKEN:
        print("❌ ERROR: DISCORD_TOKEN not found in environment variables!")
        sys.exit(1)

    print(f"Environment: {ENVIRONMENT}")

    if test_guild_id:
        print(f"Test Guild ID: {test_guild_id} (Development Mode)")
    else:
        print("Test Guild ID: Not set (Production Mode)")

    return TOKEN


def handle_shutdown(bot: MusicBot, signal_num: signal.Signals | None = None):
    """Handle graceful shutdown."""

    sig_name = f" ({signal.Signals(signal_num).name})" if signal_num else ""
    print("\n" + "-" * 50)
    print(f"Shutting down bot{sig_name}...")
    print("-" * 50)

    asyncio.create_task(bot.close())


async def main():
    """Main function to run the bot."""

    token = setup_environment()
    bot = create_bot(COMMAND_PREFIX, test_guild_id)

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_shutdown, bot, sig)

    try:
        async with bot:
            await bot.start(token)
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt...")
    except Exception as exception:
        print(f"\n❌ Fatal error: {exception}")
        import traceback

        traceback.print_exc()
    finally:
        if not bot.is_closed():
            await bot.close()

        print("\n" + "-" * 50)
        print("Bot has been shut down successfully.")
        print("-" * 50)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
    except Exception as exception:
        print(f"\n❌ Critical error: {exception}")
        sys.exit(1)
