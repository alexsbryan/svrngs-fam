#!/usr/bin/python3 -I
"""bin/svrngs-fam's `state`, against a fake svrngs, in a scratch home.

What it guards: the icon's four states rest on the helper telling them apart.
A failure that is not a refused connection must be "unreadable", never
"stopped", and a running svrngs must be read with the token and no Origin.
Each case runs the real helper as the shell does, with an argv list.
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_svrngs import TOKEN, Fake  # noqa: E402

HELPER = HERE.parent / "bin" / "svrngs-fam"
SCRATCH = tempfile.TemporaryDirectory(prefix="svrngs-fam-test-")
failures = []


def check(name, got, want):
    if got == want:
        print(f"  ok   {name}")
    else:
        failures.append(name)
        print(f"  FAIL {name}: got {got!r}, wanted {want!r}")


def state(home, *args, installed=True, data=None):
    """Run the helper with HOME at `home` and a PATH that holds no svrngs,
    so `installed` decides alone whether a svrngs command is found."""
    if installed:
        command = home / ".local/bin/svrngs"
        command.parent.mkdir(parents=True, exist_ok=True)
        command.write_text("#!/bin/sh\nexit 0\n")
        command.chmod(0o755)
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    if data is not None:
        env["SVRNGS_DIR"] = str(data)
    done = subprocess.run([str(HELPER), "state", *args], capture_output=True, text=True, env=env, timeout=30)
    return json.loads(done.stdout)


def data_dir(home, port=None, token=TOKEN, api=None):
    data = home / ".svrngs"
    (data / "lends").mkdir(parents=True, exist_ok=True)
    if api is not None:
        (data / "api").write_text(api)
    elif port is not None:
        (data / "api").write_text(f"http://127.0.0.1:{port}\n")
    if token is not None:
        (data / "token").write_text(token + "\n")
    return data


def closed_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def case(title):
    print(title)
    return Path(tempfile.mkdtemp(dir=SCRATCH.name))


home = case("no svrngs on this computer")
check("not-installed", state(home, installed=False)["svrngs"], "not-installed")

home = case("installed, never started")
data_dir(home)
check("never-started", state(home)["svrngs"], "never-started")

home = case("started once, stopped now")
data_dir(home, port=closed_port())
check("stopped", state(home)["svrngs"], "stopped")

home = case("running")
fake = Fake()
data_dir(home, port=fake.port)
(home / ".svrngs/lends/garden.json").write_text(json.dumps({"port": 3000, "kind": "ruby", "groups": ["a" * 64]}))
got = state(home, "--full")
check("running", got["svrngs"], "running")
check("both groups read", [g["person"] for g in got["groups"]], ["LittleMac", "Ana"])
check("a friend's long name is cut to 200", len(got["groups"][1]["name"]), 200)
check("a friend's lend is read", got["lends"]["a" * 64]["lent"][0]["name"], "deepseek-flash")
check("this computer's lend and its port", got["mine"], [{"name": "garden", "port": 3000, "readable": True}])
check("asked with the token", all(s["headers"].get("Authorization") == f"Bearer {TOKEN}" for s in fake.seen), True)
check("never with an Origin", any("Origin" in s["headers"] for s in fake.seen), False)
fake.close()

home = case("SVRNGS_DIR names the data directory")
fake = Fake()
elsewhere = data_dir(home / "elsewhere", port=fake.port)
check("running from SVRNGS_DIR", state(home, data=elsewhere)["svrngs"], "running")
fake.close()

# Each of these is svrngs, or something at its address, answering wrongly.
# None is a stopped svrngs, and the icon must not say it is.
for mode, why in (("error", "500"), ("not-json", "no JSON"), ("huge", "KiB")):
    home = case(f"answers {mode}")
    fake = Fake(mode)
    data_dir(home, port=fake.port)
    got = state(home)
    check(f"{mode}: unreadable, not stopped", got["svrngs"], "unreadable")
    check(f"{mode}: says why", why in got.get("reason", ""), True)
    fake.close()

home = case("a token svrngs refuses")
fake = Fake()
data_dir(home, port=fake.port, token="not-the-token-at-all")
got = state(home)
check("refused token: unreadable", got["svrngs"], "unreadable")
check("refused token: says 401", "401" in got.get("reason", ""), True)
fake.close()

home = case("no token file")
fake = Fake()
data_dir(home, port=fake.port, token=None)
check("missing token: unreadable", state(home)["svrngs"], "unreadable")
fake.close()

home = case("an api file naming another host")
data_dir(home, api="http://192.168.1.9:41097\n")
got = state(home)
check("foreign address: unreadable", got["svrngs"], "unreadable")
check("foreign address: never asked", "192.168" in got.get("reason", ""), True)

print("ALL OK" if not failures else f"{len(failures)} FAILED")
SCRATCH.cleanup()
sys.exit(1 if failures else 0)
