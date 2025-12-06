
from pathlib import Path
import platform, os

APP_NAME = "QuikNoteProTabs"

def data_dir() -> Path:
    sys = platform.system()
    home = Path.home()
    if sys == "Windows":
        base = Path(os.getenv("APPDATA", home / "AppData" / "Roaming"))
    elif sys == "Darwin":
        base = home / "Library" / "Application Support"
    else:
        base = home / ".config"
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d

def file_json(name: str) -> Path:
    return data_dir() / name
