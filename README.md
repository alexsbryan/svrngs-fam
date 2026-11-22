<img alt="svrngs, sovereign rings" src="brand/lockup.svg" width="300">

# svrngs.fam

Your [svrngs](https://github.com/alexsbryan/svrngs) groups, in the Omarchy bar.

Lend the app you're running, use your friends' models, and open what your
groups share, from one icon.

Nothing is lent until you say yes twice, and a share svrngs closes stays
closed until you keep it to a program of yours. Your svrngs key stays on your
computer. While its panel is closed, the plugin reads svrngs only when the
bar starts and each time svrngs starts. If svrngs was updated but the old
one is still running, the plugin restarts it once to use the new one.

![The svrngs panel, open on a group called House](preview.png)

## Install

In Omarchy, add the plugin:

```
omarchy plugin add https://github.com/alexsbryan/svrngs-fam --enable
```

Click the people icon in your bar. If svrngs isn't on your computer yet,
press Get svrngs. If a friend sent you an invite link, paste it first. The
plugin downloads svrngs and its installer from svrngs's latest release,
checks both against the svrngs release key, and installs svrngs for you
alone, with no password. The invite link is used only to join your
friend's group. Your browser then opens your home page, where you start a
group or join theirs.

svrngs then takes its updates from svrngs's own page,
[group.svrnme.sh](https://group.svrnme.sh/), whatever page your invite
came from, and checks each against the svrngs release key before it
replaces itself. To have it update from another page, set `SVRNGS_FROM` to
that page's address in the environment your Omarchy session starts with,
before you press Get svrngs.

The plugin uses python, ss, wl-copy and gpg, which Omarchy already has.

svrngs and the plugin are also built as Arch packages, for Omarchy's own
package repository, which signs what it ships; they're in
[svrngs-omarchy](https://github.com/alexsbryan/svrngs-omarchy).

## Remove

```
omarchy plugin remove svrngs.fam
```

That removes the plugin and leaves svrngs, with your groups. Removing svrngs
from this computer doesn't take you out of your groups; `svrngs leave
<group>` does. To remove svrngs too, follow
[Remove svrngs](https://github.com/alexsbryan/svrngs-omarchy#remove-svrngs)
for the way you installed it.

## Working on it

See [DEVELOPMENT.md](DEVELOPMENT.md).

MIT, © 2026 Alex Bryan. svrngs itself is
[AGPL-3.0](https://github.com/alexsbryan/svrngs/blob/main/LICENSE); this
plugin only talks to it, through its command and its local API.
