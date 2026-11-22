import Quickshell
import QtQuick

// The bar's reads of svrngs with the panel closed, by the real Service.qml
// alone: at start, and each time svrngs rewrites its `api` file, as it does
// at every start. tests/qml_logic.py runs it beside a stand-in svrngs that
// still answers as one from before 1.13.3 after each restart, and counts
// the restarts.
ShellRoot {
  Service {
    id: fam
  }

  Timer {
    interval: 12000
    running: true
    onTriggered: console.log("restarts: done after " + fam.reads + " reads")
  }
}
