// EchoForge skins: a skin is plain data (colors, font, corners and an optional wallpaper picture), never code.
// Used by the renderer (window.EF_SKINS) and by the tests (require).
(function (root) {
  'use strict';
  const HEX = /^#[0-9a-f]{6}$/i;
  const CORNERS = ['cut', 'round', 'square'];
  const BORDER_STYLES = { solid: 'Solid', dashed: 'Dashed', dotted: 'Dotted', double: 'Double', none: 'None' };
  // Fonts that come with Windows, so every skin looks the same on any PC. [name, CSS stack]
  const FONT_LIST = {
    forge: ['Bahnschrift (EchoForge)', "'Bahnschrift', 'Segoe UI Variable Display', 'Segoe UI', sans-serif"],
    segoe: ['Segoe UI', "'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif"],
    clean: ['Segoe UI Display', "'Segoe UI Variable Display', 'Segoe UI', sans-serif"],
    bold: ['Arial Black', "'Arial Black', 'Bahnschrift', sans-serif"],
    arial: ['Arial', "Arial, 'Segoe UI', sans-serif"],
    verdana: ['Verdana', "Verdana, 'Segoe UI', sans-serif"],
    tahoma: ['Tahoma', "Tahoma, 'Segoe UI', sans-serif"],
    trebuchet: ['Trebuchet MS', "'Trebuchet MS', 'Segoe UI', sans-serif"],
    franklin: ['Franklin Gothic', "'Franklin Gothic Medium', 'Arial Narrow', sans-serif"],
    candara: ['Candara', "Candara, 'Segoe UI', sans-serif"],
    corbel: ['Corbel', "Corbel, 'Segoe UI', sans-serif"],
    impact: ['Impact', "Impact, 'Arial Black', sans-serif"],
    georgia: ['Georgia', "Georgia, 'Times New Roman', serif"],
    palatino: ['Palatino', "'Palatino Linotype', 'Book Antiqua', Georgia, serif"],
    constantia: ['Constantia', "Constantia, Georgia, serif"],
    times: ['Times New Roman', "'Times New Roman', Times, serif"],
    retro: ['Consolas', "Consolas, 'Cascadia Mono', monospace"],
    cascadia: ['Cascadia Code', "'Cascadia Code', 'Cascadia Mono', Consolas, monospace"],
    lucida: ['Lucida Console', "'Lucida Console', Consolas, monospace"],
    courier: ['Courier New', "'Courier New', Courier, monospace"],
    comic: ['Comic Sans', "'Comic Sans MS', 'Segoe Print', cursive"],
    print: ['Segoe Print', "'Segoe Print', 'Comic Sans MS', cursive"],
    inkfree: ['Ink Free', "'Ink Free', 'Segoe Print', cursive"],
    gabriola: ['Gabriola', "Gabriola, Georgia, serif"]
  };
  const FONTS = Object.fromEntries(Object.entries(FONT_LIST).map(([k, v]) => [k, v[1]]));
  const FONT_NAMES = Object.fromEntries(Object.entries(FONT_LIST).map(([k, v]) => [k, v[0]]));
  const CORNER_NAMES = { cut: 'Angled', round: 'Rounded', square: 'Square' };
  // Any other font installed on the PC, by name: letters, digits, spaces and dashes only.
  const FONT_NAME = /^[\w][\w .-]{0,47}$/;
  const fontStack = (key, custom, fallback) => (custom && FONT_NAME.test(custom) ? `'${custom}', ` : '') + (FONTS[key] || FONTS[fallback]);

  // 'forge' is EchoForge's own look: it uses the Accent and Background settings instead of fixed colors.
  const PRESETS = [
    { id: 'forge', name: 'EchoForge', kind: 'preset', a1: '#ffd27a', a2: '#ff6a1f', a3: '#e5145f', bg: '#0b0c10', bg2: '#101117', corners: 'cut', font: 'forge' },
    { id: 'arcade', name: 'Arcade Night', kind: 'preset', a1: '#9ffcff', a2: '#ff3fb4', a3: '#7a3cff', bg: '#0c0718', bg2: '#140b26', corners: 'cut', font: 'bold' },
    { id: 'handheld', name: 'Handheld', kind: 'preset', a1: '#e8ffb0', a2: '#9bd34a', a3: '#3f7f2a', bg: '#0d130b', bg2: '#121a10', corners: 'square', font: 'retro' },
    { id: 'midnight', name: 'Midnight', kind: 'preset', a1: '#cfe6ff', a2: '#4d9dff', a3: '#2a4bff', bg: '#070b16', bg2: '#0c1222', corners: 'round', font: 'clean' },
    { id: 'crimson', name: 'Crimson', kind: 'preset', a1: '#ffc2a8', a2: '#ff3b3b', a3: '#a3122e', bg: '#100708', bg2: '#170b0d', corners: 'cut', font: 'forge' },
    { id: 'carbon', name: 'Carbon', kind: 'preset', a1: '#ffffff', a2: '#c8ccd4', a3: '#6c7380', bg: '#0a0a0b', bg2: '#121214', corners: 'square', font: 'clean' },
    { id: 'ocean', name: 'Ocean', kind: 'preset', a1: '#c9fff2', a2: '#2fd4c4', a3: '#1f7ae0', bg: '#051214', bg2: '#0a1a1d', corners: 'round', font: 'clean' },
    { id: 'sunset', name: 'Sunset', kind: 'preset', a1: '#ffe29a', a2: '#ff8a3d', a3: '#d6246e', bg: '#120a10', bg2: '#1a0f17', corners: 'round', font: 'bold' },
    { id: 'paper', name: 'Paper', kind: 'preset', light: true, a1: '#ffb46b', a2: '#e0611a', a3: '#b3123f', bg: '#f1ece6', bg2: '#e7e0d8', corners: 'round', font: 'clean' }
  ];

  // ---- color helpers ----
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  function hexToRgb(h) { const n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
  const rgbToHex = (r, g, b) => '#' + [r, g, b].map(v => clamp(Math.round(v), 0, 255).toString(16).padStart(2, '0')).join('');
  function rgbToHsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
    if (mx === mn) return [0, 0, l];
    const d = mx - mn, s = l > .5 ? d / (2 - mx - mn) : d / (mx + mn);
    const h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return [h * 60, s, l];
  }
  function hslToHex(h, s, l) {
    h = ((h % 360) + 360) % 360; s = clamp(s, 0, 1); l = clamp(l, 0, 1);
    const k = n => (n + h / 30) % 12, a = s * Math.min(l, 1 - l);
    const f = n => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
    return rgbToHex(f(0) * 255, f(8) * 255, f(4) * 255);
  }
  const hueDist = (a, b) => { const d = Math.abs(a - b) % 360; return d > 180 ? 360 - d : d; };

  // Picks an accent ramp and a background from an image's pixels (RGBA, e.g. a small canvas copy of a cover).
  // The strongest colorful hue becomes the main accent, the next distinct hue the second; the image's overall hue
  // tints a dark background. A grey picture gives a silver ramp.
  function palette(px) {
    const buckets = Array.from({ length: 24 }, () => ({ w: 0, r: 0, g: 0, b: 0 }));
    const all = Array.from({ length: 24 }, () => 0);
    for (let i = 0; i + 3 < px.length; i += 4) {
      if (px[i + 3] < 128) continue;
      const r = px[i], g = px[i + 1], b = px[i + 2], [h, s, l] = rgbToHsl(r, g, b), k = Math.floor(h / 15) % 24;
      if (s > .15 && l > .08 && l < .92) all[k] += s;
      if (s < .3 || l < .18 || l > .88) continue;
      const w = s * (1 - Math.abs(l - .55));
      const bk = buckets[k]; bk.w += w; bk.r += r * w; bk.g += g * w; bk.b += b * w;
    }
    const ranked = buckets.map((bk, k) => ({ ...bk, k })).filter(bk => bk.w > 0).sort((a, b) => b.w - a.w);
    const total = ranked.reduce((n, bk) => n + bk.w, 0);
    if (!ranked.length || total < 1) return { a1: '#f2f2f6', a2: '#c4c6ce', a3: '#6e7280', bg: '#0b0b0d', bg2: '#121215' };
    const hueOf = bk => rgbToHsl(bk.r / bk.w, bk.g / bk.w, bk.b / bk.w)[0];
    const h1 = hueOf(ranked[0]);
    const second = ranked.slice(1).find(bk => hueDist(hueOf(bk), h1) >= 35 && bk.w > total * .06);
    const h3 = second ? hueOf(second) : h1 - 28;
    const base = all.indexOf(Math.max(...all)) * 15 + 7.5;
    return {
      a1: hslToHex(h1 + 8, .95, .8),
      a2: hslToHex(h1, .85, .57),
      a3: hslToHex(h3, .8, .5),
      bg: hslToHex(base, .3, .055),
      bg2: hslToHex(base, .28, .085)
    };
  }

  // A random skin whose colors go together (analogous, complementary or triadic), from a seed 0..1.
  function generate(seed = Math.random()) {
    const rnd = (() => { let x = Math.floor(seed * 2147483646) + 1; return () => (x = x * 16807 % 2147483647) / 2147483647; })();
    const h = rnd() * 360, harmony = [28, 180, 120, -40][Math.floor(rnd() * 4)];
    return {
      id: 'gen-' + Math.floor(seed * 1e9).toString(36), name: 'Generated', kind: 'generated',
      a1: hslToHex(h + 18, 1, .82), a2: hslToHex(h, .88, .58), a3: hslToHex(h + harmony, .8, .5),
      bg: hslToHex(h, .3, .055), bg2: hslToHex(h, .28, .085),
      corners: CORNERS[Math.floor(rnd() * 3)], font: Object.keys(FONTS)[Math.floor(rnd() * 4)]
    };
  }

  // Cleans a skin from a file or settings: known fields only, valid colors, short name. Returns null if unusable.
  function validate(o) {
    if (!o || typeof o !== 'object') return null;
    for (const k of ['a1', 'a2', 'a3', 'bg', 'bg2']) if (!HEX.test(o[k] || '')) return null;
    const sk = {
      id: /^[\w-]{1,40}$/.test(o.id || '') ? o.id : 'skin-' + Date.now().toString(36),
      name: String(o.name || 'My skin').replace(/[<>]/g, '').trim().slice(0, 40) || 'My skin',
      kind: ['cover', 'generated', 'custom', 'imported'].includes(o.kind) ? o.kind : 'custom',
      a1: o.a1.toLowerCase(), a2: o.a2.toLowerCase(), a3: o.a3.toLowerCase(), bg: o.bg.toLowerCase(), bg2: o.bg2.toLowerCase(),
      light: !!o.light,
      corners: CORNERS.includes(o.corners) ? o.corners : 'cut',
      font: FONTS[o.font] ? o.font : 'forge',
      bodyFont: FONTS[o.bodyFont] ? o.bodyFont : 'segoe',
      cornerSize: clamp(Math.round(o.cornerSize ?? 14), 0, 30),
      border: clamp(Math.round(o.border ?? 1), 0, 4),
      borderStyle: BORDER_STYLES[o.borderStyle] ? o.borderStyle : 'solid',
      panelAlpha: clamp(Math.round(o.panelAlpha ?? 74), 30, 100),
      wallStrength: clamp(Math.round(o.wallStrength ?? 35), 0, 90)
    };
    for (const k of ['text', 'muted', 'line']) if (HEX.test(o[k] || '')) sk[k] = o[k].toLowerCase();
    for (const k of ['fontCustom', 'bodyCustom']) if (typeof o[k] === 'string' && FONT_NAME.test(o[k].trim())) sk[k] = o[k].trim();
    if (typeof o.wall === 'string' && o.wall.length < 500) sk.wall = o.wall;
    if (typeof o.gameId === 'string' && o.gameId.length < 60) sk.gameId = o.gameId;
    return sk;
  }
  // A picture inside a shared skin file: only plain JPEG/PNG/WebP data, at most 6 MB.
  const validWallData = d => typeof d === 'string' && d.length < 8.2e6 && /^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(d);

  // CSS custom properties for a skin. The panels are see-through versions of the second background color.
  // Text, soft text and border colors are optional: without them the light or dark defaults are used.
  function cssVars(sk) {
    const [r, g, b] = hexToRgb(sk.bg2), lift = sk.light ? -8 : 10, size = sk.cornerSize ?? 14;
    const v = {
      '--a1': sk.a1, '--a2': sk.a2, '--a3': sk.a3, '--bg': sk.bg, '--bg2': sk.bg2,
      '--panel': `rgba(${clamp(r + lift, 0, 255)}, ${clamp(g + lift, 0, 255)}, ${clamp(b + lift, 0, 255)}, ${(sk.panelAlpha ?? (sk.light ? 80 : 74)) / 100})`,
      '--panel-solid': rgbToHex(r + lift, g + lift, b + lift),
      '--display': fontStack(sk.font, sk.fontCustom, 'forge'),
      '--font': fontStack(sk.bodyFont || 'segoe', sk.bodyCustom, 'segoe'),
      '--cut': sk.corners === 'cut' ? `${size}px` : '0px',
      '--rad': `${sk.corners === 'square' ? Math.min(size, 3) : size}px`,
      '--bw': `${sk.border ?? 1}px`,
      '--bstyle': sk.borderStyle || 'solid'
    };
    if (sk.text) v['--text'] = sk.text;
    if (sk.muted) { v['--muted'] = sk.muted; const [mr, mg, mb] = hexToRgb(sk.muted); v['--faint'] = `rgba(${mr}, ${mg}, ${mb}, .6)`; }
    if (sk.line) { const [lr, lg, lb] = hexToRgb(sk.line); v['--line'] = `rgba(${lr}, ${lg}, ${lb}, .22)`; v['--line2'] = `rgba(${lr}, ${lg}, ${lb}, .4)`; }
    return v;
  }

  const find = (id, mine = []) => PRESETS.find(p => p.id === id) || (mine || []).find(p => p.id === id) || null;

  const api = { PRESETS, FONTS, FONT_NAMES, CORNER_NAMES, BORDER_STYLES, FONT_NAME, palette, generate, validate, validWallData, cssVars, find, hexToRgb, rgbToHsl, hslToHex };
  if (typeof module === 'object' && module.exports) module.exports = api; else root.EF_SKINS = api;
})(typeof window !== 'undefined' ? window : globalThis);
