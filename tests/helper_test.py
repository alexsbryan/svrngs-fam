#!/usr/bin/python3 -I
"""bin/svrngs-fam's `state`, against a fake svrngs, in a scratch home.

What it guards: the icon's four states rest on the helper telling them apart.
A failure that is not a refused connection must be "unreadable", never
"stopped", and a running svrngs must be read with the token and no Origin.
Each case runs the real helper as the shell does, with an argv list.
"""

import json
import os
import pwd
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


def unnamed():
    """A uid with no account on this computer, so the helper says it by its
    number: a fixed one, like 1001, is a real account on many machines."""
    for uid in range(60001, 65534):
        try:
            pwd.getpwuid(uid)
        except KeyError:
            return str(uid)
    raise SystemExit("helper_test: every uid from 60001 has an account here")


UNNAMED = unnamed()


def check(name, got, want):
    if got == want:
        print(f"  ok   {name}")
    else:
        failures.append(name)
        print(f"  FAIL {name}: got {got!r}, wanted {want!r}")


# Stands in for the svrngs command: says what svrngs says, as it says it,
# and keeps the argv and stdin it was given. Its words are svrngs's at
# 0b36268e: share's question (cli.rs:857) and what it prints (cli.rs `Said`'s
# Display, `Shared`); a refusal as main.rs says it, `svrngs: <why>`, and
# for what it couldn't parse, a blank line and its usage (help.txt).
# $HOME/old-svrngs names an older svrngs, whose `parse` reads every flag
# before the command: 1.12.1 has no --pid (cli.rs:364 at v1.12.1), and
# 1.12.2's takes a process id alone (cli.rs:305, :321 at v1.12.2).
# $HOME/refuse holds what svrngs refuses a share with once it ran, and
# $HOME/unparsed what it refuses before it runs. A share of a port svrngs's
# table doesn't know, given no --program, is refused as svrngs refuses it,
# naming the programs it knows (share.rs `ShareRefusal::NoKind`); the ports
# it knows are 8096 and those in $HOME/known-ports. Each run's argv is
# also added to $HOME/svrngs-calls, a line each.
FAKE_COMMAND = r"""#!/bin/bash
printf '%s\n' "$@" > "$HOME/svrngs-argv"
printf '%s\n' "$*" >> "$HOME/svrngs-calls"
cat > "$HOME/svrngs-stdin"
old=$(cat "$HOME/old-svrngs" 2>/dev/null)
unparsed() { printf 'svrngs: %s\n\nsvrngs — keep what your group shares on your own computers.\n\nTo build an app for your group, make a folder with an index.html in it:\n' "$1" >&2; exit 1; }
refused() { printf 'svrngs: %s\n' "$(cat "$HOME/refuse")" >&2; exit 1; }
[ -e "$HOME/unparsed" ] && unparsed "$(cat "$HOME/unparsed")"
prev= program=
for arg in "$@"; do
  [ "$old" = 1.12.1 ] && [ "$arg" = --pid ] && unparsed 'unknown argument `--pid`'
  [ "$old" = 1.12.2 ] && [ "$prev" = --pid ] && ! [[ $arg =~ ^[0-9]+$ ]] && unparsed "--pid \`$arg\` is not a process id"
  [ "$prev" = --program ] && program=$arg
  prev=$arg
done
case "$1" in
  share)
    if [ -z "$program" ] && ! grep -qx "$2" <(echo 8096; cat "$HOME/known-ports" 2>/dev/null); then
      printf 'svrngs: say which program is on port %s: `svrngs share %s --program <name>`, its own name if it is one svrngs knows: audiobookshelf, calibre-web, factorio, holyarrs, immich, jellyfin, kokoro, llama-server, minecraft, navidrome\n' "$2" "$2" >&2
      exit 1
    fi
    [ -e "$HOME/refuse" ] && refused
    printf 'If %s takes a password on each request, paste what it takes in its Authorization header, then press Enter (Enter alone for none): ' "$6" >&2
    echo "You lend $6 (port $2) to the groups you chose, as many at once as want it. To let fewer in at once, change it on your home page, or \`svrngs share $2 --group <group> --limit <number>\`."
    echo "Lent $6: python3 in ~/garden-app. svrngs checks port $2 before each connection it carries there. While another program is on the port, it is closed. If the program starts again, $6 closes until you approve what runs there: \`svrngs approve $6\`."
    if [ -n "$program" ]; then
      echo "svrngs doesn't know $program, so your friends can reach every part of it that its own sign-in allows."
    else
      echo "$6 asks each person to sign in once, with an account you make them. In jellyfin: your picture at the top right, then Dashboard, Users and +."
    fi ;;
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

# Another account's program on svrngs's port, while svrngs is down: a uid
# of this account's own subordinate range (/etc/subuid), which is no
# account here, as `unshare --map-auto` gives it without root. It answers
# as svrngs would and writes down every byte it is sent.
FOREIGN = r"""
import socket, sys
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", int(sys.argv[1])))
s.listen()
print("ready", flush=True)
body = b'{"groups": [], "open": "http://evil.localhost:1/", "lent": []}'
while True:
    c, _ = s.accept()
    c.settimeout(2)
    try:
        got = c.recv(65536)
        print(repr(got), flush=True)
        c.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s" % (len(body), body))
    except OSError:
        pass
    c.close()
"""


def foreign(port):
    """Another account's program listening on 127.0.0.1:`port`, or None
    when this computer can't make one."""
    argv = ["unshare", "--map-auto", "--map-root-user", "setpriv", "--reuid=1", "--regid=1", "--clear-groups",
            "python3", "-I", "-c", FOREIGN, str(port)]
    try:
        held = subprocess.Popen(argv, cwd="/", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    except OSError:
        return None
    if held.stdout.readline().strip() != "ready":
        held.kill()
        return None
    return held


def owner_of_listener(port):
    """The uid /proc/net/tcp gives the listener on 127.0.0.1:`port`."""
    want = f"0100007F:{port:04X}"
    for line in Path("/proc/net/tcp").read_text().splitlines()[1:]:
        f = line.split()
        if f[1] == want and f[3] == "0A":
            return int(f[7])
    return None


home = case("another account's program on svrngs's port is sent nothing")
squat_port = closed_port()
data_dir(home, port=squat_port)
(home / ".svrngs/lends/garden.json").write_text(json.dumps({"port": closed_port(), "kind": "python3", "groups": ["a" * 64]}))
squat = foreign(squat_port)
check("another account's listener could be planted", squat is not None and owner_of_listener(squat_port) not in (None, os.getuid()), True)
try:
    got = state(home, "--full")
    asked = {verb: run(home, *args)[0] for verb, args in (
        ("approve", ("approve", "garden", "--token", "0f" * 32, "--pid", "4242@987654")),
        ("open", ("open",)), ("models", ("models",)))}
finally:
    if squat:
        squat.kill()
received = squat.communicate()[0] if squat else ""
check("its read is unreadable, never running", got["svrngs"], "unreadable")
check("and says another account's program answers there, and that it was sent nothing",
      ("account" in got.get("reason", ""), "sent it nothing" in got.get("reason", "")), (True, True))
check("approve, open and models each refuse, saying so",
      {verb: (a["ok"], "sent it nothing" in a.get("said", "")) for verb, a in asked.items()},
      {verb: (False, True) for verb in asked})
# Each connection it took is read, so whose it is can be told, then
# closed: it receives `b''` for each, and never a byte.
check("it was sent no byte on any connection, and never the token",
      ([r for r in received.splitlines() if r != "b''"], TOKEN in received), ([], False))
check("nothing was opened in the browser", (home / "browser-argv").exists(), False)

home = case("what runs here, and what is offered")
fake = Fake()
data_dir(home, port=fake.port)
puma_port, folder_port, lent_port, odd_port, pasta_port = closed_port(), closed_port(), closed_port(), closed_port(), closed_port()
(home / "notes-app").mkdir()
(home / ".svrngs/lends/lentone.json").write_text(json.dumps({"port": lent_port, "kind": "python3", "groups": []}))
odd, odd_start = serve(odd_port, home, comm=ODD_COMM, folder=home / "notes-app")
# As rootless Podman publishes a container's port: pasta listens, and
# passes each connection on into the container.
pasta, _ = serve(pasta_port, home, comm="pasta.avx2")
servers = [
    listen(puma_port, title=f"puma 8.1.2 (tcp://127.0.0.1:{puma_port}) [My Garden]"),
    listen(folder_port, folder=home / "notes-app"),
    listen(lent_port),
    odd,
    pasta,
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
check("a program that only passes a port on, as pasta does for a container, is offered as that, so it is never named as the program",
      [(offered.get(p) or {}).get("through") for p in (pasta_port, folder_port, puma_port)], [True, False, False])
check("what is already lent is not offered again", lent_port in offered, False)
check("svrngs's own port is not offered", fake.port in offered, False)
check("a browser's debug port (9222) could be planted", debug is not None, True)
check("and is never offered", 9222 in offered, False)
fake.close()

home = case("models: friends' lends that answer as one")
fake = Fake()
data_dir(home, port=fake.port)
# Each row with the key of the computer that lends it, as svrngs lists it
# (node.rs `Lending`): this computer's is GROUPS's "c"*64.
fake.lends = {"lent": [
    {"person": "Fedora", "key": "d" * 64, "name": "coder", "kind": "llama-server", "origin": f"http://model1.localhost:{fake.port}/"},
    {"person": "Fedora", "key": "d" * 64, "name": "garden", "kind": "puma", "origin": f"http://garden1.localhost:{fake.port}/"},
    {"person": "LittleMac", "key": "c" * 64, "name": "mine", "kind": "llama-server", "origin": f"http://mine1.localhost:{fake.port}/"},
    {"person": "LittleMac", "key": "e" * 64, "name": "namesake", "kind": "llama-server", "origin": f"http://model6.localhost:{fake.port}/"},
    {"person": "Mallory", "key": "f" * 64, "name": "elsewhere", "kind": "spot", "origin": "http://model2.localhost:1/"},
    {"person": "Fedora", "key": "d" * 64, "name": "asleep", "kind": "spot", "origin": f"http://model3.localhost:{fake.port}/", "answering": False},
    {"person": "Fedora", "key": "d" * 64, "name": "taken", "kind": "spot", "origin": f"http://model4.localhost:{fake.port}/", "answering": True, "held": "another"},
    {"person": "Fedora", "key": "d" * 64, "name": "newer", "kind": "spot", "origin": f"http://model5.localhost:{fake.port}/", "answering": True, "held": "paused"},
]}
fake.models = {"model1": ["qwen3-coder"], "mine1": ["mine"], "model2": ["x"], "model3": ["y"], "model4": ["z"], "model5": ["w"], "model6": ["v"]}
got, _ = run(home, "models")
check("two models found, one by a member who took your name", [(m["person"], m["name"], m["models"]) for m in got["models"]],
      [("Fedora", "coder", ["qwen3-coder"]), ("LittleMac", "namesake", ["v"])])
check("of three friends' lends asked at svrngs's own address", got["asked"], 3)
check("its address is the lend's, ending in v1", got["models"][0]["address"] if got["models"] else None, f"http://model1.localhost:{fake.port}/v1")
asked = [s["headers"].get("Host", "").split(".")[0] for s in fake.seen if s["path"] == "/v1/models"]
check("your own lend, by this computer's key, is not asked", "mine1" in asked, False)
check("a lend not at svrngs's own address is never sent the token", "model2" in asked, False)
check("a lend its lender says is not running is not asked", "model3" in asked, False)
check("nor one svrngs holds closed", "model4" in asked, False)
check("nor one held for a reason this helper doesn't know", "model5" in asked, False)
whole = state(home, "--full")
full = whole["lends"]["a" * 64]["lent"]
check("whether each is running, as its lender says, or not said", [l["answering"] for l in full], [None, None, None, None, None, False, True, True])
check("and whether svrngs holds it closed", [l["held"] for l in full], [None, None, None, None, None, None, "another", "unknown"])
check("this computer's key, and each row's lender's, pass through", (whole.get("key"), [l.get("key") for l in full][:4]),
      ("c" * 64, ["d" * 64, "d" * 64, "c" * 64, "e" * 64]))
fake.lends = {"lent": [{**fake.lends["lent"][0], "key": "not a key"}, {**fake.lends["lent"][0], "key": None}]}
check("a key that is none passes as none", [l["key"] for l in state(home, "--full")["lends"]["a" * 64]["lent"]], [None, None])
fake.close()

home = case("a held lend of this computer's: why, what svrngs read on its port, and its token")
fake = Fake()
data_dir(home, port=fake.port)
(home / "garden-app").mkdir()
garden_port, quiet_port, browser_port = closed_port(), closed_port(), closed_port()
for name, port in (("garden", garden_port), ("quiet", quiet_port), ("browser", browser_port), ("debug", 9222)):
    (home / f".svrngs/lends/{name}.json").write_text(json.dumps({"port": port, "kind": "python3", "groups": ["a" * 64]}))
garden, garden_start = serve(garden_port, home, comm=ODD_COMM, folder=home / "garden-app")
browser, browser_start = serve(browser_port, home, comm="chromium")
# This computer's own lends as svrngs lists them to it (door.rs `offered`
# for their lender): `held`, and for a held one with a port, `answers`
# (lend.rs `Answer`) and `token` (share.rs `token`), the token given only
# where approving it would be taken (share.rs `approve`, the one decider),
# as it is for another account's program on Linux and is not for a program
# listening only on another address; or, where svrngs couldn't read what
# answers, `unread` with its reason (uid.rs `Unread`) and no `answers`.
# Another person's lend says none of these (door.rs `lends`).
LISTED = "0f" * 32
own = lambda name, **row: {"person": "LittleMac", "key": "c" * 64, "name": name, "kind": "python3", "origin": f"http://{name}1.localhost:{fake.port}/", **row}
program = lambda server, start, folder: {"pid": server.pid, "start": start, "program": "python3", "folder": folder}
garden_said = program(garden, garden_start, "~/work/garden-app")
fake.lends = {"lent": [
    own("garden", held="unapproved", answering=True, answers=[garden_said], token=LISTED),
    own("quiet", held="another", answering=False, answers=[]),
    own("browser", held="unjudged", answering=True, answers=[program(browser, browser_start, "~")], token=LISTED),
    own("theirs", held="another", answering=True, answers=[{"account": UNNAMED}], token=LISTED),
    own("mixed", held="another", answering=True, answers=[garden_said, {"account": UNNAMED}], token=LISTED),
    own("far", held="another", answering=True, answers=[garden_said]),
    own("unread", held="unjudged", answering=True, answers=[]),
    own("gone", held="another", answering=True, answers=[program(garden, garden_start + 1, "~/garden-app")], token=LISTED),
    own("shapeless", held="another", answering=True, answers=[{"pid": "9"}], token=LISTED),
    own("spaced", held="another", answering=True, answers=[garden_said], token="0f 0f"),
    own("older", held="another", answering=True),
    own("failed", held="another", answering=True, unread={"why": "failed", "detail": "the read stopped"}),
    own("noreader", held="another", answering=True, unread={"why": "no_reader"}),
    own("newer", held="another", answering=True, unread={"why": "a newer svrngs's"}),
    own("debug", held="another", answering=True, answers=[{"account": UNNAMED}], token=LISTED),
    own("root", held="another", answering=True, answers=[{"account": "0"}], token=LISTED),
    own("accounts", held="another", answering=True, answers=[{"account": "0"}, {"account": UNNAMED}], token=LISTED),
    own("paused", held="paused"), own("shaped", held={"why": "a newer svrngs's"}), own("listed", held=["another"]),
    own("open", answering=True), own("nulled", held=None), own("blank", held=""),
    {"person": "Fedora", "key": "d" * 64, "name": "theirs-open", "kind": "spot", "origin": f"http://f1.localhost:{fake.port}/", "answering": True},
    # A member who took this computer's person's name, listing a held lend
    # with what answers, as a friend's row may say anything.
    {**own("namesake", held="another", answering=True, answers=[garden_said], token=LISTED), "key": "e" * 64},
]}
try:
    full, quick = state(home, "--full"), state(home, "--here")
finally:
    garden.kill()
    browser.kill()
rows_said = full["lends"]["a" * 64]["lent"]
check("svrngs's reasons pass through, unapproved its own; one this helper doesn't know is held all the same",
      [l["held"] for l in rows_said],
      ["unapproved", "another", "unjudged", "another", "another", "another", "unjudged", "another", "another", "another", "another",
       "another", "another", "another", "another", "another", "another", "unknown", "unknown", "unknown", None, None, None, None, "another"])
check("each held one's token passes through; one that is no token is none",
      [l["token"] for l in rows_said][:10], [LISTED, None, LISTED, LISTED, LISTED, None, None, LISTED, LISTED, None])
check("what svrngs read on its port passes through", rows_said[0]["answers"], [garden_said])
check("why svrngs couldn't read it passes through, a reason this helper doesn't know as unknown; read, none",
      {l["name"]: l["unread"] for l in rows_said if l["unread"] is not None or l["name"] in ("garden", "quiet")},
      {"failed": "failed", "noreader": "no_reader", "newer": "unknown", "garden": None, "quiet": None})
now = {l["name"]: l.get("now", "unsaid") for l in rows_said}
check("its line: the process svrngs read, by its pid and start",
      {k: (now["garden"] or {}).get(k) for k in ("pid", "start")}, {"pid": garden.pid, "start": garden_start})
check("named by the program and the whole folder svrngs read, never its own command or the folder's last name",
      {k: (now["garden"] or {}).get(k) for k in ("program", "folder", "name", "said")},
      {"program": "python3", "folder": "~/work/garden-app", "name": None, "said": "python3 in ~/work/garden-app"})
check("nothing svrngs could name, and its port took no connection: nothing answers", now["quiet"], None)
other = {"pid": None, "start": None, "program": "", "folder": ""}
for name, why in (("browser", "a program on the deny list, by its command"), ("far", "what svrngs gave no token for"),
                  ("unread", "what took a connection that svrngs couldn't name"), ("shapeless", "an answer in no shape svrngs gives"),
                  ("spaced", "a token that is none"), ("debug", "another account's program on a port on the deny list")):
    check(f"{why}: nothing for Keep sharing it to name", now[name], other)
check("another account's program svrngs listed a token for: said by its account, with no process to keep it to",
      now["theirs"], {**other, "account": UNNAMED, "said": f"a program of the account {UNNAMED}"})
check("another account named by its name on this computer, not its number", now["root"],
      {**other, "account": "root", "said": "a program of the account root"})
check("every one svrngs listed is said, as its token approves them all, not the first alone",
      [now[n]["said"] for n in ("accounts", "mixed")],
      [f"a program of the account root and a program of the account {UNNAMED}",
       f"python3 in ~/work/garden-app and a program of the account {UNNAMED}"])
check("a program of yours beside another account's: said whole, by the other account, with no process to keep it to",
      now["mixed"], {**other, "account": UNNAMED, "said": f"python3 in ~/work/garden-app and a program of the account {UNNAMED}"})
check("what svrngs couldn't read: no line of what answers, its reason said instead",
      [now[n] for n in ("failed", "noreader", "newer")], ["unsaid"] * 3)
check("a process gone since svrngs read it: said in svrngs's words, its pid and start as svrngs read them",
      now["gone"], {"pid": garden.pid, "start": garden_start + 1, "program": "python3", "folder": "~/garden-app",
                    "said": "python3 in ~/garden-app"})
check("a row with no answers, from an svrngs before 1.13.0, or not held, or not this computer's: no line",
      [now[n] for n in ("older", "paused", "open", "theirs-open")], ["unsaid"] * 4)
check("another computer's row, its person named as yours, gets no line of what answers here, whatever it lists",
      now["namesake"], "unsaid")
quick_now = {m["name"]: m.get("now") for m in quick["mine"]}
check("the quick read asks no group, and keeps this computer's own read of each lend's port",
      ("lends" in quick, (quick_now["garden"] or {}).get("pid"), quick_now["quiet"]), (False, garden.pid, None))
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
      "Lent garden: python3 in ~/garden-app. svrngs checks port 3000 before each connection it carries there. "
      "While another program is on the port, it is closed.\n"
      "svrngs doesn't know puma, so your friends can reach every part of it that its own sign-in allows.")
got, _ = run(home, "share", "3000", "a" * 64, "garden", "--program", "puma", "--pid", "4242@987654")
check("svrngs is told the process the panel showed, by its pid and start", (got["ok"], (home / "svrngs-argv").read_text().split()[-2:]), (True, ["--pid", "4242@987654"]))
# svrngs's kind for a port its table knows comes with the terms it ships
# for it (svrngs share.rs `kind_of`: a --program given wins over it).
calls = lambda: (home / "svrngs-calls").read_text().splitlines()
lend_as = f"share {{}} --group {'a' * 64} --name {{}}{{}} --pid 4242@987654"
(home / "svrngs-calls").unlink()
got, _ = run(home, "share", "8096", "a" * 64, "films", "--program", "pasta.avx2", "--pid", "4242@987654")
check("a port svrngs knows is lent as svrngs knows it: the program the panel read there is never said",
      (got["ok"], calls()), (True, [lend_as.format(8096, "films", "")]))
(home / "svrngs-calls").unlink()
got, _ = run(home, "share", "3000", "a" * 64, "garden", "--program", "puma", "--pid", "4242@987654")
check("a port svrngs doesn't know: svrngs is asked first, and told the program only when it asks",
      (got["ok"], calls()), (True, [lend_as.format(3000, "garden", ""), lend_as.format(3000, "garden", " --program puma")]))
(home / "svrngs-calls").unlink()
got, _ = run(home, "share", "8101", "a" * 64, "coder", "--pid", "4242@987654")
check("a port svrngs doesn't know, and no program named: nothing lent, the program asked for, with those svrngs knows",
      (got["ok"], got.get("asks"), "llama-server" in (got.get("known") or []), len(calls())), (False, "program", True, 1))
check("and said plainly", got["said"], "svrngs doesn't know what answers on port 8101. Say which program it is, then press Lend again.")
for bad in ("42; rm", "4242", "4242@", "@99", "4242@99@1"):
    got, _ = run(home, "share", "3000", "a" * 64, "garden", "--program", "puma", "--pid", bad)
    check(f"--pid {bad!r}, not a process and its start, is refused, svrngs not run",
          (got["ok"], (home / "svrngs-argv").read_text().split()[-2:]), (False, ["--pid", "4242@987654"]))
NEWER = "Lending from here needs svrngs 1.13.1 or later. Update svrngs on its home page, then try again."
for old in ("1.12.1", "1.12.2"):
    (home / "old-svrngs").write_text(old)
    got, _ = run(home, "share", "3000", "a" * 64, "garden", "--program", "puma", "--pid", "4242@987654")
    check(f"svrngs {old}, before --pid <pid>@<start>: lending says what to do", (got["ok"], got["said"]), (False, NEWER))
(home / "old-svrngs").unlink()
# What svrngs refuses a share with once it runs, at 0b36268e: share.rs:276,
# :278, :284 (ShareRefusal), cli.rs:585 (NoGroup), and a group's own terms
# (share.rs:268, Carries), which quote what to type in backticks.
for words in ("svrngs can't share port 3000: that program stopped; choose it again.",
              "svrngs can't share port 3000: another program also listens on port 3000. Stop it, or choose that one, then share it again.",
              "svrngs can't share port 3000: what answers on port 3000 changed; choose it again.",
              "you are in no group called " + "a" * 64 + " on this computer",
              "your group's programs/puma.txt says puma is lent as tcp, not as a page: `svrngs share <port> --tcp --program puma --group <group>`"):
    (home / "refuse").write_text(words)
    got, _ = run(home, "share", "3000", "a" * 64, "garden", "--program", "puma", "--pid", "4242@987654")
    check(f"svrngs's refusal is said whole: …{words[-48:]}", (got["ok"], got["said"]), (False, f"svrngs: {words}"))
(home / "refuse").unlink()
# What svrngs refuses before it runs, with its usage after (main.rs): a
# command's name svrngs won't take as --program (cli.rs:312, :327).
(home / "unparsed").write_text(f"--program `{ODD_COMM}` is not a program's name: letters, digits, - and _ only")
got, _ = run(home, "share", "3000", "a" * 64, "garden", "--program", ODD_COMM, "--pid", "4242@987654")
check("a refusal of what svrngs couldn't parse is said whole, without the usage after it", (got["ok"], got["said"]),
      (False, f"svrngs: --program `{ODD_COMM}` is not a program's name: letters, digits, - and _ only"))
(home / "unparsed").unlink()
got, _ = run(home, "unshare", "garden")
check("stopped", (got["ok"], (home / "svrngs-argv").read_text().split()), (True, ["unshare", "garden"]))
got, _ = run(home, "start")
check("start asks svrngs to restart itself", (got["ok"], (home / "svrngs-argv").read_text().split()), (True, ["restart"]))

home = case("keep sharing a held lend: what its row showed, by its token and its process")
fake = Fake()
data_dir(home, port=fake.port)
fake.ports = {"garden": {"port": 3000, "token": LISTED, "processes": {4242: 987654},
                         "answers": [{"pid": 4242, "start": 987654, "program": "python3", "folder": "~/garden-app"}]}}
posted = lambda: [(s["path"], s["headers"].get("Content-Type"), json.loads(s["body"])) for s in fake.seen if s["path"].endswith("/approve")]
got, _ = run(home, "approve", "garden", "--token", LISTED, "--pid", "4242@987654")
check("svrngs is sent the token the row was listed with, and the process its line named, and nothing else",
      posted(), [("/v1/lends/garden/approve", "application/json", {"token": LISTED, "pid": 4242, "start": 987654})])
check("as an app on this computer: with the token, never an Origin",
      [(s["headers"].get("Authorization"), "Origin" in s["headers"]) for s in fake.seen], [(f"Bearer {TOKEN}", False)])
check("svrngs approves it", fake.approved, ["garden"])
check("what svrngs kept it to is said, as `svrngs approve` says it (cli.rs:1746)", (got["ok"], got["said"]),
      (True, "garden is kept to python3 in ~/garden-app now."))
check("the svrngs command is never run to approve: the API takes the token the row was listed with",
      (home / "svrngs-argv").exists(), False)
fake.ports["theirs"] = {"port": 3003, "token": LISTED, "processes": {}, "answers": [{"account": "0"}]}
asked = len(posted())
got, _ = run(home, "approve", "theirs", "--token", LISTED)
check("a share is kept only to a process of this account's: the token alone is refused, svrngs not asked",
      (got["ok"], posted()[asked:], fake.approved), (False, [], ["garden"]))
# svrngs's refusals, as its approve route answers them (surface.rs:177-208,
# share.rs:276-288, door.rs:287 at 0b36268e): 403, its words in `error`.
for args, said in ((["--token", "1e" * 32, "--pid", "4242@987654"], "svrngs can't share port 3000: what answers on port 3000 changed; choose it again."),
                   (["--token", LISTED, "--pid", "4242@1"], "svrngs can't share port 3000: that program stopped; choose it again."),
                   (["--token", LISTED, "--pid", "77@987654"], "svrngs can't share port 3000: another program also listens on port 3000. Stop it, or choose that one, then share it again.")):
    got, _ = run(home, "approve", "garden", *args)
    check(f"svrngs's refusal is said as it said it: …{said[30:62]}…", (got["ok"], got["said"]), (False, said))
got, _ = run(home, "approve", "notes", "--token", LISTED, "--pid", "4242@987654")
check("a share svrngs doesn't have: its words", (got["ok"], got["said"]), (False, "nothing is shared from a port here by the name notes"))
check("nothing it refused is approved", fake.approved, ["garden"])
for args in (["garden"], ["garden", "--pid", "4242@987654"],
             ["garden", "--token", "--pid", "4242@987654"], ["garden", "--token", "0f 0f", "--pid", "4242@987654"],
             ["garden", "--token", LISTED, "--pid", "4242"], ["garden", "--token", LISTED, "--pid"],
             ["--replace", "--token", LISTED, "--pid", "4242@1"], ["-x", "--token", LISTED, "--pid", "4242@1"]):
    asked = len(posted())
    got, _ = run(home, "approve", *args)
    check(f"approve {' '.join(args)}: refused, svrngs not asked", (got["ok"], len(posted()) - asked), (False, 0))
fake.close()
fake = Fake("old")
data_dir(home, port=fake.port)
got, _ = run(home, "approve", "garden", "--token", LISTED, "--pid", "4242@987654")
check("an svrngs from before approving, with no such route: what to do", (got["ok"], got["said"]), (False, NEWER))
fake.close()
data_dir(home, port=closed_port())
got, _ = run(home, "approve", "garden", "--token", LISTED, "--pid", "4242@987654")
check("svrngs stopped: said so", (got["ok"], got["said"]), (False, "svrngs isn't running"))

print("ALL OK" if not failures else f"{len(failures)} FAILED")
SCRATCH.cleanup()
sys.exit(1 if failures else 0)
