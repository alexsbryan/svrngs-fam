.pragma library

// What the bar decides from the helper's answer, kept apart from QML so the
// logic test can drive it with no shell around it.

// The helper's `svrngs` field is one of these, and nothing else is believed:
// an answer naming another is read as could-not-read, never as stopped.
var STATES = ["running", "stopped", "never-started", "not-installed", "unreadable"]

// One helper answer, parsed. `reading` is the state before any answer.
function parse(raw) {
  var answer
  try {
    answer = JSON.parse(String(raw))
  } catch (e) {
    return { svrngs: "unreadable", reason: "the helper's answer was not JSON" }
  }
  if (!answer || typeof answer !== "object") return { svrngs: "unreadable", reason: "the helper answered nothing" }
  if (STATES.indexOf(answer.svrngs) < 0)
    return { svrngs: "unreadable", reason: "the helper said svrngs is " + JSON.stringify(answer.svrngs) }
  return answer
}

function stateOf(answer) {
  return answer ? answer.svrngs : "reading"
}

// How the icon looks: lit only while svrngs answers, crossed when there is no
// svrngs here at all, and a warning when an answer could not be read, which is
// not the same as stopped and is never drawn as it.
function look(answer) {
  var state = stateOf(answer)
  return {
    lit: state === "running",
    crossed: state === "not-installed",
    warning: state === "unreadable"
  }
}

// The count beside the icon: this computer's lends, from their files, shown
// only while svrngs runs to serve them.
function badge(answer, lentHere) {
  return stateOf(answer) === "running" && lentHere > 0 ? String(lentHere) : ""
}

// The catalog key that says the state in words.
function words(answer) {
  return "state." + stateOf(answer)
}
