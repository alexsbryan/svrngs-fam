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

`packaging/arch/` holds the two packages. `svrngs-bin` is svrngs's own
[`packaging/arch`](https://github.com/alexsbryan/svrngs/tree/main/packaging/arch),
copied here for each release by `bump`, given a svrngs checkout and,
if not its HEAD, the commit to copy:

```
packaging/arch/bump 1.11.1 ~/svrngs 3b9a0506
```

It writes all of `packaging/arch/svrngs-bin/`, and `SOURCE` there says
where each file came from, so change svrngs's package and bump rather than
edit the copy. On top of svrngs's files go only what Omarchy's package
repository needs: the svrngs release key as `keys/pgp/<fingerprint>.asc`,
and each file in `packaging/arch/omarchy/` in place of svrngs's, with its
sum. That's `updated-by`, the line `svrngs update` says, worded for
Omarchy.

makepkg checks each svrngs download against the svrngs release key, so
import it once with `gpg --import packaging/arch/svrngs-bin/keys/pgp/*.asc`.
Build outside this folder, because Omarchy refuses a plugin folder that
holds makepkg's links:

```
export BUILDDIR=/tmp/svrngs-build PKGDEST=/tmp/svrngs-build/out SRCDEST=/tmp/svrngs-build/src
(cd packaging/arch/svrngs-bin && makepkg -f)
(cd packaging/arch/svrngs-fam && makepkg -f)
```

The first builds `svrngs-give-bin` beside `svrngs-bin`, as svrngs's does.

`omarchy/` has drafts of `omarchy install service svrngs` and its removal,
for proposing to Omarchy.
