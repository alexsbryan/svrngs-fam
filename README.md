# svrngs.fam

svrngs in the Omarchy bar: what you lend from this computer, what your
people lend you (their models among it), and an invite. The plan, the demo
and the build order are in svrn-docs `rings/current/OMARCHY_PLUGIN.md`.

| File | What it does |
|---|---|
| `manifest.json` | The plugin, `svrngs.fam`, a bar widget for the right section |
| `Panel.qml` | The icon, its tooltip and the panel |
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

## Tests

    tests/helper_test.py   # the helper against a fake svrngs
    tests/qml_logic.py     # the widget offscreen; needs quickshell and Omarchy's shell

The idle bar is held to Omarchy's own `test/shell.d/shell-idle-spawn-test.sh`
with the plugin enabled (`runs/2026-11-17-s1.md` says how it was run).
