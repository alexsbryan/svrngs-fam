import QtQuick
import Quickshell
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "Model.js" as Model

// svrngs.fam's bar widget: the icon and its state (S1), and a panel that
// says what svrngs said. Every string from svrngs is drawn as plain text.
Panel {
  id: root
  moduleName: "svrngs.fam"
  ipcTarget: "svrngs.fam"
  manageIpc: false
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  readonly property color foreground: bar ? bar.barForeground : Commons.Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property color barIconColor: fam.look.lit ? foreground : dim
  // nf-md-account_group, and its outline when svrngs is not on this
  // computer at all.
  readonly property string glyph: fam.look.crossed ? "\uDB82\uDF58" : "\uDB82\uDC49"

  readonly property string stateWords: strings.t(Model.words(fam.answer))
  readonly property string lentWords: fam.badge === "" ? "" : strings.tn("lent.count", fam.lentHere).arg(fam.lentHere)
  readonly property string tooltip: lentWords === "" ? stateWords : stateWords + " · " + lentWords

  property alias service: fam

  Commons.Translations {
    id: strings
    directory: Qt.resolvedUrl("i18n")
  }

  Service {
    id: fam
    wanted: root.opened
  }

  function lines() {
    var out = [root.stateWords + (fam.answer && fam.answer.reason ? ": " + fam.answer.reason : "")]
    if (root.lentWords !== "") out.push(root.lentWords)
    if (!fam.look.lit) return out
    var groups = fam.answer.groups || []
    for (var i = 0; i < groups.length; i++) {
      var g = groups[i]
      out.push(strings.t("panel.group").arg(g.name).arg(g.person))
      var lends = (fam.answer.lends || {})[g.id]
      if (lends && lends.lent)
        for (var j = 0; j < lends.lent.length; j++)
          out.push("  " + strings.t("panel.friendLend").arg(lends.lent[j].person).arg(lends.lent[j].name).arg(lends.lent[j].kind))
      if (lends && lends.error) out.push("  " + strings.t("panel.groupUnread").arg(lends.error))
    }
    var here = fam.answer.listeners
    if (here) {
      out.push(here.length === 0 ? strings.t("panel.nothingHere") : strings.t("panel.runningHere"))
      for (var k = 0; k < here.length; k++) out.push("  " + strings.t("panel.listener").arg(here[k].program).arg(here[k].port))
    }
    return out
  }

  ShellIpc {
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): string { fam.refresh(root.opened); return "ok" }
    function status(): string {
      return JSON.stringify({ state: fam.state, reads: fam.reads, lentHere: fam.lentHere, badge: fam.badge, opened: root.opened })
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    // Lit only while svrngs answers; an answer that could not be read takes
    // the bar's urgent colour, never the stopped look.
    text: root.glyph
    foreground: root.barIconColor
    active: fam.look.warning
    labelText: fam.badge
    tooltipText: root.tooltip
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.MiddleButton) fam.refresh(root.opened)
      else root.toggle()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: panel.loadedContent
    contentWidth: panel.fittedContentWidth(Style.space(380))
    contentHeight: panel.fittedContentHeight(panel.loadedContentHeight, Style.space(560))

    content: PanelKeyCatcher {
      id: keyCatcher
      implicitHeight: column.implicitHeight
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Column {
        id: column
        width: parent.width
        spacing: Style.space(4)
        Repeater {
          model: root.lines()
          Text {
            required property string modelData
            width: column.width
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            text: modelData
            color: root.foreground
            font.family: Style.font.family
          }
        }
      }
    }
  }
}
