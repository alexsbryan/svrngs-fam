# svrngs.fam

Your [svrngs](https://github.com/alexsbryan/svrngs) groups, in the Omarchy bar.

Click the people icon in the bar and you see three things: what's running
on this computer that you could lend, the models your friends lend you,
and your groups with what each person in them shares. Lend the app you're
working on and your friends can open it as themselves. Copy the address of
a friend's model and any program on your computer can use it, while their
computer does the work. Start typing to find something across all your
groups.

Nothing is lent until you say yes twice, once to Lend and once to the
question that follows. Your svrngs key stays on your computer and never
reaches the clipboard. While the panel is closed the plugin runs nothing,
apart from one quick check when svrngs restarts.

## Install

You need Omarchy. Download the two packages from the latest release, check
them, and install them:

```
mkdir -p ~/Downloads/svrngs && cd ~/Downloads/svrngs
U=https://github.com/alexsbryan/svrngs-fam/releases/download/v0.2.0
curl -fLO $U/SHA256SUMS -fLO $U/svrngs-bin-1.11.0-1-x86_64.pkg.tar.zst -fLO $U/svrngs-fam-0.2.0-1-any.pkg.tar.zst
sha256sum -c SHA256SUMS
sudo pacman -U svrngs-bin-1.11.0-1-x86_64.pkg.tar.zst svrngs-fam-0.2.0-1-any.pkg.tar.zst
```

Then, as yourself, start svrngs and put the icon in your bar:

```
/usr/share/svrngs/setup-user
/usr/share/svrngs-fam/setup-user
```

If you already run svrngs from its install line, setup moves that copy
aside rather than deleting it, and your groups carry on as before.

The trade-off for now: these packages aren't signed and don't update
themselves. A new release is another download from this page, until svrngs
is in Omarchy's own package repository and arrives with your system
updates.

If you're new to svrngs, [start a group](https://github.com/alexsbryan/svrngs#start-a-group)
or ask a friend for their link. svrngs's guide explains
[lending](https://github.com/alexsbryan/svrngs/blob/main/docs/guide/lend.md)
and [models](https://github.com/alexsbryan/svrngs/blob/main/docs/guide/models.md).

## Remove

```
omarchy plugin disable svrngs.fam
rm ~/.config/omarchy/plugins/svrngs.fam
systemctl --user disable --now svrngs
sudo pacman -R svrngs-fam svrngs-bin
```

Your groups stay in `~/.svrngs`. If setup moved an older svrngs aside, it's
still in `~/.local/bin` with `.before-package` in its name.

If you added only the plugin, with `omarchy plugin add`, then
`omarchy plugin remove svrngs.fam` is all you need.

## Working on it

See [DEVELOPMENT.md](DEVELOPMENT.md).

MIT, © 2026 Alex Bryan. svrngs itself is
[AGPL-3.0](https://github.com/alexsbryan/svrngs/blob/main/LICENSE); this
plugin only talks to it, through its command and its local API.
