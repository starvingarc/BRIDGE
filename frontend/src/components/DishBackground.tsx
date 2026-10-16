import { useEffect, useRef, type RefObject } from "react";

/**
 * The sign-in page as a culture dish seen from above: cells swim in the medium, faint strands join near neighbours,
 * and a cell dropped onto another keeps that bond. Cells bounce softly off the elements passed as obstacles
 * (the sign-in card, the logo). Purely decorative: it never shows data and stops when motion is unwanted.
 */
export type DishLook = "quiet" | "morning" | "opal";

type Cell = { x: number; y: number; vx: number; vy: number; fx: number; fy: number; r: number; heading: number; speed: number; phase: number; violet: boolean;
  look: { x: number; y: number }; rippled: number;
  /** Jelly body: radial offsets of the outline and their velocities, plus a nucleus hanging on a spring. */
  ring: Float32Array; ringV: Float32Array; pvx: number; pvy: number; kx: number; ky: number; kvx: number; kvy: number };
type Bond = { a: Cell; b: Cell; rest: number };
type Ripple = { x: number; y: number; age: number; rect: DOMRect };

const TEAL = ["#ffffff", "#edf6f5", "#bad3d2", "#e3eeee", "rgba(120,160,165,.45)", "#e7f0ef", "#8daeb0"];
const VIOLET = ["#ffffff", "#efeaff", "#c7b8ee", "#e6defc", "rgba(150,120,220,.45)", "#f2edff", "#9a86d6"];
// Like a goo ball: a dragged cell reaches for its two nearest neighbours within ATTACH and holds on to both on release.
const NEAR = 170, ATTACH = 120, HOLDS = 2, MAX_REST = 125;
// Cells live at low Reynolds number: velocity is their own swimming plus the forces on them, with no momentum.
const REPEL = 95, ADHERE = 7, FIELD = 54, WALL = 85;
// A bond made by hand is a stiff, lively spring, like a goo strand: it pulls straight on the cells' velocity, so a pair
// pulled apart springs back, overshoots and settles after a couple of wobbles; the medium is the only damping.
// Tuned so a pair pulled 120 px apart snaps back in ~0.12 s, overshoots about 13 px and rests by ~0.4 s.
const BOND_K = 150, BOND_DAMP = 8, MAX_SPEED = 700;
// The outline is a ring of damped springs: stiff enough to hold the shape, loose enough to wobble after a touch.
const RING = 16, RING_K = 170, RING_D = 7, DENT = 2.2;
const DIRS = Array.from({ length: RING }, (_, i) => [Math.cos(i / RING * 6.283), Math.sin(i / RING * 6.283)] as const);

function dark() {
  const theme = document.documentElement.dataset.theme;
  return theme ? theme === "dark" : !!window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

function startDish(canvas: HTMLCanvasElement, obstacles: () => DOMRect[], still: () => boolean, look: () => DishLook) {
  const g = canvas.getContext("2d");
  if (!g) return () => undefined;
  let W = 0, H = 0, cells: Cell[] = [], bonds: Bond[] = [], ripples: Ripple[] = [], t = 0, frame = 0;
  let activePointer: number | null = null;
  let rects: DOMRect[] = [];
  let drag: Cell | null = null, pointer = { x: -999, y: -999 }, last = { x: 0, y: 0, at: 0 };
  const make = (x: number, y: number): Cell => {
    const heading = Math.random() * 6.283, speed = 9 + Math.random() * 7;
    return { x, y, vx: 0, vy: 0, fx: 0, fy: 0, r: 9 + Math.random() * 9, heading, speed,
      phase: Math.random() * 6.283, violet: Math.random() < .3, look: { x: 0, y: 0 }, rippled: 0,
      ring: new Float32Array(RING), ringV: new Float32Array(RING), pvx: 0, pvy: 0, kx: 0, ky: 0, kvx: 0, kvy: 0 };
  };
  const inside = (x: number, y: number) => rects.some(r => x > r.left - 20 && x < r.right + 20 && y > r.top - 20 && y < r.bottom + 20);
  const resize = () => {
    rects = obstacles();
    const oldW = W, oldH = H;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    W = canvas.clientWidth; H = canvas.clientHeight; canvas.width = W * dpr; canvas.height = H * dpr; g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const n = Math.round(Math.min(34, Math.max(10, W * H / 38000)));
    if (cells.length && oldW && oldH) {
      for (const c of cells) { c.x *= W / oldW; c.y *= H / oldH; for (const rect of rects) pressOut(c, rect); }
      ripples = []; draw(); return;
    }
    cells = []; bonds = []; ripples = [];
    for (let tries = 0; cells.length < n && tries < n * 20; tries++) {
      const x = W * (.06 + Math.random() * .88), y = H * (.08 + Math.random() * .84);
      if (!inside(x, y)) cells.push(make(x, y));
    }
  };

  const step = (dt: number) => {
    rects = obstacles();
    t += dt;
    for (const c of cells) { c.fx = 0; c.fy = 0; }
    // Between cells: soft repulsion inside contact, weak adhesion a little beyond it, nothing further away.
    for (let i = 0; i < cells.length; i++) for (let j = i + 1; j < cells.length; j++) {
      const a = cells[i], b = cells[j], dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || .001, contact = a.r + b.r;
      const near = contact * 1.1, far = contact * 2.3;
      if (d >= far) continue;
      const f = d < near ? -REPEL * (near - d) / near : ADHERE * 4 * ((d - near) / (far - near)) * (1 - (d - near) / (far - near));
      const fx = dx / d * f, fy = dy / d * f;
      a.fx += fx; a.fy += fy; b.fx -= fx; b.fy -= fy;
      if (d < near) { const press = (near - d) / near; dent(a, dx / d, dy / d, press); dent(b, -dx / d, -dy / d, press); }
    }
    for (const rect of rects) for (const c of cells) fieldRect(c, rect);
    for (const c of cells) fieldDish(c);

    for (const b of bonds) {
      const dx = b.b.x - b.a.x, dy = b.b.y - b.a.y, d = Math.hypot(dx, dy) || 1, ux = dx / d, uy = dy / d;
      const opening = (b.b.vx - b.a.vx) * ux + (b.b.vy - b.a.vy) * uy, f = ((d - b.rest) * BOND_K + opening * BOND_DAMP) * dt;
      if (b.a !== drag) { b.a.vx += ux * f; b.a.vy += uy * f; }
      if (b.b !== drag) { b.b.vx -= ux * f; b.b.vy -= uy * f; }
    }
    for (const c of cells) {
      if (c === drag) continue;
      c.heading += (Math.sin(t * .25 + c.phase) * .4 + (Math.random() - .5) * .9) * dt;
      const tx = Math.cos(c.heading) * c.speed + c.fx, ty = Math.sin(c.heading) * c.speed + c.fy, k = Math.min(1, dt * 2.4);
      c.vx += (tx - c.vx) * k; c.vy += (ty - c.vy) * k;
      const v = Math.hypot(c.vx, c.vy); if (v > MAX_SPEED) { c.vx *= MAX_SPEED / v; c.vy *= MAX_SPEED / v; }
      c.x += c.vx * dt; c.y += c.vy * dt;
      c.rippled = Math.max(0, c.rippled - dt);
    }
    if (drag) { drag.x += (pointer.x - drag.x) * .35; drag.y += (pointer.y - drag.y) * .35; for (const rect of rects) pressOut(drag, rect); }
    for (let i = 0; i < cells.length; i++) for (let j = i + 1; j < cells.length; j++) { // never let two cells pass through each other
      const a = cells[i], b = cells[j], dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || .001, min = (a.r + b.r) * .78;
      if (d >= min) continue;
      const push = (min - d) / 2;
      if (a !== drag) { a.x -= dx / d * push; a.y -= dy / d * push; }
      if (b !== drag) { b.x += dx / d * push; b.y += dy / d * push; }
    }
    for (const c of cells) {
      // Springs and a fast pointer must never pull a body through the card or outside the viewport.
      for (const rect of rects) pressOut(c, rect);
      c.x = Math.max(c.r, Math.min(W - c.r, c.x)); c.y = Math.max(c.r, Math.min(H - c.r, c.y));
      jiggle(c, dt);
    }
    ripples = ripples.filter(r => (r.age += dt) < 1.2);
  };

  const dent = (c: Cell, ux: number, uy: number, amount: number) => {
    for (let i = 0; i < RING; i++) { const facing = DIRS[i][0] * ux + DIRS[i][1] * uy; if (facing > 0) c.ringV[i] -= DENT * amount * facing * facing; }
  };
  const jiggle = (c: Cell, dt: number) => {
    const ax = (c.vx - c.pvx), ay = (c.vy - c.pvy); c.pvx = c.vx; c.pvy = c.vy;
    for (let i = 0; i < RING; i++) {
      const along = DIRS[i][0] * ax + DIRS[i][1] * ay;
      c.ringV[i] += (-RING_K * c.ring[i] - RING_D * c.ringV[i]) * dt - along * .004;
      c.ring[i] = Math.max(-.32, Math.min(.26, c.ring[i] + c.ringV[i] * dt));
    }
    // Volume is roughly kept: what one side loses, the rest bulges.
    let mean = 0; for (let i = 0; i < RING; i++) mean += c.ring[i]; mean /= RING;
    for (let i = 0; i < RING; i++) c.ring[i] -= mean * .5;
    c.kvx += (-60 * c.kx - 6 * c.kvx) * dt - ax * .02; c.kvy += (-60 * c.ky - 6 * c.kvy) * dt - ay * .02;
    c.kx = Math.max(-.25, Math.min(.25, c.kx + c.kvx * dt)); c.ky = Math.max(-.25, Math.min(.25, c.ky + c.kvy * dt));
  };

  // Near the card and the logo a field pushes cells away, growing smoothly as they approach.
  const fieldRect = (c: Cell, r: DOMRect) => {
    const radius = 24;
    const qx = Math.max(r.left + radius, Math.min(r.right - radius, c.x)), qy = Math.max(r.top + radius, Math.min(r.bottom - radius, c.y));
    let dx = c.x - qx, dy = c.y - qy, d = Math.hypot(dx, dy);
    if (d < .001) { dx = 0; dy = -1; d = 1; }
    const gap = d - radius - c.r;
    if (gap >= FIELD) return;
    const nx = dx / d, ny = dy / d, depth = 1 - Math.max(0, gap) / FIELD, f = WALL * depth * depth + (gap < 0 ? -gap * 6 : 0);
    c.fx += nx * f; c.fy += ny * f;
    if (depth > .45) dent(c, -nx, -ny, (depth - .45) * 1.4);
    if (depth > .7 && c !== drag) {
      if (!c.rippled && ripples.length < 8) { ripples.push({ x: qx + nx * radius, y: qy + ny * radius, age: 0, rect: r }); c.rippled = 3; }
    }
    if (gap < 0 && c !== drag) { c.x += nx * -gap * .5; c.y += ny * -gap * .5; }
  };
  const pressOut = (c: Cell, r: DOMRect) => {
    const radius = 24;
    const qx = Math.max(r.left + radius, Math.min(r.right - radius, c.x)), qy = Math.max(r.top + radius, Math.min(r.bottom - radius, c.y));
    let dx = c.x - qx, dy = c.y - qy, d = Math.hypot(dx, dy);
    const inside = c.x > r.left && c.x < r.right && c.y > r.top && c.y < r.bottom;
    if (d < .001 || inside) { // the centre crossed the edge: push back out through the nearest side
      const sides = [[c.x - r.left, -1, 0], [r.right - c.x, 1, 0], [c.y - r.top, 0, -1], [r.bottom - c.y, 0, 1]].sort((a, b) => a[0] - b[0]);
      dx = sides[0][1]; dy = sides[0][2]; d = 1;
      c.x = sides[0][1] ? (sides[0][1] < 0 ? r.left : r.right) : c.x; c.y = sides[0][2] ? (sides[0][2] < 0 ? r.top : r.bottom) : c.y;
      return pressOut(c, r);
    }
    const nx = dx / d, ny = dy / d, surface = radius + c.r * .8; // a pressed cell may flatten a little against the glass
    if (d >= surface) return;
    c.x = qx + nx * surface; c.y = qy + ny * surface;
    const want = (pointer.x - qx) * nx + (pointer.y - qy) * ny; // how far the pointer is pushing past the surface
    if (c === drag) dent(c, -nx, -ny, Math.min(1.4, Math.max(.2, (surface - want) / c.r)) * .5);
  };
  const fieldDish = (c: Cell) => {
    const ax = W * .52, ay = H * .55, ex = (c.x - W / 2) / ax, ey = (c.y - H / 2) / ay, e = Math.hypot(ex, ey);
    if (e < .9) return;
    const depth = Math.min(1.5, (e - .9) / .1);
    c.fx -= ex / e * WALL * depth; c.fy -= ey / e * WALL * depth;
  };

  const bondLine = (bond: Bond) => { // a goo strand: about 5 px at rest, thinner when stretched, thicker when pressed
    const { a, b } = bond, stretch = Math.min(1.6, (Math.hypot(b.x - a.x, b.y - a.y) || 1) / bond.rest);
    const grad = g.createLinearGradient(a.x, a.y, b.x, b.y);
    grad.addColorStop(0, "rgba(140,190,188,.85)"); grad.addColorStop(1, "rgba(168,140,242,.75)");
    g.strokeStyle = grad; g.lineWidth = Math.max(2.5, 9 - stretch * 4); g.lineCap = "round";
    g.beginPath(); g.moveTo(a.x, a.y); g.lineTo(b.x, b.y); g.stroke();
  };
  const strand = (a: Cell, b: Cell, alpha: number, width: number) => {
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2 + Math.sin(t * .8 + a.phase) * 4;
    const grad = g.createLinearGradient(a.x, a.y, b.x, b.y);
    grad.addColorStop(0, `rgba(127,180,176,${alpha})`); grad.addColorStop(1, `rgba(168,140,242,${alpha})`);
    g.strokeStyle = grad; g.lineWidth = width; g.lineCap = "round";
    g.beginPath(); g.moveTo(a.x, a.y); g.quadraticCurveTo(mx, my, b.x, b.y); g.stroke();
  };
  const drawCell = (c: Cell) => {
    const p = c.violet ? VIOLET : TEAL, r = c.r;
    const isDark = dark(), opal = look() === "opal";
    g.globalAlpha = isDark ? .82 : 1;
    g.save(); g.translate(c.x, c.y);
    const pts = DIRS.map(([dx, dy], i) => { const rr = r * (1 + c.ring[i] + .035 * Math.sin(i * 1.7 + t * 1.5 + c.phase)); return [dx * rr, dy * rr] as const; });
    g.beginPath();
    for (let i = 0; i <= RING; i++) { // quadratic curves through midpoints keep the jelly outline smooth
      const a = pts[i % RING], b = pts[(i + 1) % RING], mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
      if (i === 0) g.moveTo(mx, my); else g.quadraticCurveTo(a[0], a[1], mx, my);
    }
    g.closePath();
    const body = g.createRadialGradient(-r * .35, -r * .45, r * .05, 0, 0, r * 1.05);
    body.addColorStop(0, p[0]); body.addColorStop(.28, p[1]); body.addColorStop(.72, opal && !c.violet ? "#c3d8e9" : p[2]); body.addColorStop(1, p[3]);
    g.fillStyle = body; g.fill(); g.strokeStyle = p[4]; g.lineWidth = 1; g.stroke();
    const lx = (c.look.x * .15 + c.kx) * r, ly = (c.look.y * .15 + c.ky) * r, nucleus = g.createRadialGradient(lx - r * .1, ly - r * .12, 1, lx, ly, r * .42);
    nucleus.addColorStop(0, p[5]); nucleus.addColorStop(1, p[6]);
    g.fillStyle = nucleus; g.beginPath(); g.arc(lx, ly, r * .36, 0, 6.283); g.fill();
    g.fillStyle = "rgba(255,255,255,.8)"; g.beginPath(); g.ellipse(-r * .38, -r * .45, r * .17, r * .09, -.6, 0, 6.283); g.fill();
    g.restore(); g.globalAlpha = 1;
  };
  const drawRipple = (rp: Ripple) => { // a faint ring in the medium where a cell met the card, never drawn over the card
    const k = rp.age, R = 6 + 30 * k, r = rp.rect;
    g.save(); g.beginPath(); g.rect(0, 0, W, H); g.roundRect(r.left, r.top, r.width, r.height, 24); g.clip("evenodd");
    g.strokeStyle = `rgba(127,180,176,${.45 * (1 - k)})`; g.lineWidth = 1.5; g.beginPath(); g.arc(rp.x, rp.y, R, 0, 6.283); g.stroke();
    g.restore();
  };
  const drawRim = () => {
    const isDark = dark();
    g.lineWidth = 2; g.strokeStyle = isDark ? "rgba(140,170,175,.18)" : "rgba(150,185,190,.35)";
    g.beginPath(); g.ellipse(W / 2, H / 2, W * .56, H * .6, 0, 0, 6.283); g.stroke();
    g.lineWidth = 6; g.strokeStyle = isDark ? "rgba(255,255,255,.05)" : "rgba(255,255,255,.7)";
    g.beginPath(); g.ellipse(W / 2, H / 2, W * .545, H * .585, 0, 3.6, 4.5); g.stroke();
  };
  const draw = () => {
    g.clearRect(0, 0, W, H);
    for (const c of cells) {
      const dx = pointer.x - c.x, dy = pointer.y - c.y, d = Math.hypot(dx, dy) || 1, k = Math.min(1, 160 / d);
      c.look.x += (dx / d * k - c.look.x) * .08; c.look.y += (dy / d * k - c.look.y) * .08;
    }
    cells.forEach((a, i) => cells.filter(b => b !== a).map(b => ({ b, d: Math.hypot(b.x - a.x, b.y - a.y) })).filter(o => o.d < NEAR)
      .sort((p, q) => p.d - q.d).slice(0, 2).forEach(({ b, d }) => { if (cells.indexOf(b) > i && !linked(a, b)) strand(a, b, .55 * (1 - d / NEAR), 1.3); }));
    if (drag) { // where the dragged cell would hold on
      g.setLineDash([4, 6]); g.strokeStyle = "rgba(31,143,133,.6)"; g.lineWidth = 2; g.lineCap = "round";
      for (const o of holds(drag)) { g.beginPath(); g.moveTo(drag.x, drag.y); g.lineTo(o.x, o.y); g.stroke(); }
      g.setLineDash([]);
    }
    bonds.forEach(bondLine);
    ripples.forEach(drawRipple);
    cells.forEach(c => drawCell(c));
    drawRim();
  };
  const linked = (a: Cell, b: Cell) => bonds.some(x => (x.a === a && x.b === b) || (x.a === b && x.b === a));
  const holds = (c: Cell) => cells.filter(o => o !== c && !linked(c, o)).map(o => ({ o, d: Math.hypot(o.x - c.x, o.y - c.y) }))
    .filter(h => h.d < ATTACH).sort((p, q) => p.d - q.d).slice(0, HOLDS).map(h => h.o);

  let previous = performance.now();
  const loop = (now: number) => {
    frame = 0;
    if (document.hidden) return;
    const dt = Math.min(.033, (now - previous) / 1000); previous = now;
    if (!still()) step(dt);
    draw();
    if (!still()) frame = requestAnimationFrame(loop);
  };
  const refresh = () => {
    cancelAnimationFrame(frame); frame = 0; previous = performance.now();
    if (!document.hidden) { draw(); if (!still()) frame = requestAnimationFrame(loop); }
  };

  const at = (e: PointerEvent) => { const box = canvas.getBoundingClientRect(); return { x: e.clientX - box.left, y: e.clientY - box.top }; };
  const hit = (p: { x: number; y: number }) => cells.find(c => Math.hypot(c.x - p.x, c.y - p.y) < c.r + 8);
  const down = (e: PointerEvent) => {
    if (activePointer !== null || e.button !== 0 || e.isPrimary === false) return;
    pointer = at(e); drag = hit(pointer) ?? null;
    if (drag) { activePointer = e.pointerId; canvas.setPointerCapture?.(e.pointerId); canvas.style.cursor = "grabbing"; last = { ...pointer, at: performance.now() }; }
  };
  const move = (e: PointerEvent) => {
    if (activePointer !== null && e.pointerId !== activePointer) return;
    const p = at(e);
    if (drag) { const now = performance.now(), dt = Math.max(1, now - last.at) / 1000; drag.vx = (p.x - last.x) / dt; drag.vy = (p.y - last.y) / dt; last = { ...p, at: now }; }
    pointer = p;
    if (still() && drag) {
      drag.x = p.x; drag.y = p.y; rects = obstacles();
      for (const rect of rects) pressOut(drag, rect);
      drag.x = Math.max(drag.r, Math.min(W - drag.r, drag.x)); drag.y = Math.max(drag.r, Math.min(H - drag.r, drag.y));
      draw();
    }
    if (!drag) canvas.style.cursor = hit(p) ? "grab" : "";
  };
  const up = (e: PointerEvent) => {
    if (e.pointerId !== activePointer) return;
    if (drag) {
      for (const target of holds(drag)) {
        const dx = target.x - drag.x, dy = target.y - drag.y, d = Math.hypot(dx, dy) || 1;
        bonds.push({ a: drag, b: target, rest: Math.min(MAX_REST, Math.max(d, drag.r + target.r + 8)) });
        dent(drag, -dx / d, -dy / d, .9); dent(target, dx / d, dy / d, .9); // both squish as the strand snaps on
      }
      const v = Math.hypot(drag.vx, drag.vy), cap = 90; if (v > cap) { drag.vx *= cap / v; drag.vy *= cap / v; } // a gentle push; the medium soon stills it
      drag.heading = Math.atan2(drag.vy, drag.vx);
      for (let i = 0; i < RING; i++) drag.ringV[i] += (Math.random() - .5) * 1.2;
    }
    release(); if (still()) draw();
  };
  const release = () => {
    const id = activePointer; activePointer = null; drag = null; canvas.style.cursor = "";
    if (id !== null && canvas.hasPointerCapture?.(id)) canvas.releasePointerCapture(id);
  };
  const cancel = (e: PointerEvent) => { if (e.pointerId === activePointer) { release(); if (still()) draw(); } };
  const leave = () => { pointer = { x: -999, y: -999 }; };

  const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  const scheme = window.matchMedia?.("(prefers-color-scheme: dark)");
  const observer = new MutationObserver(refresh);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  observer.observe(canvas, { attributes: true, attributeFilter: ["data-look"] });
  resize();
  reduce?.addEventListener("change", refresh); scheme?.addEventListener("change", refresh);
  document.addEventListener("visibilitychange", refresh);
  canvas.addEventListener("pointercancel", cancel); canvas.addEventListener("lostpointercapture", cancel);
  window.addEventListener("blur", release);
  window.addEventListener("resize", resize);
  canvas.addEventListener("pointerdown", down); window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  canvas.addEventListener("pointerleave", leave);
  refresh();
  return () => {
    release(); observer.disconnect();
    reduce?.removeEventListener("change", refresh); scheme?.removeEventListener("change", refresh);
    document.removeEventListener("visibilitychange", refresh);
    canvas.removeEventListener("pointercancel", cancel); canvas.removeEventListener("lostpointercapture", cancel);
    window.removeEventListener("blur", release);
    cancelAnimationFrame(frame); window.removeEventListener("resize", resize);
    canvas.removeEventListener("pointerdown", down); window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up);
    canvas.removeEventListener("pointerleave", leave);
  };
}

export function DishBackground({ obstacles, look = "quiet" }: { obstacles: RefObject<HTMLElement | null>[]; look?: DishLook }) {
  const lookRef = useRef(look); lookRef.current = look;
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!canvas.current) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    return startDish(canvas.current,
      () => obstacles.flatMap(ref => ref.current ? [ref.current.getBoundingClientRect()] : []),
      () => !!reduce?.matches, () => lookRef.current);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return <canvas ref={canvas} className="wb-login-dish" data-look={look} aria-hidden="true" />;
}
