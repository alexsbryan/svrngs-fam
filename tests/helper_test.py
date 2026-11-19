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
import time
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


# Stands in for the svrngs command: says what svrngs says, as it says it
# (svrngs cli.rs), and keeps the argv and stdin it was given. $HOME/old-svrngs
# names an older svrngs, whose `parse` reads every flag before the command:
# 1.11 has no --pid, 1.12.2's takes a process id alone, and neither has
# approve. $HOME/refuse holds what svrngs refuses a share or approval with,
# as when the process named has stopped.
FAKE_COMMAND = r"""#!/bin/bash
printf '%s\n' "$@" > "$HOME/svrngs-argv"
cat > "$HOME/svrngs-stdin"
old=$(cat "$HOME/old-svrngs" 2>/dev/null)
# What was typed, refused before anything runs (main.rs), then the usage.
unparsed() { printf 'svrngs: %s\n\nsvrngs — keep what your group shares on your own computers.\n' "$1" >&2; exit 1; }
# What svrngs refused once it ran.
refused() { printf 'svrngs: %s\n' "$(cat "$HOME/refuse")" >&2; exit 1; }
prev=
for arg in "$@"; do
  [ "$old" = 1.11 ] && [ "$arg" = --pid ] && unparsed 'unknown argument `--pid`'
  [ "$old" = 1.12.2 ] && [ "$prev" = --pid ] && ! [[ $arg =~ ^[0-9]+$ ]] && unparsed "--pid \`$arg\` is not a process id"
  prev=$arg
done
case "$1" in
  approve)
    [ -n "$old" ] && unparsed 'unknown command `approve`'
    [ -e "$HOME/refuse" ] && refused
    echo "You lend $2 again, to python3 in ~/notes-app. Its groups and terms are as they were." ;;
  share)
    [ -e "$HOME/refuse" ] && refused
    printf 'If %s takes a password on each request, type it here (Enter alone for none): ' "$6" >&2
    echo "You lend $6 (port $2) to the groups you chose, as many at once as want it. To let fewer in at once, change it on your home page, or \`svrngs share $2 --group <group> --limit <number>\`."
    echo "svrngs doesn't know $8, so your friends can reach every part of it that its own sign-in allows."
    echo "\`svrngs unshare $6\` stops lending it." ;;
  unshare) echo "You no longer lend $2." ;;
  restart) echo "svrngs is restarting. Your home page comes back in a moment." ;;
  link) cat "$HOME/link-said" ;;
esac
"""

# Stand in for the browser and the clipboard, keeping what they were given.
STUBS = {
    "omarchy-launch-browser": '#!/bin/bash\nprintf "%s\\n" "$@" > "$HOME/browser-argv"\n',
    "wl-copy": '#!/bin/bash\ncat > "$HOME/clipboard"\n',
}


def run(home, *args, installed=True, data=None):
    """Run the helper as the shell does, with HOME at `home` and a PATH that
    holds no svrngs, so `installed` decides alone whether one is found."""
    if installed:
        command = home / ".local/bin/svrngs"
        command.parent.mkdir(parents=True, exist_ok=True)
        command.write_text(FAKE_COMMAND)
        command.chmod(0o755)
    stubs = home / "stubs"
    stubs.mkdir(exist_ok=True)
    for name, body in STUBS.items():
        (stubs / name).write_text(body)
        (stubs / name).chmod(0o755)
    # The command is named, or named as none: never the svrngs installed here.
    runtime = home / "runtime"
    runtime.mkdir(mode=0o700, exist_ok=True)
    env = {"HOME": str(home), "PATH": f"{stubs}:/usr/bin:/bin", "XDG_RUNTIME_DIR": str(runtime),
           "SVRNGS_FAM_SVRNGS": str(home / ".local/bin/svrngs") if installed else ""}
    if data is not None:
        env["SVRNGS_DIR"] = str(data)
    done = subprocess.run([str(HELPER), *args], capture_output=True, text=True, env=env, timeout=30)
    return json.loads(done.stdout), done.stdout


def state(home, *args, installed=True, data=None):
    return run(home, "state", *args, installed=installed, data=data)[0]


def listen(port, title=None, folder=None):
    """A server of this user's on 127.0.0.1:`port`, with process title
    `title` (as puma sets its own) and working folder `folder`."""
    argv = ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"]
    if title:
        argv = ["bash", "-c", 'exec -a "$0" python3 -m http.server "$1" --bind 127.0.0.1', title, str(port)]
    server = subprocess.Popen(argv, cwd=folder, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return server
        time.sleep(0.1)
    server.kill()
    raise SystemExit(f"a test server did not start on {port}")


# A server that writes down its own start (/proc/self/stat field 22, read
# while its command is still python's, which has no spaces), then names
# itself as some programs do (/proc/self/comm), and listens.
SERVE = r"""
import http.server, sys
from pathlib import Path
Path(sys.argv[2]).write_bytes(Path("/proc/self/stat").read_bytes().split()[21])
if sys.argv[3]:
    Path("/proc/self/comm").write_text(sys.argv[3])
http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), http.server.SimpleHTTPRequestHandler).serve_forever()
"""


def serve(port, home, comm="", folder=None):
    """A server of this user's on 127.0.0.1:`port`, whose command is `comm`
    when given, and the start it wrote down before it listened."""
    written = home / f"start-{port}"
    server = subprocess.Popen(["python3", "-c", SERVE, str(port), str(written), comm], cwd=folder,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return server, int(written.read_text())
        time.sleep(0.1)
    server.kill()
    raise SystemExit(f"a test server did not start on {port}")


# A command as a program may name itself: spaces and parentheses, which
# /proc/<pid>/stat shows inside its own parentheses.
ODD_COMM = "x) 1 2 (y"


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
    """A free port below 40000-48999, where svrngs opens lends to the Wi-Fi
    and the helper offers nothing (svrngs room.rs:63-69)."""
    for port in range(23000 + os.getpid() % 1000, 39000):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            if port not in taken:
                taken.add(port)
                return port
    raise SystemExit("no free port below 39000")


taken = set()


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
quiet = closed_port()
(home / ".svrngs/lends/garden.json").write_text(json.dumps({"port": quiet, "kind": "ruby", "groups": ["a" * 64]}))
got = state(home, "--full")
check("running", got["svrngs"], "running")
check("both groups read", [g["person"] for g in got["groups"]], ["LittleMac", "Ana"])
check("a friend's long name is cut to 200", len(got["groups"][1]["name"]), 200)
check("a friend's lend is read", got["lends"]["a" * 64]["lent"][0]["name"], "deepseek-flash")
check("this computer's lend, its port, its groups, and that nothing answers there now", got["mine"],
      [{"name": "garden", "port": quiet, "groups": ["a" * 64], "readable": True, "now": None}])
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

home = case("what runs here, and what is offered")
fake = Fake()
data_dir(home, port=fake.port)
puma_port, folder_port, lent_port, odd_port = closed_port(), closed_port(), closed_port(), closed_port()
(home / "notes-app").mkdir()
(home / ".svrngs/lends/lentone.json").write_text(json.dumps({"port": lent_port, "kind": "python3", "groups": []}))
odd, odd_start = serve(odd_port, home, comm=ODD_COMM, folder=home / "notes-app")
servers = [
    listen(puma_port, title=f"puma 8.1.2 (tcp://127.0.0.1:{puma_port}) [My Garden]"),
    listen(folder_port, folder=home / "notes-app"),
    listen(lent_port),
    odd,
]
debug = None
try:
    debug = listen(9222)
except SystemExit:
    pass
try:
    offered = {l["port"]: l for l in state(home, "--full")["listeners"]}
finally:
    for server in servers + ([debug] if debug else []):
        server.kill()
check("each offer names its process, by pid and start",
      {k: (offered.get(odd_port) or {}).get(k) for k in ("pid", "start")}, {"pid": odd.pid, "start": odd_start})
check("puma is named by its own title", (offered.get(puma_port) or {}).get("program"), "puma")
check("and offered under its app's name", (offered.get(puma_port) or {}).get("name"), "my-garden")
check("a server in its folder is offered under the folder's name", (offered.get(folder_port) or {}).get("name"), "notes-app")
check("what is already lent is not offered again", lent_port in offered, False)
check("svrngs's own port is not offered", fake.port in offered, False)
check("a browser's debug port (9222) could be planted", debug is not None, True)
check("and is never offered", 9222 in offered, False)
fake.close()

home = case("models: friends' lends that answer as one")
fake = Fake()
data_dir(home, port=fake.port)
fake.lends = {"lent": [
    {"person": "Fedora", "name": "coder", "kind": "llama-server", "origin": f"http://model1.localhost:{fake.port}/"},
    {"person": "Fedora", "name": "garden", "kind": "puma", "origin": f"http://garden1.localhost:{fake.port}/"},
    {"person": "LittleMac", "name": "mine", "kind": "llama-server", "origin": f"http://mine1.localhost:{fake.port}/"},
    {"person": "Mallory", "name": "elsewhere", "kind": "spot", "origin": "http://model2.localhost:1/"},
    {"person": "Fedora", "name": "asleep", "kind": "spot", "origin": f"http://model3.localhost:{fake.port}/", "answering": False},
    {"person": "Fedora", "name": "taken", "kind": "spot", "origin": f"http://model4.localhost:{fake.port}/", "answering": True, "held": "another"},
    {"person": "Fedora", "name": "newer", "kind": "spot", "origin": f"http://model5.localhost:{fake.port}/", "answering": True, "held": "paused"},
]}
fake.models = {"model1": ["qwen3-coder"], "mine1": ["mine"], "model2": ["x"], "model3": ["y"], "model4": ["z"], "model5": ["w"]}
got, _ = run(home, "models")
check("one model found", [(m["person"], m["name"], m["models"]) for m in got["models"]], [("Fedora", "coder", ["qwen3-coder"])])
check("of two friends' lends asked at svrngs's own address", got["asked"], 2)
check("its address is the lend's, ending in v1", got["models"][0]["address"] if got["models"] else None, f"http://model1.localhost:{fake.port}/v1")
asked = [s["headers"].get("Host", "").split(".")[0] for s in fake.seen if s["path"] == "/v1/models"]
check("your own lend is not asked", "mine1" in asked, False)
check("a lend not at svrngs's own address is never sent the token", "model2" in asked, False)
check("a lend its lender says is not running is not asked", "model3" in asked, False)
check("nor one svrngs holds closed", "model4" in asked, False)
check("nor one held for a reason this helper doesn't know", "model5" in asked, False)
full = state(home, "--full")["lends"]["a" * 64]["lent"]
check("whether each is running, as its lender says, or not said", [l["answering"] for l in full], [None, None, None, None, False, True, True])
check("and whether svrngs holds it closed", [l["held"] for l in full], [None, None, None, None, None, "another", "unknown"])
fake.close()

home = case("a held lend: why, and what answers on its port now")
fake = Fake()
data_dir(home, port=fake.port)
(home / "garden-app").mkdir()
garden_port, quiet_port, browser_port = closed_port(), closed_port(), closed_port()
for name, port in (("garden", garden_port), ("quiet", quiet_port), ("browser", browser_port)):
    (home / f".svrngs/lends/{name}.json").write_text(json.dumps({"port": port, "kind": "python3", "groups": ["a" * 64]}))
own = lambda name, **held: {"person": "LittleMac", "name": name, "kind": "python3", "origin": f"http://{name}1.localhost:{fake.port}/", **held}
fake.lends = {"lent": [
    own("garden", held="unapproved"), own("quiet", held="another"), own("browser", held="unjudged"),
    own("paused", held="paused"), own("shaped", held={"why": "a newer svrngs's"}), own("listed", held=["another"]),
    own("open"), own("nulled", held=None), own("blank", held=""),
]}
garden, garden_start = serve(garden_port, home, comm=ODD_COMM, folder=home / "garden-app")
browser, _ = serve(browser_port, home, comm="chromium")
try:
    full, quick = state(home, "--full"), state(home, "--here")
finally:
    garden.kill()
    browser.kill()
check("svrngs's reasons pass through; one this helper doesn't know is held all the same",
      [l["held"] for l in full["lends"]["a" * 64]["lent"]],
      ["unapproved", "another", "unjudged", "unknown", "unknown", "unknown", None, None, None])
now = {m["name"]: m.get("now", "unread") for m in full["mine"]}
check("on its port now: the name it would be offered under, and its pid",
      {k: (now["garden"] or {}).get(k) for k in ("name", "pid")}, {"name": "garden-app", "pid": garden.pid})
check("and its start, read past a command holding spaces and parentheses", (now["garden"] or {}).get("start"), garden_start)
check("nothing on its port: nothing answers", now["quiet"], None)
check("a program the panel never lends: nothing to keep sharing", (now["browser"] or {}).get("pid", "absent"), None)
check("the quick read of this computer says the same", {m["name"]: m.get("now") for m in quick["mine"]}["garden"], now["garden"])
check("a lent port is still not offered", garden_port in {l["port"] for l in full["listeners"]}, False)
fake.close()

home = case("groups asked together, a quick read, the group's own apps")
fake = Fake()
data_dir(home, port=fake.port)
fake.delay = 1.0
began = time.monotonic()
got = state(home, "--full")
took = time.monotonic() - began
check("two groups each a second slow take about one second, not two", took < 1.8, True)
check("both answered", sorted(got["lends"]), ["a" * 64, "b" * 64])
fake.delay = 0
quick = state(home, "--here")
check("the quick read says what listens here", "listeners" in quick, True)
check("and asks no group", "lends" in quick, False)
fake.lends = {"lent": [{"person": "Fedora", "name": "Money", "kind": "money", "origin": f"http://m1.localhost:{fake.port}/", "group": "a" * 64}]}
check("an app the group's folder carries is marked so", state(home, "--full")["lends"]["a" * 64]["lent"][0]["carried"], True)
fake.close()

home = case("models: what is known is not asked; not reached is not known")
fake = Fake()
data_dir(home, port=fake.port)
fake.lends = {"lent": [
    {"person": "Fedora", "name": "coder", "kind": "llama-server", "origin": f"http://model1.localhost:{fake.port}/"},
    {"person": "Fedora", "name": "flash", "kind": "spot", "origin": f"http://down1.localhost:{fake.port}/"},
    {"person": "Fedora", "name": "garden", "kind": "puma", "origin": f"http://garden1.localhost:{fake.port}/"},
]}
fake.models = {"model1": ["qwen3-coder"]}
fake.down = {"down1"}
got, _ = run(home, "models", "--skip", "model1")
said = {l["name"]: l["models"] for l in got["lends"]}
check("a lend named in --skip is listed, not asked", (said["coder"], any(s["headers"].get("Host", "").startswith("model1.") for s in fake.seen)), (None, False))
check("one not reached (502) is not known", said["flash"], None)
check("one that answered with no models is known as none", said["garden"], [])
fake.close()

home = case("open: in the browser, signed in")
fake = Fake()
data_dir(home, port=fake.port)
got, said = run(home, "open", "--lend", "garden1")
check("opened", got["ok"], True)
check("svrngs was asked for that lend", json.loads(fake.seen[-1]["body"]), {"lend": "garden1"})
given = (home / "browser-argv").read_text().strip()
check("the browser is given a page in the runtime folder", given.startswith(f"file://{home}/runtime/svrngs-fam/open-"), True)
check("not the one-time address, which no command line shows", "one-time-secret" in given, False)
handed = Path(given[len("file://"):])
check("the page sends it on to the one-time address", f"http://garden1.localhost:{fake.port}/svrngs-open?code=one-time-secret" in handed.read_text(), True)
check("only this person can read the page", (oct(handed.stat().st_mode & 0o777), oct(handed.parent.stat().st_mode & 0o777)), ("0o600", "0o700"))
check("which the helper never prints", "one-time-secret" in said, False)
old = handed.parent / "open-old.html"
old.write_text("spent")
os.utime(old, (time.time() - 3600, time.time() - 3600))
run(home, "open")
check("a page from an earlier open is cleared", old.exists(), False)
fake.close()

home = case("invite: a new link, copied")
data_dir(home)
(home / "link-said").write_text(
    "A new link to WorkingGroup. Any link you sent before stops letting anyone new in; everyone it let in stays.\n"
    "It works for a day, while this computer is on:\n\n  svrngs:CLIENTTOKEN\n\nor, to open it in a browser:\n\n  https://group.svrnme.sh/#PAGETOKEN\n")
got, said = run(home, "link", "WorkingGroup")
check("made", got["ok"], True)
check("the browser's link is the one copied", (home / "clipboard").read_text(), "https://group.svrnme.sh/#PAGETOKEN")
check("the link is never printed", "TOKEN" in said, False)
(home / "link-said").write_text("A new link to WorkingGroup. It works for a day, while this computer is on:\n\n  svrngs:CLIENTTOKEN\n")
run(home, "link", "WorkingGroup")
check("without a page, the client's link is copied", (home / "clipboard").read_text(), "svrngs:CLIENTTOKEN")

home = case("lend and stop")
data_dir(home)
got, _ = run(home, "share", "3000", "a" * 64, "garden", "--program", "puma")
check("lent", got["ok"], True)
check("svrngs is told the port, group, name and program", (home / "svrngs-argv").read_text().split(), ["share", "3000", "--group", "a" * 64, "--name", "garden", "--program", "puma"])
check("no password: an empty line", (home / "svrngs-stdin").read_text(), "\n")
check("svrngs's words, without the password question or the terminal tips", got["said"],
      "You lend garden (port 3000) to the groups you chose, as many at once as want it.\n"
      "svrngs doesn't know puma, so your friends can reach every part of it that its own sign-in allows.")
got, _ = run(home, "share", "3000", "a" * 64, "garden", "--program", "puma", "--pid", "4242@987654")
check("svrngs is told the process the panel showed, by its pid and start", (got["ok"], (home / "svrngs-argv").read_text().split()[-2:]), (True, ["--pid", "4242@987654"]))
for bad in ("42; rm", "4242", "4242@", "@99", "4242@99@1"):
    got, _ = run(home, "share", "3000", "a" * 64, "garden", "--program", "puma", "--pid", bad)
    check(f"--pid {bad!r}, not a process and its start, is refused, svrngs not run",
          (got["ok"], (home / "svrngs-argv").read_text().split()[-2:]), (False, ["--pid", "4242@987654"]))
NEWER = "Lending from here needs svrngs 1.12.3 or later. Update svrngs on its home page, then try again."
for old in ("1.11", "1.12.2"):
    (home / "old-svrngs").write_text(old)
    got, _ = run(home, "share", "3000", "a" * 64, "garden", "--program", "puma", "--pid", "4242@987654")
    check(f"svrngs {old}, before --pid <pid>@<start>: lending says what to do", (got["ok"], got["said"]), (False, NEWER))
(home / "old-svrngs").unlink()
(home / "refuse").write_text("that program stopped; choose it again")
got, _ = run(home, "share", "3000", "a" * 64, "garden", "--program", "puma", "--pid", "4242@987654")
check("a stale selection: svrngs's refusal is said", (got["ok"], got["said"]), (False, "svrngs: that program stopped; choose it again"))
(home / "refuse").write_text("another program also listens on port 3000")
got, _ = run(home, "share", "3000", "a" * 64, "garden", "--program", "puma", "--pid", "4242@987654")
check("a second program on the port: svrngs's refusal is said", (got["ok"], got["said"]), (False, "svrngs: another program also listens on port 3000"))
(home / "refuse").unlink()
got, _ = run(home, "unshare", "garden")
check("stopped", (got["ok"], (home / "svrngs-argv").read_text().split()), (True, ["unshare", "garden"]))
got, _ = run(home, "start")
check("start asks svrngs to restart itself", (got["ok"], (home / "svrngs-argv").read_text().split()), (True, ["restart"]))

home = case("keep sharing a held lend")
data_dir(home)
got, _ = run(home, "approve", "garden", "--pid", "4242@987654")
check("svrngs approves the process the line showed, and is told nothing else",
      (got["ok"], (home / "svrngs-argv").read_text().split()), (True, ["approve", "garden", "--pid", "4242@987654"]))
check("svrngs's words are said", got["said"], "You lend garden again, to python3 in ~/notes-app. Its groups and terms are as they were.")
for args in (["garden"], ["garden", "--pid", "4242"], ["garden", "--pid"], ["--replace", "--pid", "4242@1"], ["-x", "--pid", "4242@1"]):
    got, _ = run(home, "approve", *args)
    check(f"approve {' '.join(args)}: refused, svrngs not run",
          (got["ok"], (home / "svrngs-argv").read_text().split()), (False, ["approve", "garden", "--pid", "4242@987654"]))
for old in ("1.11", "1.12.2", "no-approve"):
    (home / "old-svrngs").write_text(old)
    got, _ = run(home, "approve", "garden", "--pid", "4242@987654")
    check(f"an svrngs without approve ({old}): what to do", (got["ok"], got["said"]), (False, NEWER))
(home / "old-svrngs").unlink()
(home / "refuse").write_text("that program stopped; choose it again")
got, _ = run(home, "approve", "garden", "--pid", "4242@987654")
check("a stale selection: svrngs's refusal is said", (got["ok"], got["said"]), (False, "svrngs: that program stopped; choose it again"))

print("ALL OK" if not failures else f"{len(failures)} FAILED")
SCRATCH.cleanup()
sys.exit(1 if failures else 0)
