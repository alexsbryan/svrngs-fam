import QtQuick
import QtQuick.Shapes

// svrngs's mark, drawn from its own geometry (svrngs docs/brand/src/mark.mjs,
// as mark-small.svg and mark-medium.svg draw it): three people, each a dot
// with a ring, and the gold ring of the record they keep. `cut` is "small"
// under 32 px, "medium" from 32 px (docs/brand/README.md, "One cut per
// size"). Each colour is its own, so the bar can draw it in one ink.
Item {
  id: root

  property real size: 16
  property string cut: "small"
  property color ink: "white"
  property color record: "gold"
  property color people: "salmon"
  // A slash across it, in its ink: svrngs not on this computer.
  property bool crossed: false

  readonly property bool small: cut === "small"
  // Each cut's viewBox: its origin and side.
  readonly property real boxX: small ? -94.84 : -91.34
  readonly property real boxY: small ? -106.34 : -102.84
  readonly property real box: small ? 189.67 : 182.67
  readonly property real recordWidth: small ? 14 : 7
  readonly property real ringWidth: small ? 12 : 4.5
  readonly property real dot: small ? 14 : 10
  readonly property real dotWidth: small ? 6 : 4
  readonly property var rings: small
    ? ["M-44.71 -35.2 A46 46 0 1 1 44.71 -35.2", "M52.84 -21.12 A46 46 0 1 1 8.12 56.32", "M-8.12 56.32 A46 46 0 1 1 -52.84 -21.12"]
    : ["M-42.87 -29.33 A46 46 0 1 1 42.87 -29.33", "M46.84 -22.46 A46 46 0 1 1 3.96 51.79", "M-3.96 51.79 A46 46 0 1 1 -46.84 -22.46"]

  width: size
  height: size
  implicitWidth: size
  implicitHeight: size

  Shape {
    width: root.box
    height: root.box
    preferredRendererType: Shape.CurveRenderer
    transform: [
      Translate { x: -root.boxX; y: -root.boxY },
      Scale { xScale: root.size / root.box; yScale: root.size / root.box }
    ]

    ShapePath {
      strokeColor: root.record
      strokeWidth: root.recordWidth
      fillColor: "transparent"
      PathAngleArc { radiusX: 46; radiusY: 46; startAngle: 0; sweepAngle: 360 }
    }
    ShapePath {
      strokeColor: root.ink; strokeWidth: root.ringWidth; fillColor: "transparent"; capStyle: ShapePath.FlatCap
      PathSvg { path: root.rings[0] }
    }
    ShapePath {
      strokeColor: root.ink; strokeWidth: root.ringWidth; fillColor: "transparent"; capStyle: ShapePath.FlatCap
      PathSvg { path: root.rings[1] }
    }
    ShapePath {
      strokeColor: root.ink; strokeWidth: root.ringWidth; fillColor: "transparent"; capStyle: ShapePath.FlatCap
      PathSvg { path: root.rings[2] }
    }
    ShapePath {
      strokeColor: root.ink; strokeWidth: root.dotWidth; fillColor: root.people
      PathAngleArc { centerX: 0; centerY: -46; radiusX: root.dot; radiusY: root.dot; startAngle: 0; sweepAngle: 360 }
    }
    ShapePath {
      strokeColor: root.ink; strokeWidth: root.dotWidth; fillColor: root.people
      PathAngleArc { centerX: 39.84; centerY: 23; radiusX: root.dot; radiusY: root.dot; startAngle: 0; sweepAngle: 360 }
    }
    ShapePath {
      strokeColor: root.ink; strokeWidth: root.dotWidth; fillColor: root.people
      PathAngleArc { centerX: -39.84; centerY: 23; radiusX: root.dot; radiusY: root.dot; startAngle: 0; sweepAngle: 360 }
    }
    ShapePath {
      strokeColor: root.crossed ? root.ink : "transparent"
      strokeWidth: root.ringWidth * 1.3
      fillColor: "transparent"
      capStyle: ShapePath.RoundCap
      startX: -70; startY: 50
      PathLine { x: 70; y: -90 }
    }
  }
}
