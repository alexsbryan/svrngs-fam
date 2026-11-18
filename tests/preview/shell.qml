import Quickshell
import QtQuick
import qs.Commons as Commons

// Draws the real panel, opened on a seeded svrngs, and saves it as an image
// at PREVIEW_OUT: the plugin's own preview for the marketplace.
ShellRoot {
  FloatingWindow {
    id: win
    implicitWidth: 520
    implicitHeight: 1000
    color: Commons.Color.background

    BarPanel {
      id: barPanel
      x: 24
      y: 24
    }

    function card(item) {
      if (!item) return null
      if (item.objectName === "previewCard") return item
      for (var i = 0; i < item.children.length; i++) {
        var found = card(item.children[i])
        if (found) return found
      }
      return null
    }

    Timer {
      interval: 800
      running: true
      onTriggered: {
        barPanel.service.refresh(barPanel.service.full)
        barPanel.openGroup = "1".repeat(64)
        barPanel.open()
        shoot.start()
      }
    }

    Timer {
      id: shoot
      interval: 2500
      onTriggered: {
        var target = win.card(barPanel)
        if (!target) { console.log("PREVIEW: no card"); return }
        target.grabToImage(function(result) {
          console.log(result.saveToFile(Quickshell.env("PREVIEW_OUT")) ? "PREVIEW: saved" : "PREVIEW: not saved")
        })
      }
    }
  }
}
