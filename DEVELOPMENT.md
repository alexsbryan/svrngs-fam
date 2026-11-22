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
stand-in svrngs, Get svrngs against a stand-in release, and the panel
itself offscreen, which needs Omarchy's shell. No test reaches the svrngs on your
computer. The helper's test plays another account on this computer with
`unshare --map-auto`, which needs your account to have a range in
`/etc/subuid`, as rootless Podman does; without one, that check fails. Its
stand-in svrngs proves it holds svrngs's key, then takes a request only
with the code made from that key for the one connection it came on, as
svrngs does; the key itself it refuses. The helper's proof and code are
checked against the test vectors svrngs and Give are held to.

## Packages

svrngs and this plugin as Arch packages, the setup each runs, and the
drafts for Omarchy live in
[svrngs-omarchy](https://github.com/alexsbryan/svrngs-omarchy), so that
this repository, which Omarchy's plugin marketplace reviews, is only the
plugin.
