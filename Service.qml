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
Item {
  id: root

  // A third-party plugin has no OMARCHY_PATH-style root; resolve our own.
  readonly property string pluginDir: decodeURIComponent(String(Qt.resolvedUrl(".")).replace(/^file:\/\//, "")).replace(/\/$/, "")
  readonly property string dataDir: Quickshell.env("SVRNGS_DIR") || (Quickshell.env("HOME") + "/.svrngs")
  // The harness points this at a stand-in, so a test reaches no real svrngs.
  property string helperPath: pluginDir + "/bin/svrngs-fam"

  // True while the panel is open: then, and only then, svrngs is surveyed
  // every 5 s, with what each group lends and what listens here.
  property bool wanted: false

  property var answer: null
  property int reads: 0
  readonly property int lentHere: lendFiles.count
  readonly property string state: Model.stateOf(answer)
  readonly property var look: Model.look(answer)
  readonly property string badge: Model.badge(answer, lentHere)

  property bool _again: false
  property bool _againFull: false

  // Friends' lends that answer as models, asked when the panel opens and
  // again only when which lends there are changes.
  property var models: []
  property bool modelsAsked: false
  property string _modelsKey: ""

  // The action in flight ("" when none), and what the last one said.
  property string doing: ""
  property string said: ""
  property bool saidOk: true

  // The last command run for an action, for the logic test and `status`.
  property var lastAsked: []

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
    modelsReader.running = true
  }

  function refresh(full) {
    if (helper.running) {
      _again = true
      _againFull = _againFull || full
      return
    }
    helper.command = [root.helperPath, "state"].concat(full ? ["--full"] : [])
    helper.running = true
  }

  function apply(raw) {
    reads += 1
    answer = Model.parse(raw)
    var key = Model.lendsKey(answer)
    if (wanted && answer.lends && key !== _modelsKey) {
      _modelsKey = key
      askModels()
    }
  }

  onWantedChanged: if (!wanted) { _modelsKey = ""; said = "" }

  FolderListModel {
    id: lendFiles
    folder: "file://" + root.dataDir + "/lends"
    nameFilters: ["*.json"]
    showDirs: false
    showHidden: false
    onCountChanged: if (root.wanted) root.refresh(true)
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
      if (seen >= 0 && count > seen) root.refresh(root.wanted)
      if (seen >= 0) seen = count
    }
  }

  FileView {
    path: root.dataDir + "/api"
    watchChanges: true
    printErrors: false
    onFileChanged: {
      reload()
      root.refresh(root.wanted)
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
        var full = root._againFull
        root._again = false
        root._againFull = false
        root.refresh(full)
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
      root.tell(String(reply.said || (reply.ok ? "Done" : "That didn't work")), reply.ok === true)
      root.doing = ""
      root.refresh(root.wanted)
    }
  }

  Process {
    id: modelsReader
    command: [root.helperPath, "models"]
    stdout: StdioCollector {
      id: modelsOut
      waitForEnd: true
    }
    onExited: {
      var reply
      try { reply = JSON.parse(String(modelsOut.text)) } catch (e) { reply = null }
      root.models = reply && reply.ok && Array.isArray(reply.models) ? reply.models : []
      root.modelsAsked = true
    }
  }

  // Polling is the last resort (Omarchy shell-dev.md): only while the panel
  // is open, and never a new survey while one is running.
  Timer {
    interval: 5000
    repeat: true
    running: root.wanted
    triggeredOnStart: true
    onTriggered: root.refresh(true)
  }

  Component.onCompleted: refresh(false)
}
