#!/usr/bin/python3 -I
"""svrngs-bin's setup-user and packaging/bump, in scratch directories.

setup-user moves an install made by svrngs's own install line aside, never
deleting it and never touching ~/.svrngs, and starts the packaged service;
systemctl is stood in for, so nothing reaches this computer's own svrngs.
bump points the package at a release by its SHA256SUMS, and refuses one
that lacks a platform.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "packaging/arch/svrngs-bin/setup-user"
failures = []


def check(name, got, want):
    print(f"  {'ok  ' if got == want else 'FAIL'} {name}" + ("" if got == want else f": got {got!r}, wanted {want!r}"))
    if got != want:
        failures.append(name)


def setup(home, starts=True):
    stubs = home / "stubs"
    stubs.mkdir(exist_ok=True)
    active = "exit 0" if starts else "exit 3"
    (stubs / "systemctl").write_text(
        f'#!/bin/bash\nprintf "%s\\n" "$*" >> "$HOME/systemctl-calls"\n[[ $* == *is-active* ]] && {active}\nexit 0\n')
    (stubs / "systemctl").chmod(0o755)
    (stubs / "sleep").write_text("#!/bin/bash\nexit 0\n")
    (stubs / "sleep").chmod(0o755)
    done = subprocess.run(["bash", str(SETUP)], env={"HOME": str(home), "PATH": f"{stubs}:/usr/bin:/bin"},
                          capture_output=True, text=True, timeout=30)
    calls_file = home / "systemctl-calls"
    calls = calls_file.read_text().splitlines() if calls_file.exists() else []
    calls_file.unlink(missing_ok=True)
    return done, [c for c in calls if "is-active" not in c]


def aside(folder, name):
    return sorted(p.name for p in folder.glob(f"{name}.before-package.*"))


with tempfile.TemporaryDirectory() as scratch:
    print("an install made by svrngs's own install line")
    home = Path(scratch) / "home"
    units = home / ".config/systemd/user"
    units.mkdir(parents=True)
    (units / "svrngs.service").write_text(f"[Service]\nExecStart={home}/.local/bin/svrngs\n")
    (home / ".local/bin").mkdir(parents=True)
    (home / ".local/bin/svrngs").write_bytes(b"the svrngs the install line put here")
    (home / ".svrngs/lends").mkdir(parents=True)
    (home / ".svrngs/lends/garden.json").write_text('{"port": 3000}')
    (home / ".svrngs/token").write_text("a-token")
    before = {p.relative_to(home): p.read_bytes() for p in (home / ".svrngs").rglob("*") if p.is_file()}

    done, calls = setup(home)
    check("succeeds", done.returncode, 0)
    check("its service is stopped first", calls[0], "--user disable --now svrngs.service")
    check("its service is moved aside, not deleted", len(aside(units, "svrngs.service")), 1)
    check("so the packaged service is the one systemd finds", (units / "svrngs.service").exists(), False)
    check("its binary is moved aside, not deleted", len(aside(home / ".local/bin", "svrngs")), 1)
    kept = next((home / ".local/bin").glob("svrngs.before-package.*"))
    check("with its bytes", kept.read_bytes(), b"the svrngs the install line put here")
    check("and its name now runs the package's", os.readlink(home / ".local/bin/svrngs"), "/usr/bin/svrngs")
    check("the packaged service is started", calls[-2:], ["--user daemon-reload", "--user enable --now svrngs.service"])
    after = {p.relative_to(home): p.read_bytes() for p in (home / ".svrngs").rglob("*") if p.is_file()}
    check("~/.svrngs is untouched", after, before)

    print("run again")
    done, calls = setup(home)
    check("succeeds", done.returncode, 0)
    check("moves nothing more", (len(aside(units, "svrngs.service")), len(aside(home / ".local/bin", "svrngs"))), (1, 1))
    check("stops nothing", calls, ["--user daemon-reload", "--user enable --now svrngs.service"])

    print("a computer svrngs was never on")
    fresh = Path(scratch) / "fresh"
    fresh.mkdir()
    done, calls = setup(fresh)
    check("succeeds", done.returncode, 0)
    check("the name svrngs runs the package's", os.readlink(fresh / ".local/bin/svrngs"), "/usr/bin/svrngs")
    check("only starts the service", calls, ["--user daemon-reload", "--user enable --now svrngs.service"])

    print("a service that does not start")
    stuck = Path(scratch) / "stuck"
    stuck.mkdir()
    done, _ = setup(stuck, starts=False)
    check("fails", done.returncode, 1)
    check("and says where to look", "systemctl --user status svrngs" in done.stderr, True)

    print("bump")
    copy = Path(scratch) / "packaging"
    shutil.copytree(ROOT / "packaging/arch", copy / "arch")
    pkgbuild = copy / "arch/svrngs-bin/PKGBUILD"
    x, a = "1" * 64, "2" * 64
    sums = Path(scratch) / "SHA256SUMS"
    sums.write_text(f"{x}  svrngs-linux-x86_64.tar.gz\n{a}  svrngs-linux-aarch64.tar.gz\n{'3' * 64}  give-linux-x86_64.tar.gz\n")
    (copy / "arch/svrngs-bin/setup-user").write_text("#!/bin/bash\n# changed\n")
    done = subprocess.run([str(copy / "arch/bump"), "1.11.0", "--sums", str(sums)], capture_output=True, text=True)
    s = pkgbuild.read_text()
    check("succeeds", done.returncode, 0)
    check("the version", re.search(r"(?m)^pkgver=(.*)$", s).group(1), "1.11.0")
    check("x86_64's sum from the release", re.search(r"(?m)^sha256sums_x86_64=\('(\w+)'\)$", s).group(1), x)
    check("aarch64's sum from the release", re.search(r"(?m)^sha256sums_aarch64=\('(\w+)'\)$", s).group(1), a)
    own = re.findall(r"'(\w+)'", re.search(r"(?m)^sha256sums=\((.*)\)$", s).group(1))
    check("the package's own files' sums from their bytes, an edit included",
          own[-1], hashlib.sha256(b"#!/bin/bash\n# changed\n").hexdigest())
    sums.write_text(f"{x}  svrngs-linux-x86_64.tar.gz\n")
    done = subprocess.run([str(copy / "arch/bump"), "1.12.0", "--sums", str(sums)], capture_output=True, text=True)
    check("a release missing a platform is refused", done.returncode != 0 and "aarch64" in done.stderr, True)
    check("and nothing changed", re.search(r"(?m)^pkgver=(.*)$", pkgbuild.read_text()).group(1), "1.11.0")

print("ALL OK" if not failures else f"{len(failures)} FAILED")
sys.exit(1 if failures else 0)
