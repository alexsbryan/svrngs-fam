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
      mine: [{ name: "notes", port: 3001, groups: ["g1"] }],
      lends: { g1: { lent: [
        { person: "Fedora", name: "deepseek-flash", kind: "spot", origin: "http://abc123.localhost:41097/" },
        { person: "Fedora", name: "garden", kind: "puma", origin: "http://fff999.localhost:41097/", answering: false },
        { person: "LittleMac", name: "notes", kind: "python3", origin: "http://def456.localhost:41097/", answering: false }
      ], unanswered: ["Bo"] } },
      listeners: [{ port: 3000, program: "puma", name: "garden", pid: 1 }]
    })
    readonly property string group: "󰡉"
    readonly property string outline: "󰭘"

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
      check("its glyph is the outline", barPanel.glyph, outline)
      check("dimmed", same(barPanel.barIconColor, dim), true)
      check("both lends counted from their files", fam.lentHere, 2)
      check("no count while svrngs is not there to serve them", fam.badge, "")

      console.log("running")
      show({ svrngs: "running", groups: [] })
      check("lit", same(barPanel.barIconColor, lit), true)
      check("the group glyph", barPanel.glyph, group)
      check("no warning", fam.look.warning, false)
      check("the count of lends beside it", fam.badge, "2")
      check("the tooltip says both", barPanel.tooltip, "svrngs is running · You lend 2 things from here")

      console.log("stopped")
      show({ svrngs: "stopped" })
      check("dimmed", same(barPanel.barIconColor, dim), true)
      check("the group glyph", barPanel.glyph, group)
      check("no count", fam.badge, "")
      check("no warning", fam.look.warning, false)
      check("the tooltip", barPanel.tooltip, "svrngs isn't running")

      console.log("never started")
      show({ svrngs: "never-started" })
      check("dimmed", same(barPanel.barIconColor, dim), true)
      check("the tooltip", barPanel.tooltip, "svrngs is installed but hasn't run here yet")

      console.log("an answer that could not be read is not stopped")
      show({ svrngs: "unreadable", reason: "/v1/groups answered 500: the record could not be read" })
      check("a warning", fam.look.warning, true)
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

      console.log("the panel's lists")
      show(running)
      check("groups you have left are not listed", JSON.stringify(barPanel.groups.map(function(g) { return g.name })), JSON.stringify(["WorkingGroup", "<b>Family</b>"]))
      check("what is offered", JSON.stringify(barPanel.offers), JSON.stringify([{ port: 3000, program: "puma", name: "garden" }]))
      check("what is lent, its groups' names, and that its program is down", JSON.stringify(barPanel.lent),
            JSON.stringify([{ name: "notes", port: 3001, groups: ["WorkingGroup"], answering: false }]))
      var friends = Model.friendsLends(fam.answer, barPanel.groups[0])
      check("a group's lends from others, not yours, each running or not", JSON.stringify(friends.map(function(l) { return l.person + ":" + l.label + ":" + l.answering })),
            JSON.stringify(["Fedora:abc123:true", "Fedora:fff999:false"]))
      check("whose computer did not answer is named", JSON.stringify(Model.unanswered(fam.answer, barPanel.groups[0])), JSON.stringify(["Bo"]))

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
        barPanel.close()
        harness.check("closing stops asking", harness.fam.wanted, false)
        harness.actions()
      }
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
      check("svrngs is asked to lend it, as named, to the group chosen, saying the program",
            JSON.stringify(fam.lastAsked), JSON.stringify(["share", "3000", "g2", "my-garden", "--program", "puma"]))
      check("the confirm closes", barPanel.lending, null)
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
      settle.then = harness.finish
      settle.start()
    }

    function finish() {
      console.log("the keyboard")
      show(running)
      barPanel.lending = null
      barPanel.inviting = ""
      fam.models = [{ person: "Fedora", name: "coder", label: "abc123", address: "http://abc123.localhost:41097/v1", models: ["coder"] }]
      check("a stop for every button, in the order drawn, none for a lend that is not running", JSON.stringify(barPanel.stops), JSON.stringify(
        ["stop:notes", "lend:3000", "copy:0", "invite:g1", "home:g1", "open:abc123", "invite:g2", "home:g2"]))
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
      check("the cursor stays within the buttons", barPanel.currentStop, "home:g2")
      console.log(harness.failures === 0 ? "ALL OK" : harness.failures + " FAILED")
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
