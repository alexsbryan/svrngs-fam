#!/usr/bin/python3 -I
"""bin/svrngs-fam's `state`, against a fake svrngs, in a scratch home.

What it guards: the icon's four states rest on the helper telling them apart.
A failure that is not a refused connection must be "unreadable", never
"stopped", and a running svrngs must be read with the token and no Origin.
Each case runs the real helper as the shell does, with an argv list.
"""

import fcntl
import http.client
import importlib.machinery
import importlib.util
import json
import os
import pwd
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_svrngs import TOKEN, Fake  # noqa: E402
from fake_svrngs import REFUSED_TOKEN  # noqa: E402
from fake_svrngs import ask as fake_ask  # noqa: E402
from fake_svrngs import proof as fake_proof  # noqa: E402

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
# What the helper says to an svrngs older than the panel needs: 1.13.3
# carries the update floor and Play at a lend's address.
NEWER = "This needs svrngs 1.13.3 or later. Update svrngs on its home page, then try again."


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
# `version` says $HOME/installed-version, 1.13.2 when there is none, and
# `restart` adds a line to $HOME/restarts.
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
  version) printf 'svrngs %s (0123abcd)\n' "$(cat "$HOME/installed-version" 2>/dev/null || echo 1.13.2)" ;;
  restart)
    echo restart >> "$HOME/restarts"
    # Back once the svrngs it stopped has stopped, as `systemctl restart`
    # is, when a stand-in svrngs stops for it ($HOME/stops).
    if [ -e "$HOME/stops" ]; then
      for _ in $(seq 100); do [ -e "$HOME/stopped" ] && break; sleep 0.05; done
    fi
    echo "svrngs is restarting. Your home page comes back in a moment." ;;
  link) cat "$HOME/link-said" ;;
esac
"""

# Stand in for the browser and the clipboard, keeping what they were given.
STUBS = {
    "omarchy-launch-browser": '#!/bin/bash\nprintf "%s\\n" "$@" > "$HOME/browser-argv"\n',
    "wl-copy": '#!/bin/bash\ncat > "$HOME/clipboard"\n',
    # systemctl, as the helper asks it what svrngs's login service starts:
    # $HOME/service holds its program, then its SVRNGS_DIR, a line each;
    # without them, the stand-in svrngs command and none. With
    # $HOME/no-service, systemd keeps no such service.
    "systemctl": r"""#!/bin/bash
[ "$*" = "--user show svrngs.service --property=LoadState,ExecStart,Environment" ] || exit 1
if [ -e "$HOME/no-service" ]; then printf 'LoadState=not-found\nExecStart=\nEnvironment=\n'; exit 0; fi
program=$(sed -n 1p "$HOME/service" 2>/dev/null); dir=$(sed -n 2p "$HOME/service" 2>/dev/null)
program=${program:-$HOME/.local/bin/svrngs}
echo "LoadState=loaded"
echo "ExecStart={ path=$program ; argv[]=$program ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }"
echo "Environment=${dir:+SVRNGS_DIR=$dir }PATH=/usr/bin:/bin"
""",
}


# The program this test runs as, which serves the stand-in svrngs (Fake).
SELF = os.readlink("/proc/self/exe")
me = os.getuid()


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
    try:
        done = subprocess.run([str(HELPER), *args], capture_output=True, text=True, env=env, timeout=30)
    except subprocess.TimeoutExpired:
        return {"ok": False, "svrngs": "timed out", "said": "the helper didn't answer within 30 s"}, ""
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
check("asked with each connection's code, never the token",
      (all(s["headers"].get("Authorization", "").startswith("Svrngs ") for s in fake.seen if s["path"] != "/v1/proof"),
       any(TOKEN in v for s in fake.seen for v in s["headers"].values())), (True, False))
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

home = case("a token file holding a token svrngs doesn't hold")
fake = Fake()
data_dir(home, port=fake.port, token="not-the-token-at-all")
got = state(home)
check("another token: unreadable", got["svrngs"], "unreadable")
check("another token: svrngs's proof isn't for it, so what answers isn't this svrngs, and was sent nothing",
      ("something other than your svrngs" in got.get("reason", ""), [s["path"] for s in fake.seen]), (True, ["/v1/proof"]))
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

def helper_module():
    """The helper itself, loaded as a module, so one of its functions can be
    given input no computer here can be made to show on cue."""
    loader = importlib.machinery.SourceFileLoader("svrngs_fam", str(HELPER))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


def ends(seen):
    """Each connection the stand-in svrngs took, by its number: the paths
    asked on it, in order."""
    found = {}
    for s in seen:
        found.setdefault(s["conn"], []).append(s["path"])
    return found


# svrngs's proof as svrngs and Give make it too, for these inputs: so the
# three can't drift apart (svrngs POST /v1/proof).
VECTORS = (
    ("test-token", "00" * 32, "127.0.0.1:50000", "127.0.0.1:40000", "e5a8107be851bcf50a977799f3dd752fb8a7db2607128372ab6936aa42fa046f"),
    ("test-token", "ab" * 32, "[::1]:50001", "[::1]:40000", "bdaab3ee1e00b484f65ee220d690a8b5d462ecff25a6d9f5ac898148dec38472"),
)
case("svrngs's proof: the test vectors svrngs and Give are held to")
helper = helper_module()
check("the helper's proof of each", [helper.proof(*v[:4]) for v in VECTORS], [v[4] for v in VECTORS])
check("the stand-in svrngs's, made apart from it", [fake_proof(*v[:4]) for v in VECTORS], [v[4] for v in VECTORS])
check("an end of a connection named as svrngs names it, by Rust's SocketAddr",
      [helper.end(("127.0.0.1", 50000)), helper.end(("::1", 50001, 0, 0))], ["127.0.0.1:50000", "[::1]:50001"])
# The code a program asks svrngs with on a connection, for a nonce svrngs
# gave there, as svrngs 1.13.3 takes it.
ASKS = (
    ("test-token", "11" * 32, "127.0.0.1:50000", "127.0.0.1:40000", "12948174292b9641bc74ea49e12918bd39931f81cddef77ae9c04d46e6585245"),
    ("test-token", "cd" * 32, "[::1]:50001", "[::1]:40000", "d806666da2d6c78fa07dc51fe301f57596fed866e930680a54e5bbc9de104f1c"),
)
check("the helper's ask of each", [helper.ask_for(*v[:4]) for v in ASKS], [v[4] for v in ASKS])
check("the stand-in svrngs's, made apart from it", [fake_ask(*v[:4]) for v in ASKS], [v[4] for v in ASKS])


def asking(port, *steps):
    """What the stand-in svrngs answers to raw requests, each on a
    connection of its own number: ("prove", n) asks a proof on connection
    n, keeping its nonce; ("ask", n, how) asks /v1/groups on connection n,
    with `how(conns, nonces)` as its Authorization. Each step's status,
    and for an ask, svrngs's words when it refused."""
    conns, nonces, said = {}, {}, []
    for step in steps:
        conn = conns.setdefault(step[1], http.client.HTTPConnection("127.0.0.1", port, timeout=5))
        if step[0] == "prove":
            conn.request("POST", "/v1/proof", body=json.dumps({"challenge": "00" * 32}), headers={"Content-Type": "application/json"})
            reply = conn.getresponse()
            nonces[step[1]] = json.loads(reply.read()).get("nonce")
            said.append(reply.status)
        else:
            conn.request("GET", "/v1/groups", headers={"Authorization": step[2](conns, nonces)})
            reply = conn.getresponse()
            body = json.loads(reply.read())
            said.append((reply.status, body.get("error")))
    for conn in conns.values():
        conn.close()
    return said


def code(n):
    """The ask made for connection `n`: its nonce and its two ends."""
    def made(conns, nonces):
        sock = conns[n].sock
        return f"Svrngs {fake_ask(TOKEN, nonces[n], helper.end(sock.getsockname()), helper.end(sock.getpeername()))}"
    return made


home = case("the stand-in svrngs, as svrngs: the token itself refused, and only a connection's own code taken")
fake = Fake()
said = asking(fake.port, ("prove", 1), ("ask", 1, lambda c, n: f"Bearer {TOKEN}"), ("ask", 1, code(1)),
              ("prove", 2), ("ask", 2, code(1)), ("ask", 3, code(1)), ("ask", 2, code(2)))
check("Bearer and the token: refused, saying what to use instead", said[1], (401, REFUSED_TOKEN))
check("the code for that connection: taken", said[2][0], 200)
check("another connection's code: refused", said[4][0], 401)
check("a code on a connection that asked no proof: refused", said[5][0], 401)
check("each connection's own: taken", said[6][0], 200)
fake.close()

home = case("svrngs proves it holds the token, then is asked with it on that same connection")
fake = Fake()
data_dir(home, port=fake.port)
got = state(home, "--full")
proofs = [s for s in fake.seen if s["path"] == "/v1/proof"]
check("running", got["svrngs"], "running")
check("each connection carries one challenge, then one request with the token, and no other",
      sorted({tuple(p == "/v1/proof" for p in paths) for paths in ends(fake.seen).values()}), [(True, False)])
check("the challenge is sent with no token, no Origin and nothing else a browser sends",
      [k for s in proofs for k in s["headers"] if k.lower() in ("authorization", "origin") or k.lower().startswith("sec-fetch")], [])
challenges = [json.loads(s["body"]) for s in proofs]
check("and is 32 bytes in hex, new each time",
      (all(set(c) == {"challenge"} and re.fullmatch(r"[0-9a-f]{64}", c["challenge"]) for c in challenges),
       len({c["challenge"] for c in challenges}) == len(challenges) > 1), (True, True))
fake.close()

home = case("svrngs while it starts: listening, not yet answering, is waited for")
fake = Fake(serving_after=1.5)
data_dir(home, port=fake.port)
check("running, once it answers", state(home)["svrngs"], "running")
fake.close()

home = case("svrngs that closes the connection it proved itself on is sent nothing, on it or on another")
fake = Fake("closes")
data_dir(home, port=fake.port)
got = state(home)
check("unreadable, saying so", (got["svrngs"], "closed the connection it proved itself on" in got.get("reason", ""),
                                "none of your token" in got.get("reason", "")), ("unreadable", True, True))
check("it was asked only for its proof, never with the token",
      ([s["path"] for s in fake.seen], any("Authorization" in s["headers"] for s in fake.seen)), (["/v1/proof"], False))
fake.close()

# A program at svrngs's address that isn't svrngs and can't read its token.
# It answers every request as svrngs answers a challenge, with a nonce and
# a proof made with a token of its own on that connection's own ends, or,
# told "404" after its port, as an svrngs before 1.13.3 does. It keeps the
# connection open for the next, and writes down every request, whole, a
# line of JSON each.
ANSWER = r"""
import hashlib, hmac, json, re, socket, sys

def named(address):
    host, port = address[:2]
    return f"[{host}]:{port}" if ":" in host else f"{host}:{port}"

def answer(c):
    c.settimeout(3)
    got = b""
    try:
        while True:
            while b"\r\n\r\n" not in got:
                more = c.recv(65536)
                if not more:
                    return
                got += more
            head, _, got = got.partition(b"\r\n\r\n")
            length = re.search(rb"(?im)^content-length:[ \t]*(\d+)", head)
            length = int(length.group(1)) if length else 0
            while len(got) < length:
                more = c.recv(65536)
                if not more:
                    break
                got += more
            body, got = got[:length], got[length:]
            print(json.dumps({"head": head.decode("latin-1"), "body": body.decode("latin-1")}), flush=True)
            if sys.argv[2:3] == ["404"]:
                c.sendall(b"HTTP/1.1 404 Not Found\r\ncontent-length: 0\r\n\r\n")
                continue
            try:
                challenge = str(json.loads(body)["challenge"])
            except (ValueError, KeyError, TypeError):
                challenge = ""
            said = "\n".join(("svrngs proof v1", challenge, named(c.getpeername()), named(c.getsockname())))
            made = hmac.new(b"a token of its own", said.encode(), hashlib.sha256).hexdigest()
            raw = json.dumps({"proof": made, "nonce": "ab" * 32, "groups": [], "lent": [], "open": "http://evil.localhost:1/"}).encode()
            c.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s" % (len(raw), raw))
    except OSError:
        pass
    finally:
        c.close()

def listening():
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", int(sys.argv[1])))
    s.listen()
    return s
"""
SQUAT = ANSWER + r"""
s = listening()
print("ready", flush=True)
while True:
    answer(s.accept()[0])
"""

# Another account's program on svrngs's port, while svrngs is down: a uid
# of this account's own subordinate range (/etc/subuid), which is no
# account here, as `unshare --map-auto` gives it without root.


def foreign(port):
    """Another account's program listening on 127.0.0.1:`port`, or None
    when this computer can't make one."""
    argv = ["unshare", "--map-auto", "--map-root-user", "setpriv", "--reuid=1", "--regid=1", "--clear-groups",
            "python3", "-I", "-c", SQUAT, str(port)]
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


def squatted(home, squat, port, installed=True, also=()):
    """The helper's full read, what approve, open, models and play said,
    and every request `squat`, listening on svrngs's `port`, was sent, as
    it wrote them down; `also` are processes of its own to stop with it."""
    try:
        got = state(home, "--full", installed=installed)
        asked = {verb: run(home, *args, installed=installed)[0] for verb, args in (
            ("approve", ("approve", "garden", "--token", "0f" * 32, "--pid", "4242@987654")),
            ("open", ("open",)), ("models", ("models",)), ("play", ("play", "d" * 64, "coder")))}
    finally:
        for pid in also:
            os.kill(pid, signal.SIGKILL)
        squat.kill()
    out = squat.communicate()[0]
    return got, asked, [json.loads(line) for line in out.splitlines() if line.startswith("{")], out


def sent_nothing(got, asked, received, out, home):
    check("its read is unreadable, saying something other than your svrngs answers and that it was sent nothing",
          (got["svrngs"], "something other than your svrngs" in got.get("reason", ""), "none of your token" in got.get("reason", "")),
          ("unreadable", True, True))
    check("approve, open, models and play each refuse, saying so",
          {verb: (a["ok"], "none of your token" in a.get("said", "")) for verb, a in asked.items()},
          {verb: (False, True) for verb in asked})
    check("it was asked for a proof on each connection, and sent nothing more",
          (len(received) >= 5, [r["head"].split("\r\n")[0] for r in received if not r["head"].startswith("POST /v1/proof ")]), (True, []))
    check("no byte of the token, ever", (TOKEN in out, [r["head"] for r in received if "bearer" in r["head"].lower()]), (False, []))
    check("nor any code to ask with", [r["head"] for r in received if "authorization:" in r["head"].lower()], [])
    check("nothing was opened in the browser", (home / "browser-argv").exists(), False)


home = case("another account's program on svrngs's port is sent no byte of the token")
squat_port = closed_port()
data_dir(home, port=squat_port)
(home / ".svrngs/lends/garden.json").write_text(json.dumps({"port": closed_port(), "kind": "python3", "groups": ["a" * 64]}))
squat = foreign(squat_port)
check("another account's listener could be planted", squat is not None and owner_of_listener(squat_port) not in (None, os.getuid()), True)
if squat:
    sent_nothing(*squatted(home, squat, squat_port), home)

home = case("a program of this account's on svrngs's port is sent no byte of the token")
squat_port = closed_port()
data_dir(home, port=squat_port)
squat = subprocess.Popen(["python3", "-I", "-c", SQUAT, str(squat_port)], cwd="/", stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True)
check("this account's listener could be planted", (squat.stdout.readline().strip(), owner_of_listener(squat_port)), ("ready", me))
sent_nothing(*squatted(home, squat, squat_port), home)

# The same program in a sandbox of this account's that can run svrngs's own
# file but not read its token. Its child runs that file, ~/.local/bin/svrngs
# where svrngs's installer puts it (svrngs web/install.sh `bin`; here a copy
# of this test's python, as the stand-in svrngs is a python one), takes each
# connection and keeps it, and hands it back to be read: so the process that
# holds the connection runs svrngs's own file, as a check of whose program
# took it reads it, and another reads what it is sent.
HOLD = r"""
import socket, sys
s, back = socket.socket(fileno=int(sys.argv[1])), socket.socket(fileno=int(sys.argv[2]))
back.send(b"r")
kept = []
while True:
    c = s.accept()[0]
    kept.append(c)
    socket.send_fds(back, [b"c"], [c.fileno()])
"""
EXEC_SQUAT = ANSWER + f"HOLD = {HOLD!r}\n" + r"""
import subprocess
s = listening()
mine, theirs = socket.socketpair()
child = subprocess.Popen([sys.argv[2], "-I", "-c", HOLD, str(s.fileno()), str(theirs.fileno())],
                         pass_fds=(s.fileno(), theirs.fileno()), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
mine.recv(1)
print("ready", child.pid, flush=True)
while True:
    answer(socket.socket(fileno=socket.recv_fds(mine, 1, 1)[1][0]))
"""
home = case("one whose child runs svrngs's own file and keeps each connection, while it reads them, is sent no byte of the token")
squat_port = closed_port()
data_dir(home, port=squat_port)
svrngs_file = home / ".local/bin/svrngs"
svrngs_file.parent.mkdir(parents=True)
shutil.copy(SELF, svrngs_file)
squat = subprocess.Popen(["python3", "-I", "-c", EXEC_SQUAT, str(squat_port), str(svrngs_file)], cwd="/",
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
ready = squat.stdout.readline().split()
child = int(ready[1]) if len(ready) == 2 and ready[0] == "ready" else None
check("it could be planted: its child runs svrngs's own file, and it doesn't",
      (child is not None, child and os.readlink(f"/proc/{child}/exe"), os.readlink(f"/proc/{squat.pid}/exe") != str(svrngs_file)),
      (True, str(svrngs_file), True))
sent_nothing(*squatted(home, squat, squat_port, installed=False, also=[child] if child else []), home)


class Relay:
    """A program at svrngs's address that passes each connection on to
    svrngs where it listens, at `to`, byte for byte both ways, and keeps
    what it is sent."""

    def __init__(self, port, to):
        self.to, self.sent = to, []
        self.server = socket.socket()
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", port))
        self.server.listen()
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                near = self.server.accept()[0]
            except OSError:
                return
            far = socket.create_connection(("127.0.0.1", self.to))
            threading.Thread(target=self.carry, args=(near, far, self.sent), daemon=True).start()
            threading.Thread(target=self.carry, args=(far, near, []), daemon=True).start()

    @staticmethod
    def carry(source, sink, kept):
        """One way of a connection, closed on as the other end closed it."""
        try:
            while data := source.recv(65536):
                kept.append(data)
                sink.sendall(data)
            sink.shutdown(socket.SHUT_WR)
        except OSError:
            pass

    def close(self):
        self.server.close()


home = case("a relay on svrngs's port, to svrngs itself, which proves for the relay's connection: sent no byte of the token")
fake = Fake()
squat_port = closed_port()
data_dir(home, port=squat_port)
relay = Relay(squat_port, fake.port)
try:
    got = state(home)
finally:
    relay.close()
check("unreadable, saying something other than your svrngs answers and that it was sent nothing",
      (got["svrngs"], "something other than your svrngs" in got.get("reason", ""), "none of your token" in got.get("reason", "")),
      ("unreadable", True, True))
check("svrngs was asked for its proof through the relay, and proved it with its token, on the relay's connection",
      [s["path"] for s in fake.seen], ["/v1/proof"])
check("never the token: through the relay, or to svrngs",
      (TOKEN in b"".join(relay.sent).decode("latin-1"), any("Authorization" in s["headers"] for s in fake.seen)), (False, False))
check("svrngs, asked at its own port, is read", state(home, data=data_dir(home / "direct", port=fake.port))["svrngs"], "running")
fake.close()

case("what listens at svrngs's address and never answers is waited for, then sent nothing")
waiting = socket.socket()
waiting.bind(("127.0.0.1", 0))
waiting.listen()
helper = helper_module()
helper.PROOF_WITHIN = 0.3
began = time.monotonic()
try:
    helper.dial(waiting.getsockname(), TOKEN)
    said = None
except helper.Unreadable as e:
    said = str(e)
waited = time.monotonic() - began
waiting.close()
check("unreadable once PROOF_WITHIN has passed, saying so", (said is not None and "didn't show it is your svrngs" in said, 0.3 <= waited < 3),
      (True, True))


def dribbled(listener, after):
    """One connection to `listener` answered as svrngs answers a challenge,
    whole and in its shape, its proof made with the token and a nonce in
    it, a byte every 20 ms; what else it is sent, kept in `after`."""
    c = listener.accept()[0]
    with c:
        got = b""
        while b"\r\n\r\n" not in got:
            got += c.recv(65536)
        head, _, body = got.partition(b"\r\n\r\n")
        length = int(re.search(rb"(?i)\r\ncontent-length: *(\d+)", head)[1])
        while len(body) < length:
            body += c.recv(65536)
        shown = fake_proof(TOKEN, json.loads(body)["challenge"], helper.end(c.getpeername()), helper.end(c.getsockname()))
        said = json.dumps({"proof": shown, "nonce": "11" * 32}).encode()
        answer = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s" % (len(said), said)
        try:
            for i in range(len(answer)):
                c.sendall(answer[i:i + 1])
                time.sleep(0.02)
            c.settimeout(1)
            while more := c.recv(65536):
                after.append(more)
        except OSError:
            pass


case("what proves at svrngs's address a byte at a time, too slowly to finish within PROOF_WITHIN, is asked nothing")
slow = socket.socket()
slow.bind(("127.0.0.1", 0))
slow.listen()
after = []
dribbling = threading.Thread(target=dribbled, args=(slow, after), daemon=True)
dribbling.start()
helper = helper_module()
helper.PROOF_WITHIN = 0.3
began = time.monotonic()
try:
    helper.request(slow.getsockname(), TOKEN, "GET", "/v1/groups")
    said = None
except helper.Unreadable as e:
    said = str(e)
waited = time.monotonic() - began
dribbling.join(10)
slow.close()
check("unreadable once PROOF_WITHIN has passed in all, though a byte came well within it each time",
      (said is not None and "didn't show it is your svrngs" in said, 0.3 <= waited < 1.5), (True, True))
check("and nothing asked of it after its proof", after, [])

ACTIONS = (("approve", ("approve", "garden", "--token", "0f" * 32, "--pid", "4242@987654")),
           ("open", ("open",)), ("models", ("models",)), ("play", ("play", "d" * 64, "coder")))
RESTARTED = "svrngs was updated, so it restarted to use the new one."


def lines(path):
    return path.read_text().splitlines() if path.exists() else []


def restarts(home):
    """Each `svrngs restart` the stand-in svrngs command was run for."""
    return lines(home / "restarts")


def holding(data):
    """svrngs's data-dir lock, held as a running svrngs holds it (svrngs
    cli.rs `claim`: File::try_lock, a flock on Linux), until closed."""
    held = open(data / "lock", "w")
    fcntl.flock(held, fcntl.LOCK_EX)
    return held


def older_answers(home, fake):
    """What the helper read, and what each action said, of an svrngs from
    before 1.13.3 holding its data dir."""
    got = state(home, "--full")
    return got, {verb: run(home, *args)[0] for verb, args in ACTIONS}


def sent_none(fake):
    check("it was asked only for its proof, never with the token",
          ({s["path"] for s in fake.seen}, any("Authorization" in s["headers"] for s in fake.seen)), ({"/v1/proof"}, False))


# An svrngs from before 1.13.3 holding its data dir, while its login
# service starts an svrngs that is older too, or says no version: told so,
# by that program, and never restarted. PATH's svrngs says 1.13.3 in the
# last: install.sh's ~/.local/bin/svrngs kept by its own unit beside a
# package's newer one.
OLDER_COPY = "#!/bin/bash\ncase \"$1\" in\n  version) echo 'svrngs 1.13.2 (0123abcd)' ;;\n  restart) echo restart >> \"$HOME/restarts\" ;;\nesac\n"
for version, starts, said in (("1.13.2", None, "which is 1.13.2"), ("1.13", None, "which says no version this panel can read"),
                              ("1.13.3", "older-svrngs", "which is 1.13.2")):
    home = case(f"an svrngs from before 1.13.3 holding its data dir, its login service starting {starts or 'the svrngs command'}, "
                f"which says {version if not starts else '1.13.2'}: what to do, by that program, and nothing restarted")
    fake = Fake("old")
    data = data_dir(home, port=fake.port)
    (home / "installed-version").write_text(version)
    program = home / ".local/bin/svrngs"
    if starts:
        program = home / starts
        program.write_text(OLDER_COPY)
        program.chmod(0o755)
        (home / "service").write_text(f"{program}\n")
    held = holding(data)
    got, asked = older_answers(home, fake)
    held.close()
    words = f"This needs svrngs 1.13.3 or later. Your login service starts {program}, {said}: update it on its home page, then try again."
    check("its read says what to do, naming what the service starts", (got["svrngs"], got.get("reason")), ("unreadable", words))
    check("and approve, open, models and play each say it", {verb: a.get("said") for verb, a in asked.items()}, {verb: words for verb in asked})
    check("never restarted", restarts(home), [])
    sent_none(fake)
    fake.close()

for why, setup in (("systemd keeps no svrngs service here", lambda home: (home / "no-service").touch()),
                   ("its login service keeps another data dir", lambda home: (home / "service").write_text(f"{home}/.local/bin/svrngs\n/elsewhere\n"))):
    home = case(f"an svrngs from before 1.13.3 holding its data dir, where {why}: what to do, and nothing restarted")
    fake = Fake("old")
    data = data_dir(home, port=fake.port)
    (home / "installed-version").write_text("1.13.3")
    setup(home)
    held = holding(data)
    got, asked = older_answers(home, fake)
    held.close()
    check("its read says what to do", (got["svrngs"], got.get("reason")), ("unreadable", NEWER))
    check("and approve, open, models and play each say it", {verb: (a["ok"], a.get("said")) for verb, a in asked.items()},
          {verb: (False, NEWER) for verb in asked})
    check("never restarted", restarts(home), [])
    sent_none(fake)
    fake.close()

home = case("an svrngs an update replaced, still running and holding its data dir: restarted once, then proved, then asked")
fake = Fake("old")
data = data_dir(home, port=fake.port)
(home / "installed-version").write_text("1.13.3")
(home / "stops").touch()
fake.renew(home / "restarts", home / "stopped")
held = holding(data)
got = state(home, "--full")
check("running, saying svrngs restarted to use the new one", (got["svrngs"], got.get("restarted")), ("running", RESTARTED))
check("restarted once, by the program its login service starts", (restarts(home), "version" in lines(home / "svrngs-calls")), (["restart"], True))
old, *new = fake.seen
check("the old svrngs was asked only for its proof; the new one proved itself on each connection before the token went on it",
      (old["path"], "Authorization" in old["headers"], sorted({tuple(p == "/v1/proof" for p in paths) for paths in ends(new).values()})),
      ("/v1/proof", False, [(True, False)]))
got, _ = run(home, "open")
check("an action after it restarts nothing, and says nothing of it", (got["ok"], "restarted" in got, restarts(home)), (True, False, ["restart"]))
held.close()
fake.close()

home = case("an action that finds svrngs replaced by an update: restarted once, then done, saying so")
fake = Fake("old")
data = data_dir(home, port=fake.port)
(home / "installed-version").write_text("1.13.3")
(home / "stops").touch()
fake.renew(home / "restarts", home / "stopped")
held = holding(data)
got, _ = run(home, "open", "--lend", "garden1")
held.close()
check("opened, saying svrngs restarted to use the new one", (got["ok"], got.get("restarted"), restarts(home)), (True, RESTARTED, ["restart"]))
fake.close()

# The loop the review found: the service's program says 1.13.3, but each
# restart brings back an svrngs that answers as an older one. Each read and
# action is a run of the helper of its own.
home = case("an svrngs that stays older once restarted: restarted once in all, whatever reads and actions follow, sent none of the token")
fake = Fake("old")
data = data_dir(home, port=fake.port)
(home / "installed-version").write_text("1.13.3")
held = holding(data)
got, asked = older_answers(home, fake)
again = state(home)
held.close()
check("restarted once in all", restarts(home), ["restart"])
check("its read says it restarted to use that program, and what answers is still older",
      (got["svrngs"], "restarted to use" in got.get("reason", ""), "is still older" in got.get("reason", ""),
       "none of your token" in got.get("reason", ""), "restarted" in got), ("unreadable", True, True, True, False))
check("and so do the actions and reads after it", {verb: "is still older" in a.get("said", "") for verb, a in {**asked, "state": {"said": again.get("reason")}}.items()},
      {verb: True for verb in [*asked, "state"]})
sent_none(fake)
fake.close()

home = case("a squatter that answers 404, while no svrngs holds the data dir: nothing restarted, sent none of the token")
squat_port = closed_port()
data_dir(home, port=squat_port)
(home / "installed-version").write_text("1.13.3")
squat = subprocess.Popen(["python3", "-I", "-c", SQUAT, str(squat_port), "404"], cwd="/", stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True)
check("it could be planted", squat.stdout.readline().strip(), "ready")
try:
    got = state(home, "--full")
    asked = {verb: run(home, *args)[0] for verb, args in ACTIONS}
finally:
    squat.kill()
out = squat.communicate()[0]
received = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
check("its read says something other than your svrngs answers, and that it was sent none of the token",
      (got["svrngs"], "something other than your svrngs" in got.get("reason", ""), "none of your token" in got.get("reason", "")),
      ("unreadable", True, True))
check("approve, open, models and play say the same", {verb: "something other than your svrngs" in a.get("said", "") for verb, a in asked.items()},
      {verb: True for verb in asked})
check("nothing restarted", restarts(home), [])
check("it was asked only for one proof each time, and never sent the token",
      (len(received), [r["head"].split("\r\n")[0] for r in received if not r["head"].startswith("POST /v1/proof ")],
       TOKEN in out, [r["head"] for r in received if "authorization:" in r["head"].lower()]),
      (1 + len(ACTIONS), [], False, []))

case("an answer to a challenge the helper's JSON reader can't read, whatever it raises: no proof, never a traceback")
helper = helper_module()


def deeper(raw):
    """json.loads as it fails on nesting deeper than its Python's stack."""
    raise RecursionError("maximum recursion depth exceeded")


helper.json.loads, loads = deeper, helper.json.loads
try:
    try:
        shown = helper.shown_proof(b"[[[[")
    except Exception as e:
        shown = type(e).__name__
finally:
    helper.json.loads = loads
check("shown_proof finds no proof and no nonce in it", shown, ("", ""))

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
    {"person": "Fedora", "key": "d" * 64, "name": "coder", "kind": "llama-server", "origin": f"http://model1.localhost:{fake.port}/"},
    {"person": "Fedora", "key": "d" * 64, "name": "flash", "kind": "spot", "origin": f"http://down1.localhost:{fake.port}/"},
    {"person": "Fedora", "key": "d" * 64, "name": "garden", "kind": "puma", "origin": f"http://garden1.localhost:{fake.port}/"},
]}
fake.models = {"model1": ["qwen3-coder"]}
fake.down = {"down1"}
got, _ = run(home, "models", "--skip", "model1")
said = {l["name"]: l["models"] for l in got["lends"]}
check("a lend named in --skip is listed, not asked", (said["coder"], any(s["headers"].get("Host", "").startswith("model1.") for s in fake.seen)), (None, False))
check("one not reached (502) is not known", said["flash"], None)
check("one that answered with no models is known as none", said["garden"], [])
fake.close()

home = case("Copy address: Play on for a friend's model, its address copied")
fake = Fake()
data_dir(home, port=fake.port)
FEDORA = "d" * 64
fake.playable = {(FEDORA, "coder"): "model1"}
fake.lends = {"lent": [{"person": "Fedora", "key": FEDORA, "name": "coder", "kind": "llama-server", "origin": f"http://model1.localhost:{fake.port}/"}]}
fake.models = {"model1": ["qwen3-coder"]}
got, _ = run(home, "models")
check("each model names its lender's computer and its lend, which Play is asked for by", [(m.get("key"), m["name"]) for m in got["models"]], [(FEDORA, "coder")])
played = lambda: [(s["headers"].get("Content-Type"), json.loads(s["body"])) for s in fake.seen if s["path"] == "/v1/play" and "body" in s]
got, said = run(home, "play", FEDORA, "coder")
check("svrngs is asked to turn Play on for that lend, by its computer's key and its name, and nothing else",
      played(), [("application/json", {"on": {"key": FEDORA, "name": "coder"}})])
check("as an app on this computer: with that connection's code, never an Origin",
      [(s["headers"].get("Authorization", "")[:7], "Origin" in s["headers"]) for s in fake.seen if s["path"] == "/v1/play"], [("Svrngs ", False)])
check("the address svrngs answered is copied, with v1 on its end, as an OpenAI-compatible app takes it",
      (got["ok"], (home / "clipboard").read_text() if (home / "clipboard").exists() else None), (True, f"http://model1.localhost:{fake.port}/v1"))
check("and said, with the token never in it", (got.get("address"), TOKEN in said), (f"http://model1.localhost:{fake.port}/v1", False))
check("a full read says what has Play on, as svrngs says it", state(home, "--full").get("play"),
      [{"key": FEDORA, "name": "coder", "at": f"http://model1.localhost:{fake.port}/", "open": "at",
        "said": f"Connect to http://model1.localhost:{fake.port}/."}])
(home / "clipboard").unlink(missing_ok=True)
fake.opens = {(FEDORA, "coder"): {"is": "apart"}}
got, _ = run(home, "play", FEDORA, "coder")
check("closed where Play opened it: svrngs's words, and nothing copied", (got["ok"], got["said"], (home / "clipboard").exists()),
      (False, "Closed: you and its lender are in no group together now.", False))
check("and a full read says so", [p["open"] for p in state(home, "--full")["play"]], ["apart"])
fake.opens = {(FEDORA, "coder"): {"at": "http://model1.localhost:1/"}}
got, _ = run(home, "play", FEDORA, "coder")
check("open at an address that isn't its lend's here: nothing copied", (got["ok"], (home / "clipboard").exists()), (False, False))
fake.opens = {}
got, _ = run(home, "play", FEDORA, "garden")
check("a lend not lent to this computer: svrngs's words", (got["ok"], got["said"]), (False, "garden is not lent to this computer now"))
got, _ = run(home, "play", FEDORA, "coder", "--off")
check("Stop turns it off", (got["ok"], played()[-1][1], fake.playing), (True, {"off": {"key": FEDORA, "name": "coder"}}, []))
for args in (("notakey", "coder"), (FEDORA, "co der"), (FEDORA,), ()):
    asked = len(played())
    got, _ = run(home, "play", *args)
    check(f"play {' '.join(args)[:24]!r}: refused, svrngs not asked", (got["ok"], len(played()) - asked), (False, 0))
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


def answered(home, *args):
    """The helper's answer, or None when what it printed is no JSON object."""
    try:
        got = run(home, *args)[0]
    except ValueError:
        return None
    return got if isinstance(got, dict) else None


home = case("a flag given last, with nothing after it, is refused in one answer, nothing run")
data_dir(home)
for args in (("unshare", "garden", "--group"), ("open", "--lend"), ("open", "--at"), ("models", "--skip"),
             ("share", "3000", "a" * 64, "garden", "--program"), ("share", "3000", "a" * 64, "garden", "--pid"),
             ("approve", "garden", "--token")):
    (home / "svrngs-calls").unlink(missing_ok=True)
    got = answered(home, *args)
    check(f"{' '.join(args)[:40]}: said as a refusal, svrngs not run", (got, (home / "svrngs-calls").exists()),
          ({"ok": False, "said": f"{args[-1]} wants a value after it, and none was given"}, False))

home = case("keep sharing a held lend: what its row showed, by its token and its process")
fake = Fake()
data_dir(home, port=fake.port)
fake.ports = {"garden": {"port": 3000, "token": LISTED, "processes": {4242: 987654},
                         "answers": [{"pid": 4242, "start": 987654, "program": "python3", "folder": "~/garden-app"}]}}
posted = lambda: [(s["path"], s["headers"].get("Content-Type"), json.loads(s["body"])) for s in fake.seen if s["path"].endswith("/approve")]
got, _ = run(home, "approve", "garden", "--token", LISTED, "--pid", "4242@987654")
check("svrngs is sent the token the row was listed with, and the process its line named, and nothing else",
      posted(), [("/v1/lends/garden/approve", "application/json", {"token": LISTED, "pid": 4242, "start": 987654})])
check("as an app on this computer: with that connection's code, never an Origin",
      [(s["headers"].get("Authorization", "")[:7], "Origin" in s["headers"]) for s in fake.seen if s["path"] != "/v1/proof"], [("Svrngs ", False)])
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
data_dir(home, port=closed_port())
got, _ = run(home, "approve", "garden", "--token", LISTED, "--pid", "4242@987654")
check("svrngs stopped: said so", (got["ok"], got["said"]), (False, "svrngs isn't running"))

print("ALL OK" if not failures else f"{len(failures)} FAILED")
SCRATCH.cleanup()
sys.exit(1 if failures else 0)
