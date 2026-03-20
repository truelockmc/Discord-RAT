import atexit
import ctypes
import os
import subprocess
import sys
import tempfile

import psutil

from config import ADMIN_STATUS_FILE, IS_WINDOWS

# ── Module-level admin state ───────────────────────────────────────────────
is_admin: bool = False


def load_admin_status() -> None:
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


def elevate() -> bool:
    if check_if_admin():
        raise Exception("The process already has admin rights.")

    if IS_WINDOWS:
        script = os.path.abspath(sys.argv[0])
        command = (
            f'"{script}"'
            if os.path.splitext(script)[1].lower() == ".exe"
            else f'"{sys.executable}" "{script}"'
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


def check_single_instance() -> None:
    pid_file = os.path.join(tempfile.gettempdir(), "script_instance.pid")

    if os.path.exists(pid_file):
        with open(pid_file, "r") as f:
            pid = int(f.read())
        if psutil.pid_exists(pid):
            print("An instance of the script is already running.")
            sys.exit(0)
        print("PID file found, but process is no longer running. Overwriting.")

    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    def _remove():
        if os.path.exists(pid_file):
            os.remove(pid_file)

    atexit.register(_remove)
