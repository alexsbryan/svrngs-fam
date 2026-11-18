#!/usr/bin/python3 -I
"""Draw preview.png: the real panel, offscreen, opened on a fully seeded
svrngs (tests/preview/seed.py stands in for the helper), in this computer's
Omarchy theme. Run it again after a change to how the panel looks."""
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL = Path(os.environ.get("OMARCHY_SHELL", "/usr/share/omarchy/shell"))
OUT = ROOT / "preview.png"

with tempfile.TemporaryDirectory(prefix="svrngs-fam-preview-") as directory:
    scratch = Path(directory)
    harness = scratch / "harness"
    harness.mkdir()
    shutil.copy(ROOT / "tests/preview/shell.qml", harness / "shell.qml")
    for name in ("Service.qml", "Model.js", "SvrngsMark.qml"):
        shutil.copy(ROOT / name, harness / name)
    shutil.copytree(ROOT / "i18n", harness / "i18n")
    shutil.copy(ROOT / "Panel.qml", harness / "BarPanel.qml")
    (harness / "bin").mkdir()
    shutil.copy(ROOT / "tests/preview/seed.py", harness / "bin/svrngs-fam")
    (harness / "Commons").symlink_to(SHELL / "Commons")
    shutil.copytree(SHELL / "Ui", harness / "Ui", symlinks=True)
    shutil.copy(ROOT / "tests/preview/KeyboardPanel.qml", harness / "Ui/KeyboardPanel.qml")

    home = scratch / "home"
    (home / ".svrngs/lends").mkdir(parents=True)
    (home / ".svrngs/lends/library.json").write_text('{"port": 8083, "kind": "calibre-web", "groups": []}')
    theme = Path.home() / ".local/state/omarchy/current/theme/colors.toml"
    if theme.is_file():
        (home / ".local/state/omarchy/current/theme").mkdir(parents=True)
        shutil.copy(theme, home / ".local/state/omarchy/current/theme/colors.toml")
    runtime = scratch / "runtime"
    runtime.mkdir(mode=0o700)
    env = {"HOME": str(home), "SVRNGS_DIR": str(home / ".svrngs"), "SVRNGS_FAM_SVRNGS": "",
           "PATH": "/usr/bin:/bin", "XDG_RUNTIME_DIR": str(runtime), "QT_QPA_PLATFORM": "offscreen",
           "QT_SCALE_FACTOR": "2", "PREVIEW_OUT": str(OUT), "LANG": "C.UTF-8"}
    shell = subprocess.Popen(["quickshell", "-p", str(harness)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    timer = threading.Timer(40, shell.kill)
    timer.start()
    said = []
    for line in shell.stdout:
        said.append(line)
        if "PREVIEW:" in line:
            break
    timer.cancel()
    shell.kill()
    shell.wait()

plain = re.sub(r"\x1b\[[0-9;]*m", "", "".join(said))
print("\n".join(l for l in plain.splitlines() if "PREVIEW" in l or "Error" in l or "WARN scene" in l)[-2000:])
assert "PREVIEW: saved" in plain, "no preview was saved"
print(OUT)
