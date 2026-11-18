import QtQuick
import qs.Commons
import qs.Commons as Commons

// Stands in for qs.Ui's KeyboardPanel when drawing the preview: the panel's
// card as Omarchy draws it (its popup colours, border and padding), on a
// plain item, since a layer shell window has no backend offscreen.
Rectangle {
  id: root
  objectName: "previewCard"
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
  readonly property int pad: Style.spacing.popupPadding
  z: 10
  // Its whole content, not the panel's height cap: a preview shows what
  // a person would scroll to.
  width: contentWidth + pad * 2
  height: Math.max(contentHeight, loadedContentHeight) + pad * 2
  color: Commons.Color.popups.background
  border.color: Commons.Color.popups.border
  border.width: Math.max(1, Style.space(2))

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
    x: root.pad
    y: root.pad
    width: root.contentWidth
    height: Math.max(root.contentHeight, root.loadedContentHeight)
    active: root.open
    sourceComponent: root.content
  }
}
