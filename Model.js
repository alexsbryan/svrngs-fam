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
  // lists it to its own groups. A held one's reason, the token it was
  // listed with and what svrngs read answering on its port are taken from
  // one row, the first that says it is held: approving sends back what that
  // row showed.
  var answering = {}
  var held = {}
  groups(answer).forEach(function(g) {
    var lends = answer.lends ? answer.lends[g.id] : null
    ;((lends && lends.lent) || []).forEach(function(l) {
      if (l.person !== g.person) return
      if (l.answering !== null && l.answering !== undefined) answering[l.name] = l.answering
      if (l.held && !held[l.name]) held[l.name] = l
    })
  })
  return (answer.mine || []).map(function(m) {
    var row = held[m.name] || {}
    return {
      name: m.name,
      port: m.port,
      groups: (m.groups || []).map(function(id) { return names[id] || "" }).filter(function(n) { return n !== "" }),
      answering: answering[m.name] === false ? false : true,
      held: row.held || "",
      token: typeof row.token === "string" ? row.token : "",
      unread: typeof row.unread === "string" ? row.unread : "",
      now: nowOf(row.now)
    }
  })
}

// The catalog key for why svrngs holds a lend of yours closed, for each
// reason the panel has words for (svrngs lend.rs `Hold`). Any other reason
// is still held: its line says so, and offers nothing to press.
var HELD = { another: "here.heldAnother", unjudged: "here.heldUnjudged", unapproved: "here.heldUnapproved" }

function heldKey(held) {
  return Object.prototype.hasOwnProperty.call(HELD, held) ? HELD[held] : "here.heldUnknown"
}

// What answers on a held lend's port, as svrngs read it for the lend's row
// (the helper's `svrngs_now`): null when the row says nothing, from an
// svrngs before 1.13.0 or where svrngs couldn't read it (the row's
// `unread`); else whether anything runs there and whether Keep sharing it
// keeps the share to it: only a program of yours, by its process, named
// by its program and the folder svrngs read. Another account's program
// among what answers is named by its `account`, and is never kept to, as
// Lend never lends one; `said` names every program and account svrngs
// listed there.
function nowOf(n) {
  if (n === undefined) return null
  if (n === null) return { running: false, keep: false, program: "", folder: "", said: "", pid: null, start: null, account: "" }
  var counted = function(v) { return typeof v === "number" && v >= 0 && Math.floor(v) === v }
  var account = typeof n.account === "string" ? n.account : ""
  var process = counted(n.pid) && counted(n.start) && account === ""
  var said = typeof n.said === "string" ? n.said : ""
  return { running: true, keep: process, program: n.program || "", folder: n.folder || "", said: said, pid: process ? n.pid : null, start: process ? n.start : null, account: account }
}

// Whether a lend of yours offers Keep sharing it: svrngs listed it with a
// token, which it gives only where approving it would be taken (svrngs
// share.rs `approve`, the one decider), and what answers there is a
// program of yours that isn't on the helper's deny list.
function keepable(l) {
  return !!l && l.token !== "" && l.now !== null && l.now.keep === true
}

// The helper's argv to keep sharing `l` to what its line shows: the token
// its row was listed with, and the process of yours the line names. svrngs
// approves that only while it is still what answers, every socket there
// that process's, and changes nothing else.
function approveArgs(l) {
  return ["approve", l.name, "--token", l.token, "--pid", processOf(l.now)]
}

// What listens on each of this computer's lends' ports, by the helper's own
// read of this computer (its `answering_now`), as one string; "" when this
// computer wasn't read. A change while the panel is open asks svrngs again
// (Service.qml), so what a held lend's line shows is svrngs's read of now.
function portsKey(answer) {
  if (!running(answer) || !answer.listeners) return ""
  return (answer.mine || []).map(function(m) {
    var n = m.now
    return m.name + "=" + (n === undefined ? "?" : n === null ? "-" : n.pid === null ? "x" : n.pid + "@" + n.start)
  }).join(",")
}

// A process as svrngs is told it: its pid and its start, so a pid that now
// names another process is refused, not lent.
function processOf(p) {
  return String(p.pid) + "@" + String(p.start)
}

// What runs here and could be lent. The helper already leaves out what is
// lent, svrngs itself, browsers' debug ports and the rest of its deny list.
// Each keeps the pid and start of the process shown, which lending it names,
// and whether that process only passes the port on (`through`: pasta for a
// container), and is offered under a name no other port's lend has.
function offers(answer) {
  if (!running(answer) || !answer.listeners) return []
  return answer.listeners.map(function(l) {
    return { port: l.port, program: l.program, name: freeName(l.name || l.program, l.port, answer.mine), pid: l.pid, start: l.start, through: l.through === true }
  })
}

// A lend's name is its address, where friends' browsers keep its sign-ins
// and links, and svrngs refuses one already lent for another port unless
// told to replace it, which the panel never says. So a name another port's
// lend has (or a lend whose port can't be read) is offered as name-2,
// name-3 and so on, the first that's free.
function freeName(wanted, port, mine) {
  var taken = Object.create(null)
  ;(mine || []).forEach(function(m) { if (m.port !== port) taken[m.name] = true })
  var base = cleanName(wanted)
  var name = base
  for (var n = 2; taken[name]; n++) {
    var suffix = "-" + n
    name = base.slice(0, 40 - suffix.length).replace(/-+$/, "") + suffix
  }
  return name
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
// hold it closed, for any reason (the helper gives one it doesn't know as
// "unknown").
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

// The helper's argv to lend `offer` to `group` as `name`. The helper asks
// svrngs first with no program, so a port svrngs knows is lent with the
// terms svrngs ships for it, and says `--program` only for a port svrngs
// doesn't know (svrngs refuses that without one, S0 (c)): `program`, the
// one the person named once svrngs asked, else the program the panel read
// on the port, unless that only passes it on (pasta, for a container),
// which says nothing of what answers. The process the panel showed is
// always said: svrngs lends the port only if that process holds every
// socket on it, and keeps the lend to those sockets.
function shareArgs(offer, groupId, name, program) {
  var said = program || (offer.through ? "" : offer.program)
  var named = said ? ["--program", said] : []
  return ["share", String(offer.port), groupId, name].concat(named, ["--pid", processOf(offer)])
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
