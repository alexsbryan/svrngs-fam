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
import socket
import subprocess
import tempfile
import threading
import time
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
    for name in ("Service.qml", "Model.js", "SvrngsMark.qml"):
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

# The restart after an update, with the panel closed (tests/qml/restarts.qml).
# A stand-in svrngs from before 1.13.3 holds its data dir's lock and answers
# 404. Its login service's program says 1.13.3, but each restart brings the
# same older svrngs back, as a service that runs an older copy than the one
# asked does; and each start rewrites `api`, as svrngs's does, which the bar
# reads again, each read a run of the helper of its own. Counted over 12 s:
# one restart, however many reads.
OLDER = r"""
import fcntl, os, signal, socket, sys, time
signal.alarm(60)
root, port = sys.argv[1], int(sys.argv[2])
held = open(os.path.join(root, "lock"), "w")
fcntl.flock(held, fcntl.LOCK_EX)
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
for _ in range(100):
    try:
        s.bind(("127.0.0.1", port))
        break
    except OSError:
        time.sleep(0.05)
s.listen()
with open(os.path.join(os.environ["HOME"], "older.pid"), "w") as f:
    f.write(str(os.getpid()))
with open(os.path.join(root, "api"), "w") as f:
    f.write(f"http://127.0.0.1:{port}\n")
while True:
    c = s.accept()[0]
    try:
        c.settimeout(2)
        c.recv(65536)
        c.sendall(b"HTTP/1.1 404 Not Found\r\ncontent-length: 0\r\nconnection: close\r\n\r\n")
    except OSError:
        pass
    c.close()
"""
# The svrngs command its login service runs, and systemctl as the helper
# asks it which program that service starts, for which data dir.
COMMAND = r"""#!/bin/bash
case "$1" in
  version) echo "svrngs 1.13.3 (0123abcd)" ;;
  restart)
    echo restart >> "$HOME/restarts"
    kill "$(cat "$HOME/older.pid")" 2>/dev/null
    setsid python3 -I "$HOME/older.py" "$SVRNGS_DIR" "$(cat "$HOME/port")" </dev/null >/dev/null 2>&1 &
    echo "svrngs is restarting. Your home page comes back in a moment." ;;
  *) exit 1 ;;
esac
"""
SYSTEMCTL = r"""#!/bin/bash
[ "$*" = "--user show svrngs.service --property=LoadState,ExecStart,Environment" ] || exit 1
echo "LoadState=loaded"
echo "ExecStart={ path=$HOME/bin/svrngs ; argv[]=$HOME/bin/svrngs ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }"
echo "Environment=SVRNGS_DIR=$SVRNGS_DIR"
"""

with tempfile.TemporaryDirectory(prefix="svrngs-fam-restarts-") as directory:
    scratch = Path(directory)
    harness = scratch / "harness"
    harness.mkdir()
    shutil.copy(ROOT / "tests/qml/restarts.qml", harness / "shell.qml")
    for name in ("Service.qml", "Model.js"):
        shutil.copy(ROOT / name, harness / name)
    shutil.copytree(ROOT / "bin", harness / "bin")
    home = scratch / "home"
    data = home / ".svrngs"
    data.mkdir(parents=True)
    (data / "token").write_text("restarts-test-token-0123456789\n")
    stubs = home / "stubs"
    for path, body in ((home / "bin/svrngs", COMMAND), (stubs / "systemctl", SYSTEMCTL)):
        path.parent.mkdir(exist_ok=True)
        path.write_text(body)
        path.chmod(0o755)
    (home / "older.py").write_text(OLDER)
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
    (home / "port").write_text(str(port))
    runtime = scratch / "runtime"
    runtime.mkdir(mode=0o700)
    env = {"HOME": str(home), "SVRNGS_DIR": str(data), "PATH": f"{stubs}:/usr/bin:/bin",
           "SVRNGS_FAM_SVRNGS": str(home / "bin/svrngs"), "XDG_RUNTIME_DIR": str(runtime), "QT_QPA_PLATFORM": "offscreen"}
    subprocess.Popen(["setsid", "python3", "-I", str(home / "older.py"), str(data), str(port)], env=env,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        if (data / "api").exists():
            break
        time.sleep(0.05)
    assert (data / "api").exists(), "the stand-in svrngs from before 1.13.3 did not start"
    shell = subprocess.Popen(["quickshell", "-p", str(harness)], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, env=env)
    timer = threading.Timer(40, shell.kill)
    timer.start()
    later = []
    for line in shell.stdout:
        later.append(line)
        if "restarts: done" in line:
            break
    timer.cancel()
    shell.kill()
    shell.wait()
    time.sleep(1)
    try:
        os.kill(int((home / "older.pid").read_text()), 9)
    except (OSError, ValueError):
        pass
    restarts = (home / "restarts").read_text().splitlines() if (home / "restarts").exists() else []

after = re.sub(r"\x1b\[[0-9;]*m", "", "".join(later))
reads = re.search(r"restarts: done after (\d+) reads", after)
errors = [l for l in after.splitlines() if re.search(r"svrngs|Service\.qml|Model\.js|shell\.qml", l) and re.search(r"WARN|ERROR|Error", l)]
print(f"  restarts of an svrngs that stays older, with the panel closed: {len(restarts)} in {reads.group(1) if reads else '?'} reads")
assert reads, "the restarts harness did not finish:\n" + after[-3000:]
assert not errors, "QML warnings from the plugin:\n" + "\n".join(errors)
assert int(reads.group(1)) >= 2, f"the bar read svrngs {reads.group(1)} times; the restart's api rewrite should read it again"
assert len(restarts) == 1, f"restarted {len(restarts)} times in {reads.group(1)} reads, not once"
print(f'{{"qml_logic_checks": {len(checks)}, "restarts": {len(restarts)}, "failed": 0}}')
