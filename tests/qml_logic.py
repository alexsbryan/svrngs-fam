#!/usr/bin/python3 -I
"""The bar widget's decisions, checked offscreen against the real Panel.qml,
Service.qml, Model.js and helper (tests/qml/shell.qml says which).

Needs quickshell and Omarchy's qs.Commons and qs.Ui, which the harness links
in. A check that cannot run fails: a skip that reads as a pass guards nothing.
Built after Superwhisper's tests/qml_logic.py, which found the same limits:
Quickshell does not wire Qt.exit, and Omarchy's GTK platform theme needs a
display even offscreen.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL = Path(os.environ.get("OMARCHY_SHELL", "/usr/share/omarchy/shell"))

if shutil.which("quickshell") is None:
    raise SystemExit("quickshell is not installed; the widget's logic cannot be checked")
if not SHELL.is_dir():
    raise SystemExit(f"Omarchy's shell modules are not at {SHELL}; set OMARCHY_SHELL")

with tempfile.TemporaryDirectory(prefix="svrngs-fam-qml-") as directory:
    scratch = Path(directory)
    harness = scratch / "harness"
    harness.mkdir()
    shutil.copy(ROOT / "tests/qml/shell.qml", harness / "shell.qml")
    for name in ("Service.qml", "Model.js"):
        shutil.copy(ROOT / name, harness / name)
    shutil.copytree(ROOT / "keys", harness / "keys")
    shutil.copytree(ROOT / "i18n", harness / "i18n")
    shutil.copytree(ROOT / "bin", harness / "bin")
    # Panel.qml extends qs.Ui's Panel; beside it under its own name it would
    # resolve that name to itself.
    shutil.copy(ROOT / "Panel.qml", harness / "BarPanel.qml")
    (harness / "Commons").symlink_to(SHELL / "Commons")
    shutil.copytree(SHELL / "Ui", harness / "Ui", symlinks=True)
    shutil.copy(ROOT / "tests/qml/KeyboardPanel.qml", harness / "Ui/KeyboardPanel.qml")

    # A home with no svrngs, and svrngs's data directory holding two lends.
    home = scratch / "home"
    lends = home / ".svrngs/lends"
    lends.mkdir(parents=True)
    for name, port in (("garden", 3000), ("notes", 3001)):
        (lends / f"{name}.json").write_text(json.dumps({"port": port, "kind": "ruby", "groups": []}))
    runtime = scratch / "runtime"
    runtime.mkdir(mode=0o700)

    env = {
        "HOME": str(home),
        "SVRNGS_DIR": str(home / ".svrngs"),
        "PATH": "/usr/bin:/bin",
        # No svrngs, whatever this computer has installed, and no release:
        # Get svrngs here asks a port nothing listens on, never the network.
        "SVRNGS_FAM_SVRNGS": "",
        "SVRNGS_FAM_RELEASES": "http://127.0.0.1:9/",
        "XDG_RUNTIME_DIR": str(runtime),
        "QT_QPA_PLATFORM": "offscreen",
    }
    shell = subprocess.Popen(["quickshell", "-p", str(harness)], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, env=env)
    timer = threading.Timer(40, shell.kill)
    timer.start()
    lines = []
    for line in shell.stdout:
        lines.append(line)
        if re.search(r"qml:\s+(ALL OK|\d+ FAILED)", re.sub(r"\x1b\[[0-9;]*m", "", line)):
            break
    timer.cancel()
    shell.kill()
    shell.wait()

plain = re.sub(r"\x1b\[[0-9;]*m", "", "".join(lines))
checks = re.findall(r"qml:\s+(ok|FAIL)\s+(.*?)\s*$", plain, re.MULTILINE)
for line in re.findall(r"qml:\s+(.*)$", plain, re.MULTILINE):
    print(" ", line)
failed = [name for state, name in checks if state == "FAIL"]
errors = [l for l in plain.splitlines() if re.search(r"svrngs|BarPanel|Service\.qml|Model\.js|shell\.qml", l) and re.search(r"WARN|ERROR|Error", l)]

if failed or "ALL OK" not in plain:
    print("\n".join(l for l in plain.splitlines() if re.search(r"WARN|ERROR|Error", l))[-3000:])
assert checks, "the harness produced no checks:\n" + plain[-3000:]
assert not failed, "failed: " + "; ".join(failed)
assert not errors, "QML warnings from the plugin:\n" + "\n".join(errors)
assert "ALL OK" in plain, "the harness did not finish:\n" + plain[-3000:]
print(f'{{"qml_logic_checks": {len(checks)}, "failed": 0}}')
