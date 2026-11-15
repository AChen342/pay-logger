"use strict";
// Pay Logger web app. Talks to the FastAPI endpoints in web/server.py and
// renders each screen; all the numbers come from the same Python as the
// desktop app, so this file only fetches and lays out.

const $ = (sel, el = document) => el.querySelector(sel);
const views = $("#views");
let STATE = null;          // last /api/state payload
let CURRENT = "home";

// --- helpers --------------------------------------------------------------
function money(v, cents = true) {
  if (v === null || v === undefined || isNaN(v)) return "—";
  return "$" + Number(v).toLocaleString("en-US",
    { minimumFractionDigits: cents ? 2 : 0, maximumFractionDigits: cents ? 2 : 0 });
}
function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}
function esc(s) { return (s ?? "").toString().replace(/[&<>"]/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function fmtDateISO(iso) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}
let toastTimer;
function toast(msg, isErr) {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast" + (isErr ? " err" : ""); t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.hidden = true, 3000);
}
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  return r.status === 204 ? null : r.json();
}

// --- sortable tables ------------------------------------------------------
// Click a column header to sort by it: money and hours go biggest first,
// dates oldest first, text A→Z; Notes doesn't sort. Click again to flip, a third time to go back to
// the original order. Blank cells always sink to the bottom. The choice is
// remembered per table, so it survives re-renders (e.g. after an edit).
// Text and date columns go A→Z / oldest-first on the first click (the
// tables already open newest-first, so a newest-first click changed nothing).
const ASC_FIRST = new Set(["Type", "Section", "Shift Type", "Day", "Date",
  "Start", "End", "Week Ending", "Month", "Year"]);
const UNSORTABLE = new Set(["Notes"]);
const SORTS = {};
function sortKey(text) {
  const s = (text ?? "").toString().trim();
  if (!s || s === "—") return null;
  let m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);                    // ISO
  if (m) return +new Date(+m[1], m[2] - 1, +m[3]);
  m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);                  // MM/DD/YYYY
  if (m) return +new Date(+m[3], m[1] - 1, +m[2]);
  m = s.match(/^(\d{1,2})\/(\d{4})$/);                             // MM/YYYY
  if (m) return +new Date(+m[2], m[1] - 1, 1);
  const n = parseFloat(s.replace(/[$,]|\/hr$/g, ""));
  if (!isNaN(n) && /^[-$\d.,]+(\/hr)?$/.test(s)) return n;
  return s.toLowerCase();
}
function compareKeys(a, b) {
  if (typeof a === typeof b) return a < b ? -1 : a > b ? 1 : 0;
  return typeof a === "number" ? -1 : 1;          // numbers before text
}
function makeSortable(table, id) {
  const ths = [...table.tHead.rows[0].cells];
  const tb = table.tBodies[0];
  const original = [...tb.rows];
  const keys = new Map(original.map(tr =>
    [tr, [...tr.cells].map(td => sortKey(td.dataset.sort ?? td.textContent))]));
  if (SORTS[id] && SORTS[id].col >= ths.length) delete SORTS[id];
  function apply() {
    const st = SORTS[id];
    ths.forEach((th, i) => {
      const dir = st && st.col === i ? st.dir : "";
      th.dataset.dir = dir;
      th.setAttribute("aria-sort", dir === "asc" ? "ascending" : dir === "desc" ? "descending" : "none");
    });
    let rows = original.slice();
    if (st) {
      const sign = st.dir === "asc" ? 1 : -1;
      rows.sort((a, b) => {
        const x = keys.get(a)[st.col], y = keys.get(b)[st.col];
        if (x === null || y === null) return (x === null) - (y === null);
        return sign * compareKeys(x, y);
      });
    }
    rows.forEach(r => tb.appendChild(r));
  }
  ths.forEach((th, i) => {
    if (UNSORTABLE.has(th.textContent.trim())) return;
    th.classList.add("sortable");
    th.title = "Sort by " + th.textContent;
    th.onclick = () => {
      const asc = ASC_FIRST.has(th.textContent.trim());
      const first = asc ? "asc" : "desc", second = asc ? "desc" : "asc";
      const st = SORTS[id];
      if (!st || st.col !== i) SORTS[id] = { col: i, dir: first };
      else if (st.dir === first) st.dir = second;
      else delete SORTS[id];
      apply();
    };
  });
  apply();
}

// --- navigation -----------------------------------------------------------
function switchView(name) {
  CURRENT = name;
  document.querySelectorAll("#tabbar button").forEach(b =>
    b.classList.toggle("active", b.dataset.view === name));
  RENDER[name]();
}
document.querySelectorAll("#tabbar button").forEach(b =>
  b.addEventListener("click", () => switchView(b.dataset.view)));
$("#refresh").addEventListener("click", async () => {
  $("#refresh").style.opacity = .4;
  try { await api("/api/refresh", { method: "POST" }); toast("Refreshed"); await loadState(); RENDER[CURRENT](); }
  catch (e) { toast(e.message, true); }
  $("#refresh").style.opacity = 1;
});

// --- state + top bar ------------------------------------------------------
async function loadState() {
  STATE = await api("/api/state");
  const today = STATE.today ? new Date(STATE.today + "T00:00:00") : new Date();
  $("#subtitle").textContent = today.toLocaleDateString("en-US",
    { weekday: "long", month: "long", day: "numeric" });
  const g = $("#greeting"); g.textContent = STATE.greeting || ""; g.hidden = !STATE.greeting;
  const m = $("#missed");
  if (STATE.missed && STATE.missed.length) {
    m.hidden = false;
    m.textContent = "⚠ Unlogged: " + STATE.missed.map(fmtDateISO).join(", ");
  } else m.hidden = true;
}

// --- HOME -----------------------------------------------------------------
function periodCard(key, title, p) {
  const c = el("div", "card");
  c.appendChild(el("div", "cap", title));
  const a = new Date(p.start + "T00:00:00"), b = new Date(p.end + "T00:00:00");
  const rng = a.toLocaleDateString("en-US", { month: "short", day: "numeric" }) + " – " +
              b.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  c.appendChild(el("div", "sub", rng));
  c.appendChild(el("div", "big", money(p.net)));
  c.appendChild(el("div", "sub", p.shifts
    ? `${p.shifts} shift${p.shifts !== 1 ? "s" : ""} · ${p.hours.toFixed(0)} hrs · ${money(p.per_hour)}/hr`
    : "No shifts logged yet"));
  if (p.progress) {
    const bar = el("div", "bar"); const fill = el("span");
    fill.style.width = Math.min(100, p.progress.pct * 100) + "%"; bar.appendChild(fill);
    c.appendChild(bar);
    c.appendChild(el("div", "sub", p.progress.left <= 0
      ? `✓ ${money(p.goal, false)} goal reached`
      : `${Math.round(p.progress.pct * 100)}% of ${money(p.goal, false)} · ${money(p.progress.left, false)} to go`));
  }
  return c;
}
function nextShiftCard(n) {
  const c = el("div", "card");
  c.appendChild(el("div", "cap", "Next shift"));
  if (!n) { c.appendChild(el("div", "sub", "Nothing scheduled, or no history yet.")); return c; }
  c.appendChild(el("div", "sub", fmtDateISO(n.date) + (n.clock ? " · " + n.clock : "")));
  c.appendChild(el("div", "big", "~" + money(n.mid, false)));
  c.appendChild(el("div", "sub", `usually ${money(n.lo, false)} – ${money(n.hi, false)}`));
  if (n.holiday) {
    const parts = [n.holiday.greeting, n.holiday.note].filter(Boolean).join(" · ");
    c.appendChild(el("div", "holiday", esc(parts)));
  }
  let detail = `From ${esc(n.basis)} (${n.samples} shifts)`;
  if (n.accuracy) detail += ` · usually off by ${money(n.accuracy.median_err, false)} · `
    + `${Math.round(n.accuracy.coverage * 10)} in 10 in range`;
  const d = el("div", "sub"); d.innerHTML = detail; d.style.marginTop = "8px"; c.appendChild(d);
  return c;
}
function forecastCard(f) {
  const c = el("div", "card");
  c.appendChild(el("div", "cap", "Month-end forecast"));
  if (!f) { c.appendChild(el("div", "sub", "Log a few shifts to see a forecast.")); return c; }
  const big = el("div", "big info", money(f.projected, false)); c.appendChild(big);
  c.appendChild(el("div", "sub", `Likely between ${money(f.low, false)} and ${money(f.high, false)}`));
  const lines = el("div"); lines.style.marginTop = "10px";
  if (f.source === "pace")
    lines.appendChild(el("div", "", `${money(f.so_far, false)} earned · ${f.scheduled} at your usual pace`));
  else {
    let s = `${money(f.so_far, false)} earned · ${f.scheduled} scheduled · ~${money(f.scheduled_value, false)}`;
    if (f.pending) s += ` · ${f.pending} worked, not logged`;
    lines.appendChild(el("div", "", esc(s)));
  }
  if (f.likely) lines.appendChild(el("div", "accent",
    `${f.likely} more likely on ${esc(f.likely_days)} · ~${money(f.likely_value, false)}`));
  else if (f.source !== "pace")
    lines.appendChild(el("div", "sub", "Scheduled shifts only — set your usual days in More"));
  if (f.goal_progress) {
    const gp = f.goal_progress;
    if (gp.left <= 0) lines.appendChild(el("div", "accent", `${money(f.goal, false)} goal reached`));
    else if (gp.extra_shifts === 0) lines.appendChild(el("div", "accent", `On track for your ${money(f.goal, false)} goal`));
    else lines.appendChild(el("div", "warning",
      `Pick up ~${gp.extra_shifts} more shift${gp.extra_shifts !== 1 ? "s" : ""} to hit ${money(f.goal, false)}`));
  }
  c.appendChild(lines);
  if (f.upcoming && f.upcoming.length)
    c.appendChild(el("div", "sub", "Next up · " + f.upcoming.map(fmtDateISO).join("  ")));
  return c;
}
function recentCard(rows) {
  const c = el("div", "card"); c.appendChild(el("div", "cap", "Recent shifts"));
  if (!rows.length) { c.appendChild(el("div", "sub", "No shifts logged yet.")); return c; }
  const box = el("div", "recent");
  rows.forEach(r => {
    const line = el("div", "line");
    line.appendChild(el("div", "", esc(r.date)));
    line.appendChild(el("div", "amt", money(r.net)));
    line.appendChild(el("div", "nt", esc(r.type || "") + (r.note ? " · " + esc(r.note) : "")));
    box.appendChild(line);
  });
  c.appendChild(box);
  const link = el("button", "link", "View all logs →");
  link.onclick = () => switchView("logs"); c.appendChild(link);
  return c;
}
async function renderHome() {
  views.innerHTML = "";
  if (!STATE) { try { await loadState(); } catch (e) { views.innerHTML = `<div class='center'>${esc(e.message)}</div>`; return; } }
  if (!STATE.ready) { views.innerHTML = `<div class='center'>${esc(STATE.error || "Loading the sheet…")}</div>`; return; }
  const v = el("div", "view active");
  const periods = el("div", "grid periods");
  periods.appendChild(periodCard("weekly", "This week", STATE.periods.weekly));
  periods.appendChild(periodCard("monthly", "This month", STATE.periods.monthly));
  periods.appendChild(periodCard("yearly", "This year", STATE.periods.yearly));
  v.appendChild(periods);
  const two = el("div", "grid two");
  const col = el("div");
  col.appendChild(nextShiftCard(STATE.next_shift));
  col.appendChild(forecastCard(STATE.forecast));
  two.appendChild(col);
  two.appendChild(recentCard(STATE.recent));
  v.appendChild(two);
  views.appendChild(v);
}

// --- ADD SHIFT ------------------------------------------------------------
const SHIFT_TYPES = ["Lunch", "Dinner", "Double", "Other"];
function todayISO() { return (STATE && STATE.today) || new Date().toISOString().slice(0, 10); }
function renderAdd(edit) {
  views.innerHTML = "";
  const v = el("div", "view active");
  const c = el("div", "card");
  c.innerHTML = `<div class="cap">${edit ? "Edit shift" : "Shift details"}</div>
    <label>Date</label><input type="date" id="f-date">
    <div class="field2">
      <div><label>Shift type</label><select id="f-type">${SHIFT_TYPES.map(t => `<option>${t}</option>`).join("")}</select></div>
      <div><label>Section</label><input id="f-section" placeholder="e.g. 14"></div>
    </div>
    <div class="field2">
      <div><label>Card tips</label><input id="f-card" type="number" inputmode="decimal" placeholder="0.00"></div>
      <div><label>Cash tips</label><input id="f-cash" type="number" inputmode="decimal" placeholder="0.00"></div>
    </div>
    <div class="field2">
      <div><label>Tip out</label><input id="f-tipout" type="number" inputmode="decimal" placeholder="0.00"></div>
      <div><label>Hours</label><input id="f-hours" type="number" inputmode="decimal" placeholder="0.00"></div>
    </div>
    <label>Notes</label><input id="f-notes" placeholder="optional">
    <div class="preview" id="f-prev"></div>
    <div class="err" id="f-err"></div>
    <button class="primary" id="f-save">${edit ? "Save changes" : "Save shift"}</button>`;
  v.appendChild(c);
  views.appendChild(v);

  const g = id => $("#f-" + id);
  const num = id => { const n = parseFloat(g(id).value); return isNaN(n) ? null : n; };
  function preview() {
    const card = num("card") || 0, cash = num("cash") || 0, out = num("tipout") || 0, hrs = num("hours") || 0;
    if (!(card || cash || out)) { g("prev").textContent = ""; return; }
    const net = card + cash - out;
    g("prev").textContent = `Take-home ${money(net)}` + (hrs > 0 ? `  ·  ${money(net / hrs)}/hr` : "");
  }
  ["card", "cash", "tipout", "hours"].forEach(id => g(id).addEventListener("input", preview));

  if (edit) {
    g("date").value = edit.date; g("type").value = edit.shiftType || "Dinner";
    g("section").value = edit.section || "";
    g("card").value = edit.card; g("cash").value = edit.cash;
    g("tipout").value = edit.tipOut || ""; g("hours").value = edit.hours;
    g("notes").value = edit.notes || ""; preview();
  } else {
    g("date").value = (STATE && STATE.missed && STATE.missed[0]) || todayISO();
  }

  g("save").onclick = async () => {
    const body = { date: g("date").value, card: num("card"), cash: num("cash"),
      hours: num("hours"), tipOut: num("tipout") || 0, shiftType: g("type").value,
      section: g("section").value.trim(), notes: g("notes").value.trim() };
    if (body.card === null || body.cash === null || body.hours === null) {
      g("err").textContent = "Fill in card, cash and hours."; return; }
    g("save").disabled = true; g("err").textContent = "";
    try {
      if (edit) await api("/api/shift/" + edit.index, { method: "PUT",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      else await api("/api/shift", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      toast("Saved ✓"); STATE = null; await loadState();
      switchView(edit ? "logs" : "home");
    } catch (e) { g("err").textContent = e.message; g("save").disabled = false; }
  };
}

// --- LOGS -----------------------------------------------------------------
const LOG_TABS = [["Tips", "tips"], ["Weekly", "weekly"], ["Monthly", "monthly"],
                  ["Yearly", "yearly"], ["Payday", "payday"]];
let logTab = "tips";
async function renderLogs() {
  views.innerHTML = "";
  const v = el("div", "view active");
  const tabs = el("div", "tabs");
  LOG_TABS.forEach(([label, key]) => {
    const b = el("button", key === logTab ? "active" : "", label);
    b.onclick = () => { logTab = key; renderLogs(); }; tabs.appendChild(b);
  });
  v.appendChild(tabs);
  const host = el("div", "tablewrap", "<div class='center'>Loading…</div>");
  v.appendChild(host); views.appendChild(v);
  let data;
  try { data = await api("/api/logs?tab=" + logTab); }
  catch (e) { host.innerHTML = `<div class='center'>${esc(e.message)}</div>`; return; }
  if (!data.rows.length) { host.innerHTML = "<div class='center'>Nothing here yet.</div>"; return; }
  const t = el("table");
  t.innerHTML = "<thead><tr>" + data.headers.map(h => `<th>${esc(h)}</th>`).join("") + "</tr></thead>";
  const tb = el("tbody");
  data.rows.forEach((row, i) => {
    const tr = el("tr");
    tr.innerHTML = row.map(c => `<td>${esc(c)}</td>`).join("");
    if (logTab === "tips" && data.indices) {
      tr.style.cursor = "pointer";
      tr.onclick = () => openEdit(row, data.indices[i]);
    }
    tb.appendChild(tr);
  });
  t.appendChild(tb); host.innerHTML = ""; host.appendChild(t);
  makeSortable(t, "logs:" + logTab);
}
// Tips row -> edit form. Columns: Date,Type,Hours,Card,Cash,Tip Out,Take-home,Section,Notes
function openEdit(row, index) {
  const parse = s => { const n = parseFloat((s || "").toString().replace(/[$,]/g, "")); return isNaN(n) ? "" : n; };
  switchView("add");
  const iso = (() => { const p = row[0].split("/"); return p.length === 3 ? `${p[2]}-${p[0].padStart(2,"0")}-${p[1].padStart(2,"0")}` : todayISO(); })();
  renderAdd({ index, date: iso, shiftType: row[1], hours: parse(row[2]), card: parse(row[3]),
    cash: parse(row[4]), tipOut: parse(row[5]), section: row[7], notes: row[8] });
  const del = el("button", "danger-btn", "Delete this shift");
  del.onclick = async () => {
    if (!confirm("Delete this shift? It also updates your totals.")) return;
    try { await api("/api/shift/" + index, { method: "DELETE" }); toast("Deleted ✓");
      STATE = null; await loadState(); switchView("logs"); }
    catch (e) { toast(e.message, true); }
  };
  $(".view .card").appendChild(del);
}

// --- INSIGHTS -------------------------------------------------------------
const RANGES = ["Last 30 days", "Last 90 days", "This year", "All time"];
let insRange = "Last 90 days";
function weekdayChart(data) {
  const W = 320, H = 150, pad = 24, n = 7, days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
  const byDay = {}; data.forEach(r => byDay[r.group] = r.avg);
  const full = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"];
  const vals = full.map(d => byDay[d] || 0);
  const max = Math.max(1, ...vals), bw = (W - pad * 2) / n * 0.62, gap = (W - pad * 2) / n;
  let bars = "", best = Math.max(...vals);
  vals.forEach((v, i) => {
    const h = (H - pad - 14) * (v / (max * 1.15)); const x = pad + i * gap + (gap - bw) / 2;
    const y = H - pad - h; const col = (v === best && v > 0) ? "#3ec291" : "#5b8ab8";
    bars += `<rect x="${x}" y="${y}" width="${bw}" height="${h}" rx="2" fill="${col}"/>`;
    if (v > 0) bars += `<text x="${x + bw/2}" y="${y-3}" fill="#eceef0" font-size="8" text-anchor="middle">$${Math.round(v)}</text>`;
    bars += `<text x="${x + bw/2}" y="${H-pad+11}" fill="#868d94" font-size="9" text-anchor="middle">${days[i]}</text>`;
  });
  return `<svg class="chart" viewBox="0 0 ${W} ${H}">${bars}</svg>`;
}
async function renderInsights() {
  views.innerHTML = "";
  const v = el("div", "view active");
  const sel = el("select"); sel.style.marginBottom = "12px";
  sel.innerHTML = RANGES.map(r => `<option${r === insRange ? " selected" : ""}>${r}</option>`).join("");
  sel.onchange = () => { insRange = sel.value; renderInsights(); };
  v.appendChild(sel);
  const host = el("div", "", "<div class='center'>Loading…</div>");
  v.appendChild(host); views.appendChild(v);
  let d;
  try { d = await api("/api/insights?range=" + encodeURIComponent(insRange)); }
  catch (e) { host.innerHTML = `<div class='center'>${esc(e.message)}</div>`; return; }
  host.innerHTML = "";
  const tiles = el("div", "tiles");
  [["Take-home", money(d.tiles.net)], ["Shifts", d.tiles.shifts],
   ["Avg/shift", money(d.tiles.per_shift)], ["Avg/hr", money(d.tiles.per_hour)]].forEach(([c, val]) => {
    const t = el("div", "t"); t.appendChild(el("div", "c", c)); t.appendChild(el("div", "v", val)); tiles.appendChild(t);
  });
  host.appendChild(tiles);
  const chart = el("div", "card");
  chart.appendChild(el("div", "cap", "Average take-home per shift"));
  chart.innerHTML += weekdayChart(d.weekday);
  host.appendChild(chart);
  host.appendChild(groupCard("By shift type", d.groups.Type, "Shift Type"));
  host.appendChild(groupCard("By section", d.groups.Section, "Section"));
  host.appendChild(rankCard("Best shifts", d.best));
  host.appendChild(rankCard("Slowest shifts", d.worst));
  if (d.untagged) host.appendChild(el("div", "sub", `${d.untagged} shift${d.untagged !== 1 ? "s" : ""} here have no type/section (logged before those existed) — they count everywhere except the two tables above.`));
}
function groupCard(title, rows, col) {
  const c = el("div", "card"); c.appendChild(el("div", "head", title));
  if (!rows.length) { c.appendChild(el("div", "sub", "No tagged shifts yet.")); return c; }
  const t = el("table");
  t.innerHTML = `<thead><tr><th>${col}</th><th>Shifts</th><th>Avg</th><th>Per hr</th></tr></thead>`;
  const tb = el("tbody");
  rows.forEach(r => tb.innerHTML += `<tr><td>${esc(r.group)}</td><td>${r.shifts}</td><td>${money(r.avg)}</td><td>${r.per_hour == null ? "—" : money(r.per_hour)}</td></tr>`);
  t.appendChild(tb); c.appendChild(t); makeSortable(t, "ins:" + title); return c;
}
function rankCard(title, rows) {
  const c = el("div", "card"); c.appendChild(el("div", "head", title));
  const t = el("table");
  t.innerHTML = `<thead><tr><th>Date</th><th>Type</th><th>Take-home</th><th>$/hr</th></tr></thead>`;
  const tb = el("tbody");
  rows.forEach(r => tb.innerHTML += `<tr><td data-sort="${esc(r.iso || "")}">${esc(r.date)}</td><td>${esc(r.type || "—")}</td><td>${money(r.net)}</td><td>${r.per_hour == null ? "" : money(r.per_hour)}</td></tr>`);
  t.appendChild(tb); c.appendChild(t); makeSortable(t, "ins:" + title); return c;
}

// --- MORE: payday + settings ---------------------------------------------
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
async function renderMore() {
  views.innerHTML = "";
  const v = el("div", "view active");
  let s; try { s = await api("/api/settings"); } catch (e) { s = { workdays: [] }; }

  // Settings
  const sc = el("div", "card");
  sc.innerHTML = `<div class="head">Goals & usual days</div>
    <div class="field2" style="margin-top:8px">
      <div><label>Weekly</label><input id="g-weekly" type="number" inputmode="decimal"></div>
      <div><label>Monthly</label><input id="g-monthly" type="number" inputmode="decimal"></div>
    </div>
    <label>Yearly</label><input id="g-yearly" type="number" inputmode="decimal">
    <label>Days you usually work</label><div class="days" id="g-days"></div>
    <div class="err" id="g-err"></div>
    <button class="primary" id="g-save">Save settings</button>`;
  v.appendChild(sc);

  // Payday
  const pc = el("div", "card");
  pc.innerHTML = `<div class="head">Add payday</div>
    <div class="field2" style="margin-top:8px">
      <div><label>Start</label><input id="p-start" type="date"></div>
      <div><label>End</label><input id="p-end" type="date"></div>
    </div>
    <div class="field2">
      <div><label>Gross pay</label><input id="p-gross" type="number" inputmode="decimal"></div>
      <div><label>Tax taken</label><input id="p-tax" type="number" inputmode="decimal"></div>
    </div>
    <div class="err" id="p-err"></div>
    <button class="primary" id="p-save">Save payday</button>`;
  v.appendChild(pc);
  views.appendChild(v);

  $("#g-weekly").value = s.weekly ?? ""; $("#g-monthly").value = s.monthly ?? "";
  $("#g-yearly").value = s.yearly ?? "";
  const daysBox = $("#g-days"); const chosen = new Set(s.workdays || []);
  DAYS.forEach((name, i) => {
    const b = el("button", chosen.has(i) ? "on" : "", name);
    b.onclick = () => { b.classList.toggle("on"); }; b.dataset.i = i; daysBox.appendChild(b);
  });
  $("#g-save").onclick = async () => {
    const f = id => { const n = parseFloat($("#g-" + id).value); return isNaN(n) || n <= 0 ? null : n; };
    const workdays = [...daysBox.querySelectorAll("button.on")].map(b => +b.dataset.i);
    try {
      await api("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ weekly: f("weekly"), monthly: f("monthly"), yearly: f("yearly"), workdays }) });
      toast("Settings saved ✓"); STATE = null; await loadState();
    } catch (e) { $("#g-err").textContent = e.message; }
  };
  $("#p-save").onclick = async () => {
    const gross = parseFloat($("#p-gross").value), tax = parseFloat($("#p-tax").value);
    if (isNaN(gross) || isNaN(tax)) { $("#p-err").textContent = "Enter gross and tax."; return; }
    try {
      await api("/api/payday", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start: $("#p-start").value, end: $("#p-end").value, gross, tax }) });
      toast("Payday saved ✓"); $("#p-gross").value = ""; $("#p-tax").value = "";
    } catch (e) { $("#p-err").textContent = e.message; }
  };
}

// --- missed-weekly-goal popup ----------------------------------------------
// Shown once per week, the first time the app opens after a Mon-Sun week
// that came in under the weekly goal. Add ?roast to the URL to preview it.
const ROASTS = [
  "ChatGPT, take this man's knees.",
  "Send a nuke to this man's house.",
  "Outback, revoke this man's Bloomin' Onion privileges immediately.",
  "Claude, delete this man's GitHub.",
  "Uninstall this man.",
  "Put this man in the walk-in freezer and lock the door.",
  "Strip this man of his apron and his dignity.",
  "Throw this man into the deep fryer with the Aussie Cheese Fries.",
  "Somebody get this man a second job and a therapist.",
  "Jarvis remove his balls.",
  "Chat, WTF are we doing?",
  "You should Malphite R off a bridge."
];
function maybeRoast(force) {
  const lw = STATE && STATE.last_week;
  if (!force && (!lw || !lw.missed)) return;
  const key = "roasted:" + (lw ? lw.start : "preview");
  if (!force) {
    try { if (localStorage.getItem(key)) return; localStorage.setItem(key, "1"); } catch (e) {}
  }
  const short = lw ? Math.max(0, lw.goal - lw.net) : 123.45;
  const line = ROASTS[Math.floor(Math.random() * ROASTS.length)];
  const when = lw ? `${fmtDateISO(lw.start)} – ${fmtDateISO(lw.end)}` : "preview";
  const made = lw ? `You made ${money(lw.net)} of ${money(lw.goal, false)} (${esc(when)}).` : "";
  const ov = el("div", "roast-overlay", `
    <div class="roast">
      <div class="roast-title">Missed Weekly Goal By <span class="danger">${money(short)}</span></div>
      <div class="roast-line">${esc(line)}</div>
      ${made ? `<div class="sub">${made}</div>` : ""}
      <button class="primary">I will do better (lie)</button>
    </div>`);
  const close = () => ov.remove();
  ov.querySelector("button").onclick = close;
  ov.addEventListener("click", e => { if (e.target === ov) close(); });
  document.body.appendChild(ov);
}

const RENDER = { home: renderHome, add: () => renderAdd(null), logs: renderLogs,
                 insights: renderInsights, more: renderMore };

// --- boot -----------------------------------------------------------------
(async () => {
  try { await loadState(); } catch (e) {}
  renderHome();
  maybeRoast(new URLSearchParams(location.search).has("roast"));
})();
