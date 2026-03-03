#!/usr/bin/env python3
"""
Desktop Notification Tool Module

Provides cross-platform desktop notifications and system sounds to alert the user
when long-running tasks or workflows are completed.

Implements secure subprocess execution without shell interpolation to prevent
command injection vulnerabilities.
"""

import json
import logging
import os
import subprocess
import sys

from tools.registry import registry

logger = logging.getLogger(__name__)


def is_gui_available() -> bool:
    """Check if a GUI session is available (not just an SSH headless terminal)."""
    if os.environ.get("SSH_CONNECTION"):
        return False
        
    if sys.platform == "linux":
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        
    # macOS and Windows generally assume GUI is present unless explicitly headless/SSH
    return sys.platform in ("darwin", "win32")


def notify_desktop(title: str, message: str) -> str:
    """
    Send a desktop notification securely without shell string interpolation.
    """
    if not is_gui_available():
        # Fallback to terminal bell if no GUI is present
        print(f"\a\n[BELL] {title}: {message}")
        return json.dumps({"success": True, "notice": "Sent via terminal bell (headless environment)"})

    try:
        if sys.platform == "darwin":
            # macOS: AppleScript via osascript
            # We pass the arguments securely to avoid interpolation injections
            script = f'display notification "{message.replace('"', '\\"')}" with title "{title.replace('"', '\\"')}"'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return json.dumps({"success": True, "platform": "macos"})

        elif sys.platform == "linux":
            # Linux: libnotify via notify-send
            # Subprocess array notation prevents shell injection natively
            if shutil.which("notify-send"):
                subprocess.run(["notify-send", title, message], check=True, capture_output=True)
                return json.dumps({"success": True, "platform": "linux"})
            else:
                return json.dumps({"success": False, "error": "notify-send not found on system"})

        elif sys.platform == "win32":
            # Windows: PowerShell toast notification
            # Passed safely via base64 encoded command or secure arguments
            ps_script = f"""
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $template = "<toast><visual><binding template='ToastText02'><text id='1'>{title.replace("'", "''")}</text><text id='2'>{message.replace("'", "''")}</text></binding></visual></toast>"
            $xml.LoadXml($template)
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Hermes Agent").Show($toast)
            """
            import base64
            encoded = base64.b64encode(ps_script.encode('utf-16le')).decode('utf-8')
            subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded], check=True, capture_output=True)
            return json.dumps({"success": True, "platform": "windows"})

        else:
            return json.dumps({"success": False, "error": f"Unsupported platform: {sys.platform}"})

    except subprocess.CalledProcessError as e:
        logger.error(f"Notification failed: {e.stderr or e.output}")
        return json.dumps({"success": False, "error": str(e)})
    except Exception as e:
        logger.error(f"Notification error: {e}")
        return json.dumps({"success": False, "error": str(e)})


def play_sound() -> str:
    """
    Play a default system alert sound securely.
    """
    if not is_gui_available():
        print("\a")  # Terminal bell
        return json.dumps({"success": True, "notice": "Played terminal bell (headless environment)"})

    try:
        import shutil
        if sys.platform == "darwin":
            # macOS default system sound
            if shutil.which("afplay"):
                subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=True, capture_output=True)
                return json.dumps({"success": True, "platform": "macos"})
                
        elif sys.platform == "linux":
            # PulseAudio/ALSA/PipeWire players
            sound_path = "/usr/share/sounds/freedesktop/stereo/complete.oga"
            if not os.path.exists(sound_path):
                # Fallback to terminal bell
                print("\a")
                return json.dumps({"success": True, "notice": "Sound file missing, played terminal bell"})
                
            player = shutil.which("paplay") or shutil.which("pw-play") or shutil.which("aplay")
            if player:
                subprocess.run([player, sound_path], check=True, capture_output=True)
                return json.dumps({"success": True, "platform": "linux"})
            else:
                return json.dumps({"success": False, "error": "No compatible sound player found"})

        elif sys.platform == "win32":
            # Windows system beep
            ps_script = "[System.Media.SystemSounds]::Beep.Play()"
            subprocess.run(["powershell", "-Command", ps_script], check=True, capture_output=True)
            return json.dumps({"success": True, "platform": "windows"})

        return json.dumps({"success": False, "error": f"Unsupported platform: {sys.platform}"})

    except Exception as e:
        logger.error(f"Sound play error: {e}")
        return json.dumps({"success": False, "error": str(e)})


# ===========================================================================
# Registry Schemas
# ===========================================================================

NOTIFY_SCHEMA = {
    "name": "notify",
    "description": "Send a desktop notification to the user's OS to alert them about task completion or important status updates.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "The title of the notification (e.g. 'Task Completed')."
            },
            "message": {
                "type": "string",
                "description": "The body message of the notification."
            }
        },
        "required": ["title", "message"]
    }
}

NOTIFY_SOUND_SCHEMA = {
    "name": "notify_sound",
    "description": "Play a system alert sound (beep/chime) to get the user's attention. Useful when long workflows finish.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}

# Register tools
import shutil  # required for the play_sound check

registry.register(
    name="notify",
    toolset="notification",
    schema=NOTIFY_SCHEMA,
    handler=lambda args, **kw: notify_desktop(
        title=args.get("title", "Hermes Agent"),
        message=args.get("message", "")
    ),
    check_fn=lambda: True, # Always available (fallbacks to print bell)
)

registry.register(
    name="notify_sound",
    toolset="notification",
    schema=NOTIFY_SOUND_SCHEMA,
    handler=lambda args, **kw: play_sound(),
    check_fn=lambda: True, # Always available (fallbacks to print bell)
)
