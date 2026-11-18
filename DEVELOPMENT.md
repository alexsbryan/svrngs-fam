# Working on svrngs.fam

Link your checkout as the plugin and turn it on:

```
ln -s "$PWD" ~/.config/omarchy/plugins/svrngs.fam
omarchy plugin enable svrngs.fam --section right
```

Omarchy doesn't reload a linked plugin when you save, so run
`omarchy restart shell` to see a change. `omarchy-shell svrngs.fam status`
shows what the widget holds right now.

`Panel.qml` draws the icon and the panel. `Service.qml` reads svrngs: once
at start, again whenever svrngs restarts, and while the panel is open.
`Model.js` decides what the icon and the lists show, apart from QML so it
can be tested. Every read and action goes through `bin/svrngs-fam`, the
only part that reads svrngs's key. The words are in `i18n/en.json`.

`tests/run` runs everything in about a minute: the helper against a
stand-in svrngs, the setup scripts in a scratch home, and the panel itself
offscreen, which needs Omarchy's shell. No test reaches the svrngs on your
computer.

## Packages

`packaging/arch/` holds the two packages. `packaging/arch/bump <version>`
points `svrngs-bin` at a new svrngs release, using that release's checksums.
Build outside this folder, because Omarchy refuses a plugin folder that
holds makepkg's links:

```
export BUILDDIR=/tmp/svrngs-build PKGDEST=/tmp/svrngs-build/out SRCDEST=/tmp/svrngs-build/src
(cd packaging/arch/svrngs-bin && makepkg -f)
(cd packaging/arch/svrngs-fam && makepkg -f)
```

`omarchy/` has drafts of `omarchy install service svrngs` and its removal,
for proposing to Omarchy.
