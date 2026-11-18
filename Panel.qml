import QtQuick
import QtQuick.Controls
import Quickshell
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "Model.js" as Model

// svrngs.fam's bar widget: the icon and its state, and a panel with what
// this computer lends, the models your people lend, and your groups.
// Every string from svrngs or a friend is drawn as plain text, and nothing
// is lent without a second press.
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
  readonly property string glyph: fam.look.crossed ? "󰭘" : "󰡉"

  readonly property string stateWords: strings.t(Model.words(fam.answer))
  readonly property string lentWords: fam.badge === "" ? "" : strings.tn("lent.count", fam.lentHere).arg(fam.lentHere)
  readonly property string tooltip: lentWords === "" ? stateWords : stateWords + " · " + lentWords

  // The panel's lists.
  readonly property bool isRunning: Model.running(fam.answer)
  readonly property var groups: Model.groups(fam.answer)
  readonly property var lent: Model.lent(fam.answer)
  readonly property var offers: Model.offers(fam.answer)

  // The lend waiting for its second press: { port, program, name }, or null.
  property var lending: null
  property string lendName: ""
  property string lendGroup: ""
  // The group whose new invite link waits for its second press.
  property string inviting: ""

  property alias service: fam

  Commons.Translations {
    id: strings
    directory: Qt.resolvedUrl("i18n")
  }

  Service {
    id: fam
    wanted: root.opened
  }

  onOpenedChanged: if (!opened) { lending = null; inviting = "" }

  function groupName(id) {
    for (var i = 0; i < groups.length; i++) if (groups[i].id === id) return groups[i].name
    return ""
  }

  // The first press: say what lending it means, and wait.
  function askLend(offer) {
    inviting = ""
    lending = offer
    lendName = offer.name
    lendGroup = groups.length > 0 ? groups[0].id : ""
  }

  function lend() {
    var name = Model.cleanName(lendName)
    if (!lending || name === "" || lendGroup === "") return
    if (fam.act("lend", Model.shareArgs(lending, lendGroup, name))) lending = null
  }

  function stop(name) { fam.act("stop:" + name, ["unshare", name]) }

  function openLend(label) { fam.act("open:" + label, label === "" ? ["open"] : ["open", "--lend", label]) }

  function invite(groupId) {
    if (fam.act("invite:" + groupId, ["link", groupId])) inviting = ""
  }

  function copyAddress(model) {
    Quickshell.execDetached(["wl-copy", "--", model.address])
    fam.tell(strings.t("models.copied"), true)
  }

  function startSvrngs() {
    Quickshell.execDetached(["systemctl", "--user", "start", "svrngs"])
  }

  ShellIpc {
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): string { fam.refresh(root.opened); return "ok" }
    function status(): string {
      return JSON.stringify({ state: fam.state, reads: fam.reads, lentHere: fam.lentHere, badge: fam.badge, opened: root.opened,
                              offers: root.offers.length, models: fam.models.length, said: fam.said })
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

  // ---- Pieces --------------------------------------------------------------

  component Words: Text {
    width: parent ? parent.width : implicitWidth
    textFormat: Text.PlainText
    wrapMode: Text.Wrap
    color: root.foreground
    font.family: Style.font.family
    font.pixelSize: Style.font.body
  }

  component Note: Words {
    color: root.dim
    font.pixelSize: Style.font.bodySmall
  }

  // A line of words with buttons at its end.
  component Line: Item {
    id: line
    property string words: ""
    property string note: ""
    default property alias buttons: actions.children
    width: parent ? parent.width : 0
    implicitHeight: Math.max(texts.implicitHeight, actions.implicitHeight)

    Column {
      id: texts
      anchors.left: parent.left
      anchors.right: actions.left
      anchors.rightMargin: Style.space(8)
      anchors.verticalCenter: parent.verticalCenter
      Words { text: line.words; elide: Text.ElideRight; wrapMode: Text.NoWrap }
      Note { text: line.note; visible: line.note !== ""; elide: Text.ElideRight; wrapMode: Text.NoWrap }
    }
    Row {
      id: actions
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      spacing: Style.space(6)
    }
  }

  // A button for an action: says "Working…" while its own action runs, and
  // waits while any other does.
  component Act: Button {
    property string doing: ""
    property string words: ""
    bordered: true
    enabled: fam.doing === ""
    text: doing !== "" && fam.doing === doing ? strings.t("working") : words
    foreground: root.foreground
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: panel.loadedContent
    contentWidth: panel.fittedContentWidth(Style.space(420))
    contentHeight: panel.fittedContentHeight(panel.loadedContentHeight, Style.space(620))

    content: PanelKeyCatcher {
      id: keyCatcher
      implicitHeight: column.implicitHeight
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Flickable {
        id: flick
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
          id: column
          width: flick.width
          spacing: Style.space(10)

          PanelHero {
            width: parent.width
            title: "svrngs"
            meta: root.tooltip
            detail: fam.answer && fam.answer.reason ? fam.answer.reason : ""
            foreground: root.foreground
          }

          Words {
            visible: fam.said !== ""
            text: fam.said
            color: fam.saidOk ? root.foreground : Commons.Color.urgent
          }

          // ---- svrngs not running --------------------------------------
          Column {
            visible: !root.isRunning && fam.answer !== null && fam.state !== "unreadable"
            width: parent.width
            spacing: Style.space(8)
            Note { text: strings.t("help." + fam.state) }
            Act {
              visible: fam.state === "stopped"
              words: strings.t("action.start")
              onClicked: root.startSvrngs()
            }
          }

          // ---- On this computer ----------------------------------------
          Column {
            visible: root.isRunning
            width: parent.width
            spacing: Style.space(8)

            PanelSectionHeader { text: strings.t("here.title"); foreground: root.foreground }

            Repeater {
              model: root.lent
              Line {
                required property var modelData
                words: modelData.name + (modelData.port ? " · port " + modelData.port : "")
                note: modelData.groups.length > 0 ? strings.t("here.lentTo").arg(modelData.groups.join(", ")) : strings.t("here.lentNowhere")
                Act {
                  doing: "stop:" + modelData.name
                  words: strings.t("action.stop")
                  onClicked: root.stop(modelData.name)
                }
              }
            }

            Repeater {
              model: root.offers
              Line {
                required property var modelData
                visible: !root.lending || root.lending.port !== modelData.port
                words: modelData.name
                note: strings.t("here.offer").arg(modelData.program).arg(modelData.port)
                Act {
                  words: strings.t("action.lend")
                  onClicked: root.askLend(modelData)
                }
              }
            }

            // The second press: what lending it means, said before it happens.
            Column {
              visible: root.lending !== null
              width: parent.width
              spacing: Style.space(6)
              Words {
                text: root.lending ? strings.t("lend.question").arg(Model.cleanName(root.lendName) || "…").arg(root.groupName(root.lendGroup)) : ""
                font.bold: true
              }
              Note { text: root.lending ? strings.t("here.offer").arg(root.lending.program).arg(root.lending.port) : "" }
              Row {
                spacing: Style.space(8)
                Note { text: strings.t("lend.name"); width: implicitWidth; anchors.verticalCenter: parent.verticalCenter }
                TextField {
                  width: Style.space(200)
                  text: root.lendName
                  foreground: root.foreground
                  onTextEdited: root.lendName = text
                  onAccepted: root.lend()
                }
              }
              Flow {
                visible: root.groups.length > 1
                width: parent.width
                spacing: Style.space(6)
                Repeater {
                  model: root.groups
                  Button {
                    required property var modelData
                    bordered: true
                    selected: root.lendGroup === modelData.id
                    text: modelData.name
                    foreground: root.foreground
                    onClicked: root.lendGroup = modelData.id
                  }
                }
              }
              Note { text: strings.t("lend.meaning").arg(root.groupName(root.lendGroup)) }
              Row {
                spacing: Style.space(8)
                Act {
                  doing: "lend"
                  words: strings.t("action.lend")
                  enabled: fam.doing === "" && Model.cleanName(root.lendName) !== ""
                  onClicked: root.lend()
                }
                Act { words: strings.t("action.cancel"); onClicked: root.lending = null }
              }
            }

            Note {
              visible: root.offers.length === 0 && root.lending === null
              text: fam.answer && fam.answer.listeners ? strings.t("here.none") : strings.t("here.looking")
            }
          }

          PanelSeparator { visible: root.isRunning; foreground: root.foreground }

          // ---- Models your people lend ---------------------------------
          Column {
            visible: root.isRunning
            width: parent.width
            spacing: Style.space(8)

            PanelSectionHeader { text: strings.t("models.title"); foreground: root.foreground }

            Repeater {
              model: fam.models
              Line {
                required property var modelData
                words: strings.t("models.row").arg(modelData.name).arg(modelData.person)
                // The model's own names, when they say more than the lend's.
                note: modelData.models.join(", ") === modelData.name ? "" : modelData.models.join(", ")
                Act {
                  words: strings.t("action.copyAddress")
                  onClicked: root.copyAddress(modelData)
                }
              }
            }

            Note {
              visible: fam.models.length === 0
              text: fam.modelsAsked ? strings.t("models.none") : strings.t("models.asking")
            }
          }

          PanelSeparator { visible: root.isRunning; foreground: root.foreground }

          // ---- Your groups ---------------------------------------------
          Column {
            visible: root.isRunning
            width: parent.width
            spacing: Style.space(8)

            PanelSectionHeader { text: strings.t("groups.title"); foreground: root.foreground }

            Repeater {
              model: root.groups
              Column {
                id: groupColumn
                required property var modelData
                width: parent.width
                spacing: Style.space(6)

                Line {
                  words: strings.t("groups.row").arg(groupColumn.modelData.name).arg(groupColumn.modelData.person)
                  Act {
                    doing: "invite:" + groupColumn.modelData.id
                    words: strings.t("action.invite")
                    onClicked: { root.lending = null; root.inviting = groupColumn.modelData.id }
                  }
                  Act {
                    doing: "open:"
                    words: strings.t("action.open")
                    onClicked: root.openLend("")
                  }
                }

                Column {
                  visible: root.inviting === groupColumn.modelData.id
                  width: parent.width
                  spacing: Style.space(6)
                  Note { text: strings.t("invite.question").arg(groupColumn.modelData.name) }
                  Row {
                    spacing: Style.space(8)
                    Act { words: strings.t("action.makeLink"); onClicked: root.invite(groupColumn.modelData.id) }
                    Act { words: strings.t("action.cancel"); onClicked: root.inviting = "" }
                  }
                }

                Repeater {
                  model: Model.friendsLends(fam.answer, groupColumn.modelData)
                  Line {
                    required property var modelData
                    words: strings.t("groups.friendLend").arg(modelData.person).arg(modelData.name)
                    Act {
                      visible: modelData.label !== ""
                      doing: "open:" + modelData.label
                      words: strings.t("action.open")
                      onClicked: root.openLend(modelData.label)
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
