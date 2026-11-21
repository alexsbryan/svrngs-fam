import QtQuick
import Quickshell
import Quickshell.Io
import Qt.labs.folderlistmodel
import "Model.js" as Model

// svrngs's state for the bar, from the helper and from svrngs's own files.
// It never reads the token: the helper does, and only the helper.
//
// While the panel is closed nothing runs. Three things keep the icon honest:
// one read at start; the `api` file, which svrngs writes each time it starts
// (svrngs api.rs:139-145), so a start is a file event; and `lends/`, which
// `svrngs share` and `unshare` write, counted with no process at all.
//
// How much a read asks: SHORT is svrngs's groups alone; HERE adds what
// listens on this computer, no network; FULL adds what every group lends,
// which asks each of its people's computers. FULL runs as the panel opens,
// after an action of its own, as the home page reads on opening, and when a
// HERE read finds what listens on a lend's port changed, never on a timer;
// HERE every 5 s while it is open (svrn-docs OMARCHY_PLUGIN.md; the study,
// "svrngs panel at scale").
Item {
  id: root

  // A third-party plugin has no OMARCHY_PATH-style root; resolve our own.
  readonly property string pluginDir: decodeURIComponent(String(Qt.resolvedUrl(".")).replace(/^file:\/\//, "")).replace(/\/$/, "")
  readonly property string dataDir: Quickshell.env("SVRNGS_DIR") || (Quickshell.env("HOME") + "/.svrngs")
  // The harness points this at a stand-in, so a test reaches no real svrngs.
  property string helperPath: pluginDir + "/bin/svrngs-fam"

  readonly property int short: 0
  readonly property int here: 1
  readonly property int full: 2

  // True while the panel is open: read FULL as it opens, then HERE every 5 s.
  property bool wanted: false

  property var answer: null
  property int reads: 0
  // A read in flight or waiting, for the logic test to wait on.
  readonly property bool reading: helper.running || _again
  readonly property int lentHere: lendFiles.count
  readonly property string state: Model.stateOf(answer)
  readonly property var look: Model.look(answer)
  readonly property string badge: Model.badge(answer, lentHere)

  property bool _again: false
  property int _againDepth: 0
  // What listened on this computer's lends' ports at the last read of it.
  property string _ports: ""
  // FULL reads asked, for the logic test.
  property int fullAsked: 0

  // Friends' lends that answer as models, asked when the panel opens and
  // again only when which lends there are changes. What each lend answered
  // is kept while the shell runs (label: its models, [] for none), so a
  // lend is asked once, not at every open; one not reached is not kept.
  property var models: []
  property bool modelsAsked: false
  // How many friends' lends could be models, asked or known.
  property int lendsAsked: 0
  property string _modelsKey: ""
  property var _known: ({})

  // The action in flight ("" when none), and what the last one said.
  property string doing: ""
  property string said: ""
  property bool saidOk: true

  // The last command run for an action, for the logic test and `status`.
  property var lastAsked: []

  // An action's whole reply, by the key it was asked under, as it ends:
  // the panel keeps a lend's question open until it is lent, and asks
  // which program it is when svrngs asks.
  signal replied(string key, var reply)

  function act(key, args) {
    if (doing !== "") return false
    doing = key
    said = ""
    lastAsked = args
    action.command = [root.helperPath].concat(args)
    action.running = true
    return true
  }

  function tell(words, ok) {
    said = words
    saidOk = ok
  }

  function askModels() {
    if (modelsReader.running) return
    var known = Object.keys(_known)
    modelsReader.command = [root.helperPath, "models"].concat(known.length > 0 ? ["--skip", known.join(",")] : [])
    modelsReader.running = true
  }

  // What the models lookup said, beside what was known: the lends that are
  // models now, each with its models.
  function applyModels(reply) {
    if (!reply || !reply.ok || !Array.isArray(reply.lends)) return
    var known = Object.assign({}, _known)
    reply.lends.forEach(function(l) { if (Array.isArray(l.models)) known[l.label] = l.models })
    _known = known
    models = reply.lends.filter(function(l) { return (known[l.label] || []).length > 0 })
      .map(function(l) { return Object.assign({}, l, { models: known[l.label] }) })
    lendsAsked = reply.lends.length
    modelsAsked = true
  }

  function refresh(depth) {
    var d = typeof depth === "boolean" ? (depth ? full : short) : depth
    if (d === full) fullAsked += 1
    if (helper.running) {
      _again = true
      _againDepth = Math.max(_againDepth, d)
      return
    }
    helper.command = [root.helperPath, "state"].concat(d === full ? ["--full"] : d === here ? ["--here"] : [])
    helper.running = true
  }

  function apply(raw) {
    reads += 1
    var next = Model.parse(raw)
    var asked = !!next.lends
    // A read that did not ask the groups keeps what the last one heard.
    if (next.svrngs === "running" && !next.lends && answer && answer.svrngs === "running" && answer.lends)
      next.lends = answer.lends
    answer = next
    // What listens on a lend's port changed since the last read of this
    // computer: svrngs is asked again, so a held lend's line, and the token
    // Keep sharing it sends, are svrngs's read of what answers now.
    var ports = Model.portsKey(answer)
    if (wanted && !asked && ports !== "" && _ports !== "" && ports !== _ports) refresh(full)
    if (ports !== "") _ports = ports
    var key = Model.lendsKey(answer)
    if (wanted && answer.lends && key !== _modelsKey) {
      _modelsKey = key
      askModels()
    }
  }

  onWantedChanged: {
    if (wanted) refresh(full)
    else { _modelsKey = ""; said = "" }
  }

  FolderListModel {
    id: lendFiles
    folder: "file://" + root.dataDir + "/lends"
    nameFilters: ["*.json"]
    showDirs: false
    showHidden: false
    onCountChanged: if (root.wanted) root.refresh(root.here)
  }

  // The api file appearing (svrngs's first start) is the data directory's
  // event; its rewrite at each later start is the file's own.
  FolderListModel {
    id: apiFile
    folder: "file://" + root.dataDir
    nameFilters: ["api"]
    showDirs: false
    showHidden: false
    // The first listing is no event: the read at start covers it.
    property int seen: -1
    onStatusChanged: if (status === FolderListModel.Ready && seen < 0) seen = count
    onCountChanged: {
      if (seen >= 0 && count > seen) root.refresh(root.wanted ? root.full : root.short)
      if (seen >= 0) seen = count
    }
  }

  FileView {
    path: root.dataDir + "/api"
    watchChanges: true
    printErrors: false
    onFileChanged: {
      reload()
      root.refresh(root.wanted ? root.full : root.short)
    }
  }

  Process {
    id: helper
    stdout: StdioCollector {
      id: helperOut
      waitForEnd: true
    }
    onExited: function(code) {
      var said = String(helperOut.text)
      root.apply(said.trim() === "" ? JSON.stringify({ svrngs: "unreadable", reason: "the helper exited " + code + " and said nothing" }) : said)
      if (root._again) {
        var depth = root._againDepth
        root._again = false
        root._againDepth = 0
        root.refresh(depth)
      }
    }
  }

  Process {
    id: action
    command: ["true"]
    stdout: StdioCollector {
      id: actionOut
      waitForEnd: true
    }
    onExited: function(code) {
      var reply
      try { reply = JSON.parse(String(actionOut.text)) } catch (e) { reply = { ok: false, said: "The helper exited " + code + " without an answer" } }
      if (!reply || typeof reply !== "object") reply = { ok: false, said: "The helper's answer was not an answer" }
      root.tell(String(reply.said || (reply.ok ? "Done" : "That didn't work")), reply.ok === true)
      var key = root.doing
      root.doing = ""
      root.replied(key, reply)
      root.refresh(root.wanted ? root.full : root.short)
    }
  }

  Process {
    id: modelsReader
    command: ["true"]
    stdout: StdioCollector {
      id: modelsOut
      waitForEnd: true
    }
    onExited: {
      var reply
      try { reply = JSON.parse(String(modelsOut.text)) } catch (e) { reply = null }
      root.applyModels(reply)
      root.modelsAsked = true
    }
  }

  // Polling is the last resort (Omarchy shell-dev.md): only while the panel
  // is open, only what is on this computer, and never a read while one runs.
  Timer {
    interval: 5000
    repeat: true
    running: root.wanted
    onTriggered: root.refresh(root.here)
  }

  Component.onCompleted: refresh(short)
}
