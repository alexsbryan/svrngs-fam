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

// ---- The panel's lists, from one answer ----------------------------------

function running(answer) {
  return stateOf(answer) === "running"
}

// Groups this person is still in.
function groups(answer) {
  if (!running(answer)) return []
  return (answer.groups || []).filter(function(g) { return !g.left })
}

// What this computer lends, by name, with the groups' names it goes to.
function lent(answer) {
  if (!running(answer)) return []
  var names = {}
  groups(answer).forEach(function(g) { names[g.id] = g.name })
  // Whether each is running, and whether svrngs holds it closed, as svrngs
  // lists it to its own groups.
  var answering = {}
  var held = {}
  groups(answer).forEach(function(g) {
    var lends = answer.lends ? answer.lends[g.id] : null
    ;((lends && lends.lent) || []).forEach(function(l) {
      if (l.person !== g.person) return
      if (l.answering !== null && l.answering !== undefined) answering[l.name] = l.answering
      if (l.held) held[l.name] = l.held
    })
  })
  return (answer.mine || []).map(function(m) {
    return {
      name: m.name,
      port: m.port,
      groups: (m.groups || []).map(function(id) { return names[id] || "" }).filter(function(n) { return n !== "" }),
      answering: answering[m.name] === false ? false : true,
      held: held[m.name] || ""
    }
  })
}

// What runs here and could be lent. The helper already leaves out what is
// lent, svrngs itself, browsers' debug ports and the rest of its deny list.
function offers(answer) {
  if (!running(answer) || !answer.listeners) return []
  return answer.listeners.map(function(l) { return { port: l.port, program: l.program, name: l.name || l.program } })
}

// Each group's lends from other people, for Open.
function friendsLends(answer, group) {
  var lends = running(answer) && answer.lends ? answer.lends[group.id] : null
  if (!lends || !lends.lent) return []
  return lends.lent.filter(function(l) { return l.person !== group.person }).map(function(l) {
    return { person: l.person, name: l.name, label: labelOf(l.origin), answering: opens(l) }
  })
}

// Whether a lend can be opened now: its program runs, and svrngs doesn't
// hold it closed because another account's program answers in its place.
function opens(l) {
  return l.answering !== false && !l.held
}

// The people of a group whose computer did not answer svrngs just now:
// their lends are not listed at all, so they are named instead.
function unanswered(answer, group) {
  var lends = running(answer) && answer.lends ? answer.lends[group.id] : null
  return lends && lends.unanswered ? lends.unanswered : []
}

// The label `svrngs open` takes for a lend: its address's first name.
function labelOf(origin) {
  var match = /^http:\/\/([a-z0-9]+)\.localhost:\d+\/$/.exec(String(origin || ""))
  return match ? match[1] : ""
}

// The helper's argv to lend `offer` to `group` as `name`. The program is
// always said: svrngs refuses a port it does not know without it (S0 (c)).
function shareArgs(offer, groupId, name) {
  return ["share", String(offer.port), groupId, name, "--program", offer.program]
}

// A name svrngs takes for a lend, as the helper makes them.
function cleanName(wanted) {
  return String(wanted || "").toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40).replace(/-+$/, "")
}

// Which friends' lends are models changes only when the lends do; the
// panel asks again only then.
function lendsKey(answer) {
  if (!running(answer) || !answer.lends) return ""
  var labels = []
  for (var id in answer.lends)
    (answer.lends[id].lent || []).forEach(function(l) { labels.push(labelOf(l.origin)) })
  return labels.sort().join(",")
}

// ---- A group, as the panel draws it at scale --------------------------------
// What a group's people lend, by person, and what its folder carries, once
// (an app the group carries is answered by every computer holding it; the
// first, this computer's own when it has it, is the one opened). Each thing
// matched against `query` (its name, its person, or the group's name).
function groupView(answer, group, query) {
  var lends = (running(answer) && answer.lends ? answer.lends[group.id] : null) || null
  var q = String(query || "").trim().toLowerCase()
  var inGroup = q === "" || String(group.name).toLowerCase().indexOf(q) >= 0
  var hit = function(name, person) {
    return inGroup || String(name).toLowerCase().indexOf(q) >= 0 || String(person).toLowerCase().indexOf(q) >= 0
  }
  var people = []
  var byPerson = {}
  var carried = []
  var carriedNames = {}
  var count = 0
  ;((lends && lends.lent) || []).forEach(function(l) {
    var item = { name: l.name, label: labelOf(l.origin), answering: opens(l) }
    if (l.carried) {
      if (carriedNames[l.name]) return
      carriedNames[l.name] = true
      count += 1
      if (hit(l.name, "")) carried.push(item)
      return
    }
    if (l.person === group.person) return
    count += 1
    if (!hit(l.name, l.person)) return
    if (!byPerson[l.person]) { byPerson[l.person] = []; people.push({ person: l.person, items: byPerson[l.person] }) }
    byPerson[l.person].push(item)
  })
  var gone = ((lends && lends.unanswered) || []).filter(function(p) { return q === "" || inGroup || String(p).toLowerCase().indexOf(q) >= 0 })
  return {
    people: people,
    carried: carried,
    unanswered: gone,
    count: count,
    read: lends !== null && !lends.error,
    shown: q === "" || inGroup || people.length + carried.length + gone.length > 0
  }
}

// A group's line, closed: how many things it shares, and who did not answer.
function groupSummary(view, words) {
  if (!view.read) return words.unread
  var said = view.count === 1 ? words.one : words.many.replace("%1", view.count)
  return view.unanswered.length > 0 ? said + " · " + words.quiet.replace("%1", view.unanswered.length) : said
}

// Whether a model matches what is typed.
function modelShown(model, query) {
  var q = String(query || "").trim().toLowerCase()
  return q === "" || String(model.name).toLowerCase().indexOf(q) >= 0 || String(model.person).toLowerCase().indexOf(q) >= 0
}
