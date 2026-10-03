#!/usr/bin/env python3
"""H Tele Communication - Call Centre System. Zero dependencies (Python 3.8+)."""
import json
import sqlite3
import hashlib
import secrets
import os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("DATA_DIR", BASE)
os.makedirs(DATA, exist_ok=True)
DB = os.path.join(DATA, "htele.db")
ADMIN_PW = os.environ.get("ADMIN_PASSWORD", "admin123")
PORT = int(os.environ.get("PORT", 8000))
CAMPAIGNS = ["Medicare", "ACA"]
SESSIONS = {}  # token -> user_id

INDEX_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>H Tele Communication</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <section id="loginView" class="login">
    <form id="loginForm" class="card login-card">
      <h1>H Tele Communication</h1>
      <p class="muted">Sign in to your workspace</p>
      <label>Username<input id="lu" autocomplete="username" required></label>
      <label>Password<input id="lp" type="password" autocomplete="current-password" required></label>
      <button class="btn primary">Sign in</button>
      <p id="lerr" class="err"></p>
    </form>
  </section>

  <div id="app" hidden>
    <header class="top">
      <b>H Tele Communication</b>
      <span id="who" class="muted"></span>
      <span id="stBadge" class="badge"></span>
      <button id="outBtn" class="btn small">Sign out</button>
    </header>
    <nav id="tabs" class="tabs"></nav>

    <main id="agentView" hidden>
      <div class="card">
        <h2>My shift</h2>
        <div class="row">
          <button class="btn warn" id="bIn">Break in</button>
          <button class="btn ok" id="bOut">Break out</button>
          <button class="btn dark" id="bLogout">Log out</button>
        </div>
      </div>
      <div class="card">
        <h2>Add today's numbers</h2>
        <form id="agentEntry" class="grid">
          <label>Campaign<select name="campaign" class="campSel"></select></label>
          <label>Transfers<input name="transfers" type="number" min="0" value="0"></label>
          <label>CPL<input name="cpl" type="number" min="0" value="0"></label>
          <label>CPA<input name="cpa" type="number" min="0" value="0"></label>
          <button class="btn primary">Save numbers</button>
        </form>
      </div>
      <div class="card">
        <h2>My totals today</h2>
        <div id="myTotals" class="scroll"></div>
      </div>
      <div class="card">
        <h2>My activity today</h2>
        <div id="myEvents" class="scroll"></div>
      </div>
    </main>

    <main id="adminView" hidden>
      <section data-tab="Dashboard">
        <div class="card">
          <div class="filters">
            <label>From<input type="date" id="f1"></label>
            <label>To<input type="date" id="f2"></label>
            <label>Campaign<select id="fc"><option value="">All</option></select></label>
            <button class="btn primary" id="go">Show</button>
            <button class="btn" id="csv">Download CSV</button>
          </div>
          <div id="sum" class="sum"></div>
          <div id="rep" class="scroll"></div>
        </div>
        <div class="card">
          <h2>Activity log</h2>
          <div class="filters"><label>Date<input type="date" id="fd"></label></div>
          <div id="evs" class="scroll"></div>
        </div>
      </section>
      <section data-tab="Agents">
        <div class="card">
          <h2>Register agent</h2>
          <form id="newAgent" class="grid">
            <label>Full name<input name="name" required></label>
            <label>Username<input name="username" required></label>
            <label>Password<input name="password" required minlength="4"></label>
            <label>Phone<input name="phone"></label>
            <label>Campaign<select name="campaign" class="campSel"></select></label>
            <button class="btn primary">Register agent</button>
          </form>
          <p id="aerr" class="err"></p>
        </div>
        <div class="card">
          <h2>All agents</h2>
          <div id="agents" class="scroll"></div>
        </div>
      </section>
      <section data-tab="Numbers">
        <div class="card">
          <h2>Enter numbers for an agent</h2>
          <form id="adminEntry" class="grid">
            <label>Agent<select name="user_id" id="agSel"></select></label>
            <label>Date<input name="day" type="date" id="ed"></label>
            <label>Campaign<select name="campaign" class="campSel"></select></label>
            <label>Transfers<input name="transfers" type="number" min="0" value="0"></label>
            <label>CPL<input name="cpl" type="number" min="0" value="0"></label>
            <label>CPA<input name="cpa" type="number" min="0" value="0"></label>
            <button class="btn primary">Save numbers</button>
          </form>
        </div>
        <div class="card">
          <h2>Entries on this date</h2>
          <div id="ents" class="scroll"></div>
        </div>
      </section>
    </main>
  </div>

  <div id="toast" class="toast"></div>
  <script src="app.js"></script>
</body>
</html>
'''

STYLE_CSS = '''
:root {
  --ink: #14283c;
  --bg: #f2f5f8;
  --card: #fff;
  --line: #dbe3ea;
  --sig: #14866b;
  --amb: #c98a12;
  --red: #b3392f;
  --muted: #6a7a8a;
  --r: 10px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --ink: #e6edf3;
    --bg: #0f1a26;
    --card: #172536;
    --line: #2a3d52;
    --muted: #8fa2b5;
    --sig: #34b893;
    --amb: #e0a838;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font: 15px/1.45 "Segoe UI", system-ui, sans-serif;
  background: var(--bg);
  color: var(--ink);
}
.login { min-height: 100vh; display: grid; place-items: center; padding: 16px; }
.login-card { width: 100%; max-width: 360px; }
.card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--r);
  padding: 16px;
  margin: 12px 0;
}
h1 { margin: 0 0 4px; font-size: 22px; }
h2 { margin: 0 0 12px; font-size: 16px; }
.muted { color: var(--muted); }
.err { color: var(--red); min-height: 1.2em; margin: 8px 0 0; }
label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 10px;
}
input, select {
  font: inherit;
  padding: 9px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--bg);
  color: var(--ink);
  width: 100%;
}
input:focus, select:focus, button:focus-visible {
  outline: 2px solid var(--sig);
  outline-offset: 1px;
}
.btn {
  font: inherit;
  padding: 9px 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--card);
  color: var(--ink);
  cursor: pointer;
}
.btn.primary { background: var(--sig); border-color: var(--sig); color: #fff; }
.btn.warn { background: var(--amb); border-color: var(--amb); color: #fff; }
.btn.ok { background: var(--sig); border-color: var(--sig); color: #fff; }
.btn.dark { background: var(--ink); color: var(--bg); }
.btn.small { padding: 5px 10px; font-size: 13px; }
.top {
  display: flex; gap: 12px; align-items: center; padding: 12px 16px;
  background: var(--card); border-bottom: 1px solid var(--line); flex-wrap: wrap;
}
.top .btn { margin-left: auto; }
.badge {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 99px;
  border: 1px solid var(--line);
}
.badge.Online { background: var(--sig); color: #fff; border-color: var(--sig); }
.badge.On { background: var(--amb); color: #fff; border-color: var(--amb); }
.tabs {
  display: flex; gap: 4px; padding: 8px 16px 0; overflow-x: auto;
}
.tabs button {
  font: inherit; border: 0; background: none; color: var(--muted);
  padding: 8px 14px; border-bottom: 3px solid transparent; cursor: pointer;
}
.tabs button.on { color: var(--ink); border-color: var(--sig); font-weight: 600; }
main {
  max-width: 1100px; margin: 0 auto; padding: 0 16px 40px;
}
.row { display: flex; gap: 10px; flex-wrap: wrap; }
.grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0 12px; align-items: end;
}
.grid .btn { margin-bottom: 10px; }
.filters {
  display: flex; gap: 12px; flex-wrap: wrap; align-items: end; margin-bottom: 8px;
}
.filters label { margin: 0; }
.filters .btn { margin-bottom: 0; }
.scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 560px; }
th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { font-size: 12px; color: var(--muted); font-weight: 600; }
.sum {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 10px; margin: 12px 0;
}
.sum div {
  border: 1px solid var(--line); border-radius: 8px; padding: 10px;
}
.sum b { display: block; font-size: 24px; }
.sum span { font-size: 12px; color: var(--muted); }
.toast {
  position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
  background: var(--ink); color: var(--bg); padding: 10px 18px; border-radius: 8px;
  opacity: 0; pointer-events: none; transition: opacity .2s;
}
.toast.show { opacity: 1; }
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
'''

APP_JS = '''
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
let T = localStorage.getItem("ht_token") || "";
let ME = null;
let LAST = [];

const today = () => new Date().toLocaleDateString("en-CA");
const hm = m => Math.floor(m / 60) + "h " + String(m % 60).padStart(2, "0") + "m";
const esc = s => String(s ?? "").replace(/[&<>\"]/g, c => ({"&":"&amp;","<":"&lt;", ">":"&gt;", '"':"&quot;"})[c]);

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2200);
}

async function api(path, body) {
  const options = { headers: { Authorization: "Bearer " + T } };
  if (body) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const r = await fetch("/api/" + path, options);
  const d = await r.json();
  if (r.status === 401 && path !== "login") {
    logoutUI();
    throw d;
  }
  if (!r.ok) throw d;
  return d;
}

function table(headers, rows) {
  if (!rows.length) return '<p class="muted">Nothing here yet.</p>';
  return '<table><tr>' + headers.map(x => '<th>' + x + '</th>').join("") + '</tr>' + rows.map(r => '<tr>' + r.map(c => '<td>' + c + '</td>').join("") + '</tr>').join("") + '</table>';
}

$("#loginForm").onsubmit = async e => {
  e.preventDefault();
  $("#lerr").textContent = "";
  try {
    const d = await api("login", { username: $("#lu").value, password: $("#lp").value });
    T = d.token;
    localStorage.setItem("ht_token", T);
    start();
  } catch (x) {
    $("#lerr").textContent = x.error || "Could not sign in";
  }
};

function logoutUI() {
  T = "";
  localStorage.removeItem("ht_token");
  $("#app").hidden = true;
  $("#loginView").hidden = false;
}

$("#outBtn").onclick = async () => {
  try {
    await api(ME.role === "agent" ? "event" : "logout", ME.role === "agent" ? { type: "logout" } : {});
  } catch (e) {}
  logoutUI();
};

async function start() {
  try {
    ME = await api("me");
  } catch (e) {
    return logoutUI();
  }

  $("#loginView").hidden = true;
  $("#app").hidden = false;
  $("#who").textContent = ME.name;

  $$(".campSel").forEach(s => {
    s.innerHTML = ME.campaigns.map(c => `<option>${c}</option>`).join("");
  });
  $("#fc").innerHTML = '<option value="">All</option>' + ME.campaigns.map(c => `<option>${c}</option>`).join("");

  if (ME.role === "agent") {
    $("#agentView").hidden = true;
    $("#adminView").hidden = true;
    $("#tabs").innerHTML = "";
    $("#agentView").hidden = false;
    loadAgent();
  } else {
    $("#adminView").hidden = false;
    $("#agentView").hidden = true;
    tabs();
    $("#f1").value = $("#f2").value = $("#fd").value = $("#ed").value = today();
    loadAdmin();
  }
}

function badge(status) {
  const b = $("#stBadge");
  b.textContent = status || "";
  b.className = "badge " + (status || "").split(" ")[0];
}

function tabs() {
  const secs = $$("#adminView section");
  $("#tabs").innerHTML = secs.map((s, i) => `<button data-i="${i}">${s.dataset.tab}</button>`).join("");
  const show = i => {
    secs.forEach((s, j) => s.hidden = i != j);
    $$("#tabs button").forEach((b, j) => b.classList.toggle("on", i == j));
  };
  $$("#tabs button").forEach(b => b.onclick = () => show(+b.dataset.i));
  show(0);
}

async function loadAgent() {
  ME = await api("me");
  badge(ME.status);
  const r = await api("report?from=" + today() + "&to=" + today());
  const x = r[0] || {};
  $("#myTotals").innerHTML = table(
    ["First login", "Break time", "Working time", "Transfers", "CPL", "CPA"],
    [[(x.first_login || "").slice(11), hm(x.break_min || 0), hm(x.work_min || 0), x.transfers || 0, x.cpl || 0, x.cpa || 0]]
  );
  const ev = await api("events?date=" + today());
  $("#myEvents").innerHTML = table(["Time", "Action"], ev.map(e => [e.ts.slice(11), e.type.replace("_", " ") ]));
}

async function ev(type) {
  try {
    await api("event", { type });
    toast("Saved");
    loadAgent();
  } catch (e) {
    toast(e.error || "Failed");
  }
}

$("#bIn").onclick = () => ev("break_in");
$("#bOut").onclick = () => ev("break_out");
$("#bLogout").onclick = () => $("#outBtn").click();

$("#agentEntry").onsubmit = async e => {
  e.preventDefault();
  try {
    await api("entry", Object.fromEntries(new FormData(e.target)));
    toast("Numbers saved");
    loadAgent();
  } catch (x) {
    toast(x.error || "Failed");
  }
};

async function loadAdmin() {
  loadReport();
  loadEvents();
  loadAgents();
  loadEntries();
}

async function loadReport() {
  const q = `from=${$("#f1").value}&to=${$("#f2").value}&campaign=${$("#fc").value}`;
  LAST = await api("report?" + q);
  const s = k => LAST.reduce((a, r) => a + r[k], 0);
  $("#sum").innerHTML = [
    ["Agents online", LAST.filter(r => r.status == "Online").length],
    ["On break", LAST.filter(r => r.status == "On break").length],
    ["Transfers", s("transfers")],
    ["CPL", s("cpl")],
    ["CPA", s("cpa")]
  ].map(([label, value]) => `<div><b>${value}</b><span>${label}</span></div>`).join("");

  $("#rep").innerHTML = table(
    ["Agent", "Campaign", "Status", "First login", "Last logout", "Break", "Working", "Transfers", "CPL", "CPA"],
    LAST.map(r => [esc(r.name), esc(r.campaign), r.status, r.first_login.slice(11), r.last_logout.slice(11), hm(r.break_min), hm(r.work_min), r.transfers, r.cpl, r.cpa])
  );
}

async function loadEvents() {
  const e = await api("events?date=" + $("#fd").value);
  $("#evs").innerHTML = table(["Time", "Agent", "Action"], e.map(x => [x.ts.slice(11), esc(x.name), x.type.replace("_", " ")]));
}

async function loadAgents() {
  const a = await api("agents");
  $("#agSel").innerHTML = a.filter(x => x.active).map(x => `<option value="${x.id}">${esc(x.name)}</option>`).join("");
  $("#agents").innerHTML = table(
    ["Name", "Username", "Campaign", "Phone", "Status", ""],
    a.map(x => [
      esc(x.name), esc(x.username), esc(x.campaign), esc(x.phone), x.active ? "Active" : "Disabled",
      `<button class="btn small" onclick="tog(${x.id},${x.active ? 0 : 1})">${x.active ? "Disable" : "Enable"}</button> <button class="btn small" onclick="pw(${x.id})">Reset password</button>`
    ])
  );
}

async function loadEntries() {
  const e = await api("entries?date=" + $("#ed").value);
  $("#ents").innerHTML = table(
    ["Agent", "Campaign", "Transfers", "CPL", "CPA", ""],
    e.map(x => [esc(x.name), x.campaign, x.transfers, x.cpl, x.cpa, `<button class="btn small" onclick="del(${x.id})">Delete</button>`])
  );
}

window.tog = async (id, active) => {
  await api("agent_update", { id, active });
  loadAgents();
};

window.pw = async id => {
  const p = prompt("New password (4+ characters)");
  if (p && p.length >= 4) {
    await api("agent_update", { id, password: p });
    toast("Password changed");
  }
};

window.del = async id => {
  if (confirm("Delete this entry?")) {
    await api("entry_delete", { id });
    loadEntries();
    loadReport();
  }
};

$("#go").onclick = loadReport;
$("#fd").onchange = loadEvents;
$("#ed").onchange = loadEntries;

$("#newAgent").onsubmit = async e => {
  e.preventDefault();
  $("#aerr").textContent = "";
  try {
    await api("agents", Object.fromEntries(new FormData(e.target)));
    e.target.reset();
    toast("Agent registered");
    loadAgents();
  } catch (x) {
    $("#aerr").textContent = x.error;
  }
};

$("#adminEntry").onsubmit = async e => {
  e.preventDefault();
  try {
    await api("entry", Object.fromEntries(new FormData(e.target)));
    toast("Numbers saved");
    loadEntries();
    loadReport();
  } catch (x) {
    toast(x.error || "Failed");
  }
};

$("#csv").onclick = () => {
  const headers = ["Agent", "Campaign", "First login", "Last logout", "Break min", "Working min", "Transfers", "CPL", "CPA"];
  const rows = LAST.map(r => [r.name, r.campaign, r.first_login, r.last_logout, r.break_min, r.work_min, r.transfers, r.cpl, r.cpa]);
  const csv = [headers, ...rows].map(r => r.map(v => '"' + String(v ?? "").replace(/"/g, '""') + '"').join(",")).join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = "htele_report.csv";
  a.click();
};

setInterval(() => {
  if (T && ME && ME.role === "agent") loadAgent();
  else if (T && ME) loadReport();
}, 60000);

if (T) start();
'''

ASSETS = {
    "index.html": INDEX_HTML,
    "style.css": STYLE_CSS,
    "app.js": APP_JS,
}

TYPES = {
    "index.html": "text/html; charset=utf-8",
    "style.css": "text/css",
    "app.js": "application/javascript",
}


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT,
        username TEXT UNIQUE,
        salt TEXT,
        pw TEXT,
        role TEXT DEFAULT 'agent',
        campaign TEXT,
        phone TEXT,
        active INTEGER DEFAULT 1,
        created TEXT
    );

    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        type TEXT,
        ts TEXT
    );

    CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        day TEXT,
        campaign TEXT,
        transfers INTEGER,
        cpl INTEGER,
        cpa INTEGER,
        note TEXT,
        created TEXT
    );
    """)

    if not c.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        salt, pw = hp(ADMIN_PW)
        c.execute(
            "INSERT INTO users(name, username, salt, pw, role, created) VALUES(?,?,?,?, 'admin',?)",
            ("Admin", "admin", salt, pw, now()),
        )

    c.commit()
    c.close()


def hp(password, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt, hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today():
    return datetime.now().strftime("%Y-%m-%d")


def parse_ts(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def report(c, d1, d2, campaign="", uid=None):
    q = "SELECT id, name, username, campaign FROM users WHERE role='agent'"
    if uid:
        q += f" AND id={uid}"

    out = []
    for u in c.execute(q).fetchall():
        ev = c.execute(
            "SELECT type, ts FROM events WHERE user_id=? AND date(ts) BETWEEN ? AND ? ORDER BY ts",
            (u["id"], d1, d2),
        ).fetchall()

        logins = [e["ts"] for e in ev if e["type"] == "login"]
        logouts = [e["ts"] for e in ev if e["type"] == "logout"]

        brk = 0
        open_b = None
        work = 0
        start = None

        for e in ev:
            ts = parse_ts(e["ts"])
            typ = e["type"]
            if typ == "login":
                start = ts
            elif typ == "break_in":
                open_b = ts
            elif typ == "break_out" and open_b:
                brk += (ts - open_b).total_seconds()
                open_b = None
            elif typ == "logout" and start:
                work += (ts - start).total_seconds()
                start = None
                if open_b:
                    brk += (ts - open_b).total_seconds()
                    open_b = None

        now_dt = datetime.now()
        if start:
            work += (now_dt - start).total_seconds()
        if open_b:
            brk += (now_dt - open_b).total_seconds()

        status = "Offline"
        if ev:
            last = ev[-1]["type"]
            status = {"login": "Online", "break_out": "Online", "break_in": "On break", "logout": "Offline"}[last]

        eq = "SELECT COALESCE(SUM(transfers),0) t, COALESCE(SUM(cpl),0) l, COALESCE(SUM(cpa),0) a FROM entries WHERE user_id=? AND day BETWEEN ? AND ?"
        args = [u["id"], d1, d2]
        if campaign:
            eq += " AND campaign=?"
            args.append(campaign)
        s = c.execute(eq, args).fetchone()

        out.append({
            "id": u["id"],
            "name": u["name"],
            "username": u["username"],
            "campaign": u["campaign"],
            "first_login": logins[0] if logins else "",
            "last_logout": logouts[-1] if logouts else "",
            "break_min": round(brk / 60),
            "work_min": round(max(work - brk, 0) / 60),
            "status": status,
            "transfers": s["t"],
            "cpl": s["l"],
            "cpa": s["a"],
        })

    return out


class H(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def user(self):
        token = self.headers.get("Authorization", "").replace("Bearer ", "")
        user_id = SESSIONS.get(token)
        if not user_id:
            return None
        c = db()
        user = c.execute("SELECT * FROM users WHERE id=? AND active=1", (user_id,)).fetchone()
        c.close()
        return user

    def body(self):
        n = int(self.headers.get("Content-Length", 0))
        if not n:
            return {}
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        if not parsed.path.startswith("/api/"):
            if parsed.path == "/":
                file_name = "index.html"
            else:
                file_name = parsed.path.lstrip("/")
            if file_name not in ASSETS:
                return self.send({"error": "not found"}, 404)
            content = ASSETS[file_name].encode()
            self.send_response(200)
            self.send_header("Content-Type", TYPES[file_name])
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        me = self.user()
        if not me:
            return self.send({"error": "login required"}, 401)

        c = db()
        try:
            if parsed.path == "/api/me":
                stats = report(c, today(), today(), uid=me["id"]) if me["role"] == "agent" else []
                return self.send({
                    "id": me["id"],
                    "name": me["name"],
                    "role": me["role"],
                    "campaign": me["campaign"],
                    "status": stats[0]["status"] if stats else "",
                    "campaigns": CAMPAIGNS,
                })

            if parsed.path == "/api/report":
                d1 = query.get("from", today())
                d2 = query.get("to", today())
                uid = me["id"] if me["role"] == "agent" else (int(query["agent"]) if query.get("agent") else None)
                return self.send(report(c, d1, d2, query.get("campaign", ""), uid))

            if parsed.path == "/api/events":
                day = query.get("date", today())
                sql = "SELECT e.type, e.ts, u.name FROM events e JOIN users u ON u.id=e.user_id WHERE date(e.ts)=?"
                args = [day]
                if me["role"] == "agent":
                    sql += " AND e.user_id=?"
                    args.append(me["id"])
                rows = c.execute(sql + " ORDER BY e.ts DESC", args)
                return self.send([dict(r) for r in rows])

            if parsed.path == "/api/entries":
                day = query.get("date", today())
                sql = "SELECT n.id, n.day, n.campaign, n.transfers, n.cpl, n.cpa, n.note, u.name FROM entries n JOIN users u ON u.id=n.user_id WHERE n.day=?"
                args = [day]
                if me["role"] == "agent":
                    sql += " AND n.user_id=?"
                    args.append(me["id"])
                rows = c.execute(sql + " ORDER BY n.id DESC", args)
                return self.send([dict(r) for r in rows])

            if me["role"] != "admin":
                return self.send({"error": "admin only"}, 403)

            if parsed.path == "/api/agents":
                rows = c.execute("SELECT id, name, username, campaign, phone, active, created FROM users WHERE role='agent' ORDER BY id DESC")
                return self.send([dict(r) for r in rows])

            return self.send({"error": "not found"}, 404)
        finally:
            c.close()

    def do_POST(self):
        parsed = urlparse(self.path)
        payload = self.body()
        c = db()
        try:
            if parsed.path == "/api/login":
                username = payload.get("username", "").strip()
                password = payload.get("password", "")
                row = c.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
                if not row or hp(password, row["salt"])[1] != row["pw"]:
                    return self.send({"error": "Wrong username or password"}, 401)
                token = secrets.token_hex(24)
                SESSIONS[token] = row["id"]
                if row["role"] == "agent":
                    c.execute("INSERT INTO events(user_id, type, ts) VALUES(?,?,?)", (row["id"], "login", now()))
                    c.commit()
                return self.send({"token": token, "role": row["role"]})

            me = self.user()
            if not me:
                return self.send({"error": "login required"}, 401)

            if parsed.path == "/api/event" and me["role"] == "agent":
                event_type = payload.get("type")
                if event_type not in ("break_in", "break_out", "logout"):
                    return self.send({"error": "bad type"}, 400)
                c.execute("INSERT INTO events(user_id, type, ts) VALUES(?,?,?)", (me["id"], event_type, now()))
                c.commit()
                if event_type == "logout":
                    for key in [k for k, v in SESSIONS.items() if v == me["id"]]:
                        del SESSIONS[key]
                return self.send({"ok": 1})

            if parsed.path == "/api/logout":
                for key in [k for k, v in SESSIONS.items() if v == me["id"]]:
                    del SESSIONS[key]
                return self.send({"ok": 1})

            if parsed.path == "/api/entry":
                uid = me["id"] if me["role"] == "agent" else int(payload.get("user_id") or 0)
                if not uid or payload.get("campaign") not in CAMPAIGNS:
                    return self.send({"error": "Pick agent and campaign"}, 400)
                def value(key):
                    return max(int(payload.get(key) or 0), 0)
                c.execute(
                    "INSERT INTO entries(user_id, day, campaign, transfers, cpl, cpa, note, created) VALUES(?,?,?,?,?,?,?,?)",
                    (uid, payload.get("day") or today(), payload["campaign"], value("transfers"), value("cpl"), value("cpa"), payload.get("note", ""), now()),
                )
                c.commit()
                return self.send({"ok": 1})

            if me["role"] != "admin":
                return self.send({"error": "admin only"}, 403)

            if parsed.path == "/api/agents":
                name = payload.get("name")
                username = payload.get("username")
                password = payload.get("password", "")
                if not name or not username or len(password) < 4:
                    return self.send({"error": "Name, username and a password of 4+ characters are required"}, 400)
                salt, pw = hp(password)
                try:
                    c.execute(
                        "INSERT INTO users(name, username, salt, pw, role, campaign, phone, created) VALUES(?,?,?,?, 'agent',?,?,?)",
                        (name.strip(), username.strip(), salt, pw, payload.get("campaign", ""), payload.get("phone", ""), now()),
                    )
                    c.commit()
                except sqlite3.IntegrityError:
                    return self.send({"error": "Username already taken"}, 400)
                return self.send({"ok": 1})

            if parsed.path == "/api/agent_update":
                if "active" in payload:
                    c.execute("UPDATE users SET active=? WHERE id=? AND role='agent'", (int(payload["active"]), payload["id"]))
                if payload.get("password"):
                    salt, pw = hp(payload["password"])
                    c.execute("UPDATE users SET salt=?, pw=? WHERE id=? AND role='agent'", (salt, pw, payload["id"]))
                c.commit()
                return self.send({"ok": 1})

            if parsed.path == "/api/entry_delete":
                c.execute("DELETE FROM entries WHERE id=?", (payload["id"],))
                c.commit()
                return self.send({"ok": 1})

            return self.send({"error": "not found"}, 404)
        except (ValueError, KeyError, TypeError):
            return self.send({"error": "Invalid data"}, 400)
        finally:
            c.close()


if __name__ == "__main__":
    init()
    print(f"H Tele Communication running on http://localhost:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
