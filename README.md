# svrngs.fam

[svrngs](https://github.com/alexsbryan/svrngs) in your Omarchy bar.

svrngs is where you share what you run with the people you know: the app
you're building, the films on your shelf, the graphics card in Sam's
closet. svrngs.fam puts it one click from your desktop. A small icon in
the bar, and a panel that says what's running here, what your people
lend you, and who's in your groups.

## What it does

- **Lend what you're building.** Start your app, open the panel, press
  **Lend**. It says who will be able to open it, and lends it only when you
  press again. Your friends open it as themselves; your app sees their name.
  **Stop** takes it back.
- **Use your people's models.** When a friend lends a model (a
  llama-server, or a model they pay for), it shows up here. **Copy address**
  gives you an OpenAI-compatible address for any program on this computer.
  Your laptop runs nothing; their computer does the work.
- **Open what your groups share.** Each group is one line. Open it to see
  what each person lends, and press a name to open it in your browser,
  already signed in. Something that isn't running right now is greyed out,
  so you know before you click.
- **Find anything.** With the panel open, just type: an app, a model, a
  person or a group, across all your groups.
- **Invite someone.** **Invite** makes a link to your group and copies it,
  ready for the chat.

It works from the keyboard too: arrow keys move between buttons, Enter
presses one, Escape closes the panel.

## What it doesn't do

- **Nothing lends on one click.** Every lend asks first.
- **Nothing runs while the panel is closed.** The icon keeps itself up to
  date from svrngs's own files. It passes Omarchy's own test for this.
- **Your svrngs key stays put.** Only a small helper next to the panel ever
  reads it, and it's never copied to the clipboard or written to a log.
- **Friends' text is shown as text.** A name like `<b>Sam</b>` is shown
  exactly like that.

## Get it

You need [Omarchy](https://omarchy.org) and svrngs. Both packages are on
the AUR:

```
yay -S svrngs-fam                       # brings svrngs-bin with it
/usr/share/svrngs/setup-user            # starts svrngs
/usr/share/svrngs-fam/setup-user        # puts the icon in your bar
```

If you already run svrngs from its install line, `setup-user` moves that
copy aside (it doesn't delete it) and your groups carry on as they were.
From then on, svrngs updates with your system updates.

New to svrngs? [Start a group](https://github.com/alexsbryan/svrngs#start-a-group)
first, or ask a friend for a link. Lending and models are explained in
svrngs's guide: [Lend](https://github.com/alexsbryan/svrngs/blob/main/docs/guide/lend.md),
[Models](https://github.com/alexsbryan/svrngs/blob/main/docs/guide/models.md).

## Working on it

Link your checkout as the plugin, and enable it:

```
ln -s "$PWD" ~/.config/omarchy/plugins/svrngs.fam
omarchy plugin enable svrngs.fam --section right
```

Omarchy doesn't reload a linked plugin when you save, so run
`omarchy restart shell` to see a change. `omarchy-shell svrngs.fam status`
says what the widget currently holds.

| File | What it does |
|---|---|
| `Panel.qml` | The icon and the panel |
| `Service.qml` | Reads svrngs: once at start, when svrngs restarts, and while the panel is open |
| `Model.js` | What the icon and the lists show, kept apart so it can be tested |
| `bin/svrngs-fam` | The helper. Every read and action goes through it, and only it reads svrngs's key |
| `i18n/en.json` | The words |
| `packaging/arch/` | The two AUR packages, and `bump`, which points `svrngs-bin` at a new svrngs release |
| `omarchy/` | Drafts of `omarchy install service svrngs`, for proposing to Omarchy |

`tests/run` runs every test in about a minute: the helper against a
stand-in svrngs, the setup scripts in a scratch home, and the panel itself
offscreen (that one needs Omarchy's shell). No test touches the svrngs on
your computer.

To package a release, build outside this folder, because Omarchy refuses a
plugin folder that holds makepkg's links:

```
export BUILDDIR=/tmp/svrngs-build PKGDEST=/tmp/svrngs-build/out SRCDEST=/tmp/svrngs-build/src
(cd packaging/arch/svrngs-bin && makepkg -f)
(cd packaging/arch/svrngs-fam && makepkg -f)
```

## License

MIT, © 2026 Alex Bryan. svrngs itself is
[AGPL-3.0](https://github.com/alexsbryan/svrngs/blob/main/LICENSE); this
plugin only talks to it, through its command and its local API.
