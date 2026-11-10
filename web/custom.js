/* EchoForge Retro Gaming: skins, Home dashboards, Settings, game synopses and updates.
   Loaded before the main script; everything here runs only when the main script calls it. */
"use strict";

/* ---------------- Skins (shared with EchoForge: web/skins.js) ---------------- */
const SK = window.EF_SKINS;
// Retro's own fonts on top of EchoForge's Windows fonts.
SK.FONTS.pixel = '"Press Start 2P", Consolas, monospace'; SK.FONT_NAMES.pixel = "Press Start 2P (arcade)";
SK.FONTS.inter = '"Inter", "Segoe UI", system-ui, sans-serif'; SK.FONT_NAMES.inter = "Inter";
const RETRO_PRESETS = [
  { id: "retro", name: "Retro Arcade", a1: "#ffd27a", a2: "#ff6a1f", a3: "#e5145f", bg: "#0b0c10", bg2: "#16171f", font: "pixel", bodyFont: "inter", cornerSize: 14, border: 2 },
  { id: "pocket", name: "Pocket Green", a1: "#e0f8d0", a2: "#88c070", a3: "#346856", bg: "#081820", bg2: "#0f2a2e", font: "pixel", bodyFont: "retro", corners: "square", cornerSize: 3, border: 2 },
  { id: "amber", name: "CRT Amber", a1: "#ffd98a", a2: "#ffb000", a3: "#ff6a00", bg: "#0d0800", bg2: "#1a1206", font: "retro", bodyFont: "retro", cornerSize: 6, border: 2 },
  { id: "neon", name: "Neon Night", a1: "#9ffcff", a2: "#ff3fb4", a3: "#7a3cff", bg: "#0c0718", bg2: "#170d2b", font: "pixel", bodyFont: "inter", cornerSize: 18, border: 2 },
  { id: "sixteen", name: "16-Bit Blue", a1: "#cfe6ff", a2: "#4d9dff", a3: "#2a4bff", bg: "#070b16", bg2: "#0e1526", font: "bold", bodyFont: "segoe", cornerSize: 12, border: 2 },
  { id: "crimson", name: "Crimson", a1: "#ffc2a8", a2: "#ff3b3b", a3: "#a3122e", bg: "#100708", bg2: "#1b0d10", font: "impact", bodyFont: "segoe", cornerSize: 10, border: 2 },
  { id: "carbon", name: "Carbon", a1: "#ffffff", a2: "#c8ccd4", a3: "#6c7380", bg: "#0a0a0b", bg2: "#151517", font: "clean", bodyFont: "segoe", corners: "square", cornerSize: 3, border: 1 },
  { id: "ocean", name: "Ocean", a1: "#c9fff2", a2: "#2fd4c4", a3: "#1f7ae0", bg: "#051214", bg2: "#0b1d21", font: "clean", bodyFont: "segoe", cornerSize: 20, border: 2 },
  { id: "sunset", name: "Sunset", a1: "#ffe29a", a2: "#ff8a3d", a3: "#d6246e", bg: "#120a10", bg2: "#1d111a", font: "bold", bodyFont: "inter", cornerSize: 16, border: 2 },
].map((p) => ({ kind: "preset", corners: "round", ...p }));

const hex2 = (n) => Math.round(Math.max(0, Math.min(255, n))).toString(16).padStart(2, "0");
function mixHex(a, b, t) { const A = SK.hexToRgb(a), B = SK.hexToRgb(b); return "#" + A.map((v, i) => hex2(v + (B[i] - v) * t)).join(""); }
function mySkins() { return (lib?.settings?.skins || []).map(SK.validate).filter(Boolean); }
function findSkin(id) { return RETRO_PRESETS.find((p) => p.id === id) || mySkins().find((p) => p.id === id) || RETRO_PRESETS[0]; }
let skinDraft = null;   // the skin being customized, shown live
function currentSkin() { return skinDraft || findSkin(homeLayout()?.skin || lib?.settings?.skin || "retro"); }
function fontStack(key, custom, fallback) { return (custom && SK.FONT_NAME.test(custom) ? `"${custom}", ` : "") + (SK.FONTS[key] || SK.FONTS[fallback]); }

function applySkin(sk = currentSkin()) {
  const r = document.documentElement.style, text = sk.text || "#f1ebe6", muted = sk.muted || "#9a918c";
  const v = {
    "--orange": sk.a2, "--ember": sk.a2, "--orange-hi": mixHex(sk.a2, sk.a1, 0.3), "--title": sk.a1, "--pink": sk.a3,
    "--bg": sk.bg, "--panel": mixHex(sk.bg2, "#ffffff", 0.02), "--panel-2": mixHex(sk.bg2, sk.a2, 0.12), "--navy": mixHex(sk.bg2, sk.a2, 0.1),
    "--line": sk.line || mixHex(sk.bg2, "#ffffff", 0.12), "--text": text, "--muted": muted, "--text2": mixHex(text, muted, 0.3),
    "--pixel": fontStack(sk.font, sk.fontCustom, "pixel"), "--ui": fontStack(sk.bodyFont || "inter", sk.bodyCustom, "inter"),
    "--rs": String(sk.corners === "square" ? 0.15 : (sk.cornerSize ?? 14) / 14), "--bw": `${sk.border ?? 2}px`, "--bstyle": sk.borderStyle || "solid",
  };
  for (const [k, val] of Object.entries(v)) r.setProperty(k, val);
  document.body.classList.toggle("noscan", lib?.settings?.scanlines === false);
  const wall = document.getElementById("bgWall");
  if (wall) {
    const id = sk.gameId && lib?.games?.some((g) => g.id === sk.gameId && g.art) ? sk.gameId : null;
    wall.style.backgroundImage = id ? `url("/art/${id}")` : "";
    wall.style.opacity = id ? String((sk.wallStrength ?? 35) / 100) : "0";
  }
}

// Colors from a game's cover, picked in the page from its small cover.
function coverPalette(id) {
  return new Promise((ok) => {
    const img = new Image();
    img.onload = () => {
      const c = document.createElement("canvas"), w = 64, h = Math.max(1, Math.round(64 * img.height / img.width));
      c.width = w; c.height = h; const x = c.getContext("2d"); x.drawImage(img, 0, 0, w, h);
      ok(SK.palette(x.getImageData(0, 0, w, h).data));
    };
    img.onerror = () => ok(null);
    img.src = `/thumb/${id}`;
  });
}
async function saveSettings(changes) {
  const r = await api("/api/settings", changes);
  if (r?.settings) lib.settings = r.settings;
  return r;
}
async function addSkin(sk, msg) {
  const clean = SK.validate(sk); if (!clean) return toast("That skin couldn't be used.");
  const list = mySkins().filter((x) => x.id !== clean.id);
  list.unshift(clean);
  // Keep up to 30: the oldest generated ones go first.
  while (list.length > 30) { const i = list.map((x) => x.kind).lastIndexOf("generated"); list.splice(i >= 0 ? i : list.length - 1, 1); }
  await saveSettings({ skins: list, skin: clean.id });
  skinDraft = null; applySkin(); render(false); if (msg) toast(msg);
}
async function skinFromCover(id) {
  const g = byId(id); if (!g?.art) return toast("This game has no cover yet.");
  const p = await coverPalette(id); if (!p) return toast("Couldn't read that cover.");
  await addSkin({ ...p, id: "cover-" + id, name: g.title.slice(0, 40), kind: "cover", gameId: id, font: "pixel", bodyFont: "inter", cornerSize: 14, border: 2, wallStrength: 30 },
    `Skin made from ${g.title}`);
}

/* ---------------- Home dashboards ---------------- */
const HOME_SECTIONS = { hero: "Jump back in", pinned: "Pinned", recent: "Recently played", favorites: "Favorites",
  collections: "Collections", picks: "Random picks", shelves: "A shelf per system", systems: "Systems" };
const HOME_PRESETS = [
  { id: "classic", name: "Classic", note: "Everything, the way Retro has always looked.", sections: ["hero", "pinned", "recent", "favorites", "collections", "systems"], size: "normal" },
  { id: "couch", name: "Couch", note: "Big covers for the TV.", sections: ["hero", "pinned", "recent", "favorites"], size: "big" },
  { id: "collector", name: "Collector", note: "A shelf for every system.", sections: ["pinned", "shelves"], size: "small" },
  { id: "minimal", name: "Minimal", note: "Your last game and your favorites.", sections: ["hero", "favorites"], size: "normal" },
  { id: "discover", name: "Discover", note: "Random picks from your library.", sections: ["picks", "collections", "systems"], size: "normal" },
].map((p) => ({ kind: "preset", ...p }));
function myLayouts() {
  return (lib?.settings?.layouts || []).filter((l) => l && /^[\w-]{1,40}$/.test(l.id || "") && Array.isArray(l.sections))
    .map((l) => ({ id: l.id, name: String(l.name || "My dashboard").slice(0, 40), kind: "custom",
      sections: l.sections.filter((s) => HOME_SECTIONS[s]), size: ["small", "normal", "big"].includes(l.size) ? l.size : "normal",
      skin: typeof l.skin === "string" ? l.skin : "" }));
}
let homeDraft = null;   // the dashboard being edited
function homeLayout() {
  const id = lib?.settings?.homeLayout || "classic";
  return HOME_PRESETS.find((p) => p.id === id) || myLayouts().find((p) => p.id === id) || HOME_PRESETS[0];
}
function pinnedGames() { return (lib.settings.pinned || []).map(byId).filter(Boolean); }
function picks(n = 12) {
  const day = Math.floor(Date.now() / 864e5);   // new picks every day
  return lib.games.filter((g) => g.art).map((g) => [([...g.id].reduce((a, c) => a * 31 + c.charCodeAt(0), day) >>> 0) % 1e9, g])
    .sort((a, b) => a[0] - b[0]).slice(0, n).map((x) => x[1]);
}
function homeHTML(layout = homeLayout()) {
  const rec = recent(), favs = lib.games.filter((g) => lib.favorites.includes(g.id));
  const row = (title, list, wide) => list.length ? `<div class="section-title">${esc(title)}</div><div class="row${wide ? " wide" : ""}">${list.map(wide ? seriesTile : tile).join("")}</div>` : "";
  let html = updateBanner();
  for (const s of layout.sections) {
    if (s === "hero") {
      if (rec.length) {
        const g = rec[0], h = lib.history[g.id];
        const bg = g.snap ? `<img class="hero-bg shot" src="/snap/${g.id}" alt="">` : g.art ? `<img class="hero-bg" src="/thumb/${g.id}" alt="">` : "";
        html += `<button class="hero" data-nav data-play="${g.id}" data-id="${g.id}">
          ${bg}${g.art ? `<img class="hero-art" src="/art/${g.id}" alt="">` : ""}
          <div><div class="eyebrow">JUMP BACK IN · ${SYS_SHORT[g.system]}</div><div class="title">${esc(g.title)}</div>
          <div class="info">Last played ${ago(h.last)} · ${h.plays} play${h.plays === 1 ? "" : "s"}</div></div>
          <span class="play">▶ PLAY</span></button>`;
      } else {
        html += `<div class="view-head"><h1>Welcome to EchoForge Retro Gaming</h1></div>
          <div class="empty">Pick a system below or press <b>RB</b> to browse. Games you play will show up here.</div>`;
      }
    }
    if (s === "pinned") html += row("Pinned", pinnedGames());
    if (s === "recent") html += row("Recently played", rec.slice(layout.sections.includes("hero") ? 1 : 0, 13));
    if (s === "favorites") html += row("Favorites", favs);
    if (s === "collections") html += row("Collections", seriesData().list.slice(0, 12), true);
    if (s === "picks") html += row("Random picks", picks());
    if (s === "shelves") for (const sys of lib.systems) html += row(sys.full, lib.games.filter((g) => g.system === sys.id).slice(0, 24));
    if (s === "systems") {
      html += `<div class="section-title">Systems</div><div class="systems">` + lib.systems.map((sys) => {
        const n = lib.games.filter((g) => g.system === sys.id).length;
        return `<button class="sys-card" data-nav data-view="${sys.id}" style="--c:${SYS_COLOR[sys.id]}"><div class="n">${SYS_SHORT[sys.id]}</div><div class="f">${esc(sys.full)}</div><div class="k">${n} games</div></button>`;
      }).join("") + `</div>`;
    }
  }
  if (!layout.sections.length) html += `<div class="empty">This dashboard has no sections. Turn some on in Settings → Home dashboard.</div>`;
  return `<div class="home size-${layout.size || "normal"}">${html}</div>`;
}

/* ---------------- Synopses ---------------- */
const aboutCache = {};   // game id -> answer from /api/about
let aboutOpen = false;
async function loadAbout(id, force) {
  if (NATIVE || (aboutCache[id] && !force) || aboutCache[id] === "busy") return;
  aboutCache[id] = "busy";
  try { aboutCache[id] = await api(`/api/about/${id}`); } catch (e) { delete aboutCache[id]; return; }
  if (view === "game:" + id) render(false);
}
function aboutHTML(g) {
  if (NATIVE || lib.settings.synopses === false && !aboutCache[g.id]?.own) return "";
  const a = aboutCache[g.id];
  if (!a || a === "busy") { loadAbout(g.id); return `<div class="gp-about muted">Looking up this game…</div>`; }
  const text = a.own || a.text || "";
  const facts = a.wrong ? [] : [a.year, ...(a.genre || []), (a.dev || []).join(", "), (a.pub || []).join(", ") !== (a.dev || []).join(", ") ? (a.pub || []).join(", ") : ""].filter(Boolean);
  const long = text.length > 320;
  return `${facts.length ? `<div class="gp-facts">${facts.map((f) => `<span>${esc(String(f).replace(/^./, (c) => c.toUpperCase()))}</span>`).join("")}</div>` : ""}
    ${text ? `<div class="gp-about${long && !aboutOpen ? " clamp" : ""}">${text.split(/\n{2,}/).map((p) => `<p>${esc(p)}</p>`).join("")}</div>` : ""}
    <div class="gp-aboutfoot">${long ? `<button class="linkbtn" data-nav data-act="aboutMore">${aboutOpen ? "Show less" : "Read more"}</button>` : ""}
      ${a.own ? "<span>Your own text</span>" : a.url ? `<a class="linkbtn" data-nav href="${esc(a.url)}" target="_blank" rel="noopener">From Wikipedia</a>` : ""}
      <button class="linkbtn" data-nav data-act="aboutEdit" data-arg="${g.id}">${text ? "Edit" : "Write a synopsis"}</button>
      <button class="linkbtn" data-nav data-act="aboutLookup" data-arg="${g.id}">Look it up again</button>
      ${a.text && !a.own ? `<button class="linkbtn" data-nav data-act="aboutWrong" data-arg="${g.id}">Wrong game</button>` : ""}</div>`;
}

/* ---------------- Updates ---------------- */
let upd = null;   // /api/update
async function refreshUpdate() {
  if (NATIVE) return;
  try { upd = await api("/api/update"); } catch (e) { return; }
  if (upd.busy) setTimeout(refreshUpdate, 700);
  render(false);
}
function updateBanner() {
  const l = upd?.last;
  if (!upd || !l?.ok || !l.update || !upd.installed) return "";
  return `<div class="upd"><div><b>EchoForge Retro Gaming ${esc(l.latest.version)} is ready</b><span>You have ${esc(upd.current)}. Your games, favorites and settings are kept.</span></div>
    <button class="chip-btn primary" data-nav data-act="updInstall" ${upd.busy ? "disabled" : ""}>${upd.busy ? `Downloading ${upd.pct}%` : "Update now"}</button>
    <a class="chip-btn" data-nav href="${esc(l.latest.page)}" target="_blank" rel="noopener">What's new</a></div>`;
}

/* ---------------- Settings ---------------- */
let setTab = "look", homeTab = "edit";
const tabBtn = (id, label, cur, act = "setTab") => `<button class="chip-btn${cur === id ? " primary" : ""}" data-nav data-act="${act}" data-arg="${id}">${label}</button>`;
const sw = (key, label, on) => `<button class="chip-btn ${on ? "on" : ""}" data-nav data-act="setToggle" data-arg="${key}"><span class="switch"></span>${label}</button>`;
function skinCard(sk) {
  const cur = (lib.settings.skin || "retro") === sk.id && !skinDraft;
  return `<button class="skin${cur ? " cur" : ""}" data-nav data-act="skinUse" data-arg="${esc(sk.id)}" style="--s1:${sk.a1};--s2:${sk.a2};--s3:${sk.a3};--sb:${sk.bg};--sb2:${sk.bg2}">
    <span class="sw">${sk.gameId ? `<img src="/thumb/${esc(sk.gameId)}" alt="">` : ""}<i></i><i></i><i></i></span><b>${esc(sk.name)}</b><small>${{ preset: "Built in", cover: "From a cover", generated: "Generated", custom: "Yours" }[sk.kind] || "Yours"}</small></button>`;
}
function skinEditor() {
  const d = skinDraft, color = (k, label) => `<label class="fld"><span>${label}</span><input type="color" data-nav data-skf="${k}" value="${esc(d[k] || ({ text: "#f1ebe6", muted: "#9a918c" }[k] || mixHex(d.bg2, "#ffffff", 0.12)))}"></label>`;
  const fonts = (k, custom) => `<select data-nav data-skf="${k}">${Object.keys(SK.FONTS).map((f) => `<option value="${f}" ${d[k] === f ? "selected" : ""}>${esc(SK.FONT_NAMES[f])}</option>`).join("")}</select>
      <input class="link-input" data-skf="${custom}" value="${esc(d[custom] || "")}" placeholder="Or any installed font, by name" data-nav>`;
  const range = (k, label, min, max, unit = "") => `<label class="fld wide"><span>${label} <b data-skv="${k}">${d[k] ?? ""}${unit}</b></span><input type="range" min="${min}" max="${max}" data-nav data-unit="${unit}" data-skf="${k}" value="${d[k] ?? 0}"></label>`;
  return `<div class="panelx"><div class="section-title" style="margin-top:0">Customize: ${esc(d.name)}</div>
    <label class="fld wide"><span>Name</span><input class="link-input" data-nav data-skf="name" value="${esc(d.name)}" maxlength="40"></label>
    <div class="flds">${color("a1", "Titles and highlights")}${color("a2", "Main accent")}${color("a3", "Second accent")}${color("bg", "Background")}${color("bg2", "Panels")}${color("text", "Text")}${color("muted", "Soft text")}${color("line", "Borders")}</div>
    <div class="flds"><label class="fld wide"><span>Heading font</span>${fonts("font", "fontCustom")}</label><label class="fld wide"><span>Body font</span>${fonts("bodyFont", "bodyCustom")}</label></div>
    <div class="flds"><label class="fld"><span>Corners</span><select data-nav data-skf="corners"><option value="round" ${d.corners !== "square" ? "selected" : ""}>Rounded</option><option value="square" ${d.corners === "square" ? "selected" : ""}>Square</option></select></label>
      ${range("cornerSize", "Roundness", 0, 30, "px")}${range("border", "Border thickness", 0, 4, "px")}
      <label class="fld"><span>Border style</span><select data-nav data-skf="borderStyle">${Object.entries(SK.BORDER_STYLES).map(([k, n]) => `<option value="${k}" ${(d.borderStyle || "solid") === k ? "selected" : ""}>${n}</option>`).join("")}</select></label>
      ${d.gameId ? range("wallStrength", "Cover wallpaper", 0, 90, "%") : ""}</div>
    <div class="toggles"><button class="chip-btn primary" data-nav data-act="skinSave">Save skin</button><button class="chip-btn" data-nav data-act="skinCancel">Cancel</button>
      ${d.kind !== "preset" && mySkins().some((x) => x.id === d.id) ? `<button class="chip-btn" data-nav data-act="skinDelete" data-arg="${esc(d.id)}">Delete this skin</button>` : ""}</div></div>`;
}
function lookTab() {
  const covers = lib.games.filter((g) => g.art);
  return `<p class="note">Changes show right away on this page. Pick a skin, make one from a game's cover, or press Customize to change every color, both fonts, the corners and the borders.</p>
    <div class="toggles"><button class="chip-btn" data-nav data-act="skinEdit">✎ Customize</button><button class="chip-btn" data-nav data-act="skinSurprise">🎲 Surprise me</button>
      <button class="chip-btn" data-nav data-act="skinPickCover">▦ From a game's cover</button>${sw("scanlines", "CRT scanlines", lib.settings.scanlines !== false)}</div>
    ${skinDraft ? skinEditor() : ""}
    <div class="section-title">Built in</div><div class="skins">${RETRO_PRESETS.map(skinCard).join("")}</div>
    ${mySkins().length ? `<div class="section-title">Yours</div><div class="skins">${mySkins().map(skinCard).join("")}</div>` : ""}
    ${coverPick ? `<div class="section-title">Choose a cover</div><div class="covers">${covers.slice(0, 400).map((g) => `<button class="covpick" data-nav data-act="skinCover" data-arg="${g.id}" title="${esc(g.title)}"><img src="/thumb/${g.id}" alt="" loading="lazy"></button>`).join("")}</div>` : ""}`;
}
let coverPick = false;
function homeTabHTML() {
  const cur = homeLayout(), d = homeDraft;
  const card = (l) => `<button class="skin lay${cur.id === l.id && !d ? " cur" : ""}" data-nav data-act="layUse" data-arg="${esc(l.id)}"><b>${esc(l.name)}</b><small>${esc(l.note || l.sections.map((s) => HOME_SECTIONS[s]).join(" · "))}</small></button>`;
  let editor = "";
  if (d) {
    const off = Object.keys(HOME_SECTIONS).filter((s) => !d.sections.includes(s));
    editor = `<div class="panelx"><div class="toggles">${tabBtn("edit", "Edit", homeTab, "homeTab")}${tabBtn("preview", "Preview", homeTab, "homeTab")}</div>
      ${homeTab === "preview" ? `<div class="hprev"><div class="hprev-in">${homeHTML(d).replace(/ data-nav| loading="lazy"/g, "")}</div></div>` : `
      <label class="fld wide"><span>Name</span><input class="link-input" data-nav data-layf="name" value="${esc(d.name)}" maxlength="40"></label>
      <div class="section-title">Sections, top to bottom</div>
      <div class="list">${d.sections.map((s, i) => `<div class="item"><div class="what"><b>${HOME_SECTIONS[s]}</b></div>
        <button class="chip-btn" data-nav data-act="layMove" data-arg="${i}:-1" ${i ? "" : "disabled"}>▲</button><button class="chip-btn" data-nav data-act="layMove" data-arg="${i}:1" ${i < d.sections.length - 1 ? "" : "disabled"}>▼</button>
        <button class="chip-btn" data-nav data-act="layOff" data-arg="${s}">Hide</button></div>`).join("")}
        ${off.map((s) => `<div class="item wait"><div class="what"><b>${HOME_SECTIONS[s]}</b><span>Hidden</span></div><button class="chip-btn" data-nav data-act="layOn" data-arg="${s}">Show</button></div>`).join("")}</div>
      <div class="flds"><label class="fld"><span>Cover size</span><select data-nav data-layf="size">${["small", "normal", "big"].map((z) => `<option value="${z}" ${d.size === z ? "selected" : ""}>${z[0].toUpperCase() + z.slice(1)}</option>`).join("")}</select></label>
        <label class="fld wide"><span>Skin with this dashboard</span><select data-nav data-layf="skin"><option value="">Keep my skin</option>${[...RETRO_PRESETS, ...mySkins()].map((s) => `<option value="${esc(s.id)}" ${d.skin === s.id ? "selected" : ""}>${esc(s.name)}</option>`).join("")}</select></label></div>`}
      <div class="toggles"><button class="chip-btn primary" data-nav data-act="laySave">Save and use</button><button class="chip-btn" data-nav data-act="layCancel">Cancel</button>
        ${myLayouts().some((x) => x.id === d.id) ? `<button class="chip-btn" data-nav data-act="layDelete" data-arg="${esc(d.id)}">Delete</button>` : ""}</div></div>`;
  }
  return `<p class="note">Choose how Home looks. Edit any dashboard to turn sections on or off, move them, change the cover size or pair a skin, and check it in Preview before you save. Pin to Home on a game's page adds it to the Pinned row.</p>
    <div class="toggles"><button class="chip-btn" data-nav data-act="layEdit">✎ Edit this dashboard</button></div>${editor}
    <div class="section-title">Ready-made</div><div class="skins">${HOME_PRESETS.map(card).join("")}</div>
    ${myLayouts().length ? `<div class="section-title">Yours</div><div class="skins">${myLayouts().map(card).join("")}</div>` : ""}`;
}
function gamesTab() {
  const s = lib.settings;
  return `<p class="note">How games start and what EchoForge Retro Gaming does in the background.</p>
    <div class="section-title" style="margin-top:0">During a game</div>
    <div class="toggles">${sw("padMenu", "Tap Select + Start: RetroArch menu", s.padMenu !== false)}${sw("padQuit", "Hold Select + Start: quit to Retro", s.padQuit !== false)}${sw("fullscreen", "Full-screen games", s.fullscreen !== false)}</div>
    <p class="note">Tap Select + Start (Back + Start on Xbox, Share + Options on PlayStation) for RetroArch's Quick Menu: save and load states, screenshots, controls and more.
      Hold them for 2 seconds to close the game; RetroArch saves first. On the keyboard, F1 opens the menu and Esc twice quits.</p>
    <div class="section-title">Your library</div>
    <div class="toggles">${sw("synopses", "Game synopses from Wikipedia", s.synopses !== false)}${sw("fetchArt", "Download missing box art", s.fetchArt !== false)}</div>
    <p class="note">Synopses show what a game is about, with its year, genre and developer, on the game's page. Only the game's name is sent to Wikipedia and Wikidata.</p>`;
}
function aboutTab() {
  const l = upd?.last;
  return `<p class="note">EchoForge Retro Gaming ${esc(upd?.current || lib.version)}. ${upd && !upd.installed ? "This copy runs from its source folder, so it's updated with git." : "Updates come from the project's GitHub releases and are checked against GitHub's checksum before they run."}</p>
    ${updateBanner()}
    <div class="toggles">${sw("autoUpdate", "Check for updates once a day", lib.settings.autoUpdate !== false)}
      <button class="chip-btn" data-nav data-act="updCheck">Check for updates</button></div>
    ${upd?.error ? `<p class="note" style="color:var(--nes)">${esc(upd.error)}</p>` : ""}
    ${l ? `<p class="note">${l.ok ? (l.update ? "" : `You're up to date.${l.latest ? ` The newest release on GitHub is ${esc(l.latest.version)}.` : ""}`) : esc(l.error)}</p>` : ""}`;
}
function viewSettings() {
  const body = { look: lookTab, home: homeTabHTML, games: gamesTab, about: aboutTab }[setTab] || lookTab;
  return `<div class="view-head"><h1>Settings</h1></div>
    <div class="toggles">${tabBtn("look", "Skin", setTab)}${tabBtn("home", "Home dashboard", setTab)}${tabBtn("games", "Games", setTab)}${tabBtn("about", "Updates", setTab)}</div>${body()}`;
}

/* ---------------- Actions ---------------- */
async function customAct(name, arg, el) {
  const S = lib.settings;
  switch (name) {
    case "setTab": setTab = arg; coverPick = false; if (arg === "about") refreshUpdate(); render(false); return true;
    case "homeTab": homeTab = arg; render(false); return true;
    case "setToggle": { await saveSettings({ [arg]: !(S[arg] !== false) }); applySkin(); render(false); return true; }
    case "skinUse": skinDraft = null; await saveSettings({ skin: arg }); applySkin(); render(false); toast(`Skin: ${findSkin(arg).name}`); return true;
    case "skinEdit": { const b = currentSkin(); skinDraft = { ...b, kind: b.kind === "preset" ? "custom" : b.kind, id: b.kind === "preset" ? "skin-" + Date.now().toString(36) : b.id, name: b.kind === "preset" ? `My ${b.name}` : b.name }; render(false); return true; }
    case "skinCancel": skinDraft = null; applySkin(); render(false); return true;
    case "skinSave": await addSkin(skinDraft, "Skin saved"); return true;
    case "skinDelete": { const list = mySkins().filter((x) => x.id !== arg); skinDraft = null; await saveSettings({ skins: list, skin: S.skin === arg ? "retro" : S.skin }); applySkin(); render(false); toast("Skin deleted"); return true; }
    case "skinSurprise": { const g = SK.generate(); await addSkin({ ...g, name: "Surprise " + (mySkins().filter((x) => x.kind === "generated").length + 1), font: ["pixel", "bold", "clean", "retro"][Math.floor(Math.random() * 4)], bodyFont: "inter", border: 2 }, "Here's a new look"); return true; }
    case "skinPickCover": coverPick = !coverPick; render(false); return true;
    case "skinCover": coverPick = false; await skinFromCover(arg); return true;
    case "makeSkin": await skinFromCover(arg); return true;
    case "layUse": homeDraft = null; await saveSettings({ homeLayout: arg }); applySkin(); render(false); toast(`Home: ${homeLayout().name}`); return true;
    case "layEdit": { const c = homeLayout(); homeDraft = { ...c, sections: [...c.sections], id: c.kind === "preset" ? "home-" + Date.now().toString(36) : c.id, name: c.kind === "preset" ? `My ${c.name}` : c.name, kind: "custom", skin: c.skin || "" }; homeTab = "edit"; render(false); return true; }
    case "layCancel": homeDraft = null; render(false); return true;
    case "layMove": { const [i, d] = arg.split(":").map(Number), s = homeDraft.sections; [s[i], s[i + d]] = [s[i + d], s[i]]; render(false); return true; }
    case "layOff": homeDraft.sections = homeDraft.sections.filter((s) => s !== arg); render(false); return true;
    case "layOn": homeDraft.sections.push(arg); render(false); return true;
    case "laySave": { const d = homeDraft, list = myLayouts().filter((x) => x.id !== d.id); list.unshift({ id: d.id, name: d.name, sections: d.sections, size: d.size, skin: d.skin }); homeDraft = null; await saveSettings({ layouts: list.slice(0, 20), homeLayout: d.id }); applySkin(); render(false); toast("Dashboard saved"); return true; }
    case "layDelete": { const list = myLayouts().filter((x) => x.id !== arg); homeDraft = null; await saveSettings({ layouts: list, homeLayout: S.homeLayout === arg ? "classic" : S.homeLayout }); applySkin(); render(false); return true; }
    case "pin": { const list = [...(S.pinned || [])], i = list.indexOf(arg); if (i >= 0) list.splice(i, 1); else list.unshift(arg); await saveSettings({ pinned: list }); render(false); toast(i >= 0 ? "Unpinned from Home" : "Pinned to Home"); return true; }
    case "aboutMore": aboutOpen = !aboutOpen; render(false); return true;
    case "aboutEdit": { const a = aboutCache[arg] || {}, text = prompt(`Synopsis for “${byId(arg).title}”.\nType your own, or clear it to go back to Wikipedia's.`, a.own || a.text || ""); if (text === null) return true;
      await api("/api/about", { id: arg, text: text === (a.text || "") ? "" : text }); await loadAbout(arg, true); toast(text.trim() && text !== a.text ? "Synopsis saved" : "Back to Wikipedia's synopsis"); return true; }
    case "aboutLookup": { toast("Looking it up on Wikipedia…"); const r = await api("/api/about", { id: arg, lookup: true }); await loadAbout(arg, true); toast(!r.ok ? r.error : r.found ? "Synopsis found" : "Wikipedia has no article that matches this game's name. You can write your own."); return true; }
    case "aboutWrong": await api("/api/about", { id: arg, wrong: true }); await loadAbout(arg, true); toast("Removed. Retro won't look this game up again unless you ask."); return true;
    case "updCheck": { toast("Checking for updates…"); await api("/api/update/check", {}); await refreshUpdate(); return true; }
    case "updInstall": { const r = await api("/api/update/install", {}); if (!r.ok) { toast(r.error); return true; } toast("Downloading the update…"); refreshUpdate(); return true; }
  }
  return false;
}
// Form fields in Settings: skin colors and fonts change live; dashboard fields change the draft.
function customInput(el) {
  if (el.dataset.skf && skinDraft) {
    const k = el.dataset.skf;
    skinDraft[k] = el.type === "range" ? +el.value : el.value;
    const lab = document.querySelector(`[data-skv="${k}"]`); if (lab) lab.textContent = el.value + (el.dataset.unit || "");
    applySkin(skinDraft);
    return true;
  }
  if (el.dataset.layf && homeDraft) { homeDraft[el.dataset.layf] = el.value; if (el.tagName === "SELECT") render(false); return true; }
  return false;
}
