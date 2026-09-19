/* Mockup helper: FB1 design maths + SSD drawing, shared by all mockup pages.
   Mirrors what design_rules.py / ssd_layout.py will do in the real app. */

const ARCS = ["F", "FS", "AS", "A", "AP", "FP"];           // clockwise from fore
const ARC_ANGLE = { F: -90, FS: -30, AS: 30, A: 90, AP: 150, FP: 210 };

function rnd(x) { return Math.max(1, Math.floor(x + 0.5)); }   // FB1 p.10: .5 up, never 0

function systemMass(s, tmf) {
  switch (s.type) {
    case "beam": {
      if (s.cls === 1) return 1;
      const base = 2 ** (s.cls - 1);
      const n = s.arcs.length;
      if (s.cls === 2) return n > 3 ? 3 : 2;
      return base + (base / 4) * (n - 1);
    }
    case "torp": return 4 + (s.arcs.length - 1);
    case "needle": return 2;
    case "pds": case "fc": return 1;
    case "adfc": return 2;
    case "screen": return Math.max(s.level * 3, rnd(tmf * 0.05 * s.level));
    case "sml": return 3;
    case "mag": return s.salvos * 2;
    case "hangar": return 9;
    case "smp": return 1;
    default: return 0;
  }
}
function systemPoints(s, tmf) {
  const m = systemMass(s, tmf);
  switch (s.type) {
    case "beam": return s.cls === 1 ? 3 : m * 3;
    case "fc": return 4;
    case "adfc": return 8;
    case "needle": return 6;
    default: return m * 3;
  }
}
function designTotals(d) {
  const drive = rnd(d.tmf * 0.05 * d.thrust), ftl = d.ftl ? rnd(d.tmf * 0.1) : 0;
  const rows = [
    ["Basic hull", 0, d.tmf],
    ["Hull integrity", d.hull, d.hull * 2],
    ["Armour", d.armour, d.armour * 2],
    ["Main drive (thrust " + d.thrust + ")", drive, drive * 2],
    ["FTL drive", ftl, ftl * 2],
  ];
  d.systems.forEach(s => rows.push([label(s), systemMass(s, d.tmf), systemPoints(s, d.tmf)]));
  const mass = rows.reduce((a, r) => a + r[1], 0);
  const pts = rows.reduce((a, r) => a + r[2], 0);
  return { rows, mass, pts, drive, ftl };
}
function label(s) {
  const arcs = s.arcs ? " (" + (s.arcs.length === 6 ? "all" : s.arcs.join("/")) + ")" : "";
  return ({ beam: "Class-" + s.cls + " beam", torp: "Pulse torpedo", needle: "Needle beam",
            pds: "Point defence (PDS)", fc: "Fire control", adfc: "Area-defence FC",
            screen: "Screen level-" + s.level, sml: "Salvo missile launcher",
            mag: "SM magazine (" + s.salvos + ")", hangar: "Hangar bay (1 group)",
            smp: "Submunition pack" })[s.type] + arcs;
}
function trackRows(n) {                    // FB1 p.5: 4 rows, extras in the upper rows
  const b = Math.floor(n / 4), r = n % 4;
  return [0, 1, 2, 3].map(i => b + (i < r ? 1 : 0));
}
function crewFactors(tmf) { return Math.ceil(tmf / 20); }
function cfBoxes(hull, cf) {               // FB1 p.8 dot placement (1-based box numbers)
  const step = Math.ceil(hull / cf), out = [];
  for (let i = 1; i < cf; i++) out.push(i * step);
  out.push(hull);
  return out;
}

/* ---------- SSD drawing (monochrome, like the printed sheet) ---------- */
function arcRing(cx, cy, r, arcs) {
  let p = "";
  ARCS.forEach(a => {
    const on = arcs.includes(a);
    const a0 = (ARC_ANGLE[a] - 27) * Math.PI / 180, a1 = (ARC_ANGLE[a] + 27) * Math.PI / 180;
    const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
    const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
    p += `<path d="M${x0.toFixed(1)} ${y0.toFixed(1)} A${r} ${r} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}"
          stroke="#000" stroke-width="${on ? 3 : 0.6}" fill="none" opacity="${on ? 1 : 0.35}"/>`;
  });
  return p;
}
function icon(s, x, y, out) {
  let g = "";
  switch (s.type) {
    case "beam":
      g += `<circle cx="${x}" cy="${y}" r="9" fill="#fff" stroke="#000" stroke-width="1.4"/>
            <text x="${x}" y="${y + 3.6}" font-size="10" font-weight="700" text-anchor="middle">${s.cls}</text>`;
      g += arcRing(x, y, 12.5, s.arcs); break;
    case "torp":
      g += `<circle cx="${x}" cy="${y}" r="9" fill="#fff" stroke="#000" stroke-width="1.4"/>
            <path d="M${x - 4} ${y + 4} L${x} ${y - 5} L${x + 4} ${y + 4} Z" fill="#000"/>`;
      g += arcRing(x, y, 12.5, s.arcs); break;
    case "pds":
      g += `<circle cx="${x}" cy="${y}" r="6.5" fill="#fff" stroke="#000" stroke-width="1.2"/>
            <path d="M${x - 4.5} ${y - 4.5} L${x + 4.5} ${y + 4.5} M${x + 4.5} ${y - 4.5} L${x - 4.5} ${y + 4.5}" stroke="#000" stroke-width="1.1"/>`; break;
    case "fc":
      g += `<rect x="${x - 6}" y="${y - 6}" width="12" height="12" fill="#fff" stroke="#000" stroke-width="1.2"/>
            <circle cx="${x}" cy="${y}" r="2.4" fill="#000"/>`; break;
    case "adfc":
      g += `<rect x="${x - 6}" y="${y - 6}" width="12" height="12" fill="#fff" stroke="#000" stroke-width="1.2"/>
            <circle cx="${x}" cy="${y}" r="3.6" fill="none" stroke="#000"/><circle cx="${x}" cy="${y}" r="1.3" fill="#000"/>`; break;
    case "screen":
      for (let i = 0; i < s.level; i++)
        g += `<rect x="${x - 3 + i * 7 - (s.level - 1) * 3.5}" y="${y - 8}" width="6" height="16" rx="2" fill="#fff" stroke="#000" stroke-width="1.2"/>`;
      break;
    case "sml":
      g += `<rect x="${x - 7}" y="${y - 7}" width="14" height="14" fill="#fff" stroke="#000" stroke-width="1.2"/>
            <path d="M${x - 4} ${y + 4} L${x} ${y - 5} L${x + 4} ${y + 4} Z" fill="#000"/>`; break;
    case "mag":
      g += `<rect x="${x - 13}" y="${y - 6}" width="26" height="12" fill="#fff" stroke="#000" stroke-width="1.2"/>`;
      for (let i = 0; i < s.salvos; i++) {
        const sx = x - 8 + i * 8;
        g += `<path d="M${sx - 2.5} ${y + 3} L${sx} ${y - 3} L${sx + 2.5} ${y + 3} Z" fill="#fff" stroke="#000" stroke-width="0.8"/>`;
      }
      break;
    case "hangar":
      g += `<rect x="${x - 10}" y="${y - 7}" width="20" height="14" rx="3" fill="#fff" stroke="#000" stroke-width="1.2"/>
            <path d="M${x - 5} ${y + 3} L${x} ${y - 4} L${x + 5} ${y + 3} L${x} ${y + 1} Z" fill="#000"/>
            <text x="${x + 7}" y="${y + 5}" font-size="6" font-weight="700">${s.fighter || ""}</text>`; break;
    case "smp":
      g += `<rect x="${x - 6}" y="${y - 6}" width="12" height="12" fill="#fff" stroke="#000" stroke-width="1.2"/>
            <path d="M${x - 3} ${y} L${x + 3} ${y} M${x} ${y - 3} L${x} ${y + 3}" stroke="#000" stroke-width="1.4"/>`; break;
  }
  if (out) g += `<path d="M${x - 11} ${y - 11} L${x + 11} ${y + 11} M${x + 11} ${y - 11} L${x - 11} ${y + 11}" stroke="#c0392b" stroke-width="2.2" class="ko"/>`;
  return g;
}

/* opts: {damage:{hull,armour,out:[systemIndex]}, core:true} */
function ssdSVG(d, opts = {}) {
  const dmg = opts.damage || { hull: 0, armour: 0, out: [] };
  const W = 200;
  let g = "", y = 22;
  const weapons = [], defences = [];
  d.systems.forEach((s, i) => (["beam", "torp", "needle", "sml", "mag", "smp", "hangar"].includes(s.type) ? weapons : defences).push([s, i]));
  weapons.sort((a, b) => (b[0].cls || 0) - (a[0].cls || 0));

  // weapons: biggest first, rows of 3, centred
  for (let r = 0; r < weapons.length; r += 3) {
    const row = weapons.slice(r, r + 3), gap = 56, x0 = W / 2 - (row.length - 1) * gap / 2;
    row.forEach(([s, i], k) => g += icon(s, x0 + k * gap, y, dmg.out.includes(i)));
    y += 34;
  }
  // defences: rows of 6
  for (let r = 0; r < defences.length; r += 6) {
    const row = defences.slice(r, r + 6), gap = 26, x0 = W / 2 - (row.length - 1) * gap / 2;
    row.forEach(([s, i], k) => g += icon(s, x0 + k * gap, y, dmg.out.includes(i)));
    y += 26;
  }
  y += 2;
  // armour + damage track
  const rows = trackRows(d.hull), cols = Math.max(rows[0], d.armour ? Math.min(d.armour, 12) : 0);
  const bs = Math.min(11, 150 / Math.max(cols, 1)), tx = W / 2 - (cols * bs) / 2;
  if (d.armour) {
    const ar = Math.ceil(d.armour / 12);
    for (let a = 0; a < d.armour; a++) {
      const cx = tx + (a % 12) * bs + bs / 2, cy = y + Math.floor(a / 12) * bs + bs / 2;
      g += `<circle cx="${cx}" cy="${cy}" r="${bs / 2 - 0.8}" fill="#fff" stroke="#000" stroke-width="0.9"/>`;
      if (a < dmg.armour) g += `<path d="M${cx - bs / 2 + 1.5} ${cy + bs / 2 - 1.5} L${cx + bs / 2 - 1.5} ${cy - bs / 2 + 1.5}" stroke="#c0392b" stroke-width="1.6" class="ko"/>`;
    }
    y += ar * bs + 2;
  }
  const cf = cfBoxes(d.hull, crewFactors(d.tmf));
  let n = 0;
  rows.forEach((len, ri) => {
    for (let c = 0; c < len; c++) {
      n++;
      const bx = tx + c * bs, by = y + ri * bs;
      g += `<rect x="${bx}" y="${by}" width="${bs}" height="${bs}" fill="#fff" stroke="#000" stroke-width="0.9"/>`;
      if (cf.includes(n)) g += `<path d="${star(bx + bs / 2, by + bs / 2, bs * 0.32)}" fill="#000"/>`;
      if (n <= dmg.hull) g += `<path d="M${bx + 1.5} ${by + bs - 1.5} L${bx + bs - 1.5} ${by + 1.5}" stroke="#c0392b" stroke-width="1.6" class="ko"/>`;
    }
  });
  y += 4 * bs + 10;
  // FTL, drive, core box
  if (d.ftl) g += `<rect x="18" y="${y}" width="20" height="16" fill="#fff" stroke="#000" stroke-width="1.2"/>
        <path d="M21 ${y + 8} C25 ${y + 1}, 27 ${y + 1}, 28 ${y + 8} S31 ${y + 15}, 35 ${y + 8}" stroke="#000" fill="none" stroke-width="1.2"/>`;
  g += `<path d="M46 ${y + 16} L46 ${y + 5} L57 ${y - 1} L68 ${y + 5} L68 ${y + 16} Z" fill="#fff" stroke="#000" stroke-width="1.3"/>
        <text x="57" y="${y + 13.5}" font-size="10" font-weight="700" text-anchor="middle">${d.thrust}</text>`;
  if (opts.core !== false) {
    g += `<rect x="118" y="${y - 2}" width="66" height="20" rx="5" fill="#fff" stroke="#000" stroke-width="1.1"/>`;
    ["B", "L", "P"].forEach((t, k) => g += `<rect x="${123 + k * 20}" y="${y + 1}" width="15" height="14" fill="#000"/>
        <text x="${130.5 + k * 20}" y="${y + 11.5}" font-size="8" font-weight="700" fill="#fff" text-anchor="middle">${t}</text>`);
  }
  y += 26;
  return `<svg viewBox="0 0 ${W} ${y}" xmlns="http://www.w3.org/2000/svg" font-family="Arial, sans-serif" class="ssd">${g}</svg>`;
}
function star(cx, cy, r) {
  let p = "";
  for (let i = 0; i < 10; i++) {
    const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * 0.45 : r;
    p += (i ? "L" : "M") + (cx + rr * Math.cos(a)).toFixed(2) + " " + (cy + rr * Math.sin(a)).toFixed(2);
  }
  return p + "Z";
}

/* ---------- demo data: two FB1 classes (NPV checks) + two custom classes ---------- */
const DESIGNS = {
  vandenburg: { name: "Vandenburg", type: "Heavy Cruiser", code: "CH", tmf: 80, hull: 24, armour: 5, thrust: 6, ftl: true,
    source: "FB1 p.16", npvBook: 261,
    systems: [{ type: "beam", cls: 3, arcs: ["FP", "F", "FS"] }, { type: "beam", cls: 2, arcs: ["F", "FP", "AP"] },
      { type: "beam", cls: 2, arcs: ["F", "FS", "AS"] }, { type: "beam", cls: 1, arcs: ARCS },
      { type: "pds" }, { type: "pds" }, { type: "fc" }, { type: "fc" }, { type: "screen", level: 1 }] },
  furious: { name: "Furious", type: "Escort Cruiser", code: "CE", tmf: 64, hull: 19, armour: 3, thrust: 4, ftl: true,
    source: "FB1 p.16", npvBook: 219,
    systems: [{ type: "beam", cls: 3, arcs: ["F"] }, { type: "beam", cls: 2, arcs: ["F", "FP", "AP"] },
      { type: "beam", cls: 2, arcs: ["F", "FS", "AS"] }, { type: "beam", cls: 1, arcs: ARCS },
      { type: "torp", arcs: ["F"] }, { type: "pds" }, { type: "pds" }, { type: "pds" },
      { type: "fc" }, { type: "fc" }, { type: "adfc" }, { type: "screen", level: 1 }] },
  halberd: { name: "Halberd", type: "Destroyer", code: "DD", tmf: 30, hull: 9, armour: 1, thrust: 6, ftl: true,
    source: "custom",
    systems: [{ type: "beam", cls: 2, arcs: ["FP", "F", "FS"] }, { type: "beam", cls: 2, arcs: ["FP", "F", "FS"] },
      { type: "beam", cls: 1, arcs: ARCS }, { type: "beam", cls: 1, arcs: ARCS }, { type: "pds" }, { type: "fc" }] },
  sentinel: { name: "Sentinel", type: "Frigate", code: "FF", tmf: 20, hull: 5, armour: 1, thrust: 6, ftl: true,
    source: "custom",
    systems: [{ type: "beam", cls: 2, arcs: ["FP", "F", "FS"] }, { type: "beam", cls: 1, arcs: ARCS },
      { type: "pds" }, { type: "pds" }, { type: "fc" }] },
};

const FLEET = {
  name: "7th Cruiser Squadron", faction: "NAC", admiral: "R.Adm. A. Brigstone", limit: 1100,
  ships: [
    { id: "CH-1", name: "RNS Lancaster", d: "vandenburg", status: "Ready" },
    { id: "CE-1", name: "RNS Nashville", d: "furious", status: "Damaged",
      damage: { hull: 6, armour: 3, out: [5] } },
    { id: "CE-2", name: "RNS Tripoli", d: "furious", status: "In repair",
      damage: { hull: 11, armour: 3, out: [0, 9] } },
    { id: "DD-1", name: "RNS Kestrel", d: "halberd", status: "Ready" },
    { id: "DD-2", name: "RNS Merlin", d: "halberd", status: "Ready" },
    { id: "FF-1", name: "RNS Picket", d: "sentinel", status: "Ready" },
    { id: "FF-2", name: "RNS Vigil", d: "sentinel", status: "Lost" },
  ],
};
function fleetPoints(f) {
  return f.ships.filter(s => s.status !== "Lost").reduce((a, s) => a + designTotals(DESIGNS[s.d]).pts, 0);
}
