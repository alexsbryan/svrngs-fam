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
// is lent without a second press. A lend svrngs holds closed is kept to
// a program of yours that answers on its port now with one, Keep sharing
// it, beside the words that say what that is; another account's program
// there is named, and never offered.
//
// Laid out for someone in many groups (the study "svrngs panel at scale",
// after svrngs V1.9's home page): a group is one line until it is opened,
// one open at a time; inside it, what each person lends is a row of names,
// each name the way in, and what the group's folder carries is one row.
// What the rows share is said once. Typing finds a thing, a model or a
// person in every group.
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
  // svrngs's mark in the bar (svrngs docs/brand): the bar's ink, its record
  // ring gold, both dimmed while svrngs isn't running; the bar's warning
  // colour when its answer couldn't be read; a slash when it isn't here.
  readonly property color gold: "#e0b040"
  readonly property color urgentColor: bar ? bar.urgent : Commons.Color.urgent
  readonly property color iconInk: fam.look.warning ? urgentColor : barIconColor
  readonly property color iconRecord: fam.look.lit ? gold : Qt.darker(gold, 1.6)

  readonly property string stateWords: strings.t(Model.words(fam.answer))
  readonly property string lentWords: fam.badge === "" ? "" : strings.tn("lent.count", fam.lentHere).arg(fam.lentHere)
  readonly property string tooltip: lentWords === "" ? stateWords : stateWords + " · " + lentWords

  // The panel's lists.
  readonly property bool isRunning: Model.running(fam.answer)
  // While svrngs isn't running: "start", "get" or "" (Model.js `wayOn`).
  readonly property string wayOn: Model.wayOn(fam.answer)
  readonly property var groups: Model.groups(fam.answer)
  readonly property var lent: Model.lent(fam.answer)
  readonly property var offers: Model.offers(fam.answer)

  // What is typed to find a thing; while there is any, every group with a
  // match is open, showing only its matches.
  property string query: ""
  readonly property bool finding: query.trim() !== ""
  // The one group open, by id; a person in one group has it open.
  property string openGroup: ""
  readonly property var views: {
    var out = {}
    groups.forEach(function(g) { out[g.id] = Model.groupView(fam.answer, g, root.query) })
    return out
  }
  readonly property var shownModels: fam.models.filter(function(m) { return Model.modelShown(m, root.query) })

  // The lend waiting for its second press: { port, program, name }, or null.
  // It stays until svrngs lends it, so a refusal can be answered in place.
  property var lending: null
  property string lendName: ""
  property bool nameEdited: false
  property string lendGroup: ""
  // Which program it is, asked only once svrngs says it doesn't know its
  // port (the helper's `asks`), with the programs svrngs knows.
  property bool askProgram: false
  property string lendProgram: ""
  property var knownPrograms: []
  // The group whose new invite link waits for its second press.
  property string inviting: ""
  // Get svrngs waiting for its second press, and the invite link given, if any.
  property bool getting: false
  property string getLink: ""
  // The friend's model whose Copy address waits for its second press, by
  // its label: Play is off for it, so what turning Play on lets in is said
  // first, and nothing is turned on until Turn on and copy.
  property string turningOn: ""

  // The keyboard's cursor: one stop per button, in the order they are drawn.
  property bool cursorActive: false
  property int cursor: 0
  readonly property var stops: {
    var out = []
    if (!isRunning) {
      var way = Model.wayOn(fam.answer)
      if (way === "start") return ["start"]
      if (way === "get") return getting ? ["get:confirm", "get:cancel"] : ["get"]
      return []
    }
    if (!finding) {
      lent.forEach(function(l) { out.push("stop:" + l.name); if (Model.keepable(l)) out.push("keep:" + l.name) })
      offers.forEach(function(o) { if (!lending || lending.port !== o.port) out.push("lend:" + o.port) })
      if (lending) out = out.concat(groups.length > 1 ? ["lend:group"] : [], ["lend:confirm", "lend:cancel"])
    }
    shownModels.forEach(function(m) {
      out.push("copy:" + m.label)
      if (Model.playOf(fam.answer, m)) out.push("unplay:" + m.label)
      if (turningOn === m.label) out.push("play:confirm", "play:cancel")
    })
    groups.forEach(function(g) {
      var view = views[g.id]
      if (!view || !view.shown) return
      out.push("group:" + g.id)
      if (!expanded(g.id)) return
      view.people.forEach(function(p) { p.items.forEach(function(i) { if (i.answering && i.label !== "") out.push("open:" + i.label) }) })
      view.carried.forEach(function(i) { if (i.label !== "") out.push("open:" + i.label) })
      if (finding) return
      out.push("invite:" + g.id, "home:" + g.id)
      if (inviting === g.id) out.push("invite:confirm", "invite:cancel")
    })
    return out
  }
  readonly property string currentStop: cursorActive && stops.length > 0 ? stops[Math.min(cursor, stops.length - 1)] : ""

  property alias service: fam

  Commons.Translations {
    id: strings
    directory: Qt.resolvedUrl("i18n")
  }

  Service {
    id: fam
    wanted: root.opened
  }

  Connections {
    target: fam
    function onReplied(key, reply) {
      if (key === "lend") root.lendAnswered(reply)
      // Play's answers in the panel's own words, svrngs's when it refused.
      else if (/^copy:/.test(key) && reply.ok === true) fam.tell(strings.t("models.copied").arg(String(reply.address)), true)
      else if (/^unplay:/.test(key) && reply.ok === true) fam.tell(strings.t("models.unplayed"), true)
    }
  }

  onOpenedChanged: if (!opened) { lending = null; inviting = ""; getting = false; turningOn = ""; cursorActive = false; cursor = 0; query = "" }
  onQueryChanged: cursor = 0

  function expanded(id) {
    return finding || openGroup === id || groups.length === 1
  }

  function toggleGroup(id) {
    inviting = ""
    openGroup = openGroup === id ? "" : id
  }

  function moveCursor(dx, dy) {
    if (!cursorActive) { cursorActive = true; cursor = 0; return }
    cursor = Math.max(0, Math.min(stops.length - 1, cursor + (dy !== 0 ? dy : dx)))
  }

  // Put the cursor on `stop` once it is drawn: a first press moves it to
  // its own second press.
  function cursorTo(stop) {
    Qt.callLater(function() { var at = root.stops.indexOf(stop); if (at >= 0) root.cursor = at })
  }

  function activate(stop) {
    var kind = stop.split(":")[0]
    var rest = stop.slice(kind.length + 1)
    if (kind === "start") startSvrngs()
    else if (stop === "get") { getting = true; cursorTo("get:confirm") }
    else if (stop === "get:confirm") getSvrngs()
    else if (stop === "get:cancel") getting = false
    else if (kind === "stop") root.stop(rest)
    else if (kind === "keep") keep(lent.filter(function(l) { return l.name === rest })[0])
    else if (stop === "lend:confirm") lend()
    else if (stop === "lend:cancel") lending = null
    else if (stop === "lend:group") nextLendGroup()
    else if (kind === "lend") {
      var offer = offers.filter(function(o) { return String(o.port) === rest })[0]
      if (offer) { askLend(offer); cursorTo("lend:confirm") }
    }
    else if (kind === "copy") copyAddress(fam.models.filter(function(m) { return m.label === rest })[0])
    else if (stop === "play:confirm") turnOn(fam.models.filter(function(m) { return m.label === root.turningOn })[0])
    else if (stop === "play:cancel") turningOn = ""
    else if (kind === "unplay") unplay(fam.models.filter(function(m) { return m.label === rest })[0])
    else if (kind === "group") { toggleGroup(rest); cursorTo(stop) }
    else if (stop === "invite:confirm") invite(inviting)
    else if (stop === "invite:cancel") inviting = ""
    else if (kind === "invite") { lending = null; turningOn = ""; inviting = rest; cursorTo("invite:confirm") }
    else if (kind === "home") openLend("")
    else if (kind === "open") openLend(rest)
  }

  function groupName(id) {
    for (var i = 0; i < groups.length; i++) if (groups[i].id === id) return groups[i].name
    return ""
  }

  // The first press: say what lending it means, and wait.
  function askLend(offer) {
    inviting = ""
    turningOn = ""
    lending = offer
    lendName = offer.name
    nameEdited = false
    askProgram = false
    lendProgram = ""
    knownPrograms = []
    lendGroup = groups.length > 0 ? groups[0].id : ""
  }

  function nextLendGroup() {
    var at = groups.map(function(g) { return g.id }).indexOf(lendGroup)
    if (groups.length > 0) lendGroup = groups[(at + 1) % groups.length].id
  }

  // The program typed, once svrngs asked: the name follows it until the
  // person changes the name.
  function typeProgram(text) {
    lendProgram = text
    if (!nameEdited && lending) lendName = Model.freeName(text || lending.name, lending.port, fam.answer ? fam.answer.mine : [])
  }

  function lend() {
    var name = Model.cleanName(lendName)
    var program = askProgram ? Model.cleanName(lendProgram) : ""
    if (!lending || name === "" || lendGroup === "" || askProgram && program === "") return
    fam.act("lend", Model.shareArgs(lending, lendGroup, name, program))
  }

  // svrngs's answer to a lend: lent, the question closes; refused, it
  // stays, its words said above, and asks which program it is when svrngs
  // doesn't know the port.
  function lendAnswered(reply) {
    if (!lending) return
    if (reply.ok === true) { lending = null; askProgram = false; return }
    if (reply.asks !== "program") return
    askProgram = true
    // A list through a signal is a sequence, not a JS Array.
    var known = []
    for (var i = 0; reply.known && i < reply.known.length; i++) if (typeof reply.known[i] === "string") known.push(reply.known[i])
    knownPrograms = known
  }

  function stop(name) { fam.act("stop:" + name, ["unshare", name]) }

  // Keep sharing a held lend, to what its line shows answering: the process
  // svrngs read for its row, sent with the token the row was listed with.
  function keep(l) {
    if (Model.keepable(l)) fam.act("keep:" + l.name, Model.approveArgs(l))
  }

  // A lend of yours, in a word: that svrngs doesn't list it, so lends it to
  // nobody; why svrngs holds it closed, for any reason; then whether it
  // runs or where it goes.
  function lentNote(l) {
    if (l.unlisted) return strings.t("here.unlisted")
    if (l.held !== "") return strings.t(Model.heldKey(l.held))
    if (!l.answering) return strings.t("here.notRunning")
    return l.groups.length > 0 ? strings.t("here.lentTo").arg(l.groups.join(", ")) : strings.t("here.lentNowhere")
  }

  // Under a held lend's line, for any reason it is held: what svrngs read
  // answering on its port, which Keep sharing it would keep sharing; another
  // account's program there, named, with how to get the share back; or that
  // svrngs couldn't read it, said apart from nothing answering.
  function nowWords(l) {
    if (l.held === "") return ""
    var said = l.held === "unapproved" ? [strings.t("here.approveWhy")] : []
    var now = l.now
    if (l.unread !== "") said.push(strings.t("here.nowUnread"))
    else if (now !== null && !now.running) said.push(strings.t("here.nowNothing"))
    else if (now !== null && now.account !== "") said.push(strings.t("here.nowAccount").arg(now.said))
    else if (now !== null && !now.keep) said.push(strings.t("here.nowOther"))
    else if (now !== null) said.push(strings.t("here.now").arg(now.said))
    return said.join(" ")
  }

  function openLend(label) { fam.act("open:" + label, label === "" ? ["open"] : ["open", "--lend", label]) }

  function invite(groupId) {
    if (fam.act("invite:" + groupId, ["link", groupId])) inviting = ""
  }

  // Copy address: with Play on for that lend, its address copied at once,
  // which turns nothing on (the helper's `copy`). With Play off, nothing
  // runs: the panel says what Play lets in, under that model's row, and
  // waits for Turn on and copy (Model.js `copyStep`). Never svrngs's own key.
  function copyAddress(model) {
    if (!model) return
    if (Model.copyStep(fam.answer, model) === "copy") { fam.act("copy:" + model.label, Model.copyArgs(model)); return }
    lending = null
    inviting = ""
    turningOn = model.label
    cursorTo("play:confirm")
  }

  // Turn on and copy, the second press: Play turned on for that lend, so a
  // program of yours reaches it at its address here with no key, then the
  // address svrngs opened it at copied (the helper's `play`).
  function turnOn(model) {
    if (model && turningOn === model.label && fam.act("copy:" + model.label, Model.playArgs(model, false))) turningOn = ""
  }

  function unplay(model) {
    if (model) fam.act("unplay:" + model.label, Model.playArgs(model, true))
  }

  // Under a friend's model: its own names, when they say more than the
  // lend's, and whether Play is on for it: open, or svrngs's words for
  // where it is closed.
  function modelNote(m) {
    var ids = m.models.join(", ") === m.name ? "" : m.models.join(", ")
    var played = Model.playOf(fam.answer, m)
    var play = played === null ? "" : played.open === "at" ? strings.t("models.playing") : played.said
    return [ids, play].filter(function(w) { return w !== "" }).join(" · ")
  }

  // svrngs's own installer, run by the helper once its signature verifies
  // against the svrngs release key; with an invite link, it joins that group.
  function getSvrngs() {
    var link = getLink.trim()
    if (fam.act("get", link === "" ? ["get"] : ["get", "--link", link])) getting = false
  }

  function startSvrngs() {
    fam.act("start", ["start"])
  }

  function summary(view) {
    return Model.groupSummary(view, {
      one: strings.t("groups.thing"), many: strings.t("groups.things"),
      quiet: strings.t("groups.quiet"), unread: strings.t("groups.unread")
    })
  }

  ShellIpc {
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): string { fam.refresh(root.opened); return "ok" }
    function status(): string {
      return JSON.stringify({ state: fam.state, reads: fam.reads, lentHere: fam.lentHere, badge: fam.badge, opened: root.opened,
                              offers: root.offers.length, models: fam.models.length, said: fam.said, stop: root.currentStop })
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    // Lit only while svrngs answers; an answer that could not be read takes
    // the bar's urgent colour, never the stopped look.
    foreground: root.barIconColor
    iconComponent: Component {
      SvrngsMark {
        size: Style.bar.iconCanvas
        ink: root.iconInk
        record: root.iconRecord
        people: root.iconInk
        crossed: fam.look.crossed
      }
    }
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
  // waits while any other does. Told to a screen reader as a button by its
  // words, which qs.Ui's Button doesn't say itself, and pressed by it too.
  component Act: Button {
    id: act
    property string doing: ""
    property string words: ""
    property string stop: ""
    hasCursor: stop !== "" && root.currentStop === stop
    bordered: true
    enabled: fam.doing === ""
    text: doing !== "" && fam.doing === doing ? strings.t("working") : words
    foreground: root.foreground
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.onPressAction: if (act.enabled) act.clicked()
  }

  // A thing's name, which is its way in: dimmed, and pressed to no end,
  // while its program is not running.
  component Cell: Button {
    property var item: ({})
    readonly property string stop: "open:" + item.label
    hasCursor: root.currentStop === stop
    enabled: fam.doing === "" && item.answering === true && item.label !== ""
    text: fam.doing === stop ? strings.t("working") : item.name
    foreground: item.answering === false ? root.dim : root.foreground
    horizontalPadding: Style.space(4)
    verticalPadding: Style.space(1)
    tooltipText: item.answering === false ? strings.t("groups.notRunning") : ""
    onClicked: root.openLend(item.label)
  }

  // A row of cells under a name: a person's lends, or the group's own apps.
  component Shelf: Item {
    id: shelf
    property string who: ""
    property var items: []
    width: parent ? parent.width : 0
    implicitHeight: Math.max(whoText.implicitHeight, cells.implicitHeight)
    Note {
      id: whoText
      width: Style.space(80)
      text: shelf.who
      elide: Text.ElideRight
      wrapMode: Text.NoWrap
      anchors.top: parent.top
      anchors.topMargin: Style.space(3)
    }
    Flow {
      id: cells
      anchors.left: whoText.right
      anchors.right: parent.right
      anchors.leftMargin: Style.space(6)
      spacing: Style.space(2)
      Repeater {
        model: shelf.items
        Cell { required property var modelData; item: modelData }
      }
    }
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
      onMoveRequested: function(dx, dy) { root.moveCursor(dx, dy) }
      onActivateRequested: if (root.currentStop !== "") root.activate(root.currentStop)
      // Typing anywhere in the panel is typed into the search.
      onTextKey: function(t) {
        if (!root.isRunning || t === "" || t.trim() === "" && root.query === "") return
        find.text = find.text + t
        root.query = find.text
        find.forceActiveFocus()
      }

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
            iconComponent: Component {
              SvrngsMark { cut: "medium"; size: Style.font.display; ink: root.foreground; record: root.gold; people: "#f08070" }
            }
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
          // An svrngs older than the panel works with is never started:
          // the helper's words say why, in place of Start svrngs, and Get
          // svrngs is offered where it replaces it (Model.js `wayOn`).
          Column {
            visible: !root.isRunning && fam.answer !== null && (fam.state !== "unreadable" || root.wayOn === "get")
            width: parent.width
            spacing: Style.space(8)
            Note {
              visible: fam.state !== "unreadable"
              text: Model.olderOf(fam.answer) !== "" ? Model.olderOf(fam.answer) : strings.t("help." + fam.state)
            }
            Act {
              visible: root.wayOn === "start"
              doing: "start"
              words: strings.t("action.start")
              stop: "start"
              onClicked: root.startSvrngs()
            }
            Act {
              visible: root.wayOn === "get" && !root.getting
              doing: "get"
              words: strings.t("action.get")
              stop: "get"
              onClicked: root.getting = true
            }
            // The second press: what getting svrngs does, said before it does.
            Column {
              visible: root.wayOn === "get" && root.getting
              width: parent.width
              spacing: Style.space(6)
              Note { id: getMeaning; text: strings.t("get.meaning") + (fam.state === "not-installed" ? "" : " " + strings.t("get.over")) }
              TextField {
                width: parent.width
                text: root.getLink
                foreground: root.foreground
                placeholderText: strings.t("get.link")
                onTextEdited: root.getLink = text
                onAccepted: root.getSvrngs()
              }
              Row {
                spacing: Style.space(8)
                Act { doing: "get"; words: strings.t("action.get"); stop: "get:confirm"; Accessible.description: getMeaning.text; onClicked: root.getSvrngs() }
                Act { words: strings.t("action.cancel"); stop: "get:cancel"; onClicked: root.getting = false }
              }
            }
          }

          TextField {
            id: find
            visible: root.isRunning
            width: parent.width
            foreground: root.foreground
            placeholderText: strings.t("find.placeholder")
            onTextChanged: root.query = text
            onAccepted: { root.cursorActive = true; root.cursor = 0; keyCatcher.forceActiveFocus() }
            Keys.onPressed: function(event) {
              if (event.key === Qt.Key_Down) {
                root.cursorActive = true
                root.cursor = 0
                keyCatcher.forceActiveFocus()
                event.accepted = true
              } else if (event.key === Qt.Key_Escape) {
                if (text !== "") text = ""
                else keyCatcher.forceActiveFocus()
                event.accepted = true
              }
            }
          }

          // ---- On this computer ----------------------------------------
          Column {
            visible: root.isRunning && !root.finding
            width: parent.width
            spacing: Style.space(8)

            PanelSectionHeader { text: strings.t("here.title"); foreground: root.foreground }

            Repeater {
              model: root.lent
              Column {
                id: lentLine
                required property var modelData
                width: parent.width
                spacing: Style.space(4)
                Line {
                  words: lentLine.modelData.name + (lentLine.modelData.port ? " · port " + lentLine.modelData.port : "")
                  note: root.lentNote(lentLine.modelData)
                  Act {
                    doing: "stop:" + lentLine.modelData.name
                    stop: doing
                    words: strings.t("action.stop")
                    onClicked: root.stop(lentLine.modelData.name)
                  }
                }
                Note {
                  visible: text !== ""
                  text: root.nowWords(lentLine.modelData)
                }
                Act {
                  visible: Model.keepable(lentLine.modelData)
                  doing: "keep:" + lentLine.modelData.name
                  stop: doing
                  words: strings.t("action.keep")
                  onClicked: root.keep(lentLine.modelData)
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
                  stop: "lend:" + modelData.port
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
                  onTextEdited: { root.lendName = text; root.nameEdited = true }
                  onAccepted: root.lend()
                }
              }
              // Which program it is, once svrngs asked: one word, its own
              // name, and the programs svrngs knows, whose terms it keeps.
              Row {
                visible: root.askProgram
                spacing: Style.space(8)
                Note { text: strings.t("lend.program"); width: implicitWidth; anchors.verticalCenter: parent.verticalCenter }
                TextField {
                  width: Style.space(200)
                  text: root.lendProgram
                  foreground: root.foreground
                  onTextEdited: root.typeProgram(text)
                  onAccepted: root.lend()
                }
              }
              Note {
                visible: root.askProgram
                text: !root.lending ? ""
                  : (root.lending.through ? strings.t("lend.through").arg(root.lending.program) + " " : "")
                    + (root.knownPrograms.length > 0 ? strings.t("lend.known").arg(root.knownPrograms.join(", ")) : "")
              }
              Dropdown {
                visible: root.groups.length > 1
                width: parent.width
                label: strings.t("lend.group")
                options: root.groups.map(function(g) { return { value: g.id, label: g.name } })
                value: root.lendGroup
                hasCursor: root.currentStop === "lend:group"
                foreground: root.foreground
                onChanged: function(v) { root.lendGroup = v }
              }
              Note { text: strings.t("lend.meaning").arg(root.groupName(root.lendGroup)) }
              Row {
                spacing: Style.space(8)
                Act {
                  doing: "lend"
                  stop: "lend:confirm"
                  words: strings.t("action.lend")
                  enabled: fam.doing === "" && Model.cleanName(root.lendName) !== "" && (!root.askProgram || Model.cleanName(root.lendProgram) !== "")
                  onClicked: root.lend()
                }
                Act { words: strings.t("action.cancel"); stop: "lend:cancel"; onClicked: root.lending = null }
              }
            }

            Note {
              visible: root.offers.length === 0 && root.lending === null
              text: fam.answer && fam.answer.listeners ? strings.t("here.none") : strings.t("here.looking")
            }
          }

          PanelSeparator { visible: root.isRunning && !root.finding; foreground: root.foreground }

          // ---- Models your people lend ---------------------------------
          Column {
            visible: root.isRunning && (!root.finding || root.shownModels.length > 0)
            width: parent.width
            spacing: Style.space(8)

            PanelSectionHeader { text: strings.t("models.title"); foreground: root.foreground }

            Repeater {
              model: root.shownModels
              Column {
                id: modelLine
                required property var modelData
                width: parent.width
                spacing: Style.space(4)
                Line {
                  words: strings.t("models.row").arg(modelLine.modelData.name).arg(modelLine.modelData.person)
                  note: root.modelNote(modelLine.modelData)
                  Act {
                    doing: "copy:" + modelLine.modelData.label
                    words: strings.t("action.copyAddress")
                    stop: doing
                    onClicked: root.copyAddress(modelLine.modelData)
                  }
                  Act {
                    visible: Model.playOf(fam.answer, modelLine.modelData) !== null
                    doing: "unplay:" + modelLine.modelData.label
                    words: strings.t("action.stop")
                    stop: doing
                    onClicked: root.unplay(modelLine.modelData)
                  }
                }
                // The second press, while Play is off for it: what turning
                // Play on lets in, said before anything is turned on.
                Column {
                  visible: root.turningOn === modelLine.modelData.label
                  width: parent.width
                  spacing: Style.space(6)
                  Words {
                    text: strings.t("play.question").arg(modelLine.modelData.name)
                    font.bold: true
                  }
                  Note {
                    id: playMeaning
                    text: strings.t("play.meaning").arg(modelLine.modelData.name)
                  }
                  Row {
                    spacing: Style.space(8)
                    Act {
                      doing: "copy:" + modelLine.modelData.label
                      stop: "play:confirm"
                      words: strings.t("action.turnOnAndCopy")
                      Accessible.description: playMeaning.text
                      onClicked: root.turnOn(modelLine.modelData)
                    }
                    Act { words: strings.t("action.cancel"); stop: "play:cancel"; onClicked: root.turningOn = "" }
                  }
                }
              }
            }

            Note {
              visible: fam.models.length === 0
              text: !fam.modelsAsked ? strings.t("models.asking")
                : fam.lendsAsked > 0 ? strings.t("models.quiet") : strings.t("models.none")
            }
          }

          PanelSeparator { visible: root.isRunning && (!root.finding || root.shownModels.length > 0); foreground: root.foreground }

          // ---- Your groups ---------------------------------------------
          Column {
            visible: root.isRunning
            width: parent.width
            spacing: Style.space(4)

            PanelSectionHeader { text: strings.t("groups.title"); foreground: root.foreground }

            Repeater {
              model: root.groups
              Column {
                id: groupColumn
                required property var modelData
                readonly property var view: root.views[modelData.id] || { people: [], carried: [], unanswered: [], shown: false, count: 0, read: false }
                readonly property bool open: root.expanded(modelData.id)
                visible: view.shown
                width: parent.width
                spacing: Style.space(4)

                // The group, closed to one line: its name, what it shares,
                // who did not answer. Pressed, it opens; the rest close.
                Button {
                  width: parent.width
                  leftAlign: true
                  hasCursor: root.currentStop === "group:" + groupColumn.modelData.id
                  selected: groupColumn.open && !root.finding
                  foreground: root.foreground
                  text: (groupColumn.open ? "▾ " : "▸ ") + groupColumn.modelData.name + "   " + root.summary(groupColumn.view)
                  onClicked: root.toggleGroup(groupColumn.modelData.id)
                }

                Column {
                  visible: groupColumn.open
                  width: parent.width - Style.space(14)
                  x: Style.space(14)
                  spacing: Style.space(4)

                  Note {
                    visible: !root.finding && groupColumn.view.count > 0
                    text: strings.t("groups.shared").arg(groupColumn.modelData.person)
                  }

                  Repeater {
                    model: groupColumn.view.people
                    Shelf {
                      required property var modelData
                      who: modelData.person
                      items: modelData.items
                    }
                  }

                  Shelf {
                    visible: groupColumn.view.carried.length > 0
                    who: strings.t("groups.carried")
                    items: groupColumn.view.carried
                  }

                  Repeater {
                    model: groupColumn.view.unanswered
                    Note {
                      required property var modelData
                      text: strings.t("groups.unanswered").arg(modelData)
                    }
                  }

                  Note {
                    visible: groupColumn.view.read && groupColumn.view.count === 0 && groupColumn.view.unanswered.length === 0
                    text: strings.t("groups.empty")
                  }

                  Row {
                    visible: !root.finding
                    spacing: Style.space(8)
                    Act {
                      doing: "invite:" + groupColumn.modelData.id
                      words: strings.t("action.invite")
                      stop: doing
                      onClicked: { root.lending = null; root.turningOn = ""; root.inviting = groupColumn.modelData.id }
                    }
                    Act {
                      doing: "open:"
                      stop: "home:" + groupColumn.modelData.id
                      words: strings.t("action.home")
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
                      Act { words: strings.t("action.makeLink"); stop: "invite:confirm"; onClicked: root.invite(groupColumn.modelData.id) }
                      Act { words: strings.t("action.cancel"); stop: "invite:cancel"; onClicked: root.inviting = "" }
                    }
                  }
                }
              }
            }

            Note {
              visible: root.finding && root.groups.every(function(g) { return !(root.views[g.id] || {}).shown }) && root.shownModels.length === 0
              text: strings.t("find.none").arg(root.query.trim())
            }
          }
        }
      }
    }
  }
}
