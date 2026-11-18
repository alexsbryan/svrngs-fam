# svrngs.fam

svrngs in the Omarchy bar: what you lend from this computer, what your
people lend you (their models among it), and an invite. The plan, the demo
and the build order are in svrn-docs `rings/current/OMARCHY_PLUGIN.md`.

| File | What it does |
|---|---|
| `manifest.json` | The plugin, `svrngs.fam`, a bar widget for the right section |
| `Panel.qml` | The icon, its tooltip, and the panel: what runs here with **Lend** (always a second press) and what you lend with **Stop**; your people's models with **Copy address**; your groups with **Invite** and **Open** |
| `Service.qml` | svrngs's state: one read at start, a file event at each svrngs start, the lends folder counted with no process, and a survey every 5 s only while the panel is open |
| `Model.js` | What the icon shows for each answer |
| `bin/svrngs-fam` | The helper. Every read and action goes through it; it alone reads svrngs's token |
| `i18n/en.json` | The words, through Omarchy's `Translations` |

## Try it

    ln -s "$PWD" ~/.config/omarchy/plugins/svrngs.fam
    omarchy plugin enable svrngs.fam --section right

Omarchy's shell does not reload a linked plugin on save (its watcher does
not follow the link): `omarchy restart shell` loads a change.
`omarchy-shell svrngs.fam status` says what the widget holds.

## Packages

Two, in `packaging/arch/`: `svrngs-bin` (svrngs itself, from its GitHub
Release; svrn-docs `rings/current/SVRNGS_PACKAGE.md`) and `svrngs-fam` (this
plugin, which needs it).

    packaging/arch/bump 1.11.0             # svrngs-bin to a release, by its SHA256SUMS
    # Build outside this folder: it is the plugin, and Omarchy refuses a
    # plugin folder holding makepkg's links.
    export BUILDDIR=/tmp/svrngs-build PKGDEST=/tmp/svrngs-build/out SRCDEST=/tmp/svrngs-build/src
    (cd packaging/arch/svrngs-bin && makepkg -f)
    (cd packaging/arch/svrngs-fam && makepkg -f)
    sudo pacman -U /tmp/svrngs-build/out/*.pkg.tar.zst
    /usr/share/svrngs/setup-user           # as yourself: the packaged svrngs runs, an
                                           # install-line one moved aside; ~/.svrngs kept
    /usr/share/svrngs-fam/setup-user       # as yourself: the icon in the bar

## Tests

    tests/run              # all of them, about a minute

The idle bar is held to Omarchy's own `test/shell.d/shell-idle-spawn-test.sh`
with the plugin enabled (`runs/2026-11-17-s1.md` says how it was run).
