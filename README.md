<img alt="svrngs, sovereign rings" src="brand/lockup.svg" width="300">

# svrngs.fam

Your [svrngs](https://github.com/alexsbryan/svrngs) groups, in the Omarchy bar.

Lend the app you're running, use your friends' models, and open what your
groups share, from one icon.

Nothing is lent until you say yes twice. Your svrngs key stays on your
computer, and the plugin sits idle while its panel is closed.

![The svrngs panel, open on a group called House](preview.png)

## Install

In Omarchy, add the plugin:

```
omarchy plugin add https://github.com/alexsbryan/svrngs-fam --enable
```

Click the people icon in your bar. If svrngs isn't on your computer yet,
press Get svrngs. If a friend sent you an invite link, paste it first. The
plugin downloads svrngs's installer, checks it against the svrngs release
key, and installs svrngs for you alone, with no password. Your browser then
opens your home page, where you start a group or join your friend's.

Get svrngs needs a svrngs release that carries its signed installer, which
starts with the next one. Until then, install svrngs with the line in
[its README](https://github.com/alexsbryan/svrngs#start-a-group), and the
icon lights up once it's running.

The plugin uses python, ss, wl-copy and gpg, which Omarchy already has.

### Or as packages

The latest release also carries both as packages, for a computer where
pacman should own svrngs:

```
mkdir -p ~/Downloads/svrngs && cd ~/Downloads/svrngs
U=https://github.com/alexsbryan/svrngs-fam/releases/download/v0.2.1
curl -fLO $U/SHA256SUMS -fLO $U/svrngs-bin-1.11.1-1-x86_64.pkg.tar.zst -fLO $U/svrngs-fam-0.2.1-1-any.pkg.tar.zst
sha256sum -c SHA256SUMS
sudo pacman -U svrngs-bin-1.11.1-1-x86_64.pkg.tar.zst svrngs-fam-0.2.1-1-any.pkg.tar.zst
/usr/share/svrngs/setup-user
/usr/share/svrngs-fam/setup-user
```

If you already run svrngs from its install line, setup moves that copy
aside rather than deleting it, and your groups carry on as before. These
packages don't update themselves, and they aren't signed, though the
svrngs inside is checked against the svrngs release key when they're
built.

If you're new to svrngs, [start a group](https://github.com/alexsbryan/svrngs#start-a-group)
or ask a friend for their link. svrngs's guide explains
[lending](https://github.com/alexsbryan/svrngs/blob/main/docs/guide/lend.md)
and [models](https://github.com/alexsbryan/svrngs/blob/main/docs/guide/models.md).

## Remove

`omarchy plugin remove svrngs.fam` removes the plugin. svrngs itself stays,
with your groups.

To remove svrngs too, stop it with `systemctl --user disable --now svrngs`,
then delete what installed it: `~/.local/bin/svrngs` if you used Get svrngs
or svrngs's install line, or `sudo pacman -R svrngs-fam svrngs-bin` if you
used the packages. Your groups stay in `~/.svrngs` until you delete that
folder.

## Working on it

See [DEVELOPMENT.md](DEVELOPMENT.md).

MIT, © 2026 Alex Bryan. svrngs itself is
[AGPL-3.0](https://github.com/alexsbryan/svrngs/blob/main/LICENSE); this
plugin only talks to it, through its command and its local API.
