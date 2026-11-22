import Quickshell
import QtQuick
import qs.Commons as Commons
import "Model.js" as Model

// The bar widget's own decisions, with no compositor: what the icon shows for
// each state the helper can answer, and that the helper runs only at start
// and while the panel is open. tests/qml_logic.py starts it with HOME and
// SVRNGS_DIR in a scratch directory holding two lends and no svrngs.
ShellRoot {
  Item {
    id: harness

    property int failures: 0
    property int readsWhenClosed: 0

    function check(name, got, want) {
      if (String(got) === String(want)) {
        console.log("  ok   " + name)
      } else {
        failures++
        console.log("  FAIL " + name + ": got " + JSON.stringify(String(got)) + ", wanted " + JSON.stringify(String(want)))
      }
    }

    function same(a, b) {
      return String(Qt.rgba(a.r, a.g, a.b, 1)) === String(Qt.rgba(b.r, b.g, b.b, 1))
    }

    readonly property var fam: barPanel.service
    readonly property var running: ({
      svrngs: "running",
      groups: [
        { id: "g1", name: "WorkingGroup", person: "LittleMac", left: false },
        { id: "g2", name: "<b>Family</b>", person: "Alex", left: false },
        { id: "g3", name: "Old", person: "LittleMac", left: true }
      ],
      key: "kme",
      mine: [{ name: "notes", port: 3001, groups: ["g1"] }],
      lends: { g1: { lent: [
        { person: "Fedora", key: "kfedora", name: "deepseek-flash", kind: "spot", origin: "http://abc123.localhost:41097/" },
        { person: "Fedora", key: "kfedora", name: "garden", kind: "puma", origin: "http://fff999.localhost:41097/", answering: false },
        { person: "LittleMac", key: "kme", name: "notes", kind: "python3", origin: "http://def456.localhost:41097/", answering: false }
      ], unanswered: ["Bo"] } },
      listeners: [{ port: 3000, program: "puma", name: "garden", pid: 1, start: 77 }]
    })

    // Your lends svrngs holds, as the helper gives them: each held row with
    // why, the token svrngs listed it with, and `now`, what svrngs read
    // answering on its port (the helper's `svrngs_now`), as svrngs 1.13.0
    // lists them; "unread" as an svrngs before it does, with neither;
    // "account" another account's program svrngs listed a token for; "lost"
    // a port svrngs couldn't read, its reason in `unread`.
    readonly property var kept: ({
      svrngs: "running",
      groups: running.groups,
      key: "kme",
      mine: [
        { name: "garden", port: 3000, groups: ["g1"] },
        { name: "quiet", port: 3002, groups: ["g1"] },
        { name: "theirs", port: 3003, groups: ["g1"] },
        { name: "odd", port: 3004, groups: ["g1"] },
        { name: "shaped", port: 3006, groups: ["g1"] },
        { name: "unread", port: 3005, groups: ["g1"] },
        { name: "untold", port: 3007, groups: ["g1"] },
        { name: "account", port: 3008, groups: ["g1"] },
        { name: "lost", port: 3009, groups: ["g1"] },
        { name: "notes", port: 3001, groups: ["g1"] }
      ],
      lends: { g1: { lent: [
        { person: "LittleMac", key: "kme", name: "garden", kind: "puma", origin: "http://k1.localhost:41097/", held: "unapproved", token: "t1",
          now: { pid: 10, start: 20, program: "puma", folder: "~/my-garden", said: "puma in ~/my-garden" } },
        { person: "LittleMac", key: "kme", name: "quiet", kind: "puma", origin: "http://k2.localhost:41097/", held: "another", token: null, now: null },
        { person: "LittleMac", key: "kme", name: "theirs", kind: "puma", origin: "http://k3.localhost:41097/", held: "unjudged", token: "t3",
          now: { pid: null, start: null, program: "", folder: "" } },
        { person: "LittleMac", key: "kme", name: "odd", kind: "python3", origin: "http://k4.localhost:41097/", held: "unknown", token: "t4",
          now: { pid: 11, start: 21, program: "python3", folder: "~/work/odd", said: "python3 in ~/work/odd" } },
        { person: "LittleMac", key: "kme", name: "shaped", kind: "python3", origin: "http://k6.localhost:41097/", held: "paused", token: "t6",
          now: { pid: 13, start: 23, program: "python3", folder: "~/tmp/odd", said: "python3 in ~/tmp/odd" } },
        { person: "LittleMac", key: "kme", name: "unread", kind: "python3", origin: "http://k5.localhost:41097/", held: "unapproved" },
        { person: "LittleMac", key: "kme", name: "untold", kind: "python3", origin: "http://k7.localhost:41097/", held: "another", token: null,
          now: { pid: 14, start: 24, program: "python3", folder: "", said: "python3" } },
        { person: "LittleMac", key: "kme", name: "account", kind: "python3", origin: "http://k8.localhost:41097/", held: "another", token: "t8",
          now: { pid: null, start: null, program: "", folder: "", account: "root", said: "a program of the account root and a program of the account bob" } },
        { person: "LittleMac", key: "kme", name: "lost", kind: "python3", origin: "http://k9.localhost:41097/", held: "another", token: null,
          unread: "failed" },
        { person: "LittleMac", key: "kme", name: "notes", kind: "python3", origin: "http://def456.localhost:41097/", answering: false }
      ], unanswered: [] } },
      listeners: []
    })

    function show(answer) {
      fam.apply(typeof answer === "string" ? answer : JSON.stringify(answer))
    }

    // The read at start is the real helper's, in a home with no svrngs.
    Timer {
      id: firstRead
      interval: 50
      repeat: true
      running: true
      onTriggered: {
        if (harness.fam.reads < 1) return
        stop()
        harness.states()
      }
    }

    function states() {
      var lit = barPanel.foreground
      var dim = barPanel.dim

      console.log("the read at start, by the real helper")
      check("one read", fam.reads, 1)
      check("no svrngs here: not-installed", fam.state, "not-installed")
      check("the mark is crossed out", fam.look.crossed, true)
      check("dimmed", same(barPanel.barIconColor, dim), true)
      check("both lends counted from their files", fam.lentHere, 2)
      check("no count while svrngs is not there to serve them", fam.badge, "")

      console.log("running")
      show({ svrngs: "running", groups: [] })
      check("lit", same(barPanel.barIconColor, lit), true)
      check("the mark is not crossed out", fam.look.crossed, false)
      check("no warning", fam.look.warning, false)
      check("the count of lends beside it", fam.badge, "2")
      check("the tooltip says both", barPanel.tooltip, "svrngs is running · You lend 2 things from here")
      check("the mark's record ring is gold", same(barPanel.iconRecord, barPanel.gold), true)

      console.log("stopped")
      show({ svrngs: "stopped" })
      check("dimmed", same(barPanel.barIconColor, dim), true)
      check("the mark is not crossed out", fam.look.crossed, false)
      check("no count", fam.badge, "")
      check("no warning", fam.look.warning, false)
      check("the tooltip", barPanel.tooltip, "svrngs isn't running")
      check("the gold dims with it", same(barPanel.iconRecord, Qt.darker(barPanel.gold, 1.6)), true)

      console.log("never started")
      show({ svrngs: "never-started" })
      check("dimmed", same(barPanel.barIconColor, dim), true)
      check("the tooltip", barPanel.tooltip, "svrngs is installed but hasn't run here yet")

      console.log("an answer that could not be read is not stopped")
      show({ svrngs: "unreadable", reason: "/v1/groups answered 500: the record could not be read" })
      check("a warning", fam.look.warning, true)
      check("the mark takes the bar's warning colour", same(barPanel.iconInk, barPanel.urgentColor), true)
      check("not lit", same(barPanel.barIconColor, dim), true)
      check("no count", fam.badge, "")
      check("the tooltip says so", barPanel.tooltip, "svrngs's answer couldn't be read")
      check("the panel lists nothing", barPanel.groups.length + barPanel.offers.length + barPanel.lent.length, 0)

      console.log("an answer the plugin does not know")
      show({ svrngs: "paused" })
      check("a state outside the set is unreadable", fam.state, "unreadable")
      check("and says what it was", fam.answer.reason, "the helper said svrngs is \"paused\"")
      show("Traceback (most recent call last):")
      check("words that are not JSON are unreadable", fam.state, "unreadable")

      console.log("svrngs restarted on the way to an answer, to use an update")
      var restarted = "svrngs was updated, so it restarted to use the new one."
      fam.said = ""
      show({ svrngs: "running", groups: [], restarted: restarted })
      check("a read says so, as no failure", JSON.stringify([fam.said, fam.saidOk]), JSON.stringify([restarted, true]))
      show({ svrngs: "running", groups: [] })
      check("and keeps saying it through the next read", fam.said, restarted)
      check("an action says so before its own words, and only when it did",
            JSON.stringify([Model.replyWords({ ok: true, said: "Opened in your browser", restarted: restarted }), Model.replyWords({ ok: false, said: "nope" })]),
            JSON.stringify([restarted + "\nOpened in your browser", "nope"]))
      fam.said = ""

      console.log("the panel's lists")
      show(running)
      check("groups you have left are not listed", JSON.stringify(barPanel.groups.map(function(g) { return g.name })), JSON.stringify(["WorkingGroup", "<b>Family</b>"]))
      check("what is offered, with the process shown", JSON.stringify(barPanel.offers), JSON.stringify([{ port: 3000, program: "puma", name: "garden", pid: 1, start: 77, through: false }]))
      check("what is lent, its groups' names, and that its program is down", JSON.stringify(barPanel.lent),
            JSON.stringify([{ name: "notes", port: 3001, groups: ["WorkingGroup"], unlisted: false, answering: false, held: "", token: "", unread: "", now: null }]))
      var friends = Model.friendsLends(fam.answer, barPanel.groups[0])
      check("a group's lends from others, not yours, each running or not", JSON.stringify(friends.map(function(l) { return l.person + ":" + l.label + ":" + l.answering })),
            JSON.stringify(["Fedora:abc123:true", "Fedora:fff999:false"]))
      check("whose computer did not answer is named", JSON.stringify(Model.unanswered(fam.answer, barPanel.groups[0])), JSON.stringify(["Bo"]))
      var held = JSON.parse(JSON.stringify(running))
      held.lends.g1.lent[0].held = "unjudged"
      held.lends.g1.lent[2] = { person: "LittleMac", key: "kme", name: "notes", kind: "python3", origin: "http://def456.localhost:41097/", answering: true, held: "another" }
      show(held)
      check("a friend's lend svrngs holds closed can't be opened, though its port answers",
            JSON.stringify(Model.friendsLends(fam.answer, barPanel.groups[0]).map(function(l) { return l.label + ":" + l.answering })),
            JSON.stringify(["abc123:false", "fff999:false"]))
      check("nor in the group's view", JSON.stringify(Model.groupView(fam.answer, barPanel.groups[0], "").people[0].items.map(function(i) { return i.answering })),
            JSON.stringify([false, false]))
      check("your own lend says why svrngs holds it", JSON.stringify(barPanel.lent.map(function(l) { return l.held })), JSON.stringify(["another"]))
      held.lends.g1.lent[0].held = "unknown"
      show(held)
      check("a friend's lend held for a reason the panel doesn't know can't be opened either",
            Model.friendsLends(fam.answer, barPanel.groups[0])[0].answering, false)
      held.lends.g1.lent[0].held = "unapproved"
      show(held)
      check("nor one held until its lender chooses what it shares",
            Model.friendsLends(fam.answer, barPanel.groups[0])[0].answering, false)

      console.log("a lend of yours svrngs holds: why, what svrngs read on its port, Keep sharing it")
      show(kept)
      check("its note says why, for any reason, never where it's lent", JSON.stringify(barPanel.lent.map(function(l) { return barPanel.lentNote(l) })), JSON.stringify([
        "Closed until you choose what it shares",
        "Closed: what answers on its port isn't what you chose to share",
        "Closed: svrngs can't tell what is answering on its port",
        "Closed by svrngs. Its home page says why",
        "Closed by svrngs. Its home page says why",
        "Closed until you choose what it shares",
        "Closed: what answers on its port isn't what you chose to share",
        "Closed: what answers on its port isn't what you chose to share",
        "Closed: what answers on its port isn't what you chose to share",
        "Not running now: start it, and your people can open it"]))
      check("under it, what svrngs read answering on its port", JSON.stringify(barPanel.lent.map(function(l) { return barPanel.nowWords(l) })), JSON.stringify([
        "svrngs now keeps each share to the program you approve. Now answering: puma in ~/my-garden.",
        "Its program isn't running. Start it, then keep sharing it here.",
        "What answers on its port now can't be shared from here.",
        "Now answering: python3 in ~/work/odd.",
        "Now answering: python3 in ~/tmp/odd.",
        "svrngs now keeps each share to the program you approve.",
        "Now answering: python3.",
        "Now answering: a program of the account root and a program of the account bob. Only your own programs can be shared from here: stop that one and start yours, or press Stop and lend yours again.",
        "svrngs couldn't read what answers on its port. Open this panel again to look again.",
        ""]))
      check("each keeps the token its row was listed with", JSON.stringify(barPanel.lent.map(function(l) { return l.token })),
            JSON.stringify(["t1", "", "t3", "t4", "t6", "", "", "t8", "", ""]))
      check("Keep sharing it wherever svrngs listed a token for a program of yours, for any reason it holds the lend, unless the panel never lends it",
            JSON.stringify(barPanel.stops.filter(function(s) { return /^(stop|keep):/.test(s) })),
            JSON.stringify(["stop:garden", "keep:garden", "stop:quiet", "stop:theirs", "stop:odd", "keep:odd", "stop:shaped", "keep:shaped",
              "stop:unread", "stop:untold", "stop:account", "stop:lost", "stop:notes"]))
      check("another account's program, though svrngs listed a token for it, offers no Keep sharing it", Model.keepable(barPanel.lent[7]), false)
      check("and pressing it anyway asks nothing", (function() { barPanel.keep(barPanel.lent[7]); return fam.doing })(), "")
      var twice = JSON.parse(JSON.stringify(kept))
      twice.groups = running.groups.slice(0, 2).map(function(g) { return Object.assign({}, g, { person: "LittleMac" }) })
      twice.lends.g2 = { lent: [Object.assign({}, kept.lends.g1.lent[0], { token: "t9", now: { pid: 99, start: 98, program: "puma", folder: "~/my-garden" } })], unanswered: [] }
      show(twice)
      check("lent to two groups: the reason, token and process all come from one row",
            JSON.stringify(Model.approveArgs(barPanel.lent[0])), JSON.stringify(["approve", "garden", "--token", "t1", "--pid", "10@20"]))

      console.log("your rows are told by this computer's key, never by your name")
      // A member who took this computer's person's name lists a lend of
      // the same name, held, with what answers, a token and running.
      var namesake = JSON.parse(JSON.stringify(running))
      namesake.lends.g1.lent.push({ person: "LittleMac", key: "kother", name: "notes", kind: "python3", origin: "http://n1.localhost:41097/",
        answering: true, held: "another", token: "tn", now: { pid: 40, start: 41, program: "python3", folder: "~/theirs", said: "python3 in ~/theirs" } })
      show(namesake)
      check("can't write on your lend's line, nor give it a Keep sharing it",
            JSON.stringify(barPanel.lent.map(function(l) { return [l.held, l.token, l.answering, Model.keepable(l)].join("|") })), JSON.stringify(["||false|false"]))
      check("and what they lend is listed as theirs, under the name they took",
            JSON.stringify(Model.groupView(fam.answer, barPanel.groups[0], "").people.map(function(p) { return p.person + ":" + p.items.map(function(i) { return i.label }).join("+") })),
            JSON.stringify(["Fedora:abc123+fff999", "LittleMac:n1"]))
      check("to open, as a friend's", JSON.stringify(Model.friendsLends(fam.answer, barPanel.groups[0]).map(function(l) { return l.label })),
            JSON.stringify(["abc123", "fff999", "n1"]))
      var keyless = JSON.parse(JSON.stringify(running))
      delete keyless.key
      show(keyless)
      check("with no key from svrngs, no row is yours", JSON.stringify(barPanel.lent.map(function(l) { return l.answering })), JSON.stringify([true]))

      console.log("a lend svrngs doesn't list is never said lent")
      // ghost: its file says WorkingGroup, whose lends svrngs listed without
      // it, as it leaves out a declaration it can't read (door.rs
      // `offered`); broken: a file the helper couldn't read; family: lent
      // to a group whose lends weren't read, so not judged.
      var unlisted = JSON.parse(JSON.stringify(running))
      unlisted.mine = running.mine.concat([{ name: "ghost", port: 3010, groups: ["g1"] }, { name: "broken", port: null, readable: false },
                                           { name: "family", port: 3011, groups: ["g2"] }])
      show(unlisted)
      check("its line says svrngs doesn't share it, and how to fix it; one not judged says where it is lent",
            JSON.stringify(barPanel.lent.map(function(l) { return barPanel.lentNote(l) })), JSON.stringify([
              "Not running now: start it, and your people can open it",
              "Not shared: svrngs can't read this lend. Stop it, then lend it again.",
              "Not shared: svrngs can't read this lend. Stop it, then lend it again.",
              "Lent to <b>Family</b>"]))
      check("and it still has Stop", barPanel.stops.indexOf("stop:ghost") >= 0 && barPanel.stops.indexOf("stop:broken") >= 0, true)

      console.log("an offer's name is one no other port's lend has")
      var named = JSON.parse(JSON.stringify(running))
      named.listeners = [{ port: 3002, program: "python3", name: "notes", pid: 5, start: 6 }]
      show(named)
      check("a name another port's lend has: -2", barPanel.offers[0].name, "notes-2")
      barPanel.askLend(barPanel.offers[0])
      check("and the lend asks under it", barPanel.lendName, "notes-2")
      barPanel.lending = null
      named.mine = running.mine.concat([{ name: "notes-2", port: 3005, groups: [] }])
      show(named)
      check("-3 when -2 is taken too", barPanel.offers[0].name, "notes-3")
      named.mine = [{ name: "notes", port: null, groups: [], readable: false }]
      show(named)
      check("a lend whose port can't be read keeps its name", barPanel.offers[0].name, "notes-2")
      named.mine = [{ name: "notes", port: 3002, groups: [] }]
      show(named)
      check("the same port's own name is no other port's", barPanel.offers[0].name, "notes")
      var long = "a123456789b123456789c123456789d123456789"
      named.listeners[0].name = long
      named.mine = [{ name: long, port: 1, groups: [] }]
      show(named)
      check("a long name is cut to make room, within 40", barPanel.offers[0].name, long.slice(0, 38) + "-2")
      show(running)

      console.log("nothing runs while the panel is closed")
      readsWhenClosed = fam.reads
      closedWait.start()
    }

    Timer {
      id: closedWait
      interval: 6000
      onTriggered: {
        harness.check("6 s closed: no read", harness.fam.reads, harness.readsWhenClosed)
        console.log("opening the panel surveys at once")
        barPanel.open()
        openWait.start()
      }
    }

    Timer {
      id: openWait
      interval: 1500
      onTriggered: {
        harness.check("asked to read", harness.fam.wanted, true)
        harness.check("read once on open", harness.fam.reads, harness.readsWhenClosed + 1)
        harness.ports()
        barPanel.close()
        harness.check("closing stops asking", harness.fam.wanted, false)
        harness.show(harness.here(15))
        harness.check("closed, a change on a lend's port asks nothing", harness.fam.fullAsked - harness.fullBefore, 0)
        harness.actions()
      }
    }

    // A read of this computer alone, as the helper's `--here` gives it, with
    // process `pid` listening on the lent port of notes; null for none.
    function here(pid) {
      return { svrngs: "running", groups: running.groups, listeners: [],
               mine: [{ name: "notes", port: 3001, groups: ["g1"], now: pid === null ? null : { pid: pid, start: pid + 1, program: "python3", folder: "~/notes" } }] }
    }

    property int fullBefore: 0

    // While the panel is open, what listens on a lend's port changing asks
    // svrngs again; the same again, or svrngs's own answer, asks nothing.
    function ports() {
      console.log("what listens on a lend's port changes while the panel is open")
      show(here(null))
      var before = fam.fullAsked
      show(here(5))
      check("svrngs is asked again", fam.fullAsked - before, 1)
      before = fam.fullAsked
      show(here(5))
      check("the same again asks nothing", fam.fullAsked - before, 0)
      before = fam.fullAsked
      var asked = here(6)
      asked.lends = running.lends
      show(asked)
      check("nor does svrngs's own answer", fam.fullAsked - before, 0)
      fullBefore = fam.fullAsked
    }

    function actions() {
      show(running)
      console.log("lend: nothing happens on the first press")
      barPanel.askLend(barPanel.offers[0])
      check("the second press is waited for", (barPanel.lending || {}).port, 3000)
      check("nothing ran", fam.doing, "")
      check("its name is offered", barPanel.lendName, "garden")
      check("the first group is chosen", barPanel.lendGroup, "g1")
      barPanel.lending = null
      check("Cancel lends nothing", fam.doing, "")

      console.log("lend: the second press")
      barPanel.askLend(barPanel.offers[0])
      barPanel.lendName = "My Garden!"
      barPanel.lendGroup = "g2"
      barPanel.lend()
      check("svrngs is asked to lend it, as named, to the group chosen, with the program the panel read for a port svrngs doesn't know",
            JSON.stringify(fam.lastAsked), JSON.stringify(["share", "3000", "g2", "my-garden", "--program", "puma", "--pid", "1@77"]))
      check("the question stays while svrngs is asked", (barPanel.lending || {}).port, 3000)
      check("it runs", fam.doing, "lend")
      barPanel.stop("notes")
      check("a second action waits for the first", JSON.stringify(fam.lastAsked[0]), JSON.stringify("share"))
      settle.then = harness.afterLend
      settle.start()
    }

    function afterLend() {
      // The harness's home has no svrngs, so the real helper says so.
      check("svrngs's answer is said", fam.said, "svrngs is not installed on this computer")
      check("as a failure", fam.saidOk, false)
      check("a lend refused keeps its question, to change and press again", (barPanel.lending || {}).port, 3000)
      barPanel.lending = null

      console.log("invite: a second press too")
      barPanel.inviting = "g1"
      check("asking runs nothing", fam.doing, "")
      barPanel.invite("g1")
      check("a new link is asked of svrngs", JSON.stringify(fam.lastAsked), JSON.stringify(["link", "g1"]))
      check("the question closes", barPanel.inviting, "")
      settle.then = harness.afterInvite
      settle.start()
    }

    function afterInvite() {
      console.log("open")
      barPanel.openLend("abc123")
      check("a friend's lend opens by its label", JSON.stringify(fam.lastAsked), JSON.stringify(["open", "--lend", "abc123"]))
      settle.then = harness.afterOpen
      settle.start()
    }

    function afterOpen() {
      console.log("Keep sharing it: one press, what its line shows, by its row's token")
      show(kept)
      barPanel.activate("keep:quiet")
      check("nothing runs where nothing answers", fam.doing, "")
      barPanel.activate("keep:untold")
      check("nor where svrngs listed no token", fam.doing, "")
      barPanel.activate("keep:garden")
      check("svrngs is asked to approve what the line shows: its row's token, the process by its pid and start, nothing else",
            JSON.stringify(fam.lastAsked), JSON.stringify(["approve", "garden", "--token", "t1", "--pid", "10@20"]))
      check("it runs", fam.doing, "keep:garden")
      settle.then = harness.forwarded
      settle.start()
    }

    // A container's port, as rootless Podman publishes it: pasta listens,
    // and passes each connection on. pasta is never named as the program;
    // svrngs names a port it knows, and the person one it doesn't.
    function forwardedAnswer() {
      var through = JSON.parse(JSON.stringify(running))
      through.listeners = [{ port: 8101, program: "pasta.avx2", name: "pasta-avx2", pid: 2, start: 78, through: true }]
      return through
    }

    function forwarded() {
      console.log("lending what pasta passes on from a container")
      show(forwardedAnswer())
      check("it is offered as passing its port on", barPanel.offers[0].through, true)
      check("lending it names no program, so svrngs's own is used for a port it knows",
            JSON.stringify(Model.shareArgs(barPanel.offers[0], "g1", "films", "")), JSON.stringify(["share", "8101", "g1", "films", "--pid", "2@78"]))
      barPanel.askLend(barPanel.offers[0])
      check("nothing asks which program it is until svrngs does", barPanel.askProgram, false)
      fam.replied("lend", { ok: false, asks: "program", known: ["kokoro", "llama-server"], said: "svrngs doesn't know what answers on port 8101." })
      check("when svrngs asks, the question stays, and asks which program", [barPanel.lending !== null, barPanel.askProgram].join(","), "true,true")
      check("with the programs svrngs knows", barPanel.knownPrograms.join(","), "kokoro,llama-server")
      barPanel.typeProgram("llama-server")
      check("the name follows the program typed, until it is changed", barPanel.lendName, "llama-server")
      barPanel.lend()
      check("and the lend says that program", JSON.stringify(fam.lastAsked),
            JSON.stringify(["share", "8101", "g1", "llama-server", "--program", "llama-server", "--pid", "2@78"]))
      settle.then = harness.forwardedAfter
      settle.start()
    }

    function forwardedAfter() {
      check("refused, it still asks which program", [barPanel.lending !== null, barPanel.askProgram].join(","), "true,true")
      fam.replied("lend", { ok: true, said: "You lend llama-server (port 8101)." })
      check("lent, the question closes", barPanel.lending, null)
      show(forwardedAnswer())
      barPanel.askLend(barPanel.offers[0])
      check("a new question asks no program until svrngs does", [barPanel.askProgram, barPanel.lendProgram].join(","), "false,")
      barPanel.lending = null
      copied()
    }

    // A friend's model, and Play's rows as the helper's `plays_of` gives
    // them: none, or on for it, open at its address or closed there.
    readonly property var coder: ({ person: "Fedora", key: "kfedora", name: "coder", label: "abc123", address: "http://abc123.localhost:41097/v1", models: ["coder"] })
    readonly property string playMeaning: "Play lets any program of yours on this computer use coder as you, with no key, until you press Stop here or on your home page. It gives no say in your groups, and lets no other account on this computer in."

    function playing(open) {
      var answer = JSON.parse(JSON.stringify(running))
      var said = open === "at" ? "Connect to http://abc123.localhost:41097/." : "Closed: you and its lender are in no group together now."
      answer.play = [{ key: "kfedora", name: "coder", at: "http://abc123.localhost:41097/", open: open, said: said }]
      return answer
    }

    // Copy address on a friend's model with Play off: what Play lets in
    // (svrngs play.rs: this account's programs, at its address here, with
    // no key) is said under its row, and nothing runs until Turn on and
    // copy, which turns Play on and copies the address svrngs answered.
    // Pressed as a person presses, on the panel's own buttons.
    function copied() {
      console.log("Copy address with Play off: what Play lets in is said first, and nothing is turned on until Turn on and copy")
      fam.models = [coder]
      barPanel.open()
      show(running)
      check("with Play off for it, Copy address asks first", Model.copyStep(fam.answer, coder), "ask")
      var before = JSON.stringify(fam.lastAsked)
      var content = panelOf(barPanel)
      press(content, "copy:abc123")
      check("pressed, nothing runs", [fam.doing, JSON.stringify(fam.lastAsked) === before].join("|"), "|true")
      check("its second press waits under its row: Turn on and copy, then Cancel",
            JSON.stringify(barPanel.stops.filter(function(s) { return /^(copy|unplay|play):/.test(s) })), JSON.stringify(["copy:abc123", "play:confirm", "play:cancel"]))
      var shown = shownTexts(content)
      check("the question and what Play lets in are drawn, before anything runs",
            [shown.indexOf("Turn on Play for coder?") >= 0, shown.indexOf(playMeaning) >= 0, shown.indexOf("Turn on and copy") >= 0].join(","), "true,true,true")
      var confirm = withStop(content, "play:confirm")
      check("Turn on and copy says what Play lets in to a screen reader, as its description", confirm ? confirm.Accessible.description : "no such button", playMeaning)
      press(content, "play:cancel")
      check("Cancel turns nothing on, and closes it", [barPanel.turningOn, fam.doing, JSON.stringify(fam.lastAsked) === before].join("|"), "||true")
      check("its question is gone", shownTexts(content).indexOf(playMeaning) < 0, true)
      console.log("the same by the keyboard")
      barPanel.activate("copy:abc123")
      check("Enter on Copy address runs nothing, and waits", [fam.doing, barPanel.turningOn].join("|"), "|abc123")
      barPanel.activate("play:cancel")
      check("Enter on Cancel turns nothing on", [fam.doing, barPanel.turningOn, JSON.stringify(fam.lastAsked) === before].join("|"), "||true")
      press(content, "copy:abc123")
      press(content, "play:confirm")
      check("Turn on and copy asks the helper to turn Play on for it, by its computer's key and its name",
            JSON.stringify(fam.lastAsked), JSON.stringify(["play", "kfedora", "coder"]))
      check("it runs, and the question closes", [fam.doing, barPanel.turningOn].join("|"), "copy:abc123|")
      barPanel.close()
      settle.then = harness.copiedAfter
      settle.start()
    }

    function copiedAfter() {
      check("refused, the helper's words are said as a failure", fam.saidOk, false)
      show(running)
      fam.replied("copy:abc123", { ok: true, at: "http://abc123.localhost:41097/", address: "http://abc123.localhost:41097/v1", said: "Copied." })
      check("copied, it says what was copied and that Play is on, that the app needs no key, any text if it insists, and how to stop", fam.said,
            "Copied http://abc123.localhost:41097/v1, its OpenAI-compatible address. Play is on for it: an app on this computer can use it with no key, and if the app asks for one, type any text. Press Stop to turn Play off.")
      check("never svrngs's own key", fam.said.indexOf(".svrngs/token") < 0 && fam.said.indexOf("token") < 0, true)
      show(playing("at"))
      check("its row says Play is on", barPanel.modelNote(coder), "Play is on: any program of yours here can use it")
      check("with its Stop beside Copy address", JSON.stringify(barPanel.stops.filter(function(s) { return /^(copy|unplay|play):/.test(s) })),
            JSON.stringify(["copy:abc123", "unplay:abc123"]))
      console.log("Copy address with Play on: copied at once, asking nothing and turning nothing on")
      check("with Play on for it, Copy address copies at once", Model.copyStep(fam.answer, coder), "copy")
      barPanel.activate("copy:abc123")
      check("pressed, the helper copies its address with `copy`, which turns nothing on", JSON.stringify(fam.lastAsked), JSON.stringify(["copy", "kfedora", "coder"]))
      check("and nothing asks first", barPanel.turningOn, "")
      settle.then = harness.copiedOn
      settle.start()
    }

    function copiedOn() {
      show(playing("apart"))
      check("closed where Play opened it, its row says svrngs's words, and keeps its Stop",
            [barPanel.modelNote(coder), barPanel.stops.indexOf("unplay:abc123") >= 0].join("|"),
            "Closed: you and its lender are in no group together now.|true")
      check("Play on, though closed there: Copy address still asks nothing", Model.copyStep(fam.answer, coder), "copy")
      barPanel.activate("unplay:abc123")
      check("Stop asks the helper to turn Play off for it", JSON.stringify(fam.lastAsked), JSON.stringify(["play", "kfedora", "coder", "--off"]))
      settle.then = harness.copiedStopped
      settle.start()
    }

    function copiedStopped() {
      fam.replied("unplay:abc123", { ok: true, said: "Play is off for coder." })
      check("stopped, it says so", fam.said, "Stopped: Play is off for it.")
      show(running)
      check("with Play off, its row says nothing of it and has no Stop",
            [barPanel.modelNote(coder), barPanel.stops.indexOf("unplay:abc123")].join("|"), "|-1")
      check("and Copy address asks first again", Model.copyStep(fam.answer, coder), "ask")
      fam.said = ""
      finish()
    }

    function finish() {
      console.log("the keyboard")
      show(running)
      barPanel.lending = null
      barPanel.inviting = ""
      fam.models = [{ person: "Fedora", key: "kfedora", name: "coder", label: "abc123", address: "http://abc123.localhost:41097/v1", models: ["coder"] }]
      check("groups start closed: a stop each", JSON.stringify(barPanel.stops), JSON.stringify(
        ["stop:notes", "lend:3000", "copy:abc123", "group:g1", "group:g2"]))
      check("no cursor until a key moves it", barPanel.currentStop, "")
      barPanel.moveCursor(0, 1)
      check("the first key puts it on the first button", barPanel.currentStop, "stop:notes")
      barPanel.moveCursor(0, 1)
      check("down moves it", barPanel.currentStop, "lend:3000")
      barPanel.activate(barPanel.currentStop)
      check("Enter on Lend asks first", (barPanel.lending || {}).port, 3000)
      check("and lends nothing", fam.doing, "")
      keys.start()
    }

    function keysAfter() {
      check("the cursor moves to the second press", barPanel.currentStop, "lend:confirm")
      barPanel.moveCursor(0, 1)
      barPanel.activate(barPanel.currentStop)
      check("Cancel by keyboard lends nothing", [barPanel.lending, fam.doing].join("|"), "|")
      barPanel.moveCursor(0, -99)
      barPanel.moveCursor(0, 99)
      check("the cursor stays within the buttons", barPanel.currentStop, "group:g2")
      scale()
    }

    // ---- At scale: groups that open, a search, and what is kept ----------------
    function scale() {
      console.log("groups open one at a time")
      barPanel.cursorActive = false
      barPanel.activate("group:g1")
      check("Enter on a group opens it", barPanel.openGroup, "g1")
      check("its running lends are stops, a stopped one is not, then Invite and Home page",
            JSON.stringify(barPanel.stops.slice(3)), JSON.stringify(["group:g1", "open:abc123", "invite:g1", "home:g1", "group:g2"]))
      var view = barPanel.views["g1"]
      check("its people's lends by person", JSON.stringify(view.people.map(function(p) { return p.person + ":" + p.items.map(function(i) { return i.name }).join("+") })),
            JSON.stringify(["Fedora:deepseek-flash+garden"]))
      check("its line says what it shares and who did not answer", barPanel.summary(view), "2 things shared · 1 not answering")
      check("a group never read says so", barPanel.summary(barPanel.views["g2"]), "couldn't ask this group")
      barPanel.toggleGroup("g2")
      check("opening another closes the first", [barPanel.expanded("g1"), barPanel.expanded("g2")].join(","), "false,true")
      barPanel.toggleGroup("g2")
      check("pressed again, it closes", barPanel.expanded("g2"), false)

      console.log("typing finds things in every group")
      barPanel.query = "gar"
      check("this computer's lines step aside", barPanel.stops.indexOf("stop:notes"), -1)
      check("a group with a match opens on it alone", JSON.stringify(barPanel.views["g1"].people[0].items.map(function(i) { return i.name })), JSON.stringify(["garden"]))
      check("a stopped match is shown and is no stop", JSON.stringify(barPanel.stops), JSON.stringify(["group:g1"]))
      check("a group with none is not shown", barPanel.views["g2"].shown, false)
      check("nor a model that does not match", barPanel.shownModels.length, 0)
      barPanel.query = "fedora"
      check("a person's name finds what they lend, and their model", JSON.stringify(barPanel.stops), JSON.stringify(["copy:abc123", "group:g1", "open:abc123"]))
      barPanel.query = "<b>"
      check("a group's name finds the group", barPanel.views["g2"].shown, true)
      barPanel.query = "zzz"
      check("nothing found shows nothing", barPanel.stops.length, 0)
      barPanel.query = ""

      console.log("which lends are models is remembered")
      fam.applyModels({ ok: true, lends: [
        { label: "m1", person: "Cy", name: "coder", models: ["qwen"] },
        { label: "n1", person: "Cy", name: "forgejo", models: [] },
        { label: "u1", person: "Fedora", name: "flash", models: null }] })
      check("a model found is listed", JSON.stringify(fam.models.map(function(m) { return m.label })), JSON.stringify(["m1"]))
      check("an answer is kept, one not reached is not", JSON.stringify(Object.keys(fam._known).sort()), JSON.stringify(["m1", "n1"]))
      fam.applyModels({ ok: true, lends: [
        { label: "m1", person: "Cy", name: "coder", models: null },
        { label: "u1", person: "Fedora", name: "flash", models: ["flash"] }] })
      check("one kept is listed without being asked; one reached now is added",
            JSON.stringify(fam.models.map(function(m) { return m.label + ":" + m.models.join("") })), JSON.stringify(["m1:qwen", "u1:flash"]))

      console.log("a read of this computer alone keeps what the groups said")
      show(running)
      show({ svrngs: "running", groups: running.groups, mine: running.mine, listeners: [] })
      check("the lends of the last full read stay", Object.keys(fam.answer.lends).join(","), "g1")
      check("what listens here is the new read's", fam.answer.listeners.length, 0)
      show({ svrngs: "stopped" })
      check("svrngs stopped keeps nothing of it", fam.answer.lends, undefined)

      console.log("no svrngs here: Get svrngs, a second press")
      show({ svrngs: "not-installed" })
      barPanel.cursorActive = true
      check("its one stop is Get svrngs", JSON.stringify(barPanel.stops), JSON.stringify(["get"]))
      barPanel.activate("get")
      check("the first press asks first", barPanel.getting, true)
      check("and runs nothing", fam.doing, "")
      barPanel.getLink = "  https://group.svrnme.sh/#AbCdEf0123456789 "
      barPanel.getSvrngs()
      check("the second press runs the helper's get, with the link", JSON.stringify(fam.lastAsked), JSON.stringify(["get", "--link", "https://group.svrnme.sh/#AbCdEf0123456789"]))
      settle.then = harness.afterGet
      settle.start()
    }

    function afterGet() {
      check("a release that can't be read is said, and nothing is installed", fam.said.indexOf("couldn't be read") >= 0 && !fam.saidOk, true)

      console.log("svrngs stopped: Start svrngs")
      show({ svrngs: "stopped" })
      check("its one stop is Start", JSON.stringify(barPanel.stops), JSON.stringify(["start"]))
      barPanel.activate("start")
      check("Start asks the helper, which asks svrngs", JSON.stringify(fam.lastAsked), JSON.stringify(["start"]))
      settle.then = harness.finish2
      settle.start()
    }

    function finish2() {
      older()
      plain()
      console.log(harness.failures === 0 ? "ALL OK" : harness.failures + " FAILED")
    }

    // An svrngs older than the panel works with, as the helper's read says
    // it (`stopped_here`, `TooOld`): its words, and whether Get svrngs
    // replaces it. Start svrngs is never offered beside them.
    function older() {
      console.log("an svrngs older than the panel works with is never started from here")
      var words = "This svrngs is 1.12.2, older than 1.13.3, so the panel won't start it: its shares would open under older rules. Press Get svrngs to install the latest signed release."
      barPanel.getting = false
      show({ svrngs: "stopped", older: words, get: true })
      check("stopped and older: Get svrngs in Start svrngs's place", JSON.stringify([Model.wayOn(fam.answer), barPanel.stops]), JSON.stringify(["get", ["get"]]))
      barPanel.activate("get")
      check("its first press asks first, and runs nothing", [barPanel.getting, fam.doing, JSON.stringify(barPanel.stops)].join("|"), 'true||["get:confirm","get:cancel"]')
      barPanel.activate("get:cancel")
      show({ svrngs: "stopped", get: false,
             older: "The svrngs at /usr/bin/svrngs is 1.12.2, older than 1.13.3, so the panel won't start it: its shares would open under older rules. Update it the way you installed it, as with your package manager, then open this panel again." })
      check("older, and not one Get svrngs replaces: nothing to press", JSON.stringify([Model.wayOn(fam.answer), barPanel.stops]), JSON.stringify(["", []]))
      show({ svrngs: "never-started", get: true, older: words.replace("start it", "use it") })
      check("installed, never started, and older: Get svrngs", JSON.stringify(barPanel.stops), JSON.stringify(["get"]))
      show({ svrngs: "unreadable", get: true, reason: "This svrngs is 1.13.2, older than 1.13.3, so the panel won't restart it: its shares would open under older rules. Press Get svrngs to install the latest signed release." })
      check("an older svrngs running, not restarted: Get svrngs", JSON.stringify(barPanel.stops), JSON.stringify(["get"]))
      show({ svrngs: "unreadable", reason: "/v1/groups answered 500" })
      check("any other answer that couldn't be read: nothing to press", JSON.stringify(barPanel.stops), "[]")
      show({ svrngs: "stopped" })
      check("stopped, and not older: Start svrngs", JSON.stringify([Model.wayOn(fam.answer), barPanel.stops]), JSON.stringify(["start", ["start"]]))

      barPanel.open()
      show({ svrngs: "stopped", older: words, get: true })
      var content = panelOf(barPanel)
      var shown = shownTexts(content)
      check("drawn: the helper's words, Get svrngs, and no Start svrngs",
            [shown.indexOf(words) >= 0, shown.indexOf("Get svrngs") >= 0, shown.indexOf("Start svrngs") < 0].join(","), "true,true,true")
      press(content, "get")
      var meaning = shownTexts(content).filter(function(t) { return t.indexOf("This downloads svrngs") === 0 })[0] || ""
      check("Get's second press says it replaces the older svrngs and keeps your groups",
            meaning.indexOf("It replaces the older svrngs here, and keeps your groups and what you lend.") > 0, true)
      var confirm = withStop(content, "get:confirm")
      check("and its Get svrngs says it to a screen reader, as its description", confirm ? confirm.Accessible.description : "no such button", meaning)
      barPanel.close()
    }

    // Every item under `item` that draws text it is given, as Text and
    // Omarchy's Text-based pieces do: one with a textFormat and a text.
    function texts(item, out) {
      if (!item || out.seen.indexOf(item) >= 0) return out
      out.seen.push(item)
      if (item.textFormat !== undefined && typeof item.text === "string") out.found.push(item)
      var kids = item.children || []
      for (var i = 0; i < kids.length; i++) texts(kids[i], out)
      if (item.contentItem) texts(item.contentItem, out)
      return out
    }

    // Names anyone in a group sets, each in markup: drawn as typed, never
    // as rich text, which would draw <img src=…> by fetching it.
    function plain() {
      console.log("names are drawn as plain text, never as rich text")
      var marked = JSON.parse(JSON.stringify(running))
      marked.groups[0].name = "<i>WorkingGroup</i>"
      marked.groups[1].name = "<img src=\"http://127.0.0.1:9/x.png\">"
      marked.lends.g1.lent[0].person = "<u>Fedora</u>"
      marked.lends.g1.lent[0].name = "<s>deepseek</s>"
      marked.lends.g1.unanswered = ["<big>Bo</big>"]
      marked.listeners[0].program = "<b>puma</b>"
      barPanel.open()
      show(marked)
      fam.models = [{ person: "<u>Fedora</u>", key: "kfedora", name: "<s>coder</s>", label: "abc123", address: "http://abc123.localhost:41097/v1", models: ["coder"] }]
      barPanel.toggleGroup("g1")
      barPanel.askLend(barPanel.offers[0])
      var found = texts(panelOf(barPanel), { seen: [], found: [] }).found
      var shown = found.map(function(t) { return t.text })
      var marks = ["<i>WorkingGroup</i>", "<img src=", "<u>Fedora</u>", "<s>deepseek</s>", "<big>Bo</big>", "<b>puma</b>", "<s>coder</s>"]
      check("each name is drawn by some text in the panel",
            JSON.stringify(marks.filter(function(m) { return !shown.some(function(s) { return s.indexOf(m) >= 0 }) })), "[]")
      check("and every text that draws one is plain text",
            JSON.stringify(found.filter(function(t) { return t.text.indexOf("<") >= 0 && t.textFormat !== Text.PlainText }).map(function(t) { return t.text })), "[]")
      barPanel.lending = null

      // Why svrngs couldn't be read, the helper's `reason`, which the hero
      // draws as its detail (Panel.qml's PanelHero, Omarchy's): it can
      // quote svrngs's own words and its api file.
      show({ svrngs: "unreadable", reason: "<b>svrngs</b> answered <img src=\"http://127.0.0.1:9/r.png\">" })
      found = texts(panelOf(barPanel), { seen: [], found: [] }).found
      check("why svrngs couldn't be read is drawn by some text in the panel",
            found.some(function(t) { return t.text.indexOf("<b>svrngs</b> answered <img src=") >= 0 }), true)
      check("as plain text",
            JSON.stringify(found.filter(function(t) { return t.text.indexOf("<") >= 0 && t.textFormat !== Text.PlainText }).map(function(t) { return t.text })), "[]")
      barPanel.close()
    }

    // The text drawn, and shown, under `item`.
    function shownTexts(item) {
      return texts(item, { seen: [], found: [] }).found.filter(function(t) { return t.visible }).map(function(t) { return t.text })
    }

    // The button under `item` that is the keyboard's stop `stop`, shown.
    function withStop(item, stop) {
      if (!item) return null
      if (item.stop === stop && item.visible) return item
      var kids = item.children || []
      for (var i = 0; i < kids.length; i++) {
        var found = withStop(kids[i], stop)
        if (found) return found
      }
      return null
    }

    // A person's press on that button, shown and enabled.
    function press(item, stop) {
      var button = withStop(item, stop)
      if (button && button.enabled) button.clicked()
      else check("a shown, enabled button for " + stop, button ? "disabled" : "none", stop)
    }

    // The panel's content, as qs.Ui's KeyboardPanel loads it while open.
    function panelOf(item) {
      var kids = item.children || []
      for (var i = 0; i < kids.length; i++) {
        if (kids[i].loadedContent !== undefined) return kids[i].loadedContent
        var inner = panelOf(kids[i])
        if (inner) return inner
      }
      return null
    }

    Timer {
      id: keys
      interval: 100
      onTriggered: harness.keysAfter()
    }

    // Waits for the action in flight to end, then goes on.
    Timer {
      id: settle
      property var then: null
      interval: 100
      repeat: true
      onTriggered: {
        if (harness.fam.doing !== "" || harness.fam.reading) return
        stop()
        then()
      }
    }
  }

  BarPanel {
    id: barPanel
  }
}
