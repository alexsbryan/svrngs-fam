import QtQuick

// Stands in for qs.Ui's KeyboardPanel in the logic harness. The real one is a
// layer shell window, which has no backend offscreen; the widget's decisions
// need none. It keeps the properties Panel.qml sets and reads, and builds its
// content only while open, as the real one does.
Item {
  id: root
  required property Item anchorItem
  required property QtObject bar
  property var owner: null
  property bool open: false
  property Item focusTarget: null
  property int contentWidth: 280
  property int contentHeight: 200
  property Component content: null
  readonly property Item loadedContent: loader.item
  readonly property real loadedContentHeight: loader.item ? loader.item.implicitHeight : 0
  width: contentWidth
  height: contentHeight

  function fittedContentWidth(width, cap) {
    var desired = Math.max(1, Number(width) || 1)
    return Math.round(cap !== undefined && Number(cap) > 0 ? Math.min(desired, Number(cap)) : desired)
  }
  function fittedContentHeight(implicitHeight, cap) {
    var desired = Math.max(1, Number(implicitHeight) || 1)
    return Math.round(cap !== undefined && Number(cap) > 0 ? Math.min(desired, Number(cap)) : desired)
  }

  Loader {
    id: loader
    anchors.fill: parent
    active: root.open
    sourceComponent: root.content
  }
}
